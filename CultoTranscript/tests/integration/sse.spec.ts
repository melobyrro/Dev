/**
 * SSE (Server-Sent Events) Integration Tests
 *
 * These tests verify the real-time event streaming functionality:
 * 1. SSE connection establishment
 * 2. Heartbeat events (keep-alive)
 * 3. Video status updates
 * 4. Error event handling
 * 5. Connection recovery
 */

import { test, expect } from '@playwright/test';
import {
  EventType,
  HeartbeatEventDTO,
  VideoStatusEventDTO,
  SSEEventDTO,
  isHeartbeatEvent,
  isVideoStatusEvent,
} from '../types';

/**
 * Helper function to create an EventSource in the browser context
 * and collect events for testing
 */
async function connectToSSE(page: any, url: string, timeout: number = 40000) {
  return page.evaluate(
    ({ url, timeout }) => {
      return new Promise<{ success: boolean; events: any[]; error?: string }>(
        (resolve) => {
          const events: any[] = [];
          const eventSource = new EventSource(url);
          let timeoutId: NodeJS.Timeout;

          const cleanup = (success: boolean, error?: string) => {
            clearTimeout(timeoutId);
            eventSource.close();
            resolve({ success, events, error });
          };

          // Set timeout
          timeoutId = setTimeout(() => {
            cleanup(false, `Timeout after ${timeout}ms waiting for events`);
          }, timeout);

          // Listen for messages
          eventSource.addEventListener('message', (event) => {
            try {
              const data = JSON.parse(event.data);
              events.push(data);

              // If we receive a heartbeat, consider it a success
              if (data.type === 'heartbeat') {
                cleanup(true);
              }
            } catch (error) {
              cleanup(false, `Failed to parse event: ${error}`);
            }
          });

          // Listen for errors
          eventSource.addEventListener('error', (error) => {
            // If we already have events, this might just be a normal close
            if (events.length > 0) {
              cleanup(true);
            } else {
              cleanup(false, `Connection error: ${error}`);
            }
          });

          // Listen for open
          eventSource.addEventListener('open', () => {
            console.log('SSE connection opened');
          });
        }
      );
    },
    { url, timeout }
  );
}

test.describe('SSE Integration - Connection', () => {
  test('SSE endpoint is accessible', async ({ request }) => {
    // Try to connect to SSE endpoint
    const response = await request.get('http://localhost:8000/api/v2/events/stream');

    // SSE endpoints typically return 200 and keep connection open
    expect(response.status()).toBe(200);

    // Check Content-Type header
    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('text/event-stream');
  });

  test('SSE connection establishes successfully', async ({ page }) => {
    // Navigate to a page (needed for browser context)
    await page.goto('http://localhost:5173');

    // Create EventSource connection
    const result = await connectToSSE(
      page,
      'http://localhost:8000/api/v2/events/stream',
      10000
    );

    // Verify connection was successful
    expect(result.success).toBe(true);
    expect(result.error).toBeUndefined();
  });
});

