"""
VOLT — Catalyst calendar
Three sources:
  1. Earnings dates  — pulled per-stock from yfinance (best-effort; isolated).
  2. Macro events    — Fed/CPI/NFP, derived from known recurring schedules.
  3. Options expiry  — standard monthly (3rd Friday) + quarterly triple-witching.

Macro dates: US CPI and NFP follow predictable monthly cadences but exact dates
shift, so we APPROXIMATE forward and clearly tag them as scheduled estimates.
FOMC meeting dates are fixed and published a year ahead — hardcoded below and
trivially updatable once a year in FOMC_DATES.
"""
import datetime as dt
import calendar


# FOMC decision dates — published by the Fed ~1yr ahead. Update once a year.
# 2025-2026 schedule (decision day = 2nd day of each meeting).
FOMC_DATES = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]


def third_friday(year, month):
    """3rd Friday of a month = standard US monthly options expiry."""
    c = calendar.Calendar()
    fridays = [d for d in c.itermonthdates(year, month)
               if d.month == month and d.weekday() == 4]
    return fridays[2]


def first_friday(year, month):
    """First Friday — NFP (jobs report) is released the first Friday of each month."""
    c = calendar.Calendar()
    fridays = [d for d in c.itermonthdates(year, month)
               if d.month == month and d.weekday() == 4]
    return fridays[0]


def macro_events(start: dt.date, end: dt.date):
    """Generate macro catalyst events between start and end (inclusive)."""
    events = []

    # FOMC (exact, hardcoded)
    for s in FOMC_DATES:
        d = dt.date.fromisoformat(s)
        if start <= d <= end:
            events.append({"date": d.isoformat(), "text": "FOMC rate decision", "tag": "macro", "scope": "all"})

    # Walk each month in range for NFP, CPI, options expiry
    y, m = start.year, start.month
    while dt.date(y, m, 1) <= end:
        # NFP — first Friday
        nfp = first_friday(y, m)
        if start <= nfp <= end:
            events.append({"date": nfp.isoformat(), "text": "Non-Farm Payrolls (jobs report)", "tag": "macro", "scope": "all"})
        # CPI — typically mid-month (~10th-14th business day). Approximate to 2nd Wednesday, tagged est.
        c = calendar.Calendar()
        weds = [d for d in c.itermonthdates(y, m) if d.month == m and d.weekday() == 2]
        cpi = weds[1]
        if start <= cpi <= end:
            events.append({"date": cpi.isoformat(), "text": "US CPI inflation data (est.)", "tag": "macro", "scope": "all"})
        # Options expiry — 3rd Friday
        opex = third_friday(y, m)
        if start <= opex <= end:
            quarterly = m in (3, 6, 9, 12)
            events.append({
                "date": opex.isoformat(),
                "text": "Triple-witching options expiry" if quarterly else "Monthly options expiry",
                "tag": "macro", "scope": "all",
            })
        # advance month
        m += 1
        if m > 12:
            m, y = 1, y + 1

    return events


def earnings_date(yf_ticker_obj):
    """Best-effort next earnings date from a yfinance Ticker. Returns ISO date or None.
    Wrapped by caller in try/except so a failure never breaks the run."""
    try:
        cal = yf_ticker_obj.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                d = ed[0] if isinstance(ed, (list, tuple)) else ed
                return d.isoformat() if hasattr(d, "isoformat") else str(d)
        # Older yfinance returns a DataFrame
        if hasattr(cal, "loc") and "Earnings Date" in getattr(cal, "index", []):
            d = cal.loc["Earnings Date"][0]
            return d.date().isoformat() if hasattr(d, "date") else str(d)
    except Exception:
        pass
    return None
