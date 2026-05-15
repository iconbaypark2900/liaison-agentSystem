# Spark Agent System — Full Project Overview

## 1. Executive Summary

Spark Agent System is a local-first, human-in-the-loop agentic engineering control plane designed to coordinate coding agents, local models, governed remote endpoint models, research workers, validation scripts, policies, and project workflows.

The project is being built on the DGX Spark environment as a practical operating layer for a controlled engineering department. Its purpose is not just to call models. Its purpose is to make model-assisted engineering safe, inspectable, repeatable, and auditable.

The current system can:

- Route tasks to local models and coding agents.
- Resolve capabilities from declarative YAML configuration.
- Generate context bundles so agents do not rely on chat history.
- Run human approval gates before model/research execution.
- Create remote endpoint requests and dry-run NIM payloads.
- Create research-worker requests for tools like ML-Intern.
- Run safe artifact-only validation profiles.
- Track budgets and JSONL logs.
- Preserve rollback points through Git tags.

The system is currently at **Phase 8A**, where NVIDIA NIM remote calls are still dry-run only. Real endpoint calls are not enabled yet.

---

## 2. Project Purpose

The project exists to solve a specific problem: using many models and coding agents without losing control of context, costs, files, approvals, or execution boundaries.

The system is designed around a controlled flow:

```text
request -> context -> approval -> execution/dry-run -> validation -> review -> commit
```

It is meant to support work across:

- AI/ML engineering
- Retrieval-Augmented Generation systems
- Scientific research workflows
- Quantum computing experiments
- Frontend/backend software development
- Agentic engineering automation
- Remote endpoint model usage
- Research-worker sampling and evaluation

The long-term goal is to become an internal engineering department where specialized agents and models can safely contribute to projects while the human remains the final authority.

---

## 3. Design Philosophy

## 3.1 Local-first by default

Local models and local agents should be used whenever possible. Hosted endpoint models should only be used when they provide clear value, such as long-context architecture review, repo-wide reasoning, or specialized scientific/quantum analysis.

## 3.2 Human approval before external execution

Remote endpoint calls, research-worker runs, publication actions, paid compute, and dataset upload actions must require human approval.

## 3.3 Context bundles are the source of truth

Agents should not rely on chat history. The system generates task-specific context bundles containing the task description, approved prior outputs, handoff files, relevant policies, resolved skills, validation summaries, and required output paths.

## 3.4 Remote outputs are read-only until approved

Remote endpoint outputs are advisory. They are written to outbox artifacts and cannot directly edit source files.

## 3.5 Every important action should create an artifact

The system records task outputs, approvals, validation summaries, dry-run payloads, logs, and Git commits/tags.

## 3.6 Runtime state is not source code

Runtime workflow state is kept out of the source repo. Directories such as `.spark-flow/` and `logs/` should not be committed.

---

## 4. Current Repository Structure

The main source repo is:

```text
~/spark/agent-system
```

Recommended structure:

```text
agent-system/
├── README.md
├── PROJECT_SPEC.md
├── ROADMAP.md
├── CHANGELOG.md
├── .gitignore
├── bin/
│   └── spark-flow
├── checks/
│   ├── python.sh
│   ├── rag.sh
│   ├── ml-research.sh
│   ├── sampling.sh
│   ├── quantum.sh
│   └── security.sh
├── config/
│   ├── budget_limits.yaml
│   ├── capability_routes.yaml
│   ├── model_routes.yaml
│   ├── provider_registry.yaml
│   ├── research_workers.yaml
│   ├── skill_resolution.yaml
│   └── validation_profiles.yaml
├── departments/
├── policies/
├── skills/
├── templates/
├── workflows/
├── docs/
│   ├── phases/
│   ├── architecture.md
│   ├── operating_model.md
│   └── command_reference.md
└── examples/
    └── spark-flow-demo/
```

The runtime demo workspace is:

```text
~/spark/flow-demos/spark-flow-demo
```

The demo workspace contains `.spark-flow/` task state, which should not be committed into the source repo.

---

## 5. The `spark-flow` CLI

`spark-flow` is the conductor command. It coordinates tasks, phases, context, approvals, validation, routing, remote dry-runs, and research-worker dry-runs.

Current command families include:

