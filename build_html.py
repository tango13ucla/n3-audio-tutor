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
from __future__ import annotations
import glob
import hashlib
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
from vocab_cards import (
    HAS_KANJI_RE,
    VOCAB_CARDS,
    analyze_kanji_reading_trap,
    build_dynamic_vocab_card,
)
import tutor_prefs

MEMORY_PREFS = tutor_prefs.load_prefs()
MEMORY_FOCUS = tutor_prefs.focus_set(MEMORY_PREFS)
DECK_CAP = tutor_prefs.deck_cap(MEMORY_PREFS)
TODAY_LOAD, TODAY_LOAD_WHY = tutor_prefs.today_load(MEMORY_PREFS)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, "index.html")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
AUDIO_MANIFEST_PATH = os.path.join(BASE_DIR, "audio", "audio_manifest.json")
RADIO_META_PATH = os.path.join(BASE_DIR, "audio", "daily_radio_meta.json")
TRUE_GREEN_EPOCH = 1794761500

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
    kana_val = str(entry.get("kana") or surf).strip()
    if HAS_KANJI_RE.search(surf) and kana_val != surf:
        thl, ttag, opq = analyze_kanji_reading_trap(
            surf, kana_val, str(entry.get("zh") or ""), str(entry.get("head") or "")
        )
        entry["trap_hl"] = thl
        entry["trap_tag"] = ttag
        entry["zh_opaque"] = opq
    rich_words[surf] = entry


def resolve_word_audio(w: str) -> str:
    return rich_words.get(w, {}).get("audio") or word_audio_map.get(w, "")

SUBJ_CN = {"文法": "语法", "活用": "活用", "語彙": "词汇", "聴解": "听力"}


def strip_opt_prefix(s: str) -> str:
    return re.sub(r"^[a-dA-D]\.\s*", "", str(s)).strip()


def clean_zen_text(s: str) -> str:
    txt = str(s or "").strip()
    txt = re.sub(r"[✅❌⭕✕✓↑↓🎧★]", "", txt)
    txt = re.sub(r"\d+/\d+(?:\s*(?:&|与|和)\s*\d+/\d+)?\s*课[^·。！!：:]*[·：:\s]*", "", txt)
    txt = txt.replace("——", "：").replace("—", "：")
    txt = re.sub(
        r"^(?:听力保命铁律|声音\+画面双锚|双重铁证|考场秒杀铁律|考试卷面铁律|秒杀铁律|记忆铁律|一眼锁死助词|看动词时态定画面|这对双胞胎反着记)[：:]\s*",
        "",
        txt,
    )
    txt = re.sub(
        r"^(?:正确接续|标准接续|得体地道|头号反向陷阱|反向陷阱|字面陷阱|N3\s*变形题头号陷阱)[！!：:\s]*",
        "",
        txt,
    )
    txt = re.sub(r"[，,]\s*(?:完美契合|N3\s*必考核心句型)(?=[。！!]?$)", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"[！!]+$", "。", txt)
    txt = re.sub(r"[！!]+", "。", txt)
    return txt


LISTENING_OPT_NOTES = {
    "Q-20261114-001": {
        "じゃあ、今日は作らなくていいね。": "「那今天不用做了呢。」把口语 しないと（必须做）听反了。",
        "ほんとだ、急いで帰ろう。": "「真的耶，赶紧回去吧。」顺着女生催回家做晚饭自然回应。",
        "夕飯、おいしかったね。": "「晚饭真好吃呢。」时态不对，晚饭还没开始准备。",
    },
    "Q-20261114-002": {
        "袋をもらう。": "「要袋子。」误把礼貌谢绝的 袋はいいです 按字面听成要。",
        "袋はいらない。": "「不要袋子。」客人谢绝装袋并说明直接拿回去。",
        "大きい袋に変える。": "「换成大袋子。」对话中未提及。",
    },
    "Q-20261114-003": {
        "えっ、本当？あそこ好きだったのに。": "「啊真的吗？我明明很喜欢那家的。」对老店歇业传闻的惊讶与惋惜。",
        "うん、私が閉めたんだよ。": "「嗯，是我把门关上的。」把店歇业（閉まる）听成了自己关门（閉めた）。",
        "パン、買ってきてくれたの？": "「你帮我买面包回来了吗？」答非所问。",
    },
    "Q-20261114-004": {
        "昨日もう会議は終わりましたよ。": "「昨天会已经开完了哦。」与上司说的「开会前」矛盾。",
        "コピー機は使いません。": "「不用复印机。」答非所问。",
        "はい、すぐコピーしておきます。": "「好的，我马上提前印好。」听懂口语缩音 しといて，得体承接任务。",
    },
    "Q-20261114-005": {
        "うん、引き継ぎをしておけば大丈夫だよ。": "「嗯，只要提前做好工作交接就没问题。」部长准假并叮嘱交接。",
        "えっ、私に来週休んでほしいの？": "「咦，你要我下周休息吗？」把下属请假听反成了让部长休假。",
        "金曜日ならもう休みましたよ。": "「周五的话已经休过了哦。」时态错误，请的是下周五的假。",
    },
    "N3-L06": {
        "会議室を準備する": "「布置会议室。」课长说 会議室は後にして（先放后面再弄）。",
        "資料を印刷する": "「打印资料。」课长明确指示 先に資料を印刷してくれる？（先印资料）。",
        "課長にメールする": "「给课长发邮件。」对话中未提及。",
    },
    "VAR-L01": {
        "うん、今すぐ払わないとね。": "「嗯，得马上交了呢。」用同义口语 払わないと 顺着附和。",
        "じゃあ、払わなくてもいいんだね。": "「那不用交了呢。」把口语 払わなくちゃ（必须交）听反了。",
        "昨日もう払ったよ。": "「昨天已经交了哦。」与男生刚发现还没交矛盾。",
    },
    "VAR-L04": {
        "ホテルには泊まらないよ。": "「不住酒店哦。」答非所问。",
        "旅行は楽しかったね。": "「旅行真开心呢。」过去式错误，旅行在下个月还没去。",
        "わかった、今すぐ予約しておくね。": "「好，我现在就提前订好。」听懂口语缩音 しとかないと，回应马上订。",
    },
    "VAR-L06": {
        "銀行へ行く": "「去银行。」前辈说 銀行はその後でね（排在回邮件之后）。",
        "昼ご飯を食べる": "「吃午饭。」对话中未提及。",
        "メールを返信する": "「回复邮件。」前辈要求 その前に（去银行前先把邮件回了）。",
    },
}
try:
    from weak_expansion_wave2 import WAVE2_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE2_LISTENING_OPT_NOTES)
except Exception:
    pass


def build_opt_notes(card_id: str, raw_notes: dict | None) -> dict:
    if card_id in LISTENING_OPT_NOTES:
        return dict(LISTENING_OPT_NOTES[card_id])
    out = {}
    for k, v in (raw_notes or {}).items():
        cleaned = clean_zen_text(v)
        if cleaned:
            out[str(k)] = cleaned
    return out


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
    if (qid and qid in MEMORY_FOCUS) or (point_key and point_key in MEMORY_FOCUS):
        base += 0.45
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
            "opt_notes": build_opt_notes(vid, vc.get("option_notes")),
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
    opt_notes = build_opt_notes(qid, t_item.get("option_notes"))
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
            "opt_notes": opt_notes,
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
            "opt_notes": build_opt_notes(qid, ext.get("option_notes")),
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "is_listening": is_l,
        },
        "variants": variants_by_base.get(qid, []),
    })

plan_date_str = (
    live_state.get("study_date")
    or radio_meta.get("date")
    or live_state.get("updated_at", plan.get("plan_date", "2026-11-15"))[:10]
)
MIN_REAL_TS = 1_700_000_000
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

raw_seeded_day = dict((cloud_snap.get("dates") or {}).get(plan_date_str) or {})
clean_green_at = {
    k: int(v)
    for k, v in (raw_seeded_day.get("greenAt") or {}).items()
    if int(v or 0) >= MIN_REAL_TS
}
clean_retest_at = {
    k: int(v)
    for k, v in (raw_seeded_day.get("retestAt") or {}).items()
    if int(v or 0) >= MIN_REAL_TS
}
raw_seeded_day["greenAt"] = clean_green_at
raw_seeded_day["retestAt"] = clean_retest_at
seeded_day = raw_seeded_day

card_to_base = {p["id"]: p["id"] for p in raw_points}
for p in raw_points:
    for vc in p.get("variants") or []:
        if vc.get("id"):
            card_to_base[vc["id"]] = p["id"]

touched_today_ids = set()
for cid in list(clean_green_at.keys()) + list(clean_retest_at.keys()) + list((seeded_day.get("sched") or {}).keys()):
    touched_today_ids.add(card_to_base.get(cid, cid))

prev_day_touched_ids = set()
try:
    all_snap_dates = sorted(d for d in (cloud_snap.get("dates") or {}).keys() if d < plan_date_str)
    if all_snap_dates:
        prev_day_obj = (cloud_snap.get("dates") or {}).get(all_snap_dates[-1]) or {}
        for cid in list((prev_day_obj.get("greenAt") or {}).keys()) + list((prev_day_obj.get("retestAt") or {}).keys()):
            prev_day_touched_ids.add(card_to_base.get(cid, cid))
except Exception:
    pass

try:
    import datetime as _dt_mod
    _plan_day_ord = _dt_mod.date.fromisoformat(plan_date_str[:10]).toordinal()
except Exception:
    _plan_day_ord = 1


def deck_sort_key(p: dict):
    qid = p["id"]
    if qid in touched_today_ids:
        return (0, -p["roi_score"], -p["exam_weight"], qid)
    st = resolve_point_status(p["point_key"])
    is_graduated = 1 if st == "green" else 0
    return (1 + is_graduated, -p["roi_score"], -p["exam_weight"], qid)


raw_points.sort(key=deck_sort_key)
raw_points = raw_points[:DECK_CAP]

# Cross-day fresh sentence rotation: if a point was NOT yet touched today, has variants,
# and was answered yesterday (or is in cross-day consolidation), swap in a fresh variant sentence
# as today's primary while preserving the original in variants for same-day retest!
for _p in raw_points:
    _qid = _p["id"]
    _vars = list(_p.get("variants") or [])
    if _qid in touched_today_ids or not _vars:
        continue
    if _qid in prev_day_touched_ids:
        _all_cards = [_p["primary"]] + _vars
        _pick_idx = 1 + (_plan_day_ord % len(_vars))
        _new_prim = _all_cards[_pick_idx]
        _p["primary"] = _new_prim
        _p["variants"] = [_c for _i, _c in enumerate(_all_cards) if _i != _pick_idx]
        if _p.get("teach"):
            _p["teach"]["example_ja"] = _new_prim.get("full_ja") or _p["teach"].get("example_ja", "")
            _p["teach"]["zh_meaning"] = _new_prim.get("zh_meaning") or _p["teach"].get("zh_meaning", "")
            _p["teach"]["audio"] = _new_prim.get("exp_audio") or _p["teach"].get("audio", "")

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


def norm_tier_meta(p_obj: dict) -> tuple[str, str, int]:
    status = p_obj.get("status", "yellow")
    if status in ("red", "orange"):
        return "todo", "todo", 0
    if status == "green":
        return "done", "done", 3
    if status == "gray":
        return "wip", "wip0", 0
    s = 2 if int(p_obj.get("streak") or 1) >= 2 else 1
    ok_d = str(p_obj.get("last_ok_date") or "20261114").replace("-", "")[:8] or "20261114"
    return "wip", f"wip{s}:{ok_d}", s


grammar_items = []
for p in live_state.get("grammar_points", []):
    nm = p.get("name", "")
    tier, mstate, streak = norm_tier_meta(p)
    grammar_items.append({
        "key": nm,
        "name": nm,
        "sub": p.get("meaning", ""),
        "family": re.sub(r"^\d+\.\s*", "", p.get("family", "")),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "point_id": point_id_by_key.get(nm, ""),
        "note": clean_zen_text(p.get("exam_alert") or p.get("note", "")),
    })

henkei_items = []
for p in live_state.get("henkei_points", []):
    if p.get("tier") == "basic_n5n4" and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    tier, mstate, streak = norm_tier_meta(p)
    henkei_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("example", ""),
        "family": re.sub(r"^\d+(?:\.\d+)?\s*", "", p.get("subcategory") or p.get("category", "")),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "point_id": point_id_by_key.get(pid, ""),
        "note": clean_zen_text(p.get("note", "")),
    })

listening_items = []
for p in live_state.get("listening_points", []):
    if not p.get("is_core165") and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    tier, mstate, streak = norm_tier_meta(p)
    listening_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("meaning", "") or p.get("full", ""),
        "family": p.get("category", ""),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "point_id": point_id_by_key.get(pid, ""),
        "note": clean_zen_text(p.get("trap", "") or p.get("note", "")),
    })

DROP_CASUAL_WORDS = {"ぱさぱさ", "ずしっと", "万年筆", "こと", "おく", "ない", "だ"}
vocab_items = []
seen_vocab_words = set()
vc_audio_manifest = audio_manifest.get("vocab_cards", {})

for p in live_state.get("vocab_tracked", []):
    w = p.get("word", "")
    if w in DROP_CASUAL_WORDS:
        continue
    seen_vocab_words.add(w)
    tier, mstate, streak = norm_tier_meta(p)
    w_info = rich_words.get(w, {})
    vc_spec = VOCAB_CARDS.get(w, {})
    meaning_short = w_info.get("zh") or (vc_spec.get("zh", "").split(" · ")[0]) or re.sub(r"^\d+\.\s*", "", p.get("category", ""))
    vocab_items.append({
        "key": w,
        "name": w,
        "sub": meaning_short,
        "family": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "point_id": point_id_by_key.get(w, ""),
        "audio": resolve_word_audio(w),
        "note": clean_zen_text(vc_spec.get("twin") or w_info.get("tip") or p.get("classroom_note") or ""),
    })

for kw, pitch, desc in CORE_N3_KANA_VOCAB:
    if kw in seen_vocab_words:
        continue
    seen_vocab_words.add(kw)
    vc_spec = VOCAB_CARDS.get(kw, {})
    vocab_items.append({
        "key": kw,
        "name": kw,
        "sub": desc.split("（")[0],
        "family": "高频假名副词",
        "tier": "wip",
        "mstate": "wip0",
        "streak": 0,
        "point_id": point_id_by_key.get(kw, ""),
        "audio": resolve_word_audio(kw),
        "note": clean_zen_text(vc_spec.get("twin") or f"声调 {pitch} · {desc}"),
    })

vocab_cards_payload = {}
all_vc_keys = list(seen_vocab_words) + [k for k in VOCAB_CARDS if k not in seen_vocab_words]
for vw in all_vc_keys:
    spec = build_dynamic_vocab_card(vw, rich_words.get(vw, {}))
    vc_aud = vc_audio_manifest.get(vw) or {}
    w_aud = resolve_word_audio(vw)
    front_aud = vc_aud.get("front") or (w_aud if spec["mode"] == "kana_meaning" else "")
    rev_aud = vc_aud.get("rev") or ""
    full_aud = vc_aud.get("full") or rev_aud or w_aud
    vocab_cards_payload[vw] = {
        "mode": spec["mode"],
        "chunk_ja": spec["chunk_ja"],
        "target": spec["target"],
        "kana": spec["kana"],
        "trap_hl": spec.get("trap_hl") or [],
        "trap_tag": spec.get("trap_tag") or "",
        "zh_opaque": bool(spec.get("zh_opaque", True)),
        "pitch": spec["pitch"],
        "zh": spec["zh"],
        "twin": spec["twin"],
        "zh_speak": spec.get("zh_speak", ""),
        "front_audio": front_aud,
        "rev_audio": rev_aud,
        "full_audio": full_aud,
        "word_audio": w_aud,
    }


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

baked_epoch = int(live_state.get("_baked_epoch") or 0)
seeded_overrides = {
    mk: mv
    for mk, mv in (cloud_snap.get("masteryOverrides") or {}).items()
    if isinstance(mv, list) and len(mv) == 2 and int(mv[1] or 0) >= max(TRUE_GREEN_EPOCH, baked_epoch - 7200)
}
recent_weak_words = [
    it["name"]
    for it in vocab_items
    if it["tier"] != "done" and (it["name"] in recent_weak_keys or it["name"] in MEMORY_FOCUS)
]

vocab_base_done = sum(1 for it in vocab_items if it["tier"] == "done")

