# Template Development

Use this guide when changing the template itself. It describes how to keep
generated projects updateable and how to prove that a template change did not
break existing golden paths.

## Start With One Task

The root project state is authoritative. Before changing files:

```bash
make agent-status
make agent-context TASK=<id>
make task-start TASK=<id>
```

Only one task may be `in-progress`. A1 and A2 approvals must be granted by a
human; agents can move implemented A1 work to review but must not approve it.
Agents must work on a non-`main` branch, commit their own changes, push that
branch to `origin`, and open a ready GitHub pull request. The CI guard for
pushes to `main` is a signal; actual push blocking requires GitHub branch
protection or a ruleset that marks the guard as a required check.

## Choose The Ownership Boundary

Template-owned files can be changed when the scaffold or workflow changes:

- `copier.yml`
- `template/Makefile.jinja`
- `template/tools/`
- generated workflow and agent files
- profile-specific runtime scaffold
- template tests

Generated-project-owned files should be skipped or preserved during updates:

- product docs and brief
- roadmap and requirements
- existing tasks
- ADRs created after generation

The `_skip_if_exists` entries in `copier.yml` enforce that boundary.

## Change Profiles Safely

When changing profile behavior, update the smallest matching set:

1. `copier.yml` exclusions or answers
2. files under `template/`
3. `docs/profile-matrix.md`
4. golden path tests for affected profiles
5. documentation validation if the profile contract changes

Do not add runtime infrastructure such as databases, queues, Redis, brokers, or
cloud services unless an approved task explicitly scopes that work.

## Documentation Rules

Root template docs explain the template. Generated docs explain the selected
project only. Avoid copying full architecture prose between them.

Run:

```bash
make validate-template-docs
make validate-project
```

Generated projects additionally expose:

```bash
make validate-docs
```

Managed generated projects also expose:

```bash
make validate-project
make validate-agent-skills
make sync-project-docs
```

Documentation validation is deterministic. It checks required entry documents,
navigation, internal links, documented Make commands, profile relevance,
dashboard drift, unresolved Jinja placeholders, personal absolute paths, and
stale example paths.

## Update And Release Checks

For a narrow template change:

```bash
make check
```

`make check` is validation-only. It must not rewrite tracked files. Use explicit
mutating commands such as `make sync-project-docs`, generated `make format`, or
generated `make api-generate` when files need to be rewritten.

Before review or release-candidate signoff:

```bash
make release-check
```

`make release-check` must preserve existing golden paths. It does not publish,
tag, push images, or perform an external release.

## Template Release And Publication

Template release is a post-merge maintainer operation, separate from the agent
`branch -> commit -> push -> PR -> merge` workflow. It runs on `main` only after
a human merges the reviewed change. A coding agent on a feature branch cannot
use it to bypass the PR workflow: the command rejects non-`main` branches and
dirty worktrees.

### What `make template-release` does

`make template-release BUMP=<major|minor|patch>` prepares a **local** release:

1. validates the current version, the requested bump, the branch (`main`
   unless `ALLOW_NON_MAIN=1` is set for tests or dry runs), a clean worktree, a
   missing target tag, and Git identity;
2. runs `make release-check`;
3. validates the candidate project state;
4. updates `template.version` in `project/state.yaml`, creates the
   `chore(release): vX.Y.Z` commit, and creates the annotated `vX.Y.Z` Git tag
   on `main`.

Use `DRY_RUN=1` to preview the release without writing state, committing, or
tagging.

### What it does NOT do

`make template-release` never pushes. It does not publish anything to GitHub,
does not create a GitHub Release, and does not, by itself, expose the new
version to Copier. It is not a substitute for the agent PR workflow and gives no
one authority to commit to `main` outside the post-merge release procedure.

### When the release becomes Copier/GitHub visible

The release becomes visible to Copier and GitHub only after the commit and the
tag are pushed to `origin`. Until then the release exists only in the local
clone.

### Publishing the release

A maintainer publishes the prepared local release with an explicit human
action:

```bash
git push origin main --follow-tags
```

No automation in this repository pushes release commits or tags automatically.

### Choosing the bump

The maintainer chooses `BUMP` from the merged change set: use `major` for
breaking template or update contracts, `minor` for new template capability, and
`patch` for fixes, documentation, or tooling changes that preserve behavior.
Without a `BUMP`, the command defaults to `patch`. Agents may propose the bump
in review; executing the release remains a human post-merge action on `main`.

## Finish Work

Before moving a task to review:

```bash
make sync-project-docs
make agent-pre-review TASK=<id>
make task-review TASK=<id>
```

For A1 or A2 tasks, stop in review with approval pending. A human can later run:

```bash
make task-approve TASK=<id> APPROVED_BY="<human>"
```
