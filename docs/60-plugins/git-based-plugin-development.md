# Git-Based Plugin Development Guide

This guide covers developing and distributing Praxis plugins through Git repositories, enabling collaborative development and flexible distribution without requiring PyPI publication.

## Overview

Git-based plugin development offers several advantages:
- **Instant testing** - No install/build cycle during development
- **Easy collaboration** - Standard Git workflows (PRs, branches, etc.)
- **Flexible distribution** - Users can clone or pip install from Git
- **Version control** - Pin to specific commits, tags, or branches

## Repository Structure

### Recommended Layout

```
my-praxis-plugins/
├── README.md                 # Repository overview and usage
├── .gitignore               # Python gitignore template
├── LICENSE                  # Your chosen license
├── requirements.txt         # Shared dependencies for all plugins
├── requirements-dev.txt     # Development dependencies
├── plugins/                 # All plugins live here
│   ├── audio-transcribe/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src/
│   │       └── praxis_plugin_audio_transcribe/
│   │           ├── __init__.py
│   │           ├── praxis_plugin.yaml
│   │           ├── plugin.py
│   │           ├── models.py
│   │           └── types.py
│   ├── content-qa/
│   └── data-extractor/
├── scripts/
│   ├── setup-dev.sh        # Developer setup script
│   ├── test-all.sh         # Run all plugin tests
│   └── build-all.sh        # Build all plugins
├── docs/
│   ├── plugin-guide.md     # Usage documentation
│   └── development.md      # Development guide
├── examples/
│   └── pipelines/          # Example pipeline YAMLs
└── .github/
    └── workflows/
        └── test.yml        # CI/CD configuration
```

## Development Workflow

### Initial Setup

1. **Create Repository**
   ```bash
   mkdir my-praxis-plugins
   cd my-praxis-plugins
   git init
   
   # Create directory structure
   mkdir -p plugins scripts docs examples/pipelines
   ```

2. **Configure Praxis for Development**
   ```bash
   # Add to your Praxis .env file
   echo 'PRAXIS_PLUGIN_PATHS="/path/to/my-praxis-plugins/plugins"' >> /path/to/praxis/backend/.env
   
   # Or export temporarily
   export PRAXIS_PLUGIN_PATHS="/path/to/my-praxis-plugins/plugins"
   ```

3. **Create Setup Script**
   ```bash
   # scripts/setup-dev.sh
   #!/bin/bash
   REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
   
   echo "🔧 Setting up Praxis plugin development environment..."
   
   # Check if .env exists
   ENV_FILE="${HOME}/.praxis/.env"
   if [ -f "$ENV_FILE" ]; then
     if ! grep -q "PRAXIS_PLUGIN_PATHS" "$ENV_FILE"; then
       echo "PRAXIS_PLUGIN_PATHS=\"${REPO_ROOT}/plugins\"" >> "$ENV_FILE"
       echo "✅ Added plugin path to $ENV_FILE"
     fi
   else
     echo "⚠️  No .env file found. Add this to your Praxis .env:"
     echo "   PRAXIS_PLUGIN_PATHS=\"${REPO_ROOT}/plugins\""
   fi
   
   # Install development dependencies
   if [ -f requirements-dev.txt ]; then
     pip install -r requirements-dev.txt
   fi
   
   echo "✅ Setup complete! Run 'praxis plugin list' to verify plugins are discovered."
   ```

### Daily Development

1. **Create/Modify Plugins**
   ```bash
   # Work on your plugin
   vim plugins/audio-transcribe/src/praxis_plugin_audio_transcribe/plugin.py
   ```

2. **Test Immediately**
   ```bash
   # No installation needed - changes are reflected instantly
   cd /path/to/praxis/backend
   pdm run praxis plugin list
   pdm run praxis plugin run audio-transcribe --help
   ```

3. **Commit Changes**
   ```bash
   git add -A
   git commit -m "feat: add voice activity detection"
   git push origin main
   ```

## Distribution Methods

### Method 1: Clone and Configure (Developers)

Perfect for active development and contributors.

```bash
# Clone the repository
git clone https://github.com/username/my-praxis-plugins.git
cd my-praxis-plugins

# Run setup script
./scripts/setup-dev.sh

# Start developing!
praxis plugin list
```

### Method 2: Direct Git Installation (End Users)

For users who want to install plugins as packages.

```bash
# Install single plugin from Git
pip install git+https://github.com/username/my-praxis-plugins.git#subdirectory=plugins/audio-transcribe

# Install specific version/tag
pip install git+https://github.com/username/my-praxis-plugins.git@v1.0.0#subdirectory=plugins/audio-transcribe

# Install from branch
pip install git+https://github.com/username/my-praxis-plugins.git@feature/new-model#subdirectory=plugins/audio-transcribe
```

### Method 3: Requirements File

Create `requirements-plugins.txt`:

```txt
# Praxis External Plugins
git+https://github.com/username/my-praxis-plugins.git@main#subdirectory=plugins/audio-transcribe
git+https://github.com/username/my-praxis-plugins.git@main#subdirectory=plugins/content-qa
git+https://github.com/username/my-praxis-plugins.git@main#subdirectory=plugins/data-extractor
```

Users install with:
```bash
pip install -r requirements-plugins.txt
```

### Method 4: Meta-Package (Advanced)

Create a root `pyproject.toml` that installs all plugins:

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-praxis-plugins"
version = "1.0.0"
description = "Collection of Praxis plugins"
dependencies = [
    "praxis-plugin-audio-transcribe",
    "praxis-plugin-content-qa",
    "praxis-plugin-data-extractor",
]

