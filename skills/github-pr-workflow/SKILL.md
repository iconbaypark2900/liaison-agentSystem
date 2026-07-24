---
name: github-pr-workflow
description: Create, review, and close PRs; track CI checks; manage branch lifecycle for post-closeout tasks.
---

# GitHub PR Workflow Skill

## Purpose

Automate the pull request lifecycle: branch creation, commit, PR open, CI status polling, review response, and merge closeout.

## Rules

- Always work on a feature branch named `reflexion/<task-id>` or `feature/<slug>`.
- Write a meaningful PR title (under 70 chars) and body (summary + test plan).
- Do not force-push to main or master.
- Check CI status before requesting review.
- Link the PR to the originating spark-flow task in the body.
- Never merge without CI passing and at least one approval.

## Steps

1. Ensure all changes are committed on a feature branch.
2. Push the branch: `git push -u origin <branch>`.
3. Open the PR: `gh pr create --title "<title>" --body "<body>"`.
4. Poll CI: `gh pr checks <pr-number> --watch`.
5. If CI fails: read the failing job log, apply a fix commit, re-push.
6. Request review: `gh pr review --request <reviewer>`.
7. After approval and green CI: merge with `gh pr merge --squash`.
8. Delete the remote branch after merge.

## Output

- PR URL
- CI verdict (pass / fail + failing job name)
- Merge commit SHA
- Closeout note in spark-flow outbox

## Guardrails

- Never include secrets, credentials, or private keys in commits.
- Do not push directly to protected branches.
- Do not merge if tests are skipped or CI is pending.
