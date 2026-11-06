"""Ultimate eBook, Manga, Webtoon & Audiobook Stack Catalog, Organic Pipelines & Root-Cause Diagnosis (v1.3.0)."""

from typing import Any, Dict, List

DIAGNOSIS_REPORT: List[Dict[str, Any]] = [
    {
        "id": "legacy-db-mount-preservation",
        "severity": "CRITICAL",
        "severity_label": "기존 서재 DB 100% 무손실 보존",
        "service": "Komga · Kavita · Audiobookshelf · Calibre",
        "title": "기존 SQLite DB에 등록된 서재 경로(/data, /manga, /audiobooks) 및 '캘리버 서재' 100% 무손실 승계",
        "cause": (
            "실제 운영 중인 SQLite DB를 전수 분석한 결과, Komga는 `file:/data/`, Kavita는 `/manga`, Audiobookshelf는 `/audiobooks`를 "
            "기존 서재 루트로 참조하고 있었습니다. 만약 이 마운트 경로를 임의로 변경하면 기존에 등록된 수백 권의 만화·소설(`호빗`, `삼체`, `토지`, `듄`, `해리포터` 등)과 "
            "독서 진행률이 '파일 없음(Unavailable)' 상태가 됩니다."
        ),
        "before_snippet": (
            "# 기존 서재 경로를 바꾸면 DB 내 책 목록이 깨짐\n"
            "# 또한 /volume1/docker/calibre/캘리버 서재가 분리되어 있었음"
        ),
        "after_snippet": (
            "# 1) 기존 마운트(/data, /manga, /audiobooks) 100% 원형 유지!\n"
            "# 2) 신규 통합 마운트(/ebooks, /calibre-library) 추가 및 REST API 자동 등록!\n"
            "# 3) 기존 '캘리버 서재'(metadata.db)를 /calibre-library 로 자동 무손실 복제!"
        ),
        "solution": (
            "기존 컨테이너 내부 경로(`/data`, `/manga`, `/audiobooks`)를 100% 그대로 유지해 기존 서재를 완벽히 보호하면서, "
            "`ebook-control-center`의 `auto_wirer.py`가 REST API로 신규 통합 서재(`/ebooks/*`, `/calibre-library`)를 자동 추가합니다."
        ),
    },
    {
        "id": "abs-nested-volume",
        "severity": "CRITICAL",
        "severity_label": "치명적 중첩 마운트 해결",
        "service": "Audiobookshelf",
        "title": "Audiobookshelf 중첩(Nested) 볼륨 마운트로 인한 백업 폭발 및 DB 손상 위험 완치",
        "cause": (
            "기존 compose.yaml에서 상위 폴더 자체인 `/volume1/docker/audiobookshelf:/config:rw`를 마운트하면서, "
            "동시에 그 하위 폴더인 `/volume1/docker/audiobookshelf/audiobooks`와 `/metadata`를 중복 마운트했습니다. "
            "이로 인해 Audiobookshelf가 `/config` 백업 시 수십 GB의 오디오북/전자책까지 설정 파일로 오인하여 디스크 병목을 유발합니다."
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
            "  - /volume1/docker/audiobookshelf/audiobooks:/audiobooks:rw\n"
            "  - /volume1/mediarr/ebooks:/ebooks:rw\n"
            "  - /volume1/mediarr/ebooks/calibre-library:/calibre-library:rw"
        ),
        "solution": (
            "`/config` 경로를 `/volume1/docker/audiobookshelf/config`로 완전히 분리하고, 통합 관제 센터(`ebook-control-center`)가 "
            "기존 상위 폴더에 있던 `absdatabase.sqlite`와 `migrations`만 안전하게 `config/` 하위로 무손실 이관합니다."
        ),
    },
    {
        "id": "mediarr-hardlink-and-port-harmony",
        "severity": "CRITICAL",
        "severity_label": "Mediarr-Stack 완벽 공존 & 0.1초 하드링크",
        "service": "Readarr ↔ Mediarr (Prowlarr · qBittorrent)",
        "title": "`mediarr-stack`과 포트 충돌 제로화(:8586, :8192) 및 `/volume1/mediarr` 단일 볼륨 0.1초 하드링크 통합",
        "cause": (
            "시놀로지 NAS에서 이미 가동 중인 `mediarr-stack`이 `8585`(관제 센터)와 `8191`(FlareSolverr) 포트를 사용 중이며, "
            "토렌트 다운로더(`qBittorrent`)는 `/volume1/mediarr:/data` 볼륨에서 동작합니다. 도서 스택이 별도 볼륨(`/volume1/data`)이나 "
            "중복 포트(`8191`)를 쓰면 포트 충돌 에러가 나거나 하드링크가 작동하지 않습니다."
        ),
        "before_snippet": (
            "# 포트 8191 충돌 (mediarr-gluetun 이미 사용 중)\n"
            "# /volume1/data 미존재로 하드링크 불가"
        ),
        "after_snippet": (
            "ebook-control-center: 8586:8500 (mediarr 8585와 나란히 공존)\n"
            "ebook-flaresolverr: 8192:8191 (내부망은 flaresolverr:8191 유지)\n"
            "통합 볼륨: /volume1/mediarr:/data & /volume1/mediarr/ebooks:/ebooks"
        ),
        "solution": (
            "`mediarr-stack`과 동일한 `/volume1/mediarr` 볼륨을 공유하여 qBittorrent가 받은 도서·오디오북 토렌트를 Readarr가 "
            "0.1초 하드링크(추가 용량 0바이트)로 서재에 즉시 연결하고, Prowlarr(:9696)·qBittorrent(:8181)와 자동 배선됩니다."
        ),
    },
    {
        "id": "kavita-abs-permissions",
        "severity": "HIGH",
        "severity_label": "시놀로지 권한 충돌 해결",
        "service": "Kavita & Audiobookshelf & CWA",
        "title": "전 컨테이너 시놀로지 표준 PUID(1026)/PGID(100) 권한 통일 및 자동 자가 치유",
        "cause": (
            "기존 compose.yaml에서 Kavita와 Audiobookshelf에 `PUID=1026`/`PGID=100` 설정이 빠져 있어 `root:root` 권한으로 "
            "DB와 캐시가 생성되었고, DSM File Station이나 타 컨테이너에서 접근할 때 Permission Denied(`EACCES`)를 유발했습니다."
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
            "    PUID: 1026\n"
            "    PGID: 100\n"
            "audiobookshelf:\n"
            "  user: \"1026:100\""
        ),
        "solution": (
            "11개 전 컨테이너에 `1026:100` 권한을 부여하고, `ebook-control-center`가 부팅 및 주기적 점검마다 `root` 소유 파일을 "
            "`1026:100 (775/664)`으로 자동 복구합니다."
        ),
    },
    {
        "id": "zero-touch-auto-wirer",
        "severity": "HIGH",
        "severity_label": "Zero-Touch REST API 자동 배선",
        "service": "Auto-Wirer Engine (auto_wirer.py)",
        "title": "수동 초기 설정이 필요 없는 전 서비스 REST API · SQLite · 확장 리포지토리 Zero-Touch 자동 배선",
        "cause": (
            "컨테이너만 띄워놓으면 사용자가 일일이 Komga, Kavita, Audiobookshelf, CWA, Suwayomi, Readarr에 접속해 "
            "폴더 경로를 등록하고 확장 프로그램 주소(Keiyoushi)와 다운로드 클라이언트를 수동 입력해야 하는 불편함이 있었습니다."
        ),
        "before_snippet": (
            "# 각 웹 UI에 일일이 접속해 서재 폴더·API 키·확장 리포지토리 수동 등록 필요"
        ),
        "after_snippet": (
            "# auto_wirer.py 가 부팅 직후부터 REST API & DB를 자동 배선:\n"
            "# Komga·Kavita·ABS 신규 통합 서재 자동 생성 + CWA DB 직결 +\n"
            "# Suwayomi Keiyoushi 리포지토리 주입 + Readarr↔Prowlarr↔qBittorrent 자동 연동"
        ),
        "solution": (
            "`mediarr-stack`과 동일한 수준의 `auto_wirer.py` 엔진을 탑재하여, 총괄 디렉터님께서 손 하나 까딱하지 않으셔도 "
            "모든 서재 폴더, API 키, 토렌트 카테고리, 만화 확장 리포지토리가 100% 자동으로 연결됩니다."
        ),
    },
    {
        "id": "komf-race-and-kaml",
        "severity": "HIGH",
        "severity_label": "부팅 순서 & 한국어 메타데이터 완비",
        "service": "Komf ↔ Komga / Kavita",
        "title": "Komga·Kavita `service_healthy` 부팅 대기 및 Kaml 파서 호환 한국어(`ko`) 메타데이터 자동 주입",
        "cause": (
            "Komga와 Kavita가 완전히 부팅되기 전에 Komf가 먼저 접속을 시도하면 연결 오류가 발생하며, "
            "기존 Watchtower와 연동할 때도 컨테이너 기동 순서가 보장되어야 합니다."
        ),
        "before_snippet": (
            "depends_on:\n"
            "  - komga\n"
            "  - kavita\n"
            "# healthcheck 및 Watchtower depends-on 라벨 부재"
        ),
        "after_snippet": (
            "depends_on:\n"
            "  komga: { condition: service_healthy }\n"
            "  kavita: { condition: service_healthy }\n"
            "labels:\n"
            "  com.centurylinklabs.watchtower.enable: \"true\"\n"
            "  com.centurylinklabs.watchtower.depends-on: \"ebook-komga,ebook-kavita\""
        ),
        "solution": (
            "3중 폴백 헬스체크와 Watchtower 종속성 라벨을 전 컨테이너에 적용하고, Komf가 한국어(`ko`) 제목·줄거리·표지를 "
            "최우선으로 가져오도록 `application.yml`을 자동 프로비저닝합니다."
        ),
    },
]


