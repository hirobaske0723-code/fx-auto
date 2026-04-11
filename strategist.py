"""
FX Bot まとめ&方針策定エージェント
Evaluatorの結果を統合し、本番移行判定・優先課題・推奨アクションを出力する
"""
import json
import os
from datetime import datetime, timedelta

import requests

import logging
log = logging.getLogger(__name__)

TRADES_FILE = "trades.json"
REPORTS_DIR = "reports"

# 本番移行基準
GRADUATION_CRITERIA = {
    "min_trades": 50,          # サンプル数
    "min_profit_factor": 1.3,  # プロフィットファクター
    "max_drawdown_pct": 15.0,  # 最大ドローダウン（%）
    "min_consecutive_weeks": 4, # 連続プラス週
}

try:
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, INITIAL_BALANCE
except ImportError:
    LLM_API_KEY = ""
    LLM_BASE_URL = ""
    LLM_MODEL = ""
    INITIAL_BALANCE = 100_000


def _call_llm(prompt: str) -> str:
    if not LLM_API_KEY or not LLM_BASE_URL:
        return '{"comparison": "LLM未設定", "priority_issues": [], "recommended_actions": []}'
    response = requests.post(
        LLM_BASE_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_graduation(eval_results: list[dict]) -> dict:
    """本番移行4条件チェック"""
    trades = _load_json(TRADES_FILE)
    total_trades = len(trades)

    # プロフィットファクター
    gains = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = gains / losses if losses > 0 else (float("inf") if gains > 0 else 0.0)

    # 最大ドローダウン
    dd_result = next((r for r in eval_results if r["axis"] == "リスク管理"), {})
    max_dd_pct = dd_result.get("data", {}).get("max_dd_pct", 999)

    # 連続プラス週を計算
    consecutive_plus_weeks = _count_consecutive_plus_weeks(trades)

    criteria = GRADUATION_CRITERIA
    checks = {
        "サンプル数": {
            "ok": total_trades >= criteria["min_trades"],
            "value": f"{total_trades}件",
            "target": f"{criteria['min_trades']}件以上",
        },
        "プロフィットファクター": {
            "ok": pf >= criteria["min_profit_factor"],
            "value": f"{pf:.2f}" if pf != float("inf") else "∞",
            "target": f"{criteria['min_profit_factor']}以上",
        },
        "最大ドローダウン": {
            "ok": max_dd_pct < criteria["max_drawdown_pct"],
            "value": f"{max_dd_pct:.1f}%",
            "target": f"{criteria['max_drawdown_pct']}%未満",
        },
        "連続プラス週": {
            "ok": consecutive_plus_weeks >= criteria["min_consecutive_weeks"],
            "value": f"{consecutive_plus_weeks}週",
            "target": f"{criteria['min_consecutive_weeks']}週以上",
        },
    }
    all_ok = all(c["ok"] for c in checks.values())
    return {"all_ok": all_ok, "checks": checks}


def _count_consecutive_plus_weeks(trades: list) -> int:
    """直近から遡って連続してプラスだった週数を返す"""
    if not trades:
        return 0

    # 週ごとのPnLを集計
    weekly: dict[str, float] = {}
    for t in trades:
        ts = datetime.fromisoformat(t.get("timestamp", "2000-01-01"))
        # ISO週番号でグループ化
        week_key = ts.strftime("%Y-W%W")
        weekly[week_key] = weekly.get(week_key, 0) + t["pnl"]

    # 直近から連続プラスをカウント
    sorted_weeks = sorted(weekly.keys(), reverse=True)
    consecutive = 0
    for week in sorted_weeks:
        if weekly[week] > 0:
            consecutive += 1
        else:
            break
    return consecutive


def _load_previous_report() -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    reports = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith("-weekly-eval.md")],
        reverse=True,
    )
    if not reports:
        return "（過去レポートなし）"
    try:
        with open(os.path.join(REPORTS_DIR, reports[0]), "r", encoding="utf-8") as f:
            return f.read()[:2000]
    except Exception:
        return "（過去レポート読み込み失敗）"


