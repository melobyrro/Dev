# Help Command

Provide comprehensive help about using Claude Code with CultoTranscript.

## Instructions

Display the following information:

1. **Project Overview**:
   - Brief description: Automated sermon transcription and analysis platform
   - Main capabilities: 3-tier transcription, AI analysis, chatbot

2. **Available Skills**:
   - **environment-checker**: Verify dev environment setup (Docker, ports, .env, GPU)
   - **browser-tester**: E2E UI testing with browser automation
   - **database-inspector**: Query PostgreSQL database for videos/jobs/transcripts
   - **log-analyzer**: Monitor Docker container logs for errors
   - **error-fixer**: Automatically diagnose and fix errors

3. **Available Commands**:
   - `/help` - This help message
   - `/context` - Show current session context
   - `/project` - Display project overview
   - `/test` - Run test suite

4. **MCP Servers Available**:
   - **ref**: Documentation search (used by error-fixer)
   - **browser-use**: Browser automation (used by browser-tester)
   - **sequential-thinking**: Advanced problem-solving
   - **ide**: IDE integration tools

5. **Common Workflows**:

   **Debugging transcription failures:**
   1. Use database-inspector to check job status
   2. Use log-analyzer to examine worker logs
   3. Use error-fixer to diagnose and fix

   **Testing new features:**
   1. Use environment-checker to verify setup
   2. Make code changes
   3. Use browser-tester for E2E validation
   4. Use database-inspector to verify data

   **Local development:**
   ```bash
   docker-compose up -d          # Start services
   docker-compose logs -f        # Monitor logs
   docker-compose up -d --build  # Rebuild after changes
   ```

6. **Resources**:
   - See .claude/CLAUDE.md for detailed project context
   - See README.md for quick start
   - See ARCHITECTURE.md for system design
   - See DEPLOYMENT.md for production deployment

Format this information clearly using markdown with appropriate sections.
