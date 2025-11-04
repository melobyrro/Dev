# CultoTranscript - Development Guide

## Quick Start

### Local Development

The project uses Docker containers with volume mounts for live development.

**Project Location**: `~/Dev/CultoTranscript` (local) or `~/CultoTranscript` (production)

## When to Restart Containers

### ⚠️ IMPORTANT: Always restart containers after making changes!

Different types of changes require different restart strategies:

### 1. Template/HTML Changes (`.html` files)

**Files affected**: `app/web/templates/**/*.html`

**Restart command**:
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web"
# OR locally:
docker restart culto_web
```

**Why**: Jinja2 templates are cached. FastAPI needs to reload them.

**Examples**:
- Modified `base.html` CSS
- Changed `login.html` layout
- Updated `index.html` structure

### 2. Python Code Changes

**Files affected**: `app/**/*.py`

**Restart command**:
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web culto_worker"
# OR locally:
docker restart culto_web culto_worker
```

**Why**: Python modules are loaded at startup.

**Examples**:
- Modified routes in `app/web/routes/`
- Changed models in `app/common/models.py`
- Updated worker logic in `app/worker/`

### 3. Configuration Changes

**Files affected**: `.env`

**Restart command**:
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web culto_worker culto_scheduler"
# OR locally:
docker restart culto_web culto_worker culto_scheduler
```

**Why**: Environment variables are read at container startup.

**Examples**:
- Changed `GEMINI_API_KEY`
- Modified `WHISPER_MODEL_SIZE`
- Updated `MAX_VIDEO_DURATION`

### 4. Dockerfile Changes

**Files affected**: `docker/*.Dockerfile`, `docker/docker-compose.yml`

**Rebuild command**:
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "cd ~/CultoTranscript && docker compose -f docker/docker-compose.yml up -d --build"
# OR locally:
cd docker
docker-compose up -d --build
```

**Why**: Container images need to be rebuilt.

### 5. Database Schema Changes

**Files affected**: `migrations/*.sql`

**Migration command**:
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker exec culto_web alembic upgrade head"
# OR locally:
docker exec culto_web alembic upgrade head
```

**Then restart**:
```bash
docker restart culto_web culto_worker
```

## Development Workflow

### Making UI/UX Changes

1. **Edit template files locally**:
   ```bash
   code app/web/templates/base.html
   ```

2. **Restart web container** (REQUIRED):
   ```bash
   ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web"
   ```

3. **Clear browser cache and refresh**:
   - Chrome/Edge: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
   - Firefox: `Cmd+Shift+R` or `Ctrl+F5`

4. **Verify changes**:
   - Open https://church.byrroserver.com
   - Check that your changes are visible

### Making Backend Changes

1. **Edit Python files locally**:
   ```bash
   code app/web/routes/videos.py
   ```

2. **Restart affected containers**:
   ```bash
   ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web culto_worker"
   ```

3. **Check logs for errors**:
   ```bash
   ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker logs --tail 50 culto_web"
   ```

### Testing Changes Locally

If you want to test locally before pushing to production:

1. **Start local containers**:
   ```bash
   cd ~/Dev/CultoTranscript/docker
   docker-compose up -d
   ```

2. **Access locally**:
   - Open http://localhost:8000

3. **Make changes and restart**:
   ```bash
   docker restart culto_web
   ```

4. **When satisfied, push to production**:
   ```bash
   git add .
   git commit -m "Updated UI/UX"
   git push

   # Then on server:
   ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "cd ~/CultoTranscript && git pull && docker restart culto_web"
   ```

## Common Development Tasks

### View Live Logs

```bash
# Web service
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker logs -f culto_web"

# Worker service
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker logs -f culto_worker"
```

### Check Container Status

```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker ps | grep culto"
```

### Access Container Shell

```bash
# Web container
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker exec -it culto_web bash"

# Database
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker exec -it culto_db psql -U culto_admin -d culto"
```

### Clear Redis Queue

```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker exec culto_redis redis-cli FLUSHALL"
```

## Debugging Tips

### 1. Template Not Updating

**Problem**: Changed HTML but see old version

**Solution**:
1. Restart container: `docker restart culto_web`
2. Hard refresh browser: `Cmd+Shift+R`
3. Check file was saved
4. Verify volume mount in docker-compose.yml

### 2. Python Changes Not Applied

**Problem**: Modified Python code but behavior unchanged

**Solution**:
1. Confirm file is saved
2. Restart: `docker restart culto_web culto_worker`
3. Check logs: `docker logs culto_web`
4. Look for syntax errors

### 3. Environment Variable Not Working

**Problem**: Changed .env but value not updated

**Solution**:
1. Verify .env location (should be in project root)
2. Restart ALL services: `docker restart culto_web culto_worker culto_scheduler`
3. Check variable: `docker exec culto_web env | grep YOUR_VAR`

## Quick Reference

### SSH Command
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11
```

### Restart Web Only (Templates/CSS)
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web"
```

### Restart All Services
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "docker restart culto_web culto_worker culto_scheduler"
```

### Full Rebuild
```bash
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11 "cd ~/CultoTranscript && docker compose -f docker/docker-compose.yml up -d --build"
```

## Development Checklist

After making changes:
- [ ] Files saved
- [ ] Container(s) restarted
- [ ] Browser cache cleared
- [ ] Changes verified in browser
- [ ] Logs checked for errors
- [ ] Committed to git
- [ ] Pushed to remote (if applicable)

## See Also

- [README.md](README.md) - Project overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture

---

**Remember**: Always restart containers after making changes! 🔄
