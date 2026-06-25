# Roadmap

## Completed

* Phase 1: Registries and policies
* Phase 2: Read-only inspection commands
* Phase 3: Context bundles
* Phase 4: Remote request skeleton
* Phase 5: Research-worker skeleton
* Phase 6: Safe validation profiles
* Phase 7: Conductor hardening
* Phase 7B: Context hygiene hardening
* Phase 8A: NIM remote dry-run payload builder
* Phase 10: Workflow packs
* Phase 11: Dashboard panels (tasks, approvals, validation, routing, context bundles, logs, budgets)

## Next

### Phase 8B — Real NIM endpoint execution

Add real read-only NIM calls behind:

* approved remote request
* capability validation
* provider validation
* budget check
* NVIDIA_API_KEY presence
* outbox-only output
* JSONL logging

### Phase 8C — Remote result approval and handoff

Promote remote result artifacts only after human approval.

### Phase 9 — Real ML-Intern sandbox integration

Enable sandbox-only ML-Intern execution with no publishing or private-data upload.
