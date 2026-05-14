#!/bin/bash
set -euo pipefail

# Check for Security validation
# Check for obvious secret files
found_secret=false

if [[ -f ".env" ]]; then
    echo "security validation: fail - found secret file: .env"
    found_secret=true
fi

# Check for *.env files
for file in .*.env; do
    if [[ -f "$file" && "$file" != "*.env" ]]; then
        echo "security validation: fail - found secret file: $file"
        found_secret=true
    fi
done

# Check for *.local.json files
for file in .*.local.json; do
    if [[ -f "$file" && "$file" != "*.local.json" ]]; then
        echo "security validation: fail - found secret file: $file"
        found_secret=true
    fi
done

if [[ "$found_secret" == true ]]; then
    exit 1
fi

# Check .gitignore for .spark-flow/
if [[ -f ".gitignore" ]]; then
    if ! grep -q "\.spark-flow/" ".gitignore"; then
        echo "security validation: warning - .spark-flow/ not ignored in .gitignore"
    fi
fi

# Check for SECURITY.md - warning only
if [[ ! -f "SECURITY.md" ]]; then
    echo "security validation: warning - SECURITY.md not found"
fi

echo "security validation: pass"