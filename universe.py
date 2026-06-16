"""
VOLT — Scan universe
The WIDE list the background scanner sweeps each day. Separate from config.WATCHLIST
(your pinned focus-15). The dashboard surfaces only assets that fire a signal,
so a large universe here = more opportunities found, not more to read.

Structure: each entry is (yf_symbol, display_ticker, category).
categories: ai, crypto, commodity, index, forex, momentum, equity

S&P 500 members are fetched live from Wikipedia at build time (in fetch.py) so the
list stays current automatically; if that fetch fails we fall back to SP500_FALLBACK
below. Everything else is curated here.
"""

# ─── Non-equity / curated buckets ─────────────────────────────────────────────
FOREX = [
    ("EURUSD=X", "EUR/USD", "forex"), ("GBPUSD=X", "GBP/USD", "forex"),
    ("USDJPY=X", "USD/JPY", "forex"), ("AUDUSD=X", "AUD/USD", "forex"),
    ("USDCAD=X", "USD/CAD", "forex"), ("USDCHF=X", "USD/CHF", "forex"),
    ("NZDUSD=X", "NZD/USD", "forex"), ("EURGBP=X", "EUR/GBP", "forex"),
    ("DX=F", "DXY (Dollar Index)", "forex"),
]

CRYPTO = [
    ("BTC-USD", "BTC", "crypto"), ("ETH-USD", "ETH", "crypto"),
    ("SOL-USD", "SOL", "crypto"), ("XRP-USD", "XRP", "crypto"),
    ("BNB-USD", "BNB", "crypto"), ("DOGE-USD", "DOGE", "crypto"),
    ("ADA-USD", "ADA", "crypto"), ("AVAX-USD", "AVAX", "crypto"),
    ("LINK-USD", "LINK", "crypto"),
]

COMMODITY = [
    ("GC=F", "Gold", "commodity"), ("SI=F", "Silver", "commodity"),
    ("CL=F", "Crude Oil (WTI)", "commodity"), ("BZ=F", "Brent Crude", "commodity"),
    ("NG=F", "Natural Gas", "commodity"), ("HG=F", "Copper", "commodity"),
    ("PL=F", "Platinum", "commodity"), ("PA=F", "Palladium", "commodity"),
    ("ZC=F", "Corn", "commodity"), ("ZW=F", "Wheat", "commodity"),
]

INDEX = [
    ("SPY", "SPY", "index"), ("QQQ", "QQQ", "index"), ("DIA", "DIA", "index"),
    ("IWM", "IWM (Russell 2k)", "index"), ("^VIX", "VIX", "index"),
    ("^GSPC", "S&P 500", "index"), ("^IXIC", "Nasdaq Comp", "index"),
    ("^DJI", "Dow Jones", "index"), ("^FTSE", "FTSE 100", "index"),
    ("^N225", "Nikkei 225", "index"), ("^GDAXI", "DAX", "index"),
    ("^HSI", "Hang Seng", "index"),
]

# High-beta / social-momentum movers — the catalyst plays snap-back targets.
MOMENTUM = [
    ("PLTR", "PLTR", "momentum"), ("COIN", "COIN", "momentum"),
    ("MSTR", "MSTR", "momentum"), ("SMCI", "SMCI", "momentum"),
    ("TSLA", "TSLA", "momentum"), ("MARA", "MARA", "momentum"),
    ("RIOT", "RIOT", "momentum"), ("AFRM", "AFRM", "momentum"),
    ("SOFI", "SOFI", "momentum"), ("RDDT", "RDDT", "momentum"),
    ("HOOD", "HOOD", "momentum"), ("DKNG", "DKNG", "momentum"),
    ("RBLX", "RBLX", "momentum"), ("NFLX", "NFLX", "momentum"),
    ("META", "META", "momentum"), ("AMZN", "AMZN", "momentum"),
    ("SHOP", "SHOP", "momentum"), ("CRWD", "CRWD", "momentum"),
    ("SNOW", "SNOW", "momentum"), ("DELL", "DELL", "momentum"),
]

# Fallback S&P 500 list (used only if the live Wikipedia fetch fails).
# Trimmed to the most liquid ~60 to keep the file readable; live fetch gets all 500.
SP500_FALLBACK = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","BRK-B","LLY","AVGO",
    "TSLA","JPM","V","UNH","XOM","MA","JNJ","PG","HD","COST",
    "ABBV","MRK","CVX","ADBE","CRM","WMT","PEP","KO","BAC","ACN",
    "AMD","NFLX","MCD","TMO","CSCO","ABT","LIN","INTC","WFC","DIS",
    "QCOM","TXN","DHR","VZ","INTU","CMCSA","PM","AMGN","NOW","NKE",
    "IBM","UNP","HON","GE","CAT","BA","GS","SPGI","RTX","ISRG",
]


def equity_category(sym):
    """Tag well-known AI/chip names so they route to the AI bucket and snap-back scanner."""
    ai_chips = {"NVDA","AMD","TSM","ARM","MSFT","AVGO","GOOGL","GOOG","INTC",
                "QCOM","MU","AMAT","LRCX","ASML","MRVL","ADI","TXN","SMCI"}
    return "ai" if sym in ai_chips else "equity"


def curated_non_equity():
    """All the hand-maintained non-S&P buckets as one list of dicts."""
    out = []
    for bucket in (FOREX, CRYPTO, COMMODITY, INDEX, MOMENTUM):
        for yf_sym, disp, cat in bucket:
            out.append({"yf": yf_sym, "ticker": disp, "category": cat})
    return out
