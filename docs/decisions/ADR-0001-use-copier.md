# ADR-0001: Use Copier as the Update Mechanism

> Status: Accepted
> Date: 2026-07-31

## Context

The template must create projects and later update them without overwriting project knowledge.

## Options

- Cookiecutter
- Copier
- Custom generator

## Decision

Use Copier with `_subdirectory`, `.copier-answers.yml`, explicit skip rules, and an ownership model documented in `UPGRADING.md`.

## Consequences

### Positive

- Generated projects can be updated from new template versions.
- Answers are stored in a supported, machine-readable file.

### Negative

- Merge-sensitive files still need review during update.

## Revisit When

Copier cannot safely preserve project-owned knowledge for a required migration.
