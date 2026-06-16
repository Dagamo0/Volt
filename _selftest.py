"""
VOLT self-test — runs WITHOUT network. Builds synthetic OHLCV with known
properties and asserts each indicator/scanner produces the expected result.
This verifies the math + signal logic before live deployment.
"""
import numpy as np
import pandas as pd
import datetime as dt

import config, indicators as ind, signals as sig, catalysts as cat

th = config.THRESHOLDS["aggressive"]
PASS, FAIL = 0, 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS  {name}")
    else:
        FAIL += 1; print(f"  FAIL  {name}")

def make_df(closes, highs=None, lows=None, opens=None, vols=None):
    n = len(closes)
    idx = pd.date_range(end=dt.date.today(), periods=n, freq="D")
    closes = np.array(closes, float)
    highs = np.array(highs, float) if highs is not None else closes * 1.01
    lows = np.array(lows, float) if lows is not None else closes * 0.99
    opens = np.array(opens, float) if opens is not None else closes
    vols = np.array(vols, float) if vols is not None else np.full(n, 1e6)
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols}, index=idx)
    df["rsi"] = ind.rsi(df["Close"], 14)
    df["atr"] = ind.atr(df["High"], df["Low"], df["Close"], 14)
    _, _, hist = ind.macd(df["Close"])
    df["macd_hist"] = hist
    return df

print("\n── Indicator sanity ──")
# RSI: straight uptrend -> RSI near 100; straight downtrend -> near 0
up = make_df(list(range(100, 200)))
down = make_df(list(range(200, 100, -1)))
check("RSI high in pure uptrend (>80)", up["rsi"].iloc[-1] > 80)
check("RSI low in pure downtrend (<20)", down["rsi"].iloc[-1] < 20)
check("ATR positive", up["atr"].iloc[-1] > 0)
check("RSI bounded 0-100", up["rsi"].dropna().between(0, 100).all())

print("\n── Turtle breakout ──")
# 70 flat days at 100, then a push to a new high at 108 today
closes = [100]*70 + [101,102,103,104,105,106,107,108]
df = make_df(closes, highs=[c*1.005 for c in closes], lows=[c*0.995 for c in closes])
t = sig.turtle_breakout(df, th, 100000, 1.0, 2.0)
check("Turtle fires on new high", t is not None and t["direction"] == "long")
check("Turtle position size computed", t and t["size"]["shares"] > 0)
check("Turtle stop below entry for long", t and t["stop"] < t["entry"])
check("Turtle dollar risk = 1% of 100k = 1000", t and abs(t["size"]["dollar_risk"] - 1000) < 0.01)

# Breakdown case
closes_d = [100]*70 + [99,98,97,96,95,94,93,92]
dfd = make_df(closes_d, highs=[c*1.005 for c in closes_d], lows=[c*0.995 for c in closes_d])
td = sig.turtle_breakout(dfd, th, 100000, 1.0, 2.0)
check("Turtle fires short on new low", td is not None and td["direction"] == "short")
check("Turtle stop above entry for short", td and td["stop"] > td["entry"])

# No breakout in pure chop
chop = [100 + (i%2) for i in range(80)]
dfc = make_df(chop)
check("Turtle silent in chop", sig.turtle_breakout(dfc, th, 100000, 1.0, 2.0) is None)

print("\n── Snap-back ──")
# Build an uptrending, overbought chip stock then a huge up-spike today on big volume
base = list(np.linspace(100, 140, 60))
closes = base + [141,142,143,144,160]   # last bar gaps up hard
highs  = [c*1.01 for c in closes]; highs[-1] = closes[-1]*1.02
lows   = [c*0.99 for c in closes]; lows[-1] = closes[-2]*0.995
opens  = closes[:]; opens[-1] = 145     # opened lower, closed way up = big positive day
vols   = [1e6]*64 + [5e6]
dfs = make_df(closes, highs=highs, lows=lows, opens=opens, vols=vols)
# widen today's range so it's clearly >2x ADR
dfs.loc[dfs.index[-1], "High"] = 165
dfs.loc[dfs.index[-1], "Low"] = 144
s = sig.snapback(dfs, th, "ai")
check("Snapback fires on abnormal overbought spike (AI)", s is not None and s["direction"] == "short")
check("Snapback move_mult >= 2", s and s["move_mult"] >= 2.0)
check("Snapback ignored for commodity category", sig.snapback(dfs, th, "commodity") is None)

