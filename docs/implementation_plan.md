# WorkClaw — Implementation Plan

Build a self-hosted, Python-based AI developer tool that fetches Jira stories, analyzes code from GitHub/Bitbucket, suggests improvements (including refactoring and bug fixes), modifies code, and submits pull requests — all via a conversational CLI and web GUI.

---

## Technical Foundation & Security

> [!IMPORTANT]
> **LiteLLM Security Advisory**: LiteLLM versions 1.82.7–1.82.8 were compromised in a supply chain attack (March 2026). We pinned to verified safe versions (`>=1.82.0,!=1.82.7,!=1.82.8`).

> [!WARNING]  
> **API Credentials**: WorkClaw needs API tokens. These are loaded securely via environment variables or a local `.env` and `~/.workclaw/config.yaml`.

---

## Tech Stack

| Component | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | User preference, rich ecosystem |
| **Backend/GUI Server** | FastAPI + Uvicorn | Async, WebSocket support, serves static GUI |
| **CLI** | Typer + Rich | Modern Python CLI with beautiful output |
| **LLM Interface** | LiteLLM (pinned safe version) | Unified API for OpenAI, Anthropic, Gemini, Ollama |
| **Git Operations** | GitPython | Programmatic git (clone, branch, commit, push) |
| **HTTP Client** | httpx (async) | Async API calls to Jira, GitHub, Bitbucket |
| **Config** | Pydantic Settings + YAML | Type-safe config with env var support |
| **Storage** | File-based (YAML/JSON/Markdown) | Simple, inspectable, no DB needed |
| **Packaging** | pyproject.toml | Modern Python packaging |
| **Testing** | pytest + pytest-asyncio | Async-friendly testing |

---

## Project Structure

```
WorkClaw/
├── pyproject.toml                 # Package config, dependencies, entry points
├── README.md                      # Project documentation
├── Makefile                       # Dev shortcuts (install, test, run, lint)
├── .env.example                   # Template for environment variables
│
├── src/
│   └── workclaw/
│       ├── __init__.py            # Package init, version
│       ├── main.py                # Entry point dispatcher (CLI or GUI)
│       │
│       ├── config/
│       │   ├── settings.py        # Pydantic settings model
│       │   └── defaults.yaml      # Default configuration values
│       │
│       ├── llm/
│       │   ├── provider.py        # LLM provider abstraction (wraps LiteLLM)
│       │   └── prompts.py         # System prompts and prompt templates
│       │
│       ├── integrations/
│       │   ├── base.py            # Abstract integration interface
│       │   ├── github/
│       │   │   ├── client.py      # GitHub REST API client
│       │   │   └── pr.py          # PR creation & management
│       │   ├── bitbucket/
│       │   │   ├── client.py      # Bitbucket REST API client
│       │   │   └── pr.py          # PR creation & management
│       │   └── jira/
│       │       └── client.py      # Jira REST API client
│       │
│       ├── core/
│       │   ├── agent.py           # ReAct agent loop (reason → act → observe)
│       │   ├── context.py         # Context assembly for LLM calls
│       │   └── memory.py          # Conversation & project memory
│       │
│       ├── analysis/
│       │   ├── analyzer.py        # Code analysis coordinator
│       │   ├── refactor.py        # Refactoring opportunity detection
│       │   └── bugs.py            # Bug pattern detection
│       │
│       ├── tools/
│       │   ├── base.py            # Abstract tool interface
│       │   ├── registry.py        # Tool registry & discovery
│       │   ├── file_ops.py        # File read/write/search tools
│       │   ├── git_ops.py         # Git clone/branch/commit/push tools
│       │   └── shell.py           # Shell command execution tool
│       │
│       ├── cli/
│       │   └── app.py             # Typer CLI application
│       │
│       ├── gui/
│       │   ├── server.py          # FastAPI app + WebSocket handler
│       │   └── static/
│       │       ├── index.html     # Single-page chat interface
│       │       ├── style.css      # Premium dark-themed styles
│       │       └── app.js         # Chat logic, WebSocket client
│       │
│       └── storage/
│           └── store.py           # File-based YAML/JSON/MD storage
│
├── data/                          # Runtime data (gitignored)
│   ├── conversations/             # Chat history (Markdown)
│   ├── memory/                    # Agent memory (YAML)
│   └── workspaces/                # Cloned repos for analysis
│
└── tests/
    ├── conftest.py                # Shared fixtures
    ├── test_config.py
    ├── test_storage.py
    └── test_memory.py
```

---

## Components Detail

### 1: Project Foundation
- Project metadata and dependencies initialized in `pyproject.toml`.
- Utility `Makefile` and `README.md` created.
- Command entry points established (`workclaw` and `workclaw-gui`).

### 2: Configuration System
- `WorkClawSettings` using Pydantic Settings supporting defaults mapped via `defaults.yaml` and `.yaml/.env` sources.
- Safely manages dynamic provider choices (`llm_provider`, `llm_model`).

### 3: LLM Provider Layer
- Unified wrapper wrapping `LiteLLM`, handling retry and exception states, mapping tools back to model-specific formats.
- Defines common system prompts for Jira extraction, analysis, bug hunting, and refactoring.

### 4: Integration Layer
- Connects through asynchronous `httpx` and `GitPython`.
- **GitHub**: Cloning, fetching trees, managing PRs.
- **Bitbucket**: Native Bitbucket server interactions using app passwords.
- **Jira**: Issue fetching and updating, handling Jira's Atlassian Document Format (ADF) automatically to expose plain text logic to the LLM.

### 5: Agent Core (ReAct Loop)
- Uses asynchronous generators to rapidly iterate `think -> execute -> observe` blocks, providing responsive intermediate feedback.
- Context is assembled dynamically via `ContextAssembler` to stay strictly within token budgets.
- Local `Memory` module persists conversations and learned facts.

### 6: Code Analysis Engine
- Evaluates repository trees and large file contents via chunking. Detects code smells, potential race conditions, boundary bugs, and applies refactoring suggestions mapped directly to the active Jira issue.

### 7: Tool System
- Exposes concrete JSON schemas mapping back to Python implementations.
- Features `run_command` via an asynchronous shell sandbox that automatically rejects dangerous operations using a local blocklist.

### 8: Presentation (CLI & GUI)
- **CLI**: Real-time terminal sessions using `Typer` and `Rich`.
- **GUI**: Modern dark theme local API. `FastAPI` manages WebSocket-driven agent interactions so chat state corresponds fluidly on browser clients. Handles rendering of markdown and code formatting seamlessly.
