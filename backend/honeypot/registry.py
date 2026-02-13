"""Tool registry for registering, listing, and dispatching tool simulators."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from honeypot.engagement import EngagementEngine
from honeypot.simulators.base import SimulationResult, ToolSimulator
from shared.config import Config
from shared.db import get_session_token_count, log_interaction

if TYPE_CHECKING:
    from honeypot.session import SessionManager
    from shared.event_bus import EventBus

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, config: Config, session_manager: SessionManager, *, event_bus: EventBus | None = None) -> None:
        self.config = config
        self.sessions = session_manager
        self.event_bus = event_bus
        self._tools: dict[str, ToolSimulator] = {}
        self.engagement = EngagementEngine()

    def register(self, simulator: ToolSimulator) -> None:
        self._tools[simulator.name] = simulator
        logger.info("Registered tool: %s", simulator.name)

    def list_tools(self) -> list[dict]:
        return [tool.to_mcp_tool() for tool in self._tools.values()]

    @staticmethod
    def _build_prompt_summary(tool_name: str, arguments: dict) -> str:
        """Build a short human-readable summary of the tool call."""
        match tool_name:
            case "nmap_scan":
                target = arguments.get("target", "?")
                scan_type = arguments.get("scan_type", "quick")
                return f"nmap_scan: {target} {scan_type} scan"
            case "file_read":
                path = arguments.get("path", "?")
                return f"file_read: {path}"
            case "shell_exec":
                cmd = arguments.get("command", "?")
                return f"shell_exec: {cmd[:60]}"
            case "sqlmap_scan":
                action = arguments.get("action", "test")
                table = arguments.get("table", "")
                suffix = f" {table}" if table else ""
                return f"sqlmap_scan: {action}{suffix}"
            case "browser_navigate":
                url = arguments.get("url", "?")
                action = arguments.get("action", "navigate")
                return f"browser: {action} {url[:50]}"
            case "dns_lookup":
                domain = arguments.get("domain", "?")
                qtype = arguments.get("query_type", "A")
                return f"dns_lookup: {domain} {qtype}"
            case "aws_cli":
                cmd = arguments.get("command", "?")
                return f"aws_cli: {cmd[:50]}"
            case "kubectl":
                cmd = arguments.get("command", "?")
                ns = arguments.get("namespace", "default")
                return f"kubectl: {cmd[:40]} -n {ns}"
            case "vault_cli":
                cmd = arguments.get("command", "?")
                return f"vault: {cmd[:50]}"
            case "docker_registry":
                action = arguments.get("action", "list")
                image = arguments.get("image_name", "")
                suffix = f" {image}" if image else ""
                return f"docker_registry: {action}{suffix}"
            case _:
                return f"{tool_name}: {str(arguments)[:40]}"

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

        tokens_before = get_session_token_count(self.config.db_path, session_id)
        result = simulator.simulate(arguments, session)
        tokens_after = get_session_token_count(self.config.db_path, session_id)

        # Capture output before enrichment to detect breadcrumb injection
        output_before = result.output

        # Apply engagement engine enrichment
        computed_level = self.engagement.compute_escalation(session)
        if computed_level > session.escalation_level:
            session.escalation_level = computed_level
        result.output = self.engagement.enrich_output(result.output, session)

        # Detect injected breadcrumb
        injection: str | None = None
        if result.output != output_before:
            # Extract the injected text (breadcrumb or transient error)
            added = result.output.replace(output_before, "").strip()
            if added.startswith("# "):
                injection = added[2:]  # Remove the "# " prefix from breadcrumbs
            elif added:
                injection = added

        # Build prompt summary
        prompt_summary = self._build_prompt_summary(tool_name, arguments)

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

        if self.event_bus:
            self.event_bus.publish("interaction", {
                "session_id": session_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "escalation_delta": result.escalation_delta,
                "escalation_level": session.escalation_level,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt_summary": prompt_summary,
                "injection": injection,
            })

        # Emit token_deployed events for defensive actions
        tokens_deployed = tokens_after - tokens_before
        if tokens_deployed > 0 and self.event_bus:
            self.event_bus.publish("token_deployed", {
                "session_id": session_id,
                "tool_name": tool_name,
                "count": tokens_deployed,
                "total_tokens": tokens_after,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Apply escalation
        if result.escalation_delta > 0:
            session.escalate(result.escalation_delta)
            if self.event_bus:
                self.event_bus.publish("session_update", {
                    "session_id": session_id,
                    "escalation_level": session.escalation_level,
                    "interaction_count": session.interaction_count,
                })

        # Persist session state
        self.sessions.persist(session_id)

        logger.info("Dispatched %s for session %s (escalation=%d)",
                     tool_name, session_id, session.escalation_level)

        return result

    def register_defaults(self) -> None:
        from honeypot.simulators.aws_cli import AwsCliSimulator
        from honeypot.simulators.browser import BrowserSimulator
        from honeypot.simulators.dns_lookup import DnsLookupSimulator
        from honeypot.simulators.docker_registry import DockerRegistrySimulator
        from honeypot.simulators.file_read import FileReadSimulator
        from honeypot.simulators.kubectl import KubectlSimulator
        from honeypot.simulators.nmap import NmapSimulator
        from honeypot.simulators.shell_exec import ShellExecSimulator
        from honeypot.simulators.sqlmap import SqlmapSimulator
        from honeypot.simulators.vault_cli import VaultCliSimulator

        for sim_cls in (NmapSimulator, FileReadSimulator, ShellExecSimulator,
                        SqlmapSimulator, BrowserSimulator, DnsLookupSimulator,
                        AwsCliSimulator, KubectlSimulator, VaultCliSimulator,
                        DockerRegistrySimulator):
            self.register(sim_cls(self.config))
