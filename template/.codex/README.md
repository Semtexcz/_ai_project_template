# Codex Adapter

Canonical agent guidance lives in `.agents/`. This directory is intentionally
thin and exists only for Codex-local configuration or adapter files.

Use the deterministic Make commands:

```bash
make agent-status
make agent-context TASK=<id>
make agent-pre-task TASK=<id>
make agent-pre-review TASK=<id>
make agent-post-task TASK=<id>
```

Codex must not run `make task-approve`; A1 and A2 approvals are human actions.
