# DeepSeek Agent: a sandboxed local coding agent on DeepSeek Harness

This is a small coding agent built on **[DeepSeek Harness (`dsh`)](https://github.com/deepseek-ai/deepseek-harness)**, DeepSeek's open-source, MIT-licensed, "everything is a plugin" agent runtime. It runs **fully locally** against Ollama, with no cloud API and no API key. It is evaluated on 10 fixed coding and file tasks against a plain tool-calling loop that uses the same model and the same tools.

See [RESEARCH.md](RESEARCH.md) for what Harness and its new agent (`dsh-superagent-prototype`) are, with links, and why the project is built this way.

## How it works

```
eval.py ─┬─► harness_agent.py ──(Python SDK, JSON-RPC/stdio)──► dsh --profile sdk-minimal
         │                                                       │  + per-task Cordis patch:
         │                                                       │    - persistent-bash / terminal rows: disabled
         │                                                       │    - session-log upload, plugin inventory: disabled
         │                                                       │    - MCP client row ──► mcp_server.py (sandboxed tools)
         │                                                       └─ DeepSeek adapter (base_url) ──► Ollama /v1
         └─► baseline.py ── plain OpenAI-style tool loop ─────────────────────────────────► Ollama /v1
                            (same model, same persona, same sandboxed tools)
```

- **Harness agent** ([harness_agent.py](src/deepseek_agent/harness_agent.py)):
  - It uses the Harness Python SDK (`deepseek-harness-sdk`, which bundles the `dsh` runtime, so no Node is needed) with the standalone `sdk-minimal` profile.
  - A per-task patch ([template](src/deepseek_agent/harness_agent.py)) **switches off the default full-access bash** and the DeepSeek session-log upload.
  - It mounts our tools through Harness's own `@deepseek-ai/dsh-mcp-client`, where they show up to the model as `mcp__sandbox__*`.
  - The built-in DeepSeek adapter is pointed at Ollama (`base_url=http://127.0.0.1:11434/v1`).
  - A watchdog closes the runtime when the per-task time limit is reached.
- **Sandboxed tools** ([sandbox.py](src/deepseek_agent/sandbox.py), served over stdio MCP by [mcp_server.py](src/deepseek_agent/mcp_server.py)):
  - `read_file`, `write_file`, `list_dir`: every path is resolved, symlinks included, and must stay inside the task workspace.
  - `run_command`: runs **one** program from an allow-list (`ls cat head tail wc grep sort uniq diff find echo pwd mkdir touch cp mv python python3 pytest`). There is **no shell**, so pipes, redirects, `;`, `&&` and `$(…)` are rejected. It has a 30 s timeout and a scrubbed environment.
  - On macOS every command runs under `sandbox-exec`, which **denies network** and **denies writes outside the workspace**.
  - [tests/test_sandbox.py](tests/test_sandbox.py) checks 14 escape attempts: `../`, absolute paths, symlinks, pipes, chains, subshells, `curl`, `rm`, Python writing outside the workspace, and Python opening a socket.
- **Baseline** ([baseline.py](src/deepseek_agent/baseline.py)): about 40 lines of stdlib chat-completions → tool calls → dispatch. It uses the same persona, the same tools, a 12-step cap, and the same wall-clock cap.
- **Tasks and eval** ([tasks.py](src/deepseek_agent/tasks.py), [eval.py](src/deepseek_agent/eval.py)):
  - The 10 tasks include writing a file, fixing a bug, FizzBuzz, counting log levels (with a trap line that naive `grep ERROR` miscounts), editing JSON, implementing a function until given tests pass, summing a CSV, creating a package, fixing `slugify` against tests, and merging, sorting and de-duplicating files.
  - Checkers run **outside** the sandbox on what the agent left behind.
  - Every task gets a fresh workspace and a fresh session, borrowing the superagent's "one work item, one session, one directory" idea.
  - The two agents alternate task by task, so machine-load drift affects both equally.

## Setup

```bash
ollama pull qwen3.5:9b                                    # main eval model (already installed here)
ollama create qwen3.5-9b-12k -f ollama/Modelfile.qwen3.5-9b-12k        # same weights, 12k context
# optional, DeepSeek model that was tried first:
ollama pull deepseek-r1:8b && ollama create deepseek-r1-8b-12k -f ollama/Modelfile.deepseek-r1-8b-12k
uv sync
uv run python tests/test_sandbox.py
```

The 12k aliases exist because Ollama's default context is 4,096 tokens, which is too small for an agent loop. They download nothing and do not change Ollama's global settings.

## Run

```bash
uv run python -m deepseek_agent.eval                                    # both agents, 10 tasks → reports/eval.md
uv run python -m deepseek_agent.eval --only harness --tasks hello_file  # subset
TASK_TIMEOUT_S=300 uv run python -m deepseek_agent.eval --model deepseek-r1-8b-12k   # → reports/eval-deepseek-r1-8b-12k.md
```

Each run keeps its workspaces and the Harness home, including the full session JSONL logs, under `runs/<stamp>/` (gitignored).

## Results (2026-11-18, Apple M5, 16 GB, other heavy jobs running at the same time)

**Main eval: `qwen3.5:9b` (12k context), 10 tasks, 7-minute cap per task.** Full table: [reports/eval.md](reports/eval.md).

| Agent | Passed | Median time / task | Total | Tool calls |
|---|---|---|---|---|
| **DeepSeek Harness agent** | **10/10** | 79.7 s | 801 s | 44 |
| Plain loop (baseline) | **10/10** | 42.5 s | 627 s | 43 |

**DeepSeek model: `deepseek-r1:8b` (R1-0528 Qwen3-8B distill, Q4_K_M), 5-minute cap per task.** Full table: [reports/eval-deepseek-r1-8b-12k.md](reports/eval-deepseek-r1-8b-12k.md).

| Agent | Passed (3 tasks: hello_file, fix_add_bug, count_errors) | Tool calls |
|---|---|---|
| DeepSeek Harness agent | 0/3, all hit the 300 s cap | 0 |
| Plain loop (baseline) | 0/3, all hit the 300 s cap | 0 |

Only 3 tasks were run because every attempt uses the whole time cap. A full 10-task run would take about 1.7 hours to reach the same result.

### What this shows

1. **Harness works fully offline with a local model.**
   - The stock DeepSeek adapter talks to Ollama's OpenAI-compatible endpoint with no code changes.
   - MCP tools mounted by a Cordis patch work like native tools.
   - Its full-access shell can be removed with a two-line patch.
2. **The task set does not separate the two loops on success rate.** Both score 10/10. A 9B model plus good tools is enough for tasks this small. A harder task set is needed to see whether Harness's extras (compaction, retries, subagents) help.
3. **Harness costs time.** Its median is about 1.9× the baseline's.
   - About 9 s per task is outside the model turn: starting the `dsh` runtime, MCP handshake and probe, and shutdown. We start one runtime per task on purpose to isolate tasks; reusing one runtime would remove most of this.
   - The rest is inside the turn (median 74 s vs about 42 s). Likely causes:
     - The DeepSeek adapter sends `reasoning_effort: high` by default.
     - The model sees 5 extra built-in tools (`read_image`, `working_directory`, MCP resource tools).
     - Harness replays reasoning blocks in the history.
   - These are hypotheses from the session logs, not separately measured.
4. **The small DeepSeek model is the bottleneck, not the harness.**
   - R1-8B over-thinks. In a direct probe it spent 204 s and about 3,000 reasoning tokens deciding *how* to write `hello.txt`, and never called a tool.
   - With thinking turned off (`reasoning_effort: none`) it answers with a bash snippet in plain text instead of a tool call.
   - The larger DeepSeek models in Ollama (V3.x/V4, R1 14B+) don't fit in 16 GB alongside the other workloads. So the main eval uses the brief's fallback, `qwen3.5:9b`, which is also a Qwen3-family model.

## Caveats

- Harness is a **developer preview** (v0.2.2rc2 SDK, pinned in `uv.lock`), and its README warns of breaking changes. `mcp` 2.x renamed `FastMCP` to `MCPServer`, which this code already handles.
- `sandbox-exec` is deprecated by Apple but works. On Linux, only the path and allow-list checks apply. Python is on the allow-list, so on Linux model-written code could still write outside the workspace or reach the network. Use a container there.
- Each task was run once at temperature 0.2 (the Harness side uses the adapter's own sampling). With 10 tasks, a difference of one or two passes is noise.
- Memory was tight during the runs (about 23 GB of swap, with other model jobs running in parallel), so absolute times are pessimistic. The comparison is fair because the agents alternated task by task.
