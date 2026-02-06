"""
Transport layer abstraction for MCP tool communication.

Currently implements:
  - StdioTransport: JSON-RPC over stdin/stdout pipes (local)

Future:
  - GrpcTransport: gRPC-based transport for remote tool servers
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request."""
    method: str
    params: dict[str, Any]
    id: int | str

    def to_json(self) -> str:
        return json.dumps({
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id,
        })


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 response."""
    id: int | str
    result: Any = None
    error: dict | None = None

    @classmethod
    def from_json(cls, data: str) -> "JsonRpcResponse":
        parsed = json.loads(data)
        return cls(
            id=parsed.get("id"),
            result=parsed.get("result"),
            error=parsed.get("error"),
        )

    @property
    def is_error(self) -> bool:
        return self.error is not None


class Transport(ABC):
    """Abstract transport layer for MCP communication."""

    @abstractmethod
    def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send a request and return the response."""
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the transport (e.g., launch subprocess)."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the transport (e.g., terminate subprocess)."""
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the transport is active."""
        ...


class StdioTransport(Transport):
    """
    JSON-RPC over stdin/stdout pipes to a subprocess.

    This is MCP's native local transport. The tool server runs as
    a child process. We write JSON-RPC requests to its stdin and
    read responses from its stdout. One line = one message.
    """

    def __init__(self, command: list[str], env: dict[str, str] | None = None):
        """
        Args:
            command: Command to launch the tool server process.
                     e.g., ["python", "-m", "mcp_tools.servers.calculator"]
            env: Optional environment variables for the subprocess.
        """
        self.command = command
        self.env = env
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    def start(self) -> None:
        """Launch the tool server subprocess."""
        if self._process and self._process.poll() is None:
            logger.warning("Transport already running, stopping first")
            self.stop()

        logger.info(f"Starting stdio transport: {' '.join(self.command)}")
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
            bufsize=1,  # Line-buffered
        )

    def stop(self) -> None:
        """Terminate the tool server subprocess."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.info("Stdio transport stopped")

    def is_alive(self) -> bool:
        """Check if the subprocess is running."""
        return self._process is not None and self._process.poll() is None

    def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Send JSON-RPC request via stdin, read response from stdout."""
        if not self.is_alive():
            raise RuntimeError("Transport not running. Call start() first.")

        # Write request
        line = request.to_json() + "\n"
        self._process.stdin.write(line)
        self._process.stdin.flush()

        # Read response (one line)
        response_line = self._process.stdout.readline()
        if not response_line:
            # Process may have died
            stderr = self._process.stderr.read() if self._process.stderr else ""
            raise RuntimeError(
                f"Tool server process died. stderr: {stderr[:500]}"
            )

        return JsonRpcResponse.from_json(response_line.strip())

    def next_id(self) -> int:
        """Generate the next request ID."""
        self._request_id += 1
        return self._request_id


class GrpcTransport(Transport):
    """
    Placeholder for gRPC-based transport.

    Future implementation will:
    - Connect to a remote gRPC server
    - Use protobuf messages instead of JSON-RPC
    - Support streaming responses
    - Handle connection pooling and retries

    The tool server interface (ToolHandler) stays the same —
    only the transport changes.
    """

    def __init__(self, endpoint: str, credentials: Any = None):
        self.endpoint = endpoint
        self.credentials = credentials
        raise NotImplementedError(
            "gRPC transport is planned but not yet implemented. "
            "Use StdioTransport for local tool servers."
        )

    def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def is_alive(self) -> bool:
        raise NotImplementedError
