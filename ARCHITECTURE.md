# System Architecture

## Overview

The Claude Code Evolution project transforms Claude Code into an intelligent development orchestrator through a recursive tool composition system built on proven Praxis patterns.

## Core Design Principles

1. **Recursive Composition** - Pipelines are tools that can be composed infinitely
2. **Transparent Integration** - Works through existing MCP protocol without Claude Code changes
3. **Context-Aware Execution** - Hierarchical context management with proper inheritance
4. **Persistent State** - Workspaces and artifacts survive across sessions

## Component Architecture

### 1. CETO (Claude Enhanced Task Orchestrator)

The core execution engine inspired by Praxis DAGExecutor:

```
┌─────────────────────────────────────┐
│              CETO Core              │
├─────────────────────────────────────┤
│ • DAG Execution Engine              │
│ • Dependency Resolution             │
│ • Parallel Execution Groups        │
│ • Checkpoint/Resume Support        │
│ • Error Handling & Recovery        │
└─────────────────────────────────────┘
```

**Key Files:**
- `src/core/dag_executor.py` - Core DAG execution logic
- `src/core/orchestrator.py` - Pipeline orchestration
- `src/ceto/enhanced_orchestrator.py` - Claude Code specific enhancements

### 2. Recursive Tool Composition

Tools exist in a hierarchy that enables infinite composition:

```
Atomic Tools (Leaf Nodes)
├── file_reader
├── code_analyzer
├── test_runner
└── git_committer

Pipeline Tools (Composite)
├── code_review_pipeline
│   ├── file_reader
│   ├── code_analyzer
│   └── report_generator
└── ci_pipeline
    ├── test_runner
    ├── code_review_pipeline  ← Pipeline used as tool!
    └── git_committer

Mega-Workflows (Pipeline of Pipelines)
└── feature_development_workflow
    ├── analysis_pipeline
    ├── implementation_pipeline
    ├── ci_pipeline
    └── deployment_pipeline
```

**Implementation:**
```python
class PipelineTool(MCPToolV2):
    """A pipeline that IS an MCP tool"""
    
    def __init__(self, pipeline_definition: WorkflowDefinition):
        super().__init__(
            tool_id=f"pipeline.{pipeline_definition.workflow_id}",
            input_schema=self._derive_input_schema(pipeline_definition),
            output_schema=self._derive_output_schema(pipeline_definition)
        )
```

### 3. MCP Integration Layer

Seamless integration with Claude Code through the MCP protocol:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Claude Code   │    │   MCP Server    │    │ CETO Engine     │
│                 │    │                 │    │                 │
│ list_tools() ───┼────┼─→ Enhanced     │    │                 │
│                 │    │   Tool Registry │    │                 │
│ call_tool() ────┼────┼─→ Pipeline      ┼────┼─→ Workflow      │
│                 │    │   Orchestrator  │    │   Execution     │
│ ← results ──────┼────┼─← Progress      │    │                 │
│                 │    │   Streaming     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Key Features:**
- **Tool Discovery**: Claude Code sees atomic tools AND pipeline tools
- **Transparent Execution**: Pipelines execute like any other tool
- **Progress Streaming**: Real-time updates during workflow execution
- **Error Handling**: Graceful failure with detailed diagnostics

### 4. Context Management System

Hierarchical context inspired by Praxis ExecutionContext:

```
Session Context
├── Project Context (cross-session state)
│   ├── Conversation Context (chat session)
│   │   ├── Task Context (current workflow)
│   │   │   ├── Tool Context (tool execution)
│   │   │   └── Loop Context (iteration state)
│   │   └── Task Context (parallel workflow)
│   └── Conversation Context (new chat)
└── Workspace Context (persistent artifacts)
```

**Implementation:**
```python
class ReasoningContext:
    def spawn_reasoning_phase(self, phase_name: str) -> 'ReasoningContext':
        """Create child context with controlled inheritance"""
        
    def merge_child_results(self, child_context: 'ReasoningContext') -> None:
        """Merge results back to parent context"""
```

### 5. Persistent Workspace

Enterprise-grade workspace management:

```
Workspace Components:
├── Artifact Manager (command pattern storage)
├── Version Control (git-like versioning)
├── Search Engine (semantic + temporal search)
├── Collaboration (real-time sharing)
└── Learning System (pattern recognition)
```

## Data Flow

### 1. Tool Discovery Flow
```
User Request → Claude Code → MCP list_tools() → Tool Registry
                                ↓
Enhanced Tool Specs ← Tool Composition Analysis ← Pipeline Registry
```

### 2. Execution Flow
```
Claude Code → MCP call_tool() → Pipeline Orchestrator → CETO Engine
                    ↓                      ↓               ↓
Progress Updates ← Progress Streaming ← DAG Execution ← Tool Execution
```

### 3. Context Flow
```
User Session → Reasoning Context → Task Context → Tool Context
      ↓              ↓                 ↓             ↓
Workspace ← Artifact Storage ← State Updates ← Tool Outputs
```

## Integration Strategies

### 1. Transparent Integration
- Claude Code automatically discovers and uses workflow tools
- User gets sophisticated workflows through natural conversation
- No change to user experience, massive increase in capability

### 2. Explicit Workflow Management
- `/workflow` commands for detailed control
- Progress visualization and customization
- Pause/resume capability for long-running workflows

### 3. Proactive Learning
- Pattern recognition in user behavior
- Automatic workflow suggestions
- Custom workflow generation from repeated actions

## Scalability & Performance

### Parallel Execution
- **Step-level parallelism** within workflows
- **Workflow-level parallelism** for independent pipelines
- **Resource management** with configurable limits

### Memory Management
- **Context isolation** prevents memory leaks
- **Artifact streaming** for large outputs
- **Garbage collection** of completed contexts

### Fault Tolerance
- **Checkpoint/resume** for long-running workflows
- **Graceful degradation** on tool failures
- **Retry mechanisms** with exponential backoff

## Security Considerations

### Isolation
- **Sandbox execution** for untrusted tools
- **Resource limits** per tool/workflow
- **Network isolation** where appropriate

### Access Control
- **Workspace permissions** for collaboration
- **Tool access controls** based on user roles
- **Audit trails** for all executions

## Extension Points

### Custom Tools
- **Plugin interface** for new tool types
- **Dynamic loading** of external tools
- **Marketplace integration** for community tools

### Workflow Templates
- **Template engine** for parameterized workflows
- **Inheritance hierarchy** for workflow composition
- **Version management** for workflow evolution

### Integration Hooks
- **Webhook support** for external triggers
- **Event system** for workflow orchestration
- **API endpoints** for programmatic access

## Monitoring & Observability

### Metrics
- **Execution time** per tool/workflow
- **Success rates** and failure patterns
- **Resource utilization** tracking

### Logging
- **Structured logging** with correlation IDs
- **Performance profiling** for optimization
- **Error aggregation** for debugging

### Analytics
- **Usage patterns** for optimization
- **Performance trends** over time
- **User behavior** for feature development

---

This architecture enables Claude Code to evolve from a conversational assistant into a comprehensive development orchestrator while maintaining the simplicity and intuitiveness that users love.