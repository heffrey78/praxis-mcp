# Simple Plugin Management

The easiest way to use external Praxis plugins with minimal setup.

## Quick Start - Two Options

### Option 1: CLI Commands (Recommended)

Use the built-in Praxis CLI commands to manage plugin repositories:

```bash
# Add a plugin repository
pdm run praxis plugin repo add https://github.com/someone/awesome-praxis-plugins.git

# List all repositories
pdm run praxis plugin repo list

# Update all repositories
pdm run praxis plugin repo update

# Verify all plugins are valid
pdm run praxis plugin repo verify
```

The CLI automatically:
- Clones repositories to the right location
- Manages updates and versions
- Verifies plugin validity
- Handles the PRAXIS_PLUGIN_PATHS configuration

### Option 2: Manual Setup (2 Steps)

#### Step 1: Set Plugin Directories

Add to your `.env` file:
```bash
# Single directory
PRAXIS_PLUGIN_PATHS="/Users/you/my-plugins"

# Multiple directories (colon-separated)
PRAXIS_PLUGIN_PATHS="/Users/you/my-plugins:/Users/you/work-plugins:/Users/you/community-plugins"
```

#### Step 2: Clone Plugin Repos

```bash
# Create your plugins directory
mkdir -p ~/my-plugins
cd ~/my-plugins

# Clone any plugin repositories
git clone https://github.com/someone/awesome-praxis-plugins.git
git clone https://github.com/company/internal-plugins.git
git clone https://github.com/you/experimental-plugins.git
```

**That's it!** Praxis will automatically discover all plugins in these directories.

## Verify Everything Works

```bash
# List all discovered plugins
pdm run praxis plugin list

# Check a specific plugin
pdm run praxis plugin info audio-transcribe

# Run a plugin
pdm run praxis plugin run audio-transcribe --help
```

## Directory Structure

Praxis automatically scans for plugins in this structure:

```
~/my-plugins/
├── awesome-praxis-plugins/        # Git repo 1
│   └── plugins/
│       ├── audio-transcribe/
│       ├── video-process/
│       └── pdf-extract/
├── internal-plugins/              # Git repo 2
│   └── plugins/
│       ├── company-analyzer/
│       └── data-validator/
└── experimental-plugins/          # Git repo 3
    └── plugins/
        └── new-feature/
```

## Common Patterns

### Pattern 1: Personal Plugins Directory
```bash
# One-time setup
echo 'PRAXIS_PLUGIN_PATHS="$HOME/praxis-plugins"' >> ~/.env
mkdir -p ~/praxis-plugins

# Add any plugin repo
cd ~/praxis-plugins
git clone https://github.com/cool/plugins.git
```

### Pattern 2: Project-Specific Plugins
```bash
# In your project directory
mkdir plugins
echo 'PRAXIS_PLUGIN_PATHS="./plugins"' >> .env

# Clone plugins for this project
cd plugins
git clone https://github.com/needed/plugins.git
```

### Pattern 3: Team Shared Plugins
```bash
# Mount shared drive or use consistent path
PRAXIS_PLUGIN_PATHS="/opt/team/praxis-plugins:/Users/you/my-plugins"
```

## Plugin Repository Structure

Each plugin repository should follow this structure:

```
my-plugin-repo/
└── plugins/                    # Required: plugins directory
    ├── plugin-one/            # Each plugin in its own folder
    │   └── src/
    │       └── praxis_plugin_one/
    │           ├── __init__.py
    │           ├── plugin.py
    │           ├── models.py
    │           └── praxis_plugin.yaml
    └── plugin-two/
        └── src/
            └── praxis_plugin_two/
                ├── __init__.py
                ├── plugin.py
                ├── models.py
                └── praxis_plugin.yaml
```

## Updating Plugins

### Using CLI Commands (Recommended)

```bash
# Update all repositories
pdm run praxis plugin repo update

# Update a specific repository
pdm run praxis plugin repo update awesome-praxis-plugins
```

### Manual Updates

```bash
# Update a single repo
cd ~/my-plugins/awesome-praxis-plugins
git pull

# Update all repos
cd ~/my-plugins
for repo in */; do
  echo "Updating $repo..."
  git -C "$repo" pull
done
```

## FAQ

**Q: Do I need to install anything?**
A: No! Just clone and set the path. Praxis handles the rest.

**Q: Can I use private repositories?**
A: Yes! Use SSH URLs: `git clone git@github.com:company/private-plugins.git`

**Q: What if plugins have dependencies?**
A: Install them normally: `pip install openai-whisper`

**Q: Can I mix local and installed plugins?**
A: Yes! Praxis will discover both.

**Q: How do I know which plugins are loaded?**
A: Run `pdm run praxis plugin list` - external plugins will appear alongside built-ins.

## Plugin Repository CLI Commands

Praxis includes built-in commands for managing plugin repositories:

### `praxis plugin repo add`
Clone a new plugin repository:
```bash
pdm run praxis plugin repo add https://github.com/user/plugins.git
pdm run praxis plugin repo add git@github.com:company/private.git --name company
```

### `praxis plugin repo list`
Show all plugin repositories:
```bash
pdm run praxis plugin repo list
```

### `praxis plugin repo update`
Update repositories to latest version:
```bash
pdm run praxis plugin repo update              # Update all
pdm run praxis plugin repo update my-plugins   # Update specific
```

### `praxis plugin repo remove`
Remove a plugin repository:
```bash
pdm run praxis plugin repo remove old-plugins
```

### `praxis plugin repo verify`
Check all plugins are valid:
```bash
pdm run praxis plugin repo verify
```

## That's It!

No scripts, no complex setup. Just:
1. Use `praxis plugin repo add` to add repositories, OR
2. Manually set `PRAXIS_PLUGIN_PATHS` and clone repos
3. Start using plugins

The simplest possible developer experience.