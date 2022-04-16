from asyncio import StreamReader, StreamWriter
import asyncio
import random
import string

from typing import Optional
from logging import LoggerAdapter

from enochecker3 import (
    ChainDB,
    Enochecker,
    FlagSearcher,
    BaseCheckerTaskMessage,
    PutflagCheckerTaskMessage,
    GetflagCheckerTaskMessage,
    PutnoiseCheckerTaskMessage,
    GetnoiseCheckerTaskMessage,
    HavocCheckerTaskMessage,
    MumbleException,
    OfflineException,
    InternalErrorException,
    PutflagCheckerTaskMessage,
    AsyncSocket,
)

from enochecker3.utils import assert_equals, assert_in


SERVICE_PORT = 8204
checker = Enochecker("bambi-notes", SERVICE_PORT)
app = lambda: checker.app

CHARSET = string.ascii_letters + string.digits + "_-"
BANNER = b"Welcome to Bambi-Notes!\n"

class BambiNoteClient():
    UNAUTHENTICATED = 0
    
    state: "int | tuple[str, str]"
    task: BaseCheckerTaskMessage
    reader: StreamReader
    writer: StreamWriter

    def __init__(self, task, logger : Optional[LoggerAdapter]=None) -> None:
        self.state = self.UNAUTHENTICATED
        self.task = task
        self.logger = logger

    async def __aenter__(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.task.address, SERVICE_PORT) 
        except:
            raise OfflineException("Failed to establish a service connection!")

        self.logger.info("Connected!")
        await self.readuntil(BANNER)
        return self

    async def __aexit__(self, *args):
        self.writer.close()
        await self.writer.wait_closed()

    async def assert_authenticated(self):
        if self.state == BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("Trying invoke authenticated method in unauthenticated context")

    async def check_prompt(self):
        pass
    
    def debug_log(self, *args, **kwargs):
        if self.logger is not None:
            self.logger.debug(*args, **kwargs)

    async def readuntil(self, separator=b'\n', *args, **kwargs):
        self.debug_log(f"reading until {separator}")
        try:
            result = await self.reader.readuntil(separator, *args, **kwargs)
        except Exception as e:
            self.debug_log(f"Failed client readuntil: {e}")

        self.debug_log(f">>>\n {result}")
        return result

    async def register(self, username, password):
        if self.state != BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("We're already authenticated")

        await self.readuntil(b"> ")
        
        self.writer.write(b"1\n")
        await self.writer.drain()

        await self.readuntil(b"Username:\n> ")
        self.writer.write(username.encode() + b"\n")
        await self.writer.drain()

        await self.readuntil(b"Password:\n> ")
        self.writer.write(password.encode() + b"\n")
        await self.writer.drain()

        await self.readuntil(b"Registration successful!\n")
        self.state = (username, password)
    
    
    async def login(self, username, password):
        if self.state != BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("We're already authenticated")

        await self.readuntil(b"> ")
        self.writer.write(b"2\n")
        await self.writer.drain()

        line = await self.readuntil(b"> ")
        assert_in(line, b"Username:\n", "Login Failed!")
        self.writer.write(username.encode() + b"\n")
        await self.writer.drain()

        line = await self.readuntil(b"> ")
        assert_in(line, b"Password:\n", "Login Failed!")
        self.writer.write(password.encode() + b"\n")
        await self.writer.drain()

        line = await self.reader.readline()
        assert_in(line, b"Login successful!", "Login Failed!")
        self.state = (username, password)

    async def create_note(self, idx: int, note_data: bytes):
        if self.state == BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("Trying invoke authenticated method in unauthenticated context")
        
        prompt = await self.readuntil(b"> ")
        self.writer.write(b"1\n")
        await self.writer.drain()

        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Which slot to save the note into?\n> ", "Failed to create a new note")
        self.writer.write(f"{idx}\n".encode())
        await self.writer.drain()
        
        prompt = await self.reader.readline()
        assert_equals(prompt, f"Note [{idx}]\n".encode(), "Failed to create a new note")
        prompt = await self.reader.readexactly(2)
        assert_equals(prompt, b"> ", "Failed to create a new note")

        self.writer.write(note_data)
        await self.writer.drain()

        line = await self.reader.readline()
        assert_equals(line, b"Note Created!", "Failed to create a new note")

    async def list_notes(self):
        self.assert_authenticated()

        notes = {}
        notes['saved'] = []

        prompt = await self.readuntil(b"> ")
        self.writer.write(b"3\n")
        await self.writer.drain()

        await self.readuntil(f"\n\n===== [{self.state[0]}'s Notes] =====\n".encode())
        
        line = await self.reader.readline()
        if line == b"Currently Loaded:\n":
            while True:
                line = await self.reader.readline()
                
                if line == b"Saved Notes:\n":
                    break

                if line == b"===== [End of Notes] =====\n":
                    return notes
                
                assert_equals(line[:4], b"    ", "Failed to list Notes!")
                assert_equals(line[-1], 0xa,     "Failed to list Notes!")
                idx, text = (line[4:-1].split(" | ", maxsplit=1))
                
                try:
                    notes[int(idx)] = text
                except ValueError:
                    raise MumbleException("Failed to list Notes!")

        if line == b"Saved Notes:\n":
            while True:
                line == await self.reader.readline()
                if line == b"===== [End of Notes] =====\n":
                    return notes

                assert_equals(line[:3], b" | ", "Failed to list Notes!")
                filename = line[3:-1]
                notes['saved'].append(filename)
                
        return notes

    async def delete_note(self, idx):
        self.assert_authenticated()
        
        prompt = await self.readuntil(b"> ")
        self.writer.write(b"4\n")
        await self.writer.drain()

        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"<Idx> of Note to delete?\n> ", "Failed to delete Note!")

        self.writer.write(f"{idx}\n".encode())
        await self.writer.flush()

        line = await self.reader.readline()
        assert_equals(line, b"Note deleted\n", "Failed to delete Note!")

    async def load_note(self, idx: int, filename: str):
        self.assert_authenticated()
        
        prompt = await self.readuntil(b"> ")
        self.writer.write(b"5\n")
        await self.writer.drain()

        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Which note to load?\nFilename > ", "Failed to delete Note!")
        self.writer.write(f"{filename}\n".encode())
        await self.writer.drain()

        prompt = self.readuntil(b"> ")
        assert_equals(prompt, b"Which slot should it be stored in?\n> ")
        self.writer.write(f"{filename}\n".encode())
        await self.writer.drain()

    async def save_note(self, idx: int, filename: str):
        self.assert_authenticated()

        prompt = await self.readuntil(b"> ")
        self.writer.write(b"6\n")
        await self.writer.drain()

        prompt = await self.readuntil("> ")
        assert_equals( prompt, b"Which note to save?\n> ", "Failed to save Note!")
        self.writer.write(f"{idx}\n".encode())
        await self.writer.drain()

        line = await self.reader.readline()
        #if line == 
        assert_equals(line, b"Which file to save into?\n", "Failed to save Note!")
        prompt = await self.readuntil("> ")
        assert_equals(prompt, b"> ", "Failed to save Note!")
        self.writer.write(f"{filename}\n".encode())
        await self.writer.drain()

        line = self.reader.readline()
        assert_equals(line, b"Note saved!\n", "Failed to save Note!")


