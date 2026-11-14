#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the JLPT N3 Neural Audio Tutor + Mastery Panorama PWA (index.html).
Ultra-simple 2-step flow ("只留最重要的字"), large high-contrast typography for Phone & Desktop,
locked 100dvh native-app viewport (zero annoying bounce/scroll on home screen), and instant auto-sync.
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
    return rich_words.get(w, {}).get("audio") or word_audio_map.get(w, "")


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


def clean_prompt(s: str, is_listening: bool) -> str:
    txt = re.sub(r"^🎧\s*", "", str(s or "")).strip()
    if is_listening and ("1·2·3" in txt or "最自然的一句" in txt):
        return "先点上方按钮听对话，再选最自然的回答"
    return txt


def clean_rule_text(s: str) -> str:
    txt = str(s or "").strip()
    txt = re.sub(
        r"^(?:听力保命铁律|声音\+画面双锚|双重铁证|考场秒杀铁律|考试卷面铁律|秒杀铁律|记忆铁律|一眼锁死助词|看动词时态定画面|这对双胞胎反着记)[：:]\s*",
        "",
        txt,
    )
    return txt


def build_card(q: dict, subject: str, fallback_point_label: str) -> dict:
    qid = q["id"]
    t_item = TUTOR_ITEMS.get(qid, {})
    meta = audio_manifest.get(f"meta:{qid}", {})
    is_listening = subject == "聴解"

    fallback_opts = [strip_opt_prefix(o) for o in q.get("options", []) if o != "不知道"]
    fallback_ans = strip_opt_prefix(q.get("answer", ""))

    choices = t_item.get("choices") or fallback_opts
    answer = t_item.get("answer") or fallback_ans
    raw_prompt = t_item.get("prompt_display") or re.sub(r"\s*\[[A-Z0-9-]+\]", "", str(q.get("stem", ""))).strip()
    prompt_display = clean_prompt(raw_prompt, is_listening)
    full_ja = t_item.get("full_ja") or raw_prompt
    explain = meta.get("spoken_text") or t_item.get("voice_exp") or q.get("hook_zh") or ""

    point_key = t_item.get("point_key") or fallback_point_label
    if point_key in l_state_map:
        display_point = l_state_map[point_key].get("name") or fallback_point_label
    elif point_key in h_state_map:
        display_point = h_state_map[point_key].get("name") or fallback_point_label
    else:
        display_point = fallback_point_label or point_key

    hist = latest_by_qid.get(qid)
    if hist is not None:
        priority_group = 0 if not hist["ok"] else 2
    else:
        priority_group = 1

    raw_micro = t_item.get("micro_lesson") or {}
    opt_notes = t_item.get("option_notes") or {}
    core_rule = clean_rule_text(raw_micro.get("hook") or opt_notes.get(answer) or explain)

    return {
        "id": qid,
        "subject": subject,
        "point": display_point,
        "point_key": point_key,
        "walk_slot": t_item.get("walk_slot", "morning"),
        "priority_group": priority_group,
        "prompt": prompt_display,
        "choices": choices,
        "answer": answer,
        "full_ja": full_ja,
        "core_rule": core_rule,
        "option_notes": opt_notes,
        "q_audio": meta.get("q_audio", ""),
        "exp_audio": meta.get("exp_audio", ""),
        "is_listening": is_listening,
    }


def has_studio_mp3(c: dict) -> bool:
    for rel in (c.get("q_audio", ""), c.get("exp_audio", "")):
        if not rel:
            return False
        abs_p = os.path.join(BASE_DIR, rel.lstrip("./"))
        if not (os.path.exists(abs_p) and os.path.getsize(abs_p) > 0):
            return False
    return True


g_list = [
    c for c in (
        build_card(q, "文法", q.get("point", ""))
        for q in plan.get("grammar", {}).get("formal", []) + plan.get("grammar", {}).get("quick", [])
    )
    if has_studio_mp3(c)
]
h_list = [
    c for c in (
        build_card(q, "活用", re.sub(r"^[A-Z]-\d+(?:/[A-Z]-\d+)?\s*", "", q.get("point", "")))
        for q in plan.get("henkei", {}).get("formal", []) + plan.get("henkei", {}).get("quick", [])
    )
    if has_studio_mp3(c)
]
v_list = [
    c for c in (
        build_card(q, "語彙", q.get("word", ""))
        for q in plan.get("vocab", {}).get("formal", []) + plan.get("vocab", {}).get("quick", [])
    )
    if has_studio_mp3(c)
]
l_list = [
    c for c in (
        build_card(q, "聴解", "口语听辨")
        for q in plan.get("listening", {}).get("formal", [])
    )
    if has_studio_mp3(c)
]

# Put written sentences before listening on card #1 so first-open shows a clear Japanese sentence immediately,
# and tapping option #1 unlocks browser audio so subsequent listening cards auto-play out loud!
cards = []
for p_tier in (0, 1, 2):
    tier_buckets = [
        [c for c in bucket if c["priority_group"] == p_tier]
        for bucket in (v_list, h_list, g_list, l_list)
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
        "card_id": card_by_point_key.get(pid, ""),
        "note": p.get("note", ""),
    })

vocab_items = []
for p in live_state.get("vocab_tracked", []):
    w = p.get("word", "")
    st = p.get("status", "red")
    base_stat = f"练过 {p.get('seen', 0)} 次 · 错 {p.get('wrong', 0)} 次"
    v_note = f"{p['classroom_note']}（{base_stat}）" if p.get("classroom_note") else base_stat
    vocab_items.append({
        "key": w,
        "name": w,
        "sub": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "family": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": norm_tier(st),
        "card_id": card_by_point_key.get(w, ""),
        "audio": resolve_word_audio(w),
        "note": v_note,
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
        "card_id": card_by_point_key.get(pid, ""),
        "note": p.get("trap", "") or p.get("note", ""),
    })


def count_tiers(items):
    c = {"todo": 0, "wip": 0, "done": 0}
    for it in items:
        c[it["tier"]] += 1
    c["total"] = len(items)
    return c


kana36_enriched = []
kana_word_total = 0
for fam in KANA_ADVERBS_36:
    pairs_out = []
    for pr in fam["pairs"]:
        a = dict(pr["a"])
        b = dict(pr["b"])
        a["audio"] = resolve_word_audio(a["w"])
        b["audio"] = resolve_word_audio(b["w"])
        pairs_out.append({"a": a, "b": b, "scene": pr["scene"]})
        kana_word_total += 2
    kana36_enriched.append({
        "family": fam["family"],
        "tag": fam["tag"],
        "pairs": pairs_out,
    })

