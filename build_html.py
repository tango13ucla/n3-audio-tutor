#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the JLPT N3 Studio Neural Audio Tutor + Mastery Panorama PWA (index.html).
Designed with Mobile-First Ergonomics (Android Chrome PWA, Thumb Zone, Bottom-Sheet Dict,
Walk Radio + MediaSession + WakeLock) AND Desktop Studio Perfection (2-Column Mastery Split,
Full Keyboard Hotkeys, Hover Popover Dict, Architectural Typography & Whitespace).
"""
import glob
import json
import os
import re

from tutor_data import KANA_ADVERBS_36, TUTOR_ITEMS, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
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
    alias = info.get("audio_alias")
    entry["audio"] = word_audio_map.get(surf) or (word_audio_map.get(alias, "") if alias else "")
    rich_words[surf] = entry


def resolve_word_audio(w: str) -> str:
    return (rich_words.get(w, {}).get("audio") or word_audio_map.get(w, ""))


# Analyze latest practice_log.jsonl so Brain orders unseen/missed P0 items FIRST
# and marks recently-correct items as consolidation (direct retrieval, no redundant lecture)
latest_by_qid = {}
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            qid = str(rec.get("id", "")).strip()
            if qid.endswith("-twin"):
                qid = qid[:-5]
            if qid:
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                latest_by_qid[qid] = {"ok": ok and not again, "again": again}

g_state_map = {p["name"]: p for p in live_state.get("grammar_points", [])}
h_state_map = {p["id"]: p for p in live_state.get("henkei_points", [])}
v_state_map = {p["word"]: p for p in live_state.get("vocab_tracked", [])}
l_state_map = {p["id"]: p for p in live_state.get("listening_points", [])}


def strip_opt_prefix(s: str) -> str:
    return re.sub(r"^[a-dA-D]\.\s*", "", str(s)).strip()


def resolve_point_status(point_key: str) -> str:
    if point_key in g_state_map:
        return g_state_map[point_key].get("status", "yellow")
    if point_key in h_state_map:
        return h_state_map[point_key].get("status", "red")
    if point_key in v_state_map:
        return v_state_map[point_key].get("status", "red")
    if point_key in l_state_map:
        return l_state_map[point_key].get("status", "red")
    return "red"


def build_card(q: dict, subject: str, fallback_point_label: str) -> dict:
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

    point_key = t_item.get("point_key") or fallback_point_label
    if point_key in l_state_map:
        lp = l_state_map[point_key]
        display_point = lp.get("name") or fallback_point_label
    elif point_key in h_state_map:
        display_point = h_state_map[point_key].get("name") or fallback_point_label
    else:
        display_point = fallback_point_label or point_key

    pt_status = resolve_point_status(point_key)
    hist = latest_by_qid.get(qid)

    if hist is not None:
        if not hist["ok"]:
            priority_group = 0
            needs_teach = True
        else:
            priority_group = 2
            needs_teach = False
    else:
        priority_group = 1
        needs_teach = pt_status in ("red", "orange", "gray")

    micro = None
    raw_micro = t_item.get("micro_lesson")
    if raw_micro:
        audio_urls = [resolve_word_audio(w) for w in raw_micro.get("audio_words", []) if resolve_word_audio(w)]
        micro = {
            "scene": raw_micro.get("scene", "contrast_box"),
            "left": raw_micro.get("left", {}),
            "right": raw_micro.get("right", {}),
            "hook": raw_micro.get("hook", ""),
            "audio_words": raw_micro.get("audio_words", []),
            "audio_urls": audio_urls,
        }

    return {
        "id": qid,
        "subject": subject,
        "point": display_point,
        "point_key": point_key,
        "roi_tag": t_item.get("roi_tag", "高频核心"),
        "walk_slot": t_item.get("walk_slot", "morning"),
        "priority_group": priority_group,
        "needs_teach": bool(needs_teach and micro),
        "prompt": prompt_display,
        "choices": choices,
        "answer": answer,
        "full_ja": full_ja,
        "explain": explain,
        "option_notes": t_item.get("option_notes", {}),
        "micro": micro,
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
for p_tier in (0, 1, 2):
    tier_buckets = [
        [c for c in bucket if c["priority_group"] == p_tier]
        for bucket in (g_list, l_list, v_list, h_list)
    ]
    max_len = max((len(b) for b in tier_buckets), default=0)
    for i in range(max_len):
        for b in tier_buckets:
            if i < len(b):
                cards.append(b[i])

card_by_point_key = {}
for c in cards:
    card_by_point_key[c["point_key"]] = c["id"]
    card_by_point_key[c["point"]] = c["id"]


def norm_tier(status: str) -> str:
    if status in ("red", "orange"):
        return "todo"
    if status == "green":
        return "done"
    return "wip"


grammar_items = []
for p in live_state.get("grammar_points", []):
    nm = p.get("name", "")
    st = p.get("status", "yellow")
    grammar_items.append({
        "key": nm,
        "name": nm,
        "sub": p.get("meaning", ""),
        "family": re.sub(r"^\d+\.\s*", "", p.get("family", "")),
        "tier": norm_tier(st),
        "roi": bool(st in ("red", "orange") or p.get("exam_alert")),
        "card_id": card_by_point_key.get(nm, ""),
        "note": p.get("exam_alert") or p.get("note", ""),
    })

henkei_items = []
for p in live_state.get("henkei_points", []):
    if p.get("tier") == "basic_n5n4" and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    st = p.get("status", "gray")
    henkei_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("example", ""),
        "family": re.sub(r"^\d+(?:\.\d+)?\s*", "", p.get("subcategory") or p.get("category", "")),
        "tier": norm_tier(st),
        "roi": bool(st in ("red", "orange")),
        "card_id": card_by_point_key.get(pid, ""),
        "note": p.get("note", ""),
    })

vocab_items = []
for p in live_state.get("vocab_tracked", []):
    w = p.get("word", "")
    st = p.get("status", "red")
    vocab_items.append({
        "key": w,
        "name": w,
        "sub": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "family": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": norm_tier(st),
        "roi": bool(st in ("red", "orange") or p.get("wrong", 0) >= 2),
        "card_id": card_by_point_key.get(w, ""),
        "audio": resolve_word_audio(w),
        "note": f"练过 {p.get('seen', 0)} 次 · 错 {p.get('wrong', 0)} 次",
    })

listening_items = []
for p in live_state.get("listening_points", []):
    if not p.get("is_core165") and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    st = p.get("status", "gray")
    listening_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("meaning", "") or p.get("full", ""),
        "family": p.get("category", ""),
        "tier": norm_tier(st),
        "roi": bool(st in ("red", "orange") or p.get("trap")),
        "card_id": card_by_point_key.get(pid, ""),
        "note": p.get("trap", "") or p.get("note", ""),
    })


def count_tiers(items):
    c = {"todo": 0, "wip": 0, "done": 0, "roi": 0}
    for it in items:
        c[it["tier"]] += 1
        if it.get("roi") and it["tier"] != "done":
            c["roi"] += 1
    c["total"] = len(items)
    return c


kana36_enriched = []
for fam in KANA_ADVERBS_36:
    pairs_out = []
    for pr in fam["pairs"]:
        a = dict(pr["a"])
        b = dict(pr["b"])
        a["audio"] = resolve_word_audio(a["w"])
        b["audio"] = resolve_word_audio(b["w"])
        a["card_id"] = card_by_point_key.get(a["w"], "")
        b["card_id"] = card_by_point_key.get(b["w"], "")
        pairs_out.append({"a": a, "b": b, "scene": pr["scene"]})
    kana36_enriched.append({
        "family": fam["family"],
        "tag": fam["tag"],
        "pairs": pairs_out,
    })

mastery_data = {
    "grammar": {"label": "语法", "counts": count_tiers(grammar_items), "items": grammar_items},
    "henkei": {"label": "核心活用", "counts": count_tiers(henkei_items), "items": henkei_items},
    "listening": {"label": "听力口语", "counts": count_tiers(listening_items), "items": listening_items},
    "vocab": {"label": "重点词", "counts": count_tiers(vocab_items), "items": vocab_items},
}

payload = json.dumps({
    "plan_date": plan.get("plan_date", "2026-11-14"),
    "exam_date": "2026-12-06",
    "days_to_exam": plan.get("days_to_exam", 22),
    "done_audio": "./audio/done.mp3",
    "cards": cards,
    "words": rich_words,
    "mastery": mastery_data,
    "kana36": kana36_enriched,
}, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
<meta name="description" content="JLPT N3 真人级神经网络语音私教 · 声画微课 · 走路随身电台 · 全局掌握度沙盘" />
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
<title>JLPT N3 · 语音私教</title>
<style>
  :root {
    --bg: #F7F6F2;
    --card: #FFFFFF;
    --subtle: #F0EEE8;
    --subtle-2: #E8E5DC;
    --line: rgba(28, 25, 23, 0.08);
    --line-strong: rgba(28, 25, 23, 0.18);
    --ink: #1C1917;
    --ink-2: #57534E;
    --ink-3: #8C857B;
    --green: #246E53;
    --green-bg: #ECF7F2;
    --green-border: rgba(36, 110, 83, 0.30);
    --amber: #B4741A;
    --amber-bg: #FCF6EC;
    --amber-border: rgba(180, 116, 26, 0.28);
    --red: #BF3E35;
    --red-bg: #FDF2F1;
    --red-border: rgba(191, 62, 53, 0.30);
    --sans: "Inter", -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans", "Noto Sans JP", sans-serif;
    --jp: "Noto Sans JP", "Hiragino Sans", "PingFang SC", sans-serif;
    --radius-xl: 28px;
    --radius-lg: 20px;
    --radius-md: 14px;
    --shadow-card: 0 16px 44px -20px rgba(28, 25, 23, 0.08), 0 2px 6px rgba(28, 25, 23, 0.02);
  }

  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

  html, body {
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  body {
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(14px + env(safe-area-inset-top)) 16px calc(22px + env(safe-area-inset-bottom));
  }

  /* ================= RESPONSIVE SHELL (Mobile-First + Desktop Studio) ================= */
  .app-shell {
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    min-height: calc(100dvh - 36px - env(safe-area-inset-top) - env(safe-area-inset-bottom));
  }

  @media (min-width: 900px) {
    body {
      padding: 28px 36px 32px;
    }
    .app-shell {
      max-width: 980px;
      min-height: calc(100dvh - 60px);
    }
  }

  /* ================= CLEAN TOP HEADER ================= */
  .app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding: 0 2px;
  }
  .brand-left {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  .countdown {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .exam-date-sub {
    display: none;
    font-size: 12.5px;
    color: var(--ink-3);
  }
  @media (min-width: 900px) {
    .app-header { margin-bottom: 24px; }
    .countdown { font-size: 15px; }
    .exam-date-sub { display: inline; }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .install-pill {
    display: none;
    border: 1px solid var(--green-border);
    background: var(--green-bg);
    color: var(--green);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 600;
    padding: 6px 11px;
    border-radius: 999px;
    cursor: pointer;
  }
  .install-pill.visible { display: inline-flex; align-items: center; gap: 4px; }

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
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.16s ease;
  }
  .mode-btn.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(28, 25, 23, 0.08);
  }

  /* ================= VIEW 1: VOICE TUTOR (Primary) ================= */
  .tutor-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    width: 100%;
    max-width: 480px;
    margin: 0 auto;
  }
  @media (min-width: 900px) {
    .tutor-wrap {
      max-width: 680px;
    }
  }
  .tutor-wrap.hidden { display: none; }

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
  .counter-btn {
    border: none;
    background: transparent;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 12.5px;
    font-variant-numeric: tabular-nums;
    padding: 4px 6px;
    margin-left: -6px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.14s ease, color 0.14s ease;
  }
  .counter-btn:hover {
    background: var(--subtle);
    color: var(--ink);
  }
  .session-controls {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .pill-ctrl {
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    padding: 5px 11px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.15s ease;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .pill-ctrl:hover {
    border-color: var(--line-strong);
    color: var(--ink);
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
    margin-bottom: 16px;
  }
  .progress-fill {
    height: 100%;
    background: var(--green);
    border-radius: 999px;
    transition: width 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .voice-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: var(--radius-xl);
    padding: 26px 20px 22px;
    box-shadow: var(--shadow-card);
    transition: padding 0.2s ease;
  }
  @media (min-width: 900px) {
    .voice-card {
      padding: 38px 44px 32px;
    }
  }

  /* Subtle Point Context Chip */
  .card-eyebrow {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    font-size: 12px;
    color: var(--ink-3);
  }
  .subj-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-weight: 500;
    color: var(--ink-2);
  }
  .subj-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--green);
  }

  /* ================= STAGE A: 15s VISUAL+AUDIO MICRO-LESSON (Teach-Before-Test) ================= */
  .teach-stage {
    animation: fadeUp 0.2s ease;
  }
  .teach-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }
  .teach-badge {
    font-size: 12px;
    font-weight: 600;
    color: var(--amber);
    background: var(--amber-bg);
    border: 1px solid var(--amber-border);
    padding: 4px 10px;
    border-radius: 999px;
  }
  .pair-audio-btn {
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.14s ease;
  }
  .pair-audio-btn.speaking {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
  }

  .scene-art {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 14px 16px;
    margin-bottom: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 76px;
  }
  .scene-art svg {
    width: 100%;
    max-width: 340px;
    height: 58px;
    overflow: visible;
  }

  .pair-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 14px;
  }
  @media (max-width: 390px) {
    .pair-grid { grid-template-columns: 1fr; }
  }
  .pair-box {
    background: var(--bg);
    border: 1.5px solid var(--line);
    border-radius: 16px;
    padding: 14px 13px;
    text-align: left;
    cursor: pointer;
    transition: all 0.16s ease;
    position: relative;
  }
  .pair-box:hover {
    border-color: var(--line-strong);
    background: #FFFFFF;
  }
  .pair-box.primary-anchor {
    border-color: var(--green-border);
    background: rgba(236, 247, 242, 0.45);
  }
  .pair-box.speaking-box {
    border-color: var(--green);
    background: var(--green-bg);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px -8px rgba(36, 110, 83, 0.28);
  }
  .pair-ja {
    font-family: var(--jp);
    font-size: 16px;
    font-weight: 600;
    color: var(--ink);
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
  }
  .pair-spk-ic {
    font-size: 11px;
    color: var(--ink-3);
    font-family: var(--sans);
    font-weight: 400;
    flex-shrink: 0;
  }
  .pair-sub {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--green);
    margin-bottom: 4px;
  }
  .pair-box.contrast-anchor .pair-sub {
    color: var(--ink-2);
  }
  .pair-desc {
    font-size: 12.5px;
    color: var(--ink-2);
    line-height: 1.45;
  }

  .teach-hook {
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--ink);
    background: var(--subtle);
    border-radius: 13px;
    padding: 11px 14px;
    margin-bottom: 16px;
  }

  /* ================= STAGE B: TACTILE VOICE ORB & TEST ================= */
  .orb-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 18px;
  }
  .voice-orb {
    position: relative;
    width: 76px;
    height: 76px;
    border-radius: 50%;
    border: none;
    background: var(--ink);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 10px 26px -6px rgba(28, 25, 23, 0.26);
    transition: transform 0.16s ease, background 0.2s ease, box-shadow 0.2s ease;
  }
  @media (min-width: 900px) {
    .voice-orb { width: 82px; height: 82px; }
  }
  .voice-orb:hover { transform: translateY(-1px); }
  .voice-orb:active { transform: scale(0.95); }
  .voice-orb.speaking {
    background: var(--green);
    box-shadow: 0 0 0 8px rgba(36, 110, 83, 0.13), 0 10px 26px -6px rgba(36, 110, 83, 0.35);
    animation: orbPulse 1.6s ease-in-out infinite;
  }
  .voice-orb.thinking {
    background: var(--amber);
    box-shadow: 0 0 0 8px rgba(180, 116, 26, 0.15);
  }
  @keyframes orbPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.045); }
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
    margin-top: 9px;
    font-size: 12.5px;
    color: var(--ink-3);
  }

  .prompt-cue {
    font-family: var(--jp);
    font-size: 18.5px;
    font-weight: 500;
    line-height: 1.65;
    text-align: center;
    color: var(--ink);
    margin: 0 0 22px;
    padding: 0 4px;
  }
  @media (min-width: 900px) {
    .prompt-cue {
      font-size: 21px;
      margin-bottom: 26px;
    }
  }

  /* Thumb-Ergonomic + Desktop Keycap Choices */
  .choices-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  .choices-grid.stacked {
    grid-template-columns: 1fr;
  }
  .choice-btn {
    position: relative;
    background: var(--bg);
    border: 1.5px solid var(--line);
    border-radius: 16px;
    min-height: 56px;
    padding: 15px 14px;
    font-family: var(--jp);
    font-size: 16.5px;
    font-weight: 500;
    color: var(--ink);
    text-align: center;
    cursor: pointer;
    transition: all 0.14s ease;
    line-height: 1.45;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .choices-grid.stacked .choice-btn {
    justify-content: space-between;
    text-align: left;
    padding: 14px 16px;
  }
  .choice-btn:hover:not(:disabled) {
    border-color: var(--line-strong);
    background: #FFFFFF;
    transform: translateY(-1px);
  }
  .choice-btn:active:not(:disabled) {
    transform: scale(0.985);
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

  /* Subtle Desktop Keycaps (Hidden on touch devices!) */
  .kbd-hint {
    display: none;
    font-family: var(--sans);
    font-size: 11px;
    font-weight: 500;
    color: var(--ink-3);
    background: rgba(28, 25, 23, 0.05);
    border: 1px solid rgba(28, 25, 23, 0.09);
    border-radius: 5px;
    padding: 1px 5px;
    line-height: 1.3;
    flex-shrink: 0;
  }
  @media (hover: hover) and (pointer: fine) {
    .kbd-hint { display: inline-block; }
    .choices-grid:not(.stacked) .choice-btn .kbd-hint {
      position: absolute;
      top: 7px;
      right: 8px;
      font-size: 10.5px;
    }
  }

  .quick-assist-row {
    display: flex;
    gap: 8px;
    margin-top: 12px;
  }
  .assist-btn {
    flex: 1;
    background: transparent;
    border: 1px dashed var(--line-strong);
    border-radius: 14px;
    min-height: 44px;
    padding: 10px 10px;
    font-family: var(--sans);
    font-size: 12.5px;
    color: var(--ink-2);
    cursor: pointer;
    transition: all 0.14s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
  }
  .assist-btn:hover {
    background: var(--bg);
    color: var(--ink);
    border-style: solid;
  }
  .assist-btn.listening-mic {
    background: var(--green-bg);
    border-style: solid;
    border-color: var(--green-border);
    color: var(--green);
    font-weight: 600;
  }

  /* ================= STAGE C: WALK RADIO MODE (Zero-Prompt Eyes-Free) ================= */
  .walk-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--green-bg);
    border: 1px solid var(--green-border);
    color: var(--green);
    padding: 9px 14px;
    border-radius: 14px;
    margin-bottom: 18px;
    font-size: 12.5px;
    font-weight: 500;
  }
  .walk-controls-row {
    display: grid;
    grid-template-columns: 1fr 1.3fr 1fr;
    gap: 10px;
    margin-top: 18px;
  }
  .walk-nav-btn {
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink);
    border-radius: 16px;
    min-height: 52px;
    font-family: var(--sans);
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
  }
  .walk-nav-btn.primary {
    background: var(--ink);
    color: #FFFFFF;
    border-color: var(--ink);
    font-weight: 600;
  }

  /* ================= ANSWER ZONE (Full Option Breakdown + Anti-Spoiler Dict!) ================= */
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
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .replay-exp-btn.playing {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
  }
  .speed-group {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    background: var(--subtle);
    padding: 2.5px;
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
    margin-bottom: 12px;
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
  @media (min-width: 900px) {
    .full-sentence-ja { font-size: 18px; }
  }

  /* Interactive Dictionary Token (ONLY rendered inside .answer-zone!) */
  .w-tok {
    border-bottom: 1.5px dashed rgba(28, 25, 23, 0.28);
    padding-bottom: 1px;
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .w-tok:hover, .w-tok.active-tok {
    background: rgba(36, 110, 83, 0.13);
    color: var(--green);
    border-bottom-color: var(--green);
  }

  /* Option-by-Option Breakdown List */
  .opt-breakdown {
    display: flex;
    flex-direction: column;
    gap: 7px;
    margin-bottom: 16px;
  }
  .opt-row {
    display: flex;
    align-items: baseline;
    gap: 9px;
    padding: 10px 12px;
    border-radius: 13px;
    background: var(--bg);
    border: 1px solid transparent;
    font-size: 13.5px;
    line-height: 1.55;
  }
  .opt-row.is-ans {
    background: rgba(236, 247, 242, 0.65);
    border-color: rgba(36, 110, 83, 0.20);
  }
  .opt-mark {
    font-size: 11.5px;
    font-weight: 700;
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .opt-row.is-ans .opt-mark {
    background: var(--green);
    color: #FFFFFF;
  }
  .opt-row.is-dist .opt-mark {
    background: rgba(28, 25, 23, 0.08);
    color: var(--ink-2);
  }
  .opt-body {
    flex: 1;
    min-width: 0;
  }
  .opt-head-ja {
    font-family: var(--jp);
    font-weight: 600;
    color: var(--ink);
    margin-right: 6px;
  }
  .opt-note-zh {
    color: var(--ink-2);
  }
  .spaced-hint {
    font-size: 12px;
    color: var(--amber);
    background: var(--amber-bg);
    border: 1px solid var(--amber-border);
    border-radius: 11px;
    padding: 7px 12px;
    margin-bottom: 14px;
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
    min-height: 50px;
    padding: 13px 16px;
    font-family: var(--sans);
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .again-btn:hover { border-color: var(--line-strong); color: var(--ink); }
  .next-btn {
    flex: 1;
    background: var(--ink);
    color: #FFFFFF;
    border: none;
    border-radius: 15px;
    min-height: 50px;
    padding: 13px 20px;
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: opacity 0.14s ease, transform 0.12s ease;
  }
  .next-btn:hover { opacity: 0.93; }
  .next-btn:active { transform: scale(0.99); }
  .next-btn .kbd-hint {
    color: rgba(255,255,255,0.75);
    background: rgba(255,255,255,0.14);
    border-color: rgba(255,255,255,0.2);
  }

  /* Whisper-Quiet Desktop Hotkey Footer + Sync Trigger */
  .studio-footer {
    margin-top: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 6px;
    font-size: 12px;
    color: var(--ink-3);
  }
  .desktop-hotkeys {
    display: none;
  }
  @media (hover: hover) and (pointer: fine) and (min-width: 900px) {
    .desktop-hotkeys { display: inline; }
  }
  .footer-link {
    border: none;
    background: transparent;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 12px;
    padding: 4px 6px;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .footer-link:hover { color: var(--ink); }

  /* ================= WORD DICTIONARY POPOVER (Desktop Floating + Mobile Bottom Sheet!) ================= */
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(28, 25, 23, 0.22);
    z-index: 990;
    display: none;
  }
  .sheet-backdrop.open { display: block; }

  .word-popover {
    position: fixed;
    z-index: 999;
    background: #1C1917;
    color: #F7F6F2;
    box-shadow: 0 20px 48px rgba(0, 0, 0, 0.28);
    display: none;
  }
  .word-popover.open { display: block; }

  @media (max-width: 767px) {
    .word-popover {
      left: 12px !important;
      right: 12px !important;
      bottom: calc(12px + env(safe-area-inset-bottom)) !important;
      top: auto !important;
      width: auto;
      border-radius: 22px;
      padding: 18px 18px 18px;
      animation: slideSheetUp 0.18s cubic-bezier(0.22, 1, 0.36, 1);
    }
  }
  @media (min-width: 768px) {
    .sheet-backdrop.open { display: none; }
    .word-popover {
      width: 330px;
      border-radius: 18px;
      padding: 15px 17px;
      animation: popIn 0.14s ease;
    }
  }
  @keyframes slideSheetUp {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes popIn {
    from { opacity: 0; transform: translateY(4px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  .wp-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 7px;
  }
  .wp-head {
    font-family: var(--jp);
    font-size: 18px;
    font-weight: 600;
    color: #FFFFFF;
  }
  .wp-kana {
    font-family: var(--jp);
    font-size: 13.5px;
    color: #D6D3CD;
    margin-left: 6px;
  }
  .wp-pitch {
    font-size: 12px;
    color: #8CE0C2;
    margin-left: 4px;
  }
  .wp-speak {
    border: 1px solid rgba(255,255,255,0.20);
    background: rgba(255,255,255,0.11);
    color: #FFFFFF;
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    flex-shrink: 0;
  }
  .wp-pos {
    display: inline-block;
    font-size: 11.5px;
    color: #C7C2B8;
    background: rgba(255,255,255,0.09);
    padding: 2.5px 8px;
    border-radius: 6px;
    margin-bottom: 8px;
  }
  .wp-zh {
    font-size: 14.5px;
    font-weight: 500;
    color: #FFFFFF;
    margin-bottom: 5px;
    line-height: 1.45;
  }
  .wp-tip {
    font-size: 12.5px;
    color: #B8B2A7;
    line-height: 1.5;
  }

  /* ================= VIEW 2: MASTERY DASHBOARD (Mobile Stack + Desktop 2-Col Split!) ================= */
  .dash-wrap {
    display: none;
    flex-direction: column;
    gap: 14px;
    padding-bottom: 24px;
    width: 100%;
  }
  .dash-wrap.active { display: flex; }

  @media (min-width: 900px) {
    .dash-wrap.active {
      display: grid;
      grid-template-columns: 330px 1fr;
      gap: 22px;
      align-items: start;
    }
  }

  .dash-left-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .summary-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px 18px;
    box-shadow: var(--shadow-card);
  }
  .sum-row {
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding: 11px 10px;
    margin: 0 -10px;
    border-radius: 12px;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
    transition: background 0.14s ease;
  }
  .sum-row:last-child { border-bottom: none; }
  .sum-row:hover { background: var(--bg); }
  .sum-row.selected-mod {
    background: var(--subtle);
  }
  .sum-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
  .sum-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--ink);
  }
  .sum-nums {
    font-size: 11.5px;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .tri-bar {
    height: 6px;
    background: var(--subtle-2);
    border-radius: 999px;
    overflow: hidden;
    display: flex;
  }
  .tri-seg-done { background: var(--green); height: 100%; }
  .tri-seg-wip { background: #D9A441; height: 100%; }
  .tri-seg-todo { background: var(--red); height: 100%; }

  /* Dedicated Kana Adverbs Top 36 Entry Card */
  .kana36-entry {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 16px 18px;
    cursor: pointer;
    transition: all 0.15s ease;
    box-shadow: var(--shadow-card);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .kana36-entry:hover { border-color: var(--line-strong); }
  .kana36-entry.selected-mod {
    border-color: var(--ink);
    background: #FFFFFF;
  }
  .kana36-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    margin-bottom: 3px;
  }
  .kana36-sub {
    font-size: 12px;
    color: var(--ink-2);
  }
  .kana36-pill {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--green);
    background: var(--green-bg);
    padding: 4px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }

  .detail-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px 18px;
    box-shadow: var(--shadow-card);
  }
  @media (min-width: 900px) {
    .detail-card { padding: 22px 24px; }
    .mobile-only-mod-tabs { display: none !important; }
  }

  .mod-tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .mod-tabs::-webkit-scrollbar { display: none; }
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
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
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
    padding: 7px 4px;
    border-radius: 9px;
    cursor: pointer;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
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
    border-radius: 12px;
    padding: 9px 13px;
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
    max-height: 480px;
    overflow-y: auto;
  }
  @media (min-width: 900px) {
    .point-list { max-height: 620px; }
  }
  .pt-item {
    padding: 12px 6px;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
    transition: background 0.12s ease;
    border-radius: 8px;
  }
  .pt-item:hover { background: rgba(240, 238, 232, 0.45); }
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
  .pt-right {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 56%;
  }
  .pt-sub {
    font-size: 12.5px;
    color: var(--ink-2);
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pt-jump-btn {
    border: 1px solid var(--green-border);
    background: var(--green-bg);
    color: var(--green);
    font-family: var(--sans);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 999px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .pt-note {
    margin-top: 7px;
    padding-left: 15px;
    font-size: 12px;
    color: var(--ink-3);
    line-height: 1.55;
  }

  /* Kana Adverbs 36 Paired Cards */
  .kana36-banner {
    background: var(--bg);
    border-radius: 14px;
    padding: 12px 14px;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--ink-2);
    margin-bottom: 14px;
  }
  .kana-fam-block {
    margin-bottom: 18px;
  }
  .kana-fam-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    padding: 0 2px;
  }
  .kana-fam-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--ink);
  }
  .kana-fam-tag {
    font-size: 11px;
    color: var(--ink-3);
  }
  .kana-pair-card {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 12px 13px;
    margin-bottom: 8px;
  }
  .kana-pair-scene {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--green);
    margin-bottom: 8px;
  }
  .kana-twins {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  @media (max-width: 400px) {
    .kana-twins { grid-template-columns: 1fr; }
  }
  .kana-twin-item {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 11px;
    padding: 9px 11px;
  }
  .kt-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 3px;
  }
  .kt-word {
    font-family: var(--jp);
    font-size: 15px;
    font-weight: 600;
    color: var(--ink);
  }
  .kt-pitch {
    font-size: 11px;
    color: var(--ink-3);
    margin-left: 4px;
  }
  .kt-audio-btn {
    border: none;
    background: var(--subtle);
    color: var(--ink);
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 999px;
    cursor: pointer;
  }
  .kt-zh {
    font-size: 12.5px;
    color: var(--ink);
    margin-bottom: 2px;
  }
  .kt-colloc {
    font-family: var(--jp);
    font-size: 11.5px;
    color: var(--ink-3);
  }

  /* Modal Dialog */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(28, 25, 23, 0.34);
    z-index: 1000;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 18px;
  }
  .modal-overlay.open { display: flex; }
  .modal-box {
    width: 100%;
    max-width: 420px;
    background: var(--card);
    border-radius: 24px;
    padding: 22px 22px 20px;
    box-shadow: 0 24px 60px rgba(0,0,0,0.18);
    animation: popIn 0.16s ease;
  }
  .modal-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 8px;
  }
  .modal-p {
    font-size: 13px;
    line-height: 1.6;
    color: var(--ink-2);
    margin: 0 0 14px;
  }
  .modal-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .sync-textarea {
    width: 100%;
    height: 68px;
    border: 1px solid var(--line-strong);
    border-radius: 12px;
    background: var(--bg);
    padding: 8px 10px;
    font-family: monospace;
    font-size: 11.5px;
    color: var(--ink);
    margin-bottom: 10px;
    resize: none;
  }

  .done-wrap {
    text-align: center;
    padding: 22px 8px;
  }
  .done-title { font-size: 22px; font-weight: 600; margin: 0 0 8px; }
  .done-sub { font-size: 14px; color: var(--ink-2); margin: 0 0 22px; line-height: 1.6; }
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
    <div class="brand-left">
      <h1 class="visually-hidden">JLPT N3 语音私教与掌握度全景</h1>
      <span class="countdown" id="countdown-txt">距考试 22 天</span>
      <span class="exam-date-sub">12月6日 JLPT N3</span>
    </div>
    <div class="header-right">
      <button class="install-pill" id="pwa-install-btn" onclick="triggerPwaInstall()">📲 安装到桌面</button>
      <div class="mode-switch" role="tablist">
        <button class="mode-btn active" id="tab-tutor" onclick="switchMode('tutor')">语音私教</button>
        <button class="mode-btn" id="tab-dash" onclick="switchMode('dash')">掌握度</button>
      </div>
    </div>
  </header>

  <!-- VIEW 1: PRIMARY CONVERSATIONAL VOICE TUTOR -->
  <main class="tutor-wrap" id="tutor-view">
    <div class="session-bar">
      <button class="counter-btn" id="card-counter" onclick="openSessionModal()" title="查看本轮进度或重置">1 / 25</button>
      <div class="session-controls">
        <button class="pill-ctrl" id="walk-btn" onclick="toggleWalkMode()">🚶 走路听</button>
        <button class="pill-ctrl" id="top-speed-btn" onclick="cycleExpSpeed()">讲解 1.3x</button>
      </div>
    </div>
    <div class="progress-rail">
      <div class="progress-fill" id="prog-fill" style="width: 0%"></div>
    </div>

    <div class="voice-card" id="voice-card"></div>

    <footer class="studio-footer">
      <span class="desktop-hotkeys">快捷键：Space 播放 · 1/2/3 作答 · Enter 下一题 · ← 上一题 · R 还要考 · S 倍速 · W 走路听 · D 掌握度</span>
      <button class="footer-link" id="sync-guide-btn" onclick="openSyncModal()">手机安装与双端同步</button>
    </footer>
  </main>

  <!-- VIEW 2: SECONDARY MASTERY DASHBOARD (2-Column Split on Desktop, Clean Stack on Mobile) -->
  <section class="dash-wrap" id="dash-view">
    <div class="dash-left-col">
      <div class="summary-card" id="dash-summary"></div>
      <div class="kana36-entry" id="kana36-entry" onclick="selectDashMod('kana36')">
        <div>
          <div class="kana36-title">纯假名副词 Top 36</div>
          <div class="kana36-sub">真题 3–5 题封顶 · 6 组成对画面</div>
        </div>
        <span class="kana36-pill">专项攻克 →</span>
      </div>
    </div>

    <div class="detail-card" id="dash-detail-card">
      <div class="mod-tabs mobile-only-mod-tabs" id="mod-tabs"></div>
      <div id="dash-filter-zone">
        <div class="tier-tabs" id="tier-tabs"></div>
        <input type="search" class="search-input" id="pt-search" placeholder="搜索语法、假名或词义…（按 / 快速搜索）" oninput="renderMasteryList()" />
      </div>
      <div class="point-list" id="point-list"></div>
    </div>
  </section>
</div>

<!-- Backdrop + Word Dictionary Popover (Mobile Bottom Sheet / Desktop Hover Card) -->
<div class="sheet-backdrop" id="sheet-backdrop" onclick="hideWordPopover()"></div>
<div class="word-popover" id="word-popover"></div>

<!-- Lightweight Session / Install & Sync Modal -->
<div class="modal-overlay" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-box" id="modal-content"></div>
</div>

<script>
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").then(r => r.update()).catch(() => {});
}

const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.2, 1.3, 1.5, 1.8];
const SESSION_KEY = "n3_session_v5_" + DATA.plan_date;

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.3");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.3;

function computeDaysLeft() {
  try {
    const now = new Date();
    const exam = new Date("2026-12-06T09:00:00-08:00");
    const diff = Math.ceil((exam.getTime() - now.getTime()) / 86400000);
    return diff >= 0 ? diff : 0;
  } catch (e) {
    return DATA.days_to_exam;
  }
}

function loadSavedSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return { doneIds: [], requeuedIds: [], masteryOverrides: {} };
}

let sessionState = loadSavedSession();

function applyMasteryOverrides(overrides) {
  if (!overrides) return;
  Object.keys(DATA.mastery).forEach(mod => {
    DATA.mastery[mod].items.forEach(it => {
      const ov = overrides[it.key] || overrides[it.name];
      if (ov) it.tier = ov;
    });
  });
}
applyMasteryOverrides(sessionState.masteryOverrides);

function buildInitialQueue() {
  const doneSet = new Set(sessionState.doneIds || []);
  const remaining = DATA.cards.filter(c => !doneSet.has(c.id));
  return remaining.length > 0 ? remaining : DATA.cards.slice();
}

let queue = buildInitialQueue();
let idx = 0;
let stage = "quiz";
let usedTeachOnCurrent = false;
let spacedScheduledOnCurrent = false;
let currentChoices = [];
let pickedVal = null;
let walkMode = false;
let walkTimer = null;
let thinkingCountdown = 0;
let activeKind = null;
let activeMode = "tutor";
let pairPlayToken = 0;
let wakeLockSentinel = null;

function prepareChoicesForCard(q) {
  if (!q) return [];
  const arr = q.choices.slice();
  if (!q.is_listening && arr.length === 2) {
    let h = 0;
    for (let i = 0; i < q.id.length; i++) h = (h * 31 + q.id.charCodeAt(i)) >>> 0;
    const flip = (h + (q._spaced ? 1 : 0)) % 2 === 1;
    if (flip) arr.reverse();
  }
  return arr;
}

function syncCurrentCardSetup() {
  const cur = queue[idx];
  spacedScheduledOnCurrent = false;
  if (!cur) {
    currentChoices = [];
    usedTeachOnCurrent = false;
    return;
  }
  stage = cur.needs_teach ? "teach" : "quiz";
  usedTeachOnCurrent = (stage === "teach");
  currentChoices = prepareChoicesForCard(cur);
}
syncCurrentCardSetup();

let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

let deferredInstallPrompt = null;
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const btn = document.getElementById("pwa-install-btn");
  if (btn) btn.classList.add("visible");
});

function triggerPwaInstall() {
  if (!deferredInstallPrompt) {
    openSyncModal();
    return;
  }
  deferredInstallPrompt.prompt();
  deferredInstallPrompt.userChoice.finally(() => {
    deferredInstallPrompt = null;
    const btn = document.getElementById("pwa-install-btn");
    if (btn) btn.classList.remove("visible");
  });
}

const player = new Audio();
player.preload = "auto";
const wordPlayer = new Audio();
wordPlayer.preload = "auto";

const DICT_KEYS = Object.keys(DATA.words).sort((a, b) => b.length - a.length);

function vibrate(pattern) {
  try {
    if (navigator.vibrate) navigator.vibrate(pattern);
  } catch (e) {}
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function annotateJapanese(text) {
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

function renderSceneSVG(sceneType) {
  switch (sceneType) {
    case "flame_pair":
      return `<svg viewBox="0 0 320 56" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M55 46h30M70 46V32" stroke="#57534E"/>
        <path d="M70 12c6 8 6 16 0 18-6-2-6-10 0-18z" stroke="#246E53" fill="#ECF7F2"/>
        <path d="M26 20h18M22 26h22" stroke="#8C857B" stroke-dasharray="3 3"/>
        <text x="96" y="30" font-size="11" fill="#246E53" stroke="none" font-weight="600">自然熄灭 (が)</text>
        <line x1="164" y1="8" x2="164" y2="48" stroke="rgba(28,25,23,0.12)"/>
        <path d="M225 46h30M240 46V32" stroke="#57534E"/>
        <path d="M196 18l24 6M196 28l24-2" stroke="#BF3E35"/>
        <circle cx="240" cy="24" r="4" stroke="#8C857B" stroke-dasharray="2 2"/>
        <text x="260" y="30" font-size="11" fill="#57534E" stroke="none" font-weight="500">人为吹灭 (を)</text>
      </svg>`;
    case "posture_pair":
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="54" cy="22" r="5.5" stroke="#246E53" fill="#ECF7F2"/>
        <path d="M54 28l-10 9 11 5-6 8" stroke="#246E53"/>
        <circle cx="88" cy="24" r="4.5" stroke="#57534E"/>
        <path d="M88 29v15M64 23h16" stroke="#246E53" stroke-dasharray="2.5 2.5"/>
        <text x="102" y="30" font-size="11" fill="#246E53" font-weight="600">屈膝平视＝しゃがむ</text>
        <line x1="186" y1="8" x2="186" y2="48" stroke="rgba(28,25,23,0.12)"/>
        <circle cx="218" cy="20" r="6" stroke="#57534E"/>
        <path d="M218 26v20M232 14c4 4 4 10 0 14" stroke="#8C857B"/>
        <text x="244" y="30" font-size="11" fill="#57534E" font-weight="500">点头＝うなずく</text>
      </svg>`;
    case "seats_pair":
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="1.7" stroke-linecap="round">
        <rect x="20" y="18" width="18" height="18" rx="4" stroke="#246E53" fill="#ECF7F2"/>
        <rect x="44" y="18" width="18" height="18" rx="4" stroke="#246E53" fill="#ECF7F2"/>
        <rect x="68" y="18" width="18" height="18" rx="4" stroke="#246E53" fill="#ECF7F2"/>
        <rect x="92" y="18" width="18" height="18" rx="4" stroke="#246E53" fill="#ECF7F2"/>
        <text x="20" y="49" font-size="10.5" fill="#246E53" font-weight="600">空席没人＝がらがら</text>
        <line x1="158" y1="8" x2="158" y2="48" stroke="rgba(28,25,23,0.12)"/>
        <circle cx="190" cy="18" r="4" fill="#8C857B"/>
        <circle cx="226" cy="33" r="4" fill="#8C857B"/>
        <circle cx="252" cy="15" r="4" fill="#8C857B"/>
        <circle cx="278" cy="30" r="4" fill="#8C857B"/>
        <text x="186" y="49" font-size="10.5" fill="#57534E">零散不齐＝ばらばら</text>
      </svg>`;
    case "rhythm_beats":
      return `<svg viewBox="0 0 320 56" fill="none">
        <rect x="24" y="14" width="34" height="28" rx="8" fill="#ECF7F2" stroke="#246E53" stroke-width="1.6"/>
        <text x="41" y="33" text-anchor="middle" font-size="13" font-weight="600" fill="#246E53">な</text>
        <rect x="64" y="14" width="34" height="28" rx="8" fill="#ECF7F2" stroke="#246E53" stroke-width="1.6"/>
        <text x="81" y="33" text-anchor="middle" font-size="13" font-weight="600" fill="#246E53">い</text>
        <rect x="104" y="14" width="42" height="28" rx="8" fill="#246E53"/>
        <text x="125" y="33" text-anchor="middle" font-size="13" font-weight="600" fill="#FFFFFF">しょ!</text>
        <rect x="172" y="14" width="40" height="28" rx="8" fill="#FDF2F1" stroke="#BF3E35" stroke-dasharray="3 2"/>
        <text x="192" y="33" text-anchor="middle" font-size="13" font-weight="600" fill="#BF3E35">×う</text>
        <text x="224" y="32" font-size="11" fill="#57534E">尾音短促收住</text>
      </svg>`;
    case "elevation":
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="1.8" stroke-linecap="round">
        <circle cx="72" cy="16" r="10" fill="#ECF7F2" stroke="#246E53"/>
        <path d="M44 34l14-14M44 20h14v14" stroke="#246E53"/>
        <text x="90" y="20" font-size="11.5" fill="#246E53" font-weight="600">先生：召し上がる ↑</text>
        <line x1="182" y1="8" x2="182" y2="48" stroke="rgba(28,25,23,0.12)"/>
        <circle cx="216" cy="38" r="9" fill="#F0EEE8" stroke="#57534E"/>
        <text x="232" y="42" font-size="11.5" fill="#57534E">私：いただく ↓</text>
      </svg>`;
    case "timeline":
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="1.8">
        <line x1="36" y1="26" x2="284" y2="26" stroke="rgba(28,25,23,0.18)"/>
        <circle cx="56" cy="26" r="6" fill="#FFFFFF" stroke="#8C857B"/>
        <text x="56" y="46" text-anchor="middle" font-size="10.5" fill="#8C857B">食べるところ</text>
        <circle cx="160" cy="26" r="6" fill="#FFFFFF" stroke="#8C857B"/>
        <text x="160" y="46" text-anchor="middle" font-size="10.5" fill="#8C857B">食べているところ</text>
        <circle cx="264" cy="26" r="8" fill="#246E53"/>
        <text x="264" y="46" text-anchor="middle" font-size="11" font-weight="600" fill="#246E53">★食べたところ</text>
      </svg>`;
    case "slope_pair":
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="2" stroke-linecap="round">
        <path d="M26 42 Q80 38 134 12" stroke="#246E53"/>
        <path d="M125 11h10v10" stroke="#246E53"/>
        <text x="26" y="22" font-size="11" fill="#246E53" font-weight="600">同步渐变 ↗ にしたがって</text>
        <line x1="168" y1="8" x2="168" y2="48" stroke="rgba(28,25,23,0.12)" stroke-width="1.5"/>
        <path d="M188 30h96M236 30c6-14 22-14 28 0" stroke="#8C857B" stroke-width="1.7"/>
        <text x="190" y="48" font-size="10.5" fill="#57534E">人顺手做B＝ついでに</text>
      </svg>`;
    default:
      return `<svg viewBox="0 0 320 56" fill="none" stroke-width="1.7" stroke-linecap="round">
        <rect x="24" y="13" width="116" height="30" rx="9" fill="#ECF7F2" stroke="#246E53"/>
        <text x="82" y="32" text-anchor="middle" font-size="11.5" font-weight="600" fill="#246E53">核心锁定项 ✓</text>
        <path d="M150 28h20" stroke="#8C857B" stroke-dasharray="3 3"/>
        <rect x="180" y="13" width="116" height="30" rx="9" fill="#F0EEE8" stroke="rgba(28,25,23,0.18)"/>
        <text x="238" y="32" text-anchor="middle" font-size="11.5" fill="#57534E">易混干扰项 ↔</text>
      </svg>`;
  }
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
  const rate = (kind === "exp" || kind === "done") ? expSpeed : 1.02;
  player.defaultPlaybackRate = rate;
  player.playbackRate = rate;
  if ("preservesPitch" in player) player.preservesPitch = true;
  if ("webkitPreservesPitch" in player) player.webkitPreservesPitch = true;
}

function setExpSpeed(s) {
  expSpeed = s;
  try { localStorage.setItem("n3_exp_speed", String(s)); } catch (e) {}
  const topBtn = document.getElementById("top-speed-btn");
  if (topBtn) topBtn.textContent = `讲解 ${s.toFixed(1)}x`;
  if (activeKind === "exp") applyPlaybackRate("exp");
  document.querySelectorAll(".spd-btn").forEach(b => {
    b.classList.toggle("active", parseFloat(b.dataset.spd) === s);
  });
  syncOrbState();
}

function cycleExpSpeed() {
  const next = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  setExpSpeed(next);
}

function clearWalkTimer() {
  if (walkTimer) {
    clearInterval(walkTimer);
    clearTimeout(walkTimer);
    walkTimer = null;
  }
  thinkingCountdown = 0;
}

function stopAudio() {
  pairPlayToken += 1;
  clearWalkTimer();
  try {
    player.pause();
    player.currentTime = 0;
    wordPlayer.pause();
  } catch (e) {}
  activeKind = null;
  document.querySelectorAll(".pair-box").forEach(el => el.classList.remove("speaking-box"));
  syncOrbState();
}

function playMicroPairAudio(onComplete) {
  const q = queue[idx];
  if (!q || !q.micro || !q.micro.audio_urls || !q.micro.audio_urls.length) {
    if (onComplete) onComplete();
    return;
  }
  stopAudio();
  const token = ++pairPlayToken;
  activeKind = "pair";
  syncOrbState();
  const urls = q.micro.audio_urls;

  function step(k) {
    if (token !== pairPlayToken) return;
    document.querySelectorAll(".pair-box").forEach(el => el.classList.remove("speaking-box"));
    if (k >= urls.length) {
      activeKind = null;
      syncOrbState();
      if (onComplete) onComplete();
      return;
    }
    const boxEl = document.getElementById(k === 0 ? "pair-box-0" : "pair-box-1");
    if (boxEl) boxEl.classList.add("speaking-box");
    wordPlayer.src = urls[k];
    wordPlayer.currentTime = 0;
    wordPlayer.playbackRate = 1.0;
    wordPlayer.onended = () => {
      setTimeout(() => step(k + 1), 380);
    };
    wordPlayer.onerror = () => step(k + 1);
    const p = wordPlayer.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => {
        activeKind = null;
        document.querySelectorAll(".pair-box").forEach(el => el.classList.remove("speaking-box"));
        syncOrbState();
        if (onComplete) onComplete();
      });
    }
  }
  step(0);
}

function playSinglePairSide(sideIdx) {
  const q = queue[idx];
  if (!q || !q.micro || !q.micro.audio_words) return;
  const w = q.micro.audio_words[sideIdx];
  if (!w) return;
  const info = DATA.words[w];
  const url = (info && info.audio) || (q.micro.audio_urls && q.micro.audio_urls[sideIdx]);
  if (!url) return;
  stopAudio();
  const boxEl = document.getElementById(sideIdx === 0 ? "pair-box-0" : "pair-box-1");
  if (boxEl) boxEl.classList.add("speaking-box");
  wordPlayer.src = url;
  wordPlayer.currentTime = 0;
  wordPlayer.playbackRate = 1.0;
  wordPlayer.onended = () => { if (boxEl) boxEl.classList.remove("speaking-box"); };
  wordPlayer.play().catch(() => {});
}

function updateMediaSession() {
  if (!("mediaSession" in navigator) || idx >= queue.length) return;
  const q = queue[idx];
  const msTitle = (stage === "quiz")
    ? `${q.subject} · 第 ${idx + 1} 题`
    : `${q.subject} · ${q.point}`;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: msTitle,
      artist: walkMode ? getWalkProgramLabel() : "JLPT N3 语音私教",
      album: `距考试 ${computeDaysLeft()} 天`,
      artwork: [{ src: "./icon-192.png", sizes: "192x192", type: "image/png" }]
    });
    navigator.mediaSession.setActionHandler("play", () => {
      const cur = queue[idx];
      if (!cur) return;
      playMainClip(stage === "answered" ? cur.exp_audio : cur.q_audio, stage === "answered" ? "exp" : "q", false);
    });
    navigator.mediaSession.setActionHandler("pause", () => stopAudio());
    navigator.mediaSession.setActionHandler("nexttrack", () => nextCard(false));
    navigator.mediaSession.setActionHandler("previoustrack", () => prevCard());
  } catch (e) {}
}

function playMainClip(url, kind, toggleIfSame) {
  if (!url) return;
  pairPlayToken += 1;
  clearWalkTimer();
  if (toggleIfSame && activeKind === kind && !player.paused) {
    stopAudio();
    return;
  }
  activeKind = kind;
  player.src = url;
  player.currentTime = 0;
  applyPlaybackRate(kind);
  updateMediaSession();
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

  if (!walkMode || activeMode !== "tutor" || idx >= queue.length) return;
  if (finishedKind === "q" && stage !== "answered") {
    thinkingCountdown = 4;
    syncOrbState();
    walkTimer = setInterval(() => {
      thinkingCountdown -= 1;
      syncOrbState();
      if (thinkingCountdown <= 0) {
        clearWalkTimer();
        if (walkMode && stage !== "answered") {
          choose("__walk__", true);
        }
      }
    }, 900);
  } else if (finishedKind === "exp" && stage === "answered") {
    walkTimer = setTimeout(() => {
      if (walkMode && stage === "answered") nextCard(false);
    }, 950);
  }
});

function syncOrbState() {
  const orb = document.getElementById("voice-orb");
  const cap = document.getElementById("orb-caption");
  if (orb && cap) {
    const speaking = (activeKind === "q" || activeKind === "exp") && !player.paused;
    orb.classList.toggle("speaking", !!speaking);
    orb.classList.toggle("thinking", thinkingCountdown > 0);
    if (thinkingCountdown > 0) {
      cap.textContent = `脑内回想一下答案… ${thinkingCountdown}s`;
    } else if (speaking && activeKind === "q") {
      cap.textContent = "私教提问中 · 点圆球暂停";
    } else if (speaking && activeKind === "exp") {
      cap.textContent = `私教讲解中（${expSpeed.toFixed(1)}x）· 点圆球暂停`;
    } else {
      cap.textContent = stage === "answered" ? "点圆球重听题目" : "点圆球听私教提问";
    }
  }
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    const expOn = activeKind === "exp" && !player.paused;
    repBtn.classList.toggle("playing", expOn);
    repBtn.innerHTML = `${expOn ? "⏸ 讲解中" : "▶ 重听讲解"} <span class="kbd-hint">Space</span>`;
  }
  const pairBtn = document.getElementById("pair-audio-btn");
  if (pairBtn) {
    const pOn = activeKind === "pair";
    pairBtn.classList.toggle("speaking", pOn);
    pairBtn.textContent = pOn ? "🔊 播报对比中…" : "🔊 听成对发音";
  }
}

// ================= ZERO-PROMPT LIVE TIME-OF-DAY WALK RADIO =================
function getCurrentWalkSlot() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return "morning";
  if (h >= 11 && h < 17) return "midday";
  return "evening";
}

function getWalkProgramLabel() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return "晨间唤醒电台 · 错题声画＋核心语法";
  if (h >= 11 && h < 17) return "午间散步电台 · 假名副词＋口语快反";
  if (h >= 17 && h < 21) return "傍晚通勤电台 · 真题双人聴解＋活用";
  return "夜间轻复盘电台 · 1.3x 原句沉浸";
}

async function requestWakeLock(enable) {
  try {
    if (enable && "wakeLock" in navigator && !wakeLockSentinel) {
      wakeLockSentinel = await navigator.wakeLock.request("screen");
    } else if (!enable && wakeLockSentinel) {
      await wakeLockSentinel.release();
      wakeLockSentinel = null;
    }
  } catch (e) {}
}

function startWalkCurrentCard() {
  if (!walkMode || idx >= queue.length) return;
  const q = queue[idx];
  if (stage === "teach" && q.micro && q.micro.audio_urls && q.micro.audio_urls.length) {
    playMicroPairAudio(() => {
      if (!walkMode) return;
      stage = "quiz";
      renderTutor();
      setTimeout(() => {
        if (walkMode && idx < queue.length) playMainClip(queue[idx].q_audio, "q", false);
      }, 350);
    });
  } else if (stage !== "answered") {
    stage = "quiz";
    renderTutor();
    playMainClip(q.q_audio, "q", false);
  } else {
    playMainClip(q.exp_audio, "exp", false);
  }
}

function toggleWalkMode(forceState) {
  walkMode = typeof forceState === "boolean" ? forceState : !walkMode;
  const btn = document.getElementById("walk-btn");
  if (btn) {
    btn.textContent = walkMode ? "🚶 走路听 开" : "🚶 走路听";
    btn.classList.toggle("active", walkMode);
  }
  requestWakeLock(walkMode);

  if (walkMode) {
    const targetSlot = getCurrentWalkSlot();
    const head = queue.slice(0, idx);
    const tail = queue.slice(idx);
    tail.sort((a, b) => {
      const aHit = a.walk_slot === targetSlot ? 0 : 1;
      const bHit = b.walk_slot === targetSlot ? 0 : 1;
      return aHit - bHit;
    });
    queue = head.concat(tail);
    syncCurrentCardSetup();
    renderTutor();
    startWalkCurrentCard();
  } else {
    stopAudio();
    renderTutor();
  }
}

// Optional Voice Input (SpeechRecognition)
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
    if (!q || stage === "answered") return;
    if (/不知道|パス|わからない/.test(said)) {
      choose("不知道", false);
      return;
    }
    const choices = currentChoices.length ? currentChoices : q.choices;
    const cleanSaid = said.replace(/[。、！？\s]/g, "");
    const hit = choices.find(c => {
      const cc = c.replace(/（.*）|[。、\s]/g, "");
      return cleanSaid.includes(cc) || cc.includes(cleanSaid);
    });
    if (hit) choose(hit, false);
    else if (/1|一|いち/.test(cleanSaid) && choices[0]) choose(choices[0], false);
    else if (/2|二|に/.test(cleanSaid) && choices[1]) choose(choices[1], false);
    else if (/3|三|さん/.test(cleanSaid) && choices[2]) choose(choices[2], false);
    else choose("不知道", false);
  };
  recog.onend = () => {
    micActive = false;
    const b = document.getElementById("mic-btn");
    if (b) {
      b.classList.remove("listening-mic");
      b.innerHTML = `🎙 开口答 <span class="kbd-hint">M</span>`;
    }
  };
  recog.onerror = () => { micActive = false; };
  recog.start();
}

function persistSessionLocal() {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionState));
  } catch (e) {}
}

function saveRecord(q, choice, result, askAgain, consolidationOnly) {
  const rec = {
    id: q.id,
    point: q.point_key || q.point,
    choice: String(choice || ""),
    correct: String(!!result),
    ask_again: String(!!askAgain),
    ts: new Date().toISOString()
  };

  try {
    const hist = JSON.parse(localStorage.getItem("n3_tutor_log") || "[]");
    hist.push(rec);
    localStorage.setItem("n3_tutor_log", JSON.stringify(hist.slice(-500)));
  } catch (e) {}

  const newTier = (!result || askAgain) ? "todo" : (consolidationOnly ? "wip" : "done");
  sessionState.masteryOverrides[q.point_key] = newTier;
  sessionState.masteryOverrides[q.point] = newTier;
  if (result && !askAgain && !consolidationOnly) {
    if (!sessionState.doneIds.includes(q.id)) sessionState.doneIds.push(q.id);
  } else if (!result || askAgain) {
    sessionState.doneIds = sessionState.doneIds.filter(id => id !== q.id);
  }
  persistSessionLocal();
  applyMasteryOverrides(sessionState.masteryOverrides);

  if (location.protocol.startsWith("http")) {
    fetch("./api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({}, rec, { session: sessionState }))
    }).catch(() => {
      const body = new URLSearchParams(Object.assign({ "form-name": "n3-answers" }, rec)).toString();
      fetch("/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body
      }).catch(() => {});
    });
  }
}

function finishMicroLesson() {
  stopAudio();
  stage = "quiz";
  renderTutor();
  if (idx < queue.length && queue[idx].q_audio) {
    playMainClip(queue[idx].q_audio, "q", false);
  }
}

function openMicroLessonPeek() {
  const q = queue[idx];
  if (!q || !q.micro) return;
  stopAudio();
  usedTeachOnCurrent = true;
  stage = "teach";
  renderTutor();
  playMicroPairAudio();
}

function choose(val, fromWalk) {
  if (stage === "answered") return;
  hideWordPopover();
  stage = "answered";
  pickedVal = val;
  const q = queue[idx];
  const isCorrect = fromWalk ? true : (val === q.answer);
  spacedScheduledOnCurrent = false;
  if (!fromWalk) {
    vibrate(isCorrect ? 10 : [14, 30, 14]);
    const needsSpacedVerify = isCorrect && usedTeachOnCurrent && !q._spaced;
    spacedScheduledOnCurrent = needsSpacedVerify;
    saveRecord(q, val, isCorrect, false, needsSpacedVerify);
    if (!isCorrect) {
      const copy = Object.assign({}, q, { needs_teach: false, _spaced: true, roi_tag: "错题复仇" });
      queue.push(copy);
    } else if (needsSpacedVerify) {
      const insertAt = Math.min(queue.length, idx + 6);
      const spacedCopy = Object.assign({}, q, { needs_teach: false, _spaced: true, roi_tag: "间隔盲测复检" });
      queue.splice(insertAt, 0, spacedCopy);
    }
  }
  renderTutor();
  playMainClip(q.exp_audio, "exp", false);
}

function prevCard() {
  if (idx <= 0) return;
  hideWordPopover();
  stopAudio();
  idx -= 1;
  pickedVal = null;
  syncCurrentCardSetup();
  renderTutor();
  if (walkMode) startWalkCurrentCard();
}

function nextCard(requeue) {
  hideWordPopover();
  stopAudio();
  const q = queue[idx];
  if (requeue && q) {
    vibrate(12);
    saveRecord(q, pickedVal, false, true, false);
    queue.push(Object.assign({}, q, { needs_teach: false, _spaced: true, roi_tag: "主动加练" }));
  }
  idx += 1;
  pickedVal = null;
  syncCurrentCardSetup();
  renderTutor();
  if (idx < queue.length) {
    if (walkMode) {
      startWalkCurrentCard();
    } else if (stage === "teach") {
      playMicroPairAudio();
    } else if (queue[idx].q_audio) {
      playMainClip(queue[idx].q_audio, "q", false);
    }
  }
}

function jumpToCardById(cardId) {
  const foundIdx = queue.findIndex(c => c.id === cardId);
  if (foundIdx >= 0) {
    idx = foundIdx;
  } else {
    const orig = DATA.cards.find(c => c.id === cardId);
    if (!orig) return;
    queue.splice(idx, 0, orig);
  }
  pickedVal = null;
  syncCurrentCardSetup();
  switchMode("tutor");
  renderTutor();
  if (stage === "teach") playMicroPairAudio();
  else playMainClip(queue[idx].q_audio, "q", false);
}

function resetDailySession() {
  stopAudio();
  sessionState.doneIds = [];
  persistSessionLocal();
  queue = DATA.cards.slice();
  idx = 0;
  pickedVal = null;
  syncCurrentCardSetup();
  closeModal();
  renderTutor();
}

function renderTutor() {
  document.getElementById("countdown-txt").textContent = `距考试 ${computeDaysLeft()} 天`;
  document.getElementById("top-speed-btn").textContent = `讲解 ${expSpeed.toFixed(1)}x`;

  const total = queue.length;
  const pct = Math.min(100, Math.round((idx / Math.max(1, total)) * 100));
  document.getElementById("card-counter").textContent = idx < total ? `${idx + 1} / ${total}` : "本组已完成";
  document.getElementById("prog-fill").style.width = `${pct}%`;

  const box = document.getElementById("voice-card");
  if (idx >= total) {
    box.innerHTML = `
      <div class="done-wrap">
        <h2 class="done-title">今天这一组全部过关了</h2>
        <p class="done-sub">重点盲区与复仇题都已记入掌握度账本，去休息吧。</p>
        <div class="nav-row" style="max-width:340px;margin:0 auto;">
          <button class="again-btn" onclick="switchMode('dash')">看掌握度</button>
          <button class="next-btn" onclick="resetDailySession()">再练一遍</button>
        </div>
      </div>
    `;
    playMainClip(DATA.done_audio, "done", false);
    return;
  }

  const q = queue[idx];
  warmAudio(q.q_audio);
  warmAudio(q.exp_audio);
  if (q.micro && q.micro.audio_urls) q.micro.audio_urls.forEach(warmAudio);
  if (idx + 1 < total) {
    warmAudio(queue[idx + 1].q_audio);
    warmAudio(queue[idx + 1].exp_audio);
  }

  const walkBannerHTML = walkMode ? `
    <div class="walk-banner">
      <span>🎧 ${escapeHtml(getWalkProgramLabel())}</span>
      <span style="font-size:11.5px;opacity:0.85;">免手点自动连播</span>
    </div>
  ` : "";

  const eyebrowLabel = (stage === "quiz")
    ? escapeHtml(q.subject)
    : `${escapeHtml(q.subject)} · ${escapeHtml(q.point)}`;

  const eyebrowHTML = `
    <div class="card-eyebrow">
      <span class="subj-tag"><span class="subj-dot"></span>${eyebrowLabel}</span>
      <span>${escapeHtml(q.roi_tag)}</span>
    </div>
  `;

  // -------- STAGE A: 15-SECOND VISUAL + STUDIO AUDIO MICRO-LESSON --------
  if (stage === "teach" && q.micro) {
    const m = q.micro;
    box.innerHTML = `
      ${walkBannerHTML}
      ${eyebrowHTML}
      <div class="teach-stage">
        <div class="teach-header">
          <span class="teach-badge">先讲后考 · 15秒声画微课</span>
          <button class="pair-audio-btn" id="pair-audio-btn" onclick="playMicroPairAudio()">🔊 听成对发音</button>
        </div>
        <div class="scene-art">${renderSceneSVG(m.scene)}</div>
        <div class="pair-grid">
          <div class="pair-box primary-anchor" id="pair-box-0" onclick="playSinglePairSide(0)">
            <div class="pair-ja"><span>${escapeHtml(m.left.ja || "")}</span><span class="pair-spk-ic">🔊</span></div>
            <div class="pair-sub">${escapeHtml(m.left.sub || "")}</div>
            <div class="pair-desc">${escapeHtml(m.left.desc || "")}</div>
          </div>
          <div class="pair-box contrast-anchor" id="pair-box-1" onclick="playSinglePairSide(1)">
            <div class="pair-ja"><span>${escapeHtml(m.right.ja || "")}</span><span class="pair-spk-ic">🔊</span></div>
            <div class="pair-sub">${escapeHtml(m.right.sub || "")}</div>
            <div class="pair-desc">${escapeHtml(m.right.desc || "")}</div>
          </div>
        </div>
        <div class="teach-hook">${escapeHtml(m.hook)}</div>
        <div class="nav-row">
          <button class="next-btn" onclick="finishMicroLesson()">记住了，考我 → <span class="kbd-hint">Enter</span></button>
        </div>
      </div>
    `;
    syncOrbState();
    return;
  }

  // -------- STAGE B & C: VOICE TUTOR QUESTION + ANSWER ZONE --------
  const isAns = stage === "answered";
  const choices = currentChoices.length ? currentChoices : q.choices;
  const gridCls = choices.length > 2 || choices.some(c => c.length > 9) ? "choices-grid stacked" : "choices-grid";
  const choicesHTML = choices.map((c, cIdx) => {
    let cls = "choice-btn";
    if (isAns) {
      if (c === q.answer) cls += " correct";
      else if (c === pickedVal) cls += " wrong";
    }
    const innerLabel = isAns ? `<span>${annotateJapanese(c)}</span>` : `<span>${escapeHtml(c)}</span>`;
    const kbdBadge = !isAns ? `<span class="kbd-hint">${cIdx + 1}</span>` : "";
    return `<button class="${cls}" ${isAns ? "disabled" : ""} onclick='choose(${JSON.stringify(c)}, false)'>${innerLabel}${kbdBadge}</button>`;
  }).join("");

  const microPeekBtn = q.micro
    ? `<button class="assist-btn" onclick="openMicroLessonPeek()">画面微课 <span class="kbd-hint">H</span></button>`
    : "";

  const assistHTML = (!isAns && !walkMode) ? `
    <div class="quick-assist-row">
      <button class="assist-btn" id="mic-btn" onclick="toggleVoiceAnswer()">🎙 开口答 <span class="kbd-hint">M</span></button>
      ${microPeekBtn}
      <button class="assist-btn" onclick='choose("不知道", false)'>直接听讲解 <span class="kbd-hint">0</span></button>
    </div>
  ` : "";

  const walkNavHTML = walkMode ? `
    <div class="walk-controls-row">
      <button class="walk-nav-btn" onclick="prevCard()">⏮ 上一条</button>
      <button class="walk-nav-btn primary" onclick="toggleWalkMode(false)">退出走路电台</button>
      <button class="walk-nav-btn" onclick="nextCard(false)">下一条 ⏭</button>
    </div>
  ` : "";

  const speedBtnsHTML = SPEEDS.map(s =>
    `<button class="spd-btn ${s === expSpeed ? "active" : ""}" data-spd="${s}" onclick="setExpSpeed(${s})">${s.toFixed(1)}x</button>`
  ).join("");

  let breakdownHTML = "";
  if (isAns) {
    const rows = choices.map(c => {
      const right = c === q.answer;
      const note = (q.option_notes && q.option_notes[c]) || (right ? q.explain : "干扰项（语义或接续不符）");
      return `
        <div class="opt-row ${right ? "is-ans" : "is-dist"}">
          <span class="opt-mark">${right ? "✓" : "✕"}</span>
          <div class="opt-body">
            <span class="opt-head-ja">${annotateJapanese(c)}</span>
            <span class="opt-note-zh">${escapeHtml(note)}</span>
          </div>
        </div>
      `;
    }).join("");
    breakdownHTML = `<div class="opt-breakdown">${rows}</div>`;
  }

  const spacedNoticeHTML = (isAns && spacedScheduledOnCurrent)
    ? `<div class="spaced-hint">✓ 初学答对 · 已排入 5 题后无提示盲测，确认真正记住</div>`
    : "";

  const answerZoneHTML = isAns ? `
    <div class="answer-zone" id="answer-zone">
      <div class="exp-controls">
        <button class="replay-exp-btn" id="exp-replay-btn" onclick="playMainClip(queue[idx].exp_audio, 'exp', true)">▶ 重听讲解 <span class="kbd-hint">Space</span></button>
        <div class="speed-group" title="讲解语速（快捷键 S）">
          ${speedBtnsHTML}
        </div>
      </div>
      <div class="full-sentence-box">
        <div class="full-sentence-hint">
          <span>完整原句</span>
          <span>点词听发音 · 悬停看原形与声调</span>
        </div>
        <div class="full-sentence-ja">${annotateJapanese(q.full_ja)}</div>
      </div>
      ${spacedNoticeHTML}
      ${breakdownHTML}
      ${!walkMode ? `
      <div class="nav-row">
        <button class="again-btn" onclick="nextCard(true)">还要考 <span class="kbd-hint">R</span></button>
        <button class="next-btn" onclick="nextCard(false)">下一题 → <span class="kbd-hint">Enter</span></button>
      </div>` : ""}
    </div>
  ` : "";

  box.innerHTML = `
    ${walkBannerHTML}
    ${eyebrowHTML}
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
    ${walkNavHTML}
  `;
  syncOrbState();
}

// ================= ANSWER-ZONE WORD POPOVER (Desktop Hover + Mobile Bottom Sheet!) =================
const popEl = document.getElementById("word-popover");
const backdropEl = document.getElementById("sheet-backdrop");
let activeTokEl = null;
let hoverHideTimer = null;

function isMobileSheetViewport() {
  return window.innerWidth < 768;
}

function playWordAudio(surface) {
  const info = DATA.words[surface];
  if (!info || !info.audio) return;
  if (!player.paused) player.pause();
  wordPlayer.src = info.audio;
  wordPlayer.currentTime = 0;
  wordPlayer.playbackRate = 1.0;
  wordPlayer.play().catch(() => {});
}

function playDirectUrl(url) {
  if (!url) return;
  if (!player.paused) player.pause();
  wordPlayer.src = url;
  wordPlayer.currentTime = 0;
  wordPlayer.playbackRate = 1.0;
  wordPlayer.play().catch(() => {});
}

function showWordPopover(surface, anchorEl, autoSpeak) {
  const info = DATA.words[surface];
  if (!info) return;
  clearTimeout(hoverHideTimer);
  if (activeTokEl) activeTokEl.classList.remove("active-tok");
  activeTokEl = anchorEl && anchorEl.classList ? anchorEl : null;
  if (activeTokEl) activeTokEl.classList.add("active-tok");

  const hasAudio = !!info.audio;
  popEl.innerHTML = `
    <div class="wp-top">
      <div>
        <span class="wp-head">${escapeHtml(surface)}</span>
        <span class="wp-kana">${escapeHtml(info.kana)}</span>
        <span class="wp-pitch">${escapeHtml(info.pitch || "")}</span>
      </div>
      ${hasAudio ? `<button class="wp-speak" onclick='playWordAudio(${JSON.stringify(surface)})'>🔊 发音</button>` : ""}
    </div>
    <div class="wp-pos">${escapeHtml(info.head && info.head !== surface ? "原形 " + info.head + " · " + info.pos : info.pos)}</div>
    <div class="wp-zh">${escapeHtml(info.zh)}</div>
    ${info.tip ? `<div class="wp-tip">${escapeHtml(info.tip)}</div>` : ""}
  `;
  popEl.classList.add("open");

  if (isMobileSheetViewport()) {
    backdropEl.classList.add("open");
  } else if (anchorEl && anchorEl.getBoundingClientRect) {
    const r = anchorEl.getBoundingClientRect();
    const pw = popEl.offsetWidth || 330;
    const ph = popEl.offsetHeight || 135;
    let left = r.left + r.width / 2 - pw / 2;
    left = Math.max(16, Math.min(window.innerWidth - pw - 16, left));
    let top = r.top - ph - 10;
    if (top < 14) top = r.bottom + 10;
    popEl.style.left = `${left}px`;
    popEl.style.top = `${top}px`;
  }
  if (autoSpeak && hasAudio) playWordAudio(surface);
}

function hideWordPopover() {
  popEl.classList.remove("open");
  backdropEl.classList.remove("open");
  if (activeTokEl) {
    activeTokEl.classList.remove("active-tok");
    activeTokEl = null;
  }
}

document.addEventListener("mouseover", e => {
  if (isMobileSheetViewport()) return;
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (!tok || stage !== "answered") return;
  showWordPopover(tok.dataset.w, tok, false);
});

document.addEventListener("mouseout", e => {
  if (isMobileSheetViewport()) return;
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (!tok) return;
  hoverHideTimer = setTimeout(() => {
    if (!popEl.matches(":hover")) hideWordPopover();
  }, 220);
});

popEl.addEventListener("mouseenter", () => clearTimeout(hoverHideTimer));
popEl.addEventListener("mouseleave", () => { if (!isMobileSheetViewport()) hideWordPopover(); });

document.addEventListener("click", e => {
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (tok && stage === "answered") {
    e.stopPropagation();
    vibrate(8);
    showWordPopover(tok.dataset.w, tok, true);
    return;
  }
  if (!isMobileSheetViewport() && !e.target.closest("#word-popover")) {
    hideWordPopover();
  }
});

document.addEventListener("mouseup", () => {
  if (stage !== "answered" || isMobileSheetViewport()) return;
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

// ================= DESKTOP FULL KEYBOARD STUDIO HOTKEYS =================
document.addEventListener("keydown", e => {
  const tag = (e.target && e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea") {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  if (document.getElementById("app-modal").classList.contains("open")) {
    if (e.key === "Escape") closeModal();
    return;
  }

  if (e.key === "Escape") {
    hideWordPopover();
    if (walkMode) toggleWalkMode(false);
    return;
  }
  if (e.key === "/" && activeMode === "dash" && dashMod !== "kana36") {
    e.preventDefault();
    const sEl = document.getElementById("pt-search");
    if (sEl) sEl.focus();
    return;
  }
  if (e.key.toLowerCase() === "d") {
    e.preventDefault();
    switchMode(activeMode === "tutor" ? "dash" : "tutor");
    return;
  }
  if (activeMode !== "tutor") return;

  if (e.key.toLowerCase() === "s") {
    e.preventDefault();
    cycleExpSpeed();
    return;
  }
  if (e.key.toLowerCase() === "w") {
    e.preventDefault();
    toggleWalkMode();
    return;
  }

  const q = queue[idx];
  if (!q) return;

  if (e.key === "ArrowLeft" && idx > 0) {
    e.preventDefault();
    prevCard();
    return;
  }

  if (stage === "teach") {
    if (e.key === " ") {
      e.preventDefault();
      playMicroPairAudio();
    } else if (e.key === "Enter" || e.key === "ArrowRight") {
      e.preventDefault();
      finishMicroLesson();
    }
    return;
  }

  if (stage === "quiz") {
    const choices = currentChoices.length ? currentChoices : q.choices;
    if (e.key === " ") {
      e.preventDefault();
      playMainClip(q.q_audio, "q", true);
    } else if (e.key === "1" && choices[0]) {
      e.preventDefault();
      choose(choices[0], false);
    } else if (e.key === "2" && choices[1]) {
      e.preventDefault();
      choose(choices[1], false);
    } else if (e.key === "3" && choices[2]) {
      e.preventDefault();
      choose(choices[2], false);
    } else if (e.key === "0") {
      e.preventDefault();
      choose("不知道", false);
    } else if (e.key.toLowerCase() === "h" && q.micro) {
      e.preventDefault();
      openMicroLessonPeek();
    } else if (e.key.toLowerCase() === "m") {
      e.preventDefault();
      toggleVoiceAnswer();
    }
    return;
  }

  if (stage === "answered") {
    if (e.key === " ") {
      e.preventDefault();
      playMainClip(q.exp_audio, "exp", true);
    } else if (e.key === "Enter" || e.key === "ArrowRight") {
      e.preventDefault();
      nextCard(false);
    } else if (e.key.toLowerCase() === "r") {
      e.preventDefault();
      nextCard(true);
    }
  }
});

// ================= SECONDARY VIEW: MASTERY DASHBOARD + KANA ADVERBS 36 =================
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
  const c = { todo: 0, wip: 0, done: 0, roi: 0, total: items.length };
  items.forEach(it => {
    c[it.tier] += 1;
    if (it.roi && it.tier !== "done") c.roi += 1;
  });
  DATA.mastery[modKey].counts = c;
  return c;
}

function selectDashMod(modKey) {
  dashMod = modKey;
  expandedPt = null;
  if (modKey !== "kana36") {
    const c = recalcCounts(modKey);
    if (dashTier !== "roi" && c[dashTier] === 0) {
      dashTier = c.todo > 0 ? "todo" : (c.wip > 0 ? "wip" : "done");
    }
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
      <div class="sum-row ${dashMod === k ? 'selected-mod' : ''}" onclick="selectDashMod('${k}')">
        <div class="sum-head">
          <span class="sum-title">${m.label}</span>
          <span class="sum-nums">过关 ${c.done} · 巩固 ${c.wip} · 待攻克 ${c.todo}</span>
        </div>
        <div class="tri-bar">
          <div class="tri-seg-done" style="width:${pDone}%"></div>
          <div class="tri-seg-wip" style="width:${pWip}%"></div>
          <div class="tri-seg-todo" style="width:${pTodo}%"></div>
        </div>
      </div>
    `;
  }).join("");

  document.getElementById("kana36-entry").classList.toggle("selected-mod", dashMod === "kana36");

  const mobileTabsHTML = order.map(k => {
    const m = DATA.mastery[k];
    return `<button class="mod-tab ${dashMod === k ? "active" : ""}" onclick="selectDashMod('${k}')">${m.label} ${m.counts.total}</button>`;
  }).join("") + `<button class="mod-tab ${dashMod === 'kana36' ? 'active' : ''}" onclick="selectDashMod('kana36')">假名副词 36</button>`;
  document.getElementById("mod-tabs").innerHTML = mobileTabsHTML;

  const filterZone = document.getElementById("dash-filter-zone");
  if (dashMod === "kana36") {
    filterZone.style.display = "none";
    renderKana36View();
    return;
  }

  filterZone.style.display = "block";
  const curCounts = DATA.mastery[dashMod].counts;
  document.getElementById("tier-tabs").innerHTML = `
    <button class="tier-tab ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待攻克 ${curCounts.todo}</button>
    <button class="tier-tab ${dashTier === 'roi' ? 'active' : ''}" onclick="selectDashTier('roi')">提分重点 ${curCounts.roi}</button>
    <button class="tier-tab ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固中 ${curCounts.wip}</button>
    <button class="tier-tab ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已过关 ${curCounts.done}</button>
  `;

  renderMasteryList();
}

function renderKana36View() {
  const listEl = document.getElementById("point-list");
  listEl.innerHTML = `
    <div class="kana36-banner">
      <strong>考情定心丸：</strong>JLPT N3 纯假名副词/拟态词在真题中固定只占 <strong>3–5 题（约 6 分）</strong>。无需盲背偏僻词，用「成对反义/画面」锁死以下 <strong>36 个核心词（6 组×3 对）</strong>即 100% 封顶。
    </div>
    ${DATA.kana36.map(fam => `
      <div class="kana-fam-block">
        <div class="kana-fam-head">
          <span class="kana-fam-title">${escapeHtml(fam.family)}</span>
          <span class="kana-fam-tag">${escapeHtml(fam.tag)}</span>
        </div>
        ${fam.pairs.map(pr => `
          <div class="kana-pair-card">
            <div class="kana-pair-scene">画面对比：${escapeHtml(pr.scene)}</div>
            <div class="kana-twins">
              ${[pr.a, pr.b].map(item => `
                <div class="kana-twin-item">
                  <div class="kt-top">
                    <div><span class="kt-word">${escapeHtml(item.w)}</span><span class="kt-pitch">${escapeHtml(item.pitch)}</span></div>
                    ${item.audio ? `<button class="kt-audio-btn" onclick='playDirectUrl(${JSON.stringify(item.audio)})'>🔊 发音</button>` : ""}
                  </div>
                  <div class="kt-zh">${escapeHtml(item.zh)}</div>
                  <div class="kt-colloc">${escapeHtml(item.colloc)}</div>
                </div>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </div>
    `).join("")}
  `;
}

function togglePtNote(i) {
  expandedPt = (expandedPt === i) ? null : i;
  renderMasteryList();
}

function renderMasteryList() {
  const q = (document.getElementById("pt-search").value || "").trim().toLowerCase();
  const items = DATA.mastery[dashMod].items.filter(it => {
    if (q) return it.name.toLowerCase().includes(q) || (it.sub || "").toLowerCase().includes(q) || (it.family || "").toLowerCase().includes(q);
    if (dashTier === "roi") return it.roi && it.tier !== "done";
    return it.tier === dashTier;
  });

  const listEl = document.getElementById("point-list");
  if (!items.length) {
    listEl.innerHTML = `<div style="padding:28px 4px;text-align:center;color:var(--ink-3);font-size:13px;">这一栏目前已经清空了</div>`;
    return;
  }

  listEl.innerHTML = items.map((it, i) => `
    <div class="pt-item" onclick="togglePtNote(${i})">
      <div class="pt-main">
        <div class="pt-left">
          <span class="dot ${it.tier}"></span>
          <span class="pt-name">${escapeHtml(it.name)}</span>
        </div>
        <div class="pt-right">
          <span class="pt-sub">${escapeHtml(it.sub)}</span>
          ${it.card_id ? `<button class="pt-jump-btn" onclick="event.stopPropagation();jumpToCardById('${it.card_id}')">练这题</button>` : ""}
        </div>
      </div>
      ${expandedPt === i && (it.note || it.family) ? `<div class="pt-note">${escapeHtml([it.family, it.note].filter(Boolean).join(" · "))}</div>` : ""}
    </div>
  `).join("");
}

// ================= MODALS: SESSION CONTROL + INSTALL & CROSS-DEVICE SYNC =================
function closeModal() {
  document.getElementById("app-modal").classList.remove("open");
}

function openSessionModal() {
  const doneCount = (sessionState.doneIds || []).length;
  const el = document.getElementById("modal-content");
  el.innerHTML = `
    <h3 class="modal-title">本组学习进度</h3>
    <p class="modal-p">当前已自动续接进度（已完成 <strong>${doneCount}</strong> / ${DATA.cards.length} 题）。排在最前面的是错题复仇与未测高分重点，并自动开启「15秒先讲后考声画微课」。</p>
    <div class="modal-actions">
      <button class="again-btn" onclick="resetDailySession()">从第 1 题重练本组</button>
      <button class="next-btn" onclick="closeModal()">继续当前进度</button>
    </div>
  `;
  document.getElementById("app-modal").classList.add("open");
}

function exportSyncCode() {
  const code = btoa(unescape(encodeURIComponent(JSON.stringify(sessionState))));
  const ta = document.getElementById("sync-code-box");
  if (ta) {
    ta.value = code;
    ta.select();
    navigator.clipboard && navigator.clipboard.writeText(code).catch(() => {});
  }
}

function importSyncCode() {
  const ta = document.getElementById("sync-code-box");
  if (!ta || !ta.value.trim()) return;
  try {
    const parsed = JSON.parse(decodeURIComponent(escape(atob(ta.value.trim()))));
    if (parsed && typeof parsed === "object") {
      sessionState = {
        doneIds: Array.from(new Set([...(sessionState.doneIds || []), ...(parsed.doneIds || [])])),
        requeuedIds: parsed.requeuedIds || [],
        masteryOverrides: Object.assign({}, sessionState.masteryOverrides, parsed.masteryOverrides || {})
      };
      persistSessionLocal();
      applyMasteryOverrides(sessionState.masteryOverrides);
      queue = buildInitialQueue();
      idx = 0;
      pickedVal = null;
      syncCurrentCardSetup();
      closeModal();
      renderTutor();
    }
  } catch (e) {
    alert("同步码格式有误，请重新复制粘贴。");
  }
}

function openSyncModal() {
  const el = document.getElementById("modal-content");
  el.innerHTML = `
    <h3 class="modal-title">公司 Android 手机免 APK 安装 & 双端同步</h3>
    <p class="modal-p">
      <strong>1. 手机变原生全屏 App（绕过公司禁装 APK 限制）：</strong><br/>
      用手机 Chrome 打开本页 → 点右上角 <strong>⋮</strong> → 点 <strong>「添加到主屏幕 / 安装应用」</strong>，桌面即生成独立全屏 <strong>N3</strong> 图标（长按图标可直接进「走路随身听」）。<br/><br/>
      <strong>2. 手机 ↔ 电脑进度无缝合并：</strong><br/>
      在线同源环境下自动后台同步；离线或跨浏览器时，可一键复制/粘贴下方进度同步码：
    </p>
    <textarea class="sync-textarea" id="sync-code-box" placeholder="点「复制本机同步码」生成，或粘贴另一端同步码后点「粘贴合并进度」…"></textarea>
    <div class="modal-actions">
      <button class="again-btn" onclick="exportSyncCode()">复制本机同步码</button>
      <button class="again-btn" onclick="importSyncCode()">粘贴合并进度</button>
      <button class="next-btn" onclick="closeModal()">完成</button>
    </div>
  `;
  document.getElementById("app-modal").classList.add("open");
}

function initApp() {
  const params = new URLSearchParams(location.search);
  const urlMode = params.get("mode");
  if (urlMode === "dash") {
    switchMode("dash");
  } else {
    renderTutor();
    if (urlMode === "walk") {
      toggleWalkMode(true);
    }
  }

  if (location.protocol.startsWith("http")) {
    fetch("./api/state").then(r => r.ok ? r.json() : null).then(data => {
      if (!data || !data.ok || !data.session) return;
      const srv = data.session;
      if (Array.isArray(srv.doneIds) && srv.doneIds.length > (sessionState.doneIds || []).length) {
        sessionState.doneIds = Array.from(new Set([...(sessionState.doneIds || []), ...srv.doneIds]));
        sessionState.masteryOverrides = Object.assign({}, srv.masteryOverrides || {}, sessionState.masteryOverrides);
        persistSessionLocal();
        applyMasteryOverrides(sessionState.masteryOverrides);
        if (idx === 0 && stage !== "answered") {
          queue = buildInitialQueue();
          syncCurrentCardSetup();
          if (activeMode === "tutor") renderTutor();
          else renderDashboard();
        }
      }
    }).catch(() => {});
  }
}

initApp();
</script>
</body>
</html>
"""

final_html = html.replace("__PAYLOAD__", payload)
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(final_html)
print("Wrote Perfected Mobile-First + Desktop-Studio N3 Tutor HTML:", HTML_PATH, "size:", len(final_html), "bytes")
