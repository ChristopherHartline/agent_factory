"""
MCP Tool Servers — stdio-based tool infrastructure for Agent Factory.

Architecture:
    ┌──────────────┐     stdio      ┌──────────────┐
    │ Agent Runtime │ ──────────── │  Tool Server  │
    │ (LangGraph)  │  JSON-RPC    │  (subprocess) │
    └──────────────┘     pipes     └──────────────┘

Each tool server is a standalone process that communicates via
stdin/stdout using JSON-RPC 2.0 messages (the MCP protocol).

The StdioToolServer base class handles the transport.
Subclasses implement specific tools.

The ToolServerManager launches and manages server processes,
and provides LangChain-compatible tool wrappers that the
Agent Factory can register in its ToolRegistry.

Future: gRPC transport layer (swap StdioTransport for GrpcTransport
without changing tool implementations).
"""

from mcp_tools.server import StdioToolServer, ToolHandler
from mcp_tools.manager import ToolServerManager

# Bridge requires langchain — lazy import to keep servers standalone
def mcp_to_langchain_tool(*args, **kwargs):
    from mcp_tools.bridge import mcp_to_langchain_tool as _impl
    return _impl(*args, **kwargs)

def register_mcp_tools(*args, **kwargs):
    from mcp_tools.bridge import register_mcp_tools as _impl
    return _impl(*args, **kwargs)

__all__ = [
    "StdioToolServer",
    "ToolHandler",
    "ToolServerManager",
    "mcp_to_langchain_tool",
    "register_mcp_tools",
]
