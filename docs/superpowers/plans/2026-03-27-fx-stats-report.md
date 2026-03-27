# FX Bot 成績レポート & シグナル可視化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** シグナル発生を `signals_log.json` に記録し、`report.py` で取引成績・シグナル統計をターミナル出力・Markdownファイル自動保存する。

**Architecture:** `main.py` の各サイクル末尾で `save_signal()` を呼び `signals_log.json` に追記。`report.py` は `trades.json` と `signals_log.json` を読み集計・フォーマットして出力。デイリーリセット時に `report.generate(save=True)` を呼んで `logs/stats_report.md` を自動生成。

**Tech Stack:** Python 3.x, json, datetime, pytest

---

## ファイルマップ

| 操作 | パス | 役割 |
|------|------|------|
| 新規作成 | `report.py` | 集計・フォーマット・出力 |
| 新規作成 | `logs/.gitkeep` | logs/ ディレクトリをGit管理下に |
| 新規作成 | `tests/test_report.py` | report.py の単体テスト |
| 新規作成 | `tests/test_signal_logger.py` | save_signal() の単体テスト |
| 修正 | `main.py` | save_signal() 追加 + run_cycle/daily_reset に呼び出し追加 |

---

## Task 1: logs/ ディレクトリと tests/ のセットアップ

**Files:**
- Create: `logs/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: ディレクトリとファイルを作成**

```bash
mkdir -p logs tests
touch logs/.gitkeep tests/__init__.py
```

- [ ] **Step 2: コミット**

```bash
git add logs/.gitkeep tests/__init__.py
git commit -m "chore: logs/ と tests/ ディレクトリを追加"
```

---

## Task 2: save_signal() を main.py に追加

**Files:**
- Create: `tests/test_signal_logger.py`
- Modify: `main.py`

- [ ] **Step 1: テストを書く**

`tests/test_signal_logger.py` を以下の内容で作成：

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd "C:/Users/hirob/OneDrive/Desktop/Cloud codeテスト用/fx-bot"
python -m pytest tests/test_signal_logger.py -v
```

Expected: `AttributeError: module 'main' has no attribute 'save_signal'`

- [ ] **Step 3: main.py に SIGNALS_FILE 定数と save_signal() を追加**

`main.py` の `TRADES_FILE = "trades.json"` の直後（120行目付近）に以下を追加：

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m pytest tests/test_signal_logger.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add main.py tests/test_signal_logger.py
git commit -m "feat: save_signal() を main.py に追加し signals_log.json に記録"
```

---

## Task 3: report.py — 取引成績の集計

**Files:**
- Create: `tests/test_report.py`
- Create: `report.py`（_calc_trade_stats のみ）

- [ ] **Step 1: テストを書く**

`tests/test_report.py` を以下の内容で作成：

```python
import pytest
import os
import sys

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
    # 100000 → +150 → -500 → peak=100150, drawdown=500
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
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
python -m pytest tests/test_report.py -v
```

Expected: `ModuleNotFoundError: No module named 'report'`

- [ ] **Step 3: report.py を作成（_calc_trade_stats のみ）**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m pytest tests/test_report.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report.py を追加（_calc_trade_stats）"
```

---

## Task 4: report.py — シグナル統計の集計

**Files:**
- Modify: `tests/test_report.py`（テスト追記）
- Modify: `report.py`（_calc_signal_stats 追加）

- [ ] **Step 1: tests/test_report.py にテストを追記**

ファイル末尾に追加：

```python
from report import _calc_signal_stats
from unittest.mock import patch


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
```

`tests/test_report.py` の先頭 import ブロックに `from datetime import datetime, timedelta` を追加。

- [ ] **Step 2: テストが失敗することを確認**

```bash
python -m pytest tests/test_report.py::test_calc_signal_stats_empty -v
```

Expected: `ImportError: cannot import name '_calc_signal_stats'`

- [ ] **Step 3: report.py に _calc_signal_stats を追加**

`_calc_trade_stats` の直後に追加：

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m pytest tests/test_report.py -v
```

Expected: 8 passed

- [ ] **Step 5: コミット**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report.py に _calc_signal_stats を追加"
```

