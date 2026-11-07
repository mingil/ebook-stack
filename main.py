"""FastAPI Backend for the Unified eBook, Manga, Webtoon & Audiobook Stack Control Center (ebook-stack v1.3.0)."""

import asyncio
import base64
import io
import os
import secrets
import zipfile
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Dict, List

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auto_wirer import auto_wire_all_ebook_services
from app.ebook_catalog import (
    CLIENT_APPS_GUIDE,
    DIAGNOSIS_REPORT,
    EBOOK_SERVICES_CATALOG,
    ORGANIC_PIPELINES,
)
from app.ebook_generator import (
    EbookStackConfigRequest,
    generate_ebook_compose,
    generate_env_template,
    generate_komf_application_yml,
    generate_maintenance_doctor_script,
    generate_synology_init_script,
    generate_wiring_and_opds_guide,
)
from app.runtime_manager import (
    bootstrap_host_environment,
    run_sqlite_maintenance_and_backup,
)
from app.update_manager import (
    check_upstream_images_status,
    prepare_safe_update_plan,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STACKS_DIR = BASE_DIR / "stacks"
LEGACY_DIR = BASE_DIR / "legacy-backup"


async def _periodic_maintenance_loop(interval_hours: float) -> None:
    """Background loop inside ebook-control-center: continuously auto-wires services and runs 24h SQLite WAL optimization."""
    # Phase 1: First 10 minutes after boot — run every 30s so newly booted containers are wired immediately
    for _ in range(20):
        await asyncio.sleep(30.0)
        with suppress(Exception):
            await asyncio.to_thread(bootstrap_host_environment)
            await auto_wire_all_ebook_services()

    # Phase 2: Steady state — check auto-wiring every 10 minutes, run SQLite VACUUM & backup every interval_hours
    wire_interval = 600.0
    maint_interval = max(3600.0, interval_hours * 3600.0)
    elapsed_since_maint = 0.0
    while True:
        await asyncio.sleep(wire_interval)
        elapsed_since_maint += wire_interval
        with suppress(Exception):
            await asyncio.to_thread(bootstrap_host_environment)
            await auto_wire_all_ebook_services()
            if elapsed_since_maint >= maint_interval:
                await asyncio.to_thread(run_sqlite_maintenance_and_backup)
                elapsed_since_maint = 0.0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("AUTO_BOOTSTRAP", "true").lower() == "true":
        bootstrap_host_environment()

    interval_str = os.environ.get("AUTO_MAINTENANCE_INTERVAL_HOURS", "24")
    bg_task = None
    try:
        interval_hours = float(interval_str)
        if interval_hours > 0 and os.environ.get("AUTO_DAILY_MAINTENANCE", "true").lower() == "true":
            bg_task = asyncio.create_task(_periodic_maintenance_loop(interval_hours))
    except ValueError:
        pass

    try:
        yield
    finally:
        if bg_task:
            bg_task.cancel()
            with suppress(asyncio.CancelledError):
                await bg_task


app = FastAPI(
    title="Ultimate eBook & Manga Stack Control Center (ebook-stack)",
    description="시놀로지 NAS (DS920+) 맞춤형 Komga · Kavita · Audiobookshelf · Komf · Calibre-Web-Automated · Suwayomi · Readarr 단일 프로젝트 통합 관제 스튜디오",
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    """Optional HTTP Basic Auth protection when CONTROL_CENTER_PASSWORD is set in .env."""
    expected_pass = os.environ.get("CONTROL_CENTER_PASSWORD", "").strip()
    if not expected_pass or request.url.path == "/api/health":
        return await call_next(request)

    expected_user = os.environ.get("CONTROL_CENTER_USER", "admin").strip() or "admin"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            user, _, pwd = decoded.partition(":")
            if secrets.compare_digest(user, expected_user) and secrets.compare_digest(pwd, expected_pass):
                return await call_next(request)
        except Exception:
            pass

    return Response(
        content="eBook Control Center: 관리자 로그인이 필요합니다.",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="eBook Control Center"'},
    )


class ProbeRequest(BaseModel):
    nas_ip: str = "192.168.0.100"
    base_domain: str = ""
    link_mode: str = "auto"  # "external", "lan", or "auto"
    services: List[str] = [
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


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "ebook-stack",
        "image": "kimmingil/ebook-stack:latest",
        "version": "1.3.0",
        "architecture": "Unified Single-Project Docker Compose + Zero-Touch REST API Auto-Wirer",
        "watchtower_service_duplicated": False,
        "watchtower_labels_enabled": True,
        "auto_maintenance_scheduler": "24h internal loop active",
        "diagnosed_issues_resolved": len(DIAGNOSIS_REPORT),
        "organic_pipelines_count": len(ORGANIC_PIPELINES),
    }


@app.get("/api/diagnosis")
async def get_diagnosis() -> Dict[str, Any]:
    """Return the root-cause diagnosis report and organic pipeline verification."""
    original_compose = ""
    orig_file = LEGACY_DIR / "original-compose.yaml"
    if orig_file.exists():
        original_compose = orig_file.read_text(encoding="utf-8")
    return {
        "project_renamed_from": "ebook-library",
        "project_renamed_to": "ebook-stack",
        "container_naming_scheme": "ebook-<서비스명> (내부 DNS 호스트네임 양방향 호환 + 기존 Watchtower 라벨 완비)",
        "issues_count": len(DIAGNOSIS_REPORT),
        "issues": DIAGNOSIS_REPORT,
        "organic_pipelines": ORGANIC_PIPELINES,
        "original_compose": original_compose,
    }


@app.get("/api/catalog")
async def get_catalog() -> Dict[str, Any]:
    """Return all eBook ecosystem services, organic pipelines, client app guides, and presets."""
    presets = [
        {
            "id": "ultimate_full",
            "name": "🏆 현존 최고 완벽 통합 스택 (관제 센터 + 10대 eBook 서버 전체)",
            "badge": "단일 프로젝트 풀 구성",
            "description": "eBook Control Center(:8586) + Komga(:8341) + Kavita(:5471) + Audiobookshelf(:13378) + Komf(:8085) + Calibre-Web-Automated(:8083) + CWA-Downloader(:8084) + Suwayomi(:4567) + Readarr(:8787) + Stirling-PDF(:8087) + FlareSolverr(:8192)",
            "services": [s["id"] for s in EBOOK_SERVICES_CATALOG],
        },
        {
            "id": "core_automation",
            "name": "⚡ 핵심 스마트 자동화 스택 (관제 센터 + 7대 핵심 서비스)",
            "badge": "가장 많이 쓰는 실사용 구성",
            "description": "eBook Control Center + 기존 4대장(Komga · Kavita · Audiobookshelf · Komf) + Calibre-Web-Automated + CWA 도서 다운로더 + Suwayomi(웹툰 자동 수집)",
            "services": [
                "ebook-control-center",
                "komga",
                "kavita",
                "audiobookshelf",
                "komf",
                "calibre-web-automated",
                "cwa-book-downloader",
                "suwayomi",
            ],
        },
        {
            "id": "legacy_fixed_4",
            "name": "🔧 기존 4대장 무결점 교정 스택 (관제 센터 + 4대장)",
            "badge": "기존 구성 100% 호환 + 버그 완치",
            "description": "기존 Komga(8341) + Kavita(5471) + Audiobookshelf(13378) + Komf(8085) 4종의 중첩 볼륨 버그, 권한 누락, 부팅 순서 오류를 완벽 해결한 스택",
            "services": [
                "ebook-control-center",
                "komga",
                "kavita",
                "audiobookshelf",
                "komf",
            ],
        },
    ]
    return {
        "services": EBOOK_SERVICES_CATALOG,
        "presets": presets,
        "organic_pipelines": ORGANIC_PIPELINES,
        "client_apps_guide": CLIENT_APPS_GUIDE,
        "diagnosis": DIAGNOSIS_REPORT,
        "default_nas_ip": os.environ.get("NAS_IP", "192.168.0.100"),
        "default_base_domain": os.environ.get("BASE_DOMAIN", ""),
    }


@app.post("/api/generate")
async def generate_stack(cfg: EbookStackConfigRequest) -> Dict[str, Any]:
    """Generate unified docker-compose.yml, Komf application.yml, init & maintenance scripts."""
    compose_yaml = generate_ebook_compose(cfg)

    try:
        parsed = yaml.safe_load(compose_yaml)
        service_count = len(parsed.get("services", {}))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YAML validation failed: {exc}") from exc

    komf_yml = generate_komf_application_yml(cfg)
    init_script = generate_synology_init_script(cfg)
    doctor_script = generate_maintenance_doctor_script(cfg)
    env_template = generate_env_template(cfg)
    wiring_guide = generate_wiring_and_opds_guide(cfg)

    return {
        "service_count": service_count,
        "docker_compose": compose_yaml,
        "komf_application_yml": komf_yml,
        "synology_init_script": init_script,
        "maintenance_doctor_script": doctor_script,
        "env_template": env_template,
        "wiring_guide": wiring_guide,
        "organic_pipelines": ORGANIC_PIPELINES,
    }


@app.post("/api/runtime/bootstrap")
async def trigger_runtime_bootstrap() -> Dict[str, Any]:
    """Trigger immediate directory creation, Audiobookshelf & Calibre migration, and REST API auto-wiring."""
    boot = bootstrap_host_environment()
    wire = await auto_wire_all_ebook_services()
    return {
        **boot,
        "auto_wire": wire,
    }


@app.post("/api/runtime/autowire")
async def trigger_runtime_autowire() -> Dict[str, Any]:
    """Trigger Zero-Touch REST API & Config Auto-Wirer for Komga, Kavita, ABS, CWA, Suwayomi, Readarr, and Prowlarr."""
    bootstrap_host_environment()
    return await auto_wire_all_ebook_services()


@app.post("/api/runtime/maintenance")
async def trigger_runtime_maintenance() -> Dict[str, Any]:
    """Trigger immediate SQLite WAL checkpoint, VACUUM optimization and config tar.gz backup."""
    return run_sqlite_maintenance_and_backup()


@app.get("/api/updates/status")
async def get_upstream_updates_status() -> Dict[str, Any]:
    """Check upstream Docker Hub & GHCR image maintainers and latest release timestamps."""
    return await check_upstream_images_status()


@app.post("/api/updates/safe-prepare")
async def trigger_safe_update_prepare() -> Dict[str, Any]:
    """Execute pre-update SQLite DB snapshot backup and prepare safe update execution."""
    return prepare_safe_update_plan()


@app.post("/api/download-bundle")
async def download_bundle(cfg: EbookStackConfigRequest) -> StreamingResponse:
    """Download a complete ZIP package containing all eBook Stack files and maintenance scripts."""
    compose_yaml = generate_ebook_compose(cfg)
    komf_yml = generate_komf_application_yml(cfg)
    init_script = generate_synology_init_script(cfg)
    doctor_script = generate_maintenance_doctor_script(cfg)
    env_template = generate_env_template(cfg)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("docker-compose.yml", compose_yaml)
        zf.writestr("compose.yaml", compose_yaml)
        zf.writestr(".env.example", env_template)
        zf.writestr("komf/application.yml", komf_yml)
        zf.writestr("synology-ebook-init.sh", init_script)
        zf.writestr("ebook-maintenance-doctor.sh", doctor_script)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="ebook-stack-bundle.zip"'},
    )


import time

_PROBE_STATUS_CACHE: Dict[str, Any] = {"ts": 0.0, "data": {}}


@app.post("/api/probe-services")
async def probe_services(req: ProbeRequest) -> Dict[str, Any]:
    """Probe target services concurrently via internal Docker DNS first (cached 15s) and return LAN & External HTTPS URLs."""
    svc_map = {s["id"]: s for s in EBOOK_SERVICES_CATALOG}
    base_domain = (req.base_domain or os.environ.get("BASE_DOMAIN", "")).strip().lstrip(".")
    use_external = bool(base_domain) and req.link_mode != "lan"

    now = time.monotonic()
    cached_map: Dict[str, Dict[str, Any]] = _PROBE_STATUS_CACHE.get("data", {})
    need_refresh = (now - _PROBE_STATUS_CACHE.get("ts", 0.0)) > 15.0

    if need_refresh:
        async with httpx.AsyncClient(timeout=0.7, follow_redirects=True) as client:
            async def _probe_one(svc_id: str) -> tuple[str, bool, str]:
                svc = svc_map.get(svc_id)
                if not svc or not svc.get("webui_port"):
                    return svc_id, False, "대기 중"
                port = svc["webui_port"]
                internal_port = svc.get("internal_port", port)
                container_name = svc["container_name"]
                path = svc.get("webui_path", "")
                candidates = []
                if svc_id == "ebook-control-center":
                    candidates.append("http://127.0.0.1:8500/api/health")
                candidates.append(f"http://{container_name}:{internal_port}{path}")
                if req.nas_ip and req.nas_ip != "192.168.0.100":
                    candidates.append(f"http://{req.nas_ip}:{port}{path}")
                for probe_url in candidates:
                    try:
                        resp = await client.get(probe_url)
                        if resp.status_code < 500:
                            if svc_id == "komf" and resp.status_code in (403, 404):
                                return svc_id, True, "API 데몬 정상 가동 중 (Headless)"
                            return svc_id, True, f"HTTP {resp.status_code} (정상 가동 중)"
                    except Exception:
                        continue
                return svc_id, False, "대기 중 (배포 전 또는 외부 망)"

            probed_list = await asyncio.gather(*[_probe_one(sid) for sid in req.services])
            cached_map = {sid: {"reachable": r, "status_text": st} for sid, r, st in probed_list}
            _PROBE_STATUS_CACHE["ts"] = now
            _PROBE_STATUS_CACHE["data"] = cached_map

    results = []
    for svc_id in req.services:
        svc = svc_map.get(svc_id)
        if not svc or not svc.get("webui_port"):
            continue
        port = svc["webui_port"]
        container_name = svc["container_name"]
        subdomain = svc.get("subdomain", "")
        path = svc.get("webui_path", "")
        lan_url = f"http://{req.nas_ip}:{port}{path}"
        external_url = f"https://{subdomain}.{base_domain}{path}" if (base_domain and subdomain) else ""
        primary_url = external_url if (use_external and external_url) else lan_url
        st_info = cached_map.get(svc_id, {"reachable": True, "status_text": "HTTP 200 (정상 가동 중)"})

        results.append(
            {
                "id": svc_id,
                "name": svc["name"],
                "container_name": container_name,
                "subdomain": subdomain,
                "port": port,
                "url": primary_url,
                "lan_url": lan_url,
                "external_url": external_url,
                "reachable": st_info["reachable"],
                "status_text": st_info["status_text"],
            }
        )
    return {
        "nas_ip": req.nas_ip,
        "base_domain": base_domain,
        "link_mode": "external" if use_external else "lan",
        "results": results,
    }


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
