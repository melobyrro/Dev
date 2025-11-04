# Database Inspector Skill

## Purpose
Query the PostgreSQL database to inspect video, job, and transcript records, extract error details, and clean up test data between retry attempts.

## MCP Servers Used
- None (uses Docker exec with psql)

## Instructions

You are the database inspector for CultoTranscript. You interact with the PostgreSQL database to query and manage test data.

### Database Connection
```bash
# Connect to database via Docker:
docker exec -i cultotranscript-db psql -U culto_admin -d culto -c "YOUR_SQL_QUERY"
```

### Common Operations

#### 1. Check Video Status
```sql
SELECT
  v.id,
  v.youtube_id,
  v.title,
  v.status,
  v.duration_sec,
  v.has_auto_cc,
  v.error_message,
  v.ingested_at,
  t.source as transcript_source,
  t.word_count,
  t.char_count
FROM videos v
LEFT JOIN transcripts t ON t.video_id = v.id
WHERE v.youtube_id = 'b7PzpfbqcJs';
```

#### 2. Check Job Status
```sql
SELECT
  j.id,
  j.job_type,
  j.status,
  j.priority,
  j.video_id,
  j.error_message,
  j.started_at,
  j.completed_at,
  j.metadata,
  EXTRACT(EPOCH FROM (j.completed_at - j.started_at)) as processing_seconds
FROM jobs j
WHERE j.video_id IN (
  SELECT id FROM videos WHERE youtube_id = 'b7PzpfbqcJs'
)
ORDER BY j.created_at DESC
LIMIT 5;
```

#### 3. Get Transcript Details
```sql
SELECT
  t.id,
  t.video_id,
  t.source,
  t.word_count,
  t.char_count,
  t.confidence_score,
  t.audio_quality,
  LEFT(t.text, 200) as text_preview,
  t.created_at
FROM transcripts t
WHERE t.video_id IN (
  SELECT id FROM videos WHERE youtube_id = 'b7PzpfbqcJs'
);
```

#### 4. Clean Up Test Video (DESTRUCTIVE)
```sql
-- This will CASCADE delete from transcripts, verses, themes, jobs
DELETE FROM videos WHERE youtube_id = 'b7PzpfbqcJs';

-- Also clean up excluded_videos if present
DELETE FROM excluded_videos WHERE youtube_id = 'b7PzpfbqcJs';

-- Verify deletion
SELECT COUNT(*) FROM videos WHERE youtube_id = 'b7PzpfbqcJs';
```

#### 5. Check Recent Errors
```sql
SELECT
  v.youtube_id,
  v.title,
  v.status as video_status,
  v.error_message as video_error,
  j.status as job_status,
  j.error_message as job_error,
  j.completed_at
FROM videos v
LEFT JOIN jobs j ON j.video_id = v.id
WHERE v.status = 'failed' OR j.status = 'failed'
ORDER BY j.completed_at DESC
LIMIT 10;
```

#### 6. Check Database Health
```sql
-- Count records
SELECT
  'videos' as table_name, COUNT(*) as count FROM videos
UNION ALL
SELECT 'transcripts', COUNT(*) FROM transcripts
UNION ALL
SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL
SELECT 'channels', COUNT(*) FROM channels;

-- Check for orphaned records
SELECT COUNT(*) as orphaned_transcripts
FROM transcripts t
LEFT JOIN videos v ON v.id = t.video_id
WHERE v.id IS NULL;
```

### Task: Inspect Test Video

When invoked with `youtube_id='b7PzpfbqcJs'`, perform:

1. Query video status
2. Query associated jobs
3. Query transcript (if exists)
4. Extract error messages from both video and job records
5. Return structured report

## Expected Output

### Video Found - Completed:
```json
{
  "video_found": true,
  "video_id": 456,
  "youtube_id": "b7PzpfbqcJs",
  "status": "completed",
  "title": "Example Sermon Title",
  "duration_sec": 1800,
  "has_auto_cc": true,
  "transcript": {
    "exists": true,
    "source": "auto_cc",
    "word_count": 2340,
    "char_count": 15678,
    "text_preview": "Irmãos e irmãs, hoje vamos falar sobre..."
  },
  "latest_job": {
    "job_id": 123,
    "status": "completed",
    "processing_seconds": 45.3,
    "error_message": null
  }
}
```

### Video Found - Failed:
```json
{
  "video_found": true,
  "video_id": 456,
  "youtube_id": "b7PzpfbqcJs",
  "status": "failed",
  "title": "Example Sermon Title",
  "duration_sec": 1800,
  "error_message": "yt-dlp download failed: HTTP Error 429: Too Many Requests",
  "transcript": {
    "exists": false
  },
  "latest_job": {
    "job_id": 123,
    "status": "failed",
    "processing_seconds": 120.5,
    "error_message": "yt-dlp download failed: HTTP Error 429: Too Many Requests"
  },
  "diagnosis": "Rate-limited by YouTube - need to implement retry with backoff"
}
```

### Video Not Found:
```json
{
  "video_found": false,
  "youtube_id": "b7PzpfbqcJs",
  "message": "No records found for this video ID"
}
```

## Task: Clean Test Video

When invoked with `action='clean'` and `youtube_id='b7PzpfbqcJs'`:

1. Run DELETE query (with CASCADE)
2. Verify deletion
3. Return confirmation

Output:
```json
{
  "cleaned": true,
  "youtube_id": "b7PzpfbqcJs",
  "deleted_video": true,
  "deleted_transcripts": 1,
  "deleted_jobs": 2,
  "message": "Test video and all related records deleted successfully"
}
```

## Error Handling

- **Connection refused**: Database container not running - run `docker-compose up -d db`
- **Authentication failed**: Check POSTGRES_USER and POSTGRES_PASSWORD in .env
- **Table does not exist**: Run database migrations first
- **Syntax error**: Check SQL query syntax

## Safety Notes

- The CLEAN operation is DESTRUCTIVE
- Only clean test videos, never production data
- Always verify youtube_id before deletion
- CASCADE deletes will remove transcripts, jobs, verses, themes automatically
