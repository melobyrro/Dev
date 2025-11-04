# Browser Tester Skill

## Purpose
Use browser automation to interact with the CultoTranscript web UI, submit YouTube videos for transcription, and monitor job status.

## MCP Servers Used
- **browser-use**: Web browser automation via `mcp__browser-use__run_browser_agent`

## Instructions

You are the browser automation tester for CultoTranscript. Your task is to submit a YouTube video and monitor its transcription job.

### Input Parameters
- `youtube_url`: The YouTube video URL to test (e.g., https://www.youtube.com/watch?v=b7PzpfbqcJs)
- `instance_password`: Password from .env file (default: admin123)
- `max_wait_minutes`: Maximum time to wait for job completion (default: 10)

### Task Steps

#### 1. Navigate and Login
Use browser agent to:
```
Navigate to http://localhost:8000
If login page appears:
  - Find the password input field
  - Enter the instance_password
  - Click submit/login button
Verify successful login (should see dashboard or transcribe form)
```

#### 2. Submit YouTube Video
```
On the main page:
  - Find the "Adicionar Vídeo" or transcription form
  - Locate the YouTube URL input field
  - Enter the youtube_url
  - Click the submit/transcribe button
  - Wait for response
  - Capture the job_id from the response or UI
```

#### 3. Monitor Job Status
```
Every 5 seconds, check the job status:
  - Navigate to /api/jobs/{job_id}/status or check UI status indicator
  - Read the current status: queued, running, completed, failed
  - If status is "running" or "queued": continue polling
  - If status is "completed": SUCCESS - proceed to step 4
  - If status is "failed": FAILURE - capture error and exit
  - If max_wait_minutes exceeded: TIMEOUT - exit with timeout error
```

#### 4. Verify Success (if completed)
```
Navigate to the video detail page:
  - Check video status is "completed"
  - Verify transcript text is visible
  - Capture transcript source (auto_cc, transcript_api, or whisper)
  - Capture transcript word count
  - Take screenshot of successful transcription
```

## Expected Output

### On Success:
```json
{
  "success": true,
  "job_id": 123,
  "video_id": 456,
  "status": "completed",
  "transcript_source": "auto_cc",
  "word_count": 1524,
  "duration_seconds": 180,
  "processing_time_seconds": 45,
  "message": "Video transcribed successfully using auto-captions"
}
```

### On Failure:
```json
{
  "success": false,
  "job_id": 123,
  "video_id": 456,
  "status": "failed",
  "error_message": "yt-dlp download failed: Video unavailable",
  "failed_at_tier": "tier1_auto_cc",
  "processing_time_seconds": 120,
  "message": "Transcription failed at tier 1 (auto-CC extraction)"
}
```

### On Timeout:
```json
{
  "success": false,
  "job_id": 123,
  "status": "running",
  "error_message": "Job timed out after 10 minutes",
  "message": "Job exceeded maximum wait time - may need manual inspection"
}
```

## Error Handling

- **Login failure**: Check if INSTANCE_PASSWORD is correct in .env
- **Form not found**: Verify web service is running on port 8000
- **Job submission failure**: Check Redis queue is running
- **Status endpoint 404**: Job may not exist in database
- **Browser timeout**: Increase max_wait_minutes or check network issues

## Notes

- The web UI is in Portuguese (PT-BR)
- Button text may be "Transcrever", "Adicionar Vídeo", or "Enviar"
- The job polling should be patient - Whisper transcription can take several minutes
- If the browser agent has trouble finding elements, inspect the HTML structure in app/web/templates/
