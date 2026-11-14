#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
import json
import os
import re

from tutor_data import TUTOR_ITEMS, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
AUDIO_MANIFEST_PATH = os.path.join(BASE_DIR, "audio", "audio_manifest.json")

plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
with open(plans[-1], encoding="utf-8") as f:
    plan = json.load(f)

with open(STATE_PATH, encoding="utf-8") as f:
    live_state = json.load(f)

audio_manifest = {}
if os.path.exists(AUDIO_MANIFEST_PATH):
    with open(AUDIO_MANIFEST_PATH, encoding="utf-8") as f:
        audio_manifest = json.load(f)

word_audio_map = audio_manifest.get("words", {})
rich_words = {}
for surf, info in WORD_DICT.items():
    entry = dict(info)
    entry["audio"] = word_audio_map.get(surf, "")
    rich_words[surf] = entry


def strip_opt_prefix(s: str) -> str:
    return re.sub(r"^[a-dA-D]\.\s*", "", str(s)).strip()


def build_card(q: dict, subject: str, point_label: str) -> dict:
    qid = q["id"]
    t_item = TUTOR_ITEMS.get(qid, {})
    meta = audio_manifest.get(f"meta:{qid}", {})

    fallback_opts = [strip_opt_prefix(o) for o in q.get("options", []) if o != "不知道"]
    fallback_ans = strip_opt_prefix(q.get("answer", ""))

    choices = t_item.get("choices") or fallback_opts
    answer = t_item.get("answer") or fallback_ans
    prompt_display = t_item.get("prompt_display") or re.sub(r"\s*\[[A-Z0-9-]+\]", "", str(q.get("stem", ""))).strip()
    full_ja = t_item.get("full_ja") or prompt_display
    explain = meta.get("spoken_text") or t_item.get("voice_exp") or q.get("hook_zh") or ""

    return {
        "id": qid,
        "subject": subject,
        "point": point_label,
        "prompt": prompt_display,
        "choices": choices,
        "answer": answer,
        "full_ja": full_ja,
        "explain": explain,
        "q_audio": meta.get("q_audio", ""),
        "exp_audio": meta.get("exp_audio", ""),
        "is_listening": subject == "聴解",
    }


g_list = [
    build_card(q, "文法", q.get("point", ""))
    for q in plan.get("grammar", {}).get("formal", []) + plan.get("grammar", {}).get("quick", [])
]
h_list = [
    build_card(q, "活用", re.sub(r"^[A-Z]-\d+(?:/[A-Z]-\d+)?\s*", "", q.get("point", "")))
    for q in plan.get("henkei", {}).get("formal", []) + plan.get("henkei", {}).get("quick", [])
]
v_list = [
    build_card(q, "語彙", q.get("word", ""))
    for q in plan.get("vocab", {}).get("formal", []) + plan.get("vocab", {}).get("quick", [])
]
l_list = [
    build_card(q, "聴解", "口语听辨")
    for q in plan.get("listening", {}).get("formal", [])
]

cards = []
buckets = [g_list, l_list, v_list, h_list]
max_len = max(len(b) for b in buckets)
for i in range(max_len):
    for b in buckets:
        if i < len(b):
            cards.append(b[i])


# Build clean, compact Mastery Dashboard data from n3_live_state.json
def norm_tier(status: str) -> str:
    # "todo" = 待攻克 (red/orange), "wip" = 巩固中 (yellow/gray), "done" = 已过关 (green)
    if status in ("red", "orange"):
        return "todo"
    if status == "green":
        return "done"
    return "wip"


grammar_items = []
for p in live_state.get("grammar_points", []):
    grammar_items.append({
        "name": p.get("name", ""),
        "sub": re.sub(r"\([^)]*\)|（[^）]*）", "", p.get("meaning", "")).strip() or p.get("meaning", ""),
        "tier": norm_tier(p.get("status", "yellow")),
        "note": p.get("note", ""),
    })

henkei_items = []
for p in live_state.get("henkei_points", []):
    if p.get("tier") == "basic_n5n4" and p.get("status") == "gray":
        continue
    henkei_items.append({
        "name": p.get("name", ""),
        "sub": p.get("example", ""),
        "tier": norm_tier(p.get("status", "gray")),
        "note": p.get("note", ""),
    })

vocab_items = []
for p in live_state.get("vocab_tracked", []):
    vocab_items.append({
        "name": p.get("word", ""),
        "sub": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": norm_tier(p.get("status", "yellow")),
        "note": f"练过 {p.get('seen', 0)} 次 · 错 {p.get('wrong', 0)} 次",
    })

listening_items = []
for p in live_state.get("listening_points", []):
    if not p.get("is_core165") and p.get("status") == "gray":
        continue
    listening_items.append({
        "name": p.get("name", ""),
        "sub": p.get("meaning", "") or p.get("full", ""),
        "tier": norm_tier(p.get("status", "gray")),
        "note": p.get("trap", ""),
    })


def count_tiers(items):
    c = {"todo": 0, "wip": 0, "done": 0}
    for it in items:
        c[it["tier"]] += 1
    c["total"] = len(items)
    return c


mastery_data = {
    "grammar": {"label": "语法", "counts": count_tiers(grammar_items), "items": grammar_items},
    "henkei": {"label": "活用", "counts": count_tiers(henkei_items), "items": henkei_items},
    "vocab": {"label": "重点词", "counts": count_tiers(vocab_items), "items": vocab_items},
    "listening": {"label": "听力口语", "counts": count_tiers(listening_items), "items": listening_items},
}

