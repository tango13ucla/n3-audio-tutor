#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the Japanese Zen Edition of the JLPT N3 Adaptive & Two-Host Radio Platform (index.html — v9).
Aesthetic Philosophy: 禅 (Zen) · 余白 (Ma) · 墨と和紙 (Sumi & Washi) · 幾何学整列 (Strict Grid Precision)
- Zero nested boxes, zero biscuit pills, zero emoji clutter, zero vibration, zero line-wrap.
- Strict symmetric vertical gridlines, tabular numerals, traditional Japanese pigments (生成り · 墨 · 苔緑 · 弁柄).
- Unified Master Algorithm linking 35-40m Two-Host Chinese-Japanese Radio (`audioPrimed`) <-> Short-Time Adaptive Quiz.
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
from radio_dialogue_bank import MODALITY_MAP
from tutor_data import TUTOR_ITEMS, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
AUDIO_MANIFEST_PATH = os.path.join(BASE_DIR, "audio", "audio_manifest.json")
RADIO_META_PATH = os.path.join(BASE_DIR, "audio", "daily_radio_meta.json")

plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
with open(plans[-1], encoding="utf-8") as f:
    plan = json.load(f)

with open(STATE_PATH, encoding="utf-8") as f:
    live_state = json.load(f)

audio_manifest = {}
if os.path.exists(AUDIO_MANIFEST_PATH):
    with open(AUDIO_MANIFEST_PATH, encoding="utf-8") as f:
        audio_manifest = json.load(f)

radio_meta = {
    "date": live_state.get("updated_at", "2026-11-14")[:10],
    "display_date": "今日",
    "audio_url": "./audio/daily_radio.mp3",
    "duration_sec": 2220.0,
    "duration_label": "37 分钟",
    "hosts": "阿哲 · 小夏",
    "chapters": [
        {"idx": 0, "title": "深聊", "start": 0},
        {"idx": 1, "title": "听力", "start": 1350},
        {"idx": 2, "title": "词汇", "start": 1700},
        {"idx": 3, "title": "纯日", "start": 2050},
    ],
    "segments": [],
}
if os.path.exists(RADIO_META_PATH):
    try:
        with open(RADIO_META_PATH, encoding="utf-8") as f:
            loaded_rm = json.load(f)
            if loaded_rm.get("audio_url"):
                radio_meta = loaded_rm
    except Exception:
        pass

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

SUBJ_CN = {"文法": "语法", "活用": "活用", "語彙": "词汇", "聴解": "听力"}


def strip_opt_prefix(s: str) -> str:
    return re.sub(r"^[a-dA-D]\.\s*", "", str(s)).strip()


def clean_zen_text(s: str) -> str:
    txt = str(s or "").strip()
    txt = re.sub(r"[✅❌⭕✕✓↑↓🎧]", "", txt)
    txt = re.sub(
        r"^(?:听力保命铁律|声音\+画面双锚|双重铁证|考场秒杀铁律|考试卷面铁律|秒杀铁律|记忆铁律|一眼锁死助词|看动词时态定画面|这对双胞胎反着记)[：:]\s*",
        "",
        txt,
    )
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"[！!]+$", "。", txt)
    return txt


def clean_ja_head(s: str) -> str:
    txt = re.sub(r"^[✓✕〇×↑↓↔\s]+", "", str(s or "")).strip()
    txt = re.sub(r"[✅❌⭕]+$", "", txt).strip()
    return txt


def clean_prompt(s: str, is_listening: bool) -> str:
    txt = re.sub(r"^🎧\s*", "", str(s or "")).strip()
    if is_listening:
        if any(k in txt for k in ("怎么说", "哪句", "什么意思", "最合适", "怎么回应", "先做什么", "做什么")):
            return clean_zen_text(txt)
        return "听对话，选最自然的回应"
    return txt


def concise_sub(sub_a: str, sub_b: str, fallback: str) -> str:
    parts = [clean_zen_text(x).rstrip("。") for x in (sub_a, sub_b) if x and clean_zen_text(x)]
    if parts:
        joined = " · ".join(parts)
        return joined[:36] + ("…" if len(joined) > 36 else "")
    fb = clean_zen_text(fallback).rstrip("。")
    return fb[:36] + ("…" if len(fb) > 36 else "")


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


variants_by_base = {}
for vc in VARIANT_CARDS:
    meta = audio_manifest.get(f"meta:{vc['id']}", {})
    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if has_mp3_pair(q_rel, exp_rel):
        opt_clean = {k: clean_zen_text(v) for k, v in (vc.get("option_notes") or {}).items()}
        v_obj = {
            "id": vc["id"],
            "prompt": clean_prompt(vc["prompt"], vc["subject"] == "聴解"),
            "choices": vc["choices"],
            "answer": vc["answer"],
            "full_ja": vc["full_ja"],
            "core_rule": clean_zen_text(vc["core_rule"]),
            "option_notes": opt_clean,
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
    modality = MODALITY_MAP.get(qid, "listen" if is_listening else "both")

    raw_micro = t_item.get("micro_lesson") or {}
    opt_notes = {k: clean_zen_text(v) for k, v in (t_item.get("option_notes") or {}).items()}
    core_rule = clean_zen_text(raw_micro.get("hook") or opt_notes.get(answer) or explain)

    left_m = raw_micro.get("left") or {}
    right_m = raw_micro.get("right") or {}
    teach_left = {
        "ja": clean_ja_head(left_m.get("ja") or answer),
        "sub": concise_sub(left_m.get("sub", ""), left_m.get("desc", ""), opt_notes.get(answer, "") or core_rule),
    }
    other_opt = next((c for c in choices if c != answer), "")
    teach_right = {
        "ja": clean_ja_head(right_m.get("ja") or other_opt),
        "sub": concise_sub(right_m.get("sub", ""), right_m.get("desc", ""), opt_notes.get(other_opt, "")),
    }

    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if not has_mp3_pair(q_rel, exp_rel):
        return None

    initial_weak = (pt_status in ("red", "orange", "gray")) and (not is_listening)

    return {
        "id": qid,
        "subject": SUBJ_CN.get(subject, subject),
        "point": display_point,
        "point_key": point_key,
        "family": pmeta["family"],
        "modality": modality,
        "exam_weight": exam_weight,
        "roi_score": roi_score,
        "initial_weak": initial_weak,
        "teach": {
            "left": teach_left,
            "right": teach_right,
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
    tl = {"ja": clean_ja_head(ext["teach_left"]["ja"]), "sub": clean_zen_text(ext["teach_left"]["sub"]).rstrip("。")}
    tr = {"ja": clean_ja_head(ext["teach_right"]["ja"]), "sub": clean_zen_text(ext["teach_right"]["sub"]).rstrip("。")}
    opt_c = {k: clean_zen_text(v) for k, v in (ext.get("option_notes") or {}).items()}
    raw_points.append({
        "id": qid,
        "subject": SUBJ_CN.get(ext["subject"], ext["subject"]),
        "point": ext["point_display"],
        "point_key": ext["point_key"],
        "family": ext["family"],
        "modality": MODALITY_MAP.get(qid, "listen" if is_l else "both"),
        "exam_weight": w,
        "roi_score": round(w * weakness_multiplier(pt_status), 3),
        "initial_weak": (pt_status in ("red", "orange", "gray")) and (not is_l),
        "teach": {
            "left": tl,
            "right": tr,
            "example_ja": ext["full_ja"],
            "audio": exp_rel,
        },
        "primary": {
            "id": qid,
            "prompt": clean_prompt(ext["prompt"], is_l),
            "choices": ext["choices"],
            "answer": ext["answer"],
            "full_ja": ext["full_ja"],
            "core_rule": clean_zen_text(ext["core_rule"]),
            "option_notes": opt_c,
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": is_l,
        },
        "variants": variants_by_base.get(qid, []),
    })

raw_points.sort(key=lambda x: (-x["roi_score"], -x["exam_weight"], x["id"]))
raw_points = raw_points[:50]

buckets = {"语法": [], "活用": [], "词汇": [], "听力": []}
for p in raw_points:
    buckets[p["subject"]].append(p)

ordered_points = []
subj_cycle = ["语法", "活用", "词汇", "听力"]
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
        "note": clean_zen_text(p.get("exam_alert") or p.get("note", "")),
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
        "note": clean_zen_text(p.get("note", "")),
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
        "note": clean_zen_text(p.get("trap", "") or p.get("note", "")),
    })

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
        "note": clean_zen_text(w_info.get("tip") or p.get("classroom_note") or ""),
    })

