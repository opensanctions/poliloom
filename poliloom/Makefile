.PHONY: pgadmin start-pgadmin stop-pgadmin download-wikidata-dump extract-wikidata-dump truncate-db

# Start pgAdmin4 container for database inspection
pgadmin:
	docker run -d \
		--name poliloom-pgadmin \
		-p 9000:80 \
		-e PGADMIN_DEFAULT_EMAIL=admin@example.com \
		-e PGADMIN_DEFAULT_PASSWORD=admin \
		-v $(PWD)/pgadmin-servers.json:/pgadmin4/servers.json \
		--network poliloom_default \
		dpage/pgadmin4:latest

# Alias for pgadmin
start-pgadmin: pgadmin

# Stop and remove pgAdmin4 container
stop-pgadmin:
	docker stop poliloom-pgadmin || true
	docker rm poliloom-pgadmin || true

# Download the latest Wikidata dump (bzip2 compressed)
download-wikidata-dump:
	@if [ -f .env ]; then export $$(grep -v '^#' .env | xargs); fi; \
	OUTPUT_PATH=$${WIKIDATA_DUMP_BZ2_PATH:-./latest-all.json.bz2}; \
	echo "Downloading latest Wikidata dump (bzip2)..."; \
	echo "This is a large file (~100GB compressed) and may take several hours."; \
	curl -L -o "$$OUTPUT_PATH" https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2; \
	echo "Download complete: $$OUTPUT_PATH"

# Extract Wikidata dump using parallel decompression
extract-wikidata-dump:
	@if [ -f .env ]; then export $$(grep -v '^#' .env | xargs); fi; \
	INPUT_PATH=$${WIKIDATA_DUMP_BZ2_PATH:-./latest-all.json.bz2}; \
	OUTPUT_PATH=$${WIKIDATA_DUMP_JSON_PATH:-./latest-all.json}; \
	if [ ! -f "$$INPUT_PATH" ]; then \
		echo "Error: Dump file not found at $$INPUT_PATH"; \
		echo "Run 'make download-wikidata-dump' first or set WIKIDATA_DUMP_BZ2_PATH in .env"; \
		exit 1; \
	fi; \
	if ! command -v lbzip2 >/dev/null 2>&1; then \
		echo "Error: lbzip2 not found. Please install lbzip2 for parallel decompression."; \
		echo "On Ubuntu/Debian: sudo apt-get install lbzip2"; \
		echo "On macOS: brew install lbzip2"; \
		exit 1; \
	fi; \
	echo "Extracting $$INPUT_PATH to $$OUTPUT_PATH using lbzip2..."; \
	lbzip2 -d -c "$$INPUT_PATH" > "$$OUTPUT_PATH"; \
	echo "Extraction complete: $$OUTPUT_PATH"

# Truncate main database tables (cascades will handle related tables)
truncate-db:
	@echo "Truncating main database tables..."
	@docker-compose exec -T postgres psql -U postgres -d poliloom -c "TRUNCATE TABLE politicians, countries, locations, positions CASCADE;"
	@echo "Database tables truncated successfully."
