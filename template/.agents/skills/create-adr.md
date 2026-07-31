# Skill: create-adr

Purpose: record a significant architectural decision.

Use when: adding infrastructure, changing architecture style, authentication, deployment, data ownership, queues, cache, external services, or vendor lock-in.

Do not use when: the change is local implementation detail with no lasting consequence.

Inputs: context, options, decision, consequences, related requirements.

Procedure:

1. Copy `.agents/templates/adr.md`.
2. Assign the next ADR number.
3. Document context, options, decision, consequences, revisit trigger, and related links.
4. Update `docs/decisions/index.md`.

Outputs: ADR and updated ADR index.

Allowed changes: `docs/decisions/`.

Validation: `make validate-project`.
