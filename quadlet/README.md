# Local services with Podman Quadlet

These Quadlets run PostgreSQL, Meilisearch, and the Playwright browser server as
rootless systemd user services
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
systemctl --user start poliloom-postgres poliloom-meilisearch poliloom-playwright
```

Set the same development `MEILI_MASTER_KEY` in `.env` and `poliloom/.env`.
Services are exposed on `localhost` at ports 5432, 7700, and 9222 respectively.
`poliloom/.env` must point `PLAYWRIGHT_WS_ENDPOINT` at the Playwright service,
e.g. `ws://127.0.0.1:9222/`. Any Playwright browser server on that port works, so
an existing one (such as `mine-browser`) can be used instead; only run one.

## Operations

```bash
# Status
systemctl --user status poliloom-postgres poliloom-meilisearch poliloom-playwright

# Logs
journalctl --user -u poliloom-postgres -u poliloom-meilisearch -u poliloom-playwright -f

# Stop
systemctl --user stop poliloom-postgres poliloom-meilisearch poliloom-playwright
```

Data is kept in named Podman volumes. Stop a service before deleting its volume
to reset it:

```bash
podman volume rm poliloom-postgres
podman volume rm poliloom-meilisearch
```
