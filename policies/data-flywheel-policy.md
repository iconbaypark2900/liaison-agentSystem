# Data flywheel policy

A data flywheel task turns observed agent traffic into safer, cheaper, and more accurate future agent behavior. It is advisory until approved.

## Required controls

- Use only approved log sources and record the traffic window.
- Redact secrets, credentials, personal data, and proprietary payloads before dataset promotion.
- Compare every candidate against the current baseline.
- Record latency, cost, accuracy, and regression risks in a scorecard.
- Treat LLM-judge scores as evidence, not authority; keep human approval before routing or deployment changes.
- Record rollback conditions before promoting a model, prompt, tool route, or fine-tune.

## Promotion path

```text
logs -> curated examples -> experiment plan -> evaluator scorecard -> approved recommendation -> route/deploy change -> monitoring -> learning
```


## Orchestration controls

- Represent orchestrator jobs as reviewable manifests before automation.
- Record trigger, inputs, outputs, owner, retry behavior, and rollback behavior for each job.
- Keep CI/CD and API integrations advisory until the corresponding scorecard is approved.
- Do not allow scheduled optimization jobs to bypass `approve-artifact`, `decision`, `gate`, or rollback documentation.
- Treat MLRun, NeMo, NIM Proxy, datastore, evaluator, and customizer services as pluggable dependencies, not mandatory local runtime requirements.


## Traceability controls

- Capture enough trace lineage to reproduce the agent path from input to output.
- Record model calls, tool calls, retrieved context, evaluator runs, latency, cost, and safety findings when available.
- Redact secrets and sensitive user data before attaching traces to task artifacts.
- Use trace reports for debugging and promotion evidence, not as automatic deployment approval.
- Treat W&B Weave or other tracing backends as optional integrations; Spark's durable artifact remains `TRACEABILITY_REPORT.md`.
