# A. 50,000-Foot View

1. **What Is It?**  
   - We have a system that takes in videos and other content (like text from websites) and does helpful steps to transform them. For example, it can write down what people say in videos or make short summaries of long content.

2. **Why Is It Cool?**  
   - It can do many different tasks, and sometimes it does them all at once, like a team of helpers working together on different parts of the same job.

3. **The Big Idea**  
   - Think about a big lemonade stand: one person squeezes lemons, another adds sugar, another stirs, and so on. Each person must wait for their turn or for the right ingredients. That's like our pipeline of steps!

4. **How It Works**  
   - We wrote instructions in files so these steps can happen in the right order. Some steps can work at the same time if they don't need to wait for each other.

---

## B. 10,000-Foot View

1. **Basic Terms**  
   - **Pipeline**: A list of steps for processing content (like videos). We define them in YAML files that specify what goes first and what depends on what.
   - **Plugins**: Think of them like mini-apps that do a single job, web scrape, summarize text, etc.

2. **Parallel Steps**  
   - If two steps don't need each other's output, they can run at the same time.  

3. **Core Files**  
   - `src/pipelines/*.yaml` hold the instructions (like a recipe) for each pipeline.  
   - `src/plugins/*` has Python modules that does each task.  

4. **Dependency Container**  
   - We have a *container* that keeps track of important services like the task manager and artifact manager, so the code can get them whenever needed. (File reference: `src/core/dependency_container.py`)

5. **How It Runs**  
   - When you run `praxis pipeline run youtube_basic`, the system reads that pipeline file, checks which steps are needed, determines the order, then runs them in the most efficient way.

---

## C. 1000-Foot View

1. **Architecture**  
   - The system's core execution is orchestrated by the **`DAGExecutor`** (`src/core/dag_executor.py`). It works in conjunction with several specialized components:
        *   **`DAGValidator`** (`src/core/dag_validator.py`): Parses step dependencies, validates the pipeline structure, and detects cycles.
        *   **`DAGState`** (`src/core/dag_state.py`): Manages the real-time execution state of the pipeline (e.g., pending, running, completed, failed steps).
        *   **`PluginInputResolver`** (`src/core/plugin_input_resolver.py`): Prepares the necessary input data for each plugin, resolving connections and context fallbacks.
        *   **`PluginInvoker`** (`src/core/plugin_invoker.py`): Executes the actual `run` method of a plugin instance with the prepared inputs.
        *   **`PluginOutputHandler`** (`src/core/plugin_output_handler.py`): Processes the output from a plugin and merges it back into the pipeline context.
        *   **`LoopExecutionStrategy`** (`src/core/loop_execution_strategy.py`): Manages the execution of loop constructs (collection, count, condition-based) within the pipeline.
    The `DAGExecutor` itself focuses on scheduling steps in topological order based on information from these components.
   - Each *plugin* extends a base class `PluginBase` (in `src/plugins/plugin_base.py`) and implements a `run(context)` method.  

2. **Workflow**  
   - **CLI** (`src/cli/main.py`) → **Pipeline Commands** (`src/cli/pipeline.py`) → **PipelineExecutor** → **PipelineOrchestrator** (`src/core/orchestrator.py`) → **DAGExecutor** → runs each step's plugin.  
   - **Context** (`src/core/context.py`) is shared so steps can pass data between plugins.

3. **Key Modules**  
   - **`dag_executor.py`**: Orchestrates pipeline execution by coordinating `DAGValidator`, `DAGState`, `LoopExecutionStrategy`, `PluginInputResolver`, `PluginInvoker`, and `PluginOutputHandler`. Manages concurrency (via an `asyncio` Semaphore and task scheduling), and progress callbacks.
   - **`dag_validator.py`**: Responsible for validating pipeline structure, checking dependencies, and detecting cycles.
   - **`dag_state.py`**: Tracks the detailed state of each step and the overall pipeline execution.
   - **`loop_execution_strategy.py`**: Encapsulates the logic for executing different types of loops within a pipeline.
   - **`plugin_input_resolver.py`**: Focuses on preparing the input data required by each plugin, resolving any defined connections.
   - **`plugin_invoker.py`**: Handles the direct invocation of a plugin's `run` method, managing modern vs. legacy plugin signatures.
   - **`plugin_output_handler.py`**: Processes plugin results and updates the shared pipeline context.
   - **`artifact_manager.py`**: Saves files (like transcripts or downloaded videos) in a structured folder.  
   - **`task_manager.py`**: Creates unique task IDs, so each pipeline run is separate.
   - **`service_registry.py`**: Manages AI service providers (OpenAI, Azure, etc.).

