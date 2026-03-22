# AGENTS.md

## Purpose

This repository is designed for AI-assisted development.

Agents must prioritize:

- correctness
- clarity
- minimal scope changes
- testability
- maintainability

---

## Required Reading Before Any Task

Always read:

1. `docs/architecture.md`
2. relevant feature in `product/features/`
3. relevant task in `project/backlog/`
4. `context/test-strategy.md` (if exists)

---

## Core Rules

- Do not implement anything outside task scope.
- Do not refactor unrelated code.
- Do not invent requirements not present in task or feature.
- Prefer minimal, safe changes over large rewrites.
- Keep module boundaries defined in `architecture.md`.

---

## Code Quality

- Follow clean, explicit, and maintainable style.
- Prefer clarity over cleverness.
- Use type hints where reasonable.
- Every module, class, and function must include a docstring.
- Keep functions small and single-purpose.
- Avoid implicit behavior and magic values.

---

## Language

This project is **English-only**:

- code
- comments
- docstrings
- commits
- documentation
- agent communication

---

## Task Workflow

Tasks are stored in `project/backlog/`.

When implementing a task:

1. Read the task and related feature.
2. Implement only what is defined in **Scope**.
3. After completion:
   - update task status to `done`
   - move file to `project/done/`

Do not modify unrelated tasks.

Agents should follow `docs/TASK_SEQUENCE.md` to determine correct execution order.

## Task Sequence Consistency

When tasks in `project/backlog/` change, update `docs/TASK_SEQUENCE.md`.

Trigger conditions:

- a task is added
- a task is removed
- a task identifier changes

Rules:

- keep `Order` aligned with backlog
- update `Dependencies` if needed
- do not leave references to non-existing tasks

---

## Testing

Run tests via:

```bash
poetry run pytest
```

Rules:

- Add or update tests for any behavior change.
- Tests must be deterministic and fast.
- Test behavior, not implementation details.

---

## Versioning & Change Management (MANDATORY)

After every code change:

### 1. Commit

Use Conventional Commits:

```bash
type(scope): short description
```

Examples:

- `feat(api): add PDF text extraction`
- `fix(cli): handle empty input`
- `refactor(core): simplify pipeline`

---

### 2. Version bump

Follow Semantic Versioning:

- MAJOR → breaking changes
- MINOR → new features
- PATCH → fixes/refactors

Update version in `pyproject.toml`.

---

### 3. Changelog

Update `CHANGELOG.md`:

- describe change clearly
- group under: Added / Changed / Fixed

---

## Dependencies

- Use Poetry.
- Do not add dependencies unless clearly justified.
- Prefer standard library when possible.

---

## What NOT to Do

- Do not expand task scope.
- Do not refactor unrelated code.
- Do not skip tests.
- Do not skip version bump or changelog.
- Do not write vague commit messages.
- Do not introduce undocumented behavior.

---

## When in Doubt

- Ask or make the smallest safe assumption.
- Document assumptions explicitly.
- Prefer small, well-defined changes.

---

## Definition of Done

A task is done only if:

- implementation matches Scope
- all Done criteria in task are satisfied
- tests pass
- no unrelated code was modified
- version and changelog were updated
