#!/bin/bash
set -euo pipefail

# Check for RAG validation
if [[ ! -d "rag/" ]]; then
    echo "rag validation: not_applicable"
    exit 0
fi

# Check required files for RAG
if [[ ! -f "rag/retrieval_eval.yaml" ]]; then
    echo "rag validation: fail"
    exit 1
fi

if [[ ! -f "rag/eval_dataset.jsonl" ]]; then
    echo "rag validation: fail"
    exit 1
fi

if [[ ! -f "rag/golden_answers.jsonl" ]]; then
    echo "rag validation: fail"
    exit 1
fi

echo "rag validation: pass"