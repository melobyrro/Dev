import { parseArgs } from 'node:util';
import { z } from 'zod';
import { runPreflight } from './preflight.js';
import { connectOrLaunchChrome } from './chrome-launcher.js';
import { navigateAndValidate } from './cdp.js';
import { runAssertions } from './assertions.js';
import { saveResults, formatJsonOutput } from './output.js';

const ArgsSchema = z.object({
  url: z.string().url('Invalid URL format'),
  profileDir: z.string().optional(),
  debugPort: z.coerce.number().min(1).max(65535).default(9222),
  assertText: z.string().optional(),
  assertSelector: z.string().optional(),
  assertRegex: z.string().optional(),
  dumpJson: z.boolean().default(false),
});

function printUsage() {
  console.log(`
web-validate - CDP-based web validation CLI

USAGE:
  web-validate --url <url> [options]

OPTIONS:
  --url, -u <url>           Target URL (required)
  --profile-dir, -p <path>  Chrome profile directory
                            Default: ~/Library/Application Support/Google/Chrome
  --debug-port, -d <port>   CDP port (default: 9222)
  --assert-text "<text>"    Assert text exists in page
  --assert-selector "<css>" Assert CSS selector exists
  --assert-regex "<regex>"  Assert regex matches page content
  --dump-json               Output structured JSON results
  --help, -h                Show this help

EXIT CODES:
  0  All assertions passed (or no assertions specified)
  1  One or more assertions failed, or an error occurred

EXAMPLES:
  # Basic validation
  web-validate --url https://example.com

  # With assertions
  web-validate --url https://example.com --assert-text "Example Domain"

  # JSON output
  web-validate --url https://example.com --assert-selector "h1" --dump-json

NOTES:
  - If Chrome is running without CDP, you must quit it first
  - Results are saved to ~/Dev/web-automation/runs/<timestamp>/
  - Uses your existing Chrome profile (cookies, sessions preserved)
`);
}

/**
 * Main CLI entry point
 * @param {string[]} argv - Command line arguments (process.argv.slice(2))
 * @returns {Promise<number>} Exit code
 */
export async function runCLI(argv) {
  // Parse arguments
  let values;
  try {
    const parsed = parseArgs({
      args: argv,
      options: {
        url: { type: 'string', short: 'u' },
        'profile-dir': { type: 'string', short: 'p' },
        'debug-port': { type: 'string', short: 'd' },
        'assert-text': { type: 'string' },
        'assert-selector': { type: 'string' },
        'assert-regex': { type: 'string' },
        'dump-json': { type: 'boolean', default: false },
        help: { type: 'boolean', short: 'h' },
      },
      allowPositionals: false,
    });
    values = parsed.values;
  } catch (err) {
    console.error(`Error: ${err.message}`);
    console.error('Run with --help for usage information.');
    return 1;
  }

  // Handle help
  if (values.help) {
    printUsage();
    return 0;
  }

  // Check required URL
  if (!values.url) {
    console.error('Error: --url is required');
    console.error('Run with --help for usage information.');
    return 1;
  }

  // Validate and transform arguments
  let args;
  try {
    args = ArgsSchema.parse({
      url: values.url,
      profileDir: values['profile-dir'],
      debugPort: values['debug-port'] || 9222,
      assertText: values['assert-text'],
      assertSelector: values['assert-selector'],
      assertRegex: values['assert-regex'],
      dumpJson: values['dump-json'],
    });
  } catch (err) {
    if (err instanceof z.ZodError) {
      console.error('Validation error:', err.errors.map(e => e.message).join(', '));
    } else {
      console.error('Error:', err.message);
    }
    return 1;
  }

  // Preflight check
  console.error('[CLI] Running preflight checks...');
  const preflightOk = await runPreflight();
  if (!preflightOk) {
    return 1;
  }

  // Connect or launch Chrome
  let browser;
  try {
    browser = await connectOrLaunchChrome(args.debugPort, args.profileDir);
  } catch (err) {
    console.error(`[Error] ${err.message}`);
    return 1;
  }

  // Navigate and capture
  let result;
  try {
    console.error(`[CLI] Navigating to ${args.url}`);
    result = await navigateAndValidate(browser, args.url);
    console.error(`[CLI] Page loaded: "${result.title}" (${result.httpStatus}, ${result.loadTimeMs}ms)`);
  } catch (err) {
    console.error(`[Error] ${err.message}`);
    return 1;
  }

  // Run assertions
  const hasAssertions = args.assertText || args.assertSelector || args.assertRegex;
  const assertionResults = await runAssertions(result, {
    text: args.assertText,
    selector: args.assertSelector,
    regex: args.assertRegex,
  });

  // Add assertions to result
  result.assertions = assertionResults;

  // Log assertion results
  for (const a of assertionResults) {
    const icon = a.passed ? '\u2713' : '\u2717';
    console.error(`[Assertion] ${icon} ${a.type}: ${a.message}`);
  }

  // Save results
  try {
    await saveResults(result);
  } catch (err) {
    console.error(`[Warning] Failed to save results: ${err.message}`);
  }

  // Output JSON if requested
  if (args.dumpJson) {
    console.log(JSON.stringify(formatJsonOutput(result), null, 2));
  }

  // Determine exit code
  const allPassed = assertionResults.every(a => a.passed);
  if (hasAssertions && !allPassed) {
    console.error('[CLI] One or more assertions failed');
    return 1;
  }

  console.error('[CLI] Validation complete');
  return 0;
}
