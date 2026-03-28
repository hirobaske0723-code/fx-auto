# finance.html FX Bot 成績統合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FXボットの成績（trades.json / signals_log.json）を毎日0時にGitHub上のstats.jsonに自動push し、Vercel上のfinance.htmlで表示する。

**Architecture:** `report.py` が `logs/stats.json` を生成 → `main.py` の `github_push_stats()` がGitHub Contents APIでpush → `finance.html` のJavaScriptがGitHub raw URLからfetchして描画。

**Tech Stack:** Python 3.x, requests, base64, GitHub Contents API, Vanilla JS fetch API

---

## ファイルマップ

| 操作 | パス | 役割 |
|------|------|------|
| 修正 | `config.py` | PAT_TOKEN 追加 |
| 修正 | `report.py` | `generate_json()` 追加、`STATS_JSON_FILE` 定数追加 |
| 修正 | `main.py` | `github_push_stats()` 追加、`daily_reset()` に組み込み |
| 修正 | `tests/test_report.py` | `generate_json()` のテスト追加 |
| 新規 | `tests/test_github_pusher.py` | `github_push_stats()` のテスト |
| 修正 | `.company/personal/finance.html` | FX Bot セクション追加 |

---

## Task 1: config.py に PAT_TOKEN を追加

**Files:**
- Modify: `config.py:7-8`

- [ ] **Step 1: config.py の API Keys セクションに PAT_TOKEN を追加**

変更前:
```python
# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
```

変更後:
```python
# API Keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
PAT_TOKEN = os.getenv("PAT_TOKEN")
```

- [ ] **Step 2: コミット**

```bash
git add config.py
git commit -m "feat: config.py に PAT_TOKEN を追加"
```

---

## Task 2: report.py に generate_json() を追加

**Files:**
- Modify: `report.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: tests/test_report.py にテストを追記**

ファイル末尾に追加：

```python
from report import generate_json


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
```

`tests/test_report.py` の import に `generate_json` を追加：

```python
from report import _calc_trade_stats, _calc_signal_stats, generate, generate_json
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd "C:/Users/hirob/OneDrive/Desktop/Cloud codeテスト用/fx-bot"
python -m pytest tests/test_report.py::test_generate_json_creates_file -v
```

Expected: `ImportError: cannot import name 'generate_json'`

- [ ] **Step 3: report.py に STATS_JSON_FILE 定数と generate_json() を追加**

`STATS_FILE = "logs/stats_report.md"` の直後に追加：

```python
STATS_JSON_FILE = "logs/stats.json"
```

`generate()` 関数の直後に追加：

```python
def generate_json(path=None):
    if path is None:
        path = STATS_JSON_FILE
    trades = _load_json(TRADES_FILE)
    signals = _load_json(SIGNALS_FILE)

    ts = _calc_trade_stats(trades)
    ss = _calc_signal_stats(signals)

    last_signal_at = None
    last_signal_dir = None
    if ss["last_signal"]:
        last_signal_at = ss["last_signal"]["timestamp"][:16].replace("T", " ")
        last_signal_dir = "BUY" if ss["last_signal"]["signal"] == 1 else "SELL"

    data = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "balance": ts["current_balance"],
        "total_pnl": ts["total_pnl"],
        "win_rate": round(ts["win_rate"], 1),
        "total_trades": ts["total"],
        "wins": ts["wins"],
        "losses": ts["losses"],
        "max_drawdown": ts["max_drawdown"],
        "max_streak_win": ts["max_streak_win"],
        "max_streak_loss": ts["max_streak_loss"],
        "signal_7d": {
            "total": ss["total"],
            "buy": ss["buy"],
            "sell": ss["sell"],
            "rate": round(ss["rate"], 1),
            "last_signal_at": last_signal_at,
            "last_signal_dir": last_signal_dir,
        },
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m pytest tests/test_report.py -v
```

Expected: 13 passed（既存10 + 新規3）

- [ ] **Step 5: コミット**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report.py に generate_json() を追加（logs/stats.json 生成）"
```

---

## Task 3: main.py に github_push_stats() を追加

**Files:**
- Create: `tests/test_github_pusher.py`
- Modify: `main.py`

- [ ] **Step 1: tests/test_github_pusher.py を作成**

