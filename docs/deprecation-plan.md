# Deprecation Plan for Legacy Patterns

## Overview
This document outlines the deprecation strategy for legacy patterns replaced during the technical debt refactoring. The goal is to provide a smooth migration path while maintaining backward compatibility.

## Deprecation Timeline

### Phase 1: Current State (v1.x)
- All legacy patterns remain functional
- New patterns are available and recommended
- Documentation updated to prefer new patterns
- Deprecation warnings added to legacy code

### Phase 2: Soft Deprecation (v2.0)
- Legacy patterns marked with `@deprecated` decorator
- Runtime warnings when legacy patterns are used
- Migration guide prominently featured
- All internal code migrated to new patterns

### Phase 3: Hard Deprecation (v3.0)
- Legacy patterns removed from codebase
- Breaking changes documented in CHANGELOG
- Migration tools provided if needed

## Patterns to Deprecate

### 1. Context Dictionary Access
**Legacy Pattern:**
```python
# Direct dictionary access
context["key"] = value
pipeline_config = context.get("pipeline_config", {})
```

**Replacement:**
```python
# Type-safe configuration objects
context.set_config_parameter("key", value)
pipeline_config = context.get_pipeline_config()
```

**Migration Strategy:**
- Add deprecation warnings to dict access methods
- Provide automatic migration tool
- Document in migration guide

### 2. Manual Mock Creation in Tests
**Legacy Pattern:**
```python
# Complex manual mocking
container = MagicMock()
container.get_task_manager.return_value = AsyncMock()
```

**Replacement:**
```python
# Factory pattern
from tests.fixtures import MockFactory
container = MockFactory.container()
```

**Migration Strategy:**
- Mark old test patterns in code reviews
- Provide examples of migrated tests
- Gradual migration as tests are modified

### 3. Direct File I/O in Tests
**Legacy Pattern:**
```python
# Using tmp_path fixture
def test_something(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("content")
```

**Replacement:**
```python
# File loader abstraction
from tests.fixtures import TestDataFactory
loader = TestDataFactory.file_loader({"test.txt": "content"})
```

**Migration Strategy:**
- Keep tmp_path working but discourage use
- Provide migration examples
- Update test templates

### 4. Dictionary-Based Pipeline Configuration
**Legacy Pattern:**
```python
pipeline_config = {
    "pipeline_id": "test",
    "steps": [{"name": "step1", "plugin": "plugin1"}]
}
```

**Replacement:**
```python
from src.core.pipeline_config import PipelineConfiguration, StepConfiguration
pipeline_config = PipelineConfiguration(
    pipeline_id="test",
    steps=[StepConfiguration(name="step1", plugin="plugin1")]
)
```

**Migration Strategy:**
- Support both patterns during transition
- Provide conversion utilities
- Update all examples

### 5. Thread-Local Event Loop Management
**Legacy Pattern:**
```python
# Thread-local storage for event loops
_thread_local.event_loop = asyncio.new_event_loop()
```

**Replacement:**
```python
# Centralized event loop manager
from src.core.event_loop_manager import EventLoopManager
loop = EventLoopManager.get_or_create_event_loop()
```

**Migration Strategy:**
- Automatic migration in most cases
- Document edge cases
- Provide compatibility layer

## Implementation Steps

### 1. Add Deprecation Decorators
```python
import warnings
from functools import wraps

def deprecated(reason):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__} is deprecated: {reason}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### 2. Update Documentation
- Add deprecation notices to affected APIs
- Update all examples to use new patterns
- Create migration guide with before/after examples

### 3. Provide Migration Tools
```python
# Automatic migration script
pdm run python scripts/migrate_to_v2.py --check
pdm run python scripts/migrate_to_v2.py --apply
```

### 4. Communication Plan
- Announce deprecation in release notes
- Send notifications to users
- Provide support during transition

## Backward Compatibility

### Compatibility Layer
Maintain compatibility layer for smooth transition:

```python
class ExecutionContext:
    # New method
    def get_config_parameter(self, key, default=None):
        return self.pipeline_configuration.get_parameter(key, default)
    
    # Legacy support
    def __getitem__(self, key):
        warnings.warn(
            "Dict-style access is deprecated. Use get_config_parameter()",
            DeprecationWarning
        )
        return self.get_config_parameter(key)
```

### Feature Flags
Allow users to opt into new behavior:

```python
# Environment variable
PRAXIS_USE_LEGACY_PATTERNS=false

# Configuration
{
    "compatibility": {
        "use_legacy_patterns": false
    }
}
```

## Migration Guide Structure

1. **Overview** - Why we're making changes
2. **Quick Start** - Minimal changes to get started
3. **Pattern Reference** - Old vs new patterns
4. **Common Issues** - Troubleshooting guide
5. **Tools** - Automated migration helpers
6. **Support** - How to get help

## Success Metrics

- 90% of internal code migrated before v2.0
- <5% of users report migration issues
- All major users migrated before v3.0
- No critical bugs from migration

## Risk Mitigation

1. **Extensive Testing** - Test both old and new patterns
2. **Gradual Rollout** - Feature flags for early adopters
3. **Clear Communication** - Multiple channels for updates
4. **Support Resources** - Dedicated migration support
5. **Rollback Plan** - Ability to revert if needed