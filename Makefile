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
	cd cloud && docker compose up -d --build
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
	cd cloud && docker compose exec -T postgres psql -U livestockguard -d livestockguard < migrations/versions/001_initial_schema.sql

db-shell: ## Open PostgreSQL shell
	cd cloud && docker compose exec postgres psql -U livestockguard -d livestockguard

db-seed: ## Load demo farm data (animals, devices, geofences)
	@echo "$(CYAN)Loading seed data...$(RESET)"
	cd cloud && docker compose exec -T postgres psql -U livestockguard -d livestockguard < ../scripts/seed_data.sql
	@echo "$(GREEN)Loaded: Boschhoek Farm (5 animals) + Loch Vaal Plot 30 (10 animals)$(RESET)"

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(YELLOW)Resetting database...$(RESET)"
	cd cloud && docker compose down -v
	$(MAKE) start
	sleep 5
	$(MAKE) db-migrate
	$(MAKE) db-seed

# ─── SIMULATOR ──────────────────────────────────────

simulate: ## Run device simulator (Boschhoek, 5 animals)
	@echo "$(GREEN)Starting device simulator (Boschhoek Farm)...$(RESET)"
	cd tools/simulator && python3 simulator.py --farm boschhoek --animals 5 --interval 10

simulate-lochvaal: ## Run simulator for Loch Vaal (10 animals)
	@echo "$(GREEN)Starting device simulator (Loch Vaal Plot 30)...$(RESET)"
	cd tools/simulator && python3 simulator.py --farm lochvaal --animals 10 --interval 10

simulate-gateway: ## Run herdsman gateway simulator (BLE ear tags)
	@echo "$(GREEN)Starting herdsman gateway simulator (Loch Vaal)...$(RESET)"
	cd tools/simulator && python3 gateway_simulator.py --farm lochvaal --animals 10

simulate-gateway-offline: ## Run gateway simulator without API (print only)
	@echo "$(GREEN)Starting gateway simulator (offline mode)...$(RESET)"
	cd tools/simulator && python3 gateway_simulator.py --farm lochvaal --animals 10 --offline

simulate-day: ## Simulate full herdsman day at Loch Vaal (12h in 6min)
	@echo "$(GREEN)Starting herdsman daily routine simulation...$(RESET)"
	cd tools/simulator && python3 gateway_daily_sim.py --speed 120

simulate-day-offline: ## Simulate herdsman day without API
	@echo "$(GREEN)Starting herdsman daily simulation (offline)...$(RESET)"
	cd tools/simulator && python3 gateway_daily_sim.py --speed 120 --offline

simulate-day-theft: ## Simulate theft at Loch Vaal (cow taken at 8am)
	@echo "$(YELLOW)Starting THEFT scenario (Loch Vaal BLE)...$(RESET)"
	cd tools/simulator && python3 gateway_daily_sim.py --speed 360 --scenario theft

simulate-day-breach: ## Simulate geofence breach at Loch Vaal
	@echo "$(YELLOW)Starting BREACH scenario (Loch Vaal BLE)...$(RESET)"
	cd tools/simulator && python3 gateway_daily_sim.py --speed 360 --scenario breach

simulate-theft: ## Run theft scenario simulation
	@echo "$(YELLOW)Starting THEFT scenario...$(RESET)"
	cd tools/simulator && python3 simulator.py --farm boschhoek --animals 5 --scenario theft --interval 5

simulate-breach: ## Run geofence breach scenario
	@echo "$(YELLOW)Starting BREACH scenario...$(RESET)"
	cd tools/simulator && python3 simulator.py --farm boschhoek --animals 5 --scenario breach --interval 5

simulate-many: ## Simulate 50 animals at Loch Vaal (stress test)
	cd tools/simulator && python3 simulator.py --farm lochvaal --animals 50 --interval 15

# ─── MQTT WRITER ────────────────────────────────────

mqtt-writer: ## Start MQTT→DB writer (bridges simulator to database)
	@echo "$(GREEN)Starting MQTT writer (devices → database)...$(RESET)"
	cd cloud/services/mqtt_writer && python3 mqtt_writer.py

# ─── DASHBOARD ──────────────────────────────────────

dashboard: ## Start web dashboard dev server
	@echo "$(GREEN)Starting dashboard at http://localhost:5173$(RESET)"
	cd dashboard && npm install --silent && npm run dev

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
	@echo "$(GREEN)Cloud stack running. Now open MORE terminals:$(RESET)"
	@echo ""
	@echo "  Terminal 2: make mqtt-writer   (bridges MQTT → database)"
	@echo "  Terminal 3: make simulate      (generates GPS data)"
	@echo "  Terminal 4: make dashboard     (web UI at localhost:5173)"
	@echo ""
	@echo "$(CYAN)Then open http://localhost:5173 in your browser$(RESET)"

demo: ## Full live demo: stack + sims + dashboard (breach scenario)
	@bash scripts/run-demo.sh --breach

demo-normal: ## Full demo with normal day (no incidents)
	@bash scripts/run-demo.sh --normal

demo-theft: ## Full demo with theft scenario
	@bash scripts/run-demo.sh --theft

demo-mobile: ## Full demo + mobile app in browser
	@bash scripts/run-demo.sh --breach --mobile

demo-ios: ## Full demo + iOS simulator build
	@bash scripts/run-demo.sh --breach --mobile --ios

demo-android: ## Full demo + Android emulator build
	@bash scripts/run-demo.sh --breach --mobile --android

mobile-web: ## Start mobile app in browser only (port 8082)
	@echo "$(GREEN)Starting mobile app at http://localhost:8082$(RESET)"
	cd mobile && npm install && npx expo start --web --port 8082

mobile-ios: ## Build and launch mobile app on iOS simulator
	cd mobile && npm install && npx expo run:ios

mobile-android: ## Build and launch mobile app on Android emulator
	cd mobile && npm install && npx expo run:android

stop-all: ## Stop all running processes (Docker stays up)
	@echo "$(YELLOW)Stopping simulators, dashboard, mobile...$(RESET)"
	-pkill -f "gateway_daily_sim" 2>/dev/null || true
	-pkill -f "simulator.py" 2>/dev/null || true
	-pkill -f "vite.*5173" 2>/dev/null || true
	-pkill -f "expo.*8082" 2>/dev/null || true
	@echo "$(GREEN)Stopped. Docker stack still running (use 'make stop' to stop Docker).$(RESET)"

# ─── VERIFICATION ───────────────────────────────────

verify-api: ## Run API feature verification (requires stack running)
	@echo "$(CYAN)Running API feature verification...$(RESET)"
	@bash scripts/verify-features.sh

verify-e2e: ## Run Playwright E2E tests (requires dashboard + stack running)
	@echo "$(CYAN)Running Playwright E2E tests...$(RESET)"
	cd e2e && npx playwright test tests/features.spec.ts --reporter=list

verify-all: ## Run all verification (API + E2E)
	@echo "$(CYAN)Running full verification suite...$(RESET)"
	$(MAKE) verify-api
	@echo ""
	$(MAKE) verify-e2e

# ─── CLEANUP ────────────────────────────────────────

clean: ## Stop everything and remove volumes
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	cd cloud && docker compose down -v --remove-orphans
	rm -rf dashboard/node_modules
	rm -rf cloud/services/ingestion/target
	rm -rf cloud/services/geofence_engine/target
	@echo "$(GREEN)Clean!$(RESET)"
