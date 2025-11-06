# CultoTranscript Tests

Playwright-based E2E and integration tests for the CultoTranscript application.

## Setup

### Prerequisites
- Node.js 18+ installed
- Development servers running:
  - React Dev Server: `http://localhost:5173`
  - FastAPI Backend: `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Install Playwright browsers (if not already installed)
npx playwright install
```

## Project Structure

```
Tests/
├── e2e/                    # End-to-end tests
│   ├── smoke.spec.ts       # Basic server availability tests
│   └── video-list.spec.ts  # Video listing functionality tests
├── integration/            # Integration tests
│   └── sse.spec.ts        # Server-Sent Events tests
├── fixtures/              # Test data and mocks
│   └── test-data.ts       # Mock DTOs and test fixtures
├── utils/                 # Test utilities
│   └── helpers.ts         # Helper functions for tests
├── types/                 # TypeScript types
│   └── index.ts           # Shared DTO imports
├── playwright.config.ts   # Playwright configuration
└── package.json          # Dependencies and scripts
```

## Running Tests

### All Tests
```bash
npm test
```

### Smoke Tests Only
```bash
npm run test:smoke
```

### SSE Integration Tests Only
```bash
npm run test:sse
```

### E2E Tests Only
```bash
npm run test:e2e
```

### Integration Tests Only
```bash
npm run test:integration
```

### Run with UI Mode (Interactive)
```bash
npm run test:ui
```

### Run in Headed Mode (See Browser)
```bash
npm run test:headed
```

### Debug Mode
```bash
npm run test:debug
```

### Specific Browser
```bash
npm run test:chromium
npm run test:firefox
npm run test:webkit
```

### View Test Report
```bash
npm run test:report
```

## Test Categories

### Smoke Tests (`e2e/smoke.spec.ts`)
Verify basic functionality and server availability:
- React dev server is accessible
- FastAPI backend is accessible
- Critical pages load without errors
- Static assets load successfully
- Servers respond within acceptable time

**Run before starting development to ensure environment is ready.**

### SSE Integration Tests (`integration/sse.spec.ts`)
Test Server-Sent Events functionality:
- SSE connection establishment
- Heartbeat events (keep-alive every ~30 seconds)
- Event structure validation against DTOs
- Connection recovery
- Error handling

**Critical for real-time features.**

### Video List Tests (`e2e/video-list.spec.ts`)
Test video listing page functionality:
- Page load and rendering
- Video card display
- Status badges
- Navigation to detail pages
- Filtering and sorting
- Responsive design
- Loading and empty states

**Note: Some tests are placeholders until UI is fully implemented.**

## Test Configuration

### Playwright Config (`playwright.config.ts`)
- **Base URL**: `http://localhost:5173` (React dev server)
- **Timeout**: 30 seconds per action
- **Retries**: 2 on CI, 0 locally
- **Projects**: chromium, firefox, webkit
- **Screenshots**: On failure
- **Videos**: On first retry
- **Trace**: On first retry

## Shared Types

All tests use shared DTOs from `../shared/dtos.ts` for type safety:
- `VideoDTO`, `VideoDetailDTO`, `SummaryDTO`
- `EventType`, `VideoStatus` (enums)
- `HeartbeatEventDTO`, `VideoStatusEventDTO`, etc.
- Type guards: `isHeartbeatEvent()`, `isVideoStatusEvent()`

Import via: `import { VideoDTO, EventType } from '../types';`

## Test Utilities

### Helper Functions (`utils/helpers.ts`)
- `waitForElement(page, selector, timeout)` - Wait for element to appear
- `waitForSSEEvent(eventSource, eventType, timeout)` - Wait for SSE event
- `mockVideoData(overrides)` - Generate mock video data
- `waitForText(page, text, timeout)` - Wait for text to appear
- `waitForResponse(page, urlPattern, timeout)` - Wait for API response
- `isServerAccessible(url)` - Check if server is reachable
- `formatDuration(seconds)` - Format duration as HH:MM:SS

### Test Fixtures (`fixtures/test-data.ts`)
- `mockProcessedVideo`, `mockProcessingVideo`, `mockFailedVideo`
- `mockVideoDetail`, `mockSummary`
- `mockChannel`, `mockVideoList`
- `testYouTubeUrls` - Valid and invalid URL examples
- `mockTranscriptText` - Sample Portuguese sermon transcript

## Writing New Tests

### Example: Basic E2E Test
```typescript
import { test, expect } from '@playwright/test';

test('my feature works', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await expect(page.getByText('Welcome')).toBeVisible();
});
```

### Example: Using Shared Types
```typescript
import { test, expect } from '@playwright/test';
import { VideoStatus, EventType } from '../types';
import { mockVideoData } from '../utils/helpers';

test('video status is correct', async () => {
  const video = mockVideoData({ status: VideoStatus.PROCESSED });
  expect(video.status).toBe(VideoStatus.PROCESSED);
});
```

### Example: SSE Test
```typescript
import { test, expect } from '@playwright/test';
import { waitForSSEEvent } from '../utils/helpers';
import { EventType } from '../types';

test('receives heartbeat', async ({ page }) => {
  await page.goto('http://localhost:5173');

  const result = await page.evaluate(() => {
    const eventSource = new EventSource('http://localhost:8000/api/v2/events/stream');
    return new Promise((resolve) => {
      eventSource.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'heartbeat') {
          eventSource.close();
          resolve(data);
        }
      });
    });
  });

  expect(result).toHaveProperty('type', EventType.HEARTBEAT);
});
```

## CI/CD Integration

Tests are configured for CI environments:
- `CI=true` enables 2 retries and parallel execution
- Use `npm test` in CI pipeline
- Test reports are generated in `playwright-report/`
- Screenshots and videos saved in `test-results/`

## Troubleshooting

### Tests Fail: "Navigation timeout exceeded"
- Ensure dev servers are running
- Check `http://localhost:5173` and `http://localhost:8000` are accessible
- Increase timeout in test if needed

### Tests Fail: "Selector not found"
- UI may not be implemented yet (check test notes)
- Update selectors to match actual UI implementation
- Use `test:debug` to inspect page state

### SSE Tests Fail: "Timeout waiting for heartbeat"
- Backend SSE endpoint may not be implemented
- Check backend logs for errors
- Verify SSE endpoint: `http://localhost:8000/api/v2/events/stream`

### Browsers Not Installed
```bash
npx playwright install chromium firefox webkit
```

## Best Practices

1. **Always start dev servers before running tests**
2. **Use shared DTOs for type safety** - Import from `../types`
3. **Use test utilities** - Don't duplicate wait logic
4. **Test data isolation** - Use mock data from fixtures
5. **Clear test names** - Describe what is being tested
6. **Skip placeholder tests** - Use `test.skip()` for unimplemented UI
7. **Log useful info** - Help future developers understand test intent

## Next Steps

As the UI is developed:
1. Update video list tests with actual selectors
2. Add tests for video detail page
3. Add tests for video upload/import flows
4. Add tests for chatbot interface
5. Add visual regression tests (screenshots)
6. Add accessibility tests

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Test Generator](https://playwright.dev/docs/codegen) - `npx playwright codegen`
