# Error Fixer Skill

## Purpose
Analyze transcription errors, research solutions using documentation, implement code fixes, and rebuild/restart services.

## MCP Servers Used
- **ref**: Search and read documentation via `mcp__ref__ref_search_documentation` and `mcp__ref__ref_read_url`

## Instructions

You are the error fixer for CultoTranscript. When a transcription job fails, you diagnose the root cause, research the fix, implement it, and restart services.

### Input Parameters
- `error_analysis`: Structured error data from log-analyzer and database-inspector
- `youtube_id`: The video ID being tested
- `retry_count`: Current retry attempt (1-5)

### Fix Process

#### 1. Analyze Error
Examine the error data:
- Which tier failed? (1: auto-CC, 2: transcript-api, 3: whisper)
- Error type and message
- Stack trace location
- Previous fixes attempted (avoid repeating)

#### 2. Research Documentation
Use ref MCP to search for solutions:

```
For yt-dlp errors:
mcp__ref__ref_search_documentation("yt-dlp HTTP Error 403 fix python")
mcp__ref__ref_search_documentation("yt-dlp update version download audio")

For youtube-transcript-api errors:
mcp__ref__ref_search_documentation("youtube-transcript-api NoTranscriptFound fallback")
mcp__ref__ref_search_documentation("youtube-transcript-api language codes")

For faster-whisper errors:
mcp__ref__ref_search_documentation("faster-whisper model download error")
mcp__ref__ref_search_documentation("faster-whisper GPU fallback CPU")

For ffmpeg errors:
mcp__ref__ref_search_documentation("ffmpeg python audio extraction")
```

#### 3. Implement Fix
Based on research, modify the appropriate file:

**Common Fix Locations:**
- `/Users/andrebyrro/Dev/CultoTranscript/app/worker/yt_dlp_service.py` - yt-dlp issues
- `/Users/andrebyrro/Dev/CultoTranscript/app/worker/transcript_api_service.py` - API issues
- `/Users/andrebyrro/Dev/CultoTranscript/app/worker/whisper_service.py` - Whisper issues
- `/Users/andrebyrro/Dev/CultoTranscript/app/worker/transcription_service.py` - Orchestration logic
- `/Users/andrebyrro/Dev/CultoTranscript/docker/worker/Dockerfile` - Dependencies
- `/Users/andrebyrro/Dev/CultoTranscript/requirements-worker.txt` - Python packages

#### 4. Rebuild and Restart
```bash
# Rebuild worker container (if Dockerfile or requirements changed)
cd /Users/andrebyrro/Dev/CultoTranscript
docker-compose build worker

# Restart worker (if only Python code changed)
docker-compose restart worker

# Or restart all services
docker-compose restart

# Verify worker is running
docker ps | grep worker

# Check worker logs for startup errors
docker logs --tail 50 cultotranscript-worker
```

### Fix Patterns by Error Type

#### Error: HTTP 403 Forbidden (yt-dlp)
**Diagnosis**: YouTube blocking download due to outdated yt-dlp or missing headers

**Research**:
```
mcp__ref__ref_search_documentation("yt-dlp HTTP 403 fix youtube download")
```

**Fix**: Update yt-dlp and add headers
```python
# In yt_dlp_service.py
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'referer': 'https://www.youtube.com/',
}
```

**Requirements**: Ensure `requirements-worker.txt` has:
```
yt-dlp>=2025.10.22
```

**Rebuild**: `docker-compose build worker && docker-compose restart worker`

---

#### Error: HTTP 429 Too Many Requests
**Diagnosis**: Rate-limited by YouTube

**Research**:
```
mcp__ref__ref_search_documentation("yt-dlp rate limit retry backoff")
```

**Fix**: Add retry logic with exponential backoff
```python
# In yt_dlp_service.py
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
def download_audio(self, url: str, output_dir: str) -> str:
    # existing code...
```

**Requirements**: Add to `requirements-worker.txt`:
```
tenacity>=8.2.0
```

---

#### Error: Whisper Model Not Found
**Diagnosis**: Model failed to download or wrong path

**Research**:
```
mcp__ref__ref_search_documentation("faster-whisper model download path configuration")
```

**Fix**: Ensure correct model path and download
```python
# In whisper_service.py
self.model = WhisperModel(
    WHISPER_MODEL_SIZE,  # e.g., "medium"
    device=self.device,
    compute_type=self.compute_type,
    download_root="/app/tmp/whisper_models",  # Must match Docker volume
)
```

