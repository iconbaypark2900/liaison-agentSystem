#!/usr/bin/env python3
"""CLI tool to check the health of a local DGX Spark environment."""

import argparse
import json
import os
import platform
import shutil
import sys
import urllib.request
import urllib.error


def check_ollama_api() -> tuple[bool, list[str]]:
    """Check the local Ollama API and return reachability plus model names."""
    try:
        response = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5)
        raw_body = response.read()
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8")
        payload = json.loads(raw_body)
    except Exception:
        return False, []

    models: list[str] = []
    for item in payload.get("models", []):
        name = item.get("name")
        if isinstance(name, str):
            models.append(name)

    return True, models


def check_model_installed(models, expected_models):
    """Check if all expected models are installed.
    
    Args:
        models: List of installed model names
        expected_models: List of expected model names
        
    Returns:
        dict: Model status report
    """
    model_status = {}
    for model in expected_models:
        model_status[model] = model in models
    return model_status


def main():
    """Main CLI entry point."""
    # Print Python information
    print("Python version:", sys.version)
    print("Platform:", platform.system(), platform.release(), platform.machine())
    print("Current working directory:", os.getcwd())
    
    # Check if ollama is on PATH
    ollama_exists = shutil.which("ollama") is not None
    print("Ollama on PATH:", "Yes" if ollama_exists else "No")
    
    # Check Ollama API
    reachable, models = check_ollama_api()
    
    # Print model information
    print("Installed Ollama models:")
    for model in models:
        print(f"  - {model}")
        
    # Check expected models
    expected_models = [
        "qwen3.6:latest",
        "qwen3-coder:30b", 
        "gpt-oss:20b",
        "nemotron-3-nano:30b-a3b-q4_K_M"
    ]
    
    model_status = check_model_installed(models, expected_models)
    print("Expected model presence:")
    for model, installed in model_status.items():
        print(f"  - {model}: {'installed' if installed else 'missing'}")
    
    # Exit with appropriate code
    if not ollama_exists:
        print("\nError: Ollama is not installed or not on PATH")
        return 1
    elif not reachable:
        print("\nError: Ollama API is not reachable at http://127.0.0.1:11434/api/tags")
        return 1
    else:
        print("\nSuccess: Ollama environment is healthy")
        return 0


if __name__ == "__main__":
    sys.exit(main())