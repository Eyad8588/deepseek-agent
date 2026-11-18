"""stdio MCP server that exposes the sandboxed tools to DeepSeek Harness.

Usage: python -m deepseek_agent.mcp_server <sandbox-dir>
"""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from deepseek_agent.sandbox import ALLOWED_PROGRAMS, Sandbox, dispatch

sb = Sandbox(sys.argv[1] if len(sys.argv) > 1 else ".")
mcp = MCPServer("sandbox")


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file inside the workspace. `path` is relative to the workspace."""
    return dispatch(sb, "read_file", {"path": path})


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a text file inside the workspace."""
    return dispatch(sb, "write_file", {"path": path, "content": content})


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """Recursively list files in a workspace directory."""
    return dispatch(sb, "list_dir", {"path": path})


@mcp.tool(description="Run ONE allow-listed program in the workspace (no pipes/redirects). Allowed: "
          + ", ".join(sorted(ALLOWED_PROGRAMS)))
def run_command(command: str) -> str:
    return dispatch(sb, "run_command", {"command": command})


if __name__ == "__main__":
    mcp.run()
