# WorkClaw — Q&A Knowledge Base

Common questions and answers about the WorkClaw project.

---

### Do I need MCP to connect to Jira/Bitbucket/GitHub?

No. WorkClaw has built-in HTTP clients (`httpx.AsyncClient`) under `src/workclaw/integrations/`. Each integration (GitHub, Jira, Bitbucket) talks directly to its REST API. No external protocol or plugin is needed.

---

### How do integrations authenticate?

| Integration | Credentials | Method |
|---|---|---|
| GitHub | Personal Access Token (PAT) | Bearer token in `Authorization` header |
| Jira | Email + API token | Basic Auth (`email:api_token` encoded) |
| Bitbucket | Username + App Password | Basic Auth (`username:app_password`) |

All credentials are supplied via environment variables. See `src/workclaw/config/settings.py` for the full list of `WORKCLAW_*` env vars.

---

### What LLM providers are supported?

OpenAI, Anthropic, Google Gemini, and Ollama (local). Provider selection is handled by `litellm` in `src/workclaw/llm/provider.py`. Set `WORKCLAW_LLM_PROVIDER` and the corresponding API key env var.

---

### Where is conversation data stored?

Under `~/.workclaw/data/`, organized into subdirectories:

- `conversations/` — chat history
- `memory/` — persistent agent memory
- `analysis_reports/` — code analysis output

The storage layer is `src/workclaw/storage/store.py` (`FileStore` class), which uses YAML, JSON, and Markdown files. The data directory is configurable via `WORKCLAW_DATA_DIR`.

---

### How does the agent loop work?

A ReAct (Reason + Act) loop in `src/workclaw/core/agent.py`:

1. Receive user message
2. Assemble context (via `ContextAssembler`)
3. Call the LLM
4. Parse the response — if it contains a tool call, execute the tool and feed the result back; if it contains text, return it as the response
5. Repeat until a text response or max iterations is reached

The agent yields an `AsyncGenerator[AgentEvent]` with event types: `THINKING`, `TOOL_CALL`, `TOOL_RESULT`, `RESPONSE`, `ERROR`, `STATUS`. Max iterations default to 15 and are configurable via `WORKCLAW_AGENT_MAX_ITERATIONS`.

---

### How is config loaded?

Priority order (highest wins):

1. Environment variables with `WORKCLAW_` prefix
2. `.env` file in the project root
3. `~/.workclaw/config.yaml`
4. Built-in defaults in `src/workclaw/config/settings.py`

Settings are managed by a Pydantic `BaseSettings` class with `env_prefix="WORKCLAW_"`.
