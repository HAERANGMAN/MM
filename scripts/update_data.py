#!/usr/bin/env python3
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()


MARKET_SYMBOLS = [
    {"key": "NASDAQ", "label": "NASDAQ", "symbol": "^IXIC"},
    {"key": "S&P500", "label": "S&P 500", "symbol": "^GSPC"},
    {"key": "KOSPI", "label": "KOSPI", "symbol": "^KS11"},
    {"key": "KOSPI100", "label": "KOSPI 100", "symbol": "^KS100"},
    {"key": "KOSDAQ", "label": "KOSDAQ", "symbol": "^KQ11"},
    {"key": "SET Index", "label": "SET Index", "symbol": "^SET.BK"},
    {"key": "SET50", "label": "SET50", "symbol": "^SET50.BK"},
    {"key": "BTC/USD", "label": "BTC/USD", "symbol": "BTC-USD"},
    {"key": "BTC/KRW", "label": "BTC/KRW", "symbol": "BTC-KRW"},
    {"key": "DXY", "label": "Dollar Index", "symbol": "DX-Y.NYB"},
    {"key": "USD/JPY", "label": "USD/JPY", "symbol": "JPY=X"},
    {"key": "USD/KRW", "label": "USD/KRW", "symbol": "KRW=X"},
    {"key": "USD/THB", "label": "USD/THB", "symbol": "THB=X"},
    {"key": "THB/KRW", "label": "THB/KRW", "derived": True},
]

TWELVEDATA_SYMBOLS = {
    "NASDAQ": ["IXIC", "NASDAQ", "NDX"],
    "S&P500": ["GSPC", "SPX", "SPX500"],
    "KOSPI": ["KOSPI", "KS11"],
    "KOSPI100": ["KOSPI100"],
    "KOSDAQ": ["KOSDAQ", "KQ11"],
    "SET Index": ["SET", "SET.BK"],
    "SET50": ["SET50"],
    "BTC/USD": ["BTC/USD", "BTCUSD"],
    "BTC/KRW": ["BTC/KRW", "BTCKRW"],
    "DXY": ["DXY", "DX"],
    "USD/JPY": ["USD/JPY", "USDJPY"],
    "USD/KRW": ["USD/KRW", "USDKRW"],
    "USD/THB": ["USD/THB", "USDTHB"],
}

ALLOWED_SOURCES = [
    "조선",
    "중앙",
    "동아",
    "문화",
    "한경",
    "매경",
    "WSJ",
    "Bloomberg",
    "Reuters",
    "Fox News",
    "Breitbart",
]

ALLOWED_DOMAINS = [
    "chosun.com",
    "joongang.co.kr",
    "donga.com",
    "munhwa.com",
    "hankyung.com",
    "mk.co.kr",
    "wsj.com",
    "bloomberg.com",
    "reuters.com",
    "foxnews.com",
    "breitbart.com",
]

NEWS_SECTIONS = [
    {"id": "news-korea-econ", "query": "Korea economy OR Korea exports OR Korea inflation", "lang": "ko"},
    {"id": "news-thai-econ", "query": "Thailand economy OR Bank of Thailand OR Thailand inflation", "lang": "en"},
    {"id": "news-global-econ", "query": "global economy OR Federal Reserve OR ECB OR oil", "lang": "en"},
    {"id": "news-korea-soc", "query": "Korea policy OR Korea politics OR Korea industry", "lang": "ko"},
    {"id": "news-thai-soc", "query": "Thailand policy OR Thailand politics OR Thailand industry", "lang": "en"},
    {"id": "news-global-soc", "query": "geopolitics OR G7 OR trade policy OR security", "lang": "en"},
]


