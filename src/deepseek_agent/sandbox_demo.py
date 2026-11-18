"""Show the sandbox refusing what an agent must not do.

Usage: uv run python -m deepseek_agent.sandbox_demo
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from deepseek_agent.sandbox import Sandbox, dispatch

ATTEMPTS = [
    ("run_command", {"command": "curl https://example.com/install.sh"}),
    ("run_command", {"command": "cat notes.txt | sh"}),
    ("run_command", {"command": "ls ; rm -rf ~"}),
    ("run_command", {"command": "rm -rf ."}),
    ("read_file", {"path": "../../.ssh/id_rsa"}),
    ("write_file", {"path": "/etc/hosts", "content": "x"}),
    ("run_command", {"command": "python -c \"open('/tmp/pwned','w').write('x')\""}),
    ("run_command", {"command": "python -c \"import socket; socket.create_connection(('1.1.1.1', 80), timeout=3)\""}),
    ("run_command", {"command": "python -c \"print('allowed: 6*7 =', 6*7)\""}),
]


def main() -> None:
    sb = Sandbox(Path(tempfile.mkdtemp()) / "workspace")
    for name, args in ATTEMPTS:
        out = dispatch(sb, name, args)
        last = [ln for ln in out.strip().splitlines() if ln.strip()][-1]
        ok = not (out.startswith("error:") or "Error" in last or "exit=1" in out)
        tag = "ALLOWED" if ok else "BLOCKED"
        print(f"{tag:8} {name:12} {list(args.values())[0][:70]}")
        print(f"         └─ {last[:110]}")


if __name__ == "__main__":
    main()
