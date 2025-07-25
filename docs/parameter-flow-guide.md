# Parameter Flow Guide: CLI to Plugins

This guide explains how parameters flow from the CLI to plugins in Praxis pipelines.

## Overview

Parameters in Praxis follow this flow:
1. CLI parsing → 2. Pipeline Context → 3. PluginInputResolver → 4. Plugin execution

## CLI Parameter Syntax

### Basic Parameters
```bash
praxis pipeline run my_pipeline -p key=value -p another_key=another_value
```

### Multiple Parameters
```bash
praxis pipeline run my_pipeline \
  -p url=https://example.com \
  -p format=json \
  -p max_results=10
```

## Parameter Types and Handling

### String Parameters
```bash
-p message="Hello World"
-p dialogue="User: Hi\nAssistant: Hello!"
```

### File Parameters (Plugin Run Only)
When running plugins directly, you can use the `@` syntax:
```bash
praxis plugin run my_plugin -p content=@input.txt
```

**Note**: The `@` syntax is NOT currently supported in pipeline runs.

### JSON Parameters
JSON-like strings are automatically parsed:
```bash
-p config='{"key": "value", "nested": {"data": true}}'
```

## How Parameters Reach Plugins

### 1. Pipeline Context Storage
All CLI parameters are stored in the pipeline context:
```python
# In pipeline.py
for key, value in params.items():
    context[key] = value
```

### 2. Plugin Input Resolution
The `PluginInputResolver` checks multiple sources:
- Direct context fields matching plugin InputModel fields
- Step-specific data in `context[step_name]`
- Context extras for connection inputs
- Aliased fields

### 3. Plugin Access
Plugins access parameters through their InputModel:
```python
class MyPlugin(PluginBase):
    class InputModel(BaseModel):
        dialogue: Optional[str] = None
        prompt: Optional[str] = None
        config: Optional[Dict[str, Any]] = None
    
    async def run(self, context: PipelineContext) -> OutputModel:
        # PluginInputResolver automatically populates from context
        # Access via self.input_data (populated by base class)
        dialogue = self.input_data.dialogue if self.input_data else None
```

## Special Parameter Handling

### Provider and Model Parameters
These are extracted and used for AI provider configuration:
```bash
-p provider=openai -p model=gpt-4
```

### System Parameters
- `task_id`: Automatically added to context
- Parameters starting with `_` are typically internal

## Best Practices

1. **Use descriptive parameter names**: `dialogue` instead of `d`
2. **Document required parameters**: In pipeline YAML definitions
3. **Provide defaults where sensible**: In plugin InputModel
4. **Validate early**: Use Pydantic validation in InputModel

## Examples

### Passing Dialogue to Agent Pipeline
```bash
# Direct dialogue
praxis pipeline run agent_pipeline \
  -p dialogue="User: What's the weather?\nAssistant: I'll help you check the weather."

# With additional context
praxis pipeline run agent_pipeline \
  -p dialogue="Previous conversation..." \
  -p system_prompt="You are a helpful assistant" \
  -p max_turns=10
```

### Complex Configuration
```bash
praxis pipeline run data_processor \
  -p input_file=data.csv \
  -p config='{"format": "csv", "delimiter": ",", "headers": true}' \
  -p output_format=json
```

## Limitations

1. **No @ file syntax in pipeline runs**: Must read file content before passing
2. **Parameter names must match**: No automatic aliasing at CLI level
3. **All parameters are strings initially**: Type conversion happens in plugins

## Future Enhancements

Potential improvements:
- Add @ file syntax support to pipeline runs
- Support for parameter files (e.g., `--params-file config.yaml`)
- Type hints in pipeline parameter definitions
- Interactive parameter collection for pipelines