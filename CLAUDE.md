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
- `home-server/architecture.md` - VPN, WireGuard, network topology

## Global Guardrails (All Projects Inherit)

These rules apply to EVERY session. Nested CLAUDE.md files inherit and may extend these rules.

### 1. Session Start: Claude for Chrome Verification (MANDATORY)

At the START of every session, before any work:

1. Call `mcp__claude-in-chrome__tabs_context_mcp`
2. Verify response shows Chrome extension is connected
3. Confirm authenticated sessions are accessible (user is logged into browser)
4. Report to user:
   - ✓ "Claude for Chrome ready - authenticated sessions available"
   - ✗ "Claude for Chrome unavailable - browser automation won't work this session"

**This is a one-time check at session start, not continuous.**

### 2. Use Task Tool for Substantive Work

For non-trivial work, use the `Task` tool to spin up subagents:

- **Why**: Keeps main context clean, enables parallel execution
- **When**: Implementation, testing, exploration, multi-file changes
- **How**: Launch Task with clear scope, let it complete, review results

Example:
```
Task: "Implement the login form component per the spec in requirements.md"
Task: "Run all tests and report failures"
Task: "Explore the codebase to find where API calls are made"
```

### 3. Verification Before Claiming Done

Never claim work is complete without verification:
- UI changes → Use Claude for Chrome to visually confirm
- Code changes → Run tests or relevant commands
- Deployments → Check logs or UI for success

### 4. Post-Implementation Validation Pattern

After implementing changes that affect UI or user-facing behavior, spawn a validation task:

**Validation Task Template:**
```
Task: "Validate [change description]"
- Navigate to [URL/page]
- Verify visual/functional behavior
- Check browser console for errors
- Capture screenshot evidence
- Report: PASS/FAIL with details
```

**When Required:**
| Change Type | Validation |
|------------|------------|
| Dashboard YAML | Chrome MCP screenshot |
| Web app code | Navigate + verify |
| API endpoint | Test call + response |
| Backend-only | Run tests (no Chrome) |
| Documentation | Not required |

### 5. Context Discipline for Large Files

**Rules:**
1. **Changelogs** → separate CHANGELOG.md, never embedded in CLAUDE.md
2. **Large file searches** → use Grep to find specific content first, then targeted reads
3. **Exploration** → delegate to Task agents to keep main context clean
4. **Anti-patterns to avoid:**
   - Reading entire large files when an excerpt suffices
   - Repeated full-file reads without mental caching
   - Including full file contents in responses when summaries work

### 6. Temp File Hygiene

**Rule:** No temp files in project root at session end.

| File Type | Location | Lifecycle |
|-----------|----------|-----------|
| Debug scripts | `.scratch/` | Delete after use |
| Test outputs | `.scratch/` | Delete after use |
| Generated plans | `~/.claude/plans/` | Auto-managed |

All projects should have `.scratch/` in `.gitignore`.
The `/done` skill checks for orphan temp files before completing.

---

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

### Git Pull Display (Required at Session Start)
**IMPORTANT:** When you see `SessionStart:startup hook success:` in your system context at the start of a session, you MUST immediately tell the user the git pull result in your first response. The message after the colon contains the result.

Examples of what to say:
- "Git pull: Already up to date"
- "Git pull: Pulled 3 commits"
- "Git pull: Skipped (uncommitted changes)"
- "Git pull: Failed - [include error details]"

This ensures the user knows the sync status before starting work.

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

## Universal Dev Workflow (All Projects Inherit This)

> **Child CLAUDE.md files inherit these rules.** Project-specific files add domain knowledge but don't override this workflow.

### Session Start Protocol

Execute in order at the START of every session:

1. **Report git pull result** - From hook output in system context
2. **Verify Claude for Chrome** - Call `mcp__claude-in-chrome__tabs_context_mcp`
   - Success: "Claude for Chrome ready"
   - Failure: "Claude for Chrome unavailable - browser tasks limited"
3. **Announce readiness** - Brief status to user

For web app projects, also verify you can navigate to the app URL with authenticated session.

### Context Management

- **Use Task tool** to spin up subagents for substantive work
- Delegate independent subtasks to keep main context clean
- Don't bloat context with repeated file reads - let agents handle exploration
- Review agent results before proceeding

### Documentation Discipline
- Keep `requirements.md` files updated as scope changes
- Document architectural decisions in relevant `CLAUDE.md` files
- Update plans in `docs/plans/` when implementation approach changes
- Before committing, check if related docs need updates

### Session End Protocol
- Use `/done` to commit, push, and deploy
- The post-push hook automatically deploys to VM
- Verify deployment completed (look for success/error message)
- If deployment fails, help user troubleshoot before ending session

---

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
