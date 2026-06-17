"""
VOLT — Main data pipeline (two-tier: pinned focus-15 + wide scan universe)

Flow:
  1. Build the full symbol set = focus-15 (config.WATCHLIST) + curated buckets
     (forex/crypto/commodity/index/momentum) + live S&P 500 (universe.py).
  2. Download history in BATCHES with pacing so Yahoo doesn't rate-limit.
  3. Per symbol: indicators -> 3 scanners -> overall signal. Errors isolated.
  4. Earnings dates fetched only for the focus-15 + any symbol that fired a signal
     (keeps the run fast — no point pulling 500 earnings calendars).
  5. Write data.json: { focus:[...15], universe:[...all], calendar:[...], stats }.

One bad symbol never kills the run.
"""
import json, sys, time, datetime as dt
import pandas as pd

import config, universe as uni
import indicators as ind, signals as sig, catalysts as cat, sentiment as sent

try:
    import yfinance as yf
except ImportError:
    yf = None

BATCH_SIZE = 40          # symbols per yfinance download call
BATCH_PAUSE = 1.5        # seconds between batches (rate-limit politeness)


def log(msg):
    print(f"[VOLT {dt.datetime.utcnow():%H:%M:%S}] {msg}", flush=True)


def vol_descriptor(atr_pct):
    score = min(100, max(5, round(atr_pct * 14)))
    if score >= 75:  return score, "Very High", "#ff3366"
    if score >= 60:  return score, "High", "#ffaa00"
    if score >= 40:  return score, "Moderate", "#4488ff"
    return score, "Low", "#4488ff"


