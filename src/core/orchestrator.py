import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set

import yaml

from src.core.checkpoint_manager import CheckpointManager
from src.core.context import PipelineContext
from src.core.dag_executor import (
    DAGExecutionError,
    DAGExecutor,
    StepProgress,
    StepStatus,
)
from src.core.execution_context import create_execution_context
from src.core.pipeline_definition import ParamDefinition, PipelineDefinition, StepConfig
from src.models.checkpoint import PipelineCheckpoint
from src.plugins.plugin_base import PluginBase

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer


class PipelineOrchestrator:
    """Orchestrates the execution of pipelines."""

    def __init__(
        self, container: "DependencyContainer", max_workers: Optional[int] = None
    ) -> None:
        """Initialize the orchestrator with a dependency container."""
        self._container = container
        # Create checkpoint manager for suspend/resume support
        self._checkpoint_manager = CheckpointManager(container.get_artifact_manager())
        self._dag_executor = DAGExecutor(
            container, max_workers, checkpoint_manager=self._checkpoint_manager
        )
        self._progress_callback: Optional[Callable[[str, StepProgress], None]] = None
        self._current_pipeline_id: Optional[str] = None
        self.pipeline_definitions: Dict[str, Any] = {}
        self._step_registry = container.get_step_registry()
        self._load_pipeline_definitions()
        self.logger = logging.getLogger(__name__)

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineDefinition]:
        """Get a pipeline definition by ID."""
        return self.pipeline_definitions.get(pipeline_id)

    def set_progress_callback(
        self, callback: Optional[Callable[[str, StepProgress], None]]
    ) -> None:
        """Set a callback for progress updates."""
        self._progress_callback = callback
        if callback and self._dag_executor:
            self._dag_executor.set_progress_callback(
                lambda progress: callback(self._current_pipeline_id or "", progress)
            )

    async def runPipeline(
        self, context: PipelineContext, pipeline_def: PipelineDefinition
    ) -> None:
        """Run a pipeline with the given context."""
        try:
            self._current_pipeline_id = pipeline_def.id

            # Report initial pending status for all steps
            if self._progress_callback:
                for step in pipeline_def.steps:
                    self._progress_callback(
                        pipeline_def.id, StepProgress(step.name, StepStatus.PENDING)
                    )

            # Run the pipeline
            await self._dag_executor.executeDAG(context, pipeline_def.steps)

            # Report completion status
            if self._progress_callback:
                for step in pipeline_def.steps:
                    self._progress_callback(
                        pipeline_def.id, StepProgress(step.name, StepStatus.COMPLETED)
                    )
        except DAGExecutionError:
            # Re-raise DAGExecutionError directly
            raise
        except Exception as e:
            if self._progress_callback:
                for step in pipeline_def.steps:
                    self._progress_callback(
                        pipeline_def.id,
                        StepProgress(step.name, StepStatus.FAILED, e),
                    )
            raise

    def _loadPipelineConfig(self, yaml_path: str) -> PipelineDefinition:
        """Load a pipeline definition from a YAML file."""
        with Path(yaml_path).open("r") as f:
            data = yaml.safe_load(f)

        # Load params if defined
        params = [
            ParamDefinition(
                name=param["name"],
                required=param.get("required", True),
                description=param.get("description", ""),
                type=param.get("type", "string"),
            )
            for param in data.get("params", [])
        ]

        steps = [
            StepConfig(
                name=step["name"],
                plugin=step["plugin"],
                depends_on=step.get("depends_on", []),
                fail_on_error=step.get("fail_on_error", False),
            )
            for step in data["steps"]
        ]

        return PipelineDefinition(
            id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            params=params,
            steps=steps,
        )

    def validate_params(
        self, context: PipelineContext, definition: PipelineDefinition
    ) -> None:
        """Validate that all required parameters are present in the context."""
        missing_params: list[str] = []
        invalid_types: list[str] = []

        for param in definition.params:
            # --- Check missing required FIRST (and treat None as missing) ---
            # Check if param name is not in context OR if its value is None
            if param.required and (
                param.name not in context or context.get(param.name) is None
            ):
                missing_params.append(param.name)
                continue  # Don't check type if missing
            # --- End Check ---

            if param.name in context:  # Now only check type if present and not None
                value = context[param.name]
                # Basic type validation
                if param.type == "string" and not isinstance(value, str):
                    invalid_types.append(f"{param.name} (expected string)")
                elif param.type == "integer" and not isinstance(value, int):
                    invalid_types.append(f"{param.name} (expected integer)")
                elif param.type == "boolean" and not isinstance(value, bool):
                    invalid_types.append(f"{param.name} (expected boolean)")

        if missing_params:
            raise ValueError(
                f"Missing required parameters for pipeline '{definition.id}': {', '.join(missing_params)}"
            )

        if invalid_types:
            raise ValueError(
                f"Invalid parameter types in pipeline '{definition.id}': {', '.join(invalid_types)}"
            )

    def validate_pipeline(self, definition: PipelineDefinition) -> None:
        """Validate a pipeline definition for correctness."""
        # Check for duplicate step names
        step_names = {step.name for step in definition.steps}
        if len(step_names) != len(definition.steps):
            raise ValueError("Pipeline contains duplicate step names")

        # Check for duplicate param names
        param_names = {param.name for param in definition.params}
        if len(param_names) != len(definition.params):
            raise ValueError("Pipeline contains duplicate parameter names")

        # Check for invalid plugin references
        for step in definition.steps:
            if not self._step_registry.hasPlugin(step.plugin):
                raise ValueError(
                    f"Unknown plugin '{step.plugin}' referenced in step '{step.name}'"
                )

        # Check for invalid dependencies
        for step in definition.steps:
            for dep in step.depends_on:
                if dep not in step_names:
                    raise ValueError(
                        f"Step '{step.name}' depends on unknown step: '{dep}'"
                    )

            # Check that fail_on_error steps only depend on other fail_on_error steps
            if step.fail_on_error:
                for dep in step.depends_on:
                    dep_step = next(s for s in definition.steps if s.name == dep)
                    if not dep_step.fail_on_error:
                        raise ValueError(
                            f"Critical step '{step.name}' cannot depend on non-critical step '{dep}'"
                        )

        # Detect cycles using DFS
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(step_name: str) -> None:
            if step_name in rec_stack:
                raise ValueError(
                    f"Pipeline contains a circular dependency at step: {step_name}"
                )
            if step_name in visited:
                return

            visited.add(step_name)
            rec_stack.add(step_name)

            step = next(s for s in definition.steps if s.name == step_name)
            for dep in step.depends_on:
                # Handle string, ConditionalDependency, and dict types
                if isinstance(dep, str):
                    dfs(dep)
                elif isinstance(dep, dict):
                    # It's a dict-based ConditionalDependency
                    dfs(dep.get("step", ""))
                else:
                    # It's a ConditionalDependency object
                    dfs(dep.step)

            rec_stack.remove(step_name)

        # Run cycle detection for each step
        for step in definition.steps:
            if step.name not in visited:
                dfs(step.name)

    async def run_pipeline(self, pipeline_id: str, context: PipelineContext) -> None:
        """Run a pipeline with the given context."""
        self.logger.info(f"Starting pipeline execution: {pipeline_id}")
        pipeline = self.pipeline_definitions.get(pipeline_id)
        if not pipeline:
            self.logger.error(f"Pipeline {pipeline_id} not found")
            raise ValueError(f"Pipeline {pipeline_id} not found")

        # Validate parameters
        try:
            self.logger.info(f"Validating pipeline parameters for {pipeline_id}")
            self.validate_params(context, pipeline)
        except ValueError as e:
            self.logger.error(f"Parameter validation failed: {str(e)}")
            raise

        # Set progress callback if provided
        if self._progress_callback:
            self._dag_executor.set_progress_callback(
                lambda progress: self._progress_callback(pipeline_id, progress)
                if self._progress_callback
                else None
            )

        # Execute DAG
        try:
            self._current_pipeline_id = pipeline_id
            # Set pipeline_id in context so DAG executor can access it
            context["pipeline_id"] = pipeline_id
            self.logger.info(
                f"Executing DAG for pipeline {pipeline_id} with {len(pipeline.steps)} steps"
            )

            # Log each step
            for i, step in enumerate(pipeline.steps):
                self.logger.info(
                    f"Pipeline step {i + 1}: {step.name} (plugin: {step.plugin})"
                )

            await self._dag_executor.executeDAG(context, pipeline.steps)
            self.logger.info(f"Pipeline {pipeline_id} execution completed successfully")
        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            raise

    def _load_pipeline_definitions(self) -> None:
        """Load pipeline definitions from the pipeline registry."""
        pipeline_registry = self._container.get_pipeline_registry()
        self.pipeline_definitions = pipeline_registry.get_all()

    async def cleanup_providers(self) -> None:
        """Safely cleans up all registered providers."""
        self.logger.info("Orchestrator initiating provider cleanup.")
        await PluginBase.cleanup_all_providers()
        self.logger.info("Orchestrator provider cleanup complete.")

    async def resume_from_checkpoint(
        self, checkpoint: PipelineCheckpoint, resume_data: Dict[str, Any]
    ) -> None:
        """Resume pipeline execution from a checkpoint.

        Args:
            checkpoint: Checkpoint to resume from
            resume_data: Data to resume with
        """
        self.logger.info("=== Orchestrator.resume_from_checkpoint called ===")
        self.logger.info(f"Resume data: {resume_data}")
        # Get the pipeline definition
        pipeline = self.get_pipeline(checkpoint.pipeline_id)
        if not pipeline:
            # Try to get pipeline from task info
            task_manager = self._container.get_task_manager()
            task_info = task_manager.get_task_details(checkpoint.task_id)
            if task_info and "pipeline_id" in task_info:
                pipeline_id = task_info["pipeline_id"]
                pipeline = self.get_pipeline(pipeline_id)

            if not pipeline:
                raise ValueError(f"Pipeline {checkpoint.pipeline_id} not found")

        # Create execution context for resume
        context = create_execution_context(
            task_id=checkpoint.task_id,
            container=self._container,
            resume_data=resume_data,
            is_resume=True,
            checkpoint_id=checkpoint.checkpoint_id,
        )

        # Resume execution
        self._current_pipeline_id = pipeline.id

        # Set progress callback if provided
        if self._progress_callback:
            self._dag_executor.set_progress_callback(
                lambda progress: self._progress_callback(pipeline.id, progress)
                if self._progress_callback
                else None
            )

        try:
            # Resume from checkpoint
            await self._dag_executor.resume_from_checkpoint(
                context, pipeline.steps, checkpoint.checkpoint_id
            )
            self.logger.info(f"Pipeline {pipeline.id} resumed successfully")
        except Exception as e:
            self.logger.error(f"Pipeline resume failed: {str(e)}", exc_info=True)
            raise
