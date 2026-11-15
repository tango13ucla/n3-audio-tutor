#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiles the Japanese Zen Edition of the JLPT N3 Adaptive & Three-Host Salon Platform (index.html — Zen v12).
Aesthetic Philosophy: 禅 (Zen) · 余白 (Ma) · 新潮文庫級組版 (Optimal Literary Editorial Typography)
- Pure native Japanese question reading (zero "请听题", zero "空欄", zero "选", zero spoilers).
- True blind-ear JLPT N3 listening: spoken 1/2/3 choices in audio, crisp [1] [2] [3] buttons on screen.
- Calm "不确定 · 直接看讲解" on every card so zero blind guessing ever turns a weak point green.
- Distinct Desktop vs Phone ergonomics: Desktop optical-center cursor-adjacent Next + scroll-wheel advance; Phone thumb-zone + swipe-left advance.
- 《锵锵三人行》 3-host cultural salon podcast starting directly at 00:00 with zero date or countdown clutter.
- Local storage historical union-merge + 1-tap cross-device sync link (#sync=...).
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
from tutor_data import KANA_ADVERBS_36, TUTOR_ITEMS, WORD_DICT

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
    "display_date": "锵锵三人",
    "audio_url": "./audio/daily_radio.mp3",
    "duration_sec": 2100.0,
    "duration_label": "36 分钟",
    "hosts": "文涛 · 文道 · 子东",
    "chapters": [
        {"idx": 0, "title": "逐客茶", "start": 0},
        {"idx": 1, "title": "圆山町", "start": 380},
        {"idx": 2, "title": "早高峰", "start": 740},
        {"idx": 3, "title": "银座夜话", "start": 1100},
        {"idx": 4, "title": "阴翳之美", "start": 1460},
        {"idx": 5, "title": "歌舞伎町", "start": 1820},
    ],
    "segments": [],
}
if os.path.exists(RADIO_META_PATH):
    try:
        with open(RADIO_META_PATH, encoding="utf-8") as f:
            loaded_rm = json.load(f)
            if loaded_rm.get("audio_url"):
                radio_meta = loaded_rm
                radio_meta["display_date"] = "锵锵三人"
                if not radio_meta.get("hosts") or any(old_h in radio_meta.get("hosts", "") for old_h in ("阿哲", "老文", "小夏")):
                    radio_meta["hosts"] = "文涛 · 文道 · 子东"
    except Exception:
        pass

g_state_map = {p["name"]: p for p in live_state.get("grammar_points", [])}
h_state_map = {p["id"]: p for p in live_state.get("henkei_points", [])}
v_state_map = {p["word"]: p for p in live_state.get("vocab_tracked", [])}
l_state_map = {p["id"]: p for p in live_state.get("listening_points", [])}

# Exclude non-idiomatic multi-word phrases so users can tap specific individual words cleanly
DROP_MULTIWORD_PHRASES = {
    "小さな子ども", "目線を合わせる", "ひざを曲げて", "耳をすまして", "手が滑って",
    "道に迷っていたら", "走っている途中", "話し合った結果", "大きな声", "強い風",
    "急な仕事", "親切な人", "混む前に", "あの二人", "この本", "寝る前",
    "子どもの頃", "後ろの席", "降りる駅", "隣の人", "十一時以降", "１１時以降",
    "夜遅くまで", "甘い物", "目の前", "予約しておく", "コピーしといて",
}

word_audio_map = audio_manifest.get("words", {})
merged_raw_words = {}
for src_dict in (SENTENCE_LEXICON, WORD_DICT, EXTRA_WORDS):
    for surf, info in src_dict.items():
        if surf in DROP_MULTIWORD_PHRASES and surf not in v_state_map:
            continue
        if surf in merged_raw_words:
            merged_raw_words[surf] = {**merged_raw_words[surf], **info}
        else:
            merged_raw_words[surf] = dict(info)
for kw, pitch, desc in CORE_N3_KANA_VOCAB:
    if kw not in merged_raw_words:
        merged_raw_words[kw] = {
            "head": kw,
            "kana": kw,
            "pitch": pitch,
            "pos": "副詞",
            "zh": desc.split("（")[0],
            "tip": desc,
        }
for fam in KANA_ADVERBS_36:
    for pr in fam.get("pairs", []):
        for side in ("a", "b"):
            ad = pr[side]
            aw = ad["w"]
            if aw not in merged_raw_words:
                merged_raw_words[aw] = {
                    "head": aw,
                    "kana": aw,
                    "pitch": ad.get("pitch", ""),
                    "pos": "副詞",
                    "zh": ad.get("zh", ""),
                    "tip": ad.get("colloc", ""),
                }

rich_words = {}
for surf, info in merged_raw_words.items():
    entry = dict(info)
    alias = info.get("audio_alias")
    entry["audio"] = word_audio_map.get(surf) or (word_audio_map.get(alias, "") if alias else "")
    rich_words[surf] = entry


def resolve_word_audio(w: str) -> str:
    return rich_words.get(w, {}).get("audio") or word_audio_map.get(w, "")

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
        return ""
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


RECENT_GENERIC_LABELS = {"口语听辨", "高频假名副词", "核心词汇", "语法", "活用"}
recent_weak_keys = set()
log_path = os.path.join(BASE_DIR, "practice_log.jsonl")
if os.path.exists(log_path):
    try:
        with open(log_path, encoding="utf-8") as lf:
            for ln in [x.strip() for x in lf if x.strip()][-160:]:
                rec = json.loads(ln)
                if (
                    str(rec.get("correct", "")).lower() == "false"
                    or str(rec.get("ask_again", "")).lower() == "true"
                    or str(rec.get("choice", "")).strip() == "不确定"
                ):
                    pt_lbl = str(rec.get("point", "")).strip()
                    rec_qid = str(rec.get("id", "")).strip()
                    if pt_lbl and pt_lbl not in RECENT_GENERIC_LABELS:
                        recent_weak_keys.add(pt_lbl)
                    if rec_qid:
                        recent_weak_keys.add(rec_qid)
    except Exception:
        pass


def weakness_multiplier(status: str, qid: str = "", point_key: str = "") -> float:
    base = 0.20
    if status == "red":
        base = 1.00
    elif status in ("orange", "gray"):
        base = 0.92
    elif status == "yellow":
        base = 0.62
    if (qid and qid in recent_weak_keys) or (point_key and point_key in recent_weak_keys):
        base += 0.38
    return base


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
            "choices": c75.get("choices") or vc["choices"],
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

    choices = c75.get("choices") or t_item.get("choices") or fallback_opts
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
    roi_score = round(exam_weight * weakness_multiplier(pt_status, qid, point_key), 3)
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
        "roi_score": round(w * weakness_multiplier(pt_status, qid, ext["point_key"]), 3),
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
            "choices": c75.get("choices") or ext["choices"],
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

plan_date_str = (
    live_state.get("study_date")
    or radio_meta.get("date")
    or live_state.get("updated_at", plan.get("plan_date", "2026-11-14"))[:10]
)
cloud_cfg_path = os.path.join(BASE_DIR, "cloud_sync_config.json")
cloud_snap_path = os.path.join(BASE_DIR, "cloud_state_snapshot.json")
cloud_cfg = {}
if os.path.exists(cloud_cfg_path):
    try:
        with open(cloud_cfg_path, encoding="utf-8") as f:
            cloud_cfg = json.load(f)
    except Exception:
        pass

cloud_snap = {}
if os.path.exists(cloud_snap_path):
    try:
        with open(cloud_snap_path, encoding="utf-8") as f:
            cloud_snap = json.load(f)
    except Exception:
        pass

seeded_day = (cloud_snap.get("dates") or {}).get(plan_date_str) or {}
seeded_overrides = cloud_snap.get("masteryOverrides") or {}

vocab_base_done = sum(1 for it in vocab_items if it["tier"] == "done")

