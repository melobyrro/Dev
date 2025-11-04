# Context Command

Display information about the current conversation context and environment.

## Instructions

Show the user:

1. **Environment Info**:
   - Working directory
   - Git repository status
   - Platform/OS information
   - Current date

2. **Conversation Context**:
   - Files that have been read in this session
   - Recent tool usage
   - Active tasks or focus areas

3. **Session Info**:
   - Current model being used
   - Token usage statistics
   - Conversation length/age

4. **Docker Services Status** (if applicable):
   - Run `docker-compose ps` to show service status
   - Highlight any stopped or unhealthy services

5. **Available Context**:
   - Files in current directory
   - Custom slash commands available (/help, /project, /test)
   - Skills available (environment-checker, browser-tester, etc.)

Format this as a comprehensive overview to help the user understand what context is currently loaded.
