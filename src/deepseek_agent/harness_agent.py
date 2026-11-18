"""Agent built on DeepSeek Harness (`dsh`), driven through the Python SDK.

It uses the `sdk-minimal` profile plus a per-task Cordis patch that:
  * disables the full-access `persistent-bash`/terminal rows and the session-log upload
    (sdk-minimal already ships with the text read/write/edit tools off),
  * mounts our sandboxed tools as a stdio MCP server rooted at the task workspace.
The DeepSeek adapter is pointed at Ollama's OpenAI-compatible endpoint.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from deepseek_harness import DeepSeekHarness

from deepseek_agent.config import BASE_URL, PERSONA, TASK_TIMEOUT_S

PROVIDER = "deepseek-official"

PATCH_TEMPLATE = """\
- id: persistent-bash
  disabled: true
- id: terminal-bash
  disabled: true
- id: session-log-deepseek
  disabled: true
- id: plugin-package-inventory-deepseek
  disabled: true
- insert:
    - id: mcp-sandbox
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: sandbox
        transport: stdio
        command: {python}
        args: ['-m', 'deepseek_agent.mcp_server', '{workspace}']
"""


def write_patch(workspace: Path, out: Path) -> Path:
    out.write_text(PATCH_TEMPLATE.format(python=sys.executable, workspace=str(workspace)))
    return out


def _count_tool_calls(notifications) -> int:
    """Count distinct tool-call ids in the session-tree notifications (wire shape is SDK-owned)."""
    ids: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k in ("toolCallId", "tool_call_id", "callId"):
                if isinstance(o.get(k), str):
                    ids.add(o[k])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for n in notifications:
        walk(getattr(n, "payload", None) or getattr(n, "params", None) or getattr(n, "__dict__", {}))
    return len(ids)


def run_harness(prompt: str, workspace: Path, model: str, dsh_home: Path, patch_dir: Path,
                session_id: str, timeout_s: float = TASK_TIMEOUT_S) -> dict:
    workspace = workspace.resolve()
    patch = write_patch(workspace, patch_dir / f"{session_id}.patch.yml")
    env = {
        "DSH_SYSTEM_PROMPT": PERSONA,
        "DSH_CONTEXT_WINDOW": "12288",
        "DSH_TELEMETRY_MODE": "DISABLED",
    }
    seen: list = []
    t0 = time.monotonic()
    harness = DeepSeekHarness(
        dsh_home=str(dsh_home.resolve()), cwd=str(workspace), profile="sdk-minimal",
        provider=PROVIDER, model=model, max_tokens=8192, patches=(str(patch.resolve()),),
        env=env, base_url=BASE_URL, api_key="ollama",  # Ollama ignores the key; the adapter requires one
        initialize_timeout_seconds=120,
    )
    timed_out = threading.Event()

    def watchdog():
        timed_out.set()
        harness.close()  # kills the runtime; run() then raises

    timer = threading.Timer(timeout_s, watchdog)
    timer.start()
    startup = None
    try:
        harness.start()
        startup = time.monotonic() - t0
        result = harness.run(prompt, session_id=session_id, on_notification=seen.append)
        out = {"final": result.final_response, "finish": result.finish_reason}
    except Exception as e:  # noqa: BLE001
        if not timed_out.is_set():
            raise
        out = {"final": "", "finish": "timeout", "note": f"{type(e).__name__}"}
    finally:
        timer.cancel()
        harness.close()
    out.update({"tool_calls": _count_tool_calls(seen), "seconds": time.monotonic() - t0,
                "startup_seconds": startup})
    return out
