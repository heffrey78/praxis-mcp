"""Specialized mock factories for complex test scenarios.

This module provides factory functions for creating mocks of complex
components like pipeline executors, plugin systems, and agent interactions.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.core.errors import PipelineSuspendedException
from src.core.pipeline_config import PipelineConfiguration, StepConfiguration
from src.core.plugin_manifest import PluginManifest


class PipelineExecutorMockFactory:
    """Factory for creating pipeline executor mocks."""

    @staticmethod
    def create_executor(
        execute_result: Any = None,
        suspend_on_step: Optional[str] = None,
    ) -> Mock:
        """Create a mock pipeline executor."""
        if execute_result is None:
            execute_result = {"status": "completed"}
        executor = AsyncMock()

        if suspend_on_step:
            # Simulate suspension on specific step
            async def execute_with_suspension(*args: Any, **kwargs: Any) -> Any:
                step_name = kwargs.get("step_name", "")
                if step_name == suspend_on_step:
                    raise PipelineSuspendedException(
                        message=f"Suspended at {step_name}",
                        checkpoint_id="test-checkpoint",
                        suspended_steps=[step_name],
                        suspend_info={"reason": f"Suspended at {step_name}"},
                    )
                return execute_result

            executor.execute = AsyncMock(side_effect=execute_with_suspension)
        else:
            executor.execute = AsyncMock(return_value=execute_result)

        executor.run_step = AsyncMock(return_value={"output": "step result"})
        executor.validate_pipeline = AsyncMock(return_value=True)

        return executor

    @staticmethod
    def create_orchestrator(
        pipeline_config: Optional[PipelineConfiguration] = None,
    ) -> Mock:
        """Create a mock pipeline orchestrator."""
        orchestrator = MagicMock()
        orchestrator.pipeline_config = pipeline_config
        orchestrator.execute = AsyncMock(return_value={"status": "success"})
        orchestrator.prepare_context = AsyncMock()
        orchestrator.finalize = AsyncMock()

        return orchestrator


class PluginMockFactory:
    """Factory for creating plugin-related mocks."""

    @staticmethod
    def create_plugin_instance(
        name: str = "test_plugin",
        run_result: Any = "test output",
        supports_streaming: bool = False,
    ) -> Mock:
        """Create a mock plugin instance."""
        plugin = MagicMock()
        from src.core.plugin_manifest import (
            PluginCompatibility,
            PluginEntrypoint,
            PluginMetadata,
        )

        plugin.manifest = PluginManifest(
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
        plugin.run = AsyncMock(return_value=run_result)
        if supports_streaming:
            plugin.stream = AsyncMock()

        return plugin

    @staticmethod
    def create_plugin_registry(
        plugins: Optional[Dict[str, Mock]] = None,
    ) -> Mock:
        """Create a mock plugin registry."""
        registry = MagicMock()

        if plugins is None:
            plugins = {
                "test_plugin": PluginMockFactory.create_plugin_instance(),
                "processor": PluginMockFactory.create_plugin_instance("processor"),
            }

        registry.get_plugin = MagicMock(side_effect=lambda name: plugins.get(name))
        registry.list_plugins = MagicMock(return_value=list(plugins.keys()))
        registry.register_plugin = MagicMock()

        return registry

    @staticmethod
    def create_plugin_invoker(
        invoke_result: Any = None,
    ) -> Mock:
        """Create a mock plugin invoker."""
        if invoke_result is None:
            invoke_result = {"output": "test result"}
        invoker = AsyncMock()
        invoker.invoke = AsyncMock(return_value=invoke_result)
        invoker.prepare_input = AsyncMock()
        invoker.validate_output = AsyncMock(return_value=True)

        return invoker


class DialogueMockFactory:
    """Factory for dialogue-related mocks."""

    @staticmethod
    def create_cli_handler(
        user_inputs: Optional[List[str]] = None,
    ) -> Mock:
        """Create a mock CLI handler."""
        handler = MagicMock()

        if user_inputs is None:
            user_inputs = ["Yes", "No", "/exit"]

        handler.input_queue = user_inputs.copy()
        handler.input_index = 0

        def get_input(prompt: str = "") -> str:
            if handler.input_index < len(handler.input_queue):
                result = handler.input_queue[handler.input_index]
                handler.input_index += 1
                return result
            return "/exit"

        handler.get_user_input = MagicMock(side_effect=get_input)
        handler.display_message = MagicMock()
        handler.display_error = MagicMock()

        # Add the async wait_for_user_input method
        async def wait_for_user_input(event: Any = None) -> str:
            return get_input()

        handler.wait_for_user_input = AsyncMock(side_effect=wait_for_user_input)
        handler.start_interactive_session = AsyncMock()
        handler.set_dialogue_provider = MagicMock()

        return handler

    @staticmethod
    def create_conversation_service(
        responses: Optional[List[str]] = None,
    ) -> Mock:
        """Create a mock conversation service."""
        service = AsyncMock()

        if responses is None:
            responses = ["I understand.", "Processing...", "Complete."]

        service.responses = responses.copy()
        service.response_index = 0

        async def get_response(*args: Any, **kwargs: Any) -> str:
            if service.response_index < len(service.responses):
                result = service.responses[service.response_index]
                service.response_index += 1
                return result
            return "No more responses available."

        service.get_response = AsyncMock(side_effect=get_response)
        service.start_conversation = AsyncMock()
        service.end_conversation = AsyncMock()

        return service


class AgentMockFactory:
    """Factory for agent-related mocks."""

    @staticmethod
    def create_agent_service(
        agent_name: str = "test-agent",
        responses: Optional[List[str]] = None,
    ) -> Mock:
        """Create a mock agent service."""
        if responses is None:
            responses = ["I understand.", "Processing...", "Complete."]

        service = AsyncMock()
        service.agent_name = agent_name
        service.responses = responses.copy()
        service.response_index = 0

        async def run_conversation(
            session_id: str, user_message: str, stream: bool = False
        ) -> Dict[str, Any]:
            if service.response_index < len(service.responses):
                response = service.responses[service.response_index]
                service.response_index += 1
                return {"content": response, "metadata": {}}
            return {"content": "No more responses", "metadata": {}}

        service.run_conversation = AsyncMock(side_effect=run_conversation)
        service.cleanup = AsyncMock()

        return service

    @staticmethod
    def create_agent_executor(
        executor_id: str = "test-executor",
        agent_name: str = "test-agent",  # noqa: ARG004
        tools: Optional[List[Any]] = None,
    ) -> Mock:
        """Create a mock agent executor for unified executor mode."""
        from src.core.agent_executor import AgentResponse

        executor = MagicMock()
        executor.context = MagicMock()
        executor.context.tools = tools or []
        executor.context.agent_id = f"agent-{executor_id}"

        # Mock conversation history
        executor.get_conversation_history = MagicMock(
            return_value=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )

        # Mock execute_turn
        async def execute_turn(user_input: str) -> AgentResponse:
            # Check for exit commands
            if user_input.lower() in ["/exit", "/bye"]:
                return AgentResponse(
                    content="Goodbye!",
                    pipeline_resumed=True,
                    collected_data={"status": "completed"},
                )
            return AgentResponse(
                content=f"Response to: {user_input}",
                pipeline_resumed=False,
                collected_data={},
            )

        executor.execute_turn = AsyncMock(side_effect=execute_turn)

        return executor


class AsyncContextManagerMock:
    """Mock for async context managers."""

    def __init__(
        self,
        enter_value: Any = None,
        exit_exception: Optional[Exception] = None,
    ) -> None:
        """Initialize the async context manager mock."""
        self.enter_value = enter_value or self
        self.exit_exception = exit_exception
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Any:
        """Enter the async context."""
        self.entered = True
        return self.enter_value

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit the async context."""
        self.exited = True
        if self.exit_exception:
            raise self.exit_exception
        return False


