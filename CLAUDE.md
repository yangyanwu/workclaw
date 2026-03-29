# WorkClaw — CLAUDE.md

AI-powered developer tool that integrates Jira, GitHub, and Bitbucket for automated code analysis and PR creation.

## Build & Dev Commands

```sh
make install          # pip install -e ".[dev]"
make dev              # uvicorn GUI dev server (0.0.0.0:8000, --reload)
make cli              # interactive CLI chat (workclaw chat)
make test             # pytest -v
make lint             # ruff check + format --check
make format           # ruff check --fix + ruff format
make clean            # remove build artifacts, __pycache__, *.pyc
```

Run a single test: `pytest tests/path/to/test.py::test_name -v`

## Entry Points

- **CLI**: `workclaw.main:cli_entry` (registered as `workclaw` console script)
- **GUI**: `workclaw.gui.server:app` (FastAPI + WebSocket at `/ws/chat`)

## Architecture

ReAct agent loop (`core/agent.py`): user message -> context assembly -> LLM call -> parse response -> if tool_call: execute tool, feed result back, repeat; if text: return response.

**Module layout** (`src/workclaw/`):

| Module | Purpose |
|---|---|
| `core/` | Agent loop, context assembly, memory |
| `config/` | Pydantic Settings, YAML loader, defaults |
| `llm/` | LLM provider abstraction (LiteLLM-backed), system prompts |
| `tools/` | `Tool` ABC + `ToolRegistry`; concrete tools: shell, file_ops, git_ops |
| `integrations/` | `Integration` ABC; clients for GitHub, Bitbucket, Jira |
| `analysis/` | Code analysis pipeline |
| `cli/` | Typer CLI app |
| `gui/` | FastAPI server with WebSocket chat + static UI |
| `storage/` | File-based persistence (conversations, memory, reports) |

**Key abstractions**:
- `Tool` (ABC, `tools/base.py`) — `execute(**kwargs) -> ToolResult`
- `Integration` (ABC, `integrations/base.py`) — GitHub/Bitbucket/Jira clients
- `WorkClawAgent` — yields `AgentEvent` async generator (types: THINKING, TOOL_CALL, TOOL_RESULT, RESPONSE, ERROR, STATUS)

## Tooling Config

- **Ruff**: target py311, line-length 100, rules: E, F, I, N, W, UP
- **pytest**: asyncio_mode=auto, testpaths=["tests"], marker `integration` for external services
- **mypy**: python_version 3.11, strict=true
- **Python**: >=3.11, Hatchling build backend

## Config Precedence

env vars (`WORKCLAW_` prefix) > `.env` file > `~/.workclaw/config.yaml` > defaults

Key settings: `llm_provider`, `llm_model`, API keys per provider, integration tokens, `data_dir`, `agent_max_iterations`.
