# LoopConfig API Reference

The `LoopConfig` class defines loop execution parameters for iterative pipeline steps, supporting for-each, count-based, and while loops.

## Import

```python
from src.core.step_config import LoopConfig
```

## Class Definition

```python
@dataclass
class LoopConfig:
    """Configuration for loop execution in pipeline steps."""
    collection: Optional[str] = None
    item_name: str = "item"
    index_name: str = "index"
    count: Optional[Union[int, str]] = None
    condition: Optional[str] = None
    max_iterations: int = 100
    fail_fast: bool = True
    result_name: Optional[str] = None
    body: Optional[List[StepConfig]] = None
```

## Constructor

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

Creates a loop configuration for pipeline execution.

### Parameters

- **collection** (`Optional[str]`): Name of the collection variable to iterate over (for-each loops)
- **item_name** (`str`): Variable name for the current item in iteration (default: `"item"`)
- **index_name** (`str`): Variable name for the current index (default: `"index"`)
- **count** (`Optional[Union[int, str]]`): Number of iterations for count-based loops
- **condition** (`Optional[str]`): Continue condition for while loops
- **max_iterations** (`int`): Maximum iterations to prevent infinite loops (default: `100`)
- **fail_fast** (`bool`): Whether to stop on first error (default: `True`)
- **result_name** (`Optional[str]`): Variable name to collect results from iterations
- **body** (`Optional[List[StepConfig]]`): List of steps to execute in the loop body

## Loop Types

### 1. For-Each Loop

Iterates over a collection of items.

```python
# Configuration
loop_config = LoopConfig(
    collection="files",
    item_name="current_file",
    index_name="file_index",
    result_name="processed_files",
    fail_fast=False
)
```

```yaml
# YAML syntax
loop_config:
  collection: files
  item_name: current_file
  index_name: file_index
  result_name: processed_files
  fail_fast: false
  body:
    - name: process_file
      plugin: file_processor
      config:
        path: "${current_file}"
```

### 2. Count-Based Loop

Executes a fixed number of iterations.

```python
# Configuration
loop_config = LoopConfig(
    count=5,  # or "${retry_count}" for dynamic
    index_name="attempt",
    fail_fast=True
)
```

```yaml
# YAML syntax
loop_config:
  count: 5
  index_name: attempt
  body:
    - name: try_operation
      plugin: operation_handler
      config:
        attempt_number: "${attempt}"
```

### 3. While Loop

Continues while a condition is true.

```python
# Configuration
loop_config = LoopConfig(
    condition="status != 'completed' and not timeout_reached",
    max_iterations=60,
    fail_fast=True
)
```

```yaml
# YAML syntax
loop_config:
  condition: "status != 'completed' and not timeout_reached"
  max_iterations: 60
  body:
    - name: check_status
      plugin: status_checker
    - name: wait
      plugin: delay
      config:
        seconds: 10
```

## Attributes

### collection
- **Type**: `Optional[str]`
- **Description**: Name of the context variable containing the collection to iterate
- **Used for**: For-each loops
- **Example**: `"items"`, `"data_files"`, `"user_list"`

### item_name
- **Type**: `str`
- **Default**: `"item"`
- **Description**: Variable name for the current item in the loop
- **Available in**: Loop body context
- **Example**: `"current_user"`, `"file"`, `"record"`

### index_name
- **Type**: `str`
- **Default**: `"index"`
- **Description**: Variable name for the current iteration index (0-based)
- **Available in**: Loop body context
- **Example**: `"i"`, `"iteration"`, `"attempt_num"`

### count
- **Type**: `Optional[Union[int, str]]`
- **Description**: Number of iterations for count-based loops
- **Used for**: Count loops
- **Examples**: `3`, `10`, `"${max_retries}"`

### condition
- **Type**: `Optional[str]`
- **Description**: Expression evaluated before each iteration
- **Used for**: While loops
- **Evaluation**: Uses `ConditionParser`
- **Example**: `"not done and attempts < max_attempts"`

