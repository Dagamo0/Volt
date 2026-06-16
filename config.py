"""
VOLT — Configuration
Edit this file to change your watchlist, signal sensitivity, or account size.
This is the ONE file you'll touch for routine changes. Nothing else needs editing.
"""

# ─── Watchlist ────────────────────────────────────────────────────────────────
# To add an asset: copy a line, change the ticker/name/category/icon/color.
# category must be one of: 'ai', 'crypto', 'commodity', 'index'
# Yahoo Finance symbols: crypto uses -USD, futures use =F.

WATCHLIST = [
    # AI & Chips
    {"ticker": "NVDA",  "yf": "NVDA",    "name": "NVIDIA",                "category": "ai",        "icon": "NV", "color": "#76b900"},
    {"ticker": "AMD",   "yf": "AMD",     "name": "Advanced Micro Devices","category": "ai",        "icon": "AM", "color": "#ed1c24"},
    {"ticker": "TSM",   "yf": "TSM",     "name": "TSMC",                  "category": "ai",        "icon": "TS", "color": "#0070c0"},
    {"ticker": "ARM",   "yf": "ARM",     "name": "Arm Holdings",          "category": "ai",        "icon": "AR", "color": "#0091bd"},
    {"ticker": "MSFT",  "yf": "MSFT",    "name": "Microsoft",             "category": "ai",        "icon": "MS", "color": "#00a4ef"},
    {"ticker": "AVGO",  "yf": "AVGO",    "name": "Broadcom",              "category": "ai",        "icon": "AV", "color": "#cc092f"},
    {"ticker": "GOOGL", "yf": "GOOGL",   "name": "Alphabet",              "category": "ai",        "icon": "GO", "color": "#4285f4"},
    # Crypto
    {"ticker": "BTC",   "yf": "BTC-USD", "name": "Bitcoin",               "category": "crypto",    "icon": "₿", "color": "#f7931a"},
    {"ticker": "ETH",   "yf": "ETH-USD", "name": "Ethereum",              "category": "crypto",    "icon": "Ξ", "color": "#627eea"},
    # Commodities
    {"ticker": "GC=F",  "yf": "GC=F",    "name": "Gold",                  "category": "commodity", "icon": "Au", "color": "#d4af37"},
    {"ticker": "CL=F",  "yf": "CL=F",    "name": "Crude Oil (WTI)",       "category": "commodity", "icon": "○", "color": "#8b4513"},
    # Indices
    {"ticker": "SPY",   "yf": "SPY",     "name": "S&P 500 ETF",           "category": "index",     "icon": "SP", "color": "#1a73e8"},
    {"ticker": "QQQ",   "yf": "QQQ",     "name": "Nasdaq-100 ETF",        "category": "index",     "icon": "NQ", "color": "#4285f4"},
    {"ticker": "DIA",   "yf": "DIA",     "name": "Dow Jones ETF",         "category": "index",     "icon": "DJ", "color": "#1a73e8"},
]

# ─── Signal sensitivity ───────────────────────────────────────────────────────
# Set to 'conservative', 'balanced', or 'aggressive'.
# Aggressive = more signals, earlier flags, more to review.
SENSITIVITY = "aggressive"

THRESHOLDS = {
    "conservative": {
        "rsi_overbought": 75, "rsi_oversold": 25,
        "snapback_adr_mult": 2.5,   # move must be >= this x avg daily range
        "snapback_require_volume": True,
        "swing_pullback_rsi": 40,   # daily RSI must dip below this in an uptrend
        "breakout_buffer": 0.000,   # must clear the high by this fraction
    },
    "balanced": {
        "rsi_overbought": 70, "rsi_oversold": 30,
        "snapback_adr_mult": 2.0,
        "snapback_require_volume": True,
        "swing_pullback_rsi": 45,
        "breakout_buffer": 0.000,
    },
    "aggressive": {
        "rsi_overbought": 68, "rsi_oversold": 32,
        "snapback_adr_mult": 2.0,
        "snapback_require_volume": True,   # kept ON for chips — they fake out constantly
        "swing_pullback_rsi": 50,
        "breakout_buffer": -0.002,         # flags slightly BEFORE the high is cleared
    },
}

# ─── Position sizing (Turtle) ─────────────────────────────────────────────────
# Default account size — also editable live in the dashboard.
DEFAULT_ACCOUNT_SIZE = 100_000
RISK_PER_TRADE_PCT = 1.0   # % of account risked per trade (Turtle classic = 1-2%)
ATR_STOP_MULTIPLE = 2.0    # stop placed this many ATRs from entry

# ─── Data parameters ──────────────────────────────────────────────────────────
HISTORY_PERIOD = "1y"      # how much history to pull (need >55d for Turtle channels)
OUTPUT_FILE = "data.json"
