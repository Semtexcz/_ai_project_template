# Template Development

Use this guide when changing the template itself. It describes how to keep
generated projects updateable and how to prove that a template change did not
break existing golden paths.

## Start With One Task

The root project state is authoritative. Before changing files:

```bash
make agent-status
make agent-context TASK=<id> SKILL=implement-change
make task-start TASK=<id>
```

Use `SKILL=<skill>` to route the selected skill's `reads:` into context, and
`MODE=resume` when resuming or fixing an existing PR on this branch. Context is
bounded by `.agents/context-map.yaml` `budget` values and reports included and
omitted files.

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

During implementation prefer the focused checks recommended by
`make agent-context TASK=<id> SKILL=<skill>`. Run the canonical full gate once:

```bash
make check
```

`make agent-pre-review` performs diff-safety and review-readiness checks and
then runs that single full gate; it does not re-run the validators that
`make check` already contains.

Before review or release-candidate signoff:

```bash
make release-check
```

`make release-check` must preserve existing golden paths. It does not publish,
tag, push images, or perform an external release.

## Template Releases (PR-only, two-phase)

Template releases follow the same rule as every other change: all commits
reaching `main` come through a pull request. Release tooling never creates or
pushes a version commit directly on `main`.

The release flow is:

```text
1. prepare the release branch/version commit
2. open a pull request
3. CI + human approval
4. merge the pull request
5. update local main
6. verify local main == origin/main
7. create the annotated release tag
8. push the exact tag
```

Version commits are ordinary reviewed repository changes. Tags are post-merge
release metadata. Tagging does not grant permission to bypass PR governance and
never creates commits.

### Phase 1 - prepare the release commit (on a release branch)

On a non-`main` release branch, prepare the version bump as an ordinary,
reviewable commit:

```bash
git switch -c release/v1.2.0
make template-release-prepare BUMP=minor
```

`make template-release-prepare BUMP=<major|minor|patch>`:

1. validates the current template version and the requested SemVer bump;
2. refuses to run on `main` (with instructions to create a release branch),
   rejects a detached HEAD and dirty worktrees, refuses an already-existing
   target tag, and checks Git identity;
3. runs `make release-check`;
4. validates the candidate project state;
5. updates `template.version` in `project/state.yaml`;
6. creates a normal Git commit `chore(release): v1.2.0` on the current branch.

It creates no Git tag and pushes nothing. The command leaves you on the release
branch. Use `DRY_RUN=1` to preview the prepare without writing state or
committing.

The version change then goes through the normal repository workflow:

```text
release branch
-> push
-> ready pull request
-> CI
-> human review/approval
-> merge to main
```

An agent may prepare the release PR through the same workflow as any other
change when the normal workflow allows it; human approval remains required
where governance requires it.

### Phase 2 - tag the merged release (on up-to-date main)

After the release PR is merged and the current `main` tip introduces
`template.version` `v1.2.0`, update local `main` and run:

```bash
git switch main
git pull --ff-only
make template-release-tag
```

`make template-release-tag`:

1. requires branch `main`, a clean worktree, and Git identity;
2. refuses an existing target tag on `origin` (release tags are never
   overwritten);
3. fetches `origin main` into `refs/remotes/origin/main` only - no merge, no
   rebase, and no mutation of local branches;
4. requires local `main` == `origin/main` and fails clearly when local main is
   behind, ahead, or diverged;
5. reads `template.version` from `project/state.yaml`;
6. verifies that `HEAD` records `vX.Y.Z` and its first parent (`HEAD^1`)
   records a valid, strictly older template version;
7. refuses an already-existing local tag;
8. creates an annotated `vX.Y.Z` tag pointing at `HEAD`.

Tagging never creates another version commit, never modifies project state, and
never rewrites history. It is the only post-merge release mutation.

The tag-phase freshness check is explicit: the command fetches the
remote-tracking ref and requires `HEAD == refs/remotes/origin/main`. It never
silently fetches-and-merges or moves branches.

### Publishing the release

Publish only the intended tag:

```bash
git push origin v1.2.0
```

Do not republish `main` with a tag-following push such as
`git push origin main --follow-tags`: `main` was already published by the PR
merge and a tag-following push can publish unrelated annotated tags. Release
publication never uses force-push. No automation in this repository pushes
release tags automatically; if a local tag was created but publication failed,
do not rewrite history - retry the exact command above.

### Release state validation

The tag phase does not trust the state file alone. It tags only when all of
the following hold:

- `HEAD` is on `main` and equals `origin/main`;
- `project/state.yaml.template.version` at `HEAD` is `vX.Y.Z`;
- `HEAD^1` (the pre-merge mainline parent for a merge commit) records a valid,
  strictly older template version.

This identifies the current main tip as the release boundary and prevents
tagging arbitrary later commits. It supports merge commits, squash commits, and
fast-forward/rebase history without depending on GitHub commit-message layout.
The prepared `chore(release): vX.Y.Z` subject remains review evidence, but is
not a tag-time requirement because merge strategies may rewrite it.

### Failure and recovery

A prepare failure restores `project/state.yaml` and the index to the
pre-command state; no partial release commit and no tag remain. A tag failure
happens before mutation, so `HEAD`, project state, the worktree, and the tag
list are unchanged.

### Choosing the bump

The maintainer chooses `BUMP` from the merged change set: use `major` for
breaking template or update contracts, `minor` for new template capability, and
`patch` for fixes, documentation, or tooling changes that preserve behavior.
Without a `BUMP`, the command defaults to `patch`. Agents may propose the bump
in review; the version commit must still pass through the PR workflow and human
approval.

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
