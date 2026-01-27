# System Knowledge

## Environment
- OS: macOS (Darwin)
- Shell: zsh
- Primary machine: Mac
- Docker VM: `192.168.1.11` (SSH: `byrro@192.168.1.11`)
- Proxmox: `192.168.1.10` (SSH: `root@192.168.1.10`)

## Key Documentation
Before starting work, read these files for context:
- `home-server/GITOPS.md` - **GitOps workflow rules** (single source of truth)
- `home-server/AGENTS.md` - SSH access, monitoring stack, service details
- `home-server/architecture.md` - VPN, WireGuard, network topology

## Sync Protocol (GitOps)

> **Golden Rule:** Only edit files on Mac in this repo. Everything else is deployment.

**Automated hooks:**
- **Session start:** Git pull runs automatically - check for errors before proceeding
- **After git push:** VM deployment triggers automatically (pulls to VM + deploys configs)

**Ending a session:** Use `/done` to:
1. Review uncommitted changes
2. Commit with a summary
3. Push to GitHub
4. Wait for VM deploy to complete
5. Confirm success before exiting

**If hooks fail:** Claude will see the error output and can help resolve conflicts or connection issues.

**Full workflow details:** See `home-server/GITOPS.md`

## Session Workflows

### Git Pull Feedback (Enhanced)
At every session start, Claude automatically checks for git pull results and displays them:
- **Success with commits**: Shows commit messages that were pulled
- **Already up to date**: Brief confirmation
- **Skipped**: Explains uncommitted changes blocked the pull
- **Failed**: Shows actual error details and resolution steps

The hook writes results to `/tmp/claude-git-pull-result-{HASH}.txt` which Claude reads and displays.

For details, see `~/.claude/docs/session-start-behavior.md`

### `/done` Command (Enhanced)
The `/done` skill now includes:
- **Context-aware file selection**: Categorizes files as "Relevant to current work" vs "Other changes" based on session topic
- **Documentation discovery**: Finds related `requirements.md`, `CLAUDE.md`, and `docs/plans/*.md` files
- **Lightweight doc review**: Offers to review/update docs before committing
- **Enhanced commit messages**: Documents both code and doc changes

For details, see `~/.claude/skills/done/SKILL.md`

### Inline Usage Status Display
Always-visible statusLine showing context window usage:

**Example:** `Ctx: 24%`

Shows percentage of the 200K token context window currently used in this conversation. This is the only metric that updates in real-time.

**Why only context window?**
- **Context %** - Real-time data from Claude Code (accurate)
- **Session/Weekly %** - Only available via `/usage` command (requires server API + SSO)
- StatusLine scripts can't access live session data, only local cache which lags significantly

**For session/weekly usage:** Run `/usage` command in Claude Code

**Configuration:**
- `~/.claude/scripts/usage-status.sh` - Display logic (reads stdin JSON from Claude Code)
- `~/.claude/settings.json` - StatusLine command configuration

**Created:** 2026-01-26
**Simplified:** 2026-01-26 (removed approximate session/weekly metrics)

## ChatGPT Integration
- ChatGPT writes plans to `PLANS/YYYY-MM-DD-<topic>.md`
- Read PLANS/ for pending work from ChatGPT
- Update plan files with status as you execute

## Project Structure
- `home-server/` - Home automation, Docker infrastructure knowledge
- `CultoTranscript/` - Sermon transcription platform
- `claude-config-auditor/` - Configuration auditing tool

## MCP Server Configuration

### Approved MCP Servers
This system uses these MCP servers and integrations:
- **ref** - Documentation search and reference tools
- **sequential-thinking** - Structured problem-solving tool
- **chrome-devtools** - Chrome DevTools integration
- **superpowers** - Enhanced capabilities plugin
- **claude-in-chrome** - Browser automation integration

### Configuration Files
MCP servers are configured in multiple locations with specific precedence:

1. **Global Configuration**
   - `~/.claude.json` (mcpServers section) - Global + project overrides
   - `~/.claude/settings.json` (mcpServers section) - Global settings
   - For global availability, servers MUST be in BOTH files

2. **Project-Specific Configuration**
   - `<project>/.mcp.json` - Project-level supplemental servers
   - Examples: `/Users/andrebyrro/Dev/.mcp.json`, `/Users/andrebyrro/Dev/home-server/.mcp.json`

### Configuration Structure

**MCP Server Entry (in .json files):**
```json
"mcpServers": {
  "server-name": {
    "command": "npx",
    "args": ["-y", "package-name"],
    "env": {}
  }
}
```

**Plugin Entry (in settings.json only):**
```json
"enabledPlugins": {
  "plugin-name@marketplace": true
}
```

### Maintenance Guidelines

**Adding a New MCP Server:**
1. Add to `~/.claude.json` mcpServers
2. Add to `~/.claude/settings.json` mcpServers
3. Optionally add to project .mcp.json files
4. Restart Claude Code

**Removing an MCP Server:**
1. Remove from ALL config files:
   - `~/.claude.json` (global mcpServers + any project overrides)
   - `~/.claude/settings.json`
   - Project .mcp.json files
   - Any disabledMcpServers arrays in ~/.claude.json projects
2. Restart Claude Code

**Config File Backups:**
- Before modifying: `cp ~/.claude.json ~/.claude.json.backup-$(date +%Y%m%d-%H%M%S)`
- Rollback: `cp ~/.claude.json.backup-YYYYMMDD-HHMMSS ~/.claude.json`

### Verifying Configuration

**List global MCP servers:**
```bash
jq -r '.mcpServers | keys[]' ~/.claude.json
jq -r '.mcpServers | keys[]' ~/.claude/settings.json
```

**Check for project overrides:**
```bash
jq -r '.projects | to_entries[] | select(.value.mcpServers | length > 0) | "\(.key): \(.value.mcpServers | keys | join(", "))"' ~/.claude.json
```

**Verify project .mcp.json:**
```bash
jq -r '.mcpServers | keys[]' <project>/.mcp.json
```
