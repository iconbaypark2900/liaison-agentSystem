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


NVIDIA_NIM_BASE = "https://integrate.api.nvidia.com/v1"


def _pick_nvidia_model(router: "ModelRouter", use_for: str, task_tags: list[str]) -> str | None:
    """
    Return a NVIDIA NIM model name if any remote_models/quantum_models entry matches.
    Matches on use_for tag OR any trigger_tag present in task_tags.
    """
    all_remote = {**router.remote_models, **router.quantum_models}
    for spec in all_remote.values():
        uses = spec.get("use_for", [])
        triggers = spec.get("trigger_tags", [])
        if use_for in uses or any(t in task_tags for t in triggers):
            return spec.get("model")
    return None


def configure_dspy(
    use_for: str = "implementation",
    temperature: float = 0.3,
    max_tokens: int = 8192,
    allow_remote: bool = False,
    task_tags: list[str] | None = None,
) -> str:
    """
    Configure DSPy LM following model_routes.yaml and remote-model-policy.md.

    Priority:
      1. Ollama (local, always preferred when running)
      2. NVIDIA NIM free endpoint (NVIDIA_API_KEY set + use_for or #tag matches)
      3. HuggingFace Router (HF_TOKEN set, no payment gate)
      4. OpenAI (allow_remote=True + OPENAI_API_KEY, budget checked)

    Args:
        use_for:     capability tag (e.g. "implementation", "summaries", "research")
        temperature: sampling temperature
        max_tokens:  max output tokens
        allow_remote: set True only when human has approved a remote paid call
        task_tags:   hashtags extracted from task text (e.g. ["#deepseek", "#planning"])
    """
    import dspy
    from .rules import model_router, budget_guard

    router = model_router()
    guard = budget_guard()
    tags = task_tags or []

    # If the task has NIM trigger tags, skip local and go straight to NIM
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    nim_model = _pick_nvidia_model(router, use_for, tags) if (nvidia_key and tags) else None

    # ── 1. Local Ollama (local_first per model_routes.yaml) ──────────────────
    if router.local_first and _ollama_is_running() and not nim_model:
        available = _get_ollama_models()
        _, preferred_model = router.pick_local_model(use_for)

        model = preferred_model if preferred_model in available else None
        if model is None and available:
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

    # ── 2. NVIDIA NIM free endpoint ───────────────────────────────────────────
    if not nvidia_key:
        nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    if nvidia_key:
        if nim_model is None:
            nim_model = _pick_nvidia_model(router, use_for, tags)
        if nim_model:
            lm = dspy.LM(
                f"openai/{nim_model}",
                api_base=NVIDIA_NIM_BASE,
                api_key=nvidia_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            dspy.configure(lm=lm)
            print(f"[model_routes.yaml] nvidia-nim/{nim_model} (use_for={use_for})")
            return nim_model

    # ── 3. HuggingFace Router (free with account, no payment gate) ───────────
    hf_token = os.environ.get("HF_TOKEN", "")
    if hf_token:
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

    # ── 4. Paid remote (budget check required) ────────────────────────────────
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
        "[model_routes.yaml] No LM available.\n"
        "  • Ollama: install and run `ollama serve` (models already configured)\n"
        "  • NVIDIA NIM (free): set NVIDIA_API_KEY=nvapi-... in environment\n"
        "  • HuggingFace (free): set HF_TOKEN=hf_... in environment\n"
        "  • OpenAI: set allow_remote=True and OPENAI_API_KEY"
    )
