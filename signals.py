"""
VOLT — Signal engine
Computes the three signal types from an OHLCV DataFrame + config thresholds.

Signal types:
  1. Turtle Breakout  — price breaks 20d / 55d channel, with ATR position sizing.
  2. Swing Setup      — confirmed weekly trend + daily pullback that looks complete.
  3. Snap-back        — abnormal move (>= Nx avg daily range) + early reversal + volume.
"""
import pandas as pd
import indicators as ind


def _position_size(account_size, risk_pct, atr_value, stop_mult, price):
    """Classic Turtle/ATR sizing.
    Units = (account * risk%) / (ATR * stop_mult). Returns shares + $ at risk."""
    if not atr_value or atr_value <= 0:
        return {"shares": 0, "dollar_risk": 0, "stop_distance": 0}
    dollar_risk = account_size * (risk_pct / 100.0)
    stop_distance = atr_value * stop_mult
    shares = dollar_risk / stop_distance
    return {
        "shares": round(shares, 4 if price < 50 else 2),
        "dollar_risk": round(dollar_risk, 2),
        "stop_distance": round(stop_distance, 4),
        "notional": round(shares * price, 2),
    }


def turtle_breakout(df, th, account_size, risk_pct, atr_stop_mult):
    """Flag 20d/55d channel breaks. df must have High/Low/Close + atr column."""
    close = df["Close"].iloc[-1]
    atr_val = df["atr"].iloc[-1]
    buf = th["breakout_buffer"]

    hi20 = ind.rolling_extreme(df["High"], 20, "high").iloc[-1]
    lo20 = ind.rolling_extreme(df["Low"], 20, "low").iloc[-1]
    hi55 = ind.rolling_extreme(df["High"], 55, "high").iloc[-1]
    lo55 = ind.rolling_extreme(df["Low"], 55, "low").iloc[-1]

    direction, channel, level = None, None, None
    # 55-day takes priority (bigger signal) over 20-day
    if pd.notna(hi55) and close >= hi55 * (1 + buf):
        direction, channel, level = "long", "55-day", hi55
    elif pd.notna(hi20) and close >= hi20 * (1 + buf):
        direction, channel, level = "long", "20-day", hi20
    elif pd.notna(lo55) and close <= lo55 * (1 - buf):
        direction, channel, level = "short", "55-day", lo55
    elif pd.notna(lo20) and close <= lo20 * (1 - buf):
        direction, channel, level = "short", "20-day", lo20

    if direction is None:
        return None

    size = _position_size(account_size, risk_pct, atr_val, atr_stop_mult, close)
    stop = close - size["stop_distance"] if direction == "long" else close + size["stop_distance"]
    return {
        "type": "turtle",
        "direction": direction,
        "channel": channel,
        "trigger_level": round(level, 4),
        "entry": round(close, 4),
        "stop": round(stop, 4),
        "atr": round(atr_val, 4),
        "size": size,
        "note": f"{channel} {'breakout' if direction == 'long' else 'breakdown'}",
    }


