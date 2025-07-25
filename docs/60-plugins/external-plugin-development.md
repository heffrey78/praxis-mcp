# External Plugin Development Guide

This guide explains how to develop, package, and distribute external plugins for Praxis.

## Overview

Praxis supports external plugins that can be:
- Developed independently of the core Praxis codebase
- Distributed as Python packages via PyPI or private indexes
- Installed using standard Python tools (pip, poetry, pdm)
- Automatically discovered and loaded by Praxis

## Quick Start

### Creating a Plugin Package

The easiest way to create an external plugin is using the Praxis CLI:

```bash
# Interactive mode (recommended for first-time users)
pdm run praxis plugin-dev create-package -i

# Non-interactive mode
pdm run praxis plugin-dev create-package \
  --name my-awesome-plugin \
  --type transform \
  --author "Your Name" \
  --email "you@example.com"
```

This creates a complete Python package structure:

```
praxis-plugin-my-awesome-plugin/
├── pyproject.toml              # Package configuration with entry points
├── README.md                   # Documentation
├── src/
│   └── praxis_plugin_my_awesome_plugin/
│       ├── __init__.py
│       ├── models.py          # Pydantic input/output models
│       └── plugin.py          # Plugin implementation
├── tests/
│   ├── __init__.py
│   └── test_plugin.py         # Unit tests
├── .gitignore
└── setup.cfg                  # Additional package settings
```

## Plugin Design Principles

Before diving into implementation, it's important to understand the distinction between **parameters** and **configuration** in Praxis plugins. This ensures consistency across all plugins and makes them predictable for users.

See the **[Plugin Parameter vs Configuration Guide](plugin-parameter-config-guide.md)** for detailed guidelines.

## Plugin Package Structure

### 1. Package Configuration (pyproject.toml)

The `pyproject.toml` file defines your package and registers it with Praxis:

```toml
[build-system]
requires = ["setuptools>=45", "wheel", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "praxis-plugin-my-awesome-plugin"
version = "0.1.0"
description = "My awesome Praxis plugin"
authors = [{name = "Your Name", email = "you@example.com"}]
license = {text = "Apache-2.0"}
readme = "README.md"
requires-python = ">=3.8"
keywords = ["praxis", "plugin", "transform"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
]

dependencies = [
    "praxis>=1.0.0",
    "pydantic>=2.0.0",
]

[project.entry-points."praxis.plugins"]
my_awesome_plugin = "praxis_plugin_my_awesome_plugin.plugin:MyAwesomePlugin"

[project.urls]
Homepage = "https://github.com/yourusername/praxis-plugin-my-awesome-plugin"
Repository = "https://github.com/yourusername/praxis-plugin-my-awesome-plugin"
```

### 2. Plugin Implementation

Plugins must inherit from `PluginBase` and follow the Praxis plugin interface:

```python
# src/praxis_plugin_my_awesome_plugin/plugin.py
from typing import Dict, Any
from praxis.plugins.plugin_base import PluginBase
from praxis.core.context import PipelineContext
from .models import MyAwesomePluginInput, MyAwesomePluginOutput

class MyAwesomePlugin(PluginBase):
    """My awesome plugin that transforms data."""
    
    InputModel = MyAwesomePluginInput
    OutputModel = MyAwesomePluginOutput
    
    async def run(
        self, 
        inputs: MyAwesomePluginInput, 
        context: PipelineContext
    ) -> MyAwesomePluginOutput:
        """Execute the plugin logic."""
        # Your plugin implementation here
        result = inputs.data.upper()  # Example transformation
        
        return MyAwesomePluginOutput(
            transformed_data=result,
            metadata={"length": len(result)}
        )
```

### 3. Input/Output Models

Define your plugin's interface using Pydantic models:

```python
# src/praxis_plugin_my_awesome_plugin/models.py
from pydantic import BaseModel, Field
from typing import Dict, Any

class MyAwesomePluginInput(BaseModel):
    """Input model for MyAwesomePlugin."""
    data: str = Field(..., description="The data to transform")
    options: Dict[str, Any] = Field(default_factory=dict, description="Transform options")

class MyAwesomePluginOutput(BaseModel):
    """Output model for MyAwesomePlugin."""
    transformed_data: str = Field(..., description="The transformed data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Transform metadata")
```

## Development Workflow

### 1. Local Development

During development, you can test your plugin without installing it:

```bash
# Run tests
cd praxis-plugin-my-awesome-plugin
pytest

# Test with Praxis (from plugin directory)
pdm run praxis plugin-dev test .

# Start development mode with hot-reload
pdm run praxis plugin-dev dev .
```

### 2. Installing Locally

Install your plugin in editable mode for testing with Praxis:

```bash
# Using pip
pip install -e ./praxis-plugin-my-awesome-plugin

# Using pdm (if in a pdm project)
pdm add -e ./praxis-plugin-my-awesome-plugin
```

### 3. Testing Installation

After installation, verify your plugin is discovered:

```bash
# List all plugins (should include yours)
pdm run praxis plugin list

# Get info about your plugin
pdm run praxis plugin info my_awesome_plugin

# Run your plugin directly
pdm run praxis plugin run my_awesome_plugin --param data="hello world"
```

## Building and Publishing

### 1. Build the Package

```bash
cd praxis-plugin-my-awesome-plugin

# Build distribution files
python -m build

# This creates:
# - dist/praxis_plugin_my_awesome_plugin-0.1.0-py3-none-any.whl
# - dist/praxis_plugin_my_awesome_plugin-0.1.0.tar.gz
```

### 2. Test Installation

Before publishing, test the built package:

```bash
# Create a test virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install your package
pip install dist/praxis_plugin_my_awesome_plugin-0.1.0-py3-none-any.whl

# Install Praxis
pip install praxis

# Test discovery
praxis plugin list
```