mastery_data = {
    "grammar": {"label": "语法", "counts": count_tiers(grammar_items), "items": grammar_items},
    "henkei": {"label": "活用变形", "counts": count_tiers(henkei_items), "items": henkei_items},
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
    "kana_total": kana_word_total,
}, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
<meta name="description" content="JLPT N3 语音私教" />
<meta name="theme-color" content="#F3EFE8" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<link rel="manifest" href="./manifest.json" />
<link rel="icon" href="./icon-192.png" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet" />
<title>JLPT N3 · 语音私教</title>
<style>
  :root {
    --bg: #F3EFE8;
    --card: #FFFFFF;
    --surface: #FAF8F4;
    --subtle: #E8E2D7;
    --line: rgba(24, 22, 19, 0.10);
    --line-strong: rgba(24, 22, 19, 0.20);
    --ink: #181613;
    --ink-2: #4A453E;
    --ink-3: #7A7368;
    --green: #1B6B50;
    --green-bg: #E8F5EF;
    --green-border: rgba(27, 107, 80, 0.34);
    --amber: #A66314;
    --amber-bg: #FBF3E4;
    --red: #B8372E;
    --red-bg: #FCEEEB;
    --red-border: rgba(184, 55, 46, 0.30);
    --sans: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans", "Noto Sans JP", sans-serif;
    --jp: "Noto Sans JP", "Hiragino Sans", "PingFang SC", sans-serif;
    --shadow-card: 0 14px 36px -14px rgba(24, 22, 19, 0.10), 0 2px 6px rgba(24, 22, 19, 0.03);
  }

  * {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
  }

  /* Lock viewport 100% solid: prevents rubber-band bounce & annoying vertical wobble on mobile home screen */
  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    height: 100dvh;
    overflow: hidden;
    overscroll-behavior: none;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  body {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(10px + env(safe-area-inset-top)) 16px calc(12px + env(safe-area-inset-bottom));
  }

  .app-shell {
    width: 100%;
    max-width: 500px;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  @media (min-width: 900px) {
    body {
      padding: 24px 36px 24px;
    }
    .app-shell {
      max-width: 1020px;
    }
  }

  /* ================= CLEAN TOP HEADER ================= */
  .app-header {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    padding: 0 2px;
  }
  .brand-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .n3-seal {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--ink);
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.02em;
    padding: 3px 8px;
    border-radius: 8px;
    transform: translateY(-1px);
  }
  .countdown {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .countdown strong {
    font-size: 22px;
    font-weight: 800;
    color: var(--green);
    margin: 0 2px;
  }
  @media (min-width: 900px) {
    .app-header { margin-bottom: 18px; }
    .countdown { font-size: 18px; }
    .countdown strong { font-size: 24px; }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .install-pill {
    display: none;
    border: 1.5px solid var(--green-border);
    background: var(--green-bg);
    color: var(--green);
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    padding: 7px 12px;
    border-radius: 999px;
    cursor: pointer;
  }
  .install-pill.visible {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .mode-switch {
    display: inline-flex;
    background: var(--subtle);
    padding: 4px;
    border-radius: 999px;
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 15.5px;
    font-weight: 600;
    padding: 7px 16px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .mode-btn.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(24, 22, 19, 0.10);
  }

  /* ================= VIEW 1: ULTRA-CLEAN TUTOR ================= */
  .tutor-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 500px;
    margin: 0 auto;
  }
  @media (min-width: 900px) {
    .tutor-wrap {
      max-width: 700px;
    }
  }
  .tutor-wrap.hidden { display: none; }

  .session-bar {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    padding: 0 2px;
  }
  .counter-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 16px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    padding: 5px 8px;
    margin-left: -8px;
    border-radius: 10px;
    cursor: pointer;
  }
  .counter-btn:active, .counter-btn:hover {
    background: var(--subtle);
    color: var(--ink);
  }

  .walk-pill {
    border: 1.5px solid var(--line);
    background: var(--card);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    min-height: 38px;
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.15s ease;
  }
  .walk-pill svg {
    width: 17px;
    height: 17px;
    flex-shrink: 0;
  }
  .walk-pill.active {
    background: var(--green);
    color: #FFFFFF;
    border-color: var(--green);
  }

  .progress-rail {
    flex-shrink: 0;
    height: 6px;
    background: var(--subtle);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 12px;
  }
  .progress-fill {
    height: 100%;
    background: var(--green);
    border-radius: 999px;
    transition: width 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  }

  /* Scrollable ONLY if content ever exceeds viewport on tiny screens; locked solid otherwise */
  .tutor-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    display: flex;
    flex-direction: column;
  }
  .tutor-scroll::-webkit-scrollbar { display: none; }

  .voice-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 26px;
    padding: 20px 20px 22px;
    box-shadow: var(--shadow-card);
    display: flex;
    flex-direction: column;
  }
  @media (min-width: 900px) {
    .voice-card {
      border-radius: 30px;
      padding: 32px 42px 32px;
    }
  }

  .card-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .subj-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: var(--surface);
    border: 1px solid var(--line);
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }
  .subj-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
  }
  .prev-link {
    border: none;
    background: transparent;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 8px;
    cursor: pointer;
  }
  .prev-link:hover { color: var(--ink); background: var(--surface); }

  /* ================= STEP 1: LISTEN & PICK ================= */
  .orb-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 4px 0 16px;
  }
  .voice-orb {
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
    box-shadow: 0 10px 24px -6px rgba(24, 22, 19, 0.28);
    transition: transform 0.14s ease, background 0.18s ease, box-shadow 0.18s ease;
  }
  @media (min-width: 900px) {
    .voice-orb { width: 84px; height: 84px; }
  }
  .voice-orb:active { transform: scale(0.94); }
  .voice-orb.listening-emphasis {
    background: var(--green);
    box-shadow: 0 0 0 7px rgba(27, 107, 80, 0.14), 0 10px 24px -6px rgba(27, 107, 80, 0.34);
  }
  .voice-orb.speaking {
    background: var(--green);
    box-shadow: 0 0 0 9px rgba(27, 107, 80, 0.16), 0 10px 24px -6px rgba(27, 107, 80, 0.36);
    animation: orbPulse 1.5s ease-in-out infinite;
  }
  .voice-orb.thinking {
    background: var(--amber);
    box-shadow: 0 0 0 8px rgba(166, 99, 20, 0.16);
  }
  @keyframes orbPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.04); }
  }

  .orb-play-ic {
    width: 28px;
    height: 28px;
    margin-left: 3px;
  }
  .orb-bars {
    display: none;
    align-items: center;
    gap: 4px;
    height: 24px;
  }
  .voice-orb.speaking .orb-play-ic { display: none; }
  .voice-orb.speaking .orb-bars { display: inline-flex; }
  .orb-bars span {
    display: block;
    width: 4px;
    height: 10px;
    background: #FFFFFF;
    border-radius: 99px;
  }
  .voice-orb.speaking .orb-bars span:nth-child(1) { animation: wave 0.65s ease-in-out infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(2) { animation: wave 0.65s ease-in-out 0.14s infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(3) { animation: wave 0.65s ease-in-out 0.28s infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(4) { animation: wave 0.65s ease-in-out 0.1s infinite; }
  @keyframes wave {
    0%, 100% { height: 8px; }
    50% { height: 23px; }
  }

  .orb-caption {
    margin-top: 8px;
    font-size: 15px;
    font-weight: 600;
    color: var(--ink-2);
  }

  .prompt-cue {
    font-family: var(--jp);
    font-size: 23px;
    font-weight: 600;
    line-height: 1.58;
    text-align: center;
    color: var(--ink);
    margin: 0 0 20px;
    padding: 0 2px;
  }
  .prompt-cue.is-listening-cue {
    font-family: var(--sans);
    font-size: 20px;
    color: var(--ink-2);
  }
  @media (min-width: 900px) {
    .prompt-cue {
      font-size: 27px;
      margin-bottom: 24px;
    }
    .prompt-cue.is-listening-cue {
      font-size: 22px;
    }
  }

  .choices-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .choice-btn {
    position: relative;
    width: 100%;
    background: var(--surface);
    border: 1.5px solid var(--line-strong);
    border-radius: 18px;
    min-height: 60px;
    padding: 14px 18px;
    font-family: var(--jp);
    font-size: 20.5px;
    font-weight: 600;
    color: var(--ink);
    text-align: left;
    cursor: pointer;
    box-shadow: 0 2px 0 rgba(24, 22, 19, 0.04);
    transition: transform 0.12s ease, background 0.14s ease, border-color 0.14s ease;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    line-height: 1.42;
  }
  @media (min-width: 900px) {
    .choice-btn {
      min-height: 64px;
      font-size: 22px;
      padding: 15px 22px;
    }
  }
  .choice-btn:hover {
    background: #FFFFFF;
    border-color: var(--ink);
  }
  .choice-btn:active {
    transform: scale(0.988);
  }

  .kbd-hint {
    display: none;
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 600;
    color: var(--ink-3);
    background: rgba(24, 22, 19, 0.06);
    border: 1px solid rgba(24, 22, 19, 0.10);
    border-radius: 6px;
    padding: 2px 7px;
    flex-shrink: 0;
  }
  @media (hover: hover) and (pointer: fine) {
    .kbd-hint { display: inline-block; }
  }

  .skip-btn {
    margin-top: 10px;
    width: 100%;
    border: none;
    background: transparent;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 15.5px;
    font-weight: 600;
    min-height: 44px;
    border-radius: 14px;
    cursor: pointer;
  }
  .skip-btn:hover, .skip-btn:active {
    background: var(--surface);
    color: var(--ink);
  }

  /* ================= STEP 2: 1-SCREEN INSTANT EXPLANATION ================= */
  .ans-stage {
    animation: fadeIn 0.16s ease;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(3px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .ans-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .verdict-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 18px;
    font-weight: 800;
  }
  .verdict-badge.ok { color: var(--green); }
  .verdict-badge.ng { color: var(--red); }
  .verdict-badge.peek { color: var(--ink); }

  .ans-audio-bar {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .mini-audio-btn {
    border: 1.5px solid var(--line);
    background: var(--surface);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 14.5px;
    font-weight: 600;
    min-height: 38px;
    padding: 6px 13px;
    border-radius: 999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .mini-audio-btn.playing {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
  }

  .ans-answer-box {
    background: var(--green-bg);
    border: 1.5px solid var(--green-border);
    border-radius: 16px;
    padding: 12px 15px;
    margin-bottom: 10px;
    display: flex;
    align-items: baseline;
    gap: 9px;
  }
  .ans-mark-ok {
    font-size: 17px;
    font-weight: 800;
    color: var(--green);
    flex-shrink: 0;
  }
  .ans-ja-text {
    font-family: var(--jp);
    font-size: 20.5px;
    font-weight: 700;
    color: var(--green);
    line-height: 1.45;
  }

  .ans-wrong-box {
    background: var(--red-bg);
    border: 1px solid var(--red-border);
    border-radius: 15px;
    padding: 10px 14px;
    margin-bottom: 10px;
    font-size: 15.5px;
    line-height: 1.52;
    color: var(--ink);
  }
  .ans-wrong-head {
    font-family: var(--jp);
    font-weight: 700;
    color: var(--red);
    margin-right: 6px;
  }

  .core-rule-box {
    background: #F6F3EC;
    border-left: 4px solid var(--green);
    border-radius: 13px;
    padding: 12px 15px;
    margin-bottom: 12px;
    font-size: 17.5px;
    font-weight: 600;
    line-height: 1.58;
    color: var(--ink);
  }
  @media (min-width: 900px) {
    .core-rule-box { font-size: 18.5px; }
  }

  .full-sentence-box {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 12px 15px;
    margin-bottom: 16px;
  }
  .full-sentence-hint {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--ink-3);
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .full-sentence-ja {
    font-family: var(--jp);
    font-size: 20.5px;
    font-weight: 500;
    line-height: 1.82;
    color: var(--ink);
    white-space: pre-line;
  }
  @media (min-width: 900px) {
    .full-sentence-ja { font-size: 23px; }
  }

  /* Tappable Dictionary Word */
  .w-tok {
    border-bottom: 2px dotted rgba(27, 107, 80, 0.48);
    padding-bottom: 1px;
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .w-tok:hover, .w-tok.active-tok {
    background: rgba(27, 107, 80, 0.14);
    color: var(--green);
    border-bottom-style: solid;
    border-bottom-color: var(--green);
  }

  .nav-row {
    display: flex;
    gap: 10px;
  }
  .again-btn {
    background: var(--surface);
    color: var(--ink-2);
    border: 1.5px solid var(--line);
    border-radius: 17px;
    min-height: 56px;
    padding: 13px 18px;
    font-family: var(--sans);
    font-size: 16.5px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .again-btn:hover { border-color: var(--line-strong); color: var(--ink); }

  .next-btn {
    flex: 1;
    background: var(--ink);
    color: #FFFFFF;
    border: none;
    border-radius: 17px;
    min-height: 56px;
    padding: 13px 22px;
    font-family: var(--sans);
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .next-btn:active { transform: scale(0.988); }
  .next-btn .kbd-hint {
    color: rgba(255,255,255,0.8);
    background: rgba(255,255,255,0.16);
    border-color: rgba(255,255,255,0.22);
  }

  /* Walk Mode Controls */
  .walk-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--green-bg);
    border: 1px solid var(--green-border);
    color: var(--green);
    padding: 10px 14px;
    border-radius: 14px;
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 700;
  }
  .walk-controls-row {
    display: grid;
    grid-template-columns: 1fr 1.3fr 1fr;
    gap: 10px;
    margin-top: 14px;
  }
  .walk-nav-btn {
    border: 1.5px solid var(--line);
    background: var(--surface);
    color: var(--ink);
    border-radius: 16px;
    min-height: 54px;
    font-family: var(--sans);
    font-size: 15.5px;
    font-weight: 700;
    cursor: pointer;
  }
  .walk-nav-btn.primary {
    background: var(--ink);
    color: #FFFFFF;
    border-color: var(--ink);
  }

  /* Desktop-only quiet shortcut bar (completely hidden on phones!) */
  .studio-footer {
    display: none;
    flex-shrink: 0;
    margin-top: 12px;
    text-align: center;
    font-size: 13px;
    color: var(--ink-3);
  }
  @media (hover: hover) and (pointer: fine) and (min-width: 900px) {
    .studio-footer { display: block; }
  }

  /* ================= WORD DICTIONARY POPOVER (Big Font!) ================= */
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(24, 22, 19, 0.28);
    z-index: 990;
    display: none;
  }
  .sheet-backdrop.open { display: block; }

  .word-popover {
    position: fixed;
    z-index: 999;
    background: #1C1917;
    color: #F7F6F2;
    box-shadow: 0 22px 52px rgba(0, 0, 0, 0.32);
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
      border-radius: 24px;
      padding: 20px 20px 22px;
      animation: slideSheetUp 0.18s cubic-bezier(0.22, 1, 0.36, 1);
    }
  }
  @media (min-width: 768px) {
    .sheet-backdrop.open { display: none; }
    .word-popover {
      width: 360px;
      border-radius: 20px;
      padding: 18px 20px;
      animation: fadeIn 0.14s ease;
    }
  }
  @keyframes slideSheetUp {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .wp-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .wp-head {
    font-family: var(--jp);
    font-size: 23px;
    font-weight: 700;
    color: #FFFFFF;
  }
  .wp-kana {
    font-family: var(--jp);
    font-size: 16px;
    color: #E0DDD6;
    margin-left: 8px;
  }
  .wp-pitch {
    font-size: 14px;
    color: #8CE0C2;
    margin-left: 5px;
  }
  .wp-speak {
    border: 1px solid rgba(255,255,255,0.24);
    background: rgba(255,255,255,0.13);
    color: #FFFFFF;
    border-radius: 999px;
    padding: 8px 15px;
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    flex-shrink: 0;
  }
  .wp-pos {
    display: inline-block;
    font-size: 13.5px;
    color: #D4CFC5;
    background: rgba(255,255,255,0.10);
    padding: 3px 9px;
    border-radius: 7px;
    margin-bottom: 10px;
  }
  .wp-zh {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 6px;
    line-height: 1.45;
  }
  .wp-tip {
    font-size: 15px;
    color: #C4BEB3;
    line-height: 1.55;
  }

  /* ================= VIEW 2: MASTERY OVERVIEW ("总表") ================= */
  .dash-wrap {
    display: none;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    flex-direction: column;
    gap: 14px;
    padding-bottom: 20px;
    width: 100%;
  }
  .dash-wrap.active { display: flex; }

  @media (min-width: 900px) {
    .dash-wrap.active {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 22px;
      align-items: start;
    }
  }

  .dash-left-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .summary-card, .detail-card, .kana36-entry {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px;
    box-shadow: var(--shadow-card);
  }
  .sum-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 10px;
    margin: 0 -10px;
    border-radius: 13px;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
  }
  .sum-row:last-child { border-bottom: none; }
  .sum-row.selected-mod { background: var(--surface); }
  .sum-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
  .sum-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
  }
  .sum-nums {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .tri-bar {
    height: 8px;
    background: var(--subtle);
    border-radius: 999px;
    overflow: hidden;
    display: flex;
  }
  .tri-seg-done { background: var(--green); height: 100%; }
  .tri-seg-wip { background: #D9A441; height: 100%; }
  .tri-seg-todo { background: var(--red); height: 100%; }

  .kana36-entry {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .kana36-entry.selected-mod { border-color: var(--ink); }
  .kana36-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 3px;
  }
  .kana36-sub {
    font-size: 14px;
    color: var(--ink-2);
  }
  .kana36-pill {
    font-size: 14px;
    font-weight: 700;
    color: var(--green);
    background: var(--green-bg);
    padding: 6px 12px;
    border-radius: 999px;
    white-space: nowrap;
  }

  @media (min-width: 900px) {
    .mobile-only-mod-tabs { display: none !important; }
  }
  .mod-tabs {
    display: flex;
    gap: 7px;
    margin-bottom: 12px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .mod-tabs::-webkit-scrollbar { display: none; }
  .mod-tab {
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    padding: 8px 14px;
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
    gap: 5px;
    background: var(--subtle);
    padding: 4px;
    border-radius: 13px;
    margin-bottom: 12px;
  }
  .tier-tab {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    padding: 8px 6px;
    border-radius: 10px;
    cursor: pointer;
    font-variant-numeric: tabular-nums;
  }
  .tier-tab.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 700;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }

  .search-input {
    width: 100%;
    border: 1.5px solid var(--line);
    background: var(--surface);
    border-radius: 14px;
    padding: 11px 14px;
    font-family: var(--sans);
    font-size: 16px;
    color: var(--ink);
    margin-bottom: 10px;
    outline: none;
  }
  .search-input:focus { border-color: var(--ink); background: #FFFFFF; }

  .point-list {
    display: flex;
    flex-direction: column;
  }
  .pt-item {
    padding: 14px 6px;
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
    gap: 9px;
    min-width: 0;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot.todo { background: var(--red); }
  .dot.wip { background: #D9A441; }
  .dot.done { background: var(--green); }
  .pt-name {
    font-family: var(--jp);
    font-size: 17.5px;
    font-weight: 600;
    color: var(--ink);
  }
  .pt-right {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 55%;
  }
  .pt-sub {
    font-size: 15px;
    color: var(--ink-2);
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pt-jump-btn {
    border: 1.5px solid var(--green-border);
    background: var(--green-bg);
    color: var(--green);
    font-family: var(--sans);
    font-size: 13.5px;
    font-weight: 700;
    padding: 5px 11px;
    border-radius: 999px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .pt-note {
    margin-top: 8px;
    padding-left: 18px;
    font-size: 15px;
    color: var(--ink-2);
    line-height: 1.55;
  }

  /* Kana Adverbs Paired Cards */
  .kana-fam-block { margin-bottom: 20px; }
  .kana-fam-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 9px;
  }
  .kana-fam-title { font-size: 16.5px; font-weight: 700; color: var(--ink); }
  .kana-fam-tag { font-size: 13.5px; color: var(--ink-3); }
  .kana-pair-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 13px 14px;
    margin-bottom: 10px;
  }
  .kana-pair-scene {
    font-size: 14px;
    font-weight: 700;
    color: var(--green);
    margin-bottom: 9px;
  }
  .kana-twins {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  @media (max-width: 430px) {
    .kana-twins { grid-template-columns: 1fr; }
  }
  .kana-twin-item {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 13px;
    padding: 11px 13px;
  }
  .kt-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .kt-word {
    font-family: var(--jp);
    font-size: 18.5px;
    font-weight: 700;
    color: var(--ink);
  }
  .kt-pitch { font-size: 13px; color: var(--ink-3); margin-left: 5px; }
  .kt-audio-btn {
    border: none;
    background: var(--subtle);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 13.5px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    cursor: pointer;
  }
  .kt-zh { font-size: 15.5px; font-weight: 600; color: var(--ink); margin-bottom: 3px; }
  .kt-colloc { font-family: var(--jp); font-size: 14px; color: var(--ink-2); }

  /* Simple Progress Reset Modal */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(24, 22, 19, 0.36);
    z-index: 1000;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .modal-overlay.open { display: flex; }
  .modal-box {
    width: 100%;
    max-width: 390px;
    background: var(--card);
    border-radius: 24px;
    padding: 24px;
    box-shadow: 0 24px 60px rgba(0,0,0,0.2);
  }
  .modal-title { font-size: 20px; font-weight: 800; margin: 0 0 10px; }
  .modal-p { font-size: 16px; line-height: 1.6; color: var(--ink-2); margin: 0 0 18px; }
  .modal-actions { display: flex; gap: 10px; }

  .done-wrap { text-align: center; padding: 28px 8px; }
  .done-title { font-size: 24px; font-weight: 800; margin: 0 0 10px; }
  .done-sub { font-size: 16.5px; color: var(--ink-2); margin: 0 0 24px; line-height: 1.6; }
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
      <span class="n3-seal">N3</span>
      <span class="countdown" id="countdown-txt">距考试 <strong>22</strong> 天</span>
    </div>
    <div class="header-right">
      <button class="install-pill" id="pwa-install-btn" onclick="triggerPwaInstall()">加到桌面</button>
      <div class="mode-switch" role="tablist">
        <button class="mode-btn active" id="tab-tutor" onclick="switchMode('tutor')">做题</button>
        <button class="mode-btn" id="tab-dash" onclick="switchMode('dash')">总表</button>
      </div>
    </div>
  </header>

  <!-- VIEW 1: SIMPLE 2-STEP TUTOR -->
  <main class="tutor-wrap" id="tutor-view">
    <div class="session-bar">
      <button class="counter-btn" id="card-counter" onclick="openSessionModal()">1 / 35</button>
      <button class="walk-pill" id="walk-btn" onclick="toggleWalkMode()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
        <span id="walk-btn-label">随身听</span>
      </button>
    </div>
    <div class="progress-rail">
      <div class="progress-fill" id="prog-fill" style="width: 0%"></div>
    </div>

    <div class="tutor-scroll" id="tutor-scroll">
      <div class="voice-card" id="voice-card"></div>
    </div>

    <footer class="studio-footer">
      电脑快捷键：Space 听题/重听 · 1/2/3 作答 · Enter 下一题 · ← 上一题 · S 语速
    </footer>
  </main>

  <!-- VIEW 2: MASTERY OVERVIEW ("总表") -->
  <section class="dash-wrap" id="dash-view">
    <div class="dash-left-col">
      <div class="summary-card" id="dash-summary"></div>
      <div class="kana36-entry" id="kana36-entry" onclick="selectDashMod('kana36')">
        <div>
          <div class="kana36-title" id="kana36-title">纯假名副词 42 词</div>
          <div class="kana36-sub">成对反义速记</div>
        </div>
        <span class="kana36-pill">查看 →</span>
      </div>
    </div>

    <div class="detail-card" id="dash-detail-card">
      <div class="mod-tabs mobile-only-mod-tabs" id="mod-tabs"></div>
      <div id="dash-filter-zone">
        <div class="tier-tabs" id="tier-tabs"></div>
        <input type="search" class="search-input" id="pt-search" placeholder="搜语法或单词…" oninput="renderMasteryList()" />
      </div>
      <div class="point-list" id="point-list"></div>
    </div>
  </section>
</div>

<!-- Word Dictionary Bottom Sheet / Popover -->
<div class="sheet-backdrop" id="sheet-backdrop" onclick="hideWordPopover()"></div>
<div class="word-popover" id="word-popover"></div>

<!-- Lightweight Progress Reset Modal -->
<div class="modal-overlay" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-box" id="modal-content"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.2, 1.3, 1.5];
const SESSION_KEY = "n3_session_v6_" + DATA.plan_date;

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.3");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.3;

let activeKind = null;

// Seamless Auto-Sync with Web Updates (Zero Manual Cache Clearing!)
if ("serviceWorker" in navigator) {
  let swRefreshing = false;
  navigator.serviceWorker.register("./sw.js", { updateViaCache: "none" }).then(reg => {
    reg.update().catch(() => {});
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") reg.update().catch(() => {});
    });
  }).catch(() => {});

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (swRefreshing) return;
    swRefreshing = true;
    if (!activeKind) location.reload();
  });
}

function computeDaysLeft() {
  try {
    const fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Los_Angeles",
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    });
    const [y, m, d] = fmt.format(new Date()).split("-").map(Number);
    const todayUTC = Date.UTC(y, m - 1, d);
    const examUTC = Date.UTC(2026, 11, 6);
    const diff = Math.round((examUTC - todayUTC) / 86400000);
    return diff >= 0 ? diff : 0;
  } catch (e) {
    return DATA.days_to_exam;
  }
}

function loadSavedSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY) || localStorage.getItem("n3_session_v5_" + DATA.plan_date);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return { doneIds: [], masteryOverrides: {} };
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
let currentChoices = [];
let pickedVal = null;
let walkMode = false;
let walkTimer = null;
let thinkingCountdown = 0;
let activeMode = "tutor";
let wakeLockSentinel = null;

function prepareChoicesForCard(q) {
  if (!q) return [];
  const arr = q.choices.slice();
  if (!q.is_listening && arr.length === 2) {
    let h = 0;
    for (let i = 0; i < q.id.length; i++) h = (h * 31 + q.id.charCodeAt(i)) >>> 0;
    if ((h + (q._requeue ? 1 : 0)) % 2 === 1) arr.reverse();
  }
  return arr;
}

function syncCurrentCardSetup() {
  stage = "quiz";
  currentChoices = prepareChoicesForCard(queue[idx]);
  const sc = document.getElementById("tutor-scroll");
  if (sc) sc.scrollTop = 0;
}
syncCurrentCardSetup();

let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

let deferredInstallPrompt = null;
const isStandalone = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  if (isStandalone) return;
  deferredInstallPrompt = e;
  const btn = document.getElementById("pwa-install-btn");
  if (btn) btn.classList.add("visible");
});

function triggerPwaInstall() {
  if (!deferredInstallPrompt) return;
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

const preloadSet = new Set();
function warmAudio(url) {
  if (!url || preloadSet.has(url)) return;
  preloadSet.add(url);
  const a = new Audio();
  a.preload = "auto";
  a.src = url;
}

function applyPlaybackRate(kind) {
  const rate = (kind === "exp" || kind === "done") ? expSpeed : 1.0;
  player.defaultPlaybackRate = rate;
  player.playbackRate = rate;
  if ("preservesPitch" in player) player.preservesPitch = true;
  if ("webkitPreservesPitch" in player) player.webkitPreservesPitch = true;
}

function cycleExpSpeed() {
  expSpeed = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  try { localStorage.setItem("n3_exp_speed", String(expSpeed)); } catch (e) {}
  if (activeKind === "exp") applyPlaybackRate("exp");
  const spdBtn = document.getElementById("ans-spd-btn");
  if (spdBtn) spdBtn.textContent = `${expSpeed.toFixed(1)}x`;
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
  clearWalkTimer();
  try {
    player.pause();
    player.currentTime = 0;
    wordPlayer.pause();
  } catch (e) {}
  activeKind = null;
  syncOrbState();
}

function updateMediaSession() {
  if (!("mediaSession" in navigator) || idx >= queue.length) return;
  const q = queue[idx];
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: stage === "quiz" ? `${q.subject} · 第 ${idx + 1} 题` : `${q.subject} · ${q.point}`,
      artist: "JLPT N3 语音私教",
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
        if (walkMode && stage !== "answered") choose("__walk__", true);
      }
    }, 900);
  } else if (finishedKind === "exp" && stage === "answered") {
    walkTimer = setTimeout(() => {
      if (walkMode && stage === "answered") nextCard(false);
    }, 900);
  }
});

