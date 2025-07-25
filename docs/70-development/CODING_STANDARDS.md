# Praxis Backend Coding Standards

This document defines the coding standards, linting rules, and type checking requirements for the Praxis backend. All code must adhere to these standards.

## 🚨 CRITICAL RULES - NEVER VIOLATE THESE

1. **ALWAYS use PDM for all Python operations**
   - ❌ `pytest` → ✅ `pdm run pytest`
   - ❌ `python script.py` → ✅ `pdm run python script.py`
   - ❌ `mypy` → ✅ `pdm run mypy`

2. **NEVER use `# type: ignore`**
   - This is strictly forbidden - fix the root cause instead
   - Create proper type stubs or protocol types for external libraries
   - Refactor code to be properly typed

3. **NEVER access protected members from outside their class**
   - ❌ `context._data` → ✅ `context.get_data()`
   - ❌ `obj._private` → ✅ Use public methods
   - Only exception: backwards compatibility with clear documentation

## 📝 Type Annotations (MyPy)

### Configuration (from pyproject.toml)
```toml
[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true  # ALL functions must have type annotations
ignore_missing_imports = true  # External libs without types are OK
```

### Requirements
1. **Every function must be fully typed**:
   ```python
   # ❌ Bad
   def process(data):
       return data
   
   # ✅ Good
   def process(data: Dict[str, Any]) -> Dict[str, Any]:
       return data
   ```

2. **Use proper type imports**:
   ```python
   from __future__ import annotations  # If needed for forward refs
   from typing import TYPE_CHECKING, Any, Dict, List, Optional, ClassVar
   
   if TYPE_CHECKING:
       from src.core.context import PipelineContext  # Import cycles
   ```

3. **Class attributes must be typed**:
   ```python
   class MyPlugin(PluginBase):
       plugin_type: ClassVar[PluginType] = PluginType.TRANSFORM
       max_retries: int = 3
       _cache: Dict[str, Any] = {}  # Even private attrs
   ```

## 🔧 Ruff Linting Rules

### Active Rules (Phase 1, 2 & 4)
- **F** - Pyflakes (basic Python errors)
- **E4, E7, E9** - Import, statement, and runtime errors
- **I** - isort (import sorting)
- **F401** - Remove unused imports
- **TCH** - Move type-checking imports to TYPE_CHECKING block
- **B** - flake8-bugbear (bug detection)
- **C4** - flake8-comprehensions
- **DTZ** - flake8-datetimez (timezone awareness)
- **ISC** - flake8-implicit-str-concat
- **PIE** - flake8-pie (misc lints)
- **PT** - flake8-pytest-style
- **RET** - flake8-return
- **SIM** - flake8-simplify
- **TID** - flake8-tidy-imports
- **ARG** - flake8-unused-arguments
- **PTH** - flake8-use-pathlib

### Import Organization
```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# 3. Third-party
import pytest
from pydantic import BaseModel, Field

# 4. First-party (src.*)
from src.core.context import PipelineContext
from src.core.plugin_types import PluginType

# 5. Local/relative
from .models import ShellCommandInput
from .types import CommandExecutionResult
```

### Common Fixes
1. **Use pathlib instead of os.path (PTH)**:
   ```python
   # ❌ Bad
   import os
   file_path = os.path.join(dir, "file.txt")
   
   # ✅ Good
   from pathlib import Path
   file_path = Path(dir) / "file.txt"
   ```

2. **Simplify code (SIM)**:
   ```python
   # ❌ Bad
   if x == True:
       return True
   else:
       return False
   
   # ✅ Good
   return x
   ```

3. **Use comprehensions properly (C4)**:
   ```python
   # ❌ Bad
   result = list(x for x in items)
   
   # ✅ Good
   result = [x for x in items]
   ```

