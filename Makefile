.PHONY: setup install test run-backend run-frontend demo sentinel benchmark challenge metamorphic docker-up docker-down clean

setup:
	python scripts/setup_project.py

install:
	pip install -r requirements.txt
	cd frontend && npm install

run-backend:
	uvicorn backend.app.main:app --reload --port 8000

run-frontend:
	cd frontend && npm run dev

test:
	pytest backend/tests -v

demo:
	python scripts/demo_golden_path.py

sentinel:
	python scripts/sentinel.py list

benchmark:
	python scripts/sentinel.py benchmark run

challenge:
	python scripts/sentinel.py challenge run --preset Q1

metamorphic:
	python scripts/metamorphic_harness.py

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