payload = json.dumps({
    "days_to_exam": plan.get("days_to_exam", 22),
    "done_audio": "./audio/done.mp3",
    "cards": cards,
    "words": rich_words,
    "mastery": mastery_data,
}, ensure_ascii=False)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no" />
<meta name="theme-color" content="#F7F6F2" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<link rel="manifest" href="./manifest.json" />
<link rel="icon" href="./icon-192.png" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Noto+Sans+JP:wght@400;500;600&display=swap" rel="stylesheet" />
<title>N3</title>
<style>
  :root {
    --bg: #F7F6F2;
    --card: #FFFFFF;
    --subtle: #F2F0EA;
    --line: rgba(28, 25, 23, 0.08);
    --line-strong: rgba(28, 25, 23, 0.20);
    --ink: #1C1917;
    --ink-2: #57534E;
    --ink-3: #969087;
    --green: #2B7A5E;
    --green-bg: #EEF8F3;
    --green-border: rgba(43, 122, 94, 0.34);
    --amber: #B7791F;
    --amber-bg: #FCF6EB;
    --red: #C4423A;
    --red-bg: #FDF3F2;
    --red-border: rgba(196, 66, 58, 0.34);
    --sans: "Inter", -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans", "Noto Sans JP", sans-serif;
    --jp: "Noto Sans JP", "Hiragino Sans", "PingFang SC", sans-serif;
  }

  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

  body {
    margin: 0;
    min-height: 100dvh;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(18px + env(safe-area-inset-top)) 16px calc(28px + env(safe-area-inset-bottom));
    -webkit-font-smoothing: antialiased;
  }

  .app-shell {
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    min-height: calc(100dvh - 48px);
  }

  /* Clean Top Header: Countdown on left + 2-mode segmented pill on right */
  .app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 18px;
    padding: 0 2px;
  }
  .countdown {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .mode-switch {
    display: inline-flex;
    background: var(--subtle);
    padding: 3px;
    border-radius: 999px;
    border: 1px solid var(--line);
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 12.5px;
    font-weight: 500;
    padding: 5px 13px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .mode-btn.active {
    background: var(--card);
    color: var(--ink);
    box-shadow: 0 2px 8px rgba(28, 25, 23, 0.08);
  }

  /* ================= VIEW 1: VOICE TUTOR (Primary) ================= */
  .tutor-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .session-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    padding: 0 4px;
    font-size: 12.5px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .session-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .pill-ctrl {
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.14s ease;
  }
  .pill-ctrl.active {
    background: var(--ink);
    color: #FFFFFF;
    border-color: var(--ink);
  }

  .progress-rail {
    height: 3px;
    background: rgba(28, 25, 23, 0.06);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 20px;
  }
  .progress-fill {
    height: 100%;
    background: var(--green);
    border-radius: 999px;
    transition: width 0.35s ease;
  }

  .voice-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 28px;
    padding: 32px 24px 26px;
    box-shadow: 0 14px 40px -18px rgba(28, 25, 23, 0.08);
  }

  /* Tactile Breathing Voice Orb */
  .orb-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 22px;
  }
  .voice-orb {
    position: relative;
    width: 78px;
    height: 78px;
    border-radius: 50%;
    border: none;
    background: var(--ink);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 10px 26px -6px rgba(28, 25, 23, 0.28);
    transition: transform 0.16s ease, background 0.2s ease;
  }
  .voice-orb:active { transform: scale(0.95); }
  .voice-orb.speaking {
    background: var(--green);
    box-shadow: 0 0 0 8px rgba(43, 122, 94, 0.13), 0 10px 26px -6px rgba(43, 122, 94, 0.35);
    animation: orbPulse 1.6s ease-in-out infinite;
  }
  .voice-orb.thinking {
    background: var(--amber);
    box-shadow: 0 0 0 8px rgba(183, 121, 31, 0.15);
  }
  @keyframes orbPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
  }
  .orb-bars {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 22px;
  }
  .orb-bars span {
    display: block;
    width: 3.5px;
    height: 10px;
    background: #FFFFFF;
    border-radius: 99px;
    transition: height 0.15s ease;
  }
  .voice-orb.speaking .orb-bars span:nth-child(1) { animation: wave 0.7s ease-in-out infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(2) { animation: wave 0.7s ease-in-out 0.15s infinite; height: 18px; }
  .voice-orb.speaking .orb-bars span:nth-child(3) { animation: wave 0.7s ease-in-out 0.3s infinite; height: 14px; }
  .voice-orb.speaking .orb-bars span:nth-child(4) { animation: wave 0.7s ease-in-out 0.1s infinite; }
  @keyframes wave {
    0%, 100% { height: 7px; }
    50% { height: 21px; }
  }
  .orb-caption {
    margin-top: 10px;
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .prompt-cue {
    font-family: var(--jp);
    font-size: 18px;
    font-weight: 500;
    line-height: 1.6;
    text-align: center;
    color: var(--ink);
    margin: 0 0 22px;
    padding: 0 4px;
  }

  /* Focused Thumb Choices */
  .choices-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  .choices-grid.stacked {
    grid-template-columns: 1fr;
  }
  .choice-btn {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 16px 14px;
    font-family: var(--jp);
    font-size: 16px;
    font-weight: 500;
    color: var(--ink);
    text-align: center;
    cursor: pointer;
    transition: all 0.14s ease;
    line-height: 1.45;
  }
  .choices-grid.stacked .choice-btn {
    text-align: left;
    padding: 14px 16px;
  }
  .choice-btn:hover:not(:disabled) {
    border-color: var(--line-strong);
    background: #FFFFFF;
  }
  .choice-btn.correct {
    background: var(--green-bg);
    border-color: var(--green-border);
    color: var(--green);
    font-weight: 600;
  }
  .choice-btn.wrong {
    background: var(--red-bg);
    border-color: var(--red-border);
    color: var(--red);
  }

  .quick-assist-row {
    display: flex;
    gap: 10px;
    margin-top: 12px;
  }
  .assist-btn {
    flex: 1;
    background: transparent;
    border: 1px dashed var(--line-strong);
    border-radius: 14px;
    padding: 11px 12px;
    font-family: var(--sans);
    font-size: 13px;
    color: var(--ink-2);
    cursor: pointer;
    transition: all 0.14s ease;
  }
  .assist-btn.listening-mic {
    background: var(--green-bg);
    border-style: solid;
    border-color: var(--green-border);
    color: var(--green);
    font-weight: 500;
  }

  /* ================= ANSWER ZONE (With Word Hover/Tap Dictionary!) ================= */
  .answer-zone {
    margin-top: 22px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
    animation: fadeUp 0.2s ease;
  }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .exp-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .replay-exp-btn {
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 13px;
    border-radius: 999px;
    cursor: pointer;
  }
  .replay-exp-btn.playing {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
  }
  .speed-group {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    background: var(--subtle);
    padding: 2px;
    border-radius: 999px;
  }
  .spd-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 11.5px;
    padding: 4px 8px;
    border-radius: 999px;
    cursor: pointer;
    font-variant-numeric: tabular-nums;
  }
  .spd-btn.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }

  .full-sentence-box {
    background: var(--bg);
    border-radius: 16px;
    padding: 14px 16px;
    margin-bottom: 14px;
  }
  .full-sentence-hint {
    font-size: 11px;
    color: var(--ink-3);
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
  }
  .full-sentence-ja {
    font-family: var(--jp);
    font-size: 16.5px;
    line-height: 1.85;
    color: var(--ink);
    white-space: pre-line;
  }

  /* Interactive Dictionary Token (ONLY rendered inside .answer-zone!) */
  .w-tok {
    border-bottom: 1.5px dashed rgba(28, 25, 23, 0.30);
    padding-bottom: 1px;
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .w-tok:hover, .w-tok.active-tok {
    background: rgba(43, 122, 94, 0.13);
    color: var(--green);
    border-bottom-color: var(--green);
  }

  .explain-text {
    font-size: 14.5px;
    line-height: 1.7;
    color: var(--ink-2);
    margin: 0 0 18px;
  }

  .nav-row {
    display: flex;
    gap: 10px;
  }
  .again-btn {
    background: var(--bg);
    color: var(--ink-2);
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 14px 16px;
    font-family: var(--sans);
    font-size: 13.5px;
    cursor: pointer;
  }
  .next-btn {
    flex: 1;
    background: var(--ink);
    color: #FFFFFF;
    border: none;
    border-radius: 15px;
    padding: 14px 20px;
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
  }

  /* Floating Word Dictionary Popover */
  .word-popover {
    position: fixed;
    z-index: 999;
    width: min(320px, calc(100vw - 28px));
    background: #1C1917;
    color: #F7F6F2;
    border-radius: 18px;
    padding: 14px 16px;
    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.26);
    display: none;
    animation: popIn 0.14s ease;
  }
  .word-popover.open { display: block; }
  @keyframes popIn {
    from { opacity: 0; transform: translateY(4px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  .wp-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .wp-head {
    font-family: var(--jp);
    font-size: 17px;
    font-weight: 600;
    color: #FFFFFF;
  }
  .wp-kana {
    font-family: var(--jp);
    font-size: 13px;
    color: #D6D3CD;
    margin-left: 6px;
  }
  .wp-pitch {
    font-size: 11.5px;
    color: #8CE0C2;
    margin-left: 4px;
  }
  .wp-speak {
    border: 1px solid rgba(255,255,255,0.18);
    background: rgba(255,255,255,0.10);
    color: #FFFFFF;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .wp-pos {
    display: inline-block;
    font-size: 11px;
    color: #C7C2B8;
    background: rgba(255,255,255,0.09);
    padding: 2px 8px;
    border-radius: 6px;
    margin-bottom: 7px;
  }
  .wp-zh {
    font-size: 14px;
    font-weight: 500;
    color: #FFFFFF;
    margin-bottom: 4px;
    line-height: 1.45;
  }
  .wp-tip {
    font-size: 12px;
    color: #B8B2A7;
    line-height: 1.45;
  }

  /* ================= VIEW 2: MASTERY DASHBOARD (Secondary) ================= */
  .dash-wrap {
    display: none;
    flex-direction: column;
    gap: 14px;
    padding-bottom: 24px;
  }
  .dash-wrap.active { display: flex; }
  .tutor-wrap.hidden { display: none; }

  .summary-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 20px;
  }
  .sum-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 0;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
  }
  .sum-row:first-child { padding-top: 0; }
  .sum-row:last-child { padding-bottom: 0; border-bottom: none; }
  .sum-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .sum-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--ink);
  }
  .sum-nums {
    font-size: 12px;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .tri-bar {
    height: 6px;
    background: var(--subtle);
    border-radius: 999px;
    overflow: hidden;
    display: flex;
  }
  .tri-seg-done { background: var(--green); height: 100%; }
  .tri-seg-wip { background: #D9A441; height: 100%; }
  .tri-seg-todo { background: var(--red); height: 100%; }

  .detail-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px;
  }
  .mod-tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    overflow-x: auto;
  }
  .mod-tab {
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 999px;
    cursor: pointer;
    white-space: nowrap;
  }
  .mod-tab.active {
    background: var(--ink);
    color: #FFFFFF;
    border-color: var(--ink);
  }

  .tier-tabs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    background: var(--subtle);
    padding: 3px;
    border-radius: 12px;
    margin-bottom: 12px;
  }
  .tier-tab {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    padding: 7px 6px;
    border-radius: 9px;
    cursor: pointer;
    font-variant-numeric: tabular-nums;
  }
  .tier-tab.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }

  .search-input {
    width: 100%;
    border: 1px solid var(--line);
    background: var(--bg);
    border-radius: 11px;
    padding: 9px 12px;
    font-family: var(--sans);
    font-size: 13px;
    color: var(--ink);
    margin-bottom: 10px;
    outline: none;
  }
  .search-input:focus { border-color: var(--line-strong); background: #FFFFFF; }

  .point-list {
    display: flex;
    flex-direction: column;
    max-height: 430px;
    overflow-y: auto;
  }
  .pt-item {
    padding: 11px 4px;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
  }
  .pt-item:last-child { border-bottom: none; }
  .pt-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }
  .pt-left {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot.todo { background: var(--red); }
  .dot.wip { background: #D9A441; }
  .dot.done { background: var(--green); }
  .pt-name {
    font-family: var(--jp);
    font-size: 14.5px;
    font-weight: 500;
    color: var(--ink);
  }
  .pt-sub {
    font-size: 12.5px;
    color: var(--ink-2);
    text-align: right;
    max-width: 52%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pt-note {
    margin-top: 6px;
    padding-left: 15px;
    font-size: 12px;
    color: var(--ink-3);
    line-height: 1.5;
  }

  .done-wrap {
    text-align: center;
    padding: 18px 4px;
  }
  .done-title { font-size: 22px; font-weight: 600; margin: 0 0 8px; }
  .done-sub { font-size: 14px; color: var(--ink-2); margin: 0 0 22px; }
</style>
</head>
<body>
<form name="n3-answers" data-netlify="true" hidden>
  <input type="text" name="id" />
  <input type="text" name="point" />
  <input type="text" name="choice" />
  <input type="text" name="correct" />
  <input type="text" name="ask_again" />
  <input type="text" name="ts" />
</form>

<div class="app-shell">
  <header class="app-header">
    <span class="countdown" id="countdown-txt">距考试 22 天</span>
    <div class="mode-switch">
      <button class="mode-btn active" id="tab-tutor" onclick="switchMode('tutor')">语音私教</button>
      <button class="mode-btn" id="tab-dash" onclick="switchMode('dash')">掌握度</button>
    </div>
  </header>

  <!-- VIEW 1: PRIMARY CONVERSATIONAL VOICE TUTOR -->
  <main class="tutor-wrap" id="tutor-view">
    <div class="session-bar">
      <span id="card-counter">1 / 25</span>
      <div class="session-controls">
        <button class="pill-ctrl" id="handsfree-btn" onclick="toggleHandsFree()">🎧 连播 关</button>
        <button class="pill-ctrl" id="top-speed-btn" onclick="cycleExpSpeed()">讲解 1.3x</button>
      </div>
    </div>
    <div class="progress-rail">
      <div class="progress-fill" id="prog-fill" style="width: 0%"></div>
    </div>

    <div class="voice-card" id="voice-card"></div>
  </main>

  <!-- VIEW 2: SECONDARY MASTERY DASHBOARD -->
  <section class="dash-wrap" id="dash-view">
    <div class="summary-card" id="dash-summary"></div>
    <div class="detail-card">
      <div class="mod-tabs" id="mod-tabs"></div>
      <div class="tier-tabs" id="tier-tabs"></div>
      <input type="search" class="search-input" id="pt-search" placeholder="搜索语法或词义…" oninput="renderMasteryList()" />
      <div class="point-list" id="point-list"></div>
    </div>
  </section>
</div>

<!-- Floating Word Popover (ONLY triggered inside Answer Zone!) -->
<div class="word-popover" id="word-popover"></div>

<script>
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").then(r => r.update()).catch(() => {});
}

const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.2, 1.3, 1.5, 1.8];
let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.3");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.3;

let queue = DATA.cards.slice();
let idx = 0;
let answered = false;
let pickedVal = null;
let handsFree = false;
let handsFreeTimer = null;
let thinkingCountdown = 0;
let activeKind = null; // "q" | "exp" | "done" | null
let activeMode = "tutor";

// Dashboard state
let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

// Persistent studio audio players
const player = new Audio();
player.preload = "auto";
const wordPlayer = new Audio();
wordPlayer.preload = "auto";

// Pre-sort dictionary surfaces longest-first for clean Answer-Zone tokenization
const DICT_KEYS = Object.keys(DATA.words).sort((a, b) => b.length - a.length);

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function annotateJapanese(text) {
  // Tokenize Japanese text against DICT_KEYS (ONLY called inside .answer-zone!)
  const src = String(text || "");
  let out = "";
  let i = 0;
  while (i < src.length) {
    let matched = null;
    for (let k = 0; k < DICT_KEYS.length; k++) {
      const w = DICT_KEYS[k];
      if (src.startsWith(w, i)) {
        matched = w;
        break;
      }
    }
    if (matched) {
      const esc = escapeHtml(matched);
      out += `<span class="w-tok" data-w="${esc}">${esc}</span>`;
      i += matched.length;
    } else {
      out += escapeHtml(src[i]);
      i += 1;
    }
  }
  return out;
}

const preloadSet = new Set();
function warmAudio(url) {
  if (!url || preloadSet.has(url)) return;
  preloadSet.add(url);
  const a = new Audio();
  a.preload = "auto";
  a.src = url;
}

function applyPlaybackRate(kind) {
  const rate = (kind === "exp" || kind === "done") ? expSpeed : 1.05;
  player.defaultPlaybackRate = rate;
  player.playbackRate = rate;
  if ("preservesPitch" in player) player.preservesPitch = true;
  if ("webkitPreservesPitch" in player) player.webkitPreservesPitch = true;
}

function setExpSpeed(s) {
  expSpeed = s;
  try { localStorage.setItem("n3_exp_speed", String(s)); } catch (e) {}
  document.getElementById("top-speed-btn").textContent = `讲解 ${s.toFixed(1)}x`;
  if (activeKind === "exp") {
    applyPlaybackRate("exp");
  }
  document.querySelectorAll(".spd-btn").forEach(b => {
    b.classList.toggle("active", parseFloat(b.dataset.spd) === s);
  });
}

function cycleExpSpeed() {
  const next = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  setExpSpeed(next);
}

function clearHandsFreeTimer() {
  if (handsFreeTimer) {
    clearInterval(handsFreeTimer);
    clearTimeout(handsFreeTimer);
    handsFreeTimer = null;
  }
  thinkingCountdown = 0;
}

function stopAudio() {
  clearHandsFreeTimer();
  try {
    player.pause();
    player.currentTime = 0;
  } catch (e) {}
  activeKind = null;
  syncOrbState();
}

function playMainClip(url, kind, toggleIfSame) {
  if (!url) return;
  clearHandsFreeTimer();
  if (toggleIfSame && activeKind === kind && !player.paused) {
    stopAudio();
    return;
  }
  activeKind = kind;
  player.src = url;
  player.currentTime = 0;
  applyPlaybackRate(kind);
  const p = player.play();
  if (p && typeof p.catch === "function") {
    p.catch(() => {
      activeKind = null;
      syncOrbState();
    });
  }
  syncOrbState();
}

player.addEventListener("play", () => {
  applyPlaybackRate(activeKind);
  syncOrbState();
});
player.addEventListener("pause", syncOrbState);
player.addEventListener("ended", () => {
  const finishedKind = activeKind;
  activeKind = null;
  syncOrbState();

  // Hands-free commute loop!
  if (!handsFree || activeMode !== "tutor" || idx >= queue.length) return;
  if (finishedKind === "q" && !answered) {
    thinkingCountdown = 4;
    syncOrbState();
    handsFreeTimer = setInterval(() => {
      thinkingCountdown -= 1;
      syncOrbState();
      if (thinkingCountdown <= 0) {
        clearHandsFreeTimer();
        if (handsFree && !answered) {
          choose("__handsfree__", true);
        }
      }
    }, 900);
  } else if (finishedKind === "exp" && answered) {
    handsFreeTimer = setTimeout(() => {
      if (handsFree && answered) nextCard(false);
    }, 1000);
  }
});

function syncOrbState() {
  const orb = document.getElementById("voice-orb");
  const cap = document.getElementById("orb-caption");
  if (orb && cap) {
    const speaking = activeKind && !player.paused;
    orb.classList.toggle("speaking", !!speaking);
    orb.classList.toggle("thinking", thinkingCountdown > 0);
    if (thinkingCountdown > 0) {
      cap.textContent = `心里想一下答案… ${thinkingCountdown}s`;
    } else if (speaking && activeKind === "q") {
      cap.textContent = "私教提问中 · 点圆球可暂停";
    } else if (speaking && activeKind === "exp") {
      cap.textContent = `私教讲解中（${expSpeed.toFixed(1)}x）· 点圆球可暂停`;
    } else {
      cap.textContent = answered ? "点圆球重听题目" : "点圆球听私教提问";
    }
  }
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    const expOn = activeKind === "exp" && !player.paused;
    repBtn.classList.toggle("playing", expOn);
    repBtn.textContent = expOn ? "⏸ 讲解中" : "▶ 重听讲解";
  }
}

