"""Project-governance implementation behind the ``tools/project.py`` CLI.

Module ownership (lowest layer first):

``model``
    Root layout, task records, status/workflow vocabulary, task ordering.
``storage``
    Simple YAML codec, state/task loading, generated-block text, file writes.
``git``
    Read-only Git provenance for PR-mode completion.
``worktrees``
    Git worktree and branch mechanics for task-scoped parallel work.
``claims``
    Local task claims, worktree ownership resolution, claim inspection.
``lifecycle``
    Effective status, readiness, dependencies, available tasks, transition and
    approval policy.
``rendering``
    Persisted versus runtime status/board/index/worktree derivation.
``docs``
    Documentation validation.
``validation``
    Project/task validation composition.
``mutations``
    Explicit mutation and synchronization boundary.
``commands``
    Public command implementations used by the CLI.

Import direction is one-way: lower layers never import higher ones, and no
module except the CLI knows about argument parsing.
"""
