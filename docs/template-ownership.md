# Template Ownership Model

This template supports standard Copier updates for projects generated from a
versioned Git source. File ownership determines how update results are reviewed.

## Template-Owned

Template-owned files are maintained by the template and may be updated during a
Copier upgrade:

- `.github/workflows/`
- `.codex/` thin adapter files selected by governance and profile
- `.agents/` canonical skills, schemas, context map, and selected managed or
  capability skill groups
- `tools/` files selected by project type and governance, including
  `tools/agent.py` for skill validation
- `.gitignore`
- `.template-version`
- generated API client runtime scaffolding under `frontend/shared/api/`
- baseline backend system module under `backend/src/app/modules/system/`
- baseline tests and validation tooling

## Project-Owned

Project-owned files are initialized on first copy and then protected with
Copier `skip_if_exists`, so normal updates do not overwrite project knowledge:

- `docs/product.md`
- `docs/decisions/*.md`
- `project/brief.md`
- `project/roadmap.md`
- `project/requirements.md`
- `project/tasks/*.md`
- project-specific business code added after generation

If a project intentionally wants to restore a skipped baseline file, delete or
rename the local file and run `copier update` again from a clean Git state.

## Merge-Sensitive

Merge-sensitive files contain both template structure and local project edits.
Copier handles these with its smart update algorithm and reports conflicts when
the same hunk changes on both sides:

- `README.md`
- `AGENTS.md`
- `Makefile`
- `pyproject.toml`
- `backend/pyproject.toml`
- `frontend/package.json`
- `compose.yaml`
- `docs/workflow.md`
- `docs/quality.md`
- `docs/architecture.md`
- `project/state.yaml` when `governance=managed`
- `project/board.md` when `governance=managed`
- `project/index.md` when `governance=managed`

Do not commit unresolved conflict markers or `.rej` files. Review every
merge-sensitive change before accepting an upgrade.
