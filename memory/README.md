# Memory

Promoted cross-task learnings live here. Runtime task state remains in each
repo's `.spark-flow/`; only durable lessons that should affect future work are
promoted into this directory.

Use:

```bash
spark-flow promote-learning --tags "sigma,validation"
spark-flow memory-report
```

Promotion rule: do not promote secrets, raw private data, or unreviewed outputs.
