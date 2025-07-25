# Agent Session Flow Examples

## Complete Flow Diagrams

### 1. Direct CLI Agent Execution

```
User ──► praxis agent run hello-world
           │
           ▼
      AgentService
           │
           ├─► SessionManager.create_session()  [Optional - for new unified approach]
           │      │
           │      └─► Task created: "agent:hello-world"
           │
           ├─► Load agent config from agent_configs/hello-world/
           │
           ├─► Initialize MCP servers
           │
           └─► Interactive conversation loop
                 │
                 ├─► User: "Hello"
                 ├─► Agent: "Hi! How can I help?"
                 ├─► User: "Explain Python lists"
                 ├─► Agent: "Python lists are..."
                 └─► User: exit
```

### 2. Plugin Execution Flow

```
User ──► praxis plugin run agent --config '{"agent_name": "hello-world", "mode": "interactive"}'
           │
           ▼
      PluginExecutor
           │
           ├─► Load AgentPlugin
           │
           ├─► AgentPlugin.run(context)
           │      │
           │      ├─► SessionManager.create_session()
           │      │      └─► session_id: "abc123"
           │      │
           │      ├─► Check mode
           │      │
           │      └─► if interactive:
           │             └─► raise PluginSuspendedException
           │                    └─► Message: "Agent requires input"
           │                    └─► State: {"session_id": "abc123"}
           │
           ▼
      Plugin Suspended - User must resume
           │
           ▼
User ──► praxis agent resume abc123
           │
           ▼
      AgentExecutor.execute_interactive(session_id="abc123")
           │
           └─► Continue conversation...
```

### 3. Pipeline Execution Flow

```
Pipeline: data-collection.yaml
steps:
  - name: collect_user_data
    plugin: agent
    config:
      agent_name: data-collector
      mode: interactive

Execution:

PipelineExecutor ──► DAGExecutor
                        │
                        ├─► Step: collect_user_data
                        │     │
                        │     ├─► AgentPlugin.run()
                        │     │     │
                        │     │     ├─► SessionManager.create_session()
                        │     │     ├─► Inject resume_pipeline tool
                        │     │     └─► raise PluginSuspendedException
                        │     │
                        │     └─► Pipeline SUSPENDED
                        │
                        ├─► Save checkpoint with session_id
                        │
                        └─► Wait for resume...

Two Resume Paths:

Path 1: Agent-Driven Resume
Agent ──► calls resume_pipeline(collected_data={...})
           │
           └─► PipelineResumeException
                  │
                  └─► Pipeline continues with data

Path 2: User-Driven Resume  
User ──► praxis pipeline resume <task_id> --data '{"message": "here's my data"}'
           │
           └─► DAGExecutor.resume()
                  │
                  └─► AgentPlugin continues conversation
```

### 4. API/GraphQL Flow

```
Client Application Flow:

1. Create Session:
   POST /agent-sessions/create
   {"agent_name": "assistant"}
   ◄── {"session_id": "xyz789", "task_id": "task-456"}

2. Send Messages:
   POST /agent-sessions/xyz789/messages
   {"message": "Help me with Python", "stream": true}
   ◄── SSE Stream:
       data: {"type": "message", "data": {"content": "I'll help..."}}
       data: {"type": "message", "data": {"content": "Python is..."}}
       data: {"type": "waiting_for_input", "data": {}}

3. Continue Conversation:
   POST /agent-sessions/xyz789/messages
   {"message": "Show me an example"}
   ◄── SSE Stream continues...

4. Suspend (if needed):
   POST /agent-sessions/xyz789/suspend
   ◄── {"checkpoint_id": "chk-123", "message": "Suspended"}

5. Resume Later:
   POST /agent-sessions/xyz789/resume
   ◄── {"session_id": "xyz789", "state": "active"}
```

## Real-World Scenarios

### Scenario 1: Customer Support Pipeline

```yaml
name: customer-support-workflow
steps:
  - name: initial_triage
    plugin: agent
    config:
      agent_name: support-bot
      mode: interactive
      system_prompt_postfix: |
        Collect the customer's issue details.
        When you have enough information, call resume_pipeline with:
        - issue_type: (technical|billing|general)
        - severity: (low|medium|high)
        - description: brief summary
    
  - name: route_to_specialist
    plugin: router
    inputs:
      issue_type: "{{initial_triage.collected_data.issue_type}}"
      severity: "{{initial_triage.collected_data.severity}}"
    
  - name: specialist_handling
    plugin: agent
    config:
      agent_name: "{{route_to_specialist.specialist_agent}}"
      mode: interactive
```

**Flow**:
1. Customer starts chat → Session created
2. Bot collects information interactively
3. Bot calls `resume_pipeline` with categorized data
4. Pipeline routes to appropriate specialist
5. Specialist agent continues in same session

### Scenario 2: Multi-Modal Research Assistant

```python
# Start with CLI
$ praxis agent run research-assistant
> Session: res-001
> You: Research quantum computing applications
> Agent: I'll help you research quantum computing. Let me search...
> [User needs to leave]

# Continue on mobile API
curl -X POST http://api/agent-sessions/res-001/messages \
  -d '{"message": "Focus on healthcare applications"}'

# Finish on web UI (GraphQL)
mutation {
  sendMessageToSession(
    sessionId: "res-001"
    message: "Compile findings into a report"
  ) {
    content
  }
}
```

### Scenario 3: Data Collection with Validation

