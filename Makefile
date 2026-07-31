.PHONY: test-template test-copier-update project-status sync-project-docs validate-project task-ready task-start task-review task-complete task-block task-approve

test-template:
	uv run pytest

test-copier-update:
	uv run pytest tests/test_copier_update_golden_path.py

project-status:
	python template/tools/project.py status

sync-project-docs:
	python template/tools/project.py sync

validate-project:
	python template/tools/project.py validate

task-ready:
	python template/tools/project.py ready $(TASK)

task-start:
	python template/tools/project.py start $(TASK)

task-review:
	python template/tools/project.py review $(TASK)

task-complete:
	python template/tools/project.py complete $(TASK)

task-block:
	python template/tools/project.py block $(TASK) --reason "$(REASON)" --unblock "$(UNBLOCK)"

task-approve:
	python template/tools/project.py approve $(TASK) --approved-by "$(APPROVED_BY)"
