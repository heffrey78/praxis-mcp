# Enhanced Control Flow API Reference

This document provides a comprehensive API reference for the enhanced control flow features in Praxis.

## Table of Contents

1. [PipelineBuilder](#pipelinebuilder)
2. [ConditionParser](#conditionparser)
3. [ConditionalDependency](#conditionaldependency)
4. [LoopConfig](#loopconfig)
5. [YAML Schema Reference](#yaml-schema-reference)

---

## PipelineBuilder

The `PipelineBuilder` class provides a fluent API for constructing pipelines programmatically.

### Class: `PipelineBuilder`

```python
from src.core.pipeline_builder import PipelineBuilder
```

#### Constructor

```python
PipelineBuilder(pipeline_id: Optional[str] = None)
```

Creates a new pipeline builder instance.

**Parameters:**
- `pipeline_id` (Optional[str]): Unique identifier for the pipeline. If not provided, a UUID will be generated.

**Example:**
```python
builder = PipelineBuilder("my-pipeline")
# or
builder = PipelineBuilder()  # Auto-generates ID
```

#### Methods

##### `with_name(name: str) -> PipelineBuilder`

Sets the human-readable name for the pipeline.

**Parameters:**
- `name` (str): Display name for the pipeline

**Returns:** Self for method chaining

**Example:**
```python
builder.with_name("Customer Data Processing")
```

##### `with_description(description: str) -> PipelineBuilder`

Sets the pipeline description.

**Parameters:**
- `description` (str): Description of the pipeline's purpose

**Returns:** Self for method chaining

**Example:**
```python
builder.with_description("Processes customer data with validation")
```

##### `with_param(name: str, param_type: str = "string", required: bool = True, description: str = "", default: Any = None) -> PipelineBuilder`

Adds a parameter definition to the pipeline.

**Parameters:**
- `name` (str): Parameter name
- `param_type` (str): Type of the parameter ("string", "int", "float", "bool", "list", "dict")
- `required` (bool): Whether the parameter is required (default: True)
- `description` (str): Description of the parameter
- `default` (Any): Default value if not required

**Returns:** Self for method chaining

**Example:**
```python
builder.with_param("input_file", "string", required=True, description="Path to input file")
builder.with_param("batch_size", "int", default=1000, required=False)
```

##### `step(plugin: str, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None, fail_on_error: bool = True, depends_on: Optional[List[Union[str, Tuple[str, str]]]] = None) -> PipelineBuilder`

Adds a step to the pipeline.

**Parameters:**
- `plugin` (str): Name of the plugin to execute
- `name` (Optional[str]): Name of the step (auto-generated if not provided)
- `config` (Optional[Dict[str, Any]]): Configuration for the plugin
- `fail_on_error` (bool): Whether pipeline should fail if step fails (default: True)
- `depends_on` (Optional[List[Union[str, Tuple[str, str]]]]): Dependencies with optional conditions

**Returns:** Self for method chaining

**Example:**
```python
builder.step("data_loader", config={"path": "${input_file}"})
builder.step("validator", name="validate_data", fail_on_error=False)
builder.step("processor", depends_on=[("validator", "is_valid == true")])
```

##### `branch(*branches: Tuple[str, Callable[[PipelineBuilder], PipelineBuilder]]) -> PipelineBuilder`

Creates conditional branches in the pipeline.

**Parameters:**
- `*branches` (Tuple[str, Callable]): Tuples of (condition, builder_function)

**Returns:** Self for method chaining

**Example:**
```python
builder.branch(
    ("score > 0.8", lambda b: b.step("high_quality_processor")),
    ("score > 0.5", lambda b: b.step("medium_quality_processor")),
    ("score <= 0.5", lambda b: b.step("low_quality_processor"))
)
```

##### `loop_for_each(collection: str, body: Callable[[PipelineBuilder], PipelineBuilder], item_name: str = "item", index_name: str = "index", result_name: Optional[str] = None, fail_fast: bool = True) -> PipelineBuilder`

Creates a for-each loop over a collection.

**Parameters:**
- `collection` (str): Name of the collection variable to iterate over
- `body` (Callable): Function that builds the loop body
- `item_name` (str): Variable name for current item (default: "item")
- `index_name` (str): Variable name for current index (default: "index")
- `result_name` (Optional[str]): Variable to store results
- `fail_fast` (bool): Whether to stop on first error (default: True)

**Returns:** Self for method chaining

**Example:**
```python
builder.loop_for_each(
    "files",
    lambda b: b
        .step("validate_file", config={"file": "${current_file}"})
        .step("process_file"),
    item_name="current_file",
    result_name="processed_files"
)
```

##### `loop_count(count: Union[int, str], body: Callable[[PipelineBuilder], PipelineBuilder], index_name: str = "index") -> PipelineBuilder`

Creates a count-based loop.

**Parameters:**
- `count` (Union[int, str]): Number of iterations or variable name
- `body` (Callable): Function that builds the loop body
- `index_name` (str): Variable name for current index (default: "index")

**Returns:** Self for method chaining

**Example:**
```python
builder.loop_count(
    3,
    lambda b: b
        .step("retry_api_call", config={"attempt": "${attempt}"})
        .step("check_response"),
    index_name="attempt"
)
```

##### `loop_while(condition: str, body: Callable[[PipelineBuilder], PipelineBuilder], max_iterations: int = 100) -> PipelineBuilder`

Creates a while loop that continues while condition is true.

**Parameters:**
- `condition` (str): Condition expression to evaluate
- `body` (Callable): Function that builds the loop body
- `max_iterations` (int): Maximum iterations to prevent infinite loops (default: 100)

**Returns:** Self for method chaining

**Example:**
```python
builder.loop_while(
    "status != 'completed'",
    lambda b: b
        .step("check_status")
        .step("wait", config={"seconds": 10}),
    max_iterations=60
)
```

##### `parallel(*branches: Callable[[PipelineBuilder], PipelineBuilder]) -> PipelineBuilder`

Creates parallel execution branches.

**Parameters:**
- `*branches` (Callable): Functions that build parallel branches

**Returns:** Self for method chaining

**Example:**
```python
builder.parallel(
    lambda b: b.step("analyze_text"),
    lambda b: b.step("analyze_images"),
    lambda b: b.step("analyze_metadata")
)
```

##### `build() -> PipelineDefinition`

Builds and returns the pipeline definition.

**Returns:** PipelineDefinition object

**Raises:**
- `ValueError`: If the pipeline is invalid (e.g., circular dependencies)

**Example:**
```python
pipeline = builder.build()
```

##### `to_yaml(path: Optional[Union[str, Path]] = None) -> str`

Exports the pipeline to YAML format.

**Parameters:**
- `path` (Optional[Union[str, Path]]): File path to save the YAML

**Returns:** YAML string representation

**Example:**
```python
# Get YAML string
yaml_content = builder.to_yaml()

# Save to file
builder.to_yaml("my_pipeline.yaml")
```

---

## ConditionParser

The `ConditionParser` class safely evaluates condition expressions used in pipeline control flow.

### Class: `ConditionParser`

```python
from src.core.condition_parser import ConditionParser
```

#### Constructor

```python
ConditionParser()
```

Creates a new condition parser instance with expression caching.

#### Methods

##### `parse_expression(expr: str) -> ast.Expression`

Parses a condition expression into an AST (Abstract Syntax Tree).

**Parameters:**
- `expr` (str): Condition expression to parse

**Returns:** Parsed AST expression

**Raises:**
- `ValueError`: If expression contains unsafe operations

**Example:**
```python
parser = ConditionParser()
ast_expr = parser.parse_expression("score > 0.5 and status == 'active'")
```

##### `evaluate(expr: str, context: Dict[str, Any]) -> Any`

Safely evaluates a condition expression with the given context.

**Parameters:**
- `expr` (str): Condition expression to evaluate
- `context` (Dict[str, Any]): Variables available for evaluation

**Returns:** Result of the expression (typically bool)

**Raises:**
- `ValueError`: If expression is invalid or unsafe
- `KeyError`: If referenced variable not in context

**Example:**
```python
parser = ConditionParser()
context = {"score": 0.7, "status": "active"}
result = parser.evaluate("score > 0.5 and status == 'active'", context)
# result = True
```

#### Supported Operators

##### Comparison Operators
- `==` (equal)
- `!=` (not equal)
- `<` (less than)
- `<=` (less than or equal)
- `>` (greater than)
- `>=` (greater than or equal)
- `in` (membership test)
- `not in` (negative membership test)
- `is` (identity test)
- `is not` (negative identity test)

##### Logical Operators
- `and` (logical AND)
- `or` (logical OR)
- `not` (logical NOT)

##### Data Access
- Attribute access: `user.name`, `config.timeout`
- Dictionary access: `data['key']`, `params["value"]`
- List indexing: `items[0]`, `results[-1]`

#### Safety Features

The parser prevents execution of arbitrary code by:
- Disallowing function calls
- Restricting to approved operators
- Validating AST before evaluation
- No access to builtins or imports

---

## ConditionalDependency

The `ConditionalDependency` class represents a dependency with an inline condition.

### Class: `ConditionalDependency`

```python
from src.core.step_config import ConditionalDependency
```

#### Constructor

```python
ConditionalDependency(step: str, when: str)
```

Creates a conditional dependency.

**Parameters:**
- `step` (str): Name of the step to depend on
- `when` (str): Condition expression that must be true

**Example:**
```python
dep = ConditionalDependency(step="validator", when="is_valid == true")
```

#### Attributes

- `step` (str): The step name to depend on
- `when` (str): The condition expression

#### Usage in StepConfig

```python
step = StepConfig(
    name="process_data",
    plugin="processor",
    depends_on=[
        ConditionalDependency(step="validator", when="is_valid == true"),
        ConditionalDependency(step="checker", when="quality_score > 0.8")
    ]
)
```

---

## LoopConfig

The `LoopConfig` class defines loop execution parameters.

### Class: `LoopConfig`

```python
from src.core.step_config import LoopConfig
```

#### Constructor

```python
LoopConfig(
    collection: Optional[str] = None,
    item_name: str = "item",
    index_name: str = "index",
    count: Optional[Union[int, str]] = None,
    condition: Optional[str] = None,
    max_iterations: int = 100,
    fail_fast: bool = True,
    result_name: Optional[str] = None,
    body: Optional[List[StepConfig]] = None
)
```

Creates a loop configuration.

**Parameters:**
- `collection` (Optional[str]): Collection variable name (for-each loops)
- `item_name` (str): Variable name for current item (default: "item")
- `index_name` (str): Variable name for current index (default: "index")
- `count` (Optional[Union[int, str]]): Number of iterations (count loops)
- `condition` (Optional[str]): Continue condition (while loops)
- `max_iterations` (int): Maximum iterations for safety (default: 100)
- `fail_fast` (bool): Stop on first error (default: True)
- `result_name` (Optional[str]): Variable to collect results
- `body` (Optional[List[StepConfig]]): Steps to execute in loop

#### Loop Types

##### For-Each Loop
```python
config = LoopConfig(
    collection="items",
    item_name="current_item",
    body=[...]
)
```

##### Count Loop
```python
config = LoopConfig(
    count=5,
    index_name="attempt",
    body=[...]
)
```

##### While Loop
```python
config = LoopConfig(
    condition="status != 'done'",
    max_iterations=50,
    body=[...]
)
```

---

## YAML Schema Reference

### Pipeline Definition

```yaml
id: string  # Required: Unique pipeline identifier
name: string  # Required: Human-readable name
description: string  # Optional: Pipeline description

parameters:  # Optional: Pipeline parameters
  - name: string  # Required: Parameter name
    type: string  # Required: string|int|float|bool|list|dict
    required: boolean  # Optional: Default true
    default: any  # Optional: Default value
    description: string  # Optional: Parameter description

steps:  # Required: List of pipeline steps
  - name: string  # Required: Step name
    plugin: string  # Required: Plugin to execute
    config: dict  # Optional: Plugin configuration
    fail_on_error: boolean  # Optional: Default true
    depends_on:  # Optional: Dependencies
      - string  # Simple dependency
      - step: string  # Conditional dependency
        when: string  # Condition expression
    loop_config:  # Optional: Loop configuration
      # See LoopConfig section
```

### Conditional Dependencies

```yaml
depends_on:
  - step: previous_step
    when: "result == 'success'"
  - step: validator
    when: "score > 0.8 and not has_errors"
```

### Loop Configurations

#### For-Each Loop
```yaml
loop_config:
  collection: items
  item_name: current_item
  index_name: idx
  result_name: processed_items
  fail_fast: false
  body:
    - name: process_item
      plugin: processor
```

#### Count Loop
```yaml
loop_config:
  count: 3
  index_name: retry_num
  body:
    - name: attempt
      plugin: api_caller
```

#### While Loop
```yaml
loop_config:
  condition: "not finished"
  max_iterations: 100
  body:
    - name: check_status
      plugin: status_checker
```

### Variable References

Use `${}` syntax to reference variables:

```yaml
config:
  input: "${file_path}"
  size: "${batch_size}"
  current: "${item}"  # In loops
  index: "${index}"   # In loops
```

### Expression Examples

```yaml
# Simple comparisons
when: "status == 'active'"
when: "count > 100"
when: "score >= 0.5"

# Logical operations
when: "is_valid and not has_errors"
when: "status == 'active' or priority == 'high'"

# Membership tests
when: "user_type in ['premium', 'enterprise']"
when: "region not in blocked_regions"

# Attribute access
when: "user.subscription.active == true"
when: "response.status_code == 200"

# Complex conditions
when: "score > threshold and (retries < max_retries or force_retry)"
```

---

## Error Handling

### Common Exceptions

#### `ValueError`
- Invalid pipeline structure
- Circular dependencies
- Invalid condition expressions
- Missing required parameters

#### `KeyError`
- Referenced variable not in context
- Missing step in dependencies

#### `RuntimeError`
- Loop maximum iterations exceeded
- Pipeline execution failures

### Best Practices

1. **Always set max_iterations** for while loops
2. **Use fail_fast appropriately** in loops
3. **Validate expressions** before deployment
4. **Handle missing variables** gracefully
5. **Test all condition branches**

---

## Performance Considerations

### Expression Caching
- Condition expressions are parsed once and cached
- Reuse common expressions for better performance

### Loop Optimization
- Use `fail_fast: false` for resilient batch processing
- Consider chunking large collections
- Set appropriate `max_iterations` limits

### Parallel Execution
- Independent steps run concurrently by default
- Use explicit dependencies to control ordering
- Consider resource constraints

---

## Detailed API Documentation

For more detailed documentation of individual APIs, see:

- [PipelineBuilder API](api/pipeline-builder.md) - Complete method reference with examples
- [ConditionParser API](api/condition-parser.md) - Expression syntax and safety features
- [ConditionalDependency API](api/conditional-dependency.md) - Dependency configuration details
- [LoopConfig API](api/loop-config.md) - Loop types and configuration options
- [API Index](api/index.md) - Overview of all APIs

## See Also

- [Enhanced Control Flow Guide](enhanced-control-flow-guide.md)
- [Quick Reference](enhanced-control-flow-quick-reference.md)
- [Example Pipelines](../examples/control-flow/)