payload = json.dumps({
    "plan_date": plan_date_str,
    "exam_date": "2026-12-06",
    "days_to_exam": live_state.get("days_left", plan.get("days_to_exam", 21)),
    "done_audio": "./audio/done.mp3",
    "radio": radio_meta,
    "points": ordered_points,
    "words": rich_words,
    "vocab_cards": vocab_cards_payload,
    "mastery": mastery_data,
    "vocab_base_done": vocab_base_done,
    "true_green_epoch": TRUE_GREEN_EPOCH,
    "baked_epoch": baked_epoch,
    "recent_weak_words": recent_weak_words,
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
<meta name="screen-orientation" content="portrait" />
<meta name="x5-orientation" content="portrait" />
<meta name="description" content="JLPT N3 · 做题 · 随身听 · 单手记词" />
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
    padding: calc(14px + env(safe-area-inset-top)) 26px calc(16px + env(safe-area-inset-bottom));
  }

  .zen-shell {
    width: 100%;
    max-width: 496px;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  @media (min-width: 860px) and (min-height: 521px) {
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

  /* Portrait guard (phone only): counter-rotate the app when the OS rotates to landscape anyway */
  html.fp {
    width: var(--fp-w);
    height: var(--fp-h);
    overflow: hidden;
  }
  html.fp body {
    position: fixed;
    top: 0;
    left: 0;
    width: var(--fp-h) !important;
    height: var(--fp-w) !important;
    padding-left: 26px;
    padding-right: 26px;
    transform-origin: 0 0;
  }
  html.fp-90 body { transform: translateY(var(--fp-h)) rotate(-90deg); }
  html.fp-270 body { transform: translateX(var(--fp-w)) rotate(90deg); }
  html.fp #tutor-view,
  html.fp .focal-space { touch-action: manipulation; }

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
    gap: 20px;
  }
  .nav-link {
    font-size: 16.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    padding: 6px 4px 5px;
    margin: -6px -4px 0;
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
    left: 4px;
    right: 4px;
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
    width: 32px;
    height: 32px;
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
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 8px 0 8px 10px;
    margin: -4px 0;
  }
  .horizon-score .ledger-tag {
    color: var(--ink-2);
    transition: color 0.18s ease;
  }
  .horizon-score.active-ledger .ledger-tag {
    color: var(--sumi);
    font-weight: 600;
  }
  .horizon-track {
    display: none;
  }

  /* ================= 3. OPEN WASHI STAGE (余白 MA + TINDER SWIPE ERGONOMICS) ================= */
  .zen-panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .zen-panel.hidden {
    display: none;
  }
  #tutor-view {
    touch-action: pan-y;
  }

  .stage-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding-top: 14px;
    animation: fadeTurn 0.18s ease-out;
    will-change: transform, opacity;
  }
  @keyframes fadeTurn {
    from { opacity: 0.48; }
    to { opacity: 1; }
  }

  /* Tactile Tinder-style card physics on Result & Teach pages (frameless open Washi) */
  .stage-wrap.tutor-dragging {
    transition: none !important;
    animation: none !important;
  }
  .stage-wrap.tutor-settling {
    transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
  }
  .stage-wrap.tutor-fly-right {
    transform: translate3d(118%, 8px, 0) rotate(6.5deg) !important;
    opacity: 0 !important;
    transition: transform 0.21s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.19s ease !important;
  }
  .stage-wrap.tutor-fly-left {
    transform: translate3d(-118%, 8px, 0) rotate(-6.5deg) !important;
    opacity: 0 !important;
    transition: transform 0.21s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.19s ease !important;
  }
  .tutor-stamp {
    position: absolute;
    top: 46px;
    z-index: 30;
    padding: 4px 11px;
    border-radius: 5px;
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: 0.07em;
    opacity: 0;
    pointer-events: none;
  }
  .tutor-stamp.right {
    left: 2px;
    color: var(--moss);
    border: 1.5px solid var(--moss);
    background: rgba(252, 251, 248, 0.94);
  }
  .tutor-stamp.left {
    right: 2px;
    color: var(--bengara);
    border: 1.5px solid var(--bengara);
    background: rgba(252, 251, 248, 0.94);
  }
  .tutor-stamp.left.moss-tone {
    color: var(--moss);
    border-color: var(--moss);
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
    gap: 16px;
    flex-shrink: 0;
  }
  .text-btn {
    font-size: 14.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    font-variant-numeric: tabular-nums;
    padding: 8px 5px;
    margin: -6px -5px;
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
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding: 16px 0 22px;
    scrollbar-width: none;
    -webkit-mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 22px), transparent 100%);
    mask-image: linear-gradient(to bottom, #000 0, #000 calc(100% - 22px), transparent 100%);
  }
  .focal-space > * { flex-shrink: 0; }
  .focal-space::-webkit-scrollbar { display: none; }
  .stage-quiz .focal-space > :first-child,
  .stage-done .focal-space > :first-child { margin-top: auto; }
  .stage-quiz .focal-space > :last-child,
  .stage-done .focal-space > :last-child { margin-bottom: auto; }

  .action-dock {
    flex-shrink: 0;
    padding-top: 10px;
  }

  /* Right-Handed Single-Hand Mobile Ergonomics (<860px) · 上看下点:
     The top of a tall phone is for READING only (zero taps needed there).
     Everything tappable lives in the right-thumb arc (~58-88% height) plus a quiet bottom-right nav,
     so the hand never shifts up to the top corners and never curls down into the bezel. */
  .thumb-nav { display: none; }
  @media (max-width: 859px), (max-height: 520px) {
    body {
      padding-bottom: calc(4px + env(safe-area-inset-bottom));
    }
    .zen-header { display: none; }
    .zen-horizon { padding-top: 4px; }
    .horizon-score .ledger-sep,
    .horizon-score .ledger-tag { display: none; }

    .thumb-nav {
      flex-shrink: 0;
      display: flex;
      justify-content: flex-end;
      align-items: center;
      border-top: 1px solid var(--hairline);
    }
    .thumb-tabs {
      display: flex;
      align-items: stretch;
      margin-right: -10px;
    }
    .thumb-link {
      position: relative;
      height: 54px;
      min-width: 60px;
      padding: 0 11px;
      font-size: 16px;
      font-weight: 500;
      color: var(--ink-3);
      letter-spacing: 0.04em;
      transition: color 0.2s ease;
    }
    .thumb-link.active {
      color: var(--sumi);
      font-weight: 600;
    }
    /* Ink stroke resting on the hairline (mirror of the old header underline) */
    .thumb-link.active::before {
      content: "";
      position: absolute;
      top: -1px;
      left: 50%;
      width: 18px;
      margin-left: -9px;
      height: 1.5px;
      background: var(--sumi);
    }
    .thumb-link.is-playing { color: var(--moss); }
    .thumb-link:active { opacity: 0.6; }

    .ledger-back-fab { display: none !important; }
    .ledger-scroll { padding-bottom: 24px; }

    .action-dock,
    .radio-dock,
    .vc-dock {
      padding-bottom: clamp(16px, 4.4vh, 44px);
    }
    #tutor-view .stage-quiz .focal-space {
      justify-content: flex-end;
      padding-bottom: 24px;
      -webkit-mask-image: none;
      mask-image: none;
    }
    #tutor-view .stage-quiz .focal-space > :first-child,
    #tutor-view .stage-quiz .focal-space > :last-child {
      margin-top: 0;
      margin-bottom: 0;
    }
    #tutor-view .stage-quiz .quiz-focal {
      min-height: 92px;
      justify-content: flex-end;
    }
    #tutor-view .stage-quiz .listen-medallion-wrap {
      padding: 12px 0 8px;
    }
  }

  /* Desktop vs Mobile Ergonomics (>=860px):
     Quiz centers optically; reading views stay anchored from top so tapping words shifts 0px. */
  @media (min-width: 860px) and (min-height: 521px) {
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
  @media (min-width: 860px) and (min-height: 521px) {
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

  /* Quiz aux row (簡素 · Kanso): two quiet ink words, no boxes.
     The option cards stay the ONLY objects on the page; 读题 rests on the right edge under the thumb. */
  .quiz-aux-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
  }
  .quiz-aux-row .unsure-btn,
  .quiz-aux-row .aux-read-btn {
    width: auto;
    height: 48px;
    min-height: 48px;
    margin: 0;
    border: none;
    border-radius: 0;
    background: transparent;
    font-size: 14.5px;
    font-weight: 500;
    letter-spacing: 0.05em;
    transition: opacity 0.15s ease, color 0.2s ease;
  }
  .quiz-aux-row .unsure-btn {
    flex: 0 1 auto;
    justify-content: flex-start;
    padding: 0 24px 0 2px;
    color: var(--ink-3);
  }
  .quiz-aux-row .aux-read-btn {
    flex-shrink: 0;
    padding: 0 2px 0 28px;
    color: var(--ink-2);
  }
  .quiz-aux-row .aux-read-btn.playing { color: var(--moss); font-weight: 600; }
  .quiz-aux-row .unsure-btn:active,
  .quiz-aux-row .aux-read-btn:active { background: transparent; opacity: 0.5; }
  @media (min-width: 860px) and (min-height: 521px) {
    .quiz-aux-row .unsure-btn:hover,
    .quiz-aux-row .aux-read-btn:hover { background: transparent; color: var(--sumi); }
  }

  .desk-hint { display: none; }
  .kbd-tag {
    display: inline-block;
    font-family: var(--sans);
    font-size: 13px;
    color: var(--ink-3);
    opacity: 0.45;
    font-variant-numeric: tabular-nums;
    margin-left: 10px;
    flex-shrink: 0;
  }
  .unsure-btn .kbd-tag { display: none; }
  @media (min-width: 860px) and (min-height: 521px) {
    .zen-choice:hover, .listen-num-btn:hover { border-color: var(--sumi); background: #FFFFFF; }
    .unsure-btn:hover { border-color: var(--sumi); color: var(--sumi); background: rgba(252, 251, 248, 0.72); }
    .kbd-tag { opacity: 1; }
    .unsure-btn .kbd-tag { display: inline-block; }
    .desk-hint {
      display: inline-block;
      font-size: 12.5px;
      font-weight: 400;
      opacity: 0.68;
      letter-spacing: 0.03em;
      margin-left: 10px;
    }
  }
  .quiz-ja {
    cursor: pointer;
  }

  /* -------- RESULT VIEW (3-Step Human Clarity: 句意 -> 为什么用 -> 变形与辨析) -------- */
  .result-ja {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 22.5px;
    font-weight: 500;
    line-height: 1.68;
    letter-spacing: 0.03em;
    color: var(--sumi);
    white-space: pre-line;
  }
  .ans-hl {
    color: var(--moss);
    font-weight: 600;
  }
  .result-zh {
    margin: 6px 0 0;
    font-size: 15px;
    font-weight: 400;
    color: var(--ink-3);
    line-height: 1.58;
    letter-spacing: 0.012em;
  }
  .dlg {
    display: flex;
    flex-direction: column;
    gap: 9px;
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
    font-size: 19px;
    font-weight: 500;
    line-height: 1.58;
    letter-spacing: 0.02em;
    color: var(--sumi);
  }
  .dlg-row.is-ans .dlg-who {
    color: var(--moss);
    border-color: rgba(43, 95, 73, 0.35);
  }
  .dlg-zh {
    margin-top: 2px;
    font-size: 14px;
    font-weight: 400;
    color: var(--ink-3);
    line-height: 1.52;
    letter-spacing: 0.01em;
  }
  .res-cue {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 9px;
    align-items: baseline;
    margin-bottom: 10px;
  }
  .cue-tag {
    font-family: var(--sans);
    font-size: 11.5px;
    font-weight: 600;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    border: 1px solid var(--hairline-strong);
    border-radius: 4px;
    padding: 1px 6px;
    line-height: 1.45;
    white-space: nowrap;
  }
  .cue-txt {
    font-size: 14.5px;
    font-weight: 400;
    color: var(--ink-2);
    line-height: 1.56;
    letter-spacing: 0.01em;
  }
  .opt-breakdown {
    display: flex;
    flex-direction: column;
  }
  .opt-row {
    display: grid;
    grid-template-columns: 20px 1fr;
    column-gap: 9px;
    padding: 9px 0;
    border-top: 1px dashed rgba(28, 27, 24, 0.10);
    align-items: baseline;
  }
  .opt-breakdown.is-listen .opt-row {
    grid-template-columns: 34px 1fr;
  }
  .opt-row:first-child {
    border-top: none;
    padding-top: 2px;
  }
  .opt-row:last-child {
    padding-bottom: 2px;
  }
  .opt-mark {
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .opt-row.ok .opt-mark {
    color: #2D7A56;
  }
  .opt-row.ng .opt-mark {
    color: var(--bengara);
  }
  .opt-body {
    min-width: 0;
  }
  .opt-head {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }
  .opt-ja {
    font-family: var(--serif-jp);
    font-size: 17.5px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.45;
  }
  .opt-row.ok .opt-ja {
    color: #266A4A;
  }
  .opt-row.ng .opt-ja {
    color: var(--bengara);
  }
  .opt-row.dim .opt-ja {
    font-weight: 500;
    color: var(--ink-2);
  }
  .opt-badge {
    font-family: var(--sans);
    font-size: 11.5px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 4px;
    line-height: 1.4;
    letter-spacing: 0.03em;
  }
  .opt-badge.ok {
    color: #266A4A;
    background: rgba(45, 122, 86, 0.11);
  }
  .opt-badge.ng {
    color: var(--bengara);
    background: rgba(166, 61, 47, 0.10);
  }
  .opt-desc {
    margin-top: 2.5px;
    font-size: 14.5px;
    line-height: 1.56;
    color: var(--ink-2);
    letter-spacing: 0.01em;
  }
  .opt-row.dim .opt-desc {
    color: var(--ink-3);
  }

  /* Tappable Japanese words + Fixed-Geometry Zen Meaning Card (Tap anywhere on card to replay pronunciation) */
  .w-tok {
    position: relative;
    cursor: pointer;
    padding: 1px 0;
    border-radius: 3px;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }
  .w-tok.marked-tok::after {
    content: "";
    position: absolute;
    left: 50%;
    bottom: -3px;
    width: 4px;
    height: 4px;
    margin-left: -2px;
    border-radius: 50%;
    background: var(--bengara);
    opacity: 0.86;
    pointer-events: none;
  }
  .w-tok.active-tok {
    color: var(--moss);
    background: var(--moss-soft);
    box-shadow: inset 0 -1.5px 0 var(--moss);
  }
  .w-tok.active-tok.marked-tok::after {
    opacity: 0;
  }

  .inline-lex {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 108px;
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
    cursor: pointer;
  }
  .inline-lex:active {
    background: #F4F1E8;
  }
  #radio-inline-lex {
    bottom: 12px;
    box-shadow: none;
  }
  @media (min-width: 860px) and (min-height: 521px) {
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
    color: var(--ink-2);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .kana-trap {
    color: var(--bengara);
    font-weight: 700;
  }
  .kana-tag {
    font-size: 0.82em;
    color: var(--ink-3);
    font-weight: 400;
    letter-spacing: 0.02em;
    margin-left: 4px;
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
    margin: 14px 0;
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

  /* Right-Hand Ergonomic Architectural Sumi Buttons */
  .dock-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .dock-replay-btn {
    height: 52px;
    padding: 0 14px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 14.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }
  .dock-replay-btn.playing {
    border-color: var(--moss);
    color: var(--moss);
    font-weight: 600;
  }
  .sumi-btn {
    flex: 1.45;
    height: 52px;
    background: var(--sumi);
    color: var(--sheet);
    border-radius: 8px;
    font-size: 16.5px;
    font-weight: 500;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .sumi-btn:active { opacity: 0.88; }
  .ghost-btn {
    height: 52px;
    padding: 0 16px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }
  .ghost-btn:active, .dock-replay-btn:active { background: #EDEAE1; }

  /* ================= 4. THREE-HOST PODCAST SANCTUARY ("随身听") ================= */
  .radio-center {
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding-top: 28px;
    gap: 15px;
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
    gap: 16px;
    padding-top: 10px;
  }
  .scrub-wrap { width: 100%; }
  .zen-range {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 3px;
    background: var(--track);
    outline: none;
    margin: 12px 0 8px;
    cursor: pointer;
  }
  .zen-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 15px;
    height: 15px;
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

  /* Right-Hand Thumb Transport Cluster: [1.0x] [-15s] [ 播放 ] [+15s] */
  .transport-row {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
  }
  @media (min-width: 860px) and (min-height: 521px) {
    .transport-row { justify-content: space-between; }
  }
  .radio-spd-pill {
    height: 48px;
    padding: 0 13px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .step-time-btn {
    height: 48px;
    padding: 0 15px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    background: var(--sheet);
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .step-time-btn:active, .radio-spd-pill:active { background: #EDEAE1; }
  .play-toggle-btn {
    flex: 1;
    max-width: 168px;
    min-width: 118px;
    height: 48px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 0.08em;
  }

  .chapter-strip {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--hairline);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .chapter-strip::-webkit-scrollbar { display: none; }
  .chap-link {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    padding: 7px 6px;
    border-radius: 6px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .chap-link.active {
    color: var(--sumi);
    background: rgba(28, 27, 24, 0.05);
    font-weight: 600;
  }

  /* ================= 5. ZEN LEDGER ("总表") ================= */
  #dash-view {
    position: relative;
  }
  .ledger-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 16px 0 78px;
    scrollbar-width: none;
  }
  .ledger-scroll::-webkit-scrollbar { display: none; }

  .ledger-back-fab {
    display: none;
  }
  @media (max-width: 859px), (max-height: 520px) {
    .ledger-back-fab {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      position: fixed;
      right: 26px;
      bottom: calc(44px + env(safe-area-inset-bottom));
      z-index: 45;
      height: 44px;
      padding: 0 18px;
      border-radius: 22px;
      background: var(--sumi);
      color: var(--sheet);
      font-size: 14.5px;
      font-weight: 500;
      letter-spacing: 0.05em;
      box-shadow: 0 4px 16px rgba(28, 27, 24, 0.16);
    }
  }

  @media (min-width: 860px) and (min-height: 521px) {
    .ledger-scroll { padding-bottom: 12px; }
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
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 8px;
  }
  .tier-links { display: flex; gap: 16px; }
  .tier-link {
    font-size: 15px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    padding: 6px 2px;
  }
  .tier-link.active {
    color: var(--sumi);
    font-weight: 600;
  }
  .zen-search {
    width: 128px;
    border: none;
    border-bottom: 1px solid var(--hairline-strong);
    background: transparent;
    padding: 5px 0;
    font-family: inherit;
    font-size: 14.5px;
    color: var(--sumi);
    outline: none;
    -webkit-user-select: text;
    user-select: text;
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
    align-items: center;
    gap: 10px;
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
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .li-sub {
    font-size: 13.5px;
    color: var(--ink-3);
    max-width: 116px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .li-streak {
    font-size: 12.5px;
    font-variant-numeric: tabular-nums;
    color: var(--ink-3);
    letter-spacing: 0.02em;
  }
  .li-streak.s-wip { color: var(--ochre); font-weight: 500; }
  .li-streak.s-done { color: var(--moss); font-weight: 500; }
  .li-act {
    font-size: 13.5px;
    color: var(--moss);
    font-weight: 500;
    height: 32px;
    padding: 0 10px;
    border-radius: 6px;
    border: 1px solid rgba(43, 95, 73, 0.22);
    background: var(--sheet);
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .li-act:active { background: var(--moss-soft); }
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
  @media (max-width: 859px), (max-height: 520px) {
    .modal-mask {
      align-items: flex-end;
      padding: 20px 20px calc(44px + env(safe-area-inset-bottom));
    }
  }
  .modal-mask.open { display: flex; }
  .modal-card {
    width: 100%;
    max-width: 396px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 12px;
    padding: 24px 22px;
  }
  .modal-h { margin: 0 0 12px; font-size: 18px; font-weight: 600; letter-spacing: 0.04em; }
  .modal-body { margin: 0 0 14px; font-size: 16px; color: var(--ink-2); line-height: 1.85; font-variant-numeric: tabular-nums; }
  .modal-promise { margin: 0 0 16px; padding-top: 12px; border-top: 1px solid var(--hairline); font-size: 14.5px; color: var(--moss); line-height: 1.65; font-weight: 500; }
  .sync-box {
    margin: 0 0 18px;
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
    height: 42px;
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

  /* ================= 7. ONE-HANDED SWIPE VOCAB SANCTUARY ("记词") ================= */
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

  .vc-meta-right {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .vc-dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .vc-dot {
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    border: 1.3px solid rgba(28, 27, 24, 0.28);
    background: transparent;
  }
  .vc-dot.on {
    border-color: var(--moss);
    background: var(--moss);
  }

  .vc-deck-area {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 12px 0 14px;
    position: relative;
  }
  .vc-card {
    position: relative;
    width: 100%;
    flex: 1;
    max-height: 448px;
    min-height: 264px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 12px;
    padding: 28px 22px 24px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    touch-action: none;
    cursor: grab;
    will-change: transform, opacity;
  }
  .vc-card.dragging {
    transition: none !important;
    cursor: grabbing;
  }
  .vc-card.settling {
    transition: transform 0.26s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease;
  }
  .vc-card.fly-right {
    transform: translate3d(122%, 10px, 0) rotate(9deg) !important;
    opacity: 0 !important;
    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease !important;
  }
  .vc-card.fly-left {
    transform: translate3d(-122%, 10px, 0) rotate(-9deg) !important;
    opacity: 0 !important;
    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease !important;
  }
  .vc-card.fly-up {
    transform: translate3d(0, -118%, 0) scale(0.96) !important;
    opacity: 0 !important;
    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease !important;
  }

  .vc-stamp {
    position: absolute;
    top: 16px;
    padding: 3px 10px;
    border-radius: 5px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.08em;
    opacity: 0;
    pointer-events: none;
  }
  .vc-stamp.right {
    left: 18px;
    color: var(--moss);
    border: 1.5px solid var(--moss);
    background: rgba(43, 95, 73, 0.06);
  }
  .vc-stamp.left {
    right: 18px;
    color: var(--bengara);
    border: 1.5px solid var(--bengara);
    background: rgba(158, 62, 54, 0.06);
  }
  .vc-stamp.up {
    left: 50%;
    transform: translateX(-50%);
    color: var(--moss);
    border: 1.5px solid var(--moss);
    background: rgba(43, 95, 73, 0.06);
  }

  .vc-cue {
    font-size: 12.5px;
    color: var(--ink-3);
    letter-spacing: 0.06em;
    margin-bottom: 18px;
    min-height: 18px;
  }
  .vc-cue.ng {
    color: var(--bengara);
    font-weight: 600;
  }
  .vc-chunk {
    font-family: var(--serif-jp);
    font-size: 30px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.46;
    letter-spacing: 0.02em;
  }
  .vc-hl {
    font-weight: 600;
    border-bottom: 2px solid rgba(43, 95, 73, 0.48);
    padding-bottom: 2px;
  }
  .vc-reveal {
    margin-top: 22px;
    min-height: 118px;
    width: 100%;
    max-width: 390px;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.22s ease, transform 0.22s ease;
    pointer-events: none;
  }
  .vc-reveal.shown {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .vc-kana {
    font-size: 19.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .vc-zh {
    font-size: 20.5px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.42;
  }
  .vc-zh.quiet {
    font-size: 16.5px;
    font-weight: 400;
    color: var(--ink-2);
  }
  .vc-twin {
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid var(--hairline);
    font-size: 14px;
    color: var(--ink-2);
    line-height: 1.56;
  }

  .vc-dock {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 4px;
  }
  .vc-btn {
    height: 48px;
    border-radius: 8px;
    font-size: 14.5px;
    font-weight: 500;
    letter-spacing: 0.03em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .vc-btn.ng {
    flex: 1.15;
    border: 1px solid rgba(158, 62, 54, 0.34);
    color: var(--bengara);
    font-weight: 600;
    background: var(--sheet);
  }
  .vc-btn.mid {
    flex: 0.78;
    border: 1px solid var(--hairline-strong);
    color: var(--ink-2);
    background: transparent;
    font-size: 13.5px;
  }
  .vc-btn.ok {
    flex: 1.15;
    background: var(--sumi);
    color: var(--sheet);
    font-weight: 600;
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
      <button class="nav-link" id="tab-vocab" onclick="switchMode('vocab')">记词</button>
    </nav>
  </header>

  <!-- 2. THREE ZEN ENSO DAILY RITUALS (円相 · 无字打卡) -->
  <div class="zen-horizon" id="green-board" onclick="openSessionModal()">
    <div class="horizon-meta">
      <div class="enso-trio" id="enso-trio"></div>
      <span class="sr-only" id="gm-left-txt"></span>
      <button type="button" class="horizon-score" id="gm-right-txt" onclick="toggleDashLedger(event)">预计 <b>108分</b><span class="ledger-sep"> · </span><span class="ledger-tag">总表</span></button>
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
        <div class="chapter-strip" id="radio-chap-pills"></div>

        <div class="scrub-wrap">
          <input type="range" class="zen-range" id="radio-seek" min="0" max="2100" value="0" step="1" oninput="onRadioScrub(this.value)" />
          <div class="time-pair">
            <span id="radio-cur-time">00:00</span>
            <span id="radio-tot-time">35:00</span>
          </div>
        </div>

        <div class="transport-row">
          <button class="radio-spd-pill" id="radio-spd-btn" onclick="cycleRadioSpeed()">1.0x</button>
          <button class="step-time-btn" onclick="seekRadioBy(-15)">-15s</button>
          <button class="play-toggle-btn" id="radio-play-btn" onclick="toggleRadioPlay()">播放</button>
          <button class="step-time-btn" onclick="seekRadioBy(15)">+15s</button>
        </div>
      </div>
    </div>
  </section>

  <!-- 3C. ONE-HANDED SWIPE VOCAB SANCTUARY ("记词") -->
  <section class="zen-panel hidden" id="vocab-view">
    <div class="stage-wrap" id="vocab-stage-box"></div>
  </section>

  <!-- 3D. ZEN LEDGER ("总表") -->
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
    <button type="button" class="ledger-back-fab" onclick="toggleDashLedger(event)">← 返回</button>
  </section>

  <!-- 4. RIGHT-THUMB NAV (phone only · 上看下点: top is for reading, bottom-right is for touching; mirrors the old top header, no ornament) -->
  <nav class="thumb-nav" aria-label="切换">
    <div class="thumb-tabs">
      <button class="thumb-link active" id="btab-tutor" onclick="switchMode('tutor')">做题</button>
      <button class="thumb-link" id="btab-radio" onclick="switchMode('radio', true)">随身听</button>
      <button class="thumb-link" id="btab-vocab" onclick="switchMode('vocab')">记词</button>
      <button class="thumb-link" id="btab-dash" onclick="switchMode('dash')">总表</button>
    </div>
  </nav>
</div>

<div class="modal-mask" id="app-modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-card" id="modal-content"></div>
</div>

<script>
const DATA = __PAYLOAD__;
const SPEEDS = [1.0, 1.15, 1.3, 1.5];
const RADIO_SPEEDS = [1.0, 1.15, 1.3];
const ADAPTIVE_KEY = "n3_adaptive_v13_" + DATA.plan_date;
const RADIO_SIG = String((DATA.radio && DATA.radio.script_sig) || "").slice(0, 8);
const LEGACY_RADIO_POS_KEY = "n3_radio_pos_" + (DATA.radio.date || DATA.plan_date);
const RADIO_POS_KEY = LEGACY_RADIO_POS_KEY + (RADIO_SIG ? "_" + RADIO_SIG : "");
const TODAY_TAG = String(DATA.plan_date || "").replace(/-/g, "");
const TRUE_GREEN_EPOCH = Number(DATA.true_green_epoch || 1794761500);
const BAKED_EPOCH = Number(DATA.baked_epoch || 0);
const MIN_REAL_TS = 1700000000;
const VOCAB_BATCH_SIZE = 18;

function tryLockPortrait() {
  try {
    if (screen && screen.orientation && typeof screen.orientation.lock === "function") {
      screen.orientation.lock("portrait").catch(() => {});
    }
  } catch (e) {}
}
tryLockPortrait();
document.addEventListener("pointerdown", tryLockPortrait, { once: true, passive: true });
document.addEventListener("touchstart", tryLockPortrait, { once: true, passive: true });

// Portrait guard: if the phone still auto-rotates to landscape (system lock unsupported in this launch mode),
// counter-rotate the whole app so it stays upright relative to the phone, like a real portrait-only app.
let FP_ANGLE = 0;
function currentScreenAngle() {
  try {
    if (screen && screen.orientation && typeof screen.orientation.angle === "number") return screen.orientation.angle;
  } catch (e) {}
  if (typeof window.orientation === "number") return (window.orientation + 360) % 360;
  return -1;
}
function applyPortraitGuard() {
  const root = document.documentElement;
  const w = window.innerWidth || 0;
  const h = window.innerHeight || 0;
  const sw = (screen && screen.width) || w;
  const sh = (screen && screen.height) || h;
  const phone = Math.min(sw, sh) < 600;
  const ang = currentScreenAngle();
  let a = 0;
  if (phone && w > h && (ang === 90 || ang === 270 || ang === -1)) a = ang === 270 ? 270 : 90;
  FP_ANGLE = a;
  root.classList.toggle("fp", a !== 0);
  root.classList.toggle("fp-90", a === 90);
  root.classList.toggle("fp-270", a === 270);
  if (a && root.style && root.style.setProperty) {
    root.style.setProperty("--fp-w", w + "px");
    root.style.setProperty("--fp-h", h + "px");
  }
}
function fpXY(cx, cy) {
  if (FP_ANGLE === 90) return { x: window.innerHeight - cy, y: cx };
  if (FP_ANGLE === 270) return { x: cy, y: window.innerWidth - cx };
  return { x: cx, y: cy };
}
function fpX(p) { return fpXY(p.clientX, p.clientY).x; }
function fpY(p) { return fpXY(p.clientX, p.clientY).y; }
applyPortraitGuard();
window.addEventListener("resize", applyPortraitGuard);
window.addEventListener("orientationchange", () => { tryLockPortrait(); setTimeout(applyPortraitGuard, 60); });
try {
  if (screen && screen.orientation && screen.orientation.addEventListener) {
    screen.orientation.addEventListener("change", () => { tryLockPortrait(); applyPortraitGuard(); });
  }
} catch (e) {}

let expSpeed = parseFloat(localStorage.getItem("n3_exp_speed") || "1.0");
if (!SPEEDS.includes(expSpeed)) expSpeed = 1.0;
let radioSpeed = parseFloat(localStorage.getItem("n3_radio_speed") || "1.0");
if (!RADIO_SPEEDS.includes(radioSpeed)) radioSpeed = 1.0;

let activeKind = null;
let activeMode = "tutor";
let prevNonDashMode = "tutor";

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
    const radioIdle = (typeof radioPlayer === "undefined") || radioPlayer.paused;
    if (!activeKind && radioIdle) location.reload();
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
    radioSig: RADIO_SIG,
    flashProg: [0, 0, 0, 0],
    vocabSess: null,
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
  const minTs = Math.max(MIN_REAL_TS, rAt + 1);
  DATA.points.forEach(p => {
    const ps = st.pts[p.id];
    if (!ps) return;
    ps.greenAt = Math.floor(ps.greenAt || 0);
    ps.retestAt = Math.floor(ps.retestAt || 0);
    if (ps.greenAt < MIN_REAL_TS) ps.greenAt = 0;
    if (ps.retestAt < MIN_REAL_TS) ps.retestAt = 0;
    ps.wrongCount = Math.floor(ps.wrongCount || 0);
    ps.variantIdx = Math.floor(ps.variantIdx || 0);
    if (ps.greenAt >= minTs && ps.greenAt >= ps.retestAt) {
      ps.status = "green";
    } else if (ps.retestAt >= minTs || ps.wrongCount > 0 || ps.audioPrimed) {
      ps.status = "learning";
      if (ps.wrongCount > 0 && p.variants && p.variants.length > 0) {
        ps.useVariant = true;
      }
    } else {
      ps.status = "unseen";
    }
  });
}

// Seed from repo cloud_state_snapshot + union-merge ALL historical localStorage keys (v5..v13)
function loadAdaptiveState() {
  const base = createFreshAdaptiveState();

  // 1. Seed from cloud_state_snapshot.json / practice_log.jsonl baked into DATA.cloud_sync
  try {
    const cs = DATA.cloud_sync || {};
    const sd = cs.seeded_day || {};
    if (typeof sd.resetAt === "number" && sd.resetAt > base.resetAt) base.resetAt = Math.floor(sd.resetAt);
    if (typeof sd.radioMaxSec === "number" && sd.radioMaxSec > base.radioMaxSec) base.radioMaxSec = Math.floor(sd.radioMaxSec);
    if ((!RADIO_SIG || String(sd.radioSig || "") === RADIO_SIG) && Array.isArray(sd.radioPos) && sd.radioPos.length === 2 && (sd.radioPos[1] || 0) > (base.radioPos[1] || 0)) {
      base.radioPos = [Math.floor(sd.radioPos[0] || 0), Math.floor(sd.radioPos[1] || 0)];
    }
    const gMap = sd.greenAt || {};
    Object.keys(gMap).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      const gts = Math.floor(gMap[rawId] || 0);
      if (base.pts[pid] && gts >= MIN_REAL_TS) base.pts[pid].greenAt = Math.max(base.pts[pid].greenAt, gts);
    });
    const tMap = sd.retestAt || {};
    Object.keys(tMap).forEach(rawId => {
      const pid = CARD_TO_POINT_ID[rawId] || rawId;
      const tts = Math.floor(tMap[rawId] || 0);
      if (base.pts[pid] && tts >= MIN_REAL_TS) base.pts[pid].retestAt = Math.max(base.pts[pid].retestAt, tts);
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
        const mts = Math.floor(v[1] || 0);
        if (mts >= TRUE_GREEN_EPOCH) {
          base.masteryOverrides[mk] = String(v[0]);
          base.masteryOverrideTs[mk] = mts;
        }
      }
    });
  } catch (e) {}

  // 2. Union-merge all local browser keys (n3_session_v5..v6, n3_adaptive_v7..v13)
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
        if (saved.vocabSess && saved.vocabSess.date === DATA.plan_date && Array.isArray(saved.vocabSess.queue)) {
          if (!base.vocabSess || (saved.vocabSess.updatedAt || 0) >= (base.vocabSess.updatedAt || 0)) {
            base.vocabSess = saved.vocabSess;
          }
        }
        if (Array.isArray(saved.tappedWords)) {
          saved.tappedWords.forEach(w => {
            const ws = String(w || "").trim();
            if (ws && !base.tappedWords.includes(ws)) base.tappedWords.push(ws);
          });
        }
        if (typeof saved.radioMaxSec === "number" && saved.radioMaxSec > base.radioMaxSec) {
          base.radioMaxSec = Math.floor(saved.radioMaxSec);
        }
        if ((!RADIO_SIG || String(saved.radioSig || "") === RADIO_SIG) && Array.isArray(saved.radioPos) && saved.radioPos.length === 2 && (saved.radioPos[1] || 0) > (base.radioPos[1] || 0)) {
          base.radioPos = [Math.floor(saved.radioPos[0] || 0), Math.floor(saved.radioPos[1] || 0)];
        }
        if (saved.masteryOverrides && typeof saved.masteryOverrides === "object") {
          const tsObj = saved.masteryOverrideTs || {};
          Object.keys(saved.masteryOverrides).forEach(mk => {
            const val = saved.masteryOverrides[mk];
            const mts = Math.floor(tsObj[mk] || 0);
            if (mts >= TRUE_GREEN_EPOCH && mts >= (base.masteryOverrideTs[mk] || 0)) {
              base.masteryOverrides[mk] = String(val);
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
            if (typeof sp.greenAt === "number" && sp.greenAt >= MIN_REAL_TS && sp.greenAt > cur.greenAt) {
              cur.greenAt = Math.floor(sp.greenAt);
            }
            if (typeof sp.retestAt === "number" && sp.retestAt >= MIN_REAL_TS && sp.retestAt > cur.retestAt) {
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
      } catch (innerErr) {}
    });

    const legacyRadioPos = parseFloat(localStorage.getItem(LEGACY_RADIO_POS_KEY) || "0");
    const savedRadioPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    if (legacyRadioPos > base.radioMaxSec) base.radioMaxSec = Math.floor(legacyRadioPos);
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

// ================= TWO-LAYER HONEST MASTERY ENGINE (3 DISTINCT DAYS = TRUE GREEN) =================
const BASE_MSTATE_MAP = {};
Object.keys(DATA.mastery || {}).forEach(mod => {
  (DATA.mastery[mod].items || []).forEach(it => {
    const initMs = it.mstate || (it.tier === "done" ? "done" : (it.tier === "wip" ? "wip1" : "todo"));
    if (it.key) BASE_MSTATE_MAP[it.key] = initMs;
    if (it.name && !BASE_MSTATE_MAP[it.name]) BASE_MSTATE_MAP[it.name] = initMs;
  });
});

function parseMasteryState(raw) {
  const s = String(raw || "todo").trim();
  if (s === "done") return { mstate: "done", tier: "done", streak: 3, lastDate: "" };
  if (s === "wip0") return { mstate: "wip0", tier: "wip", streak: 0, lastDate: "" };
  const parts = s.split(":");
  const head = parts[0];
  const dt = parts[1] || "";
  if (head === "wip2") return { mstate: dt ? `wip2:${dt}` : "wip2", tier: "wip", streak: 2, lastDate: dt };
  if (head === "wip1" || head === "wip") return { mstate: dt ? `wip1:${dt}` : "wip1", tier: "wip", streak: 1, lastDate: dt };
  return { mstate: dt ? `todo:${dt}` : "todo", tier: "todo", streak: 0, lastDate: dt };
}

function getEffectiveMastery(key, altKey) {
  const ov = A.masteryOverrides || {};
  const ts = A.masteryOverrideTs || {};
  const k1 = key || "";
  const k2 = altKey || "";
  let raw = "";
  if (k1 && ov[k1] && k2 && ov[k2]) {
    raw = (ts[k1] || 0) >= (ts[k2] || 0) ? ov[k1] : ov[k2];
  } else if (k1 && ov[k1]) {
    raw = ov[k1];
  } else if (k2 && ov[k2]) {
    raw = ov[k2];
  } else {
    raw = BASE_MSTATE_MAP[k1] || BASE_MSTATE_MAP[k2] || "todo";
  }
  return parseMasteryState(raw);
}

function computeNextMasteryState(curObj, action, dayTag) {
  const d = dayTag || TODAY_TAG;
  if (action === "seal") return "done";
  if (action === "fail") return `todo:${d}`;
  if (curObj.tier === "done") return "done";
  if (action === "recover" || curObj.mstate === `todo:${d}`) {
    return `wip1:${d}`;
  }
  if (curObj.lastDate === d && curObj.streak >= 1) {
    return curObj.mstate;
  }
  const nextStreak = Math.min(3, (curObj.streak || 0) + 1);
  if (nextStreak >= 3) return "done";
  if (nextStreak === 2) return `wip2:${d}`;
  return `wip1:${d}`;
}

function setMasteryTier(key, mstateStr, tsSec) {
  if (!key) return;
  const ts = Math.max(TRUE_GREEN_EPOCH, Math.floor(tsSec || nowUnixSec()));
  if (ts >= (A.masteryOverrideTs[key] || 0)) {
    A.masteryOverrides[key] = String(mstateStr);
    A.masteryOverrideTs[key] = ts;
  }
}

function applyMasteryAction(key, altKey, action, tsSec) {
  const curObj = getEffectiveMastery(key, altKey);
  const nextMs = computeNextMasteryState(curObj, action, TODAY_TAG);
  const stamp = Math.max(TRUE_GREEN_EPOCH, Math.floor(tsSec || nowUnixSec()));
  if (key) setMasteryTier(key, nextMs, stamp);
  if (altKey && altKey !== key) setMasteryTier(altKey, nextMs, stamp);
  return nextMs;
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

function enrollDynamicVocabItem(w, defaultState) {
  if (!w || KNOWN_MASTERY_KEYS.has(w) || SKIP_ENROLL_WORDS.has(w)) return;
  const info = DATA.words && DATA.words[w];
  if (!info || !info.zh) return;
  KNOWN_MASTERY_KEYS.add(w);
  const initRaw = defaultState || "todo";
  if (!BASE_MSTATE_MAP[w]) BASE_MSTATE_MAP[w] = "todo";
  const parsed = parseMasteryState(initRaw);
  if (DATA.mastery && DATA.mastery.vocab && Array.isArray(DATA.mastery.vocab.items)) {
    const tipParts = [];
    if (info.head && info.head !== w) tipParts.push(`原形 ${info.head}`);
    if (info.tip) tipParts.push(info.tip);
    DATA.mastery.vocab.items.unshift({
      key: w,
      name: w,
      sub: info.zh,
      family: "今日查词",
      tier: parsed.tier,
      mstate: parsed.mstate,
      streak: parsed.streak,
      point_id: "",
      audio: info.audio || "",
      note: tipParts.join(" · ")
    });
  }
}

function applyMasteryOverrides() {
  DATA.points.forEach(p => {
    const ps = A.pts[p.id];
    if (ps && (ps.retestAt || 0) >= TRUE_GREEN_EPOCH && (ps.retestAt || 0) > (A.resetAt || 0) && (ps.retestAt || 0) > (ps.greenAt || 0)) {
      setMasteryTier(p.point_key, `todo:${TODAY_TAG}`, ps.retestAt);
      setMasteryTier(p.point, `todo:${TODAY_TAG}`, ps.retestAt);
    }
  });
  const ov = A.masteryOverrides || {};
  (A.tappedWords || []).forEach(w => enrollDynamicVocabItem(w, ov[w] || "todo"));
  Object.keys(ov).forEach(k => enrollDynamicVocabItem(k, ov[k]));
  Object.keys(DATA.mastery).forEach(mod => {
    const c = { todo: 0, wip: 0, done: 0, total: 0 };
    DATA.mastery[mod].items.forEach(it => {
      const eff = getEffectiveMastery(it.key, it.name);
      it.mstate = eff.mstate;
      it.tier = eff.tier;
      it.streak = eff.streak;
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
const CLOUD_BYTE_LIMIT = 3750;
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
    const rawG = Math.floor(ps.greenAt || 0), rawR = Math.floor(ps.retestAt || 0);
    const g = rawG >= MIN_REAL_TS ? rawG : 0;
    const r = rawR >= MIN_REAL_TS ? rawR : 0;
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
    v: 15,
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
  if (RADIO_SIG && Array.isArray(A.radioPos) && (A.radioPos[1] || 0) > 0) {
    pkt.rsig = A.radioSig || RADIO_SIG;
  }
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
  const deltaFloor = Math.max(TRUE_GREEN_EPOCH, BAKED_EPOCH > 0 ? BAKED_EPOCH - 7200 : 0);
  const ovEntries = Object.keys(A.masteryOverrides || {})
    .map(k => [k, [String(A.masteryOverrides[k]), Math.floor((A.masteryOverrideTs && A.masteryOverrideTs[k]) || 0)]])
    .filter(kv => kv[1][1] >= TRUE_GREEN_EPOCH)
    .sort((x, y) => {
      const xd = x[1][1] >= deltaFloor ? 1 : 0;
      const yd = y[1][1] >= deltaFloor ? 1 : 0;
      if (xd !== yd) return yd - xd;
      return y[1][1] - x[1][1];
    });
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
    rsig: pkt.rsig || "",
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
  const pktVer = Math.floor(pkt.v || 0);
  try {
    if (pktVer >= 14 && pkt.o && typeof pkt.o === "object") {
      Object.keys(pkt.o).forEach(mk => {
        const v = pkt.o[mk];
        if (Array.isArray(v) && v.length === 2) {
          const tier = String(v[0]);
          const ts = Math.floor(v[1] || 0);
          if (ts < TRUE_GREEN_EPOCH) return;
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

    if (pktVer >= 14 && Array.isArray(pkt.fp) && mergeFlashProgTuple(A, pkt.fp)) {
      changed = true;
    }

    if ((!RADIO_SIG || String(pkt.rsig || "") === RADIO_SIG) && Array.isArray(pkt.rp) && pkt.rp.length === 2) {
      const rpSec = Math.floor(pkt.rp[0] || 0);
      const rpTs = Math.floor(pkt.rp[1] || 0);
      const myTs = (A.radioPos && A.radioPos[1]) || 0;
      if (rpTs > myTs || (rpTs === myTs && rpSec > ((A.radioPos && A.radioPos[0]) || 0))) {
        A.radioPos = [rpSec, rpTs];
        A.radioSig = RADIO_SIG;
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
        if (e.g >= MIN_REAL_TS && e.g > (ps.greenAt || 0)) { ps.greenAt = e.g; ptsChanged = true; }
        if (e.r >= MIN_REAL_TS && e.r > (ps.retestAt || 0)) { ps.retestAt = e.r; ptsChanged = true; }
        if (applySchedTuple(ps, e.s, A.resetAt)) ptsChanged = true;
      });
    } else {
      const gIn = pkt.g || {};
      Object.keys(gIn).forEach(rawId => {
        const pid = CARD_TO_POINT_ID[rawId] || rawId;
        const ts = Math.floor(gIn[rawId] || 0);
        if (A.pts[pid] && ts >= MIN_REAL_TS && ts > (A.pts[pid].greenAt || 0)) { A.pts[pid].greenAt = ts; ptsChanged = true; }
      });
      const tIn = pkt.t || {};
      Object.keys(tIn).forEach(rawId => {
        const pid = CARD_TO_POINT_ID[rawId] || rawId;
        const ts = Math.floor(tIn[rawId] || 0);
        if (A.pts[pid] && ts >= MIN_REAL_TS && ts > (A.pts[pid].retestAt || 0)) { A.pts[pid].retestAt = ts; ptsChanged = true; }
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
      if (typeof refreshMarkedWordTokens === "function") refreshMarkedWordTokens();
      if (activeMode === "tutor") {
        if (shownChanged || viewStage !== "result") renderTutor();
      } else if (activeMode === "dash") {
        renderDashboard();
      } else if (activeMode === "vocab" && typeof onRemoteVocabSync === "function") {
        onRemoteVocabSync();
      }
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
    el.textContent = "多端实时自动同步：已连接（手机与电脑秒级对齐）";
  } else if (cloudSyncState === "synced") {
    el.textContent = "多端自动同步：已对齐最新进度";
  } else if (cloudSyncState === "offline") {
    el.textContent = "当前离线：进度已存本机，联网后自动同步";
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
  const defaultTarget = Math.min(VOCAB_BATCH_SIZE, Math.max(1, liveFlashLeft || VOCAB_BATCH_SIZE));
  const fp = Array.isArray(A.flashProg) ? A.flashProg : [0, 0, 0, 0];
  const sessCleared = (A.vocabSess && A.vocabSess.date === DATA.plan_date) ? Math.floor(A.vocabSess.cleared || 0) : 0;
  const sessTotal = (A.vocabSess && A.vocabSess.date === DATA.plan_date) ? Math.floor(A.vocabSess.total || 0) : 0;
  const flashSeen = Math.max(0, Math.floor(fp[0] || 0), sessCleared);
  const flashDone = (Math.floor(fp[2] || 0) > 0) || !!(A.vocabSess && A.vocabSess.done) || (liveFlashLeft === 0 && vItems.length > 0);
  const flashTarget = flashDone
    ? Math.max(flashSeen, sessTotal || Math.floor(fp[1] || 0) || defaultTarget)
    : Math.max(flashSeen, sessTotal || Math.floor(fp[1] || 0) || defaultTarget);
  const flashRatio = flashDone ? 1.0 : (flashSeen > 0 ? Math.min(0.96, flashSeen / Math.max(1, flashTarget)) : 0);

  const vDone = vItems.filter(it => it.tier === "done").length;
  const vWip = vItems.filter(it => it.tier === "wip").length;
  const baseDone = Number(DATA.vocab_base_done || 10);
  const vocabBonus = Math.min(8, Math.max(0, (vDone - baseDone) * 0.28 + Math.max(0, vWip - 35) * 0.06));

  // Combined 3-ritual daily completion: 50% quiz + 32% podcast + 18% vocab swipe
  const dailyLockPct = Math.min(100, Math.round((quizRatio * 0.50 + radioRatio * 0.32 + flashRatio * 0.18) * 100));

  // Projected JLPT N3 score (/180): 108 base + 12 quiz + 8 podcast + 4 nightly vocab + cross-day vocab mastery lift
  const projScore = Math.min(165, Math.round(108 + quizRatio * 12 + (radioDone ? 8 : radioRatio * 8) + flashRatio * 4 + vocabBonus));

  return {
    totalCards,
    greenCnt,
    quizRatio,
    quizDone,
    targetMins,
    listenedMins: radioDone ? targetMins : listenedMins,
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
const TRIVIAL_TAP_WORDS = new Set([
  "この", "その", "あの", "ここ", "そこ", "あそこ", "これ", "それ", "あれ", "どれ", "どちら",
  "私", "僕", "彼", "彼女", "人", "今日", "明日", "昨日", "今", "もう", "また", "もっと", "だけ", "だから"
]);

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

function isWordMarkedForReading(surface) {
  if (!surface || PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return false;
  const inTapped = Array.isArray(A.tappedWords) && A.tappedWords.includes(surface);
  const inFailed = !!(A.vocabSess && Array.isArray(A.vocabSess.failedWords) && A.vocabSess.failedWords.includes(surface));
  if (!inTapped && !inFailed) return false;
  let mKey = surface;
  const vItems = (DATA.mastery && DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  for (let i = 0; i < vItems.length; i++) {
    if (vItems[i].name === surface || vItems[i].key === surface) {
      mKey = vItems[i].key || surface;
      break;
    }
  }
  return getEffectiveMastery(mKey, surface).tier !== "done";
}

function refreshMarkedWordTokens() {
  if (typeof document === "undefined") return;
  document.querySelectorAll(".w-tok[data-w]").forEach(el => {
    const w = el.dataset.w || "";
    el.classList.toggle("marked-tok", isWordMarkedForReading(w));
  });
}

function renderTrapKanaHTML(surface, kana, trapHl, trapTag) {
  const kStr = String(kana || "").trim();
  if (!kStr) return "";
  const hasKanji = /[\u4e00-\u9faf\u3400-\u4dbf]/.test(String(surface || ""));
  if (!hasKanji) {
    return kStr !== surface ? escapeHtml(kStr) : "";
  }
  const hlArr = (Array.isArray(trapHl) ? trapHl : []).map(x => String(x || "")).filter(Boolean);
  const mask = new Array(kStr.length).fill(false);
  let pos = 0;
  for (let i = 0; i < hlArr.length; i++) {
    const sub = hlArr[i];
    let idx = kStr.indexOf(sub, pos);
    if (idx < 0) idx = kStr.indexOf(sub, 0);
    if (idx >= 0) {
      for (let j = idx; j < idx + sub.length; j++) mask[j] = true;
      pos = idx + sub.length;
    }
  }
  let html = "";
  let idx = 0;
  while (idx < kStr.length) {
    const flag = mask[idx];
    let end = idx + 1;
    while (end < kStr.length && mask[end] === flag) end++;
    const seg = escapeHtml(kStr.slice(idx, end));
    html += flag ? `<b class="kana-trap">${seg}</b>` : seg;
    idx = end;
  }
  const tag = String(trapTag || "").trim();
  if (tag) {
    html += `<span class="kana-tag">· ${escapeHtml(tag)}</span>`;
  }
  return html;
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
      const mkCls = isWordMarkedForReading(matched) ? " marked-tok" : "";
      out += `<span class="w-tok${mkCls}" data-w="${escW}">${innerHtml}</span>`;
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

const audioBlobMap = new Map();
const audioFetchMap = new Map();
let playReqSeq = 0;

function warmAudio(url) {
  if (!url) return Promise.resolve("");
  if (audioBlobMap.has(url)) return Promise.resolve(audioBlobMap.get(url));
  if (audioFetchMap.has(url)) return audioFetchMap.get(url);
  const p = fetch(url)
    .then(res => (res && res.ok ? res.blob() : null))
    .then(blob => {
      audioFetchMap.delete(url);
      if (!blob || !blob.size) return url;
      if (audioBlobMap.size >= 80) {
        const oldestKey = audioBlobMap.keys().next().value;
        const oldestUrl = audioBlobMap.get(oldestKey);
        audioBlobMap.delete(oldestKey);
        try { URL.revokeObjectURL(oldestUrl); } catch (e) {}
      }
      const blobUrl = URL.createObjectURL(blob);
      audioBlobMap.set(url, blobUrl);
      return blobUrl;
    })
    .catch(() => {
      audioFetchMap.delete(url);
      return url;
    });
  audioFetchMap.set(url, p);
  return p;
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
  playReqSeq += 1;
  try {
    player.pause();
    player.currentTime = 0;
    wordPlayer.pause();
  } catch (e) {}
  activeKind = null;
  syncAudioButtons();
}

function startResolvedClip(srcUrl, kind, seq) {
  if (seq !== playReqSeq) return;
  activeKind = kind;
  player.src = srcUrl;
  player.currentTime = 0;
  applyPlaybackRate(kind);
  const pr = player.play();
  if (pr && typeof pr.catch === "function") {
    pr.catch(() => {
      if (seq === playReqSeq) {
        activeKind = null;
        syncAudioButtons();
      }
    });
  }
  syncAudioButtons();
}

function playMainClip(url, kind, toggleIfSame) {
  if (!url) return;
  if (!radioPlayer.paused) radioPlayer.pause();
  if (toggleIfSame && activeKind === kind && !player.paused) {
    stopQuizAudio();
    return;
  }
  const seq = ++playReqSeq;
  if (audioBlobMap.has(url)) {
    startResolvedClip(audioBlobMap.get(url), kind, seq);
    return;
  }
  activeKind = kind;
  syncAudioButtons();
  warmAudio(url).then(resolvedUrl => {
    startResolvedClip(resolvedUrl || url, kind, seq);
  });
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
  const onExp = (activeKind === "exp" || activeKind === "teach") && !player.paused;
  const repBtn = document.getElementById("exp-replay-btn");
  if (repBtn) {
    repBtn.classList.toggle("playing", onExp);
    repBtn.textContent = onExp ? "暂停" : "讲解";
  }
  const dockRepBtn = document.getElementById("dock-exp-btn");
  if (dockRepBtn) {
    dockRepBtn.classList.toggle("playing", onExp);
    dockRepBtn.textContent = onExp ? "暂停" : "讲解";
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

function paintRadioSeekProgress(t) {
  const seekEl = document.getElementById("radio-seek");
  const pillEl = document.getElementById("radio-date-pill");
  const dur = Math.max(1, (radioPlayer.duration && isFinite(radioPlayer.duration)) ? radioPlayer.duration : (DATA.radio.duration_sec || 2100));
  const rm = computeDaily120Metrics();
  if (pillEl) {
    const hostsLabel = DATA.radio.hosts || "文涛 · 文道 · 子东";
    pillEl.textContent = rm.radioDone ? `锵锵三人 · ${hostsLabel} · 今日已听完 ✓` : `锵锵三人 · ${hostsLabel}`;
  }
  if (seekEl) {
    const curPct = Math.max(0, Math.min(100, ((t || 0) / dur) * 100));
    const maxPct = rm.radioDone ? 100 : Math.max(curPct, Math.min(100, ((A.radioMaxSec || 0) / dur) * 100));
    seekEl.style.background = `linear-gradient(to right, #2D7A56 0%, #2D7A56 ${curPct.toFixed(1)}%, rgba(45, 122, 86, 0.36) ${curPct.toFixed(1)}%, rgba(45, 122, 86, 0.36) ${maxPct.toFixed(1)}%, rgba(28, 27, 24, 0.10) ${maxPct.toFixed(1)}%, rgba(28, 27, 24, 0.10) 100%)`;
  }
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
    document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
    const seekEl = document.getElementById("radio-seek");
    seekEl.max = Math.ceil(DATA.radio.duration_sec || 2100);
    document.getElementById("radio-tot-time").textContent = formatMMSS(DATA.radio.duration_sec || 2100);
    renderRadioChapters(0);
    updateRadioLiveDisplay(radioPlayer.currentTime || savedPos || 0);
  } else {
    paintRadioSeekProgress(radioPlayer.currentTime || 0);
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
  A.radioSig = RADIO_SIG;
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
    <button class="chap-link ${c.idx === activeChapIdx ? 'active' : ''}" onclick="jumpRadioChapter(${c.start})">${escapeHtml(c.title.replace(/^[①②③④⑤⑥]\s*/, ""))}</button>
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
      if (!radioPlayer.paused) {
        A.radioPos = [Math.floor(t), nowUnixSec()];
        A.radioSig = RADIO_SIG;
      }
      saveAdaptiveState();
      renderGreenBoard();
      if (Date.now() - lastRadioCloudPushMs > 55000) {
        lastRadioCloudPushMs = Date.now();
        scheduleCloudPush(400);
      }
    }
  }
  paintRadioSeekProgress(t);

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
        document.getElementById("radio-chap-lbl").textContent = chapObj.title.replace(/^[①②③④⑤⑥]\s*/, "");
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
  const bTabBtn = document.getElementById("btab-radio");
  if (bTabBtn) bTabBtn.classList.toggle("is-playing", playing);
}

radioPlayer.addEventListener("play", syncRadioUI);
radioPlayer.addEventListener("pause", () => {
  syncRadioUI();
  const t = Math.floor(radioPlayer.currentTime || 0);
  if (t > 2) {
    A.radioPos = [t, nowUnixSec()];
    A.radioSig = RADIO_SIG;
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
  A.radioSig = RADIO_SIG;
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
    A.radioSig = RADIO_SIG;
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
  const tsSec = Math.max(TRUE_GREEN_EPOCH, Math.floor(stampSec || nowUnixSec()));
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
  const nextMs = applyMasteryAction(p.point_key, p.point, "fail", stamp);
  syncBackendRecord(p, activeQuizObj.id, "不确定", false, false, nextMs, stamp);

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
  const hadWrongToday = (ps.wrongCount || 0) > 0 || ((ps.retestAt || 0) > (A.resetAt || 0));

  if (isCorrect) {
    ps.greenAt = Math.max(stamp, (ps.retestAt || 0), (A.resetAt || 0) + 1);
    ps.status = "green";
    A.hotFamily = null;
    A.step += 1;
    A.lastPointId = p.id;
    recomputeStatusesFromCRDT(A);
    const nextMs = applyMasteryAction(p.point_key, p.point, hadWrongToday ? "recover" : "pass", ps.greenAt);
    syncBackendRecord(p, activeQuizObj.id, val, true, false, nextMs, ps.greenAt);
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
    const nextMs = applyMasteryAction(p.point_key, p.point, "fail", ps.retestAt);
    syncBackendRecord(p, activeQuizObj.id, val, false, false, nextMs, ps.retestAt);
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
    if (p) {
      const nextMs = applyMasteryAction(p.point_key, p.point, "fail", ps.retestAt);
      syncBackendRecord(p, p.id, pickedVal, false, true, nextMs, ps.retestAt);
    }
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
  const keepVocabSess = A.vocabSess || null;
  const keepSt = A.st || 0;
  A = createFreshAdaptiveState();
  A.resetAt = stamp;
  A.masteryOverrides = keepOverrides;
  A.masteryOverrideTs = keepOverrideTs;
  A.tappedWords = keepTapped;
  A.radioMaxSec = keepRadio;
  A.radioPos = keepRadioPos;
  A.flashProg = keepFlashProg;
  A.vocabSess = keepVocabSess;
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

let prevEnsoDoneKey = "";

function renderEnsoRingSVG(idx, ratio, isDone) {
  if (isDone) {
    return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="14" cy="14" r="10.2" fill="#2D7A56"/>
      <path d="M 9.6 14.3 L 12.6 17.2 L 18.7 10.9" fill="none" stroke="#FCFBF8" stroke-width="2.15" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
  }
  if (ratio > 0.005) {
    const pct = Math.max(8, Math.min(97, Math.round(ratio * 100)));
    return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="14" cy="14" r="9.8" fill="none" stroke="rgba(28, 27, 24, 0.13)" stroke-width="1.85"/>
      <circle cx="14" cy="14" r="9.8" pathLength="100" fill="none" stroke="#2D7A56" stroke-width="2.35" stroke-linecap="round" stroke-dasharray="${pct} 105" transform="rotate(-90 14 14)"/>
    </svg>`;
  }
  return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
    <circle cx="14" cy="14" r="9.8" fill="none" stroke="rgba(28, 27, 24, 0.20)" stroke-width="1.6" stroke-dasharray="3.6 3.2"/>
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
    if (activeMode !== "vocab") switchMode("vocab");
    else openSessionModal();
  }
}

function toggleDashLedger(ev) {
  if (ev) ev.stopPropagation();
  if (activeMode === "dash") {
    switchMode(prevNonDashMode || "tutor");
  } else {
    switchMode("dash");
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
      { ratio: m.flashRatio, done: m.flashDone, label: `记词 ${m.flashDone ? "已完成" : m.flashSeen + "/" + m.flashTarget}` }
    ];
    trioEl.innerHTML = rings.map((r, idx) => {
      const newlyDone = r.done && prevEnsoDoneKey && prevEnsoDoneKey[idx] === "0";
      return `<button class="enso-btn${r.done ? " done" : ""}${newlyDone ? " is-done" : ""}" id="enso-${idx + 1}" onclick="onEnsoTap(${idx}, event)" aria-label="${escapeHtml(r.label)}" title="${escapeHtml(r.label)}">${renderEnsoRingSVG(idx, r.ratio, r.done)}</button>`;
    }).join("");
    prevEnsoDoneKey = doneKey;
  }

  const quizPart = m.quizDone ? `做题 ✓` : `做题 ${m.greenCnt}/${m.totalCards}`;
  const radioPart = m.radioDone ? `随身听 ✓` : `听 ${m.listenedMins}/${m.targetMins}分`;
  const flashPart = m.flashDone ? `记词 ✓` : `记词 ${m.flashSeen}/${m.flashTarget}`;
  document.getElementById("gm-left-txt").textContent = `${quizPart} · ${radioPart} · ${flashPart}`;

  const rightEl = document.getElementById("gm-right-txt");
  if (rightEl) {
    const ledgerTxt = activeMode === "dash" ? "收起总表" : "总表";
    rightEl.classList.toggle("active-ledger", activeMode === "dash");
    if (m.projScore >= 120) {
      rightEl.innerHTML = `预计 <b class="moss">${m.projScore}分</b><span class="ledger-sep"> · </span><span class="ledger-tag">${ledgerTxt}</span>`;
    } else {
      rightEl.innerHTML = `预计 <b>${m.projScore}分</b><span class="ledger-sep"> · </span><span class="ledger-tag">${ledgerTxt}</span>`;
    }
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
  box.style.transform = "";
  box.style.opacity = "";

  if (viewStage === "done" || !curPointId) {
    const m = computeDaily120Metrics();
    const nextBtn = !m.radioDone
      ? `<button class="sumi-btn" onclick="switchMode('radio', true)">去听随身听 →</button>`
      : (!m.flashDone
          ? `<button class="sumi-btn" onclick="switchMode('vocab')">去单手记词 →</button>`
          : `<button class="sumi-btn" onclick="switchMode('dash')">查看总表 →</button>`);
    box.innerHTML = `
      <div class="meta-bar"><span class="overline ok">${m.allThreeDone ? "今日三修圆满 · 稳过 120 分" : "今日五十道题已全部过关"}</span></div>
      <div class="focal-space">
        <h2 class="point-heading">${m.allThreeDone ? "今日三样皆已圆满" : "五十道题已全部过关"}</h2>
        <p class="logic-line">${m.allThreeDone
          ? `做题、三人随身听与单手记词皆已收笔，预计总分稳锁在 ${m.projScore} 分。安心休息，考场稳站 120 分以上。`
          : `做题部分已拿满，当前预计 ${m.projScore} 分。${!m.radioDone ? "顺手听完今日随身听，" : ""}再去记词滑完今晚生词，就能把三枚圆印全部收满。`}</p>
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
      <div class="tutor-stamp right" id="tutor-st-right">开始做题 →</div>
      <div class="tutor-stamp left moss-tone" id="tutor-st-left">开始做题 →</div>
      <div class="meta-bar">
        <span class="overline warm">${escapeHtml(p.subject)} · 考点梳理</span>
        <div class="quiet-actions">
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
        <div class="dock-row">
          <button class="dock-replay-btn" id="dock-exp-btn" onclick="playMainClip('${p.teach.audio}', 'teach', true)">讲解</button>
          <button class="sumi-btn" onclick="completeTeachCard()"><span>开始做题 →</span><span class="desk-hint">滚轮下滑 · Enter</span></button>
        </div>
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
      </div>

      <div class="focal-space">
        <div class="quiz-focal">
          ${activeQuizObj.is_listening ? `
          <div class="listen-medallion-wrap">
            <button class="listen-medallion" id="voice-orb" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)" aria-label="播放">
              <svg class="med-ic" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>
              <div class="med-waves"><span></span><span></span><span></span></div>
            </button>
          </div>` : `<p class="quiz-ja" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)" title="轻点重听题目">${escapeHtml(activeQuizObj.prompt)}</p>`}
        </div>
      </div>

      <div class="action-dock">
        ${controlsHTML}
        <div class="quiz-aux-row">
          <button class="unsure-btn" onclick="revealWithoutGuess()">
            <span>不确定 · 直接看讲解</span>
            <span class="kbd-tag">0</span>
          </button>
          ${!activeQuizObj.is_listening ? `<button class="dock-replay-btn aux-read-btn" id="q-play-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">读题</button>` : ""}
        </div>
      </div>
    `;
    syncAudioButtons();
    return;
  }

  // -------- RESULT --------
  const q = activeQuizObj || p.primary;
  const isUnsure = pickedVal === "__UNSURE__";
  const isCorrect = !isUnsure && pickedVal === q.answer;
  const ansIdx = currentChoices.indexOf(q.answer) + 1;
  const pickedIdx = currentChoices.indexOf(pickedVal) + 1;
  const effM = getEffectiveMastery(p.point_key, p.point);
  const streakTxt = effM.streak >= 3 ? "满 3/3 已掌握" : `记忆 ${effM.streak}/3`;

  let overCls = "overline ng";
  let overTxt = "";
  if (isCorrect) {
    overCls = "overline ok";
    overTxt = q.is_listening && ansIdx > 0 ? `本题过关 · 正解 ${ansIdx} · ${streakTxt}` : `本题过关 · ${streakTxt}`;
  } else if (isUnsure) {
    overCls = "overline warm";
    overTxt = q.is_listening && ansIdx > 0 ? `未过关 · 正解 ${ansIdx} · 隔 3 题再考` : "未过关 · 隔 3 题再考";
  } else {
    overCls = "overline ng";
    overTxt = q.is_listening && ansIdx > 0
      ? `误选 ${pickedIdx || ""} · 正解 ${ansIdx} · 隔 3 题再考`
      : `误选「${pickedVal}」 · 隔 3 题再考`;
  }

  const notesMap = q.opt_notes || {};
  const orderedOpts = q.is_listening
    ? currentChoices.map((opt, idx) => ({ opt, num: idx + 1 }))
    : [
        { opt: q.answer, num: 0 },
        ...currentChoices
          .filter(o => o !== q.answer)
          .sort((a, b) => (a === pickedVal ? -1 : b === pickedVal ? 1 : 0))
          .map(opt => ({ opt, num: 0 }))
      ];

  const optRowsHTML = orderedOpts.map(({ opt, num }) => {
    const isAns = opt === q.answer;
    const isMis = !isAns && !isUnsure && opt === pickedVal;
    const rowCls = isAns ? "opt-row ok" : (isMis ? "opt-row ng" : "opt-row dim");
    const markTxt = q.is_listening
      ? (isAns ? `${num} ✓` : (isMis ? `${num} ✕` : `${num} ·`))
      : (isAns ? "✓" : (isMis ? "✕" : "×"));
    const badgeHTML = isAns
      ? `<span class="opt-badge ok">正解</span>`
      : (isMis ? `<span class="opt-badge ng">误选</span>` : "");
    const descTxt = notesMap[opt] || (isAns ? (q.form_line || "") : "");
    return `<div class="${rowCls}">
      <span class="opt-mark">${markTxt}</span>
      <div class="opt-body">
        <div class="opt-head"><span class="opt-ja">${annotateJapanese(opt)}</span>${badgeHTML}</div>
        ${descTxt ? `<div class="opt-desc">${escapeHtml(descTxt)}</div>` : ""}
      </div>
    </div>`;
  }).join("");

  const leftStampLabel = isCorrect ? "← 稍后再考" : "← 隔 3 题再考";
  const leftStampTone = isCorrect ? "" : " moss-tone";
  const rightStampLabel = isCorrect ? "下一题 →" : "隔 3 题再考 →";
  const mainBtnLabel = isCorrect ? "下一题 →" : "继续 →";

  box.innerHTML = `
    <div class="tutor-stamp right" id="tutor-st-right">${rightStampLabel}</div>
    <div class="tutor-stamp left${leftStampTone}" id="tutor-st-left">${leftStampLabel}</div>
    <div class="meta-bar">
      <span class="${overCls}">${escapeHtml(overTxt)}</span>
      <div class="quiet-actions">
        <button class="text-btn" onclick="playMainClip(activeQuizObj.q_audio, 'q', true)">原题</button>
        <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed}x</button>
      </div>
    </div>

    <div class="focal-space">
      ${(q.is_listening && renderDialogueHTML(q.full_ja, q.answer, q.zh_meaning)) || `<div class="result-ja">${annotateSentenceWithAnswer(q.full_ja, q.answer)}</div>
      ${q.zh_meaning ? `<p class="result-zh">${escapeHtml(q.zh_meaning)}</p>` : ""}`}
      <div class="result-divider"></div>
      ${q.why_line ? `<div class="res-cue"><span class="cue-tag">要点</span><span class="cue-txt">${escapeHtml(q.why_line)}</span></div>` : ""}
      <div class="opt-breakdown${q.is_listening ? " is-listen" : ""}">${optRowsHTML}</div>
    </div>

    <div class="action-dock">
      <div class="dock-row">
        <button class="dock-replay-btn" id="dock-exp-btn" onclick="playMainClip(activeQuizObj.exp_audio, 'exp', true)">讲解</button>
        ${isCorrect ? `<button class="ghost-btn" onclick="advanceNext(true)">← 再考</button>` : ""}
        <button class="sumi-btn" onclick="advanceNext(false)"><span>${mainBtnLabel}</span><span class="desk-hint">滚轮下滑 · Enter</span></button>
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
    u.rate = 1.0;
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

function recordTappedWord(surface) {
  if (!surface || PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return;
  const info = DATA.words[surface];
  if (!info || !info.zh) return;
  if (!Array.isArray(A.tappedWords)) A.tappedWords = [];
  let changed = false;
  if (!A.tappedWords.includes(surface)) {
    A.tappedWords.push(surface);
    if (A.tappedWords.length > 80) A.tappedWords = A.tappedWords.slice(-80);
    changed = true;
  }
  if (A.vocabSess && A.vocabSess.date === DATA.plan_date && Array.isArray(A.vocabSess.queue)) {
    const clearedArr = Array.isArray(A.vocabSess.clearedWords) ? A.vocabSess.clearedWords : [];
    if (!A.vocabSess.queue.includes(surface) && !clearedArr.includes(surface)) {
      const insPos = Math.min(1, A.vocabSess.queue.length);
      A.vocabSess.queue.splice(insPos, 0, surface);
      A.vocabSess.total = Math.max(A.vocabSess.queue.length + (A.vocabSess.cleared || 0), (A.vocabSess.total || 0) + 1);
      A.vocabSess.done = false;
      A.vocabSess.updatedAt = nowUnixSec();
      changed = true;
    }
  }
  if (changed) {
    applyMasteryOverrides();
    refreshMarkedWordTokens();
    renderGreenBoard();
    saveAdaptiveState();
    scheduleCloudPush(450);
  } else {
    refreshMarkedWordTokens();
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
  const kanaHtml = renderTrapKanaHTML(surface, info.kana || "", info.trap_hl, info.trap_tag);

  box.dataset.surface = surface;
  const surfEl = box.querySelector(".ilex-surf");
  const kanaEl = box.querySelector(".ilex-kana");
  const zhEl = box.querySelector(".ilex-zh");
  const metaEl = box.querySelector(".ilex-meta");
  if (surfEl) surfEl.textContent = surface;
  if (kanaEl) kanaEl.innerHTML = kanaHtml;
  if (zhEl) zhEl.textContent = info.zh || "";
  if (metaEl) metaEl.textContent = metaLine;
  box.classList.remove("empty");

  if (player.paused && radioPlayer.paused) {
    playWordAudio(surface, false);
  }
}

document.addEventListener("click", e => {
  if (activeMode === "vocab") return;
  const lexCard = e.target.closest && e.target.closest(".inline-lex");
  if (lexCard && !lexCard.classList.contains("empty")) {
    e.preventDefault();
    e.stopPropagation();
    if (lexCard.dataset.surface) playWordAudio(lexCard.dataset.surface, true);
    return;
  }
  const tok = e.target.closest && e.target.closest(".w-tok");
  if (tok && !(activeMode === "tutor" && viewStage === "quiz")) {
    e.preventDefault();
    e.stopPropagation();
    showInlineWordMeaning(tok.dataset.w, tok);
    return;
  }
  if (!lexCard) {
    const targetBoxId = activeMode === "radio" ? "radio-inline-lex" : "tutor-inline-lex";
    const box = document.getElementById(targetBoxId);
    if (box && !box.classList.contains("empty") && (e.target.closest(".focal-space") || e.target.closest(".radio-center"))) {
      clearActiveWordToken();
      clearInlineLexicon(targetBoxId);
    }
  }
});

// ================= DESKTOP MOUSE WHEEL & TINDER-STYLE RIGHT-HAND SWIPE ERGONOMICS =================
let lastWheelAdvanceAt = 0;
let tutorSwipeAnimating = false;

window.addEventListener("wheel", e => {
  if (activeMode !== "tutor" || tutorSwipeAnimating) return;
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

(function bindRightHandTouchErgonomics() {
  const tutorEl = document.getElementById("tutor-view");
  const dashEl = document.getElementById("dash-view");
  let sx = 0, sy = 0, st = 0;
  let axis = null; // null | "x" | "y"
  let tracking = false;

  function resetTutorDrag() {
    const card = document.getElementById("voice-card");
    if (card) {
      card.classList.remove("tutor-dragging");
      card.classList.add("tutor-settling");
      card.style.transform = "";
    }
    ["tutor-st-right", "tutor-st-left"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.opacity = "0";
    });
  }

  function flyTutorCard(dir, onDone) {
    const card = document.getElementById("voice-card");
    if (!card) { onDone(); return; }
    tutorSwipeAnimating = true;
    card.classList.remove("tutor-dragging", "tutor-settling");
    card.classList.add(dir === "right" ? "tutor-fly-right" : "tutor-fly-left");
    setTimeout(() => {
      tutorSwipeAnimating = false;
      onDone();
    }, 180);
  }

  tutorEl.addEventListener("touchstart", e => {
    if (tutorSwipeAnimating || activeMode !== "tutor") return;
    if (viewStage !== "result" && viewStage !== "teach") return;
    if (document.getElementById("app-modal").classList.contains("open")) return;
    if (!e.touches || e.touches.length !== 1) return;
    sx = fpX(e.touches[0]);
    sy = fpY(e.touches[0]);
    st = performance.now();
    axis = null;
    tracking = true;
  }, { passive: true });

  tutorEl.addEventListener("touchmove", e => {
    if (!tracking || !e.touches || e.touches.length !== 1) return;
    const dx = fpX(e.touches[0]) - sx;
    const dy = fpY(e.touches[0]) - sy;

    if (!axis) {
      if (Math.abs(dy) > 10 && Math.abs(dy) >= Math.abs(dx)) {
        axis = "y";
        tracking = false;
        return;
      }
      if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.18) {
        axis = "x";
        const card = document.getElementById("voice-card");
        if (card) {
          card.classList.remove("tutor-settling");
          card.classList.add("tutor-dragging");
        }
      } else {
        return;
      }
    }

    if (axis === "x") {
      if (e.cancelable) e.preventDefault();
      const card = document.getElementById("voice-card");
      if (card) {
        card.style.transform = `translate3d(${dx.toFixed(1)}px, ${(dy * 0.14).toFixed(1)}px, 0) rotate(${(dx * 0.026).toFixed(2)}deg)`;
      }
      const stR = document.getElementById("tutor-st-right");
      const stL = document.getElementById("tutor-st-left");
      if (dx > 16) {
        if (stR) stR.style.opacity = String(Math.min(1, (dx - 14) / 48));
        if (stL) stL.style.opacity = "0";
      } else if (dx < -16) {
        if (stL) stL.style.opacity = String(Math.min(1, (-dx - 14) / 48));
        if (stR) stR.style.opacity = "0";
      } else {
        if (stR) stR.style.opacity = "0";
        if (stL) stL.style.opacity = "0";
      }
    }
  }, { passive: false });

  function endTutorTouch(e, cancelled) {
    if (!tracking) return;
    tracking = false;
    if (cancelled || axis !== "x" || !e.changedTouches || !e.changedTouches.length) {
      if (axis === "x") resetTutorDrag();
      axis = null;
      return;
    }
    const dx = fpX(e.changedTouches[0]) - sx;
    const dt = Math.max(1, performance.now() - st);
    const vx = dx / dt;
    axis = null;

    if (dx >= 56 || (dx >= 30 && vx > 0.42)) {
      flyTutorCard("right", () => {
        if (viewStage === "teach") completeTeachCard();
        else advanceNext(false);
      });
      return;
    }
    if (dx <= -56 || (dx <= -30 && vx < -0.42)) {
      flyTutorCard("left", () => {
        if (viewStage === "teach") {
          completeTeachCard();
        } else {
          const q = activeQuizObj || (curPointId && getPointById(curPointId) && getPointById(curPointId).primary);
          const wasRight = !!(q && pickedVal !== "__UNSURE__" && pickedVal === q.answer);
          advanceNext(wasRight);
        }
      });
      return;
    }
    resetTutorDrag();
  }

  tutorEl.addEventListener("touchend", e => endTutorTouch(e, false), { passive: true });
  tutorEl.addEventListener("touchcancel", e => endTutorTouch(e, true), { passive: true });

  // Swipe right from left half on Ledger ("总表") to close back to previous mode one-handed
  let dsx = 0, dsy = 0, dst = 0;
  dashEl.addEventListener("touchstart", e => {
    if (activeMode !== "dash" || !e.touches || e.touches.length !== 1) return;
    const tag = (e.target && e.target.tagName || "").toLowerCase();
    if (tag === "input") return;
    dsx = fpX(e.touches[0]);
    dsy = fpY(e.touches[0]);
    dst = performance.now();
  }, { passive: true });
  dashEl.addEventListener("touchend", e => {
    if (activeMode !== "dash" || !dsx || !e.changedTouches || !e.changedTouches.length) return;
    const dx = fpX(e.changedTouches[0]) - dsx;
    const dy = fpY(e.changedTouches[0]) - dsy;
    const dt = performance.now() - dst;
    const fromEdgeZone = dsx < 160;
    dsx = 0;
    if (fromEdgeZone && dx >= 68 && Math.abs(dx) > Math.abs(dy) * 1.6 && dt < 600) {
      toggleDashLedger();
    }
  }, { passive: true });
})();

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

  if (activeMode === "vocab") {
    if (e.key === " ") { e.preventDefault(); onVocabCardTapOrReplay(); }
    else if (e.key === "ArrowRight" || e.key === "2" || e.key === "Enter") { e.preventDefault(); triggerVocabAction("right"); }
    else if (e.key === "ArrowLeft" || e.key === "1") { e.preventDefault(); triggerVocabAction("left"); }
    else if (e.key === "ArrowUp" || e.key === "3") { e.preventDefault(); triggerVocabAction("up"); }
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

// ================= MODE ROUTING & ZEN LEDGER ("总表") =================
let dashMod = "grammar";
let dashTier = "todo";
let expandedPt = null;

function switchMode(m, autoPlayRadio) {
  if (m !== "dash") prevNonDashMode = m;
  activeMode = m;
  clearActiveWordToken();
  if (m !== "tutor") stopQuizAudio();
  if (m !== "vocab") stopVocabAudioAndTimers();

  document.getElementById("app-shell").classList.toggle("wide-mode", m === "dash");
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-radio").classList.toggle("active", m === "radio");
  document.getElementById("tab-vocab").classList.toggle("active", m === "vocab");
  ["tutor", "radio", "vocab", "dash"].forEach(k => {
    const b = document.getElementById("btab-" + k);
    if (b) b.classList.toggle("active", m === k);
  });

  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("radio-view").classList.toggle("hidden", m !== "radio");
  document.getElementById("vocab-view").classList.toggle("hidden", m !== "vocab");
  document.getElementById("dash-view").classList.toggle("hidden", m !== "dash");

  renderGreenBoard();

  if (m === "radio") {
    ensureRadioReady();
    if (autoPlayRadio && radioPlayer.paused) {
      toggleRadioPlay(true);
    } else {
      syncRadioUI();
    }
  } else if (m === "vocab") {
    if (!radioPlayer.paused) {
      radioPlayer.pause();
      syncRadioUI();
    }
    enterVocabMode();
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

// ================= ONE-HANDED SWIPE VOCAB SANCTUARY ("记词") =================
let vcRevealed = false;
let vcPendingLeft = false;
let vcAnimating = false;
let vcTimer = null;
let vcToken = 0;
let lastFlashCloudPushMs = 0;

function getVocabMasteryLookup() {
  const map = {};
  const vItems = (DATA.mastery && DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  vItems.forEach(it => {
    if (it.key) map[it.key] = it;
    if (it.name) map[it.name] = it;
  });
  return map;
}

function cleanSpeakZh(zhStr) {
  let s = String(zhStr || "").replace(/[（(][^）)]*[）)]/g, "").trim();
  s = s.split(/[；;\/]/)[0].trim();
  return s || String(zhStr || "").trim();
}

function getVocabCardSpec(surface) {
  const byKey = getVocabMasteryLookup();
  const vItem = byKey[surface] || null;
  const w = (DATA.words && DATA.words[surface]) ? DATA.words[surface] : {};
  const pre = (DATA.vocab_cards && DATA.vocab_cards[surface]) ? DATA.vocab_cards[surface] : null;
  const isTapped = Array.isArray(A.tappedWords) && A.tappedWords.includes(surface);

  if (pre) {
    return {
      word: surface,
      key: (vItem && vItem.key) || surface,
      pointId: (vItem && vItem.point_id) || "",
      mode: pre.mode || "kanji_read",
      chunk_ja: pre.chunk_ja || surface,
      target: pre.target || surface,
      kana: pre.kana || w.kana || surface,
      trap_hl: Array.isArray(pre.trap_hl) ? pre.trap_hl : (w.trap_hl || []),
      trap_tag: pre.trap_tag || w.trap_tag || "",
      zh_opaque: typeof pre.zh_opaque === "boolean" ? pre.zh_opaque : (typeof w.zh_opaque === "boolean" ? w.zh_opaque : true),
      pitch: pre.pitch || w.pitch || "",
      zh: pre.zh || w.zh || (vItem && vItem.sub) || "",
      twin: pre.twin || "",
      zh_speak: typeof pre.zh_speak === "string" ? pre.zh_speak : cleanSpeakZh(pre.zh || w.zh || ""),
      front_audio: pre.front_audio || "",
      rev_audio: pre.rev_audio || "",
      full_audio: pre.full_audio || "",
      word_audio: pre.word_audio || (vItem && vItem.audio) || w.audio || "",
      source: isTapped ? "今日查词" : ""
    };
  }

  const hasKanji = /[\u4e00-\u9faf\u3400-\u4dbf]/.test(surface);
  const zh = w.zh || (vItem && vItem.sub) || "";
  const zhOpaque = hasKanji ? (typeof w.zh_opaque === "boolean" ? w.zh_opaque : true) : true;
  const tipParts = [];
  if (w.head && w.head !== surface) tipParts.push(`原形 ${w.head}`);
  let rawTip = w.tip || (vItem && vItem.note) || "";
  if (rawTip && zh && rawTip.startsWith(zh)) {
    rawTip = rawTip.slice(zh.length).replace(/^[·\s]+/, "").trim();
  }
  if (rawTip && rawTip !== zh) tipParts.push(rawTip);

  return {
    word: surface,
    key: (vItem && vItem.key) || surface,
    pointId: (vItem && vItem.point_id) || "",
    mode: hasKanji ? "kanji_read" : "kana_meaning",
    chunk_ja: surface,
    target: surface,
    kana: w.kana || surface,
    trap_hl: Array.isArray(w.trap_hl) ? w.trap_hl : [],
    trap_tag: w.trap_tag || "",
    zh_opaque: zhOpaque,
    pitch: w.pitch || "",
    zh: zh,
    twin: tipParts.join(" · "),
    zh_speak: (!hasKanji || zhOpaque) ? cleanSpeakZh(zh) : "",
    front_audio: "",
    rev_audio: "",
    full_audio: "",
    word_audio: (vItem && vItem.audio) || w.audio || "",
    source: isTapped ? "今日查词" : ""
  };
}

function countRemainingVocabPool() {
  applyMasteryOverrides();
  const vItems = (DATA.mastery && DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  return vItems.filter(it => it.tier !== "done").length;
}

function curateVocabBatch(limitCnt) {
  applyMasteryOverrides();
  const maxN = Math.max(1, limitCnt || VOCAB_BATCH_SIZE);
  const vItems = (DATA.mastery && DATA.mastery.vocab && DATA.mastery.vocab.items) ? DATA.mastery.vocab.items : [];
  const byKey = getVocabMasteryLookup();
  const seen = new Set();
  const seenHead = new Set();
  const out = [];

  function tryAdd(surface) {
    if (!surface || out.length >= maxN || seen.has(surface)) return;
    if (PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return;
    const it = byKey[surface] || null;
    const eff = getEffectiveMastery((it && it.key) || surface, surface);
    if (eff.tier === "done") return;
    const w = DATA.words[surface] || {};
    const head = w.head || surface;
    if (seenHead.has(head)) return;
    const zh = (DATA.vocab_cards && DATA.vocab_cards[surface] && DATA.vocab_cards[surface].zh) || w.zh || (it && it.sub) || "";
    if (!zh) return;
    seen.add(surface);
    seenHead.add(head);
    out.push(surface);
  }

  // 1) Words tapped today during quiz / podcast (newest first)
  const tapped = Array.isArray(A.tappedWords) ? A.tappedWords.slice().reverse() : [];
  tapped.forEach(sw => tryAdd(sw));

  // 2) Recently missed words (from tutor or Grok practice)
  const recentWeak = Array.isArray(DATA.recent_weak_words) ? DATA.recent_weak_words : [];
  recentWeak.forEach(sw => tryAdd(sw));

  // 3) Remaining 0/3 待攻克 words
  vItems.forEach(it => {
    const eff = getEffectiveMastery(it.key, it.name);
    if (eff.tier === "todo") tryAdd(it.name);
  });

  // 4) 1/3 & 2/3 巩固中 words due for cross-day progression (lastDate !== TODAY_TAG), rotated by date
  const dueWip = [];
  vItems.forEach(it => {
    const eff = getEffectiveMastery(it.key, it.name);
    if (eff.tier === "wip" && eff.lastDate !== TODAY_TAG) dueWip.push(it.name);
  });
  const rot = (parseInt(TODAY_TAG.slice(-2), 10) || 0) * 5;
  for (let i = 0; i < dueWip.length; i++) {
    tryAdd(dueWip[(i + rot) % dueWip.length]);
  }

  // 5) Any remaining wip words if needed to fill the batch
  vItems.forEach(it => {
    const eff = getEffectiveMastery(it.key, it.name);
    if (eff.tier === "wip") tryAdd(it.name);
  });

  return out;
}

function ensureVocabSession(forceNewBatch) {
  applyMasteryOverrides();
  if (!forceNewBatch && A.vocabSess && A.vocabSess.date === DATA.plan_date && Array.isArray(A.vocabSess.queue)) {
    const byKey = getVocabMasteryLookup();
    const filtered = A.vocabSess.queue.filter(sw => {
      const it = byKey[sw] || null;
      return getEffectiveMastery((it && it.key) || sw, sw).tier !== "done";
    });
    if (filtered.length !== A.vocabSess.queue.length) {
      const diff = A.vocabSess.queue.length - filtered.length;
      A.vocabSess.queue = filtered;
      A.vocabSess.cleared = Math.min(A.vocabSess.total || 0, (A.vocabSess.cleared || 0) + diff);
    }
    const clearedSet = new Set(Array.isArray(A.vocabSess.clearedWords) ? A.vocabSess.clearedWords : []);
    const tappedSet = new Set(Array.isArray(A.tappedWords) ? A.tappedWords : []);
    const urgent = (Array.isArray(DATA.recent_weak_words) ? DATA.recent_weak_words : []).filter(sw => {
      if (!sw || clearedSet.has(sw) || A.vocabSess.queue.includes(sw)) return false;
      const it = byKey[sw] || null;
      return getEffectiveMastery((it && it.key) || sw, sw).tier === "todo";
    });
    if (urgent.length > 0 && A.vocabSess.queue.length > 1) {
      const headCard = A.vocabSess.queue[0];
      const rest = A.vocabSess.queue.slice(1);
      const keepCap = Math.max(0, VOCAB_BATCH_SIZE - (A.vocabSess.cleared || 0) - 1);
      const mergedRest = urgent.concat(rest.filter(w => tappedSet.has(w) || !urgent.includes(w))).slice(0, Math.max(rest.length, keepCap));
      A.vocabSess.queue = [headCard].concat(mergedRest);
      A.vocabSess.total = (A.vocabSess.cleared || 0) + A.vocabSess.queue.length;
    }
    if (A.vocabSess.queue.length === 0 && (A.vocabSess.total || 0) > 0) {
      A.vocabSess.done = true;
    }
    return A.vocabSess;
  }

  const queue = curateVocabBatch(VOCAB_BATCH_SIZE);
  A.vocabSess = {
    date: DATA.plan_date,
    queue: queue,
    total: queue.length,
    cleared: 0,
    clearedWords: [],
    failedWords: [],
    done: queue.length === 0,
    updatedAt: nowUnixSec()
  };
  saveAdaptiveState();
  return A.vocabSess;
}

function pushVocabRecord(card, choiceLabel, isOk, stampSec) {
  const tsSec = Math.max(TRUE_GREEN_EPOCH, Math.floor(stampSec || nowUnixSec()));
  const ptKey = card.key || card.word;
  const rec = {
    id: `VC-${ptKey}`,
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
    if (markDoneNow || Date.now() - lastFlashCloudPushMs > 10000) {
      lastFlashCloudPushMs = Date.now();
      scheduleCloudPush(markDoneNow ? 80 : 350);
    }
  }
}

function stopVocabAudioAndTimers() {
  vcToken += 1;
  if (vcTimer) {
    clearTimeout(vcTimer);
    vcTimer = null;
  }
  try {
    wordPlayer.onended = null;
    wordPlayer.onerror = null;
    wordPlayer.pause();
  } catch (e) {}
  try {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  } catch (e) {}
}

function speakUtteranceLang(text, langCode, rateVal, cb) {
  const clean = String(text || "").trim();
  if (!clean || !("speechSynthesis" in window)) {
    if (cb) setTimeout(cb, 320);
    return;
  }
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    clearTimeout(safety);
    if (cb) cb();
  };
  const safety = setTimeout(finish, 3200);
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = langCode;
    u.rate = rateVal || 1.0;
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);
  } catch (e) {
    finish();
  }
}

function playUrlOnWordPlayer(url, myToken, onDone, onFail) {
  if (!url) {
    if (onFail) onFail();
    else if (onDone) onDone();
    return;
  }
  let settled = false;
  const safety = setTimeout(() => {
    if (settled || vcToken !== myToken) return;
    settled = true;
    wordPlayer.onended = null;
    wordPlayer.onerror = null;
    if (onDone) onDone();
  }, 4600);

  const handleOk = () => {
    if (settled || vcToken !== myToken) return;
    settled = true;
    clearTimeout(safety);
    wordPlayer.onended = null;
    wordPlayer.onerror = null;
    if (onDone) onDone();
  };
  const handleErr = () => {
    if (settled || vcToken !== myToken) return;
    settled = true;
    clearTimeout(safety);
    wordPlayer.onended = null;
    wordPlayer.onerror = null;
    if (onFail) onFail();
    else if (onDone) onDone();
  };

  warmAudio(url).then(resolvedUrl => {
    if (vcToken !== myToken) {
      clearTimeout(safety);
      return;
    }
    try {
      wordPlayer.onended = handleOk;
      wordPlayer.onerror = handleErr;
      wordPlayer.src = resolvedUrl || url;
      wordPlayer.currentTime = 0;
      wordPlayer.playbackRate = 1.0;
      const pr = wordPlayer.play();
      if (pr && typeof pr.catch === "function") {
        pr.catch(handleErr);
      }
    } catch (e) {
      handleErr();
    }
  });
}

function playBilingualFallback(card, includeJa, myToken, onDone) {
  const zhVoiceTxt = String(typeof card.zh_speak === "string" ? card.zh_speak : (card.zh || "")).trim();
  const speakZhStep = () => {
    if (vcToken !== myToken) return;
    if (!zhVoiceTxt) {
      if (onDone) onDone();
      return;
    }
    speakUtteranceLang(zhVoiceTxt, "zh-CN", 1.04, () => {
      if (vcToken === myToken && onDone) onDone();
    });
  };
  if (!includeJa) {
    speakZhStep();
    return;
  }
  if (card.word_audio) {
    playUrlOnWordPlayer(
      card.word_audio,
      myToken,
      () => {
        if (vcToken !== myToken) return;
        if (!zhVoiceTxt) {
          if (onDone) onDone();
          return;
        }
        vcTimer = setTimeout(speakZhStep, 140);
      },
      () => {
        speakUtteranceLang(card.chunk_ja || card.kana || card.word, "ja-JP", 0.98, speakZhStep);
      }
    );
  } else {
    speakUtteranceLang(card.chunk_ja || card.kana || card.word, "ja-JP", 0.98, speakZhStep);
  }
}

function warmUpcomingVocabCards() {
  const sess = A.vocabSess;
  if (!sess || !Array.isArray(sess.queue)) return;
  sess.queue.slice(0, 3).forEach(sw => {
    const c = getVocabCardSpec(sw);
    if (c.front_audio) warmAudio(c.front_audio);
    if (c.rev_audio) warmAudio(c.rev_audio);
    if (c.full_audio) warmAudio(c.full_audio);
    if (c.word_audio) warmAudio(c.word_audio);
  });
}

function renderStreakDotsHTML(streak) {
  const s = Math.max(0, Math.min(3, Number(streak || 0)));
  return `<span class="vc-dots" aria-hidden="true">${[0, 1, 2].map(i => `<span class="vc-dot${i < s ? " on" : ""}"></span>`).join("")}</span><span>${s}/3</span>`;
}

function renderChunkHighlightHTML(chunkJa, target) {
  const src = String(chunkJa || "");
  const tgt = String(target || "");
  if (!tgt || src === tgt) return escapeHtml(src);
  const idx = src.indexOf(tgt);
  if (idx < 0) return escapeHtml(src);
  return (
    escapeHtml(src.slice(0, idx)) +
    `<span class="vc-hl">${escapeHtml(src.slice(idx, idx + tgt.length))}</span>` +
    escapeHtml(src.slice(idx + tgt.length))
  );
}

function enterVocabMode() {
  ensureVocabSession(false);
  vcRevealed = false;
  vcPendingLeft = false;
  vcAnimating = false;
  dealCurrentVocabCard(true);
}

function startNextVocabBatch() {
  stopVocabAudioAndTimers();
  ensureVocabSession(true);
  vcRevealed = false;
  vcPendingLeft = false;
  vcAnimating = false;
  dealCurrentVocabCard(true);
}

function onRemoteVocabSync() {
  if (activeMode !== "vocab" || vcAnimating || vcPendingLeft) return;
  const sess = ensureVocabSession(false);
  if (!sess.queue.length) renderVocabStage();
}

function dealCurrentVocabCard(autoStartAudio) {
  stopVocabAudioAndTimers();
  vcRevealed = false;
  vcPendingLeft = false;
  vcAnimating = false;
  const sess = ensureVocabSession(false);
  warmUpcomingVocabCards();
  renderVocabStage();

  if (!sess.queue.length) {
    sess.done = true;
    saveAdaptiveState();
    if (sess.total > 0) {
      recordFlashProgress(sess.total, sess.total, true);
    }
    renderGreenBoard();
    return;
  }

  if (!autoStartAudio) return;
  const card = getVocabCardSpec(sess.queue[0]);
  const myToken = ++vcToken;

  if (card.mode === "kanji_read") {
    // Silent Kanji micro-chunk front so audio never spoils the reading before retrieval!
    vcTimer = setTimeout(() => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      revealVocabCard(true);
    }, 1050);
  } else {
    // Kana / spoken word: play Japanese first, pause 0.9s for Chinese meaning recall, then reveal Mandarin
    const frontUrl = card.front_audio || card.word_audio;
    const afterFront = () => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      vcTimer = setTimeout(() => {
        if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
        revealVocabCard(true);
      }, 900);
    };
    if (frontUrl) {
      playUrlOnWordPlayer(
        frontUrl,
        myToken,
        afterFront,
        () => speakUtteranceLang(card.chunk_ja || card.kana || card.word, "ja-JP", 0.98, afterFront)
      );
    } else {
      speakUtteranceLang(card.chunk_ja || card.kana || card.word, "ja-JP", 0.98, afterFront);
    }
  }
}

function revealVocabCard(playAudioNow, forceFullBilingual) {
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  const card = getVocabCardSpec(sess.queue[0]);
  stopVocabAudioAndTimers();
  vcRevealed = true;

  const revEl = document.getElementById("vc-reveal-box");
  if (revEl) revEl.classList.add("shown");
  const cueEl = document.getElementById("vc-cue-line");
  if (cueEl) {
    if (vcPendingLeft) {
      cueEl.textContent = card.mode === "kanji_read"
        ? "已标待练读音 · 盯住红字听清再滑"
        : "已记入没记住 · 听完滑一下继续";
      cueEl.className = "vc-cue ng";
    } else {
      cueEl.textContent = card.mode === "kanji_read"
        ? "读音全准右滑 · 差一拍就左滑"
        : "右滑记住 · 左滑没记住 · 上滑太熟";
      cueEl.className = "vc-cue";
    }
  }

  if (!playAudioNow) return;
  const myToken = ++vcToken;
  const needFull = !!forceFullBilingual || card.mode === "kanji_read";
  const targetUrl = needFull ? (card.full_audio || card.rev_audio) : card.rev_audio;

  if (targetUrl) {
    playUrlOnWordPlayer(
      targetUrl,
      myToken,
      null,
      () => playBilingualFallback(card, needFull, myToken, null)
    );
  } else {
    playBilingualFallback(card, needFull, myToken, null);
  }
}

function replayVocabAudio(ev) {
  if (ev) ev.stopPropagation();
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  if (!vcRevealed) {
    revealVocabCard(true, true);
    return;
  }
  const card = getVocabCardSpec(sess.queue[0]);
  stopVocabAudioAndTimers();
  const myToken = ++vcToken;
  const fullUrl = card.full_audio || (card.mode === "kanji_read" ? card.rev_audio : "");
  if (fullUrl) {
    playUrlOnWordPlayer(
      fullUrl,
      myToken,
      null,
      () => playBilingualFallback(card, true, myToken, null)
    );
  } else {
    playBilingualFallback(card, true, myToken, null);
  }
}

function onVocabCardTapOrReplay() {
  if (vcAnimating) return;
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  if (!vcRevealed) {
    revealVocabCard(true, cardNeedsFullOnTap(sess.queue[0]));
  } else {
    replayVocabAudio();
  }
}

function cardNeedsFullOnTap(surface) {
  const c = getVocabCardSpec(surface);
  return c.mode === "kanji_read";
}

function resetVocabCardTransform() {
  const cardEl = document.getElementById("vc-card");
  if (!cardEl) return;
  cardEl.classList.remove("dragging");
  cardEl.classList.add("settling");
  cardEl.style.transform = "";
  ["vc-st-right", "vc-st-left", "vc-st-up"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.opacity = "0";
  });
}

function animateOutAndNext(flyCls, afterOut) {
  const cardEl = document.getElementById("vc-card");
  vcAnimating = true;
  stopVocabAudioAndTimers();
  if (!cardEl) {
    vcAnimating = false;
    afterOut();
    return;
  }
  cardEl.classList.remove("dragging", "settling");
  cardEl.classList.add(flyCls);
  setTimeout(() => {
    vcAnimating = false;
    afterOut();
  }, 220);
}

function requeueCurrentFailedCard(sess) {
  if (!sess || !sess.queue.length) return;
  const w = sess.queue.shift();
  const insertAt = Math.min(sess.queue.length, 4);
  sess.queue.splice(insertAt, 0, w);
  sess.updatedAt = nowUnixSec();
}

function acknowledgePendingLeft(flyDir) {
  if (!vcPendingLeft || vcAnimating) return;
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  const cls = flyDir === "right" ? "fly-right" : "fly-left";
  animateOutAndNext(cls, () => {
    requeueCurrentFailedCard(sess);
    saveAdaptiveState();
    dealCurrentVocabCard(true);
  });
}

function triggerVocabAction(dir) {
  if (vcAnimating) return;
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;

  if (vcPendingLeft) {
    acknowledgePendingLeft(dir === "right" ? "right" : "left");
    return;
  }

  const word = sess.queue[0];
  const card = getVocabCardSpec(word);
  const stamp = nowUnixSec();

  if (dir === "left") {
    if (!Array.isArray(sess.failedWords)) sess.failedWords = [];
    if (!sess.failedWords.includes(word)) sess.failedWords.push(word);

    applyMasteryAction(card.key, card.word, "fail", stamp);
    if (card.pointId && A.pts[card.pointId]) {
      const ps = A.pts[card.pointId];
      ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
      ps.status = "learning";
      ps.dueStep = A.step + 2;
      recomputeStatusesFromCRDT(A);
    }
    pushVocabRecord(card, "记词:没记住", false, stamp);
    applyMasteryOverrides();
    refreshMarkedWordTokens();
    saveAdaptiveState();
    renderGreenBoard();
    scheduleCloudPush(100);

    // If user swiped Left before seeing the answer, reveal + play Japanese & Mandarin first so they learn it!
    if (!vcRevealed) {
      resetVocabCardTransform();
      vcPendingLeft = true;
      const dotsWrap = document.getElementById("vc-meta-dots");
      if (dotsWrap) dotsWrap.innerHTML = renderStreakDotsHTML(0);
      const dockEl = document.getElementById("vc-dock-row");
      if (dockEl) {
        dockEl.innerHTML = `
          <button class="vc-btn mid" onclick="replayVocabAudio(event)">再听一遍</button>
          <button class="vc-btn ok" onclick="acknowledgePendingLeft('left')">听清了 · 稍后再考 →</button>
        `;
      }
      revealVocabCard(true, true);
      return;
    }

    animateOutAndNext("fly-left", () => {
      requeueCurrentFailedCard(sess);
      saveAdaptiveState();
      dealCurrentVocabCard(true);
    });
    return;
  }

  if (dir === "up") {
    applyMasteryAction(card.key, card.word, "seal", stamp);
    if (card.pointId && A.pts[card.pointId]) {
      const ps = A.pts[card.pointId];
      ps.greenAt = Math.max(ps.greenAt || 0, stamp, (ps.retestAt || 0) + 1);
      recomputeStatusesFromCRDT(A);
    }
    pushVocabRecord(card, "记词:太熟", true, stamp);
    applyMasteryOverrides();
    refreshMarkedWordTokens();
    animateOutAndNext("fly-up", () => {
      sess.queue.shift();
      if (!Array.isArray(sess.clearedWords)) sess.clearedWords = [];
      if (!sess.clearedWords.includes(word)) sess.clearedWords.push(word);
      sess.cleared = Math.min(sess.total, (sess.cleared || 0) + 1);
      sess.done = sess.queue.length === 0;
      sess.updatedAt = stamp;
      saveAdaptiveState();
      recordFlashProgress(sess.cleared, sess.total, sess.done);
      renderGreenBoard();
      scheduleCloudPush(80);
      dealCurrentVocabCard(true);
    });
    return;
  }

  // dir === "right" ("记住")
  const hadFailToday = Array.isArray(sess.failedWords) && sess.failedWords.includes(word);
  applyMasteryAction(card.key, card.word, hadFailToday ? "recover" : "pass", stamp);
  pushVocabRecord(card, "记词:记住", true, stamp);
  applyMasteryOverrides();
  refreshMarkedWordTokens();

  animateOutAndNext("fly-right", () => {
    sess.queue.shift();
    if (!Array.isArray(sess.clearedWords)) sess.clearedWords = [];
    if (!sess.clearedWords.includes(word)) sess.clearedWords.push(word);
    sess.cleared = Math.min(sess.total, (sess.cleared || 0) + 1);
    sess.done = sess.queue.length === 0;
    sess.updatedAt = stamp;
    saveAdaptiveState();
    recordFlashProgress(sess.cleared, sess.total, sess.done);
    renderGreenBoard();
    scheduleCloudPush(90);
    dealCurrentVocabCard(true);
  });
}

function bindVocabCardGestures(cardEl) {
  if (!cardEl) return;
  let dragging = false;
  let activePid = null;
  let sx = 0, sy = 0, st = 0;

  cardEl.addEventListener("pointerdown", e => {
    if (vcAnimating) return;
    if (typeof e.button === "number" && e.button !== 0) return;
    dragging = true;
    activePid = e.pointerId;
    sx = fpX(e);
    sy = fpY(e);
    st = performance.now();
    cardEl.classList.remove("settling");
    cardEl.classList.add("dragging");
    try { cardEl.setPointerCapture(e.pointerId); } catch (err) {}
  });

  cardEl.addEventListener("pointermove", e => {
    if (!dragging || e.pointerId !== activePid) return;
    const dx = fpX(e) - sx;
    const dy = fpY(e) - sy;
    cardEl.style.transform = `translate3d(${dx.toFixed(1)}px, ${(dy * 0.42).toFixed(1)}px, 0) rotate(${(dx * 0.038).toFixed(2)}deg)`;

    const stR = document.getElementById("vc-st-right");
    const stL = document.getElementById("vc-st-left");
    const stU = document.getElementById("vc-st-up");
    if (!vcPendingLeft && dy < -26 && Math.abs(dy) > Math.abs(dx) * 1.25) {
      if (stU) stU.style.opacity = String(Math.min(1, (-dy - 22) / 48));
      if (stR) stR.style.opacity = "0";
      if (stL) stL.style.opacity = "0";
    } else if (dx > 16) {
      if (stR) stR.style.opacity = String(Math.min(1, (dx - 14) / 50));
      if (stL) stL.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    } else if (dx < -16) {
      if (stL) stL.style.opacity = String(Math.min(1, (-dx - 14) / 50));
      if (stR) stR.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    } else {
      if (stR) stR.style.opacity = "0";
      if (stL) stL.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    }
  });

  function finishGesture(e, isCancel) {
    if (!dragging || e.pointerId !== activePid) return;
    dragging = false;
    activePid = null;
    try { cardEl.releasePointerCapture(e.pointerId); } catch (err) {}
    if (isCancel) {
      resetVocabCardTransform();
      return;
    }
    const dx = fpX(e) - sx;
    const dy = fpY(e) - sy;
    const dt = Math.max(1, performance.now() - st);
    const vx = dx / dt;
    const vy = dy / dt;

    if (Math.hypot(dx, dy) < 10 && dt < 460) {
      resetVocabCardTransform();
      onVocabCardTapOrReplay();
      return;
    }

    if (vcPendingLeft) {
      if (Math.abs(dx) >= 48 || (Math.abs(dx) >= 28 && Math.abs(vx) > 0.4)) {
        acknowledgePendingLeft(dx >= 0 ? "right" : "left");
      } else {
        resetVocabCardTransform();
      }
      return;
    }

    if ((dy <= -68 || (dy <= -40 && vy < -0.5)) && Math.abs(dy) > Math.abs(dx) * 1.25) {
      triggerVocabAction("up");
      return;
    }
    if (dx >= 62 || (dx >= 34 && vx > 0.45 && Math.abs(dx) > Math.abs(dy))) {
      triggerVocabAction("right");
      return;
    }
    if (dx <= -62 || (dx <= -34 && vx < -0.45 && Math.abs(dx) > Math.abs(dy))) {
      triggerVocabAction("left");
      return;
    }
    resetVocabCardTransform();
  }

  cardEl.addEventListener("pointerup", e => finishGesture(e, false));
  cardEl.addEventListener("pointercancel", e => finishGesture(e, true));
}

function renderVocabStage() {
  const box = document.getElementById("vocab-stage-box");
  if (!box) return;
  const sess = ensureVocabSession(false);

  if (!sess.queue.length) {
    const remPool = countRemainingVocabPool();
    const m = computeDaily120Metrics();
    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline ok">${sess.total > 0 ? `本组 ${sess.total} 词已清零 · 圆印已收笔` : "核心生词已全部满 3/3"}</span>
      </div>
      <div class="focal-space">
        <h2 class="point-heading">${sess.total > 0 ? "今晚这组词全部过关" : "核心生词已全部掌握"}</h2>
        <p class="logic-line">${remPool > 0
          ? `今日记词圆印已点亮，当前预计 ${m.projScore} 分。总表里还有 ${remPool} 个词未满跨 3 天的 3/3，明天接着巩固就会真正变绿。`
          : `所有核心生词都已跨 3 天答对满 3/3，稳稳锁进长期记忆。`}</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          <button class="ghost-btn" onclick="switchMode('dash')">查看总表</button>
          ${remPool > 0
            ? `<button class="sumi-btn" onclick="startNextVocabBatch()">再练一组</button>`
            : `<button class="sumi-btn" onclick="switchMode('tutor')">回做题</button>`}
        </div>
      </div>
    `;
    return;
  }

  const word = sess.queue[0];
  const card = getVocabCardSpec(word);
  const eff = getEffectiveMastery(card.key, card.word);
  const isRequeued = Array.isArray(sess.failedWords) && sess.failedWords.includes(word);
  const posNum = Math.min(Math.max(1, sess.total), (sess.cleared || 0) + 1);
  const leftLabel = isRequeued
    ? `回炉巩固 · 余 ${sess.queue.length} 词`
    : `今晚 ${posNum} / ${sess.total} 词${card.source ? " · " + card.source : ""}`;
  const isKanjiCard = card.mode === "kanji_read";
  const hasTargetKanji = /[\u4e00-\u9faf\u3400-\u4dbf]/.test(card.target || card.word);
  const kanaHtml = (hasTargetKanji && card.kana)
    ? renderTrapKanaHTML(card.target || card.word, card.kana, card.trap_hl, card.trap_tag)
    : "";
  const quietZh = isKanjiCard && !card.zh_opaque;
  const initCue = isKanjiCard ? "默念读音 · 有一拍不准就左滑" : "听日文 · 想中文意思";
  const rightStampTxt = isKanjiCard ? "读准了" : "记住";
  const leftStampTxt = isKanjiCard ? "读音待练" : "没记住";
  const leftBtnTxt = isKanjiCard ? "← 读音不准" : "← 没记住";
  const rightBtnTxt = isKanjiCard ? "读准了 →" : "记住 →";

  box.innerHTML = `
    <div class="meta-bar">
      <span class="overline${isRequeued ? " warm" : ""}">${escapeHtml(leftLabel)}</span>
      <div class="vc-meta-right">
        <span id="vc-meta-dots" style="display:inline-flex;align-items:center;gap:6px;">${renderStreakDotsHTML(eff.streak)}</span>
        <button class="text-btn" onclick="replayVocabAudio(event)">重听</button>
      </div>
    </div>

    <div class="vc-deck-area">
      <div class="vc-card" id="vc-card">
        <div class="vc-stamp right" id="vc-st-right">${rightStampTxt}</div>
        <div class="vc-stamp left" id="vc-st-left">${leftStampTxt}</div>
        <div class="vc-stamp up" id="vc-st-up">太熟封存</div>

        <div class="vc-cue" id="vc-cue-line">${initCue}</div>
        <div class="vc-chunk">${renderChunkHighlightHTML(card.chunk_ja, card.target)}</div>

        <div class="vc-reveal${vcRevealed ? " shown" : ""}" id="vc-reveal-box">
          ${kanaHtml ? `<div class="vc-kana">${kanaHtml}</div>` : ""}
          <div class="vc-zh${quietZh ? " quiet" : ""}">${escapeHtml(card.zh)}</div>
          ${card.twin ? `<div class="vc-twin">${escapeHtml(card.twin)}</div>` : ""}
        </div>
      </div>
    </div>

    <div class="vc-dock" id="vc-dock-row">
      <button class="vc-btn ng" onclick="triggerVocabAction('left')">${leftBtnTxt}</button>
      <button class="vc-btn mid" onclick="triggerVocabAction('up')">↑ 太熟</button>
      <button class="vc-btn ok" onclick="triggerVocabAction('right')">${rightBtnTxt}</button>
    </div>
  `;

  bindVocabCardGestures(document.getElementById("vc-card"));
}

function renderDashboard() {
  applyMasteryOverrides();
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
          <span class="pillar-stat">已掌握 ${c.done} / ${c.total}</span>
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
  const remVocab = countRemainingVocabPool();
  const entryEl = document.getElementById("night-flash-entry");
  if (entryEl) {
    if (remVocab > 0) {
      const subTxt = dm.flashDone
        ? `今日一组已完成 · 余 ${remVocab} 词未满 3/3`
        : `单手右滑记住 · 左滑回炉 · 跨 3 天满 3/3 变绿`;
      entryEl.innerHTML = `
        <div class="night-bar">
          <div class="night-bar-txt">
            <div class="night-bar-title">单手记词</div>
            <div class="night-bar-sub">${subTxt}</div>
          </div>
          <button class="night-go-btn" onclick="switchMode('vocab')">去记词</button>
        </div>
      `;
    } else {
      entryEl.innerHTML = "";
    }
  }

  const curCounts = DATA.mastery[dashMod].counts;
  document.getElementById("tier-tabs").innerHTML = `
    <button class="tier-link ${dashTier === 'todo' ? 'active' : ''}" onclick="selectDashTier('todo')">待攻克 ${curCounts.todo}</button>
    <button class="tier-link ${dashTier === 'wip' ? 'active' : ''}" onclick="selectDashTier('wip')">巩固中 ${curCounts.wip}</button>
    <button class="tier-link ${dashTier === 'done' ? 'active' : ''}" onclick="selectDashTier('done')">已掌握 ${curCounts.done}</button>
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
    const stNum = Math.max(0, Math.min(3, Number(it.streak || (it.tier === "done" ? 3 : (it.tier === "wip" ? 1 : 0)))));
    const stCls = it.tier === "done" ? "s-done" : (it.tier === "wip" ? "s-wip" : "");
    return `
    <div class="ledger-item" onclick="togglePtNote(${i})">
      <div class="li-row">
        <div class="li-left">
          <span class="li-dot ${it.tier}"></span>
          <span class="li-name">${escapeHtml(it.name)}</span>
        </div>
        <div class="li-right">
          <span class="li-sub">${escapeHtml(it.sub)}</span>
          <span class="li-streak ${stCls}">${stNum}/3</span>
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
      ③ 单手记词　<strong id="modal-flash-cnt">${m.flashDone ? "今日已完成" : `${m.flashSeen} / ${m.flashTarget} 词`}</strong><br/>
      当前预计分　<strong id="modal-proj-score">${m.projScore} / 180 分</strong>
    </p>
    <p class="modal-promise">圆印代表今日三件事打卡；总表里每个词与考点需跨 3 天答对满 3/3 才算真正掌握。</p>
    <div class="sync-box">
      <p class="sync-note" id="cloud-sync-status-line">正在对齐云端进度…</p>
      <button class="sync-btn" onclick="manualCloudSync(this)">立即对齐多端进度</button>
    </div>
    <div class="dock-row">
      <button class="ghost-btn" onclick="resetTodayMission()">重做题</button>
      <button class="ghost-btn" onclick="closeModal();switchMode('dash')">总表</button>
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
    else if (activeMode === "vocab") renderVocabStage();
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
    tryLockPortrait();
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
          A.pts[pid].greenAt = Math.max(A.pts[pid].greenAt || 0, nowUnixSec());
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
  else if (m === "vocab" || m === "flash") switchMode("vocab");
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

# Built-in JS runtime boot & mode-switch smoke gate (prevents shipping any ReferenceError/TypeError)
import shutil
import subprocess

if shutil.which("node"):
    smoke_js = r"""
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[1], 'utf8');
const m = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
if (!m) throw new Error('No <script> found in index.html');
function makeEl(id) {
  return {
    id: id || '', style: {}, dataset: {}, innerHTML: '', textContent: '', value: '', children: [],
    classList: { _s: new Set(), add(...x){x.forEach(k=>this._s.add(k));}, remove(...x){x.forEach(k=>this._s.delete(k));}, toggle(k,f){if(f===undefined){if(this._s.has(k)){this._s.delete(k);return false;}this._s.add(k);return true;}if(f)this._s.add(k);else this._s.delete(k);return f;}, contains(k){return this._s.has(k);} },
    appendChild(c){this.children.push(c);return c;}, removeChild(){}, setAttribute(k,v){this[k]=v;}, getAttribute(k){return this[k]||null;},
    addEventListener(){}, removeEventListener(){}, querySelector(){return makeEl();}, querySelectorAll(){return [];},
    getBoundingClientRect(){return {left:0,top:0,width:390,height:844};}, scrollTo(){}, focus(){}, blur(){},
    play(){return Promise.resolve();}, pause(){}, load(){}
  };
}
const els = {}, store = {};
const sb = {
  console, Math, Date, JSON, Object, Array, String, Number, Boolean, Set, Map, RegExp, Error, Promise, URL, URLSearchParams,
  performance:{now:()=>Date.now()}, innerWidth:390, innerHeight:844, scrollTo:()=>{}, addEventListener:()=>{}, removeEventListener:()=>{},
  parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  setTimeout:()=>1, clearTimeout:()=>{}, setInterval:()=>1, clearInterval:()=>{}, requestAnimationFrame:()=>1, cancelAnimationFrame:()=>{},
  localStorage:{getItem:k=>(k in store?store[k]:null), setItem:(k,v)=>{store[k]=String(v);}, removeItem:k=>{delete store[k];}},
  sessionStorage:{getItem:()=>null, setItem:()=>{}, removeItem:()=>{}},
  navigator:{userAgent:'Mozilla/5.0 Mobile', serviceWorker:{register:()=>Promise.resolve({update:()=>Promise.resolve()}), getRegistration:()=>Promise.resolve(null), addEventListener:()=>{}}, mediaSession:{metadata:null, setActionHandler:()=>{}}, onLine:true, sendBeacon:()=>true},
  MediaMetadata:function(x){Object.assign(this,x);}, Audio:function(){return makeEl('audio');}, EventSource:function(){return {addEventListener(){},close(){}};},
  fetch:()=>Promise.resolve({ok:true, text:()=>Promise.resolve(''), json:()=>Promise.resolve({})}),
  location:{href:'https://tango13ucla.github.io/n3-audio-tutor/', hostname:'tango13ucla.github.io', search:'', hash:'', reload:()=>{}},
  history:{replaceState:()=>{}, pushState:()=>{}}, screen:{orientation:{lock:()=>Promise.resolve()}}, matchMedia:()=>({matches:false, addEventListener:()=>{}}),
  document:{body:makeEl('body'), documentElement:makeEl('html'), visibilityState:'visible', getElementById:id=>(els[id]||(els[id]=makeEl(id))), querySelector:s=>makeEl(s), querySelectorAll:()=>[], createElement:t=>makeEl(t), addEventListener:()=>{}}
};
sb.window = sb; sb.self = sb; sb.globalThis = sb;
vm.runInNewContext(m[1], sb, { filename: 'index.html.js' });
const pkt0 = sb.buildCompactPacket();
if (!pkt0 || pkt0.a !== 'n3z') throw new Error('Smoke check failed: invalid compact packet');
sb.switchMode('radio', false);
sb.switchMode('vocab');
sb.onVocabCardTapOrReplay();
sb.triggerVocabAction('right');
sb.switchMode('dash');
sb.openSessionModal();
sb.closeModal();
sb.switchMode('tutor');
if (typeof sb.completeTeachCard === 'function') {
  try { sb.completeTeachCard(); } catch (e) { throw new Error('completeTeachCard failed: ' + e.message); }
}
const choices = vm.runInNewContext('currentChoices', sb);
if (Array.isArray(choices) && choices.length > 0) {
  sb.submitAnswer(choices[0]);
  const pkt1 = sb.buildCompactPacket();
  if (!pkt1 || typeof pkt1.z !== 'string') throw new Error('Packet after submitAnswer invalid');
  sb.pushCloudSync(false);
  sb.advanceNext(false);
}
const stageHtml = Object.values(els).map(e => e.innerHTML || '').join('');
if (stageHtml.length < 200) {
  throw new Error('Smoke check failed: tutor stage did not render!');
}
"""
    subprocess.run(["node", "-e", smoke_js, HTML_PATH], check=True)

sw_path = os.path.join(BASE_DIR, "sw.js")
if os.path.exists(sw_path):
    with open(sw_path, encoding="utf-8") as sf:
        sw_src = sf.read()
    manifest_sig = hashlib.sha256(
        json.dumps(audio_manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:8]
    prefs_sig = hashlib.sha256(
        json.dumps({k: v for k, v in MEMORY_PREFS.items() if k != "generated_at"}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:6]
    html_sig = hashlib.sha256(final_html.encode("utf-8")).hexdigest()[:8]
    new_stamp = f'{plan_date_str}_{radio_meta.get("script_sig", "")}_{manifest_sig}_{prefs_sig}_{html_sig}'
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