```text
init
start
approve
reject
status
doctor
stop
routes
route
workflows
validate
budget
capabilities
capability
validations
skills
research-workers
context
remote-capabilities
request-remote
approve-remote
remote-run
request-research
approve-research
research-run
events
skills-for
check-state
```

The most important command patterns are:

```bash
spark-flow init <task-id> "description"
spark-flow start plan
spark-flow approve plan
spark-flow start build
spark-flow validate --profile security
spark-flow context build --show
spark-flow check-state
```

---

## 6. Task Lifecycle

A task has phases:

```text
plan -> build -> patch -> review -> close
```

Each task lives under:

```text
.spark-flow/tasks/<task-id>/
```

Typical task structure:

```text
.spark-flow/tasks/<task-id>/
├── TASK.md
├── STATE.txt
├── CHECKS.md
├── prompts/
│   ├── plan.md
│   ├── build.md
│   └── review.md
├── outbox/
│   ├── plan.md
│   ├── build.md
│   ├── review.md
│   └── test.<profile>.md
├── approved/
│   └── plan.md
├── handoff/
│   └── build.md
├── feedback/
├── context/
│   ├── build.md
│   └── build.manifest.json
└── events.jsonl
```

The human approves or rejects outputs:

```bash
spark-flow approve build
spark-flow reject build "reason"
```

The system intentionally separates raw model outputs from approved outputs.

---

## 7. Context Bundle System

The context bundle system was introduced so agents operate from a controlled source of truth.

Command:

```bash
spark-flow context <phase> --show
```

Generated files:

```text
.spark-flow/tasks/<task-id>/context/<phase>.md
.spark-flow/tasks/<task-id>/context/<phase>.manifest.json
```

A context bundle contains:

- Task ID
- Task description
- Requested phase
- Current task state
- Approved prior phase outputs
- Handoff file for the requested phase
- Resolved skills
- Relevant policies
- Validation summaries
- Required output path
- Instruction that chat history is not the source of truth

Phase 7B fixed context hygiene so bundles only include approved outputs from phases prior to the requested phase.

Correct behavior:

```text
context plan   -> no prior outputs
context build  -> approved/plan.md only
context patch  -> approved/plan.md, approved/build.md if present
context review -> approved/plan.md, approved/build.md, approved/patch.md if present
context close  -> approved/plan.md, approved/build.md, approved/patch.md if present, approved/review.md
```

---

## 8. Model Routing Layer

The model routing layer is configured in:

```text
config/model_routes.yaml
```

It separates local models, remote hosted endpoint models, and quantum/specialized models.

## 8.1 Local models

Local models are served through Ollama or local tooling. They are preferred for most coding and review tasks because they are cost-controlled and private.

Current local model roles include:

### stable

```text
provider: ollama
model: qwen3.6:latest
agent: opencode
```

Purpose:

- General local reasoning
- Stable fallback route
- Lightweight planning or support work

### coder

```text
provider: ollama
model: qwen3-coder:30b
agent: opencode
```

Purpose:

- Code implementation
- CLI development
- Test scaffolding
- Refactoring

### patch

```text
provider: ollama
model: gpt-oss:20b
agent: codex
```

Purpose:

- Patch generation
- Small fixes
- Local corrective edits

### reviewer

```text
provider: ollama
model: nemotron-3-nano:30b-a3b-q4_K_M
agent: claude
```

Purpose:

- Local review
- Risk checking
- Architecture sanity checks
- Human-readable critique

---

## 8.2 Remote models

Remote models are exposed through NVIDIA NIM or other hosted endpoint providers. They require approval and are currently dry-run only through Phase 8A.

### deepseek_v4_flash

```text
provider: nvidia_nim
model: deepseek-ai/deepseek-v4-flash
```

Purpose:

- Long-context architecture review
- Repo-wide reasoning
- Hard debugging
- Research synthesis

Trigger tags:

```text
#deepseek
#long_context
#repo_wide
#hard_debug
#architecture
```

### qwen3_coder_480b

```text
provider: nvidia_nim
model: qwen/qwen3-coder-480b-a35b-instruct
```

Purpose:

- Large coding strategy
- Multi-file refactor planning
- Complex implementation design
- Test strategy generation

Trigger tags:

```text
#big_refactor
#coding_plan
#test_strategy
```

