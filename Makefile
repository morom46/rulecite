PY := .venv/bin/python

.PHONY: help setup ingest test clean

help:
	@echo "make setup    create .venv and install the pinned packages"
	@echo "make ingest   parse data/raw/*.pdf into data/processed/rules.jsonl"
	@echo "make test     run all tests (real-data tests run only after make ingest)"
	@echo "make clean    remove data/processed and caches"

setup:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e . --no-deps

data/processed/rules.jsonl: data/raw/DISP.pdf data/raw/BCOBS.pdf data/raw/PRIN.pdf rulecite/ingest.py rulecite/ids.py
	$(PY) -m rulecite.ingest

ingest: data/processed/rules.jsonl

test:
	$(PY) -m pytest

clean:
	rm -rf data/processed .pytest_cache
	find . -name __pycache__ -prune -exec rm -rf {} +
