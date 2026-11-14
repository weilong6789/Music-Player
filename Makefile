URL := http://localhost:8000
UVICORN := uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

.PHONY: setup build start dev dev-backend dev-frontend test

setup:
	uv sync
	cd frontend && npm install

build:
	cd frontend && npm run build

# Builds the frontend, starts the server, opens the browser once it responds.
start: build
	@(until curl -sf $(URL)/api/health >/dev/null 2>&1; do sleep 0.3; done; \
	  open $(URL) 2>/dev/null || xdg-open $(URL) 2>/dev/null || true) &
	$(UVICORN)

# Backend with reload on :8000, Vite dev server on :5173 proxying /api.
dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(UVICORN) --reload --reload-dir backend

dev-frontend:
	cd frontend && npm run dev

test:
	uv run pytest
	cd frontend && npm run typecheck
