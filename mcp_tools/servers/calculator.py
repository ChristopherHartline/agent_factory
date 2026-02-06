"""
Calculator MCP Tool Server.

A simple reference implementation showing how to build an MCP tool server.
Runs as a subprocess, communicates via stdin/stdout JSON-RPC.

Launch:
    python -m mcp_tools.servers.calculator

Test manually:
    echo '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' | python -m mcp_tools.servers.calculator
    echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"calculate","arguments":{"expression":"2+2"}},"id":2}' | python -m mcp_tools.servers.calculator
"""

import math
import sys
import os

# Add project root to path so imports work when run as subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp_tools.server import StdioToolServer, ToolHandler


class CalculateTool(ToolHandler):
    name = "calculate"
    description = "Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e."
    parameters = {
        "expression": {
            "type": "string",
            "description": "Mathematical expression to evaluate (e.g., 'sqrt(2) * pi / 3')",
        },
    }

    # Allowed names in eval scope (safe math only)
    _safe_names = {
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "abs": abs,
        "round": round,
        "pi": math.pi,
        "e": math.e,
        "inf": math.inf,
    }

    def handle(self, params: dict) -> dict:
        expression = params.get("expression", "")
        if not expression:
            return {"error": "No expression provided"}

        try:
            # Restricted eval with only math functions
            result = eval(expression, {"__builtins__": {}}, self._safe_names)
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"expression": expression, "error": str(e)}


class ConvertUnitsTool(ToolHandler):
    name = "convert_units"
    description = "Convert between common units (length, weight, temperature)."
    parameters = {
        "value": {"type": "number", "description": "The value to convert"},
        "from_unit": {"type": "string", "description": "Source unit (e.g., 'km', 'lb', 'celsius')"},
        "to_unit": {"type": "string", "description": "Target unit (e.g., 'miles', 'kg', 'fahrenheit')"},
    }

    _conversions = {
        ("km", "miles"): lambda v: v * 0.621371,
        ("miles", "km"): lambda v: v * 1.60934,
        ("kg", "lb"): lambda v: v * 2.20462,
        ("lb", "kg"): lambda v: v * 0.453592,
        ("celsius", "fahrenheit"): lambda v: v * 9 / 5 + 32,
        ("fahrenheit", "celsius"): lambda v: (v - 32) * 5 / 9,
        ("m", "ft"): lambda v: v * 3.28084,
        ("ft", "m"): lambda v: v * 0.3048,
    }

    def handle(self, params: dict) -> dict:
        value = params.get("value")
        from_unit = params.get("from_unit", "").lower()
        to_unit = params.get("to_unit", "").lower()

        converter = self._conversions.get((from_unit, to_unit))
        if not converter:
            available = [f"{f} → {t}" for f, t in self._conversions.keys()]
            return {"error": f"Unknown conversion: {from_unit} → {to_unit}. Available: {available}"}

        result = converter(value)
        return {"value": value, "from": from_unit, "to": to_unit, "result": result}


if __name__ == "__main__":
    server = StdioToolServer()
    server.register(CalculateTool())
    server.register(ConvertUnitsTool())
    server.run()
