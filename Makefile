.PHONY: install install-dev test clean build release

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

clean:
	rm -rf dist/ build/ *.egg-info

build: clean
	python -m build

release: build
	twine upload dist/*
