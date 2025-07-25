# Enhanced Control Flow Guide

## Overview

Praxis now supports enhanced control flow features that make pipelines more powerful and expressive. This guide covers:

- **Inline Conditional Dependencies** - Execute steps based on runtime conditions
- **Native Loop Support** - Iterate over collections or repeat operations
- **PipelineBuilder API** - Programmatically construct pipelines with a fluent interface

## Table of Contents

1. [Inline Conditional Dependencies](#inline-conditional-dependencies)
2. [Loop Configurations](#loop-configurations)
3. [PipelineBuilder API](#pipelinebuilder-api)
4. [Best Practices](#best-practices)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

## Inline Conditional Dependencies

### Basic Syntax

Instead of using separate condition plugins, you can now specify conditions directly in step dependencies:

```yaml
steps:
  - name: check_data
    plugin: data_validator
    
  - name: process_valid_data
    plugin: data_processor
    depends_on:
      - step: check_data
        when: "is_valid == true"
        
  - name: handle_invalid_data
    plugin: error_handler
    depends_on:
      - step: check_data
        when: "is_valid == false"
```

### Supported Operators

The condition parser supports the following operators:

- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Membership**: `in`, `not in`
- **Identity**: `is`, `is not`
- **Logical**: `and`, `or`, `not`

### Complex Conditions

You can create complex conditions using logical operators:

```yaml
- name: premium_processing
  plugin: premium_handler
  depends_on:
    - step: validate_user
      when: "user.type == 'premium' and user.credits > 100"
```

### Accessing Nested Data

Use dot notation to access nested fields in the context:

```yaml
- name: process_order
  plugin: order_processor
  depends_on:
    - step: check_order
      when: "order.status == 'approved' and order.items.length > 0"
```

## Loop Configurations

### For-Each Loops

Iterate over a collection of items:

```yaml
steps:
  - name: load_items
    plugin: item_loader
    
  - name: process_items
    plugin: pipeline_loop
    depends_on: [load_items]
    loop_config:
      collection: items
      item_name: current_item
      index_name: item_index
      body:
        - name: validate_item
          plugin: item_validator
          config:
            item: "${current_item}"
            
        - name: transform_item
          plugin: item_transformer
          depends_on: [validate_item]
```

### Count-Based Loops

Execute a fixed number of iterations:

```yaml
- name: retry_operation
  plugin: pipeline_loop
  loop_config:
    count: 3
    index_name: attempt
    body:
      - name: try_operation
        plugin: api_caller
        config:
          attempt_number: "${attempt}"
```

### Conditional Loops

Loop while a condition is true:

```yaml
- name: poll_status
  plugin: pipeline_loop
  loop_config:
    condition: "status != 'completed'"
    max_iterations: 10
    body:
      - name: check_status
        plugin: status_checker
        
      - name: wait
        plugin: delay
        config:
          seconds: 5
```

### Loop Control Options

- `collection`: Name of the collection variable to iterate over
- `item_name`: Variable name for the current item (default: "item")
- `index_name`: Variable name for the current index (default: "index")
- `count`: Fixed number of iterations
- `condition`: Expression to evaluate for continuation
- `max_iterations`: Safety limit for conditional loops (default: 100)
- `fail_fast`: Stop on first error (default: false)
- `result_name`: Store results in parent context

## PipelineBuilder API

### Basic Usage

Create pipelines programmatically using the PipelineBuilder:

```python
from src.core.pipeline_builder import PipelineBuilder

pipeline = (
    PipelineBuilder("my-pipeline")
    .with_name("My Data Pipeline")
    .with_description("Processes data with validation")
    .with_param("input_file", "string", required=True)
    .with_param("threshold", "float", default=0.8)
    .step("load_data", config={"file": "${input_file}"})
    .step("validate_data")
    .step("process_data")
    .build()
)
```

### Conditional Branching

Add conditional execution paths:

```python
pipeline = (
    PipelineBuilder()
    .step("analyze_data")
    .branch(
        ("score > threshold", lambda b: b
            .step("high_quality_process")
            .step("premium_output")),
        ("score <= threshold", lambda b: b
            .step("standard_process")
            .step("basic_output"))
    )
    .step("final_report")
    .build()
)
```

### Loops in PipelineBuilder

Add different types of loops:

```python
# For-each loop
pipeline = (
    PipelineBuilder()
    .step("get_files")
    .loop_for_each(
        "files",
        lambda b: b
            .step("read_file", config={"path": "${current_file}"})
            .step("process_file")
            .step("save_result"),
        item_name="current_file"
    )
    .build()
)

# Count-based loop
pipeline = (
    PipelineBuilder()
    .loop_count(
        5,
        lambda b: b.step("iteration_task", config={"index": "${i}"}),
        index_name="i"
    )
    .build()
)

# Conditional loop
pipeline = (
    PipelineBuilder()
    .step("init_process")
    .loop_while(
        "not_done",
        lambda b: b
            .step("check_status")
            .step("process_batch")
            .step("update_progress"),
        max_iterations=50
    )
    .build()
)
```

### Parallel Execution

Run steps in parallel:

```python
pipeline = (
    PipelineBuilder()
    .step("prepare_data")
    .parallel(
        lambda b: b.step("analyze_text"),
        lambda b: b.step("analyze_images"),
        lambda b: b.step("analyze_metadata")
    )
    .step("combine_results")
    .build()
)
```

### Exporting to YAML

Convert your programmatic pipeline to YAML:

```python
# Export to string
yaml_content = builder.to_yaml()

# Export to file
from pathlib import Path
builder.to_yaml(Path("pipelines/my_pipeline.yaml"))
```

## Best Practices

### 1. Use Meaningful Condition Expressions

```yaml
# Good
when: "validation.passed and data.quality_score > 0.8"

# Less clear
when: "x and y > 0.8"
```

### 2. Limit Loop Iterations

Always set `max_iterations` for conditional loops to prevent infinite loops:

```yaml
loop_config:
  condition: "status == 'pending'"
  max_iterations: 100  # Safety limit
```

### 3. Handle Loop Results

Use `result_name` to collect results from loop iterations:

```yaml
loop_config:
  collection: items
  result_name: processed_items
  body:
    - name: process_item
      plugin: item_processor
```

### 4. Structure Complex Conditions

For readability, break complex conditions across lines:

```yaml
depends_on:
  - step: validate
    when: |
      user.subscription == 'premium' and 
      user.credits > 0 and
      (user.region == 'US' or user.region == 'EU')
```

### 5. Use PipelineBuilder for Dynamic Pipelines

When pipeline structure depends on configuration or runtime data, use PipelineBuilder:

```python
def create_pipeline(config):
    builder = PipelineBuilder(f"pipeline-{config['mode']}")
    
    if config['mode'] == 'batch':
        builder.step("batch_loader")
    else:
        builder.step("stream_loader")
    
    return builder.build()
```

## Common Patterns

### Retry Pattern

```yaml
- name: retry_api_call
  plugin: pipeline_loop
  loop_config:
    count: 3
    index_name: attempt
    fail_fast: false
    body:
      - name: api_call
        plugin: http_request
        fail_on_error: false
        
      - name: check_success
        plugin: response_validator
        depends_on:
          - step: api_call
            when: "status_code == 200"
```

### Data Validation Branch

```yaml
- name: validate_data
  plugin: data_validator

- name: process_valid
  plugin: data_processor
  depends_on:
    - step: validate_data
      when: "validation_passed == true"
      
- name: quarantine_invalid
  plugin: quarantine_handler
  depends_on:
    - step: validate_data
      when: "validation_passed == false"
```

### Batch Processing

```yaml
- name: split_into_batches
  plugin: batch_splitter
  config:
    batch_size: 100

- name: process_batches
  plugin: pipeline_loop
  loop_config:
    collection: batches
    item_name: batch
    body:
      - name: process_batch
        plugin: batch_processor
        config:
          data: "${batch}"
```

## Troubleshooting

### Condition Not Evaluating Correctly

1. **Check variable names**: Ensure variables exist in context
2. **Verify types**: String comparisons need quotes: `status == 'active'`
3. **Debug context**: Add a debug step to inspect available variables

```yaml
- name: debug_context
  plugin: context_debugger
  config:
    show_keys: true
```

### Loop Not Iterating

1. **Check collection name**: Ensure the collection variable exists
2. **Verify loop type**: Use `collection` for for-each, `count` for fixed iterations
3. **Check max_iterations**: Default is 100, increase if needed

### PipelineBuilder Errors

1. **Import errors**: Ensure correct import path
2. **Method order**: Some methods must be called in sequence
3. **Lambda syntax**: Use proper lambda syntax for nested builders

```python
# Correct
.branch(
    ("condition", lambda b: b.step("step1"))
)

# Incorrect
.branch(
    ("condition", b.step("step1"))  # Missing lambda
)
```

### Performance Issues

1. **Limit parallel branches**: Too many parallel steps can overwhelm resources
2. **Optimize loop bodies**: Keep loop iterations lightweight
3. **Use fail_fast**: Stop processing on first error when appropriate

**pattern:**
```yaml
- name: check_data
  plugin: data_checker

- name: true_branch
  depends_on:
    - step: check_data
      when: "result == true"
      
- name: false_branch
  depends_on:
    - step: check_data
      when: "result == false"
```

## Summary

The enhanced control flow features in Praxis provide powerful ways to create dynamic, conditional, and iterative pipelines. By using inline conditions, native loops, and the PipelineBuilder API, you can create more maintainable and expressive pipeline definitions.

For more examples, see the [example pipelines](examples/) directory. For API details, consult the [API Reference](api-reference.md).