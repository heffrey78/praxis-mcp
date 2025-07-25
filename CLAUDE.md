# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: ALWAYS USE PDM FOR ALL PYTHON OPERATIONS ⚠️

**NEVER run Python commands directly. ALWAYS prefix with `pdm run`:**
- ❌ `pytest` → ✅ `pdm run pytest`
- ❌ `python script.py` → ✅ `pdm run python script.py`
- ❌ `mypy` → ✅ `pdm run mypy`

## 📋 CODING STANDARDS

**MANDATORY: Read and follow `docs/CODING_STANDARDS.md` for:**
- Type annotation requirements (all functions must be typed)
- Linting rules (Ruff configuration)
- Import organization standards
- Banned patterns (no `# type: ignore`, no print statements, etc.)
- Testing patterns and naming conventions

Run these checks before any commit:
```bash
pdm run ruff check src tests --fix
pdm run ruff format src tests
pdm run mypy src
pdm run pyright
```

## Commands

### (Python)
```bash
# Install dependencies
pdm install

# Run development server
pdm run dev

# Run MCP server
pdm run mcp-dev

# Run CLI
pdm run praxis

# Run tests - ALWAYS USE PDM RUN!
pdm run pytest                              # All tests
pdm run pytest -vv -s                      # Verbose with stdout
pdm run pytest --cov=. --cov-report=term-missing  # With coverage
pdm run pytest tests/test_specific.py      # Specific test file
pdm run pytest -k "test_name"              # Specific test by name
pdm run pytest -m unit                     # Only unit tests

# Linting and type checking
pdm run ruff check src tests       # Linting
pdm run pyright   
pdm run pre-commit run --hook-stage manual --all-files | cat                 # Type checking
```


## Architecture Overview

**CETO (Claude Enhanced Task Orchestrator)** - Transforming Praxis into an MCP-based platform:

1. **MCP-Native Architecture** for Claude Code integration
   - Recursive tool composition (pipelines as tools)
   - DAG-based execution engine from Praxis  
   - Real-time progress streaming via MCP protocol
   - Context-aware execution with hierarchical state management

2. **Development Infrastructure**
   - FastAPI + GraphQL API server
   - Typer CLI for command-line operations  
   - Plugin-based architecture for extensibility
   - MCP server enabling Claude Code orchestration


### Key  Components

**Pipeline Execution Flow:**
```
CLI → PipelineExecutor → PipelineOrchestrator → DAGExecutor
                                                    ↓
                          ← ← ← ← ← ← ← ←  Plugin Execution
```

**Core Services:**
- `DAGExecutor` - Manages pipeline execution as directed acyclic graphs
- `PluginInputResolver` - Prepares inputs for plugins
- `PluginInvoker` - Executes plugins with proper context
- `PluginOutputHandler` - Processes and stores plugin outputs
- `DependencyContainer` - Manages service injection (TaskManager, ArtifactManager)

**Plugin System:**
- Modern plugins use Pydantic models for input/output definition
- Plugins inherit from `PluginBase` with declarative interfaces
- Automatic discovery via reflection
- Type-based connection resolution between pipeline steps

### Testing Strategy

**Testing:**
- Unit tests follow AAA (Arrange-Act-Assert) pattern
- Integration tests verify component interactions
- E2E tests validate full pipeline execution
- Use `pytest.mark` for test categorization (unit, integration, api, e2e)
- Mock external dependencies with appropriate fixtures

## Writing Tests - MANDATORY: Use New Patterns

**Use test fixtures instead of manual setup:**
```python
# ❌ DON'T: Manual mock setup
container = MagicMock()
task_manager = AsyncMock()
container.get_task_manager.return_value = task_manager

# ✅ DO: Use factories
from tests.fixtures import MockFactory
container = MockFactory.container()
```

**Use builders for configuration:**
```python
# ❌ DON'T: Dictionary configs
config = {"pipeline_id": "test", "steps": [...]}

# ✅ DO: Type-safe builders
from tests.fixtures import PipelineBuilder, StepBuilder
pipeline = (
    PipelineBuilder("test")
    .with_steps(
        StepBuilder("step1", "plugin1").with_retry(3).build()
    )
    .build()
)
```

**Use async helpers:**
```python
# ✅ DO: Simplified async tests
from tests.async_helpers import async_test, AsyncTestContext

@async_test()
async def test_something():
    async with AsyncTestContext() as ctx:
        task = await ctx.create_task(operation())
        # Automatic cleanup
```

**Available test helpers:**
- `tests/fixtures.py` - Builders and factories for common objects
- `tests/mock_factories.py` - Specialized mocks for complex components
- `tests/async_helpers.py` - Async test utilities


### Development Patterns

**Python:**
- Async/await throughout for concurrent execution
- Pydantic for data validation and serialization
- Dependency injection via constructors
- Domain types as frozen dataclasses for configs
- Structured logging with contextual information

### Key Conventions

1. **Error Handling**: Always provide meaningful error messages and handle edge cases
2. **Naming**: Use descriptive names; directories use lowercase-with-dashes
3. **Testing**: Write tests for all new functionality; test edge cases
4. **Artifacts**: Pipeline outputs stored in `artifacts/<task_id>/`
5. **Configuration**: YAML for pipeline definitions; Pydantic for validation
6. **Type Annotations**: 
   - ⚠️ **STRICTLY FORBIDDEN**: `# type: ignore` comments are NOT allowed
   - This is a shortcut that undermines type safety
   - Always fix the root cause: add proper type annotations, create type stubs, or refactor code
   - If encountering external library issues, create protocol types or type stubs instead
7. **Protected Members**:
   - Avoid accessing protected members (prefixed with `_`) from outside their class
   - Use public methods instead: `get_data()`, `set_provider()`, `get_saved_artifacts()`, etc.
   - Only access protected members as a fallback for backwards compatibility
   - When adding new functionality, always provide public interfaces