payload = json.dumps({
    "plan_date": plan_date_str,
    "exam_date": "2026-12-06",
    "days_to_exam": live_state.get("days_left", plan.get("days_to_exam", 22)),
    "done_audio": "./audio/done.mp3",
    "radio": radio_meta,
    "points": ordered_points,
    "words": rich_words,
    "mastery": mastery_data,
    "vocab_base_done": vocab_base_done,
    "cloud_sync": {
        "ntfy_topic": cloud_cfg.get("ntfy_topic", ""),
        "seeded_day": seeded_day,
        "seeded_overrides": seeded_overrides,
    },
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

  /* ================= 2. THREE ZEN ENSO DAILY RITUALS (円相 · 无字打卡) ================= */
  .sr-only {
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
  .zen-horizon {
    flex-shrink: 0;
    padding: 10px 0 9px;
    border-bottom: 1px solid var(--hairline);
    cursor: pointer;
  }
  .horizon-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
    gap: 12px;
  }
  .horizon-meta b {
    font-weight: 600;
    color: var(--sumi);
  }
  .horizon-meta b.moss {
    color: var(--moss);
  }
  .enso-trio {
    display: flex;
    align-items: center;
    gap: 11px;
  }
  .enso-btn {
    width: 30px;
    height: 30px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    padding: 0;
    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
  }
  .enso-btn:active {
    transform: scale(0.91);
  }
  .enso-svg {
    width: 26px;
    height: 26px;
    display: block;
    overflow: visible;
  }
  .enso-btn.is-done .enso-svg {
    animation: ensoSettle 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  }
  @keyframes ensoSettle {
    0% { transform: scale(0.88); opacity: 0.72; }
    65% { transform: scale(1.04); opacity: 1; }
    100% { transform: scale(1); opacity: 1; }
  }
  .horizon-score {
    white-space: nowrap;
    line-height: 1;
  }
  .horizon-track {
    display: none;
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
    position: relative;
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

  /* Center focal space on quiz/done; pin reading views (teach/result) cleanly from the top */
  .focal-space {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding: 20px 0 26px;
    scrollbar-width: none;
    -webkit-mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 26px), transparent 100%);
    mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 26px), transparent 100%);
  }
  .focal-space::-webkit-scrollbar { display: none; }
  .stage-quiz .focal-space > :first-child,
  .stage-done .focal-space > :first-child { margin-top: auto; }
  .stage-quiz .focal-space > :last-child,
  .stage-done .focal-space > :last-child { margin-bottom: auto; }

  .action-dock {
    flex-shrink: 0;
    padding-top: 12px;
  }

  /* Desktop vs Mobile Ergonomics:
     - Mobile (<860px): Content starts cleanly from top, interactive controls stay in bottom one-hand thumb zone.
     - Desktop (>=860px): Quiz centers optically; reading views stay anchored from top so tapping words shifts 0px. */
  @media (min-width: 860px) {
    #tutor-view .stage-wrap {
      justify-content: flex-start;
    }
    #tutor-view .focal-space {
      flex: 0 1 auto;
      justify-content: flex-start;
      padding: 22px 0 2px;
      -webkit-mask-image: none;
      mask-image: none;
    }
    #tutor-view .stage-quiz .focal-space,
    #tutor-view .stage-done .focal-space {
      margin-top: auto;
    }
    #tutor-view .action-dock {
      padding-top: 26px;
    }
    #tutor-view .stage-quiz .action-dock,
    #tutor-view .stage-done .action-dock {
      margin-bottom: auto;
    }
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

  /* -------- QUIZ VIEW (Optimal Literary Reading Scale + Blind-Ear Listening) -------- */
  .quiz-focal {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 116px;
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
    justify-content: center;
    padding: 20px 0;
  }
  .listen-medallion {
    width: 82px;
    height: 82px;
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
  .med-ic { width: 27px; height: 27px; margin-left: 2px; }
  .med-waves { display: none; align-items: center; gap: 3.5px; height: 24px; }
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
    50% { height: 20px; opacity: 1; }
  }

  .choice-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .zen-choice {
    width: 100%;
    min-height: 62px;
    padding: 14px 22px;
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

  .listen-num-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .listen-num-btn {
    min-height: 68px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-family: var(--serif-jp);
    font-size: 25px;
    font-weight: 600;
    color: var(--sumi);
    font-variant-numeric: tabular-nums;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: border-color 0.16s ease, background 0.16s ease;
  }
  .listen-num-btn:active { background: #EDEAE1; }

  .unsure-btn {
    margin-top: 12px;
    width: 100%;
    min-height: 46px;
    padding: 0 18px;
    border: 1px dashed var(--hairline-strong);
    border-radius: 8px;
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.04em;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    transition: border-color 0.16s ease, color 0.16s ease, background 0.16s ease;
  }
  .unsure-btn:active { background: #EDEAE1; }

  .kbd-tag, .desk-hint { display: none; }
  @media (min-width: 860px) {
    .zen-choice:hover, .listen-num-btn:hover { border-color: var(--sumi); background: #FFFFFF; }
    .unsure-btn:hover { border-color: var(--sumi); color: var(--sumi); background: rgba(252, 251, 248, 0.72); }
    .kbd-tag {
      display: inline-block;
      font-family: var(--sans);
      font-size: 13px;
      color: var(--ink-3);
      font-variant-numeric: tabular-nums;
    }
    .desk-hint {
      display: inline-block;
      font-size: 12.5px;
      font-weight: 400;
      opacity: 0.68;
      letter-spacing: 0.03em;
      margin-left: 10px;
    }
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
    font-size: 16px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.66;
    letter-spacing: 0.015em;
  }
  .dlg {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .dlg-row {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 10px;
    align-items: baseline;
  }
  .dlg-who {
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-3);
    text-align: center;
    min-width: 24px;
    padding: 0 5px;
    box-sizing: border-box;
    white-space: nowrap;
    border: 1px solid var(--hairline);
    border-radius: 5px;
    line-height: 22px;
    height: 22px;
    transform: translateY(-2px);
  }
  .dlg-ja {
    font-family: var(--serif-jp);
    font-size: 20px;
    font-weight: 500;
    line-height: 1.62;
    letter-spacing: 0.02em;
    color: var(--sumi);
  }
  .dlg-row.is-ans .dlg-who {
    color: var(--moss);
    border-color: rgba(43, 95, 73, 0.35);
  }
  .dlg-zh {
    margin-top: 2px;
    font-size: 14.5px;
    font-weight: 400;
    color: var(--ink-3);
    line-height: 1.55;
    letter-spacing: 0.01em;
  }
  .listen-opt-review {
    margin-top: 16px;
    padding: 10px 14px;
    border-radius: 7px;
    background: rgba(252, 251, 248, 0.62);
    border: 1px solid var(--hairline);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .lor-row {
    font-family: var(--serif-jp);
    font-size: 15.5px;
    line-height: 1.56;
    color: var(--ink-2);
    display: flex;
    gap: 8px;
  }
  .lor-row.ok {
    color: var(--moss);
    font-weight: 600;
  }
  .lor-row.ng {
    color: var(--bengara);
  }
  .lor-num {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }

  /* Tappable Japanese words + Fixed-Geometry Zen Meaning Card (Zero Layout Shift, Zero Touch Flicker) */
  .w-tok {
    cursor: pointer;
    padding: 1px 0;
    border-radius: 3px;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }
  .w-tok.active-tok {
    color: var(--moss);
    background: var(--moss-soft);
    box-shadow: inset 0 -1.5px 0 var(--moss);
  }

  .inline-lex {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 76px;
    z-index: 20;
    height: 114px;
    padding: 12px 14px;
    border-radius: 8px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    box-shadow: 0 6px 20px rgba(28, 27, 24, 0.06);
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    gap: 3px;
    overflow: hidden;
  }
  #radio-inline-lex {
    bottom: 12px;
    box-shadow: none;
  }
  @media (min-width: 860px) {
    #tutor-inline-lex {
      position: static;
      margin-top: 18px;
      box-shadow: none;
    }
  }
  .inline-lex.empty {
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
  }
  .ilex-top {
    height: 26px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }
  .ilex-head {
    min-width: 0;
    display: flex;
    align-items: baseline;
    gap: 8px;
    overflow: hidden;
    white-space: nowrap;
  }
  .ilex-surf {
    font-family: var(--serif-jp);
    font-size: 18px;
    font-weight: 600;
    color: var(--sumi);
    flex-shrink: 0;
  }
  .ilex-kana {
    font-size: 14.5px;
    color: var(--moss);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ilex-zh {
    height: 22px;
    line-height: 22px;
    font-size: 15.5px;
    font-weight: 500;
    color: var(--sumi);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ilex-meta {
    min-height: 36px;
    max-height: 36px;
    line-height: 18px;
    font-size: 13px;
    color: var(--ink-3);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .ilex-speak {
    flex-shrink: 0;
    height: 26px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--moss);
    padding: 0 9px;
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
    font-size: 16px;
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
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding-top: 34px;
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
    align-items: center;
    gap: 6px;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .chapter-strip::-webkit-scrollbar { display: none; }
  .chap-link {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    padding: 4px 2px;
    white-space: nowrap;
    flex-shrink: 0;
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

  /* ================= 6. PROGRESS & CROSS-DEVICE SYNC MODAL ================= */
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
    max-width: 380px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 10px;
    padding: 26px;
  }
  .modal-h { margin: 0 0 12px; font-size: 18px; font-weight: 600; letter-spacing: 0.04em; }
  .modal-body { margin: 0 0 14px; font-size: 16px; color: var(--ink-2); line-height: 1.85; font-variant-numeric: tabular-nums; }
  .modal-promise { margin: 0 0 16px; padding-top: 12px; border-top: 1px solid var(--hairline); font-size: 14.5px; color: var(--moss); line-height: 1.65; font-weight: 500; }
  .sync-box {
    margin: 0 0 20px;
    padding: 12px 14px;
    border-radius: 8px;
    background: rgba(245, 242, 235, 0.7);
    border: 1px solid var(--hairline);
  }
  .sync-note {
    margin: 0 0 10px;
    font-size: 13.5px;
    color: var(--ink-2);
    line-height: 1.55;
  }
  .sync-btn {
    width: 100%;
    height: 40px;
    border: 1px solid var(--hairline-strong);
    border-radius: 6px;
    background: var(--sheet);
    font-size: 14px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.03em;
  }
  .sync-btn.copied {
    border-color: var(--moss);
    color: var(--moss);
  }

  /* ================= 7. BEDTIME VOCAB FLASHCARD SANCTUARY ================= */
  .night-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    padding: 13px 16px;
    margin-bottom: 18px;
    border-radius: 9px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
  }
  .night-bar-txt { min-width: 0; }
  .night-bar-title {
    font-size: 15.5px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.02em;
  }
  .night-bar-sub {
    margin-top: 3px;
    font-size: 13px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .night-go-btn {
    flex-shrink: 0;
    height: 38px;
    padding: 0 16px;
    border-radius: 7px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.06em;
  }

  .flash-mask {
    position: fixed;
    inset: 0;
    background: var(--washi);
    display: none;
    flex-direction: column;
    align-items: center;
    padding: calc(16px + env(safe-area-inset-top)) 28px calc(20px + env(safe-area-inset-bottom));
    z-index: 120;
  }
  .flash-mask.open { display: flex; }
  .flash-shell {
    width: 100%;
    max-width: 496px;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .flash-top {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--hairline);
  }
  .flash-prog {
    font-size: 14px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
  }
  .flash-top-acts {
    display: flex;
    align-items: baseline;
    gap: 18px;
  }
  .flash-track {
    height: 2px;
    background: var(--track);
    flex-shrink: 0;
  }
  .flash-fill {
    height: 100%;
    background: var(--moss);
    transition: width 0.25s ease;
  }
  .flash-stage {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 20px 6px;
    cursor: pointer;
  }
  .flash-tag {
    font-size: 12.5px;
    color: var(--ink-3);
    letter-spacing: 0.08em;
    margin-bottom: 18px;
  }
  .flash-tag.marked { color: var(--bengara); font-weight: 600; }
  .flash-tag.mastered { color: var(--moss); font-weight: 600; }
  .flash-word {
    font-family: var(--serif-jp);
    font-size: 40px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.3;
    letter-spacing: 0.03em;
    word-break: keep-all;
  }
  .flash-back {
    margin-top: 22px;
    min-height: 112px;
    max-width: 390px;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.22s ease, transform 0.22s ease;
    pointer-events: none;
  }
  .flash-back.shown {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .flash-kana {
    font-size: 18px;
    color: var(--ink-2);
    letter-spacing: 0.04em;
    margin-bottom: 10px;
  }
  .flash-zh {
    font-size: 21px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.45;
  }
  .flash-tip {
    margin-top: 10px;
    font-size: 14.5px;
    color: var(--ink-3);
    line-height: 1.6;
  }
  .flash-hint {
    margin-top: 16px;
    font-size: 13px;
    color: var(--ink-3);
  }
  .flash-dock {
    flex-shrink: 0;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .flash-SubRow {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 4px;
  }
  .flash-nav-btn {
    font-size: 14px;
    color: var(--ink-3);
    padding: 6px 4px;
  }
  .flash-mark-btn {
    height: 52px;
    padding: 0 18px;
    border-radius: 8px;
    border: 1px solid rgba(158, 62, 54, 0.34);
    color: var(--bengara);
    font-size: 15.5px;
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .flash-mark-btn.done-mark {
    background: rgba(158, 62, 54, 0.09);
    border-color: var(--bengara);
  }
  .flash-ok-btn {
    height: 52px;
    padding: 0 18px;
    border-radius: 8px;
    border: 1px solid rgba(43, 95, 73, 0.34);
    color: var(--moss);
    font-size: 15.5px;
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .flash-ok-btn.done-ok {
    background: rgba(43, 95, 73, 0.10);
    border-color: var(--moss);
  }
  .flash-play-btn {
    flex: 1;
    height: 52px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.06em;
  }
  .flash-play-btn.paused {
    background: var(--sheet);
    color: var(--sumi);
    border: 1px solid var(--hairline-strong);
  }
</style>
</head>
<body>

<div class="zen-shell" id="app-shell">
  <!-- 1. STRICT GRID HEADER (Zero Date / Zero Countdown) -->
  <header class="zen-header">
    <div class="zen-brand"><strong>N3</strong></div>
    <nav class="zen-nav">
      <button class="nav-link active" id="tab-tutor" onclick="switchMode('tutor')">做题</button>
      <button class="nav-link" id="tab-radio" onclick="switchMode('radio', true)">随身听</button>
      <button class="nav-link" id="tab-dash" onclick="switchMode('dash')">总表</button>
    </nav>
  </header>

  <!-- 2. THREE ZEN ENSO DAILY RITUALS (円相 · 无字打卡) -->
  <div class="zen-horizon" id="green-board" onclick="openSessionModal()">
    <div class="horizon-meta">
      <div class="enso-trio" id="enso-trio"></div>
      <span class="sr-only" id="gm-left-txt"></span>
      <span class="horizon-score" id="gm-right-txt">预计 <b>108分</b> · 冲120+</span>
    </div>
    <div class="horizon-track">
      <div class="horizon-fill" id="gm-fill" style="width:0%"></div>
    </div>
  </div>

  <!-- 3A. ADAPTIVE QUIZ STAGE -->
  <main class="zen-panel" id="tutor-view">
    <div class="stage-wrap" id="voice-card"></div>
  </main>

  <!-- 3B. THREE-HOST CULTURAL SALON SANCTUARY ("随身听") -->
  <section class="zen-panel hidden" id="radio-view">
    <div class="stage-wrap">
      <div class="meta-bar">
        <span class="overline" id="radio-date-pill">锵锵三人 · 文涛 · 文道 · 子东</span>
        <div class="quiet-actions">
          <button class="text-btn" id="radio-spd-btn" onclick="cycleRadioSpeed()">1.0x</button>
        </div>
      </div>

      <div class="radio-center">
        <div class="radio-chap" id="radio-chap-lbl">逐客茶</div>
        <h2 class="radio-topic" id="radio-live-title">日本文化夜话</h2>
        <p class="radio-ja" id="radio-live-ja"></p>
        <div class="inline-lex empty" id="radio-inline-lex" data-surface="">
          <div class="ilex-top">
            <div class="ilex-head"><span class="ilex-surf"></span><span class="ilex-kana"></span></div>
            <button class="ilex-speak" type="button">发音</button>
          </div>
          <div class="ilex-zh"></div>
          <div class="ilex-meta"></div>
        </div>
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
      <div id="night-flash-entry"></div>
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

<div class="flash-mask" id="flash-modal">
  <div class="flash-shell" id="flash-shell"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.15, 1.3, 1.5];
const RADIO_SPEEDS = [1.0, 1.15, 1.3];
const ADAPTIVE_KEY = "n3_adaptive_v12_" + DATA.plan_date;
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

// ================= MASTER ALGORITHM + REAL-TIME CLOUD CRDT SYNC =================
const CARD_TO_POINT_ID = {};
DATA.points.forEach(p => {
  CARD_TO_POINT_ID[p.id] = p.id;
  if (p.primary && p.primary.id) CARD_TO_POINT_ID[p.primary.id] = p.id;
  (p.variants || []).forEach(v => {
    if (v && v.id) CARD_TO_POINT_ID[v.id] = p.id;
  });
});

function nowUnixSec() {
  return Math.floor(Date.now() / 1000);
}

function createFreshAdaptiveState() {
  const pts = {};
  DATA.points.forEach(p => {
    pts[p.id] = {
      status: "unseen",
      greenAt: 0,
      retestAt: 0,
      audioPrimed: false,
      variantIdx: 0,
      useVariant: false,
      dueStep: 0,
      wrongCount: 0,
      lt: 0
    };
  });
  return {
    step: 0,
    resetAt: 0,
    ct: 0,
    cur: "",
    st: 0,
    es: 0,
    rs: 0,
    lastPointId: null,
    hotFamily: null,
    radioMaxSec: 0,
    radioPos: [0, 0],
    flashProg: [0, 0, 0, 0],
    pts: pts,
    tappedWords: [],
    masteryOverrides: {},
    masteryOverrideTs: {},
    recentRecords: []
  };
}

function mergeFlashProgTuple(st, fp) {
  if (!Array.isArray(fp) || fp.length < 3) return false;
  const cur = Array.isArray(st.flashProg) ? st.flashProg : [0, 0, 0, 0];
  const sSeen = Math.max(0, Math.floor(fp[0] || 0));
  const sTgt = Math.max(0, Math.floor(fp[1] || 0));
  const sDone = Math.max(0, Math.floor(fp[2] || 0));
  const sUpd = Math.max(0, Math.floor(fp[3] || 0));
  const nSeen = Math.max(Math.floor(cur[0] || 0), sSeen);
  const nDone = Math.max(Math.floor(cur[2] || 0), sDone);
  const nUpd = Math.max(Math.floor(cur[3] || 0), sUpd);
  let nTgt = (sUpd >= Math.floor(cur[3] || 0) && sTgt > 0) ? sTgt : (Math.floor(cur[1] || 0) || sTgt);
  nTgt = Math.max(nSeen, nTgt);
  const next = [nSeen, nTgt, nDone, nUpd];
  if (String(next) === String(cur)) return false;
  st.flashProg = next;
  return true;
}

function recomputeStatusesFromCRDT(st) {
  const rAt = Math.floor(st.resetAt || 0);
  DATA.points.forEach(p => {
    const ps = st.pts[p.id];
    if (!ps) return;
    ps.greenAt = Math.floor(ps.greenAt || 0);
    ps.retestAt = Math.floor(ps.retestAt || 0);
    ps.wrongCount = Math.floor(ps.wrongCount || 0);
    ps.variantIdx = Math.floor(ps.variantIdx || 0);
    if (ps.greenAt > rAt && ps.greenAt >= ps.retestAt) {
      ps.status = "green";
    } else if (ps.retestAt > rAt || ps.wrongCount > 0 || ps.audioPrimed) {
      ps.status = "learning";
      if (ps.wrongCount > 0 && p.variants && p.variants.length > 0) {
        ps.useVariant = true;
      }
    } else {
      ps.status = "unseen";
    }
  });
}

// Seed from repo cloud_state_snapshot + union-merge ALL historical localStorage keys (v5..v12)
function loadAdaptiveState() {
  const base = createFreshAdaptiveState();

  // 1. Seed from cloud_state_snapshot.json / practice_log.jsonl baked into DATA.cloud_sync
  try {
    const cs = DATA.cloud_sync || {};
    const sd = cs.seeded_day || {};
    if (typeof sd.resetAt === "number" && sd.resetAt > base.resetAt) base.resetAt = Math.floor(sd.resetAt);
    if (typeof sd.radioMaxSec === "number" && sd.radioMaxSec > base.radioMaxSec) base.radioMaxSec = Math.floor(sd.radioMaxSec);
    if (Array.isArray(sd.radioPos) && sd.radioPos.length === 2 && (sd.radioPos[1] || 0) > (base.radioPos[1] || 0)) {
      base.radioPos = [Math.floor(sd.radioPos[0] || 0), Math.floor(sd.radioPos[1] || 0)];
    }
    const gMap = sd.greenAt || {};
    Object.keys(gMap).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      if (base.pts[pid]) base.pts[pid].greenAt = Math.max(base.pts[pid].greenAt, Math.floor(gMap[rawId] || 0));
    });
    const tMap = sd.retestAt || {};
    Object.keys(tMap).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      if (base.pts[pid]) base.pts[pid].retestAt = Math.max(base.pts[pid].retestAt, Math.floor(tMap[rawId] || 0));
    });
    const wMap = sd.learning || {};
    Object.keys(wMap).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      const arr = wMap[rawId];
      if (base.pts[pid] && Array.isArray(arr)) {
        base.pts[pid].wrongCount = Math.max(base.pts[pid].wrongCount, Math.floor(arr[0] || 0));
        base.pts[pid].variantIdx = Math.max(base.pts[pid].variantIdx, Math.floor(arr[1] || 0));
      }
    });
    const sch = sd.sched || {};
    Object.keys(sch).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      if (base.pts[pid]) applySchedTuple(base.pts[pid], sch[rawId], base.resetAt);
    });
    if (Array.isArray(sd.cursor)) applyCursorTuple(base, sd.cursor);
    if (Array.isArray(sd.speeds)) applySpeedTuple(base, sd.speeds);
    if (Array.isArray(sd.flashProg)) mergeFlashProgTuple(base, sd.flashProg);
    if (Array.isArray(sd.tappedWords)) {
      sd.tappedWords.forEach(w => {
        const ws = String(w || "").trim();
        if (ws && !base.tappedWords.includes(ws)) base.tappedWords.push(ws);
      });
    }
    const sov = cs.seeded_overrides || {};
    Object.keys(sov).forEach(mk => {
      const v = sov[mk];
      if (Array.isArray(v) && v.length === 2) {
        base.masteryOverrides[mk] = String(v[0]);
        base.masteryOverrideTs[mk] = Math.floor(v[1] || 1);
      } else if (typeof v === "string") {
        base.masteryOverrides[mk] = v;
        base.masteryOverrideTs[mk] = 1;
      }
    });
  } catch (e) {}

  // 2. Union-merge all local browser keys (n3_session_v5..v6, n3_adaptive_v7..v12)
  try {
    const suffix = "_" + DATA.plan_date;
    const candidateKeys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k) continue;
      if ((k.startsWith("n3_adaptive_") || k.startsWith("n3_session_")) && k.endsWith(suffix)) {
        candidateKeys.push(k);
      }
    }
    candidateKeys.sort((a, b) => (a === ADAPTIVE_KEY ? 1 : (b === ADAPTIVE_KEY ? -1 : a.localeCompare(b))));

    candidateKeys.forEach(k => {
      try {
        const saved = JSON.parse(localStorage.getItem(k) || "null");
        if (!saved) return;
        if (typeof saved.step === "number" && saved.step > base.step) base.step = saved.step;
        if (typeof saved.resetAt === "number" && saved.resetAt > base.resetAt) base.resetAt = Math.floor(saved.resetAt);
        if (typeof saved.ct === "number") {
          if (saved.ct > (base.ct || 0)) applyCursorTuple(base, [saved.cur || "", saved.step || 0, saved.lastPointId || "", saved.hotFamily || "", saved.ct]);
        } else {
          if (saved.lastPointId) base.lastPointId = saved.lastPointId;
          if (saved.hotFamily !== undefined) base.hotFamily = saved.hotFamily;
        }
        if (typeof saved.st === "number" && saved.st > (base.st || 0)) applySpeedTuple(base, [saved.es, saved.rs, saved.st]);
        if (Array.isArray(saved.flashProg)) mergeFlashProgTuple(base, saved.flashProg);
        if (Array.isArray(saved.tappedWords)) {
          saved.tappedWords.forEach(w => {
            const ws = String(w || "").trim();
            if (ws && !base.tappedWords.includes(ws)) base.tappedWords.push(ws);
          });
        }
        if (typeof saved.radioMaxSec === "number" && saved.radioMaxSec > base.radioMaxSec) {
          base.radioMaxSec = Math.floor(saved.radioMaxSec);
        }
        if (Array.isArray(saved.radioPos) && saved.radioPos.length === 2 && (saved.radioPos[1] || 0) > (base.radioPos[1] || 0)) {
          base.radioPos = [Math.floor(saved.radioPos[0] || 0), Math.floor(saved.radioPos[1] || 0)];
        }
        if (saved.masteryOverrides && typeof saved.masteryOverrides === "object") {
          const tsObj = saved.masteryOverrideTs || {};
          Object.keys(saved.masteryOverrides).forEach(mk => {
            const val = saved.masteryOverrides[mk];
            const mts = Math.floor(tsObj[mk] || (val === "done" ? 2 : 1));
            if (mts >= (base.masteryOverrideTs[mk] || 0)) {
              base.masteryOverrides[mk] = val;
              base.masteryOverrideTs[mk] = mts;
            }
          });
        }
        if (Array.isArray(saved.recentRecords)) {
          saved.recentRecords.forEach(r => {
            if (r && r.id) base.recentRecords.push(r);
          });
        }
        if (saved.pts && typeof saved.pts === "object") {
          Object.keys(saved.pts).forEach(rawId => {
            const pid = CARD_TO_POINT_ID[rawId] || rawId;
            const sp = saved.pts[rawId];
            const cur = base.pts[pid];
            if (!sp || !cur) return;
            if (typeof sp.greenAt === "number" && sp.greenAt > cur.greenAt) {
              cur.greenAt = Math.floor(sp.greenAt);
            } else if (sp.status === "green") {
              cur.greenAt = Math.max(cur.greenAt, 2);
            }
            if (typeof sp.retestAt === "number" && sp.retestAt > cur.retestAt) {
              cur.retestAt = Math.floor(sp.retestAt);
            }
            if (typeof sp.lt === "number" && sp.lt > 0) {
              if (sp.lt > (cur.lt || 0)) {
                applySchedTuple(cur, [sp.dueStep || 0, (sp.audioPrimed ? 1 : 0) | (sp.useVariant ? 2 : 0), sp.wrongCount || 0, sp.variantIdx || 0, sp.lt], 0);
              }
            } else if (!(cur.lt > 0)) {
              cur.audioPrimed = cur.audioPrimed || !!sp.audioPrimed;
              cur.variantIdx = Math.max(cur.variantIdx || 0, sp.variantIdx || 0);
              cur.useVariant = cur.useVariant || !!sp.useVariant;
              cur.dueStep = Math.max(cur.dueStep || 0, sp.dueStep || 0);
              cur.wrongCount = Math.max(cur.wrongCount || 0, sp.wrongCount || 0);
            }
          });
        }
        if (Array.isArray(saved.doneIds)) {
          saved.doneIds.forEach(rawId => {
            const pid = CARD_TO_POINT_ID[rawId] || rawId;
            if (base.pts[pid]) base.pts[pid].greenAt = Math.max(base.pts[pid].greenAt, 2);
          });
        }
      } catch (innerErr) {}
    });

    const savedRadioPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    if (savedRadioPos > base.radioMaxSec) base.radioMaxSec = Math.floor(savedRadioPos);
    if (savedRadioPos > 0 && (base.radioPos[1] || 0) === 0) {
      base.radioPos = [Math.floor(savedRadioPos), 2];
    }
  } catch (e) {}

  if (base.recentRecords.length > 25) {
    base.recentRecords = base.recentRecords.slice(-25);
  }
  recomputeStatusesFromCRDT(base);
  return base;
}

