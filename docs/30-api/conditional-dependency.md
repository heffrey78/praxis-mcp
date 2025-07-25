# ConditionalDependency API Reference

The `ConditionalDependency` class represents a step dependency with an inline condition that must be satisfied for the dependent step to execute.

## Import

```python
from src.core.step_config import ConditionalDependency
```

## Class Definition

```python
@dataclass
class ConditionalDependency:
    """Represents a dependency with an inline condition."""
    step: str
    when: str
```

## Constructor

```python
ConditionalDependency(step: str, when: str)
```

Creates a conditional dependency that will only be satisfied when the specified condition evaluates to true.

### Parameters
- **step** (`str`): Name of the step to depend on
- **when** (`str`): Condition expression that must evaluate to true

### Examples

```python
# Simple condition
dep1 = ConditionalDependency(step="validator", when="is_valid == true")

# Complex condition
dep2 = ConditionalDependency(
    step="quality_check", 
    when="quality_score > 0.8 and not has_errors"
)

# Using context variables
dep3 = ConditionalDependency(
    step="user_check",
    when="user.subscription.active and user.credits > 0"
)
```

## Attributes

### step
- **Type**: `str`
- **Description**: The name of the step that must complete before this dependency is evaluated
- **Required**: Yes

### when
- **Type**: `str`
- **Description**: A condition expression that is evaluated using the pipeline context
- **Required**: Yes
- **Evaluation**: Uses `ConditionParser` for safe evaluation

## Usage in Pipeline Definition

### In YAML

```yaml
steps:
  - name: validate_data
    plugin: data_validator
    config:
      strict: true
      
  - name: process_valid_data
    plugin: data_processor
    depends_on:
      - step: validate_data
        when: "validation_passed == true"
        
  - name: handle_invalid_data
    plugin: error_handler
    depends_on:
      - step: validate_data
        when: "validation_passed == false"
```

### In PipelineBuilder

```python
from src.core.pipeline_builder import PipelineBuilder

builder = PipelineBuilder("conditional-pipeline")

# Using tuple syntax (converts to ConditionalDependency)
builder.step("process", depends_on=[
    ("validate", "is_valid == true")
])

# Or create explicitly
from src.core.step_config import ConditionalDependency

builder.step("process", depends_on=[
    ConditionalDependency(step="validate", when="is_valid == true")
])
```

### In StepConfig

```python
from src.core.step_config import StepConfig, ConditionalDependency

step = StepConfig(
    name="process_premium",
    plugin="premium_processor",
    depends_on=[
        ConditionalDependency(step="check_user", when="user_type == 'premium'"),
        ConditionalDependency(step="check_credits", when="credits >= 100")
    ]
)
```

## Condition Expression Syntax

### Supported Operators

The `when` expression supports all operators from `ConditionParser`:

- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Membership**: `in`, `not in`
- **Identity**: `is`, `is not`
- **Logical**: `and`, `or`, `not`

### Accessing Context Variables

```python
# Direct variable access
"status == 'active'"

# Nested attribute access
"user.profile.verified == true"

# Dictionary access
"config['timeout'] > 30"

# List access
"results[0] == 'success'"
```

### Common Patterns

#### Boolean Checks
```python
# Checking boolean values
ConditionalDependency("validate", "is_valid")
ConditionalDependency("validate", "is_valid == true")  # Explicit
ConditionalDependency("validate", "not has_errors")
```

#### Numeric Comparisons
```python
# Threshold checks
ConditionalDependency("score_check", "score >= 0.8")
ConditionalDependency("count_check", "item_count > 0 and item_count <= 1000")
```

#### String Matching
```python
# Status checks
ConditionalDependency("status_check", "status == 'approved'")
ConditionalDependency("type_check", "data_type in ['json', 'xml']")
```

#### Complex Conditions
```python
# Multiple criteria
ConditionalDependency(
    "validation", 
    "is_valid and score > 0.7 and (priority == 'high' or override == true)"
)
```

## Behavior and Execution

### Dependency Resolution

1. The dependent step waits for the specified step to complete
2. Once complete, the condition is evaluated using the current pipeline context
3. If the condition evaluates to `true`, the dependency is satisfied
4. If the condition evaluates to `false`, the dependent step is skipped

### Context for Evaluation

The condition has access to:
- All pipeline parameters
- Results from completed steps
- Variables set by previous steps
- Loop variables (if within a loop)

### Example Flow

```python
# Step 1: Validation sets context variables
validate_step = StepConfig(
    name="validate",
    plugin="validator"
    # Sets: is_valid, validation_score, error_count
)

# Step 2: Process only if valid
process_step = StepConfig(
    name="process",
    plugin="processor",
    depends_on=[
        ConditionalDependency("validate", "is_valid and error_count == 0")
    ]
)

# Step 3: Error handling for invalid data
error_step = StepConfig(
    name="handle_errors",
    plugin="error_handler",
    depends_on=[
        ConditionalDependency("validate", "not is_valid or error_count > 0")
    ]
)
```