---

## 8.3 Quantum and specialized endpoint models

### ising_calibration

```text
provider: nvidia_nim
model: nvidia/ising-calibration-1-35b-a3b
```

Purpose:

- Quantum calibration analysis
- QEC plot interpretation
- Quantum chart review
- Ising-style advisory workflows

Trigger tags:

```text
#ising
#calibration
#qec_plots
#quantum_chart_analysis
```

This route is advisory and must remain read-only until explicitly approved.

---

## 9. Capability Routing Layer

Capabilities are configured in:

```text
config/capability_routes.yaml
```

Capabilities abstract away raw model IDs. Workflows should request a capability, not a specific model.

Example:

```bash
spark-flow route "#long_context #architecture"
```

The system recommends a capability-backed route.

Current capabilities include:

## 9.1 local_implementation

Purpose:

- Implement local code, tests, configs, and small refactors.

Preferred route:

```text
coder
```

Remote allowed:

```text
false
```

## 9.2 local_review

Purpose:

- Review architecture, risks, diffs, and implementation quality locally.

Preferred route:

```text
reviewer
```

Remote allowed:

```text
false
```

## 9.3 long_context_architecture

Purpose:

- Use hosted endpoint for long-context architecture or repo-wide reasoning.

Preferred routes:

```text
deepseek_v4_flash
qwen3_coder_480b
```

Remote allowed:

```text
true
```

Remote read-only:

```text
true
```

## 9.4 large_coding_strategy

Purpose:

- Use hosted endpoint for multi-file refactor strategy or coding plans.

Preferred routes:

```text
qwen3_coder_480b
deepseek_v4_flash
```

Remote allowed:

```text
true
```

Remote read-only:

```text
true
```

## 9.5 research_synthesis

Purpose:

- Use hosted endpoint for paper/research synthesis and high-level technical reports.

Preferred route:

```text
deepseek_v4_flash
```

## 9.6 quantum_calibration_analysis

Purpose:

- Use NVIDIA Ising-style analysis for QPU calibration charts/reports.

Preferred route:

```text
ising_calibration
```

## 9.7 repetitive_sampling

Purpose:

- Use ML-Intern or local code to run repeated scientific, ML, RAG, or QML sampling jobs.

Preferred routes:

```text
ml_intern
coder
```

---

## 10. Remote Endpoint Governance Lane

The remote endpoint lane is designed to make hosted endpoint usage safe.

Current flow:

```text
request-remote -> approve-remote -> remote-run --stub
request-remote -> approve-remote -> remote-run --real --dry-run
```

Commands:

```bash
spark-flow request-remote long_context_architecture "Review this architecture #long_context"
spark-flow approve-remote long_context_architecture
spark-flow remote-run long_context_architecture --stub
spark-flow remote-run long_context_architecture --real --dry-run
```

## 10.1 Stub mode

Command:

```bash
spark-flow remote-run <capability> --stub
```

Behavior:

- Requires approved remote request.
- Resolves capability and provider/model.
- Writes stub output to outbox.
- Logs the action.
- Makes no endpoint call.

Output:

```text
.spark-flow/tasks/<task>/outbox/remote.<capability>.md
```

## 10.2 NIM dry-run mode

Command:

```bash
spark-flow remote-run <capability> --real --dry-run
```

Behavior:

- Requires approved remote request.
- Requires remote_allowed: true.
- Requires remote_read_only: true.
- Requires provider: nvidia_nim.
- Checks whether NVIDIA_API_KEY exists without printing it.
- Writes request payload preview.
- Writes dry-run markdown summary.
- Logs `remote_dry_run`.
- Makes no network call.
- Executes no model.
- Uses no paid compute.

Outputs:

```text
.spark-flow/tasks/<task>/outbox/remote_payload.<capability>.json
.spark-flow/tasks/<task>/outbox/remote_dry_run.<capability>.md
```

Log:

```text
~/spark/agent-system/logs/remote_call_log.jsonl
```

Current Phase 8A status:

```text
NIM payload building works.
Real endpoint calls are not enabled yet.
```

---

## 11. Research Worker Governance Lane

Research workers are configured in:

```text
config/research_workers.yaml
```

The current planned worker is:

