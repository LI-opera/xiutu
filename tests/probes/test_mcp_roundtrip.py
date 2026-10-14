import asyncio
import json
import socket
import subprocess
import sys
import time
from datetime import timedelta

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def test_real_mcp_roundtrip_disconnect(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "mcp-server.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "scripts/probes/mcp_server.py", str(port)],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert process.poll() is None, "MCP child exited before listening"
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("MCP child startup timed out")

            async def roundtrip():
                async with (
                    httpx.AsyncClient(timeout=3) as http_client,
                    streamable_http_client(url, http_client=http_client) as (read, write, _),
                ):
                    async with ClientSession(
                        read, write, read_timeout_seconds=timedelta(seconds=3)
                    ) as session:
                        initialized = await session.initialize()
                        tools = await session.list_tools()
                        assert [t.name for t in tools.tools] == ["probe_echo"]
                        assert (
                            tools.tools[0].inputSchema["properties"]["message"]["type"] == "string"
                        )
                        output = await session.call_tool(
                            "probe_echo", {"message": "wp01-synthetic"}
                        )
                        assert not output.isError
                        assert output.structuredContent == {"message": "wp01-synthetic"}
                        print(
                            json.dumps(
                                {
                                    "protocol": initialized.protocolVersion,
                                    "tool": tools.tools[0].model_dump(),
                                    "input": {"message": "wp01-synthetic"},
                                    "output": output.model_dump(),
                                },
                                ensure_ascii=False,
                            )
                        )

            asyncio.run(roundtrip())
            process.terminate()
            process.wait(timeout=10)

            async def disconnected():
                async with (
                    httpx.AsyncClient(timeout=2) as http_client,
                    streamable_http_client(url, http_client=http_client) as (read, write, _),
                ):
                    async with ClientSession(
                        read, write, read_timeout_seconds=timedelta(seconds=2)
                    ) as session:
                        await session.initialize()

            started = time.monotonic()
            try:
                asyncio.run(asyncio.wait_for(disconnected(), timeout=6))
            except (ExceptionGroup, httpx.HTTPError, TimeoutError, OSError) as error:

                def leaves(exc):
                    if isinstance(exc, BaseExceptionGroup):
                        return [leaf for child in exc.exceptions for leaf in leaves(child)]
                    return [exc]

                assert any(
                    isinstance(leaf, (httpx.ConnectError, httpx.ConnectTimeout))
                    for leaf in leaves(error)
                )
                duration = time.monotonic() - started
                assert duration < 8
                print(
                    json.dumps(
                        {
                            "disconnect_error": type(error).__name__,
                            "leaf_errors": [type(leaf).__name__ for leaf in leaves(error)],
                            "seconds": duration,
                        }
                    )
                )
            else:
                raise AssertionError("Disconnected MCP endpoint unexpectedly succeeded")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