for kw, pitch, desc in CORE_N3_KANA_VOCAB:
    if kw in seen_vocab_words:
        continue
    seen_vocab_words.add(kw)
    vocab_items.append({
        "key": kw,
        "name": kw,
        "sub": desc.split("（")[0],
        "family": "高频假名副词",
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
    "grammar": {"label": "语法", "detail": "147 核心考点", "exam_pts": 38, "counts": count_tiers(grammar_items), "items": grammar_items},
    "henkei": {"label": "活用与敬语", "detail": "变形与授受尊谦", "exam_pts": 28, "counts": count_tiers(henkei_items), "items": henkei_items},
    "listening": {"label": "听力口语", "detail": "卷面 60 分", "exam_pts": 60, "counts": count_tiers(listening_items), "items": listening_items},
    "vocab": {"label": "核心词汇", "detail": "含常考假名副词", "exam_pts": 24, "counts": count_tiers(vocab_items), "items": vocab_items},
}

payload = json.dumps({
    "plan_date": live_state.get("updated_at", plan.get("plan_date", "2026-11-14"))[:10],
    "exam_date": "2026-12-06",
    "days_to_exam": live_state.get("days_left", plan.get("days_to_exam", 22)),
    "done_audio": "./audio/done.mp3",
    "radio": radio_meta,
    "points": ordered_points,
    "words": rich_words,
    "mastery": mastery_data,
}, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
<meta name="description" content="JLPT N3 · 自适应冲刺与双人随身电台" />
<meta name="theme-color" content="#F5F2EB" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<link rel="manifest" href="./manifest.json" />
<link rel="icon" href="./icon-192.png" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600&family=Noto+Serif+JP:wght@500;600&display=swap" rel="stylesheet" />
<title>N3</title>
<style>
  :root {
    /* Traditional Japanese Pigments (日本の伝統色): 生成り · 白練 · 墨 · 苔色 · 黄土 · 弁柄 */
    --washi: #F5F2EB;
    --sheet: #FCFBF8;
    --sumi: #1C1B18;
    --ink-2: #57534A;
    --ink-3: #8E887C;
    --hairline: rgba(28, 27, 24, 0.09);
    --hairline-strong: rgba(28, 27, 24, 0.18);
    --track: #E5E0D5;
    --moss: #2B5F49;
    --ochre: #B07D3A;
    --bengara: #9E3E36;
    --sans: "Noto Sans JP", -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans", sans-serif;
    --serif-jp: "Noto Serif JP", "Hiragino Mincho ProN", "Noto Sans JP", serif;
  }

  * {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
  }

  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    height: 100dvh;
    overflow: hidden;
    overscroll-behavior: none;
    background: var(--washi);
    color: var(--sumi);
    font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }

  body {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(14px + env(safe-area-inset-top)) 26px calc(18px + env(safe-area-inset-bottom));
  }

  .zen-shell {
    width: 100%;
    max-width: 480px;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  @media (min-width: 860px) {
    body { padding: 32px 48px 32px; }
    .zen-shell { max-width: 560px; }
    .zen-shell.wide-mode { max-width: 780px; }
  }

  button {
    font-family: inherit;
    white-space: nowrap;
    background: none;
    border: none;
    padding: 0;
    color: inherit;
    cursor: pointer;
  }

  /* ================= 1. STRICT GRID HEADER ================= */
  .zen-header {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--hairline);
  }

  .zen-brand {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.06em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .zen-brand strong {
    font-weight: 600;
    color: var(--sumi);
    margin: 0 2px;
  }

  .zen-nav {
    display: flex;
    align-items: baseline;
    gap: 22px;
  }
  .nav-link {
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    padding-bottom: 5px;
    position: relative;
    transition: color 0.2s ease;
  }
  .nav-link.active {
    color: var(--sumi);
    font-weight: 600;
  }
  .nav-link.active::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -15px;
    height: 1.5px;
    background: var(--sumi);
  }
  .nav-link.is-playing {
    color: var(--moss);
  }

  /* ================= 2. ZEN MOSS HORIZON (BEDTIME GREEN GOAL) ================= */
  .zen-horizon {
    flex-shrink: 0;
    padding: 14px 0 4px;
    cursor: pointer;
  }
  .horizon-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
  }
  .horizon-meta b {
    font-weight: 600;
    color: var(--moss);
  }
  .horizon-track {
    width: 100%;
    height: 2.5px;
    background: var(--track);
    position: relative;
    overflow: hidden;
  }
  .horizon-fill {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    background: var(--moss);
    transition: width 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  }

  /* ================= 3. OPEN WASHI STAGE (余白 MA) ================= */
  .zen-panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .zen-panel.hidden {
    display: none;
  }

  .stage-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding-top: 18px;
    animation: fadeTurn 0.18s ease-out;
  }
  @keyframes fadeTurn {
    from { opacity: 0.45; }
    to { opacity: 1; }
  }

  .meta-bar {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 26px;
  }
  .overline {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: var(--ink-3);
  }
  .overline.ok { color: var(--moss); font-weight: 600; }
  .overline.ng { color: var(--bengara); font-weight: 600; }
  .overline.warm { color: var(--ochre); }

  .quiet-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .text-btn {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    font-variant-numeric: tabular-nums;
    padding: 4px 0;
  }
  .text-btn.playing {
    color: var(--moss);
    font-weight: 600;
  }

  /* Center focal space with generous Ma (whitespace) */
  .focal-space {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 16px 0;
    scrollbar-width: none;
  }
  .focal-space::-webkit-scrollbar { display: none; }

  .action-dock {
    flex-shrink: 0;
    padding-top: 12px;
  }

  /* -------- TEACH VIEW -------- */
  .point-heading {
    margin: 0 0 22px;
    font-family: var(--serif-jp);
    font-size: 27px;
    font-weight: 600;
    line-height: 1.35;
    letter-spacing: 0.03em;
    color: var(--sumi);
  }
  .zen-pair {
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 22px;
  }
  .zen-pair-row {
    padding: 14px 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .zen-pair-row + .zen-pair-row {
    border-top: 1px solid var(--hairline);
  }
  .zp-ja {
    font-family: var(--serif-jp);
    font-size: 20px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.02em;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .zp-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--moss);
    flex-shrink: 0;
  }
  .zp-dot.muted {
    background: transparent;
    border: 1.5px solid var(--ink-3);
  }
  .zp-sub {
    padding-left: 16px;
    font-size: 14.5px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.5;
  }

  .example-line {
    font-family: var(--serif-jp);
    font-size: 20.5px;
    font-weight: 500;
    line-height: 1.78;
    letter-spacing: 0.03em;
    color: var(--sumi);
    white-space: pre-line;
  }

  /* -------- QUIZ VIEW -------- */
  .quiz-focal {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 140px;
    margin-bottom: 28px;
  }
  .quiz-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 24.5px;
    font-weight: 600;
    line-height: 1.68;
    letter-spacing: 0.03em;
    color: var(--sumi);
  }
  @media (min-width: 860px) {
    .quiz-ja { font-size: 27px; }
  }

  .listen-medallion-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
    padding: 12px 0;
  }
  .listen-medallion {
    width: 68px;
    height: 68px;
    border-radius: 50%;
    border: 1px solid var(--hairline-strong);
    background: var(--sheet);
    color: var(--sumi);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: border-color 0.2s ease, transform 0.15s ease;
  }
  .listen-medallion:active { transform: scale(0.96); }
  .listen-medallion.speaking {
    border-color: var(--moss);
    color: var(--moss);
  }
  .med-ic { width: 24px; height: 24px; margin-left: 2px; }
  .med-waves { display: none; align-items: center; gap: 3.5px; height: 20px; }
  .listen-medallion.speaking .med-ic { display: none; }
  .listen-medallion.speaking .med-waves { display: flex; }
  .med-waves span {
    width: 2.5px;
    height: 8px;
    background: var(--moss);
    animation: zenWave 0.9s ease-in-out infinite;
  }
  .med-waves span:nth-child(2) { animation-delay: 0.16s; }
  .med-waves span:nth-child(3) { animation-delay: 0.32s; }
  @keyframes zenWave {
    0%, 100% { height: 6px; opacity: 0.45; }
    50% { height: 18px; opacity: 1; }
  }
  .listen-prompt {
    margin: 0;
    font-size: 16px;
    font-weight: 400;
    color: var(--ink-2);
    letter-spacing: 0.04em;
    text-align: center;
  }

  .choice-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .zen-choice {
    width: 100%;
    min-height: 58px;
    padding: 14px 20px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-family: var(--serif-jp);
    font-size: 20.5px;
    font-weight: 500;
    color: var(--sumi);
    letter-spacing: 0.03em;
    line-height: 1.4;
    text-align: left;
    white-space: normal;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: border-color 0.16s ease, background 0.16s ease;
  }
  .zen-choice:active { background: #EDEAE1; }
  .kbd-tag { display: none; }
  @media (min-width: 860px) {
    .zen-choice:hover { border-color: var(--sumi); background: #FFFFFF; }
    .kbd-tag {
      display: inline-block;
      font-family: var(--sans);
      font-size: 12px;
      color: var(--ink-3);
      font-variant-numeric: tabular-nums;
    }
  }

  .quiet-skip {
    display: block;
    width: 100%;
    text-align: center;
    padding: 12px 0 2px;
    font-size: 13.5px;
    color: var(--ink-3);
    letter-spacing: 0.05em;
  }

  /* -------- RESULT VIEW -------- */
  .result-answer {
    margin: 0 0 12px;
    font-family: var(--serif-jp);
    font-size: 26px;
    font-weight: 600;
    color: var(--moss);
    line-height: 1.4;
    letter-spacing: 0.03em;
  }
  .result-wrong-note {
    margin: 0 0 12px;
    font-size: 14.5px;
    color: var(--bengara);
    line-height: 1.5;
  }
  .result-insight {
    margin: 0 0 22px;
    font-size: 16px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.65;
  }
  .result-divider {
    height: 1px;
    background: var(--hairline);
    margin-bottom: 20px;
  }

  /* Tappable dictionary words */
  .w-tok {
    border-bottom: 1px dotted rgba(28, 27, 24, 0.36);
    cursor: pointer;
    padding-bottom: 1px;
  }
  .w-tok:hover, .w-tok.active-tok {
    color: var(--moss);
    border-bottom-color: var(--moss);
  }

  /* Architectural Sumi Buttons */
  .dock-row {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .sumi-btn {
    flex: 1;
    height: 52px;
    background: var(--sumi);
    color: var(--sheet);
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .ghost-btn {
    height: 52px;
    padding: 0 18px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 14.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.04em;
  }

  /* ================= 4. TWO-HOST RADIO SANCTUARY ("随身听") ================= */
  .radio-center {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 16px;
  }
  .radio-chap {
    font-size: 12.5px;
    font-weight: 500;
    letter-spacing: 0.12em;
    color: var(--moss);
  }
  .radio-topic {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 24px;
    font-weight: 600;
    line-height: 1.45;
    color: var(--sumi);
  }
  .radio-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 19px;
    font-weight: 400;
    line-height: 1.7;
    color: var(--ink-2);
  }

  .radio-dock {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding-top: 12px;
  }
  .scrub-wrap {
    width: 100%;
  }
  .zen-range {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 2px;
    background: var(--track);
    outline: none;
    margin: 10px 0;
    cursor: pointer;
  }
  .zen-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--sumi);
    cursor: pointer;
  }
  .time-pair {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
  }

  .transport-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .step-time-btn {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-2);
    padding: 10px 6px;
    font-variant-numeric: tabular-nums;
  }
  .play-toggle-btn {
    min-width: 124px;
    height: 48px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.1em;
  }

  .chapter-strip {
    display: flex;
    justify-content: space-between;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
  }
  .chap-link {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.05em;
    padding: 4px 2px;
  }
  .chap-link.active {
    color: var(--sumi);
    font-weight: 600;
  }

  /* ================= 5. ZEN LEDGER ("总表" — ZERO NESTED CARDS) ================= */
  .ledger-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 16px 0 8px;
    scrollbar-width: none;
  }
  .ledger-scroll::-webkit-scrollbar { display: none; }

  @media (min-width: 860px) {
    .ledger-layout {
      display: grid;
      grid-template-columns: 260px 1fr;
      gap: 44px;
      align-items: start;
    }
  }

  .pillar-list {
    margin-bottom: 24px;
  }
  .pillar-row {
    padding: 13px 0;
    border-bottom: 1px solid var(--hairline);
    cursor: pointer;
    opacity: 0.62;
    transition: opacity 0.18s ease;
  }
  .pillar-row.active {
    opacity: 1;
  }
  .pillar-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }
  .pillar-name {
    font-size: 15.5px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.03em;
  }
  .pillar-stat {
    font-size: 12.5px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .pillar-line {
    height: 2px;
    background: var(--track);
    display: flex;
    overflow: hidden;
  }
  .seg-moss { background: var(--moss); }
  .seg-ochre { background: var(--ochre); }
  .seg-bengara { background: var(--bengara); }

  .ledger-controls {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 8px;
  }
  .tier-links {
    display: flex;
    gap: 18px;
  }
  .tier-link {
    font-size: 14px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .tier-link.active {
    color: var(--sumi);
    font-weight: 600;
  }
  .zen-search {
    width: 124px;
    border: none;
    border-bottom: 1px solid var(--hairline-strong);
    background: transparent;
    padding: 4px 0;
    font-family: inherit;
    font-size: 13.5px;
    color: var(--sumi);
    outline: none;
  }
  .zen-search::placeholder { color: var(--ink-3); }

  .ledger-item {
    padding: 13px 0;
    border-bottom: 1px solid var(--hairline);
    cursor: pointer;
  }
  .li-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
  }
  .li-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .li-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .li-dot.todo { background: var(--bengara); }
  .li-dot.wip { background: var(--ochre); }
  .li-dot.done { background: var(--moss); }
  .li-name {
    font-family: var(--serif-jp);
    font-size: 16.5px;
    font-weight: 500;
    color: var(--sumi);
  }
  .li-right {
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-shrink: 0;
  }
  .li-sub {
    font-size: 13px;
    color: var(--ink-3);
    max-width: 136px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .li-act {
    font-size: 13px;
    color: var(--moss);
    font-weight: 500;
  }
  .li-note {
    margin-top: 8px;
    padding-left: 16px;
    font-size: 13.5px;
    color: var(--ink-2);
    line-height: 1.55;
  }

  /* ================= 6. DICTIONARY SHEET & MODAL ================= */
  .zen-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(28, 27, 24, 0.22);
    z-index: 89;
    display: none;
  }
  .zen-backdrop.open { display: block; }

  .word-sheet {
    position: fixed;
    z-index: 90;
    background: var(--sheet);
    color: var(--sumi);
    border: 1px solid var(--hairline-strong);
    box-shadow: 0 18px 40px rgba(28, 27, 24, 0.12);
    display: none;
  }
  .word-sheet.open { display: block; }

  @media (max-width: 767px) {
    .word-sheet {
      left: 20px !important;
      right: 20px !important;
      bottom: calc(18px + env(safe-area-inset-bottom)) !important;
      top: auto !important;
      border-radius: 10px;
      padding: 20px 22px;
    }
  }
  @media (min-width: 768px) {
    .word-sheet {
      width: 320px;
      border-radius: 8px;
      padding: 18px 20px;
    }
  }
  .ws-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }
  .ws-head { font-family: var(--serif-jp); font-size: 22px; font-weight: 600; }
  .ws-kana { font-size: 14.5px; color: var(--ink-2); margin-left: 8px; }
  .ws-pitch { font-size: 12.5px; color: var(--ink-3); margin-left: 4px; }
  .ws-speak { font-size: 13.5px; font-weight: 600; color: var(--moss); }
  .ws-pos { font-size: 12.5px; color: var(--ink-3); margin-bottom: 4px; }
  .ws-zh { font-size: 16.5px; font-weight: 500; color: var(--sumi); }
  .ws-tip { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--hairline); font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }

  .modal-mask {
    position: fixed;
    inset: 0;
    background: rgba(28, 27, 24, 0.28);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 26px;
    z-index: 100;
  }
  .modal-mask.open { display: flex; }
  .modal-card {
    width: 100%;
    max-width: 340px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 10px;
    padding: 24px;
  }
  .modal-h { margin: 0 0 12px; font-size: 17px; font-weight: 600; letter-spacing: 0.04em; }
  .modal-body { margin: 0 0 22px; font-size: 14.5px; color: var(--ink-2); line-height: 1.75; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>

<div class="zen-shell" id="app-shell">
  <!-- 1. STRICT GRID HEADER -->
  <header class="zen-header">
    <div class="zen-brand" id="countdown-txt">残 <strong>22</strong> 日</div>
    <nav class="zen-nav">
      <button class="nav-link active" id="tab-tutor" onclick="switchMode('tutor')">做题</button>
      <button class="nav-link" id="tab-radio" onclick="switchMode('radio', true)">随身听</button>
      <button class="nav-link" id="tab-dash" onclick="switchMode('dash')">总表</button>
    </nav>
  </header>

  <!-- 2. ZEN MOSS HORIZON -->
  <div class="zen-horizon" id="green-board" onclick="openSessionModal()">
    <div class="horizon-meta">
      <span id="gm-left-txt">今日 <b>0</b> / 50</span>
      <span id="gm-right-txt">120分把握 <b>86%</b></span>
    </div>
    <div class="horizon-track">
      <div class="horizon-fill" id="gm-fill" style="width:0%"></div>
    </div>
  </div>

  <!-- 3A. ADAPTIVE QUIZ STAGE -->
  <main class="zen-panel" id="tutor-view">
    <div class="stage-wrap" id="voice-card"></div>
  </main>

  <!-- 3B. TWO-HOST CONVERSATIONAL RADIO SANCTUARY -->
  <section class="zen-panel hidden" id="radio-view">
    <div class="stage-wrap">
      <div class="meta-bar">
        <span class="overline" id="radio-date-pill">双人对谈</span>
        <div class="quiet-actions">
          <button class="text-btn" id="radio-spd-btn" onclick="cycleRadioSpeed()">1.0x</button>
        </div>
      </div>

      <div class="radio-center">
        <div class="radio-chap" id="radio-chap-lbl">易混深聊</div>
        <h2 class="radio-topic" id="radio-live-title">阿哲 · 小夏　今日重点对谈</h2>
        <p class="radio-ja" id="radio-live-ja"></p>
      </div>

      <div class="radio-dock">
        <div class="scrub-wrap">
          <input type="range" class="zen-range" id="radio-seek" min="0" max="2220" value="0" step="1" oninput="onRadioScrub(this.value)" />
          <div class="time-pair">
            <span id="radio-cur-time">00:00</span>
            <span id="radio-tot-time">37:00</span>
          </div>
        </div>

        <div class="transport-row">
          <button class="step-time-btn" onclick="seekRadioBy(-15)">-15s</button>
          <button class="play-toggle-btn" id="radio-play-btn" onclick="toggleRadioPlay()">播放</button>
          <button class="step-time-btn" onclick="seekRadioBy(15)">+15s</button>
        </div>

        <div class="chapter-strip" id="radio-chap-pills"></div>
      </div>
    </div>
  </section>

  <!-- 3C. ZEN LEDGER ("总表") -->
  <section class="zen-panel hidden" id="dash-view">
    <div class="ledger-scroll">
      <div class="ledger-layout">
        <div class="pillar-list" id="dash-summary"></div>
        <div>
          <div class="ledger-controls">
            <div class="tier-links" id="tier-tabs"></div>
            <input type="search" class="zen-search" id="pt-search" placeholder="检索…" oninput="renderMasteryList()" />
          </div>
          <div id="point-list"></div>
        </div>
      </div>
    </div>
  </section>
</div>

<div class="zen-backdrop" id="sheet-backdrop" onclick="hideWordPopover()"></div>
<div class="word-sheet" id="word-popover"></div>

<div class="modal-mask" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-card" id="modal-content"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.2, 1.3, 1.5];
const RADIO_SPEEDS = [1.0, 1.15, 1.3];
const ADAPTIVE_KEY = "n3_adaptive_v9_" + DATA.plan_date;
const RADIO_POS_KEY = "n3_radio_pos_" + (DATA.radio.date || DATA.plan_date);

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.3");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.3;
let radioSpeed = parseFloat(localStorage.getItem("n3_radio_speed") || "1.0");
if (!RADIO_SPEEDS.includes(radioSpeed)) radioSpeed = 1.0;

let activeKind = null;
let activeMode = "tutor";

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
    if (!activeKind && radioPlayer.paused) location.reload();
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

// ================= MASTER ALGORITHM (RADIO <-> QUIZ CLOSED LOOP) =================
function createFreshAdaptiveState() {
  const pts = {};
  DATA.points.forEach(p => {
    pts[p.id] = {
      status: "unseen",
      needsTeach: !!p.initial_weak,
      audioPrimed: false,
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
  try { localStorage.setItem(ADAPTIVE_KEY, JSON.stringify(A)); } catch (e) {}
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

function compute120ReadinessPct() {
  let earnedPts = 47.0;
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
    earnedPts += (sum / items.length) * mod.exam_pts * 0.72;
  });
  let greenWeight = 0;
  let totalWeight = 0;
  DATA.points.forEach(p => {
    totalWeight += p.exam_weight;
    const st = A.pts[p.id] ? A.pts[p.id].status : "unseen";
    if (st === "green") greenWeight += p.exam_weight;
    else if (st === "learning") greenWeight += p.exam_weight * 0.35;
  });
  const estScore = earnedPts + (greenWeight / Math.max(1, totalWeight)) * 20.5;
  return Math.min(99, Math.max(55, Math.round((estScore / 125.0) * 100)));
}

function selectNextPointId(forcedId) {
  if (forcedId && A.pts[forcedId] && A.pts[forcedId].status !== "green") return forcedId;
  const remaining = DATA.points.filter(p => A.pts[p.id].status !== "green");
  if (!remaining.length) return null;
  if (remaining.length === 1) return remaining[0].id;

  const nonRepeat = remaining.filter(p => p.id !== A.lastPointId);
  const pool = nonRepeat.length ? nonRepeat : remaining;

  const dueQuizzes = pool.filter(p => {
    const s = A.pts[p.id];
    return s.status === "learning" && !s.needsTeach && s.dueStep <= A.step;
  });
  if (dueQuizzes.length) {
    dueQuizzes.sort((a, b) => {
      const pa = A.pts[a.id].audioPrimed ? 1 : 0;
      const pb = A.pts[b.id].audioPrimed ? 1 : 0;
      return A.pts[a.id].dueStep - A.pts[b.id].dueStep || pb - pa || b.roi_score - a.roi_score;
    });
    return dueQuizzes[0].id;
  }

  if (A.hotFamily) {
    const famSiblings = pool.filter(p => p.family === A.hotFamily && A.pts[p.id].dueStep <= A.step);
    if (famSiblings.length) return famSiblings[0].id;
  }

  const ready = pool.filter(p => A.pts[p.id].dueStep <= A.step);
  if (ready.length) {
    ready.sort((a, b) => {
      const ma = a.modality === "memorize" ? 0.25 : (a.modality === "both" ? 0.12 : 0);
      const mb = b.modality === "memorize" ? 0.25 : (b.modality === "both" ? 0.12 : 0);
      return (b.roi_score + mb) - (a.roi_score + ma);
    });
    return ready[0].id;
  }

  pool.sort((a, b) => A.pts[a.id].dueStep - A.pts[b.id].dueStep);
  return pool[0].id;
}

let curPointId = selectNextPointId();
let viewStage = "quiz";
let activeQuizObj = null;
let currentChoices = [];
let pickedVal = null;

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
  if (!curPointId) {
    viewStage = "done";
    activeQuizObj = null;
    return;
  }
  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];
  if (ps.needsTeach && !ps.audioPrimed && !p.primary.is_listening) {
    viewStage = "teach";
    activeQuizObj = null;
  } else {
    viewStage = "quiz";
    activeQuizObj = getQuizForPoint(p, ps);
    currentChoices = prepareChoices(activeQuizObj, ps.wrongCount);
  }
}
setupCurrentTurn();

// ================= AUDIO PLAYERS =================
const player = new Audio();
player.preload = "auto";
const wordPlayer = new Audio();
wordPlayer.preload = "auto";
const radioPlayer = new Audio();
radioPlayer.preload = "metadata";

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
}

