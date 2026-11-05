"""Ultimate eBook, Manga, Webtoon & Audiobook Stack Catalog, Organic Pipelines & Root-Cause Diagnosis."""

from typing import Any, Dict, List

DIAGNOSIS_REPORT: List[Dict[str, Any]] = [
    {
        "id": "abs-nested-volume",
        "severity": "CRITICAL",
        "severity_label": "치명적 구조 결함 해결",
        "service": "Audiobookshelf",
        "title": "Audiobookshelf 중첩(Nested) 볼륨 마운트로 인한 백업 폭발 및 DB 손상 위험",
        "cause": (
            "기존 compose.yaml에서 상위 폴더 자체인 `/volume1/docker/audiobookshelf:/config:rw`를 마운트하면서, "
            "동시에 그 하위 폴더인 `/volume1/docker/audiobookshelf/audiobooks`와 `/metadata`를 중복 마운트했습니다. "
            "이로 인해 Audiobookshelf가 `/config` 폴더를 스캔하거나 자동 백업할 때 수십~수백 GB의 오디오북과 메타데이터까지 "
            "설정 파일로 오인하여 디스크 I/O 병목 및 백업 실패를 유발합니다."
        ),
        "before_snippet": (
            "volumes:\n"
            "  - /volume1/docker/audiobookshelf:/config:rw\n"
            "  - /volume1/docker/audiobookshelf/audiobooks:/audiobooks:rw\n"
            "  - /volume1/docker/audiobookshelf/metadata:/metadata:rw"
        ),
        "after_snippet": (
            "volumes:\n"
            "  - /volume1/docker/audiobookshelf/config:/config:rw\n"
            "  - /volume1/docker/audiobookshelf/metadata:/metadata:rw\n"
            "  - /volume1/data/ebooks/audiobooks:/audiobooks:rw\n"
            "  - /volume1/data/ebooks/podcasts:/podcasts:rw\n"
            "  - /volume1/data/ebooks/calibre-library:/calibre-library:rw\n"
            "  - /volume1/docker/audiobookshelf/audiobooks:/legacy-audiobooks:rw"
        ),
        "solution": (
            "`/config` 경로를 `/volume1/docker/audiobookshelf/config`로 완전히 분리하고, 통합 관리 컨테이너(`ebook-control-center`)와 "
            "초기화 스크립트가 기존 상위 폴더에 있던 `absdatabase.sqlite` 등 DB 파일만 안전하게 `config/` 하위로 자동 무손실 이관합니다."
        ),
    },
    {
        "id": "kavita-abs-permissions",
        "severity": "CRITICAL",
        "severity_label": "시놀로지 권한 충돌 해결",
        "service": "Kavita & Audiobookshelf",
        "title": "Kavita 및 Audiobookshelf 미완성 설정 및 시놀로지 PUID(1026)/PGID(100) 권한 누락",
        "cause": (
            "기존 compose.yaml 주석에 적혀 있듯 Kavita와 Audiobookshelf는 뼈대만 작성된 미완성 상태였으며, "
            "`user: 1026:100` 또는 `PUID=1026`/`PGID=100` 설정이 빠져 있었습니다. 이 상태로 운영하면 컨테이너가 `root` 권한으로 "
            "메타데이터·표지·캐시를 생성하여 시놀로지 DSM File Station에서 파일 수정/이동이 거부되거나 서재 스캔 오류가 발생합니다."
        ),
        "before_snippet": (
            "kavita:\n"
            "  environment:\n"
            "    - TZ=${TZ}  # PUID/PGID 누락\n"
            "audiobookshelf:\n"
            "  # user: 1026:100 누락"
        ),
        "after_snippet": (
            "kavita:\n"
            "  environment:\n"
            "    TZ: ${TZ}\n"
            "    PUID: ${PUID}\n"
            "    PGID: ${PGID}\n"
            "audiobookshelf:\n"
            "  user: \"${PUID}:${PGID}\""
        ),
        "solution": (
            "모든 컨테이너에 시놀로지 표준 사용자 권한(`PUID=1026`, `PGID=100`)과 `security_opt: no-new-privileges:true`를 "
            "100% 일관되게 적용했습니다."
        ),
    },
    {
        "id": "komf-race-condition",
        "severity": "HIGH",
        "severity_label": "부팅 순서 & 바이너리 호환 해결",
        "service": "Komf ↔ Komga / Kavita",
        "title": "Komga·Kavita 부팅 완료 전 Komf가 먼저 접속을 시도하여 연결 실패하는 문제",
        "cause": (
            "Komga(Spring Boot)와 Kavita(.NET)는 컨테이너 시작 후 실제 웹 포트가 열리기까지 25~60초가 소요됩니다. "
            "기존 설정은 단순 `depends_on`만 걸려 있고 `healthcheck`가 없어서, Komf가 부팅 직후 아직 열리지 않은 Komga/Kavita API에 "
            "접속을 시도하다가 Connection Refused 에러를 내며 재시작(`on-failure:5`) 횟수를 소진할 위험이 있었습니다."
        ),
        "before_snippet": (
            "depends_on:\n"
            "  - komga\n"
            "  - kavita\n"
            "# komga, kavita에 healthcheck 없음"
        ),
        "after_snippet": (
            "depends_on:\n"
            "  komga:\n"
            "    condition: service_healthy\n"
            "  kavita:\n"
            "    condition: service_healthy"
        ),
        "solution": (
            "모든 컨테이너에 `curl / wget / /dev/tcp` 3중 폴백(Fallback) 헬스체크를 탑재하여 이미지 내 특정 명령어 유무와 상관없이 "
            "100% 정확하게 상태를 판별하고, Komf가 반드시 Komga·Kavita 정상 가동(`service_healthy`) 직후 기동되도록 검증했습니다."
        ),
    },
    {
        "id": "organic-pipeline-linking",
        "severity": "HIGH",
        "severity_label": "컨테이너 간 유기적 파이프라인 완성",
        "service": "CWA · Suwayomi · Komga · Kavita · ABS",
        "title": "다운로더·변환기·뷰어 간 폴더 및 설정 분리로 인해 유기적 자동화가 끊어지는 문제 해결",
        "cause": (
            "기존에는 `/volume1/docker/komga/data`, `/volume1/docker/kavita/data`처럼 각 앱이 자기 폴더만 바라보고 있어서, "
            "새 책을 다운로드하거나 변환해도 다른 앱에서 동시에 열람할 수 없었습니다."
        ),
        "before_snippet": (
            "komga: /volume1/docker/komga/data:/data:rw\n"
            "kavita: /volume1/docker/kavita/data:/manga:rw\n"
            "abs: /volume1/docker/audiobookshelf/audiobooks:/audiobooks:rw"
        ),
        "after_snippet": (
            "# 1) CWA 다운로더 -> /cwa-book-ingest -> CWA 자동 EPUB 변환 -> /calibre-library\n"
            "# 2) Kavita · ABS · Komga 모두 /calibre-library 및 /data 동시 마운트!\n"
            "# 3) Suwayomi JVM 옵션으로 /data/manga 에 CBZ 직접 저장 -> Komga·Kavita 즉시 반영!"
        ),
        "solution": (
            "기존 서재 경로(`/legacy-*`)는 그대로 유지해 기존 책 유실을 막으면서, 신규 마스터 볼륨(`/volume1/data/ebooks`)과 "
            "`/calibre-library`를 전 뷰어가 동시에 공유하도록 연결해 단 1번의 다운로드로 모든 앱에서 즉시 열람되게 구축했습니다."
        ),
    },
    {
        "id": "komf-kaml-syntax",
        "severity": "HIGH",
        "severity_label": "Komf Kaml 파서 문법 완벽 검증",
        "service": "Komf (Metadata Engine)",
        "title": "Komf(Kotlin Kaml 파서) 호환 `application.yml` 및 환경변수 오버라이드 자동화",
        "cause": (
            "Komf(`sndxr/komf`)는 Spring Boot가 아닌 Kotlin Ktor + Kaml 파서를 사용하므로, `application.yml` 내부에 "
            "잘못된 변수 치환 문법을 넣으면 파싱 오류가 발생하거나 한국어 메타데이터 수집이 작동하지 않습니다."
        ),
        "before_snippet": (
            "environment:\n"
            "  - KOMF_KOMGA_BASE_URI=http://komga:25600\n"
            "# application.yml 상세 프로바이더 설정 없음"
        ),
        "after_snippet": (
            "# Kaml 표준 규격 application.yml 자동 생성 + KOMF_KOMGA_* / KOMF_KAVITA_* 환경변수 자동 주입\n"
            "# Komga & Kavita 실시간 이벤트 리스너 + 한국어(ko) 최우선 타이틀 매칭"
        ),
        "solution": (
            "`ebook-control-center` 컨테이너가 부팅 시 Kaml 파서 규격에 100% 부합하는 `/volume1/docker/komf/config/application.yml`을 "
            "자동 생성·검증하여 Komga와 Kavita 양쪽에 한국어 메타데이터와 표지를 자동으로 입혀줍니다."
        ),
    },
    {
        "id": "single-project-management",
        "severity": "OPTIMIZATION",
        "severity_label": "단일 프로젝트 & 통합 컨테이너 관리",
        "service": "ebook-stack 통합 아키텍처",
        "title": "프로젝트 도커 이미지(`kimmingil/ebook-stack:latest`)와 단일 `docker-compose.yml`로 전체 통합 관리",
        "cause": (
            "여러 폴더나 별도 스크립트로 나뉘어 있으면 유지보수가 번거롭습니다. 하나의 프로젝트(`ebook-stack`) 안에서 "
            "도커 이미지와 단일 `docker-compose.yml`만으로 모든 초기화·모니터링·DB 최적화·백업이 이뤄져야 합니다."
        ),
        "before_snippet": "임시 폴더명(ebook-library) + 수동 스크립트 실행 필요",
        "after_snippet": (
            "폴더명: /config/workspace/projects/ebook-stack\n"
            "통합 관제 컨테이너: ebook-control-center (kimmingil/ebook-stack:latest, :8500)\n"
            "네트워크: ebook_net (11개 컨테이너 단일 docker-compose.yml 완벽 통합)"
        ),
        "solution": (
            "`docker-compose.yml`(`compose.yaml`) 하나만 실행하면 `ebook-control-center`가 폴더 초기화·DB 마이그레이션·설정 생성·"
            "정기 SQLite VACUUM 최적화·실시간 상태 점검까지 하나의 프로젝트 안에서 100% 자동으로 관리합니다."
        ),
    },
]


