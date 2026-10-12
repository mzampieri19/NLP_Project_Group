.DEFAULT_GOAL := help

VENV := .venv
PY := $(VENV)/bin/python
BIN := $(VENV)/bin
PRE_COMMIT_CONFIG := config/.pre-commit-config.yaml

.PHONY: help setup lint format clean-nb check commit docker-build docker-run docker-stop

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create a local venv, install dev dependencies into it, and install git hooks
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	$(BIN)/pre-commit install -c $(PRE_COMMIT_CONFIG) --hook-type pre-commit --hook-type commit-msg

lint: ## Run ruff + nbqa checks (no fixes)
	$(BIN)/ruff check .
	$(BIN)/nbqa ruff .

format: ## Auto-fix and format Python code and notebooks
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .
	$(BIN)/nbqa ruff --fix .

clean-nb: ## Strip output/metadata from notebooks
	$(BIN)/nbstripout --all **/*.ipynb 2>/dev/null || find . -name '*.ipynb' -exec $(BIN)/nbstripout {} +

check: ## Run all pre-commit hooks against every file (what CI runs)
	$(BIN)/pre-commit run -c $(PRE_COMMIT_CONFIG) --all-files

commit: ## Interactively build a Conventional Commit message
	$(BIN)/cz commit

### Pipeline

select-pairs:
	python3 src/select_turns.py --esconv data/ESConv.json --out work

generate-pairs-10:
	python3 src/generate_pairs.py --work work --config src/gen_config.json --limit 10

generate-pairs-all:
	python3 src/generate_pairs.py --work work --config src/gen_config.json

check-pairs:
	python3 src/check_pairs.py --work work

finalize-pairs:
	python3 src/finalize_pairs.py --work work

process: # selects pairs, generates new sets, checks pairs
	make select-pairs generate-pairs-10 check-pairs finalize-pairs

docker-build: ## Build the dev environment image
	docker build -f docker/Dockerfile -t nlp-project-group .

docker-run: ## Run Jupyter Lab in the dev container, mounting the repo
	docker run --rm -it --name nlp-dev -p 8888:8888 -v $(PWD):/app nlp-project-group

docker-stop: ## Stop the running dev container
	docker stop nlp-dev
