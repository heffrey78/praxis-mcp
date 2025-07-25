# Finally Feature Documentation

## Overview

The `finally` feature in Praxis pipelines ensures that certain steps always run after a pipeline completes, regardless of whether intermediate steps succeed or fail. This is similar to `try-catch-finally` blocks in programming languages and is essential for cleanup operations, resource management, and monitoring.

## Basic Usage

Add `finally: true` to any step in your pipeline YAML:

```yaml
id: example_pipeline
name: Example Pipeline with Finally
description: Demonstrates finally step usage

steps:
  - name: provision_infrastructure
    plugin: libi_infra_provisioner
    fail_on_error: true
    
  - name: deploy_model
    plugin: model_deployer  
    depends_on: [provision_infrastructure]
    fail_on_error: false

  - name: cleanup_resources
    plugin: resource_cleaner
    depends_on: [provision_infrastructure]
    fail_on_error: false
    finally: true  # This step will always run
```

## Key Behaviors

### 1. Guaranteed Execution
Finally steps **always execute** after normal pipeline phases complete, regardless of failures:

- ✅ Normal steps succeed → Finally steps run
- ✅ Normal steps fail → Finally steps still run
- ✅ Pipeline crashed → Finally steps still run

### 2. Non-Critical by Design
Finally steps are automatically non-critical:

```yaml
# ❌ This will cause a validation error
- name: cleanup_step
  plugin: resource_cleaner
  finally: true
  fail_on_error: true  # ERROR: Finally steps cannot be critical

# ✅ Correct usage
- name: cleanup_step
  plugin: resource_cleaner
  finally: true
  fail_on_error: false  # Must be false (or omitted)
```

### 3. Dependency Management
Finally steps respect dependencies but use different readiness rules:

**Normal Steps:** Must wait for dependencies to complete successfully
**Finally Steps:** Wait for dependencies to reach any terminal state (completed, failed, or skipped)

```yaml
steps:
  - name: setup
    plugin: setup_plugin
    
  - name: main_work
    plugin: work_plugin
    depends_on: [setup]
    
  - name: cleanup
    plugin: cleanup_plugin
    depends_on: [setup]  # Runs when setup reaches terminal state
    finally: true
```

### 4. Execution Phases
Pipelines execute in two distinct phases:

1. **Normal Phase:** All non-finally steps execute
2. **Finally Phase:** Finally steps execute after normal phase completes

## Advanced Examples

### Multiple Finally Steps
Finally steps can depend on each other and run in parallel:

```yaml
steps:
  - name: main_process
    plugin: process_plugin
    
  - name: save_logs
    plugin: log_saver
    depends_on: [main_process]
    finally: true
    
  - name: cleanup_temp_files
    plugin: file_cleaner
    depends_on: [main_process]
    finally: true
    
  - name: send_notification
    plugin: notifier
    depends_on: [save_logs, cleanup_temp_files]  # Depends on other finally steps
    finally: true
```

### Finally with Conditional Dependencies
Finally steps can use conditional dependencies:

```yaml
steps:
  - name: conditional_step
    plugin: condition_if
    config:
      condition: "some_condition"
    
  - name: cleanup_on_success
    plugin: success_cleanup
    depends_on: [conditional_step.true]  # Only if condition was true
    finally: true
    
  - name: cleanup_on_failure
    plugin: failure_cleanup
    depends_on: [conditional_step.false]  # Only if condition was false
    finally: true
```

### Finally with Loops
Loop steps can be marked as finally:

```yaml
steps:
  - name: main_work
    plugin: work_plugin
    
  - name: cleanup_multiple_resources
    plugin: resource_cleaner
    depends_on: [main_work]
    finally: true
    loop_config:
      count: 3
      delay: 1000  # 1 second between iterations
```

## Use Cases

### 1. Infrastructure Cleanup
```yaml
steps:
  - name: provision_vm
    plugin: vm_provisioner
    
  - name: deploy_app
    plugin: app_deployer
    depends_on: [provision_vm]
    
  - name: cleanup_vm
    plugin: vm_destroyer
    depends_on: [provision_vm]
    finally: true  # Always clean up VM
```

### 2. Resource Management
```yaml
steps:
  - name: acquire_lock
    plugin: lock_manager
    
  - name: process_data
    plugin: data_processor
    depends_on: [acquire_lock]
    
  - name: release_lock
    plugin: lock_releaser
    depends_on: [acquire_lock]
    finally: true  # Always release lock
```

### 3. Monitoring and Notifications
```yaml
steps:
  - name: training_job
    plugin: ml_trainer
    
  - name: save_metrics
    plugin: metrics_saver
    depends_on: [training_job]
    finally: true  # Always save metrics
    
  - name: notify_completion
    plugin: slack_notifier
    depends_on: [training_job]
    finally: true  # Always notify
```

## Best Practices

### 1. Keep Finally Steps Simple
Finally steps should perform simple, reliable operations:

```yaml
# ✅ Good: Simple cleanup
- name: cleanup
  plugin: file_cleaner
  finally: true

# ❌ Avoid: Complex operations that might fail
- name: complex_analysis
  plugin: heavy_computation
  finally: true
```

### 2. Use Explicit Dependencies
Be explicit about what finally steps depend on:

```yaml
# ✅ Clear dependencies
- name: cleanup_db
  plugin: db_cleaner
  depends_on: [setup_db]  # Only clean up if DB was set up
  finally: true

# ❌ Unclear: No dependencies might cause issues
- name: cleanup_db
  plugin: db_cleaner
  finally: true
```

### 3. Plan for Failure Scenarios
Consider what should happen when finally steps fail:

```yaml
# Finally steps won't crash the pipeline, but log failures
- name: best_effort_cleanup
  plugin: cleanup_plugin
  finally: true
  # Failure is logged but doesn't affect pipeline status
```

## Error Handling

### Finally Step Failures
- Finally step failures are logged but don't affect overall pipeline status
- Other finally steps continue to execute
- Pipeline reports success if normal phases succeeded

### Validation Errors
Common validation errors and fixes:

```yaml
# ❌ Error: Finally step cannot be critical
- name: cleanup
  finally: true
  fail_on_error: true
  
# ✅ Fix: Remove fail_on_error or set to false
- name: cleanup
  finally: true
  fail_on_error: false
```

## Testing Finally Steps

Test finally behavior in different scenarios:

```python
# Test normal success with finally
def test_finally_after_success():
    # Setup pipeline with finally steps
    # Execute pipeline
    # Assert finally steps ran after normal steps

# Test finally after failure
def test_finally_after_failure():
    # Setup pipeline with failing step and finally steps
    # Execute pipeline  
    # Assert finally steps ran despite failure
```

## Monitoring and Debugging

### Pipeline Logs
Finally execution appears in logs:

```
[INFO] Starting normal execution phase
[INFO] Step 'main_work' completed
[INFO] Normal execution phase complete
[INFO] Starting finally execution phase with 2 finally steps
[INFO] Finally step 'cleanup' completed
[INFO] Finally execution phase complete
```

### CLI Progress
Finally steps show up in CLI progress with clear indication:

```
✓ main_work (completed)
✓ cleanup (finally - completed)
✓ notify (finally - completed)
```

This documentation should help users understand how to effectively use the finally feature in their Praxis pipelines.