ORGANIC_PIPELINES: List[Dict[str, Any]] = [
    {
        "id": "pipeline-ebook",
        "title": "파이프라인 1: 웹 도서 검색 → 자동 EPUB 변환 → 전 뷰어 동시 열람",
        "flow": "FlareSolverr(:8191) ➔ CWA Book Downloader(:8084) ➔ [/cwa-book-ingest] ➔ Calibre-Web-Automated(:8083) ➔ [/calibre-library] ➔ Kavita(:5471) & Audiobookshelf(:13378) & Komga(:8341)",
        "description": (
            "CWA Book Downloader 웹 화면에서 원하는 책(한국어/영어/일본어)을 검색해 다운로드 버튼을 누르면 `/cwa-book-ingest` 공유 볼륨으로 들어갑니다. "
            "Calibre-Web-Automated가 이를 5초 내로 감지해 EPUB/KEPUB으로 자동 변환하고 표지·메타데이터를 입혀 `/calibre-library`에 저장하며, "
            "이 폴더를 동시에 마운트하고 있는 Kavita, Audiobookshelf, Komga 서재에 파일 복사 없이 즉시 나타납니다."
        ),
    },
    {
        "id": "pipeline-manga",
        "title": "파이프라인 2: 연재 만화·웹툰 자동 수집 → CBZ 패키징 → 메타데이터 자동 매칭",
        "flow": "FlareSolverr(:8191) ➔ Suwayomi(:4567) ➔ [/data/manga (*.cbz)] ➔ Komga(:8341) & Kavita(:5471) ➔ Komf(:8085)",
        "description": (
            "Suwayomi에 JVM 시스템 프로퍼티(`-Dsuwayomi.tachidesk.config.server.downloadAsCbz=true`, `downloadsPath=/data/manga`, `flareSolverrEnabled=true`)가 "
            "사전 주입되어 있어, 연재 만화/웹툰의 새 회차가 올라오면 자동으로 `.cbz` 압축 파일로 `/data/manga`에 저장됩니다. "
            "Komga와 Kavita가 이를 스캔하는 즉시 Komf의 `eventListener`가 작동해 한국어 제목·줄거리·작가·표지를 자동으로 입힙니다."
        ),
    },
    {
        "id": "pipeline-torrent",
        "title": "파이프라인 3: 토렌트/인덱서 신간 자동 수집 → 0.1초 하드링크 서재 등록",
        "flow": "Prowlarr/qBittorrent(/volume1/data/torrents) ➔ Readarr(:8787) ➔ [/volume1/data/ebooks/{books,audiobooks}] ➔ Audiobookshelf(:13378) & Kavita(:5471)",
        "description": (
            "Readarr가 상위 `/volume1/data` 볼륨을 공유하므로, qBittorrent가 다운로드한 대용량 오디오북이나 전자책 세트를 "
            "복사 시간 0.1초, 추가 디스크 용량 소모 0바이트(하드링크)로 `/volume1/data/ebooks/audiobooks` 및 `/books`에 즉시 연결합니다."
        ),
    },
    {
        "id": "pipeline-control",
        "title": "파이프라인 4: 통합 관제 센터(ebook-control-center) 자동 프로비저닝 & DB 닥터",
        "flow": "ebook-control-center(:8500, kimmingil/ebook-stack:latest) ➔ ebook_net 내부망 10대 컨테이너 실시간 헬스체크 · API 스캔 트리거 · SQLite VACUUM · 자동 백업",
        "description": (
            "프로젝트 도커 이미지(`kimmingil/ebook-stack:latest`)가 같은 `docker-compose.yml`과 `ebook_net` 안에서 함께 구동되면서, "
            "부팅 시 폴더/설정 자동 생성과 Audiobookshelf DB 무손실 분리를 수행하고, 웹 UI(:8500)에서 원클릭 DB 최적화(VACUUM), 설정 백업, "
            "Komga/Kavita 서재 스캔 명령을 직접 실행합니다."
        ),
    },
]


