# Test Simplification Guide

This guide explains the test simplification patterns introduced in Phase 6 of the technical debt refactoring. These patterns reduce test complexity, eliminate boilerplate, and make tests more maintainable.

## Overview

The test simplification introduces:
- **Test Fixtures Library** (`tests/fixtures.py`) - Builders for common test objects
- **Mock Factories** (`tests/mock_factories.py`) - Specialized mocks for complex components  
- **Async Helpers** (`tests/async_helpers.py`) - Utilities for async test scenarios
- **Configuration Objects** - Type-safe replacements for dictionaries

## Key Benefits

1. **Reduced Boilerplate** - No more repetitive mock setup
2. **Type Safety** - Configuration objects provide IDE support
3. **Readability** - Builder pattern makes test intent clear
4. **Consistency** - Standard patterns across all tests
5. **Maintainability** - Changes in one place affect all tests

## Test Fixtures Library

### Pipeline Builder

Create pipeline configurations with a fluent API:

```python
from tests.fixtures import PipelineBuilder

# Simple pipeline
pipeline = (
    PipelineBuilder("my-pipeline", "My Pipeline", "task-123")
    .with_mode(ExecutionMode.INTERACTIVE)
    .with_parameters(api_key="secret", timeout=30)
    .with_dialogue(DialogueMode.DIRECT, ["Yes", "No"])
    .build()
)
```

### Step Builder

Create step configurations easily:

```python
from tests.fixtures import StepBuilder

# Complex step with all options
step = (
    StepBuilder("process", "processor")
    .with_dependencies("fetch", "validate")
    .with_config(mode="fast", threads=4)
    .with_condition("input.valid == true")
    .with_retry(3)
    .with_timeout(60)
    .with_loop(max_iterations=10)
    .build()
)
```

### Mock Factory

Create common mocks without manual setup:

```python
from tests.fixtures import MockFactory

# Create fully configured container
container = MockFactory.container()

# Create individual mocks
task_manager = MockFactory.task_manager()
artifact_manager = MockFactory.artifact_manager(base_dir=Path("/tmp"))
dialogue_provider = MockFactory.dialogue_provider(["Yes", "No", "/exit"])
```

### Test Data Factory

Create test data with sensible defaults:

```python
from tests.fixtures import TestDataFactory

# Execution context with all dependencies
context = TestDataFactory.execution_context(
    task_id="test-123",
    container=container,
    pipeline_config=pipeline_config,
)

# In-memory file loader
file_loader = TestDataFactory.file_loader({
    "config.yaml": "key: value",
    "data.json": '{"test": true}',
})
```

## Async Test Helpers

### Async Test Decorator

Simplifies async test setup:

```python
from tests.async_helpers import async_test

@async_test(timeout=10.0)
async def test_something():
    result = await some_operation()
    assert result == expected
```

### Async Test Context

Manages async resources automatically:

```python
from tests.async_helpers import AsyncTestContext

@async_test()
async def test_with_context():
    async with AsyncTestContext() as ctx:
        # Create tracked tasks
        task = await ctx.create_task(long_running_operation())
        
        # Add cleanup callbacks
        ctx.add_cleanup(lambda: cleanup_resources())
        
        # Tasks are cancelled and cleanup runs on exit
```

### Async Utilities

Common async patterns:

```python
from tests.async_helpers import wait_for_condition, run_with_timeout

# Wait for condition
await wait_for_condition(
    lambda: task.done(),
    timeout=5.0,
    message="Task did not complete"
)

# Run with timeout and default
result = await run_with_timeout(
    slow_operation(),
    timeout=2.0,
    default="timeout_value"
)
```

## Mock Factories for Complex Scenarios

### Plugin System Mocks

```python
from tests.mock_factories import PluginMockFactory

# Create plugin with specific behavior
plugin = PluginMockFactory.create_plugin_instance(
    name="validator",
    run_result={"valid": True, "errors": []},
    supports_streaming=True,
)

# Create entire plugin registry
registry = PluginMockFactory.create_plugin_registry({
    "validator": plugin,
    "processor": another_plugin,
})
```

### Dialogue System Mocks

```python
from tests.mock_factories import DialogueMockFactory

# CLI handler with predefined inputs
cli_handler = DialogueMockFactory.create_cli_handler(
    user_inputs=["Yes", "Process data", "/exit"]
)

# Conversation service with responses
service = DialogueMockFactory.create_conversation_service(
    responses=["Understood", "Processing...", "Complete"]
)
```

### Mock Subsystems

Mock entire subsystems with one context manager:

```python
from tests.mock_factories import MockSubsystem

# Mock entire plugin system
with MockSubsystem("plugin_system") as mocks:
    registry = mocks["registry"]
    invoker = mocks["invoker"]
    
    # Use the mocks in your test
    result = await run_pipeline_with_plugins()
```

## Migration Examples

### Before (Complex Manual Setup)

```python
def test_pipeline_execution():
    # Manual mock creation
    container = MagicMock()
    task_manager = AsyncMock()
    task_manager.create_task = AsyncMock(return_value="task-123")
    container.get_task_manager.return_value = task_manager
    
    # Manual config dict
    pipeline_config = {
        "pipeline_id": "test",
        "steps": [
            {"name": "step1", "plugin": "plugin1"},
            {"name": "step2", "plugin": "plugin2", "dependencies": ["step1"]}
        ]
    }
    
    # Complex context setup
    context = {"task_id": "task-123", "pipeline_config": pipeline_config}
    
    # Test execution...
```

### After (Simplified with Fixtures)

```python
def test_pipeline_execution():
    # Use factories
    container = MockFactory.container()
    
    # Use builders
    pipeline_config = (
        PipelineBuilder()
        .with_steps(
            StepBuilder("step1", "plugin1").build(),
            StepBuilder("step2", "plugin2").with_dependencies("step1").build()
        )
        .build()
    )
    
    # Use test data factory
    context = TestDataFactory.execution_context(
        container=container,
        pipeline_config=pipeline_config
    )
    
    # Test execution...
```

## Best Practices

1. **Use Builders for Configuration**
   - Prefer builders over manual dictionary creation
   - Chain methods for readable configuration
   - Use convenience functions for common scenarios

2. **Leverage Mock Factories**
   - Don't create mocks manually
   - Use specialized factories for complex components
   - Mock entire subsystems when needed

3. **Handle Async Properly**
   - Use `@async_test` decorator
   - Track tasks with `AsyncTestContext`
   - Set appropriate timeouts

4. **Keep Tests Focused**
   - Test one thing at a time
   - Use minimal setup for each test
   - Let fixtures handle the complexity

5. **Maintain Test Data**
   - Store common test data in fixtures
   - Use factories for variations
   - Keep test data close to tests

## Common Patterns

### Testing Pipeline Execution

```python
@async_test()
async def test_pipeline_execution():
    # Setup
    pipeline = simple_pipeline()
    context = async_test_context()
    
    # Execute
    result = await executor.run(pipeline, context)
    
    # Assert
    assert result.status == "completed"
```

### Testing with Suspension

```python
@async_test()
async def test_suspension_handling():
    # Create suspension scenario
    mocks = mock_suspension_scenario(
        suspend_at_step="validate",
        resume_data={"validated": True}
    )
    
    # Test suspension and resume
    with pytest.raises(PipelineSuspendedException):
        await executor.run(context)
    
    # Resume with data
    result = await executor.resume(context, mocks["resume_data"])
    assert result.status == "completed"
```

### Testing Dialogue Interactions

```python
def test_dialogue_flow():
    # Setup dialogue
    pipeline = interactive_pipeline()
    provider = MockFactory.dialogue_provider(["Yes", "No", "Done"])
    
    # Test interaction
    response = provider.get_response("Continue?")
    assert response == "Yes"
```

## Conclusion

The test simplification patterns make tests:
- **Easier to write** - Less boilerplate, more focus on test logic
- **Easier to read** - Clear intent with builder patterns
- **Easier to maintain** - Centralized factories and fixtures
- **More reliable** - Consistent patterns reduce bugs

When writing new tests, always check if there's a fixture or factory that can simplify your setup. The goal is to make the test's intent immediately clear while hiding the complexity in reusable components.