def swing_setup(df, th):
    """Confirmed weekly trend + daily pullback to a key level that looks complete.
    Long version: weekly up, daily RSI dipped to oversold-ish, now turning up."""
    wk = ind.weekly_trend(df["Close"])
    if wk == "sideways":
        return None

    rsi_now = df["rsi"].iloc[-1]
    rsi_prev = df["rsi"].iloc[-2]
    close = df["Close"].iloc[-1]
    ema20 = df["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
    pullback_lvl = th["swing_pullback_rsi"]

    if wk == "up":
        # pulled back (RSI was below threshold recently) and momentum now turning up
        recent_dip = df["rsi"].iloc[-6:].min() <= pullback_lvl
        turning_up = rsi_now > rsi_prev
        # within 5% above OR any distance below the 20-EMA (a pullback can dip under it)
        near_support = close <= ema20 * 1.05
        if recent_dip and turning_up and near_support:
            return {"type": "swing", "direction": "long", "weekly_trend": "up",
                    "note": "Uptrend pullback complete, momentum turning up",
                    "rsi": round(rsi_now, 1), "ref_level": round(ema20, 4)}
    if wk == "down":
        recent_pop = df["rsi"].iloc[-5:].max() >= (100 - pullback_lvl)
        turning_down = rsi_now < rsi_prev
        near_resist = close >= ema20 * 0.97
        if recent_pop and turning_down and near_resist:
            return {"type": "swing", "direction": "short", "weekly_trend": "down",
                    "note": "Downtrend rally fading, momentum turning down",
                    "rsi": round(rsi_now, 1), "ref_level": round(ema20, 4)}
    return None


def snapback(df, th, category):
    """Abnormally large move + early reversal signal + volume confirmation.
    Restricted to the high-volatility catalyst plays: AI/chips + indices."""
    if category not in ("ai", "index"):
        return None

    adr = ind.average_daily_range(df["High"], df["Low"], 20).iloc[-1]
    if pd.isna(adr) or adr <= 0:
        return None

    today_range = df["High"].iloc[-1] - df["Low"].iloc[-1]
    move_mult = today_range / adr
    if move_mult < th["snapback_adr_mult"]:
        return None

    # Direction of the abnormal move
    day_change = df["Close"].iloc[-1] - df["Open"].iloc[-1]

    # Volume confirmation: today's volume vs 20d average
    vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
    vol_today = df["Volume"].iloc[-1]
    vol_ok = (not th["snapback_require_volume"]) or (vol_avg and vol_today >= vol_avg * 1.5)
    if not vol_ok:
        return None

    rsi_now = df["rsi"].iloc[-1]
    # Early reversal: extreme RSI against the move's direction
    if day_change > 0 and rsi_now >= th["rsi_overbought"]:
        return {"type": "snapback", "direction": "short", "move_mult": round(move_mult, 2),
                "rsi": round(rsi_now, 1), "vol_x": round(vol_today / vol_avg, 1) if vol_avg else None,
                "note": f"Spiked {move_mult:.1f}x ADR, overbought — fade candidate"}
    if day_change < 0 and rsi_now <= th["rsi_oversold"]:
        return {"type": "snapback", "direction": "long", "move_mult": round(move_mult, 2),
                "rsi": round(rsi_now, 1), "vol_x": round(vol_today / vol_avg, 1) if vol_avg else None,
                "note": f"Dropped {move_mult:.1f}x ADR, oversold — bounce candidate"}
    return None


def overall_signal(turtle, swing, snap, df, th):
    """Roll the three scanners + indicators into the single pill the watchlist shows:
    bullish / bearish / neutral / watch (matches existing dashboard vocab)."""
    longs = sum(1 for s in (turtle, swing, snap) if s and s["direction"] == "long")
    shorts = sum(1 for s in (turtle, swing, snap) if s and s["direction"] == "short")
    if longs and not shorts:
        return "bullish"
    if shorts and not longs:
        return "bearish"
    if longs and shorts:
        return "watch"  # conflicting signals — worth a look
    # No scanner fired — fall back to MACD/RSI lean
    rsi_now = df["rsi"].iloc[-1]
    if rsi_now >= th["rsi_overbought"] or rsi_now <= th["rsi_oversold"]:
        return "watch"
    if df["macd_hist"].iloc[-1] > 0:
        return "bullish"
    if df["macd_hist"].iloc[-1] < 0:
        return "bearish"
    return "neutral"


# ─── Conviction scoring ───────────────────────────────────────────────────────
# The strongest plays float to the top. Bias = CONFLUENCE + TREND ALIGNMENT.
# Score is 0-100. Components are additive then capped; weights reflect the bias.

def conviction_score(df, turtle, swing, snap, weekly_trend):
    """Score a fired asset 0-100. Returns (score, reasons[]).
    Returns (0, []) if nothing fired. Higher = stronger conviction.

    Weighting philosophy (confluence + trend tilt):
      Confluence (multiple scanners agree on direction) ..... up to 34
      Trend alignment (signal direction == weekly trend) .... up to 26
      Channel strength (55-day > 20-day Turtle) ............. up to 16
      Volume / momentum confirmation ....................... up to 14
      Momentum extremity (RSI stretch, MACD cross) ......... up to 10
    """
    fired = [s for s in (turtle, swing, snap) if s]
    if not fired:
        return 0, []

    reasons = []
    score = 0.0

    # Net direction of the fired signals
    longs = sum(1 for s in fired if s["direction"] == "long")
    shorts = sum(1 for s in fired if s["direction"] == "short")
    if longs and shorts:
        net_dir = None  # conflicting — confluence penalty, see below
    else:
        net_dir = "long" if longs else "short"

    # 1. CONFLUENCE (max 34) — heaviest single component
    agree = max(longs, shorts)
    if net_dir is None:
        score += 6                      # conflicting signals: weak, ambiguous
        reasons.append("Conflicting signals")
    elif agree >= 3:
        score += 34
        reasons.append("Triple-scanner confluence")
    elif agree == 2:
        score += 24
        reasons.append("Two scanners agree")
    else:
        score += 12
        reasons.append("Single scanner")

    # 2. TREND ALIGNMENT (max 26)
    if net_dir and weekly_trend in ("up", "down"):
        aligned = (net_dir == "long" and weekly_trend == "up") or \
                  (net_dir == "short" and weekly_trend == "down")
        if aligned:
            score += 26
            reasons.append(f"Aligned with weekly {weekly_trend}-trend")
        else:
            score += 4
            reasons.append("Counter-trend")
    else:
        score += 10  # trend sideways or signals conflicting — neutral credit

    # 3. CHANNEL STRENGTH (max 16) — a 55-day break is the real Turtle signal
    if turtle:
        if turtle["channel"] == "55-day":
            score += 16
            reasons.append("55-day channel break")
        else:
            score += 8
            reasons.append("20-day channel break")

    # 4. VOLUME / MOMENTUM CONFIRMATION (max 14)
    if snap and snap.get("vol_x"):
        vx = snap["vol_x"]
        if vx >= 2.5:
            score += 14; reasons.append(f"Volume surge {vx}x")
        elif vx >= 1.5:
            score += 9; reasons.append(f"Volume confirmed {vx}x")
    elif snap:
        score += 6

    # 5. MOMENTUM EXTREMITY (max 10) — MACD fresh cross + RSI stretch
    macd_state = ind_macd_state_from_df(df)
    if "cross" in macd_state.lower():
        score += 6
        reasons.append(f"MACD {macd_state.lower()}")
    rsi_now = float(df["rsi"].iloc[-1])
    if rsi_now >= 75 or rsi_now <= 25:
        score += 4
        reasons.append(f"RSI stretched ({rsi_now:.0f})")

    return round(min(100, score), 1), reasons


def ind_macd_state_from_df(df):
    """Small helper: recompute MACD state from the df's macd_hist column."""
    hist = df["macd_hist"].dropna()
    if len(hist) < 2:
        return "Flat"
    h, p = hist.iloc[-1], hist.iloc[-2]
    if p <= 0 < h:
        return "Bullish cross"
    if p >= 0 > h:
        return "Bearish cross"
    return "Bullish" if h > 0 else "Bearish" if h < 0 else "Flat"


def conviction_tier(score):
    """Map a conviction score to a label/tier used by the dashboard."""
    if score >= 70:
        return "hot"       # elevated 'hot' treatment
    if score >= 50:
        return "strong"
    if score >= 30:
        return "moderate"
    return "weak"


# Dynamic 'hot' threshold: an asset is HOT if its score clears HOT_THRESHOLD.
# Quiet day -> few or none qualify; wild day -> many. Honest to conditions.
HOT_THRESHOLD = 70
