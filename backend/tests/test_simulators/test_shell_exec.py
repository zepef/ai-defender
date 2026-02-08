"""Tests for shell execution simulator."""


def test_whoami(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
    assert result.output.startswith("deploy")
    assert result.is_error is False


def test_id_command(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "id"}, session_id)
    assert "uid=1000(deploy)" in result.output
    assert "sudo" in result.output


def test_uname_a(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "uname -a"}, session_id)
    assert "Linux" in result.output
    assert "x86_64" in result.output


def test_hostname(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "hostname"}, session_id)
    assert "web-frontend-01" in result.output


def test_ls_app(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "ls -la /app"}, session_id)
    assert ".env" in result.output
    assert "config.yaml" in result.output


def test_ls_home(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "ls /home/deploy"}, session_id)
    assert ".aws" in result.output
    assert ".ssh" in result.output


def test_ps_aux(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "ps aux"}, session_id)
    assert "postgres" in result.output
    assert "node" in result.output
    assert "redis" in result.output


def test_env_command(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "env"}, session_id)
    assert "NODE_ENV=production" in result.output
    assert "DATABASE_URL" in result.output


def test_ifconfig(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "ifconfig"}, session_id)
    assert "10.0.1.10" in result.output
    assert "eth0" in result.output


def test_netstat(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "netstat -tlnp"}, session_id)
    assert "LISTEN" in result.output
    assert "5432" in result.output


def test_docker_ps(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "docker ps"}, session_id)
    assert "node:18-slim" in result.output
    assert "postgres:15" in result.output


def test_unknown_command(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "hackertool"}, session_id)
    assert "command not found" in result.output


def test_crontab(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "crontab -l"}, session_id)
    assert "backup.sh" in result.output


def test_history(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "history"}, session_id)
    assert "git pull" in result.output
    assert "psql" in result.output
