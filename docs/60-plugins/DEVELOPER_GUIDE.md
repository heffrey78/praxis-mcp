# Praxis External Plugin Developer Guide

## 🎯 How External Plugins Work

Praxis uses Python's standard entry point system for plugin discovery. This means:
- Plugins are standard Python packages
- They can be distributed via PyPI, private indexes, or GitHub
- They're automatically discovered when installed
- No manual registration or configuration needed

## 📦 Plugin Package Structure

```
praxis-plugin-example/
├── pyproject.toml              # Package metadata & entry point
├── README.md                   # Documentation
├── src/
│   └── praxis_plugin_example/
│       ├── __init__.py         # Package init
│       ├── praxis_plugin.yaml  # Plugin manifest (optional)
│       ├── plugin.py           # Plugin implementation
│       ├── models.py           # Pydantic models
│       └── types.py            # Type definitions
└── tests/                      # Plugin tests
```

## 🚀 Development Workflow

### 1. Local Development

```bash
# Clone or create your plugin
cd /path/to/your/plugins

# Install in development mode
pip install -e ./praxis-plugin-example

# Verify installation
pip list | grep praxis-plugin

# Test with Praxis
pdm run praxis plugin list
pdm run praxis plugin run example --help
```

### 2. Testing Without Installation

```bash
# Option A: Use environment variable
export PRAXIS_PLUGIN_PATHS="/path/to/plugin1:/path/to/plugin2"

# Option B: Use project-local plugins
mkdir praxis_plugins
ln -s /path/to/plugin praxis_plugins/

# Option C: Use user plugins directory
mkdir -p ~/.praxis/plugins
ln -s /path/to/plugin ~/.praxis/plugins/
```

### 3. Publishing

```bash
# Build the package
cd praxis-plugin-example
python -m build

# Upload to PyPI
twine upload dist/*

# Users can then install with:
pip install praxis-plugin-example
```

## 🔧 Entry Points Explained

The magic happens in `pyproject.toml`:

```toml
[project.entry-points."praxis.plugins"]
example = "praxis_plugin_example.plugin:ExamplePlugin"
```

This tells Python:
- There's a Praxis plugin named "example"
- It's implemented by the `ExamplePlugin` class
- In the `praxis_plugin_example.plugin` module

## 📝 Plugin Manifest (Optional)

While entry points handle discovery, you can include a `praxis_plugin.yaml` for additional metadata:

```yaml
metadata:
  name: example
  version: "1.0.0"
  description: "Example plugin"
  author: "Your Name"
  
requirements:
  python: ">=3.8"
  
capabilities:
  - filesystem.read
  - network.http
```

## 🌐 Using Plugins from GitHub

Users can install directly from GitHub:

```bash
# Latest from main branch
pip install git+https://github.com/user/praxis-plugin-example.git

# Specific version
pip install git+https://github.com/user/praxis-plugin-example.git@v1.0.0

# Development mode
git clone https://github.com/user/praxis-plugin-example.git
pip install -e ./praxis-plugin-example
```

## 🔒 Security

External plugins run with the same permissions as Praxis itself. For sandboxed execution:
- Praxis includes a capability-based security system
- Plugins can declare required capabilities
- Admins can restrict plugin permissions

## 💡 Best Practices

1. **Naming**: Use `praxis-plugin-` prefix for packages
2. **Versioning**: Follow semantic versioning
3. **Dependencies**: Minimize external dependencies
4. **Testing**: Include comprehensive tests
5. **Documentation**: Provide clear usage examples
6. **Imports**: Use absolute imports within your package

## 🐛 Troubleshooting

### Plugin not discovered
```bash
# Check if installed
pip list | grep praxis-plugin

# Check entry points
python -c "import importlib.metadata; print(list(importlib.metadata.entry_points(group='praxis.plugins')))"
```

### Import errors
- Ensure Praxis is installed: `pip install praxis`
- Check Python path: `python -c "import sys; print(sys.path)"`
- Verify imports in plugin code

### Development mode issues
- Use `pip install -e .` not `pip install .`
- Ensure `pyproject.toml` is in the root directory
- Check that `src/` layout is used correctly
