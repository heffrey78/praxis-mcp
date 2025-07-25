# Pipeline Parameter Flow Analysis

## Overview

This document explains how parameters flow from the CLI through the pipeline execution stack to individual plugins in the Praxis backend system.

## Parameter Flow Architecture

```
CLI (--param key=value)
    ↓
InteractivePipelineExecutor.execute()
    ↓ (adds params to context extras)
ExecutionContext (with extras dict)
    ↓
DAGExecutor._run_with_retries()
    ↓ (creates child context with resolved inputs)
PluginInputResolver.resolve_inputs()
    ↓ (resolves from multiple sources)
Plugin.run(context)
```

## Detailed Flow Analysis

### 1. CLI Parameter Entry

Parameters are provided via the command line:
```bash
praxis pipeline run my-pipeline --param dialogue=@dialogue.txt --param prompt="Be helpful"
```

### 2. InteractivePipelineExecutor Processing

In `interactive_pipeline_executor.py` (lines 76-78):
```python
# Create context
context = create_execution_context(
    task_id=task_id,
    container=self.container,
)
# Add params to extras
for key, value in params.items():
    context[key] = value
```

This stores CLI parameters directly in the ExecutionContext, making them available throughout the pipeline.

### 3. ExecutionContext Structure

The `ExecutionContext` (execution_context.py) has:
- `extras: Dict[str, Any]` - Stores dynamic parameters
- Delegation to `PipelineContext` for standard operations
- Support for child context creation with overrides

### 4. DAGExecutor Parameter Handling

The DAGExecutor handles parameters in two ways:

#### For Connection-Based Inputs (lines 476-536):
```python
if self._use_connections and step.name in self._connection_map:
    # Resolve connections for this step
    resolved_inputs = {}
    # ... resolution logic ...
    
    # Create child context with resolved inputs
    if isinstance(context_for_plugin_run_final, ExecutionContext):
        context_for_plugin_run_final = context_for_plugin_run_final.spawn_child(
            extras={
                **context_for_plugin_run_final.extras,
                **resolved_inputs,
            }
        )
```

#### For Direct Parameters:
Parameters remain in the context extras and are accessible to the PluginInputResolver.

### 5. PluginInputResolver Resolution Order

The `PluginInputResolver` (plugin_input_resolver.py) resolves parameters in this order:

1. **Step-specific data** (lines 53-57):
   ```python
   if step_config.name in context:
       step_data = context[step_config.name]
       if isinstance(step_data, dict):
           resolved_kwargs = step_data
   ```

2. **Direct field matches** (lines 60-65):
   ```python
   if field_name in context and field_name not in resolved_kwargs:
       resolved_kwargs[field_name] = context[field_name]
   ```

3. **Context extras** (lines 69-75):
   ```python
   if hasattr(context, "extras"):
       extras = getattr(context, "extras", {})
       if isinstance(extras, dict):
           for key, value in extras.items():
               if key not in resolved_kwargs:
                   resolved_kwargs[key] = value
   ```

4. **Model field resolution** (lines 108-154):
   - Checks both field name and alias
   - First from resolved_kwargs, then from context

5. **Extra fields for models with extra="allow"** (lines 156-175):
   ```python
   if supports_extra:
       # Add any fields from resolved_kwargs that aren't already in gathered_inputs
       for key, value in resolved_kwargs.items():
           if key not in gathered_inputs_for_model:
               gathered_inputs_for_model[key] = value
   ```

## Agent Plugin Parameter Placement

For the Agent plugin specifically:

### AgentInput Model
Used for pipeline-provided inputs:
```python
class AgentInput(BaseModel):
    topic: Optional[str] = Field(None, description="Topic for agent conversation")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
```

### AgentConfig Model
Used for configuration parameters:
```python
class AgentConfig(BaseModel):
    # ... other fields ...
    
    # Dialogue automation parameters
    dialogue: Optional[List[str]] = Field(
        None, 
        description="Pre-scripted dialogue responses for automated testing."
    )
    prompt: Optional[str] = Field(
        None,
        description="System prompt for LLM-based dialogue generation."
    )
    dialogue_mode: Optional[Literal["direct", "llm"]] = Field(
        None,
        description="Response mode: 'direct' uses dialogue verbatim, "
        "'llm' generates contextual responses."
    )
```

