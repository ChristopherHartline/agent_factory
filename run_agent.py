"""
Run Agent — end-to-end: MCP servers → Factory → Live Agent.

This is the script that closes the loop. It:
1. Starts real MCP tool servers (stdio subprocesses)
2. Bridges them into LangChain tools
3. Registers them in the Agent Factory's ToolRegistry
4. Loads prompt templates
5. Spawns an agent
6. Invokes it with a task
7. Prints the result

Usage:
    # List available templates
    python run_agent.py --list

    # Spawn and run an agent
    python run_agent.py --template financial-analyst-v2 --task "Analyze AAPL"

    # Use a specific model
    python run_agent.py --template code-review-agent-v2 --task "Review agent_factory.py" --model anthropic:claude-sonnet-4-5-20250929

    # Add SIRP meta-reasoning
    python run_agent.py --template deep-research-protocol-v2 --task "What is HDC?" --reasoning sirp

    # Dry run (compose prompt, don't invoke LLM)
    python run_agent.py --template financial-analyst-v2 --task "Analyze NVDA" --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import signal
import logging
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from agent_factory import (
    AgentFactory,
    PromptRegistry,
    ToolRegistry,
    ToolRegistryEntry,
    SpawnConfig,
    ReasoningFramework,
)
from mcp_tools.manager import ToolServerManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# MCP SERVER DEFINITIONS
# ============================================================
# Each entry: server_id → (command, prompt_instructions, domain_tags)
# Add new MCP servers here as you build them.

MCP_SERVERS = {
    "calculator": {
        "command": [sys.executable, "-m", "mcp_tools.servers.calculator"],
        "domain_tags": ["math", "finance", "data-science"],
        # Map MCP tool names → factory tool IDs (what templates reference)
        "id_map": {
            "calculate": "calculator",       # templates use {{TOOL_BLOCK:calculator}}
            "convert_units": "convert_units",
        },
        "prompt_instructions": {
            "calculator": """## Tool: calculator
Evaluate a mathematical expression.

Parameters:
  - expression (str): Math expression to evaluate.
    Supports: +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e

Returns: JSON with 'expression' and 'result' (numeric).

Usage notes:
  - Use for precise calculations rather than mental math
  - Supports complex expressions: "sqrt(2) * pi / 3"
  - Returns error message for invalid expressions""",
            "convert_units": """## Tool: convert_units
Convert between common units (length, weight, temperature).

Parameters:
  - value (number): The value to convert
  - from_unit (str): Source unit (km, miles, kg, lb, celsius, fahrenheit, m, ft)
  - to_unit (str): Target unit

Returns: JSON with 'value', 'from', 'to', 'result'.""",
        },
    },
    "echo": {
        "command": [sys.executable, "-m", "mcp_tools.servers.echo"],
        "domain_tags": ["testing"],
        "prompt_instructions": {
            "echo": """## Tool: echo
Echoes back the input message. Useful for testing.

Parameters:
  - message (str): The message to echo back

