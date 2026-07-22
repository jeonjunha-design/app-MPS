#!/bin/bash
# MPS 환자 차트 자동 백업 스크립트

APP_DIR="/Users/juna/Documents/app-MPS"
BACKUP_BASE="$APP_DIR/patients/_backup_$(date +%Y%m%d_%H%M%S)"
PATIENTS_DIR="$APP_DIR/patients"
LOG_FILE="$APP_DIR/backup.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') 백업 시작..." >> "$LOG_FILE"

mkdir -p "$BACKUP_BASE"

COUNT=0
for f in "$PATIENTS_DIR"/*.json; do
    if [ -f "$f" ]; then
        cp "$f" "$BACKUP_BASE/"
        COUNT=$((COUNT + 1))
    fi
done

echo "$(date '+%Y-%m-%d %H:%M:%S') 백업 완료: ${COUNT}개 파일 -> $BACKUP_BASE" >> "$LOG_FILE"

find "$PATIENTS_DIR" -maxdepth 1 -type d -name "_backup_*" -mtime +7 -exec rm -rf {} \; 2>/dev/null
echo "$(date '+%Y-%m-%d %H:%M:%S') 7일 이상 구백업 정리 완료" >> "$LOG_FILE"

echo "백업 완료: ${COUNT}개 파일"