function cycleExpSpeed() {
  expSpeed = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  try { localStorage.setItem("n3_exp_speed", String(expSpeed)); } catch (e) {}
  if (activeKind === "exp" || activeKind === "teach") applyPlaybackRate(activeKind);
  const spdBtn = document.getElementById("ans-spd-btn");
  if (spdBtn) spdBtn.textContent = `${expSpeed.toFixed(1)}x`;
}

function stopQuizAudio() {
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
  if (!radioPlayer.paused) radioPlayer.pause();
  if (toggleIfSame && activeKind === kind && !player.paused) {
    stopQuizAudio();
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
  activeKind = null;
  syncAudioButtons();
});

function syncAudioButtons() {
  const orb = document.getElementById("voice-orb");
  if (orb) orb.classList.toggle("speaking", activeKind === "q" && !player.paused);
  const qBtn = document.getElementById("q-play-btn");
  if (qBtn) {
    const onQ = activeKind === "q" && !player.paused;
    qBtn.classList.toggle("playing", onQ);
    qBtn.textContent = onQ ? "暂停" : "读题";
  }
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    const on = (activeKind === "exp" || activeKind === "teach") && !player.paused;
    repBtn.classList.toggle("playing", on);
    repBtn.textContent = on ? "暂停" : "讲解";
  }
}

