# Agent Factory

A meta-agent system that enables agents to dynamically create specialized agents with MCP tool integration.

**📊 [View Product Architecture Diagram](product-architecture.drawio)** — Open in draw.io or diagrams.net

## Overview

Agent Factory combines three key capabilities:

1. **Template-Based Agent Creation** — 30 specialized agent templates (12 full v2, 18 YAML)
2. **Dynamic Tool Injection** — MCP tool servers auto-discovered and injected via `{{TOOL_BLOCK}}` placeholders
3. **Dual Runtime Support** — deepagents (full features) or LangGraph (fallback) with ReAct loops

```
User → run_agent.py → Factory (Template + Tools) → Live Agent → MCP Tool Servers
                                                         ↓
                                                   stdio JSON-RPC
```

## Features

- **Template-based agent creation** — Searchable registry of agent personas and tasks
- **Dynamic tool injection** — `{{TOOL_BLOCK}}` placeholders replaced at spawn time
- **Dual runtime support** — Uses deepagents (full features) or falls back to LangGraph
- **Meta-reasoning injection** — SIRP protocol or standard reflection
- **Hierarchical spawning** — Agents can spawn sub-agents with depth limits
- **Genealogy tracking** — Full spawn chain for observability

## Installation

**Requirements:** Python 3.10+

```bash
# Clone the repository
git clone https://github.com/ChristopherHartline/agent_factory.git
cd agent_factory

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY is required)
```

**⚙️ Configuration Setup:**

See **[SETUP.md](SETUP.md)** for detailed configuration instructions:
- `.claude/settings.local.json` — Claude Code permissions and paths
- `.cursor/rules/` — Cursor AI rules (symlinked from shared knowledge base)
- Shared knowledge base layout at `~/Desktop/Development/agent-knowledge/`
- Quick start checklist

## Quick Start

### End-to-End CLI Usage (Recommended)

The easiest way to run agents with full MCP tool integration:

```bash
# Activate virtual environment
source venv/bin/activate

# List available agent templates
python run_agent.py --list

# Run an agent with a task
python run_agent.py \
  --template financial-analyst-v2 \
  --task "Calculate the compound interest on $10,000 at 5% for 10 years"

# Use a specific model
python run_agent.py \
  --template code-review-agent-v2 \
  --task "Review agent_factory.py" \
  --model anthropic:claude-sonnet-4-5-20250929

# Add SIRP meta-reasoning
python run_agent.py \
  --template deep-research-protocol-v2 \
  --task "What is HDC?" \
  --reasoning sirp

# Dry run (see composed prompt without invoking LLM)
python run_agent.py \
  --template financial-analyst-v2 \
  --task "Analyze NVDA" \
  --dry-run
```

### Programmatic Usage

```python
from agent_factory import AgentFactory, PromptRegistry, ToolRegistry
from expanded_system_prompts import EXPANDED_TEMPLATES

# Initialize registries
prompt_registry = PromptRegistry()
prompt_registry.load_from_yaml('prompt_registry.yaml')
prompt_registry.load_from_dict(EXPANDED_TEMPLATES)  # Override with expanded versions

tool_registry = ToolRegistry()
# Register your tools here (see MCP Tools section)

# Create factory
factory = AgentFactory(
    prompt_registry=prompt_registry,
    tool_registry=tool_registry,
)

print(f"Runtime: {factory.runtime}")  # "deepagents" or "langgraph"

# Search for templates
results = prompt_registry.search(domain_tags=["finance"])
for t in results:
    print(f"  {t.id}: {t.name}")

# Spawn an agent
from agent_factory import SpawnConfig

result = factory.create(SpawnConfig(
    template_id="financial-analyst-v2",
    task_context="Analyze NVDA for potential entry points.",
))

print(f"Agent ID: {result.agent_id}")
print(f"Tools attached: {result.tools_attached}")
```

## MCP Tools Architecture

Agent Factory uses **Model Context Protocol (MCP)** for tool integration. MCP servers run as separate processes and communicate with agents via **stdio JSON-RPC 2.0**.

