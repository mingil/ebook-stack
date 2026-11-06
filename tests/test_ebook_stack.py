"""Automated Unit & Integration Tests for the Unified eBook Stack (ebook-stack v1.3.0)."""

import asyncio
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from app.auto_wirer import (
    KEIYOUSHI_REPO_URL,
    configure_audiobookshelf_via_api,
    configure_kavita_via_api,
    configure_komga_via_api,
    configure_prowlarr_for_readarr_via_api,
    configure_readarr_via_api,
    provision_calibre_library_and_cwa,
    provision_komf_config,
    provision_qbittorrent_ebook_categories,
    provision_suwayomi_config,
)
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
    assert data["version"] == "1.3.0"
    assert data["watchtower_service_duplicated"] is False
    assert data["watchtower_labels_enabled"] is True


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
        "nas_ip": "192.168.0.100",
        "puid": 1026,
        "pgid": 100,
        "tz": "Asia/Seoul",
        "docker_root": "/volume1/docker",
        "ebook_data_root": "/volume1/mediarr/ebooks",
        "container_prefix": "ebook-",
        "keep_legacy_mounts": True,
        "control_port": 8586,
        "komga_port": 8341,
        "kavita_port": 5471,
        "audiobookshelf_port": 13378,
        "komf_port": 8085,
        "flaresolverr_port": 8192,
    }
    res = client.post("/api/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    compose_text = data["docker_compose"]

    assert "marius" not in compose_text.lower()

    parsed = yaml.safe_load(compose_text)
    assert "ebook_net" in parsed["networks"]
    services = parsed["services"]
    assert "watchtower" not in services

    # 0. Verify integrated project image (ebook-control-center) & existing Watchtower labels
    ctrl = services["ebook-control-center"]
    assert ctrl["image"] == "kimmingil/ebook-stack:latest"
    assert "8586:8500" in ctrl["ports"]
    assert "/volume1/docker:/host-docker:rw" in ctrl["volumes"]
    assert "/volume1/mediarr/ebooks:/host-data:rw" in ctrl["volumes"]
    for svc_name, svc_def in services.items():
        assert svc_def["labels"]["com.centurylinklabs.watchtower.enable"] == "true", svc_name
    assert services["komf"]["labels"]["com.centurylinklabs.watchtower.depends-on"] == "komga,kavita"

    # 1. Verify legacy SQLite DB mount preservation (/data for Komga, /manga for Kavita, /audiobooks for ABS)
    assert "/volume1/docker/komga/data:/data:rw" in services["komga"]["volumes"]
    assert "/volume1/docker/kavita/data:/manga:rw" in services["kavita"]["volumes"]
    assert "/volume1/docker/audiobookshelf/audiobooks:/audiobooks:rw" in services["audiobookshelf"]["volumes"]

    # 2. Organic Pipeline 1: CWA Downloader (Shelfmark) -> CWA -> Shared /calibre-library across Kavita, ABS, Komga
    assert services["cwa-book-downloader"]["image"] == "ghcr.io/calibrain/calibre-web-automated-book-downloader:latest"
    assert "/volume1/mediarr/ebooks/cwa-ingest:/cwa-book-ingest:rw" in services["cwa-book-downloader"]["volumes"]
    assert "/volume1/mediarr/ebooks/cwa-ingest:/books:rw" in services["cwa-book-downloader"]["volumes"]
    assert "/volume1/docker/cwa-book-downloader/config:/config:rw" in services["cwa-book-downloader"]["volumes"]
    assert "/volume1/mediarr/ebooks/cwa-ingest:/cwa-book-ingest:rw" in services["calibre-web-automated"]["volumes"]
    for viewer in ["calibre-web-automated", "kavita", "audiobookshelf", "komga"]:
        assert "/volume1/mediarr/ebooks/calibre-library:/calibre-library:rw" in services[viewer]["volumes"]

    # Verify Readarr uses verified :0.4.18-develop image, mounts /volume1/mediarr:/data:rw for 0.1s hardlinks, and FlareSolverr uses 8192
    assert services["readarr"]["image"] == "lscr.io/linuxserver/readarr:0.4.18-develop"
    assert "/volume1/mediarr:/data:rw" in services["readarr"]["volumes"]
    assert "8192:8191" in services["flaresolverr"]["ports"]
    for svc_name, svc_def in services.items():
        if svc_name != "ebook-control-center":
            assert svc_def["depends_on"]["ebook-control-center"]["condition"] == "service_healthy", svc_name

    # 3. Organic Pipeline 2: Suwayomi JVM flags -> CBZ to /data/manga + FlareSolverr URL
    suwayomi_java = services["suwayomi"]["environment"]["JAVA_TOOL_OPTIONS"]
    assert "-Dsuwayomi.tachidesk.config.server.downloadAsCbz=true" in suwayomi_java
    assert "-Dsuwayomi.tachidesk.config.server.downloadsPath=/data/manga" in suwayomi_java
    assert "-Dsuwayomi.tachidesk.config.server.flareSolverrUrl=http://flaresolverr:8191" in suwayomi_java

    # 4. Organic Pipeline 3: Audiobookshelf nested mount fix & Komf service_healthy wait
    abs_vols = services["audiobookshelf"]["volumes"]
    assert "/volume1/docker/audiobookshelf/config:/config:rw" in abs_vols
    assert "/volume1/docker/audiobookshelf:/config:rw" not in abs_vols
    komf_dep = services["komf"]["depends_on"]
    assert komf_dep["komga"]["condition"] == "service_healthy"
    assert komf_dep["kavita"]["condition"] == "service_healthy"

    # 5. Verify Kaml-compatible Komf application.yml (no unparsed ${...} placeholders)
    komf_yml_text = data["komf_application_yml"]
    assert "${" not in komf_yml_text
    komf_parsed = yaml.safe_load(komf_yml_text)
    assert komf_parsed["komga"]["baseUri"] == "http://komga:25600"
    assert komf_parsed["kavita"]["baseUri"] == "http://kavita:5000"


def test_runtime_bootstrap_calibre_migration_and_sqlite_maintenance(tmp_path: Path):
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

    # Simulate legacy Calibre library ('캘리버 서재')
    calibre_legacy = docker_dir / "calibre/캘리버 서재"
    calibre_legacy.mkdir(parents=True)
    calibre_db = calibre_legacy / "metadata.db"
    c_conn = sqlite3.connect(str(calibre_db))
    c_conn.execute("CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT);")
    c_conn.execute("INSERT INTO books (title) VALUES ('Dune');")
    c_conn.commit()
    c_conn.close()

    # 1. Run bootstrap_host_environment
    boot_res = bootstrap_host_environment(docker_root=docker_dir, data_root=data_dir)
    assert boot_res["executed"] is True

    # Verify Audiobookshelf DB was safely migrated into audiobookshelf/config/absdatabase.sqlite
    migrated_db = docker_dir / "audiobookshelf/config/absdatabase.sqlite"
    assert migrated_db.exists()

    # Verify legacy Calibre library was migrated into data_dir / calibre-library / metadata.db
    migrated_calibre_db = data_dir / "calibre-library/metadata.db"
    assert migrated_calibre_db.exists()

    # Verify Komf application.yml and Suwayomi server.conf were auto-created
    assert (docker_dir / "komf/config/application.yml").exists()
    suwa_conf = (docker_dir / "suwayomi/server.conf").read_text(encoding="utf-8")
    assert KEIYOUSHI_REPO_URL in suwa_conf

    # Verify master eBook folders were created
    for sub in ["manga", "webtoon", "lightnovels", "books", "audiobooks", "cwa-ingest", "calibre-library"]:
        assert (data_dir / sub).is_dir()

    # 2. Run SQLite VACUUM maintenance & config backup
    maint_res = run_sqlite_maintenance_and_backup(docker_root=docker_dir, data_root=data_dir)
    assert maint_res["status"] == "ok"
    assert str(migrated_db) in maint_res["optimized_databases"]
    assert len(maint_res["backups_created"]) >= 2


def test_zero_touch_auto_wirer_rest_apis(tmp_path: Path):
    docker_dir = tmp_path / "docker"
    ebook_dir = tmp_path / "ebooks"
    docker_dir.mkdir()
    ebook_dir.mkdir()

    # Pre-provision files
    assert "Keiyoushi" in provision_suwayomi_config(docker_dir)
    assert "Calibre" in provision_calibre_library_and_cwa(docker_dir, ebook_dir)
    assert "qBittorrent" in provision_qbittorrent_ebook_categories(docker_dir)
    assert "Komf" in provision_komf_config(docker_dir, "user@test.com", "pw", "kavita_key")

    cats = json.loads((docker_dir / "qbittorrent/qBittorrent/config/categories.json").read_text(encoding="utf-8"))
    assert cats["books"]["save_path"] == "/data/torrents/books"
    assert cats["audiobooks"]["save_path"] == "/data/torrents/audiobooks"
    assert cats["manga"]["save_path"] == "/data/torrents/manga"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET":
            if path == "/api/v1/libraries":
                return httpx.Response(
                    200,
                    json=[{"id": "LIB1", "name": "ebook-library_komga", "root": "/data", "scanInterval": "DISABLED"}],
                )
            if path == "/api/Library/libraries":
                return httpx.Response(
                    200,
                    json=[{"id": 1, "name": "ebook-library_kavita", "type": 2, "folders": ["/manga"]}],
                )
            if path == "/api/libraries":
                return httpx.Response(
                    200,
                    json={"libraries": [{"id": "ABS1", "name": "ebook-library", "folders": [{"fullPath": "/audiobooks"}]}]},
                )
            if path == "/api/v1/config/mediamanagement":
                return httpx.Response(200, json={"copyUsingHardlinks": False})
            return httpx.Response(200, json=[])
        if path == "/api/Plugin/authenticate":
            return httpx.Response(200, json={"token": "TEST_KAVITA_JWT"})
        return httpx.Response(201, json={"id": 1})

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as mock_client:
            k_logs = await configure_komga_via_api(mock_client, "http://komga:25600", "user", "pass")
            kv_logs = await configure_kavita_via_api(mock_client, "http://kavita:5000", "kav_key")
            abs_logs = await configure_audiobookshelf_via_api(mock_client, "http://audiobookshelf:80", "abs_tok")
            rd_logs = await configure_readarr_via_api(mock_client, "http://readarr:8787", "rd_key")
            pr_logs = await configure_prowlarr_for_readarr_via_api(
                mock_client, "http://prowlarr:9696", "pr_key", "rd_key"
            )
            return k_logs, kv_logs, abs_logs, rd_logs, pr_logs

    k_logs, kv_logs, abs_logs, rd_logs, pr_logs = asyncio.run(_run())
    assert len(k_logs) == 4  # 1 legacy scanInterval upgrade + 3 new libraries
    assert len(kv_logs) == 3  # 3 new Kavita libraries
    assert len(abs_logs) == 3  # 3 new ABS libraries
    assert len(rd_logs) == 4  # Hardlinks + 2 RootFolders + qBittorrent client
    assert len(pr_logs) == 1  # Readarr FullSync in Prowlarr


def test_control_center_basic_auth_protection(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CONTROL_CENTER_USER", "director")
    monkeypatch.setenv("CONTROL_CENTER_PASSWORD", "secret123")

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/diagnosis").status_code == 401
    assert client.get("/api/diagnosis", auth=("director", "secret123")).status_code == 200


def test_download_zip_bundle():
    res = client.post(
        "/api/download-bundle",
        json={"selected_services": ["ebook-control-center", "komga", "kavita", "audiobookshelf", "komf"]},
    )
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