function toggleHandsFree() {
  handsFree = !handsFree;
  const btn = document.getElementById("handsfree-btn");
  btn.textContent = handsFree ? "🎧 连播 开" : "🎧 连播 关";
  btn.classList.toggle("active", handsFree);
  if (handsFree && idx < queue.length) {
    if (!answered) playMainClip(queue[idx].q_audio, "q", false);
    else playMainClip(queue[idx].exp_audio, "exp", false);
  } else {
    clearHandsFreeTimer();
    syncOrbState();
  }
}

// Optional Voice Input (SpeechRecognition for hands-free oral answering!)
let recog = null;
let micActive = false;
function toggleVoiceAnswer() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    alert("当前浏览器不支持麦克风语音识别，可直接点选上方按钮作答。");
    return;
  }
  if (micActive && recog) {
    recog.stop();
    return;
  }
  stopAudio();
  recog = new SR();
  recog.lang = "ja-JP";
  recog.interimResults = false;
  micActive = true;
  const micBtn = document.getElementById("mic-btn");
  if (micBtn) {
    micBtn.classList.add("listening-mic");
    micBtn.textContent = "🎙 正在听你说…";
  }
  recog.onresult = e => {
    const said = (e.results[0] && e.results[0][0] && e.results[0][0].transcript || "").trim();
    const q = queue[idx];
    if (!q || answered) return;
    if (/不知道|パス|わからない/.test(said)) {
      choose("不知道");
      return;
    }
    const cleanSaid = said.replace(/[。、！？\s]/g, "");
    const hit = q.choices.find(c => {
      const cc = c.replace(/（.*）|[。、\s]/g, "");
      return cleanSaid.includes(cc) || cc.includes(cleanSaid);
    });
    if (hit) choose(hit);
    else if (/1|一|いち/.test(cleanSaid) && q.choices[0]) choose(q.choices[0]);
    else if (/2|二|に/.test(cleanSaid) && q.choices[1]) choose(q.choices[1]);
    else if (/3|三|さん/.test(cleanSaid) && q.choices[2]) choose(q.choices[2]);
    else choose("不知道");
  };
  recog.onend = () => {
    micActive = false;
    const b = document.getElementById("mic-btn");
    if (b) {
      b.classList.remove("listening-mic");
      b.textContent = "🎙 开口答";
    }
  };
  recog.onerror = () => { micActive = false; };
  recog.start();
}

