.PHONY: check test-template test-copier-update project-status sync-project-docs validate-project task-ready task-start task-review task-complete task-block task-approve agent-status agent-context validate-agent-skills agent-pre-task agent-pre-review agent-post-task agent-review-report

check: validate-project validate-agent-skills
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py

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

agent-status:
	python template/tools/agent.py status

agent-context:
	python template/tools/agent.py context --task $(TASK) $(if $(FORMAT),--format $(FORMAT),)

validate-agent-skills:
	python template/tools/agent.py validate-skills

agent-pre-task:
	python template/tools/agent.py pre-task --task $(TASK)

agent-pre-review:
	python template/tools/agent.py pre-review --task $(TASK)

agent-post-task:
	python template/tools/agent.py post-task --task $(TASK)

agent-review-report:
	python template/tools/agent.py context --task $(TASK)

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
