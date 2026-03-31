"""WorkClaw CLI — Typer-based command-line interface with Rich formatting."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
import yaml
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
    help="WorkClaw -- AI-powered developer tool for Jira, GitHub, and Bitbucket",
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


def _get_store() -> FileStore:
    settings = get_settings()
    return FileStore(settings.data_dir)


def _get_project_manager():
    from workclaw.projects.manager import ProjectManager

    return ProjectManager(_get_store())


# ---------------------------------------------------------------------------
# Chat command
# ---------------------------------------------------------------------------


@app.command()
def chat(
    conversation_id: Optional[str] = typer.Option(
        None, "--continue", "-c", help="Continue a previous conversation"
    ),
):
    """Start an interactive chat session with WorkClaw."""
    console.print(
        Panel.fit(
            "[bold bright_magenta]WorkClaw[/bold bright_magenta]\n"
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
            console.print(
                f"[yellow]Conversation '{conversation_id}' not found. Starting new.[/yellow]"
            )
            agent.new_conversation()
    else:
        agent.new_conversation()

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ("exit", "quit", "/exit", "/quit"):
            console.print("[dim]Goodbye![/dim]")
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
            console.print(f"[dim]... {event.data.get('message', '')}[/dim]")

        elif event.type == EventType.TOOL_CALL:
            tool_name = event.data.get("tool", "unknown")
            args = event.data.get("arguments", {})
            args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
            console.print(f"[yellow]Calling: {tool_name}({args_str})[/yellow]")

        elif event.type == EventType.TOOL_RESULT:
            tool_name = event.data.get("tool", "")
            output = event.data.get("output", "")
            if len(output) > 200:
                output = output[:200] + "..."
            console.print(f"[dim]   {tool_name}: {output}[/dim]")

        elif event.type == EventType.RESPONSE:
            content = event.data.get("content", "")
            console.print()
            console.print(
                Panel(
                    Markdown(content),
                    title="[bold bright_magenta]WorkClaw[/bold bright_magenta]",
                    border_style="bright_magenta",
                    padding=(1, 2),
                )
            )

            usage = event.data.get("usage", {})
            if usage:
                tokens = usage.get("total_tokens", 0)
                console.print(
                    f"[dim]   Tokens: {tokens} | Model: {event.data.get('model', 'unknown')}[/dim]"
                )

        elif event.type == EventType.ERROR:
            console.print(f"[bold red]Error: {event.data.get('message', '')}[/bold red]")


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
- `/new` -- Start a new conversation
- `/history` -- Show past conversations
- `/help` -- Show this help
- `exit` / `quit` -- Leave the chat

## Example Prompts
- "Analyze the repo at https://github.com/owner/repo"
- "Fetch the Jira story PROJ-123 and create an implementation plan"
- "Read the file src/main.py and suggest improvements"
- "Create a PR for story PROJ-123 with the changes we discussed"
"""
    console.print(Markdown(help_text))


# ---------------------------------------------------------------------------
# GUI command
# ---------------------------------------------------------------------------


