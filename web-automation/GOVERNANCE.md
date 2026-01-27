# Web Automation CLI Governance

## Purpose

This tool provides CDP-based web automation for validating authenticated web pages using the user's existing Chrome profile and cookies.

## Allowed Tools

| Tool | Status | Rationale |
|------|--------|-----------|
| `web-validate` CLI | **ALLOWED** | CDP-based, uses real Chrome profile |
| puppeteer-core | **ALLOWED** | Lightweight, connects to existing Chrome |
| Direct CDP calls | **ALLOWED** | Native protocol access |

## Forbidden Tools

| Tool | Status | Rationale |
|------|--------|-----------|
| Playwright | **FORBIDDEN** | Manages own browser instances, complex profile isolation |
| browsermcp | **FORBIDDEN** | Different automation model |
| Chrome DevTools UI | **FORBIDDEN** | Interactive debugging conflicts with automation |
| Claude-in-Chrome | **FORBIDDEN** | Manual browser UI, not scriptable |

## Why These Choices?

### Why puppeteer-core (not Playwright)

1. **Profile Reuse**: puppeteer-core easily connects to existing Chrome with user data
2. **CDP Native**: Direct CDP connection without abstraction layers
3. **Lightweight**: No bundled browser download required
4. **Session Persistence**: Uses real Chrome profile for authenticated sessions

### Why NOT Playwright

1. Playwright manages its own browser instances
2. Profile isolation makes session reuse complex
3. Heavier runtime with multi-browser support we don't need
4. Different automation model (contexts vs profiles)

## Preflight Enforcement

The `web-validate` CLI refuses to run if:

1. Playwright is detected in `node_modules`
2. Playwright is in `package.json` dependencies
3. `PLAYWRIGHT_*` environment variables are set

This prevents accidental mixing of automation frameworks.

## Chrome Launch Behavior

```
┌─ Is CDP running on port? ─┐
│                           │
├─ YES → Connect directly   │
│                           │
├─ NO + Chrome closed       │
│   → Launch Chrome with    │
│     --remote-debugging-port │
│     --user-data-dir (profile) │
│                           │
└─ NO + Chrome open without CDP │
    → ERROR: "Quit Chrome or   │
      restart with debug port" │
```

## Profile Directory

Default: `~/Library/Application Support/Google/Chrome`

This uses the user's real Chrome profile including:
- Cookies and sessions
- Saved passwords (via keychain)
- Extensions
- Bookmarks

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All assertions passed (or no assertions) |
| 1 | One or more assertions failed, or error |

## Output Structure

Each run creates:

```
runs/<timestamp>/
├── report.json      # Structured test results
├── screenshot.png   # Full page capture
├── page.html        # Page HTML content
└── network.json     # Network request log
```

## Adding New Validation Tools

If you need additional web automation capabilities:

1. First check if `web-validate` can be extended
2. Any new tool MUST use puppeteer-core or direct CDP
3. NEVER add Playwright or browsermcp
4. Update this document with the new tool
