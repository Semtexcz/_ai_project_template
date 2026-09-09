# Upgrading Generated Projects

This template uses the standard Copier update workflow. Generated projects keep
their answers in `.copier-answers.yml`; never edit that file by hand.

## Create an Updatable Project

Use a real Git source and a version tag:

```bash
copier copy \
  --vcs-ref <template-version> \
  <template-git-source> \
  <target-directory>
```

For released templates, use Semantic Versioning tags such as `v1.0.0`,
`v1.1.0`, or `v2.0.0`. Local smoke tests may render from the working tree, but
projects that must be updatable should be created from a Git source, not from
`.` inside an unrelated directory.

## Before Updating

- Commit or stash local changes.
- Create an upgrade branch.
- Read `CHANGELOG.md` and this file for breaking changes.
- Confirm that `git status` is clean in the generated project.

## Update

From the generated project directory:

```bash
copier update --vcs-ref <new-version>
```

Use `--defaults` only when you intentionally want to reuse the previous project
answers. Do not repair update metadata by manually editing
`.copier-answers.yml`.

## Governance Migration

Templates before the progressive-governance refactor did not have a
`governance` answer and effectively generated managed governance. Existing
generated projects should choose explicitly during upgrade:

```bash
copier update --vcs-ref <new-version> --data governance=managed
```

Use `governance=managed` to preserve `project/state.yaml`, task lifecycle,
boards, dashboards, managed agent context, and approval metadata.

Use `governance=lightweight` only when you intentionally want to stop using the
managed project-control layer. Before doing that, archive or remove managed
files such as `project/state.yaml`, `project/tasks/`, `project/board.md`,
`project/index.md`, `.agents/`, `.codex/`, and managed lifecycle references in
project-owned docs. Copier cannot safely infer that choice from local
customizations.

`workflow_mode` is also explicit on upgrade. If omitted, the new default is
`local`. Select `workflow_mode=pr` to preserve the previous strict
branch/commit/push/ready-PR instructions.

## After Updating

Run the profile checks:

```bash
make setup
make api-check
make check
make build
```

For managed projects, run `make sync-project-docs` explicitly before `make check`
if the update changes generated dashboard content. `make check` reports drift
but does not repair it.

For `fullstack-local`, also run the built runtime and browser E2E:

```bash
make run
make e2e
```

## Ownership Model

The concrete ownership map lives in `docs/template-ownership.md`.

Project-owned files such as `project/brief.md`, `project/roadmap.md`,
`project/requirements.md`, `project/tasks/*.md`, `docs/product.md`, and ADRs are
created on first copy and protected with Copier `skip_if_exists` when they are
rendered by the selected governance mode.

Template-owned files such as `tools/`, `.github/workflows/`, `.codex/`,
`.agents/`, `.gitignore`, `.template-version`, and baseline system scaffolding
may update during a template upgrade when selected by the generated project's
governance, workflow, project type, and runtime answers.

Merge-sensitive files such as `README.md`, `AGENTS.md`, `Makefile`,
`pyproject.toml`, `docs/workflow.md`, and `docs/quality.md` require review.
Copier will usually merge independent changes. When the same hunk changes in
both the project and the new template, Copier reports a conflict using inline
conflict markers by default or `.rej` files when `--conflict rej` is selected.

Do not blindly accept conflicts. Resolve them, rerun the checks, and only then
commit the upgrade.

## Project State Reconciliation Note

Newer template versions add a project-state reconciliation policy to generated
`AGENTS.md` and `docs/workflow.md`. Managed generated projects receive the full
policy (roadmap/milestone/task-level reconciliation, next-task re-evaluation,
and a concise `Project State Check`); lightweight generated projects receive
only the shared guidance to keep durable planning/status artifacts truthful when
they exist, without task selection or report-footers. Both files are
merge-sensitive: existing generated projects with local customizations may
receive merge conflicts during `copier update`. Resolve those conflicts by
preserving project-specific rules while incorporating the reconciliation policy
that matches the project's governance. No file migration is required.

## Agent Efficiency Note (context-map schema v2)

Newer template versions make agent context loading explicit and bounded:

- `.agents/context-map.yaml` uses `schema_version: 2` and separates explicit
  `files` (eagerly loaded candidates) from `search_roots` (never loaded
  automatically). Directories are never recursively expanded into context.
- A deterministic `budget` (`max_files`, `max_bytes`) bounds eager loading.
  Task, selected-skill, and bootstrap files are protected from truncation.
- `make agent-context TASK=<id> SKILL=<skill>` routes the selected skill's
  `reads:` into context; `MODE=resume` keeps context small when resuming or
  fixing an existing PR.
- Changed-file detection is branch-aware: committed branch changes, staged,
  unstaged, and untracked files are all reported even when the worktree is
  clean after a commit.
- `make agent-pre-review TASK=<id>` now runs the canonical `make check` full
  gate once instead of re-running the validators that gate already contains.
- Task records are expected to stay concise and durable; execution journals
  belong in commit history, PR descriptions, and review discussion.

These files are template-owned, so `copier update` refreshes them. `AGENTS.md`,
`docs/workflow.md`, and `README.md` are merge-sensitive and may require review
when the generated project customized them.

## A1 GitHub Merge Lifecycle Note (approval simplification)

Newer template versions simplify managed approvals for GitHub-backed projects.
In managed projects with `workflow_mode: pr`, a task's human GitHub merge is
the A1 approval/completion boundary (and the A2 completion boundary). Agents
move A1/A2 work to `review`, open one pull request per task (task id `T-###`
in the branch name or title), and stop. There is no post-merge
`task-approve`/`task-complete`/sync step and no lifecycle-only cleanup pull
request.

For existing managed generated projects:

- Historical `done` tasks that already carry `approval_status`, `approved_by`,
  and `approved_at` metadata remain valid; no task metadata needs rewriting.
- For `workflow_mode: local` or `branch` (offline fallback), nothing changes:
  a human records A1/A2 approval with `make task-approve`, then
  `make task-complete`.
- For projects that use `workflow_mode: pr`, the deterministic interpretation
  is: an A1/A2 task in `review` remains pending until the human GitHub merge of its
  pull request. `approval_status: pending` on such a task is local pre-merge
  state only and is not an authoritative approval claim. If you previously
  completed A1 tasks locally after merge with `task-approve`/`task-complete`,
  stop doing that; merge is sufficient. `tools/project.py` now rejects A1
  `task-approve` and A1/A2 `task-complete` in `pr` mode so a future agent
  cannot manufacture that local approval.
- Generated `docs/workflow.md` and `AGENTS.md` describe the merge boundary; they
  are merge-sensitive files, so resolve Copier conflicts by keeping the
  project-specific guidance while adopting the merge boundary that matches the
  project's `workflow_mode`.

## Migrations

The governance refactor adds answers rather than silently moving product-owned
files. Full automatic migration from managed to lightweight would be unsafe
because it could discard project state and tasks, so the mode choice is
documented and explicit. Use Copier migrations only when a future release must
rename paths, move directories, transform configuration, or change the answers
schema. Migration tests must use the same temporary two-tag Git repository
pattern as the Copier update golden path.
