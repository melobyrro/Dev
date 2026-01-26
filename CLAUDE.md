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

## ChatGPT Integration
- ChatGPT writes plans to `PLANS/YYYY-MM-DD-<topic>.md`
- Read PLANS/ for pending work from ChatGPT
- Update plan files with status as you execute

## Project Structure
- `home-server/` - Home automation, Docker infrastructure knowledge
- `CultoTranscript/` - Sermon transcription platform
- `claude-config-auditor/` - Configuration auditing tool
