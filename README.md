# CETO: Claude Enhanced Task Orchestrator

> **Transforming Praxis into an MCP-based platform that enables Claude Code to become an intelligent development orchestrator through recursive tool composition.**

[![GitHub Issues](https://img.shields.io/github/issues/heffrey78/praxis-mcp)](https://github.com/heffrey78/praxis-mcp/issues)
[![GitHub Stars](https://img.shields.io/github/stars/heffrey78/praxis-mcp)](https://github.com/heffrey78/praxis-mcp/stargazers)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🚀 Vision

Enable **infinite workflow complexity through simple conversation**. Users can say:
- *"Set up a React project with testing and CI/CD"* 
- *"Perform a comprehensive code review"*
- *"Deploy this feature with full testing pipeline"*

...and Claude Code automatically discovers and executes enterprise-grade workflows as if they were simple tools.

## 🏗️ Architecture

### Recursive Tool Composition
```
Atomic Tools → Pipeline Tools → Mega-Workflows
    ↓              ↓               ↓
file_reader → code_review → feature_development
git_tools   → ci_pipeline → deployment_workflow
```

### Core Innovation: **Pipelines ARE Tools**
Any pipeline can become an MCP tool usable in larger workflows, enabling unlimited composition depth.

## 🎯 Current Status

**🚧 Phase 1: Foundation** - Core MCP integration and tool registry

### Implementation Tasks (GitHub Issues)
- **[#1 Core MCP Server Integration](https://github.com/heffrey78/praxis-mcp/issues/1)** (P0) - Foundation MCP server with tool discovery
- **[#2 Enhanced Tool Registry](https://github.com/heffrey78/praxis-mcp/issues/2)** (P0) - Registry for atomic and pipeline tools  
- **[#3 PipelineTool MCP Interface](https://github.com/heffrey78/praxis-mcp/issues/3)** (P0) - Make pipelines discoverable as tools
- **[#4 Real-time Progress Streaming](https://github.com/heffrey78/praxis-mcp/issues/4)** (P1) - Live workflow progress updates
- **[#5 Example Workflows](https://github.com/heffrey78/praxis-mcp/issues/5)** (P1) - Demonstration workflows

## 🔧 Quick Start

### Prerequisites
- Python 3.11+
- PDM (Python Dependency Manager)
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/heffrey78/praxis-mcp.git
cd praxis-mcp

# Install dependencies
pdm install

# Run development server
pdm run dev

# Start MCP server (when implemented)
pdm run mcp-dev
```

### Development Commands
```bash
# Run tests
pdm run pytest -vv

# Code quality checks
pdm run ruff check src tests
pdm run mypy src
pdm run pyright

# Format code
pdm run ruff format src tests
```

## 📚 Documentation

- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and component relationships
- **[CLAUDE.md](CLAUDE.md)** - Claude Code integration guidelines  
- **[Coding Standards](docs/70-development/CODING_STANDARDS.md)** - Development guidelines
- **[Hierarchical Breakdown](docs/10-architecture/hierarchical-breakdown.md)** - Detailed system architecture

### Project Management
This project uses **lifecycle-mcp** for requirements, architecture decisions, and task management:
- **Requirements**: Comprehensive requirement gathering and analysis
- **Architecture Decisions**: ADRs with full context and consequences
- **Task Breakdown**: Implementation tasks linked to requirements
- **GitHub Integration**: Issues exported with full traceability

## 🎮 Examples

### Basic Workflow (Conceptual)
```python
# Define a code review workflow
workflow = WorkflowDefinition(
    workflow_id="code_review",
    steps=[
        WorkflowStep("analyze", "code_analyzer"),
        WorkflowStep("report", "report_generator", depends_on=["analyze"])
    ]
)

# Pipeline becomes an MCP tool automatically
pipeline_tool = PipelineTool(workflow)
# Now usable in larger workflows!
```

### MCP Integration (Target API)
```python
# Claude Code discovers this as a tool
mcp_server.register_tool(pipeline_tool)

# User conversation: "Review my code"
# → Claude Code finds and executes the workflow
# → Real-time progress updates
# → Complete code review delivered
```

## 🔗 Integration

### Claude Code Integration
The system integrates at **three levels**:
1. **Transparent** - Automatic workflow discovery and execution
2. **Explicit** - `/workflow` commands for detailed control  
3. **Proactive** - Pattern recognition and workflow suggestions

### MCP Protocol
- **Tool Discovery**: `list_tools()` returns atomic tools AND pipeline workflows
- **Execution**: `call_tool()` executes complex workflows like simple tools
- **Streaming**: Real-time progress updates during execution
- **Error Handling**: Graceful degradation with meaningful messages

## 🎯 Key Innovation

**Recursive Composition**: The breakthrough enabling infinite complexity:
```
Tool Registry
├── Atomic Tools (file_reader, git_commit, test_runner)
├── Pipeline Tools (code_review, react_setup)  
└── Mega-Workflows (full_development_cycle)
    └── Uses pipeline tools as components!
```

## 🚦 Development Status

- ✅ **Architecture Defined** - CETO system design complete
- ✅ **Requirements Documented** - Comprehensive requirement analysis  
- ✅ **Tasks Created** - 5 implementation tasks ready
- 🚧 **Implementation** - Core MCP integration in progress
- ⏳ **Testing** - Integration tests planned
- ⏳ **Examples** - Demo workflows in development

## 🤝 Contributing

1. **Check Issues** - See [GitHub Issues](https://github.com/heffrey78/praxis-mcp/issues) for current tasks
2. **Follow Standards** - Read [CODING_STANDARDS.md](docs/70-development/CODING_STANDARDS.md)
3. **Use PDM** - Always prefix Python commands with `pdm run`
4. **Test Everything** - Follow AAA testing patterns
5. **Document Changes** - Update relevant documentation

### Development Workflow
```bash
# Create feature branch
git checkout -b feature/mcp-server-integration

# Make changes following coding standards
pdm run ruff check src tests --fix
pdm run pytest -vv

# Commit and push
git commit -m "feat: implement core MCP server integration"
git push origin feature/mcp-server-integration
```

## 📈 Roadmap

- **Phase 1** (Current): Core MCP integration and tool registry
- **Phase 2**: Advanced workflow features and error handling  
- **Phase 3**: Enterprise features and performance optimization
- **Phase 4**: Ecosystem expansion and marketplace integration

## 🏆 Goals

Transform Claude Code from a **conversational coding assistant** into an **intelligent development orchestrator** that can:
- Execute enterprise-grade workflows through simple conversation
- Compose unlimited complexity through recursive tool patterns
- Provide real-time progress and intelligent error handling
- Maintain the intuitive conversational interface users love

---

**Built on proven patterns from the Praxis pipeline system** | **Powered by MCP protocol integration** | **Designed for infinite scalability**