## Advanced Usage

### Multiple Conditional Dependencies

A step can have multiple conditional dependencies that must ALL be satisfied:

```python
step = StepConfig(
    name="advanced_process",
    plugin="advanced_processor",
    depends_on=[
        ConditionalDependency("auth_check", "is_authenticated == true"),
        ConditionalDependency("quota_check", "usage < quota_limit"),
        ConditionalDependency("feature_check", "feature_enabled == true")
    ]
)
```

### Mixed Dependencies

Combine conditional and non-conditional dependencies:

```python
step = StepConfig(
    name="final_step",
    plugin="finalizer",
    depends_on=[
        "setup",  # Always required
        ConditionalDependency("optional_step", "include_optional == true"),
        "required_step"  # Always required
    ]
)
```

### In Loops

Conditional dependencies work within loops:

```yaml
loop_config:
  collection: items
  item_name: current_item
  body:
    - name: validate_item
      plugin: item_validator
      
    - name: process_item
      plugin: item_processor
      depends_on:
        - step: validate_item
          when: "is_valid == true"
          
    - name: skip_invalid
      plugin: skip_logger
      depends_on:
        - step: validate_item
          when: "is_valid == false"
```

## Error Handling

### Missing Context Variables

If a condition references a non-existent variable:

```python
# If 'missing_var' doesn't exist in context
ConditionalDependency("step1", "missing_var == true")
# Raises KeyError during evaluation
```

### Invalid Expressions

```python
# Syntax error
ConditionalDependency("step1", "value ==")  # Incomplete
# Raises ValueError during parsing

# Unsafe operation
ConditionalDependency("step1", "eval('code')")  # Function call
# Raises ValueError - not allowed
```

### Best Practices for Error Prevention

1. **Validate expressions during development**
   ```python
   parser = ConditionParser()
   parser.parse_expression("your_condition")  # Test parsing
   ```

2. **Use defensive conditions**
   ```python
   # Check existence first
   ConditionalDependency("step1", "'optional_var' in locals() and optional_var == true")
   ```

3. **Provide defaults in steps**
   ```python
   # Step sets default values
   step = StepConfig(
       name="set_defaults",
       plugin="default_setter",
       config={"is_valid": False, "score": 0.0}
   )
   ```

## Performance Considerations

1. **Condition Complexity**: Keep conditions simple for better performance
2. **Context Size**: Large contexts take longer to evaluate
3. **Caching**: Conditions are parsed once and cached by `ConditionParser`

## Comparison with Legacy Patterns

### Legacy .true/.false Pattern (Deprecated)
```yaml
# OLD - Do not use
- name: condition_check
  plugin: condition_plugin
- name: true_branch
  depends_on: [condition_check.true]
- name: false_branch
  depends_on: [condition_check.false]
```

### Modern Inline Conditions (Recommended)
```yaml
# NEW - Use this instead
- name: check_data
  plugin: data_checker
- name: process_valid
  depends_on:
    - step: check_data
      when: "is_valid == true"
- name: handle_invalid
  depends_on:
    - step: check_data
      when: "is_valid == false"
```

## Complete Example

```python
from src.core.pipeline_builder import PipelineBuilder
from src.core.step_config import ConditionalDependency

# Build a pipeline with conditional flow
pipeline = (
    PipelineBuilder("data-quality-pipeline")
    .with_param("quality_threshold", "float", default=0.8)
    .with_param("strict_mode", "bool", default=False)
    
    # Load and analyze data
    .step("load_data", config={"source": "${data_source}"})
    .step("analyze_quality", config={"detailed": True})
    
    # Conditional routing based on quality
    .step("high_quality_process", depends_on=[
        ConditionalDependency("analyze_quality", "quality_score >= quality_threshold")
    ])
    
    .step("low_quality_process", depends_on=[
        ConditionalDependency(
            "analyze_quality", 
            "quality_score < quality_threshold and not strict_mode"
        )
    ])
    
    .step("reject_low_quality", depends_on=[
        ConditionalDependency(
            "analyze_quality",
            "quality_score < quality_threshold and strict_mode"
        )
    ])
    
    # Convergence point
    .step("generate_report", depends_on=[
        "high_quality_process",
        "low_quality_process", 
        "reject_low_quality"
    ], fail_on_error=False)
    
    .build()
)
```

## See Also

- [ConditionParser API](condition-parser.md)
- [StepConfig API](step-config.md)
- [PipelineBuilder API](pipeline-builder.md)
- [Enhanced Control Flow Guide](../enhanced-control-flow-guide.md)