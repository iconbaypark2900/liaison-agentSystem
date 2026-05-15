# AGENTS.md

## Workflow

This project uses `spark-flow`.

Model roles:

- `nemotron-3-nano:30b-a3b-q4_K_M`: planning, architecture review, risk review.
- `qwen3-coder:30b`: implementation, tests, bug fixes.
- `gpt-oss:20b`: minimal Codex patch fallback.
- `qwen3.6:latest`: stable closeout/default model.

## Universal rules

- Inspect files before editing.
- Stay within the current spark-flow task thread.
- Use only the Python standard library.
- Do not install dependencies.
- Do not use `psutil`.
- Do not delete unrelated files.
- Prefer small, typed, testable functions.
- Add or update tests for implementation changes.
- Show files changed and exact validation commands.
- If something is ambiguous, make the smallest safe assumption and state it.

## PLAN phase

- Do not edit project source files.
- Create acceptance criteria.
- Define allowed files.
- Define forbidden files/directories.
- Define validation commands.
- Produce a BUILD prompt.

## BUILD phase

- Inspect files first.
- Touch only files needed for the task.
- Implement the smallest useful slice.
- Add or update tests.
- Use only the standard library for runtime code.
- Do not install dependencies.

## PATCH phase

- Fix only listed failures or review issues.
- Do not redesign.
- Do not touch unrelated files.
- Preserve existing style.

## REVIEW phase

- Do not edit files.
- Review correctness, tests, maintainability, security/privacy, and scope.
- Return approve / approve with changes / reject.

## CLOSE phase

- Update task docs if needed.
- Summarize validation.
- List follow-up tasks.
- Produce a ready-to-commit message.

## Preferred validation commands

```bash
python -m pip install -e .
spark-demo-health
python -m pytest
```
