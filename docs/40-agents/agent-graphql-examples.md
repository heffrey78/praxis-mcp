# Agent GraphQL API Examples

This document provides examples of how to use the enhanced GraphQL API for agent management, including entry point identification and agent relationship querying.

## New Features

The agent GraphQL API now supports:

1. **Entry Point Identification**: Identify which agents are entry points for their configurations
2. **Agent Relationships**: Query handoff targets with full agent information
3. **Configuration Grouping**: Group agents by their parent configuration
4. **Enhanced Metadata**: Additional fields for better agent management

## New Fields

### AgentInfo Type

```graphql
type GQLAgentInfo {
  id: String!
  name: String!
  description: String!
  defaultModel: String!
  modelSettings: JSON
  availableTools: [String!]!
  guardrails: [String!]!
  mcpServers: [String!]!
  mcpServerConfigs: [GQLMCPServerConfig!]!
  handoffNames: [String!]!
  supportsStreaming: Boolean!
  historyStorage: String!
  systemPrompt: String
  promptFilename: String
  
  # New fields
  isEntryPoint: Boolean!           # Whether this agent is the entry point
  parentConfiguration: String      # Configuration directory this agent belongs to
  handoffTargets: [GQLAgentInfo!]! # Full agent info for handoff targets
}
```

## Query Examples

### 1. Get All Agents (Enhanced)

```graphql
query GetAllAgents {
  agents {
    id
    name
    description
    defaultModel
    isEntryPoint
    parentConfiguration
    handoffNames
    handoffTargets {
      id
      name
      description
      isEntryPoint
    }
  }
}
```

**Example Response:**
```json
{
  "data": {
    "agents": [
      {
        "id": "hello-world-hello-world-agent",
        "name": "Hello World Agent",
        "description": "A simple hello world agent using external prompt file",
        "defaultModel": "gpt-4.1-nano",
        "isEntryPoint": true,
        "parentConfiguration": "hello-world",
        "handoffNames": ["Inline Prompt Agent"],
        "handoffTargets": [
          {
            "id": "hello-world-inline-prompt-agent",
            "name": "Inline Prompt Agent",
            "description": "A test agent using inline prompt configuration",
            "isEntryPoint": false
          }
        ]
      },
      {
        "id": "hello-world-inline-prompt-agent",
        "name": "Inline Prompt Agent",
        "description": "A test agent using inline prompt configuration",
        "defaultModel": "gpt-4.1-nano",
        "isEntryPoint": false,
        "parentConfiguration": "hello-world",
        "handoffNames": ["Hello World Agent"],
        "handoffTargets": [
          {
            "id": "hello-world-hello-world-agent",
            "name": "Hello World Agent",
            "description": "A simple hello world agent using external prompt file",
            "isEntryPoint": true
          }
        ]
      }
    ]
  }
}
```

### 2. Get Entry Point Agents Only

```graphql
query GetEntryPointAgents {
  entryPointAgents {
    id
    name
    description
    parentConfiguration
    handoffTargets {
      id
      name
      description
    }
  }
}
```

**Example Response:**
```json
{
  "data": {
    "entryPointAgents": [
      {
        "id": "hello-world-hello-world-agent",
        "name": "Hello World Agent",
        "description": "A simple hello world agent using external prompt file",
        "parentConfiguration": "hello-world",
        "handoffTargets": [
          {
            "id": "hello-world-inline-prompt-agent",
            "name": "Inline Prompt Agent",
            "description": "A test agent using inline prompt configuration"
          }
        ]
      }
    ]
  }
}
```

### 3. Get Agents by Configuration

```graphql
query GetAgentsByConfiguration($configName: String!) {
  agentsByConfiguration(configurationName: $configName) {
    id
    name
    description
    isEntryPoint
    handoffNames
    handoffTargets {
      id
      name
    }
  }
}
```

**Variables:**
```json
{
  "configName": "hello-world"
}
```

**Example Response:**
```json
{
  "data": {
    "agentsByConfiguration": [
      {
        "id": "hello-world-hello-world-agent",
        "name": "Hello World Agent",
        "description": "A simple hello world agent using external prompt file",
        "isEntryPoint": true,
        "handoffNames": ["Inline Prompt Agent"],
        "handoffTargets": [
          {
            "id": "hello-world-inline-prompt-agent",
            "name": "Inline Prompt Agent"
          }
        ]
      },
      {
        "id": "hello-world-inline-prompt-agent",
        "name": "Inline Prompt Agent",
        "description": "A test agent using inline prompt configuration",
        "isEntryPoint": false,
        "handoffNames": ["Hello World Agent"],
        "handoffTargets": [
          {
            "id": "hello-world-hello-world-agent",
            "name": "Hello World Agent"
          }
        ]
      }
    ]
  }
}
```

### 4. Get All Configuration Names

```graphql
query GetConfigurationNames {
  configurationNames
}
```

**Example Response:**
```json
{
  "data": {
    "configurationNames": [
      "hello-world",
      "k0rdent"
    ]
  }
}
```

### 5. Complex Query: Multi-Agent System Overview

```graphql
query MultiAgentSystemOverview {
  configurationNames
  entryPointAgents {
    id
    name
    parentConfiguration
    handoffTargets {
      id
      name
      isEntryPoint
      handoffTargets {
        id
        name
      }
    }
  }
}
```

This query gives you a complete overview of all multi-agent systems, showing:
- All available configurations
- Entry point agents for each configuration
- The complete handoff graph (2 levels deep)

## REST API Examples

The same functionality is also available via REST API:

### Get Entry Point Agents
```bash
GET /api/v1/agents/entry-points/
```

### Get Agents by Configuration
```bash
GET /api/v1/agents/by-configuration/hello-world
```

### Get Configuration Names
```bash
GET /api/v1/agents/configurations/
```

## Use Cases

### 1. Agent Configuration Dashboard
Use `entryPointAgents` to show available multi-agent systems and their entry points.

### 2. Agent Flow Visualization
Use the `handoffTargets` field to build visual representations of agent handoff flows.

### 3. Configuration Management
Use `agentsByConfiguration` to manage and edit specific agent configurations.

### 4. System Health Monitoring
Query all agents and check their `isEntryPoint` status to ensure proper configuration.

## Migration Notes

- Existing queries will continue to work unchanged
- New fields are optional and have sensible defaults
- The `handoffTargets` field provides richer information than `handoffNames`
- Entry point identification helps distinguish between multi-agent systems and individual agents 