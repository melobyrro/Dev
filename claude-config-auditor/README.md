# Claude Config Auditor - Local Agent

This agent scans Claude Code configuration files on your Mac and pushes them to n8n for auditing.

## What it does

1. Discovers projects in `~/Dev` that have `.claude/` directories
2. Reads configuration files:
   - `settings.json`
   - `settings.local.json`
   - `CLAUDE.md`
   - Lists of skills and commands
3. Computes a config hash for change detection
4. POSTs the data to n8n webhook at `http://192.168.1.11:5678/webhook/config-sync`

## Setup

### Prerequisites

- Python 3.8+
- n8n running on Docker VM (see `home-server/n8n/README.md`)

### Installation

```bash
cd ~/Dev/claude-config-auditor
./setup.sh
```

This will:
1. Install Python dependencies
2. Run a dry test to verify the agent works
3. Install and load the launchd agent

## Usage

### Manual run

```bash
# Normal run - sends data to n8n
python3 agent.py

# Dry run - prints payload without sending
python3 agent.py --dry-run
```

### View logs

```bash
tail -f /tmp/claude-config-auditor.log
```

### Manage the scheduled agent

```bash
# Check if running
launchctl list | grep claude-config-auditor

# Stop
launchctl unload ~/Library/LaunchAgents/com.byrro.claude-config-auditor.plist

# Start
launchctl load ~/Library/LaunchAgents/com.byrro.claude-config-auditor.plist
```

## Schedule

The agent runs:
- On Mac login
- Every 4 hours (14400 seconds)

## Configuration

Edit `agent.py` to modify:

### Known Projects

```python
KNOWN_PROJECTS = [
    "CultoTranscript",
    "home-server",
    "home-server/home-assistant",
    # Add more project paths as needed
]
```

### n8n Webhook URL

```python
N8N_WEBHOOK_URL = "http://192.168.1.11:5678/webhook/config-sync"
```

### Dev Root

```python
DEV_ROOT = Path.home() / "Dev"
```

## Troubleshooting

### Agent not running

Check launchd logs:
```bash
log show --predicate 'subsystem == "com.apple.launchd"' --last 1h | grep claude
```

### Can't reach n8n

Test connectivity:
```bash
curl -X POST http://192.168.1.11:5678/webhook/config-sync \
  -H "Content-Type: application/json" \
  -d '{"agent_version":"1.0.0","hostname":"test","projects":[]}'
```

### Python errors

Check the log file:
```bash
cat /tmp/claude-config-auditor.log
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent script |
| `requirements.txt` | Python dependencies |
| `com.byrro.claude-config-auditor.plist` | launchd configuration |
| `setup.sh` | Installation script |
