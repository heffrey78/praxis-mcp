# MLflow Integration Guide for Praxis

## Overview

MLflow is integrated into Praxis to provide comprehensive experiment tracking and monitoring for agent conversations. This guide covers everything you need to know about using MLflow with your Praxis project.

## What is MLflow?

MLflow is an open-source platform for managing the machine learning lifecycle, including experimentation, reproducibility, deployment, and model registry. In Praxis, MLflow is specifically used for:

- **Experiment Tracking**: Monitor agent conversation performance and behavior
- **Artifact Management**: Store conversation histories and related files
- **Metrics Logging**: Track execution times, response lengths, and other KPIs
- **Parameter Tracking**: Record which models, agents, and configurations were used

## Quick Start

### 1. Start MLflow UI

```bash
# Navigate to your Praxis project directory
cd /path/to/praxis/backend

# Start MLflow UI (runs on port 5000 by default)
pdm run mlflow ui
```

Access the UI at: **http://localhost:5000**

### 2. Generate Some Data

Run an agent conversation to generate MLflow tracking data:

```bash
# Run an agent conversation (this will create MLflow runs automatically)
pdm run praxis agent run hello-world
```

### 3. View Your Data

Open the MLflow UI in your browser and explore:
- **Experiments**: Navigate through different experiment runs
- **Runs**: View individual conversation sessions
- **Metrics**: Compare execution times and response lengths
- **Artifacts**: Download conversation histories

## Integration Details

### Automatic Tracking

MLflow tracking is automatically enabled for all agent conversations. The integration happens in:
- **File**: `src/services/conversation_runner.py`
- **Class**: `ConversationRunner`
- **Method**: `_execute_with_mlflow()`

### Tracked Data

#### Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `execution_time_seconds` | Total time for agent conversation | Seconds |
| `response_length` | Character count of agent response | Characters |

#### Tags
| Tag | Description | Example |
|-----|-------------|---------|
| `session_id` | Unique conversation session ID | `550e8400-e29b-41d4-a716-446655440000` |
| `agent_name` | Name of the agent that handled the conversation | `Hello World Agent` |
| `model` | AI model used for the conversation | `gpt-4o`, `claude-3-sonnet` |
| `tools_count` | Number of tools available to the agent | `5` |

#### Artifacts
| Artifact | Description | Format |
|----------|-------------|--------|
| `conversation_history/` | Complete conversation transcript | JSON |

### Experiment Structure

- **Default Experiment**: "OpenAI Agent"
- **Run Naming**: `Agent: {agent_name} | Session: {session_id[:8]} | {timestamp}`
- **Data Location**: `mlruns/` directory in project root

## MLflow UI Navigation

### Experiments View
- Lists all your MLflow experiments
- Shows total runs, last activity, and experiment ID
- Default experiment is "OpenAI Agent"

### Runs View
- Shows all runs within an experiment
- Sortable by metrics, parameters, and timestamps
- Click on any run to view details

### Run Details
- **Overview**: Run metadata, duration, and status
- **Parameters**: Shows tags like agent_name, model, session_id
- **Metrics**: Graphs and values for tracked metrics
- **Artifacts**: Download conversation histories and other files

### Comparison View
- Select multiple runs to compare metrics
- Useful for analyzing agent performance across sessions
- Can compare different agents or models

## Advanced Usage

### Custom MLflow Commands

```bash
# List all experiments
pdm run mlflow experiments list

# Get experiment details
pdm run mlflow experiments describe --experiment-id 0

# List runs for a specific experiment
pdm run mlflow runs list --experiment-id 0

# Search runs with filters
pdm run mlflow runs list --experiment-id 0 --filter "metrics.execution_time_seconds > 5.0"

# Download artifacts from a specific run
pdm run mlflow artifacts download --run-id <run-id> --dst-path ./downloads

# Export run data
pdm run mlflow runs export --run-id <run-id> --output-file run_data.json
```

### Querying Data Programmatically

```python
import mlflow
from mlflow.tracking import MlflowClient

# Initialize client
client = MlflowClient()

# Get experiment by name
experiment = client.get_experiment_by_name("OpenAI Agent")

# Search runs
runs = client.search_runs(
    experiment_ids=[experiment.experiment_id],
    filter_string="metrics.execution_time_seconds > 5.0",
    order_by=["metrics.execution_time_seconds DESC"]
)

# Print run information
for run in runs:
    print(f"Run ID: {run.info.run_id}")
    print(f"Agent: {run.data.tags.get('agent_name', 'Unknown')}")
    print(f"Execution Time: {run.data.metrics.get('execution_time_seconds', 0):.2f}s")
    print("---")
```

## Configuration

### Enabling/Disabling MLflow

MLflow is enabled by default. To disable it:

```python
# In your code
agent_service = AgentService(
    agent_name="your-agent",
    enable_mlflow=False  # Disable MLflow tracking
)
```

### Changing Storage Location

By default, MLflow data is stored in the `mlruns/` directory. To change this:

```bash
# Set MLflow tracking URI environment variable
export MLFLOW_TRACKING_URI=file:///path/to/your/mlflow/data

# Or use a remote tracking server
export MLFLOW_TRACKING_URI=http://your-mlflow-server:5000
```

