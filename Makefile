.PHONY: setup install test run-backend run-frontend demo docker-up docker-down clean

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

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