# Utility functions for creating complex mock scenarios
def mock_plugin_execution_chain(
    steps: List[StepConfiguration],
    results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Mock]:
    """Create a chain of mocked plugin executions."""
    if results is None:
        results = {step.name: f"{step.name}_output" for step in steps}

    mocks = {}
    for step in steps:
        plugin = PluginMockFactory.create_plugin_instance(
            name=step.plugin,
            run_result=results.get(step.name, "default_output"),
        )
        mocks[step.plugin] = plugin

    return mocks


def mock_suspension_scenario(
    suspend_at_step: str,
    resume_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Mock]:
    """Create mocks for a suspension/resume scenario."""
    if resume_data is None:
        resume_data = {"suspended_step": suspend_at_step, "state": "suspended"}

    return {
        "executor": PipelineExecutorMockFactory.create_executor(
            suspend_on_step=suspend_at_step
        ),
        "checkpoint_manager": create_checkpoint_manager_mock(resume_data),
        "task_manager": create_task_manager_mock_with_suspension(),
    }


def create_checkpoint_manager_mock(
    checkpoint_data: Optional[Dict[str, Any]] = None,
) -> Mock:
    """Create a checkpoint manager mock with data."""
    manager = AsyncMock()
    manager.save_checkpoint = AsyncMock()
    manager.load_checkpoint = AsyncMock(return_value=checkpoint_data)
    manager.delete_checkpoint = AsyncMock()

    return manager