function saveRecord(q, choice, result, askAgain) {
  const rec = {
    id: q.id,
    point: q.point,
    choice: String(choice || ""),
    correct: String(!!result),
    ask_again: String(!!askAgain),
    ts: new Date().toISOString()
  };
  try {
    const hist = JSON.parse(localStorage.getItem("n3_tutor_log") || "[]");
    hist.push(rec);
    localStorage.setItem("n3_tutor_log", JSON.stringify(hist));
  } catch (e) {}

  // Live update local Mastery Dashboard status immediately!
  const gList = DATA.mastery.grammar.items;
  for (let i = 0; i < gList.length; i++) {
    if (gList[i].name === q.point || q.point.includes(gList[i].name)) {
      gList[i].tier = (!result || askAgain) ? "todo" : "done";
    }
  }

  if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
    fetch("./api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rec)
    }).catch(() => {});
  } else if (location.protocol.startsWith("http")) {
    const body = new URLSearchParams(Object.assign({ "form-name": "n3-answers" }, rec)).toString();
    fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body
    }).catch(() => {});
  }
}

function choose(val, fromHandsFree) {
  if (answered) return;
  hideWordPopover();
  answered = true;
  pickedVal = val;
  const q = queue[idx];
  const isCorrect = fromHandsFree ? true : (val === q.answer);
  if (!fromHandsFree) {
    saveRecord(q, val, isCorrect, false);
    if (!isCorrect) queue.push(q);
  }
  renderTutor();
  playMainClip(q.exp_audio, "exp", false);
}

