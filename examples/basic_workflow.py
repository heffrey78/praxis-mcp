"""
Basic workflow example showing core concepts.

This example demonstrates:
1. Creating atomic tools
2. Composing them into a workflow  
3. Executing the workflow
4. Showing how pipelines can become tools themselves
"""

import asyncio
from typing import Any, Dict
from pydantic import BaseModel

# Import core components (these will be implemented)
from src.core.orchestrator import PipelineOrchestrator
from src.core.step_config import StepConfig
from src.core.pipeline_definition import PipelineDefinition
from src.core.execution_context import create_execution_context


class CodeAnalyzerInput(BaseModel):
    """Input for code analyzer tool"""
    file_path: str
    analysis_type: str = "basic"


class CodeAnalyzerOutput(BaseModel):
    """Output from code analyzer tool"""
    issues: list[str]
    score: float
    recommendations: list[str]


class ReportGeneratorInput(BaseModel):
    """Input for report generator tool"""
    analysis_results: Dict[str, Any]
    template: str = "standard"


class ReportGeneratorOutput(BaseModel):
    """Output from report generator"""
    report_content: str
    report_path: str


async def basic_workflow_example():
    """Demonstrate basic workflow composition and execution"""
    
    print("🚀 Basic Workflow Example")
    print("=" * 50)
    
    # Step 1: Define workflow steps
    steps = [
        StepConfig(
            name="analyze_code",
            plugin="code_analyzer",
            config={
                "file_path": "./src/main.py",
                "analysis_type": "comprehensive"
            }
        ),
        StepConfig(
            name="generate_report", 
            plugin="report_generator",
            depends_on=["analyze_code"],
            config={
                "template": "detailed"
            }
        )
    ]
    
    # Step 2: Create pipeline definition
    pipeline = PipelineDefinition(
        id="code_review_basic",
        name="Basic Code Review Pipeline",
        description="Analyze code and generate a review report",
        steps=steps
    )
    
    print(f"📋 Created pipeline: {pipeline.name}")
    print(f"   Steps: {len(pipeline.steps)}")
    print(f"   Dependencies: {[s.depends_on for s in steps if s.depends_on]}")
    
    # Step 3: Set up orchestrator and context
    # Note: In real implementation, this would come from dependency container
    orchestrator = PipelineOrchestrator(container=None)  # Simplified for example
    
    # Create execution context
    context = create_execution_context(
        task_id="example_task_001",
        container=None
    )
    
    print(f"\n⚙️  Executing workflow...")
    print(f"   Context ID: {context.task_id}")
    
    try:
        # Step 4: Execute the workflow
        await orchestrator.run_pipeline(pipeline.id, context)
        
        print(f"✅ Workflow completed successfully!")
        print(f"   Results stored in context: {list(context.keys())}")
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
    
    return context


async def pipeline_as_tool_example():
    """Demonstrate how pipelines become tools for composition"""
    
    print("\n🔧 Pipeline-as-Tool Example")
    print("=" * 50)
    
    # The basic code review pipeline from above becomes a tool
    # that can be used in larger workflows
    
    larger_workflow_steps = [
        StepConfig(
            name="quick_security_scan",
            plugin="security_scanner"
        ),
        StepConfig(
            name="comprehensive_review",
            plugin="pipeline.code_review_basic",  # Using pipeline as tool!
            depends_on=["quick_security_scan"]
        ),
        StepConfig(
            name="integration_tests",
            plugin="test_runner",
            depends_on=["comprehensive_review"],
            config={
                "test_type": "integration"
            }
        )
    ]
    
    mega_pipeline = PipelineDefinition(
        id="full_code_analysis",
        name="Complete Code Analysis Workflow",
        description="Security scan, code review, and integration testing",
        steps=larger_workflow_steps
    )
    
    print(f"📋 Created mega-workflow: {mega_pipeline.name}")
    print(f"   Uses pipeline 'code_review_basic' as a tool!")
    print(f"   Total steps: {len(mega_pipeline.steps)}")
    
    # This demonstrates the recursive composition:
    # Tools → Pipelines → Mega-workflows → Enterprise workflows
    
    print("\n🎯 Key Insight:")
    print("   The 'code_review_basic' pipeline is now a reusable tool")
    print("   that can be composed into larger workflows!")


async def main():
    """Run all examples"""
    
    # Example 1: Basic workflow
    context = await basic_workflow_example()
    
    # Example 2: Pipeline composition
    await pipeline_as_tool_example()
    
    print("\n" + "=" * 50)
    print("🎉 Examples completed!")
    print("\nNext steps:")
    print("1. Implement the actual tool classes")
    print("2. Set up MCP server integration")
    print("3. Create Claude Code interface")
    print("4. Build tool registry and discovery")


if __name__ == "__main__":
    # Note: This example shows the intended API
    # The actual implementation will be built in phases
    
    print("📚 This is a conceptual example showing the target API")
    print("🚧 Implementation coming in Phase 1 development")
    
    # Uncomment when implementation is ready:
    # asyncio.run(main())