```text
ml_intern
provider: huggingface
tool: ml-intern
status: planned
sandbox_only: true
requires_human_approval: true
```

Use cases:

- Dataset discovery
- Dataset inspection
- Repetitive sampling
- Training iteration
- Evaluation loops
- Model card generation
- Dataset card generation
- Hugging Face Hub preparation

Current flow:

```bash
spark-flow request-research ml_intern "Find datasets for RAG evaluation"
spark-flow approve-research ml_intern
spark-flow research-run ml_intern --stub
```

Current status:

```text
Research-worker lane is stub-only.
Real ML-Intern execution is not enabled yet.
```

Future real mode:

```bash
spark-flow research-run ml_intern --real --sandbox
```

Guardrails required before real execution:

- No publishing without approval.
- No private data upload.
- No paid compute without approval.
- Output must remain sandbox-only until promoted.
- Dataset policy must be enforced.

---

## 12. Skill Resolution Layer

Skills are resolved from:

```text
config/skill_resolution.yaml
```

Command:

```bash
spark-flow skills-for <workflow_name> <phase>
```

Example:

```bash
spark-flow skills-for python-cli build
```

Expected output:

```text
spark-flow-build
testing-hardening
dependency-discipline
```

Skills are used to inform which instructions, checks, and behavior patterns should apply to a workflow phase.

Planned skill categories:

- CLI build skill
- Testing hardening
- Dependency discipline
- RAG evaluation
- Scientific validation
- Quantum benchmarking
- Frontend/backend testing
- Security review
- Dataset policy compliance

---

## 13. Validation Profiles

Validation profiles are configured in:

```text
config/validation_profiles.yaml
```

Scripts live in:

```text
checks/
```

Current validation scripts:

```text
checks/python.sh
checks/rag.sh
checks/ml-research.sh
checks/sampling.sh
checks/quantum.sh
checks/security.sh
```

Command:

```bash
spark-flow validate --profile <profile>
```

Supported profiles:

## 13.1 python

Used for Python projects.

Typical checks:

- pytest
- compileall
- project-specific Python validation

## 13.2 rag

Artifact-only validation for RAG packs.

Checks for files such as:

```text
rag/retrieval_eval.yaml
rag/eval_dataset.jsonl
rag/golden_answers.jsonl
```

If no RAG pack exists, returns `not_applicable`.

## 13.3 ml-research

Artifact-only validation for ML research packs.

Checks for files such as:

```text
ml_research/experiment.yaml
ml_research/metrics.yaml
ml_research/results_schema.json
ml_research/experiment_log.jsonl
```

## 13.4 sampling

Artifact-only validation for sampling plans and results.

Checks:

```text
ml_research/sampling_plan.yaml
ml_research/sampling_results.jsonl
```

## 13.5 quantum

Artifact-only validation for quantum workflow packs.

Checks:

```text
quantum/quantum_config.yaml
quantum/backend_registry.yaml
quantum/benchmark_plan.yaml
quantum/results_schema.json
quantum/experiment_log.jsonl
```

No QPU calls are allowed in validation scripts.

## 13.6 security

Checks for common security hygiene:

- `.env`
- `*.env`
- `*.local.json`
- `.spark-flow/` ignored by `.gitignore`
- optional `SECURITY.md`

Security validation warns about missing `SECURITY.md` but does not fail the demo.

---

## 14. Policy Layer

Policies live in:

```text
policies/
```

Current policies:

```text
context-policy.md
dataset-policy.md
mcp-tool-policy.md
promotion-policy.md
remote-model-policy.md
scientific-validation-policy.md
```

## 14.1 Context policy

Controls how context is assembled, filtered, and shared.

Rules:

- Agents must read generated context bundles.
- Remote endpoints receive curated context only.
- Secrets are never included.
- Chat history is not source of truth.

## 14.2 Dataset policy

Controls dataset discovery, profiling, usage, and publishing.

Rules:

- Record source, license, schema, splits, size, risks, PII assessment, and leakage risk.
- No private data upload without approval.
- Dataset cards require review before publishing.

## 14.3 MCP tool policy

Controls tool access for MCP-connected agents.

Rules:

- MCP servers must be allowlisted.
- Tools are read-only by default.
- Destructive tools require approval.
- Tool calls must be logged.

## 14.4 Promotion policy