function nextCard(requeue) {
  hideWordPopover();
  stopAudio();
  const q = queue[idx];
  if (requeue) {
    saveRecord(q, pickedVal, false, true);
    queue.push(q);
  }
  idx += 1;
  answered = false;
  pickedVal = null;
  renderTutor();
  if (idx < queue.length && queue[idx].q_audio) {
    playMainClip(queue[idx].q_audio, "q", false);
  }
}

function renderTutor() {
  document.getElementById("countdown-txt").textContent = `距考试 ${DATA.days_to_exam} 天`;
  document.getElementById("top-speed-btn").textContent = `讲解 ${expSpeed.toFixed(1)}x`;

  const total = queue.length;
  const pct = Math.min(100, Math.round((idx / total) * 100));
  document.getElementById("card-counter").textContent = idx < total ? `${idx + 1} / ${total}` : "已完成";
  document.getElementById("prog-fill").style.width = `${pct}%`;

  const box = document.getElementById("voice-card");
  if (idx >= total) {
    box.innerHTML = `
      <div class="done-wrap">
        <h1 class="done-title">今天这一组过关了</h1>
        <p class="done-sub">去休息吧，明天继续。</p>
        <button class="next-btn" onclick="idx=0;answered=false;renderTutor()">再练一遍</button>
      </div>
    `;
    playMainClip(DATA.done_audio, "done", false);
    return;
  }

  const q = queue[idx];
  warmAudio(q.q_audio);
  warmAudio(q.exp_audio);
  if (idx + 1 < total) {
    warmAudio(queue[idx + 1].q_audio);
    warmAudio(queue[idx + 1].exp_audio);
  }

  const gridCls = q.choices.length > 2 ? "choices-grid stacked" : "choices-grid";
  const choicesHTML = q.choices.map(c => {
    let cls = "choice-btn";
    if (answered) {
      if (c === q.answer) cls += " correct";
      else if (c === pickedVal) cls += " wrong";
    }
    // Strict rule: BEFORE answering, plain text only (zero dictionary spoiler!).
    // AFTER answering, choices ALSO support word hover/tap lookup!
    const innerLabel = answered ? annotateJapanese(c) : escapeHtml(c);
    return `<button class="${cls}" ${answered ? "disabled" : ""} onclick='choose(${JSON.stringify(c)}, false)'>${innerLabel}</button>`;
  }).join("");

  const assistHTML = !answered ? `
    <div class="quick-assist-row">
      <button class="assist-btn" id="mic-btn" onclick="toggleVoiceAnswer()">🎙 开口答</button>
      <button class="assist-btn" onclick='choose("不知道", false)'>直接听讲解</button>
    </div>
  ` : "";

  const speedBtnsHTML = SPEEDS.map(s =>
    `<button class="spd-btn ${s === expSpeed ? "active" : ""}" data-spd="${s}" onclick="setExpSpeed(${s})">${s.toFixed(1)}x</button>`
  ).join("");

  const answerZoneHTML = answered ? `
    <div class="answer-zone" id="answer-zone">
      <div class="exp-controls">
        <button class="replay-exp-btn" id="exp-replay-btn" onclick="playMainClip(queue[idx].exp_audio, 'exp', true)">▶ 重听讲解</button>
        <div class="speed-group" title="讲解语速">
          ${speedBtnsHTML}
        </div>
      </div>
      <div class="full-sentence-box">
        <div class="full-sentence-hint">
          <span>完整原句</span>
          <span>点词 / 悬停看读音与原形</span>
        </div>
        <div class="full-sentence-ja">${annotateJapanese(q.full_ja)}</div>
      </div>
      <p class="explain-text">${escapeHtml(q.explain)}</p>
      <div class="nav-row">
        <button class="again-btn" onclick="nextCard(true)">还要考</button>
        <button class="next-btn" onclick="nextCard(false)">下一题 →</button>
      </div>
    </div>
  ` : "";

  box.innerHTML = `
    <div class="orb-stage">
      <button class="voice-orb" id="voice-orb" onclick="playMainClip(queue[idx].q_audio, 'q', true)" aria-label="播放题目语音">
        <div class="orb-bars"><span></span><span></span><span></span><span></span></div>
      </button>
      <div class="orb-caption" id="orb-caption">点圆球听私教提问</div>
    </div>
    <p class="prompt-cue">${escapeHtml(q.prompt)}</p>
    <div class="${gridCls}">
      ${choicesHTML}
    </div>
    ${assistHTML}
    ${answerZoneHTML}
  `;
  syncOrbState();
}