### Where to Place Dialogue Parameters

**Dialogue parameters should be placed in AgentConfig** because:
1. They are configuration parameters, not runtime inputs
2. AgentConfig is where all agent behavior configuration resides
3. The parameters control how the agent responds during execution

## Extra="allow" Pattern

The `extra="allow"` pattern enables plugins to accept additional parameters not explicitly defined in their models:

### Implementation in PluginInputResolver

1. **Check if model supports extra** (lines 156-166):
   ```python
   model_config = getattr(actual_input_model_cls, "model_config", None)
   supports_extra = False
   if model_config:
       if hasattr(model_config, "extra"):
           # Pydantic v2
           supports_extra = model_config.extra == "allow"
       elif isinstance(model_config, dict):
           # ConfigDict
           supports_extra = model_config.get("extra") == "allow"
   ```

2. **Add extra fields** (lines 167-175):
   ```python
   if supports_extra:
       # Add any fields from resolved_kwargs that aren't already in gathered_inputs
       for key, value in resolved_kwargs.items():
           if key not in gathered_inputs_for_model:
               gathered_inputs_for_model[key] = value
   ```

### When to Use extra="allow"

Use this pattern when:
- The plugin needs to accept dynamic parameters
- Parameters vary based on pipeline configuration
- You want to pass through parameters to downstream components

## Best Practices

1. **Define known parameters explicitly** in your InputModel or ConfigModel
2. **Use ConfigModel for configuration** that controls plugin behavior
3. **Use InputModel for runtime data** from previous pipeline steps
4. **Enable extra="allow" carefully** - only when truly dynamic parameters are needed
5. **Document all parameters** clearly in field descriptions

## Example: Passing Dialogue Parameters

```bash
# CLI command
praxis pipeline run agent-pipeline \
    --param dialogue='["Hello", "How can I help?", "Goodbye"]' \
    --param prompt="Be a helpful assistant" \
    --param dialogue_mode=llm

# These parameters will:
# 1. Be stored in ExecutionContext.extras by InteractivePipelineExecutor
# 2. Be resolved by PluginInputResolver when creating AgentConfig
# 3. Be available in AgentPlugin as config.dialogue, config.prompt, etc.
```

## Dialogue Parameter Access During Suspension

When the agent plugin suspends for interactive mode, the dialogue parameters need to be accessible in the suspension handler. Here's how they can be accessed:

### Access Points

1. **ExecutionContext during suspension handling**:
   ```python
   async def _handle_unified_executor_suspension(
       self,
       suspend_info: Dict[str, Any],
       task_id: str,
       pipeline_id: str,
       step_name: str,
       context: ExecutionContext,  # <-- Contains original params in extras
   ) -> Optional[Dict[str, Any]]:
   ```

2. **Extracting dialogue parameters**:
   ```python
   # In the suspension handler
   dialogue_param = context.get("dialogue")  # or context.extras.get("dialogue")
   if dialogue_param:
       # Parse and use DialogueProvider
       from src.cli.dialogue_provider import DialogueProvider
       dialogue_responses = DialogueProvider.parse_dialogue_parameter(dialogue_param)
       dialogue_provider = DialogueProvider(dialogue_responses, console)
   ```

### Integration Point

The dialogue provider should be integrated in the `wait_for_user_input` method of `CLIPipelineEventHandler`:

```python
async def wait_for_user_input(self, event: AgentInteractionEvent) -> str:
    """Interactive input collection for agent conversations."""
    # Check if dialogue provider is available
    if self.dialogue_provider and self.dialogue_provider.has_responses():
        return self.dialogue_provider.get_next_response()
    
    # Otherwise use interactive input
    user_input = self._multiline_input.get_input()
    if user_input is None:
        return "/cancel"
    return user_input
```

## Summary

The parameter flow system in Praxis is designed to be flexible and extensible:
- Parameters flow from CLI → Context → Plugin via a well-defined path
- The PluginInputResolver provides multiple resolution strategies
- The extra="allow" pattern enables dynamic parameter handling
- Clear separation between InputModel (runtime data) and ConfigModel (configuration)
- Parameters remain accessible during suspension via ExecutionContext

This architecture ensures parameters can be passed through the pipeline while maintaining type safety and validation where needed.