def create_task_manager_mock_with_suspension() -> Mock:
    """Create a task manager mock that handles suspension."""
    manager = AsyncMock()
    manager.create_task = AsyncMock(return_value="task-123")
    manager.suspend_task = AsyncMock()
    manager.resume_task = AsyncMock()
    manager.get_task_status = AsyncMock(return_value="suspended")

    return manager


# Exception class for suspension (if not imported)
class SuspendExecution(Exception):
    """Exception to simulate pipeline suspension."""

    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize with suspension data."""
        self.data = data
        super().__init__(f"Pipeline suspended: {data}")


# Context manager for mocking entire subsystems
class MockSubsystem:
    """Context manager for mocking entire subsystems."""

    def __init__(self, subsystem: str) -> None:
        """Initialize the subsystem mocker."""
        self.subsystem = subsystem
        self.patches: List[Any] = []

    def __enter__(self) -> Dict[str, Mock]:
        """Enter context and create mocks."""
        if self.subsystem == "plugin_system":
            return self._mock_plugin_system()
        if self.subsystem == "dialogue_system":
            return self._mock_dialogue_system()
        if self.subsystem == "agent_system":
            return self._mock_agent_system()
        raise ValueError(f"Unknown subsystem: {self.subsystem}")

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and stop patches."""
        for p in self.patches:
            p.stop()

    def _mock_plugin_system(self) -> Dict[str, Mock]:
        """Mock the entire plugin system."""
        registry = PluginMockFactory.create_plugin_registry()
        invoker = PluginMockFactory.create_plugin_invoker()

        self.patches.extend(
            [
                patch("src.core.plugin_registry.PluginRegistry", return_value=registry),
                patch(
                    "src.services.plugin_invoker.PluginInvoker", return_value=invoker
                ),
            ]
        )

        for p in self.patches:
            p.start()

        return {"registry": registry, "invoker": invoker}

    def _mock_dialogue_system(self) -> Dict[str, Mock]:
        """Mock the entire dialogue system."""
        cli_handler = DialogueMockFactory.create_cli_handler()
        provider_factory = MagicMock()

        self.patches.extend(
            [
                patch("src.cli.cli_handler.CLIHandler", return_value=cli_handler),
                patch(
                    "src.cli.dialogue_provider_factory.DialogueProviderFactory",
                    return_value=provider_factory,
                ),
            ]
        )

        for p in self.patches:
            p.start()

        return {"cli_handler": cli_handler, "provider_factory": provider_factory}

    def _mock_agent_system(self) -> Dict[str, Mock]:
        """Mock the entire agent system."""
        # Create mocks for agent-related components
        agent_service = AsyncMock()
        agent_service.run_conversation = AsyncMock(
            return_value={"content": "test response"}
        )
        agent_service.cleanup = AsyncMock()

        agent_factory = MagicMock()
        agent_factory.create_agent = AsyncMock()

        self.patches.extend(
            [
                patch(
                    "src.services.agent_service.AgentService",
                    return_value=agent_service,
                ),
                patch(
                    "src.services.agent_factory.AgentFactory",
                    return_value=agent_factory,
                ),
            ]
        )

        for p in self.patches:
            p.start()

        return {"agent_service": agent_service, "agent_factory": agent_factory}