let A = loadAdaptiveState();
(function initSpeedsFromState() {
  if ((A.st || 0) > 0) {
    if (SPEEDS.includes(A.es)) expSpeed = A.es;
    if (RADIO_SPEEDS.includes(A.rs)) radioSpeed = A.rs;
  } else if (expSpeed !== 1.0 || radioSpeed !== 1.0) {
    // legacy local speed preference: publish it with the lowest stamp so any real change beats it
    A.es = expSpeed;
    A.rs = radioSpeed;
    A.st = 1;
  }
})();

// ---- change stamping: every local change gets a fresh stamp, remote merges never re-stamp ----
var syncStampReady = false;
var syncApplyingRemote = false;
var syncLastPtSigs = {};
var syncLastCursorSig = "";
var syncLastIssuedMs = 0;
function syncNowMs() {
  syncLastIssuedMs = Math.max(Date.now(), syncLastIssuedMs + 1);
  return syncLastIssuedMs;
}
function ptSig(ps) {
  return `${ps.dueStep || 0}|${ps.useVariant ? 1 : 0}|${ps.audioPrimed ? 1 : 0}|${ps.wrongCount || 0}|${ps.variantIdx || 0}`;
}
function cursorSig() {
  return `${curPointId || ""}|${A.step || 0}|${A.lastPointId || ""}|${A.hotFamily || ""}`;
}
function snapshotSyncBaseline() {
  syncLastPtSigs = {};
  Object.keys(A.pts).forEach(id => { syncLastPtSigs[id] = ptSig(A.pts[id]); });
  syncLastCursorSig = cursorSig();
  A.cur = curPointId || "";
}

function saveAdaptiveState() {
  if (syncStampReady) {
    if (!syncApplyingRemote) {
      let stamped = false;
      const now = syncNowMs();
      Object.keys(A.pts).forEach(id => {
        if (syncLastPtSigs[id] !== ptSig(A.pts[id])) {
          A.pts[id].lt = now;
          stamped = true;
        }
      });
      if (cursorSig() !== syncLastCursorSig) {
        A.ct = now;
        stamped = true;
      }
      if (stamped && typeof scheduleCloudPush === "function") scheduleCloudPush(350);
    }
    snapshotSyncBaseline();
  }
  try { localStorage.setItem(ADAPTIVE_KEY, JSON.stringify(A)); } catch (e) {}
}

function schedTupleOf(ps) {
  return [ps.dueStep || 0, (ps.audioPrimed ? 1 : 0) | (ps.useVariant ? 2 : 0), ps.wrongCount || 0, ps.variantIdx || 0, ps.lt || 0];
}
// Last-writer-wins per point; equal stamps resolve deterministically so every copy converges
function applySchedTuple(ps, v, resetAtSec) {
  if (!ps || !Array.isArray(v) || v.length < 5) return false;
  const lt = Math.floor(v[4] || 0);
  if (lt <= 0 || lt <= Math.floor(resetAtSec || 0) * 1000) return false;
  const mine = schedTupleOf(ps);
  const cur = Math.floor(ps.lt || 0);
  if (lt < cur) return false;
  if (lt === cur && String(v.slice(0, 4)) <= String(mine.slice(0, 4))) return false;
  ps.dueStep = Math.floor(v[0] || 0);
  ps.audioPrimed = !!((v[1] || 0) & 1);
  ps.useVariant = !!((v[1] || 0) & 2);
  ps.wrongCount = Math.floor(v[2] || 0);
  ps.variantIdx = Math.floor(v[3] || 0);
  ps.lt = lt;
  return true;
}
function applyCursorTuple(st, c) {
  if (!Array.isArray(c) || c.length < 5) return false;
  const ct = Math.floor(c[4] || 0);
  if (ct <= 0 || ct <= Math.floor(st.resetAt || 0) * 1000) return false;
  const mine = [st.cur || "", st.step || 0, st.lastPointId || "", st.hotFamily || ""];
  if (ct < (st.ct || 0)) return false;
  if (ct === (st.ct || 0) && String(c.slice(0, 4)) <= String(mine)) return false;
  st.cur = String(c[0] || "");
  st.step = Math.floor(c[1] || 0);
  st.lastPointId = c[2] ? String(c[2]) : null;
  st.hotFamily = c[3] ? String(c[3]) : null;
  st.ct = ct;
  return true;
}
function applySpeedTuple(st, v) {
  if (!Array.isArray(v) || v.length < 3) return false;
  const t = Math.floor(v[2] || 0);
  if (t <= 0 || t < (st.st || 0)) return false;
  if (t === (st.st || 0) && `${v[0]}|${v[1]}` <= `${st.es}|${st.rs}`) return false;
  st.es = Number(v[0]) || 1.0;
  st.rs = Number(v[1]) || 1.0;
  st.st = t;
  return true;
}

function setMasteryTier(key, tier, tsSec) {
  if (!key) return;
  const ts = Math.floor(tsSec || nowUnixSec());
  if (ts >= (A.masteryOverrideTs[key] || 0)) {
    A.masteryOverrides[key] = tier;
    A.masteryOverrideTs[key] = ts;
  }
}

const SKIP_ENROLL_WORDS = new Set([
  "では", "には", "から", "まで", "ので", "のだ", "だよ", "は", "が", "を", "に", "で", "と", "も", "の", "へ", "よ", "ね", "か",
  "この", "その", "あの", "ここ", "そこ", "あそこ", "これ", "それ", "あれ", "どれ", "どちら",
  "私", "僕", "彼", "彼女", "人", "今日", "明日", "昨日", "今", "もう", "また", "もっと", "だけ", "だから"
]);
const KNOWN_MASTERY_KEYS = new Set();
Object.keys(DATA.mastery || {}).forEach(mod => {
  (DATA.mastery[mod].items || []).forEach(it => {
    if (it.key) KNOWN_MASTERY_KEYS.add(it.key);
    if (it.name) KNOWN_MASTERY_KEYS.add(it.name);
  });
});

function enrollDynamicVocabItem(w, defaultTier) {
  if (!w || KNOWN_MASTERY_KEYS.has(w) || SKIP_ENROLL_WORDS.has(w)) return;
  const info = DATA.words && DATA.words[w];
  if (!info || !info.zh) return;
  KNOWN_MASTERY_KEYS.add(w);
  if (DATA.mastery && DATA.mastery.vocab && Array.isArray(DATA.mastery.vocab.items)) {
    const tipParts = [];
    if (info.head && info.head !== w) tipParts.push(`原形 ${info.head}`);
    if (info.tip) tipParts.push(info.tip);
    DATA.mastery.vocab.items.unshift({
      key: w,
      name: w,
      sub: info.zh,
      family: "今日查词",
      tier: defaultTier || "todo",
      point_id: "",
      audio: info.audio || "",
      note: tipParts.join(" · ")
    });
  }
}

function applyMasteryOverrides() {
  DATA.points.forEach(p => {
    const ps = A.pts[p.id];
    if (ps && ps.status === "green") {
      const gts = Math.max(ps.greenAt || 2, 2);
      setMasteryTier(p.point_key, "done", gts);
      setMasteryTier(p.point, "done", gts);
    } else if (ps && (ps.retestAt || 0) > (A.resetAt || 0) && (ps.retestAt || 0) > (ps.greenAt || 0)) {
      setMasteryTier(p.point_key, "todo", ps.retestAt);
      setMasteryTier(p.point, "todo", ps.retestAt);
    }
  });
  const ov = A.masteryOverrides || {};
  (A.tappedWords || []).forEach(w => enrollDynamicVocabItem(w, ov[w] || "todo"));
  Object.keys(ov).forEach(k => enrollDynamicVocabItem(k, ov[k]));
  Object.keys(DATA.mastery).forEach(mod => {
    const c = { todo: 0, wip: 0, done: 0, total: 0 };
    DATA.mastery[mod].items.forEach(it => {
      const tier = ov[it.key] || ov[it.name];
      if (tier) it.tier = tier;
      c[it.tier] = (c[it.tier] || 0) + 1;
      c.total += 1;
    });
    DATA.mastery[mod].counts = c;
  });
}

// Legacy URL #sync fallback kept compatible alongside automatic real-time cloud sync
function encodeSyncCode() {
  const bytes = new Uint8Array(8);
  DATA.points.forEach((p, idx) => {
    if (idx < 56 && A.pts[p.id] && A.pts[p.id].status === "green") {
      bytes[idx >> 3] |= (1 << (idx & 7));
    }
  });
  bytes[7] = Math.min(255, Math.floor((A.radioMaxSec || 0) / 60));
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const b64 = btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const dateTag = String(DATA.plan_date || "").slice(5).replace("-", "");
  return `${dateTag}_${b64}`;
}

function applySyncCodeFromUrl() {
  try {
    const m = (location.hash || "").match(/sync=([0-9]{4})_([A-Za-z0-9_-]+)/);
    if (!m) return false;
    const dateTag = String(DATA.plan_date || "").slice(5).replace("-", "");
    if (m[1] !== dateTag) return false;
    let b64 = m[2].replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4 !== 0) b64 += "=";
    const bin = atob(b64);
    if (bin.length < 8) return false;
    const stamp = nowUnixSec();
    DATA.points.forEach((p, idx) => {
      if (idx < 56 && (bin.charCodeAt(idx >> 3) & (1 << (idx & 7))) !== 0) {
        if (A.pts[p.id]) A.pts[p.id].greenAt = Math.max(A.pts[p.id].greenAt || 0, stamp);
      }
    });
    const syncedSec = (bin.charCodeAt(7) || 0) * 60;
    if (syncedSec > (A.radioMaxSec || 0)) A.radioMaxSec = syncedSec;
    recomputeStatusesFromCRDT(A);
    history.replaceState(null, "", location.pathname + location.search);
    return true;
  } catch (e) {
    return false;
  }
}

// ================= REAL-TIME ZERO-LOGIN MULTI-PLATFORM CLOUD SYNC =================
const NTFY_TOPIC = (DATA.cloud_sync && DATA.cloud_sync.ntfy_topic) ? String(DATA.cloud_sync.ntfy_topic).trim() : "";
let cloudSyncState = NTFY_TOPIC ? "connecting" : "local";
let cloudLastSyncTs = 0;
let lastSyncedFp = "";
let cloudPushTimer = null;
let cloudInFlight = false;
let cloudPendingPush = false;
let cloudSSE = null;
let cloudSSERetryTimer = null;
let lastRadioCloudPushMs = 0;

function sortedMap(obj) {
  const out = {};
  Object.keys(obj || {}).sort().forEach(k => { out[k] = obj[k]; });
  return out;
}

const PLAN_TAG = "-" + String(DATA.plan_date || "").replace(/-/g, "") + "-";
const CLOUD_OUTBOX_KEY = "n3_cloud_outbox_v13";
const CLOUD_BYTE_LIMIT = 3900;
const cloudEnc = (typeof TextEncoder !== "undefined") ? new TextEncoder() : null;
function byteLen(str) { return cloudEnc ? cloudEnc.encode(str).length : str.length * 3; }
function b36(n) { n = Math.floor(n || 0); return n > 0 ? n.toString(36) : ""; }
function ub36(str) { return str ? (parseInt(str, 36) || 0) : 0; }
function encPid(id) { return String(id).replace(PLAN_TAG, "~"); }
function decPid(str) { return String(str).replace("~", PLAN_TAG); }

function loadOutbox() {
  try {
    const a = JSON.parse(localStorage.getItem(CLOUD_OUTBOX_KEY) || "[]");
    return Array.isArray(a) ? a : [];
  } catch (e) {
    return [];
  }
}
function saveOutbox(arr) {
  try { localStorage.setItem(CLOUD_OUTBOX_KEY, JSON.stringify(arr.slice(-400))); } catch (e) {}
}
function recKey(item) { return `${String(item[4] || "").slice(0, 19)}|${item[0]}|${item[2]}`; }

// Every point in one compact string: id:greenAt.retestAt.dueStep.flags.wrong.variant.stamp (base36)
function encodePointStates() {
  const parts = [];
  DATA.points.forEach(p => {
    const ps = A.pts[p.id];
    if (!ps) return;
    const t = schedTupleOf(ps);
    const g = Math.floor(ps.greenAt || 0), r = Math.floor(ps.retestAt || 0);
    if (!g && !r && !t[0] && !t[1] && !t[2] && !t[3] && !t[4]) return;
    parts.push(`${encPid(p.id)}:${b36(g)}.${b36(r)}.${b36(t[0])}.${t[1] || ""}.${b36(t[2])}.${b36(t[3])}.${b36(t[4])}`);
  });
  return parts.join(";");
}
function decodePointStates(z) {
  const out = [];
  String(z || "").split(";").forEach(ent => {
    const i = ent.indexOf(":");
    if (i <= 0) return;
    const f = ent.slice(i + 1).split(".");
    out.push({ id: decPid(ent.slice(0, i)), g: ub36(f[0]), r: ub36(f[1]), s: [ub36(f[2]), parseInt(f[3] || "0", 10) || 0, ub36(f[4]), ub36(f[5]), ub36(f[6])] });
  });
  return out;
}