// ================= TWO-HOST RADIO ENGINE =================
let radioInitialized = false;
let lastSavedSec = -1;

function formatMMSS(sec) {
  const s = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function ensureRadioReady() {
  if (!radioInitialized) {
    radioInitialized = true;
    radioPlayer.src = DATA.radio.audio_url;
    const savedPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    if (savedPos > 3 && savedPos < (DATA.radio.duration_sec || 2400) - 10) {
      radioPlayer.currentTime = savedPos;
    }
    document.getElementById("radio-date-pill").textContent = `${DATA.radio.display_date || "今日"} · 双人对谈`;
    document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
    const seekEl = document.getElementById("radio-seek");
    seekEl.max = Math.ceil(DATA.radio.duration_sec || 2220);
    document.getElementById("radio-tot-time").textContent = formatMMSS(DATA.radio.duration_sec || 2220);
    renderRadioChapters(0);
    updateRadioLiveDisplay(radioPlayer.currentTime || savedPos || 0);
  }
  radioPlayer.defaultPlaybackRate = radioSpeed;
  radioPlayer.playbackRate = radioSpeed;
  if ("preservesPitch" in radioPlayer) radioPlayer.preservesPitch = true;
}

function setupMediaSession(segTitle) {
  if (!("mediaSession" in navigator)) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: segTitle || "N3 双人随身电台",
      artist: "阿哲 · 小夏",
      album: "JLPT N3"
    });
    navigator.mediaSession.setActionHandler("play", () => toggleRadioPlay(true));
    navigator.mediaSession.setActionHandler("pause", () => toggleRadioPlay(false));
    navigator.mediaSession.setActionHandler("seekbackward", () => seekRadioBy(-15));
    navigator.mediaSession.setActionHandler("seekforward", () => seekRadioBy(15));
    navigator.mediaSession.setActionHandler("previoustrack", () => seekRadioBy(-15));
    navigator.mediaSession.setActionHandler("nexttrack", () => seekRadioBy(15));
  } catch (e) {}
}

