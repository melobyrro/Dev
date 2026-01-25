# System Knowledge

## Environment
- OS: macOS (Darwin)
- Shell: zsh
- Primary machine: Mac
- Docker VM: `192.168.1.11` (SSH: `byrro@192.168.1.11`)
- Proxmox: `192.168.1.10` (SSH: `root@192.168.1.10`)

## Key Documentation
Before starting work, read these files for context:
- `home-server/AGENTS.md` - SSH access, monitoring stack, service details
- `home-server/architecture.md` - VPN, WireGuard, network topology

## Sync Protocol
- Always `git pull` at session start (handled by claudee command)
- Before ending a session with meaningful changes, ASK the user if they want to commit
- If user approves commit, ASK if they want to push to GitHub
- Never auto-commit or auto-push without explicit user approval

## ChatGPT Integration
- ChatGPT writes plans to `PLANS/YYYY-MM-DD-<topic>.md`
- Read PLANS/ for pending work from ChatGPT
- Update plan files with status as you execute

## Project Structure
- `home-server/` - Home automation, Docker infrastructure knowledge
- `CultoTranscript/` - Sermon transcription platform
- `claude-config-auditor/` - Configuration auditing tool
