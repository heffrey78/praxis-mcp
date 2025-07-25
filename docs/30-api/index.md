# Enhanced Control Flow API Documentation

This directory contains detailed API reference documentation for all enhanced control flow classes and components.

## Core APIs

### [PipelineBuilder](pipeline-builder.md)
Fluent API for programmatically constructing pipelines with enhanced control flow features.

**Key Features:**
- Method chaining for intuitive pipeline construction
- Built-in support for conditions, loops, and branching
- YAML export functionality
- Type-safe parameter definitions

**Example:**
```python
pipeline = (
    PipelineBuilder("my-pipeline")
    .with_param("input", "string", required=True)
    .step("process")
    .branch(
        ("success", lambda b: b.step("handle_success")),
        ("failure", lambda b: b.step("handle_failure"))
    )
    .build()
)
```

### [ConditionParser](condition-parser.md)
Safe expression evaluator for pipeline conditions with security features.

**Key Features:**
- Safe evaluation preventing code injection
- Support for comparison and logical operators
- Expression caching for performance
- Comprehensive error handling

**Example:**
```python
parser = ConditionParser()
result = parser.evaluate("score > 0.8 and status == 'active'", context)
```

### [ConditionalDependency](conditional-dependency.md)
Represents step dependencies with inline conditions.

**Key Features:**
- Replace legacy .true/.false patterns
- Rich condition expressions
- Full pipeline context access
- Integration with ConditionParser

**Example:**
```python
dependency = ConditionalDependency(
    step="validate",
    when="is_valid == true and score > threshold"
)
```

### [LoopConfig](loop-config.md)
Configuration for loop execution in pipelines.

**Key Features:**
- Three loop types: for-each, count, while
- Safety limits to prevent infinite loops
- Result collection from iterations
- Flexible error handling with fail_fast

**Example:**
```python
loop = LoopConfig(
    collection="items",
    item_name="current_item",
    fail_fast=False,
    result_name="processed_items"
)
```

## Quick Reference

### Creating a Pipeline
```python
from src.core.pipeline_builder import PipelineBuilder

pipeline = PipelineBuilder("pipeline-id")
    .with_name("My Pipeline")
    .with_param("param1", "string")
    .step("step1")
    .build()
```

### Adding Conditions
```yaml
depends_on:
  - step: previous_step
    when: "result == 'success'"
```

### Creating Loops
```yaml
loop_config:
  collection: items
  body:
    - name: process_item
      plugin: processor
```

### Evaluating Expressions
```python
parser = ConditionParser()
context = {"score": 0.9}
result = parser.evaluate("score > 0.5", context)
```

## Common Patterns

### Conditional Execution
```python
builder.step("validate")
builder.branch(
    ("is_valid", lambda b: b.step("process")),
    ("not is_valid", lambda b: b.step("handle_error"))
)
```

### Retry Logic
```python
builder.loop_count(3, lambda b: b
    .step("attempt")
    .step("check", depends_on=[("attempt", "failed")])
)
```

### Parallel Processing
```python
builder.parallel(
    lambda b: b.step("task1"),
    lambda b: b.step("task2"),
    lambda b: b.step("task3")
)
```

## YAML Schema

### Pipeline Structure
```yaml
id: pipeline-id
name: Pipeline Name
parameters:
  - name: param1
    type: string
    required: true
steps:
  - name: step1
    plugin: plugin_name
    depends_on:
      - step: previous
        when: "condition"
    loop_config:
      # Loop configuration
```

### Supported Types
- `string` - Text values
- `int` - Integer numbers
- `float` - Decimal numbers
- `bool` - True/false values
- `list` - Arrays/lists
- `dict` - Key-value mappings

## Best Practices

1. **Use Type Hints** - Always specify parameter types
2. **Set Limits** - Always set max_iterations for loops
3. **Handle Errors** - Use fail_on_error appropriately
4. **Keep Conditions Simple** - Complex logic should be in plugins
5. **Document Intent** - Use descriptive names and descriptions

## Troubleshooting

### Common Issues

1. **Circular Dependencies** - Check step dependencies
2. **Missing Variables** - Ensure context has required variables
3. **Infinite Loops** - Set appropriate max_iterations
4. **Invalid Expressions** - Test with ConditionParser

### Debug Tips

```python
# Test condition parsing
parser = ConditionParser()
parser.parse_expression("your condition here")

# Validate pipeline structure
pipeline = builder.build()  # Will raise if invalid
```

## Related Documentation

- [Enhanced Control Flow Guide](../enhanced-control-flow-guide.md)
- [Quick Reference](../enhanced-control-flow-quick-reference.md)
- [Examples](../../examples/control-flow/)
- [Main API Reference](../api-reference.md)

## Version Information

This documentation covers the enhanced control flow APIs introduced in version 2.0, which replace the legacy conditional dependency patterns.