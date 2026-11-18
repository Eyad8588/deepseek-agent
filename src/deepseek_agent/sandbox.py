"""Sandboxed tools shared by the Harness agent (through MCP) and the baseline loop.

Every path is resolved and must stay inside the sandbox root, and symlinks are
followed before the check. The shell tool runs a single allow-listed program
with no shell, so pipes, redirects, `;` and `&&` are never interpreted. On
macOS the command also runs under `sandbox-exec`, which denies network access
and denies writes outside the sandbox.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ALLOWED_PROGRAMS = {
    "ls", "cat", "head", "tail", "wc", "grep", "sort", "uniq", "diff", "find",
    "echo", "pwd", "mkdir", "touch", "cp", "mv", "python", "python3", "pytest",
}
FORBIDDEN_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<", "`", "$("}
MAX_OUTPUT = 8_000
TIMEOUT_S = 30

_SEATBELT = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath "{root}") (literal "/dev/null"))
"""


class SandboxError(Exception):
    pass


class Sandbox:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths -------------------------------------------------------------
    def resolve(self, rel: str) -> Path:
        p = Path(rel)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        if p != self.root and self.root not in p.parents:
            raise SandboxError(f"path escapes sandbox: {rel}")
        return p

    # -- tools -------------------------------------------------------------
    def read_file(self, path: str) -> str:
        p = self.resolve(path)
        if not p.is_file():
            raise SandboxError(f"no such file: {path}")
        text = p.read_text(errors="replace")
        return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + "\n…[truncated]"

    def write_file(self, path: str, content: str) -> str:
        p = self.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} bytes to {p.relative_to(self.root)}"

    def list_dir(self, path: str = ".") -> str:
        p = self.resolve(path)
        if not p.is_dir():
            raise SandboxError(f"not a directory: {path}")
        out = []
        for c in sorted(p.rglob("*")):
            if "__pycache__" in c.parts or ".pytest_cache" in c.parts:
                continue
            out.append(str(c.relative_to(self.root)) + ("/" if c.is_dir() else ""))
        return "\n".join(out) or "(empty)"

    def run_command(self, command: str) -> str:
        try:
            argv = shlex.split(command)
        except ValueError as e:
            raise SandboxError(f"cannot parse command: {e}") from e
        if not argv:
            raise SandboxError("empty command")
        if any(t in FORBIDDEN_TOKENS or "$(" in t or "`" in t for t in argv):
            raise SandboxError("shell operators are not allowed; run one program per call")
        prog = os.path.basename(argv[0])
        if prog not in ALLOWED_PROGRAMS:
            raise SandboxError(f"program not allowed: {prog}. Allowed: {', '.join(sorted(ALLOWED_PROGRAMS))}")
        if prog in {"python", "python3"}:
            argv = [sys.executable, "-B", *argv[1:]]
        elif prog == "pytest":
            argv = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *argv[1:]]
        else:
            resolved = shutil.which(prog)
            if not resolved:
                raise SandboxError(f"program not found: {prog}")
            argv = [resolved, *argv[1:]]
        if sys.platform == "darwin" and shutil.which("sandbox-exec"):
            argv = ["sandbox-exec", "-p", _SEATBELT.format(root=self.root), *argv]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.root), "LANG": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            r = subprocess.run(argv, cwd=self.root, env=env, capture_output=True,
                               text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return f"timed out after {TIMEOUT_S}s"
        out = (r.stdout + (("\n[stderr]\n" + r.stderr) if r.stderr else "")).strip()
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n…[truncated]"
        return f"exit={r.returncode}\n{out}"


# OpenAI-style schemas, used by the baseline; the MCP server derives the same from signatures.
TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a UTF-8 text file inside the workspace.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path relative to the workspace"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a text file inside the workspace.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "Recursively list files in a workspace directory.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run ONE allow-listed program in the workspace (no pipes/redirects). Allowed: " + ", ".join(sorted(ALLOWED_PROGRAMS)),
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


def dispatch(sb: Sandbox, name: str, args: dict) -> str:
    fn = {"read_file": sb.read_file, "write_file": sb.write_file,
          "list_dir": sb.list_dir, "run_command": sb.run_command}.get(name)
    if fn is None:
        return f"error: unknown tool {name}"
    try:
        return fn(**args)
    except (SandboxError, TypeError, OSError) as e:
        return f"error: {e}"
