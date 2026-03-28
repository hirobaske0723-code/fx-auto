# finance.html FX Bot 成績統合 — 設計書

**作成日:** 2026-03-27
**対象ファイル:** `.company/personal/finance.html`、`fx-bot/report.py`、`fx-bot/main.py`

---

## 概要

NASで稼働中のFXボット（ペーパートレード）の成績を、Vercel上の `finance.html` に表示する。

**目的:** 市場データと自分のボット成績を1ページで一元管理する。

---

## 全体フロー

```
NAS (fx-bot コンテナ)
  └─ daily_reset() 毎日0時
       ├─ report.generate(save=True)   → logs/stats_report.md（既存）
       ├─ report.generate_json()       → logs/stats.json（新規）
       └─ github_push_stats()          → GitHub API で stats.json を push

GitHub raw URL
  https://raw.githubusercontent.com/hirobaske0723-code/fx-auto/main/logs/stats.json

Vercel (finance.html)
  └─ JS fetch() で stats.json を取得 → FX Bot セクションに表示
```

---

## stats.json フォーマット

毎日0時に生成・push される。

```json
{
  "updated_at": "2026-03-27T00:00:00",
  "balance": 103200,
  "total_pnl": 3200,
  "win_rate": 66.7,
  "total_trades": 15,
  "wins": 10,
  "losses": 5,
  "max_drawdown": 800,
  "max_streak_win": 4,
  "max_streak_loss": 2,
  "signal_7d": {
    "total": 168,
    "buy": 8,
    "sell": 6,
    "rate": 8.3,
    "last_signal_at": "2026-03-27T14:00:00",
    "last_signal_dir": "BUY"
  }
}
```

---

## finance.html 表示内容

既存の「為替」セクションの下に `widget-card` スタイルで追加。

| 項目 | 内容 |
|------|------|
| 残高 | XXX,XXX円 |
| 累計PnL | +X,XXX円（色付き: 黒字=緑、赤字=赤） |
| 勝率 | XX.X%（N戦 N勝 N敗） |
| 最大DD | -X,XXX円 |
| シグナル発生率 | X.X%（直近7日 N サイクル） |
| 最後のシグナル | YYYY-MM-DD HH:MM BUY/SELL |
| 更新 | YYYY-MM-DD HH:MM |

- データ取得中は「データ取得中...」を表示
- fetch失敗時は「データを取得できませんでした」を表示

---

## コード変更

### 変更ファイル: fx-bot/report.py

`generate_json(path="logs/stats.json")` 関数を追加。
`_calc_trade_stats()` と `_calc_signal_stats()` の結果を stats.json 形式に変換して保存。

### 変更ファイル: fx-bot/main.py

1. `github_push_stats()` 関数を追加
   - `logs/stats.json` を読み込み
   - GitHub Contents API (`PUT /repos/{owner}/{repo}/contents/{path}`) で push
   - 認証: `PAT_TOKEN` 環境変数を使用（`config.py` 経由）
2. `daily_reset()` に `report.generate_json()` と `github_push_stats()` の呼び出しを追加

### 変更ファイル: fx-bot/config.py

`PAT_TOKEN = os.getenv("PAT_TOKEN")` を追加。

### 変更ファイル: .company/personal/finance.html

「為替」セクションの下に FX Bot セクションを追加。
JavaScriptで GitHub raw URL から stats.json を fetch して表示。

---

## 環境変数追加

NAS Container Manager で fx-bot コンテナに以下を追加：
- `PAT_TOKEN` : GitHub Personal Access Token（repo スコープ）

---

## 変更しないファイル

- `paper_trader.py`
- `strategy.py`
- `market_data.py`
- `risk_manager.py`
- `notifier.py`
