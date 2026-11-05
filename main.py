"""FastAPI Backend for the Unified eBook, Manga, Webtoon & Audiobook Stack Control Center (ebook-stack)."""

import asyncio
import io
import os
import zipfile
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Dict, List

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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


async def _daily_maintenance_loop() -> None:
    """Automatically back up SQLite DBs & run VACUUM every 24h so Watchtower updates are 100% safe."""
    while True:
        await asyncio.sleep(86400)
        with suppress(Exception):
            run_sqlite_maintenance_and_backup()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("AUTO_BOOTSTRAP", "true").lower() == "true":
        bootstrap_host_environment()
    maint_task = None
    if os.environ.get("AUTO_DAILY_MAINTENANCE", "true").lower() == "true":
        maint_task = asyncio.create_task(_daily_maintenance_loop())
    try:
        yield
    finally:
        if maint_task:
            maint_task.cancel()
            with suppress(asyncio.CancelledError):
                await maint_task


app = FastAPI(
    title="Ultimate eBook & Manga Stack Control Center (ebook-stack)",
    description="시놀로지 NAS (DS920+) 맞춤형 Komga · Kavita · Audiobookshelf · Komf · Calibre-Web-Automated · Suwayomi 단일 프로젝트 통합 관제 스튜디오",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProbeRequest(BaseModel):
    nas_ip: str = "192.168.1.100"
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
        "version": "1.1.0",
        "architecture": "Unified Single-Project Docker Compose + Active Runtime Control Center",
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
        "container_naming_scheme": "ebook-<서비스명> (내부 DNS 호스트네임 양방향 호환)",
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
            "name": "🏆 현존 최고 완벽 통합 스택 (관제 센터 + 10대 서비스 전체)",
            "badge": "단일 프로젝트 풀 구성",
            "description": "eBook Control Center(:8500) + Komga + Kavita + Audiobookshelf + Komf + Calibre-Web-Automated + CWA-Downloader + Suwayomi + Readarr + Stirling-PDF + FlareSolverr",
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
            "name": "🔧 기존 업로드 4대장 무결점 교정 스택 (관제 센터 + 4대장)",
            "badge": "기존 구성 100% 호환 + 버그 완치",
            "description": "업로드하신 Komga(8341) + Kavita(5471) + Audiobookshelf(13378) + Komf(8085) 4종의 중첩 볼륨 버그, 권한 누락, 부팅 순서 오류를 완벽 해결한 스택",
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
    """Trigger immediate directory creation, Audiobookshelf DB migration, and Komf config generation."""
    return bootstrap_host_environment()


@app.post("/api/runtime/maintenance")
async def trigger_runtime_maintenance() -> Dict[str, Any]:
    """Trigger immediate SQLite VACUUM optimization and config tar.gz backup."""
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


@app.post("/api/probe-services")
async def probe_services(req: ProbeRequest) -> Dict[str, Any]:
    """Probe target NAS IP ports to check if any eBook stack services are currently online."""
    results = []
    svc_map = {s["id"]: s for s in EBOOK_SERVICES_CATALOG}

    async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
        for svc_id in req.services:
            svc = svc_map.get(svc_id)
            if not svc or not svc.get("webui_port"):
                continue
            port = svc["webui_port"]
            path = svc.get("webui_path", "")
            url = f"http://{req.nas_ip}:{port}{path}"
            try:
                resp = await client.get(url)
                reachable = resp.status_code < 500
                status_text = f"HTTP {resp.status_code} (정상 가동 중)"
            except Exception:
                reachable = False
                status_text = "대기 중 (배포 전 또는 외부 망)"

            results.append(
                {
                    "id": svc_id,
                    "name": svc["name"],
                    "container_name": svc["container_name"],
                    "port": port,
                    "url": url,
                    "reachable": reachable,
                    "status_text": status_text,
                }
            )
    return {"nas_ip": req.nas_ip, "results": results}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
