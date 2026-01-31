# CultoTranscript - Deployment Guide

## Production Status

✅ **Live at**: https://church.byrroserver.com
🖥️ **Server**: 192.168.1.11 (byrro@192.168.1.11)
📁 **Location**: ~/CultoTranscript
🔐 **Reverse Proxy**: Caddy with Cloudflare DNS + Let's Encrypt

## Quick Access

```bash
# SSH into server
ssh -i ~/.ssh/id_ed25519 byrro@192.168.1.11

# View containers
docker ps | grep culto

# Check logs
docker logs --tail 50 culto_web
docker logs --tail 50 culto_worker

# Restart services
docker restart culto_web culto_worker culto_scheduler
```

## Architecture

**5 Docker Containers**:
- `culto_web` - FastAPI (port 8000)
- `culto_worker` - Transcription processor
- `culto_scheduler` - Channel monitor
- `culto_db` - PostgreSQL 16 + pgvector
- `culto_redis` - Redis 7 queue

**Networks**:
- `docker_culto_network` - Internal services
- `byrro-net` - Caddy reverse proxy access

**Reverse Proxy**: Existing Caddy container
- Config: `/mnt/ByrroServer/docker-data/caddy/Caddyfile`
- Added: `church.byrroserver.com { reverse_proxy culto_web:8000 }`
- HTTPS: Auto via Cloudflare DNS challenge

## Initial Setup (New Installation)

### 1. Clone & Configure

```bash
cd ~
git clone <repository-url> CultoTranscript
cd CultoTranscript
cp .env.example .env
nano .env
```

Update:
```bash
POSTGRES_PASSWORD=<secure-password>
INSTANCE_PASSWORD=<admin-password>
SECRET_KEY=$(openssl rand -hex 32)
GEMINI_API_KEY=<your-gemini-api-key>
```

### 2. Start Services

```bash
docker compose -f docker/docker-compose.yml up -d
docker ps | grep culto
```

### 3. Run Migrations

```bash
docker exec culto_web alembic upgrade head
```

### 4. Connect to Caddy (if not already connected)

```bash
docker network connect byrro-net culto_web
```

### 5. Configure DNS

Add A record in Cloudflare:
- **Name**: church
- **Content**: <server-public-ip>

### 6. Add to Caddyfile

Append to `/mnt/ByrroServer/docker-data/caddy/Caddyfile`:

```caddy
# --- Church Services ---
church.byrroserver.com {
	import common
	reverse_proxy culto_web:8000
}
```

Then reload:
```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Updating Production

### Code Updates

```bash
cd ~/CultoTranscript
git pull
docker compose -f docker/docker-compose.yml restart

# Or full rebuild if Dockerfile changed:
docker compose -f docker/docker-compose.yml up -d --build
```

### Database Migrations

```bash
docker exec culto_web alembic upgrade head
```

### Environment Changes

```bash
nano ~/CultoTranscript/.env
docker restart culto_web culto_worker
```

## Monitoring & Troubleshooting

### Check Health

```bash
# Container status
docker ps --filter name=culto

# Resource usage
docker stats --no-stream | grep culto

# Disk space
df -h
docker system df
```

### Common Issues

#### 1. Worker Not Processing

**Symptoms**: Videos stuck in "queued"

**Fix**:
```bash
docker logs culto_worker
docker restart culto_worker
```

#### 2. Gemini API Errors

**Symptoms**: "Analytics failed"

**Fix**:
```bash
# Check API key
docker exec culto_web env | grep GEMINI

# Restart services
docker restart culto_web culto_worker
```

#### 3. HTTPS Certificate Issues

**Symptoms**: SSL errors

**Fix**:
```bash
# Check DNS
nslookup church.byrroserver.com

# Check Caddy logs
docker logs caddy | grep church

# Reload Caddy
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

#### 4. Database Connection Errors

**Fix**:
```bash
docker restart culto_db
sleep 10
docker restart culto_web culto_worker
```

#### 5. Out of Disk Space

**Fix**:
```bash
docker system prune -a --volumes
```

### View Logs

```bash
# Real-time logs
docker logs -f culto_web
docker logs -f culto_worker

# Last 100 lines
docker logs --tail 100 culto_web

# With timestamps
docker logs --timestamps culto_worker

# Search for errors
docker logs culto_worker | grep -i error
```

## Backup & Recovery

### Database Backup

```bash
# Create backup
docker exec culto_db pg_dump -U culto_admin culto > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker exec -i culto_db psql -U culto_admin -d culto
```

### Automated Backups

Create `/home/byrro/backup-culto.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/byrro/culto-backups"
mkdir -p $BACKUP_DIR
docker exec culto_db pg_dump -U culto_admin culto | gzip > "$BACKUP_DIR/db_$(date +%Y%m%d).sql.gz"
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete
```

Add to crontab:
```bash
chmod +x /home/byrro/backup-culto.sh
crontab -e
# Add: 0 2 * * * /home/byrro/backup-culto.sh
```

## Performance Tuning

### Scale Workers

```bash
docker compose -f docker/docker-compose.yml up -d --scale worker=3
```

Note: Each worker uses ~2GB RAM

### Database Optimization

```bash
docker exec culto_db psql -U culto_admin -d culto -c "VACUUM ANALYZE;"
```

## Security Checklist

- [ ] Changed POSTGRES_PASSWORD from default
- [ ] Changed INSTANCE_PASSWORD from default
- [ ] Generated new SECRET_KEY
- [ ] Configured firewall (ports 80, 443, 22 only)
- [ ] API keys stored securely
- [ ] Backup script configured
- [ ] HTTPS working with valid certificate

## Rollback Procedure

```bash
cd ~/CultoTranscript
docker compose -f docker/docker-compose.yml down
git log --oneline  # Find previous commit
git checkout <commit-hash>
docker compose -f docker/docker-compose.yml up -d --build
```

## Production Checklist

Before going live:

- [ ] .env configured with production values
- [ ] Gemini API key set and tested
- [ ] DNS record created and propagated
- [ ] HTTPS certificate provisioned
- [ ] Firewall configured
- [ ] Backup script configured
- [ ] Test transcription completed
- [ ] Test analytics V2 completed
- [ ] Chatbot tested

## Useful Commands

```bash
# Restart all services
docker restart culto_web culto_worker culto_scheduler

# View resource usage
docker stats

# Clean up
docker system prune -a

# Check queue depth
docker exec culto_redis redis-cli LLEN transcription_queue

# Recent job stats
docker exec culto_db psql -U culto_admin -d culto -c "SELECT status, COUNT(*) FROM jobs WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY status;"
```

## Support

**Logs**: `docker logs <container>`
**Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
**Changelog**: See [CHANGELOG.md](CHANGELOG.md)

**Troubleshooting Steps**:
1. Check container logs
2. Verify environment variables
3. Test network connectivity
4. Review this guide
5. Open GitHub issue with error details

---

**Last Updated**: 2025-11-03
**Production URL**: https://church.byrroserver.com
**Status**: ✅ Live
