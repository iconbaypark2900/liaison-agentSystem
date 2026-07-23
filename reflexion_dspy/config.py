"""
LM configuration for DSPy.

Tries models in priority order:
  1. Local Ollama (fastest, free, private)
  2. HuggingFace Router (OpenAI-compatible, cloud)
  3. OpenAI (fallback)
"""

from __future__ import annotations

import os
import subprocess


def _ollama_is_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _get_ollama_models() -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()[1:]  # skip header
        return [line.split()[0] for line in lines if line.strip()]
    except Exception:
        return []


# Preferred local models in order
PREFERRED_LOCAL_MODELS = [
    "qwen3-coder:30b",
    "qwen3:6b",
    "llama3.1:8b",
    "mistral:7b",
]

HF_ROUTER_BASE = "https://router.huggingface.co/v1"
HF_ROUTER_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


def configure_dspy(
    prefer_local: bool = True,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """Configure DSPy's global LM. Returns the model name used."""
    import dspy

    hf_token = os.environ.get("HF_TOKEN", "")

    if prefer_local and _ollama_is_running():
        available = _get_ollama_models()
        model = next(
            (m for m in PREFERRED_LOCAL_MODELS if m in available),
            available[0] if available else None,
        )
        if model:
            lm = dspy.LM(
                f"ollama_chat/{model}",
                api_base="http://localhost:11434",
                temperature=temperature,
                max_tokens=max_tokens,
            )
            dspy.configure(lm=lm)
            print(f"[DSPy] Using local Ollama model: {model}")
            return model

    if hf_token:
        lm = dspy.LM(
            f"openai/{HF_ROUTER_MODEL}",
            api_base=HF_ROUTER_BASE,
            api_key=hf_token,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        dspy.configure(lm=lm)
        print(f"[DSPy] Using HuggingFace Router: {HF_ROUTER_MODEL}")
        return HF_ROUTER_MODEL

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        lm = dspy.LM("openai/gpt-4o-mini", temperature=temperature, max_tokens=max_tokens)
        dspy.configure(lm=lm)
        print("[DSPy] Using OpenAI GPT-4o-mini")
        return "openai/gpt-4o-mini"

    raise RuntimeError(
        "No LM available. Set HF_TOKEN for HuggingFace Router, "
        "OPENAI_API_KEY for OpenAI, or run Ollama locally."
    )
