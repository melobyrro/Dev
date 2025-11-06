/**
 * Test utility helpers for Playwright tests
 */

import { Page, expect } from '@playwright/test';
import { VideoDTO, VideoStatus, EventType, SSEEventDTO } from '../types';

/**
 * Wait for an element to appear on the page
 * @param page - Playwright page object
 * @param selector - CSS selector for the element
 * @param timeout - Maximum wait time in milliseconds (default: 30000)
 */
export async function waitForElement(
  page: Page,
  selector: string,
  timeout: number = 30000
): Promise<void> {
  await expect(page.locator(selector)).toBeVisible({ timeout });
}

/**
 * Wait for a specific SSE event type to be received
 * @param eventSource - EventSource connection
 * @param eventType - Type of event to wait for (from EventType enum)
 * @param timeout - Maximum wait time in milliseconds (default: 35000)
 * @returns Promise that resolves with the event data
 */
export async function waitForSSEEvent(
  eventSource: EventSource,
  eventType: EventType,
  timeout: number = 35000
): Promise<SSEEventDTO> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      eventSource.close();
      reject(new Error(`Timeout waiting for SSE event: ${eventType}`));
    }, timeout);

    eventSource.addEventListener('message', (event) => {
      try {
        const data: SSEEventDTO = JSON.parse(event.data);
        if (data.type === eventType) {
          clearTimeout(timer);
          eventSource.close();
          resolve(data);
        }
      } catch (error) {
        clearTimeout(timer);
        eventSource.close();
        reject(new Error(`Failed to parse SSE event: ${error}`));
      }
    });

    eventSource.addEventListener('error', (error) => {
      clearTimeout(timer);
      eventSource.close();
      reject(new Error(`SSE connection error: ${error}`));
    });
  });
}

/**
 * Generate mock video data for testing
 * @param overrides - Optional field overrides
 * @returns Mock VideoDTO object
 */
export function mockVideoData(overrides?: Partial<VideoDTO>): VideoDTO {
  const defaultData: VideoDTO = {
    id: 'test-video-123',
    title: 'Test Sermon: The Power of Faith',
    youtube_id: 'dQw4w9WgXcQ',
    status: VideoStatus.PROCESSED,
    duration: 3600, // 1 hour
    created_at: new Date().toISOString(),
    processed_at: new Date().toISOString(),
    thumbnail_url: 'https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg',
    channel_id: 'test-channel-456',
  };

  return { ...defaultData, ...overrides };
}

/**
 * Wait for a specific text to appear on the page
 * @param page - Playwright page object
 * @param text - Text to wait for
 * @param timeout - Maximum wait time in milliseconds (default: 30000)
 */
export async function waitForText(
  page: Page,
  text: string,
  timeout: number = 30000
): Promise<void> {
  await expect(page.getByText(text)).toBeVisible({ timeout });
}

/**
 * Wait for a specific HTTP response
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to match (can be string or regex)
 * @param timeout - Maximum wait time in milliseconds (default: 30000)
 * @returns Promise that resolves with the response
 */
export async function waitForResponse(
  page: Page,
  urlPattern: string | RegExp,
  timeout: number = 30000
): Promise<any> {
  const response = await page.waitForResponse(urlPattern, { timeout });
  return response.json();
}

/**
 * Check if a URL is accessible (returns 200)
 * @param url - Full URL to check
 * @returns Promise that resolves to true if accessible, false otherwise
 */
export async function isServerAccessible(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    return response.ok;
  } catch (error) {
    return false;
  }
}

/**
 * Generate a random test channel ID
 * @returns Random channel ID string
 */
export function generateTestChannelId(): string {
  return `test-channel-${Date.now()}-${Math.random().toString(36).substring(7)}`;
}

/**
 * Generate a random test video ID
 * @returns Random video ID string
 */
export function generateTestVideoId(): string {
  return `test-video-${Date.now()}-${Math.random().toString(36).substring(7)}`;
}

/**
 * Format duration in seconds to human-readable string (HH:MM:SS)
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  return [hours, minutes, secs]
    .map((v) => v.toString().padStart(2, '0'))
    .join(':');
}
