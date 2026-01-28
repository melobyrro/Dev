# Agent Policy Integration (Codex + Claude)

## Purpose
Keep Codex aligned with the same per-project policy Claude uses (CLAUDE.md), without duplicating rules.

## Policy Sources
- **Authoritative rules**: nearest `CLAUDE.md` (walk up from the working directory).
- **Codex shim**: `CODEX.md` sits next to each `CLAUDE.md` and only points to it.
- **Repo-wide pointer**: `/Users/andrebyrro/Dev/.agent/POLICY_POINTER.md` (outside this repo).

## Enforcement
- **Validator**: `/Users/andrebyrro/Dev/scripts/validate-agent-policy.sh`
  - Ensures every `CLAUDE.md` has a sibling `CODEX.md`.
  - Verifies `CODEX.md` references `CLAUDE.md` and `/Users/andrebyrro/Dev/.agent/POLICY_POINTER.md`.
  - Guards against duplicating policy blocks in `CODEX.md` (line limit + heading keyword checks).
- **Git hooks (Dev root repo)**:
  - `/Users/andrebyrro/Dev/.git/hooks/pre-commit`
  - `/Users/andrebyrro/Dev/.git/hooks/pre-push`

## Convenience Entry Points
- `/Users/andrebyrro/Dev/Makefile` → `make validate-policy`
- `/Users/andrebyrro/Dev/home-server/home-assistant/Makefile` → `make validate-policy`

## Maintenance
- Update policies only in `CLAUDE.md` files.
- Keep `CODEX.md` minimal and pointer-only; do not copy rules into it.
- If new `CLAUDE.md` files are added, run the validator and add a sibling `CODEX.md`.