function syncOrbState() {
  const orb = document.getElementById("voice-orb");
  const cap = document.getElementById("orb-caption");
  if (orb && cap) {
    const speaking = activeKind === "q" && !player.paused;
    orb.classList.toggle("speaking", !!speaking);
    orb.classList.toggle("thinking", thinkingCountdown > 0);
    if (thinkingCountdown > 0) {
      cap.textContent = `心里想一下答案… ${thinkingCountdown}s`;
    } else if (speaking) {
      cap.textContent = "播放中 · 点此暂停";
    } else {
      cap.textContent = (queue[idx] && queue[idx].is_listening) ? "点此听对话" : "点此听题";
    }
  }
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    const expOn = activeKind === "exp" && !player.paused;
    repBtn.classList.toggle("playing", expOn);
    repBtn.textContent = expOn ? "暂停讲解" : "重听讲解";
  }
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

function getCurrentWalkSlot() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return "morning";
  if (h >= 11 && h < 17) return "midday";
  return "evening";
}

function startWalkCurrentCard() {
  if (!walkMode || idx >= queue.length) return;
  const q = queue[idx];
  if (stage !== "answered") {
    playMainClip(q.q_audio, "q", false);
  } else {
    playMainClip(q.exp_audio, "exp", false);
  }
}

function toggleWalkMode(forceState) {
  walkMode = typeof forceState === "boolean" ? forceState : !walkMode;
  const btn = document.getElementById("walk-btn");
  const lbl = document.getElementById("walk-btn-label");
  if (btn) btn.classList.toggle("active", walkMode);
  if (lbl) lbl.textContent = walkMode ? "随身听中" : "随身听";
  requestWakeLock(walkMode);

  if (walkMode) {
    const target = getCurrentWalkSlot();
    const head = queue.slice(0, idx);
    const tail = queue.slice(idx);
    tail.sort((a, b) => {
      const aMatch = (a.walk_slot === target || (target === "midday" && a.walk_slot === "afternoon")) ? 0 : 1;
      const bMatch = (b.walk_slot === target || (target === "midday" && b.walk_slot === "afternoon")) ? 0 : 1;
      return aMatch - bMatch;
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

function persistSessionLocal() {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionState));
  } catch (e) {}
}

function saveRecord(q, choice, result, askAgain) {
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

  const newTier = (!result || askAgain) ? "todo" : "done";
  sessionState.masteryOverrides[q.point_key] = newTier;
  sessionState.masteryOverrides[q.point] = newTier;
  if (result && !askAgain) {
    if (!sessionState.doneIds.includes(q.id)) sessionState.doneIds.push(q.id);
  } else {
    sessionState.doneIds = sessionState.doneIds.filter(id => id !== q.id);
  }
  persistSessionLocal();
  applyMasteryOverrides(sessionState.masteryOverrides);

  if (location.protocol.startsWith("http")) {
    fetch("./api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({}, rec, { session: sessionState }))
    }).catch(() => {});
  }
}

