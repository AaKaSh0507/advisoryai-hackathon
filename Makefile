# Template Intelligence Engine - Makefile
# ========================================
# Commands to manage all services

.PHONY: help install up down restart status logs clean build frontend backend db-shell redis-shell minio-shell health

# Default target
help:
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║       Template Intelligence Engine - Available Commands        ║"
	@echo "╠════════════════════════════════════════════════════════════════╣"
	@echo "║  make up           - Start all services (infra + backend)      ║"
	@echo "║  make down         - Stop all services                         ║"
	@echo "║  make restart      - Restart all services                      ║"
	@echo "║  make status       - Show status of all services               ║"
	@echo "║  make logs         - Tail logs from all services               ║"
	@echo "║  make health       - Check health of all services              ║"
	@echo "╠════════════════════════════════════════════════════════════════╣"
	@echo "║  make frontend     - Start frontend dev server                 ║"
	@echo "║  make frontend-install - Install frontend dependencies         ║"
	@echo "║  make backend      - Start only backend services               ║"
	@echo "║  make infra        - Start only infrastructure (db,redis,minio)║"
	@echo "╠════════════════════════════════════════════════════════════════╣"
	@echo "║  make build        - Build/rebuild Docker images               ║"
	@echo "║  make clean        - Stop services and remove volumes          ║"
	@echo "║  make install      - Install all dependencies                  ║"
	@echo "╠════════════════════════════════════════════════════════════════╣"
	@echo "║  make db-shell     - Open PostgreSQL shell                     ║"
	@echo "║  make redis-shell  - Open Redis CLI                            ║"
	@echo "║  make logs-api     - Tail API logs only                        ║"
	@echo "║  make logs-worker  - Tail worker logs only                     ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""

# ============================================================================
# Main Commands
# ============================================================================

## Start all services (infrastructure + backend)
up:
	@echo "🚀 Starting all services..."
	docker compose up -d
	@echo ""
	@echo "✅ Backend services started!"
	@echo ""
	@echo "📍 URLs:"
	@echo "   - Backend API:    http://localhost:8000"
	@echo "   - API Docs:       http://localhost:8000/docs"
	@echo "   - MinIO Console:  http://localhost:9001"
	@echo ""
	@echo "💡 Run 'make frontend' in another terminal to start the frontend"

## Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker compose down
	@-pkill -f "next-server" 2>/dev/null || true
	@-pkill -f "node.*next" 2>/dev/null || true
	@echo "✅ All services stopped"

## Restart all services
restart: down up

## Show status of all services
status:
	@echo "📊 Service Status:"
	@echo ""
	@docker compose ps
	@echo ""
	@echo "🔍 Checking frontend..."
	@curl -s -o /dev/null -w "   Frontend (localhost:3000): HTTP %{http_code}\n" http://localhost:3000 2>/dev/null || echo "   Frontend: Not running"

## Tail logs from all Docker services
logs:
	docker compose logs -f

## Check health of all services
health:
	@echo "🏥 Health Check:"
	@echo ""
	@echo "=== Infrastructure ==="
	@curl -s http://localhost:8000/health/infrastructure 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "❌ Backend not reachable"
	@echo ""
	@echo "=== Workers ==="
	@curl -s http://localhost:8000/health/workers 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "❌ Backend not reachable"
	@echo ""
	@echo "=== Frontend ==="
	@curl -s -o /dev/null -w "Status: HTTP %{http_code}\n" http://localhost:3000 2>/dev/null || echo "❌ Frontend not running"

# ============================================================================
# Individual Service Commands
# ============================================================================

## Start frontend development server
frontend:
	@echo "🎨 Starting frontend dev server..."
	@echo ""
	@echo "📍 Frontend will be available at: http://localhost:3000"
	@echo ""
	cd frontend && npm run dev

## Install frontend dependencies
frontend-install:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ Frontend dependencies installed"

## Start only backend services (api + worker)
backend:
	@echo "🔧 Starting backend services..."
	docker compose up -d api worker
	@echo "✅ Backend services started"

## Start only infrastructure (postgres, redis, minio)
infra:
	@echo "🏗️  Starting infrastructure..."
	docker compose up -d postgres redis minio minio-init
	@echo "✅ Infrastructure started"
	@echo ""
	@echo "📍 Services:"
	@echo "   - PostgreSQL: localhost:5432"
	@echo "   - Redis:      localhost:6379"
	@echo "   - MinIO:      localhost:9000 (API) / localhost:9001 (Console)"

# ============================================================================
# Build & Clean Commands
# ============================================================================

## Build/rebuild Docker images
build:
	@echo "🔨 Building Docker images..."
	docker compose build
	@echo "✅ Build complete"

## Stop services and remove volumes (full cleanup)
clean:
	@echo "🧹 Cleaning up everything..."
	docker compose down -v --remove-orphans
	@-pkill -f "next-server" 2>/dev/null || true
	@-pkill -f "node.*next" 2>/dev/null || true
	@echo "✅ Cleanup complete (volumes removed)"

## Install all dependencies
install: frontend-install
	@echo "✅ All dependencies installed"

# ============================================================================
# Shell Access Commands
# ============================================================================

## Open PostgreSQL shell
db-shell:
	@echo "🐘 Opening PostgreSQL shell..."
	docker exec -it template-intelligence-db psql -U postgres -d template_intelligence

## Open Redis CLI
redis-shell:
	@echo "📮 Opening Redis CLI..."
	docker exec -it template-intelligence-redis redis-cli

# ============================================================================
# Log Commands
# ============================================================================

## Tail API logs only
logs-api:
	docker compose logs -f api

## Tail worker logs only
logs-worker:
	docker compose logs -f worker

## Tail database logs only
logs-db:
	docker compose logs -f postgres

# ============================================================================
# Development Helpers
# ============================================================================

## Run all services (backend + frontend in foreground)
all: up
	@echo ""
	@echo "⏳ Waiting for backend to be healthy..."
	@sleep 5
	@make frontend

## Quick start - build and run everything
start: build up
	@echo ""
	@echo "✅ System ready!"
	@echo ""
	@echo "💡 Run 'make frontend' to start the frontend dev server"
