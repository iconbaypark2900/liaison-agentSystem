#!/bin/bash
set -euo pipefail

# Check for ML Research validation
if [[ ! -d "ml_research/" ]]; then
    echo "ml-research validation: not_applicable"
    exit 0
fi

# Check required files for ML Research
if [[ ! -f "ml_research/experiment.yaml" ]]; then
    echo "ml-research validation: fail"
    exit 1
fi

if [[ ! -f "ml_research/metrics.yaml" ]]; then
    echo "ml-research validation: fail"
    exit 1
fi

if [[ ! -f "ml_research/results_schema.json" ]]; then
    echo "ml-research validation: fail"
    exit 1
fi

if [[ ! -f "ml_research/experiment_log.jsonl" ]]; then
    echo "ml-research validation: fail"
    exit 1
fi

echo "ml-research validation: pass"