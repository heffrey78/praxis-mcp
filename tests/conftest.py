import contextlib
import shutil
import tempfile
from pathlib import Path

import httpx
import pytest

from src.core.dependency_container import DependencyContainer
from src.core.pipeline_definition import ParamDefinition, PipelineDefinition, StepConfig
from src.main import app
from src.plugins.plugin_base import PluginBase


# Configure pytest to filter common warnings - NOTE: These are now in the root conftest.py and pytest.ini
def pytest_configure(config):
    """Configure pytest with custom settings including warning filters."""
    # Add custom project markers if needed


@pytest.fixture(autouse=True)
def cleanup_artifacts():
    """Fixture to clean up artifacts after tests."""
    # Setup
    artifacts_dir = Path(tempfile.mkdtemp())
    yield artifacts_dir

    # Teardown
    with contextlib.suppress(OSError, PermissionError):
        # Windows may sometimes fail to remove files immediately
        shutil.rmtree(artifacts_dir)


@pytest.fixture()
def mock_container(request):
    """
    Create a container with mock artifacts directory.

    This fixture creates a fresh dependency container for each test,
    with a temporary directory for artifacts.
    """
    # Create a clean temp dir for this test
    artifacts_dir = Path(tempfile.mkdtemp())

    # Create container with the temp dir and mock providers
    config = {"artifacts_dir": str(artifacts_dir), "mock_providers": True}
    container = DependencyContainer(config)

    # Register dummy pipeline for testing
    registry = container.get_pipeline_registry()
    pipeline = PipelineDefinition(
        id="test_pipeline",
        name="Test Pipeline",
        description="Pipeline for testing",
        params=[
            ParamDefinition(
                name="param1",
                required=True,
                description="Test parameter",
                type="string",
            )
        ],
        steps=[StepConfig(name="step1", plugin="mock_plugin", depends_on=[])],
    )
    registry.register(pipeline)

    # Get registries and register mock plugins
    step_registry = container.get_step_registry()

    # Return container
    yield container

    # Teardown - clean up temp dir
    with contextlib.suppress(OSError, PermissionError):
        # Windows may sometimes fail to remove files immediately
        shutil.rmtree(artifacts_dir)


@pytest.fixture()
def zero_tasks_file():
    """Fixture to create a task manager with empty history."""
    task_manager = DependencyContainer().get_task_manager()
    task_manager.history_file.write_text('{"tasks": {}}')


@pytest.fixture()
def temp_artifacts_dir(tmp_path):
    """Create a temporary artifacts directory."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return artifacts_dir


@pytest.fixture()
def test_artifacts_dir(tmp_path):
    """Create a temporary directory for test artifacts."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True)
    yield artifacts_dir
    # Cleanup
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)


@pytest.fixture()
def container(test_artifacts_dir):
    """Create a DependencyContainer with test configuration."""
    config = {"artifacts_dir": str(test_artifacts_dir), "openai_api_key": "test_key"}
    container = DependencyContainer(config)
    return container


@pytest.fixture(autouse=True)
def cleanup_task_history(container):
    """Ensure task history is clean before each test."""
    task_manager = container.get_task_manager()
    if task_manager.history_file.exists():
        task_manager.history_file.write_text('{"tasks": {}}')
    yield
    # Cleanup after test
    if task_manager.history_file.exists():
        task_manager.history_file.write_text('{"tasks": {}}')


@pytest.fixture()
async def test_client():
    """Create a FastAPI test client."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_plugin_base_shutdown_flag():
    """Ensure the PluginBase shutdown flag is reset before each test."""
    if hasattr(PluginBase, "_is_shutting_down"):
        PluginBase._is_shutting_down = False
    yield
    # Optional: Reset again after test if needed, though usually not necessary
    if hasattr(PluginBase, "_is_shutting_down"):
        PluginBase._is_shutting_down = False


@pytest.fixture()
def mock_artifact_manager(tmp_path: Path):
    """Create a properly mocked ArtifactManager that uses tmp_path for all file operations.

    This fixture ensures that test artifacts are created in pytest's temporary directory
    instead of the project root, preventing accidental creation of MagicMock/ directories.
    """
    from unittest.mock import Mock

    from src.core.artifact_manager import ArtifactManager

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    # Use Mock (not MagicMock) to avoid unexpected string representations
    manager = Mock(spec=ArtifactManager)

    # Set up attributes that return real paths
    manager.artifacts_dir = str(artifacts_dir)
    manager.base_dir = str(artifacts_dir)

    # Mock get_artifacts_dir to return real paths
    def get_artifacts_dir(task_id: str) -> str:
        task_dir = artifacts_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return str(task_dir)

    manager.get_artifacts_dir = Mock(side_effect=get_artifacts_dir)

    # Mock get_task_dir to return Path objects
    def get_task_dir(task_id: str) -> Path:
        task_dir = artifacts_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    manager.get_task_dir = Mock(side_effect=get_task_dir)

    # Mock async methods for path operations
    async def mock_path_exists(path: str) -> bool:
        return Path(path).exists()

    async def mock_makedirs(path: str, exist_ok: bool = True) -> None:
        Path(path).mkdir(parents=True, exist_ok=exist_ok)

    manager.path_exists = Mock(side_effect=mock_path_exists)
    manager.makedirs = Mock(side_effect=mock_makedirs)

    return manager
