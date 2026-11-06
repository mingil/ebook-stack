"""Runtime Auto-Bootstrapper, Permission Self-Healer, SQLite WAL Optimizer & Backup Engine for ebook-control-center."""

import os
import shutil
import sqlite3
import tarfile
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.auto_wirer import (
    discover_ebook_credentials,
    provision_calibre_library_and_cwa,
    provision_komf_config,
    provision_qbittorrent_ebook_categories,
    provision_suwayomi_config,
)


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


def _safe_chown_chmod_tree(root_dir: Path, puid: int = 1026, pgid: int = 100, max_depth: int = 3) -> None:
    """Recursively heal root:root ownership on config/ebook folders created by Docker daemon or DSM File Station."""
    if not root_dir.exists():
        return
    _apply_synology_permissions(root_dir, puid, pgid)
    with suppress(Exception):
        base_parts = len(root_dir.parts)
        for dirpath, dirnames, filenames in os.walk(root_dir):
            cur_path = Path(dirpath)
            if len(cur_path.parts) - base_parts >= max_depth:
                dirnames.clear()
            for dname in dirnames:
                _apply_synology_permissions(cur_path / dname, puid, pgid)
            for fname in filenames:
                _apply_synology_permissions(cur_path / fname, puid, pgid)


def _resolve_ebook_root(base_data_root: Path) -> Path:
    """Resolve the ebook library directory whether /volume1/mediarr (/host-data) or /volume1/mediarr/ebooks is mounted."""
    if base_data_root.name in ("host-data", "mediarr") and (
        (base_data_root / "torrents").exists() or (base_data_root / "media").exists()
    ):
        return base_data_root / "ebooks"
    return base_data_root


def bootstrap_host_environment(
    docker_root: Path | None = None,
    data_root: Path | None = None,
) -> Dict[str, Any]:
    """Automatically provision folders, migrate Audiobookshelf & Calibre DBs, write Komf/Suwayomi configs, and enforce 1026:100 ownership."""
    mounts = get_mount_paths()
    d_root = docker_root or mounts["docker"]
    raw_data_root = data_root or mounts["data"]
    e_root = _resolve_ebook_root(raw_data_root)
    puid = int(os.environ.get("PUID", "1026"))
    pgid = int(os.environ.get("PGID", "100"))

    actions: List[str] = []
    if not d_root.exists() and not raw_data_root.exists():
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
        strict_dirs = {
            "komf/config",
            "calibre-web-automated/config",
            "cwa-book-downloader/config",
            "suwayomi",
            "readarr",
            "stirling-pdf/configs",
            "stirling-pdf/logs",
            "stirling-pdf/tessdata",
        }
        for sub in config_subdirs:
            target = d_root / sub
            target.mkdir(parents=True, exist_ok=True)
            _apply_synology_permissions(target.parent, puid, pgid)
            if sub in strict_dirs:
                _safe_chown_chmod_tree(target, puid, pgid, max_depth=2)
            else:
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

        # Ensure existing audiobookshelf/config & komga/config & kavita/config files have 1026:100 ownership
        for cfg_sub in ["audiobookshelf/config", "audiobookshelf/metadata", "komga/config", "kavita/config", "komf/config"]:
            _safe_chown_chmod_tree(d_root / cfg_sub, puid, pgid, max_depth=2)

    # 3. Create unified eBook library directories & torrent hardlink subdirs (/data/torrents/{books,audiobooks,manga})
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
    if raw_data_root.exists():
        e_root.mkdir(parents=True, exist_ok=True)
        _apply_synology_permissions(raw_data_root, puid, pgid)
        _apply_synology_permissions(e_root, puid, pgid)
        for sub in library_subdirs:
            sub_dir = e_root / sub
            sub_dir.mkdir(parents=True, exist_ok=True)
            _apply_synology_permissions(sub_dir, puid, pgid)
            # Also ensure top-level if raw_data_root is mounted directly in tests
            if raw_data_root != e_root:
                alt_dir = raw_data_root / sub
                alt_dir.mkdir(parents=True, exist_ok=True)
                _apply_synology_permissions(alt_dir, puid, pgid)

        # Create torrent hardlink folders if /volume1/mediarr (/host-data) is mounted
        torrents_dir = raw_data_root / "torrents"
        if torrents_dir.exists() or raw_data_root.name in ("host-data", "mediarr"):
            for t_sub in ["torrents/books", "torrents/audiobooks", "torrents/manga"]:
                t_dir = raw_data_root / t_sub
                t_dir.mkdir(parents=True, exist_ok=True)
                _apply_synology_permissions(t_dir, puid, pgid)

        actions.append(f"통합 마스터 서재({e_root}) 하위 폴더 {len(library_subdirs)}개 및 하드링크 폴더 생성 완료")

    # 4. Pre-provision Komf, Suwayomi, Calibre-Web-Automated, and qBittorrent categories
    creds = discover_ebook_credentials(d_root)
    if d_root.exists():
        actions.append(
            provision_komf_config(
                d_root,
                komga_user=creds["komga_user"],
                komga_password=creds["komga_password"],
                kavita_api_key=creds["kavita_api_key"],
                puid=puid,
                pgid=pgid,
            )
        )
        actions.append(provision_suwayomi_config(d_root, puid=puid, pgid=pgid))
        actions.append(provision_qbittorrent_ebook_categories(d_root, puid=puid, pgid=pgid))

    if raw_data_root.exists():
        actions.append(provision_calibre_library_and_cwa(d_root, e_root, puid=puid, pgid=pgid))
        if raw_data_root != e_root:
            provision_calibre_library_and_cwa(d_root, raw_data_root, puid=puid, pgid=pgid)

    return {
        "executed": True,
        "mode": "active_container_management",
        "message": "통합 관제 엔진이 폴더 구조·권한(1026:100)·DB 무손실 분리·Calibre 이관·설정 파일을 완벽히 초기화했습니다.",
        "actions": actions,
    }