4. **Pytest style (PT)**:
   ```python
   # ❌ Bad
   @pytest.fixture
   def my_fixture():
       ...
   
   @pytest.mark.asyncio
   async def test_something():
       ...
   
   with pytest.raises(ValueError):
       ...
   
   # ✅ Good
   @pytest.fixture()  # PT001: Always use parentheses
   def my_fixture():
       ...
   
   @pytest.mark.asyncio()  # PT023: Always use parentheses for marks
   async def test_something():
       ...
   
   with pytest.raises(ValueError, match="specific error"):  # PT011: Set match parameter
       ...
   ```

5. **Remove unused imports (F401)**:
   ```python
   # ❌ Bad
   import os  # Never used
   from typing import Dict, Any  # Only Dict used
   
   # ✅ Good
   from typing import Dict  # Only import what you use
   ```

## 🔍 Pyright Type Checking

### Configuration (from pyrightconfig.json)
- `typeCheckingMode: "standard"`
- `reportUnnecessaryTypeIgnoreComment: "error"`
- `reportPrivateUsage: "warning"`
- Python version: 3.11

### Key Requirements
1. **No unnecessary type comments**
2. **Avoid accessing private members**
3. **Proper type variance in generics**
4. **ClassVar overrides are warnings** - When implementing plugins, overriding ClassVar attributes (InputModel, OutputModel, ConfigModel) will generate warnings but is the intended pattern

## 🚫 Banned Patterns

### No Print Statements in Core Code
```python
# ❌ Bad (in src/core/*, src/services/*, src/plugins/*)
print(f"Processing {item}")

# ✅ Good
logger.info(f"Processing {item}")
```

### No Shell=True in Subprocess
```python
# ❌ Bad - Security risk
subprocess.run(cmd, shell=True)

# ❌ Bad - preexec_fn not supported everywhere
await asyncio.create_subprocess_exec(
    *cmd_parts,
    preexec_fn=os.setsid
)

# ✅ Good - Use start_new_session for process groups
await asyncio.create_subprocess_exec(
    *cmd_parts,
    start_new_session=True  # Creates new process group on Unix
)

# ✅ Good - Platform-specific handling
if os.name != 'nt':
    # Unix: can use process groups
    process = await asyncio.create_subprocess_exec(
        *cmd_parts,
        start_new_session=True
    )
else:
    # Windows: no process group
    process = await asyncio.create_subprocess_exec(*cmd_parts)
```

### Proper Async Patterns
```python
# ❌ Bad
def get_data():
    return requests.get(url).json()

# ✅ Good
async def get_data() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        return response.json()
```

## ✅ Testing Standards

### Pytest Style Requirements (PT rules)
```python
# ✅ ALWAYS use parentheses on decorators
@pytest.fixture()  # NOT @pytest.fixture
@pytest.mark.asyncio()  # NOT @pytest.mark.asyncio
@pytest.mark.unit()  # NOT @pytest.mark.unit

# ✅ ALWAYS specify match parameter for pytest.raises
with pytest.raises(ValueError, match="specific error message"):
    ...  # NOT just pytest.raises(ValueError)

# ✅ Import only what you use
from unittest.mock import Mock  # NOT Mock, patch if only using Mock
```

### Test Naming
```python
# Pattern: test_<what>_<condition>_<expected>
def test_withdraw_insufficient_funds_raises_error():
    ...

def test_parse_json_valid_input_returns_dict():
    ...
```

### Pytest Markers
```python
@pytest.mark.unit()  # Note the parentheses!
async def test_simple_logic():
    ...

@pytest.mark.integration()  # Note the parentheses!
async def test_database_interaction():
    ...
```

### AAA Pattern
```python
async def test_shell_command_timeout():
    # Arrange
    plugin = ShellCommandPlugin()
    config = ShellCommandConfig(command="sleep 10", timeout=1)
    
    # Act
    with pytest.raises(RuntimeError) as exc_info:
        await plugin.run(context)
    
    # Assert
    assert "timed out" in str(exc_info.value)
```

## 🏗️ Code Structure

### Plugin Structure
```
src/plugins/<category>/<plugin_name>/
├── __init__.py       # Empty or minimal imports
├── types.py          # Internal types (dataclasses)
├── models.py         # Pydantic models (public interface)
└── plugin.py         # Plugin implementation
```

