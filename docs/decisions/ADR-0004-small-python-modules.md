# ADR-0004: Enforce Small Single-Responsibility Python Modules

> Status: Accepted
> Date: 2026-08-17

## Context

Python modules grow easiest when unrelated behavior is added to an existing
file. Line count is not architecture, but it is a useful deterministic signal
that a human or agent should review cohesion and responsibility boundaries.

## Options

- Rely only on judgment in review.
- Fail all modules above a low line-count target.
- Combine judgment-based responsibility rules with a deterministic hard limit.

## Decision

Prefer atomic, single-responsibility handwritten Python modules. Use 200 source
LOC as the target, 300 source LOC as a decomposition signal, and 500 source LOC
as the deterministic hard limit.

The checker counts non-blank, non-comment physical lines in `.py` files.
Docstrings and executable statements count as source. The 300 LOC threshold is
warning-only. Modules above 500 LOC fail unless `quality.yaml` contains an
explicit exception with a reason.

## Consequences

### Positive

- Reviewers get an early signal before modules become hard to understand.
- CI can enforce the hard limit without replacing architectural judgment.
- Exceptions are visible and documented instead of implicit.

### Negative

- Legacy lifecycle tools need temporary documented exceptions until they are
  decomposed through planned tool refactors.

## Revisit When

The project adopts richer static architecture analysis that can enforce
cohesion and ownership boundaries more directly than line-count signals.
