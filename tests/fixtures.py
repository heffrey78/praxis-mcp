"""Test fixtures and builders for simplified test setup.

This module provides factory functions and builders to reduce test complexity
and eliminate repetitive boilerplate code across the test suite.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from unittest.mock import AsyncMock, MagicMock, Mock

from src.core.dialogue_config import DialogueConfiguration, DialogueMode
from src.core.execution_context import ExecutionContext, create_execution_context
from src.core.file_loader import InMemoryFileLoader
from src.core.pipeline_config import (
    ExecutionConfiguration,
    ExecutionMode,
    PipelineConfiguration,
    ResumeConfiguration,
    ResumeStrategy,
    StepConfiguration,
)
from src.core.plugin_manifest import PluginManifest


class StepBuilder:
    """Builder for creating StepConfiguration objects with sensible defaults."""

    def __init__(self, name: str = "test_step", plugin: str = "test_plugin") -> None:
        """Initialize step builder with defaults."""
        self._name = name
        self._plugin = plugin
        self._dependencies: List[str] = []
        self._condition: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._retry_count = 0
        self._timeout: Optional[int] = None
        self._skip_on_failure = False
        self._loop_config: Optional[Dict[str, Any]] = None

    def with_dependencies(self, *deps: str) -> "StepBuilder":
        """Add dependencies to the step."""
        self._dependencies.extend(deps)
        return self

    def with_config(self, **kwargs: Any) -> "StepBuilder":
        """Add configuration parameters."""
        self._config.update(kwargs)
        return self

    def with_condition(self, condition: str) -> "StepBuilder":
        """Set execution condition."""
        self._condition = condition
        return self

    def with_retry(self, count: int = 3) -> "StepBuilder":
        """Enable retries."""
        self._retry_count = count
        return self

    def with_timeout(self, seconds: int) -> "StepBuilder":
        """Set timeout."""
        self._timeout = seconds
        return self

    def with_loop(self, max_iterations: int = 10) -> "StepBuilder":
        """Enable looping."""
        self._loop_config = {"max_iterations": max_iterations}
        return self

    def build(self) -> StepConfiguration:
        """Build the step configuration."""
        return StepConfiguration(
            name=self._name,
            plugin=self._plugin,
            dependencies=self._dependencies,
            condition=self._condition,
            config=self._config,
            retry_count=self._retry_count,
            timeout=self._timeout,
            skip_on_failure=self._skip_on_failure,
            loop_config=self._loop_config,
        )


class PipelineBuilder:
    """Builder for creating PipelineConfiguration objects."""

    def __init__(
        self,
        pipeline_id: str = "test-pipeline",
        name: str = "Test Pipeline",
        task_id: str = "test-task-123",
    ) -> None:
        """Initialize pipeline builder."""
        self._pipeline_id = pipeline_id
        self._name = name
        self._task_id = task_id
        self._mode = ExecutionMode.NORMAL
        self._parameters: Dict[str, Any] = {}
        self._file_parameters: Set[str] = set()
        self._steps: List[StepConfiguration] = []
        self._finally_steps: List[StepConfiguration] = []
        self._dialogue_config: Optional[DialogueConfiguration] = None
        self._resume_config: Optional[ResumeConfiguration] = None
        self._quiet = False

    def with_mode(self, mode: ExecutionMode) -> "PipelineBuilder":
        """Set execution mode."""
        self._mode = mode
        return self

    def with_parameters(self, **params: Any) -> "PipelineBuilder":
        """Add parameters."""
        self._parameters.update(params)
        return self

    def with_file_parameters(self, *params: str) -> "PipelineBuilder":
        """Mark parameters as file parameters."""
        self._file_parameters.update(params)
        return self

    def with_step(self, step: StepConfiguration) -> "PipelineBuilder":
        """Add a step."""
        self._steps.append(step)
        return self

    def with_steps(self, *steps: StepConfiguration) -> "PipelineBuilder":
        """Add multiple steps."""
        self._steps.extend(steps)
        return self

    def with_dialogue(
        self,
        mode_or_config: Union[
            DialogueMode, DialogueConfiguration
        ] = DialogueMode.DIRECT,
        responses: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> "PipelineBuilder":
        """Add dialogue configuration.

        Can accept either:
        - A DialogueConfiguration object directly
        - DialogueMode and other parameters to construct one
        """
        if isinstance(mode_or_config, DialogueConfiguration):
            self._dialogue_config = mode_or_config
        else:
            # Construct DialogueConfiguration from parameters
            config_params: Dict[str, Any] = {"mode": mode_or_config}
            if responses is not None:
                config_params["responses"] = responses
            # Add any additional keyword arguments
            config_params.update(kwargs)
            self._dialogue_config = DialogueConfiguration(**config_params)
        return self

    def with_resume(
        self,
        checkpoint_id: str = "checkpoint-123",
        strategy: ResumeStrategy = ResumeStrategy.CHECKPOINT,
    ) -> "PipelineBuilder":
        """Add resume configuration."""
        self._resume_config = ResumeConfiguration(
            checkpoint_id=checkpoint_id, strategy=strategy
        )
        return self

    def quiet(self) -> "PipelineBuilder":
        """Enable quiet mode."""
        self._quiet = True
        return self

    def build(self) -> PipelineConfiguration:
        """Build the pipeline configuration."""
        return PipelineConfiguration(
            pipeline_id=self._pipeline_id,
            pipeline_name=self._name,
            task_id=self._task_id,
            mode=self._mode,
            quiet=self._quiet,
            parameters=self._parameters,
            file_parameters=self._file_parameters,
            steps=self._steps,
            finally_steps=self._finally_steps,
            dialogue_config=self._dialogue_config,
            resume_config=self._resume_config,
        )


class MockFactory:
    """Factory for creating common mock objects."""

    @staticmethod
    def container(
        task_manager: Optional[Mock] = None,
        artifact_manager: Optional[Mock] = None,
        type_registry: Optional[Mock] = None,
        checkpoint_manager: Optional[Mock] = None,
    ) -> Mock:
        """Create a mock dependency container."""
        container = MagicMock()
        container.get_task_manager.return_value = (
            task_manager or MockFactory.task_manager()
        )
        container.get_artifact_manager.return_value = (
            artifact_manager or MockFactory.artifact_manager()
        )
        container.get_type_registry.return_value = (
            type_registry or MockFactory.type_registry()
        )
        container.get_checkpoint_manager.return_value = (
            checkpoint_manager or MockFactory.checkpoint_manager()
        )
        return container

    @staticmethod
    def task_manager() -> Mock:
        """Create a mock task manager."""
        manager = AsyncMock()
        manager.create_task = AsyncMock(return_value="test-task-123")
        manager.update_task = AsyncMock()
        manager.complete_task = AsyncMock()
        manager.fail_task = AsyncMock()
        manager.update_checkpoint = AsyncMock()
        return manager

    @staticmethod
    def artifact_manager(base_dir: Path = Path("/tmp/artifacts")) -> Mock:
        """Create a mock artifact manager."""
        manager = MagicMock()
        manager.get_artifact_path.return_value = base_dir / "test-task-123"
        manager.save_artifact = AsyncMock()
        manager.load_artifact = AsyncMock()
        manager.list_artifacts = AsyncMock(return_value=[])
        return manager

    @staticmethod
    def type_registry() -> Mock:
        """Create a mock type registry."""
        registry = MagicMock()
        registry.get_type = MagicMock(return_value=str)
        registry.register_type = MagicMock()
        return registry

    @staticmethod
    def checkpoint_manager() -> Mock:
        """Create a mock checkpoint manager."""
        manager = AsyncMock()
        manager.save_checkpoint = AsyncMock()
        manager.load_checkpoint = AsyncMock()
        manager.list_checkpoints = AsyncMock(return_value=[])
        return manager

    @staticmethod
    def plugin(
        name: str = "test_plugin",
        manifest: Optional[PluginManifest] = None,
        run_result: Any = "test output",
    ) -> Mock:
        """Create a mock plugin."""
        plugin = MagicMock()
        if manifest is None:
            from src.core.plugin_manifest import (
                PluginCompatibility,
                PluginEntrypoint,
                PluginMetadata,
            )

            manifest = PluginManifest(
                api_version="praxis/v1",
                kind="PluginManifest",
                metadata=PluginMetadata(
                    name=name,
                    description=f"Test {name} plugin",
                    author="Test Author",
                    version="1.0.0",
                ),
                compatibility=PluginCompatibility(
                    praxis=">=1.0.0,<2.0.0",
                    python=">=3.8,<4.0",
                ),
                entrypoints=[
                    PluginEntrypoint(
                        name=name,
                        module=f"test.plugins.{name}",
                        class_name=f"{name.title()}Plugin",
                    )
                ],
                signature=None,
            )
        plugin.manifest = manifest
        plugin.run = AsyncMock(return_value=run_result)
        plugin.stream = AsyncMock()
        return plugin

    @staticmethod
    def dialogue_provider(responses: Optional[List[str]] = None) -> Mock:
        """Create a mock dialogue provider."""
        provider = MagicMock()
        provider.responses = responses or ["Yes", "No", "/exit"]
        provider.response_index = 0

        def get_response(*args: Any, **kwargs: Any) -> str:
            if provider.response_index < len(provider.responses):
                response = provider.responses[provider.response_index]
                provider.response_index += 1
                return response
            return "/exit"

        provider.get_response = MagicMock(side_effect=get_response)
        provider.cleanup = MagicMock()
        return provider


class TestDataFactory:
    """Factory for creating common test data."""

    @staticmethod
    def pipeline_definition(
        pipeline_id: str = "test-pipeline",
        name: str = "Test Pipeline",
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Create a mock pipeline definition."""
        definition = MagicMock()
        definition.id = pipeline_id
        definition.name = name
        definition.steps = steps or [
            {"name": "step1", "plugin": "plugin1"},
            {"name": "step2", "plugin": "plugin2", "dependencies": ["step1"]},
        ]
        definition.finally_steps = []
        definition.parameters = {}
        return definition

    @staticmethod
    def execution_context(
        task_id: str = "test-task-123",
        container: Optional[Mock] = None,
        **kwargs: Any,
    ) -> ExecutionContext:
        """Create an execution context with sensible defaults."""
        if container is None:
            container = MockFactory.container()

        return create_execution_context(
            task_id=task_id,
            container=container,
            **kwargs,
        )

    @staticmethod
    def file_loader(files: Optional[Dict[str, str]] = None) -> InMemoryFileLoader:
        """Create an in-memory file loader with test files."""
        loader = InMemoryFileLoader()
        if files:
            for path, content in files.items():
                loader.add_file(str(path), content)
        return loader


# Convenience functions for quick test setup
def simple_pipeline() -> PipelineConfiguration:
    """Create a simple two-step pipeline configuration."""
    return (
        PipelineBuilder()
        .with_steps(
            StepBuilder("fetch", "fetcher").build(),
            StepBuilder("process", "processor").with_dependencies("fetch").build(),
        )
        .build()
    )


def interactive_pipeline() -> PipelineConfiguration:
    """Create an interactive pipeline with dialogue."""
    return (
        PipelineBuilder()
        .with_mode(ExecutionMode.INTERACTIVE)
        .with_dialogue(DialogueMode.DIRECT, ["Yes", "No"])
        .with_steps(
            StepBuilder("input", "user_input").build(),
            StepBuilder("process", "processor").with_dependencies("input").build(),
        )
        .build()
    )


def async_test_context(container: Optional[Mock] = None) -> ExecutionContext:
    """Create execution context suitable for async tests."""
    return TestDataFactory.execution_context(
        container=container,
        execution_config=ExecutionConfiguration(
            max_concurrent_steps=5,
            use_thread_pool=True,
            fail_fast=False,
        ),
    )
