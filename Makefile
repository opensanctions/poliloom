.PHONY: pgadmin-start pgadmin-stop download-wikidata-dump extract-wikidata-dump db-truncate db-dump db-restore run-download-pipeline run-import-pipeline export-positions-csv export-locations-csv index-dump index-dump-restore index-snapshot index-snapshot-restore

# Start pgAdmin4 container for database inspection
pgadmin-start:
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
			-e PGADMIN_CONFIG_SERVER_MODE=False \
			-e PGADMIN_CONFIG_MASTER_PASSWORD_REQUIRED=False \
			-v $(PWD)/pgadmin-servers.json:/pgadmin4/servers.json \
			--network poliloom_default \
			dpage/pgadmin4:latest; \
	fi

# Stop and remove pgAdmin4 container
pgadmin-stop:
	docker stop poliloom-pgadmin || true
	docker rm poliloom-pgadmin || true


# Truncate main database tables (cascades will handle related tables)
db-truncate:
	@echo "Truncating main database tables..."
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "TRUNCATE TABLE politicians, countries, locations, positions, wikidata_classes CASCADE;"
	@echo "Database tables truncated successfully."

# Dump database to local file
db-dump:
	@mkdir -p dumps
	@echo "Dumping database to dumps/postgres.sql..."
	@docker compose exec -T postgres pg_dump -U postgres -d poliloom -f /dumps/postgres.sql
	@echo "Database dumped successfully to dumps/postgres.sql"

# Restore database from local file
db-restore:
	@echo "Restoring database from dumps/postgres.sql..."
	@if [ ! -f dumps/postgres.sql ]; then \
		echo "Error: dumps/postgres.sql not found. Run 'make db-dump' first."; \
		exit 1; \
	fi
	@docker compose exec -T postgres psql -U postgres -d poliloom -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@docker compose exec -T postgres psql -U postgres -d poliloom -f /docker-entrypoint-initdb.d/01-init.sql
	@docker compose exec -T postgres psql -U postgres -d poliloom -f /dumps/postgres.sql
	@echo "Database restored successfully from dumps/postgres.sql"


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

# Dump search index to local file
index-dump:
	@mkdir -p dumps
	@echo "Dumping Meilisearch to dumps/meilisearch.dump..."
	@. ./.env && \
	TASK_UID=$$(curl -s -X POST "http://localhost:7700/dumps" \
		-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq -r '.taskUid') && \
	trap 'echo "Cancelling dump task..."; curl -s -X POST "http://localhost:7700/tasks/cancel?uids=$$TASK_UID" -H "Authorization: Bearer $$MEILI_MASTER_KEY" > /dev/null; exit 1' INT && \
	echo "Dump task started (taskUid: $$TASK_UID). Waiting for completion..." && \
	while true; do \
		STATUS=$$(curl -s "http://localhost:7700/tasks/$$TASK_UID" \
			-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq -r '.status'); \
		if [ "$$STATUS" = "succeeded" ]; then \
			DUMP_UID=$$(curl -s "http://localhost:7700/tasks/$$TASK_UID" \
				-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq -r '.details.dumpUid'); \
			mv dumps/$$DUMP_UID.dump dumps/meilisearch.dump; \
			echo "Meilisearch dumped successfully to dumps/meilisearch.dump"; \
			break; \
		elif [ "$$STATUS" = "failed" ]; then \
			echo "Dump failed!"; \
			exit 1; \
		fi; \
		sleep 1; \
	done

# Restore search index from local file
index-dump-restore:
	@echo "Restoring Meilisearch from dumps/meilisearch.dump..."
	@if [ ! -f dumps/meilisearch.dump ]; then \
		echo "Error: dumps/meilisearch.dump not found. Run 'make index-dump' first."; \
		exit 1; \
	fi
	@docker compose stop meilisearch
	@. ./.env && docker run --rm \
		-v poliloom_meilisearch_data:/meili_data \
		-v $(PWD)/dumps:/dumps \
		-e MEILI_MASTER_KEY=$$MEILI_MASTER_KEY \
		getmeili/meilisearch:v1.29 \
		meilisearch --import-dump /dumps/meilisearch.dump
	@docker compose up -d meilisearch
	@echo "Meilisearch restored successfully from dumps/meilisearch.dump"

# Create search index snapshot (faster than dump, same version only)
index-snapshot:
	@mkdir -p dumps
	@echo "Creating Meilisearch snapshot in dumps/..."
	@. ./.env && \
	TASK_UID=$$(curl -s -X POST "http://localhost:7700/snapshots" \
		-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq -r '.taskUid') && \
	trap 'echo "Cancelling snapshot task..."; curl -s -X POST "http://localhost:7700/tasks/cancel?uids=$$TASK_UID" -H "Authorization: Bearer $$MEILI_MASTER_KEY" > /dev/null; exit 1' INT && \
	echo "Snapshot task started (taskUid: $$TASK_UID). Waiting for completion..." && \
	while true; do \
		STATUS=$$(curl -s "http://localhost:7700/tasks/$$TASK_UID" \
			-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq -r '.status'); \
		if [ "$$STATUS" = "succeeded" ]; then \
			echo "Snapshot created successfully in dumps/"; \
			ls -lh dumps/*.snapshot 2>/dev/null || echo "Snapshot file created"; \
			break; \
		elif [ "$$STATUS" = "failed" ]; then \
			echo "Snapshot failed!"; \
			curl -s "http://localhost:7700/tasks/$$TASK_UID" \
				-H "Authorization: Bearer $$MEILI_MASTER_KEY" | jq '.error'; \
			exit 1; \
		fi; \
		sleep 1; \
	done

# Restore search index from snapshot (same version only)
index-snapshot-restore:
	@echo "Restoring Meilisearch from snapshot..."
	@SNAPSHOT=$$(ls -t dumps/*.snapshot 2>/dev/null | head -1); \
	if [ -z "$$SNAPSHOT" ]; then \
		echo "Error: No snapshot found in dumps/. Run 'make index-snapshot' first."; \
		exit 1; \
	fi; \
	echo "Using snapshot: $$SNAPSHOT"
	@docker compose stop meilisearch
	@docker volume rm poliloom_meilisearch_data || true
	@SNAPSHOT=$$(ls -t dumps/*.snapshot 2>/dev/null | head -1) && \
	. ./.env && docker run --rm \
		-v poliloom_meilisearch_data:/meili_data \
		-v $(PWD)/dumps:/dumps \
		-e MEILI_MASTER_KEY=$$MEILI_MASTER_KEY \
		getmeili/meilisearch:v1.29 \
		meilisearch --import-snapshot /dumps/$$(basename $$SNAPSHOT)
	@docker compose up -d meilisearch
	@echo "Meilisearch restored successfully from snapshot"
