# Project Workflow Playbook

## Purpose

This document explains how to use this template to turn an idea into a working project and how to collaborate with an AI agent without overengineering the process.

Use it as a practical guide, not as rigid bureaucracy.
You do not need every document for every change, but you should keep the overall flow clear.

## Default Flow

The recommended path is:

1. define the idea in `docs/VISION.MD`
2. capture the main product requirement in `product/prds/`
3. split the work into one or more features in `product/features/`
4. add user stories only when they help clarify user behavior
5. create implementation tasks in `project/backlog/`
6. maintain execution order in `docs/TASK_SEQUENCE.md`
7. implement only from a concrete task
8. validate with tests
9. push changes and make sure CI passes

This is the default workflow, not a law.
For a small project, one PRD, one feature, and a few tasks may be enough.
For a larger project, you may need several features, ADRs, and more structured sequencing.

## What Each Document Is For

### `docs/VISION.MD`

Use for the highest-level project intent.

Write it when:

- the project is new
- the direction is still fuzzy
- you need to align humans and AI on purpose and non-goals

It should answer:

- why this project exists
- who it is for
- what value it should create
- what it explicitly should not do

### `product/prds/PRD-*.md`

Use a PRD when you need a clear product requirement before implementation begins.

Write it when:

- the feature area is important enough to deserve explicit scope
- there are real constraints, dependencies, or success criteria
- you want the AI agent to plan or implement against a stable definition

Keep it focused on outcomes, scope, constraints, and success criteria.
Do not turn it into a technical design document.

### `product/features/FEATURE-*.md`

Use a feature document to define one deliverable capability or problem area.

Write it when:

- a PRD needs to be broken into smaller deliverables
- a standalone feature deserves its own scope and success criteria
- multiple tasks will belong to the same capability

A feature should be smaller than a PRD and broader than a task.

### `product/user-stories/US-*.md`

User stories are optional.
Use them only when user behavior, roles, or acceptance logic need clarification.

Write them when:

- the user interaction is easy to misunderstand
- there are different user types or expectations
- acceptance conditions benefit from a user-centered framing

Skip them when they add no clarity.
This template prefers simple workflow over mandatory ceremony.

### `project/backlog/TASK-*.md`

Tasks are the execution unit.
AI implementation should usually start from a task, not from a vague prompt.

Every task should make these things explicit:

- the goal
- enough context to avoid guesswork
- which code and docs may change
- what is in scope and out of scope
- how to verify the result

If work cannot be implemented safely from the current task, the task is not specific enough yet.

### `docs/TASK_SEQUENCE.md`

Use this file to keep backlog order and dependencies explicit.

Update it when:

- a new task is added
- a task is removed
- dependencies change
- task IDs change

This helps both humans and AI agents avoid picking the wrong work next.

### `docs/ARCHITECTURE.md`

Use this document before implementation.

It explains:

- where code belongs
- which boundaries should be preserved
- how to avoid mixing planning artifacts with runtime logic

When a task is clear but the code location is not, this document should resolve that uncertainty.

### `docs/decisions/ADR-*.md`

ADRs are optional and should be used sparingly.

Write one when:

- an architectural decision will affect future work
- there are multiple reasonable approaches
- you want to record why one option was chosen

Do not create ADRs for trivial implementation details.

### `AGENTS.md`

This file defines how AI agents are expected to work in the repository.

Use it to understand:

- what agents must read before starting work
- what they must not do
- how scope discipline and testing should work
- what "done" means in this repository

## How To Go From Idea To First Push

### 1. Start with intent

Create or update `docs/VISION.MD`.
Keep it short and concrete.

Good output at this step:

- a clear goal
- a target user
- a value proposition
- explicit non-goals

### 2. Write one PRD for the first meaningful slice

Do not model the entire future of the product.
Describe the first important problem worth solving.

A good PRD should give enough clarity that features can be derived from it without inventing requirements.

### 3. Split the PRD into features

Create one feature file per meaningful capability or workstream.
If everything fits into one feature, keep one feature.

Use features to separate concerns such as:

- ingestion
- export
- authentication
- reporting

### 4. Add user stories only where behavior needs clarification

If a feature is mainly system behavior, a user story may be unnecessary.
If a feature depends on user roles, flows, or acceptance details, add one or more stories.

### 5. Break the feature into tasks

Tasks should be small enough to implement safely and test fully.

A good task is:

- scoped
- testable
- explicit about touchpoints
- safe to hand to an AI agent

If a task feels broad, split it before implementation starts.

### 6. Update task order

Reflect the new backlog in `docs/TASK_SEQUENCE.md`.
This is the bridge between planning and execution.

### 7. Ask the AI agent to work from the docs

The best prompts reference the project artifacts directly.

Effective pattern:

- point the agent to the relevant PRD, feature, and task
- name the exact goal
- say what must remain out of scope
- require tests and minimal changes

Good example:

```text
Implement TASK-004 from project/backlog/TASK-004-....md.
Read AGENTS.md, docs/ARCHITECTURE.md, the related feature, and the related PRD first.
Stay within Scope and Out of Scope.
Add or update tests and keep changes minimal.
```

### 8. Review the implementation through the task

Review against:

- task scope
- feature intent
- architectural boundaries
- validation steps

If the code is correct but the task is outdated, update the task or related docs.
Do not leave planning artifacts behind the code reality.

### 9. Push only when the slice is complete

A practical checkpoint is:

- code implemented
- tests passing locally
- docs updated if behavior changed
- changes committed cleanly
- pushed branch passes CI

That is a good "current state" milestone, even though the project itself continues.

## How To Work With The AI Agent

### Give the agent a narrow target

Do not start with:

- "build the app"
- "finish the project"
- "make it production ready"

Start with a concrete task or a bounded planning request.

### Prefer repository artifacts over long prose prompts

The template is designed so the agent can read project intent from documents.
That is more reliable than repeating the full context in every prompt.

### Decide whether you want planning or implementation

Use planning when:

- the idea is still ambiguous
- scope is unstable
- architecture is unclear
- you want help writing PRDs, features, or tasks

Use implementation when:

- the task already exists
- scope is concrete
- validation is known

### Keep the human in charge of scope

The agent can propose:

- task breakdown
- feature structure
- ADR drafts
- implementation details

The human should still own:

- what matters now
- what is out of scope
- whether complexity is justified

### Use ADRs only when uncertainty is structural

If the question is "which helper function name is better", do not write an ADR.
If the question is "should this project use a local-first or API-first architecture", an ADR may be worth it.

### Correct the docs when reality changes

If implementation reveals that the original task or feature was wrong, update the planning documents.
This template works best when the docs remain operational, not archival.

## Recommended Minimum For Small Projects

For many projects, this lightweight path is enough:

1. fill in `docs/VISION.MD`
2. create one PRD
3. create one or two features
4. create a few tasks
5. maintain `docs/TASK_SEQUENCE.md`
6. implement task by task with tests

User stories and ADRs should be added only when they create clarity.

## Final Rule

This template is meant to support good decisions, not force paperwork.

If a document does not improve clarity, do not create it.
If an AI agent cannot work safely without a document, add it before implementation starts.