### max_iterations
- **Type**: `int`
- **Default**: `100`
- **Description**: Safety limit to prevent infinite loops
- **Applies to**: All loop types, especially while loops
- **Best practice**: Always set appropriately for your use case

### fail_fast
- **Type**: `bool`
- **Default**: `True`
- **Description**: Whether to stop the loop on first error
- **True**: Stop immediately on error
- **False**: Continue processing remaining items

### result_name
- **Type**: `Optional[str]`
- **Description**: Variable name to store collected results
- **Purpose**: Aggregate results from all iterations
- **Example**: `"processed_items"`, `"validation_results"`

### body
- **Type**: `Optional[List[StepConfig]]`
- **Description**: Steps to execute in each iteration
- **Context**: Has access to loop variables and parent context

## Usage Examples

### Example 1: File Processing Loop

```python
from src.core.step_config import LoopConfig, StepConfig

# Process each file in a directory
loop_config = LoopConfig(
    collection="input_files",
    item_name="file",
    index_name="file_num",
    result_name="processed_files",
    fail_fast=False,  # Continue even if some files fail
    body=[
        StepConfig(
            name="validate_file",
            plugin="file_validator",
            config={"path": "${file}"}
        ),
        StepConfig(
            name="process_file",
            plugin="file_processor",
            depends_on=[("validate_file", "is_valid == true")],
            config={
                "input": "${file}",
                "output": "processed_${file_num}.txt"
            }
        )
    ]
)
```

### Example 2: Retry Loop with Backoff

```python
# Retry API call with exponential backoff
loop_config = LoopConfig(
    count=3,
    index_name="retry",
    body=[
        StepConfig(
            name="calculate_delay",
            plugin="math_calc",
            config={"seconds": "2 ** ${retry}"}  # 1, 2, 4 seconds
        ),
        StepConfig(
            name="wait",
            plugin="delay",
            depends_on=[("calculate_delay", "retry > 0")],
            config={"duration": "${seconds}"}
        ),
        StepConfig(
            name="api_call",
            plugin="http_client",
            fail_on_error=False,
            config={"endpoint": "${api_url}"}
        ),
        StepConfig(
            name="check_success",
            plugin="response_checker",
            depends_on=["api_call"]
        ),
        StepConfig(
            name="break_on_success",
            plugin="loop_control",
            depends_on=[("check_success", "status_code == 200")],
            config={"action": "break"}
        )
    ]
)
```

### Example 3: Polling Loop

```python
# Poll job status until complete
loop_config = LoopConfig(
    condition="job_status not in ['completed', 'failed', 'cancelled']",
    max_iterations=120,  # Max 2 hours with 60s delay
    body=[
        StepConfig(
            name="get_job_status",
            plugin="job_api",
            config={"job_id": "${job_id}"}
        ),
        StepConfig(
            name="log_progress",
            plugin="logger",
            config={
                "message": "Job ${job_id} status: ${job_status}",
                "progress": "${job_progress}"
            }
        ),
        StepConfig(
            name="check_timeout",
            plugin="timeout_checker",
            config={"start_time": "${job_start_time}"}
        ),
        StepConfig(
            name="wait",
            plugin="delay",
            depends_on=[("check_timeout", "not timed_out")],
            config={"seconds": 60}
        )
    ]
)
```

## Loop Context Variables

During loop execution, additional variables are available:

### For All Loop Types
- `${index_name}`: Current iteration index (0-based)
- Parent context variables remain accessible

### For For-Each Loops
- `${item_name}`: Current item from collection
- `${collection}_length`: Total number of items

### For Count Loops
- `${count}`: Total number of iterations

### For While Loops
- Previous iteration results remain in context

## Advanced Features

### Nested Loops

Loops can be nested within other loops:

```yaml
# Outer loop over categories
loop_config:
  collection: categories
  item_name: category
  body:
    - name: process_category
      plugin: category_handler
      
    # Inner loop over items in category
    - name: process_items
      plugin: pipeline_loop
      loop_config:
        collection: "${category.items}"
        item_name: item
        body:
          - name: process_item
            plugin: item_processor
```

### Dynamic Collections

Collections can be generated dynamically:

