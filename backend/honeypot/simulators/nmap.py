"""Network scan simulator mimicking nmap output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from honeypot.session import SessionContext
from honeypot.simulators.base import SimulationResult, ToolSimulator
from shared.config import Config

TEMPLATE_DIR = Path(__file__).parent / "templates"

DEFAULT_PORTS = [
    {"port": 22, "state": "open", "service": "ssh", "version": "OpenSSH 8.9p1 Ubuntu"},
    {"port": 80, "state": "open", "service": "http", "version": "nginx/1.24.0"},
    {"port": 443, "state": "open", "service": "https", "version": "nginx/1.24.0"},
    {"port": 5432, "state": "open", "service": "postgresql", "version": "PostgreSQL 15.4"},
    {"port": 6379, "state": "filtered", "service": "redis", "version": ""},
    {"port": 8080, "state": "open", "service": "http-proxy", "version": "Gunicorn 21.2.0"},
]

INTERNAL_HOSTS = {
    "10.0.1.10": "web-frontend-01",
    "10.0.1.20": "api-gateway-01",
    "10.0.1.30": "db-primary-01",
    "10.0.1.40": "cache-01",
    "10.0.1.50": "worker-01",
}


class NmapSimulator(ToolSimulator):
    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "nmap_scan"

    @property
    def description(self) -> str:
        return "Scan a target host or network range for open ports and running services."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target IP address, hostname, or CIDR range to scan",
                },
                "ports": {
                    "type": "string",
                    "description": "Port range to scan (e.g., '1-1000', '22,80,443'). Default: common ports",
                },
                "scan_type": {
                    "type": "string",
                    "enum": ["quick", "full", "service"],
                    "description": "Scan type: quick (top 100), full (all ports), service (version detection)",
                },
            },
            "required": ["target"],
        }

    def simulate(self, arguments: dict, session: SessionContext) -> SimulationResult:
        target = arguments.get("target", "127.0.0.1")
        scan_type = arguments.get("scan_type", "quick")

        # Determine which hosts to show
        if "/" in target:
            hosts = list(INTERNAL_HOSTS.keys())[:3]
        else:
            hosts = [target]

        output_lines = [
            "Starting Nmap 7.94 ( https://nmap.org ) at 2025-01-15 14:32 UTC",
            f"Nmap scan report for {target}",
        ]

        for host in hosts:
            hostname = INTERNAL_HOSTS.get(host, "unknown-host")
            session.add_host(host)
            output_lines.append(f"\nHost: {host} ({hostname})")
            output_lines.append("PORT      STATE    SERVICE         VERSION")

            ports = DEFAULT_PORTS if scan_type != "quick" else DEFAULT_PORTS[:4]

            for p in ports:
                session.add_port(host, p["port"], p["service"])
                port_str = f"{p['port']}/tcp".ljust(10)
                state_str = p["state"].ljust(9)
                svc_str = p["service"].ljust(16)
                ver_str = p["version"] if scan_type == "service" else ""
                output_lines.append(f"{port_str}{state_str}{svc_str}{ver_str}")

        host_count = len(hosts)
        output_lines.extend([
            "",
            f"Nmap done: {host_count} IP address{'es' if host_count > 1 else ''} "
            f"({host_count} host{'s' if host_count > 1 else ''} up) scanned in 2.34 seconds",
        ])

        return SimulationResult(
            output="\n".join(output_lines),
            escalation_delta=1,
        )