function toggleRadioPlay(forcePlay) {
  stopQuizAudio();
  ensureRadioReady();
  const wantPlay = typeof forcePlay === "boolean" ? forcePlay : radioPlayer.paused;
  if (wantPlay) {
    radioPlayer.playbackRate = radioSpeed;
    radioPlayer.play().catch(() => {});
  } else {
    radioPlayer.pause();
  }
  syncRadioUI();
}

function seekRadioBy(delta) {
  ensureRadioReady();
  const dur = radioPlayer.duration || DATA.radio.duration_sec || 2220;
  radioPlayer.currentTime = Math.max(0, Math.min(dur - 1, (radioPlayer.currentTime || 0) + delta));
  updateRadioLiveDisplay(radioPlayer.currentTime);
}

function jumpRadioChapter(startSec) {
  ensureRadioReady();
  radioPlayer.currentTime = startSec;
  if (radioPlayer.paused) toggleRadioPlay(true);
  updateRadioLiveDisplay(startSec);
}

function onRadioScrub(val) {
  ensureRadioReady();
  radioPlayer.currentTime = parseFloat(val) || 0;
  updateRadioLiveDisplay(radioPlayer.currentTime);
}

function cycleRadioSpeed() {
  radioSpeed = RADIO_SPEEDS[(RADIO_SPEEDS.indexOf(radioSpeed) + 1) % RADIO_SPEEDS.length];
  try { localStorage.setItem("n3_radio_speed", String(radioSpeed)); } catch (e) {}
  radioPlayer.defaultPlaybackRate = radioSpeed;
  radioPlayer.playbackRate = radioSpeed;
  document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
}

