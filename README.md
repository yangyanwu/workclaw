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

# Analyze a repo with a Jira story
workclaw analyze https://github.com/owner/repo --jira PROJ-123
```

## 🛠️ CLI Commands

| Command | Description |
|---|---|
| `workclaw chat` | Start an interactive chat session |
| `workclaw gui` | Launch the web GUI |
| `workclaw analyze <repo-url>` | Analyze a repository |
| `workclaw pr <repo-url> --jira KEY` | Create a PR for a Jira story |
| `workclaw config set <key> <val>` | Set a config value |
| `workclaw config show` | Show current configuration |
| `workclaw status` | Check integration health |

## 📁 Project Structure

```
WorkClaw/
├── src/workclaw/
│   ├── config/       # Configuration management
│   ├── llm/          # LLM provider abstraction
│   ├── integrations/ # GitHub, Bitbucket, Jira clients
│   ├── core/         # Agent loop, context, memory
│   ├── analysis/     # Code analysis engine
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
