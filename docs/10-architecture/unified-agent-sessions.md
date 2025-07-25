# Unified Interactive Agent Sessions Architecture

## Overview

This document outlines the architecture for implementing a unified interactive agent experience across CLI, API, and GraphQL interfaces with proper session management, suspend/resume capabilities, and task tracking.

## Core Concepts

### 1. Agent Session
An agent session represents a conversation between a user and an agent. Sessions:
- Have a unique ID (UUID)
- Are linked to a task ID for tracking
- Can be suspended and resumed
- Maintain conversation history
- Track metadata (interface, creation time, last activity)

### 2. Session States
```
┌─────────┐      ┌─────────┐      ┌───────────┐      ┌───────────┐
│ CREATED │ ───► │ ACTIVE  │ ───► │ SUSPENDED │ ───► │ COMPLETED │
└─────────┘      └─────────┘      └───────────┘      └───────────┘
                       │                                     ▲
                       └─────────────────────────────────────┘
```

### 3. Session Storage
Sessions are stored with:
- **Metadata**: Session info, state, timestamps
- **History**: Full conversation history
- **Checkpoint**: Serialized agent state for resumption
- **Artifacts**: References to generated artifacts

## Architecture Components

### 1. Core Session Manager

```python
# src/core/agent_session.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime

class SessionState(Enum):
    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentSession:
    """Represents an agent conversation session."""
    session_id: str
    task_id: str
    agent_name: str
    interface: str  # cli, api, graphql, webhook
    state: SessionState
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    checkpoint_id: Optional[str] = None
    parent_session_id: Optional[str] = None  # For forked sessions

class AgentSessionManager:
    """Centralized session management for all agent interfaces."""
    
    def __init__(self, storage_backend: SessionStorageBackend):
        self.storage = storage_backend
        self.task_manager = None  # Injected
        
    async def create_session(
        self,
        agent_name: str,
        interface: str,
        initial_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentSession:
        """Create a new agent session with associated task."""
        # Create task for tracking
        task_id = await self.task_manager.create_task(
            pipeline_name=f"agent:{agent_name}",
            params={"interface": interface},
            source=interface
        )
        
        # Create session
        session = AgentSession(
            session_id=str(uuid.uuid4()),
            task_id=task_id,
            agent_name=agent_name,
            interface=interface,
            state=SessionState.CREATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        await self.storage.save_session(session)
        await self.task_manager.update_task_status(task_id, "running")
        
        return session
        
    async def suspend_session(
        self,
        session_id: str,
        conversation_state: Dict[str, Any],
        reason: str = "user_requested"
    ) -> str:
        """Suspend a session with checkpoint."""
        session = await self.storage.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        # Create checkpoint
        checkpoint_id = await self._create_checkpoint(session, conversation_state)
        
        # Update session
        session.state = SessionState.SUSPENDED
        session.checkpoint_id = checkpoint_id
        session.updated_at = datetime.utcnow()
        session.metadata["suspend_reason"] = reason
        
        await self.storage.save_session(session)
        await self.task_manager.update_task_status(session.task_id, "suspended")
        
        return checkpoint_id
        
    async def resume_session(
        self,
        session_id: str,
        interface: Optional[str] = None
    ) -> Tuple[AgentSession, Dict[str, Any]]:
        """Resume a suspended session."""
        session = await self.storage.get_session(session_id)
        if not session or session.state != SessionState.SUSPENDED:
            raise ValueError(f"Session {session_id} not found or not suspended")
            
        # Load checkpoint
        conversation_state = await self._load_checkpoint(session.checkpoint_id)
        
        # Update session
        session.state = SessionState.ACTIVE
        session.updated_at = datetime.utcnow()
        if interface:
            session.interface = interface  # Allow interface switching
            
        await self.storage.save_session(session)
        await self.task_manager.update_task_status(session.task_id, "running")
        
        return session, conversation_state
```

### 2. Storage Backend

```python
# src/core/agent_session_storage.py
from abc import ABC, abstractmethod
import json
from pathlib import Path

class SessionStorageBackend(ABC):
    """Abstract base for session storage implementations."""
    
    @abstractmethod
    async def save_session(self, session: AgentSession) -> None:
        pass
        
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        pass
        
    @abstractmethod
    async def list_sessions(
        self,
        state: Optional[SessionState] = None,
        agent_name: Optional[str] = None,
        interface: Optional[str] = None
    ) -> List[AgentSession]:
        pass

class FileSessionStorage(SessionStorageBackend):
    """File-based session storage implementation."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.sessions_dir = base_dir / "agent_sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
    async def save_session(self, session: AgentSession) -> None:
        session_file = self.sessions_dir / f"{session.session_id}.json"
        session_data = {
            "session_id": session.session_id,
            "task_id": session.task_id,
            "agent_name": session.agent_name,
            "interface": session.interface,
            "state": session.state.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
            "checkpoint_id": session.checkpoint_id,
            "parent_session_id": session.parent_session_id
        }
        
        async with aiofiles.open(session_file, 'w') as f:
            await f.write(json.dumps(session_data, indent=2))
```