def run(eval_results: list[dict]) -> str:
    log.info("FX Strategistエージェント開始")

    today = datetime.now().strftime("%Y-%m-%d")
    previous_report = _load_previous_report()
    graduation = _check_graduation(eval_results)

    # スコアサマリー
    score_summary = "\n".join([f"- {r['axis']}: {r.get('score', 0)}/10" for r in eval_results])
    all_issues = []
    for r in eval_results:
        for issue in r.get("issues", []):
            all_issues.append(f"[{r['axis']}] {issue}")
    issues_text = "\n".join([f"- {i}" for i in all_issues]) or "（問題なし）"

    prompt = f"""あなたはFXシステムトレード方針策定の専門家です。
以下の評価結果を統合して、優先課題と推奨アクションを作成してください。

【今週のスコア】
{score_summary}

【検出された問題点】
{issues_text}

【前回レポート（参考）】
{previous_report}

【出力指示】
1. 前回比較（前回レポートがない場合は「初回評価」と記載）
2. 優先課題リスト（影響度・修正コスト付き、最大5件）
3. 今週の推奨アクション（最大3つ、具体的に）

出力形式（JSONのみ）:
{{
  "comparison": "前回比較の分析文（2〜3文）",
  "priority_issues": [
    {{"rank": 1, "axis": "軸名", "issue": "課題", "impact": "高/中/低", "cost": "大/中/小"}},
    ...
  ],
  "recommended_actions": ["アクション1", "アクション2", "アクション3"]
}}
"""
    strategy_json = {}
    try:
        text = _call_llm(prompt)
        if "{" in text and "}" in text:
            strategy_json = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except Exception as e:
        log.error(f"方針策定エラー: {e}")
        strategy_json = {"comparison": "エラー", "priority_issues": [], "recommended_actions": []}

    report_md = _build_report(today, eval_results, graduation, strategy_json)
    _save_report(today, report_md)
    _notify_slack(today, eval_results, graduation)

    log.info("FX Strategistエージェント完了")
    return report_md


def _build_report(today: str, eval_results: list, graduation: dict, strategy: dict) -> str:
    # スコアテーブル
    score_rows = "\n".join([
        f"| {r['axis']} | {r.get('score', 0)}/10 | {', '.join(r.get('issues', [])[:1]) or 'なし'} |"
        for r in eval_results
    ])
    total_score = sum(r.get("score", 0) for r in eval_results)
    max_score = len(eval_results) * 10

    # 本番移行チェック
    grad_rows = "\n".join([
        f"| {name} | {'✅' if c['ok'] else '❌'} | {c['value']} | {c['target']} |"
        for name, c in graduation["checks"].items()
    ])
    grad_summary = "**✅ 全条件クリア → 本番移行検討可**" if graduation["all_ok"] else \
        f"**❌ 未達条件あり（{sum(1 for c in graduation['checks'].values() if not c['ok'])}項目）**"

    # 優先課題
    issues_md = "\n".join([
        f"{p.get('rank', i+1)}. **[{p.get('impact','?')}影響/{p.get('cost','?')}コスト]** [{p.get('axis','')}] {p.get('issue','')}"
        for i, p in enumerate(strategy.get("priority_issues", []))
    ]) or "（課題なし）"

    # 推奨アクション
    actions_md = "\n".join([f"- [ ] {a}" for a in strategy.get("recommended_actions", [])]) or "（なし）"

    return f"""# FX Bot 週次評価レポート {today}

## スコアサマリー

| 軸 | スコア | 主な問題点 |
|---|---|---|
{score_rows}

**合計: {total_score}/{max_score}点**

## 本番移行判定

| 条件 | 判定 | 現在値 | 目標 |
|---|---|---|---|
{grad_rows}

{grad_summary}

## 前回比較

{strategy.get('comparison', '（比較なし）')}

## 優先課題リスト

{issues_md}

## 今週の推奨アクション

{actions_md}

---
_生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}_
"""


def _save_report(today: str, report_md: str):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"{today}-weekly-eval.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_md)
    log.info(f"レポート保存: {path}")


def _notify_slack(today: str, eval_results: list, graduation: dict):
    try:
        from config import SLACK_WEBHOOK_URL
        if not SLACK_WEBHOOK_URL:
            return

        total = sum(r.get("score", 0) for r in eval_results)
        max_score = len(eval_results) * 10
        score_lines = "\n".join([f"  {r['axis']}: {r.get('score',0)}/10" for r in eval_results])
        grad_status = "✅ 本番移行条件クリア" if graduation["all_ok"] else \
            f"❌ 本番移行 未達({sum(1 for c in graduation['checks'].values() if not c['ok'])}項目)"

        text = (
            f"📊 *FX Bot 週次評価 {today}*\n"
            f"合計: `{total}/{max_score}点`\n"
            f"{score_lines}\n"
            f"{grad_status}"
        )
        requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
    except Exception as e:
        log.warning(f"Slack通知失敗: {e}")