// ================= ANSWER-ZONE WORD POPOVER LOGIC =================
const popEl = document.getElementById("word-popover");
let activeTokEl = null;
let hoverHideTimer = null;

function playWordAudio(surface) {
  const info = DATA.words[surface];
  if (!info || !info.audio) return;
  // Pause main explanation briefly so word pronunciation is crystal clear
  if (!player.paused) player.pause();
  wordPlayer.src = info.audio;
  wordPlayer.currentTime = 0;
  wordPlayer.playbackRate = 1.0;
  wordPlayer.play().catch(() => {});
}

function showWordPopover(surface, anchorEl, autoSpeak) {
  const info = DATA.words[surface];
  if (!info) return;
  clearTimeout(hoverHideTimer);
  if (activeTokEl) activeTokEl.classList.remove("active-tok");
  activeTokEl = anchorEl;
  if (anchorEl) anchorEl.classList.add("active-tok");

  const showHead = info.head && info.head !== surface ? `${surface}（原形：${info.head}）` : surface;
  popEl.innerHTML = `
    <div class="wp-top">
      <div>
        <span class="wp-head">${escapeHtml(surface)}</span>
        <span class="wp-kana">${escapeHtml(info.kana)}</span>
        <span class="wp-pitch">${escapeHtml(info.pitch || "")}</span>
      </div>
      <button class="wp-speak" onclick='playWordAudio(${JSON.stringify(surface)})'>🔊 发音</button>
    </div>
    <div class="wp-pos">${escapeHtml(info.head !== surface ? "原形 " + info.head + " · " + info.pos : info.pos)}</div>
    <div class="wp-zh">${escapeHtml(info.zh)}</div>
    ${info.tip ? `<div class="wp-tip">${escapeHtml(info.tip)}</div>` : ""}
  `;
  popEl.classList.add("open");

  // Position cleanly near anchor element without overflowing viewport
  if (anchorEl) {
    const r = anchorEl.getBoundingClientRect();
    const pw = popEl.offsetWidth || 290;
    const ph = popEl.offsetHeight || 130;
    let left = r.left + r.width / 2 - pw / 2;
    left = Math.max(14, Math.min(window.innerWidth - pw - 14, left));
    let top = r.top - ph - 10;
    if (top < 12) top = r.bottom + 10;
    popEl.style.left = `${left}px`;
    popEl.style.top = `${top}px`;
  }
  if (autoSpeak) playWordAudio(surface);
}

