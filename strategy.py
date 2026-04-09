import pandas as pd
from config import MA_SHORT, MA_LONG, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT


def calculate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    移動平均クロス + RSI によるシグナル判定
    signal: 1=買い, -1=売り, 0=様子見
    """
    df = df.copy()

    # 移動平均
    df["ma_short"] = df["close"].rolling(MA_SHORT).mean()
    df["ma_long"] = df["close"].rolling(MA_LONG).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # ゴールデンクロス / デッドクロス
    ma_cross_up = (df["ma_short"] > df["ma_long"]) & (
        df["ma_short"].shift(1) <= df["ma_long"].shift(1)
    )
    ma_cross_down = (df["ma_short"] < df["ma_long"]) & (
        df["ma_short"].shift(1) >= df["ma_long"].shift(1)
    )

    # シグナル：クロス + RSIフィルター
    df["signal"] = 0
    df.loc[ma_cross_up & (df["rsi"] < RSI_OVERSOLD), "signal"] = 1    # 買い
    df.loc[ma_cross_down & (df["rsi"] > RSI_OVERBOUGHT), "signal"] = -1  # 売り

    return df
