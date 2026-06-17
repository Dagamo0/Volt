"""
VOLT — Market sentiment & news
Three free sources, every network call isolated so a failure never breaks the run:

  1. Crypto Fear & Greed   — api.alternative.me/fng (no key, clean JSON). Reliable.
  2. Stock Fear & Greed    — CNN's index, best-effort via their JSON endpoint.
                             Falls back to None if CNN changes/blocks it.
  3. Per-asset headlines   — yfinance Ticker.news (already free in the pipeline).

Nothing here is allowed to raise. Each function returns its data or a safe default.
"""
import json
import urllib.request
import datetime as dt


def _get_json(url, timeout=12):
    """Fetch JSON with a browser-ish UA. Returns dict/list or None on any failure."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def crypto_fear_greed():
    """Crypto Fear & Greed Index. Returns {value:int, label:str} or None."""
    data = _get_json("https://api.alternative.me/fng/?limit=1&format=json")
    try:
        d = data["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:
        return None


def stock_fear_greed():
    """CNN Fear & Greed Index (stocks). Best-effort. Returns {value:int, label:str} or None.
    CNN serves this via a JSON endpoint behind a UA check; we try, and fall back cleanly."""
    data = _get_json("https://production.dataviz.cnn.io/index/fearandgreed/graphdata")
    try:
        fg = data["fear_and_greed"]
        val = int(round(fg["score"]))
        return {"value": val, "label": fg["rating"].title()}
    except Exception:
        return None


def label_from_value(v):
    """Uniform labelling if a source gives a number but no text."""
    if v is None:
        return None
    if v <= 25:
        return "Extreme Fear"
    if v <= 45:
        return "Fear"
    if v <= 55:
        return "Neutral"
    if v <= 75:
        return "Greed"
    return "Extreme Greed"


def market_sentiment():
    """Combined market-wide sentiment block for the dashboard header."""
    crypto = crypto_fear_greed()
    stock = stock_fear_greed()
    return {
        "stock": stock,
        "crypto": crypto,
        "asOf": dt.datetime.utcnow().isoformat() + "Z",
    }


def asset_headlines(yf_ticker_obj, limit=4):
    """Recent headlines for one asset from yfinance. Returns list of
    {title, publisher, link, published} — newest first. Empty list on failure."""
    out = []
    try:
        news = getattr(yf_ticker_obj, "news", None) or []
        for item in news[:limit]:
            # yfinance news schema shifted over versions; handle both shapes.
            content = item.get("content", item)
            title = content.get("title") or item.get("title")
            if not title:
                continue
            publisher = (content.get("provider", {}) or {}).get("displayName") \
                or item.get("publisher") or ""
            link = (content.get("canonicalUrl", {}) or {}).get("url") \
                or content.get("clickThroughUrl", {}).get("url") \
                or item.get("link") or ""
            # publish time
            pub = content.get("pubDate") or item.get("providerPublishTime")
            if isinstance(pub, (int, float)):
                pub = dt.datetime.utcfromtimestamp(pub).strftime("%b %d")
            elif isinstance(pub, str):
                pub = pub[:10]
            out.append({"title": title, "publisher": publisher,
                        "link": link, "published": pub or ""})
    except Exception:
        pass
    return out
