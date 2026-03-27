import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_signals(tmp_path, monkeypatch):
    """signals_log.json を tmp_path に向ける"""
    monkeypatch.chdir(tmp_path)


def _call_save_signal(price, signal, rsi, ma_short, ma_long, action):
    """main.py の save_signal() を直接インポートして呼ぶ"""
    import importlib
    import main as m
    importlib.reload(m)
    m.save_signal(price, signal, rsi, ma_short, ma_long, action)


def test_save_signal_creates_file():
    _call_save_signal(149.823, 1, 58.3, 149.801, 149.756, "entry")
    assert os.path.exists("signals_log.json")


def test_save_signal_content():
    _call_save_signal(149.823, 1, 58.3, 149.801, 149.756, "entry")
    with open("signals_log.json") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["signal"] == 1
    assert data[0]["price"] == 149.823
    assert data[0]["action"] == "entry"
    assert "timestamp" in data[0]


def test_save_signal_appends():
    _call_save_signal(149.823, 1, 58.3, 149.801, 149.756, "entry")
    _call_save_signal(150.001, -1, 42.1, 150.010, 149.900, "skip(position)")
    with open("signals_log.json") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[1]["signal"] == -1


def test_save_signal_watch():
    _call_save_signal(149.500, 0, 50.0, 149.490, 149.480, "watch")
    with open("signals_log.json") as f:
        data = json.load(f)
    assert data[0]["action"] == "watch"