Returns: JSON with 'echoed' and 'length'.""",
        },
    },
}


def start_mcp_servers(manager: ToolServerManager, server_ids: list[str] | None = None):
    """Start MCP tool servers and return discovered tools."""
    server_ids = server_ids or list(MCP_SERVERS.keys())
    all_tools = {}

    for sid in server_ids:
        config = MCP_SERVERS.get(sid)
        if not config:
            logger.warning(f"Unknown MCP server: {sid}")
            continue

        manager.register_server(sid, config["command"])

        try:
            tools = manager.start(sid)
            tool_names = [t["name"] for t in tools]
            logger.info(f"  [{sid}] started — tools: {tool_names}")
            all_tools[sid] = tools
        except Exception as e:
            logger.error(f"  [{sid}] failed to start: {e}")

    return all_tools


def register_mcp_in_factory(
    manager: ToolServerManager,
    tool_registry: ToolRegistry,
    discovered: dict[str, list[dict]],
):
    """
    Bridge MCP tools into the Agent Factory's ToolRegistry.

    This is the key wiring step — it creates LangChain tool wrappers
    around MCP server calls and registers them with prompt_instructions
    so the factory can inject them into agent system prompts.
    """
    from mcp_tools.bridge import mcp_to_langchain_tool

    registered = []

    for server_id, tools in discovered.items():
        config = MCP_SERVERS.get(server_id, {})
        domain_tags = config.get("domain_tags", [])
        instructions_map = config.get("prompt_instructions", {})
        id_map = config.get("id_map", {})

        for tool_schema in tools:
            mcp_name = tool_schema["name"]

            # Map MCP tool name to factory tool ID
            # (templates reference factory IDs in {{TOOL_BLOCK:id}})
            factory_id = id_map.get(mcp_name, mcp_name)

            # Create LangChain wrapper that proxies to MCP server
            lc_tool = mcp_to_langchain_tool(manager, server_id, mcp_name)

            # Get prompt instructions (keyed by factory_id)
            instructions = instructions_map.get(factory_id, "")
            if not instructions:
                instructions = instructions_map.get(mcp_name, "")
            if not instructions:
                instructions = f"## Tool: {factory_id}\n{tool_schema.get('description', '')}"

            # Register in factory using the factory_id (not MCP name)
            entry = ToolRegistryEntry(
                id=factory_id,
                name=lc_tool.name,
                description=lc_tool.description,
                tool_type="mcp_server",
                prompt_instructions=instructions,
                tool_instance=lc_tool,  # This is the key — actual callable
                domain_tags=domain_tags,
            )
            tool_registry.register(entry)
            registered.append(factory_id)

    return registered


def load_templates(registry: PromptRegistry) -> int:
    """Load all prompt templates."""
    # YAML base templates
    yaml_path = PROJECT_ROOT / "prompt_registry.yaml"
    count = registry.load_from_yaml(yaml_path)

    # Expanded v2 templates (override YAML entries)
    from expanded_system_prompts import EXPANDED_TEMPLATES
    count += registry.load_from_dict(EXPANDED_TEMPLATES)

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Run an Agent Factory agent with live MCP tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py --list
  python run_agent.py --template code-review-agent-v2 --task "Review this Python file" --dry-run
  python run_agent.py --template financial-analyst-v2 --task "Analyze AAPL technical setup"
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available templates and exit")
    parser.add_argument("--template", "-t", type=str, help="Template ID to spawn")
    parser.add_argument("--task", type=str, help="Task description for the agent")
    parser.add_argument("--model", "-m", type=str, default=None, help="Model override (e.g., anthropic:claude-sonnet-4-5-20250929)")
    parser.add_argument("--reasoning", "-r", type=str, choices=["none", "standard", "sirp"], default="none", help="Meta-reasoning framework")
    parser.add_argument("--dry-run", action="store_true", help="Compose prompt and show it, but don't invoke the LLM")
    parser.add_argument("--servers", type=str, nargs="*", default=None, help="Which MCP servers to start (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Load templates ────────────────────────────────────
    prompt_registry = PromptRegistry()
    count = load_templates(prompt_registry)

    if args.list:
        print(f"\nAvailable templates ({count}):\n")
        templates = prompt_registry.search()
        # Group by domain
        by_domain: dict[str, list] = {}
        for t in templates:
            for d in t.domain_tags:
                by_domain.setdefault(d, []).append(t)

        seen = set()
        for domain in sorted(by_domain.keys()):
            print(f"  [{domain}]")
            for t in by_domain[domain]:
                if t.id not in seen:
                    tools = ", ".join(t.required_tools) if t.required_tools else "none"
                    print(f"    {t.id:<35} {t.name} (tools: {tools})")
                    seen.add(t.id)
            print()
        return

    if not args.template or not args.task:
        parser.error("--template and --task are required (or use --list)")

    # ── Start MCP servers ─────────────────────────────────
    manager = ToolServerManager()

    # Graceful shutdown on Ctrl+C
    def shutdown(sig, frame):
        print("\nShutting down MCP servers...")
        manager.stop_all()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)

    print("Starting MCP tool servers...")
    discovered = start_mcp_servers(manager, args.servers)

    # ── Register tools in factory ─────────────────────────
    tool_registry = ToolRegistry()
    registered = register_mcp_in_factory(manager, tool_registry, discovered)
    print(f"Registered {len(registered)} live tools: {registered}\n")

    # ── Create factory ────────────────────────────────────
    factory = AgentFactory(
        prompt_registry=prompt_registry,
        tool_registry=tool_registry,
        default_model=args.model or "anthropic:claude-sonnet-4-5-20250929",
    )

    # ── Spawn the agent ───────────────────────────────────
    reasoning = {
        "none": ReasoningFramework.NONE,
        "standard": ReasoningFramework.STANDARD,
        "sirp": ReasoningFramework.SIRP,
    }[args.reasoning]

    config = SpawnConfig(
        template_id=args.template,
        reasoning_framework=reasoning,
        task_context=args.task,
        model=args.model,
    )

    # Dry run: compose prompt without building LLM agent
    if args.dry_run:
        template = prompt_registry.get(config.template_id)
        if not template:
            print(f"Error: Template '{config.template_id}' not found.")
            manager.stop_all()
            return

        # Resolve tools
        tool_ids = config.tool_overrides if config.tool_overrides is not None \
            else template.required_tools + template.optional_tools
        _, resolved_ids, missing_ids = tool_registry.resolve(tool_ids)

        # Compose prompt (no LLM needed)
        composed = factory.composer.compose(template, config)

        print(f"\nTemplate: {template.id} ({template.name})")
        print(f"  Tools attached: {resolved_ids}")
        print(f"  Tools missing:  {missing_ids}")
        print(f"  Prompt length:  {len(composed)} chars")
        print(f"\n{'='*60}")
        print("  DRY RUN — Composed System Prompt")
        print(f"{'='*60}\n")
        print(composed)
        print(f"\n{'='*60}")
        print(f"  Tools available to agent: {resolved_ids}")
        print(f"  Tools missing: {missing_ids}")
        print(f"{'='*60}")
        manager.stop_all()
        return

    try:
        result = factory.create(config)
    except ValueError as e:
        print(f"Error: {e}")
        manager.stop_all()
        return

    print(f"Agent spawned: {result.agent_id}")
    print(f"  Tools attached: {result.tools_attached}")
    print(f"  Tools missing:  {result.tools_missing}")
    print(f"  Prompt length:  {len(result.composed_prompt)} chars")

    if False:  # dry_run already handled above
        print(f"\n{'='*60}")
        print("  DRY RUN — Composed System Prompt")
        print(f"{'='*60}\n")
        print(result.composed_prompt)
        print(f"\n{'='*60}")
        print(f"  Tools available to agent: {result.tools_attached}")
        print(f"  Tools missing: {result.tools_missing}")
        print(f"{'='*60}")
        manager.stop_all()
        return

    # ── Invoke the agent ──────────────────────────────────
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠  ANTHROPIC_API_KEY not set. Cannot invoke agent.")
        print("   Set it in .env or export it, then re-run.")
        print("   Use --dry-run to see the composed prompt without invoking.")
        manager.stop_all()
        return

    print(f"\nInvoking agent with task: {args.task}\n")
    print("=" * 60)

    try:
        from langchain_core.messages import HumanMessage
        response = result.agent.invoke({
            "messages": [HumanMessage(content=args.task)]
        })

        messages = response.get("messages", [])
        if messages:
            print(messages[-1].content)
        else:
            print("Agent completed but produced no output.")
    except Exception as e:
        print(f"Agent invocation failed: {e}")
    finally:
        print("=" * 60)
        manager.stop_all()
        print("\nMCP servers stopped.")


if __name__ == "__main__":
    main()
