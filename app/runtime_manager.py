"""Runtime Auto-Bootstrapper, Permission Self-Healer, SQLite Optimizer & Backup Engine for ebook-control-center."""

import os
import shutil
import sqlite3
import tarfile
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.ebook_generator import EbookStackConfigRequest, generate_komf_application_yml


def get_mount_paths() -> Dict[str, Path]:
    docker_mount = Path(os.environ.get("HOST_DOCKER_MOUNT", "/host-docker"))
    data_mount = Path(os.environ.get("HOST_DATA_MOUNT", "/host-data"))
    return {"docker": docker_mount, "data": data_mount}


def _apply_synology_permissions(target: Path, puid: int = 1026, pgid: int = 100) -> None:
    """Safely apply Synology PUID:PGID (1026:100) and 775/664 permissions so non-root containers never hit EACCES."""
    with suppress(Exception):
        if target.is_dir():
            target.chmod(0o775)
        else:
            target.chmod(0o664)
    with suppress(Exception):
        os.chown(target, puid, pgid)


def bootstrap_host_environment(
    docker_root: Path | None = None,
    data_root: Path | None = None,
) -> Dict[str, Any]:
    """Automatically provision folders, migrate Audiobookshelf DB, write Komf config, and enforce 1026:100 ownership."""
    mounts = get_mount_paths()
    d_root = docker_root or mounts["docker"]
    e_root = data_root or mounts["data"]
    puid = int(os.environ.get("PUID", "1026"))
    pgid = int(os.environ.get("PGID", "100"))

    actions: List[str] = []
    if not d_root.exists() and not e_root.exists():
        return {
            "executed": False,
            "mode": "preview_standalone",
            "message": "호스트 마운트(/host-docker, /host-data) 미감지: 스튜디오 프리뷰 모드로 동작합니다.",
            "actions": actions,
        }

    # 1. Create config directories & enforce PUID:PGID ownership
    config_subdirs = [
        "komga/config",
        "komga/data",
        "kavita/config",
        "kavita/data",
        "audiobookshelf/config",
        "audiobookshelf/metadata",
        "audiobookshelf/audiobooks",
        "komf/config",
        "calibre-web-automated/config",
        "cwa-book-downloader/config",
        "suwayomi",
        "readarr",
        "stirling-pdf/configs",
        "stirling-pdf/logs",
        "stirling-pdf/tessdata",
        "_backups/ebook-stack",
    ]
    if d_root.exists():
        for sub in config_subdirs:
            target = d_root / sub
            target.mkdir(parents=True, exist_ok=True)
            _apply_synology_permissions(target.parent, puid, pgid)
            _apply_synology_permissions(target, puid, pgid)
        actions.append(f"도커 설정 폴더 {len(config_subdirs)}개 자동 생성 및 PUID({puid}):PGID({pgid}) 권한 부여 완료")

        # 2. Safe migration for Audiobookshelf nested volume bug
        abs_root = d_root / "audiobookshelf"
        abs_cfg = abs_root / "config"
        old_db = abs_root / "absdatabase.sqlite"
        new_db = abs_cfg / "absdatabase.sqlite"
        if old_db.exists() and not new_db.exists():
            for item in abs_root.glob("absdatabase.sqlite*"):
                dst_item = abs_cfg / item.name
                shutil.copy2(item, dst_item)
                _apply_synology_permissions(dst_item, puid, pgid)
            for folder_name in ["backups", "migrations"]:
                src_dir = abs_root / folder_name
                dst_dir = abs_cfg / folder_name
                if src_dir.is_dir() and not dst_dir.exists():
                    shutil.copytree(src_dir, dst_dir)
                    for sub_item in dst_dir.rglob("*"):
                        _apply_synology_permissions(sub_item, puid, pgid)
                    _apply_synology_permissions(dst_dir, puid, pgid)
            actions.append("Audiobookshelf 기존 상위 폴더 DB(absdatabase.sqlite)를 /config 하위로 무손실 이관 및 권한 교정 완료")

        # 3. Auto-generate Komf application.yml if missing
        komf_yml_path = d_root / "komf/config/application.yml"
        if not komf_yml_path.exists():
            cfg = EbookStackConfigRequest(
                komga_user=os.environ.get("KOMGA_USER", "fauna035@gmail.com"),
                komga_password=os.environ.get("KOMGA_PASSWORD", "YOUR_KOMGA_PASSWORD"),
                kavita_api_key=os.environ.get("KAVITA_API_KEY", "JR5SNjbYayxiZtzTgEIWOTfZ6Od3iyTa"),
            )
            komf_yml_path.write_text(generate_komf_application_yml(cfg), encoding="utf-8")
            _apply_synology_permissions(komf_yml_path, puid, pgid)
            actions.append("Komf 한국어·글로벌 메타데이터 설정 파일(komf/config/application.yml) 자동 생성 완료")

    # 4. Create unified eBook library directories & enforce 1026:100 ownership
    library_subdirs = [
        "manga",
        "webtoon",
        "comics",
        "lightnovels",
        "books",
        "audiobooks",
        "podcasts",
        "magazines",
        "cwa-ingest",
        "calibre-library",
    ]
    if e_root.exists():
        _apply_synology_permissions(e_root, puid, pgid)
        for sub in library_subdirs:
            sub_dir = e_root / sub
            sub_dir.mkdir(parents=True, exist_ok=True)
            _apply_synology_permissions(sub_dir, puid, pgid)
        actions.append(f"통합 마스터 서재 하위 폴더 {len(library_subdirs)}개 생성 및 PUID({puid}):PGID({pgid}) 권한 적용 완료")

    return {
        "executed": True,
        "mode": "active_container_management",
        "message": "통합 관제 엔진이 폴더 구조·권한(1026:100)·DB 분리·설정 파일을 완벽히 초기화했습니다.",
        "actions": actions,
    }


