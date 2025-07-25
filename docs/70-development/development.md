# Development Guide

This document provides guidelines and best practices for **implementing and extending** the existing codebase. It also addresses five critical questions new developers typically have when approaching a codebase:

1. **Entry Point & Control Flow**  
2. **Core Domain Models & Data Structures**  
3. **System Boundaries & Integration Points**  
4. **Critical Paths & Error Handling**  
5. **Code Organization & Architectural Patterns**  

---

## Table of Contents

1. [Overview](#overview)  
2. [Understanding the Codebase](#understanding-the-codebase)  
   - [1. Entry Point & Control Flow](#1-entry-point--control-flow)  
   - [2. Core Domain Models & Data Structures](#2-core-domain-models--data-structures)  
   - [3. System Boundaries & Integration Points](#3-system-boundaries--integration-points)  
   - [4. Critical Paths & Error Handling](#4-critical-paths--error-handling)  
   - [5. Code Organization & Architectural Patterns](#5-code-organization--architectural-patterns)  
3. [Project Structure](#project-structure)  
4. [Core Components](#core-components)  
5. [Implementation Steps](#implementation-steps)  
6. [Adding or Modifying Plugins](#adding-or-modifying-plugins)  
7. [Enhanced Control Flow](#enhanced-control-flow)  
8. [Parallel Execution & DAG Details](#parallel-execution--dag-details)  
9. [Testing Strategy](#testing-strategy)  
10. [References](#references)  
11. [Plugin Development Guidelines](#plugin-development-guidelines)

---

## Overview

The **Pipeline Architecture** uses a **DAG-based orchestrator** to run **modular processing steps** (plugins) in a **flexible, parallelizable** manner. Each plugin handles a single responsibility (e.g., web scraping, summarizing text) and declares any prerequisites. The **PipelineOrchestrator** reads a YAML or JSON pipeline definition. The **`DAGExecutor`** then, in concert with specialized components like **`DAGValidator`** (for structure validation), **`DAGState`** (for managing execution state), **`PluginInputResolver`** (for preparing plugin inputs), **`PluginInvoker`** (for calling plugin `run` methods), **`PluginOutputHandler`** (for processing plugin results), and **`LoopExecutionStrategy`** (for managing loops), schedules and runs these plugins based on their dependencies.

### Goals

- **Modularity**: Each step (plugin) is independently testable and replaceable.
- **Parallelization**: Steps that do not depend on each other can run simultaneously.
- **Configuration as Code**: Pipeline definitions are stored in human-readable files (YAML/JSON).
- **Simplicity**: Keep code readable and composable; avoid deep inheritance trees.

---

## Understanding the Codebase

This section answers five common questions new developers ask when learning a new system.

### 1. Entry Point & Control Flow

**Question**: *Where does the application start, and how does control flow among components?*

- **CLI Entry Point**: The main entry is in `src/__main__.py`. This is where `main()` is defined.
- **CLI Commands**: The user runs a command such as `praxis pipeline <name>` or `praxis list`.
- **Pipeline Execution**: Once arguments are parsed, the system:
  1. **Loads** the requested pipeline definition from the `PipelineRegistry`.
  2. **Creates** a new task (`TaskManager`), generating a unique `task_id`.
  3. **Initializes** the `PipelineContext` (which includes references to artifacts, parameters, etc.).
  4. **Calls** `PipelineOrchestrator.runPipeline()`. The orchestrator, in turn, utilizes the `DAGExecutor`. The `DAGExecutor` coordinates with `DAGValidator`, `DAGState`, `PluginInputResolver`, `PluginInvoker`, `PluginOutputHandler`, and `LoopExecutionStrategy` to **execute** each plugin step in dependency order, managing concurrency and state.

This approach ensures a **clear, consistent flow** from CLI input → pipeline definition → task creation → DAG execution → final results.

### 2. Core Domain Models & Data Structures

**Question**: *What are the fundamental entities and how are they transformed?*

1. **PipelineDefinition**  
   - Defines the pipeline (its ID, name, steps, parameters).  
   - Typically loaded from YAML or JSON.

2. **StepConfig**  
   - A single pipeline step (with `name`, `plugin`, `depends_on`, etc.).  
   - Declares which plugin it uses and what dependencies must finish first.

3. **PipelineContext**  
   - A shared dictionary-like object storing pipeline execution data (e.g., `video_path`, `transcript`, etc.).  
   - Also holds references to `task_id` and the `artifact_manager`.

4. **Task**  
   - Represents a single pipeline run, identified by a `task_id`.  
   - Lives in `TaskManager`, which tracks creation time, parameters, and status.

5. **Artifacts**  
   - Files produced or consumed by pipeline steps. Each task has its own directory for these artifacts (`artifacts/<task_id>/...`).

### 3. System Boundaries & Integration Points

**Question**: *What external systems or services does Praxis integrate with?*

- **OpenAIClient**: Some plugins (e.g., transcription, summarization) connect to LLM-based services.  
- **File System**: The `ArtifactManager` writes and reads local files for artifacts.  
- **CLI**: The only public interface for users to start tasks.  
- **Plugins**: Each plugin might integrate with other external libraries (e.g., `yt_dlp` for YouTube downloads).

These boundaries are kept **modular** so that new integrations (e.g., another AI service or a new data store) can be added in separate plugins or via an updated `openai_client.py`.

### 4. Critical Paths & Error Handling

**Question**: *Where is the main business logic, and how do we handle failures?*

- **`DAGExecutor` and its components**: The core logic of pipeline execution, including:
    - **`DAGValidator`**: Validates the pipeline structure and dependencies.
    - **`DAGState`**: Tracks the real-time status of each step (pending, running, completed, failed, skipped).
    - **`PluginInputResolver`**: Prepares the data each plugin needs to run, handling connections.
    - **`PluginInvoker`**: Executes the specific plugin's `run` method.
    - **`PluginOutputHandler`**: Takes the plugin's result and updates the pipeline context.
    - **`LoopExecutionStrategy`**: Manages the execution of any loop constructs.
    - **`DAGExecutor`**: Orchestrates these components, managing task scheduling, concurrency (with an `asyncio.Semaphore`), and retries for plugin execution.
- **`PipelineOrchestrator`**: Validates pipeline parameters at a high level, sets up the initial context, and initiates the DAG execution via the `DAGExecutor`.
- **Error Handling**:
  - Each step can specify whether it is **critical** or not (`fail_on_error`).
  - Failures in critical steps halt the pipeline; non-critical step failures are logged by the `DAGExecutor` (via `DAGState`) but do not necessarily stop the entire pipeline, allowing other independent branches to continue.
  - Retry logic for individual plugin execution is managed within the `DAGExecutor`'s `_run_with_retries()` method, which is called by the `PluginInvoker`.

### 5. Code Organization & Architectural Patterns

**Question**: *How is the code organized, and which patterns are used?*

1. **Dependency Injection** via the `DependencyContainer` ensures services like `TaskManager` or `PipelineRegistry` are accessed consistently.  
2. **Plugin System**: Steps are **pluggable** classes inheriting from `PluginBase`.  
3. **DAG Pattern**: Each pipeline is a DAG of steps, and the executor performs a topological sort.  
4. **Configuration as Code**: YAML/JSON pipeline definitions and a lightweight approach (no heavy frameworks).  
5. **Functional Elements**: Many plugins or transformations rely on pure functions to keep logic simple, testable, and side-effect free where possible.

---

## Project Structure

```
├── README.md
├── artifacts
│   └── task_history.json
├── praxis
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── artifact_manager.py
│   │   ├── container_base.py
│   │   ├── context.py
│   │   ├── dag_executor.py
│   │   ├── dag_state.py
│   │   ├── dag_validator.py
│   │   ├── dependency_container.py
│   │   ├── loop_execution_strategy.py
│   │   ├── openai_client.py
│   │   ├── orchestrator.py
│   │   ├── pipeline_definition.py
│   │   ├── plugin_discovery.py
│   │   ├── plugin_input_resolver.py
│   │   ├── plugin_invoker.py
│   │   ├── plugin_output_handler.py
│   │   ├── step_config.py
│   │   ├── step_registry.py
│   │   └── task_manager.py
│   ├── pipelines
│   ├── plugins
│   │   ├── __init__.py
│   │   ├── plugin_base.py
│   │   ├── source
│   │   └── transform
│   └── tests
├── docs
│   ├── praxis-uml-flow.mmd
│   ├── praxis-uml-flow.svg
│   ├── cli-flow-details.md
│   ├── cli-flow.mmd
│   ├── cli-flow.svg
│   ├── development.md
│   ├── pipeline_params.md
│   ├── prd.md
│   └── task.md
├── poetry.lock
└── pyproject.toml

```

- **orchestrator.py**: Main interface for pipeline runs (`runPipeline`).  
- **pipeline_definition.py**: Data structure describing the pipeline.  
- **step_config.py**: Definition of each pipeline step's properties.  
- **plugin_base.py**: Abstract class for all plugins.  
- **context.py**: Holds shared runtime state.  
- **dag_executor.py**: Orchestrates pipeline execution by coordinating helper components. Manages concurrency and high-level step transitions.
- **dag_validator.py**: Validates pipeline structure, checks dependencies, and detects cycles.
- **dag_state.py**: Tracks the real-time state of each step and the overall pipeline execution.
- **loop_execution_strategy.py**: Encapsulates the logic for executing different types of loops within a pipeline.
- **plugin_input_resolver.py**: Focuses on preparing the input data required by each plugin, resolving connections.
- **plugin_invoker.py**: Handles the direct invocation of a plugin's `run` method.
- **plugin_output_handler.py**: Processes plugin results and updates the shared pipeline context.
- **step_registry.py**: Plugin discovery and registration.
- **openai_client.py**: Communication with external AI services.
- **plugins/**: Contains actual plugin implementations (source, transform, analysis steps).

---

## Core Components

### PipelineOrchestrator
- **Method**: `runPipeline(context, pipelineDefinition)`  
- **Role**: Validates pipeline, sets up the execution environment, calls `DAGExecutor`.  
- **Why**: This is the *heart* of high-level pipeline coordination.

### PipelineDefinition
- **Role**: Container for pipeline ID, name, parameters, and steps.  
- **Why**: A single, canonical object for pipeline structure, loaded from YAML/JSON.

### StepConfig
- **Role**: Describes each step (plugin name, dependencies, etc.).  
- **Why**: Decouples plugin logic from pipeline logic.

### PluginBase
- **Role**: Common interface (`run(context)` or `run(inputs, context)`) all plugins implement.  
- **Why**: Uniform structure for each step, making them swappable.

### PipelineContext
- **Role**: Shared data container (dict-like). Can be an `EnhancedContext` during execution to manage connections.  
- **Why**: Minimizes global state. Each pipeline run is isolated by a unique context.

### Plugin Connection System

The pipeline system uses a smart connection resolution approach to determine how data flows between plugins. This is primarily managed by the `ConnectionResolver` (used by `DAGExecutor` to prepare `EnhancedContext`) and `PluginInputResolver` (used by `DAGExecutor` to prepare inputs for `PluginInvoker`).

#### Connection Resolution

When a pipeline is created and executed:

1. **Analyze Plugin Requirements**: The `PluginInputResolver` (and `PluginBase`'s Pydantic integration) helps understand plugin input needs.
2. **Resolve Connections**: `ConnectionResolver` determines how outputs from previous steps connect to inputs of subsequent steps, creating a `connection_map` for `EnhancedContext`.
3. **Validate Type Compatibility**: The system (partially `ConnectionResolver`, partially Pydantic in plugins) ensures connected fields have compatible types.

#### Connection Types

The system supports both explicit and implicit connections:

- **Explicit Connections**: Specified directly in the pipeline definition
- **Implicit Connections**: Automatically resolved based on type compatibility and field names

#### Resolution Algorithm

For each input of a step, the system:

1. Checks for explicit connections in the pipeline definition
2. If no explicit connection, searches for compatible outputs from dependency steps
3. If exactly one compatible output exists, creates an automatic connection
4. If multiple compatible outputs exist, tries to match by field name
5. If ambiguity remains, requires an explicit connection

#### Pipeline Definition Example

```yaml
steps:
  - name: web_scrape
    plugin: web_scrape
    depends_on: []
    
  - name: summarize
    plugin: content_summarize
    depends_on: [transcribe]
    connections:
      # Only needed for ambiguous cases
      inputs:
        text: ${transcribe.transcript}
```

The `connections` section is optional for unambiguous cases but required when multiple compatible outputs exist.

### DAGExecutor
- **Role**: Orchestrates the pipeline execution flow. It uses `DAGValidator` to validate the pipeline structure, `DAGState` to track step statuses, `LoopExecutionStrategy` to manage loops, `PluginInputResolver` to prepare inputs for plugins, `PluginInvoker` to execute plugins, and `PluginOutputHandler` to process plugin outputs and update the context. It manages overall concurrency and step transitions.
- **Why**: Centralizes the coordination of the execution lifecycle, delegating specific tasks to specialized components for clarity and testability.

### DAGValidator
- **Role**: Responsible for validating the pipeline structure. This includes parsing step dependencies (including conditional ones), building an internal graph representation of the pipeline, and performing cycle detection to ensure the pipeline is a valid Directed Acyclic Graph (DAG).
- **Why**: Ensures that pipelines are structurally sound before execution begins, preventing runtime errors due to invalid dependency definitions or circular logic.

### DAGState
- **Role**: Manages and tracks the real-time state of each step within the pipeline (e.g., pending, running, completed, failed, skipped). It also tracks overall pipeline execution timing and status.
- **Why**: Provides a clear and centralized way to monitor the progress of a pipeline and to determine which steps are ready to run, have failed, or have been skipped due to unmet conditions.

### LoopExecutionStrategy
- **Role**: Encapsulates the logic for executing different types of loops defined in a pipeline (collection-based, count-based, condition-based). It manages iteration-specific context setup and orchestrates the execution of the loop body, often by invoking a nested `DAGExecutor` instance for the body steps.
- **Why**: Isolates complex loop handling logic, making the main `DAGExecutor` cleaner and loop behaviors easier to manage and extend.

### PluginInputResolver
- **Role**: Prepares the input data that each plugin requires to execute. It resolves input values based on defined connections (from an `EnhancedContext`'s `connection_map`) and handles fallbacks to the general pipeline context if necessary.
- **Why**: Decouples the `DAGExecutor` and `PluginInvoker` from the details of how plugin inputs are gathered and constructed, promoting cleaner interfaces.

### PluginInvoker
- **Role**: Handles the direct invocation of a plugin's `run` method using the modern signature (e.g., `run(inputs: Model, context: Context)`), passing the appropriate arguments prepared by the `PluginInputResolver`.
- **Why**: Centralizes the logic for actually calling plugin code.

### PluginOutputHandler
- **Role**: Takes the raw output returned by a plugin's `run` method (which could be a Pydantic model, a dictionary, or other types) and processes it. This includes merging the output back into the main pipeline context (`EnhancedContext`) so that downstream steps can access it.
- **Why**: Standardizes how plugin results are integrated into the pipeline's state, ensuring consistency.

### StepRegistry
- **Role**: Maintains a map of plugin name → plugin class.  
- **Why**: Keeps plugin lookup dynamic (no giant `if/else` block).

### Plugins
- **Examples**: `WebScrapePlugin`, `ContentSummarizePlugin`, etc.  
- **Why**: Each plugin does one task well, encouraging modular design and easier testing.

---

## Implementation Steps

Below is a *recommended* approach to **incrementally** implement or extend this architecture:

1. **Configure the Registry**:  
   ```python
   registry = StepRegistry()
   registry.register_plugin("web_scrape", WebScrapePlugin)
   # ...
   ```
2. **Load a Pipeline**:  
   - Parse a YAML (or JSON) file  
   - Create a `PipelineDefinition` with `steps`  
3. **Resolve & Schedule**:  
   - The `DAGExecutor` now internally uses `DAGValidator` to parse dependencies and validate the graph structure.  
   - `PipelineOrchestrator` calls `DAGExecutor.executeDAG(...)`.
4. **Implement `executeDAG`**:  
   - `DAGExecutor` coordinates with `DAGState` to track step statuses.
   - It identifies ready steps based on completed dependencies (and conditional outcomes if applicable).
   - For each ready step, it uses `PluginInputResolver` to prepare inputs, then `PluginInvoker` to execute the plugin's `run` method.
   - `PluginOutputHandler` processes the results and updates the context.
   - `LoopExecutionStrategy` is invoked for loop steps.
   - Concurrency is managed via an `asyncio.Semaphore`.
5. **Plugin Logic**:  
   ```python
   # Modern Pydantic Plugin Example
   class MyPlugin(PluginBase):
       InputModel = MyPluginInput
       OutputModel = MyPluginOutput

       async def run(self, inputs: MyPluginInput, context: PipelineContext) -> MyPluginOutput:
           # Use inputs.my_input_field
           # ... logic ...
           return MyPluginOutput(my_output_field=result)
   ```
6. **Parallel Execution** (Managed by `DAGExecutor`):  
   - `DAGExecutor` uses `asyncio` and a `Semaphore` to run independent steps concurrently.
   - The `DAGState` component helps in identifying which steps can be scheduled.
7. **Testing**:  
   - **Unit Tests** for each plugin.  
   - **Integration Tests** for full pipeline runs.  
   - Check concurrency stability if steps run in parallel.

---

## Adding or Modifying Plugins

1. **Create a new file** in `plugins/` named after the new task.  
2. **Inherit** from `PluginBase`, define `InputModel` and `OutputModel`, implement `run(inputs, context)`.  
3. **Register** the new plugin in `step_registry.py` or let `plugin_discovery` handle it.  
4. **Add** the step to a pipeline definition.

```yaml
steps:
  - name: "extract_pdf"
    plugin: "pdf_extractor"
    depends_on: []
```

---

## Enhanced Control Flow

Praxis supports enhanced control flow features that make pipelines more dynamic and expressive. These features include inline conditional dependencies, native loop support, and a programmatic pipeline builder API.

### Key Components

1. **ConditionParser** (`src/core/condition_parser.py`)
   - Safely evaluates condition expressions
   - Supports comparison, logical, and membership operators
   - Prevents execution of arbitrary code

2. **ConditionalDependency** (`src/core/step_config.py`)
   - Represents dependencies with inline conditions
   - Evaluated at runtime by DAGState

3. **LoopConfig** (`src/core/step_config.py`)
   - Configuration for loop steps
   - Supports for-each, count-based, and conditional loops
   - Integrated with LoopExecutionStrategy

4. **PipelineBuilder** (`src/core/pipeline_builder.py`)
   - Fluent API for programmatic pipeline construction
   - Generates pipelines with enhanced control flow
   - Exports to YAML format

### Documentation

- **[Enhanced Control Flow Guide](enhanced-control-flow-guide.md)** - Comprehensive guide with examples
- **[Quick Reference](enhanced-control-flow-quick-reference.md)** - Cheat sheet for syntax and patterns

### Example: Conditional Dependencies

```yaml
steps:
  - name: validate_data
    plugin: validator
    
  - name: process_valid
    plugin: processor
    depends_on:
      - step: validate_data
        when: "validation_passed == true"
        
  - name: handle_invalid
    plugin: error_handler
    depends_on:
      - step: validate_data
        when: "validation_passed == false"
```

### Example: Loop Configuration

```yaml
- name: process_items
  plugin: pipeline_loop
  loop_config:
    collection: items
    item_name: current_item
    body:
      - name: transform
        plugin: transformer
        config:
          input: "${current_item}"
```

### Example: PipelineBuilder

```python
from src.core.pipeline_builder import PipelineBuilder

pipeline = (
    PipelineBuilder("my-pipeline")
    .with_param("threshold", "float", default=0.8)
    .step("analyze")
    .branch(
        ("score > threshold", lambda b: b.step("high_quality")),
        ("score <= threshold", lambda b: b.step("standard"))
    )
    .build()
)
```

---

## Parallel Execution & DAG Details

- **Topological Sorting and Scheduling**: The `DAGExecutor`, guided by `DAGValidator` and `DAGState`, effectively performs a topological sort to determine execution order. It identifies "ready" steps (all dependencies met, conditions satisfied) and schedules them for execution.
- **Concurrency Management**: `DAGExecutor` uses an `asyncio.Semaphore` to limit the number of concurrently running plugin tasks, preventing resource exhaustion.
- **Thread/Async Safety**: When plugins run concurrently, they should ideally operate on their own specific input data and write to distinct output keys in the context, or use appropriate synchronization if shared mutable state is unavoidable (though this is discouraged). `PluginOutputHandler` helps manage how outputs are merged back.
- **Completion and Conditionals**: Steps dependent on multiple prior steps will only become ready after all those prior steps complete successfully. For conditional dependencies, `DAGState` tracks the outcome of conditional plugins, and `DAGExecutor` uses this information to determine if subsequent dependent steps in a conditional branch should run or be skipped.

---

## Testing Strategy

### Unit Tests
- **Each Plugin**:  
  1. Supply a mocked `PipelineContext`  
  2. Call `plugin.run(context)`  
  3. Verify outputs in `context`

### Integration Tests
- **Sample Pipeline**:  
  1. YAML/JSON defining steps  
  2. `PipelineOrchestrator` + new `PipelineContext`  
  3. `runPipeline` → confirm final artifacts

### Performance / Concurrency Tests
- **Parallel Steps**:  
  1. Confirm correct step ordering  
  2. Ensure system stability with multiple concurrent tasks  
  3. Validate no race conditions in shared data

---

## References

1. **Gary Bernhardt** – [*Functional Core, Imperative Shell*](https://www.youtube.com/watch?v=m0u5EbEpSgo)  
2. **Martin Fowler** – [*Patterns of Enterprise Application Architecture*](https://martinfowler.com/books/eaa.html)  
3. **Apache Airflow** – [*Conceptual DAG Orchestration Patterns*](https://airflow.apache.org/docs/apache-airflow/stable/)  
4. **Python Packaging** – [*Entry Points and Plugin Systems*](https://packaging.python.org/en/latest/specifications/entry-points/)

---

## Plugin Development Guidelines

### Parameter vs Configuration Distinction

When developing plugins, it's crucial to understand the difference between parameters and configuration:

- **Parameters**: The actual data to be processed (text, URLs, files)
- **Configuration**: Settings that control HOW the processing happens (modes, options, limits)

See the **[Plugin Parameter vs Configuration Guide](plugin-parameter-config-guide.md)** for detailed guidelines and examples.

### Plugin Constructor Pattern

Always use a consistent constructor signature, especially for advanced plugins:

```python
class MyPlugin(PluginBase):
    def __init__(
        self,
        artifact_manager=None,
        config=None,
        specific_param: str = "default",
        mock_mode: bool = False,
        provider_manager = None
    ):
        super().__init__(artifact_manager, config, provider_manager=provider_manager)
        self.specific_param = specific_param
        self.mock_mode = mock_mode
        # Override from config if present
        if config:
            self.mock_mode = config.get("mock_mode", self.mock_mode)
            self.specific_param = config.get("specific_param", self.specific_param)
```

#### Constructor Guidelines

1. **Standard Dependencies**:  
   - Accept `openai_client`, `artifact_manager`, and `config` as the first parameters.  
   - Pass them to `super().__init__`.  
2. **Plugin-Specific Parameters**:  
   - Add them after standard dependencies, with defaults.  
   - Use Python type hints.  
3. **Configuration Priority**:  
   - Direct constructor arguments are defaults.  
   - `config` dict overrides them if present.  
4. **Type Safety**:  
   - Validate or cast as needed.  

### Functional Plugin Architecture

#### Core Principles

1. **Immutable Data Structures**  
   - Use `@dataclass(frozen=True)` for configs to avoid accidental mutation. 

   When to use dataclasses:

    You need simple data containers with minimal dependencies
    You want to keep your project lightweight
    You don't need runtime validation
    You're focused on standard Python libraries
    Performance is a critical concern (dataclasses have lower overhead)

  When to move to Pydantic:

    You need data validation at runtime
    You're working with external data (APIs, user input, etc.)
    You need automatic type coercion (like converting strings to ints)
    You're already using a framework that integrates with Pydantic (like FastAPI)
    You want JSON schema generation

2. **Pure Functions for Core Logic**  
   - Keep *business logic* in standalone functions; they accept input and return output with minimal side effects.  
3. **Explicit Context Updates**  
   - Return a dict of changes from your pure functions, then integrate them into `context`.  
4. **Error Handling & Logging**  
   - Use structured exceptions, log where appropriate, and re-raise if needed.

#### Plugin Structure Example

```python
@dataclass(frozen=True)
class PluginConfig:
    input_path: str
    output_dir: str

@dataclass
class PluginResult:
    output_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

def process_content(config: PluginConfig) -> PluginResult:
    # Pure function implementing core logic
    return PluginResult(
        output_path="/some/path",
        metadata={"info": "details"}
    )

def update_context(result: PluginResult) -> Dict[str, Any]:
    return {
        "output_path": result.output_path,
        "metadata": result.metadata
    }

class ExamplePlugin(PluginBase):
    async def run(self, context: PipelineContext) -> None:
        if "input_path" not in context:
            raise ValueError("No input path provided.")

        config = PluginConfig(
            input_path=context["input_path"],
            output_dir=context.artifacts_dir
        )

        try:
            result = process_content(config)
            context.update(update_context(result))
        except Exception as e:
            self.logger.error(f"Failed to process content: {e}")
            raise
```

### Benefits of This Approach

1. **Testability**: Pure functions are easy to test in isolation.  
2. **Maintainability**: Logic is clear and separated from side effects.  
3. **Reliability**: Immutable data structures help avoid accidental mutations.  
4. **Extensibility**: Additional plugin steps are straightforward to create by following the same pattern.

## Plugin Consistency Requirements

### 1. File Organization
```python
# Standard library imports
import os
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, Protocol

# Third-party imports
import yt_dlp

# Local imports
from src.plugins.plugin_base import PluginBase
from src.core.context import PipelineContext

# Domain types
@dataclass(frozen=True)
class MyConfig:
    ...

# Protocol definitions
class MyProtocol(Protocol):
    ...

# Pure functions
def process_content():
    ...
```

- Group imports by standard library, third-party, and local
- Add clear section comments
- Keep related code together

### 2. Domain Types
```python
@dataclass(frozen=True)
class DownloadConfig:
    url: str
    output_dir: str
    format: str = "bestvideo+bestaudio/best" # refer to https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#format-selection

@dataclass
class DownloadResult:
    video_path: str
    metadata: Dict[str, Any]
```

- Use `@dataclass(frozen=True)` for configs
- Use `@dataclass` for results
- Use consistent naming with `Config` and `Result` suffixes
- Include type hints for all fields

### 3. Protocol Definitions
```python
class VideoDownloader(Protocol):
    """Protocol defining the interface for video downloading functionality."""
    def download(self, config: DownloadConfig) -> DownloadResult:
        """Download a video according to the provided configuration."""
        ...
```

- Define protocols for core functionality
- Include descriptive docstrings
- Use clear method names

### 4. Pure Functions
```python
def process_content(config: ProcessConfig) -> ProcessResult:
    """Process content according to configuration.
    
    Pure function that handles core logic without side effects.
    """
    # Implementation
    return ProcessResult(...)

def update_context(result: ProcessResult) -> Dict[str, Any]:
    """Create context updates from process result."""
    return {
        "output_path": result.output_path,
        "metadata": result.metadata
    }
```

- Extract core logic into pure functions
- Functions take config objects, return result objects
- Include helper functions for context updates
- Use descriptive names

### 5. Plugin Class Structure
```python
@dataclass
class MyPluginConfig:
    mock_mode: bool = False
    specific_param: str = "default"

class MyPlugin(PluginBase):
    """Plugin for processing specific content.
    
    Requirements:
        - input_path: Path to input file
        
    Outputs:
        - output_path: Path to processed file
        - metadata: Dictionary of processing metadata
        
    Config Options:
        - mock_mode: If True, returns mock data (default: False)
        - specific_param: Custom parameter (default: "default")
    """
    
    requirements = ["input_path"]
    outputs = ["output_path", "metadata"]
    
    def __init__(
        self,
        openai_client=None,
        artifact_manager=None,
        config: Dict[str, Any] = None
    ):
        super().__init__(openai_client, artifact_manager, config)
        config = config or {}
        self.cfg = MyPluginConfig(
            mock_mode=config.get("mock_mode", False),
            specific_param=config.get("specific_param", "default")
        )
```

- Inherit from `PluginBase`
- Include comprehensive docstring
- Define requirements and outputs
- Follow standard constructor pattern
- Use config dataclass

### 6. Context Handling
```python
async def run(self, context: PipelineContext) -> None:
    """Run the plugin."""
    self.validate_requirements(context)
    
    try:
        config = ProcessConfig(
            input_path=context["input_path"],
            output_dir=context.artifacts_dir
        )
        
        result = process_content(config)
        
        # Update context with results
        context.update(update_context(result))
        
        # Save artifacts
        context.save_artifact(
            "metadata.json",
            json.dumps(result.metadata, indent=2)
        )
        
    except Exception as e:
        logger.error(f"Failed to process content: {str(e)}", exc_info=True)
        raise RuntimeError(f"Failed to process content: {str(e)}")
```

- Use `PipelineContext` type hint
- Use `context.artifacts_dir` for paths
- Use `context.update()` and `context.save_artifact()`
- Validate requirements
- Handle errors properly

### 7. Error Handling
```python
try:
    result = process_content(config)
except ValueError as e:
    logger.error(f"Invalid configuration: {str(e)}", exc_info=True)
    raise
except IOError as e:
    logger.error(f"Failed to read/write file: {str(e)}", exc_info=True)
    raise RuntimeError(f"IO operation failed: {str(e)}")
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    raise
```

- Use descriptive error messages
- Include `exc_info=True` in logging
- Wrap specific errors appropriately
- Log both errors and successes

### 8. Logging
```python
logger = logging.getLogger(__name__)

# In functions/methods:
logger.info(f"Starting processing of {input_path}")
logger.info(f"Successfully processed {count} items")
logger.error(f"Failed to process {input_path}: {str(e)}")
```

- Use consistent log levels
- Include relevant details
- Log start and completion
- Use f-strings

### 9. Type Hints
```python
from typing import Optional

def process_items(
    items: list[str],
    config: ProcessConfig,
    max_items: Optional[int] = None
) -> ProcessResult:
    ...
```

- Use type hints consistently
- Use `list[str]` over `List[str]`
- Include class variable hints
- Use `Optional` for optional params

### 10. Testing
```python
@pytest.mark.asyncio
async def test_my_plugin(artifact_manager):
    # Arrange
    plugin = MyPlugin(config={"mock_mode": True})
    context = PipelineContext({"input_path": "/test/path"})
    
    # Act
    await plugin.run(context)
    
    # Assert
    assert "output_path" in context
    assert os.path.exists(context["output_path"])
```

- Test pure functions separately
- Test success and error cases
- Test mock and real modes
- Verify context and artifacts

### 11. Documentation
```python
def process_content(config: ProcessConfig) -> ProcessResult:
    """Process content according to the configuration.
    
    Args:
        config: Configuration object containing:
            - input_path: Path to input file
            - max_items: Maximum items to process
    
    Returns:
        ProcessResult containing:
            - output_path: Path to processed file
            - metadata: Processing metadata
            
    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If processing fails
    
    Example:
        ```python
        config = ProcessConfig(input_path="/path/to/file")
        result = process_content(config)
        print(result.output_path)
        ```
    """
```

- Include comprehensive docstrings
- Document all options
- Explain complex logic
- Include examples

### 12. Async/Await
```python
class MyPlugin(PluginBase):
    async def run(self, context: PipelineContext) -> None:
        async with aiohttp.ClientSession() as session:
            result = await process_content(session, config)
            
@pytest.mark.asyncio
async def test_my_plugin():
    await plugin.run(context)
```

- Make `run` method async
- Use `await` properly
- Handle async contexts
- Include async in tests

These requirements ensure consistency, maintainability, and reliability across all plugins in the system. Following these patterns makes the code more predictable and easier to understand for all developers.

## Avoiding Unnecessary Abstraction

1. Don't create wrapper functions that only call a single function
   - If a function just forwards its arguments to another function, it's probably unnecessary
   - Example of what NOT to do:
     ```python
     # Bad - unnecessary wrapper
     async def save_artifacts(self, context, result):
         await context.save_artifact("data.json", json.dumps(result))
     
     # Good - direct call
     await context.save_artifact("data.json", json.dumps(result))
     ```

2. Keep abstraction meaningful
   - Only create new functions when they provide real value:
     - Reusable logic
     - Complex transformations
     - Meaningful grouping of operations
   - If a function doesn't hide complexity or enable reuse, it probably shouldn't exist

3. Prefer composition over inheritance
   - Use inheritance only when there's true "is-a" relationship
   - Favor small, focused classes over deep inheritance hierarchies

4. Follow YAGNI (You Aren't Gonna Need It)
   - Don't add abstraction layers for hypothetical future use
   - Wait until you have concrete use cases before generalizing

---

*Last Updated: 2024-01-25*  
*Author: Praxis Team*  

# Logging Configuration

Praxis uses a centralized logging configuration system. All logging is configured through `src.core.logging.setup_logging()`.

## Default Behavior
- Base logging level is INFO by default
- Debug mode can be enabled with `--debug` flag in CLI
- The 'praxis' logger follows the base logging level
- The 'asyncio' logger is always set to INFO level

## Usage in Code

```python
from src.core.logging import setup_logging

# Basic usage with default settings
setup_logging()

# Enable debug logging
setup_logging(debug=True)

# Custom log format
setup_logging(log_format='%(levelname)s: %(message)s')
```

## Getting a Logger

```python
import logging

# Get the Praxis logger
logger = logging.getLogger('praxis')

# Use the logger
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

## CLI Debug Mode
The CLI provides a `--debug` flag that enables debug logging:

```bash
praxis --debug pipeline run my_pipeline
```