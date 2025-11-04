# Log Analyzer Skill

## Purpose
Monitor and analyze Docker container logs to identify errors, exceptions, and diagnostic information during transcription job processing.

## MCP Servers Used
- None (uses Docker logs commands)

## Instructions

You are the log analyzer for CultoTranscript. You monitor Docker container logs to diagnose issues in real-time.

### Container Names
- `cultotranscript-web` - FastAPI web service
- `cultotranscript-worker` - Transcription worker
- `cultotranscript-scheduler` - Channel monitoring scheduler
- `cultotranscript-db` - PostgreSQL database
- `cultotranscript-redis` - Redis queue

### Common Operations

#### 1. Stream Worker Logs (Real-time)
```bash
# Follow logs from worker container
docker logs -f --tail 100 cultotranscript-worker
```

#### 2. Get Recent Worker Logs
```bash
# Get last 200 lines from worker
docker logs --tail 200 cultotranscript-worker
```

#### 3. Search for Errors
```bash
# Find ERROR level messages
docker logs cultotranscript-worker 2>&1 | grep -i "ERROR"

# Find exceptions and tracebacks
docker logs cultotranscript-worker 2>&1 | grep -A 10 -i "exception\|traceback"

# Find specific error patterns
docker logs cultotranscript-worker 2>&1 | grep -i "yt-dlp\|whisper\|transcript_api\|ffmpeg"
```

#### 4. Get Logs for Specific Time Range
```bash
# Logs since 5 minutes ago
docker logs --since 5m cultotranscript-worker

# Logs from specific timestamp
docker logs --since "2025-11-02T10:00:00" cultotranscript-worker
```

#### 5. Check All Services Health
```bash
# Check if containers are running
docker ps --filter name=cultotranscript

# Quick log check for all services
for service in web worker scheduler db redis; do
  echo "=== cultotranscript-$service ==="
  docker logs --tail 5 cultotranscript-$service 2>&1
done
```

#### 6. Search for YouTube Video ID in Logs
```bash
# Find logs related to specific video
docker logs cultotranscript-worker 2>&1 | grep -i "b7PzpfbqcJs"
```

### Task: Monitor Job Processing

When monitoring a transcription job with `youtube_id='b7PzpfbqcJs'`:

1. Start following worker logs
2. Watch for key events:
   - Job picked from queue
   - Video metadata extraction
   - Tier 1: yt-dlp auto-CC attempt
   - Tier 2: youtube-transcript-api attempt
   - Tier 3: faster-whisper attempt
   - Success or failure messages
3. Capture error messages, stack traces, and diagnostic info
4. Return structured analysis

## Expected Output

### Success Pattern:
```
INFO - Processing job 123: transcribe_video
INFO - Extracting video info for b7PzpfbqcJs
INFO - Video: "Example Sermon" (1800 seconds)
INFO - Attempting tier 1: yt-dlp auto-CC
INFO - Successfully extracted auto-captions (2340 words)
INFO - Transcript saved with source: auto_cc
INFO - Job 123 completed successfully
```

Parsed output:
```json
{
  "job_id": 123,
  "youtube_id": "b7PzpfbqcJs",
  "status": "completed",
  "successful_tier": 1,
  "tier_used": "auto_cc",
  "word_count": 2340,
  "processing_steps": [
    "Job picked from queue",
    "Video metadata extracted",
    "Tier 1 (auto-CC): SUCCESS"
  ],
  "errors": []
}
```

### Failure Pattern - Tier 1 Fails, Tier 2 Succeeds:
```
INFO - Processing job 123: transcribe_video
INFO - Extracting video info for b7PzpfbqcJs
INFO - Video: "Example Sermon" (1800 seconds)
INFO - Attempting tier 1: yt-dlp auto-CC
WARNING - Tier 1 failed: No auto-generated captions found
INFO - Attempting tier 2: youtube-transcript-api
INFO - Successfully extracted transcript via API (2180 words)
INFO - Transcript saved with source: transcript_api
INFO - Job 123 completed successfully
```

