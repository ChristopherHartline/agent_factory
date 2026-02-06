"""
Echo MCP Tool Server — minimal reference implementation.

Use this as a template for building new tool servers.
It implements a single tool that echoes back its input,
useful for testing the transport layer.

Launch:
    python -m mcp_tools.servers.echo

Test:
    echo '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' | python -m mcp_tools.servers.echo
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp_tools.server import StdioToolServer, ToolHandler


class EchoTool(ToolHandler):
    name = "echo"
    description = "Echoes back the input message. Useful for testing."
    parameters = {
        "message": {
            "type": "string",
            "description": "The message to echo back",
        },
    }

    def handle(self, params: dict) -> dict:
        message = params.get("message", "")
        return {"echoed": message, "length": len(message)}


if __name__ == "__main__":
    server = StdioToolServer()
    server.register(EchoTool())
    server.run()