EBOOK_SERVICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "ebook-control-center",
        "name": "eBook Control Center (통합 관제·자동화 엔진)",
        "container_name": "ebook-control-center",
        "hostname": "ebook-control-center",
        "category": "control",
        "essential": True,
        "default_enabled": True,
        "image": "kimmingil/ebook-stack:latest",
        "port": 8500,
        "internal_port": 8500,
        "webui_port": 8500,
        "webui_path": "",
        "description": "본 프로젝트의 전용 도커 이미지로 구동되는 통합 컨트롤 센터. 컨테이너 부팅 시 폴더 생성·Audiobookshelf DB 무손실 분리·Komf 및 Suwayomi 설정 자동 생성을 수행하고, 웹 대시보드에서 전체 서버 상태 점검·원클릭 서재 스캔·SQLite DB 최적화(VACUUM)·백업을 관리합니다.",
        "role_badge": "통합 관제 · 자동 초기화 · DB 닥터",
        "config_dir": None,
        "tuning_badge": "Auto-Bootstrap + Live API Control",
    },
    {
        "id": "komga",
        "name": "Komga",
        "container_name": "ebook-komga",
        "hostname": "komga",
        "category": "core_server",
        "essential": True,
        "default_enabled": True,
        "image": "gotson/komga:latest",
        "port": 8341,
        "internal_port": 25600,
        "webui_port": 8341,
        "webui_path": "",
        "description": "만화·웹툰·잡지(CBZ/CBR/PDF/EPUB) 전용 최고급 미디어 서버. 스마트 컬렉션, 읽기 목록, OPDS 스트리밍, Mihon(Tachiyomi)·Panels·Tachimanga 앱 완벽 연동을 지원합니다.",
        "role_badge": "만화·웹툰 메인 서버",
        "config_dir": "komga",
        "tuning_badge": "G1GC + Max 3GB RAM + 3중 폴백 헬스체크",
    },
    {
        "id": "kavita",
        "name": "Kavita",
        "container_name": "ebook-kavita",
        "hostname": "kavita",
        "category": "core_server",
        "essential": True,
        "default_enabled": True,
        "image": "jvmilazz0/kavita:latest",
        "port": 5471,
        "internal_port": 5000,
        "webui_port": 5471,
        "webui_path": "",
        "description": "라이트노벨(EPUB)·일반 소설·단행본·만화를 아우르는 초고속 하이브리드 전자책 리더. Calibre-Web-Automated의 /calibre-library 와 Suwayomi의 /data/manga 를 동시에 공유합니다.",
        "role_badge": "라이트노벨·EPUB·만화 하이브리드 서버",
        "config_dir": "kavita",
        "tuning_badge": "PUID/PGID 1026:100 + .NET GC 최적화",
    },
    {
        "id": "audiobookshelf",
        "name": "Audiobookshelf",
        "container_name": "ebook-audiobookshelf",
        "hostname": "audiobookshelf",
        "category": "core_server",
        "essential": True,
        "default_enabled": True,
        "image": "advplyr/audiobookshelf:latest",
        "port": 13378,
        "internal_port": 80,
        "webui_port": 13378,
        "webui_path": "",
        "description": "오디오북(M4B/MP3/FLAC), 팟캐스트 자동 구독·다운로드, 전자책(EPUB) 통합 스트리밍 서버. 중첩 볼륨 버그를 완벽 해결했으며 /calibre-library 도서를 동시에 열람할 수 있습니다.",
        "role_badge": "오디오북·팟캐스트·소설 스트리밍",
        "config_dir": "audiobookshelf",
        "tuning_badge": "중첩 볼륨 분리 완료 + PUID 1026",
    },
    {
        "id": "komf",
        "name": "Komf (Metadata Engine)",
        "container_name": "ebook-komf",
        "hostname": "komf",
        "category": "metadata",
        "essential": True,
        "default_enabled": True,
        "image": "sndxr/komf:latest",
        "port": 8085,
        "internal_port": 8085,
        "webui_port": 8085,
        "webui_path": "",
        "description": "Komga와 Kavita 양쪽에 동시에 연결되어 만화·웹툰·라이트노벨의 제목, 줄거리, 작가, 장르 태그, 고화질 표지를 AniList·MangaUpdates·Bangumi 등에서 자동으로 수집해 입혀주는 엔진입니다.",
        "role_badge": "Komga·Kavita 메타데이터 자동화",
        "config_dir": "komf",
        "tuning_badge": "ShenandoahGC 512MB + Kaml 완벽 호환",
    },
    {
        "id": "calibre-web-automated",
        "name": "Calibre-Web-Automated (CWA)",
        "container_name": "ebook-calibre-web",
        "hostname": "calibre-web-automated",
        "category": "core_server",
        "essential": True,
        "default_enabled": True,
        "image": "crocodilestick/calibre-web-automated:latest",
        "port": 8083,
        "internal_port": 8083,
        "webui_port": 8083,
        "webui_path": "",
        "description": "무거운 데스크톱 Calibre를 대체하는 차세대 전자책 자동 변환·관리 서버. /cwa-book-ingest 폴더에 들어온 모든 책을 자동으로 EPUB 변환 후 /calibre-library 에 등록하여 Kavita·ABS·Kobo·Kindle과 즉시 공유합니다.",
        "role_badge": "전자책 자동 변환 & Kobo/Kindle 서버",
        "config_dir": "calibre-web-automated",
        "tuning_badge": "Auto-Ingest + Kavita/ABS 서재 공유",
    },
    {
        "id": "cwa-book-downloader",
        "name": "CWA Book Downloader (Shelfmark)",
        "container_name": "ebook-book-downloader",
        "hostname": "cwa-book-downloader",
        "category": "automation",
        "essential": False,
        "default_enabled": True,
        "image": "ghcr.io/calibrain/calibre-web-automated-book-downloader:latest",
        "port": 8084,
        "internal_port": 8084,
        "webui_port": 8084,
        "webui_path": "",
        "description": "웹에서 원하는 도서 제목·저자·ISBN을 검색해 다운로드 버튼만 누르면 /books(/cwa-book-ingest) 폴더로 자동 투입하여 Calibre-Web-Automated, Kavita, Audiobookshelf에 10초 내로 자동 등록시키는 도서 요청 포털입니다.",
        "role_badge": "원클릭 도서 검색·자동 다운로드 포털",
        "config_dir": "cwa-book-downloader",
        "tuning_badge": "Shelfmark v1.6+ 공식 이미지 + CWA 직결",
    },
    {
        "id": "suwayomi",
        "name": "Suwayomi-Server (Tachidesk)",
        "container_name": "ebook-suwayomi",
        "hostname": "suwayomi",
        "category": "automation",
        "essential": False,
        "default_enabled": True,
        "image": "ghcr.io/suwayomi/tachidesk:latest",
        "port": 4567,
        "internal_port": 4567,
        "webui_port": 4567,
        "webui_path": "",
        "description": "Mihon(구 Tachiyomi) 확장 생태계 기반 연재 만화·웹툰 자동 수집 서버. 공식 startup_script.sh 환경변수(DOWNLOAD_AS_CBZ=true, FLARESOLVERR_ENABLED=true)가 사전 적용되어 새 회차를 자동으로 CBZ 압축해 /data/manga(Komga·Kavita 공유 폴더)에 꽂아줍니다.",
        "role_badge": "웹툰·만화 신규 회차 자동 수집 서버",
        "config_dir": "suwayomi",
        "tuning_badge": "CBZ 자동설정 → Komga/Kavita 직결",
    },
    {
        "id": "readarr",
        "name": "Readarr",
        "container_name": "ebook-readarr",
        "hostname": "readarr",
        "category": "automation",
        "essential": False,
        "default_enabled": True,
        "image": "lscr.io/linuxserver/readarr:nightly",
        "port": 8787,
        "internal_port": 8787,
        "webui_port": 8787,
        "webui_path": "",
        "description": "Prowlarr 및 qBittorrent(/volume1/data/torrents)와 연동하여 신간 전자책·오디오북 토렌트를 자동 다운로드하고 /volume1/data/ebooks 로 0.1초 하드링크 정리하는 매니저입니다.",
        "role_badge": "*Arr 전자책·오디오북 자동 수집",
        "config_dir": "readarr",
        "tuning_badge": "/volume1/data 단일 볼륨 하드링크 완비",
    },
    {
        "id": "stirling-pdf",
        "name": "Stirling-PDF",
        "container_name": "ebook-stirling-pdf",
        "hostname": "stirling-pdf",
        "category": "utility",
        "essential": False,
        "default_enabled": True,
        "image": "frooodle/s-pdf:latest",
        "port": 8087,
        "internal_port": 8080,
        "webui_port": 8087,
        "webui_path": "",
        "description": "스캔된 PDF 전공서적·논문·매거진을 위한 올인원 웹 PDF 가공 스튜디오. 한국어(kor)+영어(eng) 광학문자인식(OCR), 양면 스캔 분할, 여백 제거, EPUB 변환을 지원합니다.",
        "role_badge": "스캔북 한국어 OCR & PDF 스튜디오",
        "config_dir": "stirling-pdf",
        "tuning_badge": "한국어(kor) OCR + 전자책 변환",
    },
    {
        "id": "flaresolverr",
        "name": "FlareSolverr",
        "container_name": "ebook-flaresolverr",
        "hostname": "flaresolverr",
        "category": "utility",
        "essential": False,
        "default_enabled": True,
        "image": "ghcr.io/flaresolverr/flaresolverr:latest",
        "port": 8191,
        "internal_port": 8191,
        "webui_port": 8191,
        "webui_path": "",
        "description": "Suwayomi, CWA-Book-Downloader, Readarr가 외부 도서·웹툰 사이트에 접근할 때 발생하는 Cloudflare 보안 검증을 백그라운드에서 자동 통과시켜 줍니다.",
        "role_badge": "Cloudflare 자동 우회 프록시",
        "config_dir": "flaresolverr",
        "tuning_badge": "Suwayomi · CWA 다운로더 자동 연동",
    },
]


