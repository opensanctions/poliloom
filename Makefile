.PHONY: db-truncate db-dump db-restore export-positions-csv index-dump index-snapshot

DB_HOST ?= localhost
DB_PORT ?= 5432
DB_NAME ?= poliloom
DB_USER ?= postgres
DB_PASSWORD ?= postgres

PSQL = PGPASSWORD="$(DB_PASSWORD)" psql -h "$(DB_HOST)" -p "$(DB_PORT)" -U "$(DB_USER)" -d "$(DB_NAME)"

db-truncate:
	@echo "Truncating main database tables..."
	@$(PSQL) -c "TRUNCATE TABLE politicians, countries, locations, positions, wikidata_classes CASCADE;"
	@echo "Database tables truncated successfully."

DUMP_FILE = poliloom-db-$(shell date +%Y%m%d-%H%M%S).sql

db-dump:
	@mkdir -p dumps
	@echo "Dumping database to dumps/$(DUMP_FILE)..."
	@PGPASSWORD="$(DB_PASSWORD)" pg_dump -h "$(DB_HOST)" -p "$(DB_PORT)" -U "$(DB_USER)" -d "$(DB_NAME)" -f dumps/$(DUMP_FILE)
	@echo "Database dumped successfully to dumps/$(DUMP_FILE)"

db-restore:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE is required. Usage: make db-restore FILE=path/to/dump.sql"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "Error: $(FILE) not found."; \
		exit 1; \
	fi
	@echo "Restoring database from $(FILE)..."
	@$(PSQL) -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@$(PSQL) -f init-db.sql
	@$(PSQL) -f "$(FILE)"
	@echo "Database restored successfully from $(FILE)"

export-positions-csv:
	@$(PSQL) -c "\COPY (SELECT wikidata_id, name FROM positions ORDER BY wikidata_id) TO STDOUT WITH CSV HEADER"

index-dump:
	@mkdir -p dumps
	@. ./.env && curl --fail-with-body --silent --show-error \
		-X POST http://localhost:7700/dumps \
		-H "Authorization: Bearer $$MEILI_MASTER_KEY"
	@echo

index-snapshot:
	@mkdir -p dumps
	@. ./.env && curl --fail-with-body --silent --show-error \
		-X POST http://localhost:7700/snapshots \
		-H "Authorization: Bearer $$MEILI_MASTER_KEY"
	@echo
