import requests
import certifi
import logging
from config import SLACK_WEBHOOK_URL

log = logging.getLogger(__name__)


def _send(message: str):
    if not SLACK_WEBHOOK_URL:
        log.info(f"[SLACK未設定] {message}")
        return
    try:
        r = requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=5, verify=certifi.where())
        r.raise_for_status()
    except Exception as e:
        log.warning(f"Slack通知失敗: {e}")


def notify_start():
    _send("🚀 *FX Bot 起動しました*（ペーパートレードモード）")


def notify_open(trade: dict):
    direction_jp = "買い" if trade["direction"] == "long" else "売り"
    emoji = "🟢" if trade["direction"] == "long" else "🔴"
    _send(
        f"{emoji} *エントリー [{direction_jp}]*\n"
        f"価格: `{trade['price']:.3f}`\n"
        f"SL: `{trade['sl']:.3f}` | TP: `{trade['tp']:.3f}`"
    )


def notify_close(trade: dict):
    pnl_emoji = "✅" if trade["pnl"] >= 0 else "❌"
    direction_jp = "買い" if trade["direction"] == "long" else "売り"
    _send(
        f"{pnl_emoji} *クローズ [{trade['reason']}] ({direction_jp})*\n"
        f"`{trade['entry_price']:.3f}` → `{trade['exit_price']:.3f}`\n"
        f"損益: `{trade['pnl']:+.0f}円` | 残高: `{trade['balance']:,.0f}円`"
    )


def notify_risk_stop(daily_pnl: float, limit: float):
    _send(
        f"🛑 *デイリー損失上限に達しました*\n"
        f"本日の損失: `{daily_pnl:+.0f}円`（上限: {limit:.0f}円）\n"
        f"本日の取引を停止します。"
    )


def notify_daily_reset(daily_pnl: float):
    emoji = "📈" if daily_pnl >= 0 else "📉"
    _send(
        f"{emoji} *デイリーリセット*\n"
        f"昨日の損益: `{daily_pnl:+.0f}円`\n"
        f"本日の取引を開始します。"
    )


def notify_error(error: str):
    _send(f"⚠️ *エラー発生*\n```{error}```")
