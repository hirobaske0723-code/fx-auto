import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# 通貨ペア
SYMBOL_FROM = "USD"
SYMBOL_TO = "JPY"
TIMEFRAME = "60min"

# 戦略パラメータ
MA_SHORT = 20
MA_LONG = 50
RSI_PERIOD = 14

# 発注
LOT_SIZE = 0.01        # 0.01ロット
PIP_SIZE = 0.01        # USD/JPYの1pip
UNITS = int(LOT_SIZE * 100_000)  # 1000通貨

# リスク管理
STOP_LOSS_PIPS = 10
TAKE_PROFIT_PIPS = 15
DAILY_LOSS_LIMIT_PCT = 0.03   # 3%

# 仮想残高（ペーパートレード）
INITIAL_BALANCE = 100_000     # 100,000円