function hideWordPopover() {
  popEl.classList.remove("open");
  if (activeTokEl) {
    activeTokEl.classList.remove("active-tok");
    activeTokEl = null;
  }
}

// Desktop hover on .w-tok inside .answer-zone / answered choices
document.addEventListener("mouseover", e => {
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (!tok || !answered) return;
  showWordPopover(tok.dataset.w, tok, false);
});

document.addEventListener("mouseout", e => {
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (!tok) return;
  hoverHideTimer = setTimeout(() => {
    if (!popEl.matches(":hover")) hideWordPopover();
  }, 240);
});

popEl.addEventListener("mouseenter", () => clearTimeout(hoverHideTimer));
popEl.addEventListener("mouseleave", () => hideWordPopover());

// Tap / Click on .w-tok (plays pronunciation immediately!) or outside to dismiss
document.addEventListener("click", e => {
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (tok && answered) {
    e.stopPropagation();
    showWordPopover(tok.dataset.w, tok, true);
    return;
  }
  if (!e.target.closest("#word-popover")) {
    hideWordPopover();
  }
});

// Text selection lookup ONLY inside #answer-zone!
document.addEventListener("mouseup", () => {
  if (!answered) return;
  const sel = window.getSelection && window.getSelection();
  if (!sel || sel.isCollapsed) return;
  const az = document.getElementById("answer-zone");
  if (!az || !az.contains(sel.anchorNode)) return;
  const txt = sel.toString().trim();
  if (!txt || txt.length > 18) return;
  const hit = DICT_KEYS.find(k => k === txt || k.includes(txt) || txt.includes(k));
  if (hit) {
    const range = sel.getRangeAt(0);
    showWordPopover(hit, range, false);
  }
});

