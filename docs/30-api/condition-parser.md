# ConditionParser API Reference

The `ConditionParser` class provides safe evaluation of condition expressions used in pipeline control flow, supporting common comparison and logical operations while preventing execution of arbitrary code.

## Import

```python
from src.core.condition_parser import ConditionParser
```

## Class Definition

```python
class ConditionParser:
    """Parses and evaluates condition expressions safely."""
```

## Constructor

```python
def __init__(self) -> None
```

Creates a new condition parser instance with built-in expression caching for performance.

### Example
```python
parser = ConditionParser()
```

## Methods

### parse_expression

```python
def parse_expression(self, expr: str) -> ast.Expression
```

Parses a condition expression into an Abstract Syntax Tree (AST) for validation and evaluation.

#### Parameters
- **expr** (`str`): The condition expression to parse

#### Returns
- `ast.Expression`: Parsed and validated AST

#### Raises
- `ValueError`: If the expression contains unsafe operations or invalid syntax

#### Example
```python
parser = ConditionParser()
ast_expr = parser.parse_expression("score > 0.5 and status == 'active'")
```

### evaluate

```python
def evaluate(self, expr: str, context: Dict[str, Any]) -> Any
```

Safely evaluates a condition expression with the given context variables.

#### Parameters
- **expr** (`str`): The condition expression to evaluate
- **context** (`Dict[str, Any]`): Dictionary of variables available during evaluation

#### Returns
- `Any`: Result of the expression evaluation (typically `bool` for conditions)

#### Raises
- `ValueError`: If the expression is invalid or contains unsafe operations
- `KeyError`: If the expression references a variable not present in context
- `AttributeError`: If accessing non-existent attributes
- `TypeError`: If operations are performed on incompatible types

#### Examples

```python
parser = ConditionParser()

# Simple comparison
context = {"score": 0.75}
result = parser.evaluate("score > 0.5", context)  # True

# Multiple conditions
context = {"status": "active", "credits": 100}
result = parser.evaluate("status == 'active' and credits > 50", context)  # True

# Membership test
context = {"user_type": "premium", "allowed_types": ["premium", "enterprise"]}
result = parser.evaluate("user_type in allowed_types", context)  # True

# Attribute access
context = {"user": {"name": "Alice", "active": True}}
result = parser.evaluate("user.active == true", context)  # True

# Complex expression
context = {
    "score": 0.8,
    "threshold": 0.7,
    "retries": 2,
    "max_retries": 3,
    "force": False
}
result = parser.evaluate(
    "score > threshold and (retries < max_retries or force)", 
    context
)  # True
```

## Supported Operations

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal to | `status == 'active'` |
| `!=` | Not equal to | `error_code != 0` |
| `<` | Less than | `count < 100` |
| `<=` | Less than or equal | `score <= threshold` |
| `>` | Greater than | `value > minimum` |
| `>=` | Greater than or equal | `age >= 18` |
| `in` | Member of collection | `role in ['admin', 'moderator']` |
| `not in` | Not member of collection | `status not in ['deleted', 'banned']` |
| `is` | Identity check | `value is None` |
| `is not` | Negative identity | `result is not None` |

### Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `and` | Logical AND | `is_valid and has_permission` |
| `or` | Logical OR | `is_admin or is_moderator` |
| `not` | Logical NOT | `not is_expired` |

### Data Access

#### Attribute Access
Access object attributes using dot notation:
```python
# Context: {"user": {"profile": {"age": 25}}}
"user.profile.age > 18"
```

#### Dictionary Access
Access dictionary values using bracket notation:
```python
# Context: {"data": {"temperature": 72}}
"data['temperature'] < 80"
```

#### List Indexing
Access list elements by index:
```python
# Context: {"items": ["apple", "banana", "cherry"]}
"items[0] == 'apple'"
"items[-1] == 'cherry'"  # Negative indexing supported
```

### Literals

#### Boolean Literals
- `True`, `true`
- `False`, `false`

#### None/Null
- `None`, `null`

#### Numeric Literals
- Integers: `42`, `-10`, `0`
- Floats: `3.14`, `-0.5`, `1e10`

#### String Literals
- Single quotes: `'hello'`
- Double quotes: `"world"`

#### List Literals
```python
"value in [1, 2, 3]"
"status in ['pending', 'processing', 'complete']"
```

#### Dictionary Literals
```python
"config == {'debug': true, 'timeout': 30}"
```

## Safety Features

### Prevented Operations

The parser blocks potentially dangerous operations:

1. **Function Calls**
   ```python
   # NOT ALLOWED - will raise ValueError
   "eval('malicious code')"
   "os.system('rm -rf /')"
   "__import__('os').remove('file')"
   ```

2. **Lambda Expressions**
   ```python
   # NOT ALLOWED
   "lambda x: x * 2"
   ```

3. **Comprehensions**
   ```python
   # NOT ALLOWED
   "[x for x in range(10)]"
   "{k: v for k, v in items}"
   ```

4. **Arithmetic Operations** (by default)
   ```python
   # NOT ALLOWED - could be used for DoS
   "10 ** 1000000"
   ```

