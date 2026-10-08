.DEFAULT_GOAL := help

.PHONY: help setup lint format clean-nb check commit docker-build docker-run docker-stop

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev dependencies and git hooks
	pip install -r requirements-dev.txt
	pre-commit install --hook-type pre-commit --hook-type commit-msg

lint: ## Run ruff + nbqa checks (no fixes)
	ruff check .
	nbqa ruff .

format: ## Auto-fix and format Python code and notebooks
	ruff check --fix .
	ruff format .
	nbqa ruff --fix .

clean-nb: ## Strip output/metadata from notebooks
	nbstripout --all **/*.ipynb 2>/dev/null || find . -name '*.ipynb' -exec nbstripout {} +

check: ## Run all pre-commit hooks against every file (what CI runs)
	pre-commit run --all-files

commit: ## Interactively build a Conventional Commit message
	cz commit

docker-build: ## Build the dev environment image
	docker build -t nlp-project-group .

docker-run: ## Run Jupyter Lab in the dev container, mounting the repo
	docker run --rm -it --name nlp-dev -p 8888:8888 -v $(PWD):/app nlp-project-group

docker-stop: ## Stop the running dev container
	docker stop nlp-dev
