# Infrastructure-as-Code Strategy

## Executive Summary

**Goal:** Create a professional, replicable home server setup with GitOps practices that provide disaster recovery, change tracking, and guardrails for future work.

**Approach:** Hybrid strategy - full automation where changes are frequent, documentation where changes are rare.

---

## Current State

### Infrastructure Stack
```
┌─────────────────────────────────────┐
│  Proxmox (192.168.1.10)             │  ← Hypervisor, ZFS storage
│  └── Docker VM (192.168.1.11)       │  ← Ubuntu/Debian running Docker
│      └── ~30 containers             │  ← Home Assistant, Caddy, *arr stack, etc.
└─────────────────────────────────────┘
```

### What's Currently in Git
| Item | In Git? | Location |
|------|---------|----------|
| Docker compose files | ✅ Yes | `home-server/docker/*/` |
| Home Assistant configs | ✅ Yes | `home-server/home-assistant/ha-config/` |
| Deploy scripts | ✅ Yes | `home-server/scripts/` |
| Architecture docs | ✅ Yes | `home-server/architecture.md` |
| Container app configs (Caddyfile, etc.) | ❌ No | Only on VM at `/mnt/ByrroServer/docker-data/` |
| VM OS configuration | ❌ No | Not documented |
| Proxmox configuration | ❌ No | Not documented |
| ZFS pool/dataset config | ❌ No | Not documented |

### Current GitOps Flow
```
Mac (edit) → GitHub (push) → VM (auto-pull + deploy via hook)
```
- Works for docker-compose files and HA configs
- Gap: Container-specific configs (Caddyfile, etc.) not in Git

---

## Proposed Plan

### Layer-by-Layer Strategy

| Layer | Change Frequency | Strategy | Priority |
|-------|------------------|----------|----------|
| **Containers/Configs** | Daily/Weekly | Full GitOps, auto-deploy | 🔴 High - Do first |
| **Docker VM** | Monthly | Ansible playbook + docs | 🟡 Medium - Phase 2 |
| **Proxmox** | Rarely | Export configs + runbook | 🟢 Low - Phase 3 |
| **ZFS/Hardware** | Almost never | Document once | 🟢 Low - Phase 3 |

### Phase 1: Complete Container GitOps (Immediate)

**Goal:** Every container config editable from Mac, version controlled, auto-deployed.

**Tasks:**
1. Audit all containers for configs not in Git
2. Copy missing configs (Caddyfile, etc.) to repo under `home-server/docker/<container>/`
3. Update `deploy-from-repo.sh` to sync these configs to container data paths
4. Create `GITOPS.md` workflow documentation
5. Add guardrails: checklist for adding new containers

**Result:**
- Single source of truth: `~/Dev/home-server/`
- Workflow: Edit on Mac → commit → push → auto-deploy to VM
- Any container rebuildable from Git

### Phase 2: VM Configuration as Code (Later)

**Goal:** Rebuild Docker VM from scratch using Ansible.

**Tasks:**
1. Document current VM setup (packages, users, mounts, cron jobs)
2. Create Ansible playbook: `home-server/ansible/docker-vm.yml`
3. Include: Docker install, user setup, mount points, SSH keys, cron jobs
4. Test by provisioning a fresh VM

**Result:**
- VM rebuildable in ~30 minutes with one command
- Changes to VM tracked in Git

### Phase 3: Proxmox & Storage Documentation (Later)

**Goal:** Document enough to rebuild from bare metal.

**Tasks:**
1. Export Proxmox VM configs: `qm config <vmid>`
2. Document ZFS pool creation commands
3. Document network/VLAN setup
4. Create `home-server/docs/bare-metal-setup.md` runbook

**Result:**
- Not automated (changes too rare to justify)
- But documented enough to rebuild if needed

---

## Proposed Directory Structure

```
Dev/
├── home-server/
│   ├── GITOPS.md                    # Workflow documentation
│   ├── AGENTS.md                    # For Claude context
│   ├── architecture.md              # Network/VPN docs
│   │
│   ├── docker/                      # All container configs
│   │   ├── caddy/
│   │   │   ├── docker-compose.yml
│   │   │   └── Caddyfile            # ← ADD: currently only on VM
│   │   ├── homeassistant/
│   │   │   └── docker-compose.yml
│   │   └── ... (other containers)
│   │
│   ├── home-assistant/
│   │   └── ha-config/               # HA yaml configs
│   │
│   ├── scripts/
│   │   └── deploy-from-repo.sh      # Syncs repo → container paths
│   │
│   ├── ansible/                     # ← ADD: Phase 2
│   │   └── docker-vm.yml
│   │
│   └── docs/                        # ← ADD: Phase 3
│       └── bare-metal-setup.md
```

---

## Workflow After Implementation

### Adding a New Container
1. Create `home-server/docker/<name>/docker-compose.yml`
2. Add any config files to same directory
3. Update `deploy-from-repo.sh` if configs need syncing
4. Commit → push → auto-deploys

### Editing Existing Config
1. Edit file in `~/Dev/home-server/` on Mac
2. Commit → push → auto-deploys to VM
3. Container restarts with new config

### Disaster Recovery
| Scenario | Recovery |
|----------|----------|
| Container dies | `docker-compose up -d` (configs in Git) |
| VM dies | Run Ansible playbook, then deploy script |
| Proxmox dies | Follow bare-metal runbook, restore VM backup |

---

## Benefits

1. **Single source of truth** - Always edit on Mac, everything flows from Git
2. **Change history** - See what changed, when, why (git log)
3. **Disaster recovery** - Rebuild any layer from Git + docs
4. **Guardrails** - New work naturally fits the framework
5. **Professional practice** - Same patterns used in industry

---

## Open Questions

1. Should we audit missing configs now or add them incrementally as we touch containers?
2. Any containers with secrets that need special handling (not in Git)?
3. Preferred timeline for Phase 2 (Ansible) and Phase 3 (Proxmox docs)?
