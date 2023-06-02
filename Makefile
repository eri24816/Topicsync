APP = api

.PHONY: clean init test

init:
	poetry env use python3.11
	poetry install

test:
	poetry run pytest -vv --cov-report=term-missing --cov=unittest

clean:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	rm -rf .hypothesis
	rm -rf .pytest_cache
	rm -rf .tox
	rm -f report.xml
	rm -f coverage.xml