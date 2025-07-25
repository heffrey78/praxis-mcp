from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeAlias,
    Union,
)

from src.core.connections import ConnectionResolver
from src.core.dag_state import DAGState  # Import new DAGState
from src.core.dag_validator import (
    DAGValidator,
)  # Import ParsedDependency from dag_validator
from src.core.errors import (
    PipelineSuspendedException,
    PluginError,
    PluginInputError,
    PluginSuspendedException,
    RetryablePluginError,
)

# Import ExecutionContext for runtime checks
from src.core.execution_context import ExecutionContext
from src.core.loop_execution_strategy import (
    LoopExecutionStrategy,
)  # Import new LoopExecutionStrategy
from src.core.pipeline_definition import PipelineDefinition

# Import the new resolver
from src.core.plugin_input_resolver import PluginInputResolver
from src.core.plugin_invoker import PluginInvoker  # New import

# Import PluginOutputHandler
from src.core.plugin_output_handler import PluginOutputHandler
from src.core.step_config import StepConfig
from src.core.step_registry import StepRegistry
from src.core.suspend_context import SuspendContext
from src.core.template_processor import TemplateProcessor

if TYPE_CHECKING:
    from src.core.context import PipelineContext  # noqa: F401 (typing-only)
    from src.core.dag_validator import (
        ParsedDependency,
    )
    from src.plugins.plugin_base import PluginBase  # noqa: F401 (typing-only)

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUSPENDED = "suspended"


@dataclass
class StepProgress:
    """Progress information for a step."""

    step_name: str
    status: StepStatus
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    step_number: Optional[int] = None
    total_steps: Optional[int] = None
    group_name: Optional[str] = None  # Name of the parallel execution group
    # Add fields for final summary reporting via callback
    artifact_dir_path: Optional[str] = None
    artifact_list: Optional[List[str]] = None
    task_id: Optional[str] = None  # Add task_id to match the callback usage


@dataclass
class StepExecutionResult:
    """Result of a step execution."""

    status: str
    error: Optional[str] = None
    output: Optional[Any] = None
    saved_artifacts: Optional[List[Any]] = None
    is_critical: bool = False


class DAGExecutionError(Exception):
    """Error raised when a critical step fails."""

    def __init__(self, step_name: str, error: Exception) -> None:
        self.step_name = step_name
        self.error = error
        super().__init__(f"Step '{step_name}' failed: {str(error)}")


class PipelineExecutionError(Exception):
    """Aggregate exception that captures both normal and finally phase errors."""

    def __init__(
        self,
        normal_error: Optional[Exception] = None,
        finally_errors: Optional[List[Exception]] = None,
    ) -> None:
        self.normal_error = normal_error
        self.finally_errors = finally_errors or []

        # Build comprehensive error message
        messages = []
        if normal_error:
            messages.append(f"Normal phase failed: {str(normal_error)}")
        if self.finally_errors:
            messages.append(f"Finally phase had {len(self.finally_errors)} error(s)")
            for i, err in enumerate(self.finally_errors, 1):
                messages.append(f"  Finally error {i}: {str(err)}")

        super().__init__("; ".join(messages))

    def has_normal_error(self) -> bool:
        return self.normal_error is not None

    def has_finally_errors(self) -> bool:
        return len(self.finally_errors) > 0


# Define constants for retry logic
RETRY_DELAY = 1.0  # Default retry delay in seconds

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Tuple returned by plugin execution helpers: (plugin_output, saved_artifacts)
PluginRunResult: TypeAlias = Tuple[Optional[Any], List[Any]]


