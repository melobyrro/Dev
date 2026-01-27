import { mkdir, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RUNS_DIR = join(__dirname, '..', 'runs');

/**
 * Save validation results to disk
 * @param {object} result - Full result object from navigateAndValidate + assertions
 * @returns {Promise<string>} Path to the run directory
 */
export async function saveResults(result) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const runDir = join(RUNS_DIR, timestamp);

  await mkdir(runDir, { recursive: true });

  // Save JSON report (without large base64 data)
  const report = {
    requestedUrl: result.requestedUrl,
    finalUrl: result.finalUrl,
    title: result.title,
    httpStatus: result.httpStatus,
    loadTimeMs: result.loadTimeMs,
    timestamp: result.timestamp,
    assertions: result.assertions,
    networkRequestCount: result.networkRequests?.length || 0,
    // Include summary of main document request
    mainDocument: result.networkRequests?.find(r =>
      r.url === result.requestedUrl ||
      r.url === result.finalUrl ||
      r.contentType?.includes('text/html')
    ) || null,
  };

  await writeFile(
    join(runDir, 'report.json'),
    JSON.stringify(report, null, 2)
  );

  // Save screenshot
  if (result.screenshot) {
    await writeFile(
      join(runDir, 'screenshot.png'),
      Buffer.from(result.screenshot, 'base64')
    );
  }

  // Save HTML
  if (result.html) {
    await writeFile(join(runDir, 'page.html'), result.html);
  }

  // Save full network log
  if (result.networkRequests) {
    await writeFile(
      join(runDir, 'network.json'),
      JSON.stringify(result.networkRequests, null, 2)
    );
  }

  console.error(`[Output] Results saved to ${runDir}`);
  return runDir;
}

/**
 * Format results for JSON output (without large data)
 * @param {object} result
 * @returns {object}
 */
export function formatJsonOutput(result) {
  return {
    requestedUrl: result.requestedUrl,
    finalUrl: result.finalUrl,
    title: result.title,
    httpStatus: result.httpStatus,
    loadTimeMs: result.loadTimeMs,
    timestamp: result.timestamp,
    assertions: result.assertions,
    success: result.assertions?.every(a => a.passed) ?? true,
  };
}
