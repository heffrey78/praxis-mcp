import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from src.core.context import PipelineContext
from src.core.errors import PipelineSuspendedException
from src.core.step_config import LoopConfig, StepConfig

# from src.core.dag_executor import DAGExecutor # Moved to TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.dag_executor import ContainerLike
    from src.core.execution_context import ExecutionContext
    from src.core.step_registry import StepRegistry

logger = logging.getLogger(__name__)


class LoopExecutionStrategy:
    """
    Manages the execution of loop bodies within a DAG.

    This class handles iterating over collections, counts, or conditions,
    setting up the iteration-specific context, and invoking the execution
    of the loop body using a DAGExecutor instance.
    """

    def __init__(
        self,
        parent_executor_container: Union["ContainerLike", "StepRegistry"],
        parent_executor_max_workers: int,
        parent_executor_use_connections: bool,
        progress_callback: Optional[Callable[[Any], None]] = None,
        checkpoint_manager: Optional[Any] = None,
    ) -> None:
        self.parent_executor_container = parent_executor_container
        self.parent_executor_max_workers = parent_executor_max_workers
        self.parent_executor_use_connections = parent_executor_use_connections
        self.progress_callback = progress_callback
        self.checkpoint_manager = checkpoint_manager

    def _create_synthetic_body(self, step: StepConfig) -> List[StepConfig]:
        """Create a synthetic loop body from the step's own configuration."""
        if step.plugin == "pipeline_loop" or (
            step.loop_config
            and isinstance(step.loop_config, LoopConfig)
            and step.loop_config.body
        ):
            # Already has a body or is a pipeline_loop - no synthesis needed
            return (
                step.loop_config.body
                if isinstance(step.loop_config, LoopConfig)
                else []
            )

        # Create a synthetic step that mirrors the parent step
        synthetic_step = StepConfig(
            name=f"{step.name}_iteration",
            plugin=step.plugin,
            config=step.config.copy() if step.config else {},
            depends_on=[],  # No dependencies within loop iteration
            fail_on_error=step.fail_on_error,
        )

        logger.debug(f"Created synthetic body for direct plugin loop '{step.name}'")
        return [synthetic_step]

    async def execute_loop(
        self,
        parent_context: Union[PipelineContext, "ExecutionContext"],
        step: StepConfig,
    ) -> None:
        """Main entry point to execute a loop step."""
        if not hasattr(step, "loop_config") or step.loop_config is None:
            logger.error(f"Loop step {step.name} missing loop_config")
            raise ValueError(f"Loop step {step.name} is missing loop configuration")

        loop_config = step.loop_config
        loop_context = parent_context.copy()
        if hasattr(loop_context, "clear_saved_artifacts"):
            loop_context.clear_saved_artifacts()

        any_iteration_failed = False

        try:
            # Handle dict-based loop configs by converting to LoopConfig
            if isinstance(loop_config, dict):
                loop_config = LoopConfig(**loop_config)

            if loop_config.condition:
                any_iteration_failed = await self._execute_condition_based_loop(
                    parent_context, step, loop_context, loop_config
                )
            else:
                any_iteration_failed = await self._execute_collection_or_count_loop(
                    parent_context, step, loop_context, loop_config
                )

            # Merge final loop_context state back to parent context
            logger.debug(
                f"Merging final loop context state back into parent context for loop '{step.name}'"
            )
            # Get data from loop_context using public method
            loop_data = loop_context.get_data()
            parent_context.update(loop_data)

        except PipelineSuspendedException:
            # IMPORTANT: Merge loop context back to parent before propagating suspension
            # This ensures partial loop results are preserved in the checkpoint
            logger.info(
                f"Loop '{step.name}' suspended - merging partial loop state to parent context"
            )
            # Get data from loop_context using public method
            loop_data = loop_context.get_data()
            parent_context.update(loop_data)
            # Re-raise to propagate suspension
            raise
        except Exception as e:
            logger.error(
                f"Error executing loop step {step.name}: {str(e)}", exc_info=True
            )
            # The DAGState in DAGExecutor will handle marking the step as failed.
            # We re-raise here so the DAGExecutor can catch it and update its state.
            raise

        if any_iteration_failed:
            # This exception will be caught by DAGExecutor and used to mark the loop step as FAILED.
            raise Exception(f"One or more iterations failed in loop step {step.name}")

    async def _execute_collection_or_count_loop(
        self,
        parent_context: Union[PipelineContext, "ExecutionContext"],
        step: StepConfig,
        loop_context: Union[PipelineContext, "ExecutionContext"],
        loop_config: LoopConfig,
    ) -> bool:
        any_iteration_failed = False
        items = []
        if loop_config.collection:
            collection_name = loop_config.collection
            items = parent_context.get(
                collection_name, []
            )  # Use parent_context to get initial collection
            logger.info(
                f"Loop {step.name}: Iterating over collection '{collection_name}'. Items found: {len(items)}."
            )

        if not items and loop_config.count is not None:
            logger.info(
                f"Loop {step.name}: Iterating {loop_config.count} times (count-based)."
            )
            items = list(range(loop_config.count))

        if not items:
            logger.warning(f"Loop step {step.name}: No items to iterate over.")
            return False  # No iterations, so no failures

        # Determine effective body - use existing or create synthetic
        effective_body = self._create_synthetic_body(step)

        if not effective_body:
            logger.warning(f"Loop step {step.name} has no executable body")
            return False

        # Check if we're resuming and should skip already-processed items
        start_index = 0
        # Check if we're resuming from a specific iteration
        loop_iteration = loop_context.get_loop_iteration_index()
        if loop_iteration is not None:
            # We're resuming - check which items have been processed
            processed_items = []
            for idx in range(len(items)):
                # Check if this item was already processed
                # This assumes plugins mark items as processed with a pattern like "item_{idx}_processed"
                if loop_context.get(f"item_{items[idx]}_processed", False):
                    processed_items.append(idx)

            if processed_items:
                # Start from the next unprocessed item
                start_index = len(processed_items)
                logger.info(
                    f"Loop {step.name} resuming: Skipping {len(processed_items)} already-processed items. "
                    f"Starting from index {start_index}"
                )

        for i, item_data in enumerate(items):
            # Skip already-processed items
            if i < start_index:
                logger.debug(
                    f"Skipping already-processed item at index {i} for loop {step.name}"
                )
                continue

            logger.info(
                f"Starting loop iteration {i + 1}/{len(items)} for step {step.name}"
            )
            iteration_context = (
                loop_context.copy()
            )  # Use a copy of loop_context for each iteration

            if loop_config.item_name:
                iteration_context[loop_config.item_name] = item_data
            if loop_config.index_name:
                iteration_context[loop_config.index_name] = i

            # Record iteration index and step name via public API
            iteration_context.set_loop_context(step.name, i)
            logger.info(
                f"Loop {step.name}: Set loop context (step={step.name}, index={i}) on context id={id(iteration_context)}"
            )

            try:
                # Single execution path for all loop patterns
                await self._run_loop_body(iteration_context, effective_body)
                logger.info(f"Completed loop iteration {i + 1} of {step.name}")

                # IMPORTANT: Merge iteration context back to loop context
                # This preserves accumulated state across iterations
                # Get data from iteration_context using public method
                iteration_data = iteration_context.get_data()
                loop_context.update(iteration_data)
                logger.debug(
                    f"Merged iteration {i + 1} results back to loop context for {step.name}"
                )
            except PipelineSuspendedException:
                # IMPORTANT: Even on suspension, merge context changes
                # This ensures partial results are preserved
                # Get data from iteration_context using public method
                iteration_data = iteration_context.get_data()
                loop_context.update(iteration_data)
                logger.info(
                    f"Loop iteration {i + 1} for {step.name} requested suspension - merged partial results"
                )
                # Allow suspension to propagate up
                raise  # Re-raise to propagate suspension
            except Exception as e:
                logger.error(
                    f"Error in loop iteration {i + 1} for {step.name}: {str(e)}",
                    exc_info=True,
                )
                any_iteration_failed = True
                if loop_config.fail_fast:
                    logger.warning(
                        f"Fail-fast enabled, stopping loop execution for {step.name} after iteration {i + 1} failure."
                    )
                    raise  # Re-raise to stop the loop immediately

            if loop_config.delay and i < len(items) - 1:
                logger.info(
                    f"Delaying {loop_config.delay}ms before next iteration of {step.name}"
                )
                await asyncio.sleep(loop_config.delay / 1000)

        # Update the main loop_context with results if a result_name is specified
        # This typically happens if loop body steps are designed to populate a specific key
        if loop_config.result_name and loop_config.result_name in loop_context:
            # The parent_context will be updated with loop_context._data at the end of execute_loop
            logger.info(
                f"Loop {step.name}: Result '{loop_config.result_name}' will be available in parent context."
            )
        elif loop_config.result_name:
            logger.warning(
                f"Loop {step.name}: result_name '{loop_config.result_name}' was specified, but not found in the final loop context."
            )

        return any_iteration_failed

    async def _execute_condition_based_loop(
        self,
        parent_context: Union[
            PipelineContext, "ExecutionContext"
        ],  # parent_context for initial condition check if needed
        step: StepConfig,
        loop_context: Union[
            PipelineContext, "ExecutionContext"
        ],  # loop_context is mutated and carries state between iterations
        loop_config: LoopConfig,
    ) -> bool:
        any_iteration_failed = False
        loop_counter = 0
        max_iterations = loop_config.max_iterations

        # Determine effective body - use existing or create synthetic
        effective_body = self._create_synthetic_body(step)

        if not effective_body:
            logger.warning(f"Loop step {step.name} has no executable body")
            return False

        while loop_counter < max_iterations:
            # Condition should be evaluated against the current state of loop_context
            if not loop_config.condition:
                # This shouldn't happen as we only call this method when condition is set
                raise ValueError(
                    f"Loop {step.name}: No condition specified for condition-based loop"
                )
            condition_value = loop_context.get(loop_config.condition)
            logger.info(
                f"Condition-based loop {step.name} (iteration {loop_counter + 1}/{max_iterations}): "
                f"Condition '{loop_config.condition}' evaluated to: {condition_value}"
            )

            if not condition_value:
                logger.info(
                    f"Loop {step.name}: Condition '{loop_config.condition}' is false. Exiting loop."
                )
                break

            logger.info(
                f"Starting condition-based loop iteration {loop_counter + 1} for step {step.name}"
            )
            iteration_context = (
                loop_context.copy()
            )  # Fresh context copy for this iteration's execution
            if loop_config.item_name:
                iteration_context[loop_config.item_name] = loop_counter
            if loop_config.index_name:
                iteration_context[loop_config.index_name] = loop_counter

            # Record iteration index and step name via public API
            iteration_context.set_loop_context(step.name, loop_counter)

            try:
                # Single execution path for all loop patterns
                await self._run_loop_body(iteration_context, effective_body)
                # IMPORTANT: Update loop_context with the results from this iteration's execution,
                # so the condition for the *next* iteration is evaluated on the updated state.
                # Get data from iteration_context using public method
                iteration_data = iteration_context.get_data()
                loop_context.update(iteration_data)
                logger.info(
                    f"Completed condition-based loop iteration {loop_counter + 1} of {step.name}"
                )
            except PipelineSuspendedException:
                # Allow suspension to propagate up
                logger.info(
                    f"Condition-based loop iteration {loop_counter + 1} for {step.name} requested suspension"
                )
                raise  # Re-raise to propagate suspension
            except Exception as e:
                logger.error(
                    f"Error in condition-based loop iteration {loop_counter + 1} for {step.name}: {str(e)}",
                    exc_info=True,
                )
                any_iteration_failed = True
                # Update loop_context even on failure, in case partial results are important for condition
                # Get data from iteration_context using public method
                iteration_data = iteration_context.get_data()
                loop_context.update(iteration_data)
                if loop_config.fail_fast:
                    logger.warning(
                        f"Fail-fast enabled for {step.name}, stopping loop after iteration {loop_counter + 1} failure."
                    )
                    raise  # Re-raise to stop the loop

            loop_counter += 1
            if loop_config.delay and loop_counter < max_iterations:
                # Check condition again before sleeping if it's the last possible iteration
                # loop_config.condition is guaranteed to be non-None here
                next_condition_value = loop_context.get(loop_config.condition)
                if next_condition_value:  # Only delay if we might continue
                    logger.info(
                        f"Delaying {loop_config.delay}ms before next iteration of {step.name}"
                    )
                    await asyncio.sleep(loop_config.delay / 1000)

        if loop_counter >= max_iterations:
            logger.warning(
                f"Loop '{step.name}' reached max iterations ({max_iterations}). Condition: {loop_config.condition}={loop_context.get(loop_config.condition) if loop_config.condition else 'None'}"
            )

        if loop_config.result_name and loop_config.result_name in loop_context:
            logger.info(
                f"Loop {step.name}: Result '{loop_config.result_name}' will be available in parent context."
            )
        elif loop_config.result_name:
            logger.warning(
                f"Loop {step.name}: result_name '{loop_config.result_name}' was specified, but not found in the final loop context."
            )

        return any_iteration_failed

    async def _run_loop_body(
        self,
        context_for_body: Union[PipelineContext, "ExecutionContext"],
        body_steps: List[StepConfig],
    ) -> None:
        """Executes the body of a loop using a new DAGExecutor instance."""
        # This import needs to be here to avoid circular dependency at module load time.
        # It's safe because this method is only called at runtime after all modules are loaded.
        from src.core.dag_executor import DAGExecutor

        logger.debug(
            f"Loop Body Execution: Creating new DAGExecutor for loop body. Context ID: {id(context_for_body)}"
        )

        # Ensure the container reference is valid
        if not self.parent_executor_container:
            raise RuntimeError(
                "LoopExecutionStrategy is missing a valid container reference from parent DAGExecutor."
            )

        body_executor = DAGExecutor(
            container=self.parent_executor_container,
            max_workers=self.parent_executor_max_workers,
            use_connections=self.parent_executor_use_connections,
            checkpoint_manager=self.checkpoint_manager,
        )
        if self.progress_callback:
            body_executor.set_progress_callback(self.progress_callback)

        # The context_for_body already has loop-specific variables (_loop_iteration_index, item_name, index_name)
        # and is a copy of the main loop_context, which itself is a copy of the parent_context.
        # The DAGExecutor's executeDAG method will further process this context, potentially creating
        # a new EnhancedContext if connections are enabled for the body steps.
        await body_executor.executeDAG(context_for_body, body_steps)
        logger.debug(
            "Loop Body Execution: Finished executing loop body with new DAGExecutor."
        )
