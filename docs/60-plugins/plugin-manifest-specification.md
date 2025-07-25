# Plugin Manifest Specification

This document describes the complete specification for Praxis plugin manifests (`praxis_plugin.yaml`).

## Overview

Plugin manifests are **OPTIONAL** for basic plugin functionality but **REQUIRED** for:
- Security sandboxing and capability declarations
- Package distribution metadata
- Version compatibility checks
- Dependency management

## Manifest Format

### Complete Example

```yaml
api_version: praxis/v1  # Required

metadata:
  name: example-plugin  # Must match pattern: ^[a-z0-9-]+$
  version: "1.0.0"      # Semantic version (X.Y.Z)
  description: "A example plugin for demonstration"  # Max 500 chars
  author: "Your Name"
  author_email: "you@example.com"  # Optional
  license: "Apache-2.0"            # Optional
  homepage: "https://github.com/user/example-plugin"  # Optional

compatibility:
  praxis: ">=1.0.0,<2.0.0"  # Required: Praxis version constraint
  python: ">=3.8,<4.0"      # Required: Python version constraint

entrypoints:
  - name: example          # Required: Plugin identifier
    module: example_plugin.plugin  # Required: Python module path
    class_name: ExamplePlugin      # Required: Plugin class name

capabilities:
  - name: filesystem.read    # Required: Capability name
    level: required          # required or optional
    scope: "/data"           # Optional: Scope restriction
  - name: network.http
    level: optional

dependencies:  # Optional
  - name: requests
    version: ">=2.25.0"
  - name: pandas
    version: "~=1.3.0"
    extras: ["sql", "excel"]
```

### Minimal Example (Without Manifest)

For local development, plugins work without manifests:

```python
# plugin.py
from src.plugins.plugin_base import PluginBase

class ExamplePlugin(PluginBase):
    """Plugin description."""
    # ... implementation
```

## Field Specifications

### api_version (Required)
- **Type**: string
- **Value**: Must be `praxis/v1`
- **Description**: Manifest format version

### metadata (Required)
All fields under metadata are required unless marked optional:

- **name**: Plugin identifier
  - Pattern: `^[a-z0-9-]+$` (lowercase letters, numbers, hyphens only)
  - Example: `audio-transcribe`, `data-extractor`
  
- **version**: Semantic version
  - Format: `X.Y.Z` (e.g., `1.0.0`, `2.1.3`)
  
- **description**: Plugin description
  - Maximum 500 characters
  
- **author**: Plugin author name
  
- **author_email** (Optional): Contact email
  
- **license** (Optional): License identifier (e.g., `Apache-2.0`, `MIT`)
  
- **homepage** (Optional): Plugin homepage URL

### compatibility (Required)
Version constraints for runtime compatibility:

- **praxis**: Praxis version constraint
  - Uses PEP 440 version specifiers
  - Examples: `>=1.0.0`, `~=1.2.0`, `>=1.0.0,<2.0.0`
  
- **python**: Python version constraint
  - Same format as praxis version
  - Example: `>=3.8,<4.0`

### entrypoints (Required)
List of plugin entry points. Each entry must have:

- **name**: Plugin identifier used in pipelines
- **module**: Python module containing the plugin class
- **class_name**: Name of the plugin class

### capabilities (Optional)
Security capabilities required by the plugin. Each capability has:

- **name**: Capability identifier
  - Common capabilities:
    - `filesystem.read`: Read files
    - `filesystem.write`: Write files
    - `network.http`: Make HTTP requests
    - `network.https`: Make HTTPS requests
    - `system.exec`: Execute system commands
    - `system.env`: Access environment variables
    
- **level**: Requirement level
  - `required`: Plugin won't function without this
  - `optional`: Plugin has degraded functionality without this
  
- **scope** (Optional): Restrict capability to specific scope
  - For filesystem: directory paths (e.g., `/tmp`, `/data`)
  - For network: URL patterns or domains

### dependencies (Optional)
Python package dependencies. Each dependency has:

- **name**: Package name
- **version** (Optional): Version constraint (PEP 440)
- **extras** (Optional): List of package extras

## Manifest Discovery

Praxis looks for manifests in these locations:

1. **Package-based plugins**: In the module directory specified by entry point
2. **Local folder plugins**: `praxis_plugin.yaml` in plugin directory
3. **Development plugins**: Same directory as plugin.py

## Validation Rules

1. **Name validation**: Must match `^[a-z0-9-]+$`
2. **Version validation**: Must be semantic version (X.Y.Z)
3. **Compatibility validation**: Must be valid PEP 440 version specifiers
4. **Capability validation**: Must use known capability names
5. **Entry point validation**: Module and class must exist

## When You Need a Manifest

### Required For:
- Distribution via PyPI or package managers
- Security sandboxing with specific capabilities
- Version compatibility enforcement
- Explicit dependency management

### Not Required For:
- Local development and testing
- Simple plugins without external dependencies
- Plugins that only use Praxis built-in features
- Quick prototyping

## Migration Guide

### From No Manifest to Manifest

1. Start with minimal manifest:
```yaml
api_version: praxis/v1
metadata:
  name: my-plugin
  version: "0.1.0"
  description: "My plugin"
  author: "Me"
compatibility:
  praxis: ">=1.0.0"
  python: ">=3.8"
entrypoints:
  - name: my_plugin
    module: my_plugin
    class_name: MyPlugin
```

2. Add capabilities as needed
3. Add dependencies if using external packages
4. Update version compatibility based on testing

## Common Issues

### "Unsupported API version"
- Ensure `api_version: praxis/v1` is the first line

### "String should match pattern"
- Plugin names must be lowercase with hyphens only
- No underscores, uppercase, or special characters

### "Field required"
- Check all required fields are present
- `compatibility` section is often forgotten

### "Invalid manifest structure"
- Validate YAML syntax
- Check indentation (use spaces, not tabs)
- Ensure all required fields have values

## Best Practices

1. **Start without manifest** for local development
2. **Add manifest** when ready to distribute
3. **Declare minimal capabilities** for better security
4. **Use semantic versioning** consistently
4. **Test compatibility** before updating constraints
5. **Document capabilities** in plugin README

## Future Compatibility

The `api_version: praxis/v1` ensures forward compatibility. Future versions may add optional fields but will maintain backward compatibility with v1 manifests.