**Docker**: Verify volume in `docker-compose.yml`:
```yaml
volumes:
  - whisper-models:/app/tmp/whisper_models
```

---

#### Error: FFmpeg Not Found
**Diagnosis**: ffmpeg not installed in Docker image

**Research**:
```
mcp__ref__ref_search_documentation("install ffmpeg docker python alpine")
```

**Fix**: Add to `docker/worker/Dockerfile`:
```dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

**Rebuild**: `docker-compose build worker`

---

#### Error: GPU Not Available / OpenVINO Error
**Diagnosis**: Intel GPU not accessible or OpenVINO misconfigured

**Research**:
```
mcp__ref__ref_search_documentation("faster-whisper openvino cpu fallback")
```

**Fix**: Ensure graceful CPU fallback
```python
# In whisper_service.py
def _initialize_model(self):
    try:
        self.device = "auto"  # Try GPU
        self.compute_type = "int8"
    except Exception as e:
        logger.warning(f"GPU init failed: {e}. Falling back to CPU")
        self.device = "cpu"
        self.compute_type = "int8"
```

**Note**: CPU fallback is expected on systems without Intel GPU

---

#### Error: NoTranscriptFound (youtube-transcript-api)
**Diagnosis**: Video has no API-accessible transcripts (expected)

**Research**:
```
mcp__ref__ref_search_documentation("youtube-transcript-api language codes list")
```

**Fix**: Ensure tier 3 (Whisper) is working, as this is the final fallback
- No code fix needed - this is expected behavior
- Verify Whisper tier is functional

---

#### Error: Video Unavailable / Private
**Diagnosis**: Video is deleted, private, or restricted

**Fix**: No code fix possible - video is inaccessible
**Action**: Try different test video, or if this is production, mark video as skipped

---

#### Error: Audio Extraction Failed
**Diagnosis**: FFmpeg or codec issue

**Research**:
```
mcp__ref__ref_search_documentation("ffmpeg extract audio from video python yt-dlp")
```

**Fix**: Add audio conversion options
```python
# In yt_dlp_service.py
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
        'preferredquality': '192',
    }],
}
```

---

### Task: Fix Error

When invoked with error analysis:

1. **Read error details**
   - Error message
   - Failed tier
   - Stack trace

2. **Research solution**
   - Use ref MCP to search documentation
   - Read relevant documentation pages
   - Identify best fix approach

3. **Implement fix**
   - Modify appropriate Python file
   - Update requirements if needed
   - Update Dockerfile if needed

4. **Rebuild/Restart**
   - Rebuild if Dockerfile/requirements changed
   - Restart if only code changed
   - Verify container starts successfully

5. **Return fix report**

## Expected Output

```json
{
  "fix_applied": true,
  "error_type": "HTTP 403 Forbidden",
  "root_cause": "Outdated yt-dlp version and missing user agent headers",
  "research_done": [
    "Searched yt-dlp documentation for HTTP 403 fixes",
    "Read yt-dlp GitHub issues about YouTube blocking"
  ],
  "files_modified": [
    "/Users/andrebyrro/Dev/CultoTranscript/app/worker/yt_dlp_service.py",
    "/Users/andrebyrro/Dev/CultoTranscript/requirements-worker.txt"
  ],
  "changes_summary": [
    "Updated yt-dlp to version 2025.10.22",
    "Added user-agent and referer headers to ydl_opts",
    "Rebuilt worker container"
  ],
  "services_restarted": ["worker"],
  "ready_for_retry": true,
  "estimated_fix_confidence": "high"
}
```

## Error Handling

- **Cannot find file**: Verify project directory structure
- **Permission denied**: Check file permissions, may need sudo for Docker operations
- **Syntax error after fix**: Review Python syntax, test locally if possible
- **Container won't start**: Check Docker logs for startup errors
- **Build fails**: Check Dockerfile syntax and package availability

## Notes

- Always back up files before modifying (Git should track changes)
- Test fixes incrementally - don't change multiple things at once
- Document each fix in the output for audit trail
- If same error occurs after fix, increase retry count and try different approach
- Max 5 retry attempts before escalating to user
- Use ref MCP extensively - don't guess fixes, research them
- Prefer official documentation over Stack Overflow or blog posts
- When in doubt, check the project's existing code patterns and follow them
