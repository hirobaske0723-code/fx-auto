import yfinance as yf
import pandas as pd


def get_forex_data() -> pd.DataFrame:
    """yfinanceからUSD/JPYの1時間足データを取得する（APIキー不要）"""
    ticker = yf.Ticker("USDJPY=X")
    df = ticker.history(period="30d", interval="1h")

    if df.empty:
        raise ValueError("yfinance: データが取得できませんでした")

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    df.index = df.index.tz_localize(None)
    return df[["open", "high", "low", "close"]]
