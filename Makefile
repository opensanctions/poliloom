.PHONY: pgadmin start-pgadmin stop-pgadmin download-wikidata-dump extract-wikidata-dump db-truncate db-dump db-restore run-download-pipeline run-import-pipeline export-positions-csv export-locations-csv development production

# Start pgAdmin4 container for database inspection
pgadmin:
	@if docker ps -a --format '{{.Names}}' | grep -q '^poliloom-pgadmin$$'; then \
		if docker ps --format '{{.Names}}' | grep -q '^poliloom-pgadmin$$'; then \
			echo "pgAdmin container is already running"; \
		else \
			echo "Starting existing pgAdmin container..."; \
			docker start poliloom-pgadmin; \
		fi \
	else \
		echo "Creating and starting new pgAdmin container..."; \
		docker run -d \
			--name poliloom-pgadmin \
			-p 9000:80 \
			-e PGADMIN_DEFAULT_EMAIL=admin@example.com \
			-e PGADMIN_DEFAULT_PASSWORD=admin \
			-v $(PWD)/pgadmin-servers.json:/pgadmin4/servers.json \
			--network poliloom_default \
			dpage/pgadmin4:latest; \
	fi

# Alias for pgadmin
start-pgadmin: pgadmin

# Stop and remove pgAdmin4 container
stop-pgadmin:
	docker stop poliloom-pgadmin || true
	docker rm poliloom-pgadmin || true


# Truncate main database tables (cascades will handle related tables)
db-truncate:
	@echo "Truncating main database tables..."
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "TRUNCATE TABLE politicians, countries, locations, positions, wikidata_classes CASCADE;"
	@echo "Database tables truncated successfully."

# Dump database to local file
db-dump:
	@echo "Dumping database to poliloom_db_dump.sql..."
	@docker compose exec -T postgres pg_dump -U postgres -d poliloom > poliloom_db_dump.sql
	@echo "Database dumped successfully to poliloom_db_dump.sql"

# Restore database from local file
db-restore:
	@echo "Restoring database from poliloom_db_dump.sql..."
	@if [ ! -f poliloom_db_dump.sql ]; then \
		echo "Error: poliloom_db_dump.sql not found. Run 'make db-dump' first or ensure the file exists."; \
		exit 1; \
	fi
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@docker compose exec -T postgres psql -U postgres -d poliloom < init-db.sql
	@docker compose exec -T postgres psql -U postgres -d poliloom < poliloom_db_dump.sql
	@echo "Database restored successfully from poliloom_db_dump.sql"


# Download and extract wikidata dump
run-download-pipeline:
	@echo "Running download and extract pipeline..."
	@. ./.env && echo "Using file paths from .env:"
	@. ./.env && echo "  Compressed: $$WIKIDATA_DUMP_COMPRESSED"
	@. ./.env && echo "  Extracted: $$WIKIDATA_DUMP_EXTRACTED"
	@echo "⏳ Step 1/2: Downloading wikidata dump..."
	@. ./.env && docker compose run --rm api poliloom dump-download --output $$WIKIDATA_DUMP_COMPRESSED
	@echo "⏳ Step 2/2: Extracting dump..."
	@. ./.env && docker compose run --rm api poliloom dump-extract --input $$WIKIDATA_DUMP_COMPRESSED --output $$WIKIDATA_DUMP_EXTRACTED
	@echo "✅ Download pipeline completed successfully!"

# Run complete import pipeline for wikidata dump
run-import-pipeline:
	@echo "Running complete import pipeline..."
	@echo "This will run: hierarchy → entities → politicians → embeddings"
	@. ./.env && echo "Using extracted dump from .env: $$WIKIDATA_DUMP_EXTRACTED"
	@echo "⏳ Step 1/4: Importing hierarchy trees..."
	@. ./.env && docker compose run --rm api poliloom import-hierarchy --file $$WIKIDATA_DUMP_EXTRACTED
	@echo "⏳ Step 2/4: Importing entities..."
	@. ./.env && docker compose run --rm api poliloom import-entities --file $$WIKIDATA_DUMP_EXTRACTED
	@echo "⏳ Step 3/4: Importing politicians..."
	@. ./.env && docker compose run --rm api poliloom import-politicians --file $$WIKIDATA_DUMP_EXTRACTED
	@echo "⏳ Step 4/4: Generating embeddings..."
	@docker compose run --rm api poliloom embed-entities
	@echo "✅ Import pipeline completed successfully!"

# Export all positions to CSV file
export-positions-csv:
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "\COPY (SELECT wikidata_id, name FROM positions ORDER BY wikidata_id) TO STDOUT WITH CSV HEADER"

# Export all locations to CSV file
export-locations-csv:
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "\COPY (SELECT wikidata_id, name FROM locations ORDER BY wikidata_id) TO STDOUT WITH CSV HEADER"

# Set up development environment with docker compose
development:
	docker compose up -d

# Start production services (GUI and API only, no databases)
production:
	docker compose up -d api gui