Parsed output:
```json
{
  "job_id": 123,
  "youtube_id": "b7PzpfbqcJs",
  "status": "completed",
  "successful_tier": 2,
  "tier_used": "transcript_api",
  "word_count": 2180,
  "processing_steps": [
    "Job picked from queue",
    "Video metadata extracted",
    "Tier 1 (auto-CC): FAILED - No auto-generated captions found",
    "Tier 2 (transcript-api): SUCCESS"
  ],
  "warnings": [
    "Tier 1 fallback occurred"
  ],
  "errors": []
}
```

### Complete Failure Pattern:
```
INFO - Processing job 123: transcribe_video
INFO - Extracting video info for b7PzpfbqcJs
INFO - Video: "Example Sermon" (1800 seconds)
INFO - Attempting tier 1: yt-dlp auto-CC
WARNING - Tier 1 failed: No auto-generated captions found
INFO - Attempting tier 2: youtube-transcript-api
ERROR - Tier 2 failed: NoTranscriptFound - No transcripts available
INFO - Attempting tier 3: faster-whisper
INFO - Downloading audio with yt-dlp...
ERROR - yt-dlp download failed: HTTP Error 403: Forbidden
ERROR - Job 123 failed: Unable to download audio for transcription
Traceback (most recent call last):
  File "/app/worker/transcription_service.py", line 145, in process_video
    audio_path = self.yt_dlp.download_audio(url, tmpdir)
  File "/app/worker/yt_dlp_service.py", line 89, in download_audio
    raise Exception(f"yt-dlp download failed: {str(e)}")
Exception: yt-dlp download failed: HTTP Error 403: Forbidden
```

Parsed output:
```json
{
  "job_id": 123,
  "youtube_id": "b7PzpfbqcJs",
  "status": "failed",
  "failed_tier": 3,
  "processing_steps": [
    "Job picked from queue",
    "Video metadata extracted",
    "Tier 1 (auto-CC): FAILED - No auto-generated captions found",
    "Tier 2 (transcript-api): FAILED - NoTranscriptFound",
    "Tier 3 (whisper): FAILED - HTTP Error 403: Forbidden"
  ],
  "errors": [
    {
      "tier": 3,
      "error_type": "HTTP Error 403",
      "error_message": "yt-dlp download failed: HTTP Error 403: Forbidden",
      "file": "yt_dlp_service.py",
      "line": 89,
      "diagnosis": "YouTube blocking download - may need updated yt-dlp version or different user agent"
    }
  ],
  "stack_trace": "Exception: yt-dlp download failed: HTTP Error 403: Forbidden\n  File \"/app/worker/yt_dlp_service.py\", line 89"
}
```

### Error Pattern Library

Common error patterns to watch for:

1. **No Captions**: "No auto-generated captions found" → Expected, should fallback
2. **API Transcript Missing**: "NoTranscriptFound" → Expected, should fallback
3. **Rate Limiting**: "HTTP Error 429" → YouTube rate limit, need backoff/retry
4. **Forbidden**: "HTTP Error 403" → Blocked by YouTube, need updated yt-dlp
5. **Video Unavailable**: "Video unavailable" → Private/deleted video
6. **Model Not Found**: "whisper model not found" → Model download issue
7. **GPU Error**: "CUDA error" / "OpenVINO error" → GPU issue, should fallback to CPU
8. **FFmpeg Error**: "ffmpeg not found" / "audio codec error" → FFmpeg installation issue
9. **Timeout**: "timeout" / "timed out" → Network or processing timeout
10. **Out of Memory**: "out of memory" / "OOM" → Insufficient RAM for Whisper model

## Task: Analyze Failure

When a job fails:

1. Extract all ERROR and WARNING messages
2. Identify which tier(s) failed
3. Extract stack traces
4. Identify root cause from error patterns
5. Suggest fix based on error type

## Error Handling

- **Container not found**: Run `docker ps -a` to check container name
- **Permission denied**: Run with sudo or ensure Docker group membership
- **Logs too large**: Use --tail and --since to limit output
- **Container not running**: Logs will still be available from stopped container

## Notes

- Worker logs are most critical for transcription debugging
- Web logs show job submission and API calls
- Database logs show connection issues
- Redis logs show queue operations
- Always check for stack traces - they provide file/line info for debugging
