# Makefile for Audiobook Timestamp Extractor

PYTHON := python3
PIP := pip
VENV_BIN := ./venv/bin

.PHONY: install test run-local build run-docker clean

install:
	$(PIP) install -r requirements.txt

test:
	@echo "Running tests with coverage (excluding main.py)..."
	# Ensure venv usage if available, else assume active env
	if [ -d "venv" ]; then \
		source venv/bin/activate && PYTHONPATH=. pytest --cov=src tests/; \
	else \
		PYTHONPATH=. pytest --cov=src tests/; \
	fi

run-local:
	@echo "Running locally..."
	$(PYTHON) -m src.main --help

docker-build:
	docker build -t audiobook-extractor .

run-docker:
	@echo "Run with example volume mount (adjust paths as needed):"
	@echo "docker run -v \$$(pwd)/repo:/app/repo -v \$$(pwd)/input:/app/input audiobook-extractor input/epub/book.epub input/audio/book.m4b"

clean:
	rm -rf __pycache__
	rm -rf src/__pycache__
	rm -rf tests/__pycache__
	rm -f .coverage
	rm -f chapter_timestamps.json
	rm -rf repo/
