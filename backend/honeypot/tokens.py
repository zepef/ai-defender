"""Honey token generator.

Produces fake credentials that embed a session hash derivative for traceability.
Each token can be traced back to the attacker session that received it.
"""

from __future__ import annotations

import hashlib
import secrets
import string
from enum import Enum


class TokenType(Enum):
    AWS_ACCESS_KEY = "aws_access_key"
    API_TOKEN = "api_token"
    DB_CREDENTIAL = "db_credential"
    ADMIN_LOGIN = "admin_login"
    SSH_KEY = "ssh_key"


class HoneyTokenGenerator:
    def __init__(self) -> None:
        self._counter = 0

    def _session_hash(self, session_id: str) -> str:
        return hashlib.sha256(session_id.encode()).hexdigest()[:8]

    def _random_string(self, length: int, charset: str | None = None) -> str:
        chars = charset or (string.ascii_letters + string.digits)
        return "".join(secrets.choice(chars) for _ in range(length))

    def generate(self, token_type: TokenType, session_id: str) -> str:
        self._counter += 1
        tag = self._session_hash(session_id)

        match token_type:
            case TokenType.AWS_ACCESS_KEY:
                return self._generate_aws_key(tag)
            case TokenType.API_TOKEN:
                return self._generate_api_token(tag)
            case TokenType.DB_CREDENTIAL:
                return self._generate_db_credential(tag)
            case TokenType.ADMIN_LOGIN:
                return self._generate_admin_login(tag)
            case TokenType.SSH_KEY:
                return self._generate_ssh_key(tag)

    def _generate_aws_key(self, tag: str) -> str:
        suffix = self._random_string(12, string.ascii_uppercase + string.digits)
        key_id = "AKIA" + tag.upper() + suffix
        secret = self._random_string(40, string.ascii_letters + string.digits + "+/")
        return f"aws_access_key_id={key_id}\naws_secret_access_key={secret}"

    def _generate_api_token(self, tag: str) -> str:
        # JWT-like format with the tag embedded in the payload section
        header = self._random_string(20, string.ascii_letters + string.digits)
        payload = tag + self._random_string(30, string.ascii_letters + string.digits)
        signature = self._random_string(22, string.ascii_letters + string.digits + "-_")
        return f"eyJ{header}.{payload}.{signature}"

    def _generate_db_credential(self, tag: str) -> str:
        password = tag + self._random_string(16, string.ascii_letters + string.digits + "!@#$%")
        return f"postgresql://admin:{password}@db-internal.corp.local:5432/production"

    def _generate_admin_login(self, tag: str) -> str:
        password = "Adm1n" + tag + self._random_string(8, string.digits + "!@#")
        return f"admin:{password}"

    def _generate_ssh_key(self, tag: str) -> str:
        key_body = self._random_string(68, string.ascii_letters + string.digits + "+/")
        # Embed the tag in the key body
        key_body = key_body[:16] + tag + key_body[24:]
        return (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            f"b3BlbnNzaC1rZXktdjEAAAAA{key_body}\n"
            f"{self._random_string(68, string.ascii_letters + string.digits + '+/')}\n"
            f"{self._random_string(40, string.ascii_letters + string.digits + '+/')}==\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
