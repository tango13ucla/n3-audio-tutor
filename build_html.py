#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the JLPT N3 Real-Time Adaptive Platform (index.html).
1) Exam-Score ROI Priority (Official N3 Pillar Weight x Weakness toward 120+/180)
2) Mastery-Driven Pedagogical Routing (Weak -> Teach Point First, Quiz 4 Steps Later;
   Semi-Familiar -> Direct Quiz; Wrong -> Confusion-Family Contrast + Reverse-Angle Variant Quiz)
3) Dual Goals:
   - Home: 50-Cell "All-Green Before Sleep" Matrix + Live 120-Point Exam Readiness %
   - Secondary Tab ("总表"): Unified 4 Official JLPT N3 Pillars (Grammar, Conjugation/Keigo, Listening, Core Vocab)
4) Zero Vibration, Large Crisp Fonts, Locked 100dvh Native Viewport, Instant Web Auto-Sync.
"""
import glob
import json
import os
import re

from adaptive_bank import (
    CORE_N3_KANA_VOCAB,
    EXTRA_PRIMARY_CARDS,
    EXTRA_WORDS,
    POINT_META,
    VARIANT_CARDS,
)
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
merged_raw_words = dict(WORD_DICT)
merged_raw_words.update(EXTRA_WORDS)

rich_words = {}
for surf, info in merged_raw_words.items():
    entry = dict(info)
    alias = info.get("audio_alias")
    entry["audio"] = word_audio_map.get(surf) or (word_audio_map.get(alias, "") if alias else "")
    rich_words[surf] = entry


def resolve_word_audio(w: str) -> str:
    return rich_words.get(w, {}).get("audio") or word_audio_map.get(w, "")


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


def weakness_multiplier(status: str) -> float:
    # Unmastered / weak points get highest priority; yellow gets verification priority
    if status == "red":
        return 1.00
    if status in ("orange", "gray"):
        return 0.92
    if status == "yellow":
        return 0.62
    return 0.20


def has_mp3_pair(q_rel: str, exp_rel: str) -> bool:
    for rel in (q_rel, exp_rel):
        if not rel:
            return False
        abs_p = os.path.join(BASE_DIR, rel.lstrip("./"))
        if not (os.path.exists(abs_p) and os.path.getsize(abs_p) > 0):
            return False
    return True


# Build Variant lookup by base card ID
variants_by_base = {}
for vc in VARIANT_CARDS:
    meta = audio_manifest.get(f"meta:{vc['id']}", {})
    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if has_mp3_pair(q_rel, exp_rel):
        v_obj = {
            "id": vc["id"],
            "prompt": clean_prompt(vc["prompt"], vc["subject"] == "聴解"),
            "choices": vc["choices"],
            "answer": vc["answer"],
            "full_ja": vc["full_ja"],
            "core_rule": clean_rule_text(vc["core_rule"]),
            "option_notes": vc.get("option_notes", {}),
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": vc["subject"] == "聴解",
        }
        variants_by_base.setdefault(vc["variant_of"], []).append(v_obj)


def build_base_point(q: dict, subject: str, fallback_point_label: str) -> dict:
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

    pt_status = resolve_point_status(point_key)
    pmeta = POINT_META.get(qid, {"family": "general", "weight": 2.2})
    exam_weight = float(pmeta["weight"])
    roi_score = round(exam_weight * weakness_multiplier(pt_status), 3)

    raw_micro = t_item.get("micro_lesson") or {}
    opt_notes = t_item.get("option_notes") or {}
    core_rule = clean_rule_text(raw_micro.get("hook") or opt_notes.get(answer) or explain)

    left_m = raw_micro.get("left") or {}
    right_m = raw_micro.get("right") or {}
    teach_left = {
        "ja": left_m.get("ja") or answer,
        "sub": " · ".join(x for x in [left_m.get("sub", ""), left_m.get("desc", "")] if x) or opt_notes.get(answer, ""),
    }
    other_opt = next((c for c in choices if c != answer), "")
    teach_right = {
        "ja": right_m.get("ja") or other_opt,
        "sub": " · ".join(x for x in [right_m.get("sub", ""), right_m.get("desc", "")] if x) or opt_notes.get(other_opt, ""),
    }

    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if not has_mp3_pair(q_rel, exp_rel):
        return None

    return {
        "id": qid,
        "subject": subject,
        "point": display_point,
        "point_key": point_key,
        "family": pmeta["family"],
        "exam_weight": exam_weight,
        "roi_score": roi_score,
        "initial_weak": pt_status in ("red", "orange", "gray"),
        "walk_slot": t_item.get("walk_slot", "morning"),
        "teach": {
            "left": teach_left,
            "right": teach_right,
            "rule": core_rule,
            "example_ja": full_ja,
            "audio": exp_rel,
        },
        "primary": {
            "id": qid,
            "prompt": prompt_display,
            "choices": choices,
            "answer": answer,
            "full_ja": full_ja,
            "core_rule": core_rule,
            "option_notes": opt_notes,
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": is_listening,
        },
        "variants": variants_by_base.get(qid, []),
    }


raw_points = []
for q in plan.get("grammar", {}).get("formal", []) + plan.get("grammar", {}).get("quick", []):
    pt = build_base_point(q, "文法", q.get("point", ""))
    if pt:
        raw_points.append(pt)
for q in plan.get("henkei", {}).get("formal", []) + plan.get("henkei", {}).get("quick", []):
    pt = build_base_point(q, "活用", re.sub(r"^[A-Z]-\d+(?:/[A-Z]-\d+)?\s*", "", q.get("point", "")))
    if pt:
        raw_points.append(pt)
for q in plan.get("vocab", {}).get("formal", []) + plan.get("vocab", {}).get("quick", []):
    pt = build_base_point(q, "語彙", q.get("word", ""))
    if pt:
        raw_points.append(pt)
for q in plan.get("listening", {}).get("formal", []):
    pt = build_base_point(q, "聴解", "口语听辨")
    if pt:
        raw_points.append(pt)

for ext in EXTRA_PRIMARY_CARDS:
    qid = ext["id"]
    meta = audio_manifest.get(f"meta:{qid}", {})
    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if not has_mp3_pair(q_rel, exp_rel):
        continue
    pt_status = resolve_point_status(ext["point_key"])
    w = float(ext["weight"])
    is_l = ext["subject"] == "聴解"
    raw_points.append({
        "id": qid,
        "subject": ext["subject"],
        "point": ext["point_display"],
        "point_key": ext["point_key"],
        "family": ext["family"],
        "exam_weight": w,
        "roi_score": round(w * weakness_multiplier(pt_status), 3),
        "initial_weak": pt_status in ("red", "orange", "gray"),
        "walk_slot": "morning" if ext["subject"] == "文法" else ("midday" if ext["subject"] in ("語彙", "活用") else "evening"),
        "teach": {
            "left": ext["teach_left"],
            "right": ext["teach_right"],
            "rule": clean_rule_text(ext["core_rule"]),
            "example_ja": ext["full_ja"],
            "audio": exp_rel,
        },
        "primary": {
            "id": qid,
            "prompt": clean_prompt(ext["prompt"], is_l),
            "choices": ext["choices"],
            "answer": ext["answer"],
            "full_ja": ext["full_ja"],
            "core_rule": clean_rule_text(ext["core_rule"]),
            "option_notes": ext["option_notes"],
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": is_l,
        },
        "variants": variants_by_base.get(qid, []),
    })

# Sort strictly by Official N3 Score ROI (Exam Importance x Weakness), cap at Top 50 Pillars, then interleave smoothly
raw_points.sort(key=lambda x: (-x["roi_score"], -x["exam_weight"], x["id"]))
raw_points = raw_points[:50]

# Smoothly interleave top-priority buckets so user doesn't hit 10 listening or 10 grammar in a row,
# and ensure point #0 is non-listening so first-open shows Japanese text before browser audio unlock
buckets = {"文法": [], "活用": [], "語彙": [], "聴解": []}
for p in raw_points:
    buckets[p["subject"]].append(p)

ordered_points = []
subj_cycle = ["文法", "活用", "語彙", "聴解"]
while any(buckets.values()):
    for s in subj_cycle:
        if buckets[s]:
            ordered_points.append(buckets[s].pop(0))

point_id_by_key = {}
for p in ordered_points:
    point_id_by_key[p["point_key"]] = p["id"]
    point_id_by_key[p["point"]] = p["id"]


def norm_tier(status: str) -> str:
    if status in ("red", "orange"):
        return "todo"
    if status == "green":
        return "done"
    return "wip"


# ================= UNIFIED 4 OFFICIAL JLPT N3 PILLARS FOR "总表" =================
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
        "point_id": point_id_by_key.get(nm, ""),
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
        "point_id": point_id_by_key.get(pid, ""),
        "note": p.get("note", ""),
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
        "point_id": point_id_by_key.get(pid, ""),
        "note": p.get("trap", "") or p.get("note", ""),
    })

# Fold genuine high-frequency N3 Kana Adverbs cleanly into Core Vocab (dropping non-N3 casual chat words!)
DROP_CASUAL_WORDS = {"ぱさぱさ", "ずしっと", "万年筆"}
vocab_items = []
seen_vocab_words = set()

for p in live_state.get("vocab_tracked", []):
    w = p.get("word", "")
    if w in DROP_CASUAL_WORDS:
        continue
    seen_vocab_words.add(w)
    st = p.get("status", "red")
    w_info = rich_words.get(w, {})
    meaning_short = w_info.get("zh") or re.sub(r"^\d+\.\s*", "", p.get("category", ""))
    vocab_items.append({
        "key": w,
        "name": w,
        "sub": meaning_short,
        "family": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": norm_tier(st),
        "point_id": point_id_by_key.get(w, ""),
        "audio": resolve_word_audio(w),
        "note": w_info.get("tip") or p.get("classroom_note") or "",
    })

for kw, pitch, desc in CORE_N3_KANA_VOCAB:
    if kw in seen_vocab_words:
        continue
    seen_vocab_words.add(kw)
    vocab_items.append({
        "key": kw,
        "name": kw,
        "sub": desc.split("（")[0],
        "family": "高频假名副词（真题占3–5分）",
        "tier": "wip",
        "point_id": point_id_by_key.get(kw, ""),
        "audio": resolve_word_audio(kw),
        "note": f"声调 {pitch} · {desc}",
    })


def count_tiers(items):
    c = {"todo": 0, "wip": 0, "done": 0}
    for it in items:
        c[it["tier"]] += 1
    c["total"] = len(items)
    return c


mastery_data = {
    "grammar": {"label": "语法（147核心点）", "short": "语法", "exam_pts": 38, "counts": count_tiers(grammar_items), "items": grammar_items},
    "henkei": {"label": "活用与敬语（语法+听力双跨）", "short": "活用敬语", "exam_pts": 28, "counts": count_tiers(henkei_items), "items": henkei_items},
    "listening": {"label": "听力口语（占卷面 60 分）", "short": "听力口语", "exam_pts": 60, "counts": count_tiers(listening_items), "items": listening_items},
    "vocab": {"label": "核心词汇（含高频假名副词）", "short": "核心词汇", "exam_pts": 24, "counts": count_tiers(vocab_items), "items": vocab_items},
}

payload = json.dumps({
    "plan_date": plan.get("plan_date", "2026-11-14"),
    "exam_date": "2026-12-06",
    "days_to_exam": plan.get("days_to_exam", 22),
    "done_audio": "./audio/done.mp3",
    "points": ordered_points,
    "words": rich_words,
    "mastery": mastery_data,
}, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
<meta name="description" content="JLPT N3 自适应冲刺 120+ 语音私教" />
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
<title>JLPT N3 · 冲刺 120+</title>
<style>
  :root {
    --bg: #F3EFE8;
    --card: #FFFFFF;
    --surface: #FAF8F4;
    --subtle: #E6E0D4;
    --line: rgba(24, 22, 19, 0.10);
    --line-strong: rgba(24, 22, 19, 0.20);
    --ink: #181613;
    --ink-2: #4A453E;
    --ink-3: #7A7368;
    --green: #1B7A58;
    --green-bright: #22946B;
    --green-bg: #E7F5EF;
    --green-border: rgba(27, 122, 88, 0.34);
    --amber: #B86E14;
    --amber-cell: #E09B36;
    --amber-bg: #FCF4E6;
    --amber-border: rgba(184, 110, 20, 0.30);
    --red: #B8372E;
    --red-bg: #FCEEEB;
    --red-border: rgba(184, 55, 46, 0.30);
    --sans: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans", "Noto Sans JP", sans-serif;
    --jp: "Noto Sans JP", "Hiragino Sans", "PingFang SC", sans-serif;
    --shadow-card: 0 14px 34px -14px rgba(24, 22, 19, 0.10), 0 2px 6px rgba(24, 22, 19, 0.03);
  }

  * {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
  }

  /* Locked 100dvh viewport: zero rubber-band bounce or annoying vertical wobble */
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
    padding: calc(8px + env(safe-area-inset-top)) 15px calc(10px + env(safe-area-inset-bottom));
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
    body { padding: 20px 36px 20px; }
    .app-shell { max-width: 1020px; }
  }

  /* ================= TOP HEADER ================= */
  .app-header {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .brand-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .n3-seal {
    background: var(--ink);
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 8px;
  }
  .countdown {
    font-size: 16.5px;
    font-weight: 700;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .countdown strong {
    font-size: 21px;
    font-weight: 800;
    color: var(--green);
    margin: 0 2px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .walk-icon-btn {
    border: 1.5px solid var(--line);
    background: var(--card);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    height: 38px;
    padding: 0 12px;
    border-radius: 999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .walk-icon-btn svg { width: 16px; height: 16px; }
  .walk-icon-btn.active {
    background: var(--green);
    color: #FFFFFF;
    border-color: var(--green);
  }

  .mode-switch {
    display: inline-flex;
    background: var(--subtle);
    padding: 3.5px;
    border-radius: 999px;
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
  }
  .mode-btn.active {
    background: var(--card);
    color: var(--ink);
    font-weight: 700;
    box-shadow: 0 2px 6px rgba(24, 22, 19, 0.10);
  }

  /* ================= GOAL 2: HOME "ALL-GREEN BEFORE SLEEP" BOARD ================= */
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
    .tutor-wrap { max-width: 700px; }
  }
  .tutor-wrap.hidden { display: none; }

  .green-mission-board {
    flex-shrink: 0;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 10px 13px 11px;
    margin-bottom: 10px;
    cursor: pointer;
  }
  .gm-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 7px;
    font-variant-numeric: tabular-nums;
  }
  .gm-left {
    font-size: 14.5px;
    font-weight: 700;
    color: var(--ink);
  }
  .gm-left strong {
    color: var(--green);
    font-size: 16.5px;
    font-weight: 800;
  }
  .gm-right {
    font-size: 14px;
    font-weight: 700;
    color: var(--ink-2);
  }
  .gm-right strong {
    color: var(--green);
    font-size: 16px;
    font-weight: 800;
  }
  .gm-cells {
    display: grid;
    grid-template-columns: repeat(25, 1fr);
    gap: 3px;
  }
  .gm-cell {
    height: 7px;
    border-radius: 2.5px;
    background: #E2DDD2;
    transition: background 0.25s ease, transform 0.2s ease;
  }
  .gm-cell.learning {
    background: var(--amber-cell);
  }
  .gm-cell.green {
    background: var(--green-bright);
  }
  .gm-cell.current {
    box-shadow: 0 0 0 1.8px var(--ink);
    transform: scaleY(1.22);
  }

  /* Scroll container: locked solid unless tiny viewport overflows */
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
    padding: 18px 19px 20px;
    box-shadow: var(--shadow-card);
    display: flex;
    flex-direction: column;
  }
  @media (min-width: 900px) {
    .voice-card {
      border-radius: 30px;
      padding: 28px 40px 30px;
    }
  }

  .card-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .stage-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 14.5px;
    font-weight: 700;
  }
  .stage-pill.teach {
    background: var(--amber-bg);
    color: var(--amber);
    border: 1px solid var(--amber-border);
  }
  .stage-pill.quiz {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--line);
  }
  .stage-pill.variant {
    background: var(--green-bg);
    color: var(--green);
    border: 1px solid var(--green-border);
  }

  .mini-audio-btn {
    border: 1.5px solid var(--line);
    background: var(--surface);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    min-height: 36px;
    padding: 5px 12px;
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

  /* ================= CARD TYPE 1: TEACH POINT FIRST (For Low Mastery!) ================= */
  .teach-title {
    font-family: var(--jp);
    font-size: 22px;
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 12px;
    line-height: 1.35;
  }
  @media (min-width: 900px) {
    .teach-title { font-size: 25px; }
  }
  .contrast-stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }
  .contrast-item {
    border-radius: 16px;
    padding: 12px 15px;
    border: 1.5px solid var(--line);
    background: var(--surface);
  }
  .contrast-item.primary {
    background: var(--green-bg);
    border-color: var(--green-border);
  }
  .ci-ja {
    font-family: var(--jp);
    font-size: 20px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 3px;
  }
  .contrast-item.primary .ci-ja { color: var(--green); }
  .ci-sub {
    font-size: 15px;
    font-weight: 600;
    color: var(--ink-2);
    line-height: 1.45;
  }

  /* ================= CARD TYPE 2: ADAPTIVE QUIZ ================= */
  .orb-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 2px 0 14px;
  }
  .voice-orb {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    border: none;
    background: var(--ink);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 10px 22px -6px rgba(24, 22, 19, 0.28);
    transition: transform 0.14s ease, background 0.18s ease;
  }
  @media (min-width: 900px) {
    .voice-orb { width: 80px; height: 80px; }
  }
  .voice-orb:active { transform: scale(0.94); }
  .voice-orb.listening-emphasis {
    background: var(--green);
    box-shadow: 0 0 0 7px rgba(27, 122, 88, 0.14);
  }
  .voice-orb.speaking {
    background: var(--green);
    box-shadow: 0 0 0 9px rgba(27, 122, 88, 0.16);
    animation: orbPulse 1.5s ease-in-out infinite;
  }
  .voice-orb.thinking { background: var(--amber); }
  @keyframes orbPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.04); }
  }
  .orb-play-ic { width: 26px; height: 26px; margin-left: 3px; }
  .orb-bars { display: none; align-items: center; gap: 4px; height: 22px; }
  .voice-orb.speaking .orb-play-ic { display: none; }
  .voice-orb.speaking .orb-bars { display: inline-flex; }
  .orb-bars span { display: block; width: 4px; height: 9px; background: #FFFFFF; border-radius: 99px; }
  .voice-orb.speaking .orb-bars span:nth-child(1) { animation: wave 0.65s ease-in-out infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(2) { animation: wave 0.65s ease-in-out 0.14s infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(3) { animation: wave 0.65s ease-in-out 0.28s infinite; }
  .voice-orb.speaking .orb-bars span:nth-child(4) { animation: wave 0.65s ease-in-out 0.1s infinite; }
  @keyframes wave {
    0%, 100% { height: 7px; }
    50% { height: 21px; }
  }
  .orb-caption {
    margin-top: 7px;
    font-size: 14.5px;
    font-weight: 600;
    color: var(--ink-2);
  }

  .prompt-cue {
    font-family: var(--jp);
    font-size: 22.5px;
    font-weight: 600;
    line-height: 1.56;
    text-align: center;
    color: var(--ink);
    margin: 0 0 18px;
  }
  .prompt-cue.is-listening-cue {
    font-family: var(--sans);
    font-size: 19.5px;
    color: var(--ink-2);
  }
  @media (min-width: 900px) {
    .prompt-cue { font-size: 26.5px; margin-bottom: 22px; }
    .prompt-cue.is-listening-cue { font-size: 22px; }
  }

  .choices-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .choice-btn {
    width: 100%;
    background: var(--surface);
    border: 1.5px solid var(--line-strong);
    border-radius: 18px;
    min-height: 58px;
    padding: 13px 18px;
    font-family: var(--jp);
    font-size: 20px;
    font-weight: 600;
    color: var(--ink);
    text-align: left;
    cursor: pointer;
    box-shadow: 0 2px 0 rgba(24, 22, 19, 0.04);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    line-height: 1.4;
  }
  @media (min-width: 900px) {
    .choice-btn { min-height: 62px; font-size: 22px; padding: 14px 22px; }
  }
  .choice-btn:hover { background: #FFFFFF; border-color: var(--ink); }
  .choice-btn:active { transform: scale(0.988); }

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
    margin-top: 8px;
    width: 100%;
    border: none;
    background: transparent;
    color: var(--ink-3);
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    min-height: 42px;
    border-radius: 13px;
    cursor: pointer;
  }
  .skip-btn:hover { background: var(--surface); color: var(--ink); }

  /* ================= CARD TYPE 3: INSTANT RESULT ================= */
  .verdict-badge {
    font-size: 17.5px;
    font-weight: 800;
  }
  .verdict-badge.ok { color: var(--green); }
  .verdict-badge.ng { color: var(--red); }

  .ans-answer-box {
    background: var(--green-bg);
    border: 1.5px solid var(--green-border);
    border-radius: 16px;
    padding: 11px 14px;
    margin-bottom: 9px;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .ans-mark-ok { font-size: 17px; font-weight: 800; color: var(--green); }
  .ans-ja-text {
    font-family: var(--jp);
    font-size: 20px;
    font-weight: 700;
    color: var(--green);
    line-height: 1.42;
  }

  .ans-wrong-box {
    background: var(--red-bg);
    border: 1px solid var(--red-border);
    border-radius: 14px;
    padding: 9px 13px;
    margin-bottom: 9px;
    font-size: 15px;
    line-height: 1.48;
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
    padding: 11px 14px;
    margin-bottom: 10px;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.55;
    color: var(--ink);
  }

  .full-sentence-box {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 11px 14px;
    margin-bottom: 14px;
  }
  .full-sentence-hint {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-3);
    margin-bottom: 5px;
    display: flex;
    justify-content: space-between;
  }
  .full-sentence-ja {
    font-family: var(--jp);
    font-size: 20px;
    font-weight: 500;
    line-height: 1.78;
    color: var(--ink);
    white-space: pre-line;
  }
  @media (min-width: 900px) {
    .full-sentence-ja { font-size: 22.5px; }
  }

  .w-tok {
    border-bottom: 2px dotted rgba(27, 122, 88, 0.48);
    padding-bottom: 1px;
    border-radius: 3px;
    cursor: pointer;
  }
  .w-tok:hover, .w-tok.active-tok {
    background: rgba(27, 122, 88, 0.14);
    color: var(--green);
    border-bottom-style: solid;
    border-bottom-color: var(--green);
  }

  .nav-row { display: flex; gap: 10px; }
  .again-btn {
    background: var(--surface);
    color: var(--ink-2);
    border: 1.5px solid var(--line);
    border-radius: 16px;
    min-height: 54px;
    padding: 12px 16px;
    font-family: var(--sans);
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
  }
  .next-btn {
    flex: 1;
    background: var(--ink);
    color: #FFFFFF;
    border: none;
    border-radius: 16px;
    min-height: 54px;
    padding: 12px 20px;
    font-family: var(--sans);
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .next-btn .kbd-hint {
    color: rgba(255,255,255,0.8);
    background: rgba(255,255,255,0.16);
    border-color: rgba(255,255,255,0.22);
  }

  .studio-footer {
    display: none;
    flex-shrink: 0;
    margin-top: 10px;
    text-align: center;
    font-size: 13px;
    color: var(--ink-3);
  }
  @media (hover: hover) and (pointer: fine) and (min-width: 900px) {
    .studio-footer { display: block; }
  }

  /* ================= WORD DICTIONARY POPOVER ================= */
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
      border-radius: 24px;
      padding: 20px 20px 22px;
    }
  }
  @media (min-width: 768px) {
    .sheet-backdrop.open { display: none; }
    .word-popover { width: 360px; border-radius: 20px; padding: 18px 20px; }
  }
  .wp-top { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
  .wp-head { font-family: var(--jp); font-size: 23px; font-weight: 700; color: #FFFFFF; }
  .wp-kana { font-family: var(--jp); font-size: 16px; color: #E0DDD6; margin-left: 8px; }
  .wp-pitch { font-size: 14px; color: #8CE0C2; margin-left: 5px; }
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
  .wp-zh { font-size: 18px; font-weight: 700; color: #FFFFFF; margin-bottom: 6px; line-height: 1.45; }
  .wp-tip { font-size: 15px; color: #C4BEB3; line-height: 1.55; }

  /* ================= GOAL 1: GLOBAL DASHBOARD ("总表" - 4 Official N3 Pillars) ================= */
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
      grid-template-columns: 350px 1fr;
      gap: 22px;
      align-items: start;
    }
  }

  .dash-left-col { display: flex; flex-direction: column; gap: 12px; }
  .score-goal-card, .summary-card, .detail-card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px;
    box-shadow: var(--shadow-card);
  }
  .sg-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }
  .sg-title { font-size: 16px; font-weight: 700; color: var(--ink-2); }
  .sg-pct { font-size: 26px; font-weight: 800; color: var(--green); font-variant-numeric: tabular-nums; }
  .sg-bar {
    height: 10px;
    background: var(--subtle);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 8px;
  }
  .sg-fill { height: 100%; background: var(--green-bright); border-radius: 999px; transition: width 0.3s ease; }
  .sg-sub { font-size: 14px; color: var(--ink-2); line-height: 1.5; }

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
  .sum-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .sum-title { font-size: 16.5px; font-weight: 700; color: var(--ink); }
  .sum-nums { font-size: 14px; font-weight: 600; color: var(--ink-2); font-variant-numeric: tabular-nums; }
  .tri-bar { height: 8px; background: var(--subtle); border-radius: 999px; overflow: hidden; display: flex; }
  .tri-seg-done { background: var(--green-bright); height: 100%; }
  .tri-seg-wip { background: #D9A441; height: 100%; }
  .tri-seg-todo { background: var(--red); height: 100%; }

  @media (min-width: 900px) {
    .mobile-only-mod-tabs { display: none !important; }
  }
  .mod-tabs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    margin-bottom: 12px;
  }
  .mod-tab {
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--ink-2);
    font-family: var(--sans);
    font-size: 14.5px;
    font-weight: 700;
    padding: 8px 4px;
    border-radius: 11px;
    cursor: pointer;
    text-align: center;
  }
  .mod-tab.active { background: var(--ink); color: #FFFFFF; border-color: var(--ink); }

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
  .tier-tab.active { background: var(--card); color: var(--ink); font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }

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

  .point-list { display: flex; flex-direction: column; }
  .pt-item { padding: 14px 6px; border-bottom: 1px solid var(--line); cursor: pointer; }
  .pt-item:last-child { border-bottom: none; }
  .pt-main { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .pt-left { display: flex; align-items: center; gap: 9px; min-width: 0; }
  .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .dot.todo { background: var(--red); }
  .dot.wip { background: #D9A441; }
  .dot.done { background: var(--green-bright); }
  .pt-name { font-family: var(--jp); font-size: 17.5px; font-weight: 600; color: var(--ink); }
  .pt-right { display: flex; align-items: center; gap: 7px; max-width: 58%; }
  .pt-sub {
    font-size: 14.5px;
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
    padding: 5px 10px;
    border-radius: 999px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .pt-audio-btn {
    border: none;
    background: var(--subtle);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 600;
    padding: 5px 9px;
    border-radius: 999px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .pt-note { margin-top: 8px; padding-left: 18px; font-size: 15px; color: var(--ink-2); line-height: 1.55; }

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
  .done-title { font-size: 24px; font-weight: 800; color: var(--green); margin: 0 0 10px; }
  .done-sub { font-size: 17px; color: var(--ink-2); margin: 0 0 24px; line-height: 1.6; }
</style>
</head>
<body>
<div class="app-shell">
  <header class="app-header">
    <div class="brand-left">
      <span class="n3-seal">N3</span>
      <span class="countdown" id="countdown-txt">距考试 <strong>22</strong> 天</span>
    </div>
    <div class="header-right">
      <button class="walk-icon-btn" id="walk-btn" onclick="toggleWalkMode()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
        <span id="walk-btn-label">随身听</span>
      </button>
      <div class="mode-switch" role="tablist">
        <button class="mode-btn active" id="tab-tutor" onclick="switchMode('tutor')">今日学习</button>
        <button class="mode-btn" id="tab-dash" onclick="switchMode('dash')">总表</button>
      </div>
    </div>
  </header>

  <!-- VIEW 1: ADAPTIVE LEARNING + ALL-GREEN MISSION BOARD -->
  <main class="tutor-wrap" id="tutor-view">
    <div class="green-mission-board" onclick="openSessionModal()">
      <div class="gm-top">
        <span class="gm-left" id="gm-left-txt">今日全绿通关 <strong>0 / 50</strong></span>
        <span class="gm-right" id="gm-right-txt">120分把握 <strong>66%</strong></span>
      </div>
      <div class="gm-cells" id="gm-cells"></div>
    </div>

    <div class="tutor-scroll" id="tutor-scroll">
      <div class="voice-card" id="voice-card"></div>
    </div>

    <footer class="studio-footer">
      电脑快捷键：Space 播放/重听 · 1/2/3 作答 · Enter 继续 · S 语速
    </footer>
  </main>

  <!-- VIEW 2: UNIFIED 4-PILLAR DASHBOARD ("总表") -->
  <section class="dash-wrap" id="dash-view">
    <div class="dash-left-col">
      <div class="score-goal-card">
        <div class="sg-head">
          <span class="sg-title">冲刺 120+ 分当前把握度</span>
          <span class="sg-pct" id="dash-readiness-pct">66%</span>
        </div>
        <div class="sg-bar"><div class="sg-fill" id="dash-readiness-fill" style="width:66%"></div></div>
        <div class="sg-sub" id="dash-readiness-sub">按真题分值权重计算（阅读基础已稳，当前集中补齐听力60分与高分语法活用盲区）。</div>
      </div>
      <div class="summary-card" id="dash-summary"></div>
    </div>

    <div class="detail-card">
      <div class="mod-tabs mobile-only-mod-tabs" id="mod-tabs"></div>
      <div class="tier-tabs" id="tier-tabs"></div>
      <input type="search" class="search-input" id="pt-search" placeholder="搜语法、活用或词汇…" oninput="renderMasteryList()" />
      <div class="point-list" id="point-list"></div>
    </div>
  </section>
</div>

<div class="sheet-backdrop" id="sheet-backdrop" onclick="hideWordPopover()"></div>
<div class="word-popover" id="word-popover"></div>

<div class="modal-overlay" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-box" id="modal-content"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.2, 1.3, 1.5];
const ADAPTIVE_KEY = "n3_adaptive_v7_" + DATA.plan_date;

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.3");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.3;

let activeKind = null;

// Instant Web Auto-Sync (Zero Manual Cache Clearing)
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
    const diff = Math.round((Date.UTC(2026, 11, 6) - Date.UTC(y, m - 1, d)) / 86400000);
    return diff >= 0 ? diff : 0;
  } catch (e) {
    return DATA.days_to_exam;
  }
}

// ================= REAL-TIME ADAPTIVE ENGINE =================
function createFreshAdaptiveState() {
  const pts = {};
  DATA.points.forEach(p => {
    pts[p.id] = {
      status: "unseen",            // "unseen" (gray) -> "learning" (amber) -> "green" (done)
      needsTeach: !!p.initial_weak, // Weak points ALWAYS teach knowledge card first, quiz 4 steps later!
      variantIdx: 0,
      useVariant: false,
      dueStep: 0,
      wrongCount: 0
    };
  });
  return {
    step: 0,
    lastPointId: null,
    hotFamily: null,
    pts: pts,
    masteryOverrides: {}
  };
}

function loadAdaptiveState() {
  const base = createFreshAdaptiveState();
  try {
    const raw = localStorage.getItem(ADAPTIVE_KEY);
    if (raw) {
      const saved = JSON.parse(raw);
      if (saved && saved.pts) {
        base.step = saved.step || 0;
        base.lastPointId = saved.lastPointId || null;
        base.hotFamily = saved.hotFamily || null;
        base.masteryOverrides = saved.masteryOverrides || {};
        Object.keys(base.pts).forEach(id => {
          if (saved.pts[id]) Object.assign(base.pts[id], saved.pts[id]);
        });
      }
    }
  } catch (e) {}
  return base;
}

let A = loadAdaptiveState();

function saveAdaptiveState() {
  try {
    localStorage.setItem(ADAPTIVE_KEY, JSON.stringify(A));
  } catch (e) {}
}

function applyMasteryOverrides() {
  const ov = A.masteryOverrides || {};
  Object.keys(DATA.mastery).forEach(mod => {
    DATA.mastery[mod].items.forEach(it => {
      const tier = ov[it.key] || ov[it.name];
      if (tier) it.tier = tier;
    });
  });
}
applyMasteryOverrides();

// Exam-Weighted 120-Point Readiness Model (Reading 60pt strong baseline + 4 Tracked N3 Pillars)
function compute120ReadinessPct() {
  let earnedPts = 47.0; // Reading comprehension strong baseline (~78-81% of 60 pts)
  Object.keys(DATA.mastery).forEach(modKey => {
    const mod = DATA.mastery[modKey];
    const items = mod.items;
    if (!items.length) return;
    let sum = 0;
    items.forEach(it => {
      if (it.tier === "done") sum += 1.0;
      else if (it.tier === "wip") sum += 0.58;
      else sum += 0.12;
    });
    const ratio = sum / items.length;
    earnedPts += ratio * mod.exam_pts * 0.72;
  });
  // Direct high-ROI boost from today's 50 core exam points turning green
  let greenWeight = 0;
  let totalWeight = 0;
  DATA.points.forEach(p => {
    totalWeight += p.exam_weight;
    const st = A.pts[p.id] ? A.pts[p.id].status : "unseen";
    if (st === "green") greenWeight += p.exam_weight;
    else if (st === "learning") greenWeight += p.exam_weight * 0.35;
  });
  const missionRatio = greenWeight / Math.max(1, totalWeight);
  const estScore = earnedPts + missionRatio * 20.5;
  const pct = Math.min(99, Math.max(55, Math.round((estScore / 125.0) * 100)));
  return pct;
}

// Pick the optimal next point & card mode ("teach" vs "quiz") based on current mastery & confusion graph
function selectNextPointId(forcedId) {
  if (forcedId && A.pts[forcedId] && A.pts[forcedId].status !== "green") {
    return forcedId;
  }
  const remaining = DATA.points.filter(p => A.pts[p.id].status !== "green");
  if (!remaining.length) return null;
  if (remaining.length === 1) return remaining[0].id;

  const nonRepeat = remaining.filter(p => p.id !== A.lastPointId);
  const pool = nonRepeat.length ? nonRepeat : remaining;

  // 1. Due spaced quizzes (learned Teach Card 4+ steps ago, or due Reverse-Angle Variant after mistake!)
  const dueQuizzes = pool.filter(p => {
    const s = A.pts[p.id];
    return s.status === "learning" && !s.needsTeach && s.dueStep <= A.step;
  });
  if (dueQuizzes.length) {
    dueQuizzes.sort((a, b) => A.pts[a.id].dueStep - A.pts[b.id].dueStep || b.roi_score - a.roi_score);
    return dueQuizzes[0].id;
  }

  // 2. Confusion-Family Pivot: if user just missed a point in family F, pull a ready sibling in family F!
  if (A.hotFamily) {
    const famSiblings = pool.filter(p => p.family === A.hotFamily && A.pts[p.id].dueStep <= A.step);
    if (famSiblings.length) {
      return famSiblings[0].id;
    }
  }

  // 3. Next highest Exam-Weight x Weakness point whose dueStep <= A.step
  const ready = pool.filter(p => A.pts[p.id].dueStep <= A.step);
  if (ready.length) {
    return ready[0].id;
  }

  // 4. Near end of session when only a couple cooling-down items remain: pick earliest dueStep
  pool.sort((a, b) => A.pts[a.id].dueStep - A.pts[b.id].dueStep);
  return pool[0].id;
}

let curPointId = selectNextPointId();
let viewStage = "active"; // "teach" | "quiz" | "result" | "done"
let activeQuizObj = null;
let currentChoices = [];
let pickedVal = null;
let quizShownAt = Date.now();
let walkMode = false;
let walkTimer = null;
let thinkingCountdown = 0;
let activeMode = "tutor";
let wakeLockSentinel = null;

function getPointById(pid) {
  return DATA.points.find(p => p.id === pid) || null;
}

function getQuizForPoint(p, pState) {
  if (pState.useVariant && p.variants && p.variants.length > 0) {
    return p.variants[pState.variantIdx % p.variants.length];
  }
  return p.primary;
}

function prepareChoices(qObj, salt) {
  const arr = qObj.choices.slice();
  if (!qObj.is_listening && arr.length === 2) {
    let h = salt || 0;
    for (let i = 0; i < qObj.id.length; i++) h = (h * 31 + qObj.id.charCodeAt(i)) >>> 0;
    if (h % 2 === 1) arr.reverse();
  }
  return arr;
}

function setupCurrentTurn(forcedId) {
  curPointId = selectNextPointId(forcedId);
  pickedVal = null;
  const sc = document.getElementById("tutor-scroll");
  if (sc) sc.scrollTop = 0;

  if (!curPointId) {
    viewStage = "done";
    activeQuizObj = null;
    return;
  }
  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];
  if (ps.needsTeach && !walkMode) {
    viewStage = "teach";
    activeQuizObj = null;
  } else {
    viewStage = "quiz";
    activeQuizObj = getQuizForPoint(p, ps);
    currentChoices = prepareChoices(activeQuizObj, ps.wrongCount);
    quizShownAt = Date.now();
  }
}
setupCurrentTurn();

const player = new Audio();
player.preload = "auto";
const wordPlayer = new Audio();
wordPlayer.preload = "auto";

const DICT_KEYS = Object.keys(DATA.words).sort((a, b) => b.length - a.length);

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
  const rate = (kind === "exp" || kind === "teach" || kind === "done") ? expSpeed : 1.0;
  player.defaultPlaybackRate = rate;
  player.playbackRate = rate;
  if ("preservesPitch" in player) player.preservesPitch = true;
  if ("webkitPreservesPitch" in player) player.webkitPreservesPitch = true;
}

function cycleExpSpeed() {
  expSpeed = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  try { localStorage.setItem("n3_exp_speed", String(expSpeed)); } catch (e) {}
  if (activeKind === "exp" || activeKind === "teach") applyPlaybackRate(activeKind);
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
  syncAudioButtons();
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
  const pr = player.play();
  if (pr && typeof pr.catch === "function") {
    pr.catch(() => {
      activeKind = null;
      syncAudioButtons();
    });
  }
  syncAudioButtons();
}

player.addEventListener("play", () => {
  applyPlaybackRate(activeKind);
  syncAudioButtons();
});
player.addEventListener("pause", syncAudioButtons);
player.addEventListener("ended", () => {
  const finishedKind = activeKind;
  activeKind = null;
  syncAudioButtons();

  if (!walkMode || activeMode !== "tutor" || viewStage === "done") return;
  if (finishedKind === "q" && viewStage === "quiz") {
    thinkingCountdown = 4;
    syncAudioButtons();
    walkTimer = setInterval(() => {
      thinkingCountdown -= 1;
      syncAudioButtons();
      if (thinkingCountdown <= 0) {
        clearWalkTimer();
        if (walkMode && viewStage === "quiz" && activeQuizObj) {
          submitAnswer(activeQuizObj.answer, true);
        }
      }
    }, 900);
  } else if (finishedKind === "exp" && viewStage === "result") {
    walkTimer = setTimeout(() => {
      if (walkMode && viewStage === "result") advanceNext(false);
    }, 900);
  }
});

function syncAudioButtons() {
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
      cap.textContent = (activeQuizObj && activeQuizObj.is_listening) ? "点此听对话" : "点此听题";
    }
  }
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    const on = (activeKind === "exp" || activeKind === "teach") && !player.paused;
    repBtn.classList.toggle("playing", on);
    repBtn.textContent = on ? "暂停讲解" : (viewStage === "teach" ? "听讲解" : "重听讲解");
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

function toggleWalkMode(forceState) {
  walkMode = typeof forceState === "boolean" ? forceState : !walkMode;
  const btn = document.getElementById("walk-btn");
  const lbl = document.getElementById("walk-btn-label");
  if (btn) btn.classList.toggle("active", walkMode);
  if (lbl) lbl.textContent = walkMode ? "随身听中" : "随身听";
  requestWakeLock(walkMode);

  stopAudio();
  setupCurrentTurn(curPointId);
  renderTutor();
  if (walkMode && activeQuizObj) {
    playMainClip(activeQuizObj.q_audio, "q", false);
  }
}

function syncBackendRecord(p, qid, choice, isCorrect, askAgain, newTier) {
  A.masteryOverrides[p.point_key] = newTier;
  A.masteryOverrides[p.point] = newTier;
  applyMasteryOverrides();
  saveAdaptiveState();

  const rec = {
    id: qid,
    point: p.point_key || p.point,
    choice: String(choice || ""),
    correct: String(!!isCorrect),
    ask_again: String(!!askAgain),
    ts: new Date().toISOString()
  };
  if (location.protocol.startsWith("http")) {
    fetch("./api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rec)
    }).catch(() => {});
  }
}

// Step 1A: User finishes studying a Knowledge Teaching Card -> schedule real Quiz 4 steps later!
function completeTeachCard() {
  stopAudio();
  hideWordPopover();
  const p = getPointById(curPointId);
  if (p) {
    const ps = A.pts[p.id];
    ps.status = "learning";
    ps.needsTeach = false;
    ps.dueStep = A.step + 4; // Spaced retrieval: come back 4 steps later to test!
    A.step += 1;
    A.lastPointId = p.id;
    A.hotFamily = null;
    saveAdaptiveState();
  }
  setupCurrentTurn();
  renderTutor();
  autoPlayCurrentTurn();
}

// If user taps "不确定，先看知识点" on a semi-familiar Quiz -> flip immediately to its Knowledge Card!
function switchToTeachForCurrent() {
  stopAudio();
  hideWordPopover();
  const p = getPointById(curPointId);
  if (!p) return;
  const ps = A.pts[p.id];
  ps.status = "learning";
  ps.needsTeach = true;
  ps.wrongCount += 1;
  if (p.variants && p.variants.length > 0) {
    ps.useVariant = true; // Next quiz will use a fresh angle!
  }
  A.hotFamily = p.family;
  syncBackendRecord(p, activeQuizObj ? activeQuizObj.id : p.id, "先学考点", false, false, "todo");
  viewStage = "teach";
  renderTutor();
  playMainClip(p.teach.audio, "teach", false);
}

let lastFromWalk = false;

// Step 1B: User answers a Quiz -> Adaptive Engine updates Green Matrix & schedules next path!
function submitAnswer(val, fromWalk) {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  hideWordPopover();
  stopAudio();
  pickedVal = val;
  lastFromWalk = !!fromWalk;
  viewStage = "result";

  const p = getPointById(curPointId);
  const ps = A.pts[p.id];
  const isCorrect = (val === activeQuizObj.answer);

  if (fromWalk) {
    // Passive Walk Mode: warm up point and cycle through all 50 points without faking green mastery!
    if (ps.status === "unseen") {
      ps.status = "learning";
      ps.needsTeach = false;
    }
    ps.dueStep = A.step + DATA.points.length;
  } else if (isCorrect) {
    ps.status = "green"; // Cell turns SOLID EMERALD GREEN!
    ps.needsTeach = false;
    A.hotFamily = null;
    syncBackendRecord(p, activeQuizObj.id, val, true, false, "done");
  } else {
    // Wrong: stays Amber, activates Confusion-Family contrast next, and schedules Reverse-Angle Variant 4 steps later!
    ps.status = "learning";
    ps.needsTeach = false;
    ps.wrongCount += 1;
    if (p.variants && p.variants.length > 0) {
      if (ps.useVariant) ps.variantIdx += 1;
      ps.useVariant = true;
    }
    ps.dueStep = A.step + 4;
    A.hotFamily = p.family;
    syncBackendRecord(p, activeQuizObj.id, val, false, false, "todo");
  }

  A.step += 1;
  A.lastPointId = p.id;
  saveAdaptiveState();

  renderTutor();
  playMainClip(activeQuizObj.exp_audio, "exp", false);
}

function advanceNext(forceRetestCurrent) {
  stopAudio();
  hideWordPopover();
  if (forceRetestCurrent && curPointId) {
    const p = getPointById(curPointId);
    const ps = A.pts[curPointId];
    ps.status = "learning";
    ps.needsTeach = false;
    if (p && p.variants && p.variants.length > 0) ps.useVariant = true;
    ps.dueStep = A.step + 4;
    if (p) syncBackendRecord(p, p.id, pickedVal, false, true, "todo");
  }
  setupCurrentTurn();
  renderTutor();
  autoPlayCurrentTurn();
}

function autoPlayCurrentTurn() {
  if (viewStage === "teach") {
    const p = getPointById(curPointId);
    if (p && p.teach.audio) playMainClip(p.teach.audio, "teach", false);
  } else if (viewStage === "quiz" && activeQuizObj && activeQuizObj.q_audio) {
    playMainClip(activeQuizObj.q_audio, "q", false);
  } else if (viewStage === "done") {
    playMainClip(DATA.done_audio, "done", false);
  }
}

function jumpToPointById(pid) {
  if (!pid || !A.pts[pid]) return;
  stopAudio();
  if (A.pts[pid].status === "green") {
    A.pts[pid].status = "learning";
    A.pts[pid].needsTeach = false;
    A.pts[pid].dueStep = A.step;
  }
  setupCurrentTurn(pid);
  switchMode("tutor");
  renderTutor();
  autoPlayCurrentTurn();
}

function resetTodayMission() {
  stopAudio();
  const keepOverrides = A.masteryOverrides || {};
  A = createFreshAdaptiveState();
  A.masteryOverrides = keepOverrides;
  saveAdaptiveState();
  closeModal();
  setupCurrentTurn();
  renderTutor();
}

function renderGreenBoard() {
  document.getElementById("countdown-txt").innerHTML = `距考试 <strong>${computeDaysLeft()}</strong> 天`;
  const total = DATA.points.length;
  let greenCnt = 0;
  const cellsHTML = DATA.points.map(p => {
    const st = A.pts[p.id].status;
    if (st === "green") greenCnt += 1;
    let cls = "gm-cell";
    if (st === "green") cls += " green";
    else if (st === "learning") cls += " learning";
    if (p.id === curPointId && viewStage !== "done") cls += " current";
    return `<div class="${cls}"></div>`;
  }).join("");

  const readiness = compute120ReadinessPct();
  document.getElementById("gm-left-txt").innerHTML = `今日全绿通关 <strong>${greenCnt} / ${total}</strong>`;
  document.getElementById("gm-right-txt").innerHTML = `120分把握 <strong>${readiness}%</strong>`;
  document.getElementById("gm-cells").innerHTML = cellsHTML;
}

function renderTutor() {
  renderGreenBoard();
  const box = document.getElementById("voice-card");

  if (viewStage === "done" || !curPointId) {
    const readiness = compute120ReadinessPct();
    box.innerHTML = `
      <div class="done-wrap">
        <h2 class="done-title">50 格全部变绿！今日通关</h2>
        <p class="done-sub">今天最重要的 50 个 N3 核心提分考点已全部拿下，冲刺 120+ 把握度已推升至 <strong>${readiness}%</strong>。安心去睡觉吧！</p>
        <div class="nav-row">
          <button class="again-btn" onclick="switchMode('dash')">看全局总表</button>
          <button class="next-btn" onclick="resetTodayMission()">再刷一轮</button>
        </div>
      </div>
    `;
    return;
  }

  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];

  // -------- CARD 1: TEACH KNOWLEDGE POINT FIRST (When Mastery is Low!) --------
  if (viewStage === "teach") {
    warmAudio(p.teach.audio);
    warmAudio(p.primary.q_audio);
    box.innerHTML = `
      <div class="card-top-row">
        <span class="stage-pill teach">${escapeHtml(p.subject)} · 先记考点（稍后考你）</span>
        <div style="display:flex;gap:6px;">
          <button class="mini-audio-btn" id="exp-replay-btn" onclick="playMainClip('${p.teach.audio}', 'teach', true)">听讲解</button>
          <button class="mini-audio-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed.toFixed(1)}x</button>
        </div>
      </div>

      <h2 class="teach-title">${escapeHtml(p.point)}</h2>

      <div class="contrast-stack">
        <div class="contrast-item primary">
          <div class="ci-ja">✓ ${escapeHtml(p.teach.left.ja)}</div>
          <div class="ci-sub">${escapeHtml(p.teach.left.sub)}</div>
        </div>
        ${p.teach.right && p.teach.right.ja ? `
        <div class="contrast-item">
          <div class="ci-ja">↔ ${escapeHtml(p.teach.right.ja)}</div>
          <div class="ci-sub">${escapeHtml(p.teach.right.sub)}</div>
        </div>` : ""}
      </div>

      <div class="core-rule-box">${escapeHtml(p.teach.rule)}</div>

      <div class="full-sentence-box">
        <div class="full-sentence-hint">
          <span>代表例句</span>
          <span>点划线词看意思·听发音</span>
        </div>
        <div class="full-sentence-ja">${annotateJapanese(p.teach.example_ja)}</div>
      </div>

      <div class="nav-row">
        <button class="next-btn" onclick="completeTeachCard()">记住了，继续 → <span class="kbd-hint">Enter</span></button>
      </div>
    `;
    syncAudioButtons();
    return;
  }

  // -------- CARD 2: ADAPTIVE QUIZ (Primary or Reverse-Angle Variant) --------
  if (viewStage === "quiz" && activeQuizObj) {
    warmAudio(activeQuizObj.q_audio);
    warmAudio(activeQuizObj.exp_audio);
    const isVariant = activeQuizObj.id !== p.primary.id;
    const pillCls = isVariant ? "stage-pill variant" : "stage-pill quiz";
    const pillTxt = isVariant ? `${escapeHtml(p.subject)} · 换角度复检` : `${escapeHtml(p.subject)} · 实战检验`;

    const choicesHTML = currentChoices.map((c, cIdx) => `
      <button class="choice-btn" onclick='submitAnswer(${JSON.stringify(c)}, false)'>
        <span>${escapeHtml(c)}</span>
        <span class="kbd-hint">${cIdx + 1}</span>
      </button>
    `).join("");

    box.innerHTML = `
      <div class="card-top-row">
        <span class="${pillCls}">${pillTxt}</span>
        <span></span>
      </div>
      <div class="orb-stage">
        <button class="voice-orb ${activeQuizObj.is_listening ? 'listening-emphasis' : ''}" id="voice-orb" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)" aria-label="播放题目">
          <svg class="orb-play-ic" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>
          <div class="orb-bars"><span></span><span></span><span></span><span></span></div>
        </button>
        <div class="orb-caption" id="orb-caption">${activeQuizObj.is_listening ? "点此听对话" : "点此听题"}</div>
      </div>
      <p class="prompt-cue ${activeQuizObj.is_listening ? 'is-listening-cue' : ''}">${escapeHtml(activeQuizObj.prompt)}</p>
      <div class="choices-stack">
        ${choicesHTML}
      </div>
      ${!walkMode ? `<button class="skip-btn" onclick="switchToTeachForCurrent()">没把握，先看知识点</button>` : ""}
    `;
    syncAudioButtons();
    return;
  }

  // -------- CARD 3: INSTANT RESULT + ADAPTIVE NEXT ROUTING --------
  const q = activeQuizObj || p.primary;
  const isCorrect = pickedVal === q.answer;
  const verdictCls = isCorrect ? "ok" : "ng";
  const verdictTxt = lastFromWalk
    ? "随身听精讲 · 亲手答对即变绿"
    : (isCorrect ? "✓ 答对了 · 本格已变绿！" : "✕ 答错了 · 稍后换角度再考");

  let wrongBoxHTML = "";
  if (!isCorrect && pickedVal) {
    const wNote = (q.option_notes && q.option_notes[pickedVal]) || "语义或接续不符";
    wrongBoxHTML = `
      <div class="ans-wrong-box">
        <span class="ans-wrong-head">✕ ${annotateJapanese(pickedVal)}</span>
        <span>${escapeHtml(wNote)}</span>
      </div>
    `;
  }

  box.innerHTML = `
    <div id="answer-zone">
      <div class="card-top-row">
        <span class="verdict-badge ${verdictCls}">${verdictTxt}</span>
        <div style="display:flex;gap:6px;">
          <button class="mini-audio-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">原题</button>
          <button class="mini-audio-btn" id="exp-replay-btn" onclick="playMainClip(activeQuizObj.exp_audio, 'exp', true)">重听讲解</button>
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

      <div class="nav-row">
        ${isCorrect ? `<button class="again-btn" onclick="advanceNext(true)">还不稳，再考</button>` : ""}
        <button class="next-btn" onclick="advanceNext(false)">继续 → <span class="kbd-hint">Enter</span></button>
      </div>
    </div>
  `;
  syncAudioButtons();
}

// ================= WORD DICTIONARY POPOVER =================
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
        <span class="wp-kana">${escapeHtml(info.kana || "")}</span>
        <span class="wp-pitch">${escapeHtml(info.pitch || "")}</span>
      </div>
      ${hasAudio ? `<button class="wp-speak" onclick='playWordAudio(${JSON.stringify(surface)})'>发音</button>` : ""}
    </div>
    ${info.pos ? `<div class="wp-pos">${escapeHtml(info.head && info.head !== surface ? "原形 " + info.head + " · " + info.pos : info.pos)}</div>` : ""}
    <div class="wp-zh">${escapeHtml(info.zh || "")}</div>
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
  if (!tok || (viewStage !== "result" && viewStage !== "teach")) return;
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
  if (tok && (viewStage === "result" || viewStage === "teach")) {
    e.stopPropagation();
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
  if (e.key === "/" && activeMode === "dash") {
    e.preventDefault();
    const sEl = document.getElementById("pt-search");
    if (sEl) sEl.focus();
    return;
  }
  if (activeMode !== "tutor") return;

  if (e.key.toLowerCase() === "s") {
    e.preventDefault();
    cycleExpSpeed();
    return;
  }

  if (viewStage === "teach") {
    const p = getPointById(curPointId);
    if (e.key === " ") {
      e.preventDefault();
      if (p) playMainClip(p.teach.audio, "teach", true);
    } else if (e.key === "Enter" || e.key === "ArrowRight") {
      e.preventDefault();
      completeTeachCard();
    }
    return;
  }

  if (viewStage === "quiz" && activeQuizObj) {
    if (e.key === " ") {
      e.preventDefault();
      playMainClip(activeQuizObj.q_audio, "q", true);
    } else if (e.key === "1" && currentChoices[0]) {
      e.preventDefault();
      submitAnswer(currentChoices[0], false);
    } else if (e.key === "2" && currentChoices[1]) {
      e.preventDefault();
      submitAnswer(currentChoices[1], false);
    } else if (e.key === "3" && currentChoices[2]) {
      e.preventDefault();
      submitAnswer(currentChoices[2], false);
    } else if (e.key === "0") {
      e.preventDefault();
      switchToTeachForCurrent();
    }
    return;
  }

  if (viewStage === "result" && activeQuizObj) {
    if (e.key === " ") {
      e.preventDefault();
      playMainClip(activeQuizObj.exp_audio, "exp", true);
    } else if (e.key === "Enter" || e.key === "ArrowRight") {
      e.preventDefault();
      advanceNext(false);
    }
  }
});

// ================= GOAL 1: UNIFIED 4-PILLAR DASHBOARD ("总表") =================
let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

function switchMode(m) {
  activeMode = m;
  hideWordPopover();
  if (m === "dash") stopAudio();
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-dash").classList.toggle("active", m === "dash");
  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("dash-view").classList.toggle("active", m === "dash");
  if (m === "dash") renderDashboard();
  else renderGreenBoard();
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
  const readiness = compute120ReadinessPct();
  document.getElementById("dash-readiness-pct").textContent = `${readiness}%`;
  document.getElementById("dash-readiness-fill").style.width = `${readiness}%`;

  const order = ["grammar", "henkei", "listening", "vocab"];
  document.getElementById("dash-summary").innerHTML = order.map(k => {
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

  document.getElementById("mod-tabs").innerHTML = order.map(k => {
    const m = DATA.mastery[k];
    return `<button class="mod-tab ${dashMod === k ? "active" : ""}" onclick="selectDashMod('${k}')">${m.short}</button>`;
  }).join("");

  const curCounts = DATA.mastery[dashMod].counts;
  document.getElementById("tier-tabs").innerHTML = `
    <button class="tier-tab ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待练 ${curCounts.todo}</button>
    <button class="tier-tab ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固 ${curCounts.wip}</button>
    <button class="tier-tab ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已会 ${curCounts.done}</button>
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
          ${it.audio ? `<button class="pt-audio-btn" onclick="event.stopPropagation();playDirectUrl('${it.audio}')">发音</button>` : ""}
          ${it.point_id ? `<button class="pt-jump-btn" onclick="event.stopPropagation();jumpToPointById('${it.point_id}')">去练</button>` : ""}
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
  const greenCnt = DATA.points.filter(p => A.pts[p.id].status === "green").length;
  const learningCnt = DATA.points.filter(p => A.pts[p.id].status === "learning").length;
  const readiness = compute120ReadinessPct();
  const el = document.getElementById("modal-content");
  el.innerHTML = `
    <h3 class="modal-title">今日冲刺 120+ 进度</h3>
    <p class="modal-p">
      已变绿过关：<strong>${greenCnt} / ${DATA.points.length}</strong> 格<br/>
      已看考点待考：<strong>${learningCnt}</strong> 格<br/>
      当前 120 分把握度：<strong>${readiness}%</strong><br/>
      <span style="font-size:14.5px;color:var(--ink-3);">把上面 50 格全部刷成绿色，今天就能安心睡觉了。</span>
    </p>
    <div class="modal-actions">
      <button class="again-btn" onclick="resetTodayMission()">重置今日绿格</button>
      <button class="next-btn" onclick="closeModal()">继续通关</button>
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
}

initApp();
</script>
</body>
</html>
"""

final_html = html.replace("__PAYLOAD__", payload)
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(final_html)
print(
    "Wrote Adaptive 120+ N3 Platform:",
    HTML_PATH,
    "points:",
    len(ordered_points),
    "size:",
    len(final_html),
)
