# Changelog

## phase-8a-nim-dry-run-payload

* Added NIM remote dry-run payload generation.
* Preserved remote-run --stub.
* Added remote-run --real --dry-run.
* Writes payload preview JSON and dry-run summary markdown.
* Logs remote_dry_run records with zero estimated cost.

## phase-7b-context-hygiene

* Fixed context bundle phase filtering.
* Context bundles now include only approved outputs from prior phases.

## phase-7-conductor-hardening

* Added state checks, event inspection, phase-specific skills, and context --show.

## phase-6-validation-profiles

* Added safe artifact-only validation profiles.

## phase-5-research-worker-skeleton

* Added research-worker request/approval/stub flow.

## phase-4-remote-capability-skeleton

* Added capability-based remote request/approval/stub flow.
