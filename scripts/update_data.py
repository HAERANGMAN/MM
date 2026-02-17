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
MARKET_HISTORY_FILE = DATA_DIR / "market_history.json"

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()


MARKET_SYMBOLS = [
    {"key": "NASDAQ", "label": "NASDAQ", "symbol": "^IXIC"},
    {"key": "S&P500", "label": "S&P 500", "symbol": "^GSPC"},
    {"key": "KOSPI", "label": "KOSPI", "symbol": "^KS11"},
    {"key": "KOSPI100", "label": "KOSPI 100", "symbol": "KOSPI100.KS"},
    {"key": "KOSDAQ", "label": "KOSDAQ", "symbol": "^KQ11"},
    {"key": "SET Index", "label": "SET Index", "symbol": "^SET.BK"},
    {"key": "SET50", "label": "SET50", "symbol": "^SET50.BK"},
    {"key": "BTC/USD", "label": "BTC/USD", "symbol": "BTC-USD"},
    {"key": "BTC/KRW", "label": "BTC/KRW", "symbol": "BTC-KRW"},
    {"key": "DXY", "label": "Dollar Index", "symbol": "DX-Y.NYB"},
    {"key": "USD/JPY", "label": "USD/JPY", "symbol": "JPY=X"},
    {"key": "USD/KRW", "label": "USD/KRW", "symbol": "KRW=X"},
    {"key": "USD/THB", "label": "USD/THB", "symbol": "THB=X"},
    {"key": "THB/KRW", "label": "THB/KRW"},
]

TWELVEDATA_SYMBOLS = {
    "NASDAQ": ["IXIC", "NASDAQ", "NDX"],
    "S&P500": ["GSPC", "SPX", "SPX500"],
    "KOSPI": ["KOSPI", "KS11"],
    "KOSPI100": ["KOSPI100", "KOSPI100:KSC", "KS100:KSC", "KS100"],
    "KOSDAQ": ["KOSDAQ", "KQ11"],
    "SET Index": ["SET", "SET.BK"],
    "SET50": ["SET50", "SET50.BK", "SET50:SET", "SET50_SET50"],
    "BTC/USD": ["BTC/USD", "BTCUSD"],
    "BTC/KRW": ["BTC/KRW", "BTCKRW"],
    "DXY": ["DXY", "DX"],
    "USD/JPY": ["USD/JPY", "USDJPY"],
    "USD/KRW": ["USD/KRW", "USDKRW"],
    "USD/THB": ["USD/THB", "USDTHB"],
}

