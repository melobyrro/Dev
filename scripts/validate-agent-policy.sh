#!/usr/bin/env bash
set -u

root="/Users/andrebyrro/Dev"
policy_pointer="/Users/andrebyrro/Dev/.agent/POLICY_POINTER.md"
exit_code=0

echo "Scanning for CLAUDE.md under $root"
mapfile -t claude_files < <(rg --files -g 'CLAUDE.md' "$root" || true)

if [ ${#claude_files[@]} -eq 0 ]; then
  echo "No CLAUDE.md files found."
  exit 1
fi

echo "Found ${#claude_files[@]} CLAUDE.md file(s)."

for claude in "${claude_files[@]}"; do
  dir=$(dirname "$claude")
  codex_path=""
  if [ -f "$dir/CODEX.md" ]; then
    codex_path="$dir/CODEX.md"
  elif [ -f "$dir/codex.md" ]; then
    codex_path="$dir/codex.md"
  else
    echo "MISSING CODEX.md next to $claude"
    exit_code=1
    continue
  fi

  if ! rg -q "CLAUDE\.md" "$codex_path"; then
    echo "Missing CLAUDE.md reference: $codex_path"
    exit_code=1
  fi

  if ! rg -q "\.agent/POLICY_POINTER\.md" "$codex_path"; then
    echo "Missing .agent/POLICY_POINTER.md reference: $codex_path"
    exit_code=1
  fi

  lines=$(wc -l < "$codex_path" | tr -d ' ')
  if [ "$lines" -ge 200 ]; then
    echo "CODEX.md too long (${lines} lines): $codex_path"
    exit_code=1
  fi

  if rg -n -e 'Operating Contract|Definition of Done|DoD|Non-Negotiables' "$codex_path" >/dev/null; then
    echo "CODEX.md contains policy heading keywords: $codex_path"
    exit_code=1
  fi

done

if [ "$exit_code" -ne 0 ]; then
  echo "Policy validation failed."
else
  echo "Policy validation passed."
fi

exit "$exit_code"
