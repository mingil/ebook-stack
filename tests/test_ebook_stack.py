"""Automated Unit & Integration Tests for the Unified eBook Stack (ebook-stack)."""

import io
import sqlite3
import zipfile
from pathlib import Path
import yaml
from fastapi.testclient import TestClient

from app.runtime_manager import (
    bootstrap_host_environment,
    run_sqlite_maintenance_and_backup,
)
from main import app

client = TestClient(app)


def test_health_endpoint_and_no_marius_or_watchtower():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "ebook-stack"
    assert data["image"] == "kimmingil/ebook-stack:latest"


def test_catalog_has_no_watchtower_and_includes_control_center():
    res = client.get("/api/catalog")
    assert res.status_code == 200
    data = res.json()
    service_ids = [s["id"] for s in data["services"]]
    assert "watchtower" not in service_ids
    assert "ebook-control-center" in service_ids
    assert len(service_ids) == 11
    assert len(data["organic_pipelines"]) == 4


def test_generate_unified_compose_verifies_organic_integration():
    payload = {
        "nas_ip": "192.168.1.100",
        "puid": 1026,
        "pgid": 100,
        "tz": "Asia/Seoul",
        "docker_root": "/volume1/docker",
        "ebook_data_root": "/volume1/data/ebooks",
        "container_prefix": "ebook-",
        "keep_legacy_mounts": True,
        "komga_port": 8341,
        "kavita_port": 5471,
        "audiobookshelf_port": 13378,
        "komf_port": 8085,
    }
    res = client.post("/api/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    compose_text = data["docker_compose"]

    # Ensure zero "marius" and zero "watchtower"
    assert "marius" not in compose_text.lower()
    assert "watchtower" not in compose_text.lower()

    parsed = yaml.safe_load(compose_text)
    assert "ebook_net" in parsed["networks"]
    services = parsed["services"]
    assert "watchtower" not in services

    # 0. Verify integrated project image (ebook-control-center)
    ctrl = services["ebook-control-center"]
    assert ctrl["image"] == "kimmingil/ebook-stack:latest"
    assert "/volume1/docker:/host-docker:rw" in ctrl["volumes"]
    assert "/volume1/data/ebooks:/host-data:rw" in ctrl["volumes"]

    # 1. Organic Pipeline 1: CWA Downloader -> CWA -> Shared /calibre-library across Kavita, ABS, Komga
    assert "/volume1/data/ebooks/cwa-ingest:/cwa-book-ingest:rw" in services["cwa-book-downloader"]["volumes"]
    assert "/volume1/data/ebooks/cwa-ingest:/cwa-book-ingest:rw" in services["calibre-web-automated"]["volumes"]
    for viewer in ["calibre-web-automated", "kavita", "audiobookshelf", "komga"]:
        assert "/volume1/data/ebooks/calibre-library:/calibre-library:rw" in services[viewer]["volumes"]

    # 2. Organic Pipeline 2: Suwayomi JVM flags -> CBZ to /data/manga + FlareSolverr URL
    suwayomi_java = services["suwayomi"]["environment"]["JAVA_TOOL_OPTIONS"]
    assert "-Dsuwayomi.tachidesk.config.server.downloadAsCbz=true" in suwayomi_java
    assert "-Dsuwayomi.tachidesk.config.server.downloadsPath=/data/manga" in suwayomi_java
    assert "-Dsuwayomi.tachidesk.config.server.flareSolverrUrl=http://flaresolverr:8191" in suwayomi_java

    # 3. Organic Pipeline 3: Audiobookshelf nested mount fix & Komf service_healthy wait
    abs_vols = services["audiobookshelf"]["volumes"]
    assert "/volume1/docker/audiobookshelf/config:/config:rw" in abs_vols
    assert "/volume1/docker/audiobookshelf:/config:rw" not in abs_vols
    komf_dep = services["komf"]["depends_on"]
    assert komf_dep["komga"]["condition"] == "service_healthy"
    assert komf_dep["kavita"]["condition"] == "service_healthy"

    # 4. Verify Kaml-compatible Komf application.yml (no unparsed ${...} placeholders)
    komf_yml_text = data["komf_application_yml"]
    assert "${" not in komf_yml_text
    komf_parsed = yaml.safe_load(komf_yml_text)
    assert komf_parsed["komga"]["baseUri"] == "http://komga:25600"
    assert komf_parsed["kavita"]["baseUri"] == "http://kavita:5000"


def test_runtime_bootstrap_and_sqlite_maintenance(tmp_path: Path):
    docker_dir = tmp_path / "docker"
    data_dir = tmp_path / "ebooks"
    docker_dir.mkdir()
    data_dir.mkdir()

    # Simulate legacy Audiobookshelf root-level SQLite DB before migration
    abs_legacy_dir = docker_dir / "audiobookshelf"
    abs_legacy_dir.mkdir(parents=True)
    legacy_db_file = abs_legacy_dir / "absdatabase.sqlite"
    conn = sqlite3.connect(str(legacy_db_file))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT);")
    conn.execute("INSERT INTO items (title) VALUES ('Test Audiobook');")
    conn.commit()
    conn.close()

    # 1. Run bootstrap_host_environment
    boot_res = bootstrap_host_environment(docker_root=docker_dir, data_root=data_dir)
    assert boot_res["executed"] is True

    # Verify Audiobookshelf DB was safely migrated into audiobookshelf/config/absdatabase.sqlite
    migrated_db = docker_dir / "audiobookshelf/config/absdatabase.sqlite"
    assert migrated_db.exists()

    # Verify Komf application.yml was auto-created
    assert (docker_dir / "komf/config/application.yml").exists()

    # Verify master eBook folders were created
    for sub in ["manga", "webtoon", "lightnovels", "books", "audiobooks", "cwa-ingest", "calibre-library"]:
        assert (data_dir / sub).is_dir()

    # 2. Run SQLite VACUUM maintenance & config backup
    maint_res = run_sqlite_maintenance_and_backup(docker_root=docker_dir, data_root=data_dir)
    assert maint_res["status"] == "ok"
    assert str(migrated_db) in maint_res["optimized_databases"]
    assert len(maint_res["backups_created"]) >= 2


def test_download_zip_bundle():
    res = client.post("/api/download-bundle", json={"selected_services": ["ebook-control-center", "komga", "kavita", "audiobookshelf", "komf"]})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert "docker-compose.yml" in names
    assert "compose.yaml" in names
    assert "komf/application.yml" in names


def test_safe_update_prepare_endpoint():
    res = client.post("/api/updates/safe-prepare")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready_for_safe_update"
    assert "docker compose pull" in data["command"]
