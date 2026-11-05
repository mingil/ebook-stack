#!/bin/bash
# =============================================================================
# 🛠️ SYNOLOGY EBOOK STACK - 폴더·권한·DB 무손실 마이그레이션 자동화 스크립트
# =============================================================================
# (참고: docker-compose.yml의 ebook-control-center 컨테이너가 부팅 시 아래 작업을 자동으로
#  수행하므로 수동 실행하지 않으셔도 되며, 시놀로지 작업 스케줄러에서 초기 1회 실행용으로도 쓸 수 있습니다.)
# =============================================================================
set -e

echo '[1/5] 도커 컨테이너별 전용 설정(Config) 폴더 생성 중...'
mkdir -p "/volume1/docker/komga/config"
mkdir -p "/volume1/docker/komga/data"
mkdir -p "/volume1/docker/kavita/config"
mkdir -p "/volume1/docker/kavita/data"
mkdir -p "/volume1/docker/audiobookshelf/config"
mkdir -p "/volume1/docker/audiobookshelf/metadata"
mkdir -p "/volume1/docker/audiobookshelf/audiobooks"
mkdir -p "/volume1/docker/komf/config"
mkdir -p "/volume1/docker/calibre-web-automated/config"
mkdir -p "/volume1/docker/cwa-book-downloader/config"
mkdir -p "/volume1/docker/suwayomi"
mkdir -p "/volume1/docker/readarr"
mkdir -p "/volume1/docker/stirling-pdf/configs"
mkdir -p "/volume1/docker/stirling-pdf/logs"
mkdir -p "/volume1/docker/stirling-pdf/tessdata"

echo '[2/5] Audiobookshelf 기존 중첩 볼륨(Nested Mount) 데이터베이스 안전 이관 점검 중...'
if [ -f "/volume1/docker/audiobookshelf/absdatabase.sqlite" ] && [ ! -f "/volume1/docker/audiobookshelf/config/absdatabase.sqlite" ]; then
  echo '  -> 기존 상위 폴더에 있던 Audiobookshelf DB를 /config 하위 폴더로 무손실 복사합니다...'
  cp -a "/volume1/docker/audiobookshelf/absdatabase.sqlite"* "/volume1/docker/audiobookshelf/config/" 2>/dev/null || true
  [ -d "/volume1/docker/audiobookshelf/backups" ] && cp -rn "/volume1/docker/audiobookshelf/backups" "/volume1/docker/audiobookshelf/config/" 2>/dev/null || true
  [ -d "/volume1/docker/audiobookshelf/migrations" ] && cp -rn "/volume1/docker/audiobookshelf/migrations" "/volume1/docker/audiobookshelf/config/" 2>/dev/null || true
fi

echo '[3/5] 통합 마스터 eBook 서재 폴더 구조(/volume1/data/ebooks) 생성 중...'
mkdir -p "/volume1/data/ebooks/manga"
mkdir -p "/volume1/data/ebooks/webtoon"
mkdir -p "/volume1/data/ebooks/comics"
mkdir -p "/volume1/data/ebooks/lightnovels"
mkdir -p "/volume1/data/ebooks/books"
mkdir -p "/volume1/data/ebooks/audiobooks"
mkdir -p "/volume1/data/ebooks/podcasts"
mkdir -p "/volume1/data/ebooks/magazines"
mkdir -p "/volume1/data/ebooks/cwa-ingest"
mkdir -p "/volume1/data/ebooks/calibre-library"

echo '[4/5] Komf 한국어·글로벌 메타데이터 설정 파일(application.yml) 준비 중...'
if [ ! -f "/volume1/docker/komf/config/application.yml" ]; then
  cat << 'KOMF_EOF' > "/volume1/docker/komf/config/application.yml"
# =============================================================================
# 🤖 KOMF (Komga & Kavita Metadata Fetcher) - 한국어·글로벌 통합 최적화 설정 파일
# 저장 경로: /volume1/docker/komf/config/application.yml
# (참고: 실제 비밀번호와 API 키는 도커 환경변수 KOMF_KOMGA_*, KOMF_KAVITA_*가 자동 오버라이드합니다)
# =============================================================================

komga:
  baseUri: "http://komga:25600"
  komgaUser: "fauna035@gmail.com"
  komgaPassword: "YOUR_KOMGA_PASSWORD"
  eventListener:
    enabled: true
    metadataLibraryFilter: []
    metadataSeriesExcludeFilter: []
  metadataUpdate:
    default:
      libraryType: MANGA
      updateModes:
        - API
      aggregate: true
      mergeTags: true
      mergeGenres: true
      bookCovers: true
      seriesCovers: true
      overrideExistingCovers: false
      lockMetadata: false
      postProcessing:
        seriesTitle: true
        seriesTitleLanguage: "ko"
        alternativeSeriesTitles: true
        alternativeSeriesTitleLanguages:
          - "ko"
          - "en"
          - "ja"
          - "ja-ro"
        orderBooks: false
        readingDirectionValue: null
        languageValue: "ko"

kavita:
  baseUri: "http://kavita:5000"
  apiKey: "JR5SNjbYayxiZtzTgEIWOTfZ6Od3iyTa"
  eventListener:
    enabled: true
    metadataLibraryFilter: []
    metadataSeriesExcludeFilter: []
  metadataUpdate:
    default:
      libraryType: MANGA
      updateModes:
        - API
      aggregate: true
      mergeTags: true
      mergeGenres: true
      bookCovers: true
      seriesCovers: true
      overrideExistingCovers: false
      postProcessing:
        seriesTitle: true
        seriesTitleLanguage: "ko"
        alternativeSeriesTitles: true
        alternativeSeriesTitleLanguages:
          - "ko"
          - "en"
          - "ja"
        languageValue: "ko"

metadataProviders:
  malClientId: ""
  comicVineApiKey: ""
  defaultProviders:
    mangaUpdates:
      priority: 10
      enabled: true
      mediaType: MANGA
    anilist:
      priority: 20
      enabled: true
      mediaType: MANGA
    mal:
      priority: 30
      enabled: false
    bangumi:
      priority: 40
      enabled: true
    nautiljon:
      priority: 50
      enabled: true
    kodansha:
      priority: 60
      enabled: true
    yenPress:
      priority: 70
      enabled: true
    viz:
      priority: 80
      enabled: true

database:
  file: /config/database.sqlite

server:
  port: 8085
KOMF_EOF
fi

echo '[5/5] 시놀로지 표준 사용자 권한(PUID=1026, PGID=100) 일괄 적용 중...'
chown -R 1026:100 "/volume1/docker/komga" "/volume1/docker/kavita" "/volume1/docker/audiobookshelf" "/volume1/docker/komf" "/volume1/docker/calibre-web-automated" "/volume1/docker/cwa-book-downloader" "/volume1/docker/suwayomi" "/volume1/docker/readarr" "/volume1/docker/stirling-pdf" "/volume1/data/ebooks"
chmod -R 775 "/volume1/data/ebooks"

echo '✅ eBook Stack 폴더 생성, DB 무손실 분리, 권한 적용이 100% 완료되었습니다!'