### How It Works

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│ Live Agent  │────────>│ MCP Manager  │────────>│ calculator      │
│             │  calls  │              │  stdio  │ (subprocess)    │
│ ReAct Loop  │<────────│ Tool Bridge  │<────────│ JSON-RPC 2.0    │
└─────────────┘ results └──────────────┘         └─────────────────┘
```

**Key Components:**

1. **MCP Servers** (`mcp_tools/servers/`) — Standalone Python modules exposing tools
2. **stdio Transport** (`mcp_tools/transport.py`) — JSON-RPC communication via stdin/stdout
3. **Tool Bridge** (`mcp_tools/bridge.py`) — Converts MCP tools to LangChain StructuredTools
4. **Tool Manager** (`mcp_tools/manager.py`) — Lifecycle management for MCP servers
5. **Factory Integration** (`run_agent.py`) — Auto-discovery and registration

### Communication Protocol

Each MCP server is a subprocess launched via:
```bash
python -m mcp_tools.servers.calculator
```

Communication happens via **line-buffered JSON messages**:

**Request (Agent → Server):**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "calculate",
    "arguments": {"expression": "10000 * (1.05 ** 10)"}
  },
  "id": 1
}
```

**Response (Server → Agent):**
```json
{
  "jsonrpc": "2.0",
  "result": {"result": "16288.946267774416"},
  "id": 1
}
```

**Supported Methods:**
- `ping` — Health check
- `tools/list` — Discover available tools
- `tools/call` — Execute a tool

### Current MCP Tools

| Tool ID | Server | Tools | Description | Status |
|---------|--------|-------|-------------|--------|
| `calculator` | `mcp_tools.servers.calculator` | `calculate`, `convert_units` | Math expressions, unit conversion | ✅ **Active** |
| `echo` | `mcp_tools.servers.echo` | `echo` | Test server (echoes input back) | ✅ **Active** |

### Planned MCP Tools

**Priority 1 (Core Functionality):**

| Tool ID | Purpose | API/Library | Agents Enabled |
|---------|---------|-------------|----------------|
| `web_search` | Real-time web search | DuckDuckGo / Brave API | llm-researcher-v2, deep-research-protocol-v2, cybersecurity-specialist-v2 |
| `web_fetch` | Fetch URLs/APIs | requests / httpx | All research agents, data-scientist-v2 |
| `file_system` | Read/write files | pathlib (sandboxed) | code-review-agent-v2, technical-writer, data-engineer |

**Priority 2 (Advanced Capabilities):**

| Tool ID | Purpose | API/Library | Agents Enabled |
|---------|---------|-------------|----------------|
| `code_executor` | Python/JS sandbox | Docker / E2B | code-review-agent-v2, data-scientist-v2, qa-engineer |
| `database_query` | SQL queries | SQLite / Postgres | data-engineer, financial-analyst-v2 |
| `chart_generator` | Visualizations | Matplotlib / Plotly | financial-analyst-v2, data-scientist-v2 |

**Template-Specific (Future):**

| Tool ID | Purpose | API/Library | Agents Enabled |
|---------|---------|-------------|----------------|
| `market_data_api` | Stock market data | Alpha Vantage / Yahoo Finance | financial-analyst-v2, stock-market-analyst-v2 |
| `image_gen` | Image generation | DALL-E / Midjourney | image-gen-director-v2 |

### Creating Custom MCP Servers

Create a new server in `mcp_tools/servers/`:

```python
# mcp_tools/servers/my_tool.py

from mcp_tools.server import StdioToolServer, ToolHandler

class MyToolHandler(ToolHandler):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something useful"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input data"},
            },
            "required": ["input"],
        }

    def handle(self, arguments: dict) -> dict:
        result = f"Processed: {arguments['input']}"
        return {"result": result}

if __name__ == "__main__":
    server = StdioToolServer()
    server.register_handler(MyToolHandler())
    server.run()
```

Register in `run_agent.py`:

