# spark-flow-demo

A tiny demo project for testing the DGX Spark local multi-model workflow.

The final project should expose a Python CLI named:

```bash
spark-demo-health
```

It should check:

- Python version
- platform
- current working directory
- whether `ollama` exists on PATH
- whether the Ollama API responds
- installed Ollama model names
- whether expected local models are installed

This project is intentionally small so we can test the full `spark-flow` lifecycle:

1. PLAN with Nemotron
2. BUILD with Qwen3-Coder
3. PATCH with GPT-OSS if needed
4. REVIEW with Nemotron
5. CLOSE with Qwen3.6
