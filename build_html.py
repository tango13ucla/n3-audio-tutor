#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the Japanese Zen Edition of the JLPT N3 Adaptive & Two-Coach Podcast Platform (index.html — Zen v11).
Aesthetic Philosophy: 禅 (Zen) · 余白 (Ma) · 新潮文庫級組版 (Optimal Literary Editorial Typography)
- Pure native Japanese question reading (zero "请听题", zero "空欄", zero "选", zero spoilers).
- 3-step human teacher explanation (both text & voice):
  ① 句意 (what the sentence means) -> ② 为什么用 (context) -> ③ 变形与辨析 (conjugation / contrast).
- Instant inline word meaning on tap (100% sentence lexicon coverage + zero Android Chrome Google Search popup).
- Dual Daily Lock Horizon ("做题 50 + 随身听 = 稳过 120 分"): visibly locks projected N3 score from 108 -> 132+.
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
from clear_explanations import CARDS_75
from radio_dialogue_bank import MODALITY_MAP
from sentence_lexicon import SENTENCE_LEXICON
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
    "duration_sec": 2100.0,
    "duration_label": "35 分钟",
    "hosts": "阿哲 · 小夏",
    "chapters": [
        {"idx": 0, "title": "语法", "start": 0},
        {"idx": 1, "title": "听力", "start": 1200},
        {"idx": 2, "title": "词汇", "start": 1580},
        {"idx": 3, "title": "纯日", "start": 1880},
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
merged_raw_words = {}
for src_dict in (SENTENCE_LEXICON, WORD_DICT, EXTRA_WORDS):
    for surf, info in src_dict.items():
        if surf in merged_raw_words:
            merged_raw_words[surf] = {**merged_raw_words[surf], **info}
        else:
            merged_raw_words[surf] = dict(info)

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
    txt = re.sub(r"\d+/\d+(?:\s*&\s*\d+/\d+)?\s*课上[^·。！!]*[·\s]*", "", txt)
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
    txt = re.sub(r"^（向[^）]+）\s*", "", txt).strip()
    if is_listening:
        if any(k in txt for k in ("怎么说", "哪句", "什么意思", "最合适", "怎么回应", "先做什么", "做什么", "处理")):
            return clean_zen_text(txt)
        return "听对话，选出最自然的回应"
    return txt


def concise_sub(sub_a: str, sub_b: str, fallback: str) -> str:
    parts = [clean_zen_text(x).rstrip("。") for x in (sub_a, sub_b) if x and clean_zen_text(x)]
    if parts:
        joined = " · ".join(parts)
        return joined[:42] + ("…" if len(joined) > 42 else "")
    fb = clean_zen_text(fallback).rstrip("。")
    return fb[:42] + ("…" if len(fb) > 42 else "")


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
        clean_rel = rel.split("?")[0].lstrip("./")
        abs_p = os.path.join(BASE_DIR, clean_rel)
        if not (os.path.exists(abs_p) and os.path.getsize(abs_p) > 0):
            return False
    return True


variants_by_base = {}
for vc in VARIANT_CARDS:
    vid = vc["id"]
    c75 = CARDS_75.get(vid, {})
    meta = audio_manifest.get(f"meta:{vid}", {})
    q_rel = meta.get("q_audio", "")
    exp_rel = meta.get("exp_audio", "")
    if has_mp3_pair(q_rel, exp_rel):
        v_obj = {
            "id": vid,
            "prompt": c75.get("prompt_clean") or clean_prompt(vc["prompt"], vc["subject"] == "聴解"),
            "choices": vc["choices"],
            "answer": vc["answer"],
            "full_ja": c75.get("full_ja") or vc["full_ja"],
            "zh_meaning": c75.get("zh_meaning", ""),
            "why_line": c75.get("why_line", ""),
            "form_line": c75.get("form_line") or clean_zen_text(vc["core_rule"]),
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": vc["subject"] == "聴解",
        }
        variants_by_base.setdefault(vc["variant_of"], []).append(v_obj)


def build_base_point(q: dict, subject: str, fallback_point_label: str) -> dict:
    qid = q["id"]
    c75 = CARDS_75.get(qid, {})
    t_item = TUTOR_ITEMS.get(qid, {})
    meta = audio_manifest.get(f"meta:{qid}", {})
    is_listening = subject == "聴解"

    fallback_opts = [strip_opt_prefix(o) for o in q.get("options", []) if o != "不知道"]
    fallback_ans = strip_opt_prefix(q.get("answer", ""))

    choices = t_item.get("choices") or fallback_opts
    answer = t_item.get("answer") or fallback_ans
    raw_prompt = c75.get("prompt_clean") or t_item.get("prompt_display") or re.sub(r"\s*\[[A-Z0-9-]+\]", "", str(q.get("stem", ""))).strip()
    prompt_display = clean_prompt(raw_prompt, is_listening)
    full_ja = c75.get("full_ja") or t_item.get("full_ja") or raw_prompt

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
    why_line = c75.get("why_line", "")
    form_line = c75.get("form_line") or clean_zen_text(raw_micro.get("hook") or "")
    zh_meaning = c75.get("zh_meaning", "")

    left_m = raw_micro.get("left") or {}
    right_m = raw_micro.get("right") or {}
    teach_left = {
        "ja": clean_ja_head(left_m.get("ja") or answer),
        "sub": concise_sub(left_m.get("sub", ""), left_m.get("desc", ""), opt_notes.get(answer, "") or form_line),
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

    return {
        "id": qid,
        "subject": SUBJ_CN.get(subject, subject),
        "point": display_point,
        "point_key": point_key,
        "family": pmeta["family"],
        "modality": modality,
        "exam_weight": exam_weight,
        "roi_score": roi_score,
        "teach": {
            "left": teach_left,
            "right": teach_right,
            "example_ja": full_ja,
            "zh_meaning": zh_meaning,
            "audio": exp_rel,
        },
        "primary": {
            "id": qid,
            "prompt": prompt_display,
            "choices": choices,
            "answer": answer,
            "full_ja": full_ja,
            "zh_meaning": zh_meaning,
            "why_line": why_line,
            "form_line": form_line,
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
    c75 = CARDS_75.get(qid, {})
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
    full_ja = c75.get("full_ja") or ext["full_ja"]
    raw_points.append({
        "id": qid,
        "subject": SUBJ_CN.get(ext["subject"], ext["subject"]),
        "point": ext["point_display"],
        "point_key": ext["point_key"],
        "family": ext["family"],
        "modality": MODALITY_MAP.get(qid, "listen" if is_l else "both"),
        "exam_weight": w,
        "roi_score": round(w * weakness_multiplier(pt_status), 3),
        "teach": {
            "left": tl,
            "right": tr,
            "example_ja": full_ja,
            "zh_meaning": c75.get("zh_meaning", ""),
            "audio": exp_rel,
        },
        "primary": {
            "id": qid,
            "prompt": c75.get("prompt_clean") or clean_prompt(ext["prompt"], is_l),
            "choices": ext["choices"],
            "answer": ext["answer"],
            "full_ja": full_ja,
            "zh_meaning": c75.get("zh_meaning", ""),
            "why_line": c75.get("why_line", ""),
            "form_line": c75.get("form_line") or clean_zen_text(ext["core_rule"]),
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
<meta name="description" content="JLPT N3 · 每日做题与双人随身听" />
<meta name="theme-color" content="#F5F2EB" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<link rel="manifest" href="./manifest.json" />
<link rel="icon" href="./icon-192.png" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600&family=Noto+Serif+JP:wght@500;600&display=swap" rel="stylesheet" />
<title>N3</title>
<style>
  :root {
    /* Traditional Japanese Pigments (日本の伝統色): 生成り · 白練 · 墨 · 苔色 · 黄土 · 弁柄 */
    --washi: #F5F2EB;
    --sheet: #FCFBF8;
    --sumi: #1C1B18;
    --ink-2: #48443C;
    --ink-3: #847E72;
    --hairline: rgba(28, 27, 24, 0.09);
    --hairline-strong: rgba(28, 27, 24, 0.18);
    --track: #E5E0D5;
    --moss: #2B5F49;
    --moss-soft: rgba(43, 95, 73, 0.10);
    --ochre: #B07D3A;
    --bengara: #9E3E36;
    /* Editorial Bilingual Pairing: Japanese Literary Mincho + Clean Chinese Humanist Sans */
    --sans: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", -apple-system, BlinkMacSystemFont, sans-serif;
    --serif-jp: "Hiragino Mincho ProN", "YuMincho", "Noto Serif JP", serif;
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
    /* Eliminate Android Chrome Touch-to-Search Google bar on word tap */
    -webkit-user-select: none;
    user-select: none;
    -webkit-touch-callout: none;
  }

  body {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(15px + env(safe-area-inset-top)) 28px calc(18px + env(safe-area-inset-bottom));
  }

  .zen-shell {
    width: 100%;
    max-width: 496px;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  @media (min-width: 860px) {
    body { padding: 34px 48px 34px; }
    .zen-shell { max-width: 590px; }
    .zen-shell.wide-mode { max-width: 800px; }
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
    font-size: 15px;
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
    gap: 24px;
  }
  .nav-link {
    font-size: 16.5px;
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

  /* ================= 2. DUAL DAILY LOCK HORIZON (做题 + 随身听 -> 稳过 120) ================= */
  .zen-horizon {
    flex-shrink: 0;
    padding: 13px 0 4px;
    cursor: pointer;
  }
  .horizon-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
    gap: 8px;
  }
  .horizon-meta b {
    font-weight: 600;
    color: var(--sumi);
  }
  .horizon-meta b.moss {
    color: var(--moss);
  }
  .horizon-track {
    width: 100%;
    height: 3px;
    background: var(--track);
    border-radius: 2px;
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
    padding-top: 16px;
    animation: fadeTurn 0.18s ease-out;
  }
  @keyframes fadeTurn {
    from { opacity: 0.48; }
    to { opacity: 1; }
  }

  .meta-bar {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 28px;
    gap: 12px;
  }
  .overline {
    font-size: 14.5px;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: var(--ink-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .overline.ok { color: var(--moss); font-weight: 600; }
  .overline.ng { color: var(--bengara); font-weight: 600; }
  .overline.warm { color: var(--ochre); }

  .quiet-actions {
    display: flex;
    align-items: center;
    gap: 18px;
    flex-shrink: 0;
  }
  .text-btn {
    font-size: 14.5px;
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

  /* Center focal space with balanced Japanese Ma (余白) */
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
    margin: 0 0 20px;
    font-family: var(--serif-jp);
    font-size: 27.5px;
    font-weight: 600;
    line-height: 1.38;
    letter-spacing: 0.03em;
    color: var(--sumi);
  }
  .zen-pair {
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 20px;
  }
  .zen-pair-row {
    padding: 15px 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .zen-pair-row + .zen-pair-row {
    border-top: 1px solid var(--hairline);
  }
  .zp-ja {
    font-family: var(--serif-jp);
    font-size: 22px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.025em;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .zp-dot {
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    background: var(--moss);
    flex-shrink: 0;
  }
  .zp-dot.muted {
    background: transparent;
    border: 1.5px solid var(--ink-3);
  }
  .zp-sub {
    padding-left: 16.5px;
    font-size: 16.5px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.6;
  }

  .example-line {
    font-family: var(--serif-jp);
    font-size: 22.5px;
    font-weight: 500;
    line-height: 1.76;
    letter-spacing: 0.03em;
    color: var(--sumi);
    white-space: pre-line;
  }
  .example-zh {
    margin: 8px 0 0;
    font-size: 17px;
    color: var(--ink-2);
    line-height: 1.62;
  }

  /* -------- QUIZ VIEW (Optimal Literary Reading Scale + Zen Ma) -------- */
  .quiz-focal {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 140px;
    margin-bottom: 32px;
  }
  .quiz-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 27px;
    font-weight: 600;
    line-height: 1.74;
    letter-spacing: 0.035em;
    color: var(--sumi);
  }
  @media (min-width: 860px) {
    .quiz-ja { font-size: 30px; }
  }

  .listen-medallion-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    padding: 12px 0;
  }
  .listen-medallion {
    width: 74px;
    height: 74px;
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
  .med-ic { width: 25px; height: 25px; margin-left: 2px; }
  .med-waves { display: none; align-items: center; gap: 3.5px; height: 22px; }
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
    50% { height: 19px; opacity: 1; }
  }
  .listen-prompt {
    margin: 0;
    font-size: 18px;
    font-weight: 400;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    text-align: center;
  }

  .choice-list {
    display: flex;
    flex-direction: column;
    gap: 13px;
  }
  .zen-choice {
    width: 100%;
    min-height: 64px;
    padding: 15px 22px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-family: var(--serif-jp);
    font-size: 22.5px;
    font-weight: 500;
    color: var(--sumi);
    letter-spacing: 0.03em;
    line-height: 1.44;
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
      font-size: 13px;
      color: var(--ink-3);
      font-variant-numeric: tabular-nums;
    }
  }

  .quiet-skip {
    display: block;
    width: 100%;
    text-align: center;
    padding: 12px 0 2px;
    font-size: 14.5px;
    color: var(--ink-3);
    letter-spacing: 0.05em;
  }

  /* -------- RESULT VIEW (3-Step Human Clarity: 句意 -> 为什么用 -> 变形与辨析) -------- */
  .result-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 24px;
    font-weight: 500;
    line-height: 1.76;
    letter-spacing: 0.03em;
    color: var(--sumi);
    white-space: pre-line;
  }
  .ans-hl {
    color: var(--moss);
    font-weight: 600;
  }
  .result-zh {
    margin: 10px 0 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.62;
    letter-spacing: 0.015em;
  }

  /* Tappable Japanese words + Instant Inline Zen Meaning Strip (Zero Google Search, Zero Modal Trap) */
  .w-tok {
    border-bottom: 1px solid rgba(28, 27, 24, 0.15);
    cursor: pointer;
    padding: 0 1px 1px;
    border-radius: 3px;
    transition: color 0.14s ease, background 0.14s ease, border-color 0.14s ease;
  }
  .w-tok:active, .w-tok.active-tok {
    color: var(--moss);
    background: var(--moss-soft);
    border-bottom-color: var(--moss);
  }

  .inline-lex {
    margin-top: 12px;
    min-height: 36px;
    padding: 8px 12px;
    border-radius: 7px;
    background: rgba(252, 251, 248, 0.78);
    border: 1px solid var(--hairline);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .inline-lex.empty {
    background: transparent;
    border-color: transparent;
    padding: 4px 0 0;
    min-height: 24px;
  }
  .ilex-hint {
    font-size: 13px;
    color: var(--ink-3);
    letter-spacing: 0.04em;
  }
  .ilex-main {
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px 9px;
    line-height: 1.48;
  }
  .ilex-surf {
    font-family: var(--serif-jp);
    font-size: 18px;
    font-weight: 600;
    color: var(--sumi);
  }
  .ilex-kana {
    font-size: 14.5px;
    color: var(--moss);
    font-weight: 500;
  }
  .ilex-zh {
    font-size: 16px;
    font-weight: 500;
    color: var(--sumi);
  }
  .ilex-meta {
    width: 100%;
    font-size: 13.5px;
    color: var(--ink-3);
  }
  .ilex-speak {
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--moss);
    padding: 4px 8px;
    border-radius: 5px;
    border: 1px solid rgba(43, 95, 73, 0.25);
  }

  .result-divider {
    height: 1px;
    background: var(--hairline);
    margin: 18px 0;
  }
  .result-logic {
    display: flex;
    flex-direction: column;
    gap: 11px;
  }
  .logic-line {
    margin: 0;
    font-size: 17px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.74;
    letter-spacing: 0.015em;
  }

  /* Architectural Sumi Buttons */
  .dock-row {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .sumi-btn {
    flex: 1;
    height: 54px;
    background: var(--sumi);
    color: var(--sheet);
    border-radius: 8px;
    font-size: 17px;
    font-weight: 500;
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .ghost-btn {
    height: 54px;
    padding: 0 20px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 15.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.04em;
  }

  /* ================= 4. TWO-COACH PODCAST SANCTUARY ("随身听") ================= */
  .radio-center {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 16px;
  }
  .radio-chap {
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.12em;
    color: var(--moss);
  }
  .radio-topic {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 26px;
    font-weight: 600;
    line-height: 1.45;
    color: var(--sumi);
  }
  .radio-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 22px;
    font-weight: 400;
    line-height: 1.76;
    color: var(--ink-2);
  }

  .radio-dock {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding-top: 12px;
  }
  .scrub-wrap { width: 100%; }
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
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: var(--sumi);
    cursor: pointer;
  }
  .time-pair {
    display: flex;
    justify-content: space-between;
    font-size: 13.5px;
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
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-2);
    padding: 10px 6px;
    font-variant-numeric: tabular-nums;
  }
  .play-toggle-btn {
    min-width: 132px;
    height: 50px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 16.5px;
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
    font-size: 14.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.05em;
    padding: 4px 2px;
  }
  .chap-link.active {
    color: var(--sumi);
    font-weight: 600;
  }

  /* ================= 5. ZEN LEDGER ("总表") ================= */
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
      grid-template-columns: 270px 1fr;
      gap: 46px;
      align-items: start;
    }
  }

  .pillar-list { margin-bottom: 24px; }
  .pillar-row {
    padding: 14px 0;
    border-bottom: 1px solid var(--hairline);
    cursor: pointer;
    opacity: 0.62;
    transition: opacity 0.18s ease;
  }
  .pillar-row.active { opacity: 1; }
  .pillar-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }
  .pillar-name {
    font-size: 16.5px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.03em;
  }
  .pillar-stat {
    font-size: 13.5px;
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
  .tier-links { display: flex; gap: 20px; }
  .tier-link {
    font-size: 15px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .tier-link.active {
    color: var(--sumi);
    font-weight: 600;
  }
  .zen-search {
    width: 132px;
    border: none;
    border-bottom: 1px solid var(--hairline-strong);
    background: transparent;
    padding: 4px 0;
    font-family: inherit;
    font-size: 14.5px;
    color: var(--sumi);
    outline: none;
    -webkit-user-select: text;
    user-select: text;
  }
  .zen-search::placeholder { color: var(--ink-3); }

  .ledger-item {
    padding: 14px 0;
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
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .li-dot.todo { background: var(--bengara); }
  .li-dot.wip { background: var(--ochre); }
  .li-dot.done { background: var(--moss); }
  .li-name {
    font-family: var(--serif-jp);
    font-size: 18.5px;
    font-weight: 500;
    color: var(--sumi);
  }
  .li-right {
    display: flex;
    align-items: baseline;
    gap: 14px;
    flex-shrink: 0;
  }
  .li-sub {
    font-size: 14px;
    color: var(--ink-3);
    max-width: 138px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .li-act {
    font-size: 14px;
    color: var(--moss);
    font-weight: 500;
  }
  .li-note {
    margin-top: 9px;
    padding-left: 16.5px;
    font-size: 15px;
    color: var(--ink-2);
    line-height: 1.62;
  }

  /* ================= 6. PROGRESS MODAL ================= */
  .modal-mask {
    position: fixed;
    inset: 0;
    background: rgba(28, 27, 24, 0.28);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 28px;
    z-index: 100;
  }
  .modal-mask.open { display: flex; }
  .modal-card {
    width: 100%;
    max-width: 365px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 10px;
    padding: 26px;
  }
  .modal-h { margin: 0 0 12px; font-size: 18px; font-weight: 600; letter-spacing: 0.04em; }
  .modal-body { margin: 0 0 14px; font-size: 16px; color: var(--ink-2); line-height: 1.85; font-variant-numeric: tabular-nums; }
  .modal-promise { margin: 0 0 22px; padding-top: 12px; border-top: 1px solid var(--hairline); font-size: 14.5px; color: var(--moss); line-height: 1.65; font-weight: 500; }
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

  <!-- 2. DUAL DAILY LOCK HORIZON -->
  <div class="zen-horizon" id="green-board" onclick="openSessionModal()">
    <div class="horizon-meta">
      <span id="gm-left-txt">做题 <b>0/50</b> · 听 <b>0/35分</b></span>
      <span id="gm-right-txt">预计 <b>108分</b> · 冲120+</span>
    </div>
    <div class="horizon-track">
      <div class="horizon-fill" id="gm-fill" style="width:0%"></div>
    </div>
  </div>

  <!-- 3A. ADAPTIVE QUIZ STAGE -->
  <main class="zen-panel" id="tutor-view">
    <div class="stage-wrap" id="voice-card"></div>
  </main>

  <!-- 3B. TWO-COACH CONVERSATIONAL PODCAST SANCTUARY -->
  <section class="zen-panel hidden" id="radio-view">
    <div class="stage-wrap">
      <div class="meta-bar">
        <span class="overline" id="radio-date-pill">双人对谈</span>
        <div class="quiet-actions">
          <button class="text-btn" id="radio-spd-btn" onclick="cycleRadioSpeed()">1.0x</button>
        </div>
      </div>

      <div class="radio-center">
        <div class="radio-chap" id="radio-chap-lbl">语法</div>
        <h2 class="radio-topic" id="radio-live-title">阿哲 · 小夏　今日重点对谈</h2>
        <p class="radio-ja" id="radio-live-ja"></p>
        <div class="inline-lex empty" id="radio-inline-lex"><span class="ilex-hint">点日文词即显词义</span></div>
      </div>

      <div class="radio-dock">
        <div class="scrub-wrap">
          <input type="range" class="zen-range" id="radio-seek" min="0" max="2100" value="0" step="1" oninput="onRadioScrub(this.value)" />
          <div class="time-pair">
            <span id="radio-cur-time">00:00</span>
            <span id="radio-tot-time">35:00</span>
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

<div class="modal-mask" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-card" id="modal-content"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.15, 1.3, 1.5];
const RADIO_SPEEDS = [1.0, 1.15, 1.3];
const ADAPTIVE_KEY = "n3_adaptive_v11_" + DATA.plan_date;
const LEGACY_V10_KEY = "n3_adaptive_v10_" + DATA.plan_date;
const LEGACY_V9_KEY = "n3_adaptive_v9_" + DATA.plan_date;
const RADIO_POS_KEY = "n3_radio_pos_" + (DATA.radio.date || DATA.plan_date);

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.0");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.0;
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

// Block native mobile selection / Chrome Touch-to-Search bar on Japanese tokens
document.addEventListener("contextmenu", e => {
  if (e.target && e.target.closest && e.target.closest(".w-tok")) {
    e.preventDefault();
  }
});

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

// ================= MASTER ALGORITHM (QUIZ-FIRST + PODCAST DUAL LOCK FOR 120+) =================
function createFreshAdaptiveState() {
  const pts = {};
  DATA.points.forEach(p => {
    pts[p.id] = {
      status: "unseen",
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
    radioMaxSec: 0,
    pts: pts,
    masteryOverrides: {}
  };
}

function loadAdaptiveState() {
  const base = createFreshAdaptiveState();
  try {
    const raw = localStorage.getItem(ADAPTIVE_KEY) || localStorage.getItem(LEGACY_V10_KEY) || localStorage.getItem(LEGACY_V9_KEY);
    if (raw) {
      const saved = JSON.parse(raw);
      if (saved && saved.pts) {
        base.step = saved.step || 0;
        base.lastPointId = saved.lastPointId || null;
        base.hotFamily = saved.hotFamily || null;
        base.radioMaxSec = saved.radioMaxSec || 0;
        base.masteryOverrides = saved.masteryOverrides || {};
        Object.keys(base.pts).forEach(id => {
          if (saved.pts[id]) {
            base.pts[id].status = saved.pts[id].status || "unseen";
            base.pts[id].audioPrimed = !!saved.pts[id].audioPrimed;
            base.pts[id].variantIdx = saved.pts[id].variantIdx || 0;
            base.pts[id].useVariant = !!saved.pts[id].useVariant;
            base.pts[id].dueStep = saved.pts[id].dueStep || 0;
            base.pts[id].wrongCount = saved.pts[id].wrongCount || 0;
          }
        });
      }
    }
    const savedRadioPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    if (savedRadioPos > base.radioMaxSec) base.radioMaxSec = savedRadioPos;
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

function computeDaily120Metrics() {
  const totalCards = Math.max(1, DATA.points.length);
  const greenCnt = DATA.points.filter(p => A.pts[p.id] && A.pts[p.id].status === "green").length;
  const quizRatio = Math.min(1.0, greenCnt / totalCards);

  const radioDur = Math.max(600, DATA.radio.duration_sec || 2100);
  const targetMins = Math.max(1, Math.round(radioDur / 60));
  const listenedSec = Math.min(radioDur, Math.max(0, A.radioMaxSec || 0));
  const listenedMins = Math.min(targetMins, Math.floor(listenedSec / 60));
  const radioRatio = Math.min(1.0, listenedSec / (radioDur * 0.92));

  // Combined daily completion: 60% from 50 daily questions + 40% from daily podcast
  const dailyLockPct = Math.min(100, Math.round((quizRatio * 0.60 + radioRatio * 0.40) * 100));

  // Realistic projected JLPT N3 total score (/180):
  // Reading foundation + 27 mastered grammar points starts at 108 pts.
  // Finishing today's 50 questions locks +14 pts; finishing today's podcast locks +10 pts -> 132 pts (comfortably >120!).
  const projScore = Math.round(108 + quizRatio * 14 + radioRatio * 10);

  return {
    totalCards,
    greenCnt,
    quizDone: greenCnt >= totalCards,
    targetMins,
    listenedMins,
    radioDone: radioRatio >= 0.98,
    dailyLockPct,
    projScore
  };
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
    return s.status === "learning" && s.dueStep <= A.step;
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
  viewStage = "quiz";
  activeQuizObj = getQuizForPoint(p, ps);
  currentChoices = prepareChoices(activeQuizObj, ps.wrongCount);
}
setupCurrentTurn();

// ================= AUDIO PLAYERS & COMPLETE LEXICON =================
const player = new Audio();
player.preload = "auto";
const wordPlayer = new Audio();
wordPlayer.preload = "auto";
const radioPlayer = new Audio();
radioPlayer.preload = "metadata";

const PARTICLE_FALLBACK = {
  "では": { kana: "では", pos: "复合助词", zh: "在……里面（范围或场所主题）" },
  "には": { kana: "には", pos: "复合助词", zh: "对于……来说；向……" },
  "から": { kana: "から", pos: "助词", zh: "从……；因为……" },
  "まで": { kana: "まで", pos: "助词", zh: "到……为止" },
  "ので": { kana: "ので", pos: "接续助词", zh: "因为……（客观原因）" },
  "のだ": { kana: "のだ", pos: "说明句尾", zh: "是因为……呀（解释说明）" },
  "だよ": { kana: "だよ", pos: "句尾语气", zh: "……哦，是……呀" },
  "は": { kana: "は（读わ）", pos: "提示助词", zh: "提示整句话谈论的主题" },
  "が": { kana: "が", pos: "主格助词", zh: "标出动作或状态的主体" },
  "を": { kana: "を（读お）", pos: "宾格助词", zh: "标出动作直接作用的宾语" },
  "に": { kana: "に", pos: "格助词", zh: "标出时间点、对象或目的地" },
  "で": { kana: "で", pos: "格助词", zh: "标出动作场所、工具或原因" },
  "と": { kana: "と", pos: "助词", zh: "和……；一……就……；引述内容" },
  "も": { kana: "も", pos: "提示助词", zh: "也，都，连……也" },
  "の": { kana: "の", pos: "领格助词", zh: "的" },
  "へ": { kana: "へ（读え）", pos: "方向助词", zh: "朝向，往……去" },
  "よ": { kana: "よ", pos: "终助词", zh: "句尾提醒或告知语气（哦、呀）" },
  "ね": { kana: "ね", pos: "终助词", zh: "句尾确认或共鸣语气（吧、呢）" },
  "か": { kana: "か", pos: "疑问助词", zh: "吗（句尾表疑问）" }
};

Object.keys(PARTICLE_FALLBACK).forEach(pk => {
  if (!DATA.words[pk]) DATA.words[pk] = PARTICLE_FALLBACK[pk];
});

const DICT_KEYS = Object.keys(DATA.words).sort((a, b) => b.length - a.length);

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Tokenize full sentence first so multi-character words & conjugated chunks never get split in half!
function renderJapaneseWithHighlight(text, highlightTarget) {
  const src = String(text || "");
  const target = String(highlightTarget || "").split("（")[0].trim();
  const hlIdx = (target && target.length >= 1) ? src.indexOf(target) : -1;
  const hlEnd = hlIdx >= 0 ? hlIdx + target.length : -1;

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
      const tStart = i;
      const tEnd = i + matched.length;
      const escW = escapeHtml(matched);
      let innerHtml = "";
      if (hlIdx >= 0 && tStart < hlEnd && tEnd > hlIdx) {
        const s1 = Math.max(tStart, hlIdx) - tStart;
        const s2 = Math.min(tEnd, hlEnd) - tStart;
        innerHtml =
          escapeHtml(matched.slice(0, s1)) +
          `<span class="ans-hl">${escapeHtml(matched.slice(s1, s2))}</span>` +
          escapeHtml(matched.slice(s2));
      } else {
        innerHtml = escW;
      }
      out += `<span class="w-tok" data-w="${escW}">${innerHtml}</span>`;
      i = tEnd;
    } else {
      const ch = escapeHtml(src[i]);
      if (hlIdx >= 0 && i >= hlIdx && i < hlEnd) {
        out += `<span class="ans-hl">${ch}</span>`;
      } else {
        out += ch;
      }
      i += 1;
    }
  }
  return out;
}

function annotateJapanese(text) {
  return renderJapaneseWithHighlight(text, "");
}

function annotateSentenceWithAnswer(fullJa, ans) {
  return renderJapaneseWithHighlight(fullJa, ans);
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
  if (spdBtn) spdBtn.textContent = `${expSpeed}x`;
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

// ================= TWO-COACH PODCAST ENGINE =================
let radioInitialized = false;
let lastSavedSec = -1;
let lastRenderedSegIdx = -1;

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
    seekEl.max = Math.ceil(DATA.radio.duration_sec || 2100);
    document.getElementById("radio-tot-time").textContent = formatMMSS(DATA.radio.duration_sec || 2100);
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
      title: segTitle || "N3 每日随身听",
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
  const dur = radioPlayer.duration || DATA.radio.duration_sec || 2100;
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

  if (t > (A.radioMaxSec || 0)) {
    const prevMin = Math.floor((A.radioMaxSec || 0) / 60);
    A.radioMaxSec = Math.floor(t);
    if (Math.floor(A.radioMaxSec / 60) !== prevMin) {
      saveAdaptiveState();
      renderGreenBoard();
    }
  }

  const segs = DATA.radio.segments || [];
  let curSeg = null;
  let segIdx = -1;
  for (let i = 0; i < segs.length; i++) {
    if (t >= segs[i].start && t < segs[i].end) {
      curSeg = segs[i];
      segIdx = i;
      break;
    }
  }

  if (curSeg) {
    if (segIdx !== lastRenderedSegIdx) {
      lastRenderedSegIdx = segIdx;
      const chaps = DATA.radio.chapters || [];
      const chapObj = chaps[curSeg.chapter] || chaps[0];
      if (chapObj) {
        document.getElementById("radio-chap-lbl").textContent = chapObj.title.replace(/^[①②③④]\s*/, "");
        renderRadioChapters(chapObj.idx);
      }
      document.getElementById("radio-live-title").textContent = curSeg.title;
      document.getElementById("radio-live-ja").innerHTML = annotateJapanese(curSeg.ja_focus || "");
      clearInlineLexicon("radio-inline-lex");
      setupMediaSession(curSeg.title);
    }

    if (curSeg.point_id && A.pts[curSeg.point_id] && t >= curSeg.end - 6) {
      const ps = A.pts[curSeg.point_id];
      if (!ps.audioPrimed) {
        ps.audioPrimed = true;
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
radioPlayer.addEventListener("pause", () => {
  syncRadioUI();
  scheduleCloudPush();
});
radioPlayer.addEventListener("ended", () => {
  const dur = radioPlayer.duration || DATA.radio.duration_sec || 2100;
  A.radioMaxSec = Math.ceil(dur);
  saveAdaptiveState();
  renderGreenBoard();
  syncRadioUI();
  scheduleCloudPush();
});
radioPlayer.addEventListener("loadedmetadata", () => {
  updateRadioLiveDisplay(radioPlayer.currentTime || 0);
  renderGreenBoard();
});
radioPlayer.addEventListener("timeupdate", () => {
  const t = radioPlayer.currentTime || 0;
  updateRadioLiveDisplay(t);
  if (Math.abs(t - lastSavedSec) >= 3) {
    lastSavedSec = t;
    try { localStorage.setItem(RADIO_POS_KEY, String(Math.floor(t))); } catch (e) {}
    saveAdaptiveState();
  }
});

// ================= SILENT CLOUD SYNC & QUIZ ACTIONS =================
const CLOUD_SYNC_TOPIC = "n3pwa_8c4e91f2a7d03b65e2194f8a0c7d3e52";
const CLOUD_BUF_KEY = "n3_cloud_log_buf_v1";
const CLOUD_SENT_SIG_KEY = "n3_cloud_sent_sig_v1";
let cloudPushTimer = null;

function loadCloudLogBuf() {
  try {
    const raw = localStorage.getItem(CLOUD_BUF_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch (e) {
    return [];
  }
}

function saveCloudLogBuf(arr) {
  try {
    localStorage.setItem(CLOUD_BUF_KEY, JSON.stringify(arr.slice(-35)));
  } catch (e) {}
}

function flushCloudSyncNow() {
  if (!navigator.onLine) return;
  const buf = loadCloudLogBuf();
  const rSec = Math.floor(A.radioMaxSec || 0);
  const lastTs = buf.length ? buf[buf.length - 1].ts : "";
  const sig = `${DATA.plan_date}|${lastTs}|${Math.floor(rSec / 30)}`;
  try {
    if (localStorage.getItem(CLOUD_SENT_SIG_KEY) === sig) return;
  } catch (e) {}
  if (!buf.length && rSec < 15) return;

  const payload = JSON.stringify({
    v: 1,
    date: DATA.plan_date,
    radioSec: rSec,
    logs: buf.slice(-25)
  });
  fetch(`https://ntfy.sh/${CLOUD_SYNC_TOPIC}`, {
    method: "POST",
    mode: "cors",
    keepalive: true,
    body: payload
  }).then(res => {
    if (res && res.ok) {
      try { localStorage.setItem(CLOUD_SENT_SIG_KEY, sig); } catch (e) {}
    }
  }).catch(() => {});
}

function scheduleCloudPush() {
  if (cloudPushTimer) clearTimeout(cloudPushTimer);
  cloudPushTimer = setTimeout(flushCloudSyncNow, 1100);
}

function pullCloudSync() {
  if (!navigator.onLine) return;
  fetch(`https://ntfy.sh/${CLOUD_SYNC_TOPIC}/json?since=12h&poll=1`, { cache: "no-store" })
    .then(r => r.ok ? r.text() : "")
    .then(txt => {
      if (!txt) return;
      const lines = txt.split("\n").filter(Boolean);
      const localBuf = loadCloudLogBuf();
      const seenTs = new Set(localBuf.map(x => x.ts));
      let changed = false;

      lines.forEach(ln => {
        try {
          const ev = JSON.parse(ln);
          if (ev.event !== "message" || !ev.message) return;
          const msg = JSON.parse(ev.message);
          if (msg.date === DATA.plan_date && typeof msg.radioSec === "number" && msg.radioSec > (A.radioMaxSec || 0)) {
            A.radioMaxSec = msg.radioSec;
            changed = true;
          }
          const logs = Array.isArray(msg.logs) ? msg.logs : (msg.ts ? [msg] : []);
          logs.forEach(rec => {
            if (!rec || !rec.ts) return;
            if (!seenTs.has(rec.ts)) {
              seenTs.add(rec.ts);
              localBuf.push(rec);
            }
            const ok = String(rec.correct) === "true";
            const again = String(rec.ask_again) === "true";
            const tier = (ok && !again) ? "done" : "todo";
            if (rec.point && A.masteryOverrides[rec.point] !== tier) {
              A.masteryOverrides[rec.point] = tier;
              changed = true;
            }
            if (rec.date === DATA.plan_date && rec.pid && A.pts[rec.pid]) {
              const targetStatus = (ok && !again) ? "green" : "learning";
              if (A.pts[rec.pid].status !== targetStatus) {
                A.pts[rec.pid].status = targetStatus;
                changed = true;
              }
            }
          });
        } catch (e) {}
      });

      if (changed) {
        localBuf.sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
        saveCloudLogBuf(localBuf);
        applyMasteryOverrides();
        saveAdaptiveState();
        renderGreenBoard();
        if (activeMode === "dash") renderDash();
      }
    })
    .catch(() => {});
}

function syncBackendRecord(p, qid, choice, isCorrect, askAgain, newTier) {
  A.masteryOverrides[p.point_key] = newTier;
  A.masteryOverrides[p.point] = newTier;
  applyMasteryOverrides();
  saveAdaptiveState();

  const rec = {
    pid: p.id,
    id: qid,
    point: p.point_key || p.point,
    correct: String(!!isCorrect),
    ask_again: String(!!askAgain),
    date: DATA.plan_date,
    ts: new Date().toISOString()
  };
  const buf = loadCloudLogBuf();
  buf.push(rec);
  saveCloudLogBuf(buf);
  scheduleCloudPush();

  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    fetch("./api/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rec)
    }).catch(() => {});
  }
}

function completeTeachCard() {
  stopQuizAudio();
  clearActiveWordToken();
  const p = getPointById(curPointId);
  if (p) {
    const ps = A.pts[p.id];
    ps.status = "learning";
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
  clearActiveWordToken();
  const p = getPointById(curPointId);
  if (!p) return;
  const ps = A.pts[p.id];
  ps.status = "learning";
  ps.wrongCount += 1;
  if (p.variants && p.variants.length > 0) ps.useVariant = true;
  ps.dueStep = A.step + 4;
  A.hotFamily = p.family;
  syncBackendRecord(p, activeQuizObj ? activeQuizObj.id : p.id, "先看考点", false, false, "todo");
  viewStage = "teach";
  renderTutor();
  playMainClip(p.teach.audio, "teach", false);
}

function submitAnswer(val) {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  clearActiveWordToken();
  stopQuizAudio();
  pickedVal = val;
  viewStage = "result";

  const p = getPointById(curPointId);
  const ps = A.pts[p.id];
  const isCorrect = (val === activeQuizObj.answer);

  if (isCorrect) {
    ps.status = "green";
    A.hotFamily = null;
    syncBackendRecord(p, activeQuizObj.id, val, true, false, "done");
  } else {
    ps.status = "learning";
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
  clearActiveWordToken();
  if (forceRetestCurrent && curPointId) {
    const p = getPointById(curPointId);
    const ps = A.pts[curPointId];
    ps.status = "learning";
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
  const keepRadio = A.radioMaxSec || 0;
  A = createFreshAdaptiveState();
  A.masteryOverrides = keepOverrides;
  A.radioMaxSec = keepRadio;
  saveAdaptiveState();
  closeModal();
  setupCurrentTurn();
  renderTutor();
}

function renderGreenBoard() {
  document.getElementById("countdown-txt").innerHTML = `残 <strong>${computeDaysLeft()}</strong> 日`;
  const m = computeDaily120Metrics();

  const quizPart = m.quizDone ? `做题 <b class="moss">✓</b>` : `做题 <b>${m.greenCnt}/${m.totalCards}</b>`;
  const radioPart = m.radioDone ? `随身听 <b class="moss">✓</b>` : `听 <b>${m.listenedMins}/${m.targetMins}分</b>`;
  document.getElementById("gm-left-txt").innerHTML = `${quizPart} · ${radioPart}`;

  if (m.projScore >= 120) {
    document.getElementById("gm-right-txt").innerHTML = `预计 <b class="moss">${m.projScore}分 · 稳过120</b>`;
  } else {
    document.getElementById("gm-right-txt").innerHTML = `预计 <b>${m.projScore}分</b> · 冲120+`;
  }
  document.getElementById("gm-fill").style.width = `${m.dailyLockPct}%`;
}

function renderTutor() {
  renderGreenBoard();
  const box = document.getElementById("voice-card");

  if (viewStage === "done" || !curPointId) {
    const m = computeDaily120Metrics();
    box.innerHTML = `
      <div class="meta-bar"><span class="overline ok">${m.radioDone ? "今日双项圆满 · 稳过 120 分" : "五十道题已全部刷绿"}</span></div>
      <div class="focal-space">
        <h2 class="point-heading">${m.radioDone ? "今日题与随身听皆已完成" : "今日五十题已过关"}</h2>
        <p class="logic-line">${m.radioDone
          ? `今日预计总分已锁定在 ${m.projScore} 分。每天保持这一套节奏，十二月考场上稳稳站上 120 分以上。`
          : `做题部分已拿满，当前预计 ${m.projScore} 分。再去把今日随身听顺完，就能稳稳锁定 132 分。`}</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          <button class="ghost-btn" onclick="resetTodayMission()">再来一轮</button>
          ${m.radioDone
            ? `<button class="sumi-btn" onclick="switchMode('dash')">查看总表</button>`
            : `<button class="sumi-btn" onclick="switchMode('radio', true)">去听随身听 · 锁死120+</button>`}
        </div>
      </div>
    `;
    return;
  }

  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];

  // -------- TEACH (on demand when user taps 先看考点) --------
  if (viewStage === "teach") {
    warmAudio(p.teach.audio);
    warmAudio(p.primary.q_audio);
    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline warm">${escapeHtml(p.subject)} · 考点梳理</span>
        <div class="quiet-actions">
          <button class="text-btn" id="exp-replay-btn" onclick="playMainClip('${p.teach.audio}', 'teach', true)">讲解</button>
          <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed}x</button>
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
        ${p.teach.zh_meaning ? `<p class="example-zh">${escapeHtml(p.teach.zh_meaning)}</p>` : ""}
        <div class="inline-lex empty" id="tutor-inline-lex"><span class="ilex-hint">点日文词即显词义</span></div>
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
    else if (ps.audioPrimed) label += " · 随身听已讲";

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

  // -------- RESULT (3-Step Clear Human Order: ① 句意 -> ② 为什么用 -> ③ 变形与辨析) --------
  const q = activeQuizObj || p.primary;
  const isCorrect = pickedVal === q.answer;
  const overCls = isCorrect ? "overline ok" : "overline ng";
  const overTxt = isCorrect ? "已变绿" : `误选「${pickedVal}」 · 稍后复考`;

  box.innerHTML = `
    <div class="meta-bar">
      <span class="${overCls}">${escapeHtml(overTxt)}</span>
      <div class="quiet-actions">
        <button class="text-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">原题</button>
        <button class="text-btn" id="exp-replay-btn" onclick="playMainClip(activeQuizObj.exp_audio, 'exp', true)">讲解</button>
        <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed}x</button>
      </div>
    </div>

    <div class="focal-space">
      <div class="result-ja">${annotateSentenceWithAnswer(q.full_ja, q.answer)}</div>
      ${q.zh_meaning ? `<p class="result-zh">${escapeHtml(q.zh_meaning)}</p>` : ""}
      <div class="inline-lex empty" id="tutor-inline-lex"><span class="ilex-hint">点日文词即显词义</span></div>
      <div class="result-divider"></div>
      <div class="result-logic">
        ${q.why_line ? `<p class="logic-line">${escapeHtml(q.why_line)}</p>` : ""}
        ${q.form_line ? `<p class="logic-line">${escapeHtml(q.form_line)}</p>` : ""}
      </div>
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

// ================= INSTANT INLINE WORD MEANING (ZERO MODAL, ZERO GOOGLE BAR) =================
let activeTokEl = null;

function clearActiveWordToken() {
  if (activeTokEl) {
    activeTokEl.classList.remove("active-tok");
    activeTokEl = null;
  }
}

function clearInlineLexicon(boxId) {
  const el = document.getElementById(boxId);
  if (!el) return;
  el.className = "inline-lex empty";
  el.innerHTML = `<span class="ilex-hint">点日文词即显词义</span>`;
}

function speakJapaneseFallback(text) {
  if (!("speechSynthesis" in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ja-JP";
    u.rate = 0.92;
    window.speechSynthesis.speak(u);
  } catch (e) {}
}

function playWordAudio(surface, pauseMainIfNeeded) {
  const info = DATA.words[surface];
  if (!info) return;
  if (pauseMainIfNeeded && !player.paused) {
    player.pause();
    syncAudioButtons();
  }
  if (info.audio) {
    wordPlayer.src = info.audio;
    wordPlayer.currentTime = 0;
    wordPlayer.playbackRate = 1.0;
    wordPlayer.play().catch(() => speakJapaneseFallback(info.kana || surface));
  } else {
    speakJapaneseFallback(info.kana || surface);
  }
}

function playDirectUrl(url) {
  if (!url) return;
  if (!player.paused) player.pause();
  wordPlayer.src = url;
  wordPlayer.currentTime = 0;
  wordPlayer.playbackRate = 1.0;
  wordPlayer.play().catch(() => {});
}

function showInlineWordMeaning(surface, tokEl) {
  const info = DATA.words[surface];
  if (!info) return;
  clearActiveWordToken();
  if (tokEl && tokEl.classList) {
    activeTokEl = tokEl;
    activeTokEl.classList.add("active-tok");
  }

  const targetBoxId = activeMode === "radio" ? "radio-inline-lex" : "tutor-inline-lex";
  const box = document.getElementById(targetBoxId);
  if (!box) return;

  const headDiff = info.head && info.head !== surface ? `原形 ${info.head}` : "";
  const metaLine = [headDiff, info.pos, info.tip].filter(Boolean).join(" · ");

  box.className = "inline-lex";
  box.innerHTML = `
    <div class="ilex-main">
      <span class="ilex-surf">${escapeHtml(surface)}</span>
      ${info.kana && info.kana !== surface ? `<span class="ilex-kana">${escapeHtml(info.kana)}${info.pitch ? " " + escapeHtml(info.pitch) : ""}</span>` : (info.pitch ? `<span class="ilex-kana">${escapeHtml(info.pitch)}</span>` : "")}
      <span class="ilex-zh">${escapeHtml(info.zh || "")}</span>
      ${metaLine ? `<div class="ilex-meta">${escapeHtml(metaLine)}</div>` : ""}
    </div>
    <button class="ilex-speak" onclick='event.stopPropagation();playWordAudio(${JSON.stringify(surface)}, true)'>发音</button>
  `;

  // Auto-pronounce the tapped word ONLY if teacher explanation / podcast is currently quiet,
  // so looking up a word while listening never cuts off the teacher mid-sentence!
  if (player.paused && radioPlayer.paused) {
    playWordAudio(surface, false);
  }
}

document.addEventListener("click", e => {
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (tok && !(activeMode === "tutor" && viewStage === "quiz")) {
    e.preventDefault();
    e.stopPropagation();
    showInlineWordMeaning(tok.dataset.w, tok);
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
  clearActiveWordToken();
  if (m !== "tutor") stopQuizAudio();

  document.getElementById("app-shell").classList.toggle("wide-mode", m === "dash");
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-radio").classList.toggle("active", m === "radio");
  document.getElementById("tab-dash").classList.toggle("active", m === "dash");

  document.getElementById("green-board").style.display = (m === "dash") ? "none" : "block";
  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("radio-view").classList.toggle("hidden", m !== "radio");
  document.getElementById("dash-view").classList.toggle("hidden", m !== "dash");

  renderGreenBoard();

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
    listEl.innerHTML = `<div style="padding:36px 0;color:var(--ink-3);font-size:15px;">此处已清空</div>`;
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
  const m = computeDaily120Metrics();
  document.getElementById("modal-content").innerHTML = `
    <h3 class="modal-h">今日 120+ 锁定进度</h3>
    <p class="modal-body">
      今日做题　　<strong>${m.greenCnt} / ${m.totalCards} 题</strong><br/>
      今日随身听　<strong>${m.listenedMins} / ${m.targetMins} 分钟</strong><br/>
      当前预计分　<strong>${m.projScore} / 180 分</strong><br/>
      今日双项满　<strong>132 分（稳过 120 分线）</strong>
    </p>
    <p class="modal-promise">每天把 50 道题刷绿、把一期随身听听完，十二月考场上一定稳站 120 分以上。</p>
    <div class="dock-row">
      <button class="ghost-btn" onclick="resetTodayMission()">重做题</button>
      <button class="sumi-btn" onclick="closeModal()">继续</button>
    </div>
  `;
  document.getElementById("app-modal").classList.add("open");
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    flushCloudSyncNow();
  } else if (document.visibilityState === "visible") {
    pullCloudSync();
  }
});
window.addEventListener("online", () => {
  flushCloudSyncNow();
  pullCloudSync();
});

function initApp() {
  const params = new URLSearchParams(location.search);
  const m = params.get("mode");
  if (m === "dash") switchMode("dash");
  else if (m === "radio" || m === "walk") switchMode("radio", false);
  else renderTutor();
  setTimeout(() => {
    flushCloudSyncNow();
    pullCloudSync();
  }, 400);
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
    "Wrote Zen v11 N3 Platform:",
    HTML_PATH,
    "points:",
    len(ordered_points),
    "lexicon:",
    len(rich_words),
    "size:",
    len(final_html),
)
