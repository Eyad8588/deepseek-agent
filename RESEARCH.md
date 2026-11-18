# Research: "the DeepSeek harness" and its new agent

Researched 2026-11-18. Sources are listed per section. The facts come from the official GitHub repos (read through the GitHub API). Third-party articles were used only for dates and context.

## TL;DR

| Question | Answer |
|---|---|
| What is "the DeepSeek harness"? | **DeepSeek Harness (`dsh`)**: an open-source **agent runtime**, not a model. It is built on the Cordis plugin kernel, where *everything is a plugin*: models, tools, sandbox, filesystem, sessions, the loop, and the UI. |
| Repo / license | [github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness), **MIT**. Developer preview (v0.1, announced 2026-08-13). The README says to expect breaking changes. About 283k stars on 2026-11-18. |
| What is "the new agent"? | **dsh-superagent-prototype** ([github.com/deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype), **MIT**, created 2026-10-31). It is a *research prototype* of a proactive coding agent for one GitHub repo. It runs as a bundle on top of Harness, listens to GitHub (and optionally Feishu), opens a work item per request, works in its own session and directory, and replies with a PR. |
| Runs with local models? | **Yes.** There are three ways: (1) the built-in DeepSeek adapter honours `DEEPSEEK_BASE_URL`, so it can point at any compatible `/v1` endpoint; (2) a "Custom model API" provider using the `openai-completions` protocol with any base URL; (3) the `dsh-llm-pi-ai` adapter config in `cordis.patch.yml`. Ollama serves an OpenAI-compatible `/v1` API, so it can be the endpoint. |
| How to drive it from Python | Run `pip install deepseek-harness-sdk`. It ships a native runtime wheel (macOS 14+ arm64 is supported) and the `dsh` CLI, and needs no system Node.js. `DeepSeekHarness(...).run(prompt)` drives a `dsh --profile sdk-minimal` process over JSON-RPC on stdio. |

## DeepSeek Harness (`dsh`)

- **Architecture.** Harness is built on [Cordis](https://github.com/cordiverse/cordis), and its paper is [arXiv 2608.25512](https://arxiv.org/abs/2608.25512). An app is a *Cordis tree* of plugin rows defined in YAML. A *profile* is one such tree (`web`, `sdk`, `sdk-minimal`, …). User `cordis.patch.yml` files and `--patch` files can insert, replace, or disable rows. Every piece can be swapped: LLM adapters, tool rows, `sandbox-policy`, `terminal-bash`, `agent-loop`, compaction, and session persistence.
- **Ways to run it.** `npx @deepseek-ai/dsh web` (Web UI on :3080), a desktop app, and Python and TypeScript SDKs over JSON-RPC.
- **`sdk-minimal` profile.** It has a persistent `bash` tool, `read_image`, automatic compaction, and JSONL sessions. Its README notes two defaults that matter for this project:
  - It pins `sandbox-policy.mode: danger-full-access`, so the shell can touch any path. *"use a disposable checkout or container."*
  - `session-log-deepseek` uploads session-log events along with model requests by default. We **disable** it, so nothing extra goes to the endpoint.
- **Tools.** Plugins written in TypeScript (`defineTool`), or any **MCP server** added through a `@deepseek-ai/dsh-mcp-client` row (stdio or Streamable HTTP). MCP tools appear to the model as native tools.
- **Model providers.** DeepSeek (API key or account), a catalog of third-party providers (Anthropic, OpenAI, Kimi, GLM, …), and *Custom model API* with OpenAI Chat Completions, OpenAI Responses, Anthropic Messages, or Gemini protocols. The `compat` switches (`supportsDeveloperRole`, `maxTokensField`, `thinkingFormat: deepseek`) cover gateways that differ from OpenAI.
- **Contributions.** At launch DeepSeek said it could not take external PRs. Feedback goes through Discussions, and the ecosystem grows through plugins (GitHub topic `dsh-plugin`).

Sources: [repo README](https://github.com/deepseek-ai/deepseek-harness) ·
[providers guide](https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/user/guide/providers.md) ·
[Python SDK guide](https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/user/guide/python-sdk.md) ·
[Python SDK reference](https://github.com/deepseek-ai/deepseek-harness/blob/main/python/sdk/README.md) ·
[sdk-minimal bundle](https://github.com/deepseek-ai/deepseek-harness/blob/main/packages/bundle/sdk-minimal/README.md) ([tree](https://github.com/deepseek-ai/deepseek-harness/blob/main/packages/bundle/sdk-minimal/cordis.patch.yml)) ·
[MCP client](https://github.com/deepseek-ai/deepseek-harness/blob/main/packages/mcp/mcp-client/README.md) ·
[tool tutorial](https://github.com/deepseek-ai/deepseek-harness/blob/main/docs/user/develop/basic/tool.md) ·
[official site](https://deepseek.com/en/harness/) ·
[DeepSeek on X (v0.1 announcement)](https://x.com/deepseek_ai/status/2087887408440164663) ·
[The New Stack](https://thenewstack.io/deepseek-harness-open-source-plugins/) ·
[MarkTechPost](https://www.marktechpost.com/2026/08/17/deepseek-ai-releases-deepseek-harness-in-developer-preview/)

## dsh-superagent-prototype (the "new agent")

- It is a bundle for Harness: a *proactive* coding agent for **one GitHub repository**. People who are allowed can ask it for work on GitHub or Feishu. It opens a work item, runs it in its own agent session and directory, and answers in the original thread, for example with a PR. A web panel shows what needs a human.
- Its philosophy is *"take as little human attention as possible, and give as much value as possible"*. It acts only when asked or when a team-written rule allows it.
- Its documentation covers the philosophy, domain model, authorization, execution, prompts, panel, deployment, and architecture. Setup is done *by a coding agent* following `SETUP.md`.
- **It is labelled a research prototype, "not an official DeepSeek product".** It needs a GitHub App/webhooks, and optionally Feishu, so it does not fit a fully offline local eval.

Sources: [repo README](https://github.com/deepseek-ai/dsh-superagent-prototype) ·
[Startup Fortune](https://startupfortune.com/deepseek-open-sources-the-architecture-behind-its-super-agent/) ·
[Flowtivity](https://flowtivity.ai/blog/dsh-super-agent/)

## Conflicting or unclear details

- **Star counts** differ a lot between articles (33k to 188k). The GitHub API shows about 283k for the harness and about 23.7k for the superagent on 2026-11-18.
- **Dates:** one Flowtivity post dates Harness to 2026-10-31. The official X post and most coverage say **2026-08-13**. 2026-10-31 is the superagent's creation date, which is probably where the mix-up comes from.

## Decision for this project

The target is clear and it runs locally, so the project goes ahead (step 2):

- **The agent runs on DeepSeek Harness** through the Python SDK and the `sdk-minimal` profile, with a project patch that:
  - points the DeepSeek adapter at **Ollama** (`DEEPSEEK_BASE_URL=http://127.0.0.1:11434/v1`),
  - **disables** the full-access `persistent-bash` row and `session-log-deepseek`,
  - adds our own **sandboxed tools as a stdio MCP server**: file read/write/list inside a sandbox directory, and a shell with an allow-list and no `sh -c`.
- **The superagent itself is not reproduced.** It needs GitHub and Feishu infrastructure. Its idea, work items handled in isolated per-task sessions and directories, is reused: every eval task runs in a fresh sandbox directory with a fresh session.
- **Baseline:** a plain OpenAI-style tool-calling loop against the same Ollama model with the *same* MCP tools. This isolates what the harness adds: its loop, its prompts and compaction, and its tool plumbing.
