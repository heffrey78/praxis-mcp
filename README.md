# Claude Code Evolution: Praxis-Inspired Task Orchestration

Transform Claude Code from a conversational coding assistant into an **Intelligent Development Orchestrator** using proven patterns from the Praxis pipeline system.

## Vision

Create a recursive tool composition system where pipelines themselves become MCP tools, enabling infinite workflow complexity through simple conversational commands while maintaining Claude Code's intuitive interface.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run basic example
python examples/basic_workflow.py

# Start MCP server (for Claude Code integration)
python -m ceto.mcp_server
```

## Core Architecture

### CETO (Claude Enhanced Task Orchestrator)
- **DAG-based execution** inspired by Praxis
- **Recursive composition** - pipelines as tools
- **Context-aware reasoning** with hierarchical state management
- **Persistent workspaces** across sessions

### Key Components

1. **Core Engine** (`src/core/`)
   - `dag_executor.py` - DAG execution engine
   - `orchestrator.py` - Pipeline orchestration
   - `execution_context.py` - Context management
   - `artifact_manager.py` - State persistence

2. **MCP Integration** (`src/mcp_server/`)
   - Seamless Claude Code integration
   - Tool discovery and execution
   - Real-time progress reporting

3. **Tool Framework** (`src/tools/`)
   - Atomic tools (basic operations)
   - Pipeline tools (composed workflows)
   - Mega-workflows (pipelines of pipelines)

## Integration with Claude Code

The system integrates at **three levels**:

1. **Transparent** - Claude Code automatically uses workflows without user awareness
2. **Explicit** - Users can invoke `/workflow` commands for detailed control
3. **Proactive** - System suggests automation based on user patterns

## Project Structure

```
praxis-mcp/
├── src/
│   ├── core/              # Core execution engine (copied from Praxis)
│   ├── ceto/              # Enhanced orchestrator for Claude Code
│   ├── mcp_server/        # MCP protocol integration
│   ├── tools/             # Tool implementations
│   ├── workflows/         # Pre-built workflow definitions
│   └── workspace/         # Persistent workspace management
├── examples/              # Working examples and demos
├── tests/                 # Comprehensive test suite
├── docs/                  # Documentation and specifications
└── CLAUDE_CODE_EVOLUTION_PLAN.md  # Complete vision document
```

## Development

This project uses modern Python development practices:

- **Pydantic v2** for type-safe interfaces
- **Async/await** throughout for performance
- **AAA testing patterns** with comprehensive fixtures
- **Ruff/MyPy** for code quality

See `CLAUDE.md` for detailed development guidelines.

## Examples

### Basic Workflow Composition
```python
from ceto import WorkflowDefinition, WorkflowStep

# Define a code review workflow
workflow = WorkflowDefinition(
    workflow_id="code_review",
    steps=[
        WorkflowStep(step_id="analyze", tool_id="code_analyzer"),
        WorkflowStep(step_id="report", tool_id="report_generator", 
                    depends_on=["analyze"])
    ]
)
```

### Pipeline as Tool
```python
from ceto import PipelineTool, ToolRegistry

# Create pipeline tool
pipeline_tool = PipelineTool(workflow)

# Register as a tool (now usable in other pipelines!)
registry.register_tool(pipeline_tool)
```

## Roadmap

- **Phase 1** (Months 1-3): Foundation - Core engine and basic MCP integration
- **Phase 2** (Months 4-6): Intelligence - Context management and learning
- **Phase 3** (Months 7-9): Collaboration - Persistent workspaces and sharing
- **Phase 4** (Months 10-12): Ecosystem - Marketplace and enterprise features

## Contributing

1. Follow the patterns established in the Praxis codebase
2. Use the testing infrastructure in `tests/`
3. Maintain type safety with Pydantic models
4. Document all public APIs

See `docs/CONTRIBUTING.md` for detailed guidelines.

## License

[To be determined]

---

*Built on proven patterns from the Praxis pipeline system*