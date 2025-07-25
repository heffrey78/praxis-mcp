# Slack Slash Commands for Praxis Pipeline & Plugin Execution

## 1. Goal

Enable users to execute any Praxis pipeline or plugin directly from Slack using slash commands. This includes passing required parameters and receiving feedback on the execution status and results, mirroring some of the capabilities of the CLI and API.

## 2. Proposed Slash Commands

We'll introduce a primary command for execution, and potentially helper commands for discovery:

*   **`/praxis-run`**: The main command for executing pipelines or plugins.
    *   **Syntax for Pipelines**: `/praxis-run pipeline <pipeline_id> [param1=value1] [param2=value2] ...`
    *   **Syntax for Plugins**: `/praxis-run plugin <plugin_id> [input_field1=value1] [input_field2=value2] ... [config='{"key":"value", "another_key":123}']`
        *   The `config` parameter for plugins will expect a valid JSON string.
    *   **Slack `usage_hint`**: `pipeline <id> [params...] | plugin <id> [inputs...] [config='{json_string}']`
    *   **Description**: "Execute a Praxis pipeline or plugin with specified parameters."

*   **(Optional - Stretch Goal for initial MVP) `/praxis-list`**: For discovering available pipelines and plugins.
    *   **Syntax**: `/praxis-list pipelines` or `/praxis-list plugins`
    *   **Slack `usage_hint`**: `pipelines | plugins`
    *   **Description**: "List available Praxis pipelines or plugins."

*   **(Optional - Stretch Goal for initial MVP) `/praxis-help`**: For getting details about a specific pipeline or plugin, including its parameters.
    *   **Syntax**: `/praxis-help pipeline <pipeline_id>` or `/praxis-help plugin <plugin_id>`
    *   **Slack `usage_hint`**: `pipeline <id> | plugin <id>`
    *   **Description**: "Get help and parameter information for a Praxis pipeline or plugin."

## 3. Slack Manifest (`slack-manifest.yml`) Updates

*   Add the definition for the `/praxis-run` command.
*   If `/praxis-list` and `/praxis-help` are pursued, their definitions will also be added.
*   The `request_url` for these new commands will point to a new, generalized webhook endpoint in the Praxis backend, for example: `https://YOUR_NGROK_ID.ngrok-free.app/api/webhooks/slack_praxis_command`.

## 4. Backend Implementation

### 4.1. New Webhook Endpoint & Adapter

*   **Endpoint**: Create a new FastAPI POST endpoint, e.g., `/api/webhooks/slack_praxis_command`.
*   **Adapter**: Develop a new `WebhookAdapter` (e.g., `PraxisCommandAdapter` in `src/api/webhooks/slack_command_adapter.py` or similar) to specifically handle these generic Praxis commands.

### 4.2. Command Parsing (within the new Adapter's `parse` method)

The `parse` method will be responsible for deconstructing the Slack command:
*   Receive raw slash command data: `command` (e.g., `/praxis-run`), `text` (the arguments string), `response_url`, `channel_id`, `user_id`.
*   **Dispatch Logic**:
    *   Based on `command` (e.g. if `/praxis-run`, `/praxis-list` are separate commands registered in manifest) or the first part of `text` if using a single versatile command.
*   **For `/praxis-run`**:
    *   The first argument in `text` must be either `pipeline` or `plugin`.
    *   The second argument will be the `pipeline_id` or `plugin_id`.
    *   Remaining arguments will be parsed as key-value pairs (e.g., `param_name=param_value`).
        *   A simple split by space, then by `=` for each pair.
        *   Values containing spaces will not be supported in MVP unless a robust quoting mechanism is implemented. Assume simple string values initially.
        *   The `config` parameter for plugins must be a single argument where the value is a valid JSON string (e.g., `config='{"model": "gpt-4o"}'`). The parser must correctly handle the single quotes around the JSON string.
*   **For `/praxis-list` (if implemented)**:
    *   The argument in `text` will be `pipelines` or `plugins`.