### Custom Experiment Names

To use a different experiment name:

```python
# In src/services/conversation_runner.py
mlflow.set_experiment("Your Custom Experiment Name")
```

## Data Management

### Storage Structure

```
mlruns/
├── 0/                          # Default experiment
│   ├── meta.yaml              # Experiment metadata
│   └── <run-id>/              # Individual runs
│       ├── meta.yaml          # Run metadata
│       ├── metrics/           # Metric values
│       ├── params/            # Parameters (empty for this integration)
│       ├── tags/              # Tag values
│       └── artifacts/         # Stored artifacts
│           └── conversation_history/
├── .trash/                    # Deleted runs
└── <experiment-id>/           # Other experiments
```

### Backup and Export

```bash
# Backup entire MLflow data directory
cp -r mlruns/ mlruns_backup_$(date +%Y%m%d)

# Export specific experiment
pdm run mlflow experiments export --experiment-id 0 --output-file experiment_backup.json

# Export all runs from an experiment
pdm run mlflow runs export-batch --experiment-id 0 --output-file runs_backup.json
```

### Cleanup

```bash
# Clean up old runs (be careful with this)
pdm run mlflow gc --experiment-id 0

# Delete specific runs
pdm run mlflow runs delete --run-id <run-id>
```

## Troubleshooting

### Common Issues

#### 1. MLflow UI Not Starting
```bash
# Error: command not found
# Solution: Use PDM to run MLflow
pdm run mlflow ui

# Error: Port already in use
# Solution: Use different port
pdm run mlflow ui --port 5001
```

#### 2. No Data Appearing
- Ensure you've run agent conversations after starting MLflow
- Check that `enable_mlflow=True` in your agent service configuration
- Verify the `mlruns/` directory exists and has data

#### 3. Import Errors
```bash
# Error: MLflow not available, disabling tracking
# Solution: Verify MLflow is installed
pdm list | grep mlflow

# If not installed, reinstall dependencies
pdm install
```

#### 4. Permission Issues
```bash
# Error: Permission denied writing to mlruns/
# Solution: Check directory permissions
chmod 755 mlruns/
```

### Debugging MLflow Integration

Enable debug logging to troubleshoot issues:

```python
# In src/services/conversation_runner.py
import logging
logging.getLogger("mlflow").setLevel(logging.DEBUG)
```

Check the logs for MLflow-related messages:
```bash
tail -f logs/backend.log | grep -i mlflow
```

## Best Practices

### 1. Regular Cleanup
- Periodically review and clean up old experiment runs
- Archive important runs before cleanup
- Consider setting up automated cleanup for old data

### 2. Meaningful Run Names
The system automatically generates descriptive run names:
```
Agent: Hello World Agent | Session: 550e8400 | 14:30:25
```

### 3. Artifact Management
- Conversation histories are automatically saved as artifacts
- Consider downloading important conversations for backup
- Use the artifact system to store additional debugging information

### 4. Monitoring
- Set up alerts for unusually long execution times
- Monitor agent performance trends over time
- Use comparison view to analyze different agent configurations

### 5. Integration with CI/CD
```bash
# In your CI pipeline, you might want to:
# 1. Run tests that generate MLflow data
pdm run pytest tests/test_agents.py

# 2. Export the results
pdm run mlflow runs export-batch --experiment-id 0 --output-file test_results.json

# 3. Archive or analyze the results
```

## Remote MLflow Server

For production deployments, consider using a remote MLflow server:

### Setup Remote Server
```bash
# On your MLflow server machine
pdm run mlflow server --host 0.0.0.0 --port 5000

# Configure Praxis to use remote server
export MLFLOW_TRACKING_URI=http://your-server:5000
```

### Authentication
```bash
# For MLflow with authentication
export MLFLOW_TRACKING_USERNAME=your-username
export MLFLOW_TRACKING_PASSWORD=your-password
```

## Extending MLflow Integration

### Adding Custom Metrics

To track additional metrics, modify `src/services/conversation_runner.py`:

```python
async def _execute_with_mlflow(self, agent, input_items, session_id, run_kwargs):
    with mlflow.start_run(run_name=run_name) as run:
        # Existing code...
        
        # Add custom metrics
        mlflow.log_metric("input_token_count", len(str(input_items)))
        mlflow.log_metric("tool_calls_count", count_tool_calls(response))
        
        # Add custom tags
        mlflow.set_tag("conversation_type", determine_conversation_type(input_items))
        
        return response
```

### Custom Artifacts

```python
# Save additional artifacts
custom_data = {"analysis": "detailed_analysis", "metadata": {...}}
with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
    json.dump(custom_data, f, indent=2)
    mlflow.log_artifact(f.name, "analysis")
    os.unlink(f.name)
```

## Conclusion

MLflow provides powerful tracking and monitoring capabilities for your Praxis agent conversations. By following this guide, you can:

- Monitor agent performance and behavior
- Track conversation histories and artifacts
- Compare different agents and configurations
- Debug issues and optimize performance
- Export and backup your experiment data

For additional MLflow features and advanced configurations, refer to the [official MLflow documentation](https://mlflow.org/docs/latest/index.html). 