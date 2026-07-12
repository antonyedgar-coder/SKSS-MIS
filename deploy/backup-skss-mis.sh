#!/bin/bash
BACKUP_DIR="/var/backups/skss-mis"
mkdir -p "$BACKUP_DIR"
cp /var/www/skss-mis/skss_mis.db "$BACKUP_DIR/skss_mis_$(date +%F_%H-%M).db"
find "$BACKUP_DIR" -type f -mtime +14 -delete
