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
            raise

        self.debug_log(f">>>\n {result}")
        return result

    async def readline(self):
        return await self.readuntil(b'\n')

    async def write(self, data: bytes):
        self.debug_log(f"<<<\n{data}")
        self.writer.write(data)
        await self.writer.drain()
        
    async def register(self, username, password):
        if self.state != BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("We're already authenticated")

        await self.readuntil(b"> ")
        
        await self.write(b"1\n")
        
        await self.readuntil(b"Username:\n> ")
        await self.write(username.encode() + b"\n")
        
        await self.readuntil(b"Password:\n> ")
        await self.write(password.encode() + b"\n")
        
        await self.readuntil(b"Registration successful!\n")
        self.state = (username, password)
    
    
    async def login(self, username, password):
        if self.state != BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("We're already authenticated")

        await self.readuntil(b"> ")
        await self.write(b"2\n")
        
        line = await self.readuntil(b"> ")
        assert_equals(line, b"Username:\n> ", "Login Failed!")
        await self.write(username.encode() + b"\n")
        
        line = await self.readuntil(b"> ")
        assert_equals(line, b"Password:\n> ", "Login Failed!")
        await self.write(password.encode() + b"\n")
        
        line = await self.readline()
        assert_equals(line, b"Login successful!\n", "Login Failed!")
        self.state = (username, password)

    async def create_note(self, idx: int, note_data: bytes):
        if self.state == BambiNoteClient.UNAUTHENTICATED:
            raise InternalErrorException("Trying invoke authenticated method in unauthenticated context")
        
        prompt = await self.readuntil(b"> ")
        await self.write(b"1\n")
        
        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Which slot to save the note into?\n> ", "Failed to create a new note")
        await self.write(f"{idx}\n".encode())
                
        prompt = await self.readline()
        assert_equals(prompt, f"Note [{idx}]\n".encode(), "Failed to create a new note")
        prompt = await self.reader.readexactly(2)
        assert_equals(prompt, b"> ", "Failed to create a new note")

        await self.write(note_data + b"\n")
        
        line = await self.readline()
        assert_equals(line, b"Note Created!\n", "Failed to create a new note")

    async def list_notes(self):
        self.assert_authenticated()

        notes = {}
        notes['saved'] = []

        prompt = await self.readuntil(b"> ")
        await self.write(b"3\n")
        
        await self.readuntil(f"\n\n===== [{self.state[0]}'s Notes] =====\n".encode())
        
        line = await self.readline()
        if line == b"Currently Loaded:\n":
            while True:
                line = await self.readline()
                
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
                line == await self.readline()
                if line == b"===== [End of Notes] =====\n":
                    return notes

                assert_equals(line[:3], b" | ", "Failed to list Notes!")
                filename = line[3:-1]
                notes['saved'].append(filename)
                
        return notes

    async def delete_note(self, idx):
        self.assert_authenticated()
        
        prompt = await self.readuntil(b"> ")
        await self.write(b"4\n")
        
        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"<Idx> of Note to delete?\n> ", "Failed to delete Note!")

        await self.write(f"{idx}\n".encode())
        await self.writer.flush()

        line = await self.readline()
        assert_equals(line, b"Note deleted\n", "Failed to delete Note!")

    async def load_note(self, idx: int, filename: str):
        self.assert_authenticated()
        
        prompt = await self.readuntil(b"> ")
        await self.write(b"5\n")
        
        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Which note to load?\nFilename > ", "Failed to delete Note!")
        await self.write(f"{filename}\n".encode())
        
        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Which slot should it be stored in?\n> ")
        await self.write(f"{filename}\n".encode())
        
    async def save_note(self, idx: int, filename: str):
        self.assert_authenticated()

        prompt = await self.readuntil(b"> ")
        await self.write(b"6\n")
        
        prompt = await self.readuntil(b"> ")
        assert_equals( prompt, b"Which note to save?\n> ", "Failed to save Note!")
        await self.write(f"{idx}\n".encode())
        
        line = await self.readline()
        assert_equals(line, b"Which file to save into?\n", "Failed to save Note!")
        prompt = await self.readuntil(b"> ")
        assert_equals(prompt, b"Filename > ", "Failed to save Note!")
        await self.write(f"{filename}\n".encode())
        
        line = await self.readline()
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