def fetch_sp500():
    """Live S&P 500 constituents from Wikipedia; fall back to the curated list."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        syms = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        log(f"S&P 500 list: {len(syms)} symbols from Wikipedia")
        return syms
    except Exception as e:
        log(f"S&P 500 live fetch failed ({e}); using fallback list")
        return uni.SP500_FALLBACK


def build_symbol_set():
    """Return (ordered list of asset-meta dicts, set of focus tickers)."""
    seen, metas = set(), []
    focus_tickers = set()

    # 1. Pinned focus-15 first (with their display metadata)
    for a in config.WATCHLIST:
        metas.append({"yf": a["yf"], "ticker": a["ticker"], "name": a["name"],
                      "category": a["category"], "icon": a["icon"], "color": a["color"],
                      "focus": True})
        seen.add(a["yf"]); focus_tickers.add(a["ticker"])

    # 2. Curated non-equity buckets
    for m in uni.curated_non_equity():
        if m["yf"] in seen:
            continue
        metas.append({**m, "name": m["ticker"], "icon": m["ticker"][:2].upper(),
                      "color": "#5a5a78", "focus": False})
        seen.add(m["yf"])

    # 3. S&P 500 equities
    for sym in fetch_sp500():
        if sym in seen:
            continue
        metas.append({"yf": sym, "ticker": sym, "name": sym,
                      "category": uni.equity_category(sym),
                      "icon": sym[:2].upper(), "color": "#5a5a78", "focus": False})
        seen.add(sym)

    return metas, focus_tickers


def download_batched(symbols):
    """Download 1y daily history for all symbols in paced batches.
    Returns dict {yf_symbol: DataFrame}. Failures simply omitted."""
    out = {}
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        try:
            data = yf.download(batch, period=config.HISTORY_PERIOD, auto_adjust=False,
                               group_by="ticker", threads=True, progress=False)
            for sym in batch:
                try:
                    df = data[sym] if len(batch) > 1 else data
                    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
                    if len(df) >= 60:
                        out[sym] = df
                except Exception:
                    pass
        except Exception as e:
            log(f"batch {i//BATCH_SIZE} failed: {e}")
        log(f"  fetched {min(i+BATCH_SIZE, len(symbols))}/{len(symbols)} symbols")
        time.sleep(BATCH_PAUSE)
    return out


def analyze(meta, df, th):
    """Compute indicators + scanners for one asset. Returns asset dict."""
    out = {"id": meta["yf"].lower().replace("=", "").replace("^", "").replace("-", ""),
           "ticker": meta["ticker"], "name": meta["name"], "category": meta["category"],
           "icon": meta["icon"], "color": meta["color"], "focus": meta["focus"], "error": None}
    try:
        df = df.copy()
        df["rsi"] = ind.rsi(df["Close"], 14)
        df["atr"] = ind.atr(df["High"], df["Low"], df["Close"], 14)
        macd_line, signal_line, hist = ind.macd(df["Close"])
        df["macd_hist"] = hist

        last, prev = df.iloc[-1], df.iloc[-2]
        price = float(last["Close"])
        change_pct = float((last["Close"] / prev["Close"] - 1) * 100)
        atr_val = float(last["atr"]); atr_pct = (atr_val / price * 100) if price else 0
        rsi_val = float(last["rsi"])

        turtle = sig.turtle_breakout(df, th, config.DEFAULT_ACCOUNT_SIZE,
                                     config.RISK_PER_TRADE_PCT, config.ATR_STOP_MULTIPLE)
        swing = sig.swing_setup(df, th)
        snap = sig.snapback(df, th, meta["category"])
        overall = sig.overall_signal(turtle, swing, snap, df, th)
        wk_trend = ind.weekly_trend(df["Close"])
        conv_score, conv_reasons = sig.conviction_score(df, turtle, swing, snap, wk_trend)
        conv_tier = sig.conviction_tier(conv_score)

        vscore, vlabel, vcolor = vol_descriptor(atr_pct)
        vol20 = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(last["Volume"] / vol20) if vol20 else 1.0

        # Chart data — only for fired or focus assets (keeps data.json lean).
        # ~90 days of OHLC + the 20/55-day Turtle channel lines for overlay.
        chart = None
        if meta["focus"] or bool(turtle or swing or snap):
            hi20 = ind.rolling_extreme(df["High"], 20, "high")
            lo20 = ind.rolling_extreme(df["Low"], 20, "low")
            hi55 = ind.rolling_extreme(df["High"], 55, "high")
            lo55 = ind.rolling_extreme(df["Low"], 55, "low")
            tail = df.iloc[-90:]
            bars, ch20h, ch20l, ch55h, ch55l = [], [], [], [], []
            for ts, row in tail.iterrows():
                t = ts.strftime("%Y-%m-%d")
                bars.append({"time": t,
                             "open": round(float(row["Open"]), 4),
                             "high": round(float(row["High"]), 4),
                             "low": round(float(row["Low"]), 4),
                             "close": round(float(row["Close"]), 4)})
                def _v(series):
                    x = series.get(ts)
                    return round(float(x), 4) if x is not None and not pd.isna(x) else None
                ch20h.append({"time": t, "value": _v(hi20)})
                ch20l.append({"time": t, "value": _v(lo20)})
                ch55h.append({"time": t, "value": _v(hi55)})
                ch55l.append({"time": t, "value": _v(lo55)})
            chart = {"bars": bars,
                     "ch20High": [c for c in ch20h if c["value"] is not None],
                     "ch20Low": [c for c in ch20l if c["value"] is not None],
                     "ch55High": [c for c in ch55h if c["value"] is not None],
                     "ch55Low": [c for c in ch55l if c["value"] is not None]}

        out.update({
            "price": round(price, 4), "change": round(change_pct, 2),
            "vol": vscore, "volLabel": vlabel, "volColor": vcolor,
            "sparkline": [round(float(x), 4) for x in df["Close"].iloc[-30:].tolist()],
            "signal": overall,
            "fired": bool(turtle or swing or snap),
            "conviction": conv_score,
            "convictionTier": conv_tier,
            "convictionReasons": conv_reasons,
            "metrics": {
                "rsi": round(rsi_val, 1), "atr": round(atr_val, 4), "atrPct": round(atr_pct, 2),
                "macd": ind.macd_state(macd_line, signal_line, hist),
                "support": round(float(df["Low"].iloc[-20:].min()), 4),
                "resistance": round(float(df["High"].iloc[-20:].max()), 4),
                "volRatio": f"{vol_ratio:.1f}x avg",
                "weeklyTrend": ind.weekly_trend(df["Close"]),
            },
            "scanners": {"turtle": turtle, "swing": swing, "snapback": snap},
            "earnings": None,
            "chart": chart,
        })
    except Exception as e:
        out.update({"price": None, "change": None, "signal": "neutral",
                    "fired": False, "error": str(e)})
    return out


def build():
    if yf is None:
        log("ERROR: yfinance not installed. Run: pip install -r requirements.txt"); sys.exit(1)

    th = config.THRESHOLDS[config.SENSITIVITY]
    metas, focus_tickers = build_symbol_set()
    log(f"Universe: {len(metas)} symbols (focus={len(focus_tickers)}), sensitivity={config.SENSITIVITY}")

    frames = download_batched([m["yf"] for m in metas])
    log(f"Downloaded usable history for {len(frames)}/{len(metas)} symbols")

    assets = []
    for m in metas:
        df = frames.get(m["yf"])
        if df is None:
            assets.append({"id": m["yf"].lower(), "ticker": m["ticker"], "name": m["name"],
                           "category": m["category"], "icon": m["icon"], "color": m["color"],
                           "focus": m["focus"], "price": None, "change": None,
                           "signal": "neutral", "fired": False,
                           "error": "no data (symbol unavailable or delisted)"})
        else:
            assets.append(analyze(m, df, th))

    # Earnings + headlines: only for focus + anything that fired (keeps run fast)
    for a in assets:
        if a["focus"] or a.get("fired"):
            try:
                tk = yf.Ticker(a["ticker"])
                a["earnings"] = cat.earnings_date(tk)
                a["headlines"] = sent.asset_headlines(tk, limit=4)
            except Exception:
                a["earnings"] = None
                a["headlines"] = []

    # Market-wide sentiment (Fear & Greed gauges)
    market = sent.market_sentiment()
    log(f"Sentiment — stock F&G: {market['stock']}, crypto F&G: {market['crypto']}")

    # Calendar window
    today = dt.date.today()
    window_end = today + dt.timedelta(days=21)
    macro = cat.macro_events(today, window_end)
    earnings_events = []
    for a in assets:
        ed = a.get("earnings")
        if ed:
            try:
                edate = dt.date.fromisoformat(ed[:10])
                if today <= edate <= window_end + dt.timedelta(days=75):
                    earnings_events.append({"date": edate.isoformat(),
                                            "text": f"{a['ticker']} earnings",
                                            "tag": "earnings", "scope": a["ticker"]})
            except Exception:
                pass
    calendar_feed = sorted(macro + earnings_events, key=lambda x: x["date"])

    focus = [a for a in assets if a["focus"]]
    universe_assets = assets  # full set; dashboard filters to fired/by category
    ok = sum(1 for a in assets if not a["error"])
    fired = sum(1 for a in assets if a.get("fired"))

    payload = {
        "generated": dt.datetime.utcnow().isoformat() + "Z",
        "sensitivity": config.SENSITIVITY,
        "defaultAccountSize": config.DEFAULT_ACCOUNT_SIZE,
        "riskPerTradePct": config.RISK_PER_TRADE_PCT,
        "atrStopMultiple": config.ATR_STOP_MULTIPLE,
        "focus": focus,
        "universe": universe_assets,
        "calendar": calendar_feed,
        "sentiment": market,
        "stats": {"ok": ok, "failed": len(assets) - ok, "total": len(assets), "fired": fired},
    }
    with open(config.OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    log(f"Done — {ok}/{len(assets)} OK, {fired} fired a signal, "
        f"{len(calendar_feed)} calendar events. Wrote {config.OUTPUT_FILE}")
    if ok == 0:
        log("WARNING: every symbol failed — Yahoo may be rate-limiting or down."); sys.exit(1)


if __name__ == "__main__":
    build()
