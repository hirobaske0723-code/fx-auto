import time
import os
import sys
import signal
import atexit
import json
import schedule
import logging
from datetime import datetime, timedelta
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
                save_trade(result)

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
# トレード記録（trades.jsonに追記）
# ──────────────────────────────
TRADES_FILE = "trades.json"
SIGNALS_FILE = "signals_log.json"


def save_signal(price: float, signal: int, rsi: float, ma_short: float, ma_long: float, action: str):
    signals = []
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
            signals = json.load(f)
    signals.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "price": round(price, 3),
        "signal": signal,
        "rsi": round(rsi, 1),
        "ma_short": round(ma_short, 3),
        "ma_long": round(ma_long, 3),
        "action": action,
    })
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)


def save_trade(trade: dict):
    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            trades = json.load(f)
    trade["timestamp"] = datetime.now().isoformat()
    trades.append(trade)
    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)


# ──────────────────────────────
# 週次レポート（毎週月曜0時）
# ──────────────────────────────
def weekly_report():
    since = datetime.now() - timedelta(days=7)
    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            all_trades = json.load(f)
        trades = [t for t in all_trades if datetime.fromisoformat(t["timestamp"]) >= since]

    total_pnl = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    log.info(f"週次レポート: {len(trades)}trades | PnL={total_pnl:+.0f}円 | 勝率={win_rate:.0f}%")

    from notifier import _send
    _send(
        f"📊 *週次レポート*\n"
        f"取引数: `{len(trades)}`（勝: {len(wins)} / 負: {len(losses)}）\n"
        f"勝率: `{win_rate:.0f}%`\n"
        f"週間損益: `{total_pnl:+.0f}円`\n"
        f"現在残高: `{trader.balance:,.0f}円`"
    )


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
    schedule.every().hour.at(":00").do(run_cycle)   # 15分足
    schedule.every().hour.at(":15").do(run_cycle)
    schedule.every().hour.at(":30").do(run_cycle)
    schedule.every().hour.at(":45").do(run_cycle)
    schedule.every().day.at("00:00").do(daily_reset)
    schedule.every().monday.at("00:00").do(weekly_report)

    # 起動時に即1回実行
    run_cycle()

    # メインループ
    while True:
        schedule.run_pending()
        time.sleep(30)
