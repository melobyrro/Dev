import { access, readFile } from 'node:fs/promises';
import { join } from 'node:path';

/**
 * Preflight check - refuse to run if Playwright is detected
 * @returns {Promise<boolean>} true if OK to proceed, false if should abort
 */
export async function runPreflight() {
  // Check for Playwright in node_modules
  const playwrightIndicators = [
    join(process.cwd(), 'node_modules', 'playwright'),
    join(process.cwd(), 'node_modules', '@playwright'),
  ];

  for (const indicator of playwrightIndicators) {
    try {
      await access(indicator);
      console.error('ERROR: Playwright detected in current project.');
      console.error('This tool uses puppeteer-core and should not be mixed with Playwright.');
      console.error('See GOVERNANCE.md for rationale.');
      return false;
    } catch {
      // Not found, continue
    }
  }

  // Check package.json for playwright dependency
  try {
    const pkgPath = join(process.cwd(), 'package.json');
    const pkg = JSON.parse(await readFile(pkgPath, 'utf-8'));
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

    if (allDeps.playwright || allDeps['@playwright/test']) {
      console.error('ERROR: Playwright found in package.json dependencies.');
      console.error('This tool uses puppeteer-core and should not be mixed with Playwright.');
      return false;
    }
  } catch {
    // No package.json or unreadable, skip check
  }

  // Check for PLAYWRIGHT env vars
  const playwrightEnvVars = Object.keys(process.env).filter(k =>
    k.startsWith('PLAYWRIGHT_') || k === 'PWDEBUG'
  );

  if (playwrightEnvVars.length > 0) {
    console.error('WARNING: Playwright environment variables detected:', playwrightEnvVars.join(', '));
    console.error('This may indicate Playwright is in use. Proceeding with caution...');
  }

  // Print reminder about DevTools
  console.error('[Preflight] Reminder: Do not use Chrome DevTools UI during automated runs.');

  return true;
}
