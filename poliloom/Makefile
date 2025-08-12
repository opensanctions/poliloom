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


# Truncate main database tables (cascades will handle related tables)
truncate-db:
	@echo "Truncating main database tables..."
	@docker-compose exec -T postgres psql -U postgres -d poliloom -c "TRUNCATE TABLE politicians, countries, locations, positions CASCADE;"
	@echo "Database tables truncated successfully."