function buildCompactPacket() {
  const pkt = {
    a: "n3z",
    v: 13,
    u: nowUnixSec(),
    d: DATA.plan_date,
    r: Math.floor(A.resetAt || 0),
    m: Math.floor(A.radioMaxSec || 0),
    rp: Array.isArray(A.radioPos) ? [Math.floor(A.radioPos[0] || 0), Math.floor(A.radioPos[1] || 0)] : [0, 0],
    z: encodePointStates(),
    c: [A.cur || curPointId || "", Math.floor(A.step || 0), A.lastPointId || "", A.hotFamily || "", Math.floor(A.ct || 0)],
    sp: [A.es || expSpeed, A.rs || radioSpeed, Math.floor(A.st || 0)],
    o: {},
    l: []
  };
  let size = byteLen(JSON.stringify(pkt));
  // answers not yet confirmed by the relay go first (oldest first), never dropped
  const sentKeys = [];
  for (const item of loadOutbox()) {
    const add = byteLen(JSON.stringify(item)) + 1;
    if (size + add > CLOUD_BYTE_LIMIT - 400) break;
    pkt.l.push(item);
    sentKeys.push(recKey(item));
    size += add;
  }
  if (Array.isArray(A.flashProg) && (A.flashProg[0] > 0 || A.flashProg[2] > 0)) {
    pkt.fp = [
      Math.floor(A.flashProg[0] || 0),
      Math.floor(A.flashProg[1] || 0),
      Math.floor(A.flashProg[2] || 0),
      Math.floor(A.flashProg[3] || 0)
    ];
    size += byteLen(JSON.stringify(pkt.fp)) + 7;
  }
  if (Array.isArray(A.tappedWords) && A.tappedWords.length) {
    const twSlice = A.tappedWords.slice(-30);
    const twAdd = byteLen(JSON.stringify(twSlice)) + 7;
    if (size + twAdd <= CLOUD_BYTE_LIMIT - 120) {
      pkt.tw = twSlice;
      size += twAdd;
    }
  }
  const ovEntries = Object.keys(A.masteryOverrides || {}).map(k => [
    k,
    [String(A.masteryOverrides[k]), Math.floor((A.masteryOverrideTs && A.masteryOverrideTs[k]) || 1)]
  ]).sort((x, y) => y[1][1] - x[1][1]);
  for (const kv of ovEntries) {
    const add = byteLen(JSON.stringify(kv[0]) + ":" + JSON.stringify(kv[1])) + 1;
    if (size + add > CLOUD_BYTE_LIMIT) break;
    pkt.o[kv[0]] = kv[1];
    size += add;
  }
  pkt.o = sortedMap(pkt.o);
  Object.defineProperty(pkt, "_sentKeys", { value: sentKeys, enumerable: false });
  return pkt;
}

function packetFingerprint(pkt) {
  if (!pkt || pkt.a !== "n3z") return "";
  return JSON.stringify({
    d: pkt.d || "",
    r: Math.floor(pkt.r || 0),
    m: Math.floor((pkt.m || 0) / 30),
    rp: pkt.rp || [0, 0],
    fp: Array.isArray(pkt.fp) ? [Math.floor(pkt.fp[0] || 0), Math.floor(pkt.fp[1] || 0), Math.floor(pkt.fp[2] || 0)] : [],
    z: String(pkt.z || "").split(";").filter(Boolean).sort().join(";"),
    c: pkt.c || [],
    sp: pkt.sp || [],
    tw: Array.isArray(pkt.tw) ? pkt.tw.slice().sort() : [],
    o: sortedMap(pkt.o || {}),
    g: pkt.z ? {} : sortedMap(pkt.g || {}),
    t: pkt.z ? {} : sortedMap(pkt.t || {}),
    w: pkt.z ? {} : sortedMap(pkt.w || {})
  });
}

function mergeIncomingRecords(compactList) {
  if (!Array.isArray(compactList) || !compactList.length) return;
  const seen = new Set((A.recentRecords || []).map(r => `${String(r.ts || "").slice(0, 19)}|${r.id}|${r.choice}`));
  compactList.forEach(item => {
    if (!Array.isArray(item) || item.length < 4) return;
    const rec = {
      id: String(item[0] || ""),
      point: String(item[1] || ""),
      choice: String(item[2] || ""),
      correct: item[3] ? "true" : "false",
      ask_again: "false",
      ts: String(item[4] || "")
    };
    const key = `${rec.ts.slice(0, 19)}|${rec.id}|${rec.choice}`;
    if (rec.id && !seen.has(key)) {
      seen.add(key);
      A.recentRecords.push(rec);
    }
  });
  A.recentRecords.sort((a, b) => String(a.ts || "").localeCompare(String(b.ts || "")));
  if (A.recentRecords.length > 25) A.recentRecords = A.recentRecords.slice(-25);
}

function applyIncomingPacket(pkt) {
  if (!pkt || pkt.a !== "n3z") return false;
  let changed = false;
  syncApplyingRemote = true;
  try {
    if (pkt.o && typeof pkt.o === "object") {
      Object.keys(pkt.o).forEach(mk => {
        const v = pkt.o[mk];
        if (Array.isArray(v) && v.length === 2) {
          const tier = String(v[0]);
          const ts = Math.floor(v[1] || 1);
          const curTs = A.masteryOverrideTs[mk] || 0;
          if (ts > curTs || (ts === curTs && String(A.masteryOverrides[mk] || "") < tier)) {
            A.masteryOverrides[mk] = tier;
            A.masteryOverrideTs[mk] = ts;
            changed = true;
          }
        }
      });
    }

    if (pkt.d !== DATA.plan_date) {
      if (changed) {
        applyMasteryOverrides();
        saveAdaptiveState();
      }
      return changed;
    }

    const rIn = Math.floor(pkt.r || 0);
    if (rIn > (A.resetAt || 0)) {
      A.resetAt = rIn;
      changed = true;
    }

    const mIn = Math.floor(pkt.m || 0);
    if (mIn > (A.radioMaxSec || 0)) {
      A.radioMaxSec = mIn;
      changed = true;
    }

    if (Array.isArray(pkt.fp) && mergeFlashProgTuple(A, pkt.fp)) {
      changed = true;
    }

    if (Array.isArray(pkt.rp) && pkt.rp.length === 2) {
      const rpSec = Math.floor(pkt.rp[0] || 0);
      const rpTs = Math.floor(pkt.rp[1] || 0);
      const myTs = (A.radioPos && A.radioPos[1]) || 0;
      if (rpTs > myTs || (rpTs === myTs && rpSec > ((A.radioPos && A.radioPos[0]) || 0))) {
        A.radioPos = [rpSec, rpTs];
        try { localStorage.setItem(RADIO_POS_KEY, String(rpSec)); } catch (e) {}
        if (radioInitialized && radioPlayer.paused && Math.abs((radioPlayer.currentTime || 0) - rpSec) > 1) {
          lastSavedSec = rpSec;
          radioPlayer.currentTime = rpSec;
          updateRadioLiveDisplay(rpSec);
        }
        changed = true;
      }
    }

    let ptsChanged = false;
    if (typeof pkt.z === "string") {
      decodePointStates(pkt.z).forEach(e => {
        const pid = CARD_TO_POINT_ID[e.id] || e.id;
        const ps = A.pts[pid];
        if (!ps) return;
        if (e.g > (ps.greenAt || 0)) { ps.greenAt = e.g; ptsChanged = true; }
        if (e.r > (ps.retestAt || 0)) { ps.retestAt = e.r; ptsChanged = true; }
        if (applySchedTuple(ps, e.s, A.resetAt)) ptsChanged = true;
      });
    } else {
      // older page versions (before v13)
      const gIn = pkt.g || {};
      Object.keys(gIn).forEach(rawId => {
        const pid = CARD_TO_POINT_ID[rawId] || rawId;
        const ts = Math.floor(gIn[rawId] || 0);
        if (A.pts[pid] && ts > (A.pts[pid].greenAt || 0)) { A.pts[pid].greenAt = ts; ptsChanged = true; }
      });
      const tIn = pkt.t || {};
      Object.keys(tIn).forEach(rawId => {
        const pid = CARD_TO_POINT_ID[rawId] || rawId;
        const ts = Math.floor(tIn[rawId] || 0);
        if (A.pts[pid] && ts > (A.pts[pid].retestAt || 0)) { A.pts[pid].retestAt = ts; ptsChanged = true; }
      });
    }
    if (ptsChanged) changed = true;

    let curChanged = false;
    if (Array.isArray(pkt.c) && applyCursorTuple(A, pkt.c)) {
      curChanged = true;
      changed = true;
    }

    if (Array.isArray(pkt.sp) && applySpeedTuple(A, pkt.sp)) {
      if (SPEEDS.includes(A.es)) expSpeed = A.es;
      if (RADIO_SPEEDS.includes(A.rs)) radioSpeed = A.rs;
      try {
        localStorage.setItem("n3_exp_speed", String(expSpeed));
        localStorage.setItem("n3_radio_speed", String(radioSpeed));
      } catch (e) {}
      radioPlayer.defaultPlaybackRate = radioSpeed;
      radioPlayer.playbackRate = radioSpeed;
      if (activeKind === "exp" || activeKind === "teach") applyPlaybackRate(activeKind);
      const sb = document.getElementById("ans-spd-btn");
      if (sb) sb.textContent = `${expSpeed}x`;
      const rb = document.getElementById("radio-spd-btn");
      if (rb) rb.textContent = `${radioSpeed}x`;
      changed = true;
    }

    if (Array.isArray(pkt.tw)) {
      if (!Array.isArray(A.tappedWords)) A.tappedWords = [];
      pkt.tw.forEach(w => {
        const ws = String(w || "").trim();
        if (ws && !A.tappedWords.includes(ws)) {
          A.tappedWords.push(ws);
          changed = true;
        }
      });
      if (A.tappedWords.length > 80) A.tappedWords = A.tappedWords.slice(-80);
    }

    mergeIncomingRecords(pkt.l);

    if (changed) {
      recomputeStatusesFromCRDT(A);
      applyMasteryOverrides();
      let shownChanged = false;
      if (viewStage === "quiz" || viewStage === "done") {
        const prevId = curPointId;
        const prevQ = activeQuizObj ? activeQuizObj.id : "";
        const prevC = currentChoices.join("|");
        const prevStage = viewStage;
        const want = (A.cur && A.pts[A.cur] && A.pts[A.cur].status !== "green") ? A.cur : "";
        const curOk = curPointId && A.pts[curPointId] && A.pts[curPointId].status !== "green";
        if (curChanged && want) setupCurrentTurn(want);
        else if (!curOk) setupCurrentTurn();
        else setupCurrentTurn(curPointId);
        shownChanged = curPointId !== prevId || viewStage !== prevStage ||
          (activeQuizObj ? activeQuizObj.id : "") !== prevQ || currentChoices.join("|") !== prevC;
        if (shownChanged) {
          stageEnteredAt = performance.now();
          if (activeKind === "q" || activeKind === "done") stopQuizAudio();
        }
      }
      saveAdaptiveState();
      renderGreenBoard();
      if (activeMode === "tutor") {
        if (shownChanged || viewStage !== "result") renderTutor();
      } else if (activeMode === "dash") renderDashboard();
    }
    return changed;
  } finally {
    syncApplyingRemote = false;
  }
}

function updateSyncModalBadge() {
  const el = document.getElementById("cloud-sync-status-line");
  if (!el) return;
  if (!NTFY_TOPIC) {
    el.textContent = "本地保存模式";
    return;
  }
  if (cloudSyncState === "live") {
    el.textContent = "多端实时自动同步：已连接（手机与电脑做题秒级合并）";
  } else if (cloudSyncState === "synced") {
    el.textContent = "多端自动同步：已对齐最新进度";
  } else if (cloudSyncState === "offline") {
    el.textContent = "当前离线：做题已存本机，联网后自动同步";
  } else {
    el.textContent = "多端自动同步：正在对齐云端进度…";
  }
}

function pushCloudSync(useKeepalive) {
  if (!NTFY_TOPIC) return Promise.resolve(false);
  const pkt = buildCompactPacket();
  const fp = packetFingerprint(pkt);
  const hasOutbox = pkt._sentKeys.length > 0;
  if (!useKeepalive && !hasOutbox && fp === lastSyncedFp) return Promise.resolve(false);

  if (cloudInFlight && !useKeepalive) {
    cloudPendingPush = true;
    return Promise.resolve(false);
  }

  cloudInFlight = true;
  return fetch(`https://ntfy.sh/${NTFY_TOPIC}`, {
    method: "POST",
    body: JSON.stringify(pkt),
    keepalive: !!useKeepalive
  }).then(resp => {
    cloudInFlight = false;
    if (resp && resp.ok) {
      lastSyncedFp = fp;
      cloudLastSyncTs = Date.now();
      if (cloudSyncState !== "live") cloudSyncState = "synced";
      updateSyncModalBadge();
      if (hasOutbox) {
        const done = new Set(pkt._sentKeys);
        const rest = loadOutbox().filter(it => !done.has(recKey(it)));
        saveOutbox(rest);
        if (rest.length) cloudPendingPush = true;
      }
    } else if (hasOutbox) {
      setTimeout(() => scheduleCloudPush(0), 20000);
    }
    if (cloudPendingPush) {
      cloudPendingPush = false;
      scheduleCloudPush(250);
    }
    return !!(resp && resp.ok);
  }).catch(() => {
    cloudInFlight = false;
    if (cloudSyncState !== "live") cloudSyncState = "offline";
    updateSyncModalBadge();
    // not delivered: keep everything queued and try again shortly
    setTimeout(() => scheduleCloudPush(0), 15000);
    return false;
  });
}

function scheduleCloudPush(delayMs) {
  if (!NTFY_TOPIC) return;
  if (cloudPushTimer) clearTimeout(cloudPushTimer);
  cloudPushTimer = setTimeout(() => {
    cloudPushTimer = null;
    pushCloudSync(false);
  }, typeof delayMs === "number" ? delayMs : 120);
}

function pullCloudSync(pushIfLocalAhead) {
  if (!NTFY_TOPIC) return Promise.resolve(false);
  return fetch(`https://ntfy.sh/${NTFY_TOPIC}/json?poll=1&since=all`, {
    cache: "no-store"
  }).then(resp => resp.ok ? resp.text() : "").then(raw => {
    let latestRemoteFp = "";
    if (raw) {
      raw.split("\n").forEach(line => {
        const s = line.trim();
        if (!s) return;
        try {
          const env = JSON.parse(s);
          if (env && env.event === "message" && typeof env.message === "string") {
            const pkt = JSON.parse(env.message);
            if (pkt && pkt.a === "n3z") {
              if (pkt.d === DATA.plan_date) latestRemoteFp = packetFingerprint(pkt);
              applyIncomingPacket(pkt);
            }
          }
        } catch (e) {}
      });
    }
    cloudLastSyncTs = Date.now();
    if (cloudSyncState !== "live") cloudSyncState = "synced";
    updateSyncModalBadge();

    const myFp = packetFingerprint(buildCompactPacket());
    if (latestRemoteFp && myFp === latestRemoteFp && !loadOutbox().length) {
      lastSyncedFp = myFp;
      return true;
    }
    if (pushIfLocalAhead && myFp !== latestRemoteFp) {
      // Automatically upload any local-only historical progress (e.g. from Phone or Desktop) so every device converges!
      return pushCloudSync(false);
    }
    return true;
  }).catch(() => {
    if (cloudSyncState !== "live") cloudSyncState = "offline";
    updateSyncModalBadge();
    return false;
  });
}

function connectCloudSSE() {
  if (!NTFY_TOPIC || typeof EventSource === "undefined") return;
  if (cloudSSE && cloudSSE.readyState !== 2) return;
  try {
    if (cloudSSE) cloudSSE.close();
  } catch (e) {}

  try {
    cloudSSE = new EventSource(`https://ntfy.sh/${NTFY_TOPIC}/sse`);
    cloudSSE.onopen = () => {
      cloudSyncState = "live";
      updateSyncModalBadge();
    };
    cloudSSE.onmessage = ev => {
      if (!ev || !ev.data) return;
      try {
        const env = JSON.parse(ev.data);
        const msgStr = (env && env.event === "message" && typeof env.message === "string") ? env.message : ev.data;
        const pkt = JSON.parse(msgStr);
        if (pkt && pkt.a === "n3z") {
          const inFp = packetFingerprint(pkt);
          applyIncomingPacket(pkt);
          const myFp = packetFingerprint(buildCompactPacket());
          if (myFp === inFp) lastSyncedFp = myFp;
          cloudLastSyncTs = Date.now();
          cloudSyncState = "live";
          updateSyncModalBadge();
        }
      } catch (e) {}
    };
    cloudSSE.onerror = () => {
      try { cloudSSE.close(); } catch (e) {}
      cloudSSE = null;
      if (cloudSyncState === "live") cloudSyncState = "synced";
      updateSyncModalBadge();
      if (cloudSSERetryTimer) clearTimeout(cloudSSERetryTimer);
      cloudSSERetryTimer = setTimeout(() => {
        if (document.visibilityState === "visible") connectCloudSSE();
      }, 6000);
    };
  } catch (e) {}
}