ORGANIC_PIPELINES: List[Dict[str, Any]] = [
    {
        "id": "pipeline-ebook",
        "title": "파이프라인 1: 웹 도서 원클릭 검색 ➔ 자동 EPUB/KEPUB 변환 ➔ 4대 뷰어 동시 즉시 열람",
        "flow": "FlareSolverr(:8192) ➔ CWA Book Downloader(:8084) ➔ [/cwa-book-ingest] ➔ Calibre-Web-Automated(:8083) ➔ [/calibre-library] ➔ Kavita(:5471) & Audiobookshelf(:13378) & Komga(:8341)",
        "description": (
            "CWA Book Downloader(Shelfmark) 웹 화면에서 원하는 책(한국어/영어/일본어)을 검색해 다운로드 버튼을 누르면 `/cwa-book-ingest`로 들어갑니다. "
            "Calibre-Web-Automated가 이를 5초 내로 감지해 EPUB으로 자동 변환하고 표지·메타데이터를 입혀 `/calibre-library`에 저장하며, "
            "이 폴더가 이미 자동 등록되어 있는 Kavita, Audiobookshelf, Komga 서재에 파일 복사 없이 즉시 나타납니다."
        ),
    },
    {
        "id": "pipeline-manga",
        "title": "파이프라인 2: 연재 만화·웹툰 신규 회차 자동 수집 ➔ CBZ 압축 저장 ➔ 한국어 메타데이터 자동 주입",
        "flow": "FlareSolverr(:8192) + Keiyoushi 확장 ➔ Suwayomi(:4567) ➔ [/ebooks/manga (*.cbz)] ➔ Komga(:8341) & Kavita(:5471) ➔ Komf(:8085)",
        "description": (
            "Suwayomi에 Keiyoushi 공식 만화·웹툰 확장 리포지토리와 CBZ 자동 압축(`downloadAsCbz=true`, `downloadsPath=/ebooks/manga`)이 사전 주입되어 있어, "
            "새 회차가 올라오면 자동으로 `.cbz` 파일로 `/ebooks/manga`에 저장됩니다. Komga와 Kavita가 이를 스캔하는 즉시 Komf의 `eventListener`가 작동해 한국어 제목·줄거리·작가·표지를 입힙니다."
        ),
    },
    {
        "id": "pipeline-torrent",
        "title": "파이프라인 3: Mediarr-Stack 연동 신간 토렌트 수집 ➔ 0.1초 하드링크 서재 등록",
        "flow": "Mediarr Prowlarr(:9696) & qBittorrent(:8181, /data/torrents/books) ➔ Readarr(:8787) ➔ [/data/ebooks/{books,audiobooks}] ➔ Audiobookshelf(:13378) & Kavita(:5471)",
        "description": (
            "`auto_wirer.py`가 Readarr(:8787)를 `mediarr-stack`의 Prowlarr(:9696) 및 qBittorrent(:8181)와 자동으로 연결합니다. "
            "상위 `/volume1/mediarr:/data` 단일 볼륨을 공유하므로 대용량 오디오북이나 전자책 세트를 복사 시간 0.1초, 추가 디스크 소모 0바이트(하드링크)로 서재에 즉시 연결합니다."
        ),
    },
    {
        "id": "pipeline-control",
        "title": "파이프라인 4: 통합 관제 센터(ebook-control-center) Zero-Touch API 자동 배선 & 24h SQLite WAL 닥터",
        "flow": "ebook-control-center(:8586, kimmingil/ebook-stack:latest) ➔ Komga · Kavita · ABS · CWA · Suwayomi · Readarr 실시간 REST API 자동 배선 & 24h DB 최적화",
        "description": (
            "`ebook-control-center(:8586)`가 구동 즉시 기존 서재(`/data`, `/manga`, `/audiobooks`, `캘리버 서재`)를 100% 무손실 보존하면서 "
            "신규 통합 서재를 각 앱의 REST API로 자동 등록하고, 24시간마다 SQLite 무잠금 WAL 체크포인트(`VACUUM`)와 설정 백업을 수행합니다."
        ),
    },
]


