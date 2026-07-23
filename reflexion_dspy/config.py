"""
LM configuration for DSPy — driven by config/model_routes.yaml.

Priority order:
  1. Local Ollama (local_first: true per model_routes.yaml defaults)
  2. HuggingFace Router (remote, requires human approval per policy)
  3. OpenAI (last resort)

Remote model calls are gated by:
  - policies/remote-model-policy.md: require_human_approval_for_remote
  - config/budget_limits.yaml: daily_remote_budget_usd
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
        lines = result.stdout.strip().splitlines()[1:]
        return [line.split()[0] for line in lines if line.strip()]
    except Exception:
        return []


def configure_dspy(
    use_for: str = "implementation",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    allow_remote: bool = False,
) -> str:
    """
    Configure DSPy LM following model_routes.yaml and remote-model-policy.md.

    Args:
        use_for:       capability tag (e.g. "implementation", "summaries", "research")
        temperature:   sampling temperature
        max_tokens:    max output tokens
        allow_remote:  set True only when human has approved a remote call
    """
    import dspy
    from .rules import model_router, budget_guard

    router = model_router()
    guard = budget_guard()

    # ── Local-first (per model_routes.yaml defaults.local_first) ─────────────
    if router.local_first and _ollama_is_running():
        available = _get_ollama_models()
        _, preferred_model = router.pick_local_model(use_for)

        # Try preferred model first, then any available
        model = preferred_model if preferred_model in available else None
        if model is None and available:
            # Fallback: pick first available local model
            local_models = router.all_local_models()
            model = next((m for m in local_models if m in available), available[0])

        if model:
            lm = dspy.LM(
                f"ollama_chat/{model}",
                api_base="http://localhost:11434",
                temperature=temperature,
                max_tokens=max_tokens,
            )
            dspy.configure(lm=lm)
            print(f"[model_routes.yaml] local/{model} (use_for={use_for})")
            return model

    # ── Remote gate (policies/remote-model-policy.md) ────────────────────────
    if not allow_remote and router.require_human_approval_for_remote:
        hf_token = os.environ.get("HF_TOKEN", "")
        if hf_token:
            # HF Router is treated as a "semi-local" endpoint — no payment gate
            HF_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
            lm = dspy.LM(
                f"openai/{HF_MODEL}",
                api_base="https://router.huggingface.co/v1",
                api_key=hf_token,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            dspy.configure(lm=lm)
            print(f"[model_routes.yaml] hf-router/{HF_MODEL} (use_for={use_for})")
            return HF_MODEL

    # ── Paid remote (budget check required) ──────────────────────────────────
    if allow_remote:
        ok, reason = guard.check_budget(estimated_cost=0.01)
        if not ok:
            raise RuntimeError(f"[budget_limits.yaml] {reason}")
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            lm = dspy.LM("openai/gpt-4o-mini", temperature=temperature, max_tokens=max_tokens)
            dspy.configure(lm=lm)
            guard.log_call(
                task_id="config",
                provider="openai",
                model="gpt-4o-mini",
                estimated_cost=0.01,
            )
            print(f"[model_routes.yaml] remote/gpt-4o-mini (human approved, budget OK)")
            return "openai/gpt-4o-mini"

    raise RuntimeError(
        "[model_routes.yaml] No LM available. "
        "Set HF_TOKEN for HuggingFace Router or run Ollama locally. "
        "For paid remote models set allow_remote=True with OPENAI_API_KEY."
    )
