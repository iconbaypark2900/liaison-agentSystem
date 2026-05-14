# Context Policy

## Purpose

Prevent context loss, over-sharing, and uncontrolled prompt growth.

## Context tiers

1. Task-only context:
   - task description
   - current phase
   - required output

2. Standard engineering context:
   - approved handoffs
   - acceptance criteria
   - relevant files
   - policies
   - skills

3. Domain context:
   - RAG configs
   - ML experiment configs
   - quantum configs
   - validation logs

4. Remote endpoint context:
   - curated summaries only
   - no secrets
   - no unnecessary private files
   - human-approved request text

## Rules

- Agents must read generated context bundles instead of relying on chat history.
- Remote endpoints receive only approved, curated context.
- Secrets, `.env`, and private credentials are never included.