ALLOWED_SOURCES = [
    "議곗꽑",
    "以묒븰",
    "?숈븘",
    "臾명솕",
    "?쒓꼍",
    "留ㅺ꼍",
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
    {
        "id": "news-korea-econ",
        "query": "Korea economy OR Korea exports OR Korea inflation OR ?쒓뎅 寃쎌젣 OR ?섏텧",
        "lang": "ko",
        "domains": ["chosun.com", "joongang.co.kr", "donga.com", "munhwa.com", "hankyung.com", "mk.co.kr"],
        "fallback_query": "Korea economy OR Korea market OR Korea policy",
    },
    {
        "id": "news-thai-econ",
        "query": "Thailand economy OR Bank of Thailand OR Thailand inflation OR SET Index OR baht",
        "lang": "en",
        "domains": ["reuters.com", "bloomberg.com", "wsj.com", "bangkokpost.com", "nationthailand.com"],
        "fallback_query": "Thailand economy OR Thailand policy OR Thailand market",
    },
    {
        "id": "news-global-econ",
        "query": "global economy OR Federal Reserve OR ECB OR oil",
        "lang": "en",
        "domains": ["wsj.com", "bloomberg.com", "reuters.com", "foxnews.com", "breitbart.com"],
        "fallback_query": "economy OR market OR inflation OR rates",
    },
    {
        "id": "news-korea-soc",
        "query": "Korea policy OR Korea politics OR Korea industry OR ?쒓뎅 ?뺤튂",
        "lang": "ko",
        "domains": ["chosun.com", "joongang.co.kr", "donga.com", "munhwa.com", "hankyung.com", "mk.co.kr"],
        "fallback_query": "Korea politics OR Korea policy OR Korea security",
    },
    {
        "id": "news-thai-soc",
        "query": "Thailand policy OR Thailand politics OR Thailand industry",
        "lang": "en",
        "domains": ["reuters.com", "bloomberg.com", "wsj.com", "bangkokpost.com", "nationthailand.com"],
        "fallback_query": "Thailand politics OR Thailand policy OR Thailand security",
    },
    {
        "id": "news-global-soc",
        "query": "geopolitics OR G7 OR trade policy OR security",
        "lang": "en",
        "domains": ["wsj.com", "bloomberg.com", "reuters.com", "foxnews.com", "breitbart.com"],
        "fallback_query": "global security OR geopolitics OR policy",
    },
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


def load_market_history():
    if not MARKET_HISTORY_FILE.exists():
        return {"generated_at": None, "series": {}}
    try:
        raw = json.loads(MARKET_HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"generated_at": None, "series": {}}
        if "series" not in raw or not isinstance(raw["series"], dict):
            raw["series"] = {}
        return raw
    except Exception:
        return {"generated_at": None, "series": {}}


def normalize_points(points):
    out = []
    if not isinstance(points, list):
        return out
    for p in points:
        try:
            t = int(p.get("time"))
            v = float(p.get("value"))
            if math.isfinite(v):
                out.append({"time": t, "value": v})
        except Exception:
            continue
    out.sort(key=lambda x: x["time"])
    return out


def collapse_to_daily(points):
    daily = {}
    for p in points:
        day_ts = int(datetime.fromtimestamp(p["time"], tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        daily[day_ts] = p["value"]
    out = [{"time": t, "value": daily[t]} for t in sorted(daily.keys())]
    return out


def update_market_history(history, source_series, snapshot_items, now_ts):
    cutoff = now_ts - (5 * 365 * 86400)
    day_ts = int(datetime.fromtimestamp(now_ts, tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    series_map = history.get("series", {})

    for item in MARKET_SYMBOLS:
        key = item["key"]
        existing = normalize_points(series_map.get(key, []))
        existing = collapse_to_daily(existing)

        # Seed with raw external history once if empty.
        seed = normalize_points(source_series.get(key, []))
        seed = collapse_to_daily(seed)
        if not existing and seed:
            existing = seed

        snap = next((x for x in snapshot_items if x.get("key") == key), None)
        price = None if not snap else snap.get("price")
        if price is not None:
            try:
                pv = float(price)
                if math.isfinite(pv):
                    if existing and existing[-1]["time"] == day_ts:
                        # Same UTC day: keep one daily point and refresh value.
                        existing[-1]["value"] = pv
                    else:
                        existing.append({"time": day_ts, "value": pv})
            except Exception:
                pass

        # Keep 5 years window.
        existing = [p for p in existing if p["time"] >= cutoff]
        series_map[key] = existing

    history["generated_at"] = datetime.now(timezone.utc).isoformat()
    history["series"] = series_map
    return history


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


def fetch_series(item):
    key = item["key"]
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
    if key == "THB/KRW":
        return fetch_frankfurter("THB", "KRW")
    return fetch_yahoo(item["symbol"])


def build_market():
    errors = []
    by_key = {}
    source_series = {}
    for item in MARKET_SYMBOLS:
        try:
            points = fetch_series(item)
            source_series[item["key"]] = points
            last = points[-1]["value"] if points else None
            prev = points[-2]["value"] if len(points) > 1 else None
            if len(points) < 2:
                dod = None
                mom = None
                yoy = None
            else:
                dod = pct(last, prev)
                mom = pct(last, pick_lookback(points, 30))
                yoy = pct(last, pick_lookback(points, 365))
            by_key[item["key"]] = {
                "key": item["key"],
                "label": item["label"],
                "price": last,
                "dod": dod,
                "mom": mom,
                "yoy": yoy,
                "raw_points": len(points),
            }
            if len(points) < 2:
                errors.append(f"{item['label']}: insufficient raw points ({len(points)})")
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
                "raw_points": 0,
            }

    valid = sum(1 for x in by_key.values() if x["price"] is not None)
    lead_keys = ["NASDAQ", "S&P500", "KOSPI", "USD/KRW"]
    lead = []
    for k in lead_keys:
        v = by_key.get(k, {})
        if v.get("dod") is not None:
            lead.append(f"{v['label']} {v['dod']:+.2f}%")
    insight = f"Raw data summary: {', '.join(lead) if lead else 'N/A'}"
    if valid == 0:
        insight = f"Market data load failed: {' | '.join(errors[:3]) if errors else 'API/network error'}"

    items = [by_key[s["key"]] for s in MARKET_SYMBOLS]
    market = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insight": insight,
        "errors": errors,
        "items": items,
    }
    now_ts = int(datetime.now(timezone.utc).timestamp())
    history = load_market_history()
    history = update_market_history(history, source_series, items, now_ts)
    return market, history


def allowed_article(a, section=None):
    src = ((a.get("source") or {}).get("name") or "").lower()
    url = (a.get("url") or "").lower()
    source_match = any(x.lower() in src for x in ALLOWED_SOURCES)
    section_domains = (section or {}).get("domains") or ALLOWED_DOMAINS
    domain_match = any(d in url for d in section_domains)
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

    section_domains = section.get("domains") or ALLOWED_DOMAINS
    section_query = section.get("query") or "economy OR policy OR market"
    fallback_query = section.get("fallback_query") or "economy OR policy OR market OR trade"

    attempts = [
        {
            "q": section_query,
            "from": from_1h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section_query,
            "from": from_2h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section_query,
            "from": from_3h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section_query,
            "from": from_6h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section_query,
            "from": from_12h,
            "sortBy": "publishedAt",
            "pageSize": 30,
            "language": section["lang"],
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": section_query,
            "from": from_24h,
            "sortBy": "publishedAt",
            "pageSize": 50,
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": fallback_query,
            "from": from_48h,
            "sortBy": "publishedAt",
            "pageSize": 50,
            "domains": ",".join(section_domains),
            "apiKey": NEWS_API_KEY,
        },
        {
            "q": fallback_query,
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
            if not allowed_article(a, section):
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
                    "source": {"name": (a.get("source") or {}).get("name", "異쒖쿂誘몄긽")},
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
    market, history = build_market()
    news = build_news()
    (DATA_DIR / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "market_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    print("updated data/market.json, data/market_history.json and data/news.json")


if __name__ == "__main__":
    main()

