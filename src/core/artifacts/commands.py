"""Command structures for artifact operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class CommandStatus(Enum):
    """Status of an artifact command."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactOperation(Enum):
    """Type of artifact operation."""

    SAVE = "save"
    DELETE = "delete"
    UPDATE = "update"


@dataclass(frozen=True)
class ArtifactCommand:
    """Command for artifact operations.

    Attributes:
        id: Unique identifier for the command
        operation: Type of operation to perform
        task_id: ID of the task this artifact belongs to
        filename: Name of the artifact file
        content: Content to save
        content_type: Type of content (json, text, binary, etc)
        subdir: Optional subdirectory within task directory
        metadata: Additional metadata about the artifact
        timestamp: When the command was created
        status: Current status of the command
        error: Error message if command failed
    """

    operation: ArtifactOperation
    task_id: str
    filename: str
    content: Any
    content_type: str
    id: UUID = field(default_factory=uuid4)
    subdir: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: CommandStatus = field(default=CommandStatus.PENDING)
    error: Optional[str] = None

    def with_status(
        self, status: CommandStatus, error: Optional[str] = None
    ) -> "ArtifactCommand":
        """Create a new command with updated status.

        Args:
            status: New status for the command
            error: Optional error message

        Returns:
            New command instance with updated status
        """
        return ArtifactCommand(
            id=self.id,
            operation=self.operation,
            task_id=self.task_id,
            filename=self.filename,
            content=self.content,
            content_type=self.content_type,
            subdir=self.subdir,
            metadata=self.metadata,
            timestamp=self.timestamp,
            status=status,
            error=error,
        )
