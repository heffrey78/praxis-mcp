"""Middleware system for processing artifact commands."""

import asyncio
import logging
from functools import wraps
from typing import Any, Awaitable, Callable, List, Optional, Protocol

from .commands import ArtifactCommand

logger = logging.getLogger(__name__)


class MiddlewareHandler(Protocol):
    """Protocol defining the interface for middleware handlers."""

    async def __call__(self, command: ArtifactCommand) -> Optional[ArtifactCommand]:
        """Process a command.

        Args:
            command: The command to process

        Returns:
            The processed command or None to terminate the chain
        """
        ...


class MiddlewareError(Exception):
    """Base class for middleware errors."""

    def __init__(self, message: str, handler_name: str, command_id: str) -> None:
        self.handler_name = handler_name
        self.command_id = command_id
        super().__init__(f"{handler_name}: {message} (command: {command_id})")


def create_middleware_handler(
    name: str,
) -> Callable[
    [Callable[..., Awaitable[Optional[ArtifactCommand]]]],
    Callable[..., Awaitable[Optional[ArtifactCommand]]],
]:
    """Create a named middleware handler with logging.

    Args:
        name: Name of the handler for logging

    Returns:
        Decorator that wraps a method as a middleware handler
    """

    def decorator(
        method: Callable[..., Awaitable[Optional[ArtifactCommand]]],
    ) -> Callable[..., Awaitable[Optional[ArtifactCommand]]]:
        @wraps(method)
        async def wrapped_handler(
            self_or_cmd: Any, cmd_or_none: Optional[ArtifactCommand] = None
        ) -> Optional[ArtifactCommand]:
            # Initialize command variable before try block
            command: Optional[ArtifactCommand] = None
            try:
                # Handle both instance methods and standalone functions
                if cmd_or_none is None:
                    # Called as standalone function
                    command = self_or_cmd
                    instance = None
                else:
                    # Called as instance method
                    instance = self_or_cmd
                    command = cmd_or_none

                if command is not None:
                    logger.debug(
                        f"Starting handler '{name}' for command {str(command.id)}"
                    )
                if instance:
                    result = await method(instance, command)
                else:
                    result = await method(command)
                if command is not None:
                    logger.debug(
                        f"Completed handler '{name}' for command {str(command.id)}"
                    )
                return result
            except Exception as e:
                # Handle case where command might not be initialized
                command_id = str(command.id) if command else "unknown"
                logger.error(
                    f"Error in handler '{name}' for command {command_id}: {str(e)}"
                )
                raise MiddlewareError(str(e), name, command_id) from e

        return wrapped_handler

    return decorator


class ArtifactMiddleware:
    """Middleware system for processing artifact commands.

    The middleware system allows for a chain of handlers to process
    artifact commands in sequence. Each handler can modify the command
    or terminate the chain by returning None.
    """

    def __init__(self) -> None:
        self.handlers: List[
            Callable[[ArtifactCommand], Awaitable[Optional[ArtifactCommand]]]
        ] = []
        self._lock = asyncio.Lock()

    def use(
        self, handler: Callable[[ArtifactCommand], Awaitable[Optional[ArtifactCommand]]]
    ) -> None:
        """Add a middleware handler to the chain.

        Args:
            handler: Async handler that processes commands
        """
        self.handlers.append(handler)

    async def execute(self, command: ArtifactCommand) -> Optional[ArtifactCommand]:
        """Execute all middleware handlers in sequence.

        Args:
            command: Command to process

        Returns:
            Processed command or None if chain was terminated

        Raises:
            MiddlewareError: If any handler fails
        """
        async with self._lock:
            current_command: Optional[ArtifactCommand] = command
            try:
                for handler in self.handlers:
                    if current_command is None:
                        break
                    current_command = await handler(current_command)
                return current_command
            except MiddlewareError:
                # Re-raise middleware errors as they're already formatted
                raise
            except Exception as e:
                # Wrap unexpected errors
                raise MiddlewareError(
                    str(e), "middleware_chain", str(command.id)
                ) from e
