# Agent recipe: {{RECIPE_ID}}

Exported from Liaison build corpus — use as skill pack, launch recipe, or external agent system prompt.

## Source

- Project: {{PROJECT_KEY}}
- Repo: {{REPO_PATH}}
- Pattern: {{PATTERN_ID}}
- Workflow: {{WORKFLOW}}
- Exported: {{EXPORTED_AT}}
- Task slices: {{TASK_IDS}}

## Launch recipe

{{LAUNCH_RECIPE}}

## Agent chain

{{AGENT_CHAIN}}

## Distilled build steps

{{BUILD_STEPS}}

## Approved artifact patterns

{{APPROVED_ARTIFACTS}}

## Learnings (from slices)

{{LEARNINGS}}

## Failure patterns (executor sessions)

{{FAILURE_PATTERNS}}

## Validation and gates

{{VALIDATION}}

## Suggested hub attach loop

```bash
liaison init <task-id> "<slice goal>" --workflow {{WORKFLOW}}
liaison start-pattern {{PATTERN_ID}} --task-id <task-id>
# terminal: run primary executor (e.g. hermes)
liaison attach <agent> --file report.md --title "Slice report"
liaison approve-artifact <artifact>
liaison validate --profile {{VALIDATION_PROFILE}}
liaison record-build --agent <agent> --action "<what was done>" --outcome "<result>"
liaison close-task
liaison promote-learning --tags "{{PROJECT_KEY}},recipe"
liaison export-agent-recipe --from-project {{PROJECT_KEY}} --write
```

## Risks and operator notes

{{OPERATOR_NOTES}}