4. **Parallelism**  
   - The DAG executor uses `asyncio` to run independent steps simultaneously, respecting dependencies with a semaphore to control concurrency.  

5. **Error Handling**  
   - Steps can be critical or non-critical. If a critical step fails, the pipeline aborts. If non-critical, it logs an error and continues.

6. **CLI Structure**
   - The CLI is built with **Typer** and has several command groups:
     - `pipeline`: Manage and run content processing pipelines
     - `plugin`: Manage and execute individual plugins
     - `task_history`: Manage task history

7. **Pipeline Execution**
   - `PipelineExecutor` in `src/cli/pipeline.py` provides a synchronous wrapper around asynchronous pipeline execution, bridging the CLI (synchronous) with pipeline execution (asynchronous).

---

## D. 100-Foot View

1. **Design Patterns**  
   - **Dependency Injection** via the `DependencyContainer` fosters modular design.  
   - **Factory / Plugin Registry** pattern: each plugin is discovered or registered in `step_registry.py`.
   - **Command Pattern**: Each plugin is effectively a "command" that gets executed by the orchestrator.

2. **Configuration-as-Code**  
   - YAML files let non-devs define pipelines. Each step includes `plugin`, `depends_on` (with optional inline conditions), `loop_config` for iterations, and optionally `config` for configuration.
   - Supports enhanced control flow with inline conditions (`when: "condition"`), native loops (for-each, count, while), and parallel execution.
   - Decouples business logic from the orchestrator.

3. **Progress Reporting & Hooks**  
   - The `DAGExecutor` uses **progress callbacks** to notify about step states (`pending`, `running`, `completed`, `failed`). This is crucial for CLI updates (`print_step_progress` in `src/cli/pipeline.py`).  

4. **Artifact Management Strategy**  
   - Each pipeline run (task) has a unique directory: `artifacts/<task_id>/`.  
   - **File**: `artifact_manager.py` is responsible for reading/writing artifacts with thread safety.

5. **Enhanced Control Flow**
   - **Inline Conditions**: Dependencies can include `when` clauses for conditional execution (e.g., `depends_on: [{step: "validate", when: "is_valid == true"}]`)
   - **ConditionParser** (`src/core/condition_parser.py`): Safely evaluates condition expressions
   - **Native Loops**: Support for for-each, count-based, and while loops via `LoopConfig`
   - **PipelineBuilder** (`src/core/pipeline_builder.py`): Fluent API for programmatic pipeline construction

6. **Pipeline Generation**
   - The `PipelineBuilder` in `src/core/pipeline_builder.py` can programmatically construct pipelines with enhanced control flow features.
   - Supports method chaining for intuitive pipeline construction with branches, loops, and parallel execution.
   - Can export to YAML format for configuration-as-code approach.

7. **Provider Management**
   - The `ServiceRegistry` manages AI service providers, allowing the system to switch between providers (e.g., OpenAI, Azure) without code changes.
   - Providers can be configured via YAML and selected at runtime.

8. **Task History**
   - The system keeps track of all pipeline runs, their parameters, and results.
   - The `task_history` command group provides ways to view, export, and manage this history.

9. **Automated Testing**  
   - Under `tests/`, we have unit tests (e.g., `test_artifact_manager.py`, `test_cli.py`) and integration tests (e.g., `test_full_pipeline.py`). This ensures each plugin and the entire pipeline can be tested in isolation.

