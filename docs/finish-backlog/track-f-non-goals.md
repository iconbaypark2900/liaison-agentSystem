# Track F — Explicit non-goals / parking lot

**Purpose:** Items explicitly out of scope for the finish-line program. Revisit only if requirements change.

[Index ←](README.md)

---

| Item | Why parked |
|------|------------|
| Live agent streaming in dashboard | Architecture choice; tmux remains SSOT |
| Direct Hermes skill file sync | Use `export-learning-bridge` |
| Cursor as portfolio translator | Contradicts [execution-bridge.md](../execution-bridge.md) model |
| Full 27-repo Tier A plans | Operational waves ([B.1–B.2](track-b-portfolio.md)), not one PR |
| Full inotify log watchers (E3) | Defer; `liaison observe-session watch` poll/tail is enough for now |
