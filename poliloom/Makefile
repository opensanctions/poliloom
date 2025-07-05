.PHONY: pgadmin start-pgadmin stop-pgadmin download-wikidata-dump

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
	@echo "Downloading latest Wikidata dump (bzip2)..."
	@echo "This is a large file (~100GB compressed) and may take several hours."
	curl -L -o latest-all.json.bz2 https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2
	@echo "Download complete: latest-all.json.bz2"