applySyncCodeFromUrl();
applyMasteryOverrides();
saveAdaptiveState();

function computeDaily120Metrics() {
  const totalCards = Math.max(1, DATA.points.length);
  const greenCnt = DATA.points.filter(p => A.pts[p.id] && A.pts[p.id].status === "green").length;
  const quizRatio = Math.min(1.0, greenCnt / totalCards);
  const quizDone = greenCnt >= totalCards;

  const radioDur = Math.max(600, DATA.radio.duration_sec || 2100);
  const targetMins = Math.max(1, Math.round(radioDur / 60));
  const listenedSec = Math.min(radioDur, Math.max(0, A.radioMaxSec || 0));
  const listenedMins = Math.min(targetMins, Math.floor(listenedSec / 60));
  const radioRatio = Math.min(1.0, listenedSec / (radioDur * 0.92));
  const radioDone = radioRatio >= 0.98;

  const vItems = (DATA.mastery && DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  const liveFlashLeft = vItems.filter(it => it.tier !== "done").length;
  const fp = Array.isArray(A.flashProg) ? A.flashProg : [0, 0, 0, 0];
  const flashSeen = Math.max(0, Math.floor(fp[0] || 0));
  const flashDone = (Math.floor(fp[2] || 0) > 0) || (liveFlashLeft === 0 && vItems.length > 0);
  const flashTarget = flashDone
    ? Math.max(flashSeen, Math.floor(fp[1] || 0) || liveFlashLeft)
    : Math.max(flashSeen, Math.floor(fp[1] || 0) || liveFlashLeft || 1);
  const flashRatio = flashDone ? 1.0 : (flashSeen > 0 ? Math.min(0.96, flashSeen / Math.max(1, flashTarget)) : 0);

  const vDone = vItems.filter(it => it.tier === "done").length;
  const vWip = vItems.filter(it => it.tier === "wip").length;
  const vocabBonus = Math.min(8, Math.max(0, (vDone - 11) * 0.25 + Math.max(0, vWip - 33) * 0.06));

  // Combined 3-ritual daily completion: 50% quiz + 32% podcast + 18% bedtime vocab
  const dailyLockPct = Math.min(100, Math.round((quizRatio * 0.50 + radioRatio * 0.32 + flashRatio * 0.18) * 100));

  // Projected JLPT N3 score (/180): 108 base + 12 quiz + 8 podcast + 4 bedtime flashcards + permanent vocab mastery lift
  const projScore = Math.min(165, Math.round(108 + quizRatio * 12 + (radioDone ? 8 : radioRatio * 8) + flashRatio * 4 + vocabBonus));

  return {
    totalCards,
    greenCnt,
    quizRatio,
    quizDone,
    targetMins,
    listenedMins,
    radioRatio: radioDone ? 1.0 : radioRatio,
    radioDone,
    flashSeen: flashDone ? Math.max(flashSeen, flashTarget) : flashSeen,
    flashTarget,
    flashRatio,
    flashDone,
    allThreeDone: quizDone && radioDone && flashDone,
    dailyLockPct,
    projScore
  };
}

function selectNextPointId(forcedId) {
  if (forcedId && A.pts[forcedId]) return forcedId;
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
    if (syncStampReady) saveAdaptiveState();
    return;
  }
  const p = getPointById(curPointId);
  const ps = A.pts[curPointId];
  viewStage = "quiz";
  activeQuizObj = getQuizForPoint(p, ps);
  currentChoices = prepareChoices(activeQuizObj, ps.wrongCount);
  if (syncStampReady) saveAdaptiveState();
}
setupCurrentTurn((A.cur && A.pts[A.cur] && A.pts[A.cur].status !== "green") ? A.cur : undefined);
snapshotSyncBaseline();
syncStampReady = true;

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
  "か": { kana: "か", pos: "疑问助词", zh: "吗（句尾表疑问）" },
  "な": { kana: "な", pos: "助动词・终助词", zh: "连接修饰语与名词（如：はずなのに），或句尾感叹" }
};

Object.keys(PARTICLE_FALLBACK).forEach(pk => {
  if (!DATA.words[pk]) DATA.words[pk] = PARTICLE_FALLBACK[pk];
});

const DICT_KEYS = Object.keys(DATA.words).sort((a, b) => b.length - a.length);
const CONTENT_KEYS = DICT_KEYS.filter(k => k.length >= 3 && !PARTICLE_FALLBACK[k]);
const INTERJECTION_SET = new Set(["はい", "ええ", "うん", "いや", "あれ", "ほら"]);

function hasLongerContentWordAt(src, pos) {
  for (let c = 0; c < CONTENT_KEYS.length; c++) {
    if (src.startsWith(CONTENT_KEYS[c], pos)) return true;
  }
  return false;
}

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
      if (!src.startsWith(w, i)) continue;
      if (INTERJECTION_SET.has(w) && i > 0 && !"「『（(、。！？!? \n\t：:".includes(src[i - 1])) {
        continue;
      }
      if (w.length === 2 && PARTICLE_FALLBACK[w] && hasLongerContentWordAt(src, i + 1)) {
        continue;
      }
      matched = w;
      break;
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

const SPEAKER_RE = /^\s*([男女ＡＢAB]|[^\s：:「」]{1,3})\s*[：:]\s*/;
function splitSpeakerLines(text) {
  const src = String(text || "").trim();
  if (!src) return [];
  // Break before every "男：" / "女：" style label, even if the source put them on one line
  const parts = src.split(/\n+|\s*(?=[男女][：:])|\s+(?=[^\s：:「」。、]{1,3}[：:])/).map(x => x.trim()).filter(Boolean);
  return parts.map(t => {
    const m = t.match(SPEAKER_RE);
    return m ? { who: m[1], text: t.slice(m[0].length) } : { who: "", text: t };
  });
}

