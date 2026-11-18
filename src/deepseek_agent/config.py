import os

OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
BASE_URL = OLLAMA + "/v1"
# Main eval model. deepseek-r1:8b was tried first and could not drive tools (see README).
MODEL = os.environ.get("AGENT_MODEL", "qwen3.5-9b-12k")
MAX_STEPS = 12
TASK_TIMEOUT_S = float(os.environ.get("TASK_TIMEOUT_S", 420))  # wall-clock cap per task, same for both agents
PERSONA = (
    "You are a careful software engineer working in a sandboxed workspace (the current directory). "
    "Use the provided tools to inspect and change files and to run programs. "
    "Paths are relative to the workspace. Verify your work (for example by running tests) "
    "before you finish, then reply with a one-line summary."
)
