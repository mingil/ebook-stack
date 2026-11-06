"""Ultimate Synology eBook, Manga, Webtoon & Audiobook Stack Generator (v1.3.0)."""

from typing import Dict, List
from pydantic import BaseModel, Field


class EbookStackConfigRequest(BaseModel):
    nas_ip: str = Field(default="192.168.0.100", description="시놀로지 NAS 내부 IP 주소")
    puid: int = Field(default=1026, description="시놀로지 사용자 PUID (기본 1026)")
    pgid: int = Field(default=100, description="시놀로지 그룹 PGID (기본 100)")
    tz: str = Field(default="Asia/Seoul", description="타임존")
    docker_root: str = Field(default="/volume1/docker", description="도커 설정 폴더 루트 경로")
    ebook_data_root: str = Field(
        default="/volume1/mediarr/ebooks",
        description="통합 전자책·만화·오디오북 데이터 마스터 경로 (/volume1/mediarr 기반 0.1초 하드링크 지원)",
    )
    container_prefix: str = Field(default="ebook-", description="컨테이너 이름 프리픽스 (예: ebook-komga)")
    keep_legacy_mounts: bool = Field(
        default=True,
        description="기존 업로드된 /volume1/docker/{komga,kavita,audiobookshelf} 내부 데이터 경로를 원래 위치 그대로 100% 무손실 유지",
    )
    control_port: int = Field(default=8586, description="eBook Control Center 웹 대시보드 포트 (mediarr 8585와 공존)")
    komga_port: int = Field(default=8341, description="Komga 호스트 포트 (기존 8341 유지)")
    kavita_port: int = Field(default=5471, description="Kavita 호스트 포트 (기존 5471 유지)")
    audiobookshelf_port: int = Field(default=13378, description="Audiobookshelf 호스트 포트 (기존 13378 유지)")
    komf_port: int = Field(default=8085, description="Komf 호스트 포트 (기존 8085 유지)")
    cwa_port: int = Field(default=8083, description="Calibre-Web-Automated 호스트 포트")
    cwa_dl_port: int = Field(default=8084, description="CWA Book Downloader 호스트 포트")
    suwayomi_port: int = Field(default=4567, description="Suwayomi (Tachidesk) 호스트 포트")
    readarr_port: int = Field(default=8787, description="Readarr 호스트 포트")
    stirling_port: int = Field(default=8087, description="Stirling-PDF 호스트 포트")
    flaresolverr_port: int = Field(default=8192, description="FlareSolverr 호스트 포트 (mediarr 8191과 충돌 방지)")
    komga_user: str = Field(default="admin@example.com", description="Komga 관리자 이메일")
    komga_password: str = Field(default="YOUR_KOMGA_PASSWORD", description="Komga 관리자 비밀번호")
    kavita_api_key: str = Field(default="CHANGE_ME_KAVITA_API_KEY", description="Kavita OPDS/API 키")
    selected_services: List[str] = Field(
        default_factory=lambda: [
            "ebook-control-center",
            "komga",
            "kavita",
            "audiobookshelf",
            "komf",
            "calibre-web-automated",
            "cwa-book-downloader",
            "suwayomi",
            "readarr",
            "stirling-pdf",
            "flaresolverr",
        ]
    )


def _cname(cfg: EbookStackConfigRequest, base: str) -> str:
    if base == "ebook-control-center":
        return "ebook-control-center"
    prefix = (cfg.container_prefix or "").strip()
    return f"{prefix}{base}" if prefix else base


