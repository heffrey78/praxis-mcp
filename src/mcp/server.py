"""
Core MCP Server for CETO.

This module implements the MCP protocol server that enables Claude Code
to discover and execute Praxis workflows as tools.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from src.core.dag_executor import ExecutionUpdate as PraxisExecutionUpdate
from src.core.dependency_container import DependencyContainer
from src.core.execution_context import create_execution_context
from src.core.orchestrator import PipelineOrchestrator

from .models import (
    CallToolRequest,
    CallToolResponse,
    ExecutionStatus,
    ExecutionUpdate,
    ListToolsRequest,
    ListToolsResponse,
    MCPRequest,
    MCPResponse,
    ProgressUpdate,
)
from .tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class MCPServer:
    """
    Core MCP server that provides tool discovery and execution
    for Praxis workflows through the MCP protocol.
    """
    
    def __init__(
        self,
        tool_registry: Optional[MCPToolRegistry] = None,
        dependency_container: Optional[DependencyContainer] = None,
        host: str = "127.0.0.1",
        port: int = 8081
    ) -> None:
        """
        Initialize the MCP server.
        
        Args:
            tool_registry: Registry for managing tools
            dependency_container: Praxis dependency container
            host: Server host address
            port: Server port number
        """
        self.tool_registry = tool_registry or MCPToolRegistry()
        self.dependency_container = dependency_container or DependencyContainer()
        self.host = host
        self.port = port
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="CETO MCP Server",
            description="Claude Enhanced Task Orchestrator - MCP Protocol Server",
            version="1.0.0"
        )
        
        # Active executions for progress tracking
        self._active_executions: Dict[str, asyncio.Task] = {}
        self._execution_updates: Dict[str, List[ExecutionUpdate]] = {}
        
        # Setup routes
        self._setup_routes()
        
    def _setup_routes(self) -> None:
        """Setup FastAPI routes for MCP protocol."""
        
        @self.app.post("/mcp", response_model=MCPResponse)
        async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
            """Handle MCP protocol requests."""
            try:
                if request.method == "tools/list":
                    return await self._handle_list_tools(ListToolsRequest(**request.dict()))
                if request.method == "tools/call":
                    return await self._handle_call_tool(CallToolRequest(**request.dict()))
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown MCP method: {request.method}"
                )
            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                return MCPResponse(
                    error={
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    },
                    id=request.id
                )
        
        @self.app.get("/mcp/tools")
        async def list_tools() -> ListToolsResponse:
            """HTTP GET endpoint for listing tools."""
            request = ListToolsRequest()
            return await self._handle_list_tools(request)
        
        @self.app.get("/mcp/progress/{execution_id}")
        async def stream_progress(execution_id: str) -> StreamingResponse:
            """Stream execution progress updates."""
            return EventSourceResponse(self._stream_execution_progress(execution_id))
        
        @self.app.get("/health")
        async def health_check() -> Dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy", "service": "ceto-mcp-server"}
    
    async def _handle_list_tools(self, request: ListToolsRequest) -> ListToolsResponse:
        """
        Handle tools/list MCP method.
        
        Args:
            request: List tools request
            
        Returns:
            Response with available tools
        """
        logger.info("Handling list_tools request")
        
        try:
            # Get all available tools from registry
            tools = self.tool_registry.list_tools()
            
            # Convert to MCP schema format
            tool_schemas = [tool.to_mcp_schema() for tool in tools]
            
            logger.info(f"Returning {len(tool_schemas)} tools")
            
            return ListToolsResponse(
                result=tool_schemas,
                id=request.id
            )
            
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def _handle_call_tool(self, request: CallToolRequest) -> CallToolResponse:
        """
        Handle tools/call MCP method.
        
        Args:
            request: Call tool request
            
        Returns:
            Response with tool execution result
        """
        tool_name = request.tool_name
        arguments = request.tool_arguments
        
        logger.info(f"Handling call_tool request for: {tool_name}")
        
        try:
            # Validate tool exists and is available
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool not found: {tool_name}"
                )
                
            if not tool.is_available:
                raise HTTPException(
                    status_code=503,
                    detail=f"Tool not available: {tool_name}"
                )
            
            # Validate dependencies
            missing_deps = self.tool_registry.validate_tool_dependencies(tool_name)
            if missing_deps:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing dependencies: {missing_deps}"
                )
            
            # Execute the tool
            result = await self._execute_tool(tool_name, arguments)
            
            # Update tool usage statistics
            tool.usage_count += 1
            tool.last_used = time.strftime("%Y-%m-%d %H:%M:%S")
            
            logger.info(f"Successfully executed tool: {tool_name}")
            
            return CallToolResponse(
                result=result,
                id=request.id
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Generate execution ID for progress tracking
        execution_id = f"{tool_name}_{int(time.time())}"
        
        if tool.spec.tool_type.value == "atomic":
            return await self._execute_atomic_tool(execution_id, tool_name, arguments)
        if tool.spec.tool_type.value == "pipeline":
            return await self._execute_pipeline_tool(execution_id, tool_name, arguments)
        raise ValueError(f"Unknown tool type: {tool.spec.tool_type}")
    
    async def _execute_atomic_tool(
        self, 
        execution_id: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an atomic tool."""
        logger.info(f"Executing atomic tool: {tool_name}")
        
        # Initialize progress tracking
        self._execution_updates[execution_id] = []
        
        try:
            # Create execution context
            context = create_execution_context(
                task_id=execution_id,
                container=self.dependency_container
            )
            
            # Add arguments to context
            for key, value in arguments.items():
                context[key] = value
            
            # Get plugin from step registry
            plugin_class = self.tool_registry.step_registry.get_step(tool_name)
            if not plugin_class:
                raise ValueError(f"Plugin not found: {tool_name}")
            
            # Create progress callback
            def progress_callback(update: PraxisExecutionUpdate) -> None:
                mcp_update = ExecutionUpdate(
                    step_name=update.step_name,
                    status=ExecutionStatus(update.status),
                    progress=update.progress,
                    message=update.message,
                    estimated_remaining=update.estimated_remaining
                )
                self._execution_updates[execution_id].append(mcp_update)
            
            # Execute plugin
            plugin_instance = plugin_class(
                artifact_manager=context.artifact_manager,
                config=arguments,
                provider_manager=context.provider_manager
            )
            
            # Add progress update for start
            start_update = ExecutionUpdate(
                step_name=tool_name,
                status=ExecutionStatus.RUNNING,
                progress=0.0,
                message=f"Starting execution of {tool_name}",
                estimated_remaining=0
            )
            self._execution_updates[execution_id].append(start_update)
            
            # Execute the plugin
            result = await plugin_instance.run(context)
            
            # Add completion update
            completion_update = ExecutionUpdate(
                step_name=tool_name,
                status=ExecutionStatus.COMPLETED,
                progress=1.0,
                message=f"Completed execution of {tool_name}",
                estimated_remaining=0
            )
            self._execution_updates[execution_id].append(completion_update)
            
            # Return result
            return {
                "result": result.dict() if hasattr(result, 'dict') else str(result),
                "execution_id": execution_id,
                "status": "completed",
                "tool_name": tool_name
            }
            
        except Exception as e:
            # Add error update
            error_update = ExecutionUpdate(
                step_name=tool_name,
                status=ExecutionStatus.FAILED,
                progress=0.0,
                message=f"Error executing {tool_name}: {str(e)}",
                estimated_remaining=0
            )
            self._execution_updates[execution_id].append(error_update)
            raise
    
    async def _execute_pipeline_tool(
        self, 
        execution_id: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a pipeline tool."""
        logger.info(f"Executing pipeline tool: {tool_name}")
        
        # Initialize progress tracking
        self._execution_updates[execution_id] = []
        
        try:
            # Create execution context
            context = create_execution_context(
                task_id=execution_id,
                container=self.dependency_container
            )
            
            # Add arguments to context
            for key, value in arguments.items():
                context[key] = value
            
            # Get pipeline definition (this would need to be implemented)
            # For now, simulate pipeline execution
            pipeline_id = tool_name.replace("pipeline.", "")
            
            # Create progress callback
            def progress_callback(update: PraxisExecutionUpdate) -> None:
                mcp_update = ExecutionUpdate(
                    step_name=update.step_name,
                    status=ExecutionStatus(update.status),
                    progress=update.progress,
                    message=update.message,
                    estimated_remaining=update.estimated_remaining
                )
                self._execution_updates[execution_id].append(mcp_update)
            
            # Use orchestrator to execute pipeline
            orchestrator = PipelineOrchestrator(
                container=self.dependency_container,
                progress_callback=progress_callback
            )
            
            # Execute pipeline
            await orchestrator.run_pipeline(pipeline_id, context)
            
            # Return result
            return {
                "result": "Pipeline execution completed",
                "execution_id": execution_id,
                "status": "completed",
                "tool_name": tool_name,
                "context_data": dict(context)
            }
            
        except Exception as e:
            # Add error update
            error_update = ExecutionUpdate(
                step_name=tool_name,
                status=ExecutionStatus.FAILED,
                progress=0.0,
                message=f"Error executing pipeline {tool_name}: {str(e)}",
                estimated_remaining=0
            )
            self._execution_updates[execution_id].append(error_update)
            raise
    
    async def _stream_execution_progress(self, execution_id: str) -> AsyncGenerator[str, None]:
        """Stream execution progress updates."""
        logger.info(f"Starting progress stream for execution: {execution_id}")
        
        last_sent = 0
        
        while execution_id in self._execution_updates:
            updates = self._execution_updates[execution_id]
            
            # Send any new updates
            for i in range(last_sent, len(updates)):
                update = updates[i]
                progress_update = ProgressUpdate(
                    tool_name=execution_id.split('_')[0],
                    update=update,
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                yield f"data: {progress_update.json()}\n\n"
                last_sent = i + 1
            
            # Check if execution is complete
            if updates and updates[-1].status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                break
                
            # Wait before checking for more updates
            await asyncio.sleep(0.5)
        
        logger.info(f"Completed progress stream for execution: {execution_id}")
    
    async def start_server(self) -> None:
        """Start the MCP server."""
        import uvicorn
        
        logger.info(f"Starting CETO MCP Server on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self) -> None:
        """Run the MCP server (blocking)."""
        asyncio.run(self.start_server())