---

## Task 5: report.py — generate() と __main__

**Files:**
- Modify: `tests/test_report.py`（テスト追記）
- Modify: `report.py`（generate() + __main__ 追加）

- [ ] **Step 1: tests/test_report.py にテストを追記**

ファイル末尾に追加：

```python
from report import generate


def test_generate_no_data(capsys):
    """trades.json / signals_log.json がない状態でクラッシュしないこと"""
    import os
    # カレントディレクトリにファイルがない前提で実行
    orig = os.getcwd()
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            output = generate(save=False)
    finally:
        os.chdir(orig)
    assert "FX Bot 成績レポート" in output
    assert "取引数: 0" in output
    assert "記録なし" in output


def test_generate_save(tmp_path):
    """save=True で logs/stats_report.md が生成されること"""
    import os
    orig = os.getcwd()
    try:
        os.chdir(tmp_path)
        generate(save=True)
    finally:
        os.chdir(orig)
    assert (tmp_path / "logs" / "stats_report.md").exists()
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
python -m pytest tests/test_report.py::test_generate_no_data -v
```

Expected: `ImportError: cannot import name 'generate'`

- [ ] **Step 3: report.py に generate() と __main__ を追加**

`_calc_signal_stats` の直後に追加：

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m pytest tests/test_report.py -v
```

Expected: 10 passed

- [ ] **Step 5: 手動動作確認**

```bash
python report.py
```

Expected: ターミナルにレポートが表示される（取引数: 0、記録なし）

- [ ] **Step 6: コミット**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report.py に generate() を追加（手動実行・ファイル保存対応）"
```

---

## Task 6: main.py — run_cycle と daily_reset に組み込み

**Files:**
- Modify: `main.py`

- [ ] **Step 1: run_cycle() にシグナル記録を追加**

`main.py` の `run_cycle()` を修正。エントリーブロック（`# 3. エントリー`）の**前**に `position_before_entry` を記録し、エントリーブロックの**後**に `save_signal()` を呼ぶ。

変更前（99〜116行目）：
```python
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
```

変更後：
```python
        # 3. エントリー（ポジションなし時）
        position_before_entry = trader.position
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

        # 4. シグナル記録
        if signal != 0:
            action = "skip(position)" if position_before_entry is not None else "entry"
        else:
            action = "watch"
        save_signal(current_price, signal, float(rsi), float(ma_s), float(ma_l), action)

    except Exception as e:
```

- [ ] **Step 2: daily_reset() にレポート自動生成を追加**

`main.py` の先頭 import に `import report` を追加し、`daily_reset()` を修正。

import 追加（既存の `import schedule` の直後）：
```python
import report
```

変更前（167〜170行目）：
```python
def daily_reset():
    log.info("デイリーリセット")
    notify_daily_reset(risk.daily_pnl)
    risk.reset()
```

変更後：
```python
def daily_reset():
    log.info("デイリーリセット")
    notify_daily_reset(risk.daily_pnl)
    risk.reset()
    report.generate(save=True)
    log.info("stats_report.md を更新しました")
```

- [ ] **Step 3: 起動確認**

```bash
python main.py
```

Expected: 起動後の最初のサイクルで `signals_log.json` が生成されること（エラーなし）

```bash
# 確認
python -c "import json; print(json.load(open('signals_log.json')))"
```

Expected: `[{'timestamp': '...', 'price': ..., 'signal': 0, ...}]` のような出力

- [ ] **Step 4: report.py の手動実行確認**

```bash
python report.py
```

Expected: シグナルタイムラインに記録が表示される

- [ ] **Step 5: コミット**

```bash
git add main.py
git commit -m "feat: run_cycle にシグナル記録・daily_reset にレポート自動生成を追加"
```

- [ ] **Step 6: NAS に push**

```bash
git push origin main
```

Expected: GitHub Actions (deploy.yml) が起動し NAS に自動反映される

---

## 後続タスク（このプランのスコープ外）

- `logs/stats_report.md` を `finance.html` に統合（FX成績の一元管理）
- `/company` 起動時ルーティンで `stats_report.md` を読んでFXボット状況を表示
