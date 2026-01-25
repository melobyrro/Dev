# System Knowledge

## Environment
- OS: macOS (Darwin)
- Shell: zsh
- Primary machine: Mac
- Apps: Docker containers on VM (not in this repo)

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
