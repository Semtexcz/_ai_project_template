.PHONY: test-template test-copier-update

test-template:
	uv run pytest

test-copier-update:
	uv run pytest tests/test_copier_update_golden_path.py
