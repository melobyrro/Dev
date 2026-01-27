import { spawn, execSync } from 'node:child_process';
import { setTimeout } from 'node:timers/promises';
import { mkdir, cp, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ORIGINAL_CHROME_DIR = process.env.HOME + '/Library/Application Support/Google/Chrome';
const CDP_PROFILE_DIR = join(__dirname, '..', '.chrome-cdp-profile');

/**
 * Connect to an existing Chrome with CDP or launch a new one
 * @param {number} port - CDP port (default 9222)
 * @param {string|undefined} profileDir - Chrome profile directory (optional override)
 * @returns {Promise<import('puppeteer-core').Browser>}
 */
export async function connectOrLaunchChrome(port = 9222, profileDir) {
  const cdpUrl = `http://127.0.0.1:${port}`;

  // Try to connect to existing Chrome with CDP
  if (await isCDPRunning(cdpUrl)) {
    console.error(`[CDP] Connecting to existing Chrome on port ${port}`);
    return puppeteer.connect({ browserURL: cdpUrl });
  }

  // Check if Chrome is running without CDP
  if (await isChromeRunning()) {
    throw new Error(
      'Chrome is running but not with remote debugging enabled.\n' +
      'Either quit Chrome and let this tool launch it, or start Chrome with:\n' +
      `  "${CHROME_PATH}" --remote-debugging-port=${port}\n\n` +
      'To quit Chrome: Cmd+Q or `pkill -x "Google Chrome"`'
    );
  }

  // Determine profile directory
  // Chrome requires a non-default user-data-dir for remote debugging
  // We use a dedicated CDP profile that can optionally be seeded from the real profile
  const userDataDir = profileDir || CDP_PROFILE_DIR;

  // Create CDP profile directory if it doesn't exist
  await mkdir(userDataDir, { recursive: true });

  // Check if we need to seed cookies from original profile
  const cookiesPath = join(userDataDir, 'Default', 'Cookies');
  const needsSeed = !(await fileExists(cookiesPath));

  if (needsSeed && !profileDir) {
    console.error(`[CDP] First run - seeding session data from Chrome profile...`);
    await seedFromOriginalProfile(userDataDir);
  }

  // Launch Chrome with CDP
  console.error(`[CDP] Launching Chrome with remote debugging on port ${port}`);
  console.error(`[CDP] Using profile: ${userDataDir}`);

  const chromeProcess = spawn(CHROME_PATH, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
  ], {
    detached: true,
    stdio: 'ignore',
  });
  chromeProcess.unref();

  // Wait for CDP to become available (retry loop)
  const maxAttempts = 30;
  for (let i = 0; i < maxAttempts; i++) {
    await setTimeout(500);
    if (await isCDPRunning(cdpUrl)) {
      console.error(`[CDP] Chrome ready after ${(i + 1) * 0.5}s`);
      return puppeteer.connect({ browserURL: cdpUrl });
    }
  }

  throw new Error(`Chrome did not start with CDP within ${maxAttempts * 0.5}s`);
}

/**
 * Seed CDP profile from original Chrome profile (cookies, local storage)
 */
async function seedFromOriginalProfile(targetDir) {
  const sourceDefault = join(ORIGINAL_CHROME_DIR, 'Default');
  const targetDefault = join(targetDir, 'Default');

  await mkdir(targetDefault, { recursive: true });

  // Files to copy for session persistence
  const filesToCopy = [
    'Cookies',
    'Cookies-journal',
    'Local Storage',
    'Session Storage',
    'Login Data',
    'Login Data-journal',
  ];

  for (const file of filesToCopy) {
    const src = join(sourceDefault, file);
    const dest = join(targetDefault, file);
    try {
      await cp(src, dest, { recursive: true, preserveTimestamps: true });
      console.error(`[CDP] Copied ${file}`);
    } catch (err) {
      // File might not exist, that's OK
      if (err.code !== 'ENOENT') {
        console.error(`[CDP] Warning: Could not copy ${file}: ${err.message}`);
      }
    }
  }
}

async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if CDP is running on the given URL
 * @param {string} cdpUrl - e.g., http://127.0.0.1:9222
 * @returns {Promise<boolean>}
 */
async function isCDPRunning(cdpUrl) {
  try {
    const response = await fetch(`${cdpUrl}/json/version`);
    const data = await response.json();
    return !!data.webSocketDebuggerUrl;
  } catch {
    return false;
  }
}

/**
 * Check if Chrome is running (any instance)
 * @returns {Promise<boolean>}
 */
async function isChromeRunning() {
  try {
    execSync('pgrep -x "Google Chrome"', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get CDP version info for diagnostics
 * @param {number} port
 * @returns {Promise<object|null>}
 */
export async function getCDPVersion(port = 9222) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/json/version`);
    return await response.json();
  } catch {
    return null;
  }
}
