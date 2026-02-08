"""Tests for honey token generation."""

from honeypot.tokens import HoneyTokenGenerator, TokenType


def test_aws_access_key_format():
    gen = HoneyTokenGenerator()
    token = gen.generate(TokenType.AWS_ACCESS_KEY, "session123")
    lines = token.split("\n")
    assert lines[0].startswith("aws_access_key_id=AKIA")
    assert lines[1].startswith("aws_secret_access_key=")
    # Key ID should be 20+ chars
    key_id = lines[0].split("=")[1]
    assert len(key_id) >= 20


def test_api_token_jwt_format():
    gen = HoneyTokenGenerator()
    token = gen.generate(TokenType.API_TOKEN, "session123")
    assert token.startswith("eyJ")
    parts = token.split(".")
    assert len(parts) == 3


def test_db_credential_format():
    gen = HoneyTokenGenerator()
    token = gen.generate(TokenType.DB_CREDENTIAL, "session123")
    assert token.startswith("postgresql://")
    assert "@db-internal.corp.local:5432/production" in token


def test_admin_login_format():
    gen = HoneyTokenGenerator()
    token = gen.generate(TokenType.ADMIN_LOGIN, "session123")
    parts = token.split(":", 1)
    assert parts[0] == "admin"
    assert len(parts[1]) > 8


def test_ssh_key_format():
    gen = HoneyTokenGenerator()
    token = gen.generate(TokenType.SSH_KEY, "session123")
    assert "-----BEGIN OPENSSH PRIVATE KEY-----" in token
    assert "-----END OPENSSH PRIVATE KEY-----" in token


def test_tokens_are_unique():
    gen = HoneyTokenGenerator()
    tokens = set()
    for _ in range(10):
        token = gen.generate(TokenType.API_TOKEN, "session123")
        tokens.add(token)
    assert len(tokens) == 10


def test_session_traceability():
    gen = HoneyTokenGenerator()
    t1 = gen.generate(TokenType.AWS_ACCESS_KEY, "session_aaa")
    t2 = gen.generate(TokenType.AWS_ACCESS_KEY, "session_bbb")

    # Different sessions should produce different key IDs (because of session hash)
    key1 = t1.split("\n")[0].split("=")[1]
    key2 = t2.split("\n")[0].split("=")[1]
    assert key1 != key2

    # Same session hash prefix should be embedded
    import hashlib
    hash_a = hashlib.sha256(b"session_aaa").hexdigest()[:8].upper()
    assert hash_a in key1


def test_all_token_types_generate():
    gen = HoneyTokenGenerator()
    for token_type in TokenType:
        token = gen.generate(token_type, "test_session")
        assert len(token) > 0
