"""
PipelineTool - The core innovation enabling recursive composition.

A pipeline that IS an MCP tool, allowing infinite workflow composition.
"""

from typing import Any, Dict, Type, Optional
from pydantic import BaseModel, Field

from ..core.pipeline_definition import PipelineDefinition, WorkflowDefinition
from ..core.execution_context import ExecutionContext


class PipelineTool(BaseModel):
    """
    A pipeline that functions as an MCP tool.
    
    This is the key innovation that enables recursive composition:
    - Pipelines can be used as tools in other pipelines
    - Infinite nesting of workflows
    - Seamless integration with Claude Code through MCP protocol
    """
    
    # Tool identity (following MCP tool conventions)
    tool_id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool purpose and capabilities")
    version: str = Field(default="1.0.0", description="Tool version")
    
    # Pipeline definition
    pipeline: PipelineDefinition = Field(..., description="Underlying pipeline definition")
    
    # Tool interface (auto-derived from pipeline)
    input_schema: Type[BaseModel] = Field(..., description="Input schema for the pipeline")
    output_schema: Type[BaseModel] = Field(..., description="Output schema from the pipeline")
    
    # Execution metadata
    estimated_duration: int = Field(default=0, description="Estimated execution time in seconds")
    supports_streaming: bool = Field(default=True, description="Supports real-time progress updates")
    supports_cancellation: bool = Field(default=True, description="Can be cancelled mid-execution")
    
    # Dependencies and requirements
    required_tools: list[str] = Field(default_factory=list, description="Tools this pipeline depends on")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, pipeline_definition: PipelineDefinition, **data):
        """Initialize pipeline tool from pipeline definition"""
        
        # Generate tool ID from pipeline
        tool_id = f"pipeline.{pipeline_definition.workflow_id}"
        
        # Derive input/output schemas from pipeline steps
        input_schema = self._derive_input_schema(pipeline_definition)
        output_schema = self._derive_output_schema(pipeline_definition)
        
        # Calculate estimated duration
        estimated_duration = self._calculate_duration(pipeline_definition)
        
        # Extract dependencies
        required_tools = self._extract_dependencies(pipeline_definition)
        
        super().__init__(
            tool_id=tool_id,
            name=pipeline_definition.name,
            description=pipeline_definition.description,
            pipeline=pipeline_definition,
            input_schema=input_schema,
            output_schema=output_schema,
            estimated_duration=estimated_duration,
            required_tools=required_tools,
            **data
        )
    
    def _derive_input_schema(self, pipeline: PipelineDefinition) -> Type[BaseModel]:
        """
        Derive input schema from pipeline parameters and first step requirements.
        
        This creates a Pydantic model that represents all inputs needed
        to execute the entire pipeline.
        """
        
        # Start with pipeline parameters
        fields = {}
        
        # Add pipeline-level parameters
        for param in pipeline.params:
            field_type = str  # Default to string, could be enhanced with type mapping
            if param.type == "integer":
                field_type = int
            elif param.type == "boolean":
                field_type = bool
            
            fields[param.name] = (
                field_type if param.required else Optional[field_type],
                Field(description=param.description)
            )
        
        # Add first step inputs (if no dependencies)
        first_steps = [step for step in pipeline.steps if not step.depends_on]
        for step in first_steps:
            # In real implementation, would analyze step's tool requirements
            # For now, add common fields
            if step.plugin == "file_reader":
                fields["file_path"] = (str, Field(description="Path to file to read"))
            elif step.plugin == "code_analyzer":
                fields["analysis_type"] = (str, Field(default="basic", description="Type of analysis"))
        
        # Create dynamic Pydantic model
        return type(
            f"{pipeline.workflow_id}Input",
            (BaseModel,),
            {
                "__annotations__": fields,
                "__module__": __name__
            }
        )
    
    def _derive_output_schema(self, pipeline: PipelineDefinition) -> Type[BaseModel]:
        """
        Derive output schema from pipeline's final steps.
        
        This creates a Pydantic model representing all outputs
        produced by the pipeline.
        """
        
        fields = {}
        
        # Find terminal steps (steps that no other step depends on)
        all_dependencies = set()
        for step in pipeline.steps:
            all_dependencies.update(step.depends_on)
        
        terminal_steps = [
            step for step in pipeline.steps 
            if step.name not in all_dependencies
        ]
        
        # Add outputs from terminal steps
        for step in terminal_steps:
            if step.plugin == "report_generator":
                fields["report_content"] = (str, Field(description="Generated report content"))
                fields["report_path"] = (str, Field(description="Path to generated report"))
            elif step.plugin == "code_analyzer":
                fields["analysis_results"] = (Dict[str, Any], Field(description="Analysis results"))
                fields["score"] = (float, Field(description="Overall quality score"))
        
        # Always include execution metadata
        fields["execution_time"] = (float, Field(description="Total execution time in seconds"))
        fields["steps_completed"] = (int, Field(description="Number of steps completed"))
        fields["artifacts_created"] = (list[str], Field(description="List of created artifacts"))
        
        return type(
            f"{pipeline.workflow_id}Output",
            (BaseModel,),
            {
                "__annotations__": fields,
                "__module__": __name__
            }
        )
    
    def _calculate_duration(self, pipeline: PipelineDefinition) -> int:
        """Calculate estimated execution duration for the pipeline"""
        
        # Basic estimation: sum of step durations with parallelism considerations
        total_duration = 0
        
        # Group steps by their dependency levels
        dependency_levels = self._calculate_dependency_levels(pipeline)
        
        # For each level, take the maximum duration (parallel execution)
        for level_steps in dependency_levels.values():
            level_max_duration = 0
            for step_name in level_steps:
                # Estimate duration based on tool type
                step = next(s for s in pipeline.steps if s.name == step_name)
                step_duration = self._estimate_step_duration(step)
                level_max_duration = max(level_max_duration, step_duration)
            
            total_duration += level_max_duration
        
        return total_duration
    
    def _calculate_dependency_levels(self, pipeline: PipelineDefinition) -> Dict[int, list[str]]:
        """Calculate dependency levels for parallel execution planning"""
        
        levels = {}
        step_levels = {}
        
        def calculate_level(step_name: str) -> int:
            if step_name in step_levels:
                return step_levels[step_name]
            
            step = next(s for s in pipeline.steps if s.name == step_name)
            if not step.depends_on:
                level = 0
            else:
                level = max(calculate_level(dep) for dep in step.depends_on) + 1
            
            step_levels[step_name] = level
            
            if level not in levels:
                levels[level] = []
            levels[level].append(step_name)
            
            return level
        
        # Calculate levels for all steps
        for step in pipeline.steps:
            calculate_level(step.name)
        
        return levels
    
    def _estimate_step_duration(self, step) -> int:
        """Estimate duration for a single step based on tool type"""
        
        # Tool-specific duration estimates (in seconds)
        duration_map = {
            "file_reader": 5,
            "code_analyzer": 30,
            "test_runner": 120,
            "report_generator": 15,
            "git_committer": 10,
            "security_scanner": 60,
            "dependency_checker": 20,
        }
        
        # Check if it's a nested pipeline
        if step.plugin.startswith("pipeline."):
            return 300  # Assume 5 minutes for nested pipelines
        
        return duration_map.get(step.plugin, 30)  # Default 30 seconds
    
    def _extract_dependencies(self, pipeline: PipelineDefinition) -> list[str]:
        """Extract all tool dependencies from the pipeline"""
        
        dependencies = set()
        
        for step in pipeline.steps:
            if not step.plugin.startswith("pipeline."):
                # It's an atomic tool
                dependencies.add(step.plugin)
            else:
                # It's a nested pipeline - would need to recursively resolve
                dependencies.add(step.plugin)
        
        return list(dependencies)
    
    async def execute(self, inputs: BaseModel, context: ExecutionContext) -> BaseModel:
        """
        Execute the pipeline as a tool.
        
        This is where the magic happens - the pipeline executes exactly
        like any other MCP tool, but internally runs a complex workflow.
        """
        
        # Import here to avoid circular imports
        from .workflow_orchestrator import WorkflowOrchestrator
        
        orchestrator = WorkflowOrchestrator()
        
        # Convert inputs to context variables
        input_data = inputs.dict()
        for key, value in input_data.items():
            context[key] = value
        
        # Execute the underlying pipeline
        await orchestrator.execute_workflow(self.pipeline, context)
        
        # Extract outputs and create response
        output_data = self._extract_outputs(context)
        
        # Create and return output model instance
        return self.output_schema(**output_data)
    
    def _extract_outputs(self, context: ExecutionContext) -> Dict[str, Any]:
        """Extract outputs from execution context"""
        
        # This would be enhanced to properly extract outputs
        # based on the output schema definition
        
        return {
            "execution_time": getattr(context, "execution_time", 0.0),
            "steps_completed": len(getattr(context, "completed_steps", [])),
            "artifacts_created": list(getattr(context, "artifacts", {}).keys()),
            # Additional outputs would be extracted based on schema
        }
    
    def to_mcp_tool_spec(self) -> Dict[str, Any]:
        """Convert to MCP tool specification format"""
        
        return {
            "name": self.tool_id,
            "description": self.description,
            "inputSchema": self.input_schema.schema(),
            "outputSchema": self.output_schema.schema(),
            
            # Enhanced metadata for Claude Code
            "metadata": {
                "tool_type": "pipeline",
                "estimated_duration": self.estimated_duration,
                "supports_streaming": self.supports_streaming,
                "supports_cancellation": self.supports_cancellation,
                "required_tools": self.required_tools,
                "step_count": len(self.pipeline.steps),
                "complexity": self._calculate_complexity()
            }
        }
    
    def _calculate_complexity(self) -> str:
        """Calculate pipeline complexity for user information"""
        
        step_count = len(self.pipeline.steps)
        has_loops = any(hasattr(step, 'loop_config') and step.loop_config for step in self.pipeline.steps)
        has_nested_pipelines = any(step.plugin.startswith("pipeline.") for step in self.pipeline.steps)
        
        if has_nested_pipelines or has_loops:
            return "high"
        elif step_count > 5:
            return "medium"
        else:
            return "low"


# Example usage and factory functions

def create_pipeline_tool(pipeline_definition: PipelineDefinition) -> PipelineTool:
    """Factory function to create a pipeline tool from a definition"""
    return PipelineTool(pipeline_definition)


def register_pipeline_as_tool(registry, pipeline_definition: PipelineDefinition) -> PipelineTool:
    """Helper to register a pipeline as a tool in the registry"""
    pipeline_tool = create_pipeline_tool(pipeline_definition)
    registry.register_tool(pipeline_tool)
    return pipeline_tool