10. **Trade-offs**  
   - Using a custom DAG executor vs. adopting a library like Airflow. The custom approach is simpler for a smaller codebase, but might have fewer advanced scheduling features.  
   - Concurrency approach is `asyncio`-based, which is efficient for IO-bound tasks (like calling external APIs, file downloads).

---

## E. Ground-Level Explanation

1. **Detailed Concurrency Model**  
   - The **`DAGExecutor`**'s concurrency is built around Python's `asyncio`. A **Semaphore** limits concurrent tasks to avoid resource exhaustion. The `DAGExecutor` creates and manages `asyncio.Task`s for step execution, awaiting them with `asyncio.wait(...)`. Loop execution, managed by `LoopExecutionStrategy`, may also involve creating nested `DAGExecutor` instances, which similarly manage their own tasks.
   - The `PipelineExecutor` in `pipeline.py` bridges synchronous CLI calls with asynchronous execution by using a ThreadPoolExecutor and event loop management.

2. **Formal DAG Representation**  
   - `StepConfig` objects (in `src/core/step_config.py`) define step dependencies. Dependencies can include `ConditionalDependency` objects with `when` clauses for conditional execution.
   - The **`DAGValidator`** component is responsible for parsing these dependencies (including conditional ones using `ConditionParser`), building an internal graph representation, and checking for cycles using DFS to ensure the pipeline is a valid DAG.
   - Loop constructs, defined by `LoopConfig`, are managed by the **`LoopExecutionStrategy`**. This component handles the iteration logic (collection, count, or condition-based), prepares the context for each iteration, and orchestrates the execution of the loop body, typically by invoking a nested `DAGExecutor` for the body steps.

3. **Plugin System Architecture**  
   - Each plugin is effectively a "**command**" in the Command Pattern, but also part of a **parallel** or **map-reduce** flow if steps are repeated.
   - Reflection-based plugin discovery in `plugin_discovery.py` enables adding new plugins without modifying central registry code.
   - Plugins declare input and output types, enabling automatic pipeline generation through type matching.

4. **AI Provider Abstraction**  
   - The `ServiceRegistry` and the provider system enable a plugin-specific abstraction for AI services.
   - Providers can be configured with different models, API keys, and endpoints, supporting a range of AI services.
   - The `context.set_provider()` method allows plugins to use the configured provider without direct dependency.

5. **Error Handling and Resilience**  
   - The DAG executor handles failures with configurable retry logic and supports non-critical steps.
   - Fine-grained error reporting is captured in task history and step progress.
   - Graceful shutdown is implemented through signal handlers to ensure clean termination.

6. **Potential Scalability**  
   - If we want to scale to distributed systems, we'd adapt the `dag_executor` to schedule tasks on remote workers. This would likely involve a message queue and worker processes.
   - The current design is modular enough to allow hooking in a queue-based approach without major refactoring.

7. **Observability and Metrics**  
   - The system logs step times in `_report_progress(...)`. Future expansions might store metrics in a database or push them to a real-time UI.  
   - Task history provides a foundation for pipeline execution analytics and performance tracking.
   - The "parallel groups" concept in DAG executor enables tracking related steps that can run concurrently.

8. **Advanced Plugin Patterns**
   - Plugins can implement advanced patterns like:
     - **Composite pattern**: A plugin that orchestrates multiple sub-plugins
     - **Template method pattern**: Base plugin classes that implement common behavior with hooks for specialization
     - **Chain of responsibility**: Plugins that can delegate to other plugins based on content type
   - These patterns enable building more complex processing with reusable components.

---

## Adding a New Plugin (Modern Guide)

The modern approach to creating plugins uses a declarative style with Pydantic models for input/output definitions and validation. Here's how to create a new plugin following the current pattern:

1. **Create a plugin package** in the appropriate directory:
   ```bash
   mkdir -p src/plugins/transform/my_translator/
   ```

