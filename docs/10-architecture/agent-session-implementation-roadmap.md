# Agent Session Implementation Roadmap

## Summary

This document outlines the implementation plan for the unified interactive agent session architecture that addresses the requirements:

1. **Task ID Integration**: Every agent session is linked to a task ID for full traceability
2. **History Persistence**: Conversation history is stored and can be resumed
3. **DRY Architecture**: Single implementation used across CLI, API, and GraphQL
4. **Developer Experience**: Consistent, simple APIs across all interfaces

## Architecture Overview

### Core Components Created

1. **AgentSessionManager** (`src/core/agent_session.py`)
   - Centralized session lifecycle management
   - File-based storage (extensible to other backends)
   - Session states: CREATED → ACTIVE → SUSPENDED/COMPLETED/FAILED
   - Checkpoint support for suspend/resume

2. **AgentPluginExecutor** (`src/core/agent_plugin_executor.py`)
   - Unified execution logic for all interfaces
   - Handles interactive and single-turn modes
   - Event-based streaming for real-time updates
   - Integrates with existing AgentService

3. **CLI Integration** (`src/cli/agent_session.py`)
   - `praxis agent list-sessions` - List all sessions
   - `praxis agent show-session <id>` - Display session details
   - `praxis agent resume <id>` - Resume suspended session
   - `praxis agent suspend <id>` - Suspend active session
   - `praxis agent cleanup` - Clean old sessions

4. **API Endpoints** (`src/api/agent_sessions.py`)
   - POST `/agent-sessions/create` - Create new session
   - GET `/agent-sessions/{id}` - Get session details
   - POST `/agent-sessions/list` - List sessions with filters
   - POST `/agent-sessions/{id}/messages` - Send message (streaming support)
   - POST `/agent-sessions/{id}/suspend` - Suspend session
   - POST `/agent-sessions/{id}/resume` - Resume session

5. **GraphQL Schema** (`src/graphql/schemas/agent_session.graphql`)
   - Queries: agentSession, agentSessions
   - Mutations: createAgentSession, sendMessageToSession, etc.
   - Subscriptions: agentSessionEvents for real-time updates

## Implementation Phases

### Phase 1: Core Infrastructure (Current)
✅ AgentSessionManager implementation
✅ Session storage and retrieval
✅ Task ID integration
✅ Basic CLI commands
✅ API endpoints
✅ GraphQL schema and resolvers

### Phase 2: Plugin Integration (Next)
- [ ] Update agent plugin to use AgentSessionManager
- [ ] Ensure plugin works in both pipeline and standalone modes
- [ ] Add session-aware checkpointing to ConversationRunner
- [ ] Test suspend/resume in pipeline context

### Phase 3: Service Integration
- [ ] Update AgentService to be session-aware
- [ ] Integrate with ConversationRunner for history management
- [ ] Add session context to MCP tool calls
- [ ] Implement proper conversation state serialization

### Phase 4: Interactive Features
- [ ] Real-time streaming for all interfaces
- [ ] WebSocket support for GraphQL subscriptions
- [ ] Session handoff between interfaces
- [ ] Multi-turn conversation management

### Phase 5: Production Readiness
- [ ] Add authentication/authorization
- [ ] Implement session expiration
- [ ] Add Redis backend for scalability
- [ ] Performance optimization for large histories
- [ ] Comprehensive test suite

## Key Integration Points

### 1. Agent Plugin Updates

```python
# Current plugin needs to:
1. Check for existing session in context
2. Create session if not exists
3. Use AgentPluginExecutor for execution
4. Handle both pipeline and CLI execution modes
```

### 2. CLI Plugin Command

```python
# Update src/cli/plugin.py run_plugin command:
1. Detect agent plugin
2. Use AgentPluginExecutor for interactive mode
3. Handle streaming responses
4. Support session resumption
```

### 3. Pipeline Context

```python
# Add to PipelineContext:
- _agent_session_id: Optional[str]
- _agent_executor: Optional[AgentPluginExecutor]
```

## Migration Strategy

### Backward Compatibility
1. Existing agent commands continue to work
2. Sessions are optional - direct execution still supported
3. Gradual rollout by interface

### Data Migration
1. Tool to import existing conversation histories
2. Convert file-based history to session format
3. Link historical tasks to sessions

## Example Usage

### CLI Workflow
```bash
# Start new session
$ praxis agent run hello-world
> Session created: abc123...
> Agent: Hello! How can I help you today?

# User leaves and comes back later
$ praxis agent list-sessions
$ praxis agent resume abc123

# Continue conversation
> You: Let's continue our discussion about Python
> Agent: Of course! Where did we leave off...
```

### API Workflow
```python
# Create session
response = requests.post("/agent-sessions/create", json={
    "agent_name": "hello-world",
    "initial_message": "Help me with coding"
})
session_id = response.json()["session_id"]

# Send messages
response = requests.post(f"/agent-sessions/{session_id}/messages", json={
    "message": "How do I handle errors?",
    "stream": True
})

# Handle streaming response
for line in response.iter_lines():
    event = json.loads(line.replace("data: ", ""))
    print(event["data"]["content"])
```

### GraphQL Workflow
```graphql
# Create session
mutation {
  createAgentSession(
    agentName: "hello-world"
    initialMessage: "Hello"
  ) {
    sessionId
    taskId
    state
  }
}

# Subscribe to events
subscription {
  agentSessionEvents(sessionId: "abc123") {
    type
    data
    timestamp
  }
}
```

## Benefits Achieved

1. **Unified Experience**: Same session across all interfaces
2. **Full Traceability**: Every interaction linked to task IDs
3. **Seamless Handoff**: Start in CLI, continue in API
4. **Robust Recovery**: Suspend/resume at any point
5. **Developer Friendly**: Simple, consistent APIs

## Next Steps

1. Complete Phase 2 plugin integration
2. Add comprehensive tests
3. Create user documentation
4. Deploy to staging for testing
5. Gather feedback and iterate

## Technical Debt to Address

1. Current file-based storage won't scale
2. Need proper session garbage collection
3. History truncation for long conversations
4. Better error handling and recovery
5. Performance optimization needed

## Success Metrics

- Session creation latency < 100ms
- Resume latency < 200ms
- Support 1000+ concurrent sessions
- 99.9% session recovery success rate
- < 1% session data loss