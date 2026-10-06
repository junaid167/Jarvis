# JARVIS 2.0 Build Status

Branch: `jarvis-2.0-friend-core`

## Implemented

- Friend-oriented operating policy.
- Action-first execution philosophy.
- Bounded retries for ordinary action failures.
- Verification before reporting success.
- Long-running/background task registry.
- Task cancellation and progress state.
- Persistent prompt file for JARVIS 2.0 behavior.
- Existing action execution routed through the orchestrator.

## Important runtime dependency

The repository's current Git tree does not contain the existing `actions/`, `memory/`, and several `core/` modules imported by `main.py`. Those modules appear to be part of the local project but are not currently present in this GitHub repository.

Therefore this branch is an incremental upgrade, not yet a complete standalone clone of the local JARVIS installation.

## Next build stage

1. Recover/sync the missing runtime modules.
2. Add a planner that turns natural-language goals into TaskPlan objects.
3. Add task status/cancel/progress tools.
4. Add structured memory for preferences, projects and active goals.
5. Add browser/computer multi-step workflows with verification.
6. Add proactive background jobs.
7. Add automated startup diagnostics and capability discovery.
