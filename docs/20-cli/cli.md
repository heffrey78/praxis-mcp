# CLI Documentation

**Diagram Reference**: [`cli-flow.mmd`](./cli-flow.mmd)

> **Tip**: Use the Mermaid diagram to visualize how the CLI orchestrates pipeline execution. This document provides the **why** behind each node in the diagram.

---

## Table of Contents
1. [Overview of the CLI Flow](#overview-of-the-cli-flow)
2. [Main CLI Structure](#main-cli-structure)
3. [Core Services](#core-services)
4. [Pipeline Execution Flow](#pipeline-execution-flow)
6. [Plugin Execution](#plugin-execution)
7. [Task History Management](#task-history-management)
8. [Error Handling & Parallel Execution](#error-handling--parallel-execution)
9. [Progress Reporting](#progress-reporting)
10. [Context Management](#context-management)
11. [FAQ: Why These Patterns?](#faq-why-these-patterns)

---

## Overview of the CLI

The **CLI Flow** shows how a user command (e.g., `praxis pipeline run youtube_basic`) evolves into **actual pipeline execution**. The CLI is built with Typer, which provides a clean, modern command-line interface with rich help text and automatic argument parsing.

The architecture enables:
1. **Flexible** and **extensible** pipeline definitions
2. **Type-safe parameter handling**
3. **Parallel execution** of pipeline steps
5. **Individual plugin execution** for testing and debugging
6. **Task history management** for reviewing past runs

---

## Main CLI Structure

### 1. CLI Entry Point
- **File**: [`src/cli/main.py`](../src/cli/main.py)
- **Structure**: Typer application with subcommands
- **Purpose**: Centralizes CLI command registration and provides top-level help
- **Why**: Using Typer simplifies CLI development with automatic help generation, type validation, and command organization

### 2. Main Commands
- **pipeline**: Manage and run content processing pipelines
  - **list**: List available pipelines
  - **show**: Show details of a specific pipeline
  - **run**: Execute a pipeline with parameters
  - **history**: List recent task history
  - **export**: Export task artifacts
  
- **plugin**: Manage and execute individual plugins
  - **list**: List available plugins
  - **info**: Show plugin details
  - **run**: Execute a single plugin with parameters
  
- **task_history**: Manage task history
  - **list**: Show task execution history
  - **show**: Show details of a specific task
  - **clear**: Clear task history

### 3. Interactive Mode
- The pipeline command supports interactive mode when called without arguments
- Provides a selection menu for pipelines and parameter input
- **Why**: Enhances user experience for new users unfamiliar with all parameters

---

## Core Services

### DependencyContainer
- **File**: [`src/core/dependency_container.py`](../src/core/dependency_container.py)
- **Purpose**: Central **service locator** that provides access to:
  - Pipeline registry
  - Task manager
  - Artifact manager
  - Step registry
  - Service registry (for AI providers)
  - Orchestrator
- **Why**: Reduces code coupling and simplifies service access and testing

### ServiceRegistry
- **File**: [`src/core/providers.py`](../src/core/providers.py)
- **Purpose**: Manages AI service providers (e.g., OpenAI, Azure, etc.)
- **Why**: Enables switching between different AI service providers without code changes

### TaskManager
- **File**: [`src/core/task_manager.py`](../src/core/task_manager.py)
- **Purpose**: Creates tasks, tracks status, organizes task directories
- **Why**: Each pipeline run needs a unique task ID to record artifacts and progress

### ArtifactManager
- **File**: [`src/core/artifact_manager.py`](../src/core/artifact_manager.py)
- **Purpose**: Saves and retrieves **artifacts** (files) associated with a task
- **Why**: Standardizes artifact storage and retrieval across the application

### PipelineRegistry
- **File**: [`src/core/dependency_container.py`](../src/core/dependency_container.py)
- **Purpose**: Maintains available pipelines loaded from YAML files
- **Why**: Enables pipeline discovery and registration without code changes

---

## Pipeline Execution Flow

### 1. PipelineExecutor
- **File**: [`src/cli/pipeline.py`](../src/cli/pipeline.py)
- **Purpose**: Synchronous wrapper around asynchronous pipeline execution
- **Why**: Bridges CLI (synchronous) with pipeline execution (asynchronous)
- **Key Methods**:
  - `execute()`: Runs a pipeline with parameters in a separate thread
  - `_execute_async()`: Async implementation of pipeline execution

### 2. DAGExecutor
- **File**: [`src/core/dag_executor.py`](../src/core/dag_executor.py)
- **Purpose**: Runs steps in a **directed acyclic graph** (DAG) order
- **Why**: Enables parallel execution while respecting dependencies
- **Key Methods**:
  - `executeDAG()`: Main method to execute steps in dependency order
  - `_get_ready_steps()`: Identifies which steps can run now
  - `_run_with_retries()`: Runs a plugin with retry support
  - `_report_progress()`: Updates step progress

### 3. Parameter Handling
- **File**: [`src/cli/pipeline.py`](../src/cli/pipeline.py)
- **Function**: `parse_parameters()`, `validate_parameters()`, `collect_interactive_params()`
- **Purpose**: Parses and validates command-line parameters
- **Why**: Ensures parameters are correctly typed and all required parameters are provided

### 4. Pipeline Orchestrator
- **File**: [`src/core/orchestrator.py`](../src/core/orchestrator.py)
- **Purpose**: Coordinates overall pipeline execution
- **Why**: Separates orchestration logic from execution details

---

## Plugin Execution

### 1. PluginExecutor
- **File**: [`src/core/plugin_executor.py`](../src/core/plugin_executor.py)
- **Purpose**: Executes individual plugins with parameters
- **Why**: Enables testing and debugging plugins in isolation

### 2. StepRegistry
- **File**: [`src/core/step_registry.py`](../src/core/step_registry.py)
- **Purpose**: Maps plugin names to plugin classes
- **Why**: Enables plugin lookup by name during pipeline execution

### 3. PluginDiscovery
- **File**: [`src/core/plugin_discovery.py`](../src/core/plugin_discovery.py)
- **Purpose**: Discovers plugins in the plugins directory
- **Why**: Enables adding new plugins without code changes

---

## Task History Management

### 1. TaskManager
- **File**: [`src/core/task_manager.py`](../src/core/task_manager.py)
- **Purpose**: Manages task history and artifacts
- **Why**: Enables reviewing past runs and their results

### 2. Task Commands
- **File**: [`src/cli/task_history.py`](../src/cli/task_history.py)
- **Purpose**: CLI commands for viewing and managing task history
- **Why**: Provides user access to task history and artifacts

---

## Error Handling & Parallel Execution

### Retry Logic
- Steps can fail, but sometimes a retry is enough (e.g., transient network error)
- **Why**: Minimizes manual restarts for transient failures

### Critical vs Non-critical Steps
- Critical steps (`fail_on_error=True`) halt the pipeline if they fail
- Non-critical steps allow the pipeline to continue
- **Why**: Provides control over a pipeline's fault tolerance

### Parallel Execution
- **asyncio** runs multiple steps concurrently if their dependencies are met
- A **Semaphore** limits concurrency to prevent resource exhaustion
- **Why**: Speeds up execution for independent steps

### Loop Execution
- DAGExecutor supports loop constructs in pipelines
- **Why**: Enables iteration over collections or fixed number of repetitions

---

## Progress Reporting

### StepProgress
- **File**: [`src/core/dag_executor.py`](../src/core/dag_executor.py)
- **Purpose**: Tracks each step's status: *pending*, *running*, *completed*, *failed*
- **Why**: Enables visibility into pipeline execution progress

### print_step_progress
- **File**: [`src/cli/pipeline.py`](../src/cli/pipeline.py)
- **Purpose**: Displays live progress in the CLI
- **Why**: Provides real-time feedback to the user

### Task Status Tracking
- **File**: [`src/core/task_manager.py`](../src/core/task_manager.py)
- **Purpose**: Records step progress in task history
- **Why**: Enables reviewing execution details after completion

---

## Context Management

### PipelineContext
- **File**: [`src/core/context.py`](../src/core/context.py)
- **Purpose**: Stores task data (e.g., `task_id`, parameters, intermediate results)
- **Why**: 
  - Provides a shared state between pipeline steps
  - Enables each plugin to read prior results and produce new ones
  - Includes access to the AI provider for steps that need it

**Example**:
```python
context["url"] = "https://youtube.com/..."
# Step: web_scrape -> context["text"] = "..."
```

---

## FAQ: Why These Patterns?

1. **Why use Typer instead of argparse?**  
   - Typer provides automatic help generation, type validation, and a cleaner API while maintaining compatibility with Python's standard library.

2. **Why a DAG for pipeline steps?**  
   - A DAG ensures steps run only after their prerequisites finish. This naturally allows parallel runs for independent steps.

3. **Why use a central `DependencyContainer`?**  
   - It standardizes how services are retrieved, prevents scattered imports, and simplifies mocking in tests.

4. **Why separate TaskManager and ArtifactManager?**  
   - They solve different concerns. Task creation/tracking is separate from file IO. This separation keeps each class focused and more testable.

5. **Why define parameters in YAML instead of code?**  
   - Encourages a **configuration-as-code** approach. Non-developers can tweak parameters in YAML without modifying code.

6. **Why have a ServiceRegistry for AI providers?**  
   - It enables switching between different AI service providers without code changes, supporting multiple models and providers.

---

**Conclusion**:  
This document, paired with the **CLI Flow** [Mermaid diagram](./cli-flow.mmd), should help developers understand both the **technical** and the **conceptual** reasons behind the Praxis CLI's design. By seeing *how* components interact (diagram) and *why* each one is important (documentation), new contributors can ramp up quickly and **develop with confidence**.

> **Additional Reading**:  
> - [Architecture Guide](praxis-uml-flow.md) for overall pipeline structure  
> - [Plugin Development Guidelines](development.md) for best practices on writing and testing plugins.
