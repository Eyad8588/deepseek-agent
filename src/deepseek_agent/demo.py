"""Run ONE task with the DeepSeek Harness agent and print a readable trace.

Usage: uv run python -m deepseek_agent.demo [task_id] [--model M]
The trace is read back from Harness's own session log (JSONL).
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from deepseek_agent.config import MODEL
from deepseek_agent.harness_agent import run_harness
from deepseek_agent.tasks import TASKS, seed

ROOT = Path(__file__).resolve().parents[2]


def _short(s: str, n: int = 160) -> str:
    s = s.strip().replace("\n", "⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", default="fix_add_bug")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()
    task = next(t for t in TASKS if t.id == args.task)
    base = ROOT / "runs" / f"demo-{time.strftime('%Y%m%d-%H%M%S')}"
    ws = base / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    seed(task, ws)

    print(f"Task   {task.id}: {task.prompt}")
    print(f"Agent  DeepSeek Harness (sdk-minimal, bash disabled) · model {args.model} via Ollama")
    print(f"Tools  mcp__sandbox__read_file / write_file / list_dir / run_command (sandboxed)\n")
    sid = f"demo-{task.id}"
    out = run_harness(task.prompt, ws, args.model, base / "dsh-home", base, sid)

    log = next((base / "dsh-home" / "sessions").rglob("session.v4.jsonl"))
    for line in log.read_text().splitlines():
        e = json.loads(line)
        d = e.get("data", {})
        if e.get("type") == "tool/call":
            print(f"→ {d['name']}  {_short(d.get('arguments') or '', 120)}")
        elif e.get("type") == "tool/result":
            parts = d.get("message", {}).get("content", [])
            text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
            print(f"  ← {_short(text)}")
    passed = task.check(ws)
    print(f"\nAgent  {_short(out.get('final') or '', 300)}")
    print(f"Check  {'PASS' if passed else 'FAIL'} · {out['seconds']:.0f}s wall ({out['startup_seconds'] or 0:.0f}s runtime startup)"
          f" · {out['tool_calls']} tool calls · finish={out['finish']}")


if __name__ == "__main__":
    main()
