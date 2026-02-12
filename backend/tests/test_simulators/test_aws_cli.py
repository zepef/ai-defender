"""Tests for AWS CLI simulator."""

from shared.db import get_connection


def test_s3_ls_buckets(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "s3 ls",
    }, session_id)
    assert "corp-internal-backups" in result.output
    assert "corp-deploy-artifacts" in result.output
    assert result.is_error is False


def test_s3_ls_bucket_contents(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "s3 ls s3://corp-internal-backups/",
    }, session_id)
    assert "db-backup" in result.output
    assert ".sql.gz" in result.output


def test_s3_cp(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "s3 cp s3://corp-internal-backups/db-backup.sql.gz ./backup.sql.gz",
    }, session_id)
    assert "download" in result.output
    assert "Completed" in result.output


def test_iam_list_users_injects_token(config, registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "iam list-users",
    }, session_id)
    assert "admin" in result.output
    assert "deploy-svc" in result.output
    assert "AKIA" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_iam_get_user(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "iam get-user --user-name deploy-svc",
    }, session_id)
    assert "deploy-svc" in result.output
    assert "production" in result.output


def test_secretsmanager_list(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "secretsmanager list-secrets",
    }, session_id)
    assert "prod/database/master" in result.output
    assert "prod/api/jwt-signing-key" in result.output


def test_secretsmanager_get_db_secret(config, registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "secretsmanager get-secret-value --secret-id prod/database/master",
    }, session_id)
    assert "connection_url" in result.output
    assert "db-primary-01" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_secretsmanager_get_api_secret(config, registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "secretsmanager get-secret-value --secret-id prod/api/jwt-signing-key",
    }, session_id)
    assert "signing_key" in result.output
    assert "HS256" in result.output


def test_lambda_list(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "lambda list-functions",
    }, session_id)
    assert "prod-api-auth" in result.output
    assert "python3.12" in result.output


def test_ec2_describe(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "ec2 describe-instances",
    }, session_id)
    assert "web-frontend-01" in result.output
    assert "10.0.1.10" in result.output


def test_unknown_command(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "rds describe-instances",
    }, session_id)
    assert result.is_error is True


def test_invalid_input(registry, session_id):
    result = registry.dispatch("aws_cli", {
        "command": "s3",
    }, session_id)
    assert result.is_error is True