function renderDialogueHTML(fullJa, ans, zh) {
  const ja = splitSpeakerLines(fullJa);
  if (ja.length < 2 || ja.some(l => !l.who)) return "";
  const zl = splitSpeakerLines(zh);
  const zhOk = zl.length === ja.length && zl.every(l => l.who);
  return `<div class="dlg">${ja.map((l, i) => {
    const isAns = ans && l.text.indexOf(ans) >= 0;
    const zhTxt = zhOk ? zl[i].text.replace(/^「|」$/g, "") : "";
    return `<div class="dlg-row${isAns ? " is-ans" : ""}"><span class="dlg-who">${escapeHtml(l.who)}</span><div><div class="dlg-ja">${renderJapaneseWithHighlight(l.text, isAns ? ans : "")}</div>${zhTxt ? `<div class="dlg-zh">${escapeHtml(zhTxt)}</div>` : ""}</div></div>`;
  }).join("")}</div>${!zhOk && zh ? `<p class="result-zh">${escapeHtml(zh)}</p>` : ""}`;
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

function stampSpeeds() {
  A.es = expSpeed;
  A.rs = radioSpeed;
  A.st = syncNowMs();
  saveAdaptiveState();
  scheduleCloudPush(300);
}

function cycleExpSpeed() {
  expSpeed = SPEEDS[(SPEEDS.indexOf(expSpeed) + 1) % SPEEDS.length];
  try { localStorage.setItem("n3_exp_speed", String(expSpeed)); } catch (e) {}
  stampSpeeds();
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
    const localPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    const hasCloud = Array.isArray(A.radioPos) && A.radioPos.length === 2 && (A.radioPos[1] || 0) > 0;
    const savedPos = hasCloud ? (A.radioPos[0] || 0) : localPos;
    lastSavedSec = savedPos;
    if (savedPos > 3 && savedPos < (DATA.radio.duration_sec || 2400) - 10) {
      radioPlayer.currentTime = savedPos;
    }
    const hostsLabel = DATA.radio.hosts || "文涛 · 文道 · 子东";
    document.getElementById("radio-date-pill").textContent = `锵锵三人 · ${hostsLabel}`;
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
      title: segTitle || "锵锵三人 · 日本文化随身听",
      artist: DATA.radio.hosts || "文涛 · 文道 · 子东",
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

function markRadioPosByUser(t) {
  A.radioPos = [Math.floor(t || 0), nowUnixSec()];
  try { localStorage.setItem(RADIO_POS_KEY, String(Math.floor(t || 0))); } catch (e) {}
  saveAdaptiveState();
  scheduleCloudPush(800);
}

function seekRadioBy(delta) {
  ensureRadioReady();
  const dur = radioPlayer.duration || DATA.radio.duration_sec || 2100;
  radioPlayer.currentTime = Math.max(0, Math.min(dur - 1, (radioPlayer.currentTime || 0) + delta));
  updateRadioLiveDisplay(radioPlayer.currentTime);
  markRadioPosByUser(radioPlayer.currentTime);
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
  markRadioPosByUser(radioPlayer.currentTime);
}

function cycleRadioSpeed() {
  radioSpeed = RADIO_SPEEDS[(RADIO_SPEEDS.indexOf(radioSpeed) + 1) % RADIO_SPEEDS.length];
  try { localStorage.setItem("n3_radio_speed", String(radioSpeed)); } catch (e) {}
  radioPlayer.defaultPlaybackRate = radioSpeed;
  radioPlayer.playbackRate = radioSpeed;
  document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
  stampSpeeds();
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
      if (!radioPlayer.paused) A.radioPos = [Math.floor(t), nowUnixSec()];
      saveAdaptiveState();
      renderGreenBoard();
      if (Date.now() - lastRadioCloudPushMs > 55000) {
        lastRadioCloudPushMs = Date.now();
        scheduleCloudPush(400);
      }
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

    const segPids = Array.isArray(curSeg.point_ids) && curSeg.point_ids.length
      ? curSeg.point_ids
      : (curSeg.point_id ? [curSeg.point_id] : []);
    if (segPids.length && t >= curSeg.end - 12) {
      let changed = false;
      for (const pid of segPids) {
        const ps = A.pts[pid];
        if (ps && !ps.audioPrimed) {
          ps.audioPrimed = true;
          if (ps.status === "unseen") ps.status = "learning";
          changed = true;
        }
      }
      if (changed) {
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
  const t = Math.floor(radioPlayer.currentTime || 0);
  if (t > 2) {
    A.radioPos = [t, nowUnixSec()];
    if (t > (A.radioMaxSec || 0)) A.radioMaxSec = t;
    try { localStorage.setItem(RADIO_POS_KEY, String(t)); } catch (e) {}
    saveAdaptiveState();
    scheduleCloudPush(200);
  }
});
radioPlayer.addEventListener("ended", () => {
  const dur = Math.ceil(radioPlayer.duration || DATA.radio.duration_sec || 2100);
  A.radioMaxSec = dur;
  A.radioPos = [0, nowUnixSec()];
  try { localStorage.setItem(RADIO_POS_KEY, "0"); } catch (e) {}
  saveAdaptiveState();
  renderGreenBoard();
  syncRadioUI();
  scheduleCloudPush(100);
});
radioPlayer.addEventListener("loadedmetadata", () => {
  updateRadioLiveDisplay(radioPlayer.currentTime || 0);
  renderGreenBoard();
});
radioPlayer.addEventListener("timeupdate", () => {
  const t = radioPlayer.currentTime || 0;
  updateRadioLiveDisplay(t);
  if (!radioPlayer.paused && Math.abs(t - lastSavedSec) >= 3) {
    lastSavedSec = t;
    A.radioPos = [Math.floor(t), nowUnixSec()];
    try { localStorage.setItem(RADIO_POS_KEY, String(Math.floor(t))); } catch (e) {}
    saveAdaptiveState();
    if (Date.now() - lastRadioCloudPushMs > 90000) {
      lastRadioCloudPushMs = Date.now();
      scheduleCloudPush(400);
    }
  }
});

// ================= QUIZ ACTIONS =================
let stageEnteredAt = performance.now();

function syncBackendRecord(p, qid, choice, isCorrect, askAgain, newTier, stampSec) {
  const tsSec = stampSec || nowUnixSec();
  setMasteryTier(p.point_key, newTier, tsSec);
  setMasteryTier(p.point, newTier, tsSec);
  applyMasteryOverrides();

  const rec = {
    id: qid,
    point: p.point_key || p.point,
    choice: String(choice || ""),
    correct: String(!!isCorrect),
    ask_again: String(!!askAgain),
    ts: new Date(tsSec * 1000).toISOString()
  };
  if (!Array.isArray(A.recentRecords)) A.recentRecords = [];
  A.recentRecords.push(rec);
  const ob = loadOutbox();
  ob.push([rec.id, rec.point, rec.choice, isCorrect ? 1 : 0, rec.ts]);
  saveOutbox(ob);
  if (A.recentRecords.length > 25) A.recentRecords = A.recentRecords.slice(-25);
  saveAdaptiveState();

  // Real-time cloud CRDT publish across Phone & Desktop
  scheduleCloudPush(60);

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
    ps.retestAt = nowUnixSec();
    ps.status = "learning";
    ps.dueStep = A.step + 4;
    A.step += 1;
    A.lastPointId = p.id;
    A.hotFamily = null;
    saveAdaptiveState();
    scheduleCloudPush(120);
  }
  setupCurrentTurn();
  stageEnteredAt = performance.now();
  renderTutor();
  autoPlayCurrentTurn();
}

// Calm zero-guess escape hatch: never force a blind 50/50 guess (which risks lucky false-greens).
// Reveals THIS sentence's full 3-step explanation + voice immediately, and schedules a variant re-test 4 steps later.
function revealWithoutGuess() {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  clearActiveWordToken();
  stopQuizAudio();
  pickedVal = "__UNSURE__";
  viewStage = "result";
  stageEnteredAt = performance.now();

  const stamp = nowUnixSec();
  const p = getPointById(curPointId);
  const ps = A.pts[p.id];
  ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
  ps.status = "learning";
  ps.wrongCount += 1;
  if (p.variants && p.variants.length > 0) {
    if (ps.useVariant) ps.variantIdx += 1;
    ps.useVariant = true;
  }
  ps.dueStep = A.step + 4;
  A.hotFamily = p.family;
  A.step += 1;
  A.lastPointId = p.id;
  recomputeStatusesFromCRDT(A);
  syncBackendRecord(p, activeQuizObj.id, "不确定", false, false, "todo", stamp);

  renderTutor();
  playMainClip(activeQuizObj.exp_audio, "exp", false);
}

function submitAnswer(val) {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  clearActiveWordToken();
  stopQuizAudio();
  pickedVal = val;
  viewStage = "result";
  stageEnteredAt = performance.now();

  const stamp = nowUnixSec();
  const p = getPointById(curPointId);
  const ps = A.pts[p.id];
  const isCorrect = (val === activeQuizObj.answer);

  if (isCorrect) {
    ps.greenAt = Math.max(stamp, (ps.retestAt || 0), (A.resetAt || 0) + 1);
    ps.status = "green";
    A.hotFamily = null;
    A.step += 1;
    A.lastPointId = p.id;
    recomputeStatusesFromCRDT(A);
    syncBackendRecord(p, activeQuizObj.id, val, true, false, "done", ps.greenAt);
  } else {
    ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
    ps.status = "learning";
    ps.wrongCount += 1;
    if (p.variants && p.variants.length > 0) {
      if (ps.useVariant) ps.variantIdx += 1;
      ps.useVariant = true;
    }
    ps.dueStep = A.step + 4;
    A.hotFamily = p.family;
    A.step += 1;
    A.lastPointId = p.id;
    recomputeStatusesFromCRDT(A);
    syncBackendRecord(p, activeQuizObj.id, val, false, false, "todo", ps.retestAt);
  }

  renderTutor();
  playMainClip(activeQuizObj.exp_audio, "exp", false);
}

function advanceNext(forceRetestCurrent) {
  stopQuizAudio();
  clearActiveWordToken();
  if (forceRetestCurrent && curPointId) {
    const stamp = nowUnixSec();
    const p = getPointById(curPointId);
    const ps = A.pts[curPointId];
    ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
    ps.status = "learning";
    if (p && p.variants && p.variants.length > 0) ps.useVariant = true;
    ps.dueStep = A.step + 4;
    recomputeStatusesFromCRDT(A);
    if (p) syncBackendRecord(p, p.id, pickedVal, false, true, "todo", ps.retestAt);
  }
  setupCurrentTurn();
  stageEnteredAt = performance.now();
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
  setupCurrentTurn(pid);
  stageEnteredAt = performance.now();
  switchMode("tutor");
  renderTutor();
  autoPlayCurrentTurn();
}

function resetTodayMission() {
  stopQuizAudio();
  const stamp = nowUnixSec();
  const keepOverrides = A.masteryOverrides || {};
  const keepOverrideTs = A.masteryOverrideTs || {};
  const keepTapped = A.tappedWords || [];
  const keepRadio = A.radioMaxSec || 0;
  const keepRadioPos = A.radioPos || [0, 0];
  const keepFlashProg = A.flashProg || [0, 0, 0, 0];
  const keepSt = A.st || 0;
  A = createFreshAdaptiveState();
  A.resetAt = stamp;
  A.masteryOverrides = keepOverrides;
  A.masteryOverrideTs = keepOverrideTs;
  A.tappedWords = keepTapped;
  A.radioMaxSec = keepRadio;
  A.radioPos = keepRadioPos;
  A.flashProg = keepFlashProg;
  A.es = expSpeed;
  A.rs = radioSpeed;
  A.st = keepSt;
  recomputeStatusesFromCRDT(A);
  saveAdaptiveState();
  scheduleCloudPush(60);
  closeModal();
  setupCurrentTurn();
  stageEnteredAt = performance.now();
  renderTutor();
}

const ENSO_CURVE = "M 8.2 5.7 C 12.6 2.5, 19.3 3.2, 22.6 7.8 C 25.8 12.3, 24.8 19.1, 20.1 22.4 C 15.4 25.7, 8.6 24.6, 5.4 19.9 C 3.4 16.9, 3.4 12.8, 5.1 9.6";
const ENSO_ROTS = [-8, 34, -46];
let prevEnsoDoneKey = "";

function renderEnsoRingSVG(idx, ratio, isDone) {
  const rot = ENSO_ROTS[idx] || 0;
  if (isDone) {
    return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
      <g transform="rotate(${rot} 14 14)">
        <circle cx="14.1" cy="14.1" r="9.3" fill="rgba(43, 95, 73, 0.11)"/>
        <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="var(--moss)" stroke-width="1.45" stroke-linecap="round" stroke-dasharray="99 105"/>
        <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="var(--moss)" stroke-width="2.65" stroke-linecap="round" stroke-dasharray="66 105"/>
        <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="var(--moss)" stroke-width="3.3" stroke-linecap="round" stroke-dasharray="22 105"/>
      </g>
    </svg>`;
  }
  if (ratio > 0.005) {
    const drawLen = Math.max(8, Math.min(96, Math.round(ratio * 96)));
    return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
      <g transform="rotate(${rot} 14 14)">
        <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="rgba(28, 27, 24, 0.14)" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="9.5 6.5"/>
        <circle cx="8.2" cy="5.7" r="1.32" fill="var(--sumi)"/>
        <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="var(--sumi)" stroke-width="2.35" stroke-linecap="round" stroke-dasharray="${drawLen} 105"/>
      </g>
    </svg>`;
  }
  return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
    <g transform="rotate(${rot} 14 14)">
      <path d="${ENSO_CURVE}" pathLength="100" fill="none" stroke="rgba(28, 27, 24, 0.20)" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="9.5 6.5"/>
    </g>
  </svg>`;
}

function onEnsoTap(idx, ev) {
  if (ev) ev.stopPropagation();
  if (idx === 0) {
    if (activeMode !== "tutor") switchMode("tutor");
    else openSessionModal();
  } else if (idx === 1) {
    if (activeMode !== "radio") switchMode("radio", false);
    else openSessionModal();
  } else {
    openNightFlash();
  }
}

function renderGreenBoard() {
  const m = computeDaily120Metrics();

  const trioEl = document.getElementById("enso-trio");
  if (trioEl) {
    const doneKey = `${m.quizDone ? 1 : 0}${m.radioDone ? 1 : 0}${m.flashDone ? 1 : 0}`;
    const rings = [
      { ratio: m.quizRatio, done: m.quizDone, label: `做题 ${m.greenCnt}/${m.totalCards}` },
      { ratio: m.radioRatio, done: m.radioDone, label: `随身听 ${m.listenedMins}/${m.targetMins}分` },
      { ratio: m.flashRatio, done: m.flashDone, label: `睡前生词 ${m.flashDone ? "已完成" : m.flashSeen + "/" + m.flashTarget}` }
    ];
    trioEl.innerHTML = rings.map((r, idx) => {
      const newlyDone = r.done && prevEnsoDoneKey && prevEnsoDoneKey[idx] === "0";
      return `<button class="enso-btn${r.done ? " done" : ""}${newlyDone ? " is-done" : ""}" id="enso-${idx + 1}" onclick="onEnsoTap(${idx}, event)" aria-label="${escapeHtml(r.label)}" title="${escapeHtml(r.label)}">${renderEnsoRingSVG(idx, r.ratio, r.done)}</button>`;
    }).join("");
    prevEnsoDoneKey = doneKey;
  }

  const quizPart = m.quizDone ? `做题 ✓` : `做题 ${m.greenCnt}/${m.totalCards}`;
  const radioPart = m.radioDone ? `随身听 ✓` : `听 ${m.listenedMins}/${m.targetMins}分`;
  const flashPart = m.flashDone ? `生词 ✓` : `词 ${m.flashSeen}/${m.flashTarget}`;
  document.getElementById("gm-left-txt").textContent = `${quizPart} · ${radioPart} · ${flashPart}`;

  if (m.projScore >= 120) {
    document.getElementById("gm-right-txt").innerHTML = `预计 <b class="moss">${m.projScore}分 · 稳过120</b>`;
  } else {
    document.getElementById("gm-right-txt").innerHTML = `预计 <b>${m.projScore}分</b> · 冲120+`;
  }
  document.getElementById("gm-fill").style.width = `${m.dailyLockPct}%`;
}

function lexBoxHTML(id) {
  return `
    <div class="inline-lex empty" id="${id}" data-surface="">
      <div class="ilex-top">
        <div class="ilex-head"><span class="ilex-surf"></span><span class="ilex-kana"></span></div>
        <button class="ilex-speak" type="button">发音</button>
      </div>
      <div class="ilex-zh"></div>
      <div class="ilex-meta"></div>
    </div>`;
}

function renderTutor() {
  renderGreenBoard();
  clearActiveWordToken();
  const box = document.getElementById("voice-card");
  const effStage = (viewStage === "done" || !curPointId)
    ? "done"
    : ((viewStage === "quiz" && activeQuizObj) ? "quiz" : viewStage);
  box.className = "stage-wrap stage-" + effStage;

  if (viewStage === "done" || !curPointId) {
    const m = computeDaily120Metrics();
    const nextBtn = !m.radioDone
      ? `<button class="sumi-btn" onclick="switchMode('radio', true)">去听随身听</button>`
      : (!m.flashDone
          ? `<button class="sumi-btn" onclick="openNightFlash()">睡前过生词</button>`
          : `<button class="sumi-btn" onclick="switchMode('dash')">查看总表</button>`);
    box.innerHTML = `
      <div class="meta-bar"><span class="overline ok">${m.allThreeDone ? "今日三修圆满 · 稳过 120 分" : "五十道题已全部刷绿"}</span></div>
      <div class="focal-space">
        <h2 class="point-heading">${m.allThreeDone ? "今日三样皆已圆满" : "五十道题已全部过关"}</h2>
        <p class="logic-line">${m.allThreeDone
          ? `做题、三人随身听与生词皆已收笔，预计总分稳锁在 ${m.projScore} 分。安心休息，考场稳站 120 分以上。`
          : `做题部分已拿满，当前预计 ${m.projScore} 分。${!m.radioDone ? "顺手听完今日随身听，" : ""}睡前再过一遍生词，就能把三枚圆印全部收满。`}</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          <button class="ghost-btn" onclick="resetTodayMission()">再来一轮</button>
          ${nextBtn}
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
      </div>

      <div class="action-dock">
        <button class="sumi-btn" style="width:100%;" onclick="completeTeachCard()"><span>继续</span><span class="desk-hint">滚轮下滑 · Enter</span></button>
      </div>
      ${lexBoxHTML("tutor-inline-lex")}
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
    else if (ps.audioPrimed) label += " · 随身听已聊";

    const controlsHTML = activeQuizObj.is_listening
      ? `<div class="listen-num-grid">
          ${currentChoices.map((c, cIdx) => `
            <button class="listen-num-btn" onclick="submitAnswer(currentChoices[${cIdx}])">${cIdx + 1}</button>
          `).join("")}
        </div>`
      : `<div class="choice-list">
          ${currentChoices.map((c, cIdx) => `
            <button class="zen-choice" onclick="submitAnswer(currentChoices[${cIdx}])">
              <span>${escapeHtml(c)}</span>
              <span class="kbd-tag">${cIdx + 1}</span>
            </button>
          `).join("")}
        </div>`;

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
          </div>` : `<p class="quiz-ja">${escapeHtml(activeQuizObj.prompt)}</p>`}
        </div>
      </div>

      <div class="action-dock">
        ${controlsHTML}
        <button class="unsure-btn" onclick="revealWithoutGuess()">
          <span>不确定 · 直接看讲解</span>
          <span class="kbd-tag">0</span>
        </button>
      </div>
    `;
    syncAudioButtons();
    return;
  }

  // -------- RESULT (3-Step Clear Human Order: ① 句意 -> ② 为什么用 -> ③ 变形与辨析) --------
  const q = activeQuizObj || p.primary;
  const isUnsure = pickedVal === "__UNSURE__";
  const isCorrect = !isUnsure && pickedVal === q.answer;
  const ansIdx = currentChoices.indexOf(q.answer) + 1;
  const pickedIdx = currentChoices.indexOf(pickedVal) + 1;

  let overCls = "overline ng";
  let overTxt = "";
  if (isCorrect) {
    overCls = "overline ok";
    overTxt = q.is_listening && ansIdx > 0 ? `已变绿 · 正确答案 ${ansIdx}` : "已变绿";
  } else if (isUnsure) {
    overCls = "overline warm";
    overTxt = q.is_listening && ansIdx > 0 ? `直接看讲解 · 正确答案 ${ansIdx} · 稍后复考` : "直接看讲解 · 稍后复考";
  } else {
    overCls = "overline ng";
    overTxt = q.is_listening && ansIdx > 0
      ? `误选 ${pickedIdx || ""} · 正确答案 ${ansIdx} · 稍后复考`
      : `误选「${pickedVal}」 · 稍后复考`;
  }

  const listenOptsReviewHTML = q.is_listening
    ? `<div class="listen-opt-review">
        ${currentChoices.map((opt, idx) => {
          const cls = opt === q.answer ? "lor-row ok" : (opt === pickedVal ? "lor-row ng" : "lor-row");
          return `<div class="${cls}"><span class="lor-num">${idx + 1}.</span><span>${annotateJapanese(opt)}</span></div>`;
        }).join("")}
      </div>`
    : "";

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
      ${(q.is_listening && renderDialogueHTML(q.full_ja, q.answer, q.zh_meaning)) || `<div class="result-ja">${annotateSentenceWithAnswer(q.full_ja, q.answer)}</div>
      ${q.zh_meaning ? `<p class="result-zh">${escapeHtml(q.zh_meaning)}</p>` : ""}`}
      ${listenOptsReviewHTML}
      <div class="result-divider"></div>
      <div class="result-logic">
        ${q.why_line ? `<p class="logic-line">${escapeHtml(q.why_line)}</p>` : ""}
        ${q.form_line ? `<p class="logic-line">${escapeHtml(q.form_line)}</p>` : ""}
      </div>
    </div>

    <div class="action-dock">
      <div class="dock-row">
        ${isCorrect ? `<button class="ghost-btn" onclick="advanceNext(true)">再考</button>` : ""}
        <button class="sumi-btn" onclick="advanceNext(false)"><span>下一题</span><span class="desk-hint">滚轮下滑 · Enter</span></button>
      </div>
    </div>
    ${lexBoxHTML("tutor-inline-lex")}
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
  el.classList.add("empty");
  el.dataset.surface = "";
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

const TRIVIAL_TAP_WORDS = new Set([
  "この", "その", "あの", "ここ", "そこ", "あそこ", "これ", "それ", "あれ", "どれ", "どちら",
  "私", "僕", "彼", "彼女", "人", "今日", "明日", "昨日", "今", "もう", "また", "もっと", "だけ", "だから"
]);

function recordTappedWord(surface) {
  if (!surface || PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return;
  const info = DATA.words[surface];
  if (!info || !info.zh) return;
  if (!Array.isArray(A.tappedWords)) A.tappedWords = [];
  if (!A.tappedWords.includes(surface)) {
    A.tappedWords.push(surface);
    if (A.tappedWords.length > 80) A.tappedWords = A.tappedWords.slice(-80);
    applyMasteryOverrides();
    renderGreenBoard();
    saveAdaptiveState();
    scheduleCloudPush(450);
  }
}

function showInlineWordMeaning(surface, tokEl) {
  const info = DATA.words[surface];
  if (!info) return;

  const targetBoxId = activeMode === "radio" ? "radio-inline-lex" : "tutor-inline-lex";
  const box = document.getElementById(targetBoxId);
  if (!box) return;

  if (tokEl && tokEl === activeTokEl && !box.classList.contains("empty")) {
    clearActiveWordToken();
    clearInlineLexicon(targetBoxId);
    return;
  }

  recordTappedWord(surface);
  clearActiveWordToken();
  if (tokEl && tokEl.classList) {
    activeTokEl = tokEl;
    activeTokEl.classList.add("active-tok");
  }

  const headDiff = info.head && info.head !== surface ? `原形 ${info.head}` : "";
  const metaLine = [headDiff, info.pos, info.tip].filter(Boolean).join(" · ");
  const kanaTxt = info.kana && info.kana !== surface
    ? (info.kana + (info.pitch ? " " + info.pitch : ""))
    : (info.pitch || "");

  box.dataset.surface = surface;
  const surfEl = box.querySelector(".ilex-surf");
  const kanaEl = box.querySelector(".ilex-kana");
  const zhEl = box.querySelector(".ilex-zh");
  const metaEl = box.querySelector(".ilex-meta");
  if (surfEl) surfEl.textContent = surface;
  if (kanaEl) kanaEl.textContent = kanaTxt;
  if (zhEl) zhEl.textContent = info.zh || "";
  if (metaEl) metaEl.textContent = metaLine;
  box.classList.remove("empty");

  if (player.paused && radioPlayer.paused) {
    playWordAudio(surface, false);
  }
}

document.addEventListener("click", e => {
  if (flashOpen) return;
  const speakBtn = e.target.closest && e.target.closest(".ilex-speak");
  if (speakBtn) {
    e.preventDefault();
    e.stopPropagation();
    const box = speakBtn.closest(".inline-lex");
    if (box && box.dataset.surface) playWordAudio(box.dataset.surface, true);
    return;
  }
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (tok && !(activeMode === "tutor" && viewStage === "quiz")) {
    e.preventDefault();
    e.stopPropagation();
    showInlineWordMeaning(tok.dataset.w, tok);
    return;
  }
  if (!e.target.closest || !e.target.closest(".inline-lex")) {
    const targetBoxId = activeMode === "radio" ? "radio-inline-lex" : "tutor-inline-lex";
    const box = document.getElementById(targetBoxId);
    if (box && !box.classList.contains("empty") && (e.target.closest(".focal-space") || e.target.closest(".radio-center"))) {
      clearActiveWordToken();
      clearInlineLexicon(targetBoxId);
    }
  }
});

// ================= DESKTOP MOUSE WHEEL & MOBILE SWIPE ERGONOMICS =================
let lastWheelAdvanceAt = 0;

window.addEventListener("wheel", e => {
  if (flashOpen) return;
  if (activeMode !== "tutor") return;
  if (viewStage !== "result" && viewStage !== "teach") return;
  if (document.getElementById("app-modal").classList.contains("open")) return;
  if (e.deltaY < 24 || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;

  const now = performance.now();
  if (now - stageEnteredAt < 480 || now - lastWheelAdvanceAt < 750) return;

  const fs = document.querySelector("#tutor-view .focal-space");
  if (fs && fs.scrollHeight > fs.clientHeight + 8) {
    if (fs.scrollTop + fs.clientHeight < fs.scrollHeight - 8) return;
  }

  lastWheelAdvanceAt = now;
  if (viewStage === "teach") completeTeachCard();
  else advanceNext(false);
}, { passive: true });

let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;

document.getElementById("tutor-view").addEventListener("touchstart", e => {
  if (!e.touches || e.touches.length !== 1) return;
  touchStartX = e.touches[0].clientX;
  touchStartY = e.touches[0].clientY;
  touchStartTime = performance.now();
}, { passive: true });

document.getElementById("tutor-view").addEventListener("touchend", e => {
  if (flashOpen) return;
  if (activeMode !== "tutor") return;
  if (viewStage !== "result" && viewStage !== "teach") return;
  if (document.getElementById("app-modal").classList.contains("open")) return;
  if (!e.changedTouches || e.changedTouches.length !== 1) return;

  const dx = e.changedTouches[0].clientX - touchStartX;
  const dy = e.changedTouches[0].clientY - touchStartY;
  const dt = performance.now() - touchStartTime;
  if (dx <= -56 && Math.abs(dx) > Math.abs(dy) * 1.7 && dt < 650) {
    if (viewStage === "teach") completeTeachCard();
    else advanceNext(false);
  }
}, { passive: true });

// ================= KEYBOARD =================
document.addEventListener("keydown", e => {
  const tag = (e.target && e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea") {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  if (flashOpen) {
    if (e.key === "Escape") { e.preventDefault(); closeNightFlash(); }
    else if (e.key === " ") { e.preventDefault(); toggleFlashPlay(); }
    else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); flashStepNext(true); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); flashStepPrev(); }
    else if (e.key.toLowerCase() === "r" || e.key === "1") { e.preventDefault(); markFlashUnfamiliar(); }
    else if (e.key.toLowerCase() === "m" || e.key === "2") { e.preventDefault(); markFlashMastered(); }
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
    else if (e.key === "Enter" || e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); completeTeachCard(); }
    return;
  }
  if (viewStage === "quiz" && activeQuizObj) {
    if (e.key === " ") { e.preventDefault(); playMainClip(activeQuizObj.q_audio, "q", true); }
    else if (e.key === "1" && currentChoices[0]) { e.preventDefault(); submitAnswer(currentChoices[0]); }
    else if (e.key === "2" && currentChoices[1]) { e.preventDefault(); submitAnswer(currentChoices[1]); }
    else if (e.key === "3" && currentChoices[2]) { e.preventDefault(); submitAnswer(currentChoices[2]); }
    else if (e.key === "0") { e.preventDefault(); revealWithoutGuess(); }
    return;
  }
  if (viewStage === "result" && activeQuizObj) {
    if (e.key === " ") { e.preventDefault(); playMainClip(activeQuizObj.exp_audio, "exp", true); }
    else if (e.key === "Enter" || e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); advanceNext(false); }
    else if (e.key.toLowerCase() === "r") { e.preventDefault(); advanceNext(true); }
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

// ================= BEDTIME VOCAB FLASHCARD CONTROLLER =================
let flashOpen = false;
let flashDeck = [];
let flashIdx = 0;
let flashRevealed = false;
let flashPlaying = true;
let flashIsSubPass = false;
let flashMarkedSet = new Set();
let flashMasteredSet = new Set();
let flashTimerA = null;
let flashTimerB = null;
let flashRunToken = 0;
let lastFlashCloudPushMs = 0;

function buildNightFlashDeck(onlyList) {
  if (Array.isArray(onlyList) && onlyList.length) return onlyList.slice();
  applyMasteryOverrides();
  const deck = [];
  const seen = new Set();
  const seenHead = new Set();
  const vItems = (DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  const byKey = {};
  vItems.forEach(it => { byKey[it.key] = it; byKey[it.name] = it; });

  function pushCard(surface, vItem, srcLabel) {
    if (!surface || seen.has(surface)) return;
    if (vItem && vItem.tier === "done") return;
    const ovTier = A.masteryOverrides && (A.masteryOverrides[surface] || (vItem && A.masteryOverrides[vItem.key]));
    if (ovTier === "done") return;
    const w = DATA.words[surface] || {};
    const head = w.head || surface;
    if (srcLabel === "今日查过" && seenHead.has(head)) return;
    const zh = w.zh || (vItem && vItem.sub) || "";
    if (!zh) return;
    seen.add(surface);
    seenHead.add(head);
    const tipParts = [];
    if (w.head && w.head !== surface) tipParts.push(`原形 ${w.head}`);
    if (w.tip) tipParts.push(w.tip);
    else if (vItem && vItem.note) tipParts.push(vItem.note);
    deck.push({
      word: surface,
      key: (vItem && vItem.key) || surface,
      pointId: (vItem && vItem.point_id) || "",
      initTier: (vItem && vItem.tier) || "todo",
      kana: w.kana || "",
      pitch: w.pitch || "",
      zh: zh,
      tip: tipParts.join(" · "),
      audio: (vItem && vItem.audio) || w.audio || "",
      source: srcLabel
    });
  }

  // 1) Tapped words today (newest first)
  const tapped = Array.isArray(A.tappedWords) ? A.tappedWords.slice().reverse() : [];
  tapped.forEach(sw => pushCard(sw, byKey[sw] || null, "今日查过"));
  // 2) Todo vocab
  vItems.forEach(it => { if (it.tier === "todo") pushCard(it.name, it, "待练"); });
  // 3) Consolidating vocab
  vItems.forEach(it => { if (it.tier === "wip") pushCard(it.name, it, "巩固"); });
  return deck;
}

function pushFlashRecord(card, choiceLabel, isOk, stampSec) {
  const tsSec = stampSec || nowUnixSec();
  const ptKey = card.key || card.word;
  const rec = {
    id: `FLASH-${ptKey}`,
    point: ptKey,
    choice: choiceLabel,
    correct: isOk ? "true" : "false",
    ask_again: "false",
    ts: new Date(tsSec * 1000).toISOString()
  };
  if (!Array.isArray(A.recentRecords)) A.recentRecords = [];
  A.recentRecords.push(rec);
  if (A.recentRecords.length > 25) A.recentRecords = A.recentRecords.slice(-25);
  const ob = loadOutbox();
  ob.push([rec.id, rec.point, rec.choice, isOk ? 1 : 0, rec.ts]);
  saveOutbox(ob);
}

function recordFlashProgress(seenCnt, totalCnt, markDoneNow) {
  const stamp = nowUnixSec();
  const cur = Array.isArray(A.flashProg) ? A.flashProg : [0, 0, 0, 0];
  const nextSeen = Math.max(Math.floor(cur[0] || 0), Math.max(0, Math.floor(seenCnt || 0)));
  const nextTgt = Math.max(nextSeen, Math.floor(totalCnt || 0) || Math.floor(cur[1] || 0));
  const nextDone = markDoneNow ? Math.max(Math.floor(cur[2] || 0), stamp) : Math.floor(cur[2] || 0);
  const changed = mergeFlashProgTuple(A, [nextSeen, nextTgt, nextDone, stamp]);
  if (changed) {
    saveAdaptiveState();
    renderGreenBoard();
    if (markDoneNow || Date.now() - lastFlashCloudPushMs > 12000) {
      lastFlashCloudPushMs = Date.now();
      scheduleCloudPush(markDoneNow ? 80 : 400);
    }
  }
}

function clearFlashTimers() {
  if (flashTimerA) { clearTimeout(flashTimerA); flashTimerA = null; }
  if (flashTimerB) { clearTimeout(flashTimerB); flashTimerB = null; }
}

function stopFlashSpeech() {
  try { wordPlayer.pause(); } catch (e) {}
  try { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); } catch (e) {}
}

function speakFlashCard(card, onDone) {
  const token = ++flashRunToken;
  let finished = false;
  const finish = () => {
    if (finished || token !== flashRunToken) return;
    finished = true;
    if (onDone) onDone();
  };
  // Safety ceiling so a missing/stalled voice never freezes bedtime playback
  const safety = setTimeout(finish, 2400);
  const doneWrap = () => { clearTimeout(safety); finish(); };

  if (card.audio) {
    try {
      wordPlayer.onended = doneWrap;
      wordPlayer.onerror = () => {
        wordPlayer.onended = null;
        wordPlayer.onerror = null;
        speakUtteranceWithCallback(card.kana || card.word, doneWrap);
      };
      wordPlayer.src = card.audio;
      wordPlayer.currentTime = 0;
      wordPlayer.playbackRate = 0.96;
      const pr = wordPlayer.play();
      if (pr && pr.catch) {
        pr.catch(() => {
          wordPlayer.onended = null;
          wordPlayer.onerror = null;
          speakUtteranceWithCallback(card.kana || card.word, doneWrap);
        });
      }
      return;
    } catch (e) {}
  }
  speakUtteranceWithCallback(card.kana || card.word, doneWrap);
}

function speakUtteranceWithCallback(text, cb) {
  if (!("speechSynthesis" in window)) {
    setTimeout(cb, 650);
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ja-JP";
    u.rate = 0.9;
    u.onend = cb;
    u.onerror = cb;
    window.speechSynthesis.speak(u);
  } catch (e) {
    setTimeout(cb, 650);
  }
}

function openNightFlash(customList) {
  stopQuizAudio();
  if (!radioPlayer.paused) {
    radioPlayer.pause();
    syncRadioUI();
  }
  flashIsSubPass = Array.isArray(customList) && customList.length > 0;
  flashDeck = buildNightFlashDeck(customList);
  flashIdx = 0;
  flashRevealed = false;
  flashPlaying = true;
  flashMarkedSet = new Set();
  flashMasteredSet = new Set();
  flashOpen = true;
  document.getElementById("flash-modal").classList.add("open");
  runFlashCardAt(0);
}

function closeNightFlash() {
  flashOpen = false;
  flashRunToken++;
  clearFlashTimers();
  stopFlashSpeech();
  wordPlayer.onended = null;
  wordPlayer.onerror = null;
  document.getElementById("flash-modal").classList.remove("open");
  saveAdaptiveState();
  renderGreenBoard();
  scheduleCloudPush(120);
  if (activeMode === "dash") renderDashboard();
}

function runFlashCardAt(idx) {
  clearFlashTimers();
  stopFlashSpeech();
  if (!flashDeck.length) {
    renderFlashFinished();
    return;
  }
  if (idx >= flashDeck.length) {
    renderFlashFinished();
    return;
  }
  flashIdx = Math.max(0, idx);
  flashRevealed = false;
  if (!flashIsSubPass) {
    recordFlashProgress(flashIdx + 1, flashDeck.length, false);
  }
  renderFlashStage();

  const card = flashDeck[flashIdx];
  const myToken = flashRunToken + 1;
  speakFlashCard(card, () => {
    if (!flashOpen || flashRunToken !== myToken) return;
    if (!flashPlaying) return;
    flashTimerA = setTimeout(() => {
      if (!flashOpen || !flashPlaying || flashRunToken !== myToken) return;
      flashRevealed = true;
      const backEl = document.getElementById("flash-back-box");
      const hintEl = document.getElementById("flash-tap-hint");
      if (backEl) backEl.classList.add("shown");
      if (hintEl) hintEl.textContent = "点卡片重听";
      flashTimerB = setTimeout(() => {
        if (!flashOpen || !flashPlaying || flashRunToken !== myToken) return;
        runFlashCardAt(flashIdx + 1);
      }, 2150);
    }, 1050);
  });
}

function renderFlashStage() {
  const shell = document.getElementById("flash-shell");
  const card = flashDeck[flashIdx];
  const total = flashDeck.length;
  const pct = (((flashIdx + 1) / Math.max(1, total)) * 100).toFixed(1);
  const marked = flashMarkedSet.has(card.word);
  const mastered = flashMasteredSet.has(card.word);
  const kanaPart = (card.kana && card.kana !== card.word)
    ? `${card.kana}${card.pitch ? " " + card.pitch : ""}`
    : (card.pitch ? card.pitch : "");
  const tagCls = marked ? "marked" : (mastered ? "mastered" : "");
  const tagTxt = marked ? "已记入待练" : (mastered ? "已移入已会" : "先听发音 · 想一下意思");
  let cleanTip = String(card.tip || "").trim();
  if (cleanTip && card.zh && cleanTip.startsWith(card.zh)) {
    cleanTip = cleanTip.slice(card.zh.length).replace(/^[·\s]+/, "").trim();
  }
  if (cleanTip === card.zh) cleanTip = "";

  shell.innerHTML = `
    <div class="flash-top">
      <span class="flash-prog">${flashIdx + 1} / ${total} · ${escapeHtml(card.source)}</span>
      <div class="flash-top-acts">
        <button class="text-btn" onclick="replayFlashAudio()">重听</button>
        <button class="text-btn" onclick="closeNightFlash()">收起</button>
      </div>
    </div>
    <div class="flash-track"><div class="flash-fill" style="width:${pct}%"></div></div>

    <div class="flash-stage" onclick="onFlashCardTap()">
      <div class="flash-tag ${tagCls}" id="flash-tag-line">${tagTxt}</div>
      <div class="flash-word">${escapeHtml(card.word)}</div>
      <div class="flash-back ${flashRevealed ? 'shown' : ''}" id="flash-back-box">
        ${kanaPart ? `<div class="flash-kana">${escapeHtml(kanaPart)}</div>` : ""}
        <div class="flash-zh">${escapeHtml(card.zh)}</div>
        ${cleanTip ? `<div class="flash-tip">${escapeHtml(cleanTip)}</div>` : ""}
      </div>
      <div class="flash-hint" id="flash-tap-hint">${flashRevealed ? "点卡片重听" : "点一下直接看中文"}</div>
    </div>

    <div class="flash-dock">
      <div class="dock-row">
        <button class="flash-mark-btn ${marked ? 'done-mark' : ''}" id="flash-mark-btn" onclick="markFlashUnfamiliar()">${marked ? "已标不熟" : "不熟"}</button>
        <button class="flash-play-btn ${flashPlaying ? '' : 'paused'}" id="flash-play-btn" onclick="toggleFlashPlay()">${flashPlaying ? "暂停自动" : "继续自动"}</button>
        <button class="flash-ok-btn ${mastered ? 'done-ok' : ''}" id="flash-ok-btn" onclick="markFlashMastered()">${mastered ? "已标已熟" : "已熟"}</button>
      </div>
      <div class="flash-SubRow">
        <button class="flash-nav-btn" onclick="flashStepPrev()" ${flashIdx === 0 ? "style='opacity:0.32;pointer-events:none'" : ""}>上一个</button>
        <button class="flash-nav-btn" onclick="flashStepNext(true)">下一个</button>
      </div>
    </div>
  `;
}

function completeFlashSession() {
  const stamp = nowUnixSec();
  let promoted = 0;
  flashDeck.forEach(card => {
    if (flashMarkedSet.has(card.word) || flashMasteredSet.has(card.word)) return;
    const curOv = A.masteryOverrides && (A.masteryOverrides[card.key] || A.masteryOverrides[card.word]);
    const effTier = curOv || card.initTier || "todo";
    if (effTier === "todo") {
      setMasteryTier(card.key, "wip", stamp);
      setMasteryTier(card.word, "wip", stamp);
      if (promoted < 12) pushFlashRecord(card, "闪卡:顺过", true, stamp);
      promoted += 1;
    }
  });
  applyMasteryOverrides();
  recordFlashProgress(flashDeck.length, flashDeck.length, true);
  saveAdaptiveState();
  renderGreenBoard();
  scheduleCloudPush(80);
}

function renderFlashFinished() {
  completeFlashSession();
  const shell = document.getElementById("flash-shell");
  const markedCards = flashDeck.filter(c => flashMarkedSet.has(c.word));
  const masteredCnt = flashDeck.filter(c => flashMasteredSet.has(c.word)).length;
  let noteLine = "这一轮都很顺，今日生词圆印已收笔，安心休息吧。";
  if (markedCards.length) {
    noteLine = `标了 ${markedCards.length} 个不熟词（已归入待练）${masteredCnt ? `，移出 ${masteredCnt} 个已熟词` : ""}。要不要把这 ${markedCards.length} 个再顺一遍？`;
  } else if (masteredCnt) {
    noteLine = `已把 ${masteredCnt} 个熟词移入已会，今日生词圆印已收笔，安心休息吧。`;
  }
  shell.innerHTML = `
    <div class="flash-top">
      <span class="flash-prog">${flashDeck.length ? `已完成 ${flashDeck.length} 个词` : "生词已全部移入已会"}</span>
      <div class="flash-top-acts">
        <button class="text-btn" onclick="closeNightFlash()">收起</button>
      </div>
    </div>
    <div class="flash-track"><div class="flash-fill" style="width:100%"></div></div>
    <div class="flash-stage" style="cursor:default">
      <div class="flash-word" style="font-size:28px">${flashDeck.length ? "今晚过完啦" : "全部已熟"}</div>
      <div class="flash-back shown" style="min-height:0;margin-top:16px">
        <div class="flash-tip" style="font-size:16px;color:var(--ink-2)">${escapeHtml(noteLine)}</div>
      </div>
    </div>
    <div class="flash-dock">
      <div class="dock-row">
        ${markedCards.length
          ? `<button class="ghost-btn" onclick="closeNightFlash()">休息了</button>
             <button class="sumi-btn" onclick="replayMarkedFlash()">只过这 ${markedCards.length} 个不熟词</button>`
          : (flashDeck.length
              ? `<button class="ghost-btn" onclick="openNightFlash()">再来一遍</button>
                 <button class="sumi-btn" onclick="closeNightFlash()">安心休息</button>`
              : `<button class="sumi-btn" onclick="closeNightFlash()">返回</button>`)}
      </div>
    </div>
  `;
}

function replayMarkedFlash() {
  const sub = flashDeck.filter(c => flashMarkedSet.has(c.word));
  if (sub.length) openNightFlash(sub);
}

function replayFlashAudio() {
  const card = flashDeck[flashIdx];
  if (!card) return;
  clearFlashTimers();
  speakFlashCard(card, () => {
    if (flashOpen && flashPlaying) {
      flashTimerB = setTimeout(() => {
        if (flashOpen && flashPlaying) runFlashCardAt(flashIdx + 1);
      }, flashRevealed ? 1900 : 2500);
    }
  });
}

function onFlashCardTap() {
  const card = flashDeck[flashIdx];
  if (!card) return;
  if (!flashRevealed) {
    clearFlashTimers();
    flashRevealed = true;
    const backEl = document.getElementById("flash-back-box");
    const hintEl = document.getElementById("flash-tap-hint");
    if (backEl) backEl.classList.add("shown");
    if (hintEl) hintEl.textContent = "点卡片重听";
    if (flashPlaying) {
      flashTimerB = setTimeout(() => {
        if (flashOpen && flashPlaying) runFlashCardAt(flashIdx + 1);
      }, 2200);
    }
  } else {
    replayFlashAudio();
  }
}

function toggleFlashPlay() {
  flashPlaying = !flashPlaying;
  const btn = document.getElementById("flash-play-btn");
  if (btn) {
    btn.textContent = flashPlaying ? "暂停自动" : "继续自动";
    btn.classList.toggle("paused", !flashPlaying);
  }
  if (!flashPlaying) {
    clearFlashTimers();
    flashRevealed = true;
    const backEl = document.getElementById("flash-back-box");
    const hintEl = document.getElementById("flash-tap-hint");
    if (backEl) backEl.classList.add("shown");
    if (hintEl) hintEl.textContent = "点卡片重听";
  } else {
    if (flashRevealed) {
      clearFlashTimers();
      flashTimerB = setTimeout(() => {
        if (flashOpen && flashPlaying) runFlashCardAt(flashIdx + 1);
      }, 1500);
    } else {
      runFlashCardAt(flashIdx);
    }
  }
}

function flashStepNext() {
  runFlashCardAt(flashIdx + 1);
}

function flashStepPrev() {
  if (flashIdx > 0) runFlashCardAt(flashIdx - 1);
}

function markFlashUnfamiliar() {
  const card = flashDeck[flashIdx];
  if (!card) return;
  flashMarkedSet.add(card.word);
  flashMasteredSet.delete(card.word);
  const stamp = nowUnixSec();
  setMasteryTier(card.key, "todo", stamp);
  setMasteryTier(card.word, "todo", stamp);
  if (card.pointId && A.pts[card.pointId]) {
    const ps = A.pts[card.pointId];
    ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
    ps.status = "learning";
    ps.dueStep = A.step + 2;
    recomputeStatusesFromCRDT(A);
  }
  pushFlashRecord(card, "闪卡:不熟", false, stamp);
  applyMasteryOverrides();
  saveAdaptiveState();
  renderGreenBoard();
  scheduleCloudPush(100);

  // Reveal meaning immediately and give extra reading time + replay pronunciation once
  clearFlashTimers();
  flashRevealed = true;
  const backEl = document.getElementById("flash-back-box");
  const tagEl = document.getElementById("flash-tag-line");
  const markBtn = document.getElementById("flash-mark-btn");
  const okBtn = document.getElementById("flash-ok-btn");
  if (backEl) backEl.classList.add("shown");
  if (tagEl) { tagEl.textContent = "已记入待练"; tagEl.className = "flash-tag marked"; }
  if (markBtn) { markBtn.textContent = "已标不熟"; markBtn.classList.add("done-mark"); }
  if (okBtn) { okBtn.textContent = "已熟"; okBtn.classList.remove("done-ok"); }
  speakFlashCard(card, () => {
    if (flashOpen && flashPlaying) {
      flashTimerB = setTimeout(() => {
        if (flashOpen && flashPlaying) runFlashCardAt(flashIdx + 1);
      }, 2200);
    }
  });
}

function markFlashMastered() {
  const card = flashDeck[flashIdx];
  if (!card) return;
  flashMasteredSet.add(card.word);
  flashMarkedSet.delete(card.word);
  const stamp = nowUnixSec();
  setMasteryTier(card.key, "done", stamp);
  setMasteryTier(card.word, "done", stamp);
  if (card.pointId && A.pts[card.pointId]) {
    const ps = A.pts[card.pointId];
    ps.greenAt = Math.max(ps.greenAt || 0, stamp, (ps.retestAt || 0) + 1);
    recomputeStatusesFromCRDT(A);
  }
  pushFlashRecord(card, "闪卡:已熟", true, stamp);
  applyMasteryOverrides();
  saveAdaptiveState();
  renderGreenBoard();
  scheduleCloudPush(80);

  clearFlashTimers();
  stopFlashSpeech();
  flashRunToken++;
  const myToken = flashRunToken;
  const tagEl = document.getElementById("flash-tag-line");
  const okBtn = document.getElementById("flash-ok-btn");
  const markBtn = document.getElementById("flash-mark-btn");
  if (tagEl) { tagEl.textContent = "已移入已会"; tagEl.className = "flash-tag mastered"; }
  if (okBtn) { okBtn.textContent = "已标已熟"; okBtn.classList.add("done-ok"); }
  if (markBtn) { markBtn.textContent = "不熟"; markBtn.classList.remove("done-mark"); }
  flashTimerB = setTimeout(() => {
    if (flashOpen && flashRunToken === myToken) {
      runFlashCardAt(flashIdx + 1);
    }
  }, 340);
}

// Swipe left/right inside flashcard modal (isolated here, never touches tabs)
(function bindFlashSwipe() {
  let fx = 0, fy = 0, ft = 0;
  const fm = document.getElementById("flash-modal");
  fm.addEventListener("touchstart", e => {
    if (!e.touches || e.touches.length !== 1) return;
    fx = e.touches[0].clientX;
    fy = e.touches[0].clientY;
    ft = performance.now();
  }, { passive: true });
  fm.addEventListener("touchend", e => {
    if (!flashOpen || !flashDeck.length || flashIdx >= flashDeck.length) return;
    if (!e.changedTouches || e.changedTouches.length !== 1) return;
    const dx = e.changedTouches[0].clientX - fx;
    const dy = e.changedTouches[0].clientY - fy;
    const dt = performance.now() - ft;
    if (Math.abs(dx) >= 52 && Math.abs(dx) > Math.abs(dy) * 1.6 && dt < 650) {
      if (dx < 0) flashStepNext();
      else flashStepPrev();
    }
  }, { passive: true });
})();

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

  const dm = computeDaily120Metrics();
  const deckPreview = buildNightFlashDeck();
  const tappedCnt = deckPreview.filter(c => c.source === "今日查过").length;
  const entryEl = document.getElementById("night-flash-entry");
  if (entryEl) {
    if (deckPreview.length) {
      const subTxt = dm.flashDone
        ? `今日已完成 · 余 ${deckPreview.length} 词`
        : `共 ${deckPreview.length} 词${tappedCnt ? ` · 含查词 ${tappedCnt}` : " · 自动发音翻面"}`;
      entryEl.innerHTML = `
        <div class="night-bar">
          <div class="night-bar-txt">
            <div class="night-bar-title">睡前过生词</div>
            <div class="night-bar-sub">${subTxt}</div>
          </div>
          <button class="night-go-btn" onclick="openNightFlash()">${dm.flashDone ? "再过" : "开始"}</button>
        </div>
      `;
    } else {
      entryEl.innerHTML = "";
    }
  }

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

function speakLedgerItem(name, audioUrl) {
  if (audioUrl) {
    playDirectUrl(audioUrl);
  } else if (DATA.words[name]) {
    playWordAudio(name, true);
  } else {
    speakJapaneseFallback(name);
  }
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

  listEl.innerHTML = items.map((it, i) => {
    const canSpeak = !!(it.audio || dashMod === "vocab" || DATA.words[it.name]);
    return `
    <div class="ledger-item" onclick="togglePtNote(${i})">
      <div class="li-row">
        <div class="li-left">
          <span class="li-dot ${it.tier}"></span>
          <span class="li-name">${escapeHtml(it.name)}</span>
        </div>
        <div class="li-right">
          <span class="li-sub">${escapeHtml(it.sub)}</span>
          ${canSpeak ? `<button class="li-act" onclick='event.stopPropagation();speakLedgerItem(${JSON.stringify(it.name)}, ${JSON.stringify(it.audio || "")})'>听音</button>` : ""}
          ${it.point_id ? `<button class="li-act" onclick="event.stopPropagation();jumpToPointById('${it.point_id}')">练习</button>` : ""}
        </div>
      </div>
      ${expandedPt === i && (it.note || it.family) ? `<div class="li-note">${escapeHtml([it.family, it.note].filter(Boolean).join(" · "))}</div>` : ""}
    </div>
  `;
  }).join("");
}

function closeModal() {
  document.getElementById("app-modal").classList.remove("open");
}

function manualCloudSync(btnEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "正在对齐手机与电脑进度…";
  }
  pullCloudSync(true).then(() => {
    connectCloudSSE();
    const m = computeDaily120Metrics();
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.classList.add("copied");
      btnEl.textContent = `已同步最新进度（${m.greenCnt} / ${m.totalCards} 题）`;
    }
    const cntEl = document.getElementById("modal-green-cnt");
    if (cntEl) cntEl.textContent = `${m.greenCnt} / ${m.totalCards} 题`;
    const minEl = document.getElementById("modal-radio-min");
    if (minEl) minEl.textContent = `${m.listenedMins} / ${m.targetMins} 分钟`;
    const flEl = document.getElementById("modal-flash-cnt");
    if (flEl) flEl.textContent = m.flashDone ? "今日已完成" : `${m.flashSeen} / ${m.flashTarget} 词`;
    const scEl = document.getElementById("modal-proj-score");
    if (scEl) scEl.textContent = `${m.projScore} / 180 分`;
  });
}