@app.command()
def gui(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Launch the web GUI."""
    console.print(
        f"[bold bright_magenta]WorkClaw GUI[/bold bright_magenta] starting at "
        f"[link=http://localhost:{port}]http://localhost:{port}[/link]"
    )
    import uvicorn

    uvicorn.run("workclaw.gui.server:app", host=host, port=port, reload=True)


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


@app.command()
def status():
    """Check integration health status."""
    settings = get_settings()

    table = Table(title="WorkClaw Status", border_style="bright_magenta")
    table.add_column("Integration", style="white")
    table.add_column("Status", style="white")
    table.add_column("Details", style="dim")

    # LLM
    llm_status = (
        "Configured"
        if settings.get_active_api_key() or settings.llm_provider == LLMProvider.OLLAMA
        else "No API key"
    )
    table.add_row("LLM", llm_status, f"{settings.llm_provider.value}/{settings.llm_model}")

    # GitHub
    gh_status = "Token set" if settings.github_token else "No token"
    table.add_row("GitHub", gh_status, settings.github_default_owner or "-")

    # Bitbucket
    bb_status = "Configured" if settings.bitbucket_app_password else "Not configured"
    table.add_row("Bitbucket", bb_status, settings.bitbucket_username or "-")

    # Jira
    jira_status = "Configured" if settings.jira_api_token else "Not configured"
    table.add_row("Jira", jira_status, settings.jira_url or "-")

    console.print(table)


# ---------------------------------------------------------------------------
# Config command
# ---------------------------------------------------------------------------


@app.command(name="config")
def config_cmd(
    action: str = typer.Argument(help="Action: 'show' or 'set'"),
    key: Optional[str] = typer.Argument(None, help="Config key to set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
):
    """Manage WorkClaw configuration."""
    if action == "show":
        settings = get_settings()
        table = Table(title="WorkClaw Configuration", border_style="bright_magenta")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for field_name, field_info in settings.model_fields.items():
            val = getattr(settings, field_name)
            # Mask secrets
            display_val = (
                "***"
                if "secret" in field_name.lower()
                or "token" in field_name.lower()
                or "password" in field_name.lower()
                else str(val)
            )
            if hasattr(val, "get_secret_value"):
                display_val = "***" if val else "Not set"
            table.add_row(field_name, display_val)

        console.print(table)

    elif action == "set":
        if not key or value is None:
            console.print("[red]Usage: workclaw config set <key> <value>[/red]")
            raise typer.Exit(1)

        config_path = Path.home() / ".workclaw" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

        config[key] = value
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        console.print(f"[green]Set {key} = {value}[/green]")
    else:
        console.print(f"[red]Unknown action: {action}. Use 'show' or 'set'.[/red]")


# ---------------------------------------------------------------------------
# Version command
# ---------------------------------------------------------------------------


@app.command()
def version():
    """Show WorkClaw version."""
    console.print(f"[bold bright_magenta]{__app_name__}[/bold bright_magenta] v{__version__}")


# ---------------------------------------------------------------------------
# Project sub-app
# ---------------------------------------------------------------------------

project_app = typer.Typer(
    name="project",
    help="Manage multi-repo projects for code analysis.",
    rich_markup_mode="rich",
)
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(
    name: str = typer.Argument(help="Project name"),
    desc: str = typer.Option("", "--desc", "-d", help="Project description"),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", "-f", help="Load project config from YAML file"
    ),
):
    """Create a new project."""
    from workclaw.projects.models import ProjectConfig, RepoSource

    manager = _get_project_manager()

    if from_file:
        with open(from_file) as fh:
            data = yaml.safe_load(fh)
        config = ProjectConfig(**data)
    else:
        config = ProjectConfig(
            name=name,
            description=desc,
        )

    try:
        config = manager.create_project(config)
        console.print(f"[green]Created project: {config.name}[/green]")
        console.print(f"  Repositories: {len(config.repos)}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@project_app.command("list")
def project_list():
    """List all projects."""
    manager = _get_project_manager()
    projects = manager.list_projects()

    if not projects:
        console.print("[dim]No projects found.[/dim]")
        return

    table = Table(title="Projects", border_style="bright_magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Repos", style="green", justify="right")
    table.add_column("Schedule", style="yellow")
    table.add_column("Last Analysis", style="dim")

    for p in projects:
        table.add_row(
            p.name,
            p.description[:50] if p.description else "-",
            str(len(p.repos)),
            p.schedule_cron or "-",
            (p.last_analysis_at or "-")[:10],
        )

    console.print(table)


@project_app.command("show")
def project_show(
    name: str = typer.Argument(help="Project name"),
):
    """Show project details."""
    manager = _get_project_manager()
    project = manager.get_project(name)

    if not project:
        console.print(f"[red]Project '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]{project.name}[/bold]\n"
            f"Description: {project.description or '-'}\n"
            f"Created: {project.created_at or '-'}\n"
            f"Updated: {project.updated_at or '-'}\n"
            f"Last Analysis: {project.last_analysis_at or '-'}\n"
            f"Schedule: {project.schedule_cron or '-'}\n"
            f"Max Files/Repo: {project.analysis_max_files_per_repo}\n"
            f"Focus Areas: "
            f"{', '.join(project.analysis_focus_areas) if project.analysis_focus_areas else '-'}",
            title="Project Details",
            border_style="bright_magenta",
        )
    )

    if project.repos:
        table = Table(title="Repositories", border_style="bright_magenta")
        table.add_column("Name", style="cyan")
        table.add_column("URL", style="white")
        table.add_column("Provider", style="green")
        table.add_column("Branch", style="yellow")
        table.add_column("Auth", style="dim")

        for r in project.repos:
            table.add_row(
                r.name or "-",
                r.url,
                r.provider,
                r.branch or "-",
                r.auth_method.value,
            )
        console.print(table)


@project_app.command("add-repo")
def project_add_repo(
    name: str = typer.Argument(help="Project name"),
    url: str = typer.Argument(help="Repository URL"),
    provider: str = typer.Option("other", "--provider", "-p", help="github|bitbucket|other"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch to clone"),
    auth: str = typer.Option("https", "--auth", "-a", help="Auth method"),
    ssh_key: Optional[Path] = typer.Option(None, "--ssh-key", help="Path to SSH key"),
):
    """Add a repository to a project."""
    from workclaw.projects.models import AuthMethod, RepoSource

    manager = _get_project_manager()

    repo = RepoSource(
        url=url,
        provider=provider,
        branch=branch,
        auth_method=AuthMethod(auth),
        ssh_key_path=ssh_key,
    )

    try:
        project = manager.add_repo(name, repo)
        console.print(f"[green]Added repo: {repo.name} -> {project.name}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@project_app.command("remove-repo")
def project_remove_repo(
    name: str = typer.Argument(help="Project name"),
    url: str = typer.Argument(help="Repository URL to remove"),
):
    """Remove a repository from a project."""
    manager = _get_project_manager()

    try:
        project = manager.remove_repo(name, url)
        console.print(f"[green]Removed repo from {project.name}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@project_app.command("delete")
def project_delete(
    name: str = typer.Argument(help="Project name"),
):
    """Delete a project."""
    manager = _get_project_manager()

    if manager.delete_project(name):
        console.print(f"[green]Deleted project: {name}[/green]")
    else:
        console.print(f"[red]Project '{name}' not found.[/red]")
        raise typer.Exit(1)


@project_app.command("validate")
def project_validate(
    config_file: Path = typer.Argument(help="Path to project YAML config"),
):
    """Validate a project YAML config file."""
    from workclaw.projects.models import ProjectConfig

    try:
        with open(config_file) as f:
            data = yaml.safe_load(f)
        config = ProjectConfig(**data)
        console.print(f"[green]Valid config for project: {config.name}[/green]")
        console.print(f"  Repositories: {len(config.repos)}")

        manager = _get_project_manager()
        warnings = manager.validate_project(config)
        if warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  [yellow]- {w}[/yellow]")
        else:
            console.print("[green]No warnings.[/green]")
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Analyze command
# ---------------------------------------------------------------------------


def _analyze_impl(
    project_name: str,
    force: bool = False,
    max_files_override: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> None:
    """Shared implementation for analyze and schedule run."""
    from workclaw.analysis.pipeline import AnalysisPipeline
    from workclaw.llm.provider import LLMProvider as LLMProviderClass

    manager = _get_project_manager()
    config = manager.get_project(project_name)

    if not config:
        console.print(f"[red]Project '{project_name}' not found.[/red]")
        raise typer.Exit(1)

    if not config.repos:
        console.print(f"[red]Project '{project_name}' has no repositories. Use 'add-repo' first.[/red]")
        raise typer.Exit(1)

    if max_files_override:
        config.analysis_max_files_per_repo = max_files_override

    settings = get_settings()
    store = _get_store()
    llm = LLMProviderClass(settings)
    pipeline = AnalysisPipeline(llm, store, settings.workspace_dir)

    console.print(f"[bold]Analyzing project: {project_name}[/bold] ({len(config.repos)} repos)")

    async def _run():
        return await pipeline.analyze_project(config, force_reclone=force)

    result = asyncio.run(_run())

    console.print(
        f"\n[green]Analysis complete: {result.success_count} ok, "
        f"{result.failure_count} failed[/green]"
    )

    for r in result.repo_results:
        status = "[green]OK[/green]" if r.success else f"[red]FAILED[/red] ({r.error})"
        console.print(f"  {r.repo_name}: {status}")

    if result.output_path:
        console.print(f"\nReport saved to: [cyan]{result.output_path}[/cyan]")

    if output_path and result.consolidated_markdown:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.consolidated_markdown)
        console.print(f"Also saved to: [cyan]{output_path}[/cyan]")


@app.command()
def analyze(
    project: str = typer.Argument(help="Project name to analyze"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-clone"),
    max_files: Optional[int] = typer.Option(None, "--max-files", help="Max files per repo"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Custom output path"),
):
    """Analyze all repos in a project and generate a consolidated report."""
    _analyze_impl(
        project_name=project,
        force=force,
        max_files_override=max_files,
        output_path=output,
    )


# ---------------------------------------------------------------------------
# Schedule sub-app
# ---------------------------------------------------------------------------

schedule_app = typer.Typer(
    name="schedule",
    help="Manage periodic project analysis schedules.",
    rich_markup_mode="rich",
)
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("start")
def schedule_start(
    daemon: bool = typer.Option(False, "--daemon", help="Run as blocking daemon"),
):
    """Start the analysis scheduler."""
    from workclaw.analysis.pipeline import AnalysisPipeline
    from workclaw.analysis.scheduler import AnalysisScheduler
    from workclaw.llm.provider import LLMProvider as LLMProviderClass

    settings = get_settings()
    store = _get_store()
    llm = LLMProviderClass(settings)
    manager = _get_project_manager()
    pipeline = AnalysisPipeline(llm, store, settings.workspace_dir)
    scheduler = AnalysisScheduler(pipeline, manager)

    scheduler.start()
    console.print("[green]Scheduler started.[/green]")

    if daemon:
        console.print("[dim]Running as daemon. Press Ctrl+C to stop.[/dim]")
        try:
            import signal

            signal.pause()
        except KeyboardInterrupt:
            scheduler.stop()
            console.print("[dim]Scheduler stopped.[/dim]")
    else:
        console.print("[dim]Scheduler running in foreground. Use --daemon for blocking mode.[/dim]")


@schedule_app.command("list")
def schedule_list():
    """List scheduled analysis jobs."""
    manager = _get_project_manager()
    # Load existing schedules from project configs
    projects = manager.list_projects()
    jobs_from_config = [
        {"project": p.name, "cron": p.schedule_cron, "source": "config"}
        for p in projects
        if p.schedule_cron
    ]

    if not jobs_from_config:
        console.print("[dim]No scheduled analysis jobs.[/dim]")
        return

    table = Table(title="Scheduled Analysis Jobs", border_style="bright_magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Cron", style="white")
    table.add_column("Source", style="dim")

    for job in jobs_from_config:
        table.add_row(job["project"], job["cron"], job["source"])

    console.print(table)


@schedule_app.command("set")
def schedule_set(
    project: str = typer.Argument(help="Project name"),
    cron: str = typer.Argument(help="Cron expression (e.g. '0 2 * * 1')"),
):
    """Set a periodic analysis schedule for a project."""
    manager = _get_project_manager()
    config = manager.get_project(project)
    if not config:
        console.print(f"[red]Project '{project}' not found.[/red]")
        raise typer.Exit(1)

    # Validate cron expression
    parts = cron.split()
    if len(parts) != 5:
        console.print("[red]Invalid cron expression. Expected 5 fields: MIN HOUR DOM MON DOW[/red]")
        raise typer.Exit(1)

    manager.update_project(project, {"schedule_cron": cron})
    console.print(f"[green]Schedule set for {project}: {cron}[/green]")


@schedule_app.command("remove")
def schedule_remove(
    project: str = typer.Argument(help="Project name"),
):
    """Remove the analysis schedule for a project."""
    manager = _get_project_manager()
    config = manager.get_project(project)
    if not config:
        console.print(f"[red]Project '{project}' not found.[/red]")
        raise typer.Exit(1)

    manager.update_project(project, {"schedule_cron": None})
    console.print(f"[green]Schedule removed for {project}[/green]")


@schedule_app.command("run")
def schedule_run(
    project: str = typer.Argument(help="Project name"),
):
    """Run analysis immediately (one-shot)."""
    _analyze_impl(project_name=project, force=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    """Entry point for the CLI."""
    app()