class DAGExecutor:
    """Executes steps in dependency order with retries and partial execution support."""

    def __init__(
        self,
        container: Union[ContainerLike, StepRegistry],
        max_workers: Optional[int] = None,
        use_connections: bool = True,
        checkpoint_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the DAG executor."""
        logger.info(
            f"DAGExecutor.__init__: Initializing with container of type: {type(container)}"
        )

        if isinstance(container, StepRegistry):
            self._step_registry = container
            self._container: Optional[ContainerLike] = None
            logger.info(
                "DAGExecutor.__init__: Initialized with StepRegistry. self._container is None."
            )
        else:
            self._step_registry = container.get_step_registry()
            self._container = container
            logger.info(
                "DAGExecutor.__init__: Initialized with DependencyContainer. self._container is SET."
            )

        self.max_workers = max_workers or min(32, (os.cpu_count() or 4))
        self._semaphore = asyncio.Semaphore(self.max_workers)
        self._progress_callback: Optional[Callable[[StepProgress], None]] = None

        # Initialize components
        self._dag_validator = DAGValidator(self._step_registry)
        self._plugin_input_resolver = PluginInputResolver()
        self._plugin_invoker = PluginInvoker()
        self.output_handler = PluginOutputHandler()
        self._template_processor = TemplateProcessor()
        # Initialize LoopExecutionStrategy, passing necessary parts of DAGExecutor's config/state
        self._loop_executor_strategy = LoopExecutionStrategy(
            parent_executor_container=self._container
            if self._container
            else self._step_registry,
            parent_executor_max_workers=self.max_workers,
            parent_executor_use_connections=use_connections,
            progress_callback=self._progress_callback,  # Will be updated if set_progress_callback is called
            checkpoint_manager=checkpoint_manager,
        )

        # Setup other attributes
        self._use_connections = use_connections
        self._connection_resolver = (
            ConnectionResolver(self._step_registry) if use_connections else None
        )
        self._current_context: Optional[Union["PipelineContext", ExecutionContext]] = (
            None
        )
        self._steps: List[StepConfig] = []
        self._loop_states: Dict[str, Dict[str, Any]] = {}
        self._step_results: Dict[str, StepExecutionResult] = {}
        self._parallel_groups: Dict[str, str] = {}
        self._step_timings: Dict[str, Dict[str, float]] = {}
        # Parsed dependencies are only available *after* validate_steps is called.
        # Use forward reference for ParsedDependency to avoid runtime import costs
        self._parsed_dependencies: Dict[str, List["ParsedDependency"]] = {}

        # Initialize with an empty DAGState so the attribute is always non-optional
        # for static analysis.  This placeholder is replaced with the real state in
        # executeDAG.
        self._state: DAGState = DAGState([])

        # Checkpoint manager for suspend/resume support
        self._checkpoint_manager = checkpoint_manager
        self._suspend_context: Optional[Any] = None

    @property
    def max_concurrent_steps(self) -> int:
        """Return the maximum number of concurrent steps allowed."""
        return self.max_workers

    def set_progress_callback(self, callback: Callable[[StepProgress], None]) -> None:
        """Set a callback to be called when step progress changes."""
        self._progress_callback = callback
        # Also update the loop executor strategy if it exists
        if hasattr(self, "_loop_executor_strategy") and self._loop_executor_strategy:
            self._loop_executor_strategy.progress_callback = callback

    def _identify_parallel_groups(self, steps: List[StepConfig]) -> None:
        """Identify groups of steps that can run in parallel based on dependencies."""
        dependency_groups: Dict[str, List[str]] = {}

        # Group steps by their dependencies
        for step in steps:
            # Convert dependencies to strings for grouping
            dep_strs: List[str] = []
            for dep in step.depends_on:
                if isinstance(dep, str):
                    dep_strs.append(dep)
                elif hasattr(dep, "step"):
                    # ConditionalDependency or similar
                    dep_strs.append(getattr(dep, "step", ""))
            deps_key = ",".join(sorted(dep_strs))
            if deps_key not in dependency_groups:
                dependency_groups[deps_key] = []
            dependency_groups[deps_key].append(step.name)

        # Assign group names to steps
        for deps_key, step_names in dependency_groups.items():
            if len(step_names) > 1:
                # Multiple steps with same dependencies = parallel group
                group_name = (
                    f"parallel_after_{deps_key.replace(',', '_')}"
                    if deps_key
                    else "initial_parallel"
                )
                for step_name in step_names:
                    self._parallel_groups[step_name] = group_name
            else:
                # Single step = sequential
                self._parallel_groups[step_names[0]] = "sequential"

    async def _execute_loop(
        self, context: Union["PipelineContext", ExecutionContext], step: StepConfig
    ) -> PluginRunResult:
        """Delegates loop execution to LoopExecutionStrategy."""
        logger.info(
            f"DAGExecutor: Delegating loop execution for step '{step.name}' to LoopExecutionStrategy."
        )
        try:
            await self._loop_executor_strategy.execute_loop(context, step)
            # LoopExecutionStrategy handles context updates internally and re-raises on failure.
            # If it completes without error, the loop is considered successful from DAGExecutor's perspective.
            # Loop steps don't typically return a direct "plugin output"; results are in context.
            return (
                None,
                [],
            )  # Match signature for _run_with_retries, indicating no direct output/artifacts from the loop step itself
        except PipelineSuspendedException:
            # Allow suspension to propagate - will be handled by executeDAG
            logger.info(f"DAGExecutor: Loop step '{step.name}' requested suspension")
            raise
        except Exception as e:
            logger.error(
                f"DAGExecutor: Loop step '{step.name}' failed during execution via LoopExecutionStrategy: {e}",
                exc_info=True,
            )
            # LoopExecutionStrategy should raise if any iteration fails and fail_fast is on, or a summary exception.
            # This exception will be caught by the main task processing loop in executeDAG.
            raise  # Re-raise to be caught by the task handler in executeDAG

    def _report_progress(
        self,
        step_name: str,
        status: Union[StepStatus, str],
        error: Optional[Exception] = None,
        artifacts: Optional[List[Any]] = None,
    ) -> None:
        """Report progress through the callback if one is set."""
        logger.info(
            f"DAGExecutor._report_progress: Reporting progress for step '{step_name}': {status}"
        )

        # Call the generic progress callback if it's set (e.g., for CLI updates)
        if self._progress_callback:
            logger.info(
                f"DAGExecutor._report_progress: self._progress_callback is SET for step '{step_name}'. Calling it."
            )
            current_time = time.time()

            if (
                status == StepStatus.RUNNING
            ):  # Assuming StepStatus.RUNNING is comparable to string status
                self._step_timings[step_name] = {"start": current_time}
            elif (
                status
                in [
                    StepStatus.COMPLETED,
                    StepStatus.FAILED,
                    str(StepStatus.COMPLETED),
                    str(StepStatus.FAILED),
                ]
                and step_name in self._step_timings
            ):  # Compare with string form too
                self._step_timings[step_name]["end"] = current_time

            # Construct the StepProgress object for the generic callback
            # Ensure all fields are correctly sourced
            step_number_val = (
                self._state.step_numbers.get(step_name)
                if hasattr(self, "_state") and self._state
                else None
            )
            total_steps_val = (
                self._state.total_steps
                if hasattr(self, "_state") and self._state
                else None
            )
            task_id_val_generic = (
                self._current_context.task_id
                if self._current_context and hasattr(self._current_context, "task_id")
                else "UNKNOWN_TASK_ID_GenericCallback"
            )

            # Normalize to StepStatus enum (enum subclass of str, so direct cast is safe)
            step_status: StepStatus = StepStatus(status)

            progress_for_generic_callback = StepProgress(
                step_name=step_name,
                status=step_status,
                error=error,
                start_time=self._step_timings.get(step_name, {}).get("start"),
                end_time=self._step_timings.get(step_name, {}).get("end"),
                step_number=step_number_val,
                total_steps=total_steps_val,
                group_name=self._parallel_groups.get(step_name),
                task_id=task_id_val_generic,
            )
            self._progress_callback(progress_for_generic_callback)
        else:
            logger.warning(
                f"DAGExecutor._report_progress: self._progress_callback is None for step '{step_name}'. Skipping generic callback."
            )

        # ALWAYS attempt to update TaskManager if the container is available
        if self._container is not None:
            logger.info(
                f"DAGExecutor._report_progress: self._container is SET for step '{step_name}'. Attempting to update TaskManager."
            )
            task_manager = self._container.get_task_manager()
            context = self._current_context

            # DETAILED CONTEXT AND TASK_ID LOGGING
            logger.info(
                f"DAGExecutor._report_progress: For step '{step_name}', status '{status}': Checking context. Context is {'None' if context is None else 'Present'}."
            )
            if context:
                logger.info(
                    f"DAGExecutor._report_progress: For step '{step_name}', status '{status}': hasattr(context, 'task_id') is {hasattr(context, 'task_id')}."
                )
                if hasattr(context, "task_id"):
                    logger.info(
                        f"DAGExecutor._report_progress: For step '{step_name}', status '{status}': context.task_id is '{context.task_id}' (type: {type(context.task_id)})."
                    )
                    if context.task_id:  # Check if it's non-empty, not None
                        logger.info(
                            f"DAGExecutor._report_progress: All checks PASSED for step '{step_name}', status '{status}'. Calling TaskManager.update_step_progress."
                        )
                        plugin_name = "unknown"
                        if hasattr(self, "_steps") and self._steps:
                            for step_config_item in self._steps:
                                if step_config_item.name == step_name:
                                    plugin_name = step_config_item.plugin
                                    break
                        else:
                            logger.warning(
                                f"DAGExecutor._report_progress: self._steps not available or empty, plugin_name set to 'unknown' for step '{step_name}'."
                            )

                        artifacts_dict_list = []
                        if artifacts:
                            for art in artifacts:
                                if hasattr(art, "__dict__"):
                                    artifacts_dict_list.append(art.__dict__)
                                elif isinstance(art, dict):
                                    artifacts_dict_list.append(art)
                                else:
                                    logger.warning(
                                        f"DAGExecutor._report_progress: Artifact for step '{step_name}' is not a dict or object with __dict__: {type(art)}"
                                    )

                        task_manager.update_step_progress(
                            task_id=context.task_id,
                            step_name=step_name,
                            status=str(status),
                            error=str(error) if error else None,
                            start_time=self._step_timings.get(step_name, {}).get(
                                "start"
                            ),
                            end_time=self._step_timings.get(step_name, {}).get("end"),
                            plugin=plugin_name,
                            artifacts=artifacts_dict_list,
                        )
                    else:
                        logger.warning(
                            f"DAGExecutor._report_progress: context.task_id is None or empty for step '{step_name}', status '{status}'. CANNOT update TaskManager."
                        )
                else:
                    logger.warning(
                        f"DAGExecutor._report_progress: context does NOT have task_id attribute for step '{step_name}', status '{status}'. CANNOT update TaskManager."
                    )
            else:
                logger.warning(
                    f"DAGExecutor._report_progress: context is None for step '{step_name}', status '{status}'. CANNOT update TaskManager."
                )
        else:
            logger.warning(
                f"DAGExecutor._report_progress: self._container is None for step '{step_name}'. Cannot get TaskManager to update step progress (this should not happen if DAGExecutor was initialized with a DependencyContainer)."
            )

    async def _run_with_retries(
        self,
        plugin_instance: PluginBase,
        context_arg: Union["PipelineContext", ExecutionContext],
        step: StepConfig,
        attempt: int = 0,
        max_retries: int = 3,
    ) -> PluginRunResult:
        """Run a plugin with retries. Output processing is delegated to PluginOutputHandler."""
        saved_artifacts: List[Any] = []
        assert self._current_context is not None, (
            "_current_context cannot be None in _run_with_retries"
        )

        if step.name not in self._step_timings:
            self._step_timings[step.name] = {"start": time.time()}

        context_for_plugin_run_final = self._current_context

        try:
            # Clear saved artifacts for current step
            if hasattr(context_for_plugin_run_final, "clear_saved_artifacts"):
                context_for_plugin_run_final.clear_saved_artifacts()

            # If using connections, prepare the plugin context with resolved inputs
            if self._use_connections and step.name in self._connection_map:
                # Resolve connections for this step
                resolved_inputs = {}
                logger.debug(
                    f"Step {step.name} has connections: {self._connection_map[step.name]}"
                )

                for target_field, (source_step, source_field) in self._connection_map[
                    step.name
                ].items():
                    # Get value from source step output
                    if source_step in context_for_plugin_run_final:
                        source_output = context_for_plugin_run_final[source_step]
                        logger.debug(
                            f"Found source step {source_step} output: {source_output}"
                        )
                        if (
                            isinstance(source_output, dict)
                            and source_field in source_output
                        ):
                            resolved_inputs[target_field] = source_output[source_field]
                            logger.debug(
                                f"Resolved {target_field} = {source_output[source_field]} from {source_step}.{source_field}"
                            )
                        else:
                            # Try direct access
                            resolved_inputs[target_field] = source_output
                            logger.debug(
                                f"Resolved {target_field} = {source_output} (direct access)"
                            )
                    elif (
                        f"{source_step}.{source_field}" in context_for_plugin_run_final
                    ):
                        # Try dotted notation
                        resolved_inputs[target_field] = context_for_plugin_run_final[
                            f"{source_step}.{source_field}"
                        ]
                        logger.debug(f"Resolved {target_field} from dotted notation")
                    else:
                        logger.warning(
                            f"Could not resolve connection for {target_field}: source {source_step}.{source_field} not found in context"
                        )

                # Create child context with resolved inputs
                if isinstance(context_for_plugin_run_final, ExecutionContext):
                    context_for_plugin_run_final = (
                        context_for_plugin_run_final.spawn_child(
                            extras={
                                **context_for_plugin_run_final.extras,
                                **resolved_inputs,
                            }
                        )
                    )
                else:
                    # For PipelineContext, store resolved inputs directly
                    for field, value in resolved_inputs.items():
                        context_for_plugin_run_final[field] = value

                logger.debug(
                    f"Step {step.name}: Resolved {len(resolved_inputs)} input connections: {list(resolved_inputs.keys())}"
                )

            # For ExecutionContext, ensure we have a child context with step-specific data
            elif isinstance(context_for_plugin_run_final, ExecutionContext):
                context_for_plugin_run_final = context_for_plugin_run_final.spawn_child(
                    step_name=step.name,
                    loop_iteration=getattr(
                        context_for_plugin_run_final, "loop_iteration", None
                    ),
                )

            actual_plugin_payload = self._plugin_input_resolver.resolve_inputs(
                plugin_instance=plugin_instance,
                step_config=step,
                context=context_for_plugin_run_final,
            )

            if (
                plugin_instance.InputModel
                and actual_plugin_payload is None
                and not getattr(plugin_instance, "allow_empty_input", False)
            ):
                logger.error(  # Using module logger
                    f"Step {step.name}: Pydantic InputModel '{plugin_instance.InputModel.__name__}' was expected, "
                    f"but input validation failed (resolved payload is None) and allow_empty_input is not True. Cannot invoke plugin."
                )
                raise PluginInputError(
                    f"Input validation failed for Pydantic model '{plugin_instance.InputModel.__name__}' in step {step.name}"
                )

            async with self._semaphore:
                logger.debug(
                    f"Step {step.name}: Acquired semaphore. Current concurrency: {self._semaphore._value + 1}/{self.max_concurrent_steps}"
                )
                self._report_progress(step.name, StepStatus.RUNNING)

                plugin_output = (
                    await self._plugin_invoker.invoke(  # Using self._plugin_invoker
                        plugin=plugin_instance,
                        context=context_for_plugin_run_final,
                        inputs=actual_plugin_payload,
                        step_name=step.name,
                    )
                )

                if hasattr(context_for_plugin_run_final, "get_saved_artifacts"):
                    saved_artifacts.extend(
                        context_for_plugin_run_final.get_saved_artifacts()
                    )

            logger.debug(
                f"Step {step.name}: Released semaphore. Current concurrency: {self._semaphore._value}/{self.max_concurrent_steps}"
            )

            if step.name in self._step_timings:
                self._step_timings[step.name]["end"] = time.time()

            # Delegate output processing and context merging to PluginOutputHandler
            await self.output_handler.handle_output(
                raw_plugin_output=plugin_output,
                plugin_instance=plugin_instance,
                step=step,
                context=context_for_plugin_run_final,
            )

            # Propagate outputs from plugin context back to main context
            # For ExecutionContext, we don't need to propagate since context is shared
            # The plugin output handler will store outputs in the context

            # Also update saved artifacts if needed
            if hasattr(context_for_plugin_run_final, "get_saved_artifacts"):
                saved_artifacts.extend(
                    context_for_plugin_run_final.get_saved_artifacts()
                )

            return plugin_output, saved_artifacts

        except PluginSuspendedException as e:
            logger.info(f"Step {step.name} requested suspension: {str(e)}")

            # For ExecutionContext, context changes are already reflected
            # since we use a shared context model

            self._state.mark_step_suspended(step.name)
            self._report_progress(step.name, StepStatus.SUSPENDED, error=e)

            # Initialize suspend context if needed
            if self._suspend_context is None:
                self._suspend_context = SuspendContext()

            # Record suspension details
            self._suspend_context.request_suspend(
                step_name=step.name, reason=str(e), data=e.suspend_info
            )

            # Re-raise to be handled by executeDAG
            raise

        except PluginInputError as e:
            logger.error(f"Input error in step {step.name}: {e}", exc_info=True)
            self._state.mark_step_failed(step.name, e)
            self._report_progress(step.name, StepStatus.FAILED, error=e)
            if step.name in self._step_timings:
                self._step_timings[step.name]["end"] = time.time()
            if step.fail_on_error:
                raise
            return None, saved_artifacts  # Return a tuple
        except RetryablePluginError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Retryable error in step {step.name} (attempt {attempt + 1}/{max_retries}): {e}. Retrying..."
                )
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                return await self._run_with_retries(
                    plugin_instance, context_arg, step, attempt + 1, max_retries
                )
            logger.error(
                f"Failed step {step.name} after {attempt + 1} attempts (retryable error): {e}",
                exc_info=True,
            )
            self._state.mark_step_failed(step.name, e)
            self._report_progress(step.name, StepStatus.FAILED, error=e)
            if step.name in self._step_timings:
                self._step_timings[step.name]["end"] = time.time()
            if step.fail_on_error:
                raise
            return None, saved_artifacts  # Return a tuple
        except PluginError as e:
            logger.error(f"Plugin error in step {step.name}: {e}", exc_info=True)
            self._state.mark_step_failed(step.name, e)
            self._report_progress(step.name, StepStatus.FAILED, error=e)
            if step.name in self._step_timings:
                self._step_timings[step.name]["end"] = time.time()
            if step.fail_on_error:
                raise
            return None, saved_artifacts  # Return a tuple
        except Exception as e:
            if step.name in self._step_timings:
                self._step_timings[step.name]["end"] = time.time()
            logger.error(
                f"Step '{step.name}' failed with an unexpected error: {str(e)}",
                exc_info=True,
            )
            self._state.mark_step_failed(step.name, e)
            self._report_progress(step.name, StepStatus.FAILED, error=e)
            if step.fail_on_error:
                raise DAGExecutionError(step.name, e) from e
            return None, saved_artifacts  # Return a tuple

    def _create_step_task(
        self, step: StepConfig
    ) -> Optional[asyncio.Task[PluginRunResult]]:
        """Create an asyncio task for executing a step."""
        # Ensure we have a context
        assert self._current_context is not None, (
            "_current_context must be set before creating tasks"
        )

        try:
            # Check if this is a loop step
            is_loop_step = hasattr(step, "loop_config") and step.loop_config is not None

            if is_loop_step:
                # Loop steps don't need a plugin instance
                logger.info(
                    f"Step '{step.name}' is a loop step. Executing with _execute_loop."
                )
                task = asyncio.create_task(
                    self._execute_loop(self._current_context, step), name=step.name
                )
            else:
                # Regular plugin execution
                # Get step-specific configuration
                step_config_params = step.config or {}

                # Process Jinja2 templates in config
                template_context: Dict[str, Any] = {}

                # Add all parameters and context data
                if isinstance(self._current_context, dict):
                    template_context.update(self._current_context)
                else:
                    # For both PipelineContext and ExecutionContext, use get_data()
                    if hasattr(self._current_context, "get_data"):
                        get_data_func = self._current_context.get_data
                        template_context.update(get_data_func())
                    # For ExecutionContext, also include extras
                    if (
                        hasattr(self._current_context, "extras")
                        and hasattr(self._current_context, "__class__")
                        and self._current_context.__class__.__name__
                        == "ExecutionContext"
                    ):
                        extras = getattr(self._current_context, "extras", {})
                        if isinstance(extras, dict):
                            template_context.update(extras)

                    # Add task_id if available
                    if hasattr(self._current_context, "task_id"):
                        template_context["task_id"] = self._current_context.task_id

                # Process templates in config
                step_config_params = self._template_processor.process_config(
                    step_config_params, template_context
                )

                # Use the registry's get_plugin method
                plugin_instance = self._step_registry.get_plugin(
                    name=step.plugin, config=step_config_params
                )

                logger.info(
                    f"Step '{step.name}' is a regular step. Executing with _run_with_retries."
                )
                task = asyncio.create_task(
                    self._run_with_retries(
                        plugin_instance, self._current_context, step
                    ),
                    name=step.name,
                )

            # Mark step as running in state
            self._state.mark_step_running(step.name)
            return task

        except Exception as init_error:
            logger.error(
                f"Failed to get or initialize plugin '{step.plugin}' for step '{step.name}': {init_error}",
                exc_info=True,
            )
            self._state.mark_step_failed(step.name, init_error)
            self._report_progress(step.name, "failed", init_error)
            if step.fail_on_error:
                raise DAGExecutionError(step.name, init_error) from init_error
            return None

    async def _execute_normal_phase(
        self,
        step_configs: List[StepConfig],
        tasks: Dict[str, asyncio.Task[PluginRunResult]],
    ) -> None:
        """Execute normal (non-finally) steps."""
        logger.info("Starting normal execution phase")

        # Ensure we have a context
        assert self._current_context is not None, (
            "_current_context must be set in executeDAG"
        )

        # Filter out finally steps
        normal_steps = [step for step in step_configs if not step.is_finally]

        while True:
            # Get ready steps from the DAGState (only normal steps)
            ready_steps: List[StepConfig] = []
            for step in normal_steps:
                # Get context data in a way that works for both context types
                context_data = None
                if hasattr(self._current_context, "get_data"):
                    get_data_func = self._current_context.get_data
                    context_data = get_data_func()
                elif (
                    hasattr(self._current_context, "extras")
                    and hasattr(self._current_context, "__class__")
                    and self._current_context.__class__.__name__ == "ExecutionContext"
                ):
                    # ExecutionContext specific handling
                    context_data = getattr(self._current_context, "extras", {})

                if self._state.is_step_ready(
                    step.name,
                    self._parsed_dependencies,
                    context_data,
                ):
                    ready_steps.append(step)

            if not ready_steps and not tasks:
                # No steps ready and no tasks running
                remaining = [
                    s
                    for s in self._state.get_remaining_steps()
                    if s in [n.name for n in normal_steps]
                ]
                if not remaining:
                    logger.info("Normal phase execution complete.")
                    break

                # Check for steps waiting on unmet conditional branches or failed dependencies
                waiting_on_condition: List[str] = []
                waiting_on_failed_deps: List[str] = []

                for r_step_name in remaining:
                    for dep in self._parsed_dependencies.get(r_step_name, []):
                        if (
                            dep.is_conditional
                            and dep.step_name in self._state.completed_steps
                        ):
                            waiting_on_condition.append(r_step_name)
                            break
                        if dep.step_name in self._state.failed_steps:
                            # Step depends on a failed step, so it should be skipped
                            waiting_on_failed_deps.append(r_step_name)
                            break

                if waiting_on_condition or waiting_on_failed_deps:
                    logger.info(
                        f"Normal phase complete. Steps waiting on unmet conditions: {waiting_on_condition}, "
                        f"Steps waiting on failed dependencies: {waiting_on_failed_deps}"
                    )
                    for skip_step in waiting_on_condition + waiting_on_failed_deps:
                        self._state.mark_step_skipped(skip_step)
                    break

                logger.error(
                    f"Pipeline stalled unexpectedly. Remaining steps: {remaining}"
                )
                raise ValueError(f"Pipeline stalled. Remaining steps: {remaining}")

            # Start new tasks for ready steps
            for step in ready_steps:
                task = self._create_step_task(step)
                if task:
                    tasks[step.name] = task

            if not tasks:
                await asyncio.sleep(0.01)
                continue

            # Wait for any task to complete
            done, _ = await asyncio.wait(
                tasks.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks
            for task in done:
                await self._process_completed_task(task, step_configs, tasks)

    async def _execute_finally_phase(
        self,
        step_configs: List[StepConfig],
        tasks: Dict[str, asyncio.Task[PluginRunResult]],
    ) -> List[Exception]:
        """Execute finally steps (always runs, even if normal phase failed)."""
        # Filter out normal steps
        finally_steps = [step for step in step_configs if step.is_finally]
        if not finally_steps:
            return []

        logger.info(
            f"Starting finally execution phase with {len(finally_steps)} finally steps"
        )

        finally_errors: List[Exception] = []

        while True:
            # Get ready finally steps - they have different readiness rules
            ready_steps: List[StepConfig] = []
            for step in finally_steps:
                if self._state.is_step_ready_for_finally(
                    step.name,
                    self._parsed_dependencies,
                ):
                    ready_steps.append(step)

            if not ready_steps and not tasks:
                # No finally steps ready and no tasks running
                remaining = [
                    s
                    for s in self._state.get_remaining_steps()
                    if s in [n.name for n in finally_steps]
                ]
                if not remaining:
                    logger.info("Finally phase execution complete.")
                    break

                logger.error(f"Finally phase stalled. Remaining steps: {remaining}")
                # Don't raise - just log and break
                break

            # Start new tasks for ready finally steps
            for step in ready_steps:
                try:
                    task = self._create_step_task(step)
                    if task:
                        tasks[step.name] = task
                except Exception as e:
                    # Log but don't fail the entire finally phase
                    logger.error(f"Failed to start finally step '{step.name}': {e}")
                    finally_errors.append(e)

            if not tasks:
                await asyncio.sleep(0.01)
                continue

            # Wait for any task to complete
            done, _ = await asyncio.wait(
                tasks.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks - capture errors but don't fail
            for task in done:
                try:
                    await self._process_completed_task(task, step_configs, tasks)
                except Exception as e:
                    step_name = task.get_name()
                    logger.error(f"Error in finally step '{step_name}': {e}")
                    finally_errors.append(e)

        # Check for any finally steps that failed (even with fail_on_error=False)
        for step in finally_steps:
            if step.name in self._state.failed_steps:
                # Get the error from the state
                step_state = self._state.step_states.get(step.name)
                if step_state and step_state.error:
                    finally_errors.append(step_state.error)
                else:
                    # Create a generic error if we don't have the original
                    finally_errors.append(
                        Exception(f"Finally step '{step.name}' failed")
                    )

        return finally_errors

    async def _process_completed_task(
        self,
        task: asyncio.Task[PluginRunResult],
        step_configs: List[StepConfig],
        tasks: Dict[str, asyncio.Task[PluginRunResult]],
    ) -> None:
        """Process a completed task (used by both normal and finally phases)."""
        step_name = task.get_name()
        try:
            # Unpack result and artifacts
            result, saved_artifacts = await task

            # Only mark step as completed if it exists in our DAG state
            if self._state.has_step(step_name):
                # Check if the step was already marked as failed
                # (happens when fail_on_error=False and step fails)
                if step_name not in self._state.failed_steps:
                    self._state.mark_step_completed(step_name, saved_artifacts)
                    self._report_progress(
                        step_name, "completed", artifacts=saved_artifacts
                    )
            else:
                logger.debug(
                    f"Step '{step_name}' not found in DAG state, likely a sub-step from composite plugin"
                )

        except PluginSuspendedException as suspend_error:
            logger.info(f"Step '{step_name}' suspended: {suspend_error}")
            # State and suspend context already updated in _run_with_retries

        except PipelineSuspendedException as pipeline_suspend:
            logger.info(
                f"Pipeline suspended during step '{step_name}': {pipeline_suspend}"
            )
            raise

        except DAGExecutionError as dag_error:
            logger.error(
                f"DAG execution error in step '{step_name}': {dag_error.error}"
            )
            if self._state.has_step(step_name):
                self._state.mark_step_failed(step_name, dag_error.error)
                self._report_progress(
                    step_name, "failed", dag_error.error, artifacts=[]
                )
            raise  # Propagate critical failures

        except Exception as e:
            logger.error(
                f"Exception processing completed step '{step_name}': {str(e)}",
                exc_info=True,
            )
            if self._state.has_step(step_name):
                self._state.mark_step_failed(step_name, e)
                self._report_progress(step_name, "failed", e, artifacts=[])

                # Check fail_on_error for the original step config
                original_step_config = next(
                    (s for s in step_configs if s.name == step_name), None
                )
                if original_step_config and original_step_config.fail_on_error:
                    raise DAGExecutionError(step_name, e) from e
        finally:
            del tasks[step_name]

    def _build_pipeline_definition(self, steps: List[StepConfig]) -> PipelineDefinition:
        """Build a PipelineDefinition object from a list of StepConfig objects."""
        return PipelineDefinition(
            id="temporary-pipeline",
            name="Temporary Pipeline",
            description="Temporary pipeline for connection resolution",
            params=[],
            steps=steps,
        )

    async def executeDAG(
        self,
        context: Union["PipelineContext", ExecutionContext],
        steps: List[StepConfig] | Dict[str, Any],
    ) -> None:
        """Execute steps in dependency order with retries and partial execution support."""
        # Convert dictionary to StepConfig list if needed
        if isinstance(steps, dict):
            # Simplified conversion - assumes basic structure
            step_configs = [
                StepConfig(
                    name=name,
                    plugin=config.get("plugin", ""),
                    depends_on=config.get("depends_on", []),
                )
                for name, config in steps.items()
            ]
        else:
            step_configs = steps

        # Store original steps
        self._steps = step_configs

        # Validate the DAG structure using our DAGValidator
        try:
            self._parsed_dependencies = self._dag_validator.validate_steps(step_configs)
        except ValueError as e:
            logger.error(f"Pipeline validation failed: {e}")
            raise

        # Initialize the DAGState for tracking execution state
        # Only create new state if we don't already have one (e.g., from resume)
        # Note: self._state is initialized to an empty DAGState([]) in __init__
        if len(self._state.steps) == 0:
            self._state = DAGState(step_configs)
            self._state.start_execution()
            logger.debug(
                f"Created new DAGState for execution with {len(step_configs)} steps"
            )
        else:
            logger.debug(
                f"Using existing DAGState with completed steps: {self._state.completed_steps}"
            )
            logger.debug(
                f"Existing state has {len(self._state.steps)} steps, current config has {len(step_configs)} steps"
            )

            # Ensure the existing state has all the steps from current configuration
            # This handles cases where we're resuming with a slightly different pipeline
            for step in step_configs:
                if step.name not in self._state.step_states:
                    logger.warning(
                        f"Step '{step.name}' not found in restored state, adding it"
                    )
                    from src.core.dag_state import StepState

                    self._state.step_states[step.name] = StepState(name=step.name)
                    self._state.step_numbers[step.name] = (
                        len(self._state.step_numbers) + 1
                    )

            # Also update the steps list if it's empty (from old checkpoints)
            if len(self._state.steps) == 0:
                logger.warning(
                    "Existing state has empty steps list, updating with current config"
                )
                self._state.steps = step_configs

        # Store the connection map if connections are enabled
        self._connection_map: Dict[str, Dict[str, Tuple[str, str]]] = {}

        # Resolve connections if enabled
        if self._use_connections and self._connection_resolver:
            try:
                pipeline_def = self._build_pipeline_definition(step_configs)
                current_scope_connection_map = (
                    self._connection_resolver.resolve_connections(pipeline_def)
                )

                # Convert to step-based mapping for easier lookup
                for (target_step, target_field), (
                    source_step,
                    source_field,
                ) in current_scope_connection_map.items():
                    if target_step not in self._connection_map:
                        self._connection_map[target_step] = {}
                    self._connection_map[target_step][target_field] = (
                        source_step,
                        source_field,
                    )

                logger.info(
                    f"Resolved connections for {len(self._connection_map)} steps"
                )
                logger.debug(f"Connection map: {self._connection_map}")

            except Exception as e:
                logger.error(f"Connection resolution failed: {e}", exc_info=True)
                raise ValueError(f"Pipeline connection resolution failed: {e}") from e

        # Always use the passed context directly - no more EnhancedContext
        self._current_context = context

        # Setup for execution
        self._identify_parallel_groups(step_configs)
        self._step_timings.clear()

        tasks: Dict[str, asyncio.Task[PluginRunResult]] = {}
        normal_phase_error: Optional[Exception] = None
        finally_errors: List[Exception] = []

        try:
            try:
                # Phase 1: Execute normal (non-finally) steps
                await self._execute_normal_phase(step_configs, tasks)

            except Exception as e:
                # Capture the error but don't re-raise yet - we need to run finally steps
                normal_phase_error = e
                logger.error(f"Normal phase failed: {e}")

            try:
                # Phase 2: Execute finally steps (always runs, even if normal phase failed)
                finally_errors = await self._execute_finally_phase(step_configs, tasks)

            except Exception as e:
                # This should rarely happen as finally phase is designed to be resilient
                logger.error(f"Finally phase encountered unexpected error: {e}")
                finally_errors.append(e)

            # Now handle any errors from both phases
            if normal_phase_error or finally_errors:
                raise PipelineExecutionError(normal_phase_error, finally_errors)

        finally:
            # Mark execution as complete
            self._state.finish_execution()

            # Check if we need to create a checkpoint for suspended steps
            if self._suspend_context and self._suspend_context.suspended_steps:
                await self._create_suspension_checkpoint()

            # Connection validation removed - no longer using EnhancedContext

            # Generate summary and report progress
            self._print_summary()
            if self._progress_callback:
                self._report_summary_progress()

            # Propagate final context state back to original context
            if (
                hasattr(self._current_context, "get_data")
                and context is not self._current_context
            ):
                logger.info(
                    f"Final state propagation: Updating original context (id={id(context)}) with data from _current_context (id={id(self._current_context)})"
                )
                context.update(self._current_context.get_data())

                # Also propagate saved artifacts if the original context can hold them
                if hasattr(context, "get_saved_artifacts") and hasattr(
                    self._current_context, "get_saved_artifacts"
                ):
                    current_artifacts = self._current_context.get_saved_artifacts()
                    if hasattr(context, "set_saved_artifacts"):
                        context.set_saved_artifacts(current_artifacts)
                        logger.info(
                            f"Propagated {len(current_artifacts)} artifacts to original context."
                        )

            logger.info("Finished DAG execution.")

    async def _create_suspension_checkpoint(self) -> None:
        """Create checkpoint when all parallel steps have completed or suspended."""
        if not self._checkpoint_manager or not self._suspend_context:
            logger.warning(
                "Cannot create checkpoint: checkpoint manager or suspend context not available"
            )
            return

        # Check if all running steps are done (completed/failed/suspended)
        if self._state.running_steps:
            logger.info(
                f"Not creating checkpoint yet, still have running steps: {self._state.running_steps}"
            )
            return

        logger.info("Creating suspension checkpoint")

        try:
            task_id = getattr(self._current_context, "task_id", None)
            if not task_id:
                logger.error("Cannot create checkpoint: no task_id in context")
                return

            checkpoint_id = await self._checkpoint_manager.create_checkpoint(
                task_id=task_id,
                pipeline_id=getattr(self._current_context, "pipeline_id", "unknown"),
                dag_state=self._state,
                context=self._current_context,
                suspended_at_steps=self._suspend_context.suspended_steps,
                suspend_data=self._suspend_context.suspend_data,
                suspend_reasons=self._suspend_context.suspend_reasons,
            )

            logger.info(f"Created checkpoint: {checkpoint_id}")

            # Update task status to suspended
            if self._container:
                try:
                    task_manager = self._container.get_task_manager()
                    task_manager.update_task_status(task_id, "suspended")
                except Exception as e:
                    logger.warning(f"Failed to update task status to suspended: {e}")

            # Get suspend_info from the first suspended step (typically only one step suspends at a time)
            suspend_info = None
            if self._suspend_context.suspend_data:
                # Get the first step's suspend data
                first_step = next(iter(self._suspend_context.suspend_data), None)
                if first_step:
                    suspend_info = self._suspend_context.suspend_data[first_step]

            # Raise PipelineSuspendedException to signal suspension
            raise PipelineSuspendedException(
                message=f"Pipeline suspended at steps: {', '.join(self._suspend_context.suspended_steps)}",
                checkpoint_id=checkpoint_id,
                suspended_steps=self._suspend_context.suspended_steps,
                suspend_info=suspend_info,
            )

        except PipelineSuspendedException:
            # Re-raise pipeline suspension - this is expected
            raise
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}", exc_info=True)
            raise

    async def resume_from_checkpoint(
        self,
        context: Union["PipelineContext", ExecutionContext],
        steps: List[StepConfig],
        checkpoint_id: Optional[str] = None,
    ) -> None:
        """Resume pipeline execution from a checkpoint.

        Args:
            context: Pipeline context (will be populated from checkpoint)
            steps: Pipeline steps configuration
            checkpoint_id: Specific checkpoint to resume from (latest if None)
        """
        logger.info("=== DAGExecutor.resume_from_checkpoint called ===")
        logger.info(f"Context type: {type(context).__name__}")
        logger.info(f"Has resume_data: {hasattr(context, 'resume_data')}")
        if hasattr(context, "resume_data"):
            resume_data_attr = getattr(context, "resume_data", None)
            logger.info(
                f"Resume data keys: {list(resume_data_attr.keys()) if resume_data_attr else 'None'}"
            )

        if not self._checkpoint_manager:
            raise ValueError("Checkpoint manager not configured")

        logger.info(f"Resuming from checkpoint: {checkpoint_id or 'latest'}")

        # Load checkpoint
        checkpoint = await self._checkpoint_manager.load_checkpoint(
            task_id=context.task_id, checkpoint_id=checkpoint_id
        )

        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        # Clean up any stale locks before attempting resume
        logger.info(f"Cleaning up stale locks for task {context.task_id}")
        await self._checkpoint_manager.cleanup_stale_locks(context.task_id)

        # Start resume process
        if not await self._checkpoint_manager.start_resume(checkpoint.checkpoint_id):
            raise RuntimeError("Another resume is already in progress")

        # Update task status to running
        if self._container and hasattr(context, "task_id"):
            try:
                task_manager = self._container.get_task_manager()
                task_manager.update_task_status(context.task_id, "running")
            except Exception as e:
                logger.warning(f"Failed to update task status to running: {e}")

        try:
            # Restore DAG state
            self._state = await self._checkpoint_manager.restore_dag_state(checkpoint)

            # Restore context
            await self._checkpoint_manager.restore_context(checkpoint, context)

            # Initialize suspend context for the resumed execution
            self._suspend_context = SuspendContext()

            # Inject resume data from ExecutionContext if available
            if hasattr(context, "resume_data"):
                resume_data = getattr(context, "resume_data", None)
                if resume_data and isinstance(resume_data, dict):
                    logger.info(
                        f"Found resume_data in context: {list(resume_data.keys())}"
                    )
                    for step_name, step_data in resume_data.items():
                        resume_data_key = f"{step_name}_resume_data"
                        context[resume_data_key] = step_data
                        logger.info(f"Injected {resume_data_key} into context")

            # Check for resume data for suspended steps
            for step_name in checkpoint.suspended_at_steps:
                resume_data_key = f"{step_name}_resume_data"
                if resume_data_key in context:
                    logger.info(f"Found resume data for step {step_name}")
                    logger.info(f"Context type: {type(context).__name__}")
                    step_resume_data = context[resume_data_key]

                    # Check if the step completed during suspension
                    if isinstance(step_resume_data, dict) and step_resume_data.get(
                        "complete"
                    ):
                        logger.info(
                            f"Step {step_name} completed during suspension, setting output"
                        )

                        # For agent steps, reconstruct the output
                        if "collected_data" in step_resume_data:
                            # Create a minimal transcript for downstream steps
                            collected_data = step_resume_data["collected_data"]
                            transcript = (
                                "User: I need to collect some information from you.\n\n"
                            )

                            if "full_name" in collected_data:
                                transcript += f"Assistant: What is your full name?\n\nUser: {collected_data['full_name']}\n\n"
                            if "email" in collected_data:
                                transcript += f"Assistant: What is your email address?\n\nUser: {collected_data['email']}\n\n"
                            if "physical_address" in collected_data:
                                transcript += f"Assistant: What is your physical address?\n\nUser: {collected_data['physical_address']}\n\n"
                            if "birth_date" in collected_data:
                                transcript += f"Assistant: What is your birth date?\n\nUser: {collected_data['birth_date']}\n\n"

                            transcript += "Assistant: Thank you! I have collected all the required information."

                            # Set the step output in context
                            step_output = {
                                "transcript": transcript,
                                "response": "Successfully collected all required information.",
                                "metadata": {
                                    "collected_data": collected_data,
                                    "pipeline_resumed": True,
                                },
                            }
                            context[step_name] = step_output
                            logger.info(
                                f"Set {step_name} output in context: {list(step_output.keys())}"
                            )
                            logger.info(
                                f"Context now has '{step_name}' with transcript: {'transcript' in step_output}"
                            )

                        # Mark step as completed and clear any error state
                        self._state.mark_step_completed_from_suspension(
                            step_name, clear_error=True
                        )

                        # Also remove from suspend context to prevent re-suspension
                        if (
                            self._suspend_context
                            and step_name in self._suspend_context.suspended_steps
                        ):
                            self._suspend_context.suspended_steps.remove(step_name)
                            logger.info(f"Removed {step_name} from suspend context")

                        logger.info(
                            f"Marked step {step_name} as completed with output set and error cleared"
                        )

                    else:
                        # Step didn't complete, mark as resumed (back to running)
                        # Clear any previous error for retry
                        if self._state.step_states[step_name].error:
                            logger.info(
                                f"Clearing error for step {step_name} before retry: "
                                f"{self._state.step_states[step_name].error}"
                            )
                            self._state.clear_step_error(step_name)

                        self._state.mark_step_resumed(step_name)

            # Continue execution
            await self.executeDAG(context, steps)

            # Complete checkpoint on successful resume
            await self._checkpoint_manager.complete_resume(checkpoint.checkpoint_id)

        except Exception as e:
            logger.error(f"Resume failed: {e}", exc_info=True)
            raise

    def _report_summary_progress(self) -> None:
        """Helper to send the final summary via progress callback."""
        if not self._progress_callback:
            return

        final_status = (
            StepStatus.COMPLETED if not self._state.failed_steps else StepStatus.FAILED
        )
        artifact_dir_path = None
        artifact_list = None

        # Attempt to get artifact details only on success
        if final_status == StepStatus.COMPLETED:
            if self._current_context and self._container:
                try:
                    task_id = self._current_context.task_id
                    artifact_manager = self._container.get_artifact_manager()
                    task_manager = self._container.get_task_manager()

                    # Get artifact directory path
                    artifact_dir = artifact_manager.get_task_dir(task_id)
                    artifact_dir_path = str(artifact_dir.resolve())

                    # Get list of generated artifacts
                    task_details = task_manager.get_task_details(task_id)
                    if task_details:
                        artifacts_dict = task_details.get("artifacts")
                        if artifacts_dict:
                            artifact_list = sorted(artifacts_dict.keys())
                        else:
                            artifact_list = []  # Explicitly empty list if no artifacts key/dict
                    else:
                        logger.warning(
                            f"Could not retrieve task details for task ID {task_id} to list artifacts for summary."
                        )

                except Exception as e:
                    logger.warning(
                        f"Failed to retrieve artifact details for summary report: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "Could not retrieve artifact details for summary: Context or Container not available."
                )

        # Send timing report as a special progress update
        self._progress_callback(
            StepProgress(
                step_name="pipeline_summary",
                status=final_status,
                error=None,  # Summary error isn't really applicable here
                start_time=self._state.start_time,
                end_time=self._state.end_time,
                artifact_dir_path=artifact_dir_path,  # Include artifact path
                artifact_list=artifact_list,  # Include artifact list
            )
        )

    def _print_summary(self) -> None:
        """Print execution summary (to debug log)."""
        if not self._steps:
            return

        summary = "\nPipeline Execution Summary:\n"
        summary += "=" * 60 + "\n"
        summary += f"{'Step':<30} {'Status':<10} {'Duration'}\n"
        summary += "-" * 60 + "\n"

        for step_name, step_state in self._state.step_states.items():
            status = step_state.status.upper()
            duration = "-"
            if step_state.start_time is not None:
                end_time = step_state.end_time or time.time()
                duration = f"{end_time - step_state.start_time:.2f}s"

            summary += f"{step_name:<30} {status:<10} {duration}\n"

        summary += "-" * 60 + "\n"
        execution_time = self._state.get_execution_time()
        summary += f"Total Duration: {execution_time:.2f}s\n"
        summary += f"Completed Steps: {len(self._state.completed_steps)}/{self._state.total_steps}\n"
        if self._state.failed_steps:
            summary += f"Failed Steps: {len(self._state.failed_steps)}\n"
        if self._state.skipped_steps:
            summary += f"Skipped Steps: {len(self._state.skipped_steps)}\n"

        # Only log at debug level
        logger.debug(summary)

    # The rest of the file (loop execution methods, etc.) stays the same
    # I'm showing only the changed methods above


# ---------------------------------------------------------------------------
# Local helper protocols / error types
# ---------------------------------------------------------------------------


# Define container protocol for type safety
class ContainerLike(Protocol):
    """Protocol for dependency containers used with DAGExecutor."""

    def get_step_registry(self) -> StepRegistry: ...

    def get_artifact_manager(self) -> Any: ...

    def get_task_manager(self) -> Any: ...