def run_sqlite_maintenance_and_backup(
    docker_root: Path | None = None,
    data_root: Path | None = None,
) -> Dict[str, Any]:
    """Run Python-native SQLite VACUUM/ANALYZE optimization and compressed config backups."""
    mounts = get_mount_paths()
    d_root = docker_root or mounts["docker"]
    e_root = data_root or mounts["data"]

    optimized_dbs: List[str] = []
    backups_created: List[str] = []

    db_candidates = [
        d_root / "komga/config/database.sqlite",
        d_root / "kavita/config/kavita.db",
        d_root / "audiobookshelf/config/absdatabase.sqlite",
        d_root / "komf/config/database.sqlite",
        e_root / "calibre-library/metadata.db",
    ]

    for db_path in db_candidates:
        if db_path.exists() and db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path), timeout=10.0)
                conn.execute("PRAGMA optimize;")
                conn.execute("VACUUM;")
                conn.execute("ANALYZE;")
                conn.close()
                optimized_dbs.append(str(db_path))
            except Exception as exc:
                optimized_dbs.append(f"{db_path} (스킵: {exc})")

    if d_root.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = d_root / "_backups/ebook-stack" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for svc in ["komga", "kavita", "audiobookshelf", "komf", "calibre-web-automated"]:
            cfg_dir = d_root / svc / "config"
            if cfg_dir.exists():
                archive_path = backup_dir / f"{svc}_config_{timestamp}.tar.gz"
                with tarfile.open(archive_path, "w:gz") as tar:
                    tar.add(cfg_dir, arcname=f"{svc}/config")
                backups_created.append(str(archive_path))

        # Prune backups older than 30 days
        cutoff = datetime.now() - timedelta(days=30)
        parent_backup = d_root / "_backups/ebook-stack"
        if parent_backup.exists():
            for child in parent_backup.iterdir():
                if child.is_dir():
                    mtime = datetime.fromtimestamp(child.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(child, ignore_errors=True)

    return {
        "status": "ok",
        "optimized_databases": optimized_dbs,
        "backups_created": backups_created,
        "summary": f"SQLite DB 최적화 {len(optimized_dbs)}건, 설정 백업 {len(backups_created)}건 완료",
    }