### 3. Unified Plugin Executor

```python
# src/core/agent_plugin_executor.py
class AgentPluginExecutor:
    """Handles agent plugin execution with session management."""
    
    def __init__(
        self,
        session_manager: AgentSessionManager,
        agent_service: AgentService,
        conversation_runner: ConversationRunner
    ):
        self.session_manager = session_manager
        self.agent_service = agent_service
        self.conversation_runner = conversation_runner
        
    async def execute_interactive(
        self,
        agent_name: str,
        interface: str,
        session_id: Optional[str] = None,
        initial_message: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """Execute agent in interactive mode with proper session tracking."""
        
        # Create or resume session
        if session_id:
            session, state = await self.session_manager.resume_session(
                session_id, interface
            )
            history = state.get("history", [])
        else:
            session = await self.session_manager.create_session(
                agent_name, interface
            )
            history = []
            
        # Configure agent with session context
        agent_config = await self._get_agent_config(agent_name)
        agent_config["_session_id"] = session.session_id
        agent_config["_task_id"] = session.task_id
        
        # Run conversation
        try:
            async for event in self._run_conversation(
                session, agent_config, history, initial_message
            ):
                yield event
                
            # Complete session
            await self.session_manager.complete_session(session.session_id)
            
        except PipelineSuspendedException as e:
            # Suspend session
            checkpoint_data = {
                "history": self.conversation_runner.get_history(),
                "agent_state": e.state,
                "suspension_data": e.data
            }
            await self.session_manager.suspend_session(
                session.session_id,
                checkpoint_data,
                reason="pipeline_suspended"
            )
            yield AgentEvent(
                type="suspended",
                data={"session_id": session.session_id, "reason": str(e)}
            )
```

### 4. CLI Integration

```python
# src/cli/agent_session.py
@app.command("list-sessions")
async def list_sessions(
    state: Optional[str] = typer.Option(None, help="Filter by state"),
    agent: Optional[str] = typer.Option(None, help="Filter by agent name")
):
    """List all agent sessions."""
    session_manager = get_session_manager()
    sessions = await session_manager.list_sessions(
        state=SessionState(state) if state else None,
        agent_name=agent
    )
    
    table = Table(title="Agent Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Interface", style="blue")
    table.add_column("Created", style="magenta")
    
    for session in sessions:
        table.add_row(
            session.session_id[:8] + "...",
            session.agent_name,
            session.state.value,
            session.interface,
            session.created_at.strftime("%Y-%m-%d %H:%M")
        )
    console.print(table)

@app.command("resume")
async def resume_session(
    session_id: str = typer.Argument(..., help="Session ID to resume")
):
    """Resume a suspended agent session."""
    executor = get_agent_executor()
    
    console.print(f"Resuming session {session_id}...")
    
    async for event in executor.execute_interactive(
        agent_name=None,  # Will be loaded from session
        interface="cli",
        session_id=session_id
    ):
        if event.type == "message":
            console.print(f"Agent: {event.data['content']}")
        elif event.type == "suspended":
            console.print(f"Session suspended: {event.data['reason']}")
        elif event.type == "completed":
            console.print("Session completed")
```

### 5. API Integration

```python
# src/api/agent_sessions.py
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/agent-sessions", tags=["agent-sessions"])

@router.post("/create")
async def create_session(
    agent_name: str,
    initial_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> SessionResponse:
    """Create a new agent session."""
    session_manager = get_session_manager()
    session = await session_manager.create_session(
        agent_name=agent_name,
        interface="api",
        initial_message=initial_message,
        metadata=metadata
    )
    
    return SessionResponse(
        session_id=session.session_id,
        task_id=session.task_id,
        state=session.state.value,
        created_at=session.created_at
    )

@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    message: str,
    stream: bool = False
) -> Union[MessageResponse, StreamingResponse]:
    """Send a message to an active session."""
    executor = get_agent_executor()
    
    if stream:
        return StreamingResponse(
            executor.stream_response(session_id, message),
            media_type="text/event-stream"
        )
    else:
        response = await executor.send_message(session_id, message)
        return MessageResponse(
            content=response.content,
            session_id=session_id,
            turn_id=response.turn_id
        )

@router.post("/{session_id}/suspend")
async def suspend_session(
    session_id: str,
    reason: Optional[str] = None
) -> SuspendResponse:
    """Suspend an active session."""
    session_manager = get_session_manager()
    checkpoint_id = await session_manager.suspend_session(
        session_id,
        conversation_state={},  # Will be populated by executor
        reason=reason or "api_requested"
    )
    
    return SuspendResponse(
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        message="Session suspended successfully"
    )

@router.post("/{session_id}/resume")
async def resume_session(session_id: str) -> SessionResponse:
    """Resume a suspended session."""
    session, _ = await get_session_manager().resume_session(
        session_id,
        interface="api"
    )
    
    return SessionResponse(
        session_id=session.session_id,
        task_id=session.task_id,
        state=session.state.value,
        updated_at=session.updated_at
    )
```

