import json
import os
import sys
from datetime import datetime, timedelta

TRADES_FILE = "trades.json"
SIGNALS_FILE = "signals_log.json"
STATS_FILE = "logs/stats_report.md"
INITIAL_BALANCE = 100_000.0


def _load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _calc_trade_stats(trades):
    if not trades:
        return {
            "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_pnl": 0.0, "max_streak_win": 0, "max_streak_loss": 0,
            "max_drawdown": 0.0, "current_balance": INITIAL_BALANCE,
        }

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(wins) / len(trades) * 100
    total_pnl = sum(t["pnl"] for t in trades)
    current_balance = trades[-1]["balance"]

    # 最大連勝・連敗
    max_win_streak = max_loss_streak = cur = 0
    last = None
    for t in trades:
        if t["pnl"] > 0:
            cur = cur + 1 if last == "win" else 1
            last = "win"
            max_win_streak = max(max_win_streak, cur)
        else:
            cur = cur + 1 if last == "loss" else 1
            last = "loss"
            max_loss_streak = max(max_loss_streak, cur)

    # 最大ドローダウン
    peak = INITIAL_BALANCE
    max_dd = 0.0
    balance = INITIAL_BALANCE
    for t in trades:
        balance += t["pnl"]
        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "max_streak_win": max_win_streak,
        "max_streak_loss": max_loss_streak,
        "max_drawdown": max_dd,
        "current_balance": current_balance,
    }


def _calc_signal_stats(signals):
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    recent = [
        s for s in signals
        if datetime.fromisoformat(s["timestamp"]) >= week_ago
    ]

    buy = sum(1 for s in recent if s["signal"] == 1)
    sell = sum(1 for s in recent if s["signal"] == -1)
    none = sum(1 for s in recent if s["signal"] == 0)
    total = len(recent)
    rate = (buy + sell) / total * 100 if total else 0.0

    last_signal = next(
        (s for s in reversed(signals) if s["signal"] != 0), None
    )

    return {
        "total": total,
        "buy": buy,
        "sell": sell,
        "none": none,
        "rate": rate,
        "last_signal": last_signal,
    }


def _signal_label(signal):
    if signal == 1:
        return "BUY "
    if signal == -1:
        return "SELL"
    return "--- "


def _action_label(action):
    labels = {
        "entry": "エントリー",
        "skip(position)": "スキップ(ポジションあり)",
        "watch": "なし",
    }
    return labels.get(action, action)


def generate(save=False):
    trades = _load_json(TRADES_FILE)
    signals = _load_json(SIGNALS_FILE)

    ts = _calc_trade_stats(trades)
    ss = _calc_signal_stats(signals)

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  FX Bot 成績レポート — {today}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "【取引成績】",
        f"  取引数: {ts['total']} | 勝: {ts['wins']} / 負: {ts['losses']}",
        f"  勝率: {ts['win_rate']:.1f}%",
        f"  累計PnL: {ts['total_pnl']:+,.0f}円",
        f"  最大連勝: {ts['max_streak_win']} | 最大連敗: {ts['max_streak_loss']}",
        f"  最大ドローダウン: -{ts['max_drawdown']:,.0f}円",
        f"  現在残高: {ts['current_balance']:,.0f}円（初期: 100,000円）",
        "",
        "【シグナル統計（直近7日）】",
        f"  総サイクル: {ss['total']}回",
        f"  シグナル発生: 買い {ss['buy']}回 / 売り {ss['sell']}回 / なし {ss['none']}回",
        f"  シグナル発生率: {ss['rate']:.1f}%",
    ]

    if ss["last_signal"]:
        ts_str = ss["last_signal"]["timestamp"][:16].replace("T", " ")
        direction = "BUY" if ss["last_signal"]["signal"] == 1 else "SELL"
        lines.append(f"  最後のシグナル: {ts_str} {direction}")
    else:
        lines.append("  最後のシグナル: 記録なし")

    lines += ["", "【シグナル タイムライン（直近10件）】"]

    recent_10 = signals[-10:] if len(signals) >= 10 else signals
    for s in reversed(recent_10):
        ts_str = s["timestamp"][:16].replace("T", " ")
        sig = _signal_label(s["signal"])
        price = s["price"]
        action = _action_label(s["action"])
        lines.append(f"  {ts_str}  {sig}  @ {price:.3f}  → {action}")

    if not recent_10:
        lines.append("  記録なし")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    output = "\n".join(lines)
    print(output)

    if save:
        os.makedirs("logs", exist_ok=True)
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            f.write(output)

    return output


if __name__ == "__main__":
    save_flag = "--save" in sys.argv
    generate(save=save_flag)
