# FX Bot 成績レポート & シグナル可視化 — 設計書

**作成日:** 2026-03-27
**対象リポジトリ:** fx-bot

---

## 概要

FX自動売買ボット（ペーパートレード）の取引成績と、シグナル発生状況をいつでも確認・記録できる仕組みを追加する。

**目的:** 勝率・PnL・シグナル頻度を可視化して、将来のパラメータ調整の根拠にする。

---

## データ構造

### signals_log.json（新規）

毎サイクル（15分ごと）末尾に追記。

```json
{
  "timestamp": "2026-03-27T14:00:00",
  "price": 149.823,
  "signal": 1,
  "rsi": 58.3,
  "ma_short": 149.801,
  "ma_long": 149.756,
  "action": "entry"
}
```

- `signal`: `1`=買い、`-1`=売り、`0`=なし
- `action`: `"entry"` / `"skip(position)"` / `"watch"`

### trades.json（既存・変更なし）

クローズ時に追記。`timestamp` フィールドは既に実装済み。

```json
{
  "direction": "long",
  "entry_price": 149.823,
  "exit_price": 150.088,
  "reason": "TP",
  "pnl": 265.0,
  "balance": 100265.0,
  "timestamp": "2026-03-27T15:30:00"
}
```

---

## レポート出力内容

`report.py` 実行時・デイリー自動生成時に共通の以下を出力する。

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FX Bot 成績レポート — YYYY-MM-DD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【取引成績】
  取引数: N | 勝: W / 負: L
  勝率: XX.X%
  累計PnL: +X,XXX円
  最大連勝: N | 最大連敗: N
  最大ドローダウン: -X,XXX円
  現在残高: XXX,XXX円（初期: 100,000円）

【シグナル統計（直近7日）】
  総サイクル: N回
  シグナル発生: 買い N回 / 売り N回 / なし N回
  シグナル発生率: X.X%
  最後のシグナル: YYYY-MM-DD HH:MM BUY/SELL

【シグナル タイムライン（直近10件）】
  YYYY-MM-DD HH:MM  BUY/SELL/---  @ XXX.XXX  → エントリー/なし/スキップ(ポジションあり)
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## コード変更

### 変更ファイル: main.py

1. `save_signal()` 関数を追加（`save_trade()` と同パターン、`signals_log.json` に追記）
2. `run_cycle()` 末尾で `save_signal()` を呼び出す
3. `daily_reset()` 末尾で `report.generate(save=True)` を呼び出す（`logs/stats_report.md` 自動生成）

### 新規ファイル: report.py

- `trades.json` と `signals_log.json` を読み込んで集計・フォーマット
- `python report.py` でターミナル出力
- `python report.py --save` で `logs/stats_report.md` にも保存
- `generate(save=False)` 関数を公開して `main.py` から呼べるようにする

### 新規ディレクトリ: logs/

- `stats_report.md` の保存先
- `.gitkeep` を配置してGit管理下に置く

---

## 変更しないファイル

- `paper_trader.py` — 変更なし
- `strategy.py` — 変更なし
- `config.py` — 変更なし
- `market_data.py` — 変更なし

---

## 後続タスク（本設計のスコープ外）

- `logs/stats_report.md` の内容を `finance.html` に統合（別途設計）
- `/company` 起動時ルーティンで `stats_report.md` を読んでFXボット状況を表示