# Volume filter: same spike but LOW volume should be suppressed (aggressive keeps vol ON)
dfs_lowvol = dfs.copy(); dfs_lowvol.loc[dfs_lowvol.index[-1], "Volume"] = 8e5
check("Snapback suppressed when volume not confirmed", sig.snapback(dfs_lowvol, th, "ai") is None)

print("\n── Swing setup ──")
# Weekly uptrend with a recent daily pullback then turn-up
n = 160
trend = np.linspace(80, 160, n)
noise = np.zeros(n)
# carve a pullback in the last ~6 days then tick up
closes = list(trend)
for i in range(7, 1, -1):
    closes[-i] = closes[-i] - 14   # deeper pullback to push daily RSI down
closes[-1] = closes[-2] + 3        # momentum turning up today
dfw = make_df(closes)
wk = ind.weekly_trend(dfw["Close"])
check("Weekly trend reads UP on rising series", wk == "up")
sw = sig.swing_setup(dfw, th)
check("Swing setup fires in uptrend pullback", sw is not None and sw["direction"] == "long")

print("\n── Conviction scoring ──")
# A 55-day breakout aligned with weekly uptrend + a swing agreeing = high conviction
turtle_strong = {"type":"turtle","direction":"long","channel":"55-day","size":{}}
swing_agree = {"type":"swing","direction":"long","weekly_trend":"up","rsi":55}
snap_none = None
sc_hi, reasons_hi = sig.conviction_score(up, turtle_strong, swing_agree, snap_none, "up")
check("Aligned 55d breakout + swing scores high (>=60)", sc_hi >= 60)
check("Reasons include confluence", any("agree" in r.lower() or "confluence" in r.lower() for r in reasons_hi))
check("Reasons include 55-day", any("55-day" in r for r in reasons_hi))
check("Reasons include trend alignment", any("trend" in r.lower() for r in reasons_hi))

# A lone 20-day breakout against the trend = low conviction
turtle_weak = {"type":"turtle","direction":"long","channel":"20-day","size":{}}
sc_lo, reasons_lo = sig.conviction_score(down, turtle_weak, None, None, "down")
check("Lone counter-trend 20d break scores low (<40)", sc_lo < 40)
check("High conviction > low conviction", sc_hi > sc_lo)

# Conflicting signals score weak
sc_conf, _ = sig.conviction_score(up, turtle_strong, {"type":"swing","direction":"short","weekly_trend":"up","rsi":50}, None, "up")
check("Conflicting long+short scores below aligned", sc_conf < sc_hi)

# Nothing fired = 0
sc_zero, r_zero = sig.conviction_score(up, None, None, None, "up")
check("No signal = 0 conviction", sc_zero == 0 and r_zero == [])

# Tiers
check("Score 75 -> hot tier", sig.conviction_tier(75) == "hot")
check("Score 35 -> moderate tier", sig.conviction_tier(35) == "moderate")
check("Score 10 -> weak tier", sig.conviction_tier(10) == "weak")

print("\n── Catalyst calendar ──")
ev = cat.macro_events(dt.date(2026,6,1), dt.date(2026,6,30))
check("June 2026 has FOMC on the 17th", any(e["date"]=="2026-06-17" and "FOMC" in e["text"] for e in ev))
check("June 2026 has triple-witching (3rd Fri = 19th)", any(e["date"]=="2026-06-19" and "Triple" in e["text"] for e in ev))
check("June 2026 has NFP first Friday (5th)", any(e["date"]=="2026-06-05" and "Payroll" in e["text"] for e in ev))
check("Macro events all tagged macro", all(e["tag"]=="macro" for e in ev))

print(f"\n{'='*40}\nRESULT: {PASS} passed, {FAIL} failed\n{'='*40}")
import sys; sys.exit(1 if FAIL else 0)