*   The `parse` method will output:
    *   `params_for_pipeline`: A dictionary containing:
        *   `action_type`: An enum or string like `RUN_PIPELINE`, `RUN_PLUGIN`, `LIST_PIPELINES`.
        *   `target_id`: The name/ID of the pipeline or plugin.
        *   `execution_params`: A dictionary of parameters for the pipeline/plugin.
        *   `raw_command_text`: Original command text for logging/debugging.
    *   `meta`: Standard metadata like `response_url`, `channel_id`, `thread_ts` (if applicable, though slash commands don't typically originate in threads).

### 4.3. Core Logic Invocation & Response (Adapter's `run_pipeline`/`respond` methods)

*   **Immediate Acknowledgement**:
    *   Upon receiving and successfully parsing the command, an immediate ephemeral message should be sent to Slack via the `response_url` (e.g., "Received: Running pipeline `<pipeline_id>`... Task ID will follow.").
*   **Asynchronous Execution Task**:
    *   **`RUN_PIPELINE`**:
        *   Use `DependencyContainer.get_pipeline_orchestrator()`.
        *   Call `orchestrator.run_pipeline_async(pipeline_id, execution_params)` which returns a `task_id`.
        *   The `respond` method will then poll `TaskManager` for completion and post results, similar to the current `SlackAdapter`.
    *   **`RUN_PLUGIN`**:
        *   This requires a mechanism to run a single plugin. The CLI's `PluginExecutorService.run_plugin` is a good model.
        *   **Preferred Approach**: Expose or create a method in `PluginExecutorService` (or a similar new service accessible via `DependencyContainer`) that:
            1.  Accepts `plugin_id`, input parameters dictionary, and config parameters dictionary.
            2.  Manages task creation and status updates via `TaskManager`.
            3.  Loads the plugin, validates/coerces parameters against plugin's models.
            4.  Executes the plugin's `run` method within a `PipelineContext`.
            5.  Returns a `task_id`.
        *   The `respond` method will then poll `TaskManager`.
    *   **`LIST_PIPELINES` / `LIST_PLUGINS` (if implemented)**:
        *   Use `DependencyContainer.get_pipeline_service().get_all_pipeline_info()` and `DependencyContainer.get_plugin_service().get_all_plugin_info()`.
        *   Format this information (name, description) as a text message.
        *   Post directly back to Slack via `response_url`. This is a synchronous response, no polling needed.
*   **Final Response (for `RUN_*` commands, after polling in `respond` method)**:
    *   **Pipelines**: Post "Pipeline `<pipeline_id>` (Task `<task_id>`) completed. Status: `<status>`." If a standard output artifact (e.g., `summary.txt`) is found, its content can be included.
    *   **Plugins**: Post "Plugin `<plugin_id>` (Task `<task_id>`) completed. Status: `<status>`."
        *   If the plugin's output model yields simple stringifiable data, include it.
        *   For complex outputs or files: "Outputs saved as artifacts for task `<task_id>`."
        *   Include any error messages if the task failed.

### 4.4. Parameter Handling and Coercion

*   **String from Slack**: All parameters initially arrive as strings.
*   **Pipelines**: The `PipelineOrchestrator` and Pydantic models defined in pipeline YAMLs handle coercion for pipeline params.
*   **Plugins**: The new plugin execution service will be responsible for coercing string inputs and config values to the types defined in the plugin's Pydantic `InputModel` and `ConfigModel`. Pydantic's `model_validate` can often handle this.
*   **Required Parameter Check**:
    *   Before execution, attempt to fetch pipeline/plugin info using `PipelineService` or `PluginService`.
    *   Check if all required parameters (those without defaults or explicitly marked) are present in the parsed command.
    *   If not, send an error message back to Slack listing missing parameters.

## 5. Error Handling (User Feedback to Slack)

*   **Invalid command syntax**: e.g., `/praxis-run foo bar`.
*   **Unknown action/sub-command**: e.g., `/praxis-run foobar <id>`.
*   **Target pipeline/plugin not found**.
*   **Missing required parameters**.
*   **Invalid parameter values** (e.g., "abc" for an integer field that can't be coerced).
*   **Invalid JSON for plugin `config`**.
*   **Execution errors** from the pipeline/plugin itself.
*   All error messages should be clear, user-friendly, and posted via `response_url`.

## 6. Documentation

*   Update `README.md`: Add a new section detailing the `/praxis-run` command, its syntax for pipelines and plugins, examples, and how to pass parameters (especially the JSON string for plugin config).
*   Update `docs/task-progress.md` upon completion of this feature.

## 7. Testing Strategy

*   **Manual End-to-End**:
    *   Thoroughly test from Slack:
        *   `/praxis-run pipeline <id>` with various pipelines, valid and invalid params.
        *   `/praxis-run plugin <id>` with various plugins, valid/invalid inputs, and different `config` JSON strings.
        *   All error conditions: unknown command, non-existent IDs, missing params, bad param values, malformed JSON.
*   **Unit Tests**:
    *   Focus on the command parsing logic in the new adapter.
    *   Test parameter extraction and parsing of the `config` JSON string.
*   **Integration Tests (if setup permits)**:
    *   Mock Slack requests to the new webhook endpoint to verify dispatch and basic execution flow initiation.

## 8. MVP Scope & Future Enhancements

*   **MVP Focus**:
    *   Implement `/praxis-run pipeline <id> [params...]`.
    *   Implement `/praxis-run plugin <id> [inputs...] [config='{json_string}']`.
    *   Robust parsing for the above, including the quoted JSON string for plugin config.
    *   String-based parameters with basic coercion by Pydantic.
    *   Clear error handling for command structure, ID existence, basic param validation, and execution failures.
    *   Immediate ephemeral acknowledgement and final status/simple output message via `response_url`, using existing polling logic where applicable.
*   **Future Enhancements (Post-MVP)**:
    *   Implement `/praxis-list` and `/praxis-help` commands.
    *   More sophisticated parameter parsing: handling quoted values with spaces, explicit type hints from user (e.g. `age:int=30`).
    *   Interactive parameter input using Slack Modals if required parameters are missing.
    *   Support for file inputs (this is complex for slash commands; might require different interaction model).
    *   Generating and returning direct links to important artifacts.
    *   Finer-grained access control. 