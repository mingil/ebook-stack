# 📚 Ultimate Synology eBook, Manga, Webtoon & Audiobook Stack (`ebook-stack`)

시놀로지 NAS(**DS920+** 및 DSM 7.2 전 모델)와 모든 홈서버 환경을 위해 **단일 프로젝트(`ebook-stack`)와 단일 `docker-compose.yml` 안에서 전용 관제 도커 이미지(`kimmingil/ebook-stack:latest`)와 10대 eBook 서버가 100% 유기적으로 연동·관리되는 올인원 전자책 생태계**입니다.

---

## 🔗 4대 핵심 유기적 자동화 파이프라인 (검증 완료)

단순히 컨테이너들을 나열한 것이 아니라, **검색 ➔ 다운로드 ➔ 자동 포맷 변환 ➔ 메타데이터·표지 매칭 ➔ 전 뷰어 동시 열람 ➔ DB 최적화·백업**이 수동 개입 없이 맞물려 돌아가도록 설계·검증되었습니다.

1. **[파이프라인 1] 웹 도서 검색 ➔ 자동 EPUB 변환 ➔ 3대 뷰어 동시 즉시 반영**
   - `FlareSolverr(:8191)` ➔ `CWA Book Downloader(:8084)` ➔ `[/cwa-book-ingest]` ➔ `Calibre-Web-Automated(:8083)` ➔ `[/calibre-library]` ➔ **`Kavita(:5471)` & `Audiobookshelf(:13378)` & `Komga(:8341)` 동시 공유**
   - 도서 다운로더 웹 화면에서 책을 검색해 클릭 한 번으로 받으면 `/cwa-book-ingest`로 들어가고, Calibre-Web-Automated가 5초 내로 감지해 EPUB으로 자동 변환한 뒤 `/calibre-library`에 저장합니다. 이 `/calibre-library` 폴더를 Kavita, Audiobookshelf, Komga가 모두 직접 마운트하고 있어 **파일 복사 없이 모든 앱에서 즉시 열람**됩니다.
2. **[파이프라인 2] 연재 만화·웹툰 자동 수집 ➔ CBZ 압축 저장 ➔ 한국어 메타데이터 자동 주입**
   - `FlareSolverr(:8191)` ➔ `Suwayomi(:4567)` ➔ `[/data/manga (*.cbz)]` ➔ `Komga(:8341)` & `Kavita(:5471)` ➔ `Komf(:8085)`
   - Suwayomi 컨테이너에 JVM 시스템 프로퍼티(`-Dsuwayomi.tachidesk.config.server.downloadAsCbz=true`, `downloadsPath=/data/manga`, `flareSolverrEnabled=true`)가 사전 주입되어 있어, 새 회차가 올라오면 자동으로 `.cbz` 파일로 `/data/manga`에 저장됩니다. Komga와 Kavita가 이를 스캔하는 즉시 Komf의 `eventListener`가 작동해 한국어 제목·줄거리·작가·표지를 입힙니다.
3. **[파이프라인 3] 토렌트/인덱서 신간 수집 ➔ 0.1초 하드링크 서재 등록**
   - `qBittorrent(/volume1/data/torrents)` ➔ `Readarr(:8787)` ➔ `[/volume1/data/ebooks/{books,audiobooks}]`
   - Readarr가 상위 `/volume1/data` 볼륨을 공유하므로 대용량 오디오북이나 전자책 세트를 복사 시간 0.1초, 추가 디스크 소모 0바이트(하드링크)로 서재에 즉시 연결합니다.
4. **[파이프라인 4] 통합 관제 컨테이너(`ebook-control-center`) 부팅 시 자동 프로비저닝 & DB 닥터**
   - 프로젝트 도커 이미지(`kimmingil/ebook-stack:latest`)가 같은 `docker-compose.yml`과 `ebook_net` 안에서 함께 구동되면서, 부팅 시 **모든 폴더 자동 생성, Audiobookshelf 기존 DB 무손실 `/config` 분리 이관, Komf `application.yml` 자동 생성**을 수행하고, 웹 UI(`:8500`)에서 원클릭 SQLite `VACUUM` 최적화와 설정 백업을 실행합니다.

