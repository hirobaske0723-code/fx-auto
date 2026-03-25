import time
import os
import sys
import signal
import atexit
import schedule
import logging
from market_data import get_forex_data
from strategy import calculate_signals
from paper_trader import PaperTrader
from risk_manager import RiskManager
from notifier import (
    notify_start, notify_open, notify_close,
    notify_risk_stop, notify_daily_reset, notify_error,
)

# ──────────────────────────────
# ログ設定
# ──────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fx_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ──────────────────────────────
# PIDロック（多重起動防止）
# ──────────────────────────────
PID_FILE = "fx_bot.pid"


def acquire_pid_lock():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
            log.info(f"旧プロセス (PID: {old_pid}) を停止しました")
            time.sleep(2)
        except Exception:
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(PID_FILE) if os.path.exists(PID_FILE) else None)


# ──────────────────────────────
# グローバルインスタンス
# ──────────────────────────────
trader = PaperTrader()
risk = RiskManager()


# ──────────────────────────────
# メインサイクル（毎時実行）
# ──────────────────────────────
def run_cycle():
    log.info("━━━ サイクル開始 ━━━")

    if not risk.can_trade():
        log.warning("デイリー損失上限により停止中。取引スキップ。")
        return

    try:
        # 1. 価格データ取得
        df = get_forex_data()
        df = calculate_signals(df)

        current_price = df["close"].iloc[-1]
        signal = int(df["signal"].iloc[-1])
        rsi = df["rsi"].iloc[-1]
        ma_s = df["ma_short"].iloc[-1]
        ma_l = df["ma_long"].iloc[-1]

        log.info(
            f"価格={current_price:.3f} | RSI={rsi:.1f} | "
            f"MA{20}={ma_s:.3f} | MA{50}={ma_l:.3f} | signal={signal}"
        )

        # 2. SL/TP チェック（ポジションあり時）
        if trader.position:
            result = trader.check_exit(current_price)
            if result:
                log.info(f"クローズ: {result['reason']} | PnL={result['pnl']:+.0f}円 | 残高={result['balance']:,.0f}円")
                risk.record_pnl(result["pnl"])
                notify_close(result)

                if not risk.can_trade():
                    notify_risk_stop(risk.daily_pnl, risk.daily_loss_limit_amount)
                    return

        # 3. エントリー（ポジションなし時）
        if trader.position is None:
            if signal == 1:
                trade = trader.open_long(current_price)
                if trade:
                    log.info(f"買いエントリー @ {current_price:.3f}")
                    notify_open(trade)
            elif signal == -1:
                trade = trader.open_short(current_price)
                if trade:
                    log.info(f"売りエントリー @ {current_price:.3f}")
                    notify_open(trade)
            else:
                log.info("シグナルなし。様子見。")

    except Exception as e:
        log.error(f"エラー: {e}", exc_info=True)
        notify_error(str(e))


# ──────────────────────────────
# デイリーリセット（毎日0時）
# ──────────────────────────────
def daily_reset():
    log.info("デイリーリセット")
    notify_daily_reset(risk.daily_pnl)
    risk.reset()


# ──────────────────────────────
# エントリーポイント
# ──────────────────────────────
if __name__ == "__main__":
    acquire_pid_lock()
    log.info("FX Bot 起動")
    notify_start()

    # スケジュール設定
    schedule.every().hour.at(":01").do(run_cycle)   # 毎時1分に実行
    schedule.every().day.at("00:00").do(daily_reset)

    # 起動時に即1回実行
    run_cycle()

    # メインループ
    while True:
        schedule.run_pending()
        time.sleep(30)