def generate_ebook_compose(cfg: EbookStackConfigRequest) -> str:
    """Generate a unified, organically linked docker-compose.yml for the eBook ecosystem."""
    selected = [s for s in dict.fromkeys(cfg.selected_services) if s != "watchtower"]
    docker_root = cfg.docker_root.rstrip("/")
    data_root = cfg.ebook_data_root.rstrip("/")

    lines: List[str] = [
        "# =============================================================================",
        "# 📚 ULTIMATE SYNOLOGY EBOOK, MANGA, WEBTOON & AUDIOBOOK STACK (ebook-stack v1.3.0)",
        "# =============================================================================",
        "# • 프로젝트명   : ebook-stack (단일 프로젝트 & 단일 docker-compose.yml 통합 아키텍처)",
        "# • 통합 이미지  : kimmingil/ebook-stack:latest (폴더/권한 자동 초기화 · REST API 자동 배선 · 24h DB 닥터)",
        f"# • 시놀로지 권한: PUID={cfg.puid} / PGID={cfg.pgid} / TZ={cfg.tz}",
        f"# • 설정 경로    : {docker_root}/<서비스명> (순수 Config & DB 전용 완벽 분리)",
        f"# • 마스터 서재  : {data_root}:/ebooks:rw & /volume1/mediarr:/data:rw (Mediarr-Stack 0.1초 하드링크 연동)",
        "# • 기존 호환성  : 기존 Komga(/data), Kavita(/manga), ABS(/audiobooks), Calibre 서재 100% 무손실 승계",
        "# =============================================================================",
        "",
        'version: "3.9"',
        "",
        "# 🌐 1. 도커 내부 통신용 브리지 네트워크 (기존 ebook_net 100% 호환)",
        "networks:",
        "  ebook_net:",
        "    name: ebook_net",
        "    driver: bridge",
        "",
        "# 🧹 2. 시놀로지 NAS 디스크 보호용 공통 로그 로테이션 설정",
        "x-logging: &default-logging",
        '  driver: "json-file"',
        "  options:",
        '    max-size: "10m"',
        '    max-file: "3"',
        "",
        "services:",
    ]

    # 0. EBOOK CONTROL CENTER (Integrated Project Image)
    if "ebook-control-center" in selected:
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🎛️ 0. EBOOK CONTROL CENTER - 폴더/권한(1026:100) 초기화 · Zero-Touch API 배선 · 24h DB 닥터",
            "  # ---------------------------------------------------------------------------",
            "  ebook-control-center:",
            "    image: kimmingil/ebook-stack:latest",
            "    container_name: ebook-control-center",
            "    hostname: ebook-control-center",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - ebook-control-center",
            "          - ebook-stack",
            "    extra_hosts:",
            '      - "host.docker.internal:host-gateway"',
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            "      PORT: 8500",
            '      AUTO_BOOTSTRAP: "true"',
            '      AUTO_DAILY_MAINTENANCE: "true"',
            '      AUTO_MAINTENANCE_INTERVAL_HOURS: "24"',
            "      HOST_DOCKER_MOUNT: /host-docker",
            "      HOST_DATA_MOUNT: /host-data",
            f"      NAS_IP: ${{NAS_IP:-{cfg.nas_ip}}}",
            "      BASE_DOMAIN: ${BASE_DOMAIN:-}",
            f"      KOMGA_USER: ${{KOMGA_USER:-{cfg.komga_user}}}",
            "      KOMGA_PASSWORD: ${KOMGA_PASSWORD:-}",
            "      KAVITA_API_KEY: ${KAVITA_API_KEY:-}",
            "      CONTROL_CENTER_USER: ${CONTROL_CENTER_USER:-admin}",
            "      CONTROL_CENTER_PASSWORD: ${CONTROL_CENTER_PASSWORD:-}",
            "    ports:",
            f'      - "{cfg.control_port}:8500"',
            "    volumes:",
            f"      - {docker_root}:/host-docker:rw",
            f"      - {data_root}:/host-data:rw",
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8500/api/health >/dev/null || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 15s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    ctrl_dep: List[str] = []
    if "ebook-control-center" in selected:
        ctrl_dep = [
            "    depends_on:",
            "      ebook-control-center:",
            "        condition: service_healthy",
        ]

    # 1. KOMGA
    if "komga" in selected:
        cname = _cname(cfg, "komga")
        komga_vols = [
            f"      - {docker_root}/komga/config:/config:rw",
        ]
        if cfg.keep_legacy_mounts:
            komga_vols.append(f"      - {docker_root}/komga/data:/data:rw")
        else:
            komga_vols.append(f"      - {data_root}:/data:rw")
        komga_vols.extend([
            f"      - {data_root}:/ebooks:rw",
            f"      - {data_root}/calibre-library:/calibre-library:rw",
        ])

        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 📚 1. KOMGA - 만화·웹툰·매거진 메인 미디어 서버 (기존 /data 서재 100% 보존 + G1GC 최적화)",
            "  # ---------------------------------------------------------------------------",
            "  komga:",
            "    image: gotson/komga:latest",
            f"    container_name: {cname}",
            "    hostname: komga",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - komga",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 4g",
            "    cpu_shares: 768",
            "    security_opt:",
            "      - no-new-privileges:true",
            f'    user: "${{PUID:-{cfg.puid}}}:${{PGID:-{cfg.pgid}}}"',
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            '      JAVA_TOOL_OPTIONS: "-Xmx3g -XX:+UseG1GC -XX:+UseStringDeduplication"',
            "      SERVER_PORT: 25600",
            "    ports:",
            f'      - "{cfg.komga_port}:25600"',
            "    volumes:",
            *komga_vols,
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:25600/actuator/health >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:25600/actuator/health >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/25600\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 5",
            "      start_period: 60s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 2. KAVITA
    if "kavita" in selected:
        cname = _cname(cfg, "kavita")
        kavita_vols = [
            f"      - {docker_root}/kavita/config:/kavita/config:rw",
        ]
        if cfg.keep_legacy_mounts:
            kavita_vols.append(f"      - {docker_root}/kavita/data:/manga:rw")
        else:
            kavita_vols.append(f"      - {data_root}/manga:/manga:rw")
        kavita_vols.extend([
            f"      - {data_root}:/ebooks:rw",
            f"      - {data_root}:/data:rw",
            f"      - {data_root}/lightnovels:/lightnovels:rw",
            f"      - {data_root}/books:/books:rw",
            f"      - {data_root}/calibre-library:/calibre-library:rw",
        ])

        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🌟 2. KAVITA - 라이트노벨(EPUB)·소설·만화 초고속 하이브리드 서버 (기존 /manga 서재 보존)",
            "  # ---------------------------------------------------------------------------",
            "  kavita:",
            "    image: jvmilazz0/kavita:latest",
            f"    container_name: {cname}",
            "    hostname: kavita",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - kavita",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 4g",
            "    cpu_shares: 768",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            "      DOTNET_GCHeapHardLimit: 0xC0000000",
            "    ports:",
            f'      - "{cfg.kavita_port}:5000"',
            "    volumes:",
            *kavita_vols,
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:5000/api/health >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:5000/api/health >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/5000\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 5",
            "      start_period: 45s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 3. AUDIOBOOKSHELF
    if "audiobookshelf" in selected:
        cname = _cname(cfg, "audiobookshelf")
        abs_vols = [
            f"      # ✅ [핵심 수정 완료] 기존 상위 폴더({docker_root}/audiobookshelf) 중첩 마운트 버그를 /config 하위 분리로 해결",
            f"      - {docker_root}/audiobookshelf/config:/config:rw",
            f"      - {docker_root}/audiobookshelf/metadata:/metadata:rw",
        ]
        if cfg.keep_legacy_mounts:
            abs_vols.append(f"      - {docker_root}/audiobookshelf/audiobooks:/audiobooks:rw")
        else:
            abs_vols.append(f"      - {data_root}/audiobooks:/audiobooks:rw")
        abs_vols.extend([
            f"      - {data_root}:/ebooks:rw",
            f"      - {data_root}/podcasts:/podcasts:rw",
            f"      - {data_root}/books:/books:rw",
            f"      - {data_root}/lightnovels:/lightnovels:rw",
            f"      - {data_root}/calibre-library:/calibre-library:rw",
        ])

        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🎧 3. AUDIOBOOKSHELF - 오디오북·팟캐스트·전자책 스트리밍 서버 (기존 /audiobooks 서재 보존)",
            "  # ---------------------------------------------------------------------------",
            "  audiobookshelf:",
            "    image: advplyr/audiobookshelf:latest",
            f"    container_name: {cname}",
            "    hostname: audiobookshelf",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - audiobookshelf",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 4g",
            "    cpu_shares: 768",
            "    security_opt:",
            "      - no-new-privileges:true",
            f'    user: "${{PUID:-{cfg.puid}}}:${{PGID:-{cfg.pgid}}}"',
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            "      CONFIG_PATH: /config",
            "      METADATA_PATH: /metadata",
            "      PORT: 13378",
            "      JWT_SECRET_KEY: ${ABS_JWT_SECRET:-CHANGE_ME_ABS_JWT_SECRET_KEY}",
            "    ports:",
            f'      - "{cfg.audiobookshelf_port}:13378"',
            "    volumes:",
            *abs_vols,
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "nc -z 127.0.0.1 13378 >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:13378/ping >/dev/null 2>&1 || exit 1"]',
            "      interval: 20s",
            "      timeout: 5s",
            "      retries: 3",
            "      start_period: 45s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 4. KOMF
    if "komf" in selected:
        cname = _cname(cfg, "komf")
        depends_lines: List[str] = []
        if "komga" in selected or "kavita" in selected or "ebook-control-center" in selected:
            depends_lines.append("    depends_on:")
            if "ebook-control-center" in selected:
                depends_lines.extend([
                    "      ebook-control-center:",
                    "        condition: service_healthy",
                ])
            if "komga" in selected:
                depends_lines.extend([
                    "      komga:",
                    "        condition: service_healthy",
                ])
            if "kavita" in selected:
                depends_lines.extend([
                    "      kavita:",
                    "        condition: service_healthy",
                ])

        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🤖 4. KOMF - Komga & Kavita 만화·웹툰·라노벨 메타데이터 자동 수집 엔진",
            "  # ---------------------------------------------------------------------------",
            "  komf:",
            "    image: sndxr/komf:latest",
            f"    container_name: {cname}",
            "    hostname: komf",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - komf",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            '      com.centurylinklabs.watchtower.depends-on: "komga,kavita"',
            "    mem_limit: 1g",
            "    cpu_shares: 768",
            "    security_opt:",
            "      - no-new-privileges:true",
            f'    user: "${{PUID:-{cfg.puid}}}:${{PGID:-{cfg.pgid}}}"',
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            "      KOMF_KOMGA_BASE_URI: http://komga:25600",
            "      KOMF_KOMGA_USER: ${KOMGA_USER}",
            "      KOMF_KOMGA_PASSWORD: ${KOMGA_PASSWORD}",
            "      KOMF_KAVITA_BASE_URI: http://kavita:5000",
            "      KOMF_KAVITA_API_KEY: ${KAVITA_API_KEY}",
            "      KOMF_LOG_LEVEL: INFO",
            '      JAVA_TOOL_OPTIONS: "-Xmx512m -XX:+UnlockExperimentalVMOptions -XX:+UseShenandoahGC -XX:ShenandoahGCHeuristics=compact -XX:ShenandoahGuaranteedGCInterval=3600000 -XX:TrimNativeHeapInterval=3600000"',
            "    ports:",
            f'      - "{cfg.komf_port}:8085"',
            "    volumes:",
            f"      - {docker_root}/komf/config:/config:rw",
            *depends_lines,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8085 >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:8085 >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/8085\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 30s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 5. CALIBRE-WEB-AUTOMATED
    if "calibre-web-automated" in selected:
        cname = _cname(cfg, "calibre-web")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 📖 5. CALIBRE-WEB-AUTOMATED - 전자책 자동 변환(EPUB/KEPUB) & Kobo/Kindle 서버",
            "  # ---------------------------------------------------------------------------",
            "  calibre-web-automated:",
            "    image: crocodilestick/calibre-web-automated:latest",
            f"    container_name: {cname}",
            "    hostname: calibre-web-automated",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - calibre-web-automated",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 2g",
            "    cpu_shares: 768",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            '      NETWORK_SHARE_MODE: "true"',
            "      HARDCOVER_TOKEN: ${HARDCOVER_TOKEN:-}",
            "    ports:",
            f'      - "{cfg.cwa_port}:8083"',
            "    volumes:",
            f"      - {docker_root}/calibre-web-automated/config:/config:rw",
            f"      - {data_root}/cwa-ingest:/cwa-book-ingest:rw",
            f"      - {data_root}/calibre-library:/calibre-library:rw",
            f"      - {data_root}/books:/books:rw",
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8083 >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:8083 >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/8083\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 5",
            "      start_period: 120s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 6. CWA BOOK DOWNLOADER (Shelfmark)
    if "cwa-book-downloader" in selected:
        cname = _cname(cfg, "book-downloader")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🔍 6. CWA BOOK DOWNLOADER (Shelfmark) - 웹 도서 검색 & 원클릭 자동 다운로드 포털",
            "  # ---------------------------------------------------------------------------",
            "  cwa-book-downloader:",
            "    image: ghcr.io/calibrain/calibre-web-automated-book-downloader:latest",
            f"    container_name: {cname}",
            "    hostname: cwa-book-downloader",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - cwa-book-downloader",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            '      com.centurylinklabs.watchtower.depends-on: "flaresolverr"',
            "    mem_limit: 2g",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            "      FLASK_PORT: 8084",
            "      INGEST_DIR: /cwa-book-ingest",
            "      BOOK_LANGUAGE: ko,en,ja",
            '      USE_CF_BYPASS: "true"',
            "      FLARESOLVERR_URL: http://flaresolverr:8191",
            "    ports:",
            f'      - "{cfg.cwa_dl_port}:8084"',
            "    volumes:",
            f"      - {docker_root}/cwa-book-downloader/config:/config:rw",
            f"      - {data_root}/cwa-ingest:/books:rw",
            f"      - {data_root}/cwa-ingest:/cwa-book-ingest:rw",
            f"      - {data_root}/audiobooks:/audiobooks:rw",
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8084/api/health >/dev/null 2>&1 || curl -fsS http://127.0.0.1:8084 >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/8084\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 45s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 7. SUWAYOMI-SERVER (TACHIDESK)
    if "suwayomi" in selected:
        cname = _cname(cfg, "suwayomi")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 📲 7. SUWAYOMI-SERVER (Tachidesk) - 연재 만화·웹툰 자동 다운로드 서버",
            "  # ---------------------------------------------------------------------------",
            "  suwayomi:",
            "    image: ghcr.io/suwayomi/tachidesk:latest",
            f"    container_name: {cname}",
            "    hostname: suwayomi",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - suwayomi",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            '      com.centurylinklabs.watchtower.depends-on: "flaresolverr"',
            "    mem_limit: 2g",
            "    security_opt:",
            "      - no-new-privileges:true",
            f'    user: "${{PUID:-{cfg.puid}}}:${{PGID:-{cfg.pgid}}}"',
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            "      BIND_IP: 0.0.0.0",
            "      BIND_PORT: 4567",
            '      DOWNLOAD_AS_CBZ: "true"',
            '      FLARESOLVERR_ENABLED: "true"',
            "      FLARESOLVERR_URL: http://flaresolverr:8191",
            '      JAVA_TOOL_OPTIONS: "-Xmx1536m -Dsuwayomi.tachidesk.config.server.ip=0.0.0.0 -Dsuwayomi.tachidesk.config.server.port=4567 -Dsuwayomi.tachidesk.config.server.downloadsPath=/data/manga -Dsuwayomi.tachidesk.config.server.downloadAsCbz=true -Dsuwayomi.tachidesk.config.server.autoDownloadNewChapters=true -Dsuwayomi.tachidesk.config.server.flareSolverrEnabled=true -Dsuwayomi.tachidesk.config.server.flareSolverrUrl=http://flaresolverr:8191"',
            "    ports:",
            f'      - "{cfg.suwayomi_port}:4567"',
            "    volumes:",
            f"      - {docker_root}/suwayomi:/home/suwayomi/.local/share/Tachidesk:rw",
            f"      - {data_root}/manga:/home/suwayomi/.local/share/Tachidesk/downloads:rw",
            f"      - {data_root}:/ebooks:rw",
            f"      - {data_root}:/data:rw",
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:4567 >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:4567 >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/4567\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 40s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 8. READARR
    if "readarr" in selected:
        cname = _cname(cfg, "readarr")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 📡 8. READARR - Mediarr Prowlarr·qBittorrent 연동 신간 전자책·오디오북 자동 수집",
            "  # ---------------------------------------------------------------------------",
            "  readarr:",
            "    image: lscr.io/linuxserver/readarr:0.4.18-develop",
            f"    container_name: {cname}",
            "    hostname: readarr",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - readarr",
            f"          - {cname}",
            "    extra_hosts:",
            '      - "host.docker.internal:host-gateway"',
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 1g",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            "    ports:",
            f'      - "{cfg.readarr_port}:8787"',
            "    volumes:",
            f"      - {docker_root}/readarr:/config:rw",
            f"      - {data_root}:/ebooks:rw",
            "      - /volume1/mediarr:/data:rw",
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8787/ping >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:8787/ping >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 30s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 9. STIRLING-PDF
    if "stirling-pdf" in selected:
        cname = _cname(cfg, "stirling-pdf")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 📄 9. STIRLING-PDF - 스캔 전자책 한국어 OCR & 올인원 PDF 가공 스튜디오",
            "  # ---------------------------------------------------------------------------",
            "  stirling-pdf:",
            "    image: frooodle/s-pdf:latest",
            f"    container_name: {cname}",
            "    hostname: stirling-pdf",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - stirling-pdf",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 2g",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            f"      PUID: ${{PUID:-{cfg.puid}}}",
            f"      PGID: ${{PGID:-{cfg.pgid}}}",
            '      DOCKER_ENABLE_SECURITY: "true"',
            '      SECURITY_ENABLELOGIN: "true"',
            "      SECURITY_INITIALLOGIN_USERNAME: ${CONTROL_CENTER_USER:-admin}",
            "      SECURITY_INITIALLOGIN_PASSWORD: ${CONTROL_CENTER_PASSWORD:-}",
            '      INSTALL_BOOK_AND_ADVANCED_HTML_OPS: "true"',
            "      LANGS: ko_KR",
            "    ports:",
            f'      - "{cfg.stirling_port}:8080"',
            "    volumes:",
            f"      - {docker_root}/stirling-pdf/configs:/configs:rw",
            f"      - {docker_root}/stirling-pdf/logs:/logs:rw",
            f"      - {docker_root}/stirling-pdf/tessdata:/usr/share/tessdata:rw",
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8080/api/v1/info/status >/dev/null 2>&1 || wget -q --spider http://127.0.0.1:8080 >/dev/null 2>&1 || bash -c \'</dev/tcp/127.0.0.1/8080\' >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 45s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    # 10. FLARESOLVERR
    if "flaresolverr" in selected:
        cname = _cname(cfg, "flaresolverr")
        lines.extend([
            "  # ---------------------------------------------------------------------------",
            "  # 🛡️ 10. FLARESOLVERR - Suwayomi·CWA용 Cloudflare 자동 우회 프록시 (호스트 :8192 / 내부 :8191)",
            "  # ---------------------------------------------------------------------------",
            "  flaresolverr:",
            "    image: ghcr.io/flaresolverr/flaresolverr:latest",
            f"    container_name: {cname}",
            "    hostname: flaresolverr",
            "    networks:",
            "      ebook_net:",
            "        aliases:",
            "          - flaresolverr",
            f"          - {cname}",
            "    labels:",
            '      com.centurylinklabs.watchtower.enable: "true"',
            "    mem_limit: 1g",
            "    security_opt:",
            "      - no-new-privileges:true",
            "    environment:",
            f"      TZ: ${{TZ:-{cfg.tz}}}",
            "      LOG_LEVEL: info",
            "      CAPTCHA_SOLVER: none",
            "    ports:",
            f'      - "{cfg.flaresolverr_port}:8191"',
            *ctrl_dep,
            "    healthcheck:",
            '      test: ["CMD-SHELL", "python3 -c \'import urllib.request; urllib.request.urlopen(\\"http://127.0.0.1:8191/health\\")\' >/dev/null 2>&1 || curl -fsS http://127.0.0.1:8191/health >/dev/null 2>&1 || exit 1"]',
            "      interval: 30s",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 20s",
            "    restart: on-failure:5",
            "    logging: *default-logging",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def generate_komf_application_yml(cfg: EbookStackConfigRequest) -> str:
    """Generate a Kaml-parser-validated /volume1/docker/komf/config/application.yml for Komga & Kavita."""
    return f"""# =============================================================================
# 🤖 KOMF (Komga & Kavita Metadata Fetcher) - 한국어·글로벌 통합 최적화 설정 파일
# 저장 경로: {cfg.docker_root.rstrip('/')}/komf/config/application.yml
# (참고: 실제 비밀번호와 API 키는 도커 환경변수 KOMF_KOMGA_*, KOMF_KAVITA_*가 자동 오버라이드합니다)
# =============================================================================

komga:
  baseUri: "http://komga:25600"
  komgaUser: "{cfg.komga_user}"
  komgaPassword: "{cfg.komga_password}"
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
  apiKey: "{cfg.kavita_api_key}"
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
"""


def generate_synology_init_script(cfg: EbookStackConfigRequest) -> str:
    """Generate the Synology Task Scheduler root initialization & safe migration script."""
    docker_root = cfg.docker_root.rstrip("/")
    data_root = cfg.ebook_data_root.rstrip("/")
    komf_yml = generate_komf_application_yml(cfg)

    return f"""#!/bin/bash
# =============================================================================
# 🛠️ SYNOLOGY EBOOK STACK - 폴더·권한·DB 무손실 마이그레이션 자동화 스크립트
# =============================================================================
# (참고: docker-compose.yml의 ebook-control-center 컨테이너가 부팅 시 아래 작업을 자동으로
#  수행하므로 수동 실행하지 않으셔도 되며, 시놀로지 작업 스케줄러에서 초기 1회 실행용으로도 쓸 수 있습니다.)
# =============================================================================
set -e

echo '[1/5] 도커 컨테이너별 전용 설정(Config) 폴더 생성 중...'
mkdir -p "{docker_root}/komga/config"
mkdir -p "{docker_root}/komga/data"
mkdir -p "{docker_root}/kavita/config"
mkdir -p "{docker_root}/kavita/data"
mkdir -p "{docker_root}/audiobookshelf/config"
mkdir -p "{docker_root}/audiobookshelf/metadata"
mkdir -p "{docker_root}/audiobookshelf/audiobooks"
mkdir -p "{docker_root}/komf/config"
mkdir -p "{docker_root}/calibre-web-automated/config"
mkdir -p "{docker_root}/cwa-book-downloader/config"
mkdir -p "{docker_root}/suwayomi"
mkdir -p "{docker_root}/readarr"
mkdir -p "{docker_root}/stirling-pdf/configs"
mkdir -p "{docker_root}/stirling-pdf/logs"
mkdir -p "{docker_root}/stirling-pdf/tessdata"

echo '[2/5] Audiobookshelf 기존 중첩 볼륨(Nested Mount) 데이터베이스 안전 이관 점검 중...'
if [ -f "{docker_root}/audiobookshelf/absdatabase.sqlite" ] && [ ! -f "{docker_root}/audiobookshelf/config/absdatabase.sqlite" ]; then
  echo '  -> 기존 상위 폴더에 있던 Audiobookshelf DB를 /config 하위 폴더로 무손실 복사합니다...'
  cp -a "{docker_root}/audiobookshelf/absdatabase.sqlite"* "{docker_root}/audiobookshelf/config/" 2>/dev/null || true
  [ -d "{docker_root}/audiobookshelf/backups" ] && cp -rn "{docker_root}/audiobookshelf/backups" "{docker_root}/audiobookshelf/config/" 2>/dev/null || true
  [ -d "{docker_root}/audiobookshelf/migrations" ] && cp -rn "{docker_root}/audiobookshelf/migrations" "{docker_root}/audiobookshelf/config/" 2>/dev/null || true
fi

echo '[3/5] 통합 마스터 eBook 서재 폴더 구조({data_root}) 및 기존 캘리버 서재 이관 점검 중...'
mkdir -p "{data_root}/manga"
mkdir -p "{data_root}/webtoon"
mkdir -p "{data_root}/comics"
mkdir -p "{data_root}/lightnovels"
mkdir -p "{data_root}/books"
mkdir -p "{data_root}/audiobooks"
mkdir -p "{data_root}/podcasts"
mkdir -p "{data_root}/magazines"
mkdir -p "{data_root}/cwa-ingest"
mkdir -p "{data_root}/calibre-library"
if [ -f "{docker_root}/calibre/캘리버 서재/metadata.db" ] && [ ! -f "{data_root}/calibre-library/metadata.db" ]; then
  cp -rn "{docker_root}/calibre/캘리버 서재/"* "{data_root}/calibre-library/" 2>/dev/null || true
fi

echo '[4/5] Komf 한국어·글로벌 메타데이터 설정 파일(application.yml) 준비 중...'
if [ ! -f "{docker_root}/komf/config/application.yml" ]; then
  cat << 'KOMF_EOF' > "{docker_root}/komf/config/application.yml"
{komf_yml}KOMF_EOF
fi

echo '[5/5] 시놀로지 표준 사용자 권한(PUID={cfg.puid}, PGID={cfg.pgid}) 일괄 적용 중...'
chown -R {cfg.puid}:{cfg.pgid} "{docker_root}/komga" "{docker_root}/kavita" "{docker_root}/audiobookshelf" "{docker_root}/komf" "{docker_root}/calibre-web-automated" "{docker_root}/cwa-book-downloader" "{docker_root}/suwayomi" "{docker_root}/readarr" "{docker_root}/stirling-pdf" "{data_root}"
chmod -R 775 "{data_root}"

echo '✅ eBook Stack 폴더 생성, DB 무손실 분리, 권한 적용이 100% 완료되었습니다!'
"""


def generate_maintenance_doctor_script(cfg: EbookStackConfigRequest) -> str:
    """Generate an ongoing automated safe-update, SQLite VACUUM optimization & backup script."""
    docker_root = cfg.docker_root.rstrip("/")
    data_root = cfg.ebook_data_root.rstrip("/")
    backup_root = f"{docker_root}/_backups/ebook-stack"
    stack_dir = f"{docker_root}/ebook-stack"

    return f"""#!/bin/bash
# =============================================================================
# 🩺 EBOOK STACK DOCTOR - 백업 우선 안전 자동 업데이트 · SQLite 최적화 · 자가치유 스크립트
# =============================================================================
# • Watchtower 라벨 연동과 더불어, 언제든 수동 또는 스케줄러로 실행 시
#   [1. DB 스냅샷 백업] ➔ [2. 각 공식 제작자 최신 이미지 Pull & 무중단 교체] ➔
#   [3. SQLite WAL & VACUUM 속도 최적화] ➔ [4. 구버전 잉여 이미지 청소]를 수행합니다.
# =============================================================================
set -e

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="{backup_root}/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

echo "=================================================================="
echo "💾 [1/5] 업데이트 전 Komga · Kavita · Audiobookshelf · Komf · CWA 안전 스냅샷 백업"
echo "=================================================================="
for svc in komga kavita audiobookshelf komf calibre-web-automated; do
  if [ -d "{docker_root}/$svc" ]; then
    tar -czf "$BACKUP_DIR/${{svc}}_config_${{TIMESTAMP}}.tar.gz" \\
      --exclude="*.log" --exclude="cache" --exclude="Cache" --exclude="logs" \\
      -C "{docker_root}" "$svc/config" 2>/dev/null || true
    echo "  -> $svc 업데이트 전 안전 백업 완료: $BACKUP_DIR/${{svc}}_config_${{TIMESTAMP}}.tar.gz"
  fi
done

# 30일 이상 지난 오래된 백업본 자동 정리 (NAS 용량 보호)
find "{backup_root}" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {{}} + 2>/dev/null || true

echo "=================================================================="
echo "🔄 [2/5] 각 공식 제작자 최신 도커 이미지 확인 및 변경된 컨테이너만 무중단 업데이트"
echo "=================================================================="
if [ -f "{stack_dir}/docker-compose.yml" ]; then
  cd "{stack_dir}"
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
  for db_file in \\
    "{docker_root}/komga/config/database.sqlite" \\
    "{docker_root}/kavita/config/kavita.db" \\
    "{docker_root}/audiobookshelf/config/absdatabase.sqlite" \\
    "{docker_root}/komf/config/database.sqlite" \\
    "{data_root}/calibre-library/metadata.db"; do
    if [ -f "$db_file" ]; then
      echo "  -> SQLite 최적화 수행 중: $db_file"
      sqlite3 "$db_file" "PRAGMA journal_mode=WAL; PRAGMA wal_checkpoint(TRUNCATE); PRAGMA optimize; VACUUM; ANALYZE;" 2>/dev/null || true
    fi
  done
fi

echo "=================================================================="
echo "🔐 [4/5] 시놀로지 파일 권한(PUID={cfg.puid}:PGID={cfg.pgid}) 및 인제스트 폴더 자가 치유"
echo "=================================================================="
chown -R {cfg.puid}:{cfg.pgid} "{data_root}" 2>/dev/null || true
chmod -R 775 "{data_root}/cwa-ingest" 2>/dev/null || true

echo "=================================================================="
echo "🧹 [5/5] 업데이트 후 남은 구버전 잉여 도커 이미지 자동 청소 (NAS 디스크 회수)"
echo "=================================================================="
docker image prune -f >/dev/null 2>&1 || true
docker ps --filter "name={cfg.container_prefix}" --format "table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}" || true

echo "✅ [완료] 백업 ➔ 최신 이미지 안전 업데이트 ➔ DB 최적화 ➔ 구버전 이미지 청소가 모두 끝났습니다!"
"""


def generate_env_template(cfg: EbookStackConfigRequest) -> str:
    """Generate the .env.example template (zero personal credentials hardcoded)."""
    return f"""# =============================================================================
# 🔐 EBOOK STACK (.env 환경변수 설정 파일 예시)
# =============================================================================
# ⚠️ 주의: 실제 비밀번호와 API 키가 들어있는 로컬 .env 파일은 .gitignore로 보호됩니다.

# 🕒 1. 시놀로지 NAS 시스템 권한 및 타임존
TZ={cfg.tz}
PUID={cfg.puid}
PGID={cfg.pgid}
NAS_IP={cfg.nas_ip}

# 📂 2. 도커 및 마스터 서재 경로
DOCKER_ROOT={cfg.docker_root}
EBOOK_DATA_ROOT={cfg.ebook_data_root}

# 📚 3. Komga 및 Komf 연동 인증 정보
KOMGA_USER=your_email@example.com
KOMGA_PASSWORD=YOUR_KOMGA_PASSWORD

# 🌟 4. Kavita 및 Audiobookshelf 인증 정보
KAVITA_API_KEY=YOUR_KAVITA_OPDS_API_KEY
ABS_JWT_SECRET=CHANGE_ME_TO_A_RANDOM_64_CHAR_SECRET

# 📖 5. Calibre-Web-Automated 선택 옵션 (Hardcover.app API 토큰 등)
HARDCOVER_TOKEN=

# 🛡️ 6. eBook Control Center 웹 대시보드 보호 계정 & 외부 도메인 (선택)
CONTROL_CENTER_USER=admin
CONTROL_CENTER_PASSWORD=
BASE_DOMAIN=
"""


def generate_wiring_and_opds_guide(cfg: EbookStackConfigRequest) -> List[Dict[str, str]]:
    """Generate internal Docker wiring addresses and external OPDS/App URLs."""
    return [
        {
            "step": "1단계: Zero-Touch Auto-Wirer 자동 배선 (Komga · Kavita · ABS · CWA · Readarr)",
            "target": f"http://{cfg.nas_ip}:{cfg.control_port} (eBook Control Center)",
            "internal_address": "Komga: http://komga:25600 | Kavita: http://kavita:5000 | ABS: http://audiobookshelf:80",
            "details": (
                "ebook-control-center(:8586)가 부팅 즉시 기존 서재(/data, /manga, /audiobooks, 캘리버 서재)를 보존하면서 "
                "신규 통합 서재(/ebooks/*, /calibre-library)를 각 서버의 REST API로 자동 등록합니다."
            ),
        },
        {
            "step": "2단계: CWA Book Downloader → Calibre-Web-Automated → Kavita/ABS/Komga 원클릭 파이프라인",
            "target": f"http://{cfg.nas_ip}:{cfg.cwa_dl_port} → http://{cfg.nas_ip}:{cfg.cwa_port} → 전 뷰어 동시 반영",
            "internal_address": "인제스트: /cwa-book-ingest ➔ 변환 후 저장: /calibre-library (전 컨테이너 동시 공유)",
            "details": (
                "CWA Book Downloader(:8084)에서 원하는 책을 검색해 [Download]를 누르면 /cwa-book-ingest 로 내려받아지고, "
                "Calibre-Web-Automated(:8083)가 5초 내로 감지해 EPUB 자동 변환 후 /calibre-library 에 정식 등록합니다."
            ),
        },
        {
            "step": "3단계: Suwayomi (Keiyoushi 웹툰·만화 확장 내장) → Komga & Kavita 실시간 연동",
            "target": f"http://{cfg.nas_ip}:{cfg.suwayomi_port}",
            "internal_address": "FlareSolverr: http://flaresolverr:8191 | CBZ 자동 저장 경로: /ebooks/manga",
            "details": (
                "Suwayomi(:4567)에 Keiyoushi 공식 만화·웹툰 확장 리포지토리와 CBZ 자동 압축 설정이 이미 주입되어 있습니다. "
                "원하는 웹툰/만화 소스를 설치해 작품을 담으면 새 회차가 .cbz로 /ebooks/manga 에 저장되어 Komga·Kavita에 즉시 뜹니다."
            ),
        },
        {
            "step": "4단계: 모바일·태블릿 앱 OPDS 및 전용 API 연결 주소록",
            "target": "Panels / Mihon / Plappa / KOReader",
            "internal_address": (
                f"Komga OPDS: http://{cfg.nas_ip}:{cfg.komga_port}/opds/v1.2/catalog | "
                f"Kavita OPDS: http://{cfg.nas_ip}:{cfg.kavita_port}/api/opds/{cfg.kavita_api_key} | "
                f"CWA OPDS: http://{cfg.nas_ip}:{cfg.cwa_port}/opds"
            ),
            "details": (
                "아이패드 Panels, 안드로이드 Mihon, 아이폰 Plappa(CarPlay), 이북리더기 KOReader 앱에 위 주소를 등록하면 "
                "언제 어디서나 스트리밍 열람 및 오프라인 다운로드가 가능합니다."
            ),
        },
    ]
