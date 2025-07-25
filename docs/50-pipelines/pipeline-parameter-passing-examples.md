# Pipeline Parameter Passing in Praxis - Examples and Analysis

## Summary

This document provides examples of how pipeline parameters are passed to steps in Praxis, based on a thorough examination of the codebase.

## Key Findings

### 1. Pipeline Parameter Definition

Pipelines define parameters in YAML files using a `parameters` or `params` section:

```yaml
# From test-parameter-substitution.yaml
parameters:
  - name: test_param
    type: string
    description: Test parameter
    default: "default value"

# From github-issue-task-generator.yaml
parameters:
  - name: initial_context
    type: string
    description: Initial context or problem description to start the interview
    default: "I need help creating a new feature"
```

### 2. Template Syntax Usage in Pipelines

Pipeline YAML files use two different syntaxes for referencing parameters:

#### a) Double Curly Braces `{{parameter_name}}`
```yaml
# From test-parameter-substitution.yaml
steps:
  - name: test_step
    plugin: shell_command
    config:
      command: |
        echo "Raw value: {{test_param}}"
    inputs:
      input_value: "{{test_param}}"

# From github-issue-task-generator.yaml
inputs:
  topic: "{{initial_context}}"
```

#### b) Shell Variable Syntax `${parameter_name}`
```yaml
# From github-issue-task-generator.yaml
config:
  command: |
    echo "initial_context from params: ${initial_context}"
    echo "Task ID: ${task_id}"

# From web_scrape.yaml (for step outputs)
connections:
  inputs:
    text: "${scrape.text}"
```

### 3. How Parameters Actually Work

Based on code analysis, here's the actual flow:

1. **Pipeline Loading**: 
   - YAML files are loaded directly using `yaml.safe_load()` 
   - NO template processing happens - `{{}}` syntax is preserved as literal strings
   - Despite Jinja2 being a dependency, it's not used for pipeline parameter substitution

2. **Parameter Storage in Context**:
   ```python
   # From cli/pipeline.py
   # Add parameters to context
   for key, value in params.items():
       context[key] = value
   ```

3. **Environment Variable Exposure**:
   The shell_command plugin exposes context values as environment variables:
   ```python
   # From shell_command/plugin.py
   def _prepare_environment(self, context: PipelineContext, config: ShellCommandConfig) -> Dict[str, str]:
       # Add task_id as it's commonly needed
       task_id = context.get("task_id")
       if task_id:
           env["task_id"] = str(task_id)
   ```

4. **Shell Variable Substitution**:
   - When `shell_mode=true` (default), commands are executed through a shell
   - The shell (bash/sh) performs variable substitution for `${variable_name}` syntax
   - The `{{}}` syntax appears to be passed literally and may not work as expected

### 4. Working Examples from Actual Pipelines

#### Example 1: Using Shell Variables (WORKS)
```yaml
# github-issue-task-generator.yaml
steps:
  - name: debug_inputs  
    plugin: shell_command
    config:
      command: |
        echo "initial_context from params: ${initial_context}"
        echo "Task ID: ${task_id}"
```

#### Example 2: Connection References (WORKS)
```yaml
# web_scrape.yaml
steps:
  - name: summarize
    plugin: content_summarize
    connections:
      inputs:
        text: "${scrape.text}"  # References output from 'scrape' step
```

#### Example 3: Mixed Syntax (PARTIALLY WORKS)
```yaml
# test-parameter-substitution.yaml
config:
  command: |
    echo "Direct env var: ${test_param}"      # This works
    echo "Raw value: {{test_param}}"          # This prints literally
```

### 5. Input Values with `{{}}` Syntax

When `{{}}` is used in the `inputs` section:
```yaml
inputs:
  topic: "{{initial_context}}"
```

This syntax is NOT processed by Praxis. The literal string `"{{initial_context}}"` would be passed as the value.

## Conclusions

1. **`{{}}` syntax is NOT processed** - There's no template engine handling this syntax
2. **Use `${param}` for shell commands** - This is the correct syntax for shell variable substitution
3. **Connection syntax `${step.field}` works** - This is processed by the ConnectionResolver
4. **Parameters are exposed as environment variables** - Available to shell commands via `${param_name}`

## Recommendations for Pipeline Authors

1. **For Shell Commands**: Always use `${parameter_name}` syntax
2. **For Connections**: Use `${step_name.field_name}` syntax  
3. **Avoid `{{}}` syntax**: It's not processed and will be passed literally
4. **Test Your Pipelines**: Verify parameter substitution works as expected

## Example: Correct Parameter Usage

```yaml
id: my-pipeline
name: Example Pipeline with Parameters
description: Demonstrates correct parameter usage

parameters:
  - name: input_file
    type: string
    required: true
    description: Path to input file

steps:
  - name: process_file
    plugin: shell_command
    config:
      command: |
        # Correct - uses shell variable syntax
        echo "Processing file: ${input_file}"
        cat "${input_file}" | wc -l
    
  - name: save_result
    plugin: shell_command
    depends_on: [process_file]
    connections:
      inputs:
        # Correct - references previous step output
        line_count: "${process_file.stdout}"
    config:
      command: |
        echo "File has ${line_count} lines"
```

This investigation reveals that despite the presence of `{{}}` syntax in some pipeline files, Praxis does not actually process this as template syntax. Pipeline authors should use shell variable syntax `${param}` for reliable parameter substitution.