### Expression Validation

The parser validates expressions before evaluation:

```python
parser = ConditionParser()

# Valid expressions
parser.parse_expression("status == 'active'")  # OK
parser.parse_expression("score > 0.5 and verified")  # OK

# Invalid expressions raise ValueError
try:
    parser.parse_expression("__import__('os')")
except ValueError as e:
    print(f"Blocked: {e}")  # Function calls not allowed

try:
    parser.parse_expression("2 + 2")  # Arithmetic not allowed by default
except ValueError as e:
    print(f"Blocked: {e}")
```

## Performance Considerations

### Expression Caching

Parsed expressions are cached to improve performance:

```python
parser = ConditionParser()

# First evaluation parses the expression
parser.evaluate("score > 0.5", {"score": 0.6})  # Parses and caches

# Subsequent evaluations use cached AST
parser.evaluate("score > 0.5", {"score": 0.3})  # Uses cache
parser.evaluate("score > 0.5", {"score": 0.8})  # Uses cache
```

### Best Practices for Performance

1. **Reuse parser instances** to benefit from caching
2. **Use simple expressions** when possible
3. **Avoid deeply nested attribute access**
4. **Pre-validate expressions** during pipeline development

## Error Handling

### Common Errors and Solutions

#### ValueError: Invalid Expression
```python
try:
    parser.evaluate("2 +", {})  # Syntax error
except ValueError as e:
    print(f"Invalid expression: {e}")
```

#### KeyError: Missing Variable
```python
try:
    parser.evaluate("score > 0.5", {})  # 'score' not in context
except KeyError as e:
    print(f"Missing variable: {e}")
```

#### AttributeError: Invalid Attribute
```python
try:
    context = {"user": {"name": "Alice"}}
    parser.evaluate("user.age > 18", context)  # 'age' doesn't exist
except AttributeError as e:
    print(f"Invalid attribute: {e}")
```

### Defensive Evaluation

```python
def safe_evaluate(parser, expr, context, default=False):
    """Safely evaluate with a default return value."""
    try:
        return parser.evaluate(expr, context)
    except (ValueError, KeyError, AttributeError, TypeError):
        return default

# Usage
result = safe_evaluate(parser, "user.premium == true", context, default=False)
```

## Integration with Pipeline

### In YAML Pipelines

```yaml
steps:
  - name: validate_data
    plugin: validator
    
  - name: process_premium
    plugin: premium_processor
    depends_on:
      - step: validate_data
        when: "is_valid == true and user_tier == 'premium'"
```

### With PipelineBuilder

```python
builder.step("process", depends_on=[
    ("validate", "validation_score > 0.8"),
    ("authorize", "user.permissions.can_process == true")
])
```

### In Loop Conditions

```yaml
loop_config:
  condition: "retry_count < max_retries and not success"
  max_iterations: 10
  body:
    - name: attempt_operation
      plugin: operation_handler
```

## Complete Example

```python
from src.core.condition_parser import ConditionParser

# Create parser
parser = ConditionParser()

# Pipeline execution context
context = {
    "user": {
        "id": 123,
        "type": "premium",
        "credits": 150,
        "settings": {
            "notifications": True,
            "theme": "dark"
        }
    },
    "data": {
        "size": 1024,
        "format": "json",
        "compressed": False
    },
    "limits": {
        "max_size": 10240,
        "allowed_formats": ["json", "xml", "csv"]
    },
    "processing": {
        "attempts": 2,
        "max_attempts": 3,
        "status": "pending"
    }
}

# Evaluate various conditions
conditions = [
    ("user.type == 'premium'", True),
    ("user.credits > 100", True),
    ("data.size < limits.max_size", True),
    ("data.format in limits.allowed_formats", True),
    ("processing.attempts < processing.max_attempts", True),
    ("user.settings.notifications and user.settings.theme == 'dark'", True),
    ("data.compressed or data.size > 5000", False),
    ("processing.status != 'failed' and processing.attempts <= 3", True)
]

for expr, expected in conditions:
    result = parser.evaluate(expr, context)
    print(f"{expr:60} => {result} (expected: {expected})")
    assert result == expected
```

## Tips and Tricks

### 1. Null-Safe Access
```python
# Check for null before accessing
"user is not None and user.active == true"
```

### 2. Default Values
```python
# Use 'or' for defaults
"timeout or 30"  # Use 30 if timeout is falsy
```

### 3. Type Checking
```python
# Although type() isn't allowed, use duck typing
"'append' in dir(value)"  # Check if value is list-like
```

### 4. Complex Logic
```python
# Break complex conditions into multiple steps
step1: "basic_validation"
step2: "advanced_validation" depends_on: [("step1", "is_valid")]
step3: "process" depends_on: [("step2", "all_checks_passed")]
```

## See Also

- [PipelineBuilder API](pipeline-builder.md)
- [ConditionalDependency](conditional-dependency.md)
- [Enhanced Control Flow Guide](../enhanced-control-flow-guide.md)