function renderRadioChapters(activeChapIdx) {
  const chaps = DATA.radio.chapters || [];
  document.getElementById("radio-chap-pills").innerHTML = chaps.map(c => `
    <button class="chap-link ${c.idx === activeChapIdx ? 'active' : ''}" onclick="jumpRadioChapter(${c.start})">${escapeHtml(c.title.replace(/^[①②③④]\s*/, ""))}</button>
  `).join("");
}

function updateRadioLiveDisplay(t) {
  const seekEl = document.getElementById("radio-seek");
  if (seekEl) seekEl.value = Math.floor(t);
  document.getElementById("radio-cur-time").textContent = formatMMSS(t);
  if (radioPlayer.duration && isFinite(radioPlayer.duration)) {
    seekEl.max = Math.ceil(radioPlayer.duration);
    document.getElementById("radio-tot-time").textContent = formatMMSS(radioPlayer.duration);
  }

  const segs = DATA.radio.segments || [];
  let curSeg = null;
  for (let i = 0; i < segs.length; i++) {
    if (t >= segs[i].start && t < segs[i].end) {
      curSeg = segs[i];
      break;
    }
  }

  if (curSeg) {
    const chaps = DATA.radio.chapters || [];
    const chapObj = chaps[curSeg.chapter] || chaps[0];
    if (chapObj) {
      document.getElementById("radio-chap-lbl").textContent = chapObj.title.replace(/^[①②③④]\s*/, "");
      renderRadioChapters(chapObj.idx);
    }
    document.getElementById("radio-live-title").textContent = curSeg.title;
    document.getElementById("radio-live-ja").innerHTML = annotateJapanese(curSeg.ja_focus || "");
    setupMediaSession(curSeg.title);

    if (curSeg.point_id && A.pts[curSeg.point_id] && t >= curSeg.end - 6) {
      const ps = A.pts[curSeg.point_id];
      if (!ps.audioPrimed) {
        ps.audioPrimed = true;
        ps.needsTeach = false;
        if (ps.status === "unseen") ps.status = "learning";
        saveAdaptiveState();
        renderGreenBoard();
      }
    }
  }
}

function syncRadioUI() {
  const playing = !radioPlayer.paused;
  const btn = document.getElementById("radio-play-btn");
  if (btn) btn.textContent = playing ? "暂停" : "播放";
  const tabBtn = document.getElementById("tab-radio");
  if (tabBtn) tabBtn.classList.toggle("is-playing", playing);
}

radioPlayer.addEventListener("play", syncRadioUI);
radioPlayer.addEventListener("pause", syncRadioUI);
radioPlayer.addEventListener("ended", syncRadioUI);
radioPlayer.addEventListener("loadedmetadata", () => updateRadioLiveDisplay(radioPlayer.currentTime || 0));
radioPlayer.addEventListener("timeupdate", () => {
  const t = radioPlayer.currentTime || 0;
  updateRadioLiveDisplay(t);
  if (Math.abs(t - lastSavedSec) >= 3) {
    lastSavedSec = t;
    try { localStorage.setItem(RADIO_POS_KEY, String(Math.floor(t))); } catch (e) {}
  }
});

// ================= QUIZ ACTIONS =================
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

function completeTeachCard() {
  stopQuizAudio();
  hideWordPopover();
  const p = getPointById(curPointId);
  if (p) {
    const ps = A.pts[p.id];
    ps.status = "learning";
    ps.needsTeach = false;
    ps.dueStep = A.step + 4;
    A.step += 1;
    A.lastPointId = p.id;
    A.hotFamily = null;
    saveAdaptiveState();
  }
  setupCurrentTurn();
  renderTutor();
  autoPlayCurrentTurn();
}

function switchToTeachForCurrent() {
  stopQuizAudio();
  hideWordPopover();
  const p = getPointById(curPointId);
  if (!p) return;
  const ps = A.pts[p.id];
  ps.status = "learning";
  ps.needsTeach = true;
  ps.wrongCount += 1;
  if (p.variants && p.variants.length > 0) ps.useVariant = true;
  A.hotFamily = p.family;
  syncBackendRecord(p, activeQuizObj ? activeQuizObj.id : p.id, "先看考点", false, false, "todo");
  viewStage = "teach";
  renderTutor();
  playMainClip(p.teach.audio, "teach", false);
}

