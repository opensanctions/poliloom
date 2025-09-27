# PoliLoom Systemd Timers

Systemd timer templates for automated PoliLoom operations.

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
- **Function**: PostgreSQL backup to Google Cloud Storage
- **Timeout**: 2 hours

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