Defines artifact promotion:

```text
outbox -> approved -> validated -> integrated -> committed
```

## 14.5 Remote model policy

Controls hosted endpoint usage.

Rules:

- Local-first by default.
- Remote calls require explicit approval.
- Remote outputs are read-only.
- Remote outputs must be logged.
- Remote routes use capabilities, not hardcoded model IDs.

## 14.6 Scientific validation policy

Controls experimental claims and reproducibility.

Rules:

- Claims must map to metrics.
- Experiment logs are append-only.
- Baselines must be recorded.
- Failed runs must be logged.
- Statistical uncertainty should be recorded when relevant.

---

## 15. Budget and Logging

Budget configuration:

```text
config/budget_limits.yaml
```

Budget command:

```bash
spark-flow budget
```

Current budget behavior:

- Reports remote usage.
- Reads JSONL logs.
- Shows daily and monthly estimated cost.

Future behavior:

- Enforce daily/monthly limits.
- Block remote calls when budget is exceeded.
- Require explicit override approval for costly execution.

Logs:

```text
~/spark/agent-system/logs/remote_call_log.jsonl
~/spark/agent-system/logs/ml_intern_runs.jsonl
```

Logs should not be committed.

---

## 16. Current Completed Phases

## Phase 1 — Control-plane registries and policies

Added foundational config and policy files:

- capability routes
- validation profiles
- skill resolution
- research workers
- governance policies

Tag:

```text
phase-1-control-plane
```

## Phase 2 — Read-only inspection commands

Added commands for inspecting configuration.

Tag:

```text
phase-2-readonly-inspection
```

## Phase 3 — Context bundle generation

Added context generation for task phases.

Tag:

```text
phase-3-context-bundles
```

## Phase 4 — Capability-based remote request skeleton

Added:

```bash
spark-flow remote-capabilities
spark-flow request-remote <capability> "request"
spark-flow approve-remote <capability>
spark-flow remote-run <capability> --stub
```

Tag:

```text
phase-4-remote-capability-skeleton
```

## Phase 5 — Research-worker / ML-Intern skeleton

Added:

```bash
spark-flow request-research ml_intern "request"
spark-flow approve-research ml_intern
spark-flow research-run ml_intern --stub
```

Tag:

```text
phase-5-research-worker-skeleton
```

## Phase 6 — Safe domain validation profiles

Added artifact-only validators for:

- RAG
- ML research
- sampling
- quantum
- security

Tag:

```text
phase-6-validation-profiles
```

## Phase 7 — Conductor hardening

Added:

```bash
spark-flow check-state
spark-flow events
spark-flow skills-for <workflow> <phase>
spark-flow context <phase> --show
```

Tag:

```text
phase-7-conductor-hardening
```

## Phase 7B — Context hygiene hardening

Fixed context bundles so they only include approved outputs from phases prior to the requested phase.

Tag:

```text
phase-7b-context-hygiene
```

## Phase 8A — NIM remote dry-run payload builder

Added:

```bash
spark-flow remote-run <capability> --real --dry-run
```

This generates NIM payload previews without calling endpoints.

Tag:

```text
phase-8a-nim-dry-run-payload
```

---

## 17. Current Git Tags

Current rollback tags:

```text
phase-1-control-plane
phase-2-readonly-inspection
phase-3-context-bundles
phase-4-remote-capability-skeleton
phase-5-research-worker-skeleton
phase-6-validation-profiles
phase-7-conductor-hardening
phase-7b-context-hygiene
phase-8a-nim-dry-run-payload
```

Rollback example:

```bash
git checkout phase-8a-nim-dry-run-payload
```

Compare phases:

```bash
git diff phase-7b-context-hygiene..phase-8a-nim-dry-run-payload
```

---

## 18. Current Safety Boundary

Currently enabled:

```text
Local task orchestration: enabled
Context bundle generation: enabled
Validation profiles: enabled
Remote request/approval: enabled
Remote stub execution: enabled
NIM dry-run payload generation: enabled
Research-worker stub execution: enabled
```

Currently disabled:

```text
Real NIM endpoint calls
Real ML-Intern execution
Automatic source-code edits from remote outputs
Publishing to Hugging Face
Paid compute execution
QPU/hardware execution
Automatic handoff from remote output into local build
```

