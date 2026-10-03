bambinotes
==========

Authors:

* mmunier (Marc Munier)

Categories:

* pwn


Overview
--------

A terminal note-taking service written for
[Bambi CTF](https://ctftime.org/ctf/494/).

xinetd serves the compiled binary over TCP. The `SERVICE_PORT` variable sets
the port and the default is 9000. Each connection gets its own process and an
`alarm(120)` timeout.

The unauthenticated menu has two options. Register reads a username and a
password. The service creates the directory `/service/data/<username>/` and
writes the password to the file `passwd` in it. Login reads that file and
compares the stored password with the one the user sends. `sanitize_string()`
replaces `.`, `/` and newline with a null byte in every username, password and
filename. A value therefore ends at the first such character.

A logged-in user works with ten note slots in memory. Slot 0 holds a default
note after each login. Create writes a new note into an empty slot. Delete
frees a slot.

Save writes the note in a slot to a file in the directory of the user. Load
reads a file from that directory into a slot. List Saved prints the slots in
memory and the filenames in the directory. The Print option does nothing.

Note files expire. A loop in the service entrypoint deletes the data files
older than 30 minutes every 60 seconds.

### Flag Store 1

The service keeps a flag in a note that a checker user saves to a file. The
checker reads the flag back with Load and List Saved. The attack info is the
username.


Vulnerabilities
---------------

### Flag Store 1, Vuln 1

`load_note()` reads up to `NOTE_SIZE` (0x60) bytes into the buffer of a slot.
It then writes a terminator at `note[bytes_read]`. Two buffers are too small
for that read.

Slot 0 holds the default note, and `init_user()` allocates that buffer with
`calloc(1, sizeof(DEFAULT_NOTE))`. The size is 0x37 bytes. A file that we load
into slot 0 runs off the end of that chunk and into the `struct User` behind
it. The first member of the structure is `username[40]`.

We can write a note that holds 0x40 filler bytes and the name of a victim. We
save that note to a file and load the file into slot 0. The service then builds
every path from the name of the victim. List Saved and Load then show and read
the notes of the victim.

A file of exactly `NOTE_SIZE` bytes also writes the terminator one byte past a
buffer of full size.

* Difficulty: medium
* Discoverability: medium
* Patchability: medium
* Categories: pwn
* Checker exploit: `exploit_heap_overflow`, variant id 0


Patches
-------

### Flag Store 1, Vuln 1

We can mitigate the vulnerability with two changes. Give the default note a
buffer of `NOTE_SIZE` bytes. Stop the read one byte short, so that the
terminator stays in the buffer. Notes that the menu creates come from
`fgets(.., NOTE_SIZE, ..)` and already stop at `NOTE_SIZE - 1`. The shorter
read therefore truncates no legitimate note.

### Patch files

Players receive the compiled service and not its source. The fix therefore
changes the shipped binary.

* `patches/0-heap-overflow` applies the fix for exploit variant 0. The file is
  a shell script that rewrites two immediates in `bambi-notes`: the allocation
  size in `init_user()` and the read count in `load_note()`. `enochecker_test`
  runs the script with the working directory set to a copy of `service/`.
