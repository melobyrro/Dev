# Agents for CultoTranscript

## What are Agents?

Agents are specialized sub-agents with expert personas and focused responsibilities. They're used for complex orchestration where you need deep domain expertise.

## Agents vs Skills

- **Skills**: Executable tasks with specific tools and outputs (e.g., log-analyzer, browser-tester)
- **Agents**: Expert personas for complex problem-solving and orchestration (e.g., docker-manager)

## When to Create Agents

Create an agent when you need:
1. Deep domain expertise (e.g., Docker expert, Python expert, Database expert)
2. Complex multi-step orchestration
3. Delegation of specialized decision-making
4. Context-aware problem-solving in a specific area

## Agent File Format

Agents are markdown files in this directory:

```markdown
# Agent Name

## Role
Brief description of the agent's role and expertise

## Responsibilities
- List of what this agent handles
- Specific areas of expertise
- Decision-making authority

## Tools & Skills Available
- List tools this agent can use
- List skills this agent can delegate to

## Guidelines
- How the agent should approach problems
- Best practices to follow
- Safety protocols

## Example Tasks
- Examples of when to use this agent
```

## Creating Agents for CultoTranscript

Potential agents for this project:

1. **transcription-expert**: Specializes in the 3-tier transcription pipeline
   - Handles yt-dlp, youtube-transcript-api, faster-whisper
   - Troubleshoots GPU/CPU issues
   - Optimizes transcription quality

2. **analytics-expert**: Specializes in Gemini AI analysis
   - Biblical reference detection
   - Theme identification
   - Embedding generation
   - Chatbot response optimization

3. **docker-orchestrator**: Manages multi-container setup
   - Docker Compose operations
   - Service health monitoring
   - Container troubleshooting
   - Volume and network management

4. **database-architect**: PostgreSQL and pgvector expert
   - Schema design and migrations
   - Query optimization
   - Vector search tuning
   - Data integrity maintenance

## Usage Pattern

```python
# In Claude Code conversation:
# User: "I need help optimizing the transcription pipeline"
# Claude: "Let me delegate this to the transcription-expert agent"
# [Invokes agent with context]
# Agent analyzes and provides expert recommendations
```

## Best Practices

1. **Keep agents focused**: Each agent should have a clear, narrow expertise area
2. **Provide context**: Give agents relevant information from CLAUDE.md
3. **Define boundaries**: Specify what the agent can and cannot do
4. **Include examples**: Show common scenarios where the agent helps
5. **Safety first**: Include safety protocols for destructive operations

---

To create a new agent, add a markdown file in this directory with the agent's name (e.g., `transcription-expert.md`).
