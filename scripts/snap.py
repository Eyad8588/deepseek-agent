"""Render README screenshots to PNG with headless Chrome (no extra Python deps).

  python scripts/snap.py term <text-file> <out.png> "<title>" "<command line>"
  python scripts/snap.py eval <reports/eval.json> <out.png>
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "ui-monospace, 'SF Mono', Menlo, monospace"
CSS = f"""
body {{ margin:0; background:#0b0f14; font-family:-apple-system, 'Segoe UI', sans-serif; }}
.win {{ margin:24px; border-radius:12px; background:#11161d; box-shadow:0 10px 40px #0008; overflow:hidden;
        border:1px solid #232b36; }}
.bar {{ height:36px; background:#1a212b; display:flex; align-items:center; padding:0 14px; gap:8px; }}
.dot {{ width:12px; height:12px; border-radius:50%; }}
.title {{ color:#8b98a9; font-size:13px; margin-left:12px; }}
pre {{ margin:0; padding:18px 22px 22px; font:13.5px/1.55 {FONT}; color:#d6dde6; white-space:pre-wrap; }}
.cmd {{ color:#7ee787; }} .call {{ color:#79c0ff; }} .res {{ color:#8b98a9; }} .ok {{ color:#3fb950; font-weight:700; }}
.bad {{ color:#ff7b72; font-weight:700; }} .key {{ color:#d2a8ff; }}
"""


def shoot(page: str, out: Path, width: int, height: int) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={width},{height}", f"--screenshot={out.resolve()}", f"file://{f.name}"],
                   check=True, capture_output=True, timeout=120)


def colorize(line: str) -> str:
    s = html.escape(line)
    s = re.sub(r"^(BLOCKED)", r'<span class="bad">\1</span>', s)
    s = re.sub(r"^(ALLOWED)", r'<span class="ok">\1</span>', s)
    s = re.sub(r"^(→ \S+)", r'<span class="call">\1</span>', s)
    s = re.sub(r"^(\s+(←|└─).*)$", r'<span class="res">\1</span>', s)
    s = re.sub(r"\b(PASS)\b", r'<span class="ok">\1</span>', s)
    s = re.sub(r"\b(FAIL)\b", r'<span class="bad">\1</span>', s)
    s = re.sub(r"^(Task|Agent|Tools|Check)(\s)", r'<span class="key">\1</span>\2', s)
    return s


def term(src: Path, out: Path, title: str, cmd: str) -> None:
    lines = src.read_text().rstrip().splitlines()
    body = f'<span class="cmd">$ {html.escape(cmd)}</span>\n' + "\n".join(colorize(l) for l in lines)
    page = (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='win'><div class='bar'>"
            "<div class='dot' style='background:#ff5f57'></div><div class='dot' style='background:#febc2e'></div>"
            f"<div class='dot' style='background:#28c840'></div><span class='title'>{html.escape(title)}</span></div>"
            f"<pre>{body}</pre></div></body></html>")
    wrapped = sum(max(1, -(-len(l) // 125)) for l in lines) + 1
    shoot(page, out, 1180, 36 + 48 + 40 + int(wrapped * 21) + 20)


def eval_chart(src: Path, out: Path) -> None:
    d = json.loads(src.read_text())
    res = d["results"]
    tasks = list(dict.fromkeys(r["task"] for r in res))
    t = {(r["agent"], r["task"]): r for r in res}
    s = d["summary"]
    vmax = max(r["seconds"] for r in res)
    W, rowh, left = 760, 30, 150
    bars = []
    for i, task in enumerate(tasks):
        y = 20 + i * rowh
        bars.append(f"<text x='{left-10}' y='{y+15}' text-anchor='end' class='lbl'>{task}</text>")
        for j, (agent, color) in enumerate((("harness", "#4f7cff"), ("baseline", "#f0a030"))):
            r = t[(agent, task)]
            w = (W - left - 70) * r["seconds"] / vmax
            mark = "✓" if r["passed"] else "✗"
            bars.append(f"<rect x='{left}' y='{y+j*12}' width='{w:.1f}' height='10' rx='2' fill='{color}'/>"
                        f"<text x='{left+w+6:.1f}' y='{y+j*12+9}' class='val'>{r['seconds']:.0f}s {mark}</text>")
    H = 20 + len(tasks) * rowh + 10
    svg = f"<svg width='{W}' height='{H}' xmlns='http://www.w3.org/2000/svg'>{''.join(bars)}</svg>"
    def row(a, name):
        x = s[a]
        return (f"<tr><td>{name}</td><td class='big'>{x['passed']}/{x['n']}</td><td>{x['median_s']:.1f}s</td>"
                f"<td>{x['total_s']:.0f}s</td><td>{x['tool_calls']}</td></tr>")
    page = f"""<html><head><meta charset='utf-8'><style>
    body {{ margin:0; background:#fff; font-family:-apple-system,'Segoe UI',sans-serif; color:#1f2328; }}
    .card {{ margin:24px; padding:22px 26px; border:1px solid #d0d7de; border-radius:12px; }}
    h1 {{ font-size:20px; margin:0 0 4px; }} .sub {{ color:#59636e; font-size:13px; margin-bottom:16px; }}
    table {{ border-collapse:collapse; font-size:14px; margin-bottom:18px; }}
    td,th {{ padding:7px 16px; border-bottom:1px solid #e5e8eb; text-align:left; }} th {{ color:#59636e; font-weight:600; }}
    .big {{ font-weight:700; color:#1a7f37; }} .lbl {{ font:12.5px {FONT}; fill:#1f2328; }} .val {{ font:11px {FONT}; fill:#59636e; }}
    .legend span {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-1px; margin:0 6px 0 14px; }}
    </style></head><body><div class='card'>
    <h1>DeepSeek Harness agent vs plain tool-calling loop</h1>
    <div class='sub'>Model {d['model']} via Ollama (local) · 10 coding/file tasks · same sandboxed tools · 7-min cap per task</div>
    <table><tr><th>Agent</th><th>Passed</th><th>Median / task</th><th>Total</th><th>Tool calls</th></tr>
    {row('harness','DeepSeek Harness agent')}{row('baseline','Plain loop (baseline)')}</table>
    <div class='sub legend'>Time per task (✓ = checker passed)<span style='background:#4f7cff'></span>Harness
    <span style='background:#f0a030'></span>Baseline</div>{svg}</div></body></html>"""
    shoot(page, out, 860, 300 + H)


if __name__ == "__main__":
    kind, *rest = sys.argv[1:]
    if kind == "term":
        term(Path(rest[0]), Path(rest[1]), rest[2], rest[3])
    else:
        eval_chart(Path(rest[0]), Path(rest[1]))