```python
MCP_SERVERS = {
    "my_tool": {
        "command": [sys.executable, "-m", "mcp_tools.servers.my_tool"],
        "domain_tags": ["general"],
        "id_map": {"my_tool": "my_tool"},
        "prompt_instructions": {
            "my_tool": """## Tool: my_tool
Does something useful.

Parameters:
  - input (str): Input data

Returns:
  - result (str): Processed output"""
        },
    },
}
```

## Template Structure

Templates follow the **5-layer prompt pattern**:

### 1. Identity + Mandate

Who the agent is and what it's responsible for.

```yaml
# Identity + Mandate

You are a senior financial analyst specializing in equity research...

Your mandate: Given a ticker, analysis type, and timeframe, produce 
a structured assessment with a clear recommendation and confidence score.
```

### 2. Tool Instructions

Dynamic tool blocks injected at spawn time.

```yaml
# Available Tools

{{TOOL_BLOCK:market_data_api}}
{{TOOL_BLOCK:web_search}}
{{TOOL_BLOCK:calculator}}
```

The factory replaces `{{TOOL_BLOCK:tool_id}}` with actual tool instructions from the Tool Registry.

### 3. Reasoning Protocol

How the agent should think through problems.

```yaml
# Reasoning Protocol

Follow this analytical sequence:

1. DATA GATHERING — Retrieve current price, volume...
2. CONTEXT ASSESSMENT — Check for recent news...
3. PATTERN RECOGNITION — Identify support/resistance...
4. RISK IDENTIFICATION — List top 3-5 risks...
5. SYNTHESIS — Combine findings into recommendation...
```

### 4. Input/Output Contract

What the agent expects and what it produces.

```yaml
# Output Contract

Return a JSON object:
{
  "recommendation": "buy|hold|sell|...",
  "confidence": 0.0-1.0,
  "analysis": "...",
  "key_metrics": {...},
  "risks": [...],
  "sources": [...]
}
```

### 5. Guardrails

Constraints and termination conditions.

```yaml
# Guardrails

- NEVER recommend specific position sizes or dollar amounts
- NEVER claim certainty — always frame as analysis, not advice
- Maximum 10 tool calls per analysis
- If confidence falls below 0.4, return "insufficient_data"
```

## Tool Registry

Register tools for agents to use:

```python
from agent_factory import ToolRegistry, ToolRegistryEntry

tool_registry = ToolRegistry()

# Option 1: Register a LangChain tool
from langchain_community.tools import TavilySearchResults

search_tool = TavilySearchResults()
tool_registry.register_langchain_tool(
    tool_id="web_search",
    tool=search_tool,
    prompt_instructions="Search the web for current information...",
    domain_tags=["general", "research"],
)

# Option 2: Register a function
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

tool_registry.register_function(
    tool_id="calculator",
    func=calculate,
    name="calculator",
    description="Evaluate mathematical expressions",
    prompt_instructions="Use for precise calculations...",
    domain_tags=["math", "finance"],
)

# Option 3: Register an MCP server (manual entry)
tool_registry.register(ToolRegistryEntry(
    id="market_data_api",
    name="Market Data API",
    description="Retrieve stock market data",
    tool_type="mcp_server",
    prompt_instructions="""## Tool: market_data_api
Retrieve real-time and historical stock market data.

Parameters:
  - ticker (str): Stock ticker symbol
  - timeframe (str): "1d", "5d", "1m", "3m", "1y"
  - indicators (list[str]): Technical indicators to compute
...""",
    config={"server": "alpha_vantage"},
    domain_tags=["finance", "trading"],
))
```

## Factory API

### SpawnConfig

Configuration for creating an agent:

```python
from agent_factory import SpawnConfig, ReasoningFramework

config = SpawnConfig(
    template_id="financial-analyst-v2",      # Required: which template
    tool_overrides=["web_search"],           # Optional: override template's tools
    model="anthropic:claude-sonnet-4-5-20250929",  # Optional: override model
    max_iterations=15,                       # Optional: override max iterations
    reasoning_framework=ReasoningFramework.SIRP,  # Optional: inject meta-reasoning
    budget={"max_tool_calls": 10},           # Optional: resource limits
    parent_agent_id="parent-1",              # Optional: for genealogy tracking
    task_context="Additional context...",    # Optional: injected into prompt
)
```

