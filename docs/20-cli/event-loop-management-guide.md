# Event Loop Management Guide

## Overview

This guide documents the event loop management patterns used in the Praxis codebase, particularly around async/sync boundaries and CLI commands.

## Key Principles

1. **No Event Loop Creation in Libraries**: Core library code (like `PluginExecutor`) should NEVER create or manage event loops
2. **Async-First Design**: All core functionality should be async, with sync wrappers only at application boundaries
3. **CLI Commands Stay Synchronous**: Due to Typer limitations, CLI commands remain synchronous and use `asyncio.run()`

## The Typer CLI Limitation

As of 2025-01, Typer's test runner (`CliRunner`) does not support async commands. This is a known limitation:
- Issue: https://github.com/tiangolo/typer/issues/88
- Impact: All CLI commands must be synchronous
- Solution: Use `asyncio.run()` at the CLI boundary

### Correct Pattern (CLI)

```python
@app.command()
def my_command(param: str):
    """Synchronous CLI command that calls async code."""
    async def run_async():
        executor = PluginExecutor()
        return await executor.do_something_async(param)
    
    result = asyncio.run(run_async())
    print(result)
```

### Incorrect Pattern (Library)

```python
# DON'T DO THIS in library code!
class PluginExecutor:
    def get_plugin_info(self, name: str):
        # This will fail in FastAPI/server contexts!
        return asyncio.run(self.get_plugin_info_async(name))
```

## Why This Matters

### The Problem We Fixed

The original code had synchronous wrappers around async methods in the `PluginExecutor` class:

```python
def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
    """REMOVED: This method caused RuntimeError in FastAPI contexts."""
    return asyncio.run(self.get_plugin_info_async(plugin_name))
```

This pattern fails when called from within an existing event loop (like FastAPI):
- `RuntimeError: asyncio.run() cannot be called from a running event loop`
- Silent failures in plugin discovery
- Inconsistent behavior between CLI and server contexts

### The Solution

1. **Remove all sync wrappers from library code**
2. **Keep CLI commands synchronous** (Typer limitation)
3. **Use asyncio.run() only at the CLI boundary**

## Code Review Checklist

When reviewing async/sync code:

1. ✅ Library classes should be async-first
2. ✅ No `asyncio.run()` calls inside library methods
3. ✅ CLI commands can use `asyncio.run()` at the top level
4. ✅ FastAPI endpoints should use `await` directly
5. ❌ Don't create sync wrappers for async methods in libraries
6. ❌ Don't use event loop detection (`asyncio.get_event_loop()`)

## Migration Examples

### Before (Incorrect)
```python
# In library code
class MyService:
    def sync_method(self):
        return asyncio.run(self.async_method())  # BAD!
    
    async def async_method(self):
        return "result"

# In CLI
@app.command()
def my_command():
    service = MyService()
    result = service.sync_method()  # Fails in server context!
```

### After (Correct)
```python
# In library code
class MyService:
    async def async_method(self):
        return "result"
    # No sync wrapper!

# In CLI
@app.command()
def my_command():
    async def run():
        service = MyService()
        return await service.async_method()
    
    result = asyncio.run(run())  # OK at CLI boundary
```

## Testing Considerations

1. Use `pytest-asyncio` for testing async code
2. Mock async methods with `AsyncMock`
3. Test both CLI and server contexts
4. Ensure no event loop errors in either context

## Future Improvements

When Typer eventually supports async commands natively, we can update CLI commands to:

```python
@app.command()
async def my_command(param: str):
    """Native async command (future Typer version)."""
    executor = PluginExecutor()
    result = await executor.do_something_async(param)
    print(result)
```

Until then, the current pattern of synchronous CLI commands with `asyncio.run()` is the correct approach.

## References

- TASK-20250120-01: Original event loop management fix
- [Typer async command issue](https://github.com/tiangolo/typer/issues/88)
- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)