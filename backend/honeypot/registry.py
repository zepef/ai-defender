"""Tool registry for registering, listing, and dispatching tool simulators."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from honeypot.engagement import EngagementEngine
from honeypot.simulators.base import SimulationResult, ToolSimulator
from shared.config import Config
from shared.db import log_interaction

if TYPE_CHECKING:
    from honeypot.session import SessionManager

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, config: Config, session_manager: SessionManager) -> None:
        self.config = config
        self.sessions = session_manager
        self._tools: dict[str, ToolSimulator] = {}
        self.engagement = EngagementEngine()

    def register(self, simulator: ToolSimulator) -> None:
        self._tools[simulator.name] = simulator
        logger.info("Registered tool: %s", simulator.name)

    def list_tools(self) -> list[dict]:
        return [tool.to_mcp_tool() for tool in self._tools.values()]

    def dispatch(self, tool_name: str, arguments: dict, session_id: str) -> SimulationResult:
        simulator = self._tools.get(tool_name)
        if simulator is None:
            return SimulationResult(
                output=f"Error: unknown tool '{tool_name}'",
                is_error=True,
            )

        session = self.sessions.get(session_id)
        if session is None:
            return SimulationResult(output="Error: invalid session", is_error=True)

        result = simulator.simulate(arguments, session)

        # Apply engagement engine enrichment
        computed_level = self.engagement.compute_escalation(session)
        if computed_level > session.escalation_level:
            session.escalation_level = computed_level
        result.output = self.engagement.enrich_output(result.output, session)

        # Log the interaction
        log_interaction(
            self.config.db_path,
            session_id,
            method="tools/call",
            tool_name=tool_name,
            params=arguments,
            response={"output": result.output, "isError": result.is_error},
            escalation_delta=result.escalation_delta,
        )

        # Apply escalation
        if result.escalation_delta > 0:
            session.escalate(result.escalation_delta)

        # Persist session state
        self.sessions.persist(session_id)

        logger.info("Dispatched %s for session %s (escalation=%d)",
                     tool_name, session_id, session.escalation_level)

        return result

    def register_defaults(self) -> None:
        from honeypot.simulators.browser import BrowserSimulator
        from honeypot.simulators.file_read import FileReadSimulator
        from honeypot.simulators.nmap import NmapSimulator
        from honeypot.simulators.shell_exec import ShellExecSimulator
        from honeypot.simulators.sqlmap import SqlmapSimulator

        for sim_cls in (NmapSimulator, FileReadSimulator, ShellExecSimulator,
                        SqlmapSimulator, BrowserSimulator):
            self.register(sim_cls(self.config))
