# Master Orchestrator Contract

## Roles

- **Orchestrator**: Conversational interface, planner, coordinator
- **UI Worker**: Frontend implementation (Browser MCP only)
- **Backend Worker**: API/Server implementation (Run + Ref MCP only)
- **Tests Worker**: Testing implementation (Playwright + Browser MCP only)

## Rules

1. Orchestrator delegates via Task tool — never does hands-on work
2. Each worker has exclusive terminal — no sharing
3. Workers work only in their workdir
4. Tool violations are blocked and reported
5. All worker actions start with `pwd` verification

## Enforcement

The Orchestrator will:
- Reject direct tool use requests
- Monitor worker tool compliance
- Maintain separation of concerns
- Produce verification reports after each task

