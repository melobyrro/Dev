# GitOps Workflow

## Golden Rule

> **Only edit files on your Mac in the Dev repo. Everything else is deployment.**

## How It Works

```
Mac (edit) → GitHub (push) → VM (auto-pull + deploy)
       ↑                              ↓
    You edit                   Configs synced to
    files here                 container paths
```

## Workflow

### Editing a Config

1. Open file in `~/Dev/home-server/` on Mac
2. Make changes
3. Commit and push:
   ```bash
   git add -A && git commit -m "Update X config" && git push
   ```
4. Post-push hook automatically:
   - SSHs to VM
   - Pulls latest from GitHub
   - Runs `deploy-from-repo.sh`
   - Restarts affected containers

### Adding a New Container

1. Create directory: `home-server/docker/<container-name>/`
2. Add `docker-compose.yml`
3. Add any config files (`.yaml`, `.conf`, etc.)
4. Update `scripts/deploy-from-repo.sh` to sync configs:
   ```bash
   rsync -av "$REPO/docker/<container>/config.yml" "$DOCKER_DATA/<container>/"
   ```
5. Commit and push

## Directory Structure

```
home-server/
├── docker/                      # Container configs
│   ├── caddy/
│   │   ├── docker-compose.yml
│   │   └── Caddyfile            # ← Synced to VM
│   ├── homepage/
│   │   └── *.yaml               # ← Synced to VM
│   └── ...
├── home-assistant/
│   └── ha-config/               # HA automations, etc.
├── scripts/
│   └── deploy-from-repo.sh      # Deployment script
└── GITOPS.md                    # This file
```

## What Gets Synced Where

| Repo Path | VM Destination |
|-----------|----------------|
| `docker/caddy/Caddyfile` | `/mnt/ByrroServer/docker-data/caddy/` |
| `docker/homepage/*.yaml` | `/mnt/ByrroServer/docker-data/homepage/` |
| `docker/loki/config.yml` | `/mnt/ByrroServer/docker-data/loki/` |
| `docker/promtail/promtail-config.yml` | `/mnt/ByrroServer/docker-data/promtail/` |
| `home-assistant/ha-config/*` | `/mnt/ByrroServer/docker-data/homeassistant/config/` |
| `docker/*/docker-compose.yml` | `/home/byrro/docker/` |

## Secrets

**Never commit secrets to Git.**

Files with secrets stay on VM only:
- `secrets.yaml` (Home Assistant)
- `.env` files
- API keys, passwords, tokens

These are excluded from sync via `.gitignore` and rsync `--exclude`.

## Rollback

If a deploy breaks something:

```bash
# On Mac: revert the commit
git revert HEAD
git push

# Auto-deploys the reverted config
```

Or manually on VM:
```bash
cd /home/byrro/Dev
git log --oneline -5       # Find good commit
git checkout <commit> -- path/to/file
bash home-server/scripts/deploy-from-repo.sh
```

## Quick Reference

| Task | Command |
|------|---------|
| Edit config | Edit in `~/Dev/home-server/`, commit, push |
| Force deploy | `ssh byrro@192.168.1.11 "cd /home/byrro/Dev && bash home-server/scripts/deploy-from-repo.sh"` |
| Check VM state | `ssh byrro@192.168.1.11 "cat /mnt/ByrroServer/docker-data/<container>/config"` |
| View deploy log | Check Claude Code hook output |
