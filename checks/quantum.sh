#!/bin/bash
set -euo pipefail

# Check for Quantum validation
if [[ ! -d "quantum/" ]]; then
    echo "quantum validation: not_applicable"
    exit 0
fi

# Check required files for Quantum
if [[ ! -f "quantum/quantum_config.yaml" ]]; then
    echo "quantum validation: fail"
    exit 1
fi

if [[ ! -f "quantum/backend_registry.yaml" ]]; then
    echo "quantum validation: fail"
    exit 1
fi

if [[ ! -f "quantum/benchmark_plan.yaml" ]]; then
    echo "quantum validation: fail"
    exit 1
fi

if [[ ! -f "quantum/results_schema.json" ]]; then
    echo "quantum validation: fail"
    exit 1
fi

if [[ ! -f "quantum/experiment_log.jsonl" ]]; then
    echo "quantum validation: fail"
    exit 1
fi

echo "quantum validation: pass"