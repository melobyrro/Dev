# Database Schema Fix - Instructions

## Problem Summary

Your database is missing two required columns in the `transcripts` table:
- `confidence_score` (FLOAT)
- `audio_quality` (VARCHAR)

This is causing the error:
```
psycopg2.errors.UndefinedColumn) column "confidence_score" of relation "transcripts" does not exist
```

## Root Cause

Your database was initialized with `001_initial_schema.sql` but the `003_advanced_analytics.sql` migration was never run. This migration adds the missing columns.

## Solution

I've created migration file `004_fix_missing_transcript_columns.sql` to add these columns.

### Option 1: Run via Docker (Recommended)

If your database is running in Docker containers:

```bash
cd /Users/andrebyrro/Dev/CultoTranscript

# Make sure Docker containers are running
cd docker
docker-compose up -d

# Go back to project root
cd ..

# Run the migration script
./RUN_THIS_MIGRATION.sh
```

### Option 2: Run SQL directly in Docker

```bash
# Execute SQL directly in the database container
docker exec -i culto_db psql -U culto_admin -d culto < migrations/004_fix_missing_transcript_columns.sql
```

### Option 3: Run SQL manually with psql

If you have psql installed and database is accessible on localhost:

```bash
psql -h localhost -U culto_admin -d culto -f migrations/004_fix_missing_transcript_columns.sql
```

### Option 4: Run Python script

If database is accessible on localhost:5432:

```bash
python3 fix_db_simple.py
```

## Verification

After running the migration, verify the columns were added:

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'transcripts'
AND column_name IN ('confidence_score', 'audio_quality');
```

Expected output:
```
  column_name    | data_type |    column_default
-----------------+-----------+---------------------
 confidence_score| double precision | 0.0
 audio_quality   | character varying | 'medium'::character varying
```

## After Migration

1. Restart your worker container:
   ```bash
   cd docker
   docker-compose restart worker
   ```

2. Re-process the failed video - it should now work correctly with auto-captions

## Additional Fix Applied

I've also improved the VTT parser in `/Users/andrebyrro/Dev/CultoTranscript/app/worker/yt_dlp_service.py` to:
- Filter out VTT metadata headers (Kind:, Language:, etc.)
- Remove sound annotations like [Música], [Aplausos]
- Clean invalid Unicode characters
- Deduplicate repeated caption lines

This will prevent the "Kind: captions Language: pt [Música] เ" issue you were seeing.

## Need Help?

If you encounter any issues:
1. Check if Docker is running: `docker ps`
2. Check if database container is up: `docker ps | grep culto_db`
3. View database logs: `docker logs culto_db`
4. View worker logs: `docker logs culto_worker`
