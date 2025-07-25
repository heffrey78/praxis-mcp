"""
Main CLI for CETO (Claude Enhanced Task Orchestrator).
"""

import typer

from .mcp.cli import app as mcp_app

# Create main CLI app
app = typer.Typer(
    name="ceto",
    help="CETO: Claude Enhanced Task Orchestrator",
    context_settings={"help_option_names": ["-h", "--help"]}
)

# Add MCP server commands
app.add_typer(mcp_app, name="mcp", help="MCP server management")


@app.command()
def version() -> None:
    """Show CETO version information."""
    typer.echo("CETO (Claude Enhanced Task Orchestrator) v1.0.0")
    typer.echo("MCP-based platform for intelligent development workflows")


@app.command()
def info() -> None:
    """Show system information."""
    typer.echo("🎯 CETO System Information")
    typer.echo("=" * 40)
    typer.echo("Status: Development Phase")
    typer.echo("Architecture: MCP-based recursive tool composition")
    typer.echo("Core Engine: Praxis DAG execution system")
    typer.echo("")
    typer.echo("Available Commands:")
    typer.echo("  • ceto mcp start    - Start MCP server")
    typer.echo("  • ceto mcp test     - Test MCP connection")
    typer.echo("  • ceto mcp list     - List available tools")


if __name__ == "__main__":
    app()