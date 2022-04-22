#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>

#define NL "\n"
#define STORAGE_DIR "/service/data/%s/%s"

#define NOTE_SIZE 0x60
#define DEFAULT_NOTE "Well, it's a note-taking service. What did you expect?"

#define NOTE_COUNT 10
#define VALID_NOTE_IDX(idx) ((idx >= 0) && (idx < NOTE_COUNT))

void setup() {
    setbuf(stdin, NULL);
    setbuf(stdout, NULL);
    setbuf(stderr, NULL);
    alarm(30);
}

long getlong() {
    char buf[40];
    char *endp = 0;
    fgets(buf, sizeof(buf), stdin);
    long retval = strtol(buf, &endp, 0);
    if (!retval) {
        if (endp == buf) retval = -1;
    }
    return retval;
}

#define FILTERED_CHARS "./\n"
void sanitize_string(char * input) {
    size_t offset = 0;
    while (input[offset] != 0)
    {
        size_t filter_offset = 0;
        while (FILTERED_CHARS[filter_offset] != 0)
        {
            if (input[offset] == FILTERED_CHARS[filter_offset]) {
                input[offset] = 0;
                // break? -- Maybe there are a few more options for exploits if it breaks here ...
            }
            filter_offset++;
        }
        offset++;
    }
}

struct User {
    char username[40];
    char *notes[NOTE_COUNT];
};

struct User* init_user() {
    char * base_note = calloc(1, sizeof(DEFAULT_NOTE));
    strcpy(base_note, DEFAULT_NOTE);

    struct User *user_ptr = calloc(1, sizeof(struct User));
    user_ptr->notes[0] = base_note;
    return user_ptr;
}

void delete_user(struct User *user) {
    for (int note_idx = NOTE_COUNT-1; note_idx >= 0; note_idx-- ) {
        if (user->notes[note_idx]) {
            free(user->notes[note_idx]);
            user->notes[note_idx] = 0;
        }
    }
    free(user);
}

struct User* user_register() {
    
    printf(
        "Username:\n> "
    );
    char username[40];
    if (!fgets(username, 40, stdin)) {
        perror("Failed to read username");
        exit(EXIT_FAILURE);
    }
    sanitize_string(username);

    char path_buf[sizeof(username) + sizeof(STORAGE_DIR) + 0x20];
    snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, username, "passwd");
    int access_result = access(path_buf, F_OK);
    
    if ( access_result != -1 ) {
        printf("Username already taken!\n");
        return 0;
    }
      
    printf(
        "Password:\n> "
    );
    char password[40];
    fgets(password, 40, stdin);
    
    snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, username, "");
    long res = mkdir(path_buf, 0775);
    if (res) {
        perror("Failed to create user directory!");
        exit(EXIT_FAILURE);
    }

    snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, username, "passwd");
    long fd = open(path_buf, O_WRONLY|O_CREAT, 0644);
    if (fd < 0) { 
        perror("Failed to create passwd file!");
        exit(EXIT_FAILURE);
    }

    sanitize_string(password);
    if (0 > write(fd, password, strlen(password))) {
        perror("Failed to write passwd file!");
        exit(EXIT_FAILURE);
    };
    close(fd);

    puts("Registration successful!");

    // Successful login
    struct User *user = init_user();
    strcpy(user->username, username);
    return user;
}

struct User* user_login() {

    printf(
        "Username:\n> "
    );
    char username[40];
    if (!fgets(username, 40, stdin)) {
        perror("Failed to read username");
        exit(EXIT_FAILURE);
    }
    sanitize_string(username);

    char path_buf[sizeof(username) + sizeof(STORAGE_DIR) + 0x20];
    snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, username, "passwd");
    int access_result = access(path_buf, F_OK | R_OK);
    
    if ( access_result < 0 ) {
        printf("User %s does not exist!\n", username);
        return 0;
    }
    
    char password_buf[40];
    long password_fd = open(path_buf, O_RDONLY);
    if (password_fd < 0) {
        return (struct User*) password_fd;
    }
    
    int bytes_read = read(password_fd, password_buf, sizeof(password_buf) -1 );
    if (bytes_read < 0) {
        perror("Failed to read passwd file!");
        exit(EXIT_FAILURE);
    }

    password_buf[bytes_read] = 0;
    close(password_fd);

    printf(
        "Password:\n> "
    );
    char user_password[40];
    fgets(user_password, 40, stdin);
        
    if (strcmp(password_buf, user_password)) {
        puts("Wrong password!");
        return 0;
    }

    puts("Login successful!");

    // Successful login
    struct User *user = init_user();
    strcpy(user->username, username);
    return user;
}

void main_menu() {
    printf(
        "===== [Unauthenticated] =====" NL
        "   1. Register" NL 
        "   2. Login" NL
        "> " 
    );
}

void authenticated_menu(struct User *user) {
    printf(
        "===== [%s] =====" NL
        "   1. Create" NL 
        "   2. Print" NL
        "   3. List Saved" NL
        "   4. Delete" NL
        "   5. Load" NL
        "   6. Save" NL
        "> ",
        user->username
    );
}

void create_note(struct User* user) {
    printf(
        "Which slot to save the note into?" NL
        "> "
    );
    long idx = getlong();
    if (!VALID_NOTE_IDX(idx)) {
        puts("Nice Try!");
        return;
    }
    if (user->notes[idx]) {
        puts("Already Occupied!");
        return;
    }

    user->notes[idx] = malloc(NOTE_SIZE);
    printf("Note [%ld]\n> ", idx);
    long result = fgets(user->notes[idx], NOTE_SIZE, stdin);
    int len = strlen(user->notes[idx]);
    if (user->notes[idx][len-1] == '\n') user->notes[idx][len-1] = 0;

    if (result == 0) {
        exit(EXIT_SUCCESS);
    }
    puts("Note Created!");
}

