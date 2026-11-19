PY := .venv/bin/python

.PHONY: help setup ingest test testset review search search-dev search-test clean

help:
	@echo "make setup    create .venv and install the pinned packages (with PyTorch for the CPU)"
	@echo "make ingest   parse data/raw/*.pdf into data/processed/rules.jsonl"
	@echo "make test     run all tests (real-data tests run only after make ingest)"
	@echo "make testset  check testset/questions.jsonl and print its counts"
	@echo "make review   check the test questions by hand, one at a time"
	@echo "make search Q=\"...\"   search the rules for one question"
	@echo "make search-dev   score the search methods on dev and choose the re-ranking depth"
	@echo "make search-test  score them on test, with the depth chosen on dev"
	@echo "make clean    remove data/processed and caches"

setup:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -r requirements-models.txt
	$(PY) -m pip install -e . --no-deps

data/processed/rules.jsonl: data/raw/DISP.pdf data/raw/BCOBS.pdf data/raw/PRIN.pdf rulecite/ingest.py rulecite/ids.py
	$(PY) -m rulecite.ingest

ingest: data/processed/rules.jsonl

test:
	$(PY) -m pytest

testset:
	$(PY) -m rulecite.testset

review: data/processed/rules.jsonl
	$(PY) -m rulecite.review

search: data/processed/rules.jsonl
	$(PY) -m rulecite.search "$(Q)"

search-dev: data/processed/rules.jsonl
	$(PY) -m rulecite.evaluate --split dev

search-test: data/processed/rules.jsonl
	$(PY) -m rulecite.evaluate --split test

clean:
	rm -rf data/processed .pytest_cache
	find . -name __pycache__ -prune -exec rm -rf {} +