### 6. GraphQL Integration

```graphql
# src/graphql/schema/agent_session.graphql
type AgentSession {
    sessionId: ID!
    taskId: ID!
    agentName: String!
    interface: String!
    state: SessionState!
    createdAt: DateTime!
    updatedAt: DateTime!
    metadata: JSON
    checkpointId: String
    history: [ConversationTurn!]
    artifacts: [Artifact!]
}

enum SessionState {
    CREATED
    ACTIVE
    SUSPENDED
    COMPLETED
    FAILED
}

type Query {
    agentSession(sessionId: ID!): AgentSession
    agentSessions(
        state: SessionState
        agentName: String
        interface: String
        limit: Int = 20
    ): [AgentSession!]!
}

type Mutation {
    createAgentSession(
        agentName: String!
        initialMessage: String
        metadata: JSON
    ): AgentSession!
    
    sendMessage(
        sessionId: ID!
        message: String!
    ): ConversationTurn!
    
    suspendSession(
        sessionId: ID!
        reason: String
    ): AgentSession!
    
    resumeSession(
        sessionId: ID!
    ): AgentSession!
}

type Subscription {
    agentSessionEvents(sessionId: ID!): AgentEvent!
}
```

### 7. Plugin Integration

```python
# src/plugins/core/agent/plugin.py (updated)
class AgentPlugin(PluginBase):
    """Agent plugin with unified session management."""
    
    async def run(
        self, 
        inputs: AgentInput, 
        context: PipelineContext
    ) -> AgentOutput:
        """Run agent with proper session tracking."""
        config = self._resolve_config(context)
        
        # Check if resuming from checkpoint
        session_id = context.get("_agent_session_id")
        
        # Create executor with session management
        executor = AgentPluginExecutor(
            session_manager=self.session_manager,
            agent_service=self.agent_service,
            conversation_runner=self.conversation_runner
        )
        
        # Execute based on mode
        if config.mode == "interactive":
            # For pipelines, interactive mode suspends immediately
            if not session_id:
                session = await executor.create_session_for_pipeline(
                    agent_name=config.agent_name,
                    task_id=context.task_id,
                    initial_message=inputs.topic
                )
                
                # Suspend with session info
                raise PluginSuspendedException(
                    "Agent requires interactive input",
                    state={"session_id": session.session_id}
                )
            else:
                # Resume from checkpoint
                return await executor.resume_pipeline_session(session_id, context)
                
        else:
            # Single-turn execution
            result = await executor.execute_single_turn(
                agent_name=config.agent_name,
                message=inputs.topic,
                context=context
            )
            
            return AgentOutput(
                conversation_id=result.session_id,
                transcript=result.transcript,
                summary=result.summary,
                artifacts=result.artifacts
            )
```

## Implementation Phases

### Phase 1: Core Session Management (Week 1)
1. Implement `AgentSession` and `AgentSessionManager`
2. Create file-based storage backend
3. Integrate with existing task management
4. Add session tracking to conversation runner

### Phase 2: CLI Integration (Week 2)
1. Add session management commands
2. Update agent plugin to use sessions
3. Implement resume functionality
4. Add session listing and inspection

### Phase 3: API Integration (Week 3)
1. Create REST endpoints for session management
2. Add streaming support with session context
3. Implement webhook session handling
4. Add authentication and authorization

### Phase 4: GraphQL Integration (Week 4)
1. Define GraphQL schema for sessions
2. Implement resolvers with DataLoader
3. Add subscription support for real-time updates
4. Create session-aware mutations

### Phase 5: Advanced Features (Week 5+)
1. Session expiration and cleanup
2. Multi-user session sharing
3. Session forking and merging
4. Performance optimizations

## Key Benefits

1. **Unified Experience**: Same session management across all interfaces
2. **Seamless Handoff**: Start in CLI, continue in API
3. **Full Traceability**: Every agent interaction linked to task IDs
4. **Robust Recovery**: Suspend/resume at any point
5. **Developer Friendly**: Simple, consistent APIs

## Migration Strategy

1. **Backward Compatibility**: Existing agent commands continue to work
2. **Opt-in Sessions**: Session management optional initially
3. **Gradual Rollout**: Enable per-interface as ready
4. **Data Migration**: Tool to import existing conversations

## Security Considerations

1. **Session Tokens**: Secure token generation for API access
2. **Access Control**: Role-based session permissions
3. **Data Encryption**: Encrypt sensitive conversation data
4. **Audit Logging**: Track all session operations
5. **Expiration**: Automatic cleanup of old sessions

## Performance Considerations

1. **Lazy Loading**: Load history on demand
2. **Pagination**: Handle large conversation histories
3. **Caching**: Redis for active session data
4. **Compression**: Compress checkpoint data
5. **Indexing**: Fast session lookups by various criteria