"""THROWAWAY: localhost-only HTTP peers that intentionally never finish."""
import asyncio
import time


class Servers:
    def __init__(self):
        self.servers = {}
        self.tasks = set()
        self.connections = []

    async def start(self):
        for scenario in "ABC":
            self.servers[scenario] = await asyncio.start_server(
                lambda r, w, s=scenario: self.accept(s, r, w), "127.0.0.1", 0
            )
        return self

    def url(self, scenario):
        port = self.servers[scenario].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}/infer"

    def accept(self, scenario, reader, writer):
        task = asyncio.create_task(self.handle(scenario, reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def handle(self, scenario, reader, writer):
        record = {"scenario": scenario, "accepted": time.monotonic(), "eof": False,
                  "body_bytes": 0, "body_times": []}
        self.connections.append(record)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next((int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n")
                           if line.lower().startswith(b"content-length:")), 0)
            await reader.readexactly(length)
            if scenario != "A":
                # Chunked framing permits a genuinely unbounded response body.
                writer.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                             b"Content-Type: application/octet-stream\r\n\r\n")
                await writer.drain()
            if scenario == "B":
                writer.write(b"4\r\npart\r\n")
                await writer.drain()
                record["body_bytes"] = 4
                record["body_times"].append(time.monotonic())
            if scenario == "C":
                while True:
                    # Watch peer EOF while waiting; never terminate the body ourselves.
                    try:
                        data = await asyncio.wait_for(reader.read(1), 10)
                        if not data:
                            record["eof"] = True
                            break
                        raise AssertionError("Unexpected bytes after POST body")
                    except TimeoutError:
                        writer.write(b"1\r\nx\r\n")
                        await writer.drain()
                        record["body_bytes"] += 1
                        record["body_times"].append(time.monotonic())
            else:
                assert await reader.read() == b""
                record["eof"] = True
        finally:
            writer.close()
            await writer.wait_closed()
            record["transport_closed"] = writer.transport.is_closing()
            record["closed"] = time.monotonic()

    async def settled(self):
        # Do not cancel handlers: require real peer EOF to finish them.
        if self.tasks:
            await asyncio.wait_for(asyncio.gather(*list(self.tasks)), 2)
        assert all(r.get("eof") and r.get("transport_closed") for r in self.connections)

    async def close(self):
        for server in self.servers.values():
            server.close()
            await server.wait_closed()
        await self.settled()
