# Environment Checker Skill

## Purpose
Verify that the CultoTranscript development environment is properly configured and all required services are available before running tests.

## MCP Servers Used
- None (uses standard Bash commands)

## Instructions

You are the environment checker for CultoTranscript. Perform comprehensive pre-flight checks:

### 1. Docker Daemon Check
```bash
docker info
```
- Verify Docker is running
- Check if Docker daemon is accessible

### 2. Project Directory Check
```bash
cd /Users/andrebyrro/Dev/CultoTranscript && pwd
```
- Confirm we're in the correct project directory

### 3. Environment File Check
```bash
ls -la /Users/andrebyrro/Dev/CultoTranscript/.env
cat /Users/andrebyrro/Dev/CultoTranscript/.env | grep -E "(POSTGRES_|REDIS_|WHISPER_|INSTANCE_PASSWORD)"
```
- Verify .env file exists
- Check critical environment variables are set

### 4. Port Availability Check
```bash
lsof -i :8000 -i :5432 -i :6379
```
- Check if required ports are available (8000, 5432, 6379)
- If ports are in use by existing containers, that's OK
- If ports are in use by other processes, report conflict

### 5. Docker Images Check
```bash
docker images | grep cultotranscript
```
- List available CultoTranscript Docker images
- Check if web, worker, scheduler images exist

### 6. Docker Containers Status
```bash
docker ps -a --filter name=cultotranscript
```
- Check running/stopped containers
- Report container states

### 7. GPU Device Check (Optional)
```bash
ls -la /dev/dri
```
- Check if Intel GPU device exists for faster-whisper
- If not present, note that CPU fallback will be used

### 8. Docker Compose File Check
```bash
ls -la /Users/andrebyrro/Dev/CultoTranscript/docker/docker-compose.yml
```
- Verify docker-compose.yml exists

## Expected Output

Return a structured report:

```
ENVIRONMENT CHECK REPORT
========================

✅ Docker Daemon: Running
✅ Project Directory: /Users/andrebyrro/Dev/CultoTranscript
✅ .env File: Present
✅ Critical Env Vars: All set
✅ Port 8000: Available
✅ Port 5432: Available (or in use by cultotranscript-db)
✅ Port 6379: Available (or in use by cultotranscript-redis)
✅ Docker Images: Found (web, worker, scheduler)
⚠️  GPU Device: Not found (will use CPU)
✅ docker-compose.yml: Present

OVERALL STATUS: READY ✅
```

Or if issues found:

```
ENVIRONMENT CHECK REPORT
========================

✅ Docker Daemon: Running
❌ .env File: MISSING - Run: cp .env.example .env
❌ Port 8000: In use by another process (PID 1234)
⚠️  Docker Images: Not built - Run: docker-compose build

OVERALL STATUS: NOT READY ❌

REQUIRED ACTIONS:
1. Create .env file from .env.example
2. Stop process using port 8000 or change WEB_PORT
3. Build Docker images: docker-compose build
```

## Error Handling

- If Docker daemon not running: Report "Docker Desktop not running. Please start Docker."
- If .env missing: Report "Missing .env file. Copy from .env.example"
- If ports blocked: Report which process is using the port
- If docker-compose.yml missing: Report "Invalid project structure"
