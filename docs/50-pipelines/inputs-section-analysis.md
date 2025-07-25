# How inputs section in pipeline YAML gets passed to plugins

## Overview
The `inputs` section in pipeline YAML files is currently **NOT** being parsed or used by the pipeline execution system. This appears to be a bug or missing feature.

## Current Flow

### 1. Pipeline YAML Loading (`src/core/dependency_container.py`)
- The `_parse_step_configs` method parses step configurations from YAML
- It only extracts these fields: `name`, `plugin`, `depends_on`, `fail_on_error`, `loop_config`, `config`, and `connections`
- The `inputs` field is NOT included in the `_RawStepConfigFull` TypedDict definition
- Therefore, any `inputs` section in the YAML is ignored during parsing

### 2. Parameter Substitution (`src/cli/pipeline.py`)
Pipeline parameters are added directly to the ExecutionContext in `_execute_async`:
```python
# Add parameters to context
for key, value in params.items():
    context[key] = value
```
These parameters become available in the context for plugins to access.

### 3. Plugin Input Resolution (`src/core/plugin_input_resolver.py`)
The `PluginInputResolver.resolve_inputs` method looks for plugin inputs in several places:
- Step-specific data in context (if `step.name` exists as a key)
- Direct field matches in context
- Context extras (for ExecutionContext)
- Resolved connection inputs from DAG executor

### 4. Connection Resolution (`src/core/dag_executor.py`)
- The DAG executor resolves connections defined in the `connections` section
- These resolved values are stored in the context and made available to plugins

## The Problem

The `inputs` section in pipeline YAML files like `test-parameter-substitution.yaml`:
```yaml
steps:
  - name: test_step
    plugin: shell_command
    config:
      command: |
        echo "Raw value: {{test_param}}"
    inputs:
      input_value: "{{test_param}}"  # This is ignored!
```

Is completely ignored because:
1. It's not defined in the TypedDict schema
2. It's not parsed by `_parse_step_configs`
3. It's not stored in the StepConfig dataclass

## How Parameter Substitution Works Instead

Parameters are available to plugins through:
1. **Direct context access** - parameters are added to context and can be accessed by field name
2. **Config section** - some plugins (like shell_command) implement their own parameter substitution for config values
3. **Connections** - the connections system can wire outputs from one step to inputs of another

## Current Workarounds

Since the `inputs` section is ignored, plugins access parameters through:

1. **Direct context lookup**: The PluginInputResolver checks if fields matching the plugin's InputModel exist in the context
2. **Connection resolution**: Using the `connections` section to explicitly wire values
3. **Plugin-specific config handling**: Some plugins parse their config and substitute parameters

## Recommendation

To properly support the `inputs` section:
1. Add `inputs: Dict[str, Any]` to the `_RawStepConfigFull` TypedDict
2. Parse it in `_parse_step_configs` and add to StepConfig
3. Process parameter substitution ({{param}}) for input values before plugin execution
4. Store resolved inputs in the context under the step name
5. The existing PluginInputResolver would then find these values when looking for step-specific data

Currently, the `inputs` section in pipeline YAML files serves no purpose and should be removed to avoid confusion, or the feature should be properly implemented.