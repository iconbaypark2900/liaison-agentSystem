---
name: systematic-debugging
description: Bounded failure investigation — reproduce, isolate, root-cause, and patch a bug within a fixed number of steps.
---

# Systematic Debugging Skill

## Purpose

Investigate failures in a structured, bounded way. Do not thrash. Pick a hypothesis, test it, eliminate it, move to the next.

## Rules

- Reproduce the failure first with a minimal repro command before reading code.
- Form one hypothesis at a time; test it directly.
- Read error messages and tracebacks fully before forming hypotheses.
- Do not change multiple variables at once — isolate one change per round.
- Stop after 5 hypotheses and escalate if unresolved.
- Write a root cause summary even if the fix is trivial.

## Steps

1. Reproduce: run the failing command, capture full output.
2. Identify: find the exact exception type, file, and line number.
3. Hypothesize: list at most 3 candidate causes ordered by likelihood.
4. Isolate: add a minimal print/log or write a one-line test to confirm the top hypothesis.
5. Fix: apply the minimal change that addresses the root cause.
6. Verify: re-run the repro command; confirm the failure is gone.
7. Regression check: run the full test suite.

## Output

- Reproduction command
- Root cause summary (1-3 sentences)
- Fix (diff or patch)
- Verification command + result
- Regression test added (or reason why not needed)

## Guardrails

- Do not delete passing tests to make the suite green.
- Do not suppress errors with broad `except Exception` catches.
- Do not add workarounds for a symptom when the root cause is identifiable.
