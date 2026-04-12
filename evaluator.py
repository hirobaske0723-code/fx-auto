"""
FX Bot 独立評価エージェント
5軸（収益性・リスク管理・戦略有効性・シグナル品質・システム安定性）をルールベースで評価する
FXは数値データが明確なのでLLM不要・客観スコアリング
"""
import json
import os
from datetime import datetime, timedelta

import logging
log = logging.getLogger(__name__)

TRADES_FILE = "trades.json"
SIGNALS_FILE = "signals_log.json"
LOG_FILE = "fx_bot.log"

try:
    from config import INITIAL_BALANCE
except ImportError:
    INITIAL_BALANCE = 100_000


def _load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_week_trades(all_trades: list, days: int = 7) -> list:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return [t for t in all_trades if t.get("timestamp", "") >= cutoff]


def _calc_profit_factor(trades: list) -> float:
    gains = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def _calc_max_drawdown_pct(all_trades: list) -> float:
    peak = INITIAL_BALANCE
    max_dd = 0.0
    balance = INITIAL_BALANCE
    for t in all_trades:
        balance += t["pnl"]
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _score(value, thresholds: list[tuple]) -> int:
    """
    thresholds: [(上限値, スコア), ...] を降順で評価
    例: [(10, 10), (8, 8), (5, 5)] → value>=10なら10点
    """
    for threshold, score in thresholds:
        if value >= threshold:
            return score
    return thresholds[-1][1]


# ─────────────────────────────────────────
# 軸別評価
# ─────────────────────────────────────────

def evaluate_profitability(all_trades: list, week_trades: list) -> dict:
    log.info("評価: 収益性")
    issues = []
    evidence = []

    total_pnl = sum(t["pnl"] for t in all_trades)
    week_pnl = sum(t["pnl"] for t in week_trades)
    balance = all_trades[-1]["balance"] if all_trades else INITIAL_BALANCE
    pf = _calc_profit_factor(all_trades)

    evidence.append(f"累積損益: {total_pnl:+,.0f}円")
    evidence.append(f"週間損益: {week_pnl:+,.0f}円")
    evidence.append(f"プロフィットファクター: {pf:.2f}")
    evidence.append(f"現在残高: {balance:,.0f}円")

    # スコアリング
    if total_pnl < 0:
        issues.append(f"累積損益がマイナス: {total_pnl:+,.0f}円")
        score = max(1, 4 - int(abs(total_pnl) / 5000))
    elif pf < 1.0:
        issues.append(f"プロフィットファクターが1未満: {pf:.2f}")
        score = 4
    elif pf < 1.3:
        issues.append(f"プロフィットファクターが目標(1.3)未達: {pf:.2f}")
        score = 6
    elif week_pnl < 0:
        issues.append(f"今週はマイナス: {week_pnl:+,.0f}円")
        score = 7
    else:
        score = _score(pf, [(2.0, 10), (1.5, 9), (1.3, 8)])

    return {"axis": "収益性", "score": score, "issues": issues, "evidence": evidence,
            "data": {"total_pnl": total_pnl, "week_pnl": week_pnl, "pf": pf, "balance": balance}}


def evaluate_risk_management(all_trades: list, week_trades: list) -> dict:
    log.info("評価: リスク管理")
    issues = []
    evidence = []

    max_dd_pct = _calc_max_drawdown_pct(all_trades)

    # デイリー損失上限発動カウント
    daily_pnl: dict[str, float] = {}
    for t in all_trades:
        day = t.get("timestamp", "")[:10]
        daily_pnl[day] = daily_pnl.get(day, 0) + t["pnl"]
    risk_stop_days = sum(1 for v in daily_pnl.values() if v <= -(INITIAL_BALANCE * 0.03))

    week_losses = [t["pnl"] for t in week_trades if t["pnl"] < 0]
    max_single_loss = min(week_losses) if week_losses else 0

    evidence.append(f"最大ドローダウン: {max_dd_pct:.1f}%（基準: 15%未満）")
    evidence.append(f"デイリー損失上限発動: {risk_stop_days}回")
    evidence.append(f"週間最大単発損失: {max_single_loss:+,.0f}円")

    if max_dd_pct >= 15:
        issues.append(f"最大ドローダウンが基準超え: {max_dd_pct:.1f}%（基準: 15%未満）")
        score = max(1, int(10 - max_dd_pct / 3))
    elif max_dd_pct >= 10:
        issues.append(f"最大ドローダウンが警戒水準: {max_dd_pct:.1f}%")
        score = 6
    else:
        score = _score(100 - max_dd_pct, [(98, 10), (95, 9), (90, 8), (85, 7)])

    if risk_stop_days >= 3:
        issues.append(f"デイリー損失上限が頻発: {risk_stop_days}回")
        score = max(1, score - 2)

    return {"axis": "リスク管理", "score": score, "issues": issues, "evidence": evidence,
            "data": {"max_dd_pct": max_dd_pct, "risk_stop_days": risk_stop_days}}