2. **Create a `types.py` file** to define internal dataclasses:
   ```python
   from dataclasses import dataclass
   from typing import Optional, List, Dict, Any
   from pathlib import Path

   @dataclass
   class TranslateConfig:
       """Configuration for translation processing."""
       content: str
       target_language: str
       source_language: Optional[str] = None
       preserve_formatting: bool = True
       max_length: Optional[int] = None
       output_dir: Optional[Path] = None
   
   @dataclass
   class TranslateResult:
       """Results of translation processing."""
       translated_text: str
       source_language: str
       target_language: str
       translation_path: Path
       metadata: Dict[str, Any]
   ```

3. **Create a `models.py` file** with Pydantic models that define the plugin interface:
   ```python
   from pydantic import BaseModel, Field
   from typing import Optional, List, Dict, Any
   
   class TranslatorInput(BaseModel):
       """Input interface for translator plugin.
       
       This defines what the plugin requires to operate.
       """
       content: str = Field(..., description="Text to translate")
       source_language: Optional[str] = Field(None, description="Source language code (auto-detect if None)")
       
       # Define input types - these are used for pipeline connections
       class Config:
           input_types = ["transcript", "article_text", "content", "summary"]
           input_descriptions = {
               "transcript": "Transcript of audio or video content",
               "article_text": "Text from an article or webpage",
               "content": "Generic content that can be translated",
               "summary": "Summary text to translate"
           }
   
   class TranslatorConfig(BaseModel):
       """Configuration for translator plugin.
       
       This defines how the plugin should operate.
       """
       target_language: str = Field("es", description="Target language code (e.g., 'es' for Spanish)")
       preserve_formatting: bool = Field(True, description="Whether to preserve formatting")
       max_length: Optional[int] = Field(None, description="Maximum length of translated text")
   
   class TranslatorOutput(BaseModel):
       """Output interface for translator plugin.
       
       This defines what the plugin produces.
       """
       translated_text: str = Field(..., description="Translated text")
       source_language: str = Field(..., description="Detected or specified source language")
       target_language: str = Field(..., description="Target language")
       metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the translation")
       
       # Define output types - these are used for pipeline connections
       class Config:
           output_types = ["translated_text"]
           output_descriptions = {
               "translated_text": "Text translated to the target language"
           }
   ```

