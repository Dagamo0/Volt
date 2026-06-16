"""
VOLT — Technical indicators
Pure functions operating on pandas Series/DataFrames. No network calls.
Each computes the standard textbook version of the indicator.
"""
import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (EMA with alpha = 1/period)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # When avg_loss is 0, RSI is 100 by definition
    out = out.where(avg_loss != 0, 100.0)
    return out


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def macd_state(macd_line: pd.Series, signal_line: pd.Series, hist: pd.Series) -> str:
    """Human-readable MACD state, including fresh-cross detection."""
    if len(hist.dropna()) < 2:
        return "Flat"
    h_now, h_prev = hist.iloc[-1], hist.iloc[-2]
    if h_prev <= 0 < h_now:
        return "Bullish cross"
    if h_prev >= 0 > h_now:
        return "Bearish cross"
    if h_now > 0:
        return "Bullish"
    if h_now < 0:
        return "Bearish"
    return "Flat"


def rolling_extreme(series: pd.Series, window: int, kind: str) -> pd.Series:
    """Rolling high or low over `window`, EXCLUDING the current bar.
    Used for Turtle channel breakouts (breakout = today vs prior N days)."""
    shifted = series.shift(1)
    if kind == "high":
        return shifted.rolling(window).max()
    return shifted.rolling(window).min()


def average_daily_range(high: pd.Series, low: pd.Series, period: int = 20) -> pd.Series:
    """Average of (high-low) over period — used by snap-back to define 'abnormal' move."""
    return (high - low).rolling(period).mean()


def weekly_trend(close_daily: pd.Series) -> str:
    """Classify the weekly trend from daily closes.
    Up   = weekly 10-EMA rising and price above it.
    Down = weekly 10-EMA falling and price below it.
    Else = sideways."""
    weekly = close_daily.resample("W").last().dropna()
    if len(weekly) < 12:
        return "sideways"
    ema = weekly.ewm(span=10, adjust=False).mean()
    rising = ema.iloc[-1] > ema.iloc[-3]
    falling = ema.iloc[-1] < ema.iloc[-3]
    price_above = weekly.iloc[-1] > ema.iloc[-1]
    if rising and price_above:
        return "up"
    if falling and not price_above:
        return "down"
    return "sideways"
