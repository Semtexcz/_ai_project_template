# Codex Adapter

Canonical agent guidance lives in `.agents/`. This directory is intentionally
thin and exists only for Codex-local configuration or adapter files.

Codex skill adapters in `.codex/skills/*/SKILL.md` declare `canonical_skill` and
delegate to the corresponding canonical skill under `.agents/skills`,
`.agents/managed/skills`, or `.agents/capabilities/skills`. Do not copy full
skill logic into this directory.

Core adapters are available in lightweight and managed projects. Managed
lifecycle adapters exist only when `governance=managed`. Capability adapters
exist only when the selected profile renders the matching canonical capability
skill.

Managed projects also expose deterministic lifecycle commands:

```bash
make agent-status
make agent-context TASK=<id>
make agent-pre-task TASK=<id>
make agent-pre-review TASK=<id>
make agent-post-task TASK=<id>
```

Lightweight projects do not require task state. Use durable project context and
core skills directly.

Codex must not run `make task-approve`; A1 and A2 approvals are human actions.
