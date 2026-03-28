import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
PAT_TOKEN = os.getenv("PAT_TOKEN")

# 通貨ペア
SYMBOL_FROM = "USD"
SYMBOL_TO = "JPY"
TIMEFRAME = "15min"

# 戦略パラメータ
MA_SHORT = 5
MA_LONG = 20
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
