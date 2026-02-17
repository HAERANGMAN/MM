# MM

이 문서는 현재 코드에 실제 반영된 동작 로직/알고리즘만 정리합니다.

## 1) 실행 구조

- 정적 페이지: `index.html`
- 데이터 생성기: `scripts/update_data.py`
- 자동 갱신: `.github/workflows/update-data.yml`
- 산출 파일:
  - `data/market.json` (현재가 + 변동률 + 인사이트)
  - `data/market_history.json` (차트용 기간별 시계열)
  - `data/news.json` (뉴스 섹션 결과)

`index.html`은 API를 직접 호출하지 않고, 위 JSON만 읽습니다.

## 2) 로컬 실행

`file://`로 직접 열지 말고 HTTP 서버로 실행합니다.

```powershell
cd C:\Users\abcra\OneDrive\Coding\MM
powershell -ExecutionPolicy Bypass -File .\scripts\serve.ps1
```

기본 URL: `http://localhost:8080`

종료: 서버 터미널에서 `Ctrl + C`

## 3) 마켓 데이터 로직 (실제 적용)

### 대상 종목

- NASDAQ, S&P500, KOSPI, KOSDAQ, SET Index
- BTC/USD, BTC/KRW
- DXY, USD/JPY, USD/KRW, USD/THB, THB/KRW

`KOSPI100`, `SET50`은 현재 로직에서 제거됨.

### 데이터 소스 우선순위

- 기본: Yahoo Finance chart endpoint
- 일부 종목: TwelveData 시도 후 실패 시 대체 소스
- BTC: CoinGecko 대체 가능
- FX 일부: Frankfurter API 사용

### 가격/변동률 계산

- `price`: 최신 값
- `dod`: 직전 값 대비 %
- `mom`: 약 30일 전 대비 %
- `yoy`: 약 365일 전 대비 %
- 계산 불가 시 `null` -> 프론트에서 `데이터없음`

### 차트 시계열 알고리즘 (핵심)

`data/market_history.json`은 종목별로 아래 버킷을 저장:

- `1d`: 5분봉
- `1m`: 3시간봉
- `1y`: 일봉
- `5y`: 일봉

구현 규칙:

- 1D: Yahoo `range=1d, interval=5m` 또는 TwelveData `5min`
- 1M: TwelveData `3h` 우선, 실패 시 Yahoo 1시간봉을 3시간 버킷으로 다운샘플
- 1Y: Yahoo `range=1y, interval=1d` 우선
- 5Y: Yahoo `range=5y, interval=1d` 기반
- 원천 데이터 부족/실패 시 생성/보정/스케일링 없이 빈 배열 유지

즉, 차트는 “외부 원데이터만” 사용하고 임의 생성하지 않음.

## 4) 프론트 렌더링 로직 (실제 적용)

### Section 1

- 태국 시간(`Asia/Bangkok`) 기준 날짜/주차 표시
- 불기 연도(`서기 + 543`) 표시
- 진행률:
  - 올해: `dayOfYear / 365`
  - 계약: `2025-08-22` 시작, 총 `678`일 기준
- 소수 둘째 자리 표시

### Market Watch 테이블

- 컬럼: `Index | Price | 1D | 1M | 1Y | 5Y`
- `Price`는 숫자만 출력
- 나머지 4개는 스파크라인 그래프
- 그래프 데이터 부족 시 셀에 `데이터없음`

참고: 렌더 안정성을 위해 현재 라인 그래프는 SVG 스파크라인 경로를 사용.

## 5) 뉴스 로직 (실제 적용)

뉴스 생성 스크립트는 `NEWS_API_KEY` 기반으로 섹션별 수집을 시도하며, 시간 폴백은 다음 순서:

- `1h -> 2h -> 3h -> 6h -> 12h -> 24h -> 48h`

필터링:

- 허용 출처/도메인 화이트리스트 기반
- 결과 부족/실패/요금제 제한(429 등) 시 섹션은 빈 배열
- 프론트는 빈 배열이면 `데이터없음` 표시

## 6) GitHub Actions / Pages 운용

### 시크릿

`Settings > Secrets and variables > Actions`

- `NEWS_API_KEY`
- `TWELVEDATA_API_KEY`

### 워크플로

- 수동 실행: `Actions > Update Dashboard Data > Run workflow`
- 자동 실행: 현재 cron 설정(레포의 `.github/workflows/update-data.yml` 기준)
- 실행 후 JSON 변경분이 있으면 자동 커밋/푸시

### Pages

- `Settings > Pages`
- `Deploy from a branch`
- `master` / `root`

## 7) 설계 원칙

- API 키는 클라이언트(`index.html`)에 넣지 않음
- 데이터 없으면 `데이터없음`으로 표시
- 시장 데이터/차트는 외부 원데이터 기반만 사용
- 임의 생성, 스케일링, 할루시네이션 금지
