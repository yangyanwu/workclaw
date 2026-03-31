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
| `analysis/` | Code analysis pipeline, `AnalysisPipeline`, `AnalysisScheduler` |
| `projects/` | Multi-repo project config — `ProjectConfig`, `RepoSource`, `ProjectManager`, auth-aware clone |
| `cli/` | Typer CLI app (chat, project, analyze, schedule sub-commands) |
| `gui/` | FastAPI server with WebSocket chat + static UI |
| `storage/` | File-based persistence (conversations, memory, reports, projects) |

**Key abstractions**:
- `Tool` (ABC, `tools/base.py`) — `execute(**kwargs) -> ToolResult`
- `Integration` (ABC, `integrations/base.py`) — GitHub/Bitbucket/Jira clients
- `WorkClawAgent` — yields `AgentEvent` async generator (types: THINKING, TOOL_CALL, TOOL_RESULT, RESPONSE, ERROR, STATUS)
- `ProjectManager` — CRUD for multi-repo project configs via `FileStore`
- `AnalysisPipeline` — clone all repos, analyze each via `CodeAnalyzer`, generate consolidated markdown
- `AnalysisScheduler` — APScheduler-based periodic re-analysis

## Tooling Config

- **Ruff**: target py311, line-length 100, rules: E, F, I, N, W, UP
- **pytest**: asyncio_mode=auto, testpaths=["tests"], marker `integration` for external services
- **mypy**: python_version 3.11, strict=true
- **Python**: >=3.11, Hatchling build backend

## Config Precedence

env vars (`WORKCLAW_` prefix) > `.env` file > `~/.workclaw/config.yaml` > defaults

Key settings: `llm_provider`, `llm_model`, API keys per provider, integration tokens, `data_dir`, `workspace_dir`, `agent_max_iterations`.

## Project Code Analysis

Multi-repo projects (`~/.workclaw/data/projects/<name>.yaml`) define repos with auth (SSH key/agent, HTTPS+creds, public HTTPS) and optional cron schedule.

**CLI commands**:
- `workclaw project create/list/show/add-repo/remove-repo/delete/validate` — manage projects
- `workclaw analyze <project> [--force] [--max-files N] [-o path]` — analyze all repos, generate consolidated MD
- `workclaw schedule start/list/set/remove/run` — APScheduler-based periodic re-analysis

**Storage**: `~/.workclaw/data/project_analysis/<name>_analysis.md` (consolidated) + per-repo JSON.

**Agent integration**: `agent.set_project_context(name)` loads analysis MD into system prompt; `clear_project_context()` removes it.
