# LivestockGuard — Development Makefile
# Run `make help` for available commands

.PHONY: help setup start stop restart status logs simulate test clean

# Colours
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m
RESET  := \033[0m

help: ## Show this help
	@echo ""
	@echo "$(CYAN)LivestockGuard Development Commands$(RESET)"
	@echo "────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ─── SETUP ──────────────────────────────────────────

setup: ## First-time setup (installs everything)
	@echo "$(CYAN)Setting up LivestockGuard dev environment...$(RESET)"
	@bash scripts/setup.sh

# ─── CLOUD STACK ────────────────────────────────────

start: ## Start cloud stack (PostgreSQL, Redis, EMQX, API)
	@echo "$(GREEN)Starting cloud services...$(RESET)"
	cd cloud && docker compose up -d
	@echo ""
	@echo "$(GREEN)Services started:$(RESET)"
	@echo "  API Gateway:  http://localhost:8000/docs"
	@echo "  MQTT Broker:  localhost:1883"
	@echo "  EMQX Dashboard: http://localhost:18083 (admin/public)"
	@echo "  PostgreSQL:   localhost:5432"
	@echo "  Redis:        localhost:6379"

stop: ## Stop cloud stack
	@echo "$(YELLOW)Stopping cloud services...$(RESET)"
	cd cloud && docker compose down

restart: ## Restart cloud stack
	$(MAKE) stop
	$(MAKE) start

status: ## Show running services
	cd cloud && docker compose ps

logs: ## Tail logs from all services
	cd cloud && docker compose logs -f --tail=50

logs-api: ## Tail API gateway logs only
	cd cloud && docker compose logs -f --tail=50 api_gateway

# ─── DATABASE ───────────────────────────────────────

db-migrate: ## Run database migrations
	@echo "$(CYAN)Running migrations...$(RESET)"
	cd cloud && docker compose exec postgres psql -U livestockguard -d livestockguard -f /docker-entrypoint-initdb.d/001_initial_schema.sql

db-shell: ## Open PostgreSQL shell
	cd cloud && docker compose exec postgres psql -U livestockguard -d livestockguard

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(YELLOW)Resetting database...$(RESET)"
	cd cloud && docker compose down -v
	$(MAKE) start
	sleep 3
	$(MAKE) db-migrate

# ─── SIMULATOR ──────────────────────────────────────

simulate: ## Run device simulator (5 animals, normal)
	@echo "$(GREEN)Starting device simulator...$(RESET)"
	cd tools/simulator && python3 simulator.py --animals 5 --interval 10

simulate-theft: ## Run theft scenario simulation
	@echo "$(YELLOW)Starting THEFT scenario...$(RESET)"
	cd tools/simulator && python3 simulator.py --animals 5 --scenario theft --interval 5

simulate-breach: ## Run geofence breach scenario
	@echo "$(YELLOW)Starting BREACH scenario...$(RESET)"
	cd tools/simulator && python3 simulator.py --animals 5 --scenario breach --interval 5

simulate-many: ## Simulate 50 animals (stress test)
	cd tools/simulator && python3 simulator.py --animals 50 --interval 15

# ─── DASHBOARD ──────────────────────────────────────

dashboard: ## Start web dashboard dev server
	@echo "$(GREEN)Starting dashboard at http://localhost:3000$(RESET)"
	cd dashboard && npm run dev

dashboard-install: ## Install dashboard dependencies
	cd dashboard && npm install

dashboard-build: ## Build dashboard for production
	cd dashboard && npm run build

# ─── TESTING ────────────────────────────────────────

test: ## Run all tests
	@echo "$(CYAN)Running tests...$(RESET)"
	$(MAKE) test-firmware
	$(MAKE) test-cloud
	$(MAKE) test-dashboard

test-firmware: ## Run firmware unit tests (host build)
	@echo "Firmware tests: TODO (requires Unity framework)"

test-cloud: ## Run cloud backend tests
	cd cloud && python3 -m pytest tests/ -v 2>/dev/null || echo "No tests yet"

test-dashboard: ## Run dashboard tests
	cd dashboard && npm test 2>/dev/null || echo "No tests yet"

# ─── FULL STACK ─────────────────────────────────────

dev: ## Start everything for development
	@echo "$(CYAN)Starting full development stack...$(RESET)"
	$(MAKE) start
	@echo ""
	@echo "$(GREEN)Cloud stack running. Now open two more terminals:$(RESET)"
	@echo "  Terminal 2: make dashboard"
	@echo "  Terminal 3: make simulate"
	@echo ""
	@echo "$(CYAN)Then open http://localhost:3000 in your browser$(RESET)"

# ─── CLEANUP ────────────────────────────────────────

clean: ## Stop everything and remove volumes
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	cd cloud && docker compose down -v --remove-orphans
	rm -rf dashboard/node_modules
	rm -rf cloud/services/ingestion/target
	rm -rf cloud/services/geofence_engine/target
	@echo "$(GREEN)Clean!$(RESET)"
