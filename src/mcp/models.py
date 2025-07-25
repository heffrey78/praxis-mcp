"""
Data models for MCP integration.

Defines the core data structures used in MCP protocol communication
and tool representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ToolType(str, Enum):
    """Types of tools available in the system."""
    ATOMIC = "atomic"
    PIPELINE = "pipeline" 
    MEGA_WORKFLOW = "mega_workflow"


class ExecutionStatus(str, Enum):
    """Execution status for progress updates."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionUpdate:
    """Real-time execution update for progress streaming."""
    step_name: str
    status: ExecutionStatus
    progress: float  # 0.0 to 1.0
    message: str
    estimated_remaining: int  # seconds
    metadata: Optional[Dict[str, Any]] = None


class MCPToolSpec(BaseModel):
    """Tool specification for MCP protocol."""
    
    name: str = Field(..., description="Tool identifier")
    description: str = Field(..., description="Tool purpose and capabilities")
    tool_type: ToolType = Field(..., description="Type of tool")
    
    # MCP Schema definitions
    input_schema: Dict[str, Any] = Field(..., description="Input schema (JSON Schema)")
    output_schema: Dict[str, Any] = Field(..., description="Output schema (JSON Schema)")
    
    # Tool metadata
    estimated_duration: int = Field(default=0, description="Estimated execution time in seconds")
    supports_streaming: bool = Field(default=False, description="Supports real-time progress updates")
    supports_cancellation: bool = Field(default=False, description="Can be cancelled mid-execution")
    
    # Dependencies and requirements
    required_tools: List[str] = Field(default_factory=list, description="Tools this tool depends on")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    
    # Additional metadata for enhanced functionality
    complexity: str = Field(default="low", description="Complexity level: low, medium, high")
    category: Optional[str] = Field(None, description="Tool category for organization")
    tags: List[str] = Field(default_factory=list, description="Tags for tool discovery")
    version: str = Field(default="1.0.0", description="Tool version")
    
    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert to MCP tool schema format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "metadata": {
                "tool_type": self.tool_type,
                "estimated_duration": self.estimated_duration,
                "supports_streaming": self.supports_streaming,
                "supports_cancellation": self.supports_cancellation,
                "required_tools": self.required_tools,
                "complexity": self.complexity,
                "category": self.category,
                "tags": self.tags,
                "version": self.version
            }
        }


class MCPTool(BaseModel):
    """
    Represents a tool that can be executed through MCP protocol.
    
    This is the runtime representation of a tool, containing both
    the specification and execution logic.
    """
    
    spec: MCPToolSpec = Field(..., description="Tool specification")
    
    # Execution context
    is_available: bool = Field(default=True, description="Tool availability status")
    last_used: Optional[str] = Field(None, description="Last execution timestamp")
    usage_count: int = Field(default=0, description="Number of times executed")
    
    # Performance metrics
    average_duration: Optional[float] = Field(None, description="Average execution time")
    success_rate: Optional[float] = Field(None, description="Success rate (0.0 to 1.0)")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            ExecutionStatus: lambda v: v.value,
            ToolType: lambda v: v.value
        }


class MCPRequest(BaseModel):
    """Base MCP request model."""
    method: str = Field(..., description="MCP method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")


class MCPResponse(BaseModel):
    """Base MCP response model."""
    result: Optional[Any] = Field(None, description="Method result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information")
    id: Optional[Union[str, int]] = Field(None, description="Request ID")


class ListToolsRequest(MCPRequest):
    """Request for listing available tools."""
    method: str = Field(default="tools/list", const=True)


class ListToolsResponse(MCPResponse):
    """Response containing available tools."""
    result: List[Dict[str, Any]] = Field(..., description="List of available tools")


class CallToolRequest(MCPRequest):
    """Request for executing a tool."""
    method: str = Field(default="tools/call", const=True)
    params: Dict[str, Any] = Field(..., description="Tool execution parameters")
    
    @property
    def tool_name(self) -> str:
        """Get the tool name from parameters."""
        return self.params.get("name", "")
    
    @property
    def tool_arguments(self) -> Dict[str, Any]:
        """Get the tool arguments from parameters."""
        return self.params.get("arguments", {})


class CallToolResponse(MCPResponse):
    """Response from tool execution."""
    result: Dict[str, Any] = Field(..., description="Tool execution result")


class ProgressUpdate(BaseModel):
    """Progress update for streaming execution."""
    tool_name: str = Field(..., description="Name of executing tool")
    update: ExecutionUpdate = Field(..., description="Progress update details")
    timestamp: str = Field(..., description="Update timestamp")