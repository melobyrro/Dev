# Session End - Commit & Deploy

End your Claude session by committing changes and deploying to the VM.

## Steps

1. **Check for uncommitted changes:**
   - Run `git status` to show modified/untracked files
   - If no changes, inform user and exit

2. **Review changes with user:**
   - Show the list of changed files
   - Ask user: "Do you want to commit these changes?"
   - If no, exit without committing

3. **Create commit:**
   - Ask user for a brief commit message (or generate one based on changes)
   - Stage relevant files (avoid committing secrets or temp files)
   - Create commit with Co-Authored-By trailer

4. **Push to GitHub:**
   - Run `git push`
   - Report success or failure

5. **Deploy to VM and verify:**
   - SSH to VM: `ssh byrro@192.168.1.11 "cd /home/byrro/Dev && git pull && bash home-server/scripts/deploy-from-repo.sh"`
   - Wait for command to complete
   - Check exit code
   - Report deploy status to user

6. **Final confirmation:**
   - If all succeeded: "✓ Changes committed, pushed, and deployed to VM successfully"
   - If deploy failed: "❌ Deploy failed - changes are in GitHub but VM may not be updated"

## Important

- Never commit files matching: `*.env`, `secrets.yaml`, `*.key`, `*.pem`
- Always wait for VM deploy to complete before reporting success
- If VM is unreachable, warn user but don't fail the commit/push
