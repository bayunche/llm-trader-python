.PHONY: install format lint lint-fix test plan

install:
	poetry install

format:
	poetry run black src tests

lint:
	poetry run ruff check src tests

lint-fix:
	poetry run ruff check src tests --fix

test:
	poetry run pytest

plan:
	@echo "=== 当前开发计划 ==="
	@cat 开发计划.md
