from asyncio import StreamReader, StreamWriter
from asyncio.exceptions import TimeoutError
from io import BytesIO
from logging import LoggerAdapter
from typing import Any, Optional, Union, cast

from enochecker3 import (
    DependencyInjector,
    AsyncSocket,
)

async def timed(promise: Any, logger: LoggerAdapter, ctx: str) -> Any:
    logger.debug("START: {}".format(ctx))
    start = time.time()
    result = await promise
    end = time.time()
    logger.debug("DONE:  {} (took {:.3f} seconds)".format(ctx, end - start))
    return result


class Session:
    def __init__(self, socket: AsyncSocket, logger: LoggerAdapter) -> None:
        socket_tuple = cast(tuple[StreamReader, StreamWriter], socket)
        self.reader = socket_tuple[0]
        self.writer = socket_tuple[1]
        self.logger = logger
        self.closed = False

    async def __aenter__(self) -> "Session":
        self.logger.debug("Preparing session")
        await self.prepare()
        return self

    async def __aexit__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        self.logger.debug("Closing session")
        await self.close()

    async def readuntil(self, target: bytes, ctx: Optional[str] = None) -> bytes:
        try:
            ctxstr = f"readuntil {target!r}" if ctx is None else ctx
            data = await timed(self.reader.readuntil(target), self.logger, ctx=ctxstr)
            msg = f"read:  {data[:100]!r}{'..' if len(data) > 100 else ''}"
            self.logger.debug(msg)
            return data
        except TimeoutError:
            self.logger.critical(f"Service timed out while waiting for {target!r}")
            raise MumbleException("Service took too long to respond")

    async def readline(self, ctx: Optional[str] = None) -> bytes:
        return await self.readuntil(b"\n", ctx=ctx)

    async def read(self, n: int, ctx: Optional[str] = None) -> bytes:
        try:
            ctxstr = f"reading {n} bytes" if ctx is None else ctx
            data = await timed(self.reader.readexactly(n), self.logger, ctx=ctxstr)
            msg = f"read:  {data[:60]!r}{'..' if len(data) > 60 else ''}"
            self.logger.debug(msg)
            return data
        except TimeoutError:
            self.logger.critical(f"Service timed out while reading {n} bytes")
            raise MumbleException("Service took too long to respond")

    async def drain(self) -> None:
        await self.writer.drain()

    def write(self, data: bytes) -> None:
        msg = f"write: {data[:60]!r}{'..' if len(data) > 60 else ''}"
        self.logger.debug(msg)
        self.writer.write(data)

    async def prepare(self) -> None:
        await self.readuntil(prompt)

    async def exit(self) -> None:
        if self.closed:
            return
        self.write(b"exit\n")
        await self.drain()
        await self.readuntil(b"bye!")
        await self.close()

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.writer.close()
        await self.writer.wait_closed()


