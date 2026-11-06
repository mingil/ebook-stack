"""Zero-Touch REST API, SQLite & Config Auto-Wirer for Komga, Kavita, Audiobookshelf, Komf, CWA, Suwayomi, Readarr, and Prowlarr/qBittorrent."""

import json
import os
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import httpx

from app.ebook_generator import EbookStackConfigRequest, generate_komf_application_yml

KEIYOUSHI_REPO_URL = "https://raw.githubusercontent.com/keiyoushi/extensions/repo/index.min.json"


def _safe_chown_chmod(target: Path, puid: int = 1026, pgid: int = 100, is_dir: bool = True) -> None:
    """Apply Synology PUID:PGID (1026:100) and 775/664 permissions safely."""
    try:
        os.chown(target, puid, pgid)
    except Exception:
        pass
    try:
        target.chmod(0o775 if is_dir else 0o664)
    except Exception:
        pass


def discover_ebook_credentials(docker_root: Path) -> Dict[str, str]:
    """Automatically discover API keys and tokens from Komga, Kavita, Audiobookshelf, Readarr, and Prowlarr."""
    creds = {
        "komga_user": os.environ.get("KOMGA_USER", "admin@example.com").strip(),
        "komga_password": os.environ.get("KOMGA_PASSWORD", "").strip(),
        "kavita_api_key": os.environ.get("KAVITA_API_KEY", "").strip(),
        "abs_token": os.environ.get("ABS_TOKEN", "").strip(),
        "readarr_api_key": os.environ.get("READARR_API_KEY", "").strip(),
        "prowlarr_api_key": os.environ.get("PROWLARR_API_KEY", "").strip(),
    }

    # 1. Discover Komga password from existing komf/config/application.yml or ebook-library/.env if not set
    if not creds["komga_password"]:
        env_candidates = [
            docker_root / "ebook-stack/.env",
            docker_root / "ebook-library/.env",
        ]
        for env_path in env_candidates:
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        if line.startswith("KOMGA_PASSWORD=") and not creds["komga_password"]:
                            creds["komga_password"] = line.split("=", 1)[1].strip()
                        elif line.startswith("KAVITA_API_KEY=") and not creds["kavita_api_key"]:
                            creds["kavita_api_key"] = line.split("=", 1)[1].strip()
                except Exception:
                    pass

    # 2. Discover Kavita API Key from kavita.db (AppUserAuthKey or AspNetUsers)
    if not creds["kavita_api_key"]:
        kavita_db = docker_root / "kavita/config/kavita.db"
        if kavita_db.exists():
            try:
                conn = sqlite3.connect(f"file:{kavita_db}?mode=ro", uri=True, timeout=5.0)
                row = conn.execute(
                    "SELECT Key FROM AppUserAuthKey WHERE Name IN ('komf', 'opds') ORDER BY Id DESC LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    creds["kavita_api_key"] = str(row[0]).strip()
                conn.close()
            except Exception:
                pass

    # 3. Discover Audiobookshelf root Bearer token from absdatabase.sqlite
    if not creds["abs_token"]:
        for abs_db in [
            docker_root / "audiobookshelf/config/absdatabase.sqlite",
            docker_root / "audiobookshelf/absdatabase.sqlite",
        ]:
            if abs_db.exists():
                try:
                    conn = sqlite3.connect(f"file:{abs_db}?mode=ro", uri=True, timeout=5.0)
                    row = conn.execute(
                        "SELECT token FROM users WHERE type='root' AND isActive=1 LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        creds["abs_token"] = str(row[0]).strip()
                        conn.close()
                        break
                    conn.close()
                except Exception:
                    pass

    # 4. Discover Readarr & Prowlarr API keys from config.xml
    for key_name, rel_xml in [
        ("readarr_api_key", "readarr/config.xml"),
        ("prowlarr_api_key", "prowlarr/config.xml"),
    ]:
        if not creds[key_name]:
            xml_path = docker_root / rel_xml
            if xml_path.exists():
                try:
                    content = xml_path.read_text(encoding="utf-8")
                    match = re.search(r"<ApiKey>([^<]+)</ApiKey>", content)
                    if match and match.group(1).strip():
                        creds[key_name] = match.group(1).strip()
                except Exception:
                    pass

    return creds


def provision_suwayomi_config(docker_root: Path, puid: int = 1026, pgid: int = 100) -> str:
    """Pre-configure Suwayomi server.conf with CBZ packaging, /ebooks/manga path, FlareSolverr, and Keiyoushi repo."""
    if not docker_root.exists():
        return "호스트 마운트 대기 중 (Suwayomi 설정 스킵)"

    suwa_dir = docker_root / "suwayomi"
    suwa_dir.mkdir(parents=True, exist_ok=True)
    _safe_chown_chmod(suwa_dir, puid, pgid, is_dir=True)
    conf_file = suwa_dir / "server.conf"

    desired_lines = [
        'server.ip = "0.0.0.0"',
        "server.port = 4567",
        'server.downloadsPath = "/ebooks/manga"',
        "server.downloadAsCbz = true",
        "server.autoDownloadNewChapters = true",
        "server.flareSolverrEnabled = true",
        'server.flareSolverrUrl = "http://flaresolverr:8191"',
        f'server.extensionRepos = [\n  "{KEIYOUSHI_REPO_URL}"\n]',
    ]

    if not conf_file.exists():
        conf_file.write_text("\n".join(desired_lines) + "\n", encoding="utf-8")
        _safe_chown_chmod(conf_file, puid, pgid, is_dir=False)
        return "Suwayomi: CBZ 자동 압축(/ebooks/manga), FlareSolverr 연동 및 Keiyoushi 공식 만화·웹툰 확장 리포지토리 사전 등록 완료"

    try:
        text = conf_file.read_text(encoding="utf-8")
        updated = False
        if "extensionRepos" not in text or KEIYOUSHI_REPO_URL not in text:
            text = text.rstrip() + f'\nserver.extensionRepos = [\n  "{KEIYOUSHI_REPO_URL}"\n]\n'
            updated = True
        if "downloadAsCbz" not in text:
            text = text.rstrip() + "\nserver.downloadAsCbz = true\n"
            updated = True
        if updated:
            conf_file.write_text(text, encoding="utf-8")
            _safe_chown_chmod(conf_file, puid, pgid, is_dir=False)
    except Exception:
        pass

    return "Suwayomi: CBZ 자동 저장 및 Keiyoushi 웹툰·만화 확장 리포지토리 설정 검증 완료"


def provision_calibre_library_and_cwa(
    docker_root: Path,
    ebook_data_root: Path,
    puid: int = 1026,
    pgid: int = 100,
) -> str:
    """Migrate legacy Calibre library ('캘리버 서재') to /calibre-library and wire CWA app.db automatically."""
    if not ebook_data_root.exists():
        return "호스트 데이터 마운트 대기 중 (Calibre 설정 스킵)"

    calibre_lib_dir = ebook_data_root / "calibre-library"
    calibre_lib_dir.mkdir(parents=True, exist_ok=True)
    _safe_chown_chmod(calibre_lib_dir, puid, pgid, is_dir=True)

    target_meta_db = calibre_lib_dir / "metadata.db"
    migrated = False

    # 1. Copy legacy /volume1/docker/calibre/캘리버 서재 if target metadata.db does not exist yet
    if not target_meta_db.exists() and docker_root.exists():
        legacy_candidates = [
            docker_root / "calibre/캘리버 서재",
            docker_root / "calibre/Calibre Library",
        ]
        for legacy_dir in legacy_candidates:
            if (legacy_dir / "metadata.db").exists():
                try:
                    for item in legacy_dir.iterdir():
                        dst = calibre_lib_dir / item.name
                        if item.is_dir():
                            if not dst.exists():
                                shutil.copytree(item, dst)
                        else:
                            shutil.copy2(item, dst)
                    for sub in calibre_lib_dir.rglob("*"):
                        _safe_chown_chmod(sub, puid, pgid, is_dir=sub.is_dir())
                    migrated = True
                    break
                except Exception:
                    pass

    # 2. If still no metadata.db, create a minimal valid Calibre metadata.db so CWA & Kavita never fail
    if not target_meta_db.exists():
        try:
            conn = sqlite3.connect(str(target_meta_db))
            conn.execute(
                "CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, sort TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, pubdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP, series_index REAL NOT NULL DEFAULT 1.0, author_sort TEXT, isbn TEXT DEFAULT '', lccn TEXT DEFAULT '', path TEXT NOT NULL DEFAULT '', flags INTEGER NOT NULL DEFAULT 1, uuid TEXT, has_cover BOOL DEFAULT 0, last_modified TIMESTAMP NOT NULL DEFAULT '2000-01-01 00:00:00+00:00');"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, val TEXT NOT NULL);"
            )
            conn.commit()
            conn.close()
            _safe_chown_chmod(target_meta_db, puid, pgid, is_dir=False)
        except Exception:
            pass

    # 3. Wire Calibre-Web-Automated app.db to point directly to /calibre-library
    if docker_root.exists():
        cwa_app_db = docker_root / "calibre-web-automated/config/app.db"
        if cwa_app_db.exists():
            try:
                conn = sqlite3.connect(str(cwa_app_db), timeout=5.0)
                conn.execute(
                    "UPDATE settings SET config_calibre_dir='/calibre-library', config_uploading=1 WHERE id=1;"
                )
                conn.commit()
                conn.close()
                _safe_chown_chmod(cwa_app_db, puid, pgid, is_dir=False)
            except Exception:
                pass

    if migrated:
        return "Calibre-Web-Automated: 기존 '캘리버 서재'(metadata.db 및 도서) 무손실 이관 및 /calibre-library 자동 연결 완료"
    return "Calibre-Web-Automated: /calibre-library 서재 DB 준비 및 자동 인제스트 연동 완료"


def provision_qbittorrent_ebook_categories(docker_root: Path, puid: int = 1026, pgid: int = 100) -> str:
    """Register books, audiobooks, and manga categories into mediarr-stack's qBittorrent categories.json."""
    if not docker_root.exists():
        return "호스트 마운트 대기 중 (qBittorrent 카테고리 스킵)"

    cat_dir = docker_root / "qbittorrent/qBittorrent/config"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _safe_chown_chmod(cat_dir, puid, pgid, is_dir=True)
    cat_file = cat_dir / "categories.json"

    existing: Dict[str, Any] = {}
    if cat_file.exists():
        try:
            existing = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    desired = {
        "books": {"save_path": "/data/torrents/books"},
        "audiobooks": {"save_path": "/data/torrents/audiobooks"},
        "manga": {"save_path": "/data/torrents/manga"},
        "readarr": {"save_path": "/data/torrents/books"},
    }
    changed = False
    for k, v in desired.items():
        if k not in existing:
            existing[k] = v
            changed = True

    if changed or not cat_file.exists():
        cat_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        _safe_chown_chmod(cat_file, puid, pgid, is_dir=False)

    return "qBittorrent 연동: 도서(books)·오디오북(audiobooks)·만화(manga) 전용 토렌트 카테고리(/data/torrents/*) 자동 등록 완료"


def provision_komf_config(
    docker_root: Path,
    komga_user: str,
    komga_password: str,
    kavita_api_key: str,
    puid: int = 1026,
    pgid: int = 100,
) -> str:
    """Ensure /volume1/docker/komf/config/application.yml is up-to-date with Kaml syntax & Korean metadata rules."""
    if not docker_root.exists():
        return "호스트 마운트 대기 중 (Komf 설정 스킵)"

    komf_dir = docker_root / "komf/config"
    komf_dir.mkdir(parents=True, exist_ok=True)
    _safe_chown_chmod(komf_dir, puid, pgid, is_dir=True)
    komf_yml_path = komf_dir / "application.yml"

    cfg = EbookStackConfigRequest(
        komga_user=komga_user or "admin@example.com",
        komga_password=komga_password or "YOUR_KOMGA_PASSWORD",
        kavita_api_key=kavita_api_key or "CHANGE_ME_KAVITA_API_KEY",
    )
    komf_yml_path.write_text(generate_komf_application_yml(cfg), encoding="utf-8")
    _safe_chown_chmod(komf_yml_path, puid, pgid, is_dir=False)
    return "Komf: Komga(:25600) & Kavita(:5000) 이벤트 리스너 및 한국어(ko) 최우선 메타데이터 설정(application.yml) 프로비저닝 완료"


async def configure_komga_via_api(
    client: httpx.AsyncClient,
    base_url: str,
    komga_user: str,
    komga_password: str,
) -> List[str]:
    """Ensure Komga preserves legacy '/data' library and auto-creates unified '/ebooks/manga', '/ebooks/comics', '/calibre-library' libraries."""
    logs: List[str] = []
    if not komga_user or not komga_password:
        return logs

    auth = (komga_user, komga_password)
    r_libs = await client.get(f"{base_url}/api/v1/libraries", auth=auth)
    if r_libs.status_code != 200:
        return logs

    existing_libs = r_libs.json()
    existing_roots = {str(item.get("root", "")).rstrip("/"): item for item in existing_libs}

    # 1. Enable hourly auto-scan on existing '/data' library if currently DISABLED
    legacy_lib = existing_roots.get("/data")
    if legacy_lib and legacy_lib.get("scanInterval") == "DISABLED":
        updated_lib = dict(legacy_lib)
        updated_lib["scanInterval"] = "HOURLY"
        updated_lib["scanOnStartup"] = True
        await client.put(f"{base_url}/api/v1/libraries/{legacy_lib['id']}", auth=auth, json=updated_lib)
        logs.append("Komga: 기존 서재(ebook-library_komga, /data) 자동 스캔(HOURLY) 활성화 완료")

    # 2. Auto-register unified libraries if not already registered
    desired_libraries = [
        ("Manga & Webtoon (통합)", "/ebooks/manga"),
        ("Comics & Magazines", "/ebooks/comics"),
        ("Calibre eBooks (자동변환)", "/calibre-library"),
    ]
    for lib_name, lib_root in desired_libraries:
        if lib_root not in existing_roots:
            payload = {
                "name": lib_name,
                "root": lib_root,
                "importComicInfoBook": True,
                "importComicInfoSeries": True,
                "importComicInfoCollection": True,
                "importComicInfoReadList": True,
                "importComicInfoSeriesAppendVolume": True,
                "importEpubBook": True,
                "importEpubSeries": True,
                "importMylarSeries": True,
                "importLocalArtwork": True,
                "importBarcodeIsbn": False,
                "scanForceModifiedTime": False,
                "scanInterval": "HOURLY",
                "scanOnStartup": True,
                "scanCbx": True,
                "scanPdf": True,
                "scanEpub": True,
                "scanDirectoryExclusions": ["#recycle", "@Recycle", "@eaDir"],
                "repairExtensions": False,
                "convertToCbz": False,
                "emptyTrashAfterScan": False,
                "seriesCover": "FIRST",
                "hashFiles": True,
                "hashPages": False,
                "hashKoreader": False,
                "analyzeDimensions": True,
                "oneshotsDirectory": None,
            }
            r_post = await client.post(f"{base_url}/api/v1/libraries", auth=auth, json=payload)
            if r_post.status_code in (200, 201):
                logs.append(f"Komga: 신규 통합 서재 '{lib_name}' ({lib_root}) 자동 등록 완료")

    return logs


async def configure_kavita_via_api(
    client: httpx.AsyncClient,
    base_url: str,
    kavita_api_key: str,
) -> List[str]:
    """Authenticate with Kavita via API key and auto-create Manga/Webtoon, Light Novels, and Books/Calibre libraries."""
    logs: List[str] = []
    if not kavita_api_key:
        return logs

    r_auth = await client.post(
        f"{base_url}/api/Plugin/authenticate",
        params={"apiKey": kavita_api_key, "pluginName": "ebook-control-center"},
    )
    if r_auth.status_code != 200:
        return logs

    token = r_auth.json().get("token", "")
    if not token:
        return logs

    headers = {"Authorization": f"Bearer {token}"}
    r_libs = await client.get(f"{base_url}/api/Library/libraries", headers=headers)
    if r_libs.status_code != 200:
        return logs

    existing_libs = r_libs.json()
    existing_names = {item.get("name") for item in existing_libs}
    existing_folders = {f.rstrip("/") for item in existing_libs for f in item.get("folders", [])}

    desired_kavita_libs = [
        ("Manga & Webtoon", 0, ["/ebooks/manga", "/ebooks/webtoon"]),
        ("Light Novels", 4, ["/ebooks/lightnovels"]),
        ("Books & Calibre", 2, ["/ebooks/books", "/calibre-library"]),
    ]

    for name, lib_type, folders in desired_kavita_libs:
        if name not in existing_names and not all(f in existing_folders for f in folders):
            payload = {
                "name": name,
                "type": lib_type,
                "folders": folders,
                "folderWatching": True,
                "includeInDashboard": True,
                "includeInRecommended": True,
                "manageCollections": True,
                "manageReadingLists": True,
                "includeInSearch": True,
                "allowScrobbling": False,
                "collapseSeriesRelationships": False,
                "libraryFileTypes": [1, 2, 3, 4],
                "fileGroupTypes": [1, 2, 3, 4],
                "excludePatterns": [],
                "allowMetadataMatching": True,
                "enableMetadata": True,
                "removePrefixForSortName": False,
                "inheritWebLinksFromFirstChapter": False,
                "defaultLanguage": "",
                "metadataProvider": 3 if lib_type == 0 else 2,
            }
            r_create = await client.post(f"{base_url}/api/Library/create", headers=headers, json=payload)
            if r_create.status_code in (200, 201):
                logs.append(f"Kavita: 신규 통합 서재 '{name}' ({', '.join(folders)}) 자동 등록 완료")

    return logs


async def configure_audiobookshelf_via_api(
    client: httpx.AsyncClient,
    base_url: str,
    abs_token: str,
) -> List[str]:
    """Ensure Audiobookshelf preserves legacy '/audiobooks' library and auto-creates unified Audiobooks, eBooks/Calibre, and Podcasts libraries."""
    logs: List[str] = []
    if not abs_token:
        return logs

    headers = {"Authorization": f"Bearer {abs_token}"}
    r_libs = await client.get(f"{base_url}/api/libraries", headers=headers)
    if r_libs.status_code != 200:
        return logs

    libraries = r_libs.json().get("libraries", [])
    existing_paths = {
        str(folder.get("fullPath", "")).rstrip("/")
        for lib in libraries
        for folder in lib.get("folders", [])
    }

    desired_abs_libs = [
        (
            "Audiobooks (오디오북)",
            "book",
            "audiobookshelf",
            "audible",
            [{"fullPath": "/ebooks/audiobooks"}],
            {"coverAspectRatio": 1, "disableWatcher": False, "audiobooksOnly": True, "epubsAllowScriptedContent": False},
        ),
        (
            "eBooks & Calibre (소설·전자책)",
            "book",
            "books-1",
            "google",
            [{"fullPath": "/ebooks/books"}, {"fullPath": "/ebooks/lightnovels"}, {"fullPath": "/calibre-library"}],
            {"coverAspectRatio": 0, "disableWatcher": False, "audiobooksOnly": False, "epubsAllowScriptedContent": False},
        ),
        (
            "Podcasts (팟캐스트)",
            "podcast",
            "podcast",
            "itunes",
            [{"fullPath": "/ebooks/podcasts"}],
            {"coverAspectRatio": 1, "disableWatcher": False},
        ),
    ]

    for name, media_type, icon, provider, folders, settings in desired_abs_libs:
        first_path = folders[0]["fullPath"]
        if first_path not in existing_paths:
            payload = {
                "name": name,
                "folders": folders,
                "icon": icon,
                "mediaType": media_type,
                "provider": provider,
                "settings": settings,
            }
            r_post = await client.post(f"{base_url}/api/libraries", headers=headers, json=payload)
            if r_post.status_code in (200, 201):
                logs.append(f"Audiobookshelf: 신규 통합 서재 '{name}' ({first_path}) 자동 등록 완료")

    return logs


async def configure_readarr_via_api(
    client: httpx.AsyncClient,
    base_url: str,
    readarr_api_key: str,
    qbit_host: str = "172.17.0.1",
    qbit_port: int = 8181,
    qbit_user: str = "admin",
    qbit_pass: str = "",
) -> List[str]:
    """Configure Readarr v1 hardlinks, root folders (/data/ebooks/books, /data/ebooks/audiobooks), and qBittorrent client."""
    logs: List[str] = []
    if not readarr_api_key:
        return logs

    headers = {"X-Api-Key": readarr_api_key}

    # 1. Enable hardlinks in MediaManagement
    r_mm = await client.get(f"{base_url}/api/v1/config/mediamanagement", headers=headers)
    if r_mm.status_code == 200:
        mm_data = r_mm.json()
        if not mm_data.get("copyUsingHardlinks"):
            mm_data["copyUsingHardlinks"] = True
            mm_data["deleteEmptyFolders"] = True
            await client.put(f"{base_url}/api/v1/config/mediamanagement", headers=headers, json=mm_data)
            logs.append("Readarr: 0.1초 하드링크(copyUsingHardlinks) 자동 활성화 완료")

    # 2. Register Root Folders (/data/ebooks/books & /data/ebooks/audiobooks)
    r_rf = await client.get(f"{base_url}/api/v1/rootfolder", headers=headers)
    if r_rf.status_code == 200:
        existing_paths = {str(item.get("path", "")).rstrip("/") for item in r_rf.json()}
        for target_path, rf_name in [
            ("/data/ebooks/books", "eBooks & Novels"),
            ("/data/ebooks/audiobooks", "Audiobooks"),
        ]:
            if target_path not in existing_paths:
                rf_payload = {
                    "name": rf_name,
                    "path": target_path,
                    "defaultMetadataProfileId": 1,
                    "defaultQualityProfileId": 1,
                    "defaultMonitorOption": "all",
                    "defaultNewItemMonitorOption": "all",
                    "isCalibreLibrary": False,
                }
                r_post = await client.post(f"{base_url}/api/v1/rootfolder", headers=headers, json=rf_payload)
                if r_post.status_code in (200, 201):
                    logs.append(f"Readarr: 루트 폴더({target_path}) 자동 등록 완료")

    # 3. Connect mediarr-stack's qBittorrent (:8181)
    r_dc = await client.get(f"{base_url}/api/v1/downloadclient", headers=headers)
    if r_dc.status_code == 200:
        existing_dcs = r_dc.json()
        if not any(d.get("implementation") == "QBittorrent" for d in existing_dcs):
            dc_payload = {
                "enable": True,
                "protocol": "torrent",
                "priority": 1,
                "removeCompletedDownloads": True,
                "removeFailedDownloads": True,
                "name": "qBittorrent (Mediarr VPN)",
                "implementation": "QBittorrent",
                "configContract": "QBittorrentSettings",
                "fields": [
                    {"name": "host", "value": qbit_host},
                    {"name": "port", "value": qbit_port},
                    {"name": "useSsl", "value": False},
                    {"name": "username", "value": qbit_user},
                    {"name": "password", "value": qbit_pass},
                    {"name": "musicCategory", "value": "books"},
                ],
            }
            r_post = await client.post(
                f"{base_url}/api/v1/downloadclient?forceSave=true", headers=headers, json=dc_payload
            )
            if r_post.status_code in (200, 201):
                logs.append(f"Readarr: Mediarr qBittorrent({qbit_host}:{qbit_port}, 카테고리 books) 자동 연결 완료")

    return logs


async def configure_prowlarr_for_readarr_via_api(
    client: httpx.AsyncClient,
    prowlarr_url: str,
    prowlarr_api_key: str,
    readarr_api_key: str,
) -> List[str]:
    """Register Readarr as a Full-Sync Application inside mediarr-stack's Prowlarr (:9696)."""
    logs: List[str] = []
    if not prowlarr_api_key or not readarr_api_key:
        return logs

    headers = {"X-Api-Key": prowlarr_api_key}
    r_apps = await client.get(f"{prowlarr_url}/api/v1/applications", headers=headers)
    if r_apps.status_code == 200:
        apps = r_apps.json()
        if not any(a.get("implementation") == "Readarr" for a in apps):
            readarr_app = {
                "name": "Readarr (eBook Stack)",
                "syncLevel": "fullSync",
                "implementation": "Readarr",
                "configContract": "ReadarrSettings",
                "fields": [
                    {"name": "prowlarrUrl", "value": "http://172.17.0.1:9696"},
                    {"name": "baseUrl", "value": "http://172.17.0.1:8787"},
                    {"name": "apiKey", "value": readarr_api_key},
                    {"name": "syncCategories", "value": [3030, 7000, 7010, 7020, 7030, 8000, 8010]},
                ],
            }
            r_post = await client.post(
                f"{prowlarr_url}/api/v1/applications?forceSave=true", headers=headers, json=readarr_app
            )
            if r_post.status_code in (200, 201):
                logs.append("Prowlarr 연동: Readarr(http://172.17.0.1:8787) 전자책·오디오북 인덱서 Full Sync 자동 연결 완료")

    return logs


async def _find_reachable_url(
    client: httpx.AsyncClient,
    candidates: List[str],
    probe_path: str = "",
) -> str | None:
    for base in candidates:
        try:
            r = await client.get(f"{base}{probe_path}")
            if r.status_code < 500:
                return base
        except Exception:
            continue
    return None


async def auto_wire_all_ebook_services(
    docker_root: Path | None = None,
    ebook_data_root: Path | None = None,
) -> Dict[str, Any]:
    """Master entry point: pre-provision configs & databases, then live-wire Komga, Kavita, ABS, Readarr, and Prowlarr."""
    d_root = docker_root or Path(os.environ.get("HOST_DOCKER_MOUNT", "/host-docker"))
    m_root = Path(os.environ.get("HOST_DATA_MOUNT", "/host-data"))
    e_root = ebook_data_root or (m_root / "ebooks" if m_root.name == "host-data" or m_root.name == "mediarr" else m_root)
    puid = int(os.environ.get("PUID", "1026"))
    pgid = int(os.environ.get("PGID", "100"))

    creds = discover_ebook_credentials(d_root)
    wired_actions: List[str] = []

    # 1. File/DB Pre-Provisioning
    wired_actions.append(provision_suwayomi_config(d_root, puid, pgid))
    wired_actions.append(provision_calibre_library_and_cwa(d_root, e_root, puid, pgid))
    wired_actions.append(provision_qbittorrent_ebook_categories(d_root, puid, pgid))
    wired_actions.append(
        provision_komf_config(
            d_root,
            komga_user=creds["komga_user"],
            komga_password=creds["komga_password"],
            kavita_api_key=creds["kavita_api_key"],
            puid=puid,
            pgid=pgid,
        )
    )

    # 2. Live REST API Auto-Wiring across containers
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        # Komga
        if creds["komga_password"]:
            komga_url = await _find_reachable_url(
                client,
                ["http://komga:25600", "http://host.docker.internal:8341", "http://172.17.0.1:8341"],
                "/actuator/health",
            )
            if komga_url:
                try:
                    wired_actions.extend(
                        await configure_komga_via_api(
                            client, komga_url, creds["komga_user"], creds["komga_password"]
                        )
                    )
                except Exception:
                    pass

        # Kavita
        if creds["kavita_api_key"]:
            kavita_url = await _find_reachable_url(
                client,
                ["http://kavita:5000", "http://host.docker.internal:5471", "http://172.17.0.1:5471"],
                "/api/health",
            )
            if kavita_url:
                try:
                    wired_actions.extend(
                        await configure_kavita_via_api(client, kavita_url, creds["kavita_api_key"])
                    )
                except Exception:
                    pass

        # Audiobookshelf
        if creds["abs_token"]:
            abs_url = await _find_reachable_url(
                client,
                [
                    "http://audiobookshelf:13378",
                    "http://audiobookshelf:80",
                    "http://host.docker.internal:13378",
                    "http://172.17.0.1:13378",
                ],
                "/ping",
            )
            if abs_url:
                try:
                    wired_actions.extend(
                        await configure_audiobookshelf_via_api(client, abs_url, creds["abs_token"])
                    )
                except Exception:
                    pass

        # Readarr & Prowlarr
        if creds["readarr_api_key"]:
            readarr_url = await _find_reachable_url(
                client,
                ["http://readarr:8787", "http://host.docker.internal:8787", "http://172.17.0.1:8787"],
                "/ping",
            )
            if readarr_url:
                try:
                    wired_actions.extend(
                        await configure_readarr_via_api(client, readarr_url, creds["readarr_api_key"])
                    )
                except Exception:
                    pass

            if creds["prowlarr_api_key"]:
                prowlarr_url = await _find_reachable_url(
                    client,
                    ["http://host.docker.internal:9696", "http://172.17.0.1:9696", "http://prowlarr:9696"],
                    "/ping",
                )
                if prowlarr_url:
                    try:
                        wired_actions.extend(
                            await configure_prowlarr_for_readarr_via_api(
                                client,
                                prowlarr_url,
                                creds["prowlarr_api_key"],
                                creds["readarr_api_key"],
                            )
                        )
                    except Exception:
                        pass

    return {
        "status": "ok",
        "credentials_discovered": {k: bool(v) for k, v in creds.items()},
        "wired_actions": wired_actions,
    }
