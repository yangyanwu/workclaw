# 💠 WorkClaw

**AI-powered developer tool** that integrates Jira, GitHub, and Bitbucket for automated code analysis and pull request creation.

WorkClaw fetches requirements from Jira stories, reads and analyzes your codebase, suggests improvements (including refactoring and bug fixes), modifies code, and submits pull requests — all through a conversational interface.

---

## ✨ Features

- **🤖 Multi-LLM Support** — OpenAI, Anthropic, Google Gemini, and local Ollama models
- **📋 Jira Integration** — Fetch stories, understand requirements, update ticket status
- **🐙 GitHub Integration** — Read code, create branches, submit PRs
- **🪣 Bitbucket Integration** — Same capabilities for Bitbucket repos
- **🔍 Code Analysis** — Detect bugs, suggest refactoring, identify improvements
- **💬 Conversational UI** — Chat via CLI or a beautiful web interface
- **🧠 Persistent Memory** — Remembers your projects, preferences, and past conversations
- **🔌 Extensible** — Plugin architecture for future integrations (Teams, Slack, etc.)

## 🚀 Quick Start

### 1. Install

```bash
# Clone the repository
git clone <your-repo-url>
cd WorkClaw

# Install with pip
pip install -e ".[dev]"
```

### 2. Configure

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
# At minimum, set an LLM API key and a GitHub token
```

### 3. Run

```bash
# CLI interactive chat
workclaw chat

# Web GUI
workclaw gui
# Then open http://localhost:8000

# Create a project and add repos
workclaw project create my-project --desc "My codebase"
workclaw project add-repo my-project https://github.com/owner/repo.git --provider github

# Analyze all repos in the project
workclaw analyze my-project
```

## 🛠️ CLI Commands

### Core

| Command | Description |
|---|---|
| `workclaw chat` | Start an interactive chat session |
| `workclaw gui` | Launch the web GUI |
| `workclaw status` | Check integration health |
| `workclaw config set <key> <val>` | Set a config value |
| `workclaw config show` | Show current configuration |
| `workclaw version` | Show version |

### Project Management

| Command | Description |
|---|---|
| `workclaw project create <name> --desc "..."` | Create a project |
| `workclaw project list` | List all projects |
| `workclaw project show <name>` | Show project details |
| `workclaw project add-repo <name> <url> --provider <p>` | Add a repository |
| `workclaw project remove-repo <name> <url>` | Remove a repository |
| `workclaw project delete <name>` | Delete a project |
| `workclaw project validate <file>` | Validate a YAML config |

### Analysis

| Command | Description |
|---|---|
| `workclaw analyze <project> [--force] [--max-files N] [-o path]` | Analyze all repos in a project |

### Scheduling

| Command | Description |
|---|---|
| `workclaw schedule set <project> "<cron>"` | Set a periodic analysis schedule |
| `workclaw schedule list` | List schedules |
| `workclaw schedule remove <project>` | Remove a schedule |
| `workclaw schedule run <project>` | Run analysis immediately |
| `workclaw schedule start [--daemon]` | Start the scheduler daemon |

## ⚙️ Configuration

### LLM Providers

| Provider | `WORKCLAW_LLM_PROVIDER` | Env var for key |
|---|---|---|
| OpenAI | `openai` | `WORKCLAW_OPENAI_API_KEY` |
| Anthropic | `anthropic` | `WORKCLAW_ANTHROPIC_API_KEY` |
| Google Gemini | `google` | `WORKCLAW_GOOGLE_API_KEY` |
| Ollama (local) | `ollama` | `WORKCLAW_OLLAMA_API_BASE` |

### Example `.env`

```
WORKCLAW_LLM_PROVIDER=google
WORKCLAW_LLM_MODEL=gemini/gemini-2.0-flash
WORKCLAW_GOOGLE_API_KEY=your-key-here
```

### Config Precedence

Environment variables (`WORKCLAW_` prefix) > `.env` file > `~/.workclaw/config.yaml` > defaults

## 🔬 Project Analysis Workflow

1. **Create a project** — `workclaw project create my-project --desc "Description"`
2. **Add repos** — Supports public HTTPS, SSH, or HTTPS with credentials:
   ```bash
   workclaw project add-repo my-project https://github.com/owner/repo.git --provider github
   workclaw project add-repo my-project git@github.com:owner/repo.git --provider github
   ```
3. **Run analysis** — `workclaw analyze my-project`
4. **Check the report** — Consolidated markdown at `~/.workclaw/data/project_analysis/my-project_analysis.md`
5. **Optionally schedule** periodic re-analysis:
   ```bash
   workclaw schedule set my-project "0 9 * * 1-5"  # Weekdays at 9am
   workclaw schedule start
   ```

## 📁 Project Structure

```
WorkClaw/
├── src/workclaw/
│   ├── config/       # Configuration management
│   ├── llm/          # LLM provider abstraction
│   ├── integrations/ # GitHub, Bitbucket, Jira clients
│   ├── core/         # Agent loop, context, memory
│   ├── analysis/     # Code analysis engine
│   ├── projects/     # Multi-repo project config & management
│   ├── tools/        # Agent tools (file, git, shell)
│   ├── cli/          # Typer CLI application
│   ├── gui/          # FastAPI web GUI
│   └── storage/      # File-based persistence
├── data/             # Runtime data (conversations, memory)
└── tests/            # Test suite
```

## 🔧 Development

```bash
make install   # Install with dev dependencies
make dev       # Run GUI with hot reload
make test      # Run tests
make lint      # Run linters
make format    # Auto-format code
```

## 📄 License

MIT