function openSessionModal() {
  const m = computeDaily120Metrics();
  document.getElementById("modal-content").innerHTML = `
    <h3 class="modal-h">今日三修 · 120+ 进度</h3>
    <p class="modal-body">
      ① 做题　　　<strong id="modal-green-cnt">${m.greenCnt} / ${m.totalCards} 题</strong><br/>
      ② 随身听　　<strong id="modal-radio-min">${m.listenedMins} / ${m.targetMins} 分钟</strong><br/>
      ③ 睡前生词　<strong id="modal-flash-cnt">${m.flashDone ? "今日已完成" : `${m.flashSeen} / ${m.flashTarget} 词`}</strong><br/>
      当前预计分　<strong id="modal-proj-score">${m.projScore} / 180 分</strong>
    </p>
    <p class="modal-promise">三枚圆印分别对应做题、随身听与睡前生词，全部汇总进你的整体水平。</p>
    <div class="sync-box">
      <p class="sync-note" id="cloud-sync-status-line">正在对齐云端进度…</p>
      <button class="sync-btn" onclick="manualCloudSync(this)">立即对齐多端进度</button>
    </div>
    <div class="dock-row">
      <button class="ghost-btn" onclick="resetTodayMission()">重做题</button>
      <button class="sumi-btn" onclick="closeModal()">继续</button>
    </div>
  `;
  updateSyncModalBadge();
  document.getElementById("app-modal").classList.add("open");
}

