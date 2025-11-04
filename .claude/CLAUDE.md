# ~/Dev Claude Code Configuration

## Overview

This folder contains all development projects with standardized Claude Code configurations. The setup uses a **hierarchical configuration pattern** where root-level settings apply globally, and project-specific configurations can override or extend them as needed.

## Configuration Hierarchy

```
~/Dev/
├── .claude/                    # Root-level configuration (applies to all projects)
│   ├── settings.json           # Base configuration (committed to git)
│   ├── settings.local.json     # Local overrides (machine-specific, git-ignored)
│   ├── .gitignore             # Excludes local settings
│   ├── CLAUDE.md              # This file - root context
│   ├── commands/              # Shared slash commands
│   └── skills/                # Shared skills available to all projects
│
├── [project-name]/
│   └── .claude/               # Project-specific configuration
│       ├── settings.json      # Project base configuration
│       ├── settings.local.json # Project local overrides
│       ├── .gitignore        # Excludes local settings
│       ├── CLAUDE.md         # Project-specific context and instructions
│       ├── commands/         # Project-specific slash commands
│       ├── skills/           # Project-specific skills
│       └── agents/           # Project-specific agents (optional)
```

## MCP Servers (Globally Enabled)

The following MCP servers are configured at the root level and available to all projects:

1. **ref** - Documentation search and reading
   - Use for researching library/framework documentation
   - Excellent for error-fixing workflows

2. **sequential-thinking** - Advanced problem-solving
   - Use for complex multi-step reasoning
   - Helps with planning and analysis

3. **browser-use** - Web browser automation
   - Use for E2E testing and UI validation
   - Automated web interactions

4. **ide** - IDE integration tools
   - Enhanced editor capabilities
   - Workspace management

## Infrastructure Access

All projects have SSH access to the home server infrastructure:

### Proxmox Server (Hypervisor)
- **IP Address**: 192.168.1.10
- **SSH Access**: `ssh admin@192.168.1.10`
- **Purpose**: Hypervisor host running virtual machines
- **Role**: Infrastructure layer

### Docker VM (Application Host)
- **IP Address**: 192.168.1.11
- **SSH Access**: `ssh byrro@192.168.1.11`
- **Authentication**: SSH keys configured (no password needed)
- **Purpose**: Docker container host
- **Services**:
  - Docker Engine
  - Immich (photo management)
  - CultoTranscript (sermon transcription system)
- **Project Locations**:
  - CultoTranscript: `/home/byrro/CultoTranscript/`

### Common Operations

**Check Docker containers:**
```bash
ssh byrro@192.168.1.11 "docker compose -f /home/byrro/CultoTranscript/docker/docker-compose.yml ps"
```

**View container logs:**
```bash
ssh byrro@192.168.1.11 "docker compose -f /home/byrro/CultoTranscript/docker/docker-compose.yml logs --tail=50"
```

**Restart services:**
```bash
ssh byrro@192.168.1.11 "cd /home/byrro/CultoTranscript/docker && docker compose restart <service-name>"
```

## Projects

### home-server
**Type**: Infrastructure Management
**Purpose**: Manage Proxmox hypervisor and Docker VM hosting services
**Technologies**: Bash, SSH, Docker, Docker Compose
**Claude Code Features**:
- Remote executor skill for SSH operations
- Docker manager agent for container orchestration
- Comprehensive CLAUDE.md with orchestrator patterns
- 5 custom slash commands

### CultoTranscript
**Type**: Web Application
**Purpose**: Automated sermon transcription from YouTube videos
**Technologies**: Python, FastAPI, PostgreSQL, Redis, Docker
**Claude Code Features**:
- 5 specialized skills (environment, browser, database, logs, error-fixer)
- Browser automation for E2E testing
- Database inspection and cleanup tools

## Best Practices

### Permission Strategy
- **Root level**: Selective permissions for MCP tools and safe Bash commands (ssh, tree)
- **Projects**: Each project defines appropriate permission levels
  - Administrative projects: May use bypass permissions
  - Application projects: Restricted to necessary commands only

### Skills vs Agents
- **Skills**: Executable tasks with specific tools and outputs (e.g., log-analyzer, environment-checker)
- **Agents**: Expert personas for complex orchestration (e.g., docker-manager)

### File Organization
- Keep project-specific configurations in project `.claude/` folders
- Use root-level skills only for truly shared functionality
- Document project-specific patterns in project `CLAUDE.md` files

### Adding New Projects
1. Copy `.claude-template/` to your new project
2. Customize `CLAUDE.md` with project-specific context
3. Add project-specific skills/commands as needed
4. Configure appropriate permissions in `settings.json`
5. Set up `settings.local.json` for machine-specific overrides

## Global Skills

### browser-ui-tester
Run smoke and E2E UI checks against live browser sessions. Use when validating user flows, capturing screenshots, or collecting console logs.

### test-architect
Generate and evolve unit/integration tests and minimal coverage plan. Use when adding tests or increasing coverage.

## Resources

- For detailed setup instructions, see `~/Dev/CLAUDE_SETUP.md`
- For project template, see `~/Dev/.claude-template/`
- For Claude Code documentation, visit https://docs.claude.com/en/docs/claude-code
