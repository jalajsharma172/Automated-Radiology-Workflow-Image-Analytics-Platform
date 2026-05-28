.PHONY: dev test lint build

dev:
	@echo "Starting development environment..."
	docker-compose up --build

test:
	@echo "Running tests..."
	pytest backend/tests
	pytest ai-service/tests

lint:
	@echo "Running linter..."
	flake8 backend ai-service

build:
	@echo "Building production bundles..."
	docker-compose build
