"""Local-only MCP transport probe; contains no product tools."""

import sys

from mcp.server.fastmcp import FastMCP

server = FastMCP("xiutu-wp01-probe", host="127.0.0.1", port=int(sys.argv[1]), json_response=True)


@server.tool()
def probe_echo(message: str) -> dict[str, str]:
    """Echo synthetic input to verify MCP transport."""
    return {"message": message}


server.run(transport="streamable-http")
