import pytest
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from report import _calc_trade_stats


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
