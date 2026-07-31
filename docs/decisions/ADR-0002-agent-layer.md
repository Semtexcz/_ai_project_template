# ADR-0002: Keep `.agents` Canonical and `.codex` Thin

> Status: Accepted
> Date: 2026-07-31

## Context

The template needs AI-agent guidance that is not tied to one tool, while still supporting Codex.

## Options

- Put all guidance in `.codex/`
- Put all guidance in `AGENTS.md`
- Use `AGENTS.md` plus `.agents/` as canonical guidance and `.codex/` only for supported Codex adapter settings

## Decision

Use `AGENTS.md` and `.agents/` as the canonical agent layer. Use `.codex/config.toml` only for supported project-scoped Codex settings and `.codex/hooks.json` for hook registration.

## Consequences

### Positive

- Agent workflow is portable across tools.
- Codex-specific configuration stays small and explicit.

### Negative

- Some non-Codex tools need their own thin adapters later.

## Revisit When

An agent tool needs capabilities that cannot read `AGENTS.md` or `.agents/context-map.yaml`.