[tool.setuptools.packages.find]
where = ["plugins"]
include = ["praxis_plugin_*"]
```

Then users can install everything:
```bash
pip install git+https://github.com/username/my-praxis-plugins.git
```

## Collaboration Patterns

### Feature Branch Workflow

```bash
# Create feature branch
git checkout -b feature/add-whisper-large

# Make changes and test
vim plugins/audio-transcribe/src/.../plugin.py
praxis plugin run audio-transcribe -c '{"model": "large"}'

# Push and create PR
git push origin feature/add-whisper-large
```

### Version Tagging

```bash
# Tag individual plugin versions
git tag audio-transcribe-v1.2.0
git tag content-qa-v2.0.0

# Or tag all plugins
git tag v1.5.0

# Push tags
git push --tags
```

### Continuous Integration

Example `.github/workflows/test.yml`:

```yaml
name: Test Plugins
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', 3.11]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install praxis
        pip install -r requirements-dev.txt
    
    - name: Test plugin discovery
      run: |
        export PRAXIS_PLUGIN_PATHS="${PWD}/plugins"
        praxis plugin list | grep -E "(audio-transcribe|content-qa|data-extractor)"
    
    - name: Test plugins
      run: |
        export PRAXIS_PLUGIN_PATHS="${PWD}/plugins"
        ./scripts/test-all.sh
```

## Best Practices

### 1. Plugin Independence

- Each plugin in its own directory
- Independent `pyproject.toml` files
- Can be installed/versioned separately
- Minimal inter-plugin dependencies

### 2. Documentation Standards

```markdown
# plugins/audio-transcribe/README.md

# Audio Transcribe Plugin

## Overview
Transcribes audio files using OpenAI Whisper.

## Requirements
- Python 3.8+
- ffmpeg (for audio processing)
- 1GB+ RAM for small model, 5GB+ for large

## Installation

### Development Mode
```bash
export PRAXIS_PLUGIN_PATHS="/path/to/repo/plugins"
```

### Package Mode
```bash
pip install git+https://github.com/user/plugins.git#subdirectory=plugins/audio-transcribe
```

## Usage

### CLI
```bash
praxis plugin run audio-transcribe \
  -p audio_path=/path/to/audio.mp3 \
  -c '{"model": "medium", "language": "en"}'
```

### Pipeline
```yaml
steps:
  - plugin: audio-transcribe
    config:
      model: medium
    inputs:
      audio_path: "{{ audio_file }}"
```

## Configuration Options
- `model`: Whisper model size (tiny, base, small, medium, large)
- `language`: ISO language code or None for auto-detect
- `mock_mode`: Use mock transcription for testing
```

### 3. Testing Strategy

Create `scripts/test-all.sh`:

```bash
#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PRAXIS_PLUGIN_PATHS="${REPO_ROOT}/plugins"

echo "🧪 Testing all plugins..."

# Test discovery
echo "Testing plugin discovery..."
plugin_count=$(praxis plugin list | grep -c "│" || true)
if [ "$plugin_count" -lt 5 ]; then
    echo "❌ Expected at least 5 plugins, found $plugin_count"
    exit 1
fi

# Test each plugin with mock mode
for plugin_dir in "${REPO_ROOT}"/plugins/*/; do
    if [ -d "$plugin_dir" ]; then
        plugin_name=$(basename "$plugin_dir" | sed 's/praxis-plugin-//')
        echo ""
        echo "Testing $plugin_name..."
        
        if praxis plugin run "$plugin_name" -c '{"mock_mode": true}' 2>&1 | grep -q "Error"; then
            echo "❌ $plugin_name failed"
            exit 1
        else
            echo "✅ $plugin_name passed"
        fi
    fi
done

echo ""
echo "✅ All tests passed!"
```

### 4. Security Considerations

- Always validate inputs in plugins
- Use manifest capabilities to declare permissions
- Don't hardcode sensitive data
- Document security requirements

### 5. Dependency Management

Create `plugins/shared-requirements.txt` for common dependencies:

```txt
# Shared dependencies for all plugins
pydantic>=2.0.0
aiofiles>=0.8.0
httpx>=0.24.0
```

Each plugin can then reference:
```toml
# In plugin's pyproject.toml
dependencies = [
    "-r ../shared-requirements.txt",
    "openai-whisper>=20230918",  # Plugin-specific
]
```

## Troubleshooting

### Plugins Not Discovered

1. **Check PRAXIS_PLUGIN_PATHS**
   ```bash
   echo $PRAXIS_PLUGIN_PATHS
   # Should show your plugin directory
   ```

2. **Verify manifest files**
   ```bash
   find plugins -name "praxis_plugin.yaml" -exec head -1 {} \;
   # Should show "api_version: praxis/v1" for each
   ```

3. **Check Python imports**
   ```bash
   cd plugins/audio-transcribe/src
   python -c "from praxis_plugin_audio_transcribe.plugin import AudioTranscribePlugin"
   ```

### Installation Issues

- For SSH URLs: Ensure SSH keys are configured
- For private repos: Use token authentication
- For subpackages: Ensure `#subdirectory=` path is correct

### Development vs Production

- Development: Use `PRAXIS_PLUGIN_PATHS`
- Production: Install via pip from Git
- Both can coexist (installed version takes precedence)

## Summary

Git-based plugin development provides the best balance of:
- ✅ Rapid development iteration
- ✅ Standard version control
- ✅ Flexible distribution options
- ✅ Collaborative workflows
- ✅ No dependency on PyPI

This approach is ideal for teams developing custom plugins, organizations with private plugins, and open-source plugin collections.