function choose(val, fromWalk) {
  if (stage === "answered") return;
  hideWordPopover();
  stage = "answered";
  pickedVal = val;
  const q = queue[idx];
  const isCorrect = fromWalk ? true : (val === q.answer);
  if (!fromWalk) {
    vibrate(isCorrect ? 10 : [14, 30, 14]);
    saveRecord(q, val, isCorrect, false);
    if (!isCorrect && !q._requeue) {
      queue.push(Object.assign({}, q, { _requeue: true }));
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
  else if (queue[idx] && queue[idx].q_audio) playMainClip(queue[idx].q_audio, "q", false);
}

function nextCard(requeue) {
  hideWordPopover();
  stopAudio();
  const q = queue[idx];
  if (requeue && q) {
    vibrate(12);
    saveRecord(q, pickedVal, false, true);
    queue.push(Object.assign({}, q, { _requeue: true }));
  }
  idx += 1;
  pickedVal = null;
  syncCurrentCardSetup();
  renderTutor();
  if (idx < queue.length && queue[idx].q_audio) {
    playMainClip(queue[idx].q_audio, "q", false);
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
  if (queue[idx] && queue[idx].q_audio) playMainClip(queue[idx].q_audio, "q", false);
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
  document.getElementById("countdown-txt").innerHTML = `距考试 <strong>${computeDaysLeft()}</strong> 天`;

  const total = queue.length;
  const pct = Math.min(100, Math.round((idx / Math.max(1, total)) * 100));
  document.getElementById("card-counter").textContent = idx < total ? `${idx + 1} / ${total}` : "已完成";
  document.getElementById("prog-fill").style.width = `${pct}%`;

  const box = document.getElementById("voice-card");
  if (idx >= total) {
    box.innerHTML = `
      <div class="done-wrap">
        <h2 class="done-title">今天这一组全部练完了</h2>
        <p class="done-sub">共 ${total} 题已全部过关，去休息一下吧。</p>
        <div class="nav-row">
          <button class="again-btn" onclick="switchMode('dash')">看总表</button>
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
  if (idx + 1 < total) {
    warmAudio(queue[idx + 1].q_audio);
    warmAudio(queue[idx + 1].exp_audio);
  }

  const walkBannerHTML = walkMode ? `
    <div class="walk-banner">
      <span>随身听自动连播中</span>
      <span style="font-size:13.5px;opacity:0.85;">听题 → 想4秒 → 听讲解</span>
    </div>
  ` : "";

  const walkNavHTML = walkMode ? `
    <div class="walk-controls-row">
      <button class="walk-nav-btn" onclick="prevCard()">上一题</button>
      <button class="walk-nav-btn primary" onclick="toggleWalkMode(false)">退出随身听</button>
      <button class="walk-nav-btn" onclick="nextCard(false)">下一题</button>
    </div>
  ` : "";

  // -------- STEP 1: LISTEN & PICK --------
  if (stage === "quiz") {
    const choices = currentChoices.length ? currentChoices : q.choices;
    const choicesHTML = choices.map((c, cIdx) => `
      <button class="choice-btn" onclick='choose(${JSON.stringify(c)}, false)'>
        <span>${escapeHtml(c)}</span>
        <span class="kbd-hint">${cIdx + 1}</span>
      </button>
    `).join("");

    box.innerHTML = `
      ${walkBannerHTML}
      <div class="card-top-row">
        <span class="subj-pill"><span class="subj-dot"></span>${escapeHtml(q.subject)}</span>
        ${idx > 0 ? `<button class="prev-link" onclick="prevCard()">← 上一题</button>` : `<span></span>`}
      </div>
      <div class="orb-stage">
        <button class="voice-orb ${q.is_listening ? 'listening-emphasis' : ''}" id="voice-orb" onclick="playMainClip(queue[idx].q_audio, 'q', true)" aria-label="播放题目">
          <svg class="orb-play-ic" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>
          <div class="orb-bars"><span></span><span></span><span></span><span></span></div>
        </button>
        <div class="orb-caption" id="orb-caption">${q.is_listening ? "点此听对话" : "点此听题"}</div>
      </div>
      <p class="prompt-cue ${q.is_listening ? 'is-listening-cue' : ''}">${escapeHtml(q.prompt)}</p>
      <div class="choices-stack">
        ${choicesHTML}
      </div>
      ${!walkMode ? `<button class="skip-btn" onclick='choose("不知道", false)'>不确定，直接看讲解</button>` : ""}
      ${walkNavHTML}
    `;
    syncOrbState();
    return;
  }

  // -------- STEP 2: 1-SCREEN INSTANT EXPLANATION ("只留最重要的字") --------
  const isPeek = pickedVal === "不知道" || pickedVal === "__walk__";
  const isCorrect = !isPeek && pickedVal === q.answer;
  const verdictCls = isPeek ? "peek" : (isCorrect ? "ok" : "ng");
  const verdictTxt = isPeek ? `${escapeHtml(q.subject)} · ${escapeHtml(q.point)}` : (isCorrect ? "✓ 答对了" : "✕ 答错了");

  let wrongBoxHTML = "";
  if (!isPeek && !isCorrect && pickedVal) {
    const wNote = (q.option_notes && q.option_notes[pickedVal]) || "语义或接续不符";
    wrongBoxHTML = `
      <div class="ans-wrong-box">
        <span class="ans-wrong-head">✕ ${annotateJapanese(pickedVal)}</span>
        <span>${escapeHtml(wNote)}</span>
      </div>
    `;
  }

  box.innerHTML = `
    ${walkBannerHTML}
    <div class="ans-stage" id="answer-zone">
      <div class="ans-header">
        <span class="verdict-badge ${verdictCls}">${verdictTxt}</span>
        <div class="ans-audio-bar">
          <button class="mini-audio-btn" onclick="playMainClip(queue[idx].q_audio, 'q', true)">听原题</button>
          <button class="mini-audio-btn" id="exp-replay-btn" onclick="playMainClip(queue[idx].exp_audio, 'exp', true)">重听讲解</button>
          <button class="mini-audio-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed.toFixed(1)}x</button>
        </div>
      </div>

      <div class="ans-answer-box">
        <span class="ans-mark-ok">✓</span>
        <div class="ans-ja-text">${annotateJapanese(q.answer)}</div>
      </div>

      ${wrongBoxHTML}

      <div class="core-rule-box">${escapeHtml(q.core_rule)}</div>

      <div class="full-sentence-box">
        <div class="full-sentence-hint">
          <span>完整原句</span>
          <span>点划线词看意思·听发音</span>
        </div>
        <div class="full-sentence-ja">${annotateJapanese(q.full_ja)}</div>
      </div>

      ${!walkMode ? `
      <div class="nav-row">
        <button class="again-btn" onclick="nextCard(true)">再练一次</button>
        <button class="next-btn" onclick="nextCard(false)">下一题 → <span class="kbd-hint">Enter</span></button>
      </div>` : walkNavHTML}
    </div>
  `;
  syncOrbState();
}

// ================= WORD DICTIONARY POPUP =================
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
      ${hasAudio ? `<button class="wp-speak" onclick='playWordAudio(${JSON.stringify(surface)})'>发音</button>` : ""}
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
    const pw = popEl.offsetWidth || 360;
    const ph = popEl.offsetHeight || 150;
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

// ================= DESKTOP KEYBOARD SHORTCUTS =================
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

// ================= VIEW 2: MASTERY OVERVIEW ("总表") =================
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
  if (modKey !== "kana36") {
    const c = recalcCounts(modKey);
    if (c[dashTier] === 0) {
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
          <span class="sum-nums">已会 ${c.done} · 待练 ${c.todo}</span>
        </div>
        <div class="tri-bar">
          <div class="tri-seg-done" style="width:${pDone}%"></div>
          <div class="tri-seg-wip" style="width:${pWip}%"></div>
          <div class="tri-seg-todo" style="width:${pTodo}%"></div>
        </div>
      </div>
    `;
  }).join("");

  const kTitle = document.getElementById("kana36-title");
  if (kTitle) kTitle.textContent = `纯假名副词 ${DATA.kana_total} 词`;
  document.getElementById("kana36-entry").classList.toggle("selected-mod", dashMod === "kana36");

  const mobileTabsHTML = order.map(k => {
    const m = DATA.mastery[k];
    return `<button class="mod-tab ${dashMod === k ? "active" : ""}" onclick="selectDashMod('${k}')">${m.label}</button>`;
  }).join("") + `<button class="mod-tab ${dashMod === 'kana36' ? 'active' : ''}" onclick="selectDashMod('kana36')">假名副词</button>`;
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
    <button class="tier-tab ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待练 ${curCounts.todo}</button>
    <button class="tier-tab ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固 ${curCounts.wip}</button>
    <button class="tier-tab ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已会 ${curCounts.done}</button>
  `;

  renderMasteryList();
}

function renderKana36View() {
  const listEl = document.getElementById("point-list");
  listEl.innerHTML = DATA.kana36.map(fam => `
    <div class="kana-fam-block">
      <div class="kana-fam-head">
        <span class="kana-fam-title">${escapeHtml(fam.family)}</span>
        <span class="kana-fam-tag">${escapeHtml(fam.tag)}</span>
      </div>
      ${fam.pairs.map(pr => `
        <div class="kana-pair-card">
          <div class="kana-pair-scene">${escapeHtml(pr.scene)}</div>
          <div class="kana-twins">
            ${[pr.a, pr.b].map(item => `
              <div class="kana-twin-item">
                <div class="kt-top">
                  <div><span class="kt-word">${escapeHtml(item.w)}</span><span class="kt-pitch">${escapeHtml(item.pitch)}</span></div>
                  ${item.audio ? `<button class="kt-audio-btn" onclick='playDirectUrl(${JSON.stringify(item.audio)})'>发音</button>` : ""}
                </div>
                <div class="kt-zh">${escapeHtml(item.zh)}</div>
                <div class="kt-colloc">${escapeHtml(item.colloc)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `).join("")}
    </div>
  `).join("");
}

function togglePtNote(i) {
  expandedPt = (expandedPt === i) ? null : i;
  renderMasteryList();
}

function renderMasteryList() {
  const q = (document.getElementById("pt-search").value || "").trim().toLowerCase();
  const items = DATA.mastery[dashMod].items.filter(it => {
    if (q) return it.name.toLowerCase().includes(q) || (it.sub || "").toLowerCase().includes(q) || (it.family || "").toLowerCase().includes(q);
    return it.tier === dashTier;
  });

  const listEl = document.getElementById("point-list");
  if (!items.length) {
    listEl.innerHTML = `<div style="padding:32px 4px;text-align:center;color:var(--ink-3);font-size:15.5px;">这一栏已经清空了</div>`;
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
          ${it.card_id ? `<button class="pt-jump-btn" onclick="event.stopPropagation();jumpToCardById('${it.card_id}')">去练</button>` : ""}
        </div>
      </div>
      ${expandedPt === i && (it.note || it.family) ? `<div class="pt-note">${escapeHtml([it.family, it.note].filter(Boolean).join(" · "))}</div>` : ""}
    </div>
  `).join("");
}

function closeModal() {
  document.getElementById("app-modal").classList.remove("open");
}

function openSessionModal() {
  const doneCount = (sessionState.doneIds || []).length;
  const el = document.getElementById("modal-content");
  el.innerHTML = `
    <h3 class="modal-title">本轮进度</h3>
    <p class="modal-p">当前已完成 <strong>${doneCount} / ${DATA.cards.length}</strong> 题。</p>
    <div class="modal-actions">
      <button class="again-btn" onclick="resetDailySession()">从头开始</button>
      <button class="next-btn" onclick="closeModal()">继续做题</button>
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
    if (urlMode === "walk") toggleWalkMode(true);
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
print("Wrote Ultra-Simple Big-Type N3 Tutor HTML:", HTML_PATH, "size:", len(final_html), "bytes")
