# PipelineBuilder API Reference

The `PipelineBuilder` class provides a fluent API for constructing pipelines programmatically with enhanced control flow features.

## Import

```python
from src.core.pipeline_builder import PipelineBuilder
```

## Class Definition

```python
class PipelineBuilder:
    """API for building pipelines programmatically with enhanced control flow."""
```

## Constructor

```python
def __init__(self, pipeline_id: Optional[str] = None) -> None
```

Creates a new pipeline builder instance.

### Parameters
- **pipeline_id** (`Optional[str]`): Unique identifier for the pipeline. If not provided, a UUID will be generated automatically.

### Example
```python
# With explicit ID
builder = PipelineBuilder("data-processing-pipeline")

# With auto-generated ID
builder = PipelineBuilder()
```

## Configuration Methods

### with_name

```python
def with_name(self, name: str) -> PipelineBuilder
```

Sets the human-readable name for the pipeline.

#### Parameters
- **name** (`str`): Display name for the pipeline

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example
```python
builder.with_name("Customer Data ETL Pipeline")
```

### with_description

```python
def with_description(self, description: str) -> PipelineBuilder
```

Sets the pipeline description.

#### Parameters
- **description** (`str`): Detailed description of the pipeline's purpose

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example
```python
builder.with_description("Extracts customer data from source systems, transforms and loads to warehouse")
```

### with_param

```python
def with_param(
    self,
    name: str,
    param_type: str = "string",
    required: bool = True,
    description: str = "",
    default: Any = None
) -> PipelineBuilder
```

Adds a parameter definition to the pipeline.

#### Parameters
- **name** (`str`): Parameter name
- **param_type** (`str`): Type of parameter. Valid values: `"string"`, `"int"`, `"float"`, `"bool"`, `"list"`, `"dict"`
- **required** (`bool`): Whether the parameter must be provided (default: `True`)
- **description** (`str`): Human-readable description of the parameter
- **default** (`Any`): Default value if parameter is not required

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example
```python
builder.with_param("source_database", "string", required=True, 
                  description="Connection string for source database")
builder.with_param("batch_size", "int", required=False, 
                  default=1000, description="Number of records per batch")
builder.with_param("dry_run", "bool", required=False, 
                  default=False, description="Run without making changes")
```

## Step Methods

### step

```python
def step(
    self,
    plugin: str,
    name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    fail_on_error: bool = True,
    depends_on: Optional[List[Union[str, Tuple[str, str]]]] = None
) -> PipelineBuilder
```

Adds a step to the pipeline.

#### Parameters
- **plugin** (`str`): Name of the plugin to execute
- **name** (`Optional[str]`): Name of the step. Auto-generated if not provided
- **config** (`Optional[Dict[str, Any]]`): Configuration dictionary for the plugin
- **fail_on_error** (`bool`): Whether pipeline should fail if this step fails (default: `True`)
- **depends_on** (`Optional[List[Union[str, Tuple[str, str]]]]`): List of dependencies. Can be simple step names or tuples of (step_name, condition)

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Examples

```python
# Simple step
builder.step("data_loader", config={"table": "customers"})

# Named step with configuration
builder.step("validator", name="validate_data", config={
    "schema": "customer_schema_v2",
    "strict": True
})

# Step with conditional dependency
builder.step("processor", depends_on=[
    ("validate_data", "validation_passed == true")
])

# Non-critical step
builder.step("optional_enrichment", fail_on_error=False)
```

## Control Flow Methods

### branch

```python
def branch(
    self,
    *branches: Tuple[str, Callable[[PipelineBuilder], PipelineBuilder]]
) -> PipelineBuilder
```

Creates conditional branches in the pipeline flow.

#### Parameters
- **\*branches** (`Tuple[str, Callable]`): Variable number of tuples, each containing:
  - A condition expression (str)
  - A function that builds the branch using a PipelineBuilder

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example

```python
builder.branch(
    ("quality_score >= 0.9", lambda b: b
        .step("premium_processor")
        .step("detailed_analytics")),
    
    ("quality_score >= 0.7", lambda b: b
        .step("standard_processor")
        .step("basic_analytics")),
    
    ("quality_score < 0.7", lambda b: b
        .step("data_cleaner")
        .step("revalidate"))
)
```

### parallel

```python
def parallel(
    self,
    *branches: Callable[[PipelineBuilder], PipelineBuilder]
) -> PipelineBuilder
```

Creates parallel execution branches that run concurrently.

#### Parameters
- **\*branches** (`Callable`): Variable number of functions that build parallel branches

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example

```python
builder.parallel(
    lambda b: b.step("analyze_text", config={"deep": True}),
    lambda b: b.step("analyze_images", config={"extract_metadata": True}),
    lambda b: b.step("analyze_structured", config={"validate": True})
)
builder.step("merge_analysis")  # Runs after all parallel branches complete
```

## Loop Methods

### loop_for_each

```python
def loop_for_each(
    self,
    collection: str,
    body: Callable[[PipelineBuilder], PipelineBuilder],
    item_name: str = "item",
    index_name: str = "index",
    result_name: Optional[str] = None,
    fail_fast: bool = True
) -> PipelineBuilder
```

Creates a for-each loop that iterates over a collection.

#### Parameters
- **collection** (`str`): Name of the context variable containing the collection
- **body** (`Callable`): Function that builds the loop body
- **item_name** (`str`): Variable name for the current item (default: `"item"`)
- **index_name** (`str`): Variable name for the current index (default: `"index"`)
- **result_name** (`Optional[str]`): Variable name to collect results from each iteration
- **fail_fast** (`bool`): Whether to stop on first error (default: `True`)

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example

