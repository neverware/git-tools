all: format lint

format:
	yapf -i *.py

lint:
	pylint *.py

.PHONY: all format lint
