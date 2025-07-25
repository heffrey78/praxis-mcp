# Structured Data Collection with Agents

This example demonstrates how to use the `data_schema` feature to ensure agents collect data in a specific format.

## Basic Usage

### 1. Define a Data Schema in Your Pipeline

```yaml
id: user-survey
name: User Survey Pipeline
description: Collects user information with structured data validation

steps:
  - name: collect_survey
    plugin: agent
    config:
      agent_config:
        name: Survey Agent
        agents:
          - name: default
            prompt: |
              You are a friendly survey assistant. Collect the following information:
              1. User's full name
              2. Email address
              3. Age
              4. Favorite programming language
              5. Years of experience
              
              Be conversational and friendly while collecting this data.
            model: gpt-4.1-nano
      mode: interactive
      initial_message: "Hi! I'd like to ask you a few questions for our developer survey."
      
      # Define the expected data structure
      data_schema:
        type: object
        properties:
          name:
            type: string
            description: "User's full name"
          email:
            type: string
            description: "User's email address"
          age:
            type: integer
            description: "User's age"
          favorite_language:
            type: string
            description: "Favorite programming language"
          years_experience:
            type: integer
            description: "Years of programming experience"
        required: ["name", "email", "age", "favorite_language", "years_experience"]

  - name: process_survey
    plugin: shell_command
    depends_on: [collect_survey]
    config:
      command: |
        echo "=== Survey Results ==="
        echo "Name: {{ collect_survey.metadata.collected_data.name }}"
        echo "Email: {{ collect_survey.metadata.collected_data.email }}"
        echo "Age: {{ collect_survey.metadata.collected_data.age }}"
        echo "Favorite Language: {{ collect_survey.metadata.collected_data.favorite_language }}"
        echo "Years of Experience: {{ collect_survey.metadata.collected_data.years_experience }}"
```

### 2. Using Pre-defined Schemas

You can also use pre-defined schemas by name:

```yaml
steps:
  - name: collect_developer_info
    plugin: agent
    config:
      agent_config:
        # ... agent configuration ...
      mode: interactive
      # Use a pre-registered schema
      data_schema_name: "DeveloperSurveySchema"
```

Available pre-defined schemas:
- `BasicUserInfoSchema` - name, email
- `DeveloperSurveySchema` - name, email, favorite_language, years_experience

### 3. How It Works

1. **Agent Instructions**: The agent automatically receives instructions about required fields
2. **Simplified Tool Call**: The agent only needs to signal completion, not format JSON
3. **Automatic Extraction**: When the agent calls `resume_pipeline`, the system uses OpenAI's structured outputs to extract data from the conversation
4. **Validation**: Extracted data is validated against the schema
5. **Pipeline Resume**: Validated data is passed to subsequent pipeline steps

### 4. Benefits

- **No JSON Formatting Errors**: Agents don't need to format JSON correctly
- **Type Safety**: Data is validated against the schema
- **Better UX**: Agents focus on conversation, not data formatting
- **Flexibility**: Works with any conversation style
- **Reliability**: Robust extraction using LLM with structured outputs

### 5. Testing with Pre-defined Responses

You can test pipelines with automated responses:

```bash
# Create a JSON file with responses
echo '["John Doe", "john@example.com", "30", "Python", "10"]' > responses.json

# Run pipeline with automated responses
praxis pipeline run user-survey -p dialogue=@responses.json
```

This feature makes it easy to build reliable data collection workflows with agents!