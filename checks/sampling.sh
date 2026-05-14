#!/bin/bash
set -euo pipefail

# Check for Sampling validation
if [[ ! -f "ml_research/sampling_plan.yaml" ]]; then
    echo "sampling validation: not_applicable"
    exit 0
fi

# Check required files for Sampling
if [[ ! -f "ml_research/sampling_plan.yaml" ]]; then
    echo "sampling validation: fail"
    exit 1
fi

if [[ ! -f "ml_research/sampling_results.jsonl" ]]; then
    echo "sampling validation: fail"
    exit 1
fi

echo "sampling validation: pass"