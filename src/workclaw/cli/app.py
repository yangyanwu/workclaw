"""WorkClaw CLI — Typer-based command-line interface with Rich formatting."""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from workclaw import __app_name__, __version__
from workclaw.config.settings import LLMProvider, get_settings
from workclaw.core.agent import EventType, WorkClawAgent
from workclaw.core.memory import Memory
from workclaw.llm.provider import LLMProvider as LLMProviderClass
from workclaw.storage.store import FileStore
from workclaw.tools.file_ops import (
    ListDirectoryTool,
    ReadFileTool,
    SearchInFilesTool,
    WriteFileTool,
)
from workclaw.tools.git_ops import (
    GitBranchTool,
    GitCloneTool,
    GitCommitTool,
    GitDiffTool,
    GitPushTool,
    GitStatusTool,
)
from workclaw.tools.registry import ToolRegistry
from workclaw.tools.shell import ShellTool

app = typer.Typer(
    name="workclaw",
    help="💠 WorkClaw — AI-powered developer tool for Jira, GitHub, and Bitbucket",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


def _create_agent():
    """Bootstrap the agent with all dependencies."""
    settings = get_settings()

    # Storage & Memory
    store = FileStore(settings.data_dir)
    memory = Memory(store)

    # LLM
    llm = LLMProviderClass(settings)

    # Tools
    registry = ToolRegistry()
    for tool_cls in [
        ReadFileTool,
        WriteFileTool,
        ListDirectoryTool,
        SearchInFilesTool,
        GitCloneTool,
        GitBranchTool,
        GitCommitTool,
        GitPushTool,
        GitDiffTool,
        GitStatusTool,
        ShellTool,
    ]:
        registry.register(tool_cls())

    return WorkClawAgent(settings, llm, registry, memory)


@app.command()
def chat(
    conversation_id: Optional[str] = typer.Option(
        None, "--continue", "-c", help="Continue a previous conversation"
    ),
):
    """Start an interactive chat session with WorkClaw. 💬"""
    console.print(
        Panel.fit(
            "[bold bright_magenta]💠 WorkClaw[/bold bright_magenta]\n"
            "[dim]AI-powered developer assistant[/dim]\n\n"
            "[dim]Type your message and press Enter. Type 'exit' or 'quit' to leave.[/dim]\n"
            "[dim]Type '/new' for a new conversation, '/history' to see past chats.[/dim]",
            border_style="bright_magenta",
        )
    )

    agent = _create_agent()

    if conversation_id:
        conv = agent.load_conversation(conversation_id)
        if conv:
            console.print(f"[dim]Resumed conversation: {conv.title}[/dim]")
        else:
            console.print(f"[yellow]Conversation '{conversation_id}' not found. Starting new.[/yellow]")
            agent.new_conversation()
    else:
        agent.new_conversation()

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! 💠[/dim]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ("exit", "quit", "/exit", "/quit"):
            console.print("[dim]Goodbye! 💠[/dim]")
            break

        if cmd == "/new":
            agent.new_conversation()
            console.print("[green]Started a new conversation.[/green]")
            continue

        if cmd == "/history":
            _show_history(agent)
            continue

        if cmd == "/help":
            _show_help()
            continue

        # Process message through the agent
        asyncio.run(_process_message(agent, user_input))


async def _process_message(agent: WorkClawAgent, message: str) -> None:
    """Process a user message and display streaming events."""
    async for event in agent.run(message):
        if event.type == EventType.STATUS:
            console.print(f"[dim]⏳ {event.data.get('message', '')}[/dim]")

        elif event.type == EventType.TOOL_CALL:
            tool_name = event.data.get("tool", "unknown")
            args = event.data.get("arguments", {})
            args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
            console.print(f"[yellow]🔧 Calling: {tool_name}({args_str})[/yellow]")

        elif event.type == EventType.TOOL_RESULT:
            tool_name = event.data.get("tool", "")
            output = event.data.get("output", "")
            if len(output) > 200:
                output = output[:200] + "..."
            console.print(f"[dim]   ✅ {tool_name}: {output}[/dim]")

        elif event.type == EventType.RESPONSE:
            content = event.data.get("content", "")
            console.print()
            console.print(
                Panel(
                    Markdown(content),
                    title="[bold bright_magenta]💠 WorkClaw[/bold bright_magenta]",
                    border_style="bright_magenta",
                    padding=(1, 2),
                )
            )

            usage = event.data.get("usage", {})
            if usage:
                tokens = usage.get("total_tokens", 0)
                console.print(
                    f"[dim]   📊 Tokens: {tokens} | Model: {event.data.get('model', 'unknown')}[/dim]"
                )

        elif event.type == EventType.ERROR:
            console.print(f"[bold red]❌ Error: {event.data.get('message', '')}[/bold red]")


def _show_history(agent: WorkClawAgent) -> None:
    """Show conversation history."""
    conversations = agent.list_conversations()
    if not conversations:
        console.print("[dim]No saved conversations.[/dim]")
        return

    table = Table(title="Conversation History", border_style="bright_magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Created", style="dim")

    for conv in conversations[:20]:
        table.add_row(conv["id"], conv["title"][:60], conv.get("created_at", "")[:10])

    console.print(table)
    console.print("[dim]Use: workclaw chat --continue <ID> to resume[/dim]")


def _show_help() -> None:
    """Show help for chat commands."""
    help_text = """
## Chat Commands
- `/new` — Start a new conversation
- `/history` — Show past conversations
- `/help` — Show this help
- `exit` / `quit` — Leave the chat

## Example Prompts
- "Analyze the repo at https://github.com/owner/repo"
- "Fetch the Jira story PROJ-123 and create an implementation plan"
- "Read the file src/main.py and suggest improvements"
- "Create a PR for story PROJ-123 with the changes we discussed"
"""
    console.print(Markdown(help_text))


# --- Non-chat commands ---

@app.command()
def gui(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Launch the web GUI. 🌐"""
    console.print(
        f"[bold bright_magenta]💠 WorkClaw GUI[/bold bright_magenta] starting at "
        f"[link=http://localhost:{port}]http://localhost:{port}[/link]"
    )
    import uvicorn

    uvicorn.run("workclaw.gui.server:app", host=host, port=port, reload=True)


@app.command()
def status():
    """Check integration health status. 🔍"""
    settings = get_settings()

    table = Table(title="WorkClaw Status", border_style="bright_magenta")
    table.add_column("Integration", style="white")
    table.add_column("Status", style="white")
    table.add_column("Details", style="dim")

    # LLM
    llm_status = "✅ Configured" if settings.get_active_api_key() or settings.llm_provider == LLMProvider.OLLAMA else "❌ No API key"
    table.add_row("LLM", llm_status, f"{settings.llm_provider.value}/{settings.llm_model}")

    # GitHub
    gh_status = "✅ Token set" if settings.github_token else "❌ No token"
    table.add_row("GitHub", gh_status, settings.github_default_owner or "-")

    # Bitbucket
    bb_status = "✅ Configured" if settings.bitbucket_app_password else "❌ Not configured"
    table.add_row("Bitbucket", bb_status, settings.bitbucket_username or "-")

    # Jira
    jira_status = "✅ Configured" if settings.jira_api_token else "❌ Not configured"
    table.add_row("Jira", jira_status, settings.jira_url or "-")

    console.print(table)


@app.command(name="config")
def config_cmd(
    action: str = typer.Argument(help="Action: 'show' or 'set'"),
    key: Optional[str] = typer.Argument(None, help="Config key to set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
):
    """Manage WorkClaw configuration. ⚙️"""
    if action == "show":
        settings = get_settings()
        table = Table(title="WorkClaw Configuration", border_style="bright_magenta")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for field_name, field_info in settings.model_fields.items():
            val = getattr(settings, field_name)
            # Mask secrets
            display_val = "***" if "secret" in field_name.lower() or "token" in field_name.lower() or "password" in field_name.lower() else str(val)
            if hasattr(val, "get_secret_value"):
                display_val = "***" if val else "Not set"
            table.add_row(field_name, display_val)

        console.print(table)

    elif action == "set":
        if not key or value is None:
            console.print("[red]Usage: workclaw config set <key> <value>[/red]")
            raise typer.Exit(1)

        # Write to config YAML
        from pathlib import Path

        import yaml

        config_path = Path.home() / ".workclaw" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

        config[key] = value
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        console.print(f"[green]✅ Set {key} = {value}[/green]")
    else:
        console.print(f"[red]Unknown action: {action}. Use 'show' or 'set'.[/red]")


@app.command()
def version():
    """Show WorkClaw version. 📋"""
    console.print(f"[bold bright_magenta]{__app_name__}[/bold bright_magenta] v{__version__}")


def run() -> None:
    """Entry point for the CLI."""
    app()
