# DeepSeek Agent

**A sandboxed coding agent built on DeepSeek Harness that runs fully offline against a local model, measured against a plain tool-calling loop.**

## What is DeepSeek Harness?

**[DeepSeek Harness (`dsh`)](https://github.com/deepseek-ai/deepseek-harness)** is DeepSeek's open-source agent runtime. It is MIT-licensed and has been in developer preview since August 2026.

- It is not a model. It is the loop, tools, sandbox, sessions and UI around a model.
- It is built on the [Cordis](https://github.com/cordiverse/cordis) plugin kernel, where *everything is a plugin*. An app is a YAML tree of plugin rows that patches can insert, replace or disable.
- It ships a Web UI, a desktop app, and Python and TypeScript SDKs.

DeepSeek's newer agent, **[dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype)** (October 2026), is a proactive coding agent packaged as a Harness bundle. It takes requests from GitHub or Feishu and answers with PRs. It needs GitHub and Feishu infrastructure, so it is not rebuilt here. Its "one work item, one session, one directory" idea is reused in the eval.

Full research notes and sources: **[RESEARCH.md](RESEARCH.md)**.

## What this project adds

- **Local-only DeepSeek Harness.**
  - Harness's stock DeepSeek adapter is pointed at **Ollama's** OpenAI-compatible endpoint, so there is no cloud API and no API key.
  - The DeepSeek session-log upload is switched off.
- **A safer tool surface.**
  - Harness's default full-access `bash` is **removed** with a Cordis patch.
  - Our own **sandboxed tools** are mounted through Harness's MCP client: path-jailed file I/O and an allow-listed shell with no shell syntax. On macOS it also runs under an OS-level jail that blocks network access and writes outside the workspace.
- **An honest benchmark.**
  - 10 fixed coding and file tasks with automatic checkers.
  - The Harness agent runs against a ~40-line plain tool-calling loop with the **same model, prompt, tools and time limit**.
  - Success rate and time are reported.

## Architecture

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
  - It uses `deepseek-harness-sdk`, which bundles the `dsh` runtime, so no Node is needed, with the standalone `sdk-minimal` profile.
  - Each task gets a fresh runtime, workspace and session, plus a watchdog that enforces the time limit.
  - Our tools appear to the model as `mcp__sandbox__*`.
- **Baseline** ([baseline.py](src/deepseek_agent/baseline.py)): stdlib chat-completions → tool calls → dispatch, with a 12-step cap.
- **Eval** ([eval.py](src/deepseek_agent/eval.py), [tasks.py](src/deepseek_agent/tasks.py)):
  - Agents alternate task by task, so machine-load drift affects both.
  - Checkers run **outside** the sandbox on the files each agent left behind.
  - Tasks: write a file, fix a bug, FizzBuzz, count log levels (with a trap line), edit JSON, implement a function until given tests pass, sum a CSV, create a package, fix `slugify` against tests, and merge, sort and de-duplicate files.

## Tools and sandboxing

| Tool | What it does | Guard |
|---|---|---|
| `read_file` / `write_file` / `list_dir` | File I/O in the task workspace | Every path is resolved (symlinks too) and must stay inside the workspace |
| `run_command` | Runs **one** allow-listed program: `ls cat head tail wc grep sort uniq diff find echo pwd mkdir touch cp mv python python3 pytest` | No shell: pipes, redirects, `;`, `&&`, `$(…)` and backticks are rejected. 30 s timeout, scrubbed env. On macOS it runs under `sandbox-exec`, with **no network** and **no writes outside the workspace** |

[tests/test_sandbox.py](tests/test_sandbox.py) checks 14 escape attempts: `../`, absolute paths, symlinks, pipes, chains, subshells, `curl`, `rm`, Python writing outside the workspace, and Python opening a socket.

## Quick start

Requirements: macOS 14+ on Apple Silicon (or Linux; see the caveats), [Ollama](https://ollama.com), and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Eyad8588/deepseek-agent && cd deepseek-agent
uv sync
uv run python tests/test_sandbox.py
```

```bash
ollama pull qwen3.5:9b
ollama create qwen3.5-9b-12k -f ollama/Modelfile.qwen3.5-9b-12k
```

The `*-12k` aliases reuse the same weights with a 12k context. Ollama's default of 4,096 tokens is too small for an agent loop.

Optional, the DeepSeek model:

```bash
ollama pull deepseek-r1:8b && ollama create deepseek-r1-8b-12k -f ollama/Modelfile.deepseek-r1-8b-12k
```

Run the eval:

```bash
uv run python -m deepseek_agent.eval                                    # both agents, 10 tasks → reports/eval.md
uv run python -m deepseek_agent.eval --only harness --tasks hello_file  # subset
TASK_TIMEOUT_S=300 uv run python -m deepseek_agent.eval --model deepseek-r1-8b-12k
```

Each run keeps its workspaces and Harness session logs (JSONL) under `runs/<stamp>/`, which is gitignored.

## Results

Run on 2026-11-18 on an Apple M5 with 16 GB, with other heavy jobs running at the same time.

**`qwen3.5:9b` (12k context), 10 tasks, 7-minute cap per task.** Full table: [reports/eval.md](reports/eval.md).

| Agent | Passed | Median time / task | Total | Tool calls |
|---|---|---|---|---|
| **DeepSeek Harness agent** | **10/10** | 79.7 s | 801 s | 44 |
| Plain loop (baseline) | **10/10** | 42.5 s | 627 s | 43 |

**`deepseek-r1:8b` (R1-0528 Qwen3-8B distill, Q4_K_M), 3 tasks, 5-minute cap per task.** Full table: [reports/eval-deepseek-r1-8b-12k.md](reports/eval-deepseek-r1-8b-12k.md).

| Agent | Passed | Tool calls |
|---|---|---|
| DeepSeek Harness agent | 0/3 (all timed out) | 0 |
| Plain loop (baseline) | 0/3 (all timed out) | 0 |

**What this shows:**

1. **Harness runs fully offline.**
   - The stock adapter works with Ollama with no code changes.
   - MCP tools mounted by a patch behave like native tools.
   - The full-access shell can be removed with a two-line patch.
2. **These tasks don't separate the two loops on success.** Both score 10/10. A harder task set is needed to see whether Harness's extras (compaction, retries, subagents) help.
3. **Harness costs time,** about 1.9× the baseline's median.
   - About 9 s per task is runtime startup, MCP handshake and shutdown. That cost comes from starting one runtime per task, which this eval does on purpose to keep tasks isolated.
   - The rest is inside the model turn (median 74 s vs about 42 s). Likely causes are the adapter's default `reasoning_effort: high`, 5 extra built-in tools in the prompt, and replayed reasoning blocks. These are inferred from the session logs and were not measured separately.
4. **The small DeepSeek model is the bottleneck, not the harness.**
   - R1-8B over-thinks. In a direct probe it spent 204 s and about 3,000 reasoning tokens deciding *how* to write `hello.txt`, and never called a tool.
   - With thinking off, it replies with a bash snippet in plain text instead of a tool call.
   - Larger DeepSeek models don't fit in 16 GB, so the main eval uses `qwen3.5:9b`.

## Project structure

```
deepseek-agent/
├── RESEARCH.md                  # what DeepSeek Harness / superagent are, with sources
├── src/deepseek_agent/
│   ├── harness_agent.py         # agent on DeepSeek Harness (SDK + Cordis patch + watchdog)
│   ├── mcp_server.py            # stdio MCP server exposing the sandboxed tools
│   ├── sandbox.py               # path jail, allow-listed shell, sandbox-exec profile, tool specs
│   ├── baseline.py              # plain tool-calling loop (stdlib only)
│   ├── tasks.py                 # 10 tasks: seed files + checkers
│   ├── eval.py                  # runner → reports/*.md, *.json
│   └── config.py                # model, endpoint, persona, limits
├── tests/test_sandbox.py        # sandbox escape tests
├── ollama/                      # Modelfiles for the 12k-context aliases
├── reports/                     # eval results (markdown + JSON, raw per agent)
└── docs/screenshots/            # screenshots (TODO)
```

## Screenshots

<!-- TODO: add screenshots in docs/screenshots/ and link them here -->
- TODO: eval run in the terminal (`docs/screenshots/eval-run.png`)
- TODO: `reports/eval.md` rendered (`docs/screenshots/eval-report.png`)
- TODO: a Harness session log / Web UI view of an agent run (`docs/screenshots/harness-session.png`)

## Roadmap

- [ ] Harder task set (multi-file refactors, failing test suites, longer horizons) so success rates differ
- [ ] Reuse one Harness runtime across tasks, with a fresh session and workspace each, to remove startup overhead
- [ ] Controlled ablations: `reasoning_effort` low vs high, built-in tools on vs off
- [ ] Several runs per task with confidence intervals
- [ ] Linux sandbox backend (bubblewrap / container) to match the macOS `sandbox-exec` guarantees
- [ ] Try a larger DeepSeek model (V4-Flash via a remote OpenAI-compatible endpoint) when hardware or policy allows
- [ ] Package the sandbox tools as a native `dsh` plugin (TypeScript `defineTool`) as well as MCP

## Caveats

- Harness is a **developer preview**. The SDK is pinned at `0.2.2rc2` in `uv.lock`, and upstream warns of breaking changes.
- `sandbox-exec` is deprecated by Apple but works. On Linux only the path and allow-list checks apply, and Python on the allow-list can still write elsewhere or reach the network, so use a container there.
- Each task was run once. With 10 tasks, a difference of one or two passes is noise. Absolute times are pessimistic because memory was tight (heavy swapping). The comparison stays fair because the agents alternated task by task.

## License and credits

This repo uses DeepSeek Harness as a dependency (`deepseek-harness-sdk`, MIT). No Harness source is vendored. DeepSeek Harness and dsh-superagent-prototype are © DeepSeek-AI under the MIT License.
