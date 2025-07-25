# Enhanced Control Flow Quick Reference

## Inline Conditions

### Basic Syntax
```yaml
depends_on:
  - step: previous_step
    when: "condition_expression"
```

### Operators
| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `status == 'active'` |
| `!=` | Not equal | `count != 0` |
| `<`, `>` | Less/Greater than | `score > 0.8` |
| `<=`, `>=` | Less/Greater or equal | `age >= 18` |
| `in` | Membership | `region in ['US', 'EU']` |
| `not in` | Not in | `status not in ['failed', 'error']` |
| `is` | Identity | `value is None` |
| `is not` | Not identity | `result is not None` |
| `and` | Logical AND | `x > 0 and y > 0` |
| `or` | Logical OR | `status == 'done' or timeout` |
| `not` | Logical NOT | `not is_disabled` |

### Accessing Nested Data
```yaml
when: "user.profile.age > 18"
when: "order.items[0].price > 100"
when: "response.data.status == 'success'"
```

## Loops

### For-Each Loop
```yaml
loop_config:
  collection: items          # Variable containing list
  item_name: current        # Current item variable (default: item)
  index_name: idx           # Current index variable (default: index)
  result_name: results      # Store results (optional)
  body:
    - name: process_item
      plugin: processor
```

### Count Loop
```yaml
loop_config:
  count: 5                  # Number of iterations
  index_name: i             # Index variable
  body:
    - name: iteration
      plugin: worker
```

### While Loop
```yaml
loop_config:
  condition: "not_done"     # Continue while true
  max_iterations: 100       # Safety limit
  body:
    - name: check_status
      plugin: checker
```

## PipelineBuilder API

### Basic Pipeline
```python
from src.core.pipeline_builder import PipelineBuilder

pipeline = (
    PipelineBuilder("pipeline-id")
    .with_name("Pipeline Name")
    .with_description("Description")
    .with_param("param1", "string", required=True)
    .step("plugin_name", config={"key": "value"})
    .build()
)
```

### Branching
```python
.branch(
    ("condition1", lambda b: b.step("branch1")),
    ("condition2", lambda b: b.step("branch2"))
)
```

### Loops
```python
# For-each
.loop_for_each("collection", lambda b: b
    .step("process"),
    item_name="item"
)

# Count
.loop_count(5, lambda b: b
    .step("iterate"),
    index_name="i"
)

# While
.loop_while("condition", lambda b: b
    .step("check")
    .step("process"),
    max_iterations=50
)
```

### Parallel Execution
```python
.parallel(
    lambda b: b.step("task1"),
    lambda b: b.step("task2"),
    lambda b: b.step("task3")
)
```

### Export to YAML
```python
# To string
yaml_str = builder.to_yaml()

# To file
builder.to_yaml(Path("pipeline.yaml"))
```

## Common Patterns

### Retry with Exponential Backoff
```yaml
- name: retry_operation
  plugin: pipeline_loop
  loop_config:
    count: 3
    index_name: attempt
    body:
      - name: wait
        plugin: delay
        config:
          seconds: "${2 ** attempt}"  # 1, 2, 4 seconds
      - name: try_operation
        plugin: api_call
        fail_on_error: false
```

### Conditional Processing
```yaml
- name: check
  plugin: validator

- name: process_valid
  depends_on:
    - step: check
      when: "is_valid"
      
- name: handle_error
  depends_on:
    - step: check
      when: "not is_valid"
```

### Batch Processing
```yaml
- name: process_batches
  plugin: pipeline_loop
  loop_config:
    collection: batches
    item_name: batch
    result_name: processed_batches
    body:
      - name: process
        plugin: batch_processor
        config:
          data: "${batch}"
```

## Tips

1. **Always quote strings in conditions**: `status == 'active'`
2. **Set max_iterations for while loops**: Prevent infinite loops
3. **Use meaningful variable names**: `current_user` vs `item`
4. **Test conditions independently**: Use context_debugger plugin
5. **Keep loop bodies simple**: Extract complex logic to separate pipelines