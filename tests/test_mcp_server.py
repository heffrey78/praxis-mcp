"""
Tests for MCP Server functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.mcp.server import MCPServer
from src.mcp.tool_registry import MCPToolRegistry
from src.mcp.models import (
    ExecutionStatus,
    ListToolsRequest,
    CallToolRequest,
    MCPToolSpec,
    ToolType
)


class TestMCPServer:
    """Test cases for MCP Server."""

    @pytest.fixture()
    def mock_tool_registry(self) -> MCPToolRegistry:
        """Create a mock tool registry."""
        registry = MagicMock(spec=MCPToolRegistry)
        
        # Mock tool specification
        test_tool_spec = MCPToolSpec(
            name="test_tool",
            description="Test tool for unit tests",
            tool_type=ToolType.ATOMIC,
            input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            estimated_duration=10,
            supports_streaming=True,
            supports_cancellation=True
        )
        
        registry.list_tools.return_value = [test_tool_spec]
        return registry

    @pytest.fixture()
    def mock_dependency_container(self) -> MagicMock:
        """Create a mock dependency container."""
        return MagicMock()

    @pytest.fixture()
    def mcp_server(
        self, 
        mock_tool_registry: MCPToolRegistry,
        mock_dependency_container: MagicMock
    ) -> MCPServer:
        """Create MCP server instance for testing."""
        return MCPServer(
            tool_registry=mock_tool_registry,
            dependency_container=mock_dependency_container,
            host="127.0.0.1",
            port=8081
        )

    @pytest.mark.asyncio()
    async def test_list_tools_success(
        self, 
        mcp_server: MCPServer,
        mock_tool_registry: MCPToolRegistry
    ) -> None:
        """Test successful tool listing."""
        # Arrange
        request = ListToolsRequest()
        
        # Act
        response = await mcp_server._handle_list_tools(request)
        
        # Assert
        assert response.result is not None
        assert len(response.result) == 1
        assert response.result[0]["name"] == "test_tool"
        mock_tool_registry.list_tools.assert_called_once()

    @pytest.mark.asyncio()
    async def test_call_tool_not_found(self, mcp_server: MCPServer) -> None:
        """Test calling non-existent tool."""
        # Arrange
        request = CallToolRequest(
            params={
                "name": "nonexistent_tool",
                "arguments": {"input": "test"}
            }
        )
        
        # Mock tool registry to return None
        mcp_server.tool_registry.get_tool.return_value = None
        
        # Act & Assert
        with pytest.raises(Exception):  # Should raise HTTPException
            await mcp_server._handle_call_tool(request)

    @pytest.mark.asyncio()
    async def test_call_tool_unavailable(self, mcp_server: MCPServer) -> None:
        """Test calling unavailable tool."""
        # Arrange
        request = CallToolRequest(
            params={
                "name": "test_tool",
                "arguments": {"input": "test"}
            }
        )
        
        # Mock tool as unavailable
        mock_tool = MagicMock()
        mock_tool.is_available = False
        mcp_server.tool_registry.get_tool.return_value = mock_tool
        
        # Act & Assert
        with pytest.raises(Exception):  # Should raise HTTPException
            await mcp_server._handle_call_tool(request)

    @pytest.mark.asyncio()
    async def test_call_tool_missing_dependencies(self, mcp_server: MCPServer) -> None:
        """Test calling tool with missing dependencies."""
        # Arrange
        request = CallToolRequest(
            params={
                "name": "test_tool",
                "arguments": {"input": "test"}
            }
        )
        
        # Mock tool as available but with missing dependencies
        mock_tool = MagicMock()
        mock_tool.is_available = True
        mcp_server.tool_registry.get_tool.return_value = mock_tool
        mcp_server.tool_registry.validate_tool_dependencies.return_value = ["missing_dep"]
        
        # Act & Assert
        with pytest.raises(Exception):  # Should raise HTTPException
            await mcp_server._handle_call_tool(request)

    @pytest.mark.asyncio()
    @patch('src.mcp.server.create_execution_context')
    async def test_execute_atomic_tool_success(
        self,
        mock_create_context: MagicMock,
        mcp_server: MCPServer
    ) -> None:
        """Test successful atomic tool execution."""
        # Arrange
        tool_name = "test_tool"
        arguments = {"input": "test_value"}
        
        # Mock tool
        mock_tool = MagicMock()
        mock_tool.spec.tool_type.value = "atomic"
        mcp_server.tool_registry.get_tool.return_value = mock_tool
        
        # Mock execution context
        mock_context = MagicMock()
        mock_create_context.return_value = mock_context
        
        # Mock plugin class and instance
        mock_plugin_class = MagicMock()
        mock_plugin_instance = AsyncMock()
        mock_plugin_instance.run.return_value = MagicMock(dict=lambda: {"result": "success"})
        mock_plugin_class.return_value = mock_plugin_instance
        
        mcp_server.tool_registry.step_registry.get_step.return_value = mock_plugin_class
        
        # Act
        result = await mcp_server._execute_atomic_tool("exec_1", tool_name, arguments)
        
        # Assert
        assert result["status"] == "completed"
        assert result["tool_name"] == tool_name
        assert "result" in result
        mock_plugin_instance.run.assert_called_once_with(mock_context)

    def test_server_initialization(self) -> None:
        """Test MCP server initialization."""
        # Act
        server = MCPServer()
        
        # Assert
        assert server.host == "127.0.0.1"
        assert server.port == 8081
        assert server.app is not None
        assert server.tool_registry is not None
        assert server.dependency_container is not None

    def test_server_routes_setup(self, mcp_server: MCPServer) -> None:
        """Test that FastAPI routes are properly set up."""
        # Get route paths
        route_paths = [route.path for route in mcp_server.app.routes]
        
        # Assert expected routes exist
        assert "/mcp" in route_paths
        assert "/mcp/tools" in route_paths
        assert "/health" in route_paths