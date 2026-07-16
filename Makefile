.PHONY: install demo test lint run clean

install:
	pip install -r requirements-dev.txt

demo:          ## Run the agent offline — no API keys needed
	python demo.py

test:
	pytest -q

test-cov:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check app tests
	ruff format --check app tests

run:
	uvicorn app.main:app --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
