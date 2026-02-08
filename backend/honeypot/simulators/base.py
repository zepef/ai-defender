"""Base classes for tool simulators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from honeypot.session import SessionContext


@dataclass
class SimulationResult:
    output: str
    is_error: bool = False
    injected_token_ids: list[int] = field(default_factory=list)
    escalation_delta: int = 0


class ToolSimulator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name as exposed via MCP tools/list."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable tool description."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for the tool's input parameters."""

    @abstractmethod
    def simulate(self, arguments: dict, session: SessionContext) -> SimulationResult:
        """Execute the simulated tool and return a result."""

    def to_mcp_tool(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
