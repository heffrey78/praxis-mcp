# Plugin Connection System

## Overview

The Plugin Connection System determines how data flows between steps in a pipeline. It handles the mapping of outputs from one plugin to inputs of another, ensuring type compatibility and clear data flow.

## Key Concepts

### Connection Types

- **Explicit Connections**: Directly specified in the pipeline definition
- **Implicit Connections**: Automatically determined based on compatibility

### Connection Resolution

The system resolves connections using this process:

1. **Plugin Analysis**: Extract input/output fields from Pydantic models
2. **Compatibility Check**: Determine which outputs can connect to which inputs
3. **Automatic Resolution**: Connect compatible fields when unambiguous
4. **Manual Resolution**: Require explicit connections for ambiguous cases

### Connection Syntax

Explicit connections use this syntax in pipeline definitions:

```yaml
connections:
  inputs:
    target_field: ${source_step.source_field}
```

## Field Compatibility Rules

Fields are considered compatible when:

1. They have the same or compatible types
2. They share the same semantic type in Pydantic schema metadata
3. They are explicitly listed as compatible in the `compatible_with` array

## Examples

### Simple Connection (Automatically Resolved)

```yaml
steps:
  - name: extract_text
    plugin: web_scrape
    
  - name: transcribe
    plugin: content_summarize
    depends_on: [extract_text]
    # No connections needed - automatically resolves
    # text from extract_text to text in content_summarize
```

### Ambiguous Connection (Requires Explicit Mapping)

```yaml
steps:
  - name: transcribe
    plugin: content_summarize
    
  - name: analyze
    plugin: content_analyze
    depends_on: [transcribe]
    connections:
      inputs:
        text: ${content_summarize.text}
        # Explicit connection required because content_summarize outputs
        # multiple text fields: text and timestamped_text
```

## Troubleshooting

Common connection issues and how to resolve them:

1. **Connection Ambiguity Error**: Occurs when multiple compatible outputs exist
   - Solution: Add an explicit connection in the pipeline definition

2. **No Compatible Outputs Error**: Occurs when an input cannot be satisfied
   - Solution: Ensure dependency steps produce the required output type

3. **Type Mismatch Error**: Occurs when connected fields have incompatible types
   - Solution: Use a transformation step or fix the connection 