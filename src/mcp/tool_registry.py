"""
MCP Tool Registry for CETO.

This module provides the registry system that manages both atomic tools
and pipeline tools, with automatic discovery and type checking.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from src.ceto.pipeline_tool import PipelineTool
from src.core.pipeline_definition import PipelineDefinition
from src.core.step_registry import StepRegistry

from .models import MCPTool, MCPToolSpec, ToolType

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """
    Enhanced tool registry that manages both atomic tools and pipeline tools
    with automatic dependency resolution and type checking.
    """
    
    def __init__(self, step_registry: Optional[StepRegistry] = None) -> None:
        """Initialize the MCP tool registry."""
        self.step_registry = step_registry or StepRegistry()
        self._tools: Dict[str, MCPTool] = {}
        self._dependencies: Dict[str, Set[str]] = {}
        self._tool_categories: Dict[str, str] = {}
        
    def register_atomic_tool(
        self, 
        tool_name: str, 
        plugin_class: Any,
        category: Optional[str] = None
    ) -> MCPTool:
        """
        Register an atomic tool from a Praxis plugin.
        
        Args:
            tool_name: Unique tool identifier
            plugin_class: Praxis plugin class
            category: Optional category for organization
            
        Returns:
            Registered MCPTool instance
        """
        logger.info(f"Registering atomic tool: {tool_name}")
        
        # Generate tool specification from plugin
        spec = self._create_atomic_tool_spec(tool_name, plugin_class, category)
        
        # Create MCPTool instance
        tool = MCPTool(spec=spec)
        
        # Register in internal registry
        self._tools[tool_name] = tool
        if category:
            self._tool_categories[tool_name] = category
            
        # Extract dependencies
        self._extract_dependencies(tool_name, plugin_class)
        
        return tool
    
    def register_pipeline_tool(
        self, 
        pipeline_definition: PipelineDefinition,
        category: Optional[str] = None
    ) -> MCPTool:
        """
        Register a pipeline as a tool.
        
        Args:
            pipeline_definition: Pipeline definition to register
            category: Optional category for organization
            
        Returns:
            Registered MCPTool instance
        """
        tool_name = f"pipeline.{pipeline_definition.workflow_id}"
        logger.info(f"Registering pipeline tool: {tool_name}")
        
        # Create PipelineTool instance
        pipeline_tool = PipelineTool(pipeline_definition)
        
        # Generate tool specification
        spec = self._create_pipeline_tool_spec(pipeline_tool, category)
        
        # Create MCPTool instance
        tool = MCPTool(spec=spec)
        
        # Register in internal registry
        self._tools[tool_name] = tool
        if category:
            self._tool_categories[tool_name] = category
            
        # Extract pipeline dependencies
        self._extract_pipeline_dependencies(tool_name, pipeline_definition)
        
        return tool
    
    def list_tools(
        self, 
        category: Optional[str] = None,
        tool_type: Optional[ToolType] = None
    ) -> List[MCPToolSpec]:
        """
        List available tools with optional filtering.
        
        Args:
            category: Filter by category
            tool_type: Filter by tool type
            
        Returns:
            List of tool specifications
        """
        tools = []
        
        for tool_name, tool in self._tools.items():
            # Apply category filter
            if category and self._tool_categories.get(tool_name) != category:
                continue
                
            # Apply tool type filter
            if tool_type and tool.spec.tool_type != tool_type:
                continue
                
            # Only include available tools
            if tool.is_available:
                tools.append(tool.spec)
        
        # Sort by name for consistent ordering
        tools.sort(key=lambda t: t.name)
        
        logger.info(f"Listed {len(tools)} tools (category={category}, type={tool_type})")
        return tools
    
    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(tool_name)
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available for execution."""
        tool = self._tools.get(tool_name)
        return tool is not None and tool.is_available
    
    def get_tool_dependencies(self, tool_name: str) -> Set[str]:
        """Get dependencies for a tool."""
        return self._dependencies.get(tool_name, set())
    
    def validate_tool_dependencies(self, tool_name: str) -> List[str]:
        """
        Validate that all dependencies for a tool are available.
        
        Returns:
            List of missing dependencies
        """
        dependencies = self.get_tool_dependencies(tool_name)
        missing = []
        
        for dep in dependencies:
            if not self.is_tool_available(dep):
                missing.append(dep)
                
        return missing
    
    def get_execution_order(self, tool_names: List[str]) -> List[str]:
        """
        Get execution order for tools based on dependencies.
        
        Args:
            tool_names: Tools to order
            
        Returns:
            Ordered list of tool names
            
        Raises:
            ValueError: If circular dependencies detected
        """
        # Simple topological sort
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(tool_name: str) -> None:
            if tool_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {tool_name}")
                
            if tool_name not in visited:
                temp_visited.add(tool_name)
                
                # Visit dependencies first
                for dep in self.get_tool_dependencies(tool_name):
                    if dep in tool_names:  # Only consider dependencies in our set
                        visit(dep)
                        
                temp_visited.remove(tool_name)
                visited.add(tool_name)
                result.append(tool_name)
        
        for tool_name in tool_names:
            visit(tool_name)
            
        return result
    
    def _create_atomic_tool_spec(
        self, 
        tool_name: str, 
        plugin_class: Any,
        category: Optional[str]
    ) -> MCPToolSpec:
        """Create MCP tool specification from atomic plugin."""
        
        # Extract information from plugin class
        description = getattr(plugin_class, 'DESCRIPTION', f"Atomic tool: {tool_name}")
        version = getattr(plugin_class, 'VERSION', '1.0.0')
        
        # Generate input/output schemas from plugin models
        input_schema = self._generate_input_schema(plugin_class)
        output_schema = self._generate_output_schema(plugin_class)
        
        # Estimate duration (can be enhanced with historical data)
        estimated_duration = getattr(plugin_class, 'ESTIMATED_DURATION', 30)
        
        return MCPToolSpec(
            name=tool_name,
            description=description,
            tool_type=ToolType.ATOMIC,
            input_schema=input_schema,
            output_schema=output_schema,
            estimated_duration=estimated_duration,
            supports_streaming=True,  # All tools support streaming in CETO
            supports_cancellation=True,
            complexity="low",  # Atomic tools are typically low complexity
            category=category,
            version=version
        )
    
    def _create_pipeline_tool_spec(
        self, 
        pipeline_tool: PipelineTool,
        category: Optional[str]
    ) -> MCPToolSpec:
        """Create MCP tool specification from pipeline tool."""
        
        return MCPToolSpec(
            name=pipeline_tool.tool_id,
            description=pipeline_tool.description,
            tool_type=ToolType.PIPELINE,
            input_schema=pipeline_tool.input_schema.schema() if hasattr(pipeline_tool.input_schema, 'schema') else {},
            output_schema=pipeline_tool.output_schema.schema() if hasattr(pipeline_tool.output_schema, 'schema') else {},
            estimated_duration=pipeline_tool.estimated_duration,
            supports_streaming=pipeline_tool.supports_streaming,
            supports_cancellation=pipeline_tool.supports_cancellation,
            required_tools=pipeline_tool.required_tools,
            complexity=pipeline_tool._calculate_complexity(),
            category=category,
            version=pipeline_tool.version
        )
    
    def _generate_input_schema(self, plugin_class: Any) -> Dict[str, Any]:
        """Generate JSON schema for plugin input."""
        # Look for Pydantic input model
        if hasattr(plugin_class, 'input') and hasattr(plugin_class.input, 'schema'):
            return plugin_class.input.schema()
            
        # Fallback to basic schema
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Input for the tool"
                }
            },
            "required": ["input"]
        }
    
    def _generate_output_schema(self, plugin_class: Any) -> Dict[str, Any]:
        """Generate JSON schema for plugin output."""
        # Look for Pydantic output model
        if hasattr(plugin_class, 'output') and hasattr(plugin_class.output, 'schema'):
            return plugin_class.output.schema()
            
        # Fallback to basic schema
        return {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Result from the tool"
                },
                "status": {
                    "type": "string",
                    "description": "Execution status"
                }
            },
            "required": ["result", "status"]
        }
    
    def _extract_dependencies(self, tool_name: str, plugin_class: Any) -> None:
        """Extract dependencies from plugin class."""
        dependencies = set()
        
        # Look for explicit dependencies
        if hasattr(plugin_class, 'DEPENDENCIES'):
            dependencies.update(plugin_class.DEPENDENCIES)
            
        # Look for required tools in plugin metadata
        if hasattr(plugin_class, 'REQUIRED_TOOLS'):
            dependencies.update(plugin_class.REQUIRED_TOOLS)
            
        self._dependencies[tool_name] = dependencies
    
    def _extract_pipeline_dependencies(
        self, 
        tool_name: str, 
        pipeline_definition: PipelineDefinition
    ) -> None:
        """Extract dependencies from pipeline definition."""
        dependencies = set()
        
        # Extract tool dependencies from pipeline steps
        for step in pipeline_definition.steps:
            if step.plugin.startswith("pipeline."):
                # It's a nested pipeline
                dependencies.add(step.plugin)
            else:
                # It's an atomic tool
                dependencies.add(step.plugin)
                
        self._dependencies[tool_name] = dependencies