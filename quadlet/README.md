# Local services with Podman Quadlet

These Quadlets run PostgreSQL and Meilisearch as rootless systemd user services
for local development. PostgreSQL contains separate development and test databases. The API and GUI still run
from the working tree.

## Setup

Requires Linux with systemd, cgroups v2, and Podman 6.1 or newer.

From the repository root:

```bash
cp .env.example .env
cp poliloom/.env.example poliloom/.env
mkdir -p dumps ~/.config/containers/systemd
ln -sfn "$PWD/quadlet" ~/.config/containers/systemd/poliloom
systemctl --user daemon-reload
systemctl --user start poliloom-postgres poliloom-meilisearch
```

Set the same development `MEILI_MASTER_KEY` in `.env` and `poliloom/.env`.
Services are exposed on `localhost` at ports 5432 and 7700 respectively.

## Operations

```bash
# Status
systemctl --user status poliloom-postgres poliloom-meilisearch

# Logs
journalctl --user -u poliloom-postgres -u poliloom-meilisearch -f

# Stop
systemctl --user stop poliloom-postgres poliloom-meilisearch
```

Data is kept in named Podman volumes. Stop a service before deleting its volume
to reset it:

```bash
podman volume rm poliloom-postgres
podman volume rm poliloom-meilisearch
```

`make index-dump` and `make index-snapshot` work through Meilisearch's localhost
API with either Compose or Quadlet. Restoring a dump or snapshot must be done at
Meilisearch startup using `--import-dump` or `--import-snapshot`, so it remains a
runtime-specific manual operation rather than a Make target.
