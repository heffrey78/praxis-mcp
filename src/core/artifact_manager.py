"""Manages artifact storage and retrieval using a command pattern."""

import asyncio
import json
import logging
import weakref
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .artifacts import (
    ArtifactCommand,
    ArtifactCommandHandler,
    ArtifactOperation,
    CommandStatus,
)

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

logger = logging.getLogger(__name__)


class ArtifactManager:
    """Manages artifact storage and retrieval using a command pattern.

    This class provides a high-level interface for storing and retrieving
    artifacts, using the command pattern to track all operations.
    """

    def __init__(
        self, base_dir: str, container: Optional["DependencyContainer"] = None
    ) -> None:
        """Initialize the ArtifactManager.

        Args:
            base_dir: Base directory for storing artifacts
        """
        self.base_dir = Path(base_dir)
        self._container = container
        self.command_handler = ArtifactCommandHandler(self.base_dir)
        self.command_handler.setup_default_handlers()
        # Use WeakValueDictionary to prevent memory leaks
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._locks_lock = Lock()
        logger.debug(f"Initialized ArtifactManager with base_dir: {self.base_dir}")

    def get_task_dir(self, task_id: str) -> Path:
        """Get the directory for a specific task."""
        task_dir = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    async def get_task_dir_async(self, task_id: str) -> Path:
        """Get the directory for a specific task (async version)."""
        task_dir = self.base_dir / task_id
        await self._async_makedirs(task_dir)
        return task_dir

    def _get_or_create_lock(self, task_id: str) -> asyncio.Lock:
        """Get existing lock or create new one.

        This method uses a WeakValueDictionary to automatically clean up
        locks when they are no longer referenced, preventing memory leaks.
        """
        logger.debug(f"Getting lock for task: {task_id}")
        with self._locks_lock:
            try:
                return self._locks[task_id]
            except KeyError:
                logger.debug(f"Creating new lock for task: {task_id}")
                lock = asyncio.Lock()
                self._locks[task_id] = lock
                return lock

    async def _async_path_exists(self, path: Path) -> bool:
        """Check if path exists without blocking event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, path.exists)

    async def _async_makedirs(self, path: Path) -> None:
        """Create directories without blocking event loop."""
        loop = asyncio.get_running_loop()

        def make_dirs() -> None:
            path.mkdir(parents=True, exist_ok=True)

        await loop.run_in_executor(None, make_dirs)

    def _get_content_type(self, content: Any) -> str:
        """Determine content type."""
        if isinstance(content, (dict, list)):
            return "json"
        if isinstance(content, str):
            return "text"
        if isinstance(content, bytes):
            return "binary"
        return "unknown"

    async def save_artifact(
        self,
        task_id: str,
        filename: str,
        content: Union[str, bytes, Dict[str, Any], List[Any]],
        subdir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactCommand:
        """Save an artifact using the command pattern.

        Args:
            task_id: ID of the task this artifact belongs to
            filename: Name of the artifact file
            content: Content to save
            subdir: Optional subdirectory within task directory
            metadata: Optional metadata to store with artifact

        Returns:
            Command object with execution result

        Raises:
            RuntimeError: If saving fails
        """
        content_type = self._get_content_type(content)
        command = ArtifactCommand(
            operation=ArtifactOperation.SAVE,
            task_id=task_id,
            filename=filename,
            content=content,
            content_type=content_type,
            subdir=subdir,
            metadata=metadata or {},
        )

        logger.debug(
            f"ArtifactManager.save_artifact: Created ArtifactCommand: id={command.id}, task_id={task_id}, op={command.operation}, file={filename}, subdir={subdir}, type={content_type}"
        )

        result = await self.command_handler.execute(command)
        if not result:
            raise RuntimeError("Failed to save artifact: Command execution terminated")
        if result.status == CommandStatus.FAILED:
            raise RuntimeError(f"Failed to save artifact: {result.error}")
        return result

    def get_task_artifacts(self, task_id: str) -> List[ArtifactCommand]:
        """Get all artifacts for a task.

        Args:
            task_id: ID of task to get artifacts for

        Returns:
            List of artifact commands for the task
        """
        return self.command_handler.get_task_artifacts(task_id)

    def get_artifact_path(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> Path:
        """Get the path to an artifact."""
        path = self.base_dir / task_id
        if subdir:
            path = path / subdir
        return path / filename

    def artifact_exists(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> bool:
        """Check if an artifact exists."""
        path = self.get_artifact_path(task_id, filename, subdir)
        return path.exists()

    async def artifact_exists_async(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> bool:
        """Check if an artifact exists (async version)."""
        path = self.get_artifact_path(task_id, filename, subdir)
        return await self._async_path_exists(path)

    def _get_artifact_path(self, command: ArtifactCommand) -> Path:
        """Get the full path for an artifact.

        Args:
            command: Command containing artifact details

        Returns:
            Path to the artifact file
        """
        path = self.base_dir / command.task_id
        if command.subdir:
            path = path / command.subdir
        return path / command.filename

    def read_artifact(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> Any:
        """Read an artifact from disk (synchronous version for backward compatibility).

        Note: This method exists for backward compatibility. Consider using
        read_artifact_async for better performance in async contexts.
        """
        return self.read_artifact_sync(task_id, filename, subdir)

    async def read_artifact_async(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> Any:
        """Read an artifact from disk (async version)."""
        logger.debug(f"Reading artifact: {filename} for task: {task_id}")
        async with self._get_or_create_lock(task_id):
            logger.debug(f"Acquired lock for task: {task_id}")
            path = self.get_artifact_path(task_id, filename, subdir)
            if not await self._async_path_exists(path):
                logger.error(f"Artifact not found: {path}")
                raise FileNotFoundError(f"Artifact not found: {path}")

            # Use thread pool for file operations to avoid blocking
            loop = asyncio.get_running_loop()

            if filename.endswith(".json"):

                def read_json() -> Any:
                    with path.open("r", encoding="utf-8") as f:
                        return json.load(f)

                content = await loop.run_in_executor(None, read_json)
            elif any(filename.endswith(ext) for ext in [".txt", ".md"]):

                def read_text() -> str:
                    with path.open("r", encoding="utf-8") as f:
                        return f.read()

                content = await loop.run_in_executor(None, read_text)
            else:

                def read_binary() -> bytes:
                    with path.open("rb") as f:
                        return f.read()

                content = await loop.run_in_executor(None, read_binary)

            logger.debug(f"Successfully read artifact: {path}")
            return content

    def read_artifact_sync(
        self, task_id: str, filename: str, subdir: Optional[str] = None
    ) -> Any:
        """Read an artifact from disk (synchronous version for backward compatibility)."""
        logger.debug(f"Reading artifact: {filename} for task: {task_id}")
        # Note: Since we're using asyncio.Lock, we need to handle this differently
        # For backward compatibility, we'll use the path directly without locking
        path = self.get_artifact_path(task_id, filename, subdir)
        if not path.exists():
            logger.error(f"Artifact not found: {path}")
            raise FileNotFoundError(f"Artifact not found: {path}")

        if filename.endswith(".json"):
            with path.open("r", encoding="utf-8") as f:
                content = json.load(f)
        elif any(filename.endswith(ext) for ext in [".txt", ".md"]):
            with path.open("r", encoding="utf-8") as f:
                content = f.read()
        else:
            with path.open("rb") as f:
                content = f.read()

        logger.debug(f"Successfully read artifact: {path}")
        return content

    def list_artifacts(self, task_id: str) -> List[ArtifactCommand]:
        """List all artifacts for a given task (synchronous version for backward compatibility).

        Note: This method exists for backward compatibility. Consider using
        list_artifacts_async for better performance in async contexts.
        """
        return self.list_artifacts_sync(task_id)

    async def list_artifacts_async(self, task_id: str) -> List[ArtifactCommand]:
        """List all artifacts for a given task (async version).

        Args:
            task_id: ID of the task to list artifacts for

        Returns:
            List of ArtifactCommand objects representing the artifacts
        """
        task_dir = await self.get_task_dir_async(task_id)
        if not await self._async_path_exists(task_dir):
            return []

        loop = asyncio.get_running_loop()

        def _list_files() -> List[ArtifactCommand]:
            artifacts: List[ArtifactCommand] = []
            for file_path in task_dir.glob("*"):
                if file_path.is_file():
                    with file_path.open("rb") as f:
                        content = f.read()
                    artifacts.append(
                        ArtifactCommand(
                            operation=ArtifactOperation.SAVE,
                            task_id=task_id,
                            filename=file_path.name,
                            content=content,
                            content_type=self._get_content_type(content),
                            subdir=None,
                            metadata={},
                        )
                    )
            return artifacts

        return await loop.run_in_executor(None, _list_files)

    def list_artifacts_sync(self, task_id: str) -> List[ArtifactCommand]:
        """List all artifacts for a given task (synchronous version for backward compatibility).

        Args:
            task_id: ID of the task to list artifacts for

        Returns:
            List of ArtifactCommand objects representing the artifacts
        """
        task_dir = self.get_task_dir(task_id)
        if not task_dir.exists():
            return []

        artifacts: List[ArtifactCommand] = []
        for file_path in task_dir.glob("*"):
            if file_path.is_file():
                with file_path.open("rb") as f:
                    content = f.read()
                artifacts.append(
                    ArtifactCommand(
                        operation=ArtifactOperation.SAVE,
                        task_id=task_id,
                        filename=file_path.name,
                        content=content,
                        content_type=self._get_content_type(content),
                        subdir=None,
                        metadata={},
                    )
                )
        return artifacts

    async def cleanup_task(self, task_id: str) -> None:
        """Clean up resources for completed task.

        Since we're using WeakValueDictionary, locks will be automatically
        garbage collected when no longer referenced. This method is provided
        for explicit cleanup if needed.
        """
        # The weak references will automatically clean up the lock
        # when it's no longer referenced, but we can log for debugging
        if task_id in self._locks:
            logger.debug(
                f"Task {task_id} lock will be garbage collected when unreferenced"
            )
        else:
            logger.debug(f"Task {task_id} has no active lock")