CLIENT_APPS_GUIDE: List[Dict[str, Any]] = [
    {
        "category": "만화 · 웹툰 (Komga & Kavita 연동)",
        "icon": "fa-book-open-reader",
        "clients": [
            {
                "device": "iOS / iPadOS (아이폰·아이패드)",
                "apps": "Panels (최고 추천), Paperback, Tachimanga",
                "connection": "OPDS 또는 Komga 전용 API 연동",
                "url_template": "http://{nas_ip}:{komga_port}/opds/v1.2/catalog",
                "tip": "아이패드에서는 Panels 앱에 Komga 서버를 OPDS/API로 등록하면 양면 보기, 세로 스크롤(웹툰), 읽기 진도 동기화가 완벽하게 작동합니다.",
            },
            {
                "device": "Android (갤럭시 탭·스마트폰·오닉스 북스)",
                "apps": "Mihon (구 Tachiyomi), Komga 확장 프로그램",
                "connection": "Mihon 내 Komga / Kavita 확장 설치 후 서버 URL 입력",
                "url_template": "http://{nas_ip}:{komga_port}",
                "tip": "Mihon 앱에서 Komga 확장을 설치하면 NAS의 수만 권 만화를 앱 내장 서재처럼 초고속으로 열람하고 읽기 상태가 양방향 동기화됩니다.",
            },
        ],
    },
    {
        "category": "전자책 · 소설 · 라이트노벨 (Kavita & Calibre-Web-Automated 연동)",
        "icon": "fa-tablet-screen-button",
        "clients": [
            {
                "device": "PC / 태블릿 / 모바일 웹 브라우저",
                "apps": "Kavita 내장 웹 리더 & CWA 내장 웹 리더",
                "connection": "별도 앱 설치 없이 브라우저 직접 접속 (PWA 홈 화면 추가 지원)",
                "url_template": "http://{nas_ip}:{kavita_port}",
                "tip": "Kavita의 내장 EPUB 리더는 나눔명조/리디바탕 웹폰트, 줄간격, 여백, 다크모드 설정이 현존 최고 수준이라 별도 앱 없이도 완벽합니다.",
            },
            {
                "device": "이북 리더기 (Kobo / Kindle / 크레마 / 오닉스)",
                "apps": "Kobo 무선 동기화 (CWA) / Send-to-Kindle / KOReader (OPDS)",
                "connection": "Calibre-Web-Automated Kobo Sync 토큰 또는 OPDS 주소 등록",
                "url_template": "http://{nas_ip}:{cwa_port}/opds",
                "tip": "Calibre-Web-Automated는 책을 넣는 즉시 Kobo 전용 포맷(KEPUB)으로 자동 변환하여 Kobo 리더기에서 상점 동기화만 누르면 무선으로 책이 들어옵니다.",
            },
        ],
    },
    {
        "category": "오디오북 · 팟캐스트 (Audiobookshelf 연동)",
        "icon": "fa-headphones-simple",
        "clients": [
            {
                "device": "iOS (아이폰·애플워치·CarPlay)",
                "apps": "Plappa (CarPlay·오프라인 최고 추천), ShelfPlayer, Audiobookshelf 공식 앱",
                "connection": "Audiobookshelf 서버 주소 및 계정 로그인",
                "url_template": "http://{nas_ip}:{abs_port}",
                "tip": "아이폰에서는 Plappa 또는 ShelfPlayer 앱을 연결하면 애플 카플레이(CarPlay)와 애플워치 연동, 수면 타이머, 초 단위 이어듣기가 완벽히 지원됩니다.",
            },
            {
                "device": "Android (안드로이드 스마트폰·Android Auto)",
                "apps": "Audiobookshelf 공식 앱 (Google Play 스토어)",
                "connection": "Audiobookshelf 서버 주소 및 계정 로그인",
                "url_template": "http://{nas_ip}:{abs_port}",
                "tip": "오디오북과 동일한 책의 EPUB 파일을 같은 폴더에 넣어두면, 차 안에서는 오디오북으로 듣고 집에서는 이북으로 이어 읽는 하이브리드 독서가 가능합니다.",
            },
        ],
    },
]
