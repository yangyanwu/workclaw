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
- `projects/` — project config files (YAML)
- `project_analysis/` — consolidated markdown reports and per-repo JSON from `workclaw analyze`

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

---

### How do I analyze multiple repos at once?

Use the project-based analysis workflow:

1. Create a project: `workclaw project create my-project --desc "Description"`
2. Add repos: `workclaw project add-repo my-project <url> --provider github`
3. Run analysis: `workclaw analyze my-project`
4. View the consolidated report at `~/.workclaw/data/project_analysis/my-project_analysis.md`

The analysis pipeline clones each repo (shallow clone), runs `CodeAnalyzer` on up to `max_files` per repo, then uses an LLM summarization pass to produce a consolidated markdown report.

---

### What authentication methods are supported for repo cloning?

Four methods, defined by the `AuthMethod` enum in `src/workclaw/projects/models.py`:

| Method | Use case | How it works |
|---|---|---|
| `HTTPS` | Public repos | No auth needed |
| `HTTPS_CREDENTIALS` | Private HTTPS repos | Username + password fetched from an env var |
| `SSH_KEY` | SSH with explicit key | Sets `GIT_SSH_COMMAND` with `-i <key>`; auto-detects `id_ed25519`/`id_rsa` |
| `SSH_AGENT` | SSH via system agent | Sets `GIT_SSH_COMMAND` with `StrictHostKeyChecking=accept-new` |

Auth is auto-detected from the URL format (git@ → SSH, https:// → HTTPS) but can be overridden with `--auth` on `add-repo`.

---

### How does periodic re-analysis work?

The `AnalysisScheduler` (in `src/workclaw/analysis/scheduler.py`) wraps APScheduler:

1. Set a schedule: `workclaw schedule set my-project "0 9 * * 1-5"` (weekdays at 9am, standard 5-field cron)
2. Start the daemon: `workclaw schedule start --daemon`
3. The scheduler reads all projects with a `schedule_cron` field, registers cron jobs, and runs `AnalysisPipeline.analyze_project(force_reclone=True)` on each trigger.

List active schedules with `workclaw schedule list`, remove with `workclaw schedule remove <project>`.

---

### How does the agent use project analysis?

`agent.set_project_context(name)` loads the consolidated analysis markdown into the system prompt, giving the LLM awareness of the project's codebase structure, issues, and suggestions. `clear_project_context()` removes it. This is useful for follow-up questions about a project after running analysis.
