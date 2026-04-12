import logging
import yfinance as yf
import pandas as pd
import requests
from config import ALPHA_VANTAGE_API_KEY

log = logging.getLogger(__name__)


def _get_via_yfinance() -> pd.DataFrame:
    """yfinanceからUSD/JPYの15分足データを取得する"""
    ticker = yf.Ticker("USDJPY=X")
    df = ticker.history(period="30d", interval="15m")
    if df is None or df.empty:
        raise ValueError("yfinance: データが空です")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df.index = df.index.tz_localize(None)
    return df[["open", "high", "low", "close"]]


def _get_via_alpha_vantage() -> pd.DataFrame:
    """Alpha VantageからUSD/JPYの15分足データを取得する（フォールバック）"""
    if not ALPHA_VANTAGE_API_KEY:
        raise ValueError("ALPHA_VANTAGE_API_KEY が未設定です")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": "USD",
        "to_symbol": "JPY",
        "interval": "15min",
        "outputsize": "full",
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    key = "Time Series FX (15min)"
    if key not in data:
        raise ValueError(f"Alpha Vantage: レスポンスに'{key}'がありません: {list(data.keys())}")

    rows = []
    for ts, vals in data[key].items():
        rows.append({
            "datetime": pd.Timestamp(ts),
            "open": float(vals["1. open"]),
            "high": float(vals["2. high"]),
            "low": float(vals["3. low"]),
            "close": float(vals["4. close"]),
        })

    df = pd.DataFrame(rows).set_index("datetime").sort_index()
    return df[["open", "high", "low", "close"]]


def get_forex_data() -> pd.DataFrame:
    """USD/JPYの15分足データを取得する（yfinance優先・Alpha Vantageフォールバック）"""
    try:
        df = _get_via_yfinance()
        log.debug("yfinanceからデータ取得成功")
        return df
    except Exception as e:
        log.warning(f"yfinance失敗、Alpha Vantageにフォールバック: {e}")

    try:
        df = _get_via_alpha_vantage()
        log.info("Alpha Vantageからデータ取得成功")
        return df
    except Exception as e:
        raise ValueError(f"データ取得失敗（yfinance・Alpha Vantage両方）: {e}")
