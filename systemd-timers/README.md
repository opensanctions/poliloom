# PoliLoom Systemd Timers

Systemd timer configurations for running PoliLoom on a production server. These handle automated backups and data pipeline updates.

## Setup

1. Copy service and timer files to systemd directory:

```bash
sudo cp *.service *.timer /etc/systemd/system/
```

2. Add required environment variables to `/root/poliloom/.env`:

```bash
# For backup service
POLILOOM_BACKUP_ROOT=gs://your-bucket-name/backup
```

3. Reload systemd and enable timers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable poliloom-backup.timer
sudo systemctl enable poliloom-pipeline.timer
sudo systemctl start poliloom-backup.timer
sudo systemctl start poliloom-pipeline.timer
```

## Timers

### poliloom-backup

- **Schedule**: Daily at 2 AM (±30min random delay)
- **Function**: PostgreSQL backup to Google Cloud Storage (custom format, compressed)
- **Timeout**: 2 hours
- **Format**: Creates `.dump.bz2` files compatible with `pg_restore`

### poliloom-pipeline

- **Schedule**: Daily at 3 AM (±1hr random delay)
- **Function**: Download, import, and garbage collection
- **Timeout**: 3 days
- **Note**: Exits gracefully if no new dump available

## Monitoring

Check timer status:

```bash
sudo systemctl list-timers poliloom-*
```

View logs:

```bash
sudo journalctl -u poliloom-backup.service
sudo journalctl -u poliloom-pipeline.service
```

## Backup and Restore

### Restoring from Backup

The backup service creates compressed PostgreSQL custom format dumps that can be restored using `pg_restore`:

```bash
# Restore from GCS backup (compressed custom format dump)
gsutil cp gs://your-bucket-name/backup/poliloom-db-20241228-120000.dump.bz2 - | bunzip2 | PGPASSWORD=postgres pg_restore -h localhost -p 5432 -U postgres -d poliloom --verbose --clean --if-exists

# Or from local file
bunzip2 -c poliloom-db-20241228-120000.dump.bz2 | PGPASSWORD=postgres pg_restore -h localhost -p 5432 -U postgres -d poliloom --verbose --clean --if-exists
```

### Manual Backup

To create a backup manually:

```bash
# Same format as the automated backup
PGPASSWORD=postgres pg_dump -h localhost -p 5432 -U postgres -d poliloom --format=custom --no-restrict | lbzip2 > poliloom-backup-$(date +%Y%m%d-%H%M%S).dump.bz2
```