### SpawnResult

What you get back:

```python
result = factory.create(config)

result.agent          # The compiled LangGraph agent
result.agent_id       # Unique ID (e.g., "financial-analyst-v2-1")
result.template_id    # Template used
result.tools_attached # Tools successfully resolved
result.tools_missing  # Tools that weren't available
result.composed_prompt # Final system prompt (for debugging)
result.genealogy      # Spawn chain info
```

### Registry Search

Find the right template:

```python
# Search by domain
results = prompt_registry.search(domain_tags=["finance", "trading"])

# Search by reasoning style
from agent_factory import ReasoningStyle
results = prompt_registry.search(reasoning_style=ReasoningStyle.ANALYTICAL)

# Search by keyword
results = prompt_registry.search(query="security assessment")

# Combined filters
results = prompt_registry.search(
    domain_tags=["development"],
    composable_only=True,
    min_quality=0.7,
)
```

### Factory as Tool

Expose the factory to an orchestrator agent:

```python
# Get tools for an orchestrator to use
spawn_tool = factory.as_tool()
search_tool = factory.search_registry_tool()

# The orchestrator can now:
# 1. Search for the right template
# 2. Spawn specialized agents to handle tasks
```

## Meta-Reasoning Frameworks

### SIRP (Structured Iterative Reasoning Protocol)

Injected when `reasoning_framework=ReasoningFramework.SIRP`:

```
<thinking> tags for exploratory thoughts
<count> tags for step budget tracking
<reflection> tags every 3-4 steps with quality score
<reward> tag for final self-assessment
```

### Standard Reflection

Injected when `reasoning_framework=ReasoningFramework.STANDARD`:

```
After completing analysis, assess:
- Did I address the core question?
- What is my confidence?
- What would I do differently?
```

## Creating New Templates

### YAML Format

Add to `prompt_registry.yaml`:

```yaml
- id: my-new-agent
  name: My New Agent
  version: "1.0.0"
  description: What this agent does
  prompt_type: persona  # persona | task | composite | tool-wrapper
  domain_tags: [domain1, domain2]
  reasoning_style: analytical  # analytical | creative | adversarial | methodical | exploratory | conversational
  complexity: moderate  # atomic | moderate | complex
  composable: true  # Can be used as sub-agent?
  required_tools: [tool1]
  optional_tools: [tool2, tool3]
  recommended_graph: react  # react | chain | plan-execute
  max_iterations: 12
  author: your-name
  source: curated
  system_prompt: |
    # Identity + Mandate
    ...
    
    # Available Tools
    {{TOOL_BLOCK:tool1}}
    {{TOOL_BLOCK:tool2}}
    
    # Reasoning Protocol
    ...
    
    # Output Contract
    ...
    
    # Guardrails
    ...
```

### Python Dict Format

Add to `expanded_system_prompts.py` for full control:

```python
EXPANDED_TEMPLATES["my-new-agent-v2"] = {
    "id": "my-new-agent-v2",
    "name": "My New Agent",
    "version": "2.0.0",
    # ... all fields ...
    "system_prompt": """...""",
    "input_schema": {...},  # JSON Schema for validation
    "output_schema": {...},
}
```

## Available Templates

### Finance
- `financial-analyst-v2` — Equity research with fundamental + technical analysis
- `stock-market-analyst-v2` — Market timing and technical patterns

### Development
- `code-review-agent-v2` — Code quality, security, performance review
- `data-scientist-v2` — Data analysis, ML pipelines, insights
- `devops-engineer-v2` — Infrastructure, CI/CD, deployment

### Architecture
- `senior-system-architect-v2` — Enterprise system design