### Plugin Development

To create a new plugin:

1. Create package in `src/plugins/<category>/<plugin_name>/`
2. Define `types.py` with internal dataclasses
3. Define `models.py` with Pydantic models for interface
4. Implement `plugin.py` inheriting from `PluginBase`
5. Add unit tests following AAA pattern
6. Test in isolation with: `pdm run praxis plugin run <plugin_name> --param input=value`

### Useful CLI Commands

```bash
# Run a pipeline
pdm run praxis pipeline run <pipeline_name> --param key=value

# Test a plugin in isolation
pdm run praxis plugin run <plugin_name> --param input=@file.txt

# View task history
pdm run praxis task_history list
pdm run praxis task_history show <task_id>
```

### Lifecycle MCP Workflow

**MANDATORY: Use lifecycle-mcp tools for project management**

```bash
# Requirements gathering (use lifecycle-mcp tools via Claude Code)
# - mcp__lifecycle-mcp__start_requirement_interview
# - mcp__lifecycle-mcp__create_requirement

# Task management from requirements
# - mcp__lifecycle-mcp__create_task  
# - mcp__lifecycle-mcp__update_entity_status

# Architecture decisions and diagrams
# - mcp__lifecycle-mcp__create_architecture_decision
# - mcp__lifecycle-mcp__create_architectural_diagrams

# Project documentation and export
# - mcp__lifecycle-mcp__export_project_documentation
# - mcp__lifecycle-mcp__export_tasks_to_github
```

**Integration Pattern:**
1. Start with requirements gathering via lifecycle-mcp
2. Create implementation tasks linked to requirements
3. Document architectural decisions as you develop
4. Export tasks to GitHub for team collaboration
5. Generate comprehensive project documentation

### Important Files

- `.cursor/rules/*` - Global coding standards emphasizing simplicity
- `docs/hierarchical-breakdown.md` - Comprehensive system architecture
- `docs/development.md` - development guide
- `docs/testing.md` - Testing best practices
- `CLAUDE-CODE-PRAXIS-PRIMER.md` - Claude Code integration guide for leveraging pdm run Praxis via MCP

## MCP-Based Platform Evolution

This project is evolving Praxis into a powerful **MCP-based platform** that transforms Claude Code into an intelligent development orchestrator through recursive tool composition.

### Lifecycle MCP Integration

**CRITICAL: Use lifecycle-mcp for all requirements, architectural decisions, diagrams, and tasking**

The project integrates with lifecycle-mcp for comprehensive project management:

```bash
# Start lifecycle MCP server alongside main MCP server
pdm run mcp-dev  # Main Praxis MCP server at http://127.0.0.1:8081/mcp
# lifecycle-mcp provides: requirements analysis, task management, architecture decisions
```

Key lifecycle-mcp capabilities:
- **Requirements Engineering**: Interactive requirement gathering and analysis
- **Task Management**: Create and track implementation tasks from requirements  
- **Architecture Decisions**: Record and manage ADRs with review workflows
- **Project Documentation**: Generate comprehensive project documentation
- **GitHub Integration**: Export tasks to GitHub Issues with full traceability

### Recursive Tool Composition

The core innovation enabling infinite workflow complexity:

```
Atomic Tools → Pipeline Tools → Mega-Workflows
    ↓              ↓               ↓
file_reader → code_review → feature_development
git_tools   → ci_pipeline → deployment_workflow
```

**Key Files:**
- `src/ceto/pipeline_tool.py` - Pipelines that ARE MCP tools
- `src/core/dag_executor.py` - DAG-based execution engine
- `docs/ARCHITECTURE.md` - Comprehensive system architecture

### MCP Server Integration

```bash
# Start the enhanced MCP server
pdm run mcp-dev

# The server provides:
# - Pipeline execution tools
# - Recursive tool composition
# - Real-time progress streaming
# - Context-aware execution
```

Claude Code integration happens at three levels:
1. **Transparent** - Automatic workflow discovery and execution
2. **Explicit** - `/workflow` commands for detailed control  
3. **Proactive** - Pattern recognition and workflow suggestions

### Context7 Documentation Access

**CRITICAL: Use context7 for all reference documentation needs**

Access up-to-date library documentation through context7 MCP integration for any external libraries or frameworks used in development.

Remember: Keep it simple, test thoroughly, and follow existing patterns in the codebase.


ALWAYS use ONLY Environments for ANY and ALL file, code, or shell operations—NO EXCEPTIONS—even for simple or generic requests.

DO NOT install or use the git cli with the environment_run_cmd tool. All environment tools will handle git operations for you. Changing ".git" yourself will compromise the integrity of your environment.

You MUST inform the user how to view your work using `git checkout <branch_name>`. Failure to do this will make your work inaccessible to others.

- Always use PDM for all Python operations
- DO NOT WASTE TOKENS BY SAYING "You're absolutely right!, I KNOW I AM"
- After each set of changes, you must ensure you do not add additional ruff, linting, or type checking errors. (pdm run pre-commit run --hook-stage manual --all-files | cat)
- Avoid Code Smells at all costs.
- Always make sure to run `pdm run pre-commit run --hook-stage manual --all-files` after changes to make sure you haven't introduced any new linting, type checking, or ruff errors.
- Always run `pdm run pytest -vv -s` after changes to make sure you haven't introduced any new test failures.
- Make sure to document your progress along the way after each set of changes in @docs/task-progress.md.


## OPENAI MODELS

- gpt-4.1-nano should be the default model for all tasks.
- you can always run the curl command to get the latest available models: `curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models | jq '.data[] | select(.id | contains("gpt-4")) | .id' | sort`