---

## 📦 단일 프로젝트(`docker-compose.yml`)에 포함된 전체 구성 (Watchtower 제외 완료)

| 번호 | 서비스 | 컨테이너 이름 | 호스트 포트 | 핵심 역할 |
| :--- | :--- | :--- | :---: | :--- |
| 0 | **eBook Control Center** | `ebook-control-center` | `8500` | 본 프로젝트 도커 이미지(`kimmingil/ebook-stack:latest`) — 폴더/설정 자동 프로비저닝 · DB 최적화 · 통합 관제 |
| 1 | **Komga** | `ebook-komga` | `8341` | 만화·웹툰·잡지(CBZ/CBR/PDF/EPUB) 메인 서버 (G1GC 3GB 최적화) |
| 2 | **Kavita** | `ebook-kavita` | `5471` | 라이트노벨(EPUB)·소설·만화 초고속 하이브리드 웹 리더 |
| 3 | **Audiobookshelf** | `ebook-audiobookshelf` | `13378` | 오디오북(M4B/MP3)·팟캐스트·전자책 스트리밍 & 이어듣기 동기화 |
| 4 | **Komf** | `ebook-komf` | `8085` | Komga & Kavita 만화·웹툰·라노벨 메타데이터/표지 자동 수집 엔진 |
| 5 | **Calibre-Web-Automated** | `ebook-calibre-web` | `8083` | 전자책 자동 EPUB/KEPUB 변환 · 서재 관리 · Kobo 무선 동기화 · Kindle 전송 |
| 6 | **CWA Book Downloader** | `ebook-book-downloader` | `8084` | 웹에서 도서 검색 후 클릭 한 번으로 다운로드 → CWA 자동 변환·등록 포털 |
| 7 | **Suwayomi (Tachidesk)** | `ebook-suwayomi` | `4567` | 연재 만화·웹툰 신규 회차 자동 CBZ 다운로드 → Komga·Kavita 실시간 반영 |
| 8 | **Readarr** | `ebook-readarr` | `8787` | Prowlarr·qBittorrent 연동 신간 전자책·오디오북 자동 수집 매니저 |
| 9 | **Stirling-PDF** | `ebook-stirling-pdf` | `8087` | 스캔된 PDF 책/논문의 한국어(`kor`) OCR 텍스트 인식 & 양면 분할·압축 스튜디오 |
| 10 | **FlareSolverr** | `ebook-flaresolverr` | `8191` | Suwayomi·CWA·Readarr 검색 시 Cloudflare 보안 검증 백그라운드 자동 우회 |

---

## 🚀 사용 방법 (단일 `docker-compose.yml`과 도커 이미지로 원클릭 관리)

본 프로젝트는 `docker-compose.yml` (또는 `compose.yaml`) 파일 하나로 모든 컨테이너와 관제 센터(`kimmingil/ebook-stack:latest`)가 한 번에 구동됩니다:

```bash
docker compose up -d
```

- 컨테이너가 올라오면 `ebook-control-center`(`kimmingil/ebook-stack:latest`)가 자동으로 필요한 폴더 구조(`/volume1/docker/...`, `/volume1/data/ebooks/...`)를 생성하고, Audiobookshelf 기존 DB 분리 및 Komf `application.yml` 생성을 자동으로 마칩니다.
- 용도별 프리셋 스택 파일은 `stacks/` 폴더에도 준비되어 있습니다:
  - `stacks/ebook-ultimate-stack.yml` (통합 관제 + 10대 서비스 전체)
  - `stacks/ebook-core-stack.yml` (통합 관제 + 7대 핵심 자동화 서비스)
  - `stacks/ebook-fixed-4-stack.yml` (통합 관제 + 기존 4대장 무결점 교정 버전)

---

## 📄 라이선스
MIT License
