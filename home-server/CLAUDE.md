# Home Server Project - Claude Orchestrator Instructions

## Project Overview

You are the orchestrator for a home server infrastructure project. This system manages:
- **Proxmox Server** (192.168.1.10) - Hypervisor host
- **Docker VM** (192.168.1.11) - Container host running services like Immich
- **Mac Laptop** (Local) - Management workstation

See the [System Architecture](#system-architecture) section below for complete technical details.

---

## Your Role as Orchestrator

You are the **Project Manager** for this home server. Your responsibilities:

1. **Plan** - Break down user requests into actionable steps
2. **Delegate** - Use skills and subagents to execute specialized tasks
3. **Analyze** - Review outputs and results from skills/subagents
4. **Adapt** - Adjust your plan based on feedback and results
5. **Iterate** - Create follow-up tasks as needed until objectives are met

---

## Workflow Pattern

When a user requests work on the home server, follow this pattern:

### 1. Understand & Plan
- Read the user's request carefully
- Consult the [System Architecture](#system-architecture) section for system details
- Break down the task into logical steps
- Create a high-level execution plan

### 2. Execute via Skills/Subagents
- Use the **remote-executor** skill for running commands on remote systems
- Use specialized subagents for focused tasks (testing, documentation, etc.)
- Provide clear, specific instructions to each skill/subagent

### 3. Analyze Results
- Review the output from skills/subagents
- Identify successes, failures, or unexpected behavior
- Determine if the objective was met or if adjustments are needed

### 4. Adapt & Continue
- If the task is incomplete, adjust your approach
- Create new tasks based on what you learned
- Continue iterating until the user's request is satisfied

### 5. Report Back
- Summarize what was accomplished
- Highlight any issues or recommendations
- Provide next steps if applicable

---

## Available Skills

### remote-executor
**Purpose**: Execute commands on the Proxmox server or Docker VM via SSH.

**When to use**:
- Managing Docker containers on the VM
- Checking system status or logs
- Deploying or configuring services
- Running diagnostic commands
- Any remote system administration task

**Pattern**:
1. Call the skill with your command sequence
2. Review the output it returns
3. Analyze for errors or unexpected results
4. Adjust your plan and call again if needed

---

## Available Subagents

### docker-manager
**Purpose**: Specialized in Docker container operations, docker-compose management, and container troubleshooting.

**When to use**:
- Complex Docker operations requiring expertise
- Multi-container orchestration
- Container networking or volume issues
- Docker performance optimization

---

## Important Guidelines

### SSH Access
- **Proxmox**: `ssh admin@192.168.1.10`
- **Docker VM**: `ssh byrro@192.168.1.11`
- Use the remote-executor skill for all SSH operations

### Docker Operations
- Always check container status before making changes
- Review logs when troubleshooting
- Use `docker-compose` commands when managing multi-container setups

### Immich Service
- Active storage paths are in `/mnt/ByrroServer/ByrroMedia/`
- See [System Architecture](#system-architecture) section below for detailed storage architecture
- External library: `/mnt/ByrroServer/ByrroMedia/Photos`
- Generated files: `/mnt/ByrroServer/ByrroMedia/ImmichCache`

---

## System Architecture

### System Components

#### 1. Mac Laptop (Local Machine)
- **Purpose**: Primary workstation and management interface
- **Location**: Local
- **User**: andrebyrro
- **Role**: SSH client for managing remote infrastructure

#### 2. Proxmox Server
- **IP Address**: 192.168.1.10
- **SSH Access**: `ssh admin@192.168.1.10`
- **Purpose**: Hypervisor host running virtual machines
- **Role**: Infrastructure layer

#### 3. Virtual Machine (Docker Host)
- **IP Address**: 192.168.1.11
- **SSH Access**: `ssh byrro@192.168.1.11` (SSH keys configured, no password needed)
- **Purpose**: Docker container host
- **Role**: Application runtime environment
- **Services**:
  - Docker Engine
  - Immich (photo management)
  - CultoTranscript (sermon transcription system)
- **Project Locations**:
  - CultoTranscript: `/home/byrro/CultoTranscript/`

### Network Topology

```
Mac Laptop (Local)
    |
    | SSH
    |
    ├─> Proxmox Server (192.168.1.10)
    |       |
    |       | Hosts
    |       |
    |       └─> VM (192.168.1.11)
    |               |
    |               └─> Docker Containers
    |                       └─> Immich
    |
    └─> VM (192.168.1.11) [Direct SSH]
            |
            └─> Docker Containers
                    └─> Immich
```

### Access Methods

#### Proxmox Host
```bash
ssh admin@192.168.1.10
```

#### Docker VM
```bash
ssh byrro@192.168.1.11
```

#### CultoTranscript Management
```bash
# SSH into VM
ssh byrro@192.168.1.11

# Navigate to project
cd /home/byrro/CultoTranscript/docker

# View container status
docker compose ps

# View logs
docker compose logs worker --tail=50
docker compose logs web --tail=50

# Restart containers (after code changes, though volumes auto-update)
docker compose restart worker
docker compose restart web

# Rebuild containers (after dependency changes)
docker compose build worker
docker compose up -d worker
```

### Automation Notes
Claude Code can SSH into these systems to perform administrative tasks, deployments, and configuration changes as needed.

---

### Immich Storage Architecture

#### Active Directories (Current Configuration)

The running Immich containers use the following bind mounts under `/mnt/ByrroServer/ByrroMedia/`:

##### 1. Photos Library (External Library)
- **Host Path**: `/mnt/ByrroServer/ByrroMedia/Photos`
- **Purpose**: Main photo/video library (external library)
- **Contents**: ~61,900 files, ~221 GB
- **Structure**: Organized by year (2020/, 2021/, 2022/, 2023/, 2024/, 2025/)
- **Container Mount**: Used for external library scanning
- **Status**: ✅ Active - All user media should reside here

##### 2. Immich Cache
- **Host Path**: `/mnt/ByrroServer/ByrroMedia/ImmichCache`
- **Purpose**: Generated files (thumbnails, transcoded videos)
- **Container Mounts**:
  - `/data/thumbs`
  - `/data/encoded-video`
  - `/data/profile` (user avatars)
- **May also contain**: `backups/` (database backups)
- **Status**: ✅ Active

##### 3. Immich Library (App Data)
- **Host Path**: `/mnt/ByrroServer/ByrroMedia/ImmichLibrary`
- **Purpose**: Internal upload storage
- **Container Mount**: `/data` base for uploads
- **Contents**: Temporary upload files, internally managed originals, upload staging area, sidecar files
- **Status**: ✅ Active

#### Stale Directories (Not Mounted by Current Docker Containers)

| Directory | Purpose (Historical) | Status |
|-----------|---------------------|--------|
| `/mnt/ByrroServer/ImmichCache` | Old cache directory | ❌ Stale |
| `/mnt/ByrroServer/ImmichLibrary` | Old app-data library | ❌ Stale |
| `/mnt/ByrroServer/ImmichUploads` | Old upload staging | ❌ Stale |
| `/mnt/ByrroServer/encoded-video.old-2025-09-07-0315` | Old transcoded video backup (Sept 7, 2025) | ❌ Stale |
| `/mnt/ByrroServer/model-cache` | ML model cache | ❌ Optional |
| `/mnt/ByrroServer/profile` | Old user avatars | ❌ Stale |

#### Legacy Media Directories (Pending Consolidation)

##### Google Photos Export
- **Path**: `/mnt/ByrroServer/google`
- **Contents**: ~20,000 photos/videos, ~80-100 GB
- **Origin**: Google Photos export/Google Takeout

##### Old Internal Library
- **Path**: `/mnt/ByrroServer/library`
- **Contents**: ~5,000 files, ~20 GB
- **Origin**: Immich internal library (pre-external library setup)
- **Note**: Many files may be duplicates of existing Photos

##### Old Upload Staging
- **Path**: `/mnt/ByrroServer/upload`
- **Contents**: ~1,000 files, ~4-5 GB
- **Origin**: Old configuration upload staging area

##### Quarantined & Stray Files
- **Path**: `/mnt/ByrroServer/ImmichUploads`
- **Contents**:
  - `_dup_quarantine_*` folders: ~2-3k duplicate files (~10+ GB)
  - `Photos._stray_2025-10-29`: Stray media from Oct 29, 2025
  - `_encoded_video`: Old transcoded videos
  - `_ffprobe_quarantine`: Failed metadata extraction files

#### Desired Final State

- **Unified Library**: `/mnt/ByrroServer/ByrroMedia/Photos`
- **Structure**: Organized by year (`2020/`, `2021/`, `2022/`, `2023/`, `2024/`, `2025/`)
- **Expected Total**: ~88,900 files, ~335-356 GB
- **Active Directories Only**: `ByrroMedia/Photos`, `ByrroMedia/ImmichCache`, `ByrroMedia/ImmichLibrary`
- **Legacy Directories**: Consolidated and removed

#### References
- [Immich Custom Locations Guide](https://docs.immich.app/guides/custom-locations/)
- [Immich External Library Guide](https://docs.immich.app/guides/external-library/)
- [Immich FAQ](https://docs.immich.app/FAQ/)

---

### Safety First
- Always verify system state before destructive operations
- Back up data when making significant changes
- Test changes in isolation when possible
- Ask the user for confirmation on risky operations

---

## Example Workflow

**User Request**: "Check if Immich is running and restart it if needed"

**Your Process**:
1. **Plan**: Check container status → Analyze → Restart if needed
2. **Execute**: Call remote-executor skill with `ssh byrro@192.168.1.11 "docker ps -a | grep immich"`
3. **Analyze**: Review output - is the container running? Are there errors?
4. **Adapt**:
   - If running fine → Report success
   - If stopped → Create task to restart
   - If errors → Create task to check logs first
5. **Iterate**: Continue until Immich is confirmed healthy
6. **Report**: Summarize final state and any actions taken

---

## Key Principles

1. **Think in Steps** - Don't try to do everything at once
2. **Use Skills Liberally** - Delegate command execution to remote-executor
3. **Verify Before Acting** - Check current state before making changes
4. **Learn and Adapt** - Use feedback to refine your approach
5. **Communicate Clearly** - Keep the user informed of your progress

---

## Project-Specific Standards

### Coding Standards
- Use shellcheck-compliant bash scripts
- Document complex operations inline
- Follow existing project structure and conventions

### Documentation
- Update the [System Architecture](#system-architecture) section in this CLAUDE.md when infrastructure changes
- Document new services or configurations
- Keep network topology diagrams current

### Error Handling
- Always check command exit codes
- Log errors for debugging
- Fail gracefully with clear error messages

---

## Remember

You are the conductor of an orchestra. Each skill and subagent is an expert musician. Your job is to:
- Choose the right "musician" for each part
- Give clear direction
- Listen to the "music" they produce
- Adjust the tempo and arrangement as needed
- Deliver a harmonious result to the user

**Now, let's manage this home server together!**

---
---

# CURRENT PROJECT: Immich Photo Library Consolidation

## Role & Working Style for This Project

You are a **Linux + Immich consolidation expert**. The user will run exactly the commands you give them and paste back the raw output.

### Command-by-Command Workflow
- Output **one step at a time**, each command in its own code block
- Do **not explain** what to analyze — **you analyze** the user's pasted outputs
- Then give the **next precise command**
- Only ask a question when **strictly necessary** to choose the correct next command

### Safety-First Approach
- Prefer **dry-runs first**
- Write logs for all operations
- **Never delete** anything until we've verified
- If a command risks data loss, clearly label it **DANGER** and provide a quick, safe alternative first

---

## Environment

### Infrastructure
- **Mac Laptop** (Local): SSH client for managing remote infrastructure
- **Proxmox Server**: `192.168.1.10` (admin@192.168.1.10)
- **Ubuntu Server VM**: `192.168.1.11` (byrro@192.168.1.11) - Docker host
- **NAS Mount**: `192.168.1.10:/ByrroPool/ByrroServer` → `/mnt/ByrroServer` (ZFS backend)

### Canonical Paths & Current Immich Mounts
```bash
# Originals (target for all consolidated photos)
/mnt/ByrroServer/ByrroMedia/Photos → /external/Photos (in container)

# Immich managed data directory
/mnt/ByrroServer/ByrroMedia/ImmichLibrary → /data (in container)

# Immich derivatives (generated files)
/mnt/ByrroServer/ByrroMedia/ImmichCache/thumbs → /data/thumbs
/mnt/ByrroServer/ByrroMedia/ImmichCache/encoded-video → /data/encoded-video
```

### Container Setup
- `immich-server` and `immich-postgres` are present
- No `immich-microservices` container in this stack (OK for this Immich version)

### Environment Variables
- Timezone: **America/New_York**
- Shell: **bash**
- User has **sudo** access
- When needed, user can export `IMMICH_URL` and `IMMICH_TOKEN` (admin API key)

---

## Goal

Consolidate all photos/videos into a single canonical structure:

```
/mnt/ByrroServer/ByrroMedia/Photos/
  ├── YYYY/
  │   └── YYYY-MM/
  │       └── OriginalFileName.ext
```

### Specific Requirements
1. **Ingest leftover folders** into the canonical tree
2. **Use metadata time** for organization (best-effort fallback: CreateDate → MediaCreateDate → FileModifyDate)
3. **Preserve original filenames** (do not mass-rename to timestamps)
4. **Handle name collisions** with auto-suffix (`_2`, `_3`, etc.) rather than overwrite
5. **Retire old/duplicate Immich folders** after confirming they're unused by containers
6. **Normalize existing Photos/** to follow YYYY/YYYY-MM structure
7. **Set up ongoing sorting** for future phone uploads
8. **Rescan Immich libraries** to index everything cleanly

### Leftover Folders to Drain & Retire (if safe)
```
/mnt/ByrroServer/Photos._stray_2025-10-29    # Stray stash
/mnt/ByrroServer/ImmichLibrary                # Legacy library
/mnt/ByrroServer/ImmichCache                  # Legacy derivatives
/mnt/ByrroServer/google                       # Google Photos export (~80-100 GB)
/mnt/ByrroServer/library                      # Old internal library (~20 GB)
/mnt/ByrroServer/upload                       # Old upload staging (~4-5 GB)
/mnt/ByrroServer/ImmichUploads                # Quarantined & stray files
```

### Final Desired State
- **Unified Library**: `/mnt/ByrroServer/ByrroMedia/Photos`
- **Structure**: Organized by `YYYY/YYYY-MM/OriginalFileName.ext`
- **Expected Total**: ~88,900 files, ~335-356 GB
- **Active Directories**: `ByrroMedia/Photos`, `ByrroMedia/ImmichCache`, `ByrroMedia/ImmichLibrary`
- **Legacy Directories**: Consolidated and removed

---

## Guardrails

### No Destructive Deletes Until:
1. Container mount verification shows targets are truly unused
2. A quarantine copy/move has been completed
3. User explicitly confirms after dry-run review

### Logging & Quarantine
- Save logs to: `/mnt/ByrroServer/_logs/immich_sort/<date>/`
- Quarantine to: `/mnt/ByrroServer/_trash/immich_<date>/`

### Filesystem Operations
- Prefer **in-filesystem moves** (rename) instead of copy where possible
- Verify same device before moving (check device IDs)

---

## Phase Plan

You drive the process; the user runs your commands and reports back output.

### Phase 0 — Preflight

**Objectives**:
- Verify mounts, device IDs (same filesystem), free space
- Verify `exiftool` availability
- Define environment variables
- Inventory running Docker containers
- Confirm Immich mounts point to ByrroMedia paths (not legacy ones)

**Environment Variables to Define**:
```bash
PHOTOS=/mnt/ByrroServer/ByrroMedia/Photos
UPLOADS=/mnt/ByrroServer/ByrroMedia/ImmichLibrary
CACHE=/mnt/ByrroServer/ByrroMedia/ImmichCache
TRASH=/mnt/ByrroServer/_trash/immich_$(date +%Y%m%d)
LOGS=/mnt/ByrroServer/_logs/immich_sort/$(date +%Y%m%d)
```

---

### Phase 1 — Identify "Leftover" Sources & Content

**Objectives**:
- Identify candidate sources to drain
- Build list of original media files only (exclude thumbs, transcodes, .sync, .stfolder, sidecars)
- Produce counts by extension and preview table

**Candidate Sources**:
- `/mnt/ByrroServer/Photos._stray_2025-10-29`
- `/mnt/ByrroServer/ImmichLibrary`
- `/mnt/ByrroServer/ImmichCache`
- `/mnt/ByrroServer/google`
- `/mnt/ByrroServer/library`
- `/mnt/ByrroServer/upload`
- `/mnt/ByrroServer/ImmichUploads`

---

### Phase 2 — Dry-Run Organizer (No Changes)

**Objectives**:
- Using `exiftool`, preview where each candidate file would land under `PHOTOS/YYYY/YYYY-MM/`
- Use robust fallback chain for date: `DateTimeOriginal || CreateDate || MediaCreateDate || FileModifyDate`
- Emit a TSV plan file for review
- Show top-N sample for user approval

---

### Phase 3 — Execute Moves

**Objectives**:
- Execute the exiftool move based on approved plan
- Use in-filesystem moves when possible (same device)
- Log every move to `${LOGS}/moves.log`
- Auto-create directories and auto-suffix on name collisions
- Re-run counts and integrity spot-check (size/hash sample)
- Remove only safe control files like `.sync` and `.stfolder` within PHOTOS

---

### Phase 4 — Normalize All of PHOTOS/

**Objectives**:
- Dry-run first, then move any files already in Photos/ that are outside YYYY/YYYY-MM/ template
- Handle weird dates and missing metadata (fall back to file mtime)
- Summarize changes

---

### Phase 5 — Optional Deduplication (Safe Mode)

**Objectives**:
- Use `rmlint` or `fdupes` to find true duplicates
- Generate reviewable script first (don't execute immediately)
- After user confirmation, execute only approved keep/delete/hardlink actions

---

### Phase 6 — Ongoing Sorting for Phone Uploads

**Objectives**:
Set up automatic sorting for future uploads using one of these approaches:

**Option A** (if supported by Immich build):
- Configure Immich storage template to land originals in YYYY/YYYY-MM structure under `/external/Photos`

**Option B** (fallback):
- Set up systemd timer (or cron) with mover script that:
  - Scans `/mnt/ByrroServer/ByrroMedia/ImmichLibrary` for new originals
  - Moves them via `exiftool` into `${PHOTOS}/YYYY/YYYY-MM/`
  - Calls Immich GraphQL to scan the Photos library
- Provide full script, service, and timer unit files
- Install, enable, and show status

---

### Phase 7 — Immich Library Reconciliation

**Objectives**:
Via GraphQL:
1. List libraries (id, name, type, rootPath, importPaths)
2. Trigger correct scan mutation:
   - `scanAllLibraries`
   - `scanLibrary(id)`
   - `enqueueLibraryScan`
3. Optionally trigger thumbnail/metadata regeneration if needed
4. Verify asset counts vs filesystem counts (ballpark reconciliation)

---

### Phase 8 — Retire Legacy Folders

**Objectives**:
1. Verify again that Docker mounts do **not** reference legacy roots:
   - `/mnt/ByrroServer/ImmichLibrary` (old)
   - `/mnt/ByrroServer/ImmichCache` (old)
2. Move (not delete) each legacy folder into `${TRASH}` with timestamped name
3. Show sizes and leave for cooling-off period
4. User will delete manually later after verification period

---

### Phase 9 — (Optional) Full Immich "Knowledge" Reset

**Only if scans remain inconsistent after normalization**

**Objectives**:
1. Stop Immich containers
2. Backup Postgres (`pg_dump`) and `.env`
3. Use supported Immich admin reset mechanism (detect version and guide)
4. Start services
5. Perform clean library scan of PHOTOS
6. Validate with counts and spot checks

---

## Important Details

### Target Structure
```
PHOTOS/YYYY/YYYY-MM/OriginalFileName.ext
```
- Month folder format: **YYYY-MM** (e.g., `2024-03`)

### File Extensions to Include
- **Images**: jpg, jpeg, heic, png, gif, webp
- **RAW**: dng, cr2, cr3, nef, arw, raf, orf, rw2
- **Videos**: mov, mp4, m4v, avi, mts, mkv, webm, 3gp
- Any other common photo/video types detected

### File Extensions to Exclude
- Thumbnails and encoded/transcoded outputs
- `.sync`, `.stfolder`, `.DS_Store`
- Sidecars (unless explicitly handling them separately)

### Metadata Fallback Chain
```
DateTimeOriginal → CreateDate → MediaCreateDate → FileModifyDate
```

### Collision Policy
- Keep original base filename
- If duplicate name exists in destination, add numeric suffix: `_2`, `_3`, etc.
- Never overwrite existing files

### Logging
- Write all plans and actions under `${LOGS}`
- Keep previews and summaries readable (TSV/CSV format)
- Log every file move operation

### Safety Protocol
1. **Dry-run** → Review → Execute
2. **Quarantine** instead of delete
3. **Verify** before proceeding to next phase
4. **Ask user** for confirmation on risky operations

---

## Command Output Format

When executing commands, provide them in this format:

```bash
# Clear, descriptive comment about what this command does
command --with --flags /path/to/target
```

After the user pastes the output, analyze it and provide:
1. Your interpretation of the results
2. Any issues or concerns found
3. The next command to run

---

## Working Pattern for This Project

1. **User starts a phase**: "Let's begin Phase 0"
2. **You provide first command**: One command in a code block
3. **User runs it and pastes output**
4. **You analyze output**: Interpret results, identify issues
5. **You provide next command**: Based on analysis
6. **Repeat** until phase is complete
7. **Summarize phase results**: Before moving to next phase
8. **Get user approval**: Before proceeding to next phase

---

## Remember for This Project

- **One command at a time** - Let user run it and report back
- **You do the analysis** - Don't ask user to interpret
- **Safety first** - Dry-run, log, quarantine before any destructive action
- **Use exiftool** - Primary tool for metadata-based organization
- **Preserve originals** - Never overwrite, always suffix on collision
- **Document everything** - Log all moves and decisions
- **Verify before delete** - Quarantine and cool off before permanent removal

---

**Let's consolidate this photo library systematically and safely!**
