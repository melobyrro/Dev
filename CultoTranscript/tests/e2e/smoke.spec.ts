/**
 * Smoke tests - Verify basic functionality and server availability
 *
 * These tests check that:
 * 1. Development servers are running and accessible
 * 2. Basic HTTP endpoints respond correctly
 * 3. Critical pages load without errors
 */

import { test, expect } from '@playwright/test';

test.describe('Smoke Tests - Server Availability', () => {
  test('React dev server is running at http://localhost:5173', async ({ page }) => {
    // Navigate to the React dev server
    const response = await page.goto('http://localhost:5173');

    // Verify the response is successful (HTTP 200)
    expect(response).not.toBeNull();
    expect(response!.status()).toBe(200);

    // Verify the page title loads (React app should have a title)
    await expect(page).toHaveTitle(/CultoTranscript|Vite/i);

    // Optional: Check for React root element
    const rootElement = page.locator('#root');
    await expect(rootElement).toBeAttached();
  });

  test('FastAPI server is running at http://localhost:8000/docs', async ({ page }) => {
    // Navigate to the FastAPI Swagger docs endpoint
    const response = await page.goto('http://localhost:8000/docs');

    // Verify the response is successful (HTTP 200)
    expect(response).not.toBeNull();
    expect(response!.status()).toBe(200);

    // Verify Swagger UI loads
    await expect(page).toHaveTitle(/FastAPI|Swagger/i);

    // Check for Swagger UI elements
    const swaggerUI = page.locator('.swagger-ui');
    await expect(swaggerUI).toBeVisible({ timeout: 10000 });
  });

  test('FastAPI health check endpoint responds', async ({ request }) => {
    // Make a direct API request to health check endpoint
    // Note: Adjust endpoint if your API has a different health check route
    const response = await request.get('http://localhost:8000/api/health', {
      // Some APIs might not have /api/health, try /health or /api/v2/health
      // This test might need adjustment based on actual API structure
    }).catch(async () => {
      // Fallback: Try root endpoint
      return request.get('http://localhost:8000/');
    });

    // Verify response is successful
    expect(response.status()).toBeLessThan(500); // Not a server error
  });

  test('React dev server serves static assets', async ({ page }) => {
    // Navigate to React app
    await page.goto('http://localhost:5173');

    // Check that JavaScript bundles load successfully
    const jsRequests = [];
    page.on('response', (response) => {
      if (response.url().includes('.js') || response.url().includes('.jsx')) {
        jsRequests.push(response);
      }
    });

    // Wait for page to fully load
    await page.waitForLoadState('networkidle');

    // Verify at least one JS file loaded successfully
    const successfulJsRequests = jsRequests.filter((req) => req.status() === 200);
    expect(successfulJsRequests.length).toBeGreaterThan(0);
  });

  test('Both servers respond within acceptable time', async ({ page }) => {
    // Measure React server response time
    const reactStartTime = Date.now();
    await page.goto('http://localhost:5173');
    const reactLoadTime = Date.now() - reactStartTime;

    // Measure FastAPI server response time
    const apiStartTime = Date.now();
    await page.goto('http://localhost:8000/docs');
    const apiLoadTime = Date.now() - apiStartTime;

    // Log performance metrics
    console.log(`React Server Load Time: ${reactLoadTime}ms`);
    console.log(`FastAPI Server Load Time: ${apiLoadTime}ms`);

    // Verify both servers respond in reasonable time (< 5 seconds)
    expect(reactLoadTime).toBeLessThan(5000);
    expect(apiLoadTime).toBeLessThan(5000);
  });
});

test.describe('Smoke Tests - Critical Page Loads', () => {
  test('React app root page loads without console errors', async ({ page }) => {
    // Collect console errors
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Navigate to app
    await page.goto('http://localhost:5173');

    // Wait for app to initialize
    await page.waitForLoadState('networkidle');

    // Verify no critical console errors
    // Filter out known harmless errors (like HMR warnings)
    const criticalErrors = consoleErrors.filter(
      (error) =>
        !error.includes('[vite]') &&
        !error.includes('WebSocket') &&
        !error.includes('HMR')
    );

    if (criticalErrors.length > 0) {
      console.error('Console Errors Found:', criticalErrors);
    }

    expect(criticalErrors.length).toBe(0);
  });

  test('FastAPI OpenAPI spec is accessible', async ({ request }) => {
    // Fetch OpenAPI schema
    const response = await request.get('http://localhost:8000/openapi.json');

    // Verify response is successful
    expect(response.status()).toBe(200);

    // Verify it's valid JSON
    const spec = await response.json();
    expect(spec).toHaveProperty('openapi');
    expect(spec).toHaveProperty('info');
    expect(spec).toHaveProperty('paths');
  });
});