EBOOK_SERVICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "ebook-control-center",
        "name": "eBook Control Center (통합 관제·Auto-Wirer 엔진)",
        "container_name": "ebook-control-center",
        "hostname": "ebook-control-center",
        "category": "control",
        "essential": True,
        "default_enabled": True,
        "image": "kimmingil/ebook-stack:latest",
        "port": 8586,
        "internal_port": 8500,
        "webui_port": 8586,
        "webui_path": "",
        "description": "본 프로젝트의 전용 도커 이미지로 구동되는 통합 컨트롤 센터(:8586). 부팅 시 폴더 생성·Audiobookshelf DB 분리·기존 캘리버 서재 무손실 이관을 수행하고, Zero-Touch Auto-Wirer가 Komga·Kavita·ABS·CWA·Suwayomi·Readarr·Prowlarr를 REST API로 자동 배선합니다.",
        "role_badge": "통합 관제 · Zero-Touch 자동 배선 · DB 닥터",
        "config_dir": None,
        "tuning_badge": "REST API Auto-Wirer + 24h WAL Doctor",
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
        "description": "만화·웹툰·단행본(CBZ/CBR/PDF/EPUB) 메인 서버. 기존 서재(/data: 호빗·삼체·토지·원피스·해리포터 등)를 100% 보존하면서 신규 통합 서재(/ebooks/manga, /ebooks/comics, /calibre-library)가 REST API로 자동 등록됩니다.",
        "role_badge": "만화·웹툰·단행본 메인 서버",
        "config_dir": "komga",
        "tuning_badge": "기존 서재 100% 승계 + G1GC 3GB 최적화",
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
        "description": "라이트노벨(EPUB)·소설·만화 초고속 하이브리드 웹 리더. 기존 서재(/manga) 보존과 함께 Manga & Webtoon, Light Novels, Books & Calibre 서재가 REST API로 자동 생성됩니다.",
        "role_badge": "라이트노벨·EPUB·만화 하이브리드 서버",
        "config_dir": "kavita",
        "tuning_badge": "기존 서재 보존 + 3종 신규 서재 자동 배선",
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
        "internal_port": 13378,
        "webui_port": 13378,
        "webui_path": "",
        "description": "오디오북(M4B/MP3/FLAC), 팟캐스트 자동 구독·다운로드, 전자책(EPUB) 통합 스트리밍 서버. 중첩 볼륨 버그를 완치하고 기존 서재(/audiobooks)와 신규 오디오북·전자책·팟캐스트 서재를 모두 자동 연결합니다.",
        "role_badge": "오디오북·팟캐스트·소설 스트리밍",
        "config_dir": "audiobookshelf",
        "tuning_badge": "중첩 볼륨 분리 완료 + REST API 서재 배선",
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
        "description": "Komga와 Kavita 양쪽에 동시에 연결되어 만화·웹툰·라이트노벨의 한국어 제목, 줄거리, 작가, 장르 태그, 고화질 표지를 AniList·MangaUpdates·Bangumi 등에서 자동으로 수집해 입혀주는 엔진입니다.",
        "role_badge": "Komga·Kavita 한국어 메타데이터 자동화",
        "config_dir": "komf",
        "tuning_badge": "ShenandoahGC 512MB + 한국어(ko) 최우선",
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
        "description": "기존 '/volume1/docker/calibre/캘리버 서재'를 무손실 승계하며, /cwa-book-ingest 폴더에 들어온 모든 책을 자동으로 EPUB/KEPUB 변환 후 /calibre-library 에 등록하여 Kavita·ABS·Komga·Kobo·Kindle과 즉시 공유합니다.",
        "role_badge": "전자책 자동 변환 & Kobo/Kindle 서버",
        "config_dir": "calibre-web-automated",
        "tuning_badge": "기존 캘리버 서재 자동 이관 + Auto-Ingest",
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
        "description": "웹에서 원하는 도서 제목·저자·ISBN(한국어/영어/일본어)을 검색해 다운로드 버튼만 누르면 /cwa-book-ingest 폴더로 자동 투입하여 Calibre-Web-Automated, Kavita, Audiobookshelf, Komga에 10초 내로 자동 등록시키는 포털입니다.",
        "role_badge": "원클릭 도서 검색·자동 다운로드 포털",
        "config_dir": "cwa-book-downloader",
        "tuning_badge": "Shelfmark 공식 이미지 + CWA 직결",
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
        "description": "Mihon(구 Tachiyomi) 기반 연재 만화·웹툰 자동 수집 서버. Keiyoushi 공식 확장 리포지토리와 CBZ 자동 압축(/ebooks/manga)이 사전 설정되어 새 회차를 자동으로 Komga·Kavita 공유 서재에 꽂아줍니다.",
        "role_badge": "웹툰·만화 신규 회차 자동 수집 서버",
        "config_dir": "suwayomi",
        "tuning_badge": "Keiyoushi 리포지토리 + CBZ 자동 저장",
    },
    {
        "id": "readarr",
        "name": "Readarr",
        "container_name": "ebook-readarr",
        "hostname": "readarr",
        "category": "automation",
        "essential": False,
        "default_enabled": True,
        "image": "lscr.io/linuxserver/readarr:0.4.18-develop",
        "port": 8787,
        "internal_port": 8787,
        "webui_port": 8787,
        "webui_path": "",
        "description": "Mediarr-Stack의 Prowlarr(:9696) 및 qBittorrent(:8181, /volume1/mediarr)와 자동 연동하여 신간 전자책·오디오북 토렌트를 수집하고 /data/ebooks 로 0.1초 하드링크 정리하는 매니저입니다.",
        "role_badge": "*Arr 전자책·오디오북 자동 수집",
        "config_dir": "readarr",
        "tuning_badge": "Prowlarr·qBittorrent 자동 배선 + 하드링크",
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
        "description": "스캔된 PDF 전공서적·논문·매거진을 위한 올인원 웹 PDF 가공 스튜디오. 한국어(ko_KR)+영어 광학문자인식(OCR), 양면 스캔 분할, 여백 제거, EPUB 변환을 지원합니다.",
        "role_badge": "스캔북 한국어 OCR & PDF 스튜디오",
        "config_dir": "stirling-pdf",
        "tuning_badge": "한국어(ko_KR) OCR + 전자책 변환",
    },
    {
        "id": "flaresolverr",
        "name": "FlareSolverr (eBook 전용 프록시)",
        "container_name": "ebook-flaresolverr",
        "hostname": "flaresolverr",
        "category": "utility",
        "essential": False,
        "default_enabled": True,
        "image": "ghcr.io/flaresolverr/flaresolverr:latest",
        "port": 8192,
        "internal_port": 8191,
        "webui_port": 8192,
        "webui_path": "",
        "description": "Suwayomi와 CWA-Book-Downloader가 외부 도서·웹툰 사이트에 접근할 때 발생하는 Cloudflare 보안 검증을 백그라운드에서 자동 우회합니다. (호스트 8192 포트로 mediarr 8191과 충돌 제로)",
        "role_badge": "Cloudflare 자동 우회 프록시",
        "config_dir": "flaresolverr",
        "tuning_badge": "호스트 :8192 / 내부 flaresolverr:8191",
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
                "tip": "Kavita의 내장 EPUB 리더는 웹폰트, 줄간격, 여백, 다크모드 설정이 현존 최고 수준이라 별도 앱 없이도 완벽합니다.",
            },
            {
                "device": "이북 리더기 (Kobo / Kindle / 크레마 / 오닉스)",
                "apps": "Kobo 무선 동기화 (CWA) / Send-to-Kindle / KOReader (OPDS)",
                "connection": "Calibre-Web-Automated Kobo Sync 토큰 또는 OPDS 주소 등록",
                "url_template": "http://{nas_ip}:{cwa_port}/opds",
                "tip": "Calibre-Web-Automated는 책을 넣는 즉시 Kobo 전용 포맷(KEPUB)으로 자동 변환하여 Kobo 리더기에서 무선으로 책이 들어옵니다.",
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
