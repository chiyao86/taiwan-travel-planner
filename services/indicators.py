"""共用技術指標計算模組 — RSI / MACD"""

import pandas as pd


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    計算 RSI (Relative Strength Index) 相對強弱指標

    Args:
        series: 價格序列 (通常是收盤價)
        period: RSI 計算週期 (預設 14 天)

    Returns:
        RSI 值序列 (0-100)
    """
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    計算 MACD (Moving Average Convergence Divergence) 指標

    Args:
        series: 價格序列 (通常是收盤價)
        fast: 快線EMA週期 (預設 12)
        slow: 慢線EMA週期 (預設 26)
        signal: 訊號線EMA週期 (預設 9)

    Returns:
        (macd, signal_line, histogram)
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram
