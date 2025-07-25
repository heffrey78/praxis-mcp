# ExecutionContext Architecture

## Overview

The `ExecutionContext` is a formal dataclass that carries all cross-cutting execution data through the pipeline execution stack. It replaces the previous ad-hoc pattern of manually copying attributes between context objects.

## Problem it Solves

Previously, the codebase had numerous instances of:
```python
# Manual attribute copying
setattr(context, "_container", container)
setattr(context, "_loop_iteration_index", 0)
# ... many more manual copies
```

This pattern was:
- **Fragile**: Easy to forget attributes, leading to silent None errors
- **Untypeable**: Type checkers couldn't verify attribute existence
- **Untestable**: Hard to unit test without a full pipeline setup
- **Scattered**: Attribute copying logic was duplicated in 20+ places

## Solution: ExecutionContext

The `ExecutionContext` dataclass provides:
1. **Type Safety**: All attributes are declared with proper types
2. **Single Source of Truth**: All execution data in one place
3. **Immutable Updates**: Use `spawn_child()` for scoped changes
4. **Backward Compatibility**: Dict-like interface for legacy code

## Usage

### Creating a Context

```python
from src.core.execution_context import create_execution_context

# Primary way to create context
context = create_execution_context(
    task_id="unique-task-id",
    container=dependency_container,
    # Optional parameters
    checkpoint_id="checkpoint-123",
    is_resume=True,
)
```

### Spawning Child Contexts

When entering a new execution scope (e.g., loop iteration):

```python
# Create child context with overrides
child_context = context.spawn_child(
    step_name="process_items",
    loop_iteration=5,
)
```

### Accessing Data

```python
# Direct attribute access (preferred)
artifact_path = context.get_artifact_path("output.json")
container = context.container

# Dict-like access (for compatibility)
value = context["custom_key"]
context["result"] = processed_data
```

## Key Attributes

- `task_id`: Unique identifier for the execution
- `artifact_manager`: Manages file storage
- `container`: Dependency injection container
- `checkpoint_manager`: Handles suspension/resume
- `type_registry`: Type conversion registry
- `loop_iteration`: Current loop index (if in loop)
- `step_name`: Currently executing step
- `checkpoint_id`: Resume checkpoint (if resuming)
- `resume_data`: Data from suspension
- `is_resume`: Whether this is a resume execution
- `pipeline_tools`: Tools available to plugins
- `session_id`: Session identifier for stateful plugins
- `extras`: Dict for dynamic attributes

## Migration Guide

### For Plugin Authors

Plugins should check for ExecutionContext first:

```python
# Get container (works with both old and new contexts)
if hasattr(context, "container"):
    # ExecutionContext - direct access
    container = context.container
else:
    # Legacy PipelineContext - use getattr
    container = getattr(context, "_container", None)
```

### For Core Developers

Replace manual copying:

```python
# Old way
new_context = PipelineContext(...)
setattr(new_context, "_container", container)
setattr(new_context, "_loop_index", 0)

# New way
new_context = create_execution_context(
    task_id=task_id,
    container=container,
    loop_iteration=0,
)
```

## Benefits

1. **Type Safety**: IDEs and type checkers understand all available attributes
2. **Testability**: Create minimal contexts for unit tests without full pipeline
3. **Maintainability**: Single place to add new cross-cutting concerns
4. **Performance**: No runtime attribute lookups with getattr/setattr
5. **Debugging**: Clear view of all available data in debugger

## Future Extensions

The ExecutionContext can be extended with:
- Distributed tracing context
- Security/authentication context  
- Performance monitoring hooks
- Feature flags
- Request correlation IDs

Simply add new fields to the dataclass and they're available throughout the execution stack.