function submitAnswer(val) {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  hideWordPopover();
  stopQuizAudio();
  pickedVal = val;
  viewStage = "result";

  const p = getPointById(curPointId);
  const ps = A.pts[p.id];
  const isCorrect = (val === activeQuizObj.answer);

  if (isCorrect) {
    ps.status = "green";
    ps.needsTeach = false;
    A.hotFamily = null;
    syncBackendRecord(p, activeQuizObj.id, val, true, false, "done");
  } else {
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
  stopQuizAudio();
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
  if (activeMode !== "tutor") return;
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
  stopQuizAudio();
  if (!radioPlayer.paused) radioPlayer.pause();
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
  stopQuizAudio();
  const keepOverrides = A.masteryOverrides || {};
  A = createFreshAdaptiveState();
  A.masteryOverrides = keepOverrides;
  saveAdaptiveState();
  closeModal();
  setupCurrentTurn();
  renderTutor();
}

function renderGreenBoard() {
  document.getElementById("countdown-txt").innerHTML = `残 <strong>${computeDaysLeft()}</strong> 日`;
  const total = DATA.points.length;
  const greenCnt = DATA.points.filter(p => A.pts[p.id].status === "green").length;
  const pct = Math.round((greenCnt / Math.max(1, total)) * 100);
  const readiness = compute120ReadinessPct();

  document.getElementById("gm-left-txt").innerHTML = `今日 <b>${greenCnt}</b> / ${total}`;
  document.getElementById("gm-right-txt").innerHTML = `120分把握 <b>${readiness}%</b>`;
  document.getElementById("gm-fill").style.width = `${pct}%`;
}

function renderTutor() {
  renderGreenBoard();
  const box = document.getElementById("voice-card");

  if (viewStage === "done" || !curPointId) {
    const readiness = compute120ReadinessPct();
    box.innerHTML = `
      <div class="meta-bar"><span class="overline ok">今日圆满</span></div>
      <div class="focal-space">
        <h2 class="point-heading">五十考点皆已过关</h2>
        <p class="result-insight">120 分把握度已升至 ${readiness}%，今夜可以安心休息了。</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          <button class="ghost-btn" onclick="switchMode('dash')">总表</button>
          <button class="sumi-btn" onclick="resetTodayMission()">重新一轮</button>
        </div>
      </div>
    `;
    return;
  }

  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];

  // -------- TEACH --------
  if (viewStage === "teach") {
    warmAudio(p.teach.audio);
    warmAudio(p.primary.q_audio);
    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline warm">${escapeHtml(p.subject)} · 先看考点</span>
        <div class="quiet-actions">
          <button class="text-btn" id="exp-replay-btn" onclick="playMainClip('${p.teach.audio}', 'teach', true)">讲解</button>
          <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed.toFixed(1)}x</button>
        </div>
      </div>

      <div class="focal-space">
        <h2 class="point-heading">${escapeHtml(p.point)}</h2>
        <div class="zen-pair">
          <div class="zen-pair-row">
            <div class="zp-ja"><span class="zp-dot"></span><span>${escapeHtml(p.teach.left.ja)}</span></div>
            <div class="zp-sub">${escapeHtml(p.teach.left.sub)}</div>
          </div>
          ${p.teach.right && p.teach.right.ja ? `
          <div class="zen-pair-row">
            <div class="zp-ja"><span class="zp-dot muted"></span><span>${escapeHtml(p.teach.right.ja)}</span></div>
            <div class="zp-sub">${escapeHtml(p.teach.right.sub)}</div>
          </div>` : ""}
        </div>
        <div class="example-line">${annotateJapanese(p.teach.example_ja)}</div>
      </div>

      <div class="action-dock">
        <button class="sumi-btn" style="width:100%;" onclick="completeTeachCard()">继续</button>
      </div>
    `;
    syncAudioButtons();
    return;
  }

  // -------- QUIZ --------
  if (viewStage === "quiz" && activeQuizObj) {
    warmAudio(activeQuizObj.q_audio);
    warmAudio(activeQuizObj.exp_audio);
    const isVariant = activeQuizObj.id !== p.primary.id;
    let label = p.subject;
    if (isVariant) label += " · 换题复考";
    else if (ps.audioPrimed) label += " · 电台已听";

    const choicesHTML = currentChoices.map((c, cIdx) => `
      <button class="zen-choice" onclick='submitAnswer(${JSON.stringify(c)})'>
        <span>${escapeHtml(c)}</span>
        <span class="kbd-tag">${cIdx + 1}</span>
      </button>
    `).join("");

    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline">${escapeHtml(label)}</span>
        <div class="quiet-actions">
          ${!activeQuizObj.is_listening ? `<button class="text-btn" id="q-play-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">读题</button>` : ""}
        </div>
      </div>

      <div class="focal-space">
        <div class="quiz-focal">
          ${activeQuizObj.is_listening ? `
          <div class="listen-medallion-wrap">
            <button class="listen-medallion" id="voice-orb" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)" aria-label="播放">
              <svg class="med-ic" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>
              <div class="med-waves"><span></span><span></span><span></span></div>
            </button>
            <p class="listen-prompt">${escapeHtml(activeQuizObj.prompt)}</p>
          </div>` : `<p class="quiz-ja">${escapeHtml(activeQuizObj.prompt)}</p>`}
        </div>

        <div class="choice-list">
          ${choicesHTML}
        </div>
      </div>

      <div class="action-dock">
        ${!activeQuizObj.is_listening ? `<button class="quiet-skip" onclick="switchToTeachForCurrent()">先看考点</button>` : `<div style="height:12px;"></div>`}
      </div>
    `;
    syncAudioButtons();
    return;
  }

  // -------- RESULT --------
  const q = activeQuizObj || p.primary;
  const isCorrect = pickedVal === q.answer;
  const overCls = isCorrect ? "overline ok" : "overline ng";
  const overTxt = isCorrect ? "已变绿" : "稍后复考";

  let wrongNoteHTML = "";
  if (!isCorrect && pickedVal) {
    const wNote = (q.option_notes && q.option_notes[pickedVal]) || "";
    wrongNoteHTML = `<p class="result-wrong-note">误选「${annotateJapanese(pickedVal)}」${wNote ? " · " + escapeHtml(wNote) : ""}</p>`;
  }

  box.innerHTML = `
    <div class="meta-bar">
      <span class="${overCls}">${overTxt}</span>
      <div class="quiet-actions">
        <button class="text-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">原题</button>
        <button class="text-btn" id="exp-replay-btn" onclick="playMainClip(activeQuizObj.exp_audio, 'exp', true)">讲解</button>
        <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed.toFixed(1)}x</button>
      </div>
    </div>

    <div class="focal-space">
      <h2 class="result-answer">${annotateJapanese(q.answer)}</h2>
      ${wrongNoteHTML}
      <p class="result-insight">${escapeHtml(q.core_rule)}</p>
      <div class="result-divider"></div>
      <div class="example-line">${annotateJapanese(q.full_ja)}</div>
    </div>

    <div class="action-dock">
      <div class="dock-row">
        ${isCorrect ? `<button class="ghost-btn" onclick="advanceNext(true)">再考</button>` : ""}
        <button class="sumi-btn" onclick="advanceNext(false)">下一题</button>
      </div>
    </div>
  `;
  syncAudioButtons();
}

