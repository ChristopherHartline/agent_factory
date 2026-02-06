"""
Bridge between MCP tool servers and LangChain/Agent Factory.

This module converts MCP tool servers into LangChain tools
that can be registered in the Agent Factory's ToolRegistry.

Usage:
    from mcp_tools.bridge import mcp_to_langchain_tool, register_mcp_tools

    # Single tool
    lc_tool = mcp_to_langchain_tool(manager, "calculator", "calculate")
    tool_registry.register_langchain_tool("calculator", lc_tool)

    # All tools from all servers
    register_mcp_tools(manager, tool_registry)
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from mcp_tools.manager import ToolServerManager


def mcp_to_langchain_tool(
    manager: ToolServerManager,
    server_id: str,
    tool_name: str,
    description_override: str | None = None,
) -> StructuredTool:
    """
    Create a LangChain StructuredTool that wraps an MCP tool server call.

    The returned tool, when invoked by an agent, sends a JSON-RPC
    request to the specified tool server via stdio and returns the result.

    Args:
        manager: The ToolServerManager managing the server
        server_id: Which server the tool lives on
        tool_name: The tool name (as registered on the server)
        description_override: Optional override for the tool description

    Returns:
        A LangChain StructuredTool that proxies calls to the MCP server.
    """
    # Find the tool schema from discovered tools
    tools = manager.list_tools(server_id)
    tool_schema = next((t for t in tools if t["name"] == tool_name), None)

    if tool_schema:
        description = description_override or tool_schema.get("description", tool_name)
    else:
        description = description_override or f"MCP tool: {server_id}/{tool_name}"

    def _call_mcp(**kwargs: Any) -> str:
        """Proxy call to MCP tool server."""
        try:
            result = manager.call(server_id, tool_name, kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error calling {server_id}/{tool_name}: {e}"

    return StructuredTool.from_function(
        func=_call_mcp,
        name=tool_name,
        description=description,
    )


def register_mcp_tools(
    manager: ToolServerManager,
    tool_registry: Any,  # agent_factory.ToolRegistry (avoid circular import)
    domain_tags: dict[str, list[str]] | None = None,
    prompt_instructions: dict[str, str] | None = None,
) -> list[str]:
    """
    Discover all tools from all running MCP servers and register
    them in the Agent Factory's ToolRegistry.

    Args:
        manager: The ToolServerManager with running servers
        tool_registry: An Agent Factory ToolRegistry instance
        domain_tags: Optional {tool_name: [tags]} for categorization
        prompt_instructions: Optional {tool_name: instructions} for
                             system prompt injection

    Returns:
        List of registered tool IDs.
    """
    domain_tags = domain_tags or {}
    prompt_instructions = prompt_instructions or {}
    registered = []

    for server_id, running in manager.list_servers().items():
        if not running:
            continue

        for tool_schema in manager.list_tools(server_id):
            tool_name = tool_schema["name"]
            tool_id = f"{server_id}__{tool_name}" if server_id != tool_name else tool_name

            # Create LangChain wrapper
            lc_tool = mcp_to_langchain_tool(manager, server_id, tool_name)

            # Build prompt instructions from schema if not provided
            instructions = prompt_instructions.get(tool_name)
            if not instructions:
                instructions = _auto_prompt_instructions(tool_schema)

            # Register in Agent Factory
            tool_registry.register_langchain_tool(
                tool_id=tool_id,
                tool=lc_tool,
                prompt_instructions=instructions,
                domain_tags=domain_tags.get(tool_name, []),
            )

            registered.append(tool_id)

    return registered


def _auto_prompt_instructions(schema: dict) -> str:
    """Generate prompt instructions from an MCP tool schema."""
    name = schema.get("name", "unknown")
    description = schema.get("description", "")
    params = schema.get("parameters", {}).get("properties", {})

    lines = [f"## Tool: {name}", description, ""]
    if params:
        lines.append("Parameters:")
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "any")
            pdesc = pinfo.get("description", "")
            lines.append(f"  - {pname} ({ptype}): {pdesc}")

    return "\n".join(lines)
