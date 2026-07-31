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

## After Updating

Run the profile checks:

```bash
make setup
make api-check
make check
make build
```

For `fullstack-local`, also run the built runtime and browser E2E:

```bash
make run
make e2e
```

## Ownership Model

The concrete ownership map lives in `docs/template-ownership.md`.

Project-owned files such as `project/brief.md`, `project/roadmap.md`,
`project/requirements.md`, `project/tasks/*.md`, `docs/product.md`, and ADRs are
created on first copy and protected with Copier `skip_if_exists`.

Template-owned files such as `tools/`, `.github/workflows/`, `.codex/`,
`.agents/`, `.gitignore`, `.template-version`, and baseline system scaffolding
may update during a template upgrade.

Merge-sensitive files such as `README.md`, `AGENTS.md`, `Makefile`,
`pyproject.toml`, `docs/workflow.md`, and `docs/quality.md` require review.
Copier will usually merge independent changes. When the same hunk changes in
both the project and the new template, Copier reports a conflict using inline
conflict markers by default or `.rej` files when `--conflict rej` is selected.

Do not blindly accept conflicts. Resolve them, rerun the checks, and only then
commit the upgrade.

## Migrations

The current `v1.0.0` to `v1.1.0` golden-path scenario does not need Copier
migrations because it only adds files and updates mergeable template content.
Use migrations only when a future release must rename paths, move directories,
transform configuration, or change the answers schema. Migration tests must use
the same temporary two-tag Git repository pattern as the Copier update golden
path.