void list_saved_notes(struct User* user) {

    printf("\n\n===== [%s's Notes] =====\n", user->username);

    char table_header = 0;
    for (int note_idx = 0; note_idx < NOTE_COUNT; note_idx++) {
        if (user->notes[note_idx]) {
            if (!table_header) {
                printf("Currently Loaded:\n");
                table_header = 1;
            }
            printf("    %d | %s\n", note_idx, user->notes[note_idx]);
        }
    }


    // Dunno impl shell injection here?

    char path_buf[sizeof(user->username) + sizeof(STORAGE_DIR) + 0x20];
    snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, user->username, "");
    DIR* dirfd = opendir(path_buf);
    if (dirfd <= 0) {
        perror("Failed to open user directory");
        exit(EXIT_FAILURE);
    }

    table_header = 0;
    struct dirent* entry;
    while ((entry = readdir(dirfd)) != NULL) {
        if (strcmp(entry->d_name, "passwd") == 0) {
            continue;
        }

        if (!table_header) {
            printf("Saved Notes:\n");
            table_header = 1;
        }

        // Sendfile trolololo?...
        printf(" | %s\n", entry->d_name);
    }

    puts("===== [End of Notes] =====");
    closedir(dirfd);
}

void delete_note(struct User* user) {
    printf("<Idx> of Note to delete?\n> ");
    
    long note_idx = getlong();
    if (VALID_NOTE_IDX(note_idx)) {
        if (user->notes[note_idx]) {
            free(user->notes[note_idx]);
            user->notes[note_idx] = 0;
            puts("Note deleted!");
        } else {
            printf("Note %ld doesn't exist!\n", note_idx);
        }
    } else {
        puts("Invalid Idx!");
    }
}

void load_note(struct User* user) {
    printf(
        "Which note to load?" NL
        "Filename > "
    );
    
    char path_buf[sizeof(STORAGE_DIR) + sizeof(user->username) + 0x20];
    int bytes_written = snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, user->username, "");
    if (!fgets(path_buf + bytes_written, sizeof(path_buf) - bytes_written, stdin)) {
        perror("Failed to get filename!");
        return;
    }

    sanitize_string(path_buf + bytes_written);

    printf(
        "Which slot should it be stored in?" NL
        "> "
    );

    long idx = getlong();
    if (!VALID_NOTE_IDX(idx)) {
        puts("Invalid Idx!");
        return;
    } 

    if (user->notes[idx] == 0) {
        user->notes[idx] = calloc(1, NOTE_SIZE);
    }

    int filefd = open(path_buf, O_RDONLY);
    if (filefd < 0) {
        printf("Failed to open %s" NL, path_buf);
        return;
    }

    int bytes_read = read(filefd, user->notes[idx], NOTE_SIZE);  
    if (bytes_read < 0) {
        perror("Note read failed");
        exit(EXIT_FAILURE);
    }  
    close(filefd);

    user->notes[idx][bytes_read] = 0;
    printf("Note %s was loaded into Slot %ld." NL, path_buf, idx);
}

void save_note(struct User* user) {
    printf(
        "Which note to save?" NL
        "> "
    );
    
    long idx = getlong();
    if (!VALID_NOTE_IDX(idx)) {
        puts("Invalid Idx!");
        return;
    }

    if (!user->notes[idx]) {
        printf("Note %ld does not exist!\n", idx);
        return;
    }

    printf(
        "Which file to save into?" NL
        "Filename > "
    );

    char path_buf[sizeof(STORAGE_DIR) + sizeof(user->username) + 0x20];
    int bytes_written = snprintf(path_buf, sizeof(path_buf), STORAGE_DIR, user->username, "");
    if (!fgets(path_buf + bytes_written, sizeof(path_buf) - bytes_written, stdin)) {
        perror("Failed to get filename!");
    }
    sanitize_string(path_buf + bytes_written);
    
    // TODO: Sanitize path
    long filefd = open(path_buf, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (filefd < 0) {
        perror("Failed to open file!");
        exit(EXIT_FAILURE);
    }

    if (0 > write(filefd, user->notes[idx], strlen(user->notes[idx]))) {
        perror("Failed to write note!");
        exit(EXIT_FAILURE);
    }

    puts("Note saved!");
    close(filefd);
}

int main(int argc, const char * argv[]) {
    int menu_counter = 0;
    struct User* current_user = NULL;
    
    setup();
    puts("Welcome to Bambi-Notes!");

    while (1) {
        main_menu();
        long menu_option = getlong();
        menu_counter++;

        switch (menu_option)
        {
        case 0: 
            return 0;

        case 1:
            current_user = user_register();
            break;
        
        case 2:
            current_user = user_login();
            break;
        
        case 1337:
            puts("Nice Try!\nYeah this isn't going to do anything");
            break;
        case -1:
            return 0;
        default:
            break;
        }

        if (current_user != 0) break;
    }

    while (current_user > 0) {
        authenticated_menu(current_user);
        long menu_option = getlong();
        // menu_counter++;

        switch (menu_option)
        {
        case 0: 
            return 0;

        case 1:
            create_note(current_user);
            break;
        case 2:
            
            break;
        case 3:
            list_saved_notes(current_user);
            break;
        case 4:
            delete_note(current_user);
            break;
        case 5:
            load_note(current_user);
            break;
        case 6:
            save_note(current_user);
            break;
        case -1:
            return 0;
        default:
            break;
        }
    }

    puts("Bye!");
}