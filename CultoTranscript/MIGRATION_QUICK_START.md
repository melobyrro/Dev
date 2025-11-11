# Quick Start: Sermon Date Prefix Migration

## TL;DR

This migration adds permanent date prefixes to all video titles in the database.

**Format**: `MM/DD/YYYY - [Original Title]`

**Example**: `03/15/2024 - Culto de Domingo`

---

## Prerequisites

- Docker and docker-compose installed
- CultoTranscript application running
- Database backup (will be created in step 1)

---

## Step-by-Step Guide

### Step 1: Backup Database (REQUIRED)

```bash
docker-compose exec culto_db pg_dump -U culto_admin -d culto > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: Rebuild Application

```bash
docker-compose up -d --build
```

### Step 3: Run Tests (Optional but Recommended)

```bash
docker-compose exec culto_web python test_date_helpers_standalone.py
```

**Expected Output**:
```
======================================================================
✓ ALL TESTS PASSED!
======================================================================
```

### Step 4: Run Migration Script

```bash
docker-compose exec culto_web python scripts/update_video_titles_with_dates.py
```

**Expected Output**:
```
2025-11-10 12:00:00 - INFO - Starting video title migration...
2025-11-10 12:00:00 - INFO - Found 150 videos to process
2025-11-10 12:00:01 - INFO - [1/150] Updating video 1
2025-11-10 12:00:01 - INFO -   Old: Culto de Domingo
2025-11-10 12:00:01 - INFO -   New: 03/15/2024 - Culto de Domingo
...
2025-11-10 12:00:10 - INFO - Migration complete!
2025-11-10 12:00:10 - INFO -   Total videos: 150
2025-11-10 12:00:10 - INFO -   Updated: 145
2025-11-10 12:00:10 - INFO -   Skipped: 5
```

### Step 5: Verify Results

```bash
# Check database
docker-compose exec culto_db psql -U culto_admin -d culto -c "SELECT id, title FROM videos ORDER BY id LIMIT 5;"

# Expected output format:
#  id |            title
# ----+------------------------------
#   1 | 03/15/2024 - Culto de Domingo
#   2 | 03/22/2024 - Pregação Especial
#   3 | 03/29/2024 - Louvor e Adoração
```

### Step 6: Test Web Interface

1. Open http://localhost:8000/ (or https://church.byrroserver.com for production)
2. Verify video titles show dates
3. Check that monthly grouping works
4. Test video detail pages

### Step 7: Test New Video Ingestion

1. Submit a new test video via web UI
2. Wait for processing to complete
3. Verify the title has date prefix
4. Check that no duplicate dates appear

---

## Rollback (If Needed)

If something goes wrong:

```bash
# Restore from backup
docker-compose exec -T culto_db psql -U culto_admin -d culto < backup_YYYYMMDD_HHMMSS.sql

# Rebuild services
docker-compose up -d --build
```

---

## Troubleshooting

### Migration Script Fails

**Check logs**:
```bash
docker-compose logs culto_web
```

**Common issues**:
- Database connection timeout → Restart database container
- Permission denied → Ensure script is executable: `chmod +x scripts/update_video_titles_with_dates.py`
- Import error → Rebuild containers: `docker-compose up -d --build`

### Videos Without Dates

Some videos may be skipped if they don't have `sermon_actual_date`. This is expected for:
- Very old videos imported before this field was added
- Videos that failed processing

**To fix**:
```sql
-- Check videos without sermon_actual_date
docker-compose exec culto_db psql -U culto_admin -d culto -c "SELECT id, title, published_at FROM videos WHERE sermon_actual_date IS NULL;"

-- Manually set sermon_actual_date if needed
docker-compose exec culto_db psql -U culto_admin -d culto -c "UPDATE videos SET sermon_actual_date = published_at::date WHERE sermon_actual_date IS NULL AND published_at IS NOT NULL;"

-- Re-run migration
docker-compose exec culto_web python scripts/update_video_titles_with_dates.py
```

### Duplicate Dates in Titles

If you see titles like "03/15/2024 - 03/15/2024 - Culto":

1. Check if migration was run multiple times
2. Restore from backup
3. Re-run migration once

The helper functions should prevent this, but if it happens:

```bash
# Restore from backup
docker-compose exec -T culto_db psql -U culto_admin -d culto < backup_YYYYMMDD_HHMMSS.sql
```

---

## Production Deployment

For production server (church.byrroserver.com):

```bash
# SSH to server
ssh your_server

# Navigate to project
cd /path/to/CultoTranscript

# Pull latest changes
git pull

# Follow steps 1-7 above
```

---

## Support

For issues or questions, check:

1. **Implementation Report**: `SERMON_DATE_PREFIX_IMPLEMENTATION_REPORT.md`
2. **Application Logs**: `docker-compose logs -f culto_web culto_worker`
3. **Database State**: `docker-compose exec culto_db psql -U culto_admin -d culto`

---

**Last Updated**: 2025-11-10