def gen_random_str(k=16):
    return ''.join(random.choices(CHARSET, k=k))

def generate_creds(exploit_fake=False, namelen=16):
    # if exploit_fake
    username = ''.join(random.choices(CHARSET, k=namelen))
    password = ''.join(random.choices(CHARSET, k=namelen))
    return (username, password)

@checker.putflag(0)
async def putflag_test(
    task: PutflagCheckerTaskMessage,
    db: ChainDB,
    logger: LoggerAdapter
) -> None:

    logger.debug("TESTTEST123!")
    username, password = generate_creds()
    idx = random.randint(1, 9)
    filename = gen_random_str()
    await db.set("flag_info", (username, password, idx, filename))
    
    async with BambiNoteClient(task, logger) as client:
        await client.register(username, password)
        await client.create_note(idx, task.flag.encode())
        await client.save_note(idx, filename)

    return username

@checker.getflag(0)
async def getflag_test(
    task: GetflagCheckerTaskMessage, db: ChainDB, logger: LoggerAdapter
) -> None:
    try:
        username, password, _, filename = await db.get("flag_info")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")

    idx = random.randint(1,9)
    async with BambiNoteClient(task, logger) as client:
        await client.login(username, password)
        await client.load_note(filename, idx)

        note_list = await client.list_notes()
        try:
            assert note_list[idx] == task.flag.enocde()
        except:
            MumbleException("Flag not found!") 
        

@checker.putnoise(0)
async def putnoise0(task: PutnoiseCheckerTaskMessage):
    pass

@checker.putnoise(1)
async def putnoise1(task: PutnoiseCheckerTaskMessage):
    pass

@checker.getnoise(0)
async def getnoise0(task: GetnoiseCheckerTaskMessage):
    pass

@checker.getnoise(1)
async def getnoise1(task: GetnoiseCheckerTaskMessage):
    pass

@checker.havoc(0)
async def havoc0(task: HavocCheckerTaskMessage):
    pass

@checker.havoc(1)
async def havoc1(task: HavocCheckerTaskMessage):
    pass

@checker.havoc(2)
async def havoc2(task: HavocCheckerTaskMessage):
    pass



@checker.exploit(0)
async def exploit_test(searcher: FlagSearcher, sock: AsyncSocket) -> Optional[str]:
    r = await client.get(
        "/note/*",
    )
    assert not r.is_error

    if flag := searcher.search_flag(r.text):
        return flag

if __name__ == "__main__":
    checker.run()