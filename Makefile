.PHONY: check test-template test-copier-update project-status sync-project-docs validate-project task-ready task-start task-review task-complete task-block task-unblock task-cancel task-approve agent-status agent-context validate-agent-skills agent-pre-task agent-pre-review agent-post-task agent-review-report

check: validate-project validate-agent-skills
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py

test-template:
	uv run pytest

test-copier-update:
	uv run pytest tests/test_copier_update_golden_path.py

project-status:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py status

sync-project-docs:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py sync

validate-project:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py validate

agent-status:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py status

agent-context:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py context --task $(TASK) $(if $(FORMAT),--format $(FORMAT),)

validate-agent-skills:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py validate-skills

agent-pre-task:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py pre-task --task $(TASK)

agent-pre-review:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py pre-review --task $(TASK)

agent-post-task:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py post-task --task $(TASK)

agent-review-report:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py context --task $(TASK)

task-ready:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py ready $(TASK)

task-start:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py start $(TASK)

task-review:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py review $(TASK)

task-complete:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py complete $(TASK)

task-block:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py block $(TASK) --reason "$(REASON)" --unblock "$(UNBLOCK)"

task-unblock:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py unblock $(TASK)

task-cancel:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py cancel $(TASK)

task-approve:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py approve $(TASK) --approved-by "$(APPROVED_BY)"