def http_json(url: str):
    req = Request(url, headers={"User-Agent": "MM-Dashboard-Updater/1.0"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pct(new_v, old_v):
    if new_v is None or old_v in (None, 0):
        return None
    return ((new_v - old_v) / old_v) * 100


def pick_lookback(points, days):
    if not points:
        return None
    latest = points[-1]["time"]
    target = latest - days * 86400
    best = None
    for p in points:
        if p["time"] <= target:
            best = p["value"]
    return best if best is not None else points[0]["value"]


def downsample(points, max_points=260):
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    out = points[::step]
    if out[-1]["time"] != points[-1]["time"]:
        out.append(points[-1])
    return out


def fetch_yahoo(symbol):
    hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
    last_err = None
    for host in hosts:
        try:
            url = f"https://{host}/v8/finance/chart/{symbol}?range=5y&interval=1d"
            data = http_json(url)
            result = ((data.get("chart") or {}).get("result") or [None])[0]
            if not result:
                raise RuntimeError(f"empty chart: {host}")
            ts = result.get("timestamp") or []
            closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
            points = []
            for i, t in enumerate(ts):
                if i < len(closes) and closes[i] is not None:
                    points.append({"time": int(t), "value": float(closes[i])})
            if points:
                return points
        except Exception as e:
            last_err = e
    raise RuntimeError(f"yahoo fail {symbol}: {last_err}")


def fetch_coingecko(vs_currency):
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency={vs_currency}&days=1825&interval=daily"
    data = http_json(url)
    points = []
    for row in data.get("prices", []):
        if len(row) >= 2:
            points.append({"time": int(row[0] // 1000), "value": float(row[1])})
    return points


def fetch_frankfurter(base, quote):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=1825)
    url = f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}?from={base}&to={quote}"
    data = http_json(url)
    points = []
    rates = data.get("rates", {})
    for day in sorted(rates.keys()):
        val = (rates.get(day) or {}).get(quote)
        if val is not None:
            ts = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
            points.append({"time": ts, "value": float(val)})
    return points


def fetch_twelvedata(candidates):
    if not TWELVEDATA_API_KEY:
        raise RuntimeError("TWELVEDATA_API_KEY missing")
    last_err = None
    for symbol in candidates:
        try:
            q = urlencode({
                "symbol": symbol,
                "interval": "1day",
                "outputsize": "5000",
                "timezone": "UTC",
                "apikey": TWELVEDATA_API_KEY,
            })
            data = http_json(f"https://api.twelvedata.com/time_series?{q}")
            if data.get("status") == "error":
                raise RuntimeError(data.get("message") or "error")
            values = data.get("values") or []
            points = []
            for v in values:
                dt = v.get("datetime")
                c = v.get("close")
                if not dt or c is None:
                    continue
                ts = int(datetime.fromisoformat(dt).replace(tzinfo=timezone.utc).timestamp())
                points.append({"time": ts, "value": float(c)})
            points.sort(key=lambda x: x["time"])
            if len(points) > 10:
                return points
        except Exception as e:
            last_err = e
    raise RuntimeError(f"twelvedata fail: {last_err}")


def derive_ratio(a_points, b_points):
    map_b = {p["time"]: p["value"] for p in b_points}
    out = []
    for p in a_points:
        b = map_b.get(p["time"])
        if b and b != 0:
            out.append({"time": p["time"], "value": p["value"] / b})
    return out


def fetch_series(item):
    key = item["key"]
    if key == "THB/KRW":
        return []
    candidates = TWELVEDATA_SYMBOLS.get(key, [])
    if candidates:
        try:
            return fetch_twelvedata(candidates)
        except Exception:
            pass
    if key == "BTC/USD":
        try:
            return fetch_coingecko("usd")
        except Exception:
            return fetch_yahoo("BTC-USD")
    if key == "BTC/KRW":
        try:
            return fetch_coingecko("krw")
        except Exception:
            return fetch_yahoo("BTC-KRW")
    if key == "USD/JPY":
        return fetch_frankfurter("USD", "JPY")
    if key == "USD/KRW":
        return fetch_frankfurter("USD", "KRW")
    if key == "USD/THB":
        return fetch_frankfurter("USD", "THB")
    return fetch_yahoo(item["symbol"])


def build_market():
    errors = []
    by_key = {}
    for item in MARKET_SYMBOLS:
        if item.get("derived"):
            continue
        try:
            points = fetch_series(item)
            last = points[-1]["value"] if points else None
            prev = points[-2]["value"] if len(points) > 1 else None
            by_key[item["key"]] = {
                "key": item["key"],
                "label": item["label"],
                "price": last,
                "dod": pct(last, prev),
                "mom": pct(last, pick_lookback(points, 30)),
                "yoy": pct(last, pick_lookback(points, 365)),
                "points": downsample(points),
            }
            time.sleep(0.12)
        except Exception as e:
            errors.append(f"{item['label']}: {e}")
            by_key[item["key"]] = {
                "key": item["key"],
                "label": item["label"],
                "price": None,
                "dod": None,
                "mom": None,
                "yoy": None,
                "points": [],
            }

    usdkrw = by_key.get("USD/KRW", {}).get("points", [])
    usdthb = by_key.get("USD/THB", {}).get("points", [])
    thbkrw_points = derive_ratio(usdkrw, usdthb)
    thb_last = thbkrw_points[-1]["value"] if thbkrw_points else None
    thb_prev = thbkrw_points[-2]["value"] if len(thbkrw_points) > 1 else None

    by_key["THB/KRW"] = {
        "key": "THB/KRW",
        "label": "THB/KRW",
        "price": thb_last,
        "dod": pct(thb_last, thb_prev),
        "mom": pct(thb_last, pick_lookback(thbkrw_points, 30)),
        "yoy": pct(thb_last, pick_lookback(thbkrw_points, 365)),
        "points": downsample(thbkrw_points),
    }

    valid = sum(1 for x in by_key.values() if x["price"] is not None)
    lead_keys = ["NASDAQ", "S&P500", "KOSPI", "USD/KRW"]
    lead = []
    for k in lead_keys:
        v = by_key.get(k, {})
        if v.get("dod") is not None:
            lead.append(f"{v['label']} {v['dod']:+.2f}%")
    insight = (
        "금리 경로와 달러 방향성이 위험자산 변동성을 좌우하고 있습니다. "
        f"주요 지표 일간 변화: {', '.join(lead) if lead else '데이터 집계 중'}. "
        "수급과 실적 가이던스, 물가 지표를 함께 점검하십시오."
    )
    if valid == 0:
        insight = f"시장 데이터 로딩 실패. {' | '.join(errors[:3]) if errors else 'API/네트워크 오류'}"

    items = [by_key[s["key"]] for s in MARKET_SYMBOLS]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insight": insight,
        "errors": errors,
        "items": items,
    }


def allowed_article(a):
    src = ((a.get("source") or {}).get("name") or "").lower()
    url = (a.get("url") or "").lower()
    source_match = any(x.lower() in src for x in ALLOWED_SOURCES)
    domain_match = any(d in url for d in ALLOWED_DOMAINS)
    return source_match or domain_match


def numeric_hint(text):
    import re
    m = re.search(r"(\$|₩|%|bp|억|조|\d+\.\d+|\d+)", text or "", flags=re.IGNORECASE)
    return m.group(1) if m else "데이터없음"


def fetch_news_section(section):
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY missing")
    now_utc = datetime.now(timezone.utc)
    from_1h = (now_utc - timedelta(hours=1)).isoformat()
    from_2h = (now_utc - timedelta(hours=2)).isoformat()
    from_3h = (now_utc - timedelta(hours=3)).isoformat()
    from_6h = (now_utc - timedelta(hours=6)).isoformat()
    from_12h = (now_utc - timedelta(hours=12)).isoformat()
    from_24h = (now_utc - timedelta(hours=24)).isoformat()
    from_48h = (now_utc - timedelta(hours=48)).isoformat()

    attempts = [
        {
            "q": section["query"],
            "from": from_1h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section["query"],
            "from": from_2h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section["query"],
            "from": from_3h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section["query"],
            "from": from_6h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section["query"],
            "from": from_12h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section["query"],
            "from": from_24h,
            "sortBy": "publishedAt",
            "pageSize": 50,
            "domains": ",".join(ALLOWED_DOMAINS),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": "economy OR policy OR market OR trade",
            "from": from_48h,
            "sortBy": "publishedAt",
            "pageSize": 50,
            "apiKey": NEWS_API_KEY,
        },
    ]

    last_error = None
    for params in attempts:
        q = urlencode(params)
        data = http_json(f"https://newsapi.org/v2/everything?{q}")
        if data.get("status") == "error":
            last_error = RuntimeError(data.get("message") or data.get("code") or "newsapi error")
            continue

        out = []
        for a in data.get("articles", []):
            if not allowed_article(a):
                continue
            pub = a.get("publishedAt")
            if not pub:
                continue
            out.append(
                {
                    "title": a.get("title"),
                    "description": a.get("description"),
                    "url": a.get("url"),
                    "publishedAt": pub,
                    "source": {"name": (a.get("source") or {}).get("name", "출처미상")},
                    "numericHint": numeric_hint((a.get("title") or "") + " " + (a.get("description") or "")),
                }
            )
            if len(out) >= 5:
                break
        if out:
            return out

    if last_error:
        raise last_error
    return []


def build_news():
    sections = {}
    errors = {}
    for section in NEWS_SECTIONS:
        try:
            sections[section["id"]] = fetch_news_section(section)
        except Exception as e:
            sections[section["id"]] = []
            errors[section["id"]] = str(e)
        time.sleep(0.15)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "errors": errors,
        "key_configured": bool(NEWS_API_KEY),
    }


def main():
    market = build_market()
    news = build_news()
    (DATA_DIR / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated data/market.json and data/news.json")


if __name__ == "__main__":
    main()
