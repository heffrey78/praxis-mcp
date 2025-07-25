"""Command handler for artifact operations."""

import json
import logging
from pathlib import Path
from typing import List, Optional

from .commands import ArtifactCommand, CommandStatus
from .middleware import ArtifactMiddleware, MiddlewareError, create_middleware_handler

logger = logging.getLogger(__name__)


class ArtifactCommandHandler:
    """Handles execution of artifact commands and maintains command history.

    This class coordinates the execution of artifact commands through
    a middleware chain and maintains a history of all executed commands.
    """

    def __init__(self, base_dir: Path) -> None:
        """Initialize the command handler.

        Args:
            base_dir: Base directory for storing artifacts
        """
        self.base_dir = base_dir
        self.middleware = ArtifactMiddleware()
        self.command_history: List[ArtifactCommand] = []

        # Set up default middleware handlers
        self.setup_default_handlers()

    def setup_default_handlers(self) -> None:
        """Set up the default middleware handlers."""
        self.middleware.use(self._validate_command_handler)
        self.middleware.use(self._prepare_directories_handler)
        self.middleware.use(self._save_to_disk_handler)
        self.middleware.use(self._record_command_handler)

    @create_middleware_handler("validate_command")
    async def _validate_command_handler(
        self, command: ArtifactCommand
    ) -> Optional[ArtifactCommand]:
        """Validate the command before execution."""
        if not command.task_id or not command.filename:
            raise ValueError("Command must have task_id and filename")
        return command.with_status(CommandStatus.IN_PROGRESS)

    @create_middleware_handler("prepare_directories")
    async def _prepare_directories_handler(
        self, command: ArtifactCommand
    ) -> Optional[ArtifactCommand]:
        """Prepare necessary directories."""
        task_dir = self.base_dir / command.task_id
        if command.subdir:
            task_dir = task_dir / command.subdir

        logger.debug(
            f"PrepareDirs: command.filename='{command.filename}', command.subdir='{command.subdir}', target_dir='{task_dir}', type(target_dir)='{type(task_dir)}'"
        )
        logger.debug(
            f"PrepareDirs: target_dir='{task_dir}' exists before mkdir: {task_dir.exists()}"
        )
        try:
            task_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(
                f"PrepareDirs: target_dir='{task_dir}' mkdir call completed. Exists after mkdir: {task_dir.exists()}"
            )
        except Exception as e:
            logger.error(
                f"PrepareDirs: ERROR during mkdir for target_dir='{task_dir}': {e}",
                exc_info=True,
            )
            # Re-raise or handle as appropriate, for now, just log and let it proceed to see if save fails
            raise  # Or return command.with_status(CommandStatus.FAILED, str(e))
        return command

    @create_middleware_handler("save_to_disk")
    async def _save_to_disk_handler(
        self, command: ArtifactCommand
    ) -> Optional[ArtifactCommand]:
        """Save artifact content to disk."""
        file_path = self._get_artifact_path(command)
        logger.debug(
            f"SaveToDisk: command.filename='{command.filename}', command.subdir='{command.subdir}', final_path='{file_path}'"
        )
        logger.debug(
            f"SaveToDisk: Directory for final_path='{file_path.parent}' exists: {file_path.parent.exists()}"
        )

        try:
            # Specific log before open
            logger.debug(f"SaveToDisk: Attempting to open '{file_path}' for writing.")
            if isinstance(command.content, (dict, list)):
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(command.content, f, indent=2)
            elif isinstance(command.content, str):
                with file_path.open("w", encoding="utf-8") as f:
                    f.write(command.content)
            elif isinstance(command.content, bytes):
                with file_path.open("wb") as f:
                    f.write(command.content)
            else:
                logger.error(
                    f"SaveToDisk: Unsupported content type: {type(command.content)} for path '{file_path}'"
                )
                raise ValueError(f"Unsupported content type: {type(command.content)}")

            logger.debug(
                f"SaveToDisk: Successfully wrote to '{file_path}'. Exists: {file_path.exists()}"
            )
            return command.with_status(CommandStatus.COMPLETED)

        except FileNotFoundError:
            logger.error(
                f"SaveToDisk: FileNotFoundError for path '{file_path}'. Parent directory '{file_path.parent}' exists: {file_path.parent.exists()}",
                exc_info=True,
            )
            return command.with_status(
                CommandStatus.FAILED,
                f"FileNotFoundError: {file_path}. Parent dir exists: {file_path.parent.exists()}",
            )
        except Exception as e:
            logger.error(
                f"SaveToDisk: ERROR during saving to_disk for path '{file_path}': {e}",
                exc_info=True,
            )
            return command.with_status(CommandStatus.FAILED, str(e))

    @create_middleware_handler("record_command")
    async def _record_command_handler(
        self, command: ArtifactCommand
    ) -> Optional[ArtifactCommand]:
        """Record the command in history."""
        self.command_history.append(command)
        return command

    def _get_artifact_path(self, command: ArtifactCommand) -> Path:
        """Get the full path for an artifact."""
        path = self.base_dir / command.task_id
        if command.subdir:
            path = path / command.subdir
        return path / command.filename

    async def execute(self, command: ArtifactCommand) -> Optional[ArtifactCommand]:
        """Execute a command through the middleware chain.

        Args:
            command: Command to execute

        Returns:
            Processed command or None if chain was terminated

        Raises:
            Exception: If command execution fails
        """
        try:
            result = await self.middleware.execute(command)
            if result is None:
                return command.with_status(
                    CommandStatus.FAILED, "Command execution terminated"
                )
            return result
        except MiddlewareError as e:
            logger.error(f"Failed to execute command {command.id}: {str(e)}")
            return command.with_status(CommandStatus.FAILED, str(e))
        except Exception as e:
            logger.error(f"Unexpected error executing command {command.id}: {str(e)}")
            return command.with_status(
                CommandStatus.FAILED, f"Unexpected error: {str(e)}"
            )

    def get_task_artifacts(self, task_id: str) -> List[ArtifactCommand]:
        """Get all artifact commands for a specific task.

        Args:
            task_id: ID of the task

        Returns:
            List of commands for the task
        """
        return [cmd for cmd in self.command_history if cmd.task_id == task_id]
