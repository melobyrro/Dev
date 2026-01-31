#!/bin/bash
# Post-push auto-deployment hook
# Triggers VM deployment after git push commands

# Read tool input from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

# Only run deploy if git push was detected
if [[ "$COMMAND" == *"git push"* ]]; then
  echo "=== Auto-deploying to VM after git push ===" >&2

  # Run SSH deployment and capture exit code
  ssh -o ConnectTimeout=10 byrro@192.168.1.11 "cd /home/byrro/Dev && git pull && bash home-server/scripts/deploy-from-repo.sh" 2>&1
  SSH_EXIT=$?

  if [[ $SSH_EXIT -eq 0 ]]; then
    echo "=== VM deployment completed successfully ===" >&2
  else
    echo "=== ERROR: VM deployment failed (exit code: $SSH_EXIT) ===" >&2
    echo "=== Check SSH connection to byrro@192.168.1.11 ===" >&2
  fi

  # Always exit 0 so hook doesn't block Claude, but error is visible
  exit 0
fi

# Not a push command, exit silently
exit 0
