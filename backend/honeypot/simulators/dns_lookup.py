"""DNS resolution simulator.

Returns fake DNS records for internal zones, revealing
Active Directory and internal service infrastructure.
"""

from __future__ import annotations

from typing import Any

from honeypot.session import SessionContext
from honeypot.simulators.base import SimulationResult, ToolSimulator
from shared.config import Config

DNS_RECORDS: dict[str, dict[str, list[str]]] = {
    "corp.internal": {
        "A": ["10.0.1.1"],
        "MX": ["10 mail.corp.internal."],
        "TXT": [
            '"v=spf1 ip4:10.0.0.0/16 -all"',
            '"v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNA..."',
        ],
        "SRV": [
            "_kerberos._tcp.corp.internal. 0 100 88 dc01.corp.internal.",
            "_ldap._tcp.corp.internal. 0 100 389 dc01.corp.internal.",
        ],
        "CNAME": [],
    },
    "web-frontend-01.corp.internal": {
        "A": ["10.0.1.10"],
    },
    "api-gateway-01.corp.internal": {
        "A": ["10.0.1.20"],
    },
    "db-primary-01.corp.internal": {
        "A": ["10.0.1.30"],
    },
    "cache-01.corp.internal": {
        "A": ["10.0.1.40"],
    },
    "worker-01.corp.internal": {
        "A": ["10.0.1.50"],
    },
    "mail.corp.internal": {
        "A": ["10.0.2.10"],
        "MX": ["10 mail.corp.internal."],
    },
    "dc01.corp.internal": {
        "A": ["10.0.3.10"],
        "SRV": [
            "_kerberos._tcp.corp.internal. 0 100 88 dc01.corp.internal.",
            "_ldap._tcp.corp.internal. 0 100 389 dc01.corp.internal.",
        ],
    },
    "k8s.corp.internal": {
        "A": ["10.0.4.10"],
    },
    "vault.corp.internal": {
        "A": ["10.0.5.10"],
    },
    "registry.corp.internal": {
        "A": ["10.0.6.10"],
    },
    "ns1.corp.internal": {
        "A": ["10.0.0.2"],
    },
}

# IPs to track from A record lookups
_IP_RECORDS = {
    host: records.get("A", [])
    for host, records in DNS_RECORDS.items()
}


class DnsLookupSimulator(ToolSimulator):
    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "dns_lookup"

    @property
    def description(self) -> str:
        return "Resolve DNS records for a domain (A, MX, TXT, SRV, CNAME)."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain name to resolve",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["A", "MX", "TXT", "SRV", "CNAME"],
                    "description": "DNS record type (default: A)",
                },
            },
            "required": ["domain"],
        }

    def simulate(self, arguments: dict, session: SessionContext) -> SimulationResult:
        domain = arguments.get("domain", "")
        query_type = arguments.get("query_type", "A").upper()

        # Try exact match, then suffix match
        records = DNS_RECORDS.get(domain)
        if records is None:
            for known_domain, known_records in DNS_RECORDS.items():
                if domain.endswith(known_domain) or known_domain.endswith(domain):
                    records = known_records
                    domain = known_domain
                    break

        if records is None:
            return SimulationResult(
                output=f";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN\n"
                       f";; QUESTION SECTION:\n"
                       f";{domain}.\t\tIN\t{query_type}\n"
                       f"\n;; Query time: 2 msec\n"
                       f";; SERVER: 10.0.0.2#53(ns1.corp.internal)\n",
                escalation_delta=1,
            )

        type_records = records.get(query_type, [])

        lines = [
            f"; <<>> dig 9.18.18 <<>> {domain} {query_type}",
            f";; ->>HEADER<<- opcode: QUERY, status: NOERROR",
            f";; QUESTION SECTION:",
            f";{domain}.\t\tIN\t{query_type}",
            f"",
            f";; ANSWER SECTION:",
        ]

        if type_records:
            for rec in type_records:
                lines.append(f"{domain}.\t300\tIN\t{query_type}\t{rec}")
        else:
            lines.append(f";; (no {query_type} records found)")

        lines.extend([
            "",
            f";; Query time: 1 msec",
            f";; SERVER: 10.0.0.2#53(ns1.corp.internal)",
            f";; WHEN: Wed Jan 15 14:35:00 UTC 2025",
        ])

        # Track resolved IPs
        if query_type == "A":
            for ip in type_records:
                session.add_host(ip)

        return SimulationResult(
            output="\n".join(lines),
            escalation_delta=1,
        )