```python
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_github_push_stats_skips_without_token(monkeypatch):
    """PAT_TOKEN が未設定の場合はスキップしてエラーを出さないこと"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", None)
    import main as m
    importlib.reload(m)
    m.github_push_stats()  # should not raise


def test_github_push_stats_skips_without_file(monkeypatch):
    """stats.json が存在しない場合はスキップしてエラーを出さないこと"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)
    # stats.json を作らない
    with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
        m.github_push_stats()
    mock_put.assert_not_called()


def test_github_push_stats_new_file(tmp_path, monkeypatch):
    """stats.json が新規ファイルの場合（SHA なし）で PUT が呼ばれること"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)

    os.makedirs("logs")
    (tmp_path / "logs" / "stats.json").write_text('{"balance": 100000}', encoding="utf-8")

    mock_get = MagicMock()
    mock_get.return_value.status_code = 404  # ファイル未存在

    mock_put = MagicMock()
    mock_put.return_value.status_code = 201

    with patch("requests.get", mock_get), patch("requests.put", mock_put):
        m.github_push_stats()

    mock_put.assert_called_once()
    payload = mock_put.call_args[1]["json"]
    assert "content" in payload
    assert "sha" not in payload


def test_github_push_stats_existing_file(tmp_path, monkeypatch):
    """stats.json が既存ファイルの場合（SHA あり）で PUT に sha が含まれること"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)

    os.makedirs("logs")
    (tmp_path / "logs" / "stats.json").write_text('{"balance": 100000}', encoding="utf-8")

    mock_get = MagicMock()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"sha": "abc123"}

    mock_put = MagicMock()
    mock_put.return_value.status_code = 200

    with patch("requests.get", mock_get), patch("requests.put", mock_put):
        m.github_push_stats()

    payload = mock_put.call_args[1]["json"]
    assert payload["sha"] == "abc123"
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
python -m pytest tests/test_github_pusher.py -v
```

Expected: `AttributeError: module 'main' has no attribute 'github_push_stats'`

- [ ] **Step 3: main.py に import と定数を追加**

ファイル先頭の import ブロック（`import report` の直後）に追加：

```python
import base64
import requests as _requests
```

`SIGNALS_FILE = "signals_log.json"` の直後に追加：

```python
GITHUB_OWNER = "hirobaske0723-code"
GITHUB_REPO = "fx-auto"
GITHUB_STATS_PATH = "logs/stats.json"
```

- [ ] **Step 4: main.py に github_push_stats() を追加**

`save_signal()` 関数の直後に追加：

```python
def github_push_stats():
    from config import PAT_TOKEN
    if not PAT_TOKEN:
        log.warning("PAT_TOKEN が未設定のため stats.json の GitHub push をスキップ")
        return

    stats_file = report.STATS_JSON_FILE
    if not os.path.exists(stats_file):
        log.warning(f"{stats_file} が存在しないため push をスキップ")
        return

    with open(stats_file, "r", encoding="utf-8") as f:
        content = f.read()

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_STATS_PATH}"
    headers = {
        "Authorization": f"Bearer {PAT_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    sha = None
    r = _requests.get(api_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    payload = {
        "message": f"chore: update stats.json [{datetime.now().strftime('%Y-%m-%d %H:%M')}]",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    r = _requests.put(api_url, headers=headers, json=payload)
    if r.status_code in (200, 201):
        log.info("stats.json を GitHub に push しました")
    else:
        log.error(f"stats.json の push に失敗: {r.status_code} {r.text[:200]}")
```

- [ ] **Step 5: テストが通ることを確認**

```bash
python -m pytest tests/test_github_pusher.py -v
```

Expected: 4 passed

- [ ] **Step 6: 全テスト確認**

```bash
python -m pytest tests/ -v
```

Expected: 18 passed

- [ ] **Step 7: コミット**

```bash
git add main.py tests/test_github_pusher.py
git commit -m "feat: main.py に github_push_stats() を追加（GitHub Contents API経由）"
```

---

## Task 4: daily_reset() に generate_json と github_push_stats を組み込み

**Files:**
- Modify: `main.py:daily_reset()`

- [ ] **Step 1: daily_reset() を修正**

変更前:
```python
def daily_reset():
    log.info("デイリーリセット")
    notify_daily_reset(risk.daily_pnl)
    risk.reset()
    report.generate(save=True)
    log.info("stats_report.md を更新しました")
```

変更後:
```python
def daily_reset():
    log.info("デイリーリセット")
    notify_daily_reset(risk.daily_pnl)
    risk.reset()
    report.generate(save=True)
    report.generate_json()
    log.info("stats_report.md / stats.json を更新しました")
    github_push_stats()
```

- [ ] **Step 2: 全テスト確認**

```bash
python -m pytest tests/ -v
```

Expected: 18 passed

- [ ] **Step 3: コミット**

```bash
git add main.py
git commit -m "feat: daily_reset に generate_json と github_push_stats を追加"
```

---

## Task 5: finance.html に FX Bot セクションを追加

**Files:**
- Modify: `.company/personal/finance.html`

- [ ] **Step 1: finance.html の「為替」セクション終了タグの直後にFX Botセクションを追加**

