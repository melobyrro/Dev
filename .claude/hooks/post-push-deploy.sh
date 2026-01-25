#!/bin/bash
# Post-push auto-deployment hook
# Triggers VM deployment after git push commands

# Read tool input from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

# Only run deploy if git push was detected
if [[ "$COMMAND" == *"git push"* ]]; then
  echo "=== Auto-deploying to VM after git push ===" >&2
  ssh byrro@192.168.1.11 "cd /home/byrro/Dev && git pull && bash home-server/scripts/deploy-from-repo.sh" 2>&1
  exit 0
fi

# Not a push command, exit silently
exit 0