### Research
- `llm-researcher-v2` — AI/ML research and paper analysis
- `deep-research-protocol-v2` — Multi-hop research with evidence tracking
- `research-paper-evaluator-v2` — Academic paper review

### Creative
- `image-gen-director-v2` — Diffusion model prompt engineering

### Business
- `project-manager-v2` — PRDs, project plans, agile docs

### Security
- `cybersecurity-specialist-v2` — Threat modeling, security assessment

### Base Templates (stubs for expansion)
- `technical-writer` — Documentation
- `qa-engineer` — Test planning
- `ux-researcher` — Usability analysis
- `data-engineer` — Data pipelines
- `customer-support-agent` — Support interactions
- `content-strategist` — Content planning

## Runtime Support

The factory automatically detects the available runtime:

```python
factory = AgentFactory(...)
print(factory.runtime)  # "deepagents" or "langgraph"
```

### deepagents (Full Features)
- Planning capabilities (write_todos)
- Filesystem context management
- Sub-agent spawning

### langgraph (Fallback)
- Basic ReAct loop
- Works without deepagents installed
- Good for development/testing

## Project Structure

```
agent_factory/
├── agent_factory.py               # Core factory, registries, composer (~1064 lines)
├── expanded_system_prompts.py     # 12 fully-expanded v2 templates
├── prompt_registry.yaml           # 18 templates in YAML format (6 stubs)
├── run_agent.py                   # End-to-end CLI (MCP → Factory → Agent)
├── demo_factory.py                # Demo script (legacy)
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── .env                           # Your API keys (gitignored)
├── README.md                      # This file
├── SETUP.md                       # Configuration guide
├── architecture.drawio            # Original architecture diagram
├── product-architecture.drawio    # Product architecture diagram
│
├── mcp_tools/                     # MCP Tool Infrastructure
│   ├── __init__.py                # Package init (lazy imports)
│   ├── transport.py               # stdio/gRPC transports
│   ├── server.py                  # StdioToolServer + ToolHandler ABC
│   ├── manager.py                 # ToolServerManager (lifecycle)
│   ├── bridge.py                  # MCP → LangChain tool conversion
│   └── servers/                   # MCP server implementations
│       ├── calculator.py          # ✅ Math + unit conversion
│       ├── echo.py                # ✅ Test server
│       ├── web_search.py          # 🚧 Planned (DuckDuckGo/Brave)
│       ├── web_fetch.py           # 🚧 Planned (HTTP client)
│       ├── file_system.py         # 🚧 Planned (Read/write with sandbox)
│       ├── code_executor.py       # 🔮 Planned (Python/JS sandbox)
│       ├── database_query.py      # 🔮 Planned (SQLite/Postgres)
│       └── chart_generator.py     # 🔮 Planned (Matplotlib/Plotly)
│
├── .cursor/                       # Cursor AI rules (symlinked)
│   └── rules/
│       ├── ops-planning.mdc       # → ~/Desktop/Development/agent-knowledge/units/ops-planning/
│       ├── factory-dev.mdc        # → ~/Desktop/Development/agent-knowledge/units/factory-dev/
│       ├── agent-creator.mdc      # → ~/Desktop/Development/agent-knowledge/units/agent-creator/
│       └── sara-agent.mdc         # Sara agent identity
│
└── .claude/                       # Claude Code settings (gitignored)
    └── settings.local.json        # Permissions, paths (machine-specific)
```

**External (Shared Knowledge Base):**
```
~/Desktop/Development/agent-knowledge/
└── units/                         # Knowledge units (conventions & standards)
    ├── ops-planning/
    │   └── SKILL.md               # Planning conventions
    ├── factory-dev/
    │   └── SKILL.md               # Development standards
    └── agent-creator/
        └── SKILL.md               # Meta-agent template

Note: Simplified structure - removed Cursor rule generation, sync scripts,
and AAR loop. SKILL.md files are reference material for child agents.
```

## Architecture Overview

**📊 [View Product Architecture Diagram](product-architecture.drawio)** — Comprehensive visual guide