```python
# First step generates the collection
StepConfig(
    name="list_files",
    plugin="file_lister",
    config={"pattern": "*.csv"}
    # Sets 'csv_files' in context
)

# Loop over the generated collection
StepConfig(
    name="process_files",
    plugin="pipeline_loop",
    loop_config=LoopConfig(
        collection="csv_files",
        item_name="csv_file"
    )
)
```

### Result Collection

When `result_name` is specified, results are collected:

```python
loop_config = LoopConfig(
    collection="items",
    result_name="results",
    body=[
        StepConfig(
            name="process",
            plugin="processor"
            # Returns {"status": "success", "data": {...}}
        )
    ]
)

# After loop, context['results'] contains:
# [
#   {"status": "success", "data": {...}},  # From iteration 0
#   {"status": "success", "data": {...}},  # From iteration 1
#   ...
# ]
```

## Integration with PipelineBuilder

### For-Each Loop

```python
builder.loop_for_each(
    "files",
    lambda b: b
        .step("validate", config={"file": "${current_file}"})
        .step("process", depends_on=[("validate", "valid == true")]),
    item_name="current_file",
    result_name="processed"
)
```

### Count Loop

```python
builder.loop_count(
    5,
    lambda b: b
        .step("attempt", config={"try": "${i}"})
        .step("check_success"),
    index_name="i"
)
```

### While Loop

```python
builder.loop_while(
    "not finished",
    lambda b: b
        .step("work")
        .step("check_completion"),
    max_iterations=50
)
```

## Best Practices

### 1. Always Set max_iterations
```python
# Good - prevents infinite loops
LoopConfig(
    condition="not done",
    max_iterations=1000  # Reasonable limit
)

# Bad - could run forever
LoopConfig(
    condition="not done"
    # Uses default 100, might not be enough
)
```

### 2. Use Meaningful Variable Names
```python
# Good - clear what's being processed
LoopConfig(
    collection="customers",
    item_name="customer",
    index_name="customer_index"
)

# Less clear
LoopConfig(
    collection="data"
    # Uses defaults: item, index
)
```

### 3. Consider fail_fast Setting
```python
# For critical operations - stop on first error
LoopConfig(
    collection="critical_tasks",
    fail_fast=True  # Default
)

# For batch processing - continue on errors
LoopConfig(
    collection="files_to_process",
    fail_fast=False,
    result_name="process_results"  # Collect all results
)
```

### 4. Validate Loop Conditions
```python
# Ensure condition will eventually be false
LoopConfig(
    condition="retry_count < max_retries",
    max_iterations=10,
    body=[
        # Must update retry_count!
        StepConfig(name="increment_retry", ...)
    ]
)
```

## Common Patterns

### Retry with Limit
```yaml
loop_config:
  count: 3
  index_name: attempt
  body:
    - name: try_operation
      fail_on_error: false
    - name: break_if_success
      depends_on:
        - step: try_operation
          when: "success == true"
```

### Process Until Success
```yaml
loop_config:
  condition: "not success"
  max_iterations: 10
  body:
    - name: attempt
    - name: check_result
```

### Batch Processing
```yaml
loop_config:
  collection: batches
  item_name: batch
  fail_fast: false
  result_name: batch_results
  body:
    - name: process_batch
```

## Error Handling

### Invalid Configuration
```python
# Error: No loop type specified
LoopConfig()  # Must have collection, count, or condition

# Error: Multiple loop types
LoopConfig(
    collection="items",
    count=5  # Can't have both
)
```

### Runtime Errors
- Collection not found in context
- Maximum iterations exceeded
- Invalid condition expression
- Step failures (respects fail_fast)

## Performance Considerations

1. **Large Collections**: Consider chunking
2. **Complex Conditions**: Keep simple for performance
3. **Memory Usage**: Results collection can grow large
4. **Parallel Execution**: Loops execute sequentially

## See Also

- [PipelineBuilder API](pipeline-builder.md)
- [StepConfig API](step-config.md)
- [ConditionParser API](condition-parser.md)
- [Loop Examples](../../examples/control-flow/loops/)