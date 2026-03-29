"""WorkClaw main entry point — dispatches to CLI or GUI."""

from workclaw.cli.app import app as typer_app, run


def cli_entry() -> None:
    """Main entry point for the `workclaw` command."""
    run()


if __name__ == "__main__":
    cli_entry()
