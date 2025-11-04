# Claude Code Setup Guide - ~/Dev

Comprehensive guide for Claude Code configuration across all projects in the ~/Dev folder.

## Table of Contents

1. [Configuration Hierarchy](#configuration-hierarchy)
2. [MCP Server Setup](#mcp-server-setup)
3. [File Structure & Naming](#file-structure--naming)
4. [Permission Strategies](#permission-strategies)
5. [Creating Skills](#creating-skills)
6. [Creating Agents](#creating-agents)
7. [Creating Slash Commands](#creating-slash-commands)
8. [Project Templates](#project-templates)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Configuration Hierarchy

### Three-Tier System

Claude Code uses a hierarchical configuration system:

```
Level 1: Root Configuration (~/Dev/.claude/)
├── settings.json                 # Base settings for all projects
├── settings.local.json           # Local overrides (machine-specific)
├── CLAUDE.md                     # Root-level context
├── commands/                     # Shared slash commands
└── skills/                       # Shared skills

Level 2: Project Configuration ([project]/.claude/)
├── settings.json                 # Project base settings
├── settings.local.json           # Project local overrides
├── CLAUDE.md                     # Project-specific context
├── commands/                     # Project slash commands
├── skills/                       # Project skills
└── agents/                       # Project agents

Level 3: Inheritance & Overrides
Project settings override root settings
Local settings override base settings
```

### How Settings Merge

1. Root `settings.json` provides global defaults
2. Root `settings.local.json` overrides with machine-specific settings
3. Project `settings.json` overrides root settings for specific project
4. Project `settings.local.json` applies final machine-specific overrides

### What Goes Where

**Root Level** (`~/Dev/.claude/`):
- Universal permissions and MCP servers
- Shared skills (browser-ui-tester, test-architect)
- Common slash commands
- Cross-project documentation

**Project Level** (`[project]/.claude/`):
- Project-specific permissions
- Project-specific skills and agents
- Custom slash commands
- Project context and architecture

---

## MCP Server Setup

### Available MCP Servers

Currently enabled MCP servers across ~/Dev:

1. **ref** - Documentation search and reading
   - Search library/framework docs
   - Read documentation URLs
   - Used by error-fixer skills

2. **sequential-thinking** - Advanced problem-solving
   - Multi-step reasoning
   - Complex planning
   - Hypothesis generation and verification

3. **browser-use** - Web browser automation
   - E2E testing
   - UI validation
   - Automated web interactions

4. **ide** - IDE integration
   - Workspace operations
   - Editor capabilities
   - File management

### Enabling MCP Servers

**Globally** (in `~/Dev/.claude/settings.local.json`):
```json
{
  "enabledMcpjsonServers": [
    "ref",
    "sequential-thinking",
    "browser-use",
    "ide"
  ]
}
```

**Per-Project** (in `[project]/.claude/settings.local.json`):
```json
{
  "enabledMcpjsonServers": [
    "ref",
    "browser-use"
  ]
}
```

Project-level configuration overrides root-level. If a project needs additional servers, list all needed servers in the project config.

### Granting MCP Tool Permissions

In addition to enabling servers, you must grant permission to use their tools:

```json
{
  "permissions": {
    "allow": [
      "mcp__sequential-thinking__sequentialthinking",
      "mcp__browser-use__run_browser_agent"
    ]
  }
}
```

Permission format: `mcp__[server-name]__[tool-name]`

---

## File Structure & Naming

### Standard .claude Folder Structure

```
.claude/
├── settings.json               # Base configuration (committed)
├── settings.local.json         # Local overrides (git-ignored)
├── .gitignore                  # Exclude local settings
├── CLAUDE.md                   # Project context (committed)
├── commands/                   # Slash commands
│   ├── help.md                 # Creates /help command
│   ├── context.md              # Creates /context command
│   └── custom-command.md       # Creates /custom-command
├── skills/                     # Executable skills
│   ├── skill-name.md           # Single-file skill
│   └── complex-skill/          # Multi-file skill
│       └── SKILL.md            # Skill definition
└── agents/                     # Expert agents (optional)
    └── agent-name.md           # Agent definition
```

### File Naming Conventions

**Slash Commands** (`commands/`):
- File: `command-name.md`
- Creates: `/command-name`
- Examples: `help.md` → `/help`, `test.md` → `/test`

**Skills** (`skills/`):
- Option 1 (simple): `skill-name.md`
- Option 2 (complex): `skill-name/SKILL.md`
- Use lowercase with hyphens: `environment-checker.md`

**Agents** (`agents/`):
- File: `agent-name.md`
- Use descriptive names: `docker-manager.md`, `python-expert.md`

**Context Files**:
- Main context: `CLAUDE.md` (in .claude/ folder)
- Architecture: Include in project's `CLAUDE.md` or separate `ARCHITECTURE.md` (project-specific)

### Git Configuration

**.gitignore** (in `.claude/` folder):
```gitignore
# Local settings (machine-specific, not committed)
settings.local.json

# Temporary files
*.tmp
*.log

# OS-specific files
.DS_Store
Thumbs.db

# IDE-specific files
*.swp
*.swo
*~
```

**What to Commit**:
- ✅ `settings.json` (base configuration)
- ✅ `CLAUDE.md` (project context)
- ✅ `.gitignore`
- ✅ `commands/`, `skills/`, `agents/` (shared knowledge)

**What NOT to Commit**:
- ❌ `settings.local.json` (machine-specific)
- ❌ Temporary or generated files
- ❌ Personal API keys or secrets

---

## Permission Strategies

### Permission Modes

Three modes available:

1. **ask** (default): Prompt user for each tool usage
   ```json
   {"permissions": {"defaultMode": "ask"}}
   ```

2. **bypassPermissions**: Allow all operations without prompting
   ```json
   {"permissions": {"defaultMode": "bypassPermissions"}}
   ```

3. **selective**: Specify allow/deny lists
   ```json
   {
     "permissions": {
       "allow": ["Bash(ssh:*)", "mcp__ref__*"],
       "deny": ["Bash(rm:*)", "Bash(dd:*)"],
       "ask": []
     }
   }
   ```

### Recommended Strategies by Project Type

**Infrastructure/Admin Projects** (like home-server):
```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
```
- Full access for system administration
- Use responsibly - can modify system state

**Application Development** (like CultoTranscript):
```json
{
  "permissions": {
    "defaultMode": "ask",
    "allow": [
      "Bash(cat:*)",
      "Bash(docker-compose:*)",
      "mcp__browser-use__run_browser_agent"
    ]
  }
}
```
- Safe commands allowed
- Potentially destructive commands require confirmation

**Root Level** (~/Dev/.claude/):
```json
{
  "permissions": {
    "allow": [
      "mcp__sequential-thinking__sequentialthinking",
      "Bash(ssh:*)",
      "mcp__browser-use__run_browser_agent",
      "Bash(tree:*)"
    ]
  }
}
```
- Selective permissions for common safe operations

### Bash Permission Patterns

```json
{
  "allow": [
    "Bash(ssh:*)",          // All SSH commands
    "Bash(docker:*)",       // All Docker commands
    "Bash(cat:*)",          // Read files
    "Bash(tree:*)",         // List directory structure
    "Bash(git status:*)"    // Specific git command
  ],
  "deny": [
    "Bash(rm:*)",           // Prevent file deletion
    "Bash(dd:*)",           // Prevent disk operations
    "Bash(mkfs:*)"          // Prevent filesystem formatting
  ]
}
```

---

## Creating Skills

### What are Skills?

Skills are executable, task-oriented capabilities with specific tools and structured outputs.

### Skill Template

```markdown
# Skill Name

## Purpose
[One-sentence description of what this skill does]

## When to Use
[Scenarios where this skill is appropriate]

## Tools Used
- [Tool 1] (e.g., Bash, Read, Grep)
- [Tool 2]
- [MCP Server] (if any)

## Inputs
- [What information does this skill need?]
- [Parameters or context required]

## Outputs
- [What does this skill produce?]
- [Format of results]

## Instructions

[Detailed step-by-step instructions for Claude Code]

1. [Step 1]
2. [Step 2]
3. [Step 3]

## Error Handling

[How to handle common errors]

## Example

[Example usage scenario]
```

### Common Skill Patterns

**1. Environment Checker**:
```markdown
# Environment Checker

## Purpose
Verify development environment is properly configured

## Instructions
1. Check Docker daemon: `docker ps`
2. Verify ports available: `lsof -i :8000`
3. Check .env file exists and has required variables
4. Validate dependencies installed
5. Report status with ✅/❌ for each check
```

**2. Log Analyzer**:
```markdown
# Log Analyzer

## Purpose
Monitor and analyze application logs for errors

## Tools Used
- Bash (docker-compose logs, tail)
- Grep (for pattern matching)

## Instructions
1. Stream logs: `docker-compose logs -f --tail=100`
2. Filter for errors: grep for ERROR, FATAL, Exception
3. Identify patterns and recurring issues
4. Provide structured analysis with:
   - Error count
   - Top error types
   - Suggested fixes
```

**3. Test Runner**:
```markdown
# Test Runner

## Purpose
Execute test suite and analyze results

## Instructions
1. Run tests with coverage: `pytest --cov=app tests/`
2. Capture output
3. Analyze results:
   - Pass/fail counts
   - Coverage percentage
   - Failed test details
4. If failures, offer to debug
```

### Skills Best Practices

1. **Single Responsibility**: Each skill does one thing well
2. **Clear Instructions**: Step-by-step, no ambiguity
3. **Structured Output**: Consistent, readable results
4. **Error Handling**: Anticipate and handle failures
5. **Tool Leverage**: Use Claude Code tools effectively

---

## Creating Agents

### What are Agents?

Agents are expert personas for complex orchestration and specialized decision-making.

### Agent Template

```markdown
# Agent Name

## Role
[Brief description of expertise and role]

## Expertise Areas
- [Primary technology or domain]
- [Related tools and frameworks]
- [Problem-solving focus]

## Responsibilities
- [What this agent handles]
- [Decision-making authority]
- [Specific tasks]

## Tools & Skills Available
- Claude Code tools: [Bash, Read, Edit, etc.]
- Skills to delegate: [skill-1, skill-2]
- MCP servers: [ref, browser-use, etc.]

## Guidelines
- [Approach to problems]
- [Best practices to follow]
- [Safety protocols]

## When to Invoke
- [Scenario 1]
- [Scenario 2]

## Example Tasks
### Task 1: [Description]
[How agent would approach this]

### Task 2: [Description]
[How agent would approach this]
```

### Agent Best Practices

1. **Deep Expertise**: Agent should be truly expert in their domain
2. **Clear Boundaries**: Define what agent can and cannot do
3. **Decision Authority**: Agent can make decisions without constant approval
4. **Skill Delegation**: Agent uses skills to execute tasks
5. **Context Awareness**: Agent understands project architecture

### Example Agent: Docker Manager

```markdown
# Docker Manager

## Role
Expert in Docker and container orchestration for this project

## Expertise Areas
- Docker and Docker Compose
- Container lifecycle management
- Multi-container networking
- Volume and storage management

## Responsibilities
- Manage container operations (start, stop, restart)
- Troubleshoot container issues
- Optimize Docker configurations
- Handle docker-compose orchestration

## Tools & Skills Available
- Bash (docker, docker-compose commands)
- Read (for docker-compose.yml, Dockerfiles)
- Edit (for configuration changes)
- log-analyzer skill (for container logs)

## Guidelines
- Always check container status before operations
- Use docker-compose for multi-container operations
- Review logs when troubleshooting
- Test changes in isolation when possible

## When to Invoke
- Complex Docker operations
- Container troubleshooting
- Multi-service orchestration
- Docker configuration optimization
```

---

## Creating Slash Commands

### What are Slash Commands?

Slash commands are custom commands that expand into prompts for Claude Code.

### Command Template

```markdown
# Command Name

[Brief description of what this command does]

## Instructions

[Detailed instructions for Claude Code to execute]

1. [Step 1]
2. [Step 2]
3. [Step 3]

[Any additional guidance or formatting instructions]
```

### Standard Commands

**1. /help Command**:
Shows comprehensive help about the project and Claude Code usage

**2. /context Command**:
Displays current session context, environment, and available resources

**3. /project Command**:
Quick project overview with architecture and key information

**4. /test Command** (project-specific):
Runs test suite and analyzes results

### Custom Command Examples

**/deploy Command**:
```markdown
# Deploy Command

Deploy the application to production

## Instructions

1. Verify current branch is main
2. Ensure all tests pass
3. Build production assets
4. Run deployment script
5. Verify deployment success
6. Report deployment status
```

**/analyze Command**:
```markdown
# Analyze Command

Analyze codebase for potential issues

## Instructions

1. Run linters (pylint, flake8, etc.)
2. Check for security vulnerabilities
3. Analyze test coverage
4. Review code complexity
5. Generate analysis report with:
   - Issue count by severity
   - Top issues to address
   - Recommendations
```

---

## Project Templates

### Using the Template

**Quick Start**:
```bash
# Copy template to new project
cp -r ~/Dev/.claude-template/ /path/to/your-project/.claude/

# Set up local settings
cd /path/to/your-project/.claude/
cp settings.local.json.example settings.local.json

# Customize CLAUDE.md
mv CLAUDE.md.template CLAUDE.md
# Edit CLAUDE.md with project details

# Remove template README
rm README.md
```

### Template Contents

- Base configuration files
- Standard slash commands (/help, /context, /project)
- README guides for skills and agents
- CLAUDE.md template with comprehensive sections
- .gitignore for proper version control

### Customizing for Your Project

1. **Update settings.json**: Set appropriate permissions
2. **Configure settings.local.json**: Enable needed MCP servers
3. **Complete CLAUDE.md**: Fill in all project-specific sections
4. **Add skills**: Create project-specific skills
5. **Add agents** (optional): For complex orchestration needs
6. **Add commands** (optional): Project-specific workflows

---

## Best Practices

### Configuration Management

1. **Commit base settings**: `settings.json` and `CLAUDE.md` belong in git
2. **Keep secrets local**: Never commit `settings.local.json` or API keys
3. **Document thoroughly**: Good CLAUDE.md = effective Claude Code
4. **Use .gitignore**: Exclude machine-specific and temporary files
5. **Update regularly**: Keep documentation current as project evolves

### Permission Strategy

1. **Start restrictive**: Use "ask" mode initially, relax as needed
2. **Be selective**: Allow specific safe commands, deny dangerous ones
3. **Project-appropriate**: Infrastructure projects can use bypass, apps should be restricted
4. **Document exceptions**: Explain why certain permissions are granted

### Skills & Agents

1. **Skills for tasks**: Use skills for specific, executable operations
2. **Agents for expertise**: Use agents for complex orchestration
3. **Keep focused**: Each skill/agent should have narrow, clear purpose
4. **Provide examples**: Show how and when to use skills/agents
5. **Test thoroughly**: Verify skills work as expected

### CLAUDE.md Structure

Essential sections:
1. **Project Overview**: What it does, purpose, goals
2. **Stack & Technologies**: Languages, frameworks, tools
3. **Architecture**: Components, services, data flow
4. **Development Workflow**: How to run, test, build
5. **Claude Code Integration**: Skills, agents, workflows
6. **Common Issues**: Troubleshooting guide
7. **Resources**: Links to docs and guides

### MCP Server Usage

1. **Enable globally**: Common servers (ref, sequential-thinking, ide)
2. **Enable per-project**: Project-specific needs (browser-use for web apps)
3. **Grant permissions**: Don't forget to allow MCP tool usage
4. **Document usage**: Note in CLAUDE.md which servers are used and how

---

## Troubleshooting

### MCP Servers Not Working

**Problem**: MCP server tools not available

**Solutions**:
1. Check server is enabled in `enabledMcpjsonServers`
2. Verify permissions granted for MCP tools
3. Restart Claude Code to reload configuration
4. Check MCP server logs for errors

### Permissions Not Applying

**Problem**: Permission settings not taking effect

**Solutions**:
1. Verify JSON syntax is correct (no trailing commas)
2. Check configuration hierarchy (project overrides root)
3. Ensure settings.local.json exists if referenced
4. Restart Claude Code session

### Skills Not Available

**Problem**: Custom skills not showing up

**Solutions**:
1. Verify file is in correct location (`.claude/skills/`)
2. Check file has correct extension (`.md`)
3. For directory skills, ensure `SKILL.md` exists
4. Verify markdown formatting is correct

### Slash Commands Not Working

**Problem**: Custom /commands not recognized

**Solutions**:
1. Verify file is in `.claude/commands/` folder
2. Check file naming: `command-name.md` creates `/command-name`
3. Ensure markdown file is properly formatted
4. Restart Claude Code to reload commands

### Settings Local Not Being Used

**Problem**: Local settings not overriding base settings

**Solutions**:
1. Ensure file is named exactly `settings.local.json`
2. Check file is in correct location (`.claude/` folder)
3. Verify .gitignore includes this file
4. Check JSON syntax is valid

### MCP Permission Errors

**Problem**: "Permission denied" when using MCP tools

**Solutions**:
1. Add tool to `permissions.allow` list
2. Format: `mcp__[server-name]__[tool-name]`
3. Example: `mcp__browser-use__run_browser_agent`
4. Restart session after changing permissions

---

## Current Setup Summary

### Root Level (~/Dev/.claude/)

**MCP Servers**: ref, sequential-thinking, browser-use, ide
**Permissions**: Selective (ssh, tree, MCP tools)
**Shared Skills**: browser-ui-tester, test-architect
**Shared Commands**: help, context, project

### Projects

**home-server**:
- Type: Infrastructure management
- Permissions: Bypass (full access)
- Skills: remote-executor
- Agents: docker-manager
- Commands: 5 custom commands
- Focus: SSH operations, Docker management

**CultoTranscript**:
- Type: Web application (Python/FastAPI)
- Permissions: Selective (ask with safe allowances)
- Skills: 5 (environment-checker, browser-tester, database-inspector, log-analyzer, error-fixer)
- Agents: None (agents/ folder with README)
- Commands: 4 (help, context, project, test)
- Focus: Testing, debugging, development workflow

### Template

Location: `~/Dev/.claude-template/`
- Complete starter structure
- Standard commands
- README guides for skills/agents
- CLAUDE.md template
- Configuration examples

---

## Resources

### Official Documentation
- Claude Code Docs: https://docs.claude.com/en/docs/claude-code
- MCP Servers: https://modelcontextprotocol.org/

### Local Resources
- Root Context: ~/Dev/.claude/CLAUDE.md
- Template: ~/Dev/.claude-template/
- Examples:
  - Infrastructure: ~/Dev/home-server/.claude/
  - Web App: ~/Dev/CultoTranscript/.claude/

### Getting Help

1. Use `/help` command in any project
2. Read project CLAUDE.md for context (includes architecture details)
3. Check project-specific ARCHITECTURE.md if available
4. Review this CLAUDE_SETUP.md for configuration guidance

---

**Last Updated**: 2025-01-04
**Version**: 1.0