window.addEventListener("hashchange", () => {
  if (applySyncCodeFromUrl()) {
    applyMasteryOverrides();
    saveAdaptiveState();
    scheduleCloudPush(80);
    if (curPointId && A.pts[curPointId] && A.pts[curPointId].status === "green" && viewStage === "quiz") {
      setupCurrentTurn();
    }
    renderGreenBoard();
    if (activeMode === "tutor") renderTutor();
    else if (activeMode === "dash") renderDashboard();
  }
});

let editionCheckBusy = false;
function checkNewDailyEdition() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistration().then(reg => { if (reg) reg.update().catch(() => {}); }).catch(() => {});
  }
  if (editionCheckBusy) return;
  editionCheckBusy = true;
  fetch("./audio/daily_radio_meta.json?t=" + Date.now(), { cache: "no-store" })
    .then(r => r.ok ? r.json() : null)
    .then(rm => {
      if (!rm || !rm.date) return;
      const curRadioDate = (DATA.radio && DATA.radio.date) || DATA.plan_date || "";
      const curSig = (DATA.radio && DATA.radio.script_sig) || "";
      const isNewerDay = DATA.plan_date && rm.date > DATA.plan_date;
      const isNewerAudio = curRadioDate && rm.date >= curRadioDate && rm.script_sig && curSig && rm.script_sig !== curSig;
      if ((isNewerDay || isNewerAudio) && !activeKind && radioPlayer.paused) {
        const targetKey = `${rm.date}_${rm.script_sig || ""}`;
        try {
          const prev = sessionStorage.getItem("n3_edition_reload") || "";
          const parts = prev.split("@");
          if (parts[0] === targetKey && (Date.now() - Number(parts[1] || 0)) < 20000) return;
          sessionStorage.setItem("n3_edition_reload", `${targetKey}@${Date.now()}`);
        } catch (e) {}
        location.reload();
      }
    })
    .catch(() => {})
    .finally(() => { editionCheckBusy = false; });
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    checkNewDailyEdition();
    pullCloudSync(true);
    connectCloudSSE();
  } else {
    if (cloudPushTimer) {
      clearTimeout(cloudPushTimer);
      cloudPushTimer = null;
      pushCloudSync(true);
    }
  }
});

window.addEventListener("online", () => {
  checkNewDailyEdition();
  pullCloudSync(true);
  connectCloudSSE();
});

window.addEventListener("pagehide", () => {
  if (cloudPushTimer) {
    clearTimeout(cloudPushTimer);
    cloudPushTimer = null;
    pushCloudSync(true);
  }
});

function initApp() {
  // When running on local tutor_server.py, also union-merge local server state if present
  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    fetch("./api/state").then(r => r.ok ? r.json() : null).then(st => {
      if (!st || !st.session || !Array.isArray(st.session.doneIds)) return;
      let changed = false;
      st.session.doneIds.forEach(rawId => {
        const pid = CARD_TO_POINT_ID[rawId] || rawId;
        if (A.pts[pid] && A.pts[pid].status !== "green") {
          A.pts[pid].greenAt = Math.max(A.pts[pid].greenAt || 0, 2);
          changed = true;
        }
      });
      if (changed) {
        recomputeStatusesFromCRDT(A);
        applyMasteryOverrides();
        saveAdaptiveState();
        if (curPointId && A.pts[curPointId] && A.pts[curPointId].status === "green" && viewStage === "quiz") {
          setupCurrentTurn();
        }
        renderGreenBoard();
        if (activeMode === "tutor") renderTutor();
      }
    }).catch(() => {});
  }

  const params = new URLSearchParams(location.search);
  const m = params.get("mode");
  if (m === "dash") switchMode("dash");
  else if (m === "radio" || m === "walk") switchMode("radio", false);
  else renderTutor();

  checkNewDailyEdition();
  // Pull latest multi-platform cloud snapshot & auto-upload any local-only answers, then keep SSE live
  pullCloudSync(true).then(() => {
    connectCloudSSE();
  });
}
initApp();
</script>
</body>
</html>
"""

final_html = html.replace("__PAYLOAD__", payload)
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(final_html)

sw_path = os.path.join(BASE_DIR, "sw.js")
if os.path.exists(sw_path):
    with open(sw_path, encoding="utf-8") as sf:
        sw_src = sf.read()
    new_stamp = f'{plan_date_str}_{radio_meta.get("script_sig", "")}'
    sw_next = re.sub(
        r'const BUILD_STAMP = "[^"]*";',
        f'const BUILD_STAMP = "{new_stamp}";',
        sw_src,
        count=1,
    )
    if sw_next != sw_src:
        with open(sw_path, "w", encoding="utf-8") as sf:
            sf.write(sw_next)

print(
    "Wrote Zen v12 N3 Platform:",
    HTML_PATH,
    "points:",
    len(ordered_points),
    "lexicon:",
    len(rich_words),
    "size:",
    len(final_html),
)
