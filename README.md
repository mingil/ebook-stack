# 📚 Ultimate Synology eBook, Manga, Webtoon & Audiobook Stack (`ebook-stack` v1.3.0)

시놀로지 NAS(**DS920+** 및 DSM 7.2 전 모델)와 모든 홈서버 환경을 위해 **단일 프로젝트(`ebook-stack`)와 단일 `docker-compose.yml` 안에서 전용 관제 도커 이미지(`kimmingil/ebook-stack:latest`)와 10대 eBook 서버가 100% 유기적으로 연동·관리되는 현존 최고 수준의 올인원 전자책·만화·웹툰·오디오북 생태계**입니다.

> **핵심 설계 원칙 (`mediarr-stack`과 100% 동일 수준의 아키텍처 & 완벽 공존):**
> - **기존 서재 DB(`Komga`, `Kavita`, `Audiobookshelf`, `캘리버 서재`) 100% 무손실 승계:** 기존에 사용하시던 Komga(`/data` 서재), Kavita(`/manga` 서재), Audiobookshelf(`/audiobooks` 서재) 마운트 경로를 원래 위치 그대로 유지하여 기존 도서·만화·독서 진행률을 단 1바이트도 유실하지 않으며, 기존 `/volume1/docker/calibre/캘리버 서재`도 `/calibre-library`로 자동 무손실 이관합니다.
> - **Zero-Touch REST API & DB Auto-Wirer (`app/auto_wirer.py`) 내장:** 컨테이너만 띄우면 `ebook-control-center(:8586)`가 부팅 직후부터 Komga·Kavita·Audiobookshelf·CWA·Suwayomi·Readarr·Prowlarr의 REST API와 설정 파일을 자동으로 배선하여, **수동 초기 설정 없이도 모든 통합 서재(`/ebooks/*`, `/calibre-library`)와 Keiyoushi 만화·웹툰 확장 리포지토리가 자동 등록**됩니다.
> - **`mediarr-stack`과 단일 볼륨(`/volume1/mediarr`) 0.1초 하드링크 & 포트 충돌 제로화:** `mediarr-stack`의 `qBittorrent(:8181)` 및 `Prowlarr(:9696)`와 자동 연동되며, `/volume1/mediarr` 단일 볼륨을 공유해 대용량 오디오북·전자책 세트를 **복사 시간 0.1초, 추가 디스크 소모 0바이트(하드링크)**로 서재에 연결합니다.
> - **내장 24시간 주기 SQLite 무잠금(`WAL`) DB 닥터 & 기존 Watchtower 100% 호환:** 11개 전 컨테이너에 Watchtower 라벨(`enable=true` & `depends-on`)을 탑재했으며, 24시간마다 SQLite `WAL` 체크포인트·`VACUUM` 최적화와 30일 자동 백업을 수행합니다.

---

## 🩺 기존 `ebook-library` 6대 근본 원인 진단 및 완치 내역

1. **[CRITICAL] 기존 SQLite DB 서재 경로(`/data`, `/manga`, `/audiobooks`) 및 `'캘리버 서재'` 100% 무손실 보존**
   - 기존 마운트 경로를 그대로 유지하여 기존 등록 도서(`호빗`, `삼체`, `토지`, `원피스`, `해리포터`, `듄` 등)를 완벽히 보호하고, 신규 통합 서재(`/ebooks/*`, `/calibre-library`)는 REST API로 자동 추가했습니다.
2. **[CRITICAL] Audiobookshelf 중첩(Nested) 볼륨 마운트 버그 완치**
   - 상위 폴더(`/volume1/docker/audiobookshelf:/config`) 중복 마운트를 `/volume1/docker/audiobookshelf/config:/config`로 분리하고 기존 `absdatabase.sqlite`와 `migrations`를 자동 무손실 이관했습니다.
3. **[CRITICAL] `mediarr-stack` 포트 충돌 제로화(`:8586`, `:8192`) 및 `/volume1/mediarr` 0.1초 하드링크 통합**
   - `mediarr-control-center(:8585)` 및 `mediarr-flaresolverr(:8191)`와 충돌하지 않도록 호스트 포트를 `:8586` 및 `:8192`(내부망은 `flaresolverr:8191`)로 분리하고 `/volume1/mediarr` 볼륨을 통합했습니다.
4. **[HIGH] 전 컨테이너 시놀로지 표준 `PUID=1026` / `PGID=100` 권한 통일 및 자동 자가 치유**
5. **[HIGH] Zero-Touch REST API Auto-Wirer (`app/auto_wirer.py`) 탑재**
   - Komga·Kavita·Audiobookshelf 신규 서재 자동 생성, CWA `app.db` 직결, Suwayomi `Keiyoushi` 확장 리포지토리 사전 등록, Readarr↔Prowlarr↔qBittorrent 자동 배선을 수행합니다.
6. **[HIGH] Komga·Kavita `service_healthy` 부팅 순서 보장 및 Komf Kaml 파서 호환 한국어(`ko`) 메타데이터 자동 주입**

---

## 🔗 4대 핵심 유기적 자동화 파이프라인

