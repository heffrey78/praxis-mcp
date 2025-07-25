# Plugin Sandbox System

The Praxis plugin sandbox provides security isolation for plugin execution using context managers to ensure proper cleanup and thread safety.

## Key Features

- **Context Manager Pattern**: Uses Python context managers for guaranteed cleanup
- **Capability-Based Security**: Fine-grained permissions for file, network, and system access
- **Resource Monitoring**: CPU, memory, and wall-time limits with automatic enforcement
- **Audit Logging**: Comprehensive logging of all security-relevant operations
- **Thread Safety**: No global state modifications, safe for concurrent use

## Architecture

The sandbox system consists of several components:

1. **`PluginSandbox`**: High-level interface for creating and managing sandboxes
2. **`PluginSandboxContext`**: Low-level context manager that applies security patches
3. **`SandboxFactory`**: Factory for creating sandboxes with consistent configuration
4. **`ResourceMonitor`**: Monitors and enforces resource usage limits

## Usage

### Basic Usage

```python
from src.core.plugin_sandbox import PluginSandbox

# Create a sandbox with specific capabilities
sandbox = PluginSandbox(
    plugin_name="my-plugin",
    capabilities={"filesystem.read", "network.http"}
)

# Use the sandbox with a context manager
with sandbox.enforce():
    # Plugin code runs with restrictions
    plugin.execute()
```

### Async Usage

```python
async with sandbox.enforce_async():
    # Async plugin code runs with restrictions
    await plugin.execute_async()
```

### With Resource Limits

```python
from src.core.sandbox_types import ResourceMonitor

monitor = ResourceMonitor(
    max_memory_mb=500,      # 500MB memory limit
    max_cpu_seconds=30.0,   # 30 seconds CPU time
    max_wall_time_seconds=60.0  # 60 seconds wall time
)

sandbox = PluginSandbox(
    plugin_name="my-plugin",
    capabilities={"filesystem.read"},
    resource_monitor=monitor
)
```

### Using SandboxFactory

```python
from src.core.plugin_sandbox import SandboxFactory
from src.core.plugin_manifest import PluginCapability

factory = SandboxFactory(
    default_resource_limits={
        "max_memory_mb": 256,
        "max_cpu_seconds": 15.0
    }
)

# Create sandbox from plugin capabilities
capabilities = [
    PluginCapability(name="filesystem.read"),
    PluginCapability(name="network.http")
]

sandbox = factory.create_sandbox(
    plugin_name="my-plugin",
    capabilities=capabilities
)
```

## Capabilities

The sandbox supports the following capability types:

### Filesystem Capabilities
- `filesystem.read`: Read files and directories
- `filesystem.write`: Write files and create directories

### Network Capabilities
- `network.socket`: Create network sockets
- `network.http`: Make HTTP requests

### System Capabilities
- `system.subprocess`: Execute subprocesses
- `environment.read`: Read environment variables (sensitive vars require this)
- `environment.write`: Modify environment variables

## Security Features

### Smart Environment Variable Filtering

The sandbox automatically detects sensitive environment variables based on naming patterns:
- Variables containing: PASSWORD, SECRET, KEY, TOKEN, AUTH, CREDENTIAL, PRIVATE, CERT, SSH
- Non-sensitive variables can be read without the `environment.read` capability

### Comprehensive File Operation Coverage

All file operations are intercepted, including:
- `builtins.open()`
- `pathlib.Path.open()`, `Path.read_text()`, `Path.write_text()`
- `os.listdir()`

### Guaranteed Cleanup

Using context managers ensures that all security patches are removed even if:
- An exception occurs during plugin execution
- The sandbox activation fails
- The process is interrupted

## Audit Logging

The sandbox maintains detailed audit logs:

```python
# Get audit logs after execution
logs = sandbox.get_audit_logs()
for log in logs:
    print(f"{log.timestamp}: {log.action} - {'ALLOWED' if log.allowed else 'DENIED'}")
```

## Limitations

1. **No Nested Sandboxes**: Only one sandbox should be active at a time in a given thread
2. **Process-Wide Patches**: The sandbox modifies global functions, so it affects the entire process while active
3. **Not a Complete Security Solution**: The sandbox provides defense-in-depth but should not be the only security measure

## Best Practices

1. **Use Context Managers**: Always use `with sandbox.enforce()` or `async with sandbox.enforce_async()`
2. **Minimal Capabilities**: Grant only the capabilities a plugin actually needs
3. **Resource Limits**: Always set appropriate resource limits for untrusted plugins
4. **Audit Logs**: Monitor audit logs for security violations
5. **Thread Safety**: Avoid concurrent sandbox activation in the same thread

## Example: Sandboxed Plugin Execution

```python
from src.core.plugin_sandbox import PluginSandbox, SandboxFactory
from src.core.sandbox_types import ResourceMonitor

# Configure factory with defaults
factory = SandboxFactory(
    default_resource_limits={
        "max_memory_mb": 256,
        "max_cpu_seconds": 10.0,
        "max_wall_time_seconds": 30.0
    },
    audit_callback=lambda log: print(f"Audit: {log.action}")
)

# Create sandbox for specific plugin
sandbox = factory.create_sandbox(
    plugin_name="data-processor",
    capabilities=[
        PluginCapability(name="filesystem.read"),
        PluginCapability(name="filesystem.write", options={"path": "/tmp/output"})
    ]
)

# Execute plugin with sandbox protection
async with sandbox.enforce_async():
    result = await plugin.process_data(input_file)
    
# Check for violations
audit_logs = sandbox.get_audit_logs()
violations = [log for log in audit_logs if not log.allowed]
if violations:
    print(f"Security violations detected: {len(violations)}")
```

## Integration with Plugin System

The sandbox is integrated with the Praxis plugin system through `SandboxedPluginExecutor`:

```python
from src.core.sandboxed_plugin_executor import create_sandboxed_executor

executor = create_sandboxed_executor()
result = await executor.execute_plugin_sandboxed(
    plugin_name="my-plugin",
    params={"input": "data"},
    capabilities=[capability1, capability2]
)
```

This automatically applies sandboxing based on the plugin's declared capabilities.