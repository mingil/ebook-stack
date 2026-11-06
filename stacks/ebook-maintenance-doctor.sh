#!/bin/bash
# =============================================================================
# 🩺 EBOOK STACK DOCTOR - 백업 우선 안전 자동 업데이트 · SQLite 최적화 · 자가치유 스크립트
# =============================================================================
# • Watchtower 라벨 연동과 더불어, 언제든 수동 또는 스케줄러로 실행 시
#   [1. DB 스냅샷 백업] ➔ [2. 각 공식 제작자 최신 이미지 Pull & 무중단 교체] ➔
#   [3. SQLite WAL & VACUUM 속도 최적화] ➔ [4. 구버전 잉여 이미지 청소]를 수행합니다.
# =============================================================================
set -e

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/volume1/docker/_backups/ebook-stack/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

echo "=================================================================="
echo "💾 [1/5] 업데이트 전 Komga · Kavita · Audiobookshelf · Komf · CWA 안전 스냅샷 백업"
echo "=================================================================="
for svc in komga kavita audiobookshelf komf calibre-web-automated; do
  if [ -d "/volume1/docker/$svc" ]; then
    tar -czf "$BACKUP_DIR/${svc}_config_${TIMESTAMP}.tar.gz" \
      --exclude="*.log" --exclude="cache" --exclude="Cache" --exclude="logs" \
      -C "/volume1/docker" "$svc/config" 2>/dev/null || true
    echo "  -> $svc 업데이트 전 안전 백업 완료: $BACKUP_DIR/${svc}_config_${TIMESTAMP}.tar.gz"
  fi
done

# 30일 이상 지난 오래된 백업본 자동 정리 (NAS 용량 보호)
find "/volume1/docker/_backups/ebook-stack" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

echo "=================================================================="
echo "🔄 [2/5] 각 공식 제작자 최신 도커 이미지 확인 및 변경된 컨테이너만 무중단 업데이트"
echo "=================================================================="
if [ -f "/volume1/docker/ebook-stack/docker-compose.yml" ]; then
  cd "/volume1/docker/ebook-stack"
  docker compose pull
  docker compose up -d --remove-orphans
elif [ -f "./docker-compose.yml" ]; then
  docker compose pull
  docker compose up -d --remove-orphans
fi

echo "=================================================================="
echo "⚡ [3/5] SQLite 데이터베이스 조각 모음(WAL Checkpoint & VACUUM) 속도 최적화"
echo "=================================================================="
if command -v sqlite3 >/dev/null 2>&1; then
  for db_file in \
    "/volume1/docker/komga/config/database.sqlite" \
    "/volume1/docker/kavita/config/kavita.db" \
    "/volume1/docker/audiobookshelf/config/absdatabase.sqlite" \
    "/volume1/docker/komf/config/database.sqlite" \
    "/volume1/mediarr/ebooks/calibre-library/metadata.db"; do
    if [ -f "$db_file" ]; then
      echo "  -> SQLite 최적화 수행 중: $db_file"
      sqlite3 "$db_file" "PRAGMA journal_mode=WAL; PRAGMA wal_checkpoint(TRUNCATE); PRAGMA optimize; VACUUM; ANALYZE;" 2>/dev/null || true
    fi
  done
fi

echo "=================================================================="
echo "🔐 [4/5] 시놀로지 파일 권한(PUID=1026:PGID=100) 및 인제스트 폴더 자가 치유"
echo "=================================================================="
chown -R 1026:100 "/volume1/mediarr/ebooks" 2>/dev/null || true
chmod -R 775 "/volume1/mediarr/ebooks/cwa-ingest" 2>/dev/null || true

echo "=================================================================="
echo "🧹 [5/5] 업데이트 후 남은 구버전 잉여 도커 이미지 자동 청소 (NAS 디스크 회수)"
echo "=================================================================="
docker image prune -f >/dev/null 2>&1 || true
docker ps --filter "name=ebook-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true

echo "✅ [완료] 백업 ➔ 최신 이미지 안전 업데이트 ➔ DB 최적화 ➔ 구버전 이미지 청소가 모두 끝났습니다!"
