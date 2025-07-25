# Plugin Parameters vs Configuration Guide

This guide explains the distinction between **parameters** and **configuration** in Praxis plugins, and when to use each.

## Overview

Praxis plugins accept two types of inputs:
- **Parameters** (`-p/--param`): The actual data to be processed
- **Configuration** (`-c/--config`): Settings that control HOW the processing happens

This distinction ensures consistency across all plugins and makes the CLI interface predictable.

## Key Principles

### Parameters = Input Data
Parameters represent the **content** that the plugin will process:
- Text to analyze
- URLs to fetch
- Files to transform
- Topics to discuss
- Questions to answer

### Configuration = Processing Options
Configuration controls **how** the plugin operates:
- Which model/algorithm to use
- Output format preferences
- Processing modes (interactive vs batch)
- Resource limits (timeouts, retries)
- Feature flags (mock mode, debug mode)

## Examples Across Plugins

### Video Download Plugin
```bash
pdm run praxis plugin run video-download \
  -p 'video_url=https://youtube.com/watch?v=123' \  # WHAT to download
  -c '{"prefer_small": true, "mock_mode": true}'     # HOW to download
```
- **Parameter**: `video_url` - the video to download
- **Config**: `prefer_small`, `mock_mode` - download preferences

### Data Extraction Plugin
```bash
pdm run praxis plugin run data-extract \
  -p 'text="John Doe, age 30, lives in NYC"' \       # WHAT to extract from
  -c '{"extraction_schema": {"name": "string", "age": "integer", "city": "string"}}'
```
- **Parameter**: `text` - the content to extract from
- **Config**: `extraction_schema` - defines what structure to extract

### Agent Plugin
```bash
pdm run praxis plugin run agent \
  -p 'topic="Help me plan a vacation"' \             # WHAT to discuss
  -c '{"agent_name": "travel-assistant", "mode": "interactive", "max_turns": 10}'
```
- **Parameters**: `topic`, `context` - the subject matter
- **Config**: `agent_name`, `mode`, `max_turns` - which agent and how to interact

### Shell Command Plugin
```bash
pdm run praxis plugin run shell-command \
  -p 'input_data="file1.txt file2.txt"' \           # WHAT data to provide
  -c '{"command": "wc -l", "timeout": 30}'          # HOW to process it
```
- **Parameter**: `input_data` - data passed to the command
- **Config**: `command`, `timeout` - which command and execution limits

## Plugin Development Guidelines

When designing a plugin, ask yourself:

### Should it be a Parameter?
✅ It's the primary data being processed
✅ It varies with each execution
✅ It's what the user wants to transform/analyze
✅ It could come from a previous pipeline step

### Should it be Configuration?
✅ It controls the processing behavior
✅ It's usually the same across multiple runs
✅ It's about HOW, not WHAT
✅ It's a preference or setting

## Implementation in Plugin Code

### 1. Define Models

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Parameters go in InputModel
class MyPluginInput(BaseModel):
    """Input data for processing."""
    content: str = Field(..., description="The content to process")
    additional_data: Optional[str] = Field(None, description="Optional extra data")

# Configuration goes in ConfigModel
class MyPluginConfig(BaseModel):
    """Configuration for how to process."""
    processing_mode: Literal["fast", "accurate"] = Field("fast", description="Processing mode")
    output_format: Literal["json", "text"] = Field("json", description="Output format")
    max_retries: int = Field(3, description="Maximum retry attempts")

# Results go in OutputModel
class MyPluginOutput(BaseModel):
    """Processing results."""
    result: str = Field(..., description="Processed result")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
```

### 2. Use in Plugin Class

```python
class MyPlugin(PluginBase):
    InputModel = MyPluginInput
    OutputModel = MyPluginOutput
    ConfigModel = MyPluginConfig  # Optional, defaults to BaseModel
    
    async def run(self, context: PipelineContext) -> MyPluginOutput:
        # Get typed inputs and config
        inputs = self.get_inputs(context)  # Returns MyPluginInput
        config = self.get_config()          # Returns MyPluginConfig or dict
        
        # Process based on inputs and config
        if config.processing_mode == "fast":
            result = self.fast_process(inputs.content)
        else:
            result = self.accurate_process(inputs.content)
        
        return MyPluginOutput(result=result)
```

## CLI Usage Patterns

### Single Parameter
```bash
pdm run praxis plugin run my-plugin -p 'content="data to process"'
```

### Multiple Parameters
```bash
pdm run praxis plugin run my-plugin \
  -p 'content="main data"' \
  -p 'additional_data="extra info"'
```

### With Configuration
```bash
pdm run praxis plugin run my-plugin \
  -p 'content="data"' \
  -c '{"processing_mode": "accurate", "output_format": "json"}'
```

### From Files
```bash
# Parameters from file
pdm run praxis plugin run my-plugin -p 'content=@input.txt'

# Config from file
pdm run praxis plugin run my-plugin -p 'content="data"' -c '@config.json'
```

## Pipeline Usage

In pipelines, the distinction remains clear:

```yaml
steps:
  - name: process_data
    plugin: my-plugin
    # Inputs come from parameters or previous steps
    inputs:
      content: "{{ previous_step.output }}"
    # Config is defined statically
    config:
      processing_mode: accurate
      output_format: json
```

## Common Patterns

### 1. Provider Selection = Config
```python
class PluginConfig(BaseModel):
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "gpt-4"
```

### 2. Content/Data = Parameter
```python
class PluginInput(BaseModel):
    text: str = Field(..., description="Text to process")
    image_url: Optional[str] = Field(None, description="Image to analyze")
```

### 3. Processing Options = Config
```python
class PluginConfig(BaseModel):
    temperature: float = Field(0.7, description="Model temperature")
    max_tokens: int = Field(1000, description="Maximum output tokens")
    timeout: int = Field(30, description="Processing timeout")
```

### 4. Feature Flags = Config
```python
class PluginConfig(BaseModel):
    debug_mode: bool = Field(False, description="Enable debug output")
    mock_mode: bool = Field(False, description="Use mock responses")
    strict_mode: bool = Field(True, description="Fail on warnings")
```

## Best Practices

1. **Keep parameters minimal**: Only include what's essential for processing
2. **Provide sensible defaults**: All config should have reasonable defaults
3. **Document clearly**: Use Field descriptions to explain each parameter/config
4. **Validate appropriately**: Use Pydantic validators for both params and config
5. **Think about pipelines**: Parameters should flow naturally between steps

## Summary

The parameter/config distinction in Praxis ensures:
- **Consistency**: All plugins follow the same pattern
- **Clarity**: Users know where to put what
- **Composability**: Parameters flow between pipeline steps naturally
- **Flexibility**: Config can be reused across multiple executions

When in doubt:
- If it's the data being processed → **Parameter**
- If it's how to process the data → **Configuration**