def evaluate_strategy_effectiveness(all_trades: list) -> dict:
    log.info("評価: 戦略有効性")
    issues = []
    evidence = []

    if not all_trades:
        return {"axis": "戦略有効性", "score": 0, "issues": ["取引データなし"], "evidence": [],
                "data": {"win_rate": 0, "pf": 0, "total": 0}}

    wins = [t for t in all_trades if t["pnl"] > 0]
    win_rate = len(wins) / len(all_trades) * 100
    pf = _calc_profit_factor(all_trades)
    tp_exits = sum(1 for t in all_trades if t.get("reason") == "TP")
    sl_exits = sum(1 for t in all_trades if t.get("reason") == "SL")

    evidence.append(f"勝率: {win_rate:.1f}%（SL10/TP15設定では45%以上でプラス期待値）")
    evidence.append(f"プロフィットファクター: {pf:.2f}（目標: 1.3以上）")
    evidence.append(f"TP達成: {tp_exits}回 / SL発動: {sl_exits}回")
    evidence.append(f"総取引数: {len(all_trades)}件")

    if len(all_trades) < 10:
        issues.append(f"サンプル数が少なすぎる: {len(all_trades)}件（統計的に不安定）")
        score = 3
    elif win_rate < 40:
        issues.append(f"勝率が低い: {win_rate:.1f}%（最低ライン45%未達）")
        score = max(2, int(win_rate / 10))
    elif pf < 1.0:
        issues.append(f"プロフィットファクターが1未満: {pf:.2f}")
        score = 4
    elif pf < 1.3:
        issues.append(f"プロフィットファクターが目標未達: {pf:.2f}（目標: 1.3以上）")
        score = 6
    else:
        score = _score(win_rate, [(60, 10), (55, 9), (50, 8), (45, 7)])

    return {"axis": "戦略有効性", "score": score, "issues": issues, "evidence": evidence,
            "data": {"win_rate": win_rate, "pf": pf, "total": len(all_trades),
                     "tp_exits": tp_exits, "sl_exits": sl_exits}}


def evaluate_signal_quality(signals: list) -> dict:
    log.info("評価: シグナル品質")
    issues = []
    evidence = []

    week_ago = datetime.now() - timedelta(days=7)
    week_signals = [
        s for s in signals
        if datetime.fromisoformat(s["timestamp"]) >= week_ago
    ]

    total = len(week_signals)
    buy_cnt = sum(1 for s in week_signals if s["signal"] == 1)
    sell_cnt = sum(1 for s in week_signals if s["signal"] == -1)
    signal_rate = (buy_cnt + sell_cnt) / total * 100 if total else 0

    evidence.append(f"週間サイクル数: {total}回")
    evidence.append(f"買い: {buy_cnt}回 / 売り: {sell_cnt}回")
    evidence.append(f"シグナル発生率: {signal_rate:.1f}%")

    if total == 0:
        issues.append("直近7日間のシグナルデータなし（ボット停止の可能性）")
        return {"axis": "シグナル品質", "score": 0, "issues": issues, "evidence": evidence,
                "data": {"total": 0, "signal_rate": 0}}

    if signal_rate > 20:
        issues.append(f"シグナル発生率が高すぎる: {signal_rate:.1f}%（RSIフィルターが機能していない可能性）")
        score = 4
    elif signal_rate < 2:
        issues.append(f"シグナル発生率が低すぎる: {signal_rate:.1f}%（条件が厳しすぎる可能性）")
        score = 5
    else:
        score = 8

    # 買い/売りの極端な偏りチェック
    if (buy_cnt + sell_cnt) > 0:
        buy_ratio = buy_cnt / (buy_cnt + sell_cnt)
        if buy_ratio > 0.8 or buy_ratio < 0.2:
            issues.append(f"買い/売りシグナルの偏りが大きい: 買い{buy_cnt} / 売り{sell_cnt}")
            score = max(1, score - 1)

    return {"axis": "シグナル品質", "score": score, "issues": issues, "evidence": evidence,
            "data": {"total": total, "buy": buy_cnt, "sell": sell_cnt, "signal_rate": signal_rate}}


def evaluate_system_stability() -> dict:
    log.info("評価: システム安定性")
    issues = []
    evidence = []

    error_count = 0
    error_lines = []

    if os.path.exists(LOG_FILE):
        week_ago = datetime.now() - timedelta(days=7)
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if len(line) < 19:
                    continue
                try:
                    ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
                    if ts >= week_ago and ("[ERROR]" in line or "エラー" in line):
                        error_count += 1
                        error_lines.append(line.strip())
                except ValueError:
                    pass
    else:
        issues.append("fx_bot.log が存在しない（ボット未起動の可能性）")

    evidence.append(f"直近7日間のエラー件数: {error_count}件")
    if error_lines:
        evidence.append("直近エラー例: " + error_lines[-1][:100])

    if error_count == 0:
        score = 10
    elif error_count <= 3:
        issues.append(f"軽微なエラーあり: {error_count}件")
        score = 8
    elif error_count <= 10:
        issues.append(f"エラーが頻発: {error_count}件")
        score = 5
    else:
        issues.append(f"重大なエラー多発: {error_count}件（要調査）")
        score = max(1, 10 - error_count // 5)

    return {"axis": "システム安定性", "score": score, "issues": issues, "evidence": evidence,
            "data": {"error_count": error_count}}


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────

def run() -> list[dict]:
    """全軸を並列評価して結果リストを返す（5軸が独立して同時実行）"""
    from concurrent.futures import ThreadPoolExecutor

    log.info("FX Evaluatorエージェント開始（5軸並列評価）")

    all_trades = _load_json(TRADES_FILE)
    signals = _load_json(SIGNALS_FILE)
    week_trades = _get_week_trades(all_trades)

    log.info(f"全取引数: {len(all_trades)} / 直近7日: {len(week_trades)}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        f_profit    = executor.submit(evaluate_profitability, all_trades, week_trades)
        f_risk      = executor.submit(evaluate_risk_management, all_trades, week_trades)
        f_strategy  = executor.submit(evaluate_strategy_effectiveness, all_trades)
        f_signal    = executor.submit(evaluate_signal_quality, signals)
        f_stability = executor.submit(evaluate_system_stability)

    results = [
        f_profit.result(),
        f_risk.result(),
        f_strategy.result(),
        f_signal.result(),
        f_stability.result(),
    ]

    log.info("FX Evaluatorエージェント完了")
    return results
