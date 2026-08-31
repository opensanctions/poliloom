.PHONY: db-truncate db-dump db-restore export-positions-csv index-dump index-snapshot

DB_HOST ?= localhost
DB_PORT ?= 5432
DB_NAME ?= poliloom
DB_USER ?= postgres
DB_PASSWORD ?= postgres

PSQL = PGPASSWORD="$(DB_PASSWORD)" psql -h "$(DB_HOST)" -p "$(DB_PORT)" -U "$(DB_USER)" -d "$(DB_NAME)"

# Database commands use the exposed port and work with Compose or Quadlet.

# Truncate main database tables (cascades will handle related tables)
db-truncate:
	@echo "Truncating main database tables..."
	@$(PSQL) -c "TRUNCATE TABLE politicians, countries, locations, positions, wikidata_classes CASCADE;"
	@echo "Database tables truncated successfully."

# Dump database to local file
db-dump:
	@mkdir -p dumps
	@echo "Dumping database to dumps/postgres.sql..."
	@PGPASSWORD="$(DB_PASSWORD)" pg_dump -h "$(DB_HOST)" -p "$(DB_PORT)" -U "$(DB_USER)" -d "$(DB_NAME)" -f dumps/postgres.sql
	@echo "Database dumped successfully to dumps/postgres.sql"

# Restore database from local file
db-restore:
	@echo "Restoring database from dumps/postgres.sql..."
	@if [ ! -f dumps/postgres.sql ]; then \
		echo "Error: dumps/postgres.sql not found. Run 'make db-dump' first."; \
		exit 1; \
	fi
	@$(PSQL) -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@$(PSQL) -f init-db.sql
	@$(PSQL) -f dumps/postgres.sql
	@echo "Database restored successfully from dumps/postgres.sql"

# Export all positions to CSV file
export-positions-csv:
	@$(PSQL) -c "\COPY (SELECT wikidata_id, name FROM positions ORDER BY wikidata_id) TO STDOUT WITH CSV HEADER"

# Meilisearch writes timestamped dumps and snapshots to dumps/ asynchronously.
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
