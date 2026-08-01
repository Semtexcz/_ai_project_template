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

Documentation validation is deterministic. It checks required entry documents,
navigation, internal links, documented Make commands, profile relevance,
dashboard drift, unresolved Jinja placeholders, personal absolute paths, and
stale example paths.

## Update And Release Checks

For a narrow template change:

```bash
make check
```

Before review or release-candidate signoff:

```bash
make release-check
```

`make release-check` must preserve existing golden paths. It does not publish,
tag, push images, or perform an external release.

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