### End-to-End Flow

```
1. User provides task + template_id
   ↓
2. run_agent.py starts MCP servers (calculator, echo, ...)
   ↓
3. MCP tools discovered via "tools/list" JSON-RPC call
   ↓
4. Tools bridged to LangChain StructuredTools
   ↓
5. Tools registered in Factory ToolRegistry with prompt_instructions
   ↓
6. Factory loads template from PromptRegistry
   ↓
7. PromptComposer resolves {{TOOL_BLOCK:tool_id}} placeholders
   ↓
8. Agent built with runtime (deepagents or langgraph)
   ↓
9. Agent receives task, enters ReAct loop:
   - Think (reason about next action)
   - Act (call tool via MCP stdio JSON-RPC)
   - Observe (receive result)
   - Repeat until complete
   ↓
10. Final response returned to user
    ↓
11. MCP servers gracefully stopped
```

### Key Design Patterns

**1. Template + Tool Injection**
- Templates declare tool needs via `{{TOOL_BLOCK:tool_id}}`
- Factory resolves at spawn time with actual `prompt_instructions`
- Same template + different tools = different specialized agents

**2. stdio JSON-RPC Communication**
- MCP servers = isolated subprocesses (no shared state)
- Line-buffered JSON messages (stdin → stdout)
- Non-blocking, async-ready architecture
- Automatic retry and error handling

**3. Dual Runtime Support**
- **deepagents** (full features): planning, filesystem, sub-agent spawning
- **langgraph** (fallback): basic ReAct loop, no external dependencies
- Factory abstracts runtime — same API for both

**4. Genealogy Tracking**
- Every agent spawn recorded: `agent_id`, `parent_agent_id`, `depth`, `tools_attached`
- Enables hierarchical agent trees and observability
- Prevents infinite recursion with depth limits

**5. 5-Layer Prompt Pattern**
- **Identity + Mandate** — Who the agent is, what it's responsible for
- **Tool Instructions** — Dynamic `{{TOOL_BLOCK}}` injection
- **Reasoning Protocol** — How to think through problems
- **I/O Contract** — Expected inputs and outputs
- **Guardrails** — Constraints and termination conditions

### stdio Communication Example

**Agent calls calculator tool:**

```
Agent (LangChain) → MCP Manager → stdio Transport
                                      ↓ (write to stdin)
                        {"jsonrpc":"2.0","method":"tools/call",
                         "params":{"name":"calculate",
                         "arguments":{"expression":"10000*(1.05**10)"}},
                         "id":1}
                                      ↓
                        MCP Server (calculator subprocess)
                          - Parses JSON
                          - Executes safe eval
                          - Returns result
                                      ↓ (write to stdout)
                        {"jsonrpc":"2.0",
                         "result":{"result":"16288.946"},
                         "id":1}
                                      ↓
stdio Transport → MCP Manager → Agent (continues reasoning)
```

### Template Resolution Example

**Before (Template):**
```yaml
system_prompt: |
  You are a financial analyst.

  # Available Tools
  {{TOOL_BLOCK:calculator}}
  {{TOOL_BLOCK:market_data_api}}

  # Reasoning Protocol
  1. Gather data using market_data_api
  2. Calculate metrics using calculator
  ...
```

**After (Composed Prompt at Spawn Time):**
```yaml
system_prompt: |
  You are a financial analyst.

  # Available Tools

  ## Tool: calculator
  Evaluate mathematical expressions and convert units.

  Parameters:
    - expression (str): Math expression to evaluate

  Returns:
    - result (float): Calculated value

  ⚠️  Tool 'market_data_api' not available (missing from ToolRegistry)

  # Reasoning Protocol
  1. Gather data using market_data_api
  2. Calculate metrics using calculator
  ...
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add templates to `prompt_registry.yaml` or `expanded_system_prompts.py`
4. Register tools in your implementation
5. Submit a pull request

When adding templates:
- Follow the 5-layer structure
- Include all required fields
- Add appropriate domain tags
- Test with the demo script