// ================= DICTIONARY SHEET =================
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
    <div class="ws-top">
      <div>
        <span class="ws-head">${escapeHtml(surface)}</span>
        <span class="ws-kana">${escapeHtml(info.kana || "")}</span>
        <span class="ws-pitch">${escapeHtml(info.pitch || "")}</span>
      </div>
      ${hasAudio ? `<button class="ws-speak" onclick='playWordAudio(${JSON.stringify(surface)})'>发音</button>` : ""}
    </div>
    ${info.pos ? `<div class="ws-pos">${escapeHtml(info.head && info.head !== surface ? "原形 " + info.head + " · " + info.pos : info.pos)}</div>` : ""}
    <div class="ws-zh">${escapeHtml(info.zh || "")}</div>
    ${info.tip ? `<div class="ws-tip">${escapeHtml(info.tip)}</div>` : ""}
  `;
  popEl.classList.add("open");

  if (isMobileSheetViewport()) {
    backdropEl.classList.add("open");
  } else if (anchorEl && anchorEl.getBoundingClientRect) {
    const r = anchorEl.getBoundingClientRect();
    const pw = popEl.offsetWidth || 320;
    const ph = popEl.offsetHeight || 140;
    let left = Math.max(20, Math.min(window.innerWidth - pw - 20, r.left + r.width / 2 - pw / 2));
    let top = r.top - ph - 10;
    if (top < 16) top = r.bottom + 10;
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
  if (!tok || (activeMode === "tutor" && viewStage === "quiz")) return;
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
  if (tok && !(activeMode === "tutor" && viewStage === "quiz")) {
    e.stopPropagation();
    showWordPopover(tok.dataset.w, tok, true);
    return;
  }
  if (!isMobileSheetViewport() && !e.target.closest("#word-popover")) {
    hideWordPopover();
  }
});

// ================= KEYBOARD =================
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
  if (e.key === "Escape") { hideWordPopover(); return; }

  if (activeMode === "radio") {
    if (e.key === " ") { e.preventDefault(); toggleRadioPlay(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seekRadioBy(-15); }
    else if (e.key === "ArrowRight") { e.preventDefault(); seekRadioBy(15); }
    return;
  }
  if (activeMode !== "tutor") return;
  if (e.key.toLowerCase() === "s") { e.preventDefault(); cycleExpSpeed(); return; }

  if (viewStage === "teach") {
    const p = getPointById(curPointId);
    if (e.key === " ") { e.preventDefault(); if (p) playMainClip(p.teach.audio, "teach", true); }
    else if (e.key === "Enter" || e.key === "ArrowRight") { e.preventDefault(); completeTeachCard(); }
    return;
  }
  if (viewStage === "quiz" && activeQuizObj) {
    if (e.key === " ") { e.preventDefault(); playMainClip(activeQuizObj.q_audio, "q", true); }
    else if (e.key === "1" && currentChoices[0]) { e.preventDefault(); submitAnswer(currentChoices[0]); }
    else if (e.key === "2" && currentChoices[1]) { e.preventDefault(); submitAnswer(currentChoices[1]); }
    else if (e.key === "3" && currentChoices[2]) { e.preventDefault(); submitAnswer(currentChoices[2]); }
    else if (e.key === "0" && !activeQuizObj.is_listening) { e.preventDefault(); switchToTeachForCurrent(); }
    return;
  }
  if (viewStage === "result" && activeQuizObj) {
    if (e.key === " ") { e.preventDefault(); playMainClip(activeQuizObj.exp_audio, "exp", true); }
    else if (e.key === "Enter" || e.key === "ArrowRight") { e.preventDefault(); advanceNext(false); }
  }
});

// ================= ZEN LEDGER ("总表") =================
let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

function switchMode(m, autoPlayRadio) {
  activeMode = m;
  hideWordPopover();
  if (m !== "tutor") stopQuizAudio();

  document.getElementById("app-shell").classList.toggle("wide-mode", m === "dash");
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-radio").classList.toggle("active", m === "radio");
  document.getElementById("tab-dash").classList.toggle("active", m === "dash");

  document.getElementById("green-board").style.display = (m === "dash") ? "none" : "block";
  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("radio-view").classList.toggle("hidden", m !== "radio");
  document.getElementById("dash-view").classList.toggle("hidden", m !== "dash");

  if (m === "radio") {
    ensureRadioReady();
    if (autoPlayRadio && radioPlayer.paused) {
      toggleRadioPlay(true);
    } else {
      syncRadioUI();
    }
  } else if (m === "dash") {
    renderDashboard();
  } else {
    renderTutor();
  }
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
  document.getElementById("dash-summary").innerHTML = order.map(k => {
    const m = DATA.mastery[k];
    const c = recalcCounts(k);
    const pDone = ((c.done / Math.max(1, c.total)) * 100).toFixed(1);
    const pWip = ((c.wip / Math.max(1, c.total)) * 100).toFixed(1);
    const pTodo = ((c.todo / Math.max(1, c.total)) * 100).toFixed(1);
    return `
      <div class="pillar-row ${dashMod === k ? 'active' : ''}" onclick="selectDashMod('${k}')">
        <div class="pillar-head">
          <span class="pillar-name">${m.label}</span>
          <span class="pillar-stat">已会 ${c.done} / ${c.total}</span>
        </div>
        <div class="pillar-line">
          <div class="seg-moss" style="width:${pDone}%"></div>
          <div class="seg-ochre" style="width:${pWip}%"></div>
          <div class="seg-bengara" style="width:${pTodo}%"></div>
        </div>
      </div>
    `;
  }).join("");

  const curCounts = DATA.mastery[dashMod].counts;
  document.getElementById("tier-tabs").innerHTML = `
    <button class="tier-link ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待练 ${curCounts.todo}</button>
    <button class="tier-link ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固 ${curCounts.wip}</button>
    <button class="tier-link ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已会 ${curCounts.done}</button>
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
    listEl.innerHTML = `<div style="padding:36px 0;color:var(--ink-3);font-size:14px;">此处已清空</div>`;
    return;
  }

  listEl.innerHTML = items.map((it, i) => `
    <div class="ledger-item" onclick="togglePtNote(${i})">
      <div class="li-row">
        <div class="li-left">
          <span class="li-dot ${it.tier}"></span>
          <span class="li-name">${escapeHtml(it.name)}</span>
        </div>
        <div class="li-right">
          <span class="li-sub">${escapeHtml(it.sub)}</span>
          ${it.audio ? `<button class="li-act" onclick="event.stopPropagation();playDirectUrl('${it.audio}')">听音</button>` : ""}
          ${it.point_id ? `<button class="li-act" onclick="event.stopPropagation();jumpToPointById('${it.point_id}')">练习</button>` : ""}
        </div>
      </div>
      ${expandedPt === i && (it.note || it.family) ? `<div class="li-note">${escapeHtml([it.family, it.note].filter(Boolean).join(" · "))}</div>` : ""}
    </div>
  `).join("");
}

function closeModal() {
  document.getElementById("app-modal").classList.remove("open");
}

function openSessionModal() {
  const greenCnt = DATA.points.filter(p => A.pts[p.id].status === "green").length;
  const primedCnt = DATA.points.filter(p => A.pts[p.id].audioPrimed).length;
  const readiness = compute120ReadinessPct();
  document.getElementById("modal-content").innerHTML = `
    <h3 class="modal-h">今日修行进度</h3>
    <p class="modal-body">
      已过关　<strong>${greenCnt} / ${DATA.points.length}</strong><br/>
      电台已听　<strong>${primedCnt}</strong> 项<br/>
      120 分把握　<strong>${readiness}%</strong>
    </p>
    <div class="dock-row">
      <button class="ghost-btn" onclick="resetTodayMission()">重置</button>
      <button class="sumi-btn" onclick="closeModal()">继续</button>
    </div>
  `;
  document.getElementById("app-modal").classList.add("open");
}

function initApp() {
  const params = new URLSearchParams(location.search);
  const m = params.get("mode");
  if (m === "dash") switchMode("dash");
  else if (m === "radio" || m === "walk") switchMode("radio", false);
  else renderTutor();
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
    "Wrote Zen v9 N3 Platform:",
    HTML_PATH,
    "points:",
    len(ordered_points),
    "size:",
    len(final_html),
)
