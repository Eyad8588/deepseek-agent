"""Plain baseline: a minimal OpenAI-style tool-calling loop against Ollama.

Same model, same persona, same sandboxed tools as the Harness agent. It has no
compaction, no retries and no harness services, just the loop. Stdlib only.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from deepseek_agent.config import BASE_URL, MAX_STEPS, PERSONA, TASK_TIMEOUT_S
from deepseek_agent.sandbox import TOOL_SPECS, Sandbox, dispatch


def _chat(payload: dict, timeout_s: float) -> dict:
    req = urllib.request.Request(BASE_URL + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read())


def run_baseline(prompt: str, workspace: Path, model: str, max_steps: int = MAX_STEPS,
                 timeout_s: float = TASK_TIMEOUT_S) -> dict:
    sb = Sandbox(workspace)
    messages: list[dict] = [{"role": "system", "content": PERSONA}, {"role": "user", "content": prompt}]
    tool_calls = 0
    t0 = time.monotonic()
    final, finish = "", "max_steps"
    for _ in range(max_steps):
        if time.monotonic() - t0 > timeout_s:
            finish = "timeout"
            break
        remaining = timeout_s - (time.monotonic() - t0)
        try:
            msg = _chat({"model": model, "messages": messages, "tools": TOOL_SPECS, "temperature": 0.2},
                        max(remaining, 1))["choices"][0]["message"]
        except TimeoutError:
            finish = "timeout"
            break
        calls = msg.get("tool_calls") or []
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        if not calls:
            final, finish = msg.get("content") or "", "completed"
            break
        for c in calls:
            tool_calls += 1
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out = dispatch(sb, c["function"]["name"], args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out})
    return {"final": final, "finish": finish, "tool_calls": tool_calls, "seconds": time.monotonic() - t0}
