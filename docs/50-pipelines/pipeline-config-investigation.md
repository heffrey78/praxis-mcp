# Pipeline Config Processing Investigation

## Date: 2025-01-27

### Summary
Investigated how pipeline step configs are processed from YAML files to plugin execution. The key finding is that there is NO template processing happening on config values - they are stored and passed through as raw dictionaries.

### Investigation Details

#### 1. YAML Loading
- **Location**: `src/core/dependency_container.py`, line 226
- **Method**: Uses `yaml.safe_load()` to parse pipeline YAML files
- **Process**: Reads all `*.yaml` files from `src/pipelines/` directory

#### 2. Step Config Parsing
- **Location**: `src/core/dependency_container.py`, method `_parse_step_configs()`
- **Key Line**: Line 377: `config=step.get("config", {}),`
- **Behavior**: 
  - Extracts the `config` section from each step definition
  - Stores it as-is in the `StepConfig.config` field as a dictionary
  - No template processing occurs during loading

#### 3. Config Storage
- **Data Structure**: `StepConfig` dataclass in `src/core/step_config.py`
- **Field**: `config: Dict[str, Any] = field(default_factory=dict)` (line 159)
- **Type**: Plain Python dictionary with no special processing

#### 4. Config Usage in Execution
Found limited usage of step configs:
- **Loop Execution**: `src/core/loop_execution_strategy.py` (line 64)
  - Copies config when creating synthetic loop steps
  - `config=step.config.copy() if step.config else {}`
- **Plugin Execution**: Config is available but not automatically passed to plugins
- **Access Pattern**: Plugins would need to explicitly request step config through execution context

#### 5. Template Processing Status
**Finding**: There is NO template processing infrastructure:
- No Jinja2 or similar template engine imports found
- No `{{variable}}` pattern processing
- No variable substitution mechanisms
- Config values are preserved exactly as written in YAML

### Code References

```python
# src/core/dependency_container.py - Line 377
step_config = StepConfig(
    name=step["name"],
    plugin=step["plugin"],
    depends_on=step.get("depends_on", []),
    fail_on_error=step.get("fail_on_error", True),
    loop_config=loop_config,
    config=step.get("config", {}),  # <-- Config stored as-is
    connections=step.get("connections"),
)
```

```python
# src/core/step_config.py - Line 159
@dataclass
class StepConfig:
    name: str
    plugin: str
    # ... other fields ...
    config: Dict[str, Any] = field(default_factory=dict)  # <-- Plain dict storage
```

### Implications
1. Pipeline authors cannot use template variables in config sections
2. All config values must be static/literal in the YAML
3. Dynamic values must be passed through pipeline parameters or connections
4. Plugins receive config values exactly as written in YAML files