### Model Definition Pattern
```python
# models.py
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

class PluginOutput(BaseModel):
    """Public output interface."""
    
    result: str = Field(..., description="The result")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        json_schema_extra={
            "output_types": ["result", "metadata"],
            "output_descriptions": {
                "result": "Main result",
                "metadata": "Additional data"
            }
        }
    )
    
    @field_validator('result')
    @classmethod
    def validate_result(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Result cannot be empty")
        return v
```

## 🎯 Pydantic v2 Best Practices

### Field Validators
```python
# ✅ CORRECT: Field validators raise ValueError
@field_validator('command')
@classmethod
def validate_command(cls, v: str) -> str:
    if dangerous_pattern.search(v):
        raise ValueError("Command is dangerous")  # Gets wrapped in ValidationError
    return v

# ❌ WRONG: Don't raise ValidationError directly in validators
@field_validator('command')
@classmethod
def validate_command(cls, v: str) -> str:
    if dangerous_pattern.search(v):
        raise ValidationError("Command is dangerous")  # Don't do this!
    return v
```

### Model Configuration
```python
# ✅ Use ConfigDict (Pydantic v2)
from pydantic import ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",  # Don't allow extra fields
        validate_assignment=True,  # Validate on assignment
        arbitrary_types_allowed=True,  # Allow non-pydantic types
    )

# ❌ Don't use class Config (deprecated)
class MyModel(BaseModel):
    class Config:  # This triggers deprecation warning!
        extra = "forbid"
```

### Common Pydantic v2 Patterns
```python
# Field with validation
from pydantic import field_validator, model_validator

class MyModel(BaseModel):
    # Simple field with constraints
    age: int = Field(ge=0, le=150, description="Age in years")
    
    # Field with custom validation
    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        if v < 18:
            raise ValueError("Must be 18 or older")
        return v
    
    # Model-level validation (access to all fields)
    @model_validator(mode='after')
    def validate_model(self) -> 'MyModel':
        # Access self.field_name here
        return self

# Computed fields
from pydantic import computed_field

class MyModel(BaseModel):
    first_name: str
    last_name: str
    
    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

### Exception Handling
```python
# When using Pydantic models
from pydantic import ValidationError

try:
    model = MyModel(invalid_data="bad")
except ValidationError as e:
    # e.errors() returns list of error dicts
    # str(e) returns formatted error message
    print(f"Validation failed: {e}")
```

## 🔄 Pre-commit Hooks

Run before every commit:
```bash
pdm run pre-commit run --all-files
```

Checks performed:
1. Ruff linting and formatting
2. MyPy type checking (non-blocking)
3. Pyright type checking (non-blocking)
4. Bandit security scanning
5. No print statements in core code
6. Trailing whitespace removal
7. YAML/JSON validation

## 📋 Pre-Implementation Checklist

Before writing any code:
- [ ] Identify all required type annotations
- [ ] Plan import structure (stdlib → third-party → first-party → local)
- [ ] Use pathlib for all path operations
- [ ] Plan error handling with proper exception types
- [ ] Design with public interfaces (no protected member access)
- [ ] Consider async/await patterns
- [ ] Plan comprehensive type hints including return types

## 🎯 Quick Reference

### Common Type Patterns
```python
# Optional with default
field: Optional[str] = None

# Class variables
plugin_type: ClassVar[PluginType] = PluginType.TRANSFORM

# Forward references
def process(self, context: "PipelineContext") -> None:

# Type aliases
JsonDict = Dict[str, Any]

# Callable types
from typing import Callable
handler: Callable[[str], Awaitable[None]]
```

### Async Best Practices
```python
# Resource cleanup
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# Concurrent execution
results = await asyncio.gather(
    fetch_data(),
    process_data(),
    save_results()
)

# Timeout handling
try:
    result = await asyncio.wait_for(operation(), timeout=30)
except asyncio.TimeoutError:
    logger.error("Operation timed out")
```

Remember: When in doubt, be explicit with types and follow existing patterns in the codebase.