"""Execution context for pipeline execution.

This module provides a formal execution context that carries all cross-cutting
concerns through the pipeline execution stack. ExecutionContext wraps and
delegates to PipelineContext to maintain backward compatibility while adding
execution-specific features like suspend/resume support.

ARCHITECTURAL DECISIONS:
1. ExecutionContext delegates to PipelineContext for all shared functionality
   - Avoids duplicating state management logic
   - Ensures consistent behavior between context types
   - Simplifies maintenance by having single source of truth

2. Uses __getattr__ delegation pattern instead of inheritance
   - Allows selective method override when needed
   - Maintains clear separation of concerns
   - Enables future refactoring without breaking changes

3. ExecutionContext adds execution-specific features not in PipelineContext
   - Suspend/resume support with checkpoint tracking
   - Formal execution state management
   - Loop iteration tracking for proper context isolation

This design follows the Decorator/Wrapper pattern where ExecutionContext
enhances PipelineContext functionality without modifying its interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, TypeVar

from src.core.pipeline_config import ExecutionConfiguration

if TYPE_CHECKING:
    from src.core.agent_spec import AgentSpec
    from src.core.artifact_manager import ArtifactManager
    from src.core.checkpoint_manager import CheckpointManager
    from src.core.context import PipelineContext
    from src.core.dependency_container import DependencyContainer
    from src.core.pipeline_config import PipelineConfiguration

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Formal execution context that wraps and delegates to PipelineContext.

    This context provides execution-specific features (suspend/resume, checkpointing)
    while delegating all standard pipeline operations to the wrapped PipelineContext.
    This ensures consistency and avoids state synchronization issues.

    DESIGN RATIONALE:
    - PipelineContext handles all pipeline-specific state and operations
    - ExecutionContext adds execution flow control and lifecycle management
    - Delegation pattern ensures single source of truth for shared state

    Attributes:
        _pipeline_context: The wrapped PipelineContext instance
        checkpoint_id: ID of checkpoint for resume scenarios
        resume_data: Data provided when resuming from suspension
        is_resume: Flag indicating if this is a resume execution
        checkpoint_manager: Manager for checkpoint operations
        loop_iteration: Current loop iteration for nested contexts
        step_name: Current step being executed
        pipeline_tools: Tools available to the pipeline
        pipeline_config: Pipeline-specific configuration
        agent_spec: Agent specification if in agent context
        session_id: Session identifier for tracking
    """

    # The wrapped context that handles pipeline operations
    _pipeline_context: Optional["PipelineContext"]

    # Execution-specific data not in PipelineContext
    checkpoint_id: Optional[str] = None
    resume_data: Optional[Dict[str, Any]] = None
    is_resume: bool = False
    checkpoint_manager: Optional["CheckpointManager"] = None

    # Additional execution context
    loop_iteration: Optional[int] = None
    step_name: Optional[str] = None
    pipeline_tools: Optional[Dict[str, Any]] = None
    pipeline_configuration: Optional[PipelineConfiguration] = None
    execution_config: ExecutionConfiguration = field(
        default_factory=ExecutionConfiguration
    )
    agent_spec: Optional["AgentSpec"] = None
    session_id: Optional[str] = None

    # Extra attributes for extensibility
    extras: Dict[str, Any] = field(default_factory=dict)

    # Legacy support - will be removed in future
    pipeline_config: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate that we have a pipeline context to wrap."""
        if self._pipeline_context is None:
            raise ValueError("ExecutionContext requires a PipelineContext to wrap")
        # After this point, _pipeline_context is guaranteed to be non-None
        # Type assertion for type checker
        assert self._pipeline_context is not None

    def spawn_child(self, **overrides: Any) -> "ExecutionContext":
        """Create a child context with selective overrides.

        This is useful when entering a new execution scope (e.g., a loop iteration
        or a specific step) where some context values need to change.

        Args:
            **overrides: Keyword arguments to override in the child context

        Returns:
            A new ExecutionContext with the specified overrides applied
        """
        # Create a new instance with same pipeline context but different execution params
        # Get current values, applying overrides
        return ExecutionContext(
            _pipeline_context=overrides.get(
                "_pipeline_context", self._pipeline_context
            ),
            checkpoint_id=overrides.get("checkpoint_id", self.checkpoint_id),
            resume_data=overrides.get("resume_data", self.resume_data),
            is_resume=overrides.get("is_resume", self.is_resume),
            checkpoint_manager=overrides.get(
                "checkpoint_manager", self.checkpoint_manager
            ),
            loop_iteration=overrides.get("loop_iteration", self.loop_iteration),
            step_name=overrides.get("step_name", self.step_name),
            pipeline_tools=overrides.get("pipeline_tools", self.pipeline_tools),
            pipeline_configuration=overrides.get(
                "pipeline_configuration", self.pipeline_configuration
            ),
            execution_config=overrides.get("execution_config", self.execution_config),
            pipeline_config=overrides.get("pipeline_config", self.pipeline_config),
            agent_spec=overrides.get("agent_spec", self.agent_spec),
            session_id=overrides.get("session_id", self.session_id),
            extras=overrides.get("extras", self.extras.copy()),
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to wrapped PipelineContext.

        This is the core of the delegation pattern. Any attribute or method
        not explicitly defined on ExecutionContext is forwarded to the
        wrapped PipelineContext instance.

        DESIGN NOTE:
        We use __getattr__ instead of inheritance to:
        1. Maintain clear separation between execution and pipeline concerns
        2. Allow selective method override without complex MRO issues
        3. Enable future refactoring of either context independently

        Args:
            name: Attribute or method name to access

        Returns:
            The attribute or method from the wrapped context

        Raises:
            AttributeError: If attribute not found on either context
        """
        # First check if it's in extras (for backward compatibility)
        if name in self.extras:
            return self.extras[name]

        # Then delegate to wrapped pipeline context
        if self._pipeline_context is None:
            raise RuntimeError(
                f"Cannot access attribute '{name}' - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        if hasattr(self._pipeline_context, name):
            attr = getattr(self._pipeline_context, name)
            # If it's a method, we return it directly since bound methods
            # already have the correct 'self' reference
            return attr

        # If not found anywhere, raise AttributeError
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """Support attribute assignment for both defined fields and extras.

        ExecutionContext fields are set directly, while undefined attributes
        are stored in extras for backward compatibility.
        """
        # Check if it's a defined dataclass field
        if name in self.__dataclass_fields__:
            object.__setattr__(self, name, value)
        else:
            # Store in extras for dynamic attributes
            if "extras" in self.__dict__:
                self.extras[name] = value
            else:
                # During initialization before extras exists
                object.__setattr__(self, name, value)

    # Properties that need special handling (can't be delegated via __getattr__)
    @property
    def task_id(self) -> str:
        """Get task ID from wrapped context."""
        if self._pipeline_context is None:
            raise RuntimeError(
                "Cannot access task_id - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context.task_id

    @property
    def artifact_manager(self) -> "ArtifactManager":
        """Get artifact manager from wrapped context."""
        if self._pipeline_context is None:
            raise RuntimeError(
                "Cannot access artifact_manager - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context.artifact_manager

    @property
    def artifacts_dir(self) -> Any:
        """Get artifacts directory from wrapped context."""
        if self._pipeline_context is None:
            raise RuntimeError(
                "Cannot access artifacts_dir - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context.artifacts_dir

    @property
    def has_provider(self) -> bool:
        """Check if a provider is configured in wrapped context."""
        if self._pipeline_context is None:
            raise RuntimeError(
                "Cannot access has_provider - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context.has_provider

    # Dict-like interface for backward compatibility
    # These must be defined explicitly since __getattr__ doesn't handle special methods
    def __getitem__(self, key: str) -> Any:
        """Support dict-like access, delegating to pipeline context."""
        # First check execution-specific attributes
        if hasattr(self, key) and key in self.__dataclass_fields__:
            return getattr(self, key)
        # Then check extras
        if key in self.extras:
            return self.extras[key]
        # Finally delegate to pipeline context
        if self._pipeline_context is None:
            raise RuntimeError(
                f"Cannot access key '{key}' - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Support dict-like assignment."""
        # Check if it's an execution-specific field
        if hasattr(self, key) and key in self.__dataclass_fields__:
            setattr(self, key, value)
        else:
            # Delegate to pipeline context for storage
            if self._pipeline_context is None:
                raise RuntimeError(
                    f"Cannot set key '{key}' - ExecutionContext pipeline context is None. "
                    "This indicates improper initialization or context corruption."
                )
            self._pipeline_context[key] = value

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        # Check execution-specific fields first
        if hasattr(self, key) and key in self.__dataclass_fields__:
            return True
        # Check extras
        if key in self.extras:
            return True
        # Delegate to pipeline context
        if self._pipeline_context is None:
            raise RuntimeError(
                f"Cannot check key '{key}' - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return key in self._pipeline_context

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict-like get method with optimized delegation."""
        # Optimize for the common case - delegate directly to pipeline context
        # This avoids the overhead of going through __getitem__ and exception handling

        # Check execution-specific fields first (fast path)
        if key in self.__dataclass_fields__ and hasattr(self, key):
            return getattr(self, key)

        # Check extras (fast path)
        if key in self.extras:
            return self.extras[key]

        # Delegate to pipeline context (most common case)
        if self._pipeline_context is None:
            raise RuntimeError(
                f"Cannot get key '{key}' - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return self._pipeline_context.get(key, default)

    # Execution-specific methods (not delegated)
    def get_resume_data(self) -> Dict[str, Any]:
        """Get resume data for suspension handling.

        Returns:
            Resume data dictionary or empty dict if none
        """
        return self.resume_data or {}

    def get_checkpoint_dir(self) -> str:
        """Get the checkpoint directory for this task.

        Returns:
            Path to the checkpoint directory
        """
        # Checkpoints are stored in a subdirectory of the artifacts directory
        checkpoint_dir = self.artifact_manager.get_artifact_path(
            self.task_id, "checkpoints"
        )
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return str(checkpoint_dir)

    def get_container(self) -> Optional["DependencyContainer"]:
        """Get the dependency container.

        This is stored in the pipeline context but we provide a convenience method.

        Returns:
            The dependency container if available
        """
        # Access the private attribute of pipeline context
        # This is one of the few cases where we need to access internals
        if self._pipeline_context is None:
            raise RuntimeError(
                "Cannot access container - ExecutionContext pipeline context is None. "
                "This indicates improper initialization or context corruption."
            )
        return getattr(self._pipeline_context, "_container", None)

    # Configuration access methods
    def get_pipeline_config(self) -> Optional[PipelineConfiguration]:
        """Get the pipeline configuration object.

        Returns:
            Pipeline configuration if available
        """
        return self.pipeline_configuration

    def get_execution_config(self) -> ExecutionConfiguration:
        """Get the execution configuration object.

        Returns:
            Execution configuration (always available)
        """
        return self.execution_config

    def get_config_parameter(self, key: str, default: Any = None) -> Any:
        """Get parameter from pipeline configuration.

        Args:
            key: Parameter key
            default: Default value if not found

        Returns:
            Parameter value or default
        """
        # Check pipeline configuration first
        if self.pipeline_configuration and self.pipeline_configuration.has_parameter(
            key
        ):
            return self.pipeline_configuration.get_parameter(key)

        # Fall back to legacy pipeline_config dict
        if self.pipeline_config and key in self.pipeline_config:
            return self.pipeline_config[key]

        # Fall back to wrapped context
        if key in self:
            return self[key]

        # Return default if not found anywhere
        return default

    def set_config_parameter(self, key: str, value: Any) -> None:
        """Set parameter in pipeline configuration.

        Args:
            key: Parameter key
            value: Parameter value
        """
        if self.pipeline_configuration:
            self.pipeline_configuration.set_parameter(key, value)
        else:
            # Fall back to setting in context
            self[key] = value


def create_execution_context(
    task_id: str,
    container: "DependencyContainer",
    pipeline_context: Optional["PipelineContext"] = None,
    **kwargs: Any,
) -> ExecutionContext:
    """Factory function to create an ExecutionContext.

    This factory ensures proper initialization of the execution context
    with all required dependencies. It creates or reuses a PipelineContext
    and wraps it with execution-specific features.

    DESIGN NOTE:
    This factory is the recommended way to create ExecutionContext instances
    as it ensures proper initialization of the delegation relationship.

    Args:
        task_id: Unique identifier for the task
        container: Dependency injection container
        pipeline_context: Optional existing PipelineContext to wrap
        **kwargs: Additional execution-specific parameters like:
            - resume_data: Data for resuming from suspension
            - is_resume: Boolean flag for resume scenarios
            - checkpoint_id: ID of checkpoint being resumed
            - loop_iteration: Current loop iteration
            - step_name: Current step being executed

    Returns:
        Configured ExecutionContext instance wrapping a PipelineContext
    """
    # If no pipeline context provided, create one
    if pipeline_context is None:
        from src.core.context import PipelineContext

        artifact_manager = container.get_artifact_manager()
        type_registry = container.get_type_registry()

        pipeline_context = PipelineContext(
            task_id=task_id,
            artifact_manager=artifact_manager,
            type_registry=type_registry,
        )
        # Set the container reference in pipeline context
        pipeline_context.set_container(container)

    # Extract execution-specific params from kwargs
    execution_params = {
        "_pipeline_context": pipeline_context,
        "checkpoint_id": kwargs.pop("checkpoint_id", None),
        "resume_data": kwargs.pop("resume_data", None),
        "is_resume": kwargs.pop("is_resume", False),
        "checkpoint_manager": kwargs.pop("checkpoint_manager", None)
        or container.get_checkpoint_manager(),
        "loop_iteration": kwargs.pop("loop_iteration", None),
        "step_name": kwargs.pop("step_name", None),
        "pipeline_tools": kwargs.pop("pipeline_tools", None),
        "pipeline_configuration": kwargs.pop("pipeline_configuration", None),
        "execution_config": kwargs.pop("execution_config", None)
        or ExecutionConfiguration(),
        "agent_spec": kwargs.pop("agent_spec", None),
        "session_id": kwargs.pop("session_id", None),
        # Legacy support
        "pipeline_config": kwargs.pop("pipeline_config", None),
    }

    # Any remaining kwargs go into extras
    if kwargs:
        execution_params["extras"] = kwargs

    # Create and return the execution context
    return ExecutionContext(**execution_params)