```python
# Process each file in a directory
builder.loop_for_each(
    "input_files",
    lambda b: b
        .step("validate_file", config={"path": "${current_file}"})
        .step("process_file", depends_on=[
            ("validate_file", "is_valid == true")
        ])
        .step("save_result"),
    item_name="current_file",
    index_name="file_num",
    result_name="processed_files",
    fail_fast=False  # Continue even if some files fail
)
```

### loop_count

```python
def loop_count(
    self,
    count: Union[int, str],
    body: Callable[[PipelineBuilder], PipelineBuilder],
    index_name: str = "index"
) -> PipelineBuilder
```

Creates a count-based loop with a fixed number of iterations.

#### Parameters
- **count** (`Union[int, str]`): Number of iterations (int) or variable name containing count
- **body** (`Callable`): Function that builds the loop body
- **index_name** (`str`): Variable name for the current index (default: `"index"`)

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example

```python
# Retry with exponential backoff
builder.loop_count(
    3,  # or "${max_retries}"
    lambda b: b
        .step("calculate_delay", config={
            "seconds": "2 ** ${attempt}"
        })
        .step("wait", depends_on=[
            ("calculate_delay", "attempt > 0")
        ])
        .step("api_call", fail_on_error=False)
        .step("check_success")
        .step("break_if_success", depends_on=[
            ("check_success", "response_code == 200")
        ]),
    index_name="attempt"
)
```

### loop_while

```python
def loop_while(
    self,
    condition: str,
    body: Callable[[PipelineBuilder], PipelineBuilder],
    max_iterations: int = 100
) -> PipelineBuilder
```

Creates a while loop that continues as long as the condition is true.

#### Parameters
- **condition** (`str`): Condition expression to evaluate before each iteration
- **body** (`Callable`): Function that builds the loop body
- **max_iterations** (`int`): Maximum iterations to prevent infinite loops (default: `100`)

#### Returns
- `PipelineBuilder`: Self for method chaining

#### Example

```python
# Poll until job completes
builder.loop_while(
    "job_status not in ['completed', 'failed', 'cancelled']",
    lambda b: b
        .step("check_job_status", config={"job_id": "${job_id}"})
        .step("log_progress")
        .step("wait", config={"seconds": 30}),
    max_iterations=120  # Max 1 hour of polling
)
```

## Build Methods

### build

```python
def build() -> PipelineDefinition
```

Builds and returns the complete pipeline definition.

#### Returns
- `PipelineDefinition`: The constructed pipeline definition object

#### Raises
- `ValueError`: If the pipeline structure is invalid (e.g., circular dependencies, missing required fields)

#### Example

```python
pipeline = builder.build()
# Can now be executed or saved
```

### to_yaml

```python
def to_yaml(path: Optional[Union[str, Path]] = None) -> str
```

Exports the pipeline to YAML format.

#### Parameters
- **path** (`Optional[Union[str, Path]]`): File path to save the YAML. If not provided, returns YAML string

#### Returns
- `str`: YAML representation of the pipeline

#### Example

```python
# Get YAML string
yaml_content = builder.to_yaml()
print(yaml_content)

# Save to file
builder.to_yaml("pipelines/my_pipeline.yaml")

# Using Path object
from pathlib import Path
builder.to_yaml(Path("pipelines") / "my_pipeline.yaml")
```

## Complete Example

```python
from src.core.pipeline_builder import PipelineBuilder

# Build a complete data processing pipeline
pipeline = (
    PipelineBuilder("customer-etl")
    .with_name("Customer Data ETL Pipeline")
    .with_description("Extract, transform, and load customer data")
    .with_param("source_db", "string", required=True)
    .with_param("target_db", "string", required=True)
    .with_param("batch_size", "int", default=1000)
    
    # Extract phase
    .step("extract_data", config={
        "connection": "${source_db}",
        "query": "SELECT * FROM customers WHERE updated_at > '${last_sync}'"
    })
    
    # Validate extracted data
    .step("validate_data")
    
    # Branch based on validation
    .branch(
        ("validation_passed", lambda b: b
            # Transform in batches
            .loop_for_each(
                "data_batches",
                lambda b2: b2
                    .step("clean_data")
                    .step("enrich_data")
                    .step("transform_data"),
                result_name="transformed_batches"
            )
            # Load transformed data
            .step("load_data", config={
                "connection": "${target_db}",
                "table": "dim_customers"
            })
        ),
        ("not validation_passed", lambda b: b
            .step("log_validation_errors")
            .step("send_alert")
        )
    )
    
    # Always generate report
    .step("generate_report", fail_on_error=False)
    
    .build()
)

# Save pipeline
pipeline.to_yaml("customer_etl.yaml")
```

## Best Practices

1. **Use descriptive names** for steps and parameters
2. **Set appropriate defaults** for optional parameters
3. **Use fail_on_error=False** for non-critical steps
4. **Always set max_iterations** for while loops
5. **Collect loop results** when you need aggregated data
6. **Test each branch** of conditional logic
7. **Document complex conditions** with comments

## Common Patterns

### Retry Pattern
```python
.loop_count(3, lambda b: b
    .step("attempt")
    .step("check_success")
    .step("break_if_success", depends_on=[("check_success", "success")])
)
```

### Validation and Branching
```python
.step("validate")
.branch(
    ("is_valid", lambda b: b.step("process")),
    ("not is_valid", lambda b: b.step("handle_error"))
)
```

### Parallel Processing
```python
.step("split_data")
.parallel(
    lambda b: b.step("process_partition_1"),
    lambda b: b.step("process_partition_2"),
    lambda b: b.step("process_partition_3")
)
.step("merge_results")
```

## See Also

- [Pipeline Definition](pipeline-definition.md)
- [Condition Parser](condition-parser.md)
- [Loop Configuration](loop-config.md)
- [Examples](../../examples/control-flow/)