"""Run the fixed task set through the Harness agent and the plain baseline.

Usage: uv run python -m deepseek_agent.eval [--model M] [--only harness|baseline] [--tasks id,id]
Writes reports/eval.json and reports/eval.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import time
import traceback
from datetime import datetime
from pathlib import Path

from deepseek_agent.baseline import run_baseline
from deepseek_agent.config import MODEL
from deepseek_agent.tasks import TASKS, seed

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"


def run_one(agent: str, task, model: str, stamp: str) -> dict:
    ws = RUNS / stamp / agent / task.id / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    seed(task, ws)
    rec = {"agent": agent, "task": task.id}
    try:
        if agent == "harness":
            from deepseek_agent.harness_agent import run_harness
            home = RUNS / stamp / "dsh-home"
            home.mkdir(parents=True, exist_ok=True)
            out = run_harness(task.prompt, ws, model, home, ws.parent, f"{task.id}-{stamp}")
        else:
            out = run_baseline(task.prompt, ws, model)
        rec.update(out)
    except Exception as e:  # noqa: BLE001 — record and continue
        rec.update({"finish": "exception", "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-2000:], "seconds": None, "tool_calls": 0})
    try:
        rec["passed"] = bool(task.check(ws))
    except Exception as e:  # noqa: BLE001
        rec["passed"], rec["check_error"] = False, str(e)
    print(f"[{agent:8}] {task.id:18} passed={rec['passed']!s:5} finish={rec.get('finish')} "
          f"t={rec.get('seconds') or 0:.1f}s tools={rec.get('tool_calls')}", flush=True)
    return rec


def summarize(results: list[dict], agent: str) -> dict:
    rs = [r for r in results if r["agent"] == agent]
    if not rs:
        return {}
    times = [r["seconds"] for r in rs if r.get("seconds")]
    return {"n": len(rs), "passed": sum(r["passed"] for r in rs),
            "success_rate": sum(r["passed"] for r in rs) / len(rs),
            "median_s": statistics.median(times) if times else None,
            "total_s": sum(times), "tool_calls": sum(r.get("tool_calls") or 0 for r in rs)}


def _slug(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def report_name(model: str) -> str:
    return "eval" if model == MODEL else f"eval-{_slug(model)}"


def save_raw(results: list[dict], model: str, stamp: str) -> list[dict]:
    """Persist this run per agent, then return the latest results of every agent for this model."""
    raw = REPORTS / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for a in {r["agent"] for r in results}:
        (raw / f"{_slug(model)}__{a}.json").write_text(json.dumps({"model": model, "stamp": stamp,
                                                   "results": [r for r in results if r["agent"] == a]},
                                                  indent=2, default=str))
    merged = []
    for f in sorted(raw.glob(f"{_slug(model)}__*.json")):
        d = json.loads(f.read_text())
        if d["model"] == model:
            merged += d["results"]
    return merged


def write_report(results: list[dict], model: str, stamp: str) -> None:
    REPORTS.mkdir(exist_ok=True)
    agents = [a for a in ("harness", "baseline") if any(r["agent"] == a for r in results)]
    sums = {a: summarize(results, a) for a in agents}
    (REPORTS / f"{report_name(model)}.json").write_text(json.dumps({"model": model, "stamp": stamp, "summary": sums,
                                                   "results": results}, indent=2, default=str))
    L = [f"# Eval: DeepSeek Harness agent vs plain tool-calling loop", "",
         f"- Model: `{model}` via Ollama (local) · run `{stamp}` · {len({r["task"] for r in results})} tasks · same sandboxed tools for both",
         f"- Generated {datetime.now():%Y-%m-%d %H:%M}", "", "## Summary", "",
         "| Agent | Passed | Success rate | Median time / task | Total time | Tool calls |",
         "|---|---|---|---|---|---|"]
    for a in agents:
        s = sums[a]
        med = f"{s['median_s']:.1f}s" if s["median_s"] is not None else "–"
        L.append(f"| {a} | {s['passed']}/{s['n']} | {s['success_rate']:.0%} | {med} | {s['total_s']:.0f}s | {s['tool_calls']} |")
    L += ["", "## Per task", "", "| Task | " + " | ".join(agents) + " |", "|---|" + "---|" * len(agents)]
    for t in TASKS:
        cells = []
        for a in agents:
            r = next((r for r in results if r["agent"] == a and r["task"] == t.id), None)
            if not r:
                cells.append("–")
                continue
            mark = "✅" if r["passed"] else "❌"
            secs = f"{r['seconds']:.0f}s" if r.get("seconds") else "–"
            note = "" if r["passed"] else f" ({r.get('finish')})"
            cells.append(f"{mark} {secs}{note}")
        L.append(f"| {t.id} | " + " | ".join(cells) + " |")
    errs = [r for r in results if r.get("error")]
    if errs:
        L += ["", "## Errors", ""] + [f"- `{r['agent']}/{r['task']}`: {r['error'][:300]}" for r in errs]
    (REPORTS / f"{report_name(model)}.md").write_text("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", choices=["harness", "baseline"])
    ap.add_argument("--tasks", help="comma-separated task ids")
    args = ap.parse_args()
    tasks = [t for t in TASKS if not args.tasks or t.id in args.tasks.split(",")]
    agents = [args.only] if args.only else ["harness", "baseline"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    results = []
    for t in tasks:          # interleave agents per task so drift in machine load affects both equally
        for a in agents:
            results.append(run_one(a, t, args.model, stamp))
            write_report(save_raw(results, args.model, stamp), args.model, stamp)
    print((REPORTS / f"{report_name(args.model)}.md").read_text())


if __name__ == "__main__":
    main()