```yaml
name: user-onboarding
steps:
  - name: collect_profile
    plugin: agent
    config:
      agent_name: onboarding-assistant
      mode: interactive
      mcp_servers:
        validator:
          command: "python"
          args: ["-m", "validation_server"]
    
  - name: validate_data
    plugin: data_validator
    inputs:
      data: "{{collect_profile.collected_data}}"
    
  - name: corrections_if_needed
    plugin: conditional
    condition: "{{validate_data.has_errors}}"
    if_true:
      plugin: agent
      config:
        agent_name: onboarding-assistant  
        mode: interactive
        session_id: "{{collect_profile.session_id}}"  # Resume same session!
        initial_message: |
          There were some issues with the data:
          {{validate_data.errors}}
          Let's correct them together.
```

## State Management

### Session State Storage

```json
// artifacts/agent_sessions/abc123.json
{
  "session_id": "abc123",
  "task_id": "task-789",
  "agent_name": "hello-world",
  "interface": "plugin",
  "state": "suspended",
  "created_at": "2024-01-20T10:00:00Z",
  "updated_at": "2024-01-20T10:05:00Z",
  "checkpoint_id": "chk-456",
  "metadata": {
    "pipeline_name": "data-collection",
    "step_name": "collect_info",
    "suspend_reason": "awaiting_user_input"
  }
}
```

### Checkpoint State

```json
// artifacts/agent_checkpoints/chk-456.json
{
  "checkpoint_id": "chk-456",
  "session_id": "abc123",
  "created_at": "2024-01-20T10:05:00Z",
  "conversation_state": {
    "history": [
      {"role": "user", "content": "Hello"},
      {"role": "assistant", "content": "Hi! How can I help?"}
    ],
    "turn_count": 2,
    "agent_config": {
      "name": "hello-world",
      "model": "gpt-4",
      "tools": ["resume_pipeline"]
    }
  }
}
```

## Error Handling Examples

### 1. Session Not Found

```python
# CLI
$ praxis agent resume invalid-session
[red]Error: Session invalid-session not found[/red]

# API
POST /agent-sessions/invalid-session/messages
◄── 404 {"detail": "Session invalid-session not found"}

# Plugin
try:
    result = await executor.resume_pipeline_session("invalid")
except ValueError as e:
    # Handle gracefully
```

### 2. Agent Configuration Error

```yaml
- name: broken_agent
  plugin: agent
  config:
    agent_config_file: "missing-file.yaml"  # Error: file not found
    
# Execution fails with clear error:
# "Agent config file not found: missing-file.yaml"
```

### 3. Maximum Turns Exceeded

```python
# Config
config:
  max_turns: 5

# After 5 turns:
AgentOutput(
  response="Last response here",
  metadata={"max_turns_reached": True}
)
```

## Performance Considerations

### 1. Session Lookup Optimization

```python
# Current: O(n) file scan
# Future: Add index file or use Redis

# artifacts/agent_sessions/.index.json
{
  "by_task": {
    "task-123": "session-abc",
    "task-456": "session-xyz"
  },
  "by_agent": {
    "hello-world": ["session-abc", "session-def"],
    "assistant": ["session-xyz"]
  }
}
```

### 2. History Truncation

```python
# For long conversations
if len(history) > 100:
    # Keep system messages and last N turns
    truncated = (
        [msg for msg in history if msg.role == "system"] +
        history[-50:]  # Keep last 50 messages
    )
```

### 3. Streaming Optimization

```python
# Use async generators for memory efficiency
async def stream_response(session_id: str):
    async for event in executor.execute_interactive(session_id):
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0)  # Yield control
```

## Testing Strategies

### 1. Unit Tests

```python
async def test_session_creation():
    manager = AgentSessionManager(test_dir, mock_task_manager)
    session = await manager.create_session("test-agent", "test")
    assert session.state == SessionState.CREATED
    assert session.agent_name == "test-agent"
```

### 2. Integration Tests

```python
async def test_plugin_suspension_resume():
    # Execute plugin
    with pytest.raises(PluginSuspendedException) as exc:
        await plugin.run(context)
    
    # Verify session created
    session_id = exc.value.state["session_id"]
    assert session_id is not None
    
    # Resume and verify
    result = await executor.resume_pipeline_session(session_id)
    assert result["session_id"] == session_id
```

### 3. End-to-End Tests

```python
async def test_full_pipeline_with_agent():
    # Run pipeline with agent step
    result = await pipeline_executor.execute(
        "test-pipeline",
        params={"question": "test"}
    )
    
    # Verify suspension
    assert result.status == "suspended"
    
    # Resume with data
    final = await pipeline_executor.resume(
        result.task_id,
        {"collect_info": {"message": "answer"}}
    )
    
    assert final.status == "completed"
```

## Migration Path

### Phase 1: Add Session Tracking (Current)
- ✅ SessionManager implementation
- ✅ Basic CLI commands
- ✅ API endpoints

### Phase 2: Update Agent Plugin
- [ ] Use SessionManager in plugin
- [ ] Update suspension/resume logic
- [ ] Test with existing pipelines

### Phase 3: Update Direct Agent Execution
- [ ] Make `praxis agent` session-aware
- [ ] Add resume capability
- [ ] Maintain backward compatibility

### Phase 4: Production Features
- [ ] Add authentication
- [ ] Implement rate limiting
- [ ] Add monitoring/metrics
- [ ] Scale session storage

This architecture provides a robust foundation for interactive agent experiences across all execution modalities while maintaining simplicity and consistency.