---

## 19. Future Components Being Built

## Phase 8B — Real NIM endpoint execution

Planned command:

```bash
spark-flow remote-run <capability> --real
```

Guardrails:

- approved remote request required
- provider must be `nvidia_nim`
- `NVIDIA_API_KEY` required
- budget check required
- remote capability must be read-only
- output written only to outbox
- no source file edits
- JSONL logging required

Expected outputs:

```text
.spark-flow/tasks/<task>/outbox/remote_response.<capability>.json
.spark-flow/tasks/<task>/outbox/remote_result.<capability>.md
```

## Phase 8C — Remote result approval and handoff

Planned flow:

```text
remote_result -> approve-remote-result -> handoff -> local build agent
```

Purpose:

- Keep remote endpoint output advisory until approved.
- Prevent automatic code edits from remote output.
- Convert approved remote review into local implementation instructions.

## Phase 8D — Budget enforcement

Planned command:

```bash
spark-flow budget-check --provider nvidia_nim --estimated-cost 0.25
```

Purpose:

- Enforce daily and monthly remote budgets.
- Block calls before they happen if budget is exceeded.

## Phase 9 — Real ML-Intern sandbox integration

Planned command:

```bash
spark-flow research-run ml_intern --real --sandbox
```

Purpose:

- Dataset discovery
- Dataset profiling
- Repetitive sampling
- Evaluation loops
- Model card generation
- Dataset card generation

Guardrails:

- no publishing without approval
- no private upload
- no paid compute without approval
- sandbox output only

## Phase 10 — Domain workflow packs

Planned workflow packs:

```text
workflows/rag-app.yaml
workflows/quantum-benchmark.yaml
workflows/ml-research.yaml
workflows/frontend-backend.yaml
workflows/scientific-paper.yaml
workflows/portfolio-optimizer.yaml
workflows/qids-module.yaml
```

Each workflow should define:

- phases
- allowed agents
- required skills
- validation profile
- allowed remote capabilities
- required artifacts
- promotion rules

## Phase 11 — Dashboard/control panel

Recommended stack:

```text
FastAPI backend
Next.js frontend
SQLite local state
Tailwind / shadcn UI
```

Dashboard views:

- active task
- current phase
- approvals
- context bundle
- remote requests
- research requests
- validation status
- budget usage
- event log
- Git tag / rollback point

## Phase 12 — MCP/tool registry integration

Planned files:

```text
config/mcp_servers.yaml
config/tool_registry.yaml
config/agent_permissions.yaml
```

Purpose:

- Allow agents to use tools safely.
- Keep destructive tools approval-gated.
- Make tool access task-scoped and logged.

## Phase 13 — CI and quality gates

Planned commands:

```bash
spark-flow validate --all
spark-flow pre-commit-check
spark-flow release-check
```

Validation groups:

- Python
- TypeScript
- RAG
- ML research
- sampling
- quantum
- security
- docs

## Phase 14 — Apply to real projects

Best first real projects:

1. `quantum-hybrid-portfolio`
2. `hybrid-qml-kg-poc`
3. QIDS ecosystem
4. document deduplication reviewer
5. MQAI materials discovery

---

## 20. Recommended Next Step

The next safest technical phase is:

```text
Phase 8B — Real NIM endpoint execution
```

But it should be implemented narrowly:

```text
Only one capability: long_context_architecture
Only one provider: nvidia_nim
Only one behavior: read-only remote review output to outbox
No source edits
No automatic handoff
No autonomous chaining
```

This preserves the safety model while adding the first real hosted endpoint capability.

---

## 21. Summary

Spark Agent System is becoming a governed, local-first agentic engineering department for AI/ML, quantum, RAG, scientific research, and full-stack project development.

It currently provides:

- local model routing
- capability routing
- policy-aware context bundles
- human approval gates
- remote dry-run governance
- research-worker governance
- artifact-only validation
- budget visibility
- event/state inspection
- Git-tagged phase history

The next major milestone is controlled real endpoint execution through NVIDIA NIM, followed by remote result approval, real ML-Intern sandboxing, workflow packs, dashboarding, MCP tool control, and CI-style quality gates.

The system is intentionally being built in small, auditable phases so every new capability is governed before it can execute real external actions.