1. **[파이프라인 1] 웹 도서 원클릭 검색 ➔ 자동 EPUB/KEPUB 변환 ➔ 4대 뷰어 동시 즉시 반영**
   - `FlareSolverr(:8192)` ➔ `CWA Book Downloader(:8084)` ➔ `[/cwa-book-ingest]` ➔ `Calibre-Web-Automated(:8083)` ➔ `[/calibre-library]` ➔ **`Kavita(:5471)` & `Audiobookshelf(:13378)` & `Komga(:8341)` 동시 공유**
2. **[파이프라인 2] 연재 만화·웹툰 자동 수집(Keiyoushi 내장) ➔ CBZ 압축 저장 ➔ 한국어 메타데이터 자동 주입**
   - `FlareSolverr(:8192)` ➔ `Suwayomi(:4567)` ➔ `[/ebooks/manga (*.cbz)]` ➔ `Komga(:8341)` & `Kavita(:5471)` ➔ `Komf(:8085)`
3. **[파이프라인 3] `mediarr-stack` 연동 신간 토렌트 수집 ➔ 0.1초 하드링크 서재 등록**
   - `Mediarr Prowlarr(:9696) & qBittorrent(:8181)` ➔ `Readarr(:8787)` ➔ `[/volume1/mediarr/ebooks/{books,audiobooks}]`
4. **[파이프라인 4] 통합 관제 센터(`ebook-control-center`) Zero-Touch 자동 프로비저닝 & 24h DB 닥터**
   - `ebook-control-center(:8586, kimmingil/ebook-stack:latest)` 구동 즉시 전체 폴더 생성, DB 무손실 분리·이관, 전 서버 REST API 서재 자동 배선 및 SQLite `WAL` 최적화를 수행합니다.

---

## 📦 단일 프로젝트(`docker-compose.yml`) 전체 컨테이너 구성 (총 11대 · Watchtower 제외)

| 번호 | 서비스 | 컨테이너 이름 | 호스트 포트 | 핵심 역할 |
| :---: | :--- | :--- | :---: | :--- |
| 0 | **eBook Control Center** | `ebook-control-center` | `8586` | 본 프로젝트 도커 이미지(`kimmingil/ebook-stack:latest`) — 폴더/DB 초기화 · REST API 자동 배선 · 통합 관제 |
| 1 | **Komga** | `ebook-komga` | `8341` | 만화·웹툰·단행본(CBZ/CBR/PDF/EPUB) 메인 서버 (기존 `/data` 서재 승계 + G1GC 3GB 최적화) |
| 2 | **Kavita** | `ebook-kavita` | `5471` | 라이트노벨(EPUB)·소설·만화 초고속 하이브리드 웹 리더 (기존 `/manga` 보존 + 신규 서재 자동 생성) |
| 3 | **Audiobookshelf** | `ebook-audiobookshelf` | `13378` | 오디오북(M4B/MP3)·팟캐스트·전자책 스트리밍 & 이어듣기 동기화 (중첩 볼륨 분리 완료) |
| 4 | **Komf** | `ebook-komf` | `8085` | Komga & Kavita 만화·웹툰·라노벨 한국어(`ko`) 메타데이터/표지 자동 수집 엔진 |
| 5 | **Calibre-Web-Automated** | `ebook-calibre-web` | `8083` | 기존 캘리버 서재 승계 · 전자책 자동 EPUB/KEPUB 변환 · Kobo 무선 동기화 · Kindle 전송 |
| 6 | **CWA Book Downloader** | `ebook-book-downloader` | `8084` | 웹에서 도서 검색 후 클릭 한 번으로 다운로드 → CWA 자동 변환·등록 포털 (Shelfmark) |
| 7 | **Suwayomi (Tachidesk)** | `ebook-suwayomi` | `4567` | Keiyoushi 확장 내장 연재 만화·웹툰 신규 회차 자동 CBZ 다운로드 → Komga·Kavita 실시간 반영 |
| 8 | **Readarr** | `ebook-readarr` | `8787` | Mediarr Prowlarr·qBittorrent 연동 신간 전자책·오디오북 자동 수집 및 0.1초 하드링크 매니저 |
| 9 | **Stirling-PDF** | `ebook-stirling-pdf` | `8087` | 스캔된 PDF 책/논문의 한국어(`ko_KR`) OCR 텍스트 인식 & 양면 분할·압축 스튜디오 |
| 10 | **FlareSolverr** | `ebook-flaresolverr` | `8192` | Suwayomi·CWA 검색 시 Cloudflare 보안 검증 백그라운드 자동 우회 프록시 (내부 `:8191`) |

---

## 🚀 원클릭 실행 방법

```bash
cp .env.example .env   # (로컬 환경에는 이미 기존 Komga/Kavita/ABS 키가 이관된 .env가 준비되어 있습니다)
docker compose up -d
```

- 용도별 프리셋 스택 파일은 `stacks/` 폴더에도 준비되어 있습니다:
  - `stacks/ebook-ultimate-stack.yml` (통합 관제 + 10대 서비스 전체 풀 구성)
  - `stacks/ebook-core-stack.yml` (통합 관제 + 7대 핵심 스마트 자동화 구성)
  - `stacks/ebook-fixed-4-stack.yml` (통합 관제 + 기존 4대장 무결점 교정 버전)

---

## 📄 라이선스
MIT License
