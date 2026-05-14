---
name: testing-hardening
description: Improve or review tests for software, AI app, RAG, or scientific workflows.
---

# Testing Hardening Skill

## Purpose

Ensure implementation changes are proven by meaningful tests.

## Rules

- Test public behavior, not private implementation details.
- Mock network and external service calls in unit tests.
- Avoid paid API calls in tests unless explicitly approved.
- Include success and failure paths.
- Test CLI exit codes, API responses, tool schemas, and validation outputs where relevant.
- Do not add new test dependencies unless already present or approved.

## Output

- Missing test cases
- Risky untested behavior
- Minimal test additions
- Validation commands
