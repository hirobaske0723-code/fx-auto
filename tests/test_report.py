import pytest
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from report import _calc_trade_stats, _calc_signal_stats, generate, generate_json


def make_trade(pnl, balance):
    return {
        "direction": "long",
        "entry_price": 150.0,
        "exit_price": 150.1,
        "reason": "TP" if pnl > 0 else "SL",
        "pnl": pnl,
        "balance": balance,
        "timestamp": "2026-03-27T10:00:00",
    }


def test_calc_trade_stats_empty():
    result = _calc_trade_stats([])
    assert result["total"] == 0
    assert result["win_rate"] == 0.0
    assert result["total_pnl"] == 0.0
    assert result["max_drawdown"] == 0.0
    assert result["current_balance"] == 100000.0


def test_calc_trade_stats_wins_and_losses():
    trades = [
        make_trade(150.0, 100150.0),
        make_trade(-100.0, 100050.0),
        make_trade(200.0, 100250.0),
    ]
    result = _calc_trade_stats(trades)
    assert result["total"] == 3
    assert result["wins"] == 2
    assert result["losses"] == 1
    assert abs(result["win_rate"] - 66.7) < 0.1
    assert result["total_pnl"] == 250.0
    assert result["current_balance"] == 100250.0


def test_calc_trade_stats_max_drawdown():
    trades = [
        make_trade(150.0, 100150.0),
        make_trade(-500.0, 99650.0),
    ]
    result = _calc_trade_stats(trades)
    assert result["max_drawdown"] == 500.0


def test_calc_trade_stats_max_streak():
    trades = [
        make_trade(100.0, 100100.0),
        make_trade(100.0, 100200.0),
        make_trade(100.0, 100300.0),
        make_trade(-50.0, 100250.0),
        make_trade(-50.0, 100200.0),
    ]
    result = _calc_trade_stats(trades)
    assert result["max_streak_win"] == 3
    assert result["max_streak_loss"] == 2


# ── _calc_signal_stats ──────────────────────────────────────


def make_signal(signal, action="watch", days_ago=0):
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
    return {
        "timestamp": ts,
        "price": 150.0,
        "signal": signal,
        "rsi": 55.0,
        "ma_short": 149.9,
        "ma_long": 149.8,
        "action": action,
    }


def test_calc_signal_stats_empty():
    result = _calc_signal_stats([])
    assert result["total"] == 0
    assert result["buy"] == 0
    assert result["sell"] == 0
    assert result["rate"] == 0.0
    assert result["last_signal"] is None


def test_calc_signal_stats_counts():
    signals = [
        make_signal(1, "entry"),
        make_signal(-1, "skip(position)"),
        make_signal(0, "watch"),
        make_signal(1, "entry"),
    ]
    result = _calc_signal_stats(signals)
    assert result["buy"] == 2
    assert result["sell"] == 1
    assert result["none"] == 1
    assert result["total"] == 4
    assert abs(result["rate"] - 75.0) < 0.1


def test_calc_signal_stats_excludes_old():
    signals = [
        make_signal(1, "entry", days_ago=8),   # 8日前 → 除外
        make_signal(-1, "entry", days_ago=1),  # 1日前 → 含む
    ]
    result = _calc_signal_stats(signals)
    assert result["total"] == 1
    assert result["sell"] == 1


def test_calc_signal_stats_last_signal():
    signals = [
        make_signal(0, "watch"),
        make_signal(1, "entry"),
        make_signal(0, "watch"),
    ]
    result = _calc_signal_stats(signals)
    assert result["last_signal"]["signal"] == 1


# ── generate() ──────────────────────────────────────────────


def test_generate_no_data(tmp_path):
    """trades.json / signals_log.json がない状態でクラッシュしないこと"""
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        output = generate(save=False)
    finally:
        os.chdir(orig)
    assert "FX Bot 成績レポート" in output
    assert "取引数: 0" in output
    assert "記録なし" in output


def test_generate_save(tmp_path):
    """save=True で logs/stats_report.md が生成されること"""
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        generate(save=True)
    finally:
        os.chdir(orig)
    assert (tmp_path / "logs" / "stats_report.md").exists()


# ── generate_json() ─────────────────────────────────────────


def test_generate_json_creates_file(tmp_path):
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        os.makedirs("logs", exist_ok=True)
        generate_json()
    finally:
        os.chdir(orig)
    assert (tmp_path / "logs" / "stats.json").exists()


def test_generate_json_content_empty(tmp_path):
    """データなしでも正常に生成されること"""
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        os.makedirs("logs", exist_ok=True)
        data = generate_json()
    finally:
        os.chdir(orig)
    assert "updated_at" in data
    assert data["balance"] == 100000.0
    assert data["total_trades"] == 0
    assert data["win_rate"] == 0.0
    assert data["signal_7d"]["last_signal_at"] is None
    assert data["signal_7d"]["last_signal_dir"] is None


def test_generate_json_with_trades(tmp_path):
    """取引データがある場合に正しく集計されること"""
    import json as _json
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        os.makedirs("logs", exist_ok=True)
        trades = [
            {"direction": "long", "entry_price": 150.0, "exit_price": 150.15,
             "reason": "TP", "pnl": 150.0, "balance": 100150.0,
             "timestamp": "2026-03-27T10:00:00"},
            {"direction": "short", "entry_price": 150.2, "exit_price": 150.3,
             "reason": "SL", "pnl": -100.0, "balance": 100050.0,
             "timestamp": "2026-03-27T12:00:00"},
        ]
        with open("trades.json", "w") as f:
            _json.dump(trades, f)
        data = generate_json()
    finally:
        os.chdir(orig)
    assert data["total_trades"] == 2
    assert data["wins"] == 1
    assert data["losses"] == 1
    assert data["total_pnl"] == 50.0
    assert data["balance"] == 100050.0
