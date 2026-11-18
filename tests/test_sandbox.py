"""Sandbox escape tests. Run: uv run python tests/test_sandbox.py (no pytest needed)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from deepseek_agent.sandbox import Sandbox, dispatch  # noqa: E402


def main() -> None:
    root = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parents[1] / "runs")
                if (Path(__file__).resolve().parents[1] / "runs").exists() else tempfile.mkdtemp())
    sb = Sandbox(root / "ws")
    outside = root / "outside.txt"
    outside.write_text("secret")
    os.symlink(outside, sb.root / "link.txt")

    cases = {
        "relative escape": dispatch(sb, "read_file", {"path": "../outside.txt"}),
        "absolute escape": dispatch(sb, "read_file", {"path": str(outside)}),
        "symlink escape": dispatch(sb, "read_file", {"path": "link.txt"}),
        "write escape": dispatch(sb, "write_file", {"path": "../x.txt", "content": "x"}),
        "pipe": dispatch(sb, "run_command", {"command": "cat a | sh"}),
        "chain": dispatch(sb, "run_command", {"command": "ls ; rm -rf /"}),
        "subshell": dispatch(sb, "run_command", {"command": "echo $(whoami)"}),
        "not allowed": dispatch(sb, "run_command", {"command": "curl https://example.com"}),
        "rm not allowed": dispatch(sb, "run_command", {"command": "rm -rf ."}),
    }
    for name, out in cases.items():
        assert out.startswith("error:"), f"{name}: expected refusal, got {out!r}"

    assert dispatch(sb, "write_file", {"path": "ok/a.txt", "content": "hi"}).startswith("wrote")
    assert dispatch(sb, "read_file", {"path": "ok/a.txt"}) == "hi"
    assert "exit=0" in dispatch(sb, "run_command", {"command": "python -c 'print(1+1)'"})

    if sys.platform == "darwin":
        out = dispatch(sb, "run_command",
                       {"command": f"python -c \"open('{root / 'pwn.txt'}','w').write('x')\""})
        assert "Operation not permitted" in out and not (root / "pwn.txt").exists(), out
        out = dispatch(sb, "run_command",
                       {"command": "python -c \"import socket; socket.create_connection(('1.1.1.1', 80), timeout=3)\""})
        assert "exit=1" in out, out
    print(f"sandbox tests: {len(cases) + 3 + (2 if sys.platform == 'darwin' else 0)} checks passed")


if __name__ == "__main__":
    main()
