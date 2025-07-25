"""Async test helpers to simplify asynchronous test setup.

This module provides utilities for working with async tests, including
event loop management, async context managers, and common async patterns.
"""

import asyncio
import functools
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Optional, TypeVar

import pytest

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def async_test(timeout: float = 30.0) -> Callable[[F], F]:
    """Decorator for async tests with automatic timeout and cleanup.

    This decorator simplifies async test setup by:
    - Automatically marking the test as async
    - Setting a default timeout
    - Ensuring proper cleanup of async resources

    Args:
        timeout: Maximum time in seconds for the test to complete

    Example:
        @async_test(timeout=10.0)
        async def test_something():
            result = await some_async_operation()
            assert result == expected
    """

    def decorator(func: F) -> F:
        @pytest.mark.asyncio()
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                async with asyncio.timeout(timeout):
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                pytest.fail(f"Test timed out after {timeout} seconds")
            finally:
                # Clean up any pending tasks
                try:
                    loop = asyncio.get_running_loop()
                    tasks = [
                        t
                        for t in asyncio.all_tasks(loop)
                        if not t.done() and t != asyncio.current_task()
                    ]
                    if tasks:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    # Ignore cleanup errors
                    pass

        return wrapper  # type: ignore[return-value]

    return decorator


class AsyncTestContext:
    """Context manager for async test setup and teardown."""

    def __init__(self) -> None:
        """Initialize the async test context."""
        self._tasks: list[asyncio.Task[Any]] = []
        self._cleanup_callbacks: list[Callable[[], Any]] = []

    async def __aenter__(self) -> "AsyncTestContext":
        """Enter the async context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context and perform cleanup."""
        # Cancel any tracked tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for task cancellation
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Run cleanup callbacks
        for callback in reversed(self._cleanup_callbacks):
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass  # Ignore cleanup errors in tests

    def track_task(self, task: asyncio.Task[Any]) -> asyncio.Task[Any]:
        """Track a task for automatic cleanup."""
        self._tasks.append(task)
        return task

    def add_cleanup(self, callback: Callable[[], Any]) -> None:
        """Add a cleanup callback to be called on exit."""
        self._cleanup_callbacks.append(callback)

    async def create_task(self, coro: Any) -> asyncio.Task[Any]:
        """Create and track an async task."""
        task = asyncio.create_task(coro)
        self.track_task(task)
        return task


@asynccontextmanager
async def async_timeout(seconds: float) -> AsyncGenerator[None, None]:
    """Async context manager for operation timeouts.

    Example:
        async with async_timeout(5.0):
            await long_running_operation()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        pytest.fail(f"Test timed out after {seconds} seconds")


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition not met",
) -> None:
    """Wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds
        message: Error message if timeout occurs
    """
    start_time = asyncio.get_event_loop().time()
    while not condition():
        if asyncio.get_event_loop().time() - start_time > timeout:
            pytest.fail(f"Timeout waiting for condition: {message}")
        await asyncio.sleep(interval)


async def run_with_timeout(
    coro: Any, timeout: float = 5.0, default: Optional[T] = None
) -> T:
    """Run a coroutine with a timeout, returning default on timeout.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        default: Value to return on timeout

    Returns:
        Result of coroutine or default value
    """
    try:
        async with asyncio.timeout(timeout):
            return await coro
    except asyncio.TimeoutError:
        return default  # type: ignore[return-value]


class AsyncMockManager:
    """Manager for creating and configuring async mocks."""

    def __init__(self) -> None:
        """Initialize the mock manager."""
        self._mocks: list[Any] = []

    def create_async_mock(
        self, return_value: Any = None, side_effect: Any = None
    ) -> Any:
        """Create an async mock with proper configuration."""
        from unittest.mock import AsyncMock

        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        if side_effect is not None:
            mock.side_effect = side_effect

        self._mocks.append(mock)
        return mock

    def assert_all_awaited(self) -> None:
        """Assert that all async mocks were awaited."""
        for mock in self._mocks:
            if hasattr(mock, "assert_awaited"):
                mock.assert_awaited()


class AsyncEventWaiter:
    """Helper for waiting on async events in tests."""

    def __init__(self) -> None:
        """Initialize the event waiter."""
        self._events: dict[str, asyncio.Event] = {}

    def create_event(self, name: str) -> asyncio.Event:
        """Create a named event."""
        event = asyncio.Event()
        self._events[name] = event
        return event

    async def wait_for(self, name: str, timeout: float = 5.0) -> None:
        """Wait for a named event."""
        if name not in self._events:
            pytest.fail(f"Event '{name}' not found")

        try:
            async with asyncio.timeout(timeout):
                await self._events[name].wait()
        except asyncio.TimeoutError:
            pytest.fail(f"Timeout waiting for event '{name}'")

    def set(self, name: str) -> None:
        """Set a named event."""
        if name in self._events:
            self._events[name].set()


# Utility functions for common async patterns
async def gather_with_errors(*coros: Any) -> list[Any]:
    """Gather coroutines but don't fail on first error."""
    results = await asyncio.gather(*coros, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        # Re-raise first error after all complete
        raise errors[0]
    return results


async def run_in_parallel(*funcs: Callable[[], Any]) -> list[Any]:
    """Run multiple async functions in parallel."""
    tasks = [asyncio.create_task(func()) for func in funcs]
    return await asyncio.gather(*tasks)


def async_patch(target: str, **kwargs: Any) -> Any:
    """Create an async mock patch."""
    from unittest.mock import AsyncMock, patch

    return patch(target, new_callable=AsyncMock, **kwargs)  # type: ignore[misc]


# Example usage in tests:
"""
@async_test(timeout=10.0)
async def test_example():
    async with AsyncTestContext() as ctx:
        # Create tracked task
        task = await ctx.create_task(some_async_operation())

        # Wait for condition
        await wait_for_condition(
            lambda: task.done(),
            timeout=5.0,
            message="Task did not complete"
        )

        assert task.result() == expected
"""
