# Pipeline Parameters

Pipeline parameters allow you to define required and optional inputs for your pipelines. These parameters are validated before the pipeline runs to ensure all required data is present.

## Parameter Definition

Parameters are defined in the pipeline YAML file under the `params` section. Each parameter has the following fields:

```yaml
params:
  - name: parameter_name      # Required: Name of the parameter
    required: true           # Optional: Whether the parameter is required (default: true)
    description: "..."       # Optional: Description of what the parameter is used for
    type: string            # Optional: Parameter type (default: "string")
```

### Supported Types
- `string`: Text values
- `integer`: Whole numbers
- `boolean`: True/false values

## Example Pipelines

### YouTube Video Analysis
```yaml
id: youtube_full_analysis
name: youtube_full_analysis
description: Full analysis pipeline for YouTube videos

params:
  - name: video_url
    required: true
    description: "URL of the YouTube video to analyze"
    type: string

steps:
  - name: video_download
    plugin: video_download
    depends_on: []
    fail_on_error: true
  # ... more steps ...
```

### Web Content Analysis
```yaml
id: web_scrape
name: web_scrape
description: Pipeline for scraping and analyzing web content

params:
  - name: url
    required: true
    description: "URL of the webpage to scrape and analyze"
    type: string

steps:
  - name: scrape
    plugin: web_scrape
    depends_on: []
    fail_on_error: true
  # ... more steps ...
```

## Parameter Validation

The pipeline orchestrator validates parameters before running the pipeline:
1. Checks that all required parameters are present
2. Validates parameter types
3. Ensures no duplicate parameter names

### Validation Errors

The orchestrator will raise a `ValueError` with a descriptive message if:
- A required parameter is missing
- A parameter value has the wrong type
- There are duplicate parameter names

Example error messages:
```python
# Missing required parameter
ValueError: Missing required parameters for pipeline 'youtube_full_analysis': video_url

# Invalid parameter type
ValueError: Invalid parameter types in pipeline 'web_scrape': url (expected string)
```

## Usage in Code

When running a pipeline, provide the parameters in the context:

```python
context = PipelineContext()

# For YouTube analysis
context["video_url"] = "https://www.youtube.com/watch?v=..."
await orchestrator.runPipeline(context, youtube_pipeline)

# For web scraping
context["url"] = "https://example.com/article"
await orchestrator.runPipeline(context, web_scrape_pipeline)
```

## Best Practices

1. **Clear Descriptions**: Always provide clear descriptions for parameters to help users understand what values to provide.

2. **Required vs Optional**: Only mark parameters as required if they are absolutely necessary. Use optional parameters with sensible defaults when possible.

3. **Type Safety**: Always specify the parameter type to ensure proper validation.

4. **Naming**: Use clear, descriptive names for parameters. Follow these conventions:
   - Use lowercase with underscores
   - Be specific (e.g., `video_url` instead of just `url`)
   - Use consistent naming across similar pipelines 

## Step Connections

Steps can include an optional `connections` section to specify how outputs from previous steps map to inputs:

```yaml
- name: summarize
  plugin: content_summarize
  depends_on: [transcribe]
  connections:
    inputs:
      text: ${transcribe.transcript}
```

### Connection Format

Each connection follows this pattern:
- The key is the target input field
- The value uses `${step_name.field_name}` syntax to reference an output

### When Connections Are Required

Connections are required when:
1. Multiple compatible outputs exist from dependency steps
2. The field names don't match between steps
3. Custom transformations are needed

The system will automatically resolve unambiguous connections, so simple pipelines don't need explicit connections. 