### 3. Publish to PyPI

```bash
# Install twine if needed
pip install twine

# Upload to Test PyPI first (recommended)
twine upload -r testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

## Distribution Options

### Git-Based Development (Recommended for Teams)

See [Git-Based Plugin Development Guide](./git-based-plugin-development.md) for collaborative development workflows using Git repositories without requiring PyPI publication.

### Installing from PyPI

Once published, users can install your plugin:

```bash
# Install from PyPI
pip install praxis-plugin-my-awesome-plugin

# Or with pdm
pdm add praxis-plugin-my-awesome-plugin
```

### Using in Pipelines

External plugins can be used in pipeline definitions just like built-in plugins:

```yaml
# pipeline.yaml
name: my-pipeline
steps:
  - name: transform_data
    plugin: my_awesome_plugin
    config:
      data: "${input_data}"
      options:
        uppercase: true
```

## Plugin Discovery Mechanism

Praxis discovers external plugins through Python entry points:

1. **Entry Point Registration**: Plugins register themselves in the `praxis.plugins` entry point group
2. **Automatic Discovery**: When Praxis starts, it scans all installed packages for this entry point
3. **Plugin Loading**: Discovered plugins are loaded and registered in the StepRegistry
4. **Name Mapping**: The entry point name becomes the plugin identifier in pipelines

## Security Considerations

External plugins run with the same permissions as Praxis. When developing plugins:

1. **Validate Inputs**: Always validate and sanitize user inputs
2. **Limit File Access**: Only access files within allowed directories
3. **Handle Errors Gracefully**: Don't expose sensitive information in error messages
4. **Document Requirements**: Clearly state what permissions your plugin needs

## Best Practices

### 1. Naming Conventions

- Package name: `praxis-plugin-<your-plugin-name>`
- Entry point: Use lowercase with underscores
- Class name: Use PascalCase

### 2. Version Management

- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Specify minimum Praxis version in dependencies
- Document breaking changes in CHANGELOG

### 3. Documentation

- Include comprehensive README with examples
- Document all configuration options
- Provide example pipeline definitions
- Include troubleshooting section

### 4. Testing

- Write unit tests for all functionality
- Test with multiple Praxis versions
- Include integration tests
- Test error conditions

### 5. Dependencies

- Keep dependencies minimal
- Pin major versions only
- Test with latest versions regularly
- Document any system requirements

## Advanced Topics

### Plugin Manifest (Optional)

For advanced features, you can include a `praxis_plugin.yaml` manifest:

```yaml
# praxis_plugin.yaml
name: my_awesome_plugin
version: 0.1.0
description: My awesome transformation plugin
author: Your Name
capabilities:
  - filesystem.read
  - network.http
compatibility:
  praxis_version: ">=1.0.0"
  python_version: ">=3.8"
```

### Multiple Plugins per Package

A single package can provide multiple plugins:

```toml
[project.entry-points."praxis.plugins"]
transform_text = "my_package.plugins:TextTransformer"
transform_json = "my_package.plugins:JsonTransformer"
transform_xml = "my_package.plugins:XmlTransformer"
```

### Private Package Indexes

For private plugins, you can host your own package index:

```bash
# Install from private index
pip install praxis-plugin-internal --index-url https://pypi.company.com/simple/

# Or configure in pip.conf
[global]
extra-index-url = https://pypi.company.com/simple/
```

## Troubleshooting

### Plugin Not Discovered

1. Verify installation: `pip list | grep praxis-plugin`
2. Check entry points: `pip show -v praxis-plugin-name | grep entry_points`
3. Ensure Praxis version compatibility
4. Check for import errors in plugin code

### Import Errors

1. Verify all dependencies are installed
2. Check for circular imports
3. Ensure proper package structure
4. Test imports in Python REPL

### Performance Issues

1. Profile your plugin code
2. Use async operations where possible
3. Minimize dependencies
4. Cache expensive operations

## Example Plugins

### Simple Transform Plugin

```python
class UppercasePlugin(PluginBase):
    """Converts text to uppercase."""
    
    class InputModel(BaseModel):
        text: str
    
    class OutputModel(BaseModel):
        text: str
    
    async def run(self, inputs: InputModel, context: PipelineContext) -> OutputModel:
        return self.OutputModel(text=inputs.text.upper())
```

### File Processing Plugin

```python
class FileProcessorPlugin(PluginBase):
    """Processes files with custom logic."""
    
    class InputModel(BaseModel):
        file_path: str
        encoding: str = "utf-8"
    
    class OutputModel(BaseModel):
        processed_path: str
        line_count: int
    
    async def run(self, inputs: InputModel, context: PipelineContext) -> OutputModel:
        output_path = os.path.join(context.artifacts_dir, "processed.txt")
        line_count = 0
        
        async with aiofiles.open(inputs.file_path, 'r', encoding=inputs.encoding) as infile:
            async with aiofiles.open(output_path, 'w', encoding=inputs.encoding) as outfile:
                async for line in infile:
                    processed = line.strip().upper()
                    await outfile.write(processed + '\n')
                    line_count += 1
        
        return self.OutputModel(
            processed_path=output_path,
            line_count=line_count
        )
```

## Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [Entry Points Specification](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Praxis Plugin Examples](https://github.com/praxis-ai/plugin-examples)

## Support

For help with plugin development:

1. Check the [Praxis Documentation](https://praxis.ai/docs)
2. Browse [Example Plugins](https://github.com/praxis-ai/plugin-examples)
3. Ask in [Discussions](https://github.com/praxis-ai/praxis/discussions)
4. Report issues on [GitHub](https://github.com/praxis-ai/praxis/issues)