def run_sqlite_maintenance_and_backup(
    docker_root: Path | None = None,
    data_root: Path | None = None,
) -> Dict[str, Any]:
    """Run Python-native SQLite WAL checkpoint, VACUUM/ANALYZE optimization and compressed config backups."""
    mounts = get_mount_paths()
    d_root = docker_root or mounts["docker"]
    raw_data_root = data_root or mounts["data"]
    e_root = _resolve_ebook_root(raw_data_root)

    optimized_dbs: List[str] = []
    backups_created: List[str] = []

    db_candidates = [
        d_root / "komga/config/database.sqlite",
        d_root / "komga/config/tasks.sqlite",
        d_root / "kavita/config/kavita.db",
        d_root / "audiobookshelf/config/absdatabase.sqlite",
        d_root / "komf/config/database.sqlite",
        d_root / "calibre-web-automated/config/app.db",
        d_root / "readarr/readarr.db",
        e_root / "calibre-library/metadata.db",
        raw_data_root / "calibre-library/metadata.db",
    ]

    seen = set()
    for db_path in db_candidates:
        s_path = str(db_path)
        if s_path in seen:
            continue
        seen.add(s_path)
        if db_path.exists() and db_path.is_file():
            try:
                conn = sqlite3.connect(s_path, timeout=15.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.execute("PRAGMA optimize;")
                conn.execute("VACUUM;")
                conn.execute("ANALYZE;")
                conn.close()
                optimized_dbs.append(s_path)
            except Exception as exc:
                optimized_dbs.append(f"{db_path} (스킵: {exc})")

    if d_root.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = d_root / "_backups/ebook-stack" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for svc, rel_cfg in [
            ("komga", "komga/config"),
            ("kavita", "kavita/config"),
            ("audiobookshelf", "audiobookshelf/config"),
            ("komf", "komf/config"),
            ("calibre-web-automated", "calibre-web-automated/config"),
            ("suwayomi", "suwayomi"),
            ("readarr", "readarr"),
        ]:
            cfg_dir = d_root / rel_cfg
            if cfg_dir.exists() and any(cfg_dir.iterdir()):
                archive_path = backup_dir / f"{svc}_config_{timestamp}.tar.gz"
                with suppress(Exception):
                    with tarfile.open(archive_path, "w:gz") as tar:
                        tar.add(cfg_dir, arcname=rel_cfg)
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
        "summary": f"SQLite DB WAL 최적화 {len(optimized_dbs)}건, 설정 백업 {len(backups_created)}건 완료",
    }
