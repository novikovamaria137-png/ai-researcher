.PHONY: install install-dev test lint demo run run-fashion clean

PY ?= python3
export PYTHONPATH := src

install:
	$(PY) -m pip install -r requirements.txt

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests

## Офлайн-демо: дайджест из встроенного фикстур-фида, без сети и без ключей.
demo:
	$(PY) scripts/demo.py

## Боевой прогон в консоль: ничего не отправляет и не меняет состояние.
run:
	$(PY) -m ai_researcher --preset ai --dry-run --verbose

run-fashion:
	$(PY) -m ai_researcher --preset fashion --dry-run --verbose

clean:
	rm -rf .pytest_cache **/__pycache__ digests data
