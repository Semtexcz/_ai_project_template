.PHONY: check release-check template-release-prepare template-release-tag test-template test-agent test-workflow test-lifecycle test-static test-mirror test-release-workflow test-backend test-frontend test-python-profiles test-copier-update project-status sync-project-docs validate-project validate-template-docs validate-agent-layer sync-agent-layer task-ready task-start task-review task-complete task-block task-unblock task-cancel task-approve pr-validate agent-status agent-context validate-agent-skills agent-pre-task agent-pre-review agent-post-task agent-review-report

check: validate-project validate-template-docs validate-agent-skills validate-agent-layer
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py tests/test_agent_layer_mirror.py tests/test_agent_context_routing.py

release-check: validate-project validate-template-docs validate-agent-skills validate-agent-layer
	UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} UV_LINK_MODE=$${UV_LINK_MODE:-copy} uv run pytest

template-release-prepare:
	PYTHONDONTWRITEBYTECODE=1 python tools/template_release.py prepare $(if $(BUMP),--bump $(BUMP),) $(if $(filter 1 true yes,$(DRY_RUN)),--dry-run,)

template-release-tag:
	PYTHONDONTWRITEBYTECODE=1 python tools/template_release.py tag

test-template:
	uv run pytest

test-agent:
	uv run pytest tests/test_agent_efficiency.py

test-workflow:
	uv run pytest tests/test_agent_one_task_workflow_golden_path.py

test-lifecycle:
	uv run pytest tests/test_project_state_validation_golden_path.py

test-static:
	uv run pytest tests/test_template_static.py

test-mirror:
	uv run pytest tests/test_agent_layer_mirror.py

test-release-workflow:
	uv run pytest tests/test_template_release_workflow.py

test-backend:
	uv run pytest tests/test_backend_shared_golden_path.py tests/test_fullstack_local_golden_path.py tests/test_fullstack_production_golden_path.py

test-frontend:
	uv run pytest tests/test_frontend_shared_golden_path.py tests/test_fullstack_local_golden_path.py tests/test_fullstack_production_golden_path.py

test-python-profiles:
	uv run pytest tests/test_script_local_golden_path.py tests/test_library_shared_golden_path.py tests/test_backend_shared_golden_path.py tests/test_fullstack_local_golden_path.py tests/test_fullstack_production_golden_path.py

test-copier-update:
	uv run pytest tests/test_copier_update_golden_path.py

project-status:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py status

sync-project-docs:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py sync

validate-project:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py validate

validate-template-docs:
	PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} uv run python tools/template_docs.py

agent-status:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py status

agent-context:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py context --task $(TASK) $(if $(SKILL),--skill $(SKILL),) $(if $(MODE),--mode $(MODE),) $(if $(FORMAT),--format $(FORMAT),)

validate-agent-skills:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/agent.py validate-skills

validate-agent-layer:
	PYTHONDONTWRITEBYTECODE=1 python tools/agent_layer.py check

sync-agent-layer:
	PYTHONDONTWRITEBYTECODE=1 python tools/agent_layer.py sync

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

pr-validate:
	PYTHONDONTWRITEBYTECODE=1 python template/tools/project.py pr-validate
