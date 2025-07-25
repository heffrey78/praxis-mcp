"""
CLI commands for CETO MCP Server.
"""

import logging

import typer

from .server import MCPServer
from .tool_registry import MCPToolRegistry

app = typer.Typer(help="CETO MCP Server commands")

logger = logging.getLogger(__name__)


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", help="Server host address"),
    port: int = typer.Option(8081, help="Server port number"),
    debug: bool = typer.Option(False, help="Enable debug logging")
) -> None:
    """Start the CETO MCP server."""
    
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    typer.echo(f"🚀 Starting CETO MCP Server on {host}:{port}")
    
    try:
        # Create tool registry
        tool_registry = MCPToolRegistry()
        
        # TODO: Auto-discover and register tools from Praxis
        # This would scan for available plugins and pipeline definitions
        typer.echo("📋 Tool registry initialized")
        
        # Create and start server
        server = MCPServer(
            tool_registry=tool_registry,
            host=host,
            port=port
        )
        
        typer.echo("🎯 Server starting... (Press Ctrl+C to stop)")
        server.run()
        
    except KeyboardInterrupt:
        typer.echo("\n⏹️  Server stopped")
    except Exception as e:
        typer.echo(f"❌ Server error: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def test_connection(
    host: str = typer.Option("127.0.0.1", help="Server host address"),
    port: int = typer.Option(8081, help="Server port number")
) -> None:
    """Test connection to MCP server."""
    import httpx
    
    url = f"http://{host}:{port}/health"
    
    try:
        response = httpx.get(url, timeout=5.0)
        if response.status_code == 200:
            typer.echo("✅ MCP server is healthy")
            typer.echo(f"Response: {response.json()}")
        else:
            typer.echo(f"❌ Server returned status {response.status_code}")
            raise typer.Exit(1)
            
    except httpx.RequestError as e:
        typer.echo(f"❌ Connection failed: {e}")
        raise typer.Exit(1) from e


@app.command()
def list_tools(
    host: str = typer.Option("127.0.0.1", help="Server host address"),
    port: int = typer.Option(8081, help="Server port number")
) -> None:
    """List available tools from MCP server."""
    import httpx
    
    url = f"http://{host}:{port}/mcp/tools"
    
    try:
        response = httpx.get(url, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            tools = data.get("result", [])
            
            typer.echo(f"📋 Found {len(tools)} available tools:")
            
            for tool in tools:
                name = tool.get("name", "Unknown")
                description = tool.get("description", "No description")
                metadata = tool.get("metadata", {})
                tool_type = metadata.get("tool_type", "unknown")
                duration = metadata.get("estimated_duration", 0)
                
                typer.echo(f"  • {name} ({tool_type}) - {duration}s")
                typer.echo(f"    {description}")
                
        else:
            typer.echo(f"❌ Server returned status {response.status_code}")
            raise typer.Exit(1)
            
    except httpx.RequestError as e:
        typer.echo(f"❌ Connection failed: {e}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()