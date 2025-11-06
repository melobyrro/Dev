# Tests Quick Start Guide

## Prerequisites Checklist

Before running tests, ensure:
- [ ] React dev server running at http://localhost:5173
- [ ] FastAPI backend running at http://localhost:8000

## Quick Commands

### Run Tests
```bash
# From Tests/ directory
npm run test:smoke    # Verify servers are running (start here!)
npm run test:sse      # Test SSE heartbeat functionality
npm test              # Run all tests
```

### Debug Tests
```bash
npm run test:ui       # Interactive mode (RECOMMENDED)
npm run test:headed   # See browser window
npm run test:debug    # Debug with inspector
```

### View Results
```bash
npm run test:report   # Open HTML report
```

## Test Execution Order (Recommended)

1. **Smoke Tests First** - Verify environment
   ```bash
   npm run test:smoke
   ```
   Expected: All 8 tests pass (servers accessible)

2. **SSE Integration Tests** - Verify real-time events
   ```bash
   npm run test:sse
   ```
   Expected: 9 tests pass (heartbeat events working)

3. **E2E Tests** - Verify UI functionality
   ```bash
   npm run test:e2e
   ```
   Expected: Video list tests (may skip if UI not implemented)

## Troubleshooting

### "Navigation timeout exceeded"
**Problem**: Servers not running
**Solution**: Start dev servers first
```bash
# Terminal 1 - React
cd UI/ && npm run dev

# Terminal 2 - Backend
cd backend/ && python -m uvicorn main:app --reload
```

### "Selector not found"
**Problem**: UI not implemented yet
**Solution**: Tests will skip automatically with console notes

### "Connection refused on SSE endpoint"
**Problem**: Backend SSE not implemented
**Solution**: Implement `/api/v2/events/stream` endpoint first

## Test File Locations

- Smoke Tests: `e2e/smoke.spec.ts` (8 tests)
- SSE Tests: `integration/sse.spec.ts` (9 tests)
- Video List: `e2e/video-list.spec.ts` (15 tests - placeholders)

## Configuration

Edit `playwright.config.ts` to change:
- Base URL (default: http://localhost:5173)
- Timeout (default: 30s)
- Retries (default: 2 on CI)

## Need Help?

- Full documentation: `README.md`
- Test coverage: `TEST_COVERAGE.md`
- Playwright docs: https://playwright.dev/

## Quick Reference

| Command | Purpose |
|---------|---------|
| `npm run test:smoke` | Verify servers running |
| `npm run test:sse` | Test SSE events |
| `npm run test:ui` | Interactive mode |
| `npm run test:headed` | See browser |
| `npm run test:debug` | Debug mode |
| `npm test` | Run all tests |
