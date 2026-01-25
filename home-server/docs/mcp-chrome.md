# Chrome MCP via CDP (Persistent Profile)

## Prerequisites
- macOS
- Node.js + npx
- Google Chrome installed at `/Applications/Google Chrome.app`
- Codex CLI available

## Start Chrome with remote debugging
Quit Chrome completely first (remote debugging flags are ignored if Chrome is already running).

```bash
./scripts/chrome-mcp-start.sh
```

## Check CDP health
```bash
./scripts/chrome-mcp-check.sh
```

Expected output includes JSON with `webSocketDebuggerUrl` and a line:
`OK: webSocketDebuggerUrl detected`

## Codex MCP configuration
The chrome-devtools MCP server is configured to connect to:
`http://127.0.0.1:9222` via `--browserUrl`.

Verify with:
```bash
codex mcp list
```

## Log in once, reuse session
1. Run `./scripts/chrome-mcp-start.sh`.
2. Log in to your target site in the Chrome window.
3. Keep that Chrome window open while Codex operates.

## Troubleshooting
- Port busy (9222):
  - `lsof -iTCP:9222 -sTCP:LISTEN`
  - Quit Chrome and relaunch via `./scripts/chrome-mcp-start.sh`.
- Profile lock or wrong profile:
  - Ensure Chrome is fully quit before starting.
  - Profile is stored at `./.mcp/chrome-profile`.
- Chrome path:
  - Ensure `/Applications/Google Chrome.app` exists.