4. **Create a `plugin.py` file** that implements the plugin logic:
   ```python
   from typing import Dict, Any, Optional
   import json
   import logging
   import asyncio
   from pathlib import Path

   from src.plugins.plugin_base import PluginBase
   from src.core.context import PipelineContext
   from src.core.artifact_manager import ArtifactManager
   
   from .models import TranslatorInput, TranslatorOutput, TranslatorConfig
   from .types import TranslateConfig, TranslateResult

   logger = logging.getLogger(__name__)

   class TranslatorPlugin(PluginBase):
       """Plugin for translating text to different languages."""
       
       # Use declarative models to define the plugin interface
       input = TranslatorInput
       output = TranslatorOutput
       config = TranslatorConfig
       
       # Plugin metadata
       NAME = "content_translator"
       VERSION = "0.1.0"
       DESCRIPTION = "Translates text from one language to another"
       
       def __init__(
           self,
           artifact_manager: Optional[ArtifactManager] = None,
           config: Optional[Dict[str, Any]] = None,
           provider_manager: Optional[Any] = None
       ) -> None:
           super().__init__(artifact_manager, config, provider_manager)
           
       async def run(self, context: PipelineContext) -> TranslatorOutput:
           """Run the translation plugin."""
           logger.info("Running translator plugin")
           
           # Validate that required inputs are in the context
           self.validate_requirements(context)
           
           # Get content from context based on available keys from input model
           content = self._get_content(context)
           if not content:
               raise ValueError("No content found in context to translate")
               
           # Get configuration with defaults from plugin config
           target_language = getattr(self.cfg, "target_language", "es")
           preserve_formatting = getattr(self.cfg, "preserve_formatting", True)
           max_length = getattr(self.cfg, "max_length", None)
           
           # Create configuration object
           config = TranslateConfig(
               content=content,
               target_language=target_language,
               preserve_formatting=preserve_formatting,
               max_length=max_length,
               output_dir=context.artifacts_dir
           )
           
           try:
               logger.info(f"Translating text to {config.target_language}")
               
               # Get AI provider from context
               provider = context.get_provider()
               
               # Perform translation (possibly in a background thread)
               result = await self._translate_content(config, provider)
               
               # Create output model
               output = TranslatorOutput(
                   translated_text=result.translated_text,
                   source_language=result.source_language,
                   target_language=result.target_language,
                   metadata=result.metadata
               )
               
               # Update context
               context["translated_text"] = result.translated_text
               context["translation_source_lang"] = result.source_language
               context["translation_target_lang"] = result.target_language
                   
               # Save as artifact
               await context.save_artifact(
                   f"translation_{config.target_language}.txt", 
                   result.translated_text
               )
               
               # Save metadata
               await context.save_artifact(
                   f"translation_metadata.json",
                   json.dumps(result.metadata, indent=2)
               )
                   
               logger.info(f"Translation completed: {result.translation_path}")
               return output
               
           except Exception as e:
               logger.error(f"Failed to translate content: {str(e)}")
               raise
       
       def _get_content(self, context: PipelineContext) -> Optional[str]:
           """Get content from context based on input types."""
           input_types = self.input.Config.input_types
           for key in input_types:
               if key in context and context[key]:
                   return context[key]
           return None
           
       async def _translate_content(self, config: TranslateConfig, provider: Any) -> TranslateResult:
           """Translate content using the provider."""
           try:
               # This might be a long-running operation, consider using asyncio.to_thread
               # if the translation is CPU-intensive or blocking
               logger.info(f"Translating content to {config.target_language}")
               
               # Call the provider to translate
               translation = await provider.translate(
                   config.content,
                   target_language=config.target_language,
                   source_language=config.source_language
               )
               
               # Extract results from provider response
               translated_text = translation.get("translated_text", "")
               source_language = translation.get("detected_language", config.source_language or "unknown")
               
               # Create metadata
               metadata = {
                   "source_language": source_language,
                   "target_language": config.target_language,
                   "provider": provider.__class__.__name__,
                   "preserve_formatting": config.preserve_formatting,
                   "original_length": len(config.content),
                   "translated_length": len(translated_text)
               }
               
               # Create output path
               output_dir = config.output_dir or Path(".")
               translation_path = output_dir / f"translation_{config.target_language}.txt"
               
               return TranslateResult(
                   translated_text=translated_text,
                   source_language=source_language,
                   target_language=config.target_language,
                   translation_path=translation_path,
                   metadata=metadata
               )
               
           except Exception as e:
               logger.error(f"Translation error: {str(e)}")
               raise
   ```

5. **Create an `__init__.py` file** to expose the plugin:
   ```python
   """Translator plugin for converting text between languages."""
   
   from .plugin import TranslatorPlugin

   __all__ = ["TranslatorPlugin"]
   ```

6. **Use the plugin in a pipeline**:
   ```yaml
   steps:
     - name: translate_to_spanish
       plugin: content_translator
       depends_on: [transcribe]
       config:
         target_language: "es"
         preserve_formatting: true
   ```

### Key Improvements in the Modern Plugin System

1. **Declarative Models**:
   - Plugins define their interfaces using class attributes: `input`, `output`, and `config`
   - Interface is now fully type-checked and validated

2. **Type System in Models**:
   - Input types and output types are defined in the model's `Config` class
   - This provides better code organization and allows IDE tools to properly show type information
   - Types include descriptions for better documentation

3. **Validation and Type Checking**:
   - Pydantic models automatically validate data at runtime
   - Field definitions include types, default values, and descriptions
   - Plugin framework can use these models to validate pipeline connections

4. **Consistent Plugin Initialization**:
   - Standard constructor signature across all plugins
   - Support for artifact manager, configuration, and provider manager
   - Configuration is accessible via `self.cfg` property

5. **Structured Error Handling**:
   - Clear validation of requirements using models
   - Detailed error messages with proper context
   - Consistent logging patterns across all plugins