// ================= SECONDARY VIEW: MASTERY DASHBOARD =================
function switchMode(m) {
  activeMode = m;
  hideWordPopover();
  if (m === "dash") stopAudio();
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-dash").classList.toggle("active", m === "dash");
  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("dash-view").classList.toggle("active", m === "dash");
  if (m === "dash") renderDashboard();
}

function recalcCounts(modKey) {
  const items = DATA.mastery[modKey].items;
  const c = { todo: 0, wip: 0, done: 0, total: items.length };
  items.forEach(it => { c[it.tier] += 1; });
  DATA.mastery[modKey].counts = c;
  return c;
}

function selectDashMod(modKey) {
  dashMod = modKey;
  expandedPt = null;
  const c = recalcCounts(modKey);
  if (c[dashTier] === 0) {
    dashTier = c.todo > 0 ? "todo" : (c.wip > 0 ? "wip" : "done");
  }
  renderDashboard();
}

function selectDashTier(t) {
  dashTier = t;
  expandedPt = null;
  renderDashboard();
}

function renderDashboard() {
  const order = ["grammar", "henkei", "listening", "vocab"];
  const sumEl = document.getElementById("dash-summary");
  sumEl.innerHTML = order.map(k => {
    const m = DATA.mastery[k];
    const c = recalcCounts(k);
    const pDone = ((c.done / Math.max(1, c.total)) * 100).toFixed(1);
    const pWip = ((c.wip / Math.max(1, c.total)) * 100).toFixed(1);
    const pTodo = ((c.todo / Math.max(1, c.total)) * 100).toFixed(1);
    return `
      <div class="sum-row" onclick="selectDashMod('${k}')">
        <div class="sum-head">
          <span class="sum-title">${m.label}</span>
          <span class="sum-nums">已过关 ${c.done} · 巩固中 ${c.wip} · 待攻克 ${c.todo}</span>
        </div>
        <div class="tri-bar">
          <div class="tri-seg-done" style="width:${pDone}%"></div>
          <div class="tri-seg-wip" style="width:${pWip}%"></div>
          <div class="tri-seg-todo" style="width:${pTodo}%"></div>
        </div>
      </div>
    `;
  }).join("");

  document.getElementById("mod-tabs").innerHTML = order.map(k => {
    const m = DATA.mastery[k];
    return `<button class="mod-tab ${dashMod === k ? "active" : ""}" onclick="selectDashMod('${k}')">${m.label} ${m.counts.total}</button>`;
  }).join("");

  const curCounts = DATA.mastery[dashMod].counts;
  document.getElementById("tier-tabs").innerHTML = `
    <button class="tier-tab ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待攻克 ${curCounts.todo}</button>
    <button class="tier-tab ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固中 ${curCounts.wip}</button>
    <button class="tier-tab ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已过关 ${curCounts.done}</button>
  `;

  renderMasteryList();
}

function togglePtNote(i) {
  expandedPt = (expandedPt === i) ? null : i;
  renderMasteryList();
}

function renderMasteryList() {
  const q = (document.getElementById("pt-search").value || "").trim().toLowerCase();
  const items = DATA.mastery[dashMod].items.filter(it => {
    if (q) return it.name.toLowerCase().includes(q) || (it.sub || "").toLowerCase().includes(q);
    return it.tier === dashTier;
  });

  const listEl = document.getElementById("point-list");
  if (!items.length) {
    listEl.innerHTML = `<div style="padding:24px 4px;text-align:center;color:var(--ink-3);font-size:13px;">这一栏目前是空的</div>`;
    return;
  }

  listEl.innerHTML = items.map((it, i) => `
    <div class="pt-item" onclick="togglePtNote(${i})">
      <div class="pt-main">
        <div class="pt-left">
          <span class="dot ${it.tier}"></span>
          <span class="pt-name">${escapeHtml(it.name)}</span>
        </div>
        <span class="pt-sub">${escapeHtml(it.sub)}</span>
      </div>
      ${expandedPt === i && it.note ? `<div class="pt-note">${escapeHtml(it.note)}</div>` : ""}
    </div>
  `).join("");
}

renderTutor();
</script>
</body>
</html>
"""

final_html = html.replace("__PAYLOAD__", payload)
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(final_html)
print("Wrote Perfected Voice-Tutor + Answer-Zone Word Dict + Mastery Dashboard HTML:", HTML_PATH, "size:", len(final_html), "bytes")
