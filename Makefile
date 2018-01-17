.PHONY: clean clean-test clean-pyc docs
.DEFAULT_GOAL := run
define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT


VENV_EXISTS=$(shell [ -e .venv ] && echo 1 || echo 0 )
VENV_PATH=.venv
VENV_BIN=$(VENV_PATH)/bin
BROWSER := $(VENV_BIN)/python -c "$$BROWSER_PYSCRIPT"

.PHONY: clean
clean: clean-pyc clean-test clean-venv ## remove all build, test, coverage and Python artifacts

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test: ## remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/

.PHONY: clean-venv
clean-venv:
	-rm -rf $(VENV_PATH)

.PHONY: venv
venv: ## Create virtualenv directory and install all requirements
ifeq ($(VENV_EXISTS), 1)
	@echo virtual env already initialized
else
	virtualenv -p python3.6 .venv
	$(VENV_BIN)/pip install Cython==0.27.3 -vv
	$(VENV_BIN)/pip install -r requirements_dev.txt
endif

.PHONY: flake8
flake8: venv ## flake8
	$(VENV_BIN)/flake8 aiodirector examples tests setup.py

.PHONY: bandit
bandit: venv  # find common security issues in code
	$(VENV_BIN)/bandit -r ./aiodirector ./examples setup.py

.PHONY: mypy
mypy: venv ## lint
	$(VENV_BIN)/mypy aiodirector examples setup.py --ignore-missing-imports

.PHONY: lint
lint: flake8 bandit mypy ## lint

.PHONY: test
test: venv ## run tests
	$(VENV_BIN)/pytest

.PHONY: coverage-quiet
coverage-quiet: venv ## make coverage report
		$(VENV_BIN)/coverage run --source aiodirector -m pytest
		$(VENV_BIN)/coverage report -m
		$(VENV_BIN)/coverage html

.PHONY: coverage
coverage: venv coverage-quiet ## make coverage report and open it in browser
		$(BROWSER) htmlcov/index.html

.PHONY: docs
docs-quiet: venv ## make documentation
	rm -f docs/aiodirector.rst
	rm -f docs/modules.rst
	.venv/bin/sphinx-apidoc -o docs/ aiodirector
	$(MAKE) -C docs clean
	$(MAKE) -C docs html

.PHONY: docs
docs: venv docs-quiet ## make documentation and open it in browser
	$(BROWSER) docs/_build/html/index.html

.PHONY: servedocs
servedocs: docs ## compile the docs watching for changes
	$(VENV_BIN)/watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .

.PHONY: help
help:  ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-23s\033[0m %s\n", $$1, $$2}'
