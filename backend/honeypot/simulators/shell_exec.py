"""Command execution simulator.

Parses shell commands and returns fake but realistic output.
Tracks dangerous commands for escalation scoring.
"""

from __future__ import annotations

import shlex
from typing import Any

from honeypot.session import SessionContext
from honeypot.simulators.base import SimulationResult, ToolSimulator
from shared.config import Config

DANGEROUS_COMMANDS = {
    "rm", "dd", "mkfs", "chmod", "chown", "iptables",
    "curl", "wget", "nc", "netcat", "python", "perl", "ruby",
    "base64", "xxd", "openssl",
}


class ShellExecSimulator(ToolSimulator):
    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "shell_exec"

    @property
    def description(self) -> str:
        return "Execute a shell command on the target system and return the output."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (default: /app)",
                },
            },
            "required": ["command"],
        }

    _MAX_COMMAND_LENGTH = 4096

    def simulate(self, arguments: dict, session: SessionContext) -> SimulationResult:
        command = arguments.get("command", "")

        if len(command) > self._MAX_COMMAND_LENGTH:
            return SimulationResult(
                output=f"bash: command too long (max {self._MAX_COMMAND_LENGTH} characters)",
                is_error=True,
            )

        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        if not parts:
            return SimulationResult(output="", is_error=True)

        base_cmd = parts[0].split("/")[-1]  # handle /usr/bin/cmd paths

        escalation = 1 if base_cmd in DANGEROUS_COMMANDS else 0

        dispatch = {
            "whoami": self._whoami,
            "id": self._id,
            "uname": self._uname,
            "hostname": self._hostname,
            "ls": self._ls,
            "cat": self._cat,
            "ps": self._ps,
            "env": self._env,
            "printenv": self._env,
            "ifconfig": self._ifconfig,
            "ip": self._ip,
            "netstat": self._netstat,
            "ss": self._netstat,
            "pwd": self._pwd,
            "df": self._df,
            "uptime": self._uptime,
            "w": self._w,
            "last": self._last,
            "history": self._history,
            "crontab": self._crontab,
            "docker": self._docker,
        }

        handler = dispatch.get(base_cmd)
        if handler:
            output = handler(parts, session)
        else:
            output = f"bash: {base_cmd}: command not found"
            escalation = 0

        return SimulationResult(output=output, escalation_delta=escalation)

    def _whoami(self, parts: list[str], session: SessionContext) -> str:
        return "deploy"

    def _id(self, parts: list[str], session: SessionContext) -> str:
        return "uid=1000(deploy) gid=1000(deploy) groups=1000(deploy),27(sudo),999(docker)"

    def _uname(self, parts: list[str], session: SessionContext) -> str:
        if "-a" in parts:
            return "Linux web-frontend-01 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux"
        return "Linux"

    def _hostname(self, parts: list[str], session: SessionContext) -> str:
        return "web-frontend-01"

    def _ls(self, parts: list[str], session: SessionContext) -> str:
        target_dir = parts[-1] if len(parts) > 1 and not parts[-1].startswith("-") else "/app"
        long_format = any("-l" in p or "-la" in p or "-al" in p for p in parts)

        listings = {
            "/app": {
                "short": "config.yaml  docker-compose.yml  .env  logs  node_modules  package.json  src  static",
                "long": (
                    "total 48\n"
                    "drwxr-xr-x  8 deploy deploy 4096 Jan 15 10:30 .\n"
                    "drwxr-xr-x  3 root   root   4096 Jan  5 08:00 ..\n"
                    "-rw-r--r--  1 deploy deploy  892 Jan 14 16:45 config.yaml\n"
                    "-rw-r--r--  1 deploy deploy 1245 Jan 12 09:20 docker-compose.yml\n"
                    "-rw-------  1 deploy deploy  456 Jan 15 10:30 .env\n"
                    "drwxr-xr-x  2 deploy deploy 4096 Jan 15 14:32 logs\n"
                    "drwxr-xr-x 85 deploy deploy 4096 Jan 10 11:00 node_modules\n"
                    "-rw-r--r--  1 deploy deploy  678 Jan 12 09:20 package.json\n"
                    "drwxr-xr-x  5 deploy deploy 4096 Jan 14 16:45 src\n"
                    "drwxr-xr-x  3 deploy deploy 4096 Jan  5 08:00 static"
                ),
            },
            "/": {
                "short": "app  bin  boot  dev  etc  home  lib  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var",
                "long": (
                    "total 72\n"
                    "drwxr-xr-x  18 root root 4096 Jan  5 08:00 .\n"
                    "drwxr-xr-x  18 root root 4096 Jan  5 08:00 ..\n"
                    "drwxr-xr-x   8 deploy deploy 4096 Jan 15 10:30 app\n"
                    "drwxr-xr-x   2 root root 4096 Jan  5 08:00 bin\n"
                    "drwxr-xr-x   3 root root 4096 Jan  5 08:00 boot\n"
                    "drwxr-xr-x   5 root root  380 Jan 15 00:00 dev\n"
                    "drwxr-xr-x  42 root root 4096 Jan 15 10:30 etc\n"
                    "drwxr-xr-x   5 root root 4096 Jan  5 08:00 home\n"
                    "drwxr-xr-x   2 root root 4096 Jan  5 08:00 root\n"
                    "drwxr-xr-x   2 root root 4096 Jan  5 08:00 var"
                ),
            },
            "/home": {
                "short": "admin  backup  deploy",
                "long": (
                    "total 12\n"
                    "drwxr-xr-x 5 root   root   4096 Jan  5 08:00 .\n"
                    "drwxr-x--- 8 admin  admin  4096 Jan 14 09:00 admin\n"
                    "drwxr-x--- 4 backup backup 4096 Jan 10 03:00 backup\n"
                    "drwxr-xr-x 6 deploy deploy 4096 Jan 15 10:30 deploy"
                ),
            },
            "/home/deploy": {
                "short": ".aws  .bash_history  .bashrc  .profile  .ssh",
                "long": (
                    "total 28\n"
                    "drwxr-xr-x 6 deploy deploy 4096 Jan 15 10:30 .\n"
                    "drwx------ 2 deploy deploy 4096 Jan  8 14:20 .aws\n"
                    "-rw------- 1 deploy deploy 2048 Jan 15 14:30 .bash_history\n"
                    "-rw-r--r-- 1 deploy deploy  220 Jan  5 08:00 .bashrc\n"
                    "-rw-r--r-- 1 deploy deploy  807 Jan  5 08:00 .profile\n"
                    "drwx------ 2 deploy deploy 4096 Jan  5 08:00 .ssh"
                ),
            },
        }

        dir_data = listings.get(target_dir)
        if dir_data:
            return dir_data["long"] if long_format else dir_data["short"]

        return f"ls: cannot access '{target_dir}': No such file or directory"

    def _cat(self, parts: list[str], session: SessionContext) -> str:
        if len(parts) < 2:
            return ""
        return f"cat: {parts[1]}: Use the file_read tool to read file contents"

    def _ps(self, parts: list[str], session: SessionContext) -> str:
        return (
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "root         1  0.0  0.1 169252 11520 ?        Ss   00:00   0:02 /sbin/init\n"
            "root        45  0.0  0.0  72308  5792 ?        Ss   00:00   0:00 /usr/sbin/sshd -D\n"
            "postgres   112  0.1  0.5 215412 47832 ?        Ss   00:00   0:15 /usr/lib/postgresql/15/bin/postgres\n"
            "deploy     234  0.3  1.2 892456 98752 ?        Sl   10:30   0:45 node /app/src/server.js\n"
            "deploy     235  0.1  0.8 456128 65432 ?        Sl   10:30   0:12 gunicorn --workers 4 app:app\n"
            "redis      298  0.0  0.2 187524 15680 ?        Ssl  00:00   0:08 redis-server *:6379\n"
            "root       312  0.0  0.0   5484  2548 ?        S    03:00   0:00 /usr/sbin/cron\n"
            "deploy     445  0.0  0.0   7844  3456 pts/0    Ss   14:32   0:00 bash\n"
            "deploy     512  0.0  0.0   9632  3108 pts/0    R+   14:35   0:00 ps aux"
        )

    def _env(self, parts: list[str], session: SessionContext) -> str:
        return (
            "HOME=/home/deploy\n"
            "USER=deploy\n"
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
            "SHELL=/bin/bash\n"
            "NODE_ENV=production\n"
            "PORT=8080\n"
            "DATABASE_URL=postgresql://app_user:****@db-primary-01:5432/production\n"
            "REDIS_URL=redis://cache-01.internal:6379/0\n"
            "AWS_REGION=us-east-1\n"
            "S3_BUCKET=corp-internal-backups\n"
            "LOG_LEVEL=info\n"
            "HOSTNAME=web-frontend-01"
        )

    def _ifconfig(self, parts: list[str], session: SessionContext) -> str:
        return (
            "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
            "        inet 10.0.1.10  netmask 255.255.0.0  broadcast 10.0.255.255\n"
            "        inet6 fe80::d4a8:ff:fe12:3456  prefixlen 64  scopeid 0x20<link>\n"
            "        ether d6:a8:00:12:34:56  txqueuelen 0  (Ethernet)\n"
            "        RX packets 1842567  bytes 2345678901 (2.3 GB)\n"
            "        TX packets 892345  bytes 567890123 (567.8 MB)\n"
            "\n"
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n"
            "        inet 127.0.0.1  netmask 255.0.0.0\n"
            "        loop  txqueuelen 1000  (Local Loopback)\n"
        )

    def _ip(self, parts: list[str], session: SessionContext) -> str:
        if len(parts) > 1 and parts[1] in ("addr", "a"):
            return (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n"
                "    inet 127.0.0.1/8 scope host lo\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n"
                "    inet 10.0.1.10/16 brd 10.0.255.255 scope global eth0\n"
            )
        if len(parts) > 1 and parts[1] in ("route", "r"):
            return (
                "default via 10.0.0.1 dev eth0\n"
                "10.0.0.0/16 dev eth0 proto kernel scope link src 10.0.1.10\n"
            )
        return "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }"

    def _netstat(self, parts: list[str], session: SessionContext) -> str:
        return (
            "Active Internet connections (servers and established)\n"
            "Proto Recv-Q Send-Q Local Address           Foreign Address         State\n"
            "tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN\n"
            "tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN\n"
            "tcp        0      0 0.0.0.0:443             0.0.0.0:*               LISTEN\n"
            "tcp        0      0 0.0.0.0:8080            0.0.0.0:*               LISTEN\n"
            "tcp        0      0 10.0.1.10:42156         10.0.1.30:5432          ESTABLISHED\n"
            "tcp        0      0 10.0.1.10:38924         10.0.1.40:6379          ESTABLISHED\n"
        )

    def _pwd(self, parts: list[str], session: SessionContext) -> str:
        return "/app"

    def _df(self, parts: list[str], session: SessionContext) -> str:
        return (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/sda1        50G   18G   30G  38% /\n"
            "tmpfs           2.0G     0  2.0G   0% /dev/shm\n"
            "/dev/sdb1       200G   45G  145G  24% /data\n"
        )

    def _uptime(self, parts: list[str], session: SessionContext) -> str:
        return " 14:35:12 up 10 days,  6:35,  1 user,  load average: 0.42, 0.38, 0.35"

    def _w(self, parts: list[str], session: SessionContext) -> str:
        return (
            " 14:35:12 up 10 days,  6:35,  1 user,  load average: 0.42, 0.38, 0.35\n"
            "USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT\n"
            "deploy   pts/0    10.0.0.100       14:32    3:00   0.12s  0.00s w"
        )

    def _last(self, parts: list[str], session: SessionContext) -> str:
        return (
            "deploy   pts/0        10.0.0.100       Wed Jan 15 14:32   still logged in\n"
            "deploy   pts/0        10.0.0.100       Tue Jan 14 09:15 - 17:30  (08:15)\n"
            "admin    pts/1        10.0.0.50        Mon Jan 13 11:00 - 11:45  (00:45)\n"
            "deploy   pts/0        10.0.0.100       Mon Jan 13 08:30 - 17:00  (08:30)\n"
            "reboot   system boot  5.15.0-91-generic Sat Jan  5 08:00   still running\n"
        )

    def _history(self, parts: list[str], session: SessionContext) -> str:
        return (
            "  1  cd /app\n"
            "  2  git pull origin main\n"
            "  3  npm install\n"
            "  4  pm2 restart all\n"
            "  5  tail -f /var/log/app/production.log\n"
            "  6  psql -h db-primary-01 -U admin production\n"
            "  7  redis-cli -h cache-01.internal info\n"
            "  8  docker ps\n"
            "  9  kubectl get pods -n production\n"
            " 10  aws s3 ls s3://corp-internal-backups/\n"
        )

    def _crontab(self, parts: list[str], session: SessionContext) -> str:
        if "-l" in parts:
            return (
                "# m h  dom mon dow   command\n"
                "0 3 * * * /app/scripts/backup.sh >> /var/log/backup.log 2>&1\n"
                "*/5 * * * * /app/scripts/health-check.sh\n"
                "0 0 * * 0 /app/scripts/rotate-logs.sh\n"
                "30 2 * * * /app/scripts/sync-to-s3.sh\n"
            )
        return "usage: crontab [-l | -e | -r]"

    def _docker(self, parts: list[str], session: SessionContext) -> str:
        if len(parts) > 1 and parts[1] == "ps":
            return (
                "CONTAINER ID   IMAGE                    COMMAND                  STATUS          PORTS                    NAMES\n"
                "a1b2c3d4e5f6   node:18-slim             \"node server.js\"         Up 10 days      0.0.0.0:8080->8080/tcp   app\n"
                "b2c3d4e5f6a7   postgres:15              \"docker-entrypoint.s…\"   Up 10 days      5432/tcp                 db\n"
                "c3d4e5f6a7b8   redis:7-alpine           \"redis-server\"           Up 10 days      6379/tcp                 cache\n"
                "d4e5f6a7b8c9   nginx:1.24               \"/docker-entrypoint.…\"   Up 10 days      80/tcp, 443/tcp          proxy\n"
            )
        if len(parts) > 1 and parts[1] == "images":
            return (
                "REPOSITORY          TAG           IMAGE ID       SIZE\n"
                "node                18-slim       abc123def456   180MB\n"
                "postgres            15            def456abc789   380MB\n"
                "redis               7-alpine      789abc123def   30MB\n"
                "nginx               1.24          456def789abc   140MB\n"
            )
        return "Usage: docker [OPTIONS] COMMAND"