`</div>` の直後（為替セクション末尾、`</div>` と `</div>` の間）を探す。
具体的には `<!-- FX -->` ブロックの `</div>` 直後（368行目付近）に以下を追加：

```html
  <!-- FX Bot -->
  <div>
    <div class="section-label">FX Bot（ペーパートレード）</div>
    <div class="widget-card">
      <div class="widget-card-header">🤖 USD/JPY 自動売買</div>
      <div id="fx-bot-content" style="padding:16px 18px;">
        <div style="color:rgba(255,255,255,0.35);font-size:0.8rem;">データ取得中...</div>
      </div>
    </div>
  </div>
```

- [ ] **Step 2: finance.html の `</div>` 直前（`<footer>` の直前）に fetch スクリプトを追加**

```html
<script>
(function () {
  const RAW_URL = 'https://raw.githubusercontent.com/hirobaske0723-code/fx-auto/main/logs/stats.json';
  fetch(RAW_URL + '?t=' + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var pnlColor = d.total_pnl >= 0 ? '#4ade80' : '#f87171';
      var lastSig = (d.signal_7d.last_signal_at)
        ? d.signal_7d.last_signal_at + ' ' + d.signal_7d.last_signal_dir
        : '記録なし';
      var updatedAt = d.updated_at ? d.updated_at.slice(0, 16).replace('T', ' ') : '—';
      document.getElementById('fx-bot-content').innerHTML =
        '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;line-height:2.1;">' +
        '<tr><td style="color:rgba(255,255,255,0.4);width:150px;">残高</td><td>' + Number(d.balance).toLocaleString() + '円</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">累計PnL</td>' +
          '<td style="color:' + pnlColor + '">' + (d.total_pnl >= 0 ? '+' : '') + Number(d.total_pnl).toLocaleString() + '円</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">勝率</td>' +
          '<td>' + d.win_rate + '%（' + d.total_trades + '戦 ' + d.wins + '勝 ' + d.losses + '敗）</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">最大DD</td><td>-' + Number(d.max_drawdown).toLocaleString() + '円</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">シグナル発生率</td>' +
          '<td>' + d.signal_7d.rate + '%（直近7日 ' + d.signal_7d.total + 'サイクル）</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">最後のシグナル</td><td>' + lastSig + '</td></tr>' +
        '<tr><td style="color:rgba(255,255,255,0.4);">更新</td>' +
          '<td style="color:rgba(255,255,255,0.3);font-size:0.75rem;">' + updatedAt + '</td></tr>' +
        '</table>';
    })
    .catch(function () {
      document.getElementById('fx-bot-content').innerHTML =
        '<div style="color:rgba(255,255,255,0.25);font-size:0.8rem;">データを取得できませんでした</div>';
    });
}());
</script>
```

- [ ] **Step 3: ブラウザで finance.html を開いて表示確認**

`finance.html` をブラウザで直接開く（file://）か Vercel preview で確認。
- FX Bot セクションが「データ取得中...」→「データを取得できませんでした」と表示されることを確認
  （stats.json がまだ GitHub にないため。初回はこれが正常）

- [ ] **Step 4: コミット**

```bash
git add ".company/personal/finance.html"
git commit -m "feat: finance.html に FX Bot 成績セクションを追加"
```

---

## Task 6: NAS 設定 + push → 動作確認

**Files:** なし（NAS設定 + 手動テスト）

- [ ] **Step 1: NAS Container Manager で PAT_TOKEN 環境変数を追加**

1. DSM → Container Manager → `fx-bot` コンテナ → 設定 → 環境変数
2. `PAT_TOKEN` = `ghp_xxxxxx...`（repo スコープのPAT）を追加
3. コンテナを再起動

- [ ] **Step 2: github_push_stats を手動テスト（コンテナ内で）**

Container Manager のターミナルから：

```bash
python -X utf8 -c "
import report, main
report.generate_json()
main.github_push_stats()
"
```

Expected: `INFO stats.json を GitHub に push しました`

- [ ] **Step 3: GitHub で stats.json を確認**

`https://github.com/hirobaske0723-code/fx-auto/blob/main/logs/stats.json` にアクセスしてファイルが存在することを確認。

- [ ] **Step 4: finance.html で表示確認**

ブラウザで `personalfile-eight.vercel.app/finance.html` を開き、FX Bot セクションにデータが表示されることを確認。
（GitHub raw の CDN キャッシュが最大5分あるので、表示まで少し待つ場合あり）

- [ ] **Step 5: push して NAS に反映**

```bash
git push origin main
```

---

## 後続タスク（このプランのスコープ外）

- `logs/stats.json` の GitHub push が `paths-ignore` に引っかかってデプロイループを起こさないか確認（fx-botにはデプロイworkflowがないため問題ないはず）
