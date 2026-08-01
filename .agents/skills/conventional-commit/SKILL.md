---
name: conventional-commit
version: 1
purpose: Draft and validate one conventional commit message for the current repository change.
triggers: [conventional commit, commit message, draft commit, summarize diff]
inputs:
  required: []
reads:
  - AGENTS.md
  - .agents/skills/conventional-commit/agents/openai.yaml
  - .agents/skills/conventional-commit/agents/model.yaml
  - .agents/skills/conventional-commit/scripts/validate_commit_message.py
commands:
  - git diff --cached --stat
  - git diff --cached
  - python .agents/skills/conventional-commit/scripts/validate_commit_message.py --message "<candidate>"
outputs:
  - one validated conventional commit message
approval_boundary:
  may_approve: false
stop_conditions:
  - no scoped diff is available
  - commit intent is ambiguous after inspecting the diff
  - validator rejects every candidate
  - request requires rewriting published history
---

# Conventional Commit

Inspect the smallest relevant diff first. Prefer staged changes when they
exist; otherwise inspect the user-scoped working tree diff and say which source
you used.

Use the low-cost model profile declared in `agents/model.yaml` for drafting.
Produce exactly one commit message candidate unless the user explicitly asks for
alternatives.

Follow this sequence:

1. Read the diff summary before the patch body.
2. Infer the dominant change type from the repository change, not from filenames
   alone.
3. Use `type(scope): summary` when scope is clear and short. Omit scope when it
   would be vague.
4. Keep the summary imperative, lowercase after the colon, and without a
   trailing period.
5. Run `scripts/validate_commit_message.py` against the final candidate.

Use these type defaults:

- `feat` for user-visible behavior or capability additions.
- `fix` for bug fixes or regressions.
- `refactor` for internal restructures without behavior change.
- `docs` for documentation-only changes.
- `test` for test-only changes.
- `ci` for workflow or automation changes.
- `build` for packaging or dependency graph changes.
- `chore` for repository maintenance that does not fit the above.

If the diff mixes unrelated concerns, stop and ask for a split commit instead of
forcing one misleading summary.
