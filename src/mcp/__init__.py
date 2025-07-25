"""
MCP Server Integration for CETO (Claude Enhanced Task Orchestrator).

This module provides MCP protocol integration that transforms Praxis pipelines
into discoverable tools for Claude Code, enabling recursive composition and
intelligent development workflows.
"""

from .models import ExecutionUpdate, MCPTool, MCPToolSpec
from .server import MCPServer
from .tool_registry import MCPToolRegistry

__all__ = [
    "MCPServer",
    "MCPToolRegistry", 
    "MCPTool",
    "MCPToolSpec",
    "ExecutionUpdate"
]