test.describe('SSE Integration - Heartbeat Events', () => {
  test('SSE endpoint streams heartbeat events within 35 seconds', async ({ page }) => {
    // Navigate to a page (needed for browser context)
    await page.goto('http://localhost:5173');

    // Connect to SSE and wait for heartbeat
    const result = await connectToSSE(
      page,
      'http://localhost:8000/api/v2/events/stream',
      35000 // Wait up to 35 seconds for heartbeat
    );

    // Verify we received events
    expect(result.success).toBe(true);
    expect(result.events.length).toBeGreaterThan(0);

    // Verify we received at least one heartbeat event
    const heartbeatEvents = result.events.filter(
      (event) => event.type === EventType.HEARTBEAT
    );
    expect(heartbeatEvents.length).toBeGreaterThan(0);

    // Verify heartbeat event structure matches HeartbeatEventDTO
    const firstHeartbeat = heartbeatEvents[0] as HeartbeatEventDTO;
    expect(firstHeartbeat).toHaveProperty('type', EventType.HEARTBEAT);
    expect(firstHeartbeat).toHaveProperty('timestamp');

    // Verify timestamp is valid ISO 8601 format
    const timestamp = new Date(firstHeartbeat.timestamp);
    expect(timestamp.toString()).not.toBe('Invalid Date');
  });

  test('Heartbeat events have correct structure', async ({ page }) => {
    await page.goto('http://localhost:5173');

    const result = await connectToSSE(
      page,
      'http://localhost:8000/api/v2/events/stream',
      35000
    );

    expect(result.success).toBe(true);

    // Get heartbeat event
    const heartbeat = result.events.find(
      (event) => event.type === EventType.HEARTBEAT
    );
    expect(heartbeat).toBeDefined();

    // Validate against HeartbeatEventDTO structure
    expect(heartbeat).toMatchObject({
      type: EventType.HEARTBEAT,
      timestamp: expect.any(String),
    });

    // Verify no extra fields (should only have type and timestamp)
    const expectedKeys = ['type', 'timestamp'];
    const actualKeys = Object.keys(heartbeat!);
    expect(actualKeys.sort()).toEqual(expectedKeys.sort());
  });

  test('Multiple heartbeats received over time', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // Collect events for 60 seconds to see multiple heartbeats
    const result = await page.evaluate(() => {
      return new Promise<{ events: any[]; duration: number }>((resolve) => {
        const events: any[] = [];
        const startTime = Date.now();
        const eventSource = new EventSource(
          'http://localhost:8000/api/v2/events/stream'
        );

        // Collect events for 60 seconds
        const timeout = setTimeout(() => {
          const duration = Date.now() - startTime;
          eventSource.close();
          resolve({ events, duration });
        }, 60000);

        eventSource.addEventListener('message', (event) => {
          try {
            const data = JSON.parse(event.data);
            events.push({ ...data, receivedAt: Date.now() });

            // Stop early if we get 3 heartbeats
            const heartbeats = events.filter((e) => e.type === 'heartbeat');
            if (heartbeats.length >= 3) {
              clearTimeout(timeout);
              const duration = Date.now() - startTime;
              eventSource.close();
              resolve({ events, duration });
            }
          } catch (error) {
            console.error('Parse error:', error);
          }
        });
      });
    });

    // Should receive multiple heartbeats (at least 2)
    const heartbeats = result.events.filter((e) => e.type === EventType.HEARTBEAT);
    expect(heartbeats.length).toBeGreaterThanOrEqual(2);

    // Log heartbeat intervals for debugging
    if (heartbeats.length >= 2) {
      const intervals = [];
      for (let i = 1; i < heartbeats.length; i++) {
        const interval = heartbeats[i].receivedAt - heartbeats[i - 1].receivedAt;
        intervals.push(interval);
      }
      console.log('Heartbeat intervals (ms):', intervals);

      // Verify heartbeats are approximately 30 seconds apart (±5 seconds)
      intervals.forEach((interval) => {
        expect(interval).toBeGreaterThan(25000); // At least 25 seconds
        expect(interval).toBeLessThan(35000); // At most 35 seconds
      });
    }
  });
});

test.describe('SSE Integration - Connection Recovery', () => {
  test('SSE connection can be re-established after close', async ({ page }) => {
    await page.goto('http://localhost:5173');

    // First connection
    const result1 = await connectToSSE(
      page,
      'http://localhost:8000/api/v2/events/stream',
      35000
    );
    expect(result1.success).toBe(true);

    // Wait a bit
    await page.waitForTimeout(2000);

    // Second connection (should work independently)
    const result2 = await connectToSSE(
      page,
      'http://localhost:8000/api/v2/events/stream',
      35000
    );
    expect(result2.success).toBe(true);
  });
});

test.describe('SSE Integration - Error Handling', () => {
  test('SSE connection handles invalid endpoints gracefully', async ({ page }) => {
    await page.goto('http://localhost:5173');

    const result = await page.evaluate(() => {
      return new Promise<{ success: boolean; error: boolean }>((resolve) => {
        const eventSource = new EventSource(
          'http://localhost:8000/api/v2/events/invalid'
        );
        let errorOccurred = false;

        const timeout = setTimeout(() => {
          eventSource.close();
          resolve({ success: false, error: errorOccurred });
        }, 5000);

        eventSource.addEventListener('error', () => {
          errorOccurred = true;
          clearTimeout(timeout);
          eventSource.close();
          resolve({ success: false, error: true });
        });

        eventSource.addEventListener('message', () => {
          clearTimeout(timeout);
          eventSource.close();
          resolve({ success: true, error: false });
        });
      });
    });

    // Should get an error for invalid endpoint
    expect(result.error).toBe(true);
  });
});
