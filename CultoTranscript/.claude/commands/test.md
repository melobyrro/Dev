# Test Command

Run the CultoTranscript test suite.

## Instructions

Execute the project's test suite and provide results:

1. **Pre-Test Checks**:
   - Verify Docker services are running: `docker-compose ps`
   - Ensure test database is accessible
   - Check if culto_web container is healthy

2. **Run Tests**:
   ```bash
   # Run all tests
   docker-compose exec culto_web pytest

   # Run with verbose output
   docker-compose exec culto_web pytest -v

   # Run with coverage
   docker-compose exec culto_web pytest --cov=app tests/
   ```

3. **Test Categories** (if specific tests requested):
   ```bash
   # Transcription tests
   docker-compose exec culto_web pytest tests/test_transcription.py

   # Analytics tests
   docker-compose exec culto_web pytest tests/test_analytics_v2.py

   # API endpoint tests
   docker-compose exec culto_web pytest tests/test_api.py

   # Database model tests
   docker-compose exec culto_web pytest tests/test_models.py
   ```

4. **Analyze Results**:
   - Report pass/fail counts
   - Highlight any failed tests
   - Show coverage percentage if run with --cov
   - Identify any warnings or issues

5. **Troubleshooting Failed Tests**:
   - If tests fail, use log-analyzer skill to check for errors
   - Use database-inspector skill to verify test data state
   - Consider using error-fixer skill to diagnose issues

6. **Post-Test Actions**:
   - If all tests pass, report success
   - If tests fail, offer to:
     - Show detailed failure output
     - Help debug specific failures
     - Use error-fixer skill to attempt fixes

Always run tests before committing changes or deploying to production.