6. **Methods with Type Annotations**:
   - Return type annotations provide better documentation and type checking
   - Parameter types clarify expectations
   - Internal methods have clear signatures

7. **Modern Python Features**:
   - Full use of type hints
   - Async/await for concurrency
   - Dataclasses for data structures
   - Pydantic for validation

8. **Separation of Concerns**:
   - Models (`models.py`) define the plugin interface and validation
   - Types (`types.py`) define internal data structures
   - Plugin implementation is focused on business logic

## Error Handling & Debugging in Depth

1. **Critical Steps**: Failing means the pipeline halts. E.g., "download" might be critical—no point continuing if you can't get the video.  
2. **Non-Critical Steps**: Might fail or produce partial results but not block others. E.g., "qa" step might fail, but "summarize" can still proceed.  
3. **Logs**: By default, each step logs start/end. `_report_progress` in `dag_executor.py` captures these states.  
4. **Finding Issues**: 
   - Check the console output for errors
   - Use `praxis task_history show <task_id>` to see detailed step execution history
   - Examine files in `artifacts/<task_id>/` for logs and partial outputs
   - Enable debug logging with `--debug` for more detailed information

---

## Extended Example: "Narrative Run-Through"

**Command**:
```bash
praxis pipeline run youtube_basic --video_url="https://youtube.com/watch?v=ABC123"
```

**What Happens**:

1. **CLI** (`src/cli/main.py`) processes the command and forwards it to the pipeline runner.
2. **PipelineExecutor** (`src/cli/pipeline.py`) loads `youtube_basic.yaml` from `src/pipelines`.
   - The YAML defines steps: "download," "extract_audio," "transcribe," "summarize," etc.  
3. **TaskManager** creates a new task ID (e.g., `5035dacd-32f4-4fbf-90d9-befaa9b6e8c4`), sets up a folder `artifacts/5035dacd-...`.  
4. **PipelineExecutor** creates a new thread to run the asynchronous pipeline execution.
5. **DAGExecutor**:  
   - Finds that "download" has no dependencies, so it runs **download** first.  
   - Once "download" is done, "extract_audio" can run.
   - After "extract_audio", "transcribe" runs.
   - Finally, steps like "summarize," "overview," "chapters," etc. run in parallel (because they all only depend on "transcribe").  
6. **Artifacts**:  
   - Each plugin writes outputs (e.g., `video.mp4`, `audio.mp3`, `transcript.txt`, `summary.txt`) into that `artifacts/<task_id>/` folder.  
7. **Completion**: The pipeline "youtube_basic" is done. The CLI shows "Pipeline completed successfully!"
8. **Task History**: The task and its results are recorded in the task history for future reference.

---

## Day One Developer Setup

**Quick Start for New Developers**:

1. **Clone the repo and install dependencies**:
   ```bash
   git clone <repo-url>
   cd praxis/backend
   pip install -e .
   ```

2. **Run your first pipeline**:
   ```bash
   # Example pipeline from src/pipelines
   praxis pipeline run youtube_basic --video_url="https://youtube.com/watch?v=EXAMPLE"
   ```

3. **Check the results**:
   ```bash
   # List all completed tasks
   praxis task_history list
   
   # Show details for a specific task
   praxis task_history show <task_id>
   ```

4. **Try plugin isolation**:
   ```bash
   # List available plugins
   praxis plugin list
   
   # Run a single plugin
   praxis plugin run content_summarize --param transcript=@input.txt
   ```


That's enough for new devs to see the code in action on their first day.

## Connection Resolution Layer

Between the Pipeline Definition and Execution layers sits the Connection Resolution layer:

1. **Pipeline Definition**: Defines steps and their dependencies
2. **Connection Resolution**: Maps outputs to inputs between steps
3. **DAG Execution**: Runs steps in dependency order

The Connection Resolution layer:
- Analyzes plugin input/output models
- Validates type compatibility
- Resolves implicit connections when possible
- Enforces explicit connections when needed
- Creates a connection map for the DAG executor

This ensures type-safe data flow between pipeline steps while minimizing configuration overhead.