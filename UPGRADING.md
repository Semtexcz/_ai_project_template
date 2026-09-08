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

Newer template versions add a general project-state reconciliation policy to
generated `AGENTS.md` and `docs/workflow.md`. Both files are merge-sensitive:
existing generated projects with local customizations may receive merge
conflicts during `copier update`. Resolve those conflicts by preserving
project-specific rules while incorporating the general reconciliation policy.
No file migration is required.

## Migrations

The governance refactor adds answers rather than silently moving product-owned
files. Full automatic migration from managed to lightweight would be unsafe
because it could discard project state and tasks, so the mode choice is
documented and explicit. Use Copier migrations only when a future release must
rename paths, move directories, transform configuration, or change the answers
schema. Migration tests must use the same temporary two-tag Git repository
pattern as the Copier update golden path.
