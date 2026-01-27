# Clawdbot Setup

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Proxmox Host (192.168.1.10)              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Clawdbot Gateway (systemd: clawdbot-gateway)           ││
│  │  Port: 18789 (LAN accessible)                           ││
│  │  Auth: Token-based                                      ││
│  │  Channels: WhatsApp (+17542324777)                      ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ Docker VM       │          │ Mac (optional)  │
│ 192.168.1.11    │          │ via LAN         │
│ Node: byrroserver│         │ Node: Andre-Mac │
│ systemd service │          │ manual start    │
└─────────────────┘          └─────────────────┘
```

## Access Methods

| Method | URL/Command | Use Case |
|--------|-------------|----------|
| Web Chat | `https://clawd.byrroserver.com/chat?session=main` | Browser chat (HTTPS) |
| Control UI | `https://clawd.byrroserver.com/?token=<TOKEN>` | Admin dashboard |
| CLI | `clawdbot agent --message "..."` | Scripting |
| WhatsApp | Message yourself | Mobile access |
| LAN Direct | `http://192.168.1.10:18789/` | Fallback (no HTTPS) |

## Credentials

**Gateway Token:** `228e0ea5abb6fd156375f1376d83e6c51428b159e245a3a2`

**Tokenized Dashboard URL:**
`https://clawd.byrroserver.com/?token=228e0ea5abb6fd156375f1376d83e6c51428b159e245a3a2`

## Quick Commands

### Check Status
```bash
ssh root@192.168.1.10 "clawdbot status"
ssh root@192.168.1.10 "clawdbot channels status --probe"
ssh root@192.168.1.10 "clawdbot nodes status"
```

### Restart Gateway
```bash
ssh root@192.168.1.10 "clawdbot gateway restart"
```

### View Logs
```bash
ssh root@192.168.1.10 "clawdbot logs --follow"
```

### Re-link WhatsApp (if disconnected)
```bash
ssh -t root@192.168.1.10 "clawdbot channels login"
# Scan QR code with WhatsApp on phone
```

### Refresh OAuth Token (if revoked)
```bash
ssh -t root@192.168.1.10 "clawdbot models auth setup-token"
```

## Connect Mac as Node (Optional)

```bash
CLAWDBOT_GATEWAY_TOKEN="228e0ea5abb6fd156375f1376d83e6c51428b159e245a3a2" \
  clawdbot node run --host 192.168.1.10 --port 18789
```

## Troubleshooting

### WhatsApp not responding
1. Check channel status: `clawdbot channels status --probe`
2. If disconnected, re-link: `clawdbot channels login`

### OAuth token revoked
1. Run: `clawdbot models auth setup-token`
2. Follow prompts to authenticate
3. This creates a dedicated token that won't conflict with Mac's Claude Code

### Node not connecting
1. Check gateway is running: `clawdbot gateway status`
2. Verify gateway.bind is `lan`: `clawdbot config get gateway.bind`
3. Check firewall allows 18789

### Command execution hanging
The exec-approvals on the node should have `"security": "full"` for auto-approval:
```bash
ssh byrro@192.168.1.11 "cat ~/.clawdbot/exec-approvals.json"
```

## Config Files

| Location | File | Purpose |
|----------|------|---------|
| Proxmox | `/root/.clawdbot/clawdbot.json` | Main config |
| Proxmox | `/root/.clawdbot/credentials/whatsapp/` | WhatsApp session |
| Proxmox | `/root/.clawdbot/agents/main/agent/auth-profiles.json` | OAuth credentials |
| Docker VM | `/home/byrro/.clawdbot/exec-approvals.json` | Command approval settings |

## Systemd Services

**Gateway (Proxmox 192.168.1.10):**
```bash
systemctl status clawdbot-gateway
systemctl restart clawdbot-gateway
journalctl -u clawdbot-gateway -f
```

**Node (Docker VM 192.168.1.11):**
```bash
systemctl status clawdbot-node
systemctl restart clawdbot-node
journalctl -u clawdbot-node -f
```

## Important Notes

- **OAuth tokens**: Clawdbot has its own independent OAuth session (created via `setup-token`). This won't conflict with Mac's Claude Code.
- **WhatsApp selfChatMode**: Bot responds only to messages you send to yourself (Message Yourself feature).
- **Runtime**: Uses Node.js (not Bun) for WhatsApp reliability.
- **Gateway binding**: Set to `lan` for network access (not `loopback`).

## If OAuth Breaks in Future

Run this to re-authenticate (requires browser):
```bash
ssh -t root@192.168.1.10 "clawdbot models auth setup-token"
```

## Created
2026-01-27
