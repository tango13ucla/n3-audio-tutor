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
from phrase_and_word_lexicon import PHRASE_AND_WORD_LEXICON
from radio_dialogue_bank import MODALITY_MAP
from sentence_lexicon import SENTENCE_LEXICON
from tutor_data import KANA_ADVERBS_36, TUTOR_ITEMS, WORD_DICT
from vocab_cards import (
    HAS_KANJI_RE,
    VOCAB_CARDS,
    analyze_kanji_reading_trap,
    build_dynamic_vocab_card,
    build_vocab_audio_spec,
    get_pronunciation_mnemonic,
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

# Exclude only non-idiomatic demonstrative/adjective combinations; keep ALL real phrases & collocations!
DROP_MULTIWORD_PHRASES = {
    "あの二人", "この本", "小さな子ども", "大きな声", "強い風", "急な仕事", "親切な人",
}

word_audio_map = audio_manifest.get("words", {})
merged_raw_words = {}
for src_dict in (SENTENCE_LEXICON, WORD_DICT, EXTRA_WORDS, PHRASE_AND_WORD_LEXICON):
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
    mn = get_pronunciation_mnemonic(surf, str(entry.get("head") or ""))
    if mn:
        entry["mnemonic"] = mn
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
try:
    from weak_expansion_wave3 import WAVE3_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE3_LISTENING_OPT_NOTES)
except Exception:
    pass
try:
    from weak_expansion_wave4 import WAVE4_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE4_LISTENING_OPT_NOTES)
except Exception:
    pass
try:
    from weak_expansion_wave5 import WAVE5_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE5_LISTENING_OPT_NOTES)
except Exception:
    pass
try:
    from weak_expansion_wave6 import WAVE6_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE6_LISTENING_OPT_NOTES)
except Exception:
    pass
try:
    from weak_expansion_wave8 import WAVE8_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE8_LISTENING_OPT_NOTES)
except Exception:
    pass
try:
    from weak_expansion_wave9 import WAVE9_LISTENING_OPT_NOTES
    LISTENING_OPT_NOTES.update(WAVE9_LISTENING_OPT_NOTES)
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


def resolve_point_streak(point_key: str) -> int:
    for sm in (g_state_map, h_state_map, v_state_map, l_state_map):
        if point_key in sm:
            val = sm[point_key].get("streak")
            if val is not None:
                return int(val)
            return 3 if sm[point_key].get("status") == "green" else 0
    return 0


RECENT_GENERIC_LABELS = {"口语听辨", "高频假名副词", "核心词汇", "语法", "活用"}
recent_weak_keys = set()
log_path = os.path.join(BASE_DIR, "practice_log.jsonl")
if os.path.exists(log_path):
    try:
        _latest_outcome_by_key = {}
        with open(log_path, encoding="utf-8") as lf:
            for ln in [x.strip() for x in lf if x.strip()][-200:]:
                rec = json.loads(ln)
                rec_qid = str(rec.get("id", "")).strip()
                if not rec_qid or rec_qid.startswith(("LK:", "VC-")):
                    continue
                is_miss = (
                    str(rec.get("correct", "")).lower() == "false"
                    or str(rec.get("ask_again", "")).lower() == "true"
                    or str(rec.get("choice", "")).strip() == "不确定"
                )
                pt_lbl = str(rec.get("point", "")).strip()
                _latest_outcome_by_key[rec_qid] = is_miss
                if pt_lbl and pt_lbl not in RECENT_GENERIC_LABELS:
                    _latest_outcome_by_key[pt_lbl] = is_miss
        for _k, _was_miss in _latest_outcome_by_key.items():
            if _was_miss:
                recent_weak_keys.add(_k)
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
    if status != "green":
        if (qid and qid in recent_weak_keys) or (point_key and point_key in recent_weak_keys):
            base += 0.35
        if (qid and qid in MEMORY_FOCUS) or (point_key and point_key in MEMORY_FOCUS):
            base += 0.28
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
            "listen_parts": meta.get("listen_parts"),
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
            "listen_parts": meta.get("listen_parts"),
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
            "listen_parts": meta.get("listen_parts"),
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

answered_today_ids = set()
for cid in list(clean_green_at.keys()) + list(clean_retest_at.keys()):
    answered_today_ids.add(card_to_base.get(cid, cid))
for cid, s_arr in (seeded_day.get("sched") or {}).items():
    if isinstance(s_arr, list) and ((s_arr[0] if len(s_arr) > 0 else 0) > 0 or (s_arr[2] if len(s_arr) > 2 else 0) > 0):
        answered_today_ids.add(card_to_base.get(cid, cid))

prev_day_touched_ids = set()
prev_day_seen_cards = set()
ever_seen_order = {}
last_practiced_day_by_base = {}
_seen_seq = 0
try:
    import datetime as _dt_mod
    from zoneinfo import ZoneInfo as _ZoneInfo
    _pt_tz = _ZoneInfo("America/Los_Angeles")
    _plan_day_ord = _dt_mod.date.fromisoformat(plan_date_str[:10]).toordinal()
except Exception:
    import datetime as _dt_mod
    _pt_tz = _dt_mod.timezone(_dt_mod.timedelta(hours=-8))
    _plan_day_ord = 1

try:
    all_snap_dates = sorted(d for d in (cloud_snap.get("dates") or {}).keys() if d < plan_date_str)
    for _sd in all_snap_dates:
        _day_obj = (cloud_snap.get("dates") or {}).get(_sd) or {}
        _day_pairs = []
        for _cid, _ts in (_day_obj.get("greenAt") or {}).items():
            if int(_ts or 0) >= MIN_REAL_TS:
                _day_pairs.append((int(_ts), _cid))
        for _cid, _ts in (_day_obj.get("retestAt") or {}).items():
            if int(_ts or 0) >= MIN_REAL_TS:
                _day_pairs.append((int(_ts), _cid))
        _day_pairs.sort()
        for _, _cid in _day_pairs:
            _seen_seq += 1
            ever_seen_order[_cid] = _seen_seq
            _bid = card_to_base.get(_cid, _cid)
            if _sd > last_practiced_day_by_base.get(_bid, ""):
                last_practiced_day_by_base[_bid] = _sd
    if all_snap_dates:
        prev_day_obj = (cloud_snap.get("dates") or {}).get(all_snap_dates[-1]) or {}
        for cid in list((prev_day_obj.get("greenAt") or {}).keys()) + list((prev_day_obj.get("retestAt") or {}).keys()):
            prev_day_seen_cards.add(cid)
            prev_day_touched_ids.add(card_to_base.get(cid, cid))
except Exception:
    pass

try:
    _plog_path = os.path.join(BASE_DIR, "practice_log.jsonl")
    if os.path.exists(_plog_path):
        _plog_by_day = {}
        with open(_plog_path, encoding="utf-8") as _pf:
            for _line in _pf:
                _line = _line.strip()
                if not _line:
                    continue
                try:
                    _ev = json.loads(_line)
                except Exception:
                    continue
                _cid = str(_ev.get("id") or "").strip()
                if not _cid or _cid.startswith(("VC-", "LK:", "GROK-")):
                    continue
                _ts_raw = str(_ev.get("ts") or "").strip()
                _sday = ""
                if _ts_raw:
                    try:
                        _dt_utc = _dt_mod.datetime.fromisoformat(_ts_raw.replace("Z", "+00:00"))
                        _sday = (_dt_utc.astimezone(_pt_tz) - _dt_mod.timedelta(hours=4)).strftime("%Y-%m-%d")
                    except Exception:
                        _sday = _ts_raw[:10]
                if _sday and _sday < plan_date_str:
                    _plog_by_day.setdefault(_sday, []).append(_cid)
                    _seen_seq += 1
                    ever_seen_order[_cid] = _seen_seq
                    _bid = card_to_base.get(_cid, _cid)
                    if _sday > last_practiced_day_by_base.get(_bid, ""):
                        last_practiced_day_by_base[_bid] = _sday
        if _plog_by_day:
            _latest_plog_day = sorted(_plog_by_day.keys())[-1]
            for _cid in _plog_by_day[_latest_plog_day]:
                prev_day_seen_cards.add(_cid)
                prev_day_touched_ids.add(card_to_base.get(_cid, _cid))
except Exception:
    pass


locked_same_day_ids = []
if os.path.exists(HTML_PATH) and os.environ.get("FORCE_REDECK") != "1":
    try:
        with open(HTML_PATH, encoding="utf-8") as _ef:
            _ehtml = _ef.read()
        _em = re.search(r"const DATA = (\{.*?\});\n", _ehtml)
        if _em:
            _edata = json.loads(_em.group(1))
            if _edata.get("plan_date") == plan_date_str and len(_edata.get("points") or []) == DECK_CAP:
                locked_same_day_ids = [str(_ep["id"]) for _ep in _edata["points"] if _ep.get("id")]
    except Exception:
        locked_same_day_ids = []


def _days_since_last(qid: str) -> int:
    ld = last_practiced_day_by_base.get(qid, "")
    if not ld:
        return 999
    try:
        return max(1, _plan_day_ord - _dt_mod.date.fromisoformat(ld[:10]).toordinal())
    except Exception:
        return 2


try:
    _exam_date_str = str(MEMORY_PREFS.get("exam_date") or "2026-12-06")
    _days_to_exam = max(0, (_dt_mod.date.fromisoformat(_exam_date_str) - _dt_mod.date.fromisoformat(plan_date_str[:10])).days)
except Exception:
    _days_to_exam = 14


_hesitant_points = set((live_state.get("hesitant_points") or {}).keys())
_radio_relearn_points = set((live_state.get("radio_relearn_queue") or {}).keys())


def _is_active_miss(p: dict) -> bool:
    st = resolve_point_status(p["point_key"])
    qid = p["id"]
    pk = p["point_key"]
    if pk in _radio_relearn_points or qid in _radio_relearn_points:
        return True
    if st == "green":
        return False
    if st in ("red", "orange"):
        return True
    return (qid in recent_weak_keys) or (pk in recent_weak_keys)


def _expanding_min_gap(streak: int, is_hesitant: bool) -> int:
    """FSRS/Cepeda/Nakata expanding spacing gap scaled to exam horizon & automaticity."""
    if _days_to_exam <= 4:
        return 1
    if streak >= 2:
        base = 4 if _days_to_exam > 10 else 3
        return max(2, base - 1) if is_hesitant else base
    if streak == 1:
        return 1 if is_hesitant else 2
    return 1


def _spaced_wave_key(p: dict, allow_miss_top: bool = True):
    qid = p["id"]
    pk = p["point_key"]
    st = resolve_point_status(pk)
    streak = resolve_point_streak(pk)
    dsl = _days_since_last(qid)
    is_miss = _is_active_miss(p)
    is_hesitant = (pk in _hesitant_points) or (qid in _hesitant_points)
    in_focus = 1 if (qid in MEMORY_FOCUS or pk in MEMORY_FOCUS) else 0
    g_obj = g_state_map.get(pk) or {}
    ga_verdict = str(g_obj.get("audit_verdict") or "")
    if st == "green":
        return (5, -dsl, -p["exam_weight"], qid)
    if ga_verdict in ("blank", "weak") and allow_miss_top:
        # Spectrum 1 (陌生): absolute P0 priority — teach first then quiz!
        return (0, -(p["roi_score"] + 0.6), -p["exam_weight"], qid)
    if (is_miss or ga_verdict == "confuse") and allow_miss_top:
        # Spectrum 2 (易混) or recent miss: contrast quiz battle!
        return (0, -(p["roi_score"] + (0.35 if ga_verdict == "confuse" else 0.0)), -p["exam_weight"], qid)
    if ga_verdict == "passive" and dsl >= 1:
        # Spectrum 3 (看懂): streak=2, single clean quiz verification turns True Green!
        return (1, -p["exam_weight"], -1, -p["roi_score"], qid)
    if dsl >= 999:
        # Tier 1: Brand-new unseen syllabus point — rollout systematically by exam ROI!
        return (1, -p["exam_weight"], -in_focus, -p["roi_score"], qid)
    min_gap = _expanding_min_gap(streak, is_hesitant)
    if dsl >= min_gap and not is_miss:
        # Tier 2: Spaced-repetition due (expanding 1d -> 2d -> 3-4d confirmation gap; hesitant points resurface slightly sooner)
        return (2, -dsl, streak, -p["exam_weight"], -in_focus, qid)
    if is_miss:
        # Tier 3: Overflow active misses beyond the 50% per-subject miss cap
        return (3, -p["roi_score"], -p["exam_weight"], qid)
    # Tier 4: Recently practiced yellow — only used when fresh & due are exhausted
    return (4, streak, -p["exam_weight"], -p["roi_score"], qid)


def select_balanced_spaced_deck(candidates: list[dict], cap: int) -> list[dict]:
    by_id = {p["id"]: p for p in candidates}
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    # Step A: Exact same-day deck lock (never reshuffle mid-day once today's cards are generated)
    if locked_same_day_ids:
        for lid in locked_same_day_ids:
            if lid in by_id and lid not in chosen_ids:
                chosen.append(by_id[lid])
                chosen_ids.add(lid)
        if len(chosen) >= cap:
            return chosen[:cap]

    # Step B: Always preserve any card already touched today
    touched_pool = [p for p in candidates if p["id"] in touched_today_ids and p["id"] not in chosen_ids]
    touched_pool.sort(key=lambda p: (-p["roi_score"], -p["exam_weight"], p["id"]))
    for p in touched_pool:
        if len(chosen) >= cap:
            break
        chosen.append(p)
        chosen_ids.add(p["id"])
    if len(chosen) >= cap:
        return chosen[:cap]

    # Step B2 (Green Freshness Maintenance Guard, FSRS DSR / Bjork):
    # Reserve up to 3 silent maintenance slots for 3/3 true-green items unseen for >= 8 days (sprint)
    # or >= 14 days (long-horizon N2), preventing silent pre-exam decay without disturbing today's locked deck.
    if cap >= 25:
        _stale_gap = 8 if _days_to_exam <= 21 else 14
        stale_greens = [
            p for p in candidates
            if p["id"] not in chosen_ids
            and resolve_point_status(p["point_key"]) == "green"
            and _days_since_last(p["id"]) >= _stale_gap
        ]
        stale_greens.sort(key=lambda p: (-_days_since_last(p["id"]), -p["exam_weight"], p["id"]))
        for p in stale_greens[:3]:
            if len(chosen) >= cap:
                break
            chosen.append(p)
            chosen_ids.add(p["id"])

    # Step C: Exam-ROI Balanced Subject Quotas (29G/11L/10H/10V for cap=60, 24G/10L/8H/8V for cap=50)
    remaining_cap = cap - len(chosen)
    if remaining_cap == 60:
        quotas = {"语法": 29, "听力": 11, "活用": 10, "词汇": 10}
    elif remaining_cap == 50:
        quotas = {"语法": 24, "听力": 10, "活用": 8, "词汇": 8}
    else:
        q_g = max(1, round(remaining_cap * 0.48))
        q_l = max(1, round(remaining_cap * 0.20))
        q_h = max(1, round(remaining_cap * 0.16))
        q_v = max(0, remaining_cap - q_g - q_l - q_h)
        quotas = {"语法": q_g, "听力": q_l, "活用": q_h, "词汇": q_v}

    rem_by_subj = {"语法": [], "听力": [], "活用": [], "词汇": []}
    for p in candidates:
        if p["id"] not in chosen_ids:
            rem_by_subj.setdefault(p["subject"], []).append(p)

    # First pass: fill each subject quota using ONLY non-green candidates, capping active misses at 50% of quota
    for subj in ("语法", "听力", "活用", "词汇"):
        q = quotas.get(subj, 0)
        if q <= 0:
            continue
        non_green = [p for p in rem_by_subj.get(subj, []) if resolve_point_status(p["point_key"]) != "green"]
        miss_cap = max(1, q // 2)
        misses = [p for p in non_green if _is_active_miss(p)]
        misses.sort(key=lambda p: _spaced_wave_key(p, allow_miss_top=True))
        picked_subj: list[dict] = []
        picked_ids_subj: set[str] = set()
        for p in misses[:miss_cap]:
            picked_subj.append(p)
            picked_ids_subj.add(p["id"])
        rest = [p for p in non_green if p["id"] not in picked_ids_subj]
        rest.sort(key=lambda p: _spaced_wave_key(p, allow_miss_top=False))
        for p in rest:
            if len(picked_subj) >= q:
                break
            picked_subj.append(p)
            picked_ids_subj.add(p["id"])
        for p in picked_subj:
            chosen.append(p)
            chosen_ids.add(p["id"])

    # Second pass: automatic spillover across all remaining non-green candidates (e.g. once Vocab/Listening graduate!)
    if len(chosen) < cap:
        spill_non_green = [
            p for p in candidates
            if p["id"] not in chosen_ids and resolve_point_status(p["point_key"]) != "green"
        ]
        spill_non_green.sort(key=lambda p: _spaced_wave_key(p, allow_miss_top=True))
        for p in spill_non_green:
            if len(chosen) >= cap:
                break
            chosen.append(p)
            chosen_ids.add(p["id"])

    # Third pass: only if entire syllabus non-green pool < cap, fill remaining with oldest green review cards
    if len(chosen) < cap:
        greens = [p for p in candidates if p["id"] not in chosen_ids]
        greens.sort(key=lambda p: _spaced_wave_key(p, allow_miss_top=False))
        for p in greens:
            if len(chosen) >= cap:
                break
            chosen.append(p)
            chosen_ids.add(p["id"])

    return chosen[:cap]


# Preserve complete 156-point grammar card metadata BEFORE slicing today's deck to DECK_CAP!
all_grammar_cards_by_key = {}
for _gp_card in raw_points:
    if _gp_card.get("subject") == "语法" and _gp_card.get("point_key"):
        all_grammar_cards_by_key.setdefault(_gp_card["point_key"], _gp_card)

DECK_CAP = tutor_prefs.deck_cap(MEMORY_PREFS, day=plan_date_str)
raw_points = select_balanced_spaced_deck(raw_points, DECK_CAP)

# Cross-day fresh sentence rotation: if a point was NOT yet touched today and has variants,
# never show a sentence answered yesterday when an unseen or older variant is available!
for _p in raw_points:
    _qid = _p["id"]
    _vars = list(_p.get("variants") or [])
    if _qid in answered_today_ids or not _vars:
        continue
    _prim_id = _p["primary"]["id"]
    if _prim_id in prev_day_seen_cards or _qid in prev_day_touched_ids or _prim_id in ever_seen_order:
        _all_cards = [_p["primary"]] + _vars
        _unseen = [_c for _c in _all_cards if _c["id"] not in prev_day_seen_cards and _c["id"] not in ever_seen_order]
        if _unseen:
            _new_prim = _unseen[_plan_day_ord % len(_unseen)]
        else:
            _not_prev = [_c for _c in _all_cards if _c["id"] not in prev_day_seen_cards]
            if _not_prev:
                _not_prev.sort(key=lambda _c: (ever_seen_order.get(_c["id"], -1), _c["id"]))
                _new_prim = _not_prev[0]
            else:
                _others = [_c for _c in _all_cards if _c["id"] != _prim_id] or _all_cards
                _others.sort(key=lambda _c: (ever_seen_order.get(_c["id"], -1), _c["id"]))
                _new_prim = _others[0]
        if _new_prim["id"] != _prim_id:
            _p["primary"] = _new_prim
            _p["variants"] = [_c for _c in _all_cards if _c["id"] != _new_prim["id"]]
            if _p.get("teach"):
                _p["teach"]["example_ja"] = _new_prim.get("full_ja") or _p["teach"].get("example_ja", "")
                _p["teach"]["zh_meaning"] = _new_prim.get("zh_meaning") or _p["teach"].get("zh_meaning", "")
                _p["teach"]["audio"] = _new_prim.get("exp_audio") or _p["teach"].get("audio", "")

buckets = {"语法": [], "活用": [], "词汇": [], "听力": []}
for p in raw_points:
    g_st_ref = g_state_map.get(p.get("point_key", "")) or {}
    if p["subject"] == "语法" and g_st_ref.get("audit_verdict") in ("blank", "weak"):
        p["teach_first"] = True
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
    raw_streak = p_obj.get("streak")
    if status == "gray" or (raw_streak is not None and int(raw_streak) == 0):
        return "wip", "wip0", 0
    s = 2 if int(raw_streak or 1) >= 2 else 1
    ok_d = str(p_obj.get("last_ok_date") or "20261114").replace("-", "")[:8] or "20261114"
    return "wip", f"wip{s}:{ok_d}", s


def clean_grammar_family_cn(raw_fam: str) -> str:
    s = re.sub(r"^\d+\.\s*", "", str(raw_fam or "")).strip()
    mapping = {
        "授受・敬語・依頼": "授受与敬语",
        "授受・敬語・使役": "授受与敬语",
        "時間・局面・順序": "时间与局面",
        "時間・進行・瞬間": "时间与局面",
        "判断・推量・道理・決定": "判断与推量",
        "逆接・対比・基準外": "逆接与对比",
        "変化・比例・習慣化": "变化与比例",
        "原因・理由・根拠": "原因与依据",
        "原因・理由・結果": "原因与依据",
        "限定・強調・添加": "限定与递进",
        "否定・強調・限定": "限定与递进",
        "伝聞・様態・傾向": "传闻与倾向",
        "アスペクト・感情強制・否定呼応": "状态与情感",
        "対象・立場・条件・その他": "对象与条件",
    }
    return mapping.get(s, s or "核心语法")


def clean_grammar_front_name(nm: str) -> str:
    """Strip parenthetical meaning/usage spoilers like （経験）, （忠告）, （原因）, （目的）, （伝聞）
    for blind front-of-card recall, while preserving pure kana optional particle markers like （に）."""
    s = str(nm or "").strip()
    s = re.sub(r"[（(](?![ぁ-んァ-ヶー]+[）)])[^）)]*[）)]", "", s).strip()
    if s == "そうだ":
        s = "〜そうだ"
    return s or str(nm or "").strip()


def _norm_last_date(p_obj: dict, qid: str) -> str:
    raw = str(p_obj.get("last_ok_date") or p_obj.get("last_ng_date") or last_practiced_day_by_base.get(qid, "") or "")
    return raw.replace("-", "")[:8]


GA_MEANING_CLEAN_MAP = {
    "G-010": "期间持续（あいだ）／期间某时点（あいだに）",
    "G-003": "只好、别无选择",
    "G-004": "做了之后才第一次领悟",
    "G-009": "时隔……（再次）",
    "G-012": "做完……之后再；在……方面",
    "G-014": "代替；作为交换",
    "G-002": "动不动就、往往（多指负面）",
    "G-021": "只要……就",
    "G-022": "像……；动不动就",
    "G-045": "彻底做完／无法做完",
    "G-049": "一……就立即",
    "G-051": "没做……就（书面 〜ないで）",
    "G-062": "做完了／不小心（〜てしまう 口语）",
    "G-077": "因……而异、视情况不同",
    "G-090": "越来越（多往坏处发展）",
    "G-100": "很有……的样子；听说・似乎",
    "G-111": "（性质上）适合……",
    "G-131": "装作……",
    "G-133": "试图、刚要……",
    "G-134": "听说……",
    "GX-09": "没必要、用不着",
}

GA_ATOMIC_SPLITS = {
    "G-116": [
        ("G-116a", "いらっしゃる", "去・来・在（尊敬语）", "「行く・来る・いる」尊敬形，自己用参る", "社長は先ほど会議室へいらっしゃいました。", "社长刚才已经去会议室了。", "K-001"),
        ("G-116b", "召し上がる", "吃・喝（尊敬语）", "「食べる・飲む」尊敬形，自己用いただく", "どうぞ温かいうちに召し上がってください。", "请趁热享用。", "K-003"),
        ("G-116c", "おっしゃる", "说（尊敬语）", "「言う」尊敬形，ます形为おっしゃいます", "先生のおっしゃる通りだと思います。", "我觉得正如老师所说。", "K-002"),
        ("G-116d", "ご覧になる", "看（尊敬语）", "「見る」尊敬形，自己看用拝見する", "こちらの資料をもうご覧になりましたか。", "这份资料您已经看过了吗？", "K-004"),
        ("G-116e", "なさる", "做（尊敬语）", "「する」尊敬形，ます形为なさいます", "先生は今、日本の歴史をご研究なさっています。", "老师现在正在研究日本历史。", "K-005"),
        ("G-116f", "ご存じだ", "知道・认识（尊敬语）", "「知っている」尊敬形，自己用存じる", "こちらの鈴木様をご存じですか。", "您认识这位铃木先生吗？", "K-008"),
    ],
    "G-119": [
        ("G-119a", "伺う", "听・问・拜访（谦让语）", "向尊长「聞く・行く・訪ねる」", "明日の午後、御社に伺います。", "明天下午我去贵公司拜访。", "K-014"),
        ("G-119b", "拝見する", "看・拜读（谦让语）", "自己看对方资料，尊长看用ご覧になる", "お送りいただいた資料は、すでに拝見いたしました。", "您发来的资料，我已经拜读过了。", "K-013"),
        ("G-119c", "申す／申し上げる", "说・自称（谦让语）", "自报姓名用申します，禀报用申し上げます", "初めまして、田中と申します。", "初次见面，我叫田中。", "K-011"),
        ("G-119d", "参る", "去・来（谦让语）", "压低自己「行く・来る」，尊长用いらっしゃる", "ただいま担当者が参りますので、少々お待ちください。", "负责人马上就过来，请稍候。", "K-010"),
        ("G-119e", "いただく", "吃・喝・收下（谦让语）", "自己「食べる・飲む・もらう」，尊长用召し上がる", "素敵なお土産をいただき、ありがとうございます。", "非常感谢您送的精美伴手礼。", "K-012"),
        ("G-119f", "いたす", "做（谦让语）", "压低自己「する」，尊长用なさる", "会場の準備は私の方でいたします。", "会场的准备工作由我来做。", "K-016"),
        ("G-119g", "お目にかかる", "见面・拜见（谦让语）", "自己去见尊长的「会う」", "またお目にかかれて、とても嬉しいです。", "能再次见到您，非常高兴。", "K-019"),
        ("G-119h", "存じる／存じ上げる", "知道・认为（谦让语）", "知事用存じる，识人用存じ上げる", "申し訳ありませんが、その件は存じ上げません。", "很抱歉，那件事我不太清楚。", "K-017"),
    ],
    "G-117": [
        ("G-117a", "〜てくださる", "尊长主动为我做", "「〜てくれる」尊敬形，主语是尊长（が）", "お忙しいところ、先生が推薦状を書いてくださった。", "老师在百忙之中替我写了推荐信。", "K-006"),
        ("G-117b", "〜ていただく", "承蒙尊长为我做", "「〜てもらう」谦让形，对象是尊长（に）", "部長に企画書をチェックしていただきました。", "请部长帮我审了企划书。", "K-045"),
        ("G-117c", "〜てさしあげる", "恭敬地为尊长做", "「〜てあげる」谦让形，不当面直接对长辈说", "お世話になった先生に、お礼の手紙を書いて差し上げた。", "给关照过我的老师写了感谢信。", "K-023"),
    ],
    "G-124": [
        ("G-124a", "〜ていく", "由近及远・今后持续变化", "从现在往未来发展，或渐行渐远", "これから日本でもキャッシュレスがますます広がっていくだろう。", "今后在日本无现金支付也会越来越普及吧。", ""),
        ("G-124b", "〜てくる", "由远及近・至今渐渐变化", "从过去持续到现在，或走近・出现", "四月に入ってから、だんだん暖かくなってきた。", "进入四月以来，天气渐渐暖和起来了。", ""),
    ],
    "G-125": [
        ("G-125a", "〜てくれる", "对方主动为我做", "动作指向自己，主语是对方（先輩が）", "困っていたとき、先輩が優しく相談に乗ってくれた。", "我遇到困难时，前辈热心帮我出主意。", ""),
        ("G-125b", "〜てもらう", "我请对方为我做", "主语是自己，受惠对象用「に」（先輩に）", "わからない問題があったので、先輩に解き方を教えてもらった。", "因为有不会的题，我请前辈教了我解法。", ""),
    ],
    "G-098": [
        ("G-098a", "〜やすい", "容易做……", "动词ます干＋やすい，表顺手或易发生", "この辞書は文字が大きくて、とても使いやすい。", "这本词典字很大，非常好用。", ""),
        ("G-098b", "〜にくい", "难以做……", "动词ます干＋にくい，偏物理客观不便", "この靴は底が硬くて、長時間歩きにくい。", "这双鞋鞋底很硬，走久了不舒服。", ""),
    ],
}


def _ga_audio_url_for_sub(sub_gid: str, fallback_aud: str) -> str:
    fname = f"GA-{sub_gid}_ex.mp3"
    fpath = os.path.join(BASE_DIR, "audio", fname)
    if os.path.exists(fpath):
        with open(fpath, "rb") as af:
            h8 = hashlib.md5(af.read()).hexdigest()[:8]
        return f"./audio/{fname}?v={h8}"
    return fallback_aud


def _clean_ga_meaning(gid: str, raw: str) -> str:
    if gid in GA_MEANING_CLEAN_MAP:
        return GA_MEANING_CLEAN_MAP[gid]
    s = clean_zen_text(raw or "")
    s = s.replace(";", "；").replace(",", "，")
    s = re.sub(r"\(([^)]*)\)", r"（\1）", s)
    return s.strip()


grammar_items = []
grammar_audit_items = []
ga_split_map = {}
_ga_vmap = {"blank": 1, "weak": 1, "confuse": 2, "fuzzy": 2, "passive": 3, "instinct": 4, "solid": 4}
for g_idx, p in enumerate(live_state.get("grammar_points", [])):
    nm = p.get("name", "")
    gid = p.get("id", f"G-{g_idx + 1:03d}")
    tier, mstate, streak = norm_tier_meta(p)
    ok_d = str(p.get("last_ok_date") or "")
    ng_d = str(p.get("last_ng_date") or "")
    nov_tested = ok_d.startswith("202611") or ng_d.startswith("202611")
    fam_clean = clean_grammar_family_cn(p.get("family", ""))
    card_ref = all_grammar_cards_by_key.get(nm) or {}
    prim_ref = card_ref.get("primary") or {}
    teach_ref = card_ref.get("teach") or {}
    ex_ja = str(prim_ref.get("full_ja") or teach_ref.get("example_ja") or "").strip()
    ex_zh = str(prim_ref.get("zh_meaning") or teach_ref.get("zh_meaning") or "").strip()
    rule_txt = clean_zen_text(prim_ref.get("form_line") or prim_ref.get("why_line") or p.get("exam_alert") or p.get("note") or "")
    if len(rule_txt) > 96:
        rule_txt = rule_txt[:95].rstrip("，、； ") + "…"
    exp_aud = str(prim_ref.get("exp_audio") or teach_ref.get("audio") or "")
    meaning_clean = _clean_ga_meaning(gid, p.get("meaning", ""))
    verdict_raw = str(p.get("audit_verdict") or "")
    verdict_code = _ga_vmap.get(verdict_raw, 0)
    g_pid = point_id_by_key.get(nm, "")

    grammar_items.append({
        "gid": gid,
        "key": nm,
        "name": nm,
        "sub": meaning_clean,
        "family": fam_clean,
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "last_date": _norm_last_date(p, g_pid),
        "hesitant": bool(nm in _hesitant_points or g_pid in _hesitant_points),
        "nov_tested": nov_tested,
        "audit_code": verdict_code,
        "point_id": g_pid,
        "note": clean_zen_text(p.get("exam_alert") or p.get("note", "")),
    })

    # Blind-Spot-First priority group for atomic 1-by-1 Grammar Self-Audit:
    st_raw = p.get("status", "yellow")
    if st_raw == "green" and not nov_tested:
        pri_grp = 0
    elif st_raw in ("red", "orange"):
        pri_grp = 1
    elif not nov_tested:
        pri_grp = 2
    elif st_raw == "yellow" and streak <= 1:
        pri_grp = 3
    elif st_raw == "yellow":
        pri_grp = 4
    else:
        pri_grp = 5

    if gid in GA_ATOMIC_SPLITS:
        sub_audits = p.get("sub_audits") or {}
        child_gids = []
        for s_gid, s_name, s_meaning, s_rule, s_ex_ja, s_ex_zh, s_hk in GA_ATOMIC_SPLITS[gid]:
            child_gids.append(s_gid)
            s_rec = sub_audits.get(s_gid) or {}
            s_code = int(s_rec.get("code") or _ga_vmap.get(str(s_rec.get("verdict") or ""), 0))
            s_ts = int(s_rec.get("ts") or 0)
            s_date = str(s_rec.get("date") or "")
            grammar_audit_items.append({
                "gid": s_gid,
                "parent_gid": gid,
                "parent_name": nm,
                "henkei_key": s_hk,
                "name": s_name,
                "front_name": clean_grammar_front_name(s_name),
                "meaning": clean_zen_text(s_meaning),
                "family": fam_clean,
                "rule": clean_zen_text(s_rule),
                "ex_ja": s_ex_ja,
                "ex_zh": s_ex_zh,
                "audio": _ga_audio_url_for_sub(s_gid, exp_aud),
                "sys_tier": tier,
                "sys_streak": streak,
                "nov_tested": nov_tested,
                "pri": pri_grp,
                "verdict": s_code,
                "audit_ts": s_ts,
                "audit_date": s_date,
            })
        ga_split_map[gid] = child_gids
    else:
        grammar_audit_items.append({
            "gid": gid,
            "name": nm,
            "front_name": clean_grammar_front_name(nm),
            "meaning": meaning_clean,
            "family": fam_clean,
            "rule": rule_txt,
            "ex_ja": ex_ja,
            "ex_zh": ex_zh,
            "audio": exp_aud,
            "sys_tier": tier,
            "sys_streak": streak,
            "nov_tested": nov_tested,
            "pri": pri_grp,
            "verdict": verdict_code,
            "audit_ts": int(p.get("audit_ts") or 0),
            "audit_date": str(p.get("audit_date") or ""),
        })

_ga_front_counts = {}
for _it in grammar_audit_items:
    _fn = _it["front_name"]
    _ga_front_counts[_fn] = _ga_front_counts.get(_fn, 0) + 1
_ga_front_seen = {}
_ga_circled = ["①", "②", "③", "④", "⑤"]
for _it in grammar_audit_items:
    _fn = _it["front_name"]
    if _ga_front_counts.get(_fn, 0) > 1:
        _idx = _ga_front_seen.get(_fn, 0)
        _ga_front_seen[_fn] = _idx + 1
        _tag = _ga_circled[_idx] if _idx < len(_ga_circled) else str(_idx + 1)
        _it["front_name"] = f"{_fn} {_tag}"

grammar_audit_items.sort(key=lambda x: (x["pri"], x["family"], x["gid"]))

henkei_items = []
for p in live_state.get("henkei_points", []):
    if p.get("tier") == "basic_n5n4" and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    tier, mstate, streak = norm_tier_meta(p)
    h_pid = point_id_by_key.get(pid, "")
    henkei_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("example", ""),
        "family": re.sub(r"^\d+(?:\.\d+)?\s*", "", p.get("subcategory") or p.get("category", "")),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "last_date": _norm_last_date(p, h_pid),
        "hesitant": bool(pid in _hesitant_points or p.get("name", "") in _hesitant_points or h_pid in _hesitant_points),
        "point_id": h_pid,
        "note": clean_zen_text(p.get("note", "")),
    })

listening_items = []
for p in live_state.get("listening_points", []):
    if not p.get("is_core165") and p.get("status") == "gray":
        continue
    pid = p.get("id", "")
    tier, mstate, streak = norm_tier_meta(p)
    l_pid = point_id_by_key.get(pid, "")
    listening_items.append({
        "key": pid,
        "name": p.get("name", ""),
        "sub": p.get("meaning", "") or p.get("full", ""),
        "family": p.get("category", ""),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "last_date": _norm_last_date(p, l_pid),
        "hesitant": bool(pid in _hesitant_points or p.get("name", "") in _hesitant_points or l_pid in _hesitant_points),
        "point_id": l_pid,
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
    mn_txt = clean_zen_text(vc_spec.get("mnemonic") or get_pronunciation_mnemonic(w, str(w_info.get("head") or "")))
    base_note = clean_zen_text(vc_spec.get("twin") or w_info.get("tip") or p.get("classroom_note") or "")
    combined_note = " · ".join(x for x in ([f"记音：{mn_txt}"] if mn_txt else []) + ([base_note] if base_note else []))
    meaning_short = w_info.get("zh") or (vc_spec.get("zh", "").split(" · ")[0]) or re.sub(r"^\d+\.\s*", "", p.get("category", ""))
    v_pid = point_id_by_key.get(w, "")
    vocab_items.append({
        "key": w,
        "name": w,
        "sub": meaning_short,
        "family": re.sub(r"^\d+\.\s*", "", p.get("category", "")),
        "tier": tier,
        "mstate": mstate,
        "streak": streak,
        "last_date": _norm_last_date(p, v_pid),
        "hesitant": bool(w in _hesitant_points or v_pid in _hesitant_points),
        "point_id": v_pid,
        "audio": resolve_word_audio(w),
        "note": combined_note,
    })

for kw, pitch, desc in CORE_N3_KANA_VOCAB:
    if kw in seen_vocab_words:
        continue
    seen_vocab_words.add(kw)
    vc_spec = VOCAB_CARDS.get(kw, {})
    mn_txt = clean_zen_text(vc_spec.get("mnemonic") or get_pronunciation_mnemonic(kw))
    base_note = clean_zen_text(vc_spec.get("twin") or f"声调 {pitch} · {desc}")
    combined_note = " · ".join(x for x in ([f"记音：{mn_txt}"] if mn_txt else []) + ([base_note] if base_note else []))
    kw_pid = point_id_by_key.get(kw, "")
    vocab_items.append({
        "key": kw,
        "name": kw,
        "sub": desc.split("（")[0],
        "family": "高频假名副词",
        "tier": "wip",
        "mstate": "wip0",
        "streak": 0,
        "last_date": _norm_last_date({}, kw_pid),
        "hesitant": bool(kw in _hesitant_points or kw_pid in _hesitant_points),
        "point_id": kw_pid,
        "audio": resolve_word_audio(kw),
        "note": combined_note,
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
    hook_aud = vc_aud.get("hook") or ""
    clean_aud = vc_aud.get("clean") or ""
    aspec = build_vocab_audio_spec(spec)
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
        "mnemonic": spec.get("mnemonic") or get_pronunciation_mnemonic(vw, str((rich_words.get(vw) or {}).get("head") or "")),
        "zh_speak": spec.get("zh_speak", ""),
        "hook_spoken": aspec.get("hook_spoken", ""),
        "reveal_spoken": aspec.get("reveal_spoken", ""),
        "front_audio": front_aud,
        "rev_audio": rev_aud,
        "full_audio": full_aud,
        "hook_audio": hook_aud,
        "clean_audio": clean_aud,
        "word_audio": w_aud,
    }

# Anti-Interference Confusable Twin Graph (Nation 2000; Tinkham 1997; Waring 1997)
CONFUSABLE_VOCAB_GROUPS = [
    ["書類", "種類"],
    ["出張", "主張"],
    ["ぐったり", "ぐっすり"],
    ["だんだん", "どんどん"],
    ["うっかり", "すっかり", "しっかり", "はっきり", "ばったり", "ぴったり", "びっくり", "がっかり", "そっくり"],
    ["わざわざ", "わざと"],
    ["めったに", "なかなか"],
    ["ずいぶん", "だいぶ"],
    ["そろそろ", "もうすぐ"],
    ["あいにく", "せっかく"],
    ["加える", "加わる"],
    ["余る", "残る"],
    ["減る", "増える"],
    ["続く", "続ける"],
    ["さっぱり", "すっきり"],
    ["ほっと", "そっと", "ずっと", "もっと", "きっと", "ちょっと"],
    ["偶然", "突然", "当然", "自然"],
    ["経験", "体験", "実験"],
    ["原因", "理由"],
    ["予定", "予約", "予算", "予想"],
    ["発見", "発明", "発表"],
    ["注意", "注目", "注文"],
]
_twin_sets: dict[str, set[str]] = {}
for _grp in CONFUSABLE_VOCAB_GROUPS:
    for _a in _grp:
        for _b in _grp:
            if _a != _b:
                _twin_sets.setdefault(_a, set()).add(_b)
_known_vc_keys = [k for k in vocab_cards_payload.keys() if len(k) >= 2]
for _vw, _vobj in vocab_cards_payload.items():
    _tw_txt = str(_vobj.get("twin") or "")
    if not _tw_txt:
        continue
    for _other in _known_vc_keys:
        if _other != _vw and _other in _tw_txt:
            _twin_sets.setdefault(_vw, set()).add(_other)
            _twin_sets.setdefault(_other, set()).add(_vw)
vocab_twins_map = {k: sorted(v) for k, v in _twin_sets.items() if v}


def count_tiers(items):
    c = {"todo": 0, "wip": 0, "done": 0}
    for it in items:
        c[it["tier"]] += 1
    c["total"] = len(items)
    return c


mastery_data = {
    "grammar": {"label": "语法", "detail": f"{len(grammar_items)} 核心考点", "exam_pts": 38, "counts": count_tiers(grammar_items), "items": grammar_items},
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
seeded_ga = {
    gk: gv
    for gk, gv in (cloud_snap.get("grammarAudit") or {}).items()
    if isinstance(gv, list) and len(gv) >= 2 and int(gv[1] or 0) >= MIN_REAL_TS
}
recent_weak_words = [
    it["name"]
    for it in vocab_items
    if it["tier"] != "done" and (it["name"] in recent_weak_keys or it["name"] in MEMORY_FOCUS)
]

vocab_base_done = sum(1 for it in vocab_items if it["tier"] == "done")
vocab_daily_count = tutor_prefs.vocab_daily_count(MEMORY_PREFS, day=plan_date_str)
ga_daily_target = tutor_prefs.grammar_audit_daily_count(MEMORY_PREFS, day=plan_date_str)

payload = json.dumps({
    "plan_date": plan_date_str,
    "exam_date": "2026-12-06",
    "days_to_exam": live_state.get("days_left", plan.get("days_to_exam", 21)),
    "done_audio": "./audio/done.mp3",
    "radio": radio_meta,
    "points": ordered_points,
    "words": rich_words,
    "vocab_cards": vocab_cards_payload,
    "vocab_twins": vocab_twins_map,
    "grammar_audit": {
        "active_from": "2026-11-23",
        "daily_target": ga_daily_target,
        "split_map": ga_split_map,
        "items": grammar_audit_items,
    },
    "mastery": mastery_data,
    "vocab_base_done": vocab_base_done,
    "vocab_daily_count": vocab_daily_count,
    "true_green_epoch": TRUE_GREEN_EPOCH,
    "baked_epoch": baked_epoch,
    "recent_weak_words": recent_weak_words,
    "cloud_sync": {
        "ntfy_topic": cloud_cfg.get("ntfy_topic", ""),
        "seeded_day": seeded_day,
        "seeded_overrides": seeded_overrides,
        "seeded_ga": seeded_ga,
    },
}, ensure_ascii=False)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
<meta name="screen-orientation" content="portrait" />
<meta name="x5-orientation" content="portrait" />
<meta name="description" content="JLPT N3 · 做题 · 随身听 · 单手记词 · 体律" />
<meta name="color-scheme" content="light dark" />
<meta name="theme-color" content="#F5F2EB" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#171614" media="(prefers-color-scheme: dark)" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<link rel="manifest" href="./manifest.json" />
<link rel="icon" href="./icon-192.png" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600&family=Noto+Serif+JP:wght@500;600&display=optional" rel="stylesheet" />
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
    --moss-solid: #2D7A56;
    --moss-soft: rgba(43, 95, 73, 0.10);
    --ochre: #B07D3A;
    --bengara: #9E3E36;
    --tap-bg: #EDEAE1;
    --hover-bg: #FFFFFF;
    --soft-bg: #F4F1E8;
    /* Editorial Bilingual Pairing: Japanese Literary Mincho + Clean Chinese Humanist Sans */
    --sans: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Noto Sans CJK SC", -apple-system, BlinkMacSystemFont, sans-serif;
    --serif-jp: "Hiragino Mincho ProN", "YuMincho", "Noto Serif JP", "Noto Serif CJK SC", "Songti SC", serif;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --washi: #171614;
      --sheet: #201F1C;
      --sumi: #EAE5DA;
      --ink-2: #B9B2A5;
      --ink-3: #868074;
      --hairline: rgba(234, 229, 218, 0.09);
      --hairline-strong: rgba(234, 229, 218, 0.21);
      --track: #2F2D28;
      --moss: #62AD89;
      --moss-solid: #3F8B66;
      --moss-soft: rgba(98, 173, 137, 0.14);
      --ochre: #D2A35C;
      --bengara: #D46F66;
      --tap-bg: #2B2925;
      --hover-bg: #272521;
      --soft-bg: #22201D;
    }
  }

  * {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
  }

  html {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    overscroll-behavior: none;
    background: var(--washi);
  }

  body {
    margin: 0;
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
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
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: calc(14px + env(safe-area-inset-top)) 26px max(16px, env(safe-area-inset-bottom));
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
      padding-bottom: max(14px, env(safe-area-inset-bottom));
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
      position: relative;
    }
    .thumb-ink-bar {
      position: absolute;
      top: -1px;
      left: 0;
      width: 18px;
      height: 1.8px;
      background: var(--sumi);
      border-radius: 2px;
      pointer-events: none;
      transition: transform 0.26s cubic-bezier(0.22, 1, 0.36, 1), width 0.26s cubic-bezier(0.22, 1, 0.36, 1);
    }
    .thumb-link {
      position: relative;
      height: 54px;
      min-width: 50px;
      padding: 0 9px;
      font-size: 15px;
      font-weight: 500;
      color: var(--ink-3);
      letter-spacing: 0.04em;
      transition: color 0.2s ease;
    }
    .thumb-link.active {
      color: var(--sumi);
      font-weight: 600;
    }
    .thumb-link.is-playing { color: var(--moss); }
    .thumb-link:active { opacity: 0.6; }
    .zen-panel:not(.hidden) {
      animation: zenModeIn 0.2s cubic-bezier(0.22, 1, 0.36, 1);
    }
    @keyframes zenModeIn {
      from { opacity: 0.35; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .ledger-back-fab { display: none !important; }
    .ledger-scroll { padding-bottom: 24px; }

    .action-dock,
    .radio-dock,
    .vc-dock,
    .rv-dock,
    .ga-spec-wrap {
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

  .choice-veil-wrap {
    position: relative;
  }
  .recall-veil-overlay {
    position: absolute;
    inset: -4px;
    z-index: 4;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border-radius: 10px;
    background: rgba(250, 248, 244, 0.58);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    cursor: pointer;
    text-align: center;
    padding: 16px;
  }
  @media (prefers-color-scheme: dark) {
    .recall-veil-overlay {
      background: rgba(26, 25, 23, 0.58);
    }
  }
  .recall-veil-title {
    font-size: 15.5px;
    font-weight: 600;
    color: var(--sumi);
    letter-spacing: 0.04em;
  }
  .recall-veil-sub {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--moss);
    letter-spacing: 0.04em;
  }
  .choice-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: filter 0.22s ease, opacity 0.22s ease;
  }
  .choice-list.recall-veiled {
    filter: blur(10px);
    opacity: 0.26;
    pointer-events: none;
    user-select: none;
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
  .zen-choice:active { background: var(--tap-bg); }

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
  .listen-num-btn:active { background: var(--tap-bg); }

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
  .unsure-btn:active { background: var(--tap-bg); }

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
    .zen-choice:hover, .listen-num-btn:hover { border-color: var(--sumi); background: var(--hover-bg); }
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
  .res-point-head {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 7px;
    font-size: 13px;
    line-height: 1.48;
    color: var(--moss);
    font-weight: 500;
    letter-spacing: 0.015em;
  }
  .res-point-subj {
    color: var(--ink-3);
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.05em;
    flex-shrink: 0;
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
    background: var(--soft-bg);
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
  .ghost-btn:active, .dock-replay-btn:active { background: var(--tap-bg); }

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

  /* Story Artwork Presentation (Zen Woodblock & Wabi-Sabi Aesthetics) */
  .radio-art-card {
    position: relative;
    width: 100%;
    max-width: 440px;
    height: 140px;
    margin: 2px 0 0;
    border-radius: 8px;
    overflow: hidden;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    transition: transform 0.18s ease, border-color 0.18s ease;
  }
  @media (min-width: 860px) and (min-height: 521px) {
    .radio-art-card { height: 180px; }
  }
  .radio-art-card:active { transform: scale(0.99); }
  .radio-art-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    transition: opacity 0.35s ease;
  }
  .radio-art-meta {
    position: absolute;
    bottom: 8px;
    right: 10px;
    background: rgba(23, 22, 20, 0.76);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    color: #F5F2EB;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    padding: 3px 8px;
    border-radius: 4px;
    pointer-events: none;
  }

  /* Review Story Gallery (End-of-day / Episode Wrap-up) */
  .rv-gallery-wrap {
    margin: 14px 0 10px;
    width: 100%;
  }
  .rv-gallery-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .rv-gallery-overline {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--moss);
    text-transform: uppercase;
  }
  .rv-gallery-scroll {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    width: 100%;
  }
  @media (max-width: 480px) {
    .rv-gallery-scroll {
      display: flex;
      overflow-x: auto;
      scroll-snap-type: x mandatory;
      padding-bottom: 6px;
      -webkit-overflow-scrolling: touch;
    }
  }
  .rv-story-art-card {
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.15s ease, border-color 0.15s ease;
    display: flex;
    flex-direction: column;
  }
  @media (max-width: 480px) {
    .rv-story-art-card {
      flex: 0 0 220px;
      scroll-snap-align: start;
    }
  }
  .rv-story-art-card:active { transform: scale(0.98); }
  .rv-story-art-img-wrap {
    width: 100%;
    height: 105px;
    background: var(--tap-bg);
    overflow: hidden;
  }
  .rv-story-art-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .rv-story-art-body {
    padding: 7px 9px 8px;
  }
  .rv-story-art-title {
    font-family: var(--serif-jp);
    font-size: 13px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rv-story-art-sub {
    font-size: 11px;
    color: var(--ink-2);
    margin-top: 2px;
    line-height: 1.35;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rv-relearn-art-wrap {
    width: 100%;
    max-height: 120px;
    border-radius: 6px;
    overflow: hidden;
    margin: 4px 0 8px;
    border: 1px solid var(--hairline-strong);
  }
  .rv-relearn-art-img {
    width: 100%;
    height: 120px;
    object-fit: cover;
    display: block;
  }

  /* Story Modal Presentation */
  .story-modal-box {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 8px;
    background: var(--sheet);
  }
  .story-modal-img-wrap {
    width: 100%;
    max-height: 260px;
    overflow: hidden;
    background: var(--tap-bg);
  }
  .story-modal-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .story-modal-body {
    padding: 16px 18px 18px;
  }
  .story-modal-title {
    margin: 6px 0 4px;
    font-family: var(--serif-jp);
    font-size: 20px;
    font-weight: 600;
    color: var(--sumi);
  }
  .story-modal-sub {
    margin: 0;
    font-size: 14px;
    color: var(--ink-2);
    line-height: 1.6;
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
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .step-time-btn:active, .radio-spd-pill:active { background: var(--tap-bg); }
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
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .play-toggle-btn:active { opacity: 0.84; transform: scale(0.985); }

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
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .chap-link.active {
    color: var(--sumi);
    background: rgba(28, 27, 24, 0.05);
    font-weight: 600;
  }
  .chap-sep {
    width: 1px;
    height: 14px;
    background: var(--hairline-strong);
    flex-shrink: 0;
    margin: 0 2px;
  }
  .chap-link.chap-review {
    color: var(--ink-2);
    font-weight: 500;
  }
  .chap-link.chap-review.is-ready {
    color: var(--moss);
    background: var(--moss-soft);
    font-weight: 600;
  }
  .chap-link.chap-review.is-done {
    color: var(--moss);
    opacity: 0.72;
  }

  /* ================= 4B. POST-LISTENING 5-MIN CONTEXTUAL REVIEW ("听后复盘" 收尾小节) ================= */
  .rv-finish-strip {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 11px 14px;
    margin-bottom: 10px;
    border-radius: 8px;
    border: 1px solid rgba(43, 95, 73, 0.28);
    background: var(--moss-soft);
    color: var(--sumi);
    font-size: 13px;
    line-height: 1.4;
    text-align: left;
    transition: opacity 0.16s ease;
  }
  .rv-finish-strip:active { opacity: 0.72; }
  .rv-finish-go {
    flex-shrink: 0;
    color: var(--moss);
    font-weight: 600;
    white-space: nowrap;
  }

  #radio-player-stage.hidden,
  #radio-review-stage.hidden { display: none !important; }
  #radio-player-stage,
  #radio-review-stage {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .rv-stage-card {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    scrollbar-width: none;
    touch-action: pan-y;
    will-change: transform, opacity;
  }
  .rv-stage-card::-webkit-scrollbar { display: none; }
  .rv-stage-card.settling { transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease; }
  .rv-stage-card.fly-right { transition: transform 0.22s ease-in, opacity 0.2s ease-in; transform: translate3d(115%, -14px, 0) rotate(9deg) !important; opacity: 0 !important; }
  .rv-stage-card.fly-left { transition: transform 0.22s ease-in, opacity 0.2s ease-in; transform: translate3d(-115%, -14px, 0) rotate(-9deg) !important; opacity: 0 !important; }

  .rv-focal {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding: clamp(16px, 3.5vh, 28px) 0 14px;
    gap: 14px;
  }
  .rv-focal.is-relearn {
    justify-content: flex-start;
    padding-top: 12px;
    gap: 12px;
  }
  .rv-story-tag {
    font-size: 13px;
    font-weight: 500;
    color: var(--moss);
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rv-n2-dot {
    color: var(--bengara);
    font-weight: 600;
  }
  .rv-head {
    margin: 0;
    font-family: var(--serif-jp);
    font-size: 32px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.35;
    letter-spacing: 0.02em;
  }
  .rv-cue-line {
    margin: 0;
    font-size: 15px;
    color: var(--ink-3);
    line-height: 1.65;
  }
  .rv-clip-row {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    margin-top: 2px;
  }
  .rv-clip-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 0;
    background: transparent;
    border: none;
    font-size: 14.5px;
    font-weight: 500;
    color: var(--moss);
    letter-spacing: 0.04em;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .rv-clip-btn.playing {
    color: var(--bengara);
    font-weight: 600;
    animation: rvAudioPulse 1.2s ease-in-out infinite;
  }
  @keyframes rvAudioPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
  }
  .rv-clip-btn.quiet { color: var(--ink-3); font-size: 13.5px; }
  .rv-clip-btn:active { opacity: 0.55; }

  .rv-reveal-area {
    margin-top: 4px;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.2s ease, transform 0.2s ease;
    pointer-events: none;
  }
  .rv-reveal-area.shown {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .rv-kana-line {
    font-size: 19px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }
  .rv-zh-line {
    font-size: 18px;
    font-weight: 600;
    color: var(--sumi);
    line-height: 1.5;
    margin-bottom: 8px;
  }
  .rv-quote {
    margin: 0;
    padding-left: 12px;
    border-left: 2px solid var(--hairline-strong);
    font-size: 15.5px;
    line-height: 1.78;
    color: var(--ink-2);
  }
  .rv-quote-spk {
    font-size: 12.5px;
    color: var(--ink-3);
    margin-right: 6px;
    letter-spacing: 0.06em;
  }
  .rv-ja-ex {
    margin: 6px 0 0;
    font-family: var(--serif-jp);
    font-size: 19.5px;
    line-height: 1.7;
    color: var(--sumi);
  }
  .rv-note-line {
    margin: 4px 0 0;
    font-size: 14.5px;
    line-height: 1.72;
    color: var(--ink-2);
  }
  .rv-twin-line {
    margin: 2px 0 0;
    font-size: 13.5px;
    line-height: 1.65;
    color: var(--ink-3);
  }
  .rv-shadow-row {
    margin-top: 6px;
    padding-top: 10px;
    border-top: 1px solid var(--hairline);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .rv-shadow-hint {
    font-size: 13px;
    color: var(--ink-3);
    letter-spacing: 0.03em;
  }
  .rv-tap-hint {
    font-size: 13px;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    margin-top: 2px;
  }
  .rv-dock {
    flex-shrink: 0;
    padding-top: 10px;
    padding-bottom: 16px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
  }
  .rv-btn-relearn {
    height: 48px;
    padding: 0 18px;
    border: 1px solid rgba(154, 70, 51, 0.34);
    border-radius: 8px;
    background: transparent;
    color: var(--bengara);
    font-size: 15px;
    font-weight: 500;
    letter-spacing: 0.04em;
    flex-shrink: 0;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .rv-btn-relearn:active { background: var(--tap-bg); }
  .rv-btn-pass {
    flex: 1;
    max-width: 210px;
    height: 48px;
    padding: 0 20px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.06em;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .rv-btn-pass:active { opacity: 0.84; transform: scale(0.985); }
  .rv-done-list {
    margin: 8px 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    font-size: 15px;
    color: var(--bengara);
    font-family: var(--serif-jp);
  }
  @keyframes micPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
  .mic-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
  }
  .mic-btn.listening {
    color: var(--bengara) !important;
    font-weight: 600;
  }
  .mic-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    display: inline-block;
    animation: micPulse 1.05s ease-in-out infinite;
  }
  .mic-feedback {
    margin-top: 8px;
    font-size: 13.5px;
    line-height: 1.55;
    letter-spacing: 0.02em;
    color: var(--ink-3);
    min-height: 0;
    text-align: center;
  }
  .mic-feedback:empty { display: none; }
  .mic-feedback.ok { color: var(--moss); font-weight: 500; }
  .mic-feedback.ng { color: var(--bengara); font-weight: 500; }
  .mic-feedback.left { text-align: left; margin-top: 6px; }
  .rv-meta-right {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .rv-spk-pill {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 12px;
    font-weight: 500;
    color: var(--moss);
    background: var(--moss-soft);
    border: 1px solid rgba(43, 95, 73, 0.22);
    padding: 2.5px 8px;
    border-radius: 12px;
    line-height: 1.25;
    white-space: nowrap;
    cursor: pointer;
    transition: opacity 0.16s ease, transform 0.16s ease;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .rv-spk-pill:active { opacity: 0.65; transform: scale(0.97); }
  .spk-prompt-ja {
    margin: 2px 0 0;
    font-family: var(--serif-jp);
    font-size: 20px;
    line-height: 1.72;
    color: var(--sumi);
  }
  .spk-prompt-zh {
    margin: 2px 0 0;
    font-size: 14.5px;
    line-height: 1.68;
    color: var(--ink-3);
  }
  .spk-live-area {
    margin-top: 8px;
    padding-top: 14px;
    border-top: 1px solid var(--hairline);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .spk-heard {
    font-family: var(--serif-jp);
    font-size: 17px;
    line-height: 1.6;
    color: var(--ink-2);
  }
  .spk-heard-lbl {
    font-family: var(--sans);
    font-size: 12.5px;
    color: var(--ink-3);
    margin-right: 6px;
    letter-spacing: 0.06em;
  }
  .spk-verdict {
    font-size: 14.5px;
    line-height: 1.6;
    font-weight: 500;
  }
  .spk-verdict.ok { color: var(--moss); }
  .spk-verdict.warn { color: var(--bengara); }
  .spk-trap-line {
    font-size: 13.8px;
    line-height: 1.62;
    color: var(--bengara);
    padding-left: 10px;
    border-left: 2px solid rgba(154, 70, 51, 0.36);
  }
  .spk-model-wrap {
    margin-top: 4px;
    padding-top: 10px;
    border-top: 1px solid var(--hairline);
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .spk-model-lbl {
    font-size: 12px;
    color: var(--ink-3);
    letter-spacing: 0.08em;
  }
  .spk-model-ja {
    font-family: var(--serif-jp);
    font-size: 19px;
    line-height: 1.68;
    color: var(--sumi);
  }
  .spk-model-zh {
    font-size: 14px;
    color: var(--ink-2);
    line-height: 1.6;
  }
  .spk-tip {
    font-size: 13.5px;
    color: var(--ink-3);
    line-height: 1.62;
  }
  .rv-btn-mic {
    flex: 1;
    max-width: 230px;
    height: 48px;
    padding: 0 20px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.05em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .rv-btn-mic.listening {
    background: var(--bengara);
    color: #fff;
  }
  .rv-btn-mic:active { opacity: 0.85; transform: scale(0.985); }

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
    background: rgba(28, 27, 24, 0.32);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 28px;
    z-index: 100;
  }
  @media (prefers-color-scheme: dark) {
    .modal-mask { background: rgba(10, 9, 8, 0.66); }
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
    max-height: 82vh;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 12px;
    padding: 24px 22px;
  }
  .modal-card::-webkit-scrollbar { display: none; }
  .modal-h { margin: 0 0 12px; font-size: 18px; font-weight: 600; letter-spacing: 0.04em; }
  .modal-body { margin: 0 0 14px; font-size: 16px; color: var(--ink-2); line-height: 1.85; font-variant-numeric: tabular-nums; }
  .modal-promise { margin: 0 0 16px; padding-top: 12px; border-top: 1px solid var(--hairline); font-size: 14.5px; color: var(--moss); line-height: 1.65; font-weight: 500; }
  .sync-box {
    margin: 0 0 18px;
    padding: 12px 14px;
    border-radius: 8px;
    background: var(--soft-bg);
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
    gap: 5px;
  }
  .vc-dot {
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    border: 1.3px solid var(--hairline-strong);
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
    padding: 8px 0 6px;
    position: relative;
  }
  .vc-card {
    position: relative;
    width: 100%;
    flex: 1;
    min-height: 240px;
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 12px 4px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    touch-action: none;
    cursor: pointer;
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
    transform: translate3d(122%, 10px, 0) rotate(8deg) !important;
    opacity: 0 !important;
    transition: transform 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.22s ease !important;
  }
  .vc-card.fly-left {
    transform: translate3d(-122%, 10px, 0) rotate(-8deg) !important;
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
    top: 8px;
    padding: 3px 10px;
    border-radius: 5px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.08em;
    opacity: 0;
    pointer-events: none;
    background: var(--washi);
  }
  .vc-stamp.right {
    left: 4px;
    color: var(--moss);
    border: 1.5px solid var(--moss);
  }
  .vc-stamp.left {
    right: 4px;
    color: var(--bengara);
    border: 1.5px solid var(--bengara);
  }
  .vc-stamp.up {
    left: 50%;
    transform: translateX(-50%);
    color: var(--moss);
    border: 1.5px solid var(--moss);
  }

  .vc-cue {
    font-size: 12px;
    color: var(--ink-3);
    letter-spacing: 0.12em;
    margin-bottom: 18px;
    min-height: 17px;
    transition: opacity 0.22s ease;
  }
  .vc-cue.quiet-hide {
    opacity: 0;
    pointer-events: none;
  }
  .vc-cue.ng {
    color: var(--bengara);
    font-weight: 500;
    letter-spacing: 0.06em;
    opacity: 1;
  }
  .vc-chunk {
    font-family: var(--serif-jp);
    font-size: 33px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.48;
    letter-spacing: 0.04em;
    transition: filter 0.28s ease, opacity 0.28s ease;
  }
  .vc-chunk.ear-veil {
    filter: blur(9px);
    opacity: 0.24;
    user-select: none;
  }
  .vc-kana-front {
    font-size: 20px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.48;
    letter-spacing: 0.02em;
    margin-bottom: 14px;
    max-height: 84px;
    overflow: hidden;
    transition: opacity 0.22s ease, max-height 0.26s ease, margin 0.26s ease;
  }
  .vc-kana-front.revealed {
    opacity: 0;
    max-height: 0;
    margin-bottom: 0;
    pointer-events: none;
  }
  .vc-hl {
    font-weight: 600;
    border-bottom: 1.5px solid rgba(43, 95, 73, 0.36);
    padding-bottom: 3px;
  }
  @media (prefers-color-scheme: dark) {
    .vc-hl {
      border-bottom-color: rgba(98, 173, 137, 0.40);
    }
  }
  .vc-reveal {
    margin-top: 18px;
    min-height: 142px;
    width: 100%;
    max-width: 344px;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.24s ease, transform 0.24s ease;
    pointer-events: none;
  }
  .vc-reveal.shown {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .vc-kana {
    font-size: 18.5px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }
  .vc-zh {
    font-size: 17px;
    font-weight: 500;
    color: var(--ink-2);
    line-height: 1.54;
    letter-spacing: 0.02em;
  }
  .vc-zh.quiet {
    font-size: 15px;
    font-weight: 400;
    color: var(--ink-3);
  }
  .vc-hook {
    position: relative;
    margin: 22px auto 0;
    padding-top: 18px;
    max-width: 340px;
    font-size: 13.8px;
    color: var(--ink-2);
    line-height: 1.72;
    letter-spacing: 0.015em;
    cursor: default;
  }
  .vc-hook::before {
    content: "";
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 28px;
    height: 1px;
    background: var(--hairline-strong);
  }
  .vc-hook.rv-hook {
    margin: 10px 0 0;
    padding-top: 10px;
    max-width: none;
    border-top: 1px solid var(--hairline);
    text-align: left;
  }
  .vc-hook.rv-hook::before {
    display: none;
  }
  .vc-hook-tag {
    display: inline-block;
    margin-right: 7px;
    font-size: 11px;
    font-weight: 600;
    color: var(--ochre);
    opacity: 0.88;
    letter-spacing: 0.1em;
    vertical-align: 1px;
  }
  .vc-twin {
    margin: 14px auto 0;
    padding-top: 12px;
    border-top: 1px solid var(--hairline);
    max-width: 316px;
    font-size: 13.5px;
    color: var(--ink-2);
    line-height: 1.6;
  }
  .vc-twin.sub {
    margin: 10px auto 0;
    padding-top: 0;
    border-top: none;
    max-width: 316px;
    font-size: 12.4px;
    color: var(--ink-3);
    opacity: 0.84;
    line-height: 1.58;
  }
  @media (max-height: 700px) {
    .vc-card { padding: 8px 2px; }
    .vc-cue { margin-bottom: 12px; }
    .vc-chunk { font-size: 28px; }
    .vc-reveal { margin-top: 14px; min-height: 116px; }
    .vc-hook { margin-top: 16px; padding-top: 13px; font-size: 13.2px; line-height: 1.62; }
    .vc-twin.sub { margin-top: 7px; font-size: 12px; }
  }

  /* Vocab Kanso Aux Row (簡素 · 上看下点: frameless thumb-zone secondary actions) */
  .vc-aux-row {
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .vc-aux-right {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .vc-aux-btn {
    height: 46px;
    min-height: 46px;
    border: none;
    border-radius: 0;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: var(--ink-3);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    touch-action: manipulation;
    transition: opacity 0.15s ease, color 0.18s ease;
  }
  .vc-aux-btn.seal {
    padding: 0 22px 0 2px;
  }
  .vc-aux-btn.mic-btn {
    padding: 0 14px;
  }
  .vc-aux-btn.replay {
    padding: 0 2px 0 14px;
    font-size: 14.5px;
    color: var(--ink-2);
  }
  .vc-aux-btn:active {
    opacity: 0.5;
  }
  @media (min-width: 860px) and (min-height: 521px) {
    .vc-aux-btn:hover { color: var(--sumi); }
  }

  .vc-dock {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 2px;
  }
  .vc-btn {
    height: 52px;
    border-radius: 8px;
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.05em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    touch-action: manipulation;
    transition: opacity 0.15s ease, background 0.15s ease;
  }
  .vc-btn.ng {
    flex: 1;
    border: 1px solid var(--hairline-strong);
    color: var(--bengara);
    font-weight: 500;
    background: transparent;
  }
  .vc-btn.mid {
    flex: 0.92;
    border: 1px solid var(--hairline-strong);
    color: var(--ink-2);
    background: transparent;
    font-size: 14.5px;
  }
  .vc-btn.ok {
    flex: 1.32;
    background: var(--sumi);
    color: var(--sheet);
    font-weight: 600;
  }
  .vc-btn.ok:active { opacity: 0.86; }
  .vc-btn.ng:active, .vc-btn.mid:active { background: var(--tap-bg); }
  .vc-btn.ga-solid {
    flex: 0.92;
    border: 1px solid rgba(43, 95, 73, 0.36);
    color: var(--moss);
    font-weight: 600;
    background: var(--sheet);
    font-size: 13.8px;
  }
  .vc-btn.ga-fuzzy {
    flex: 1.05;
    background: var(--sumi);
    color: var(--sheet);
    font-weight: 600;
  }

  /* Position #3 Zen Sub-Bar ("记词 · 语法盘点" — auto-retires once 156/156 complete) */
  .vc-subnav {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 0 6px;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 0;
  }
  .vc-subtabs {
    display: flex;
    align-items: center;
    gap: 28px;
  }
  .vc-subtab {
    min-height: 40px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 8px 2px;
    letter-spacing: 0.05em;
    position: relative;
    transition: color 0.18s ease;
    font-variant-numeric: tabular-nums;
    display: inline-flex;
    align-items: center;
    touch-action: manipulation;
  }
  .vc-subtab.active {
    color: var(--sumi);
    font-weight: 600;
  }
  .vc-subtab.active::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -7px;
    height: 1.5px;
    background: var(--sumi);
  }
  .vc-subtab-cnt {
    margin-left: 5px;
    font-size: 12px;
    font-weight: 400;
    color: var(--ink-3);
  }
  .vc-subtab.active .vc-subtab-cnt {
    color: var(--ink-2);
  }
  .vc-submeta {
    font-size: 12px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
  }

  /* Grammar Self-Audit ("语法盘点" · 开放宣纸/夜墨画布 · 一词一问 · 零废话) */
  .ga-meta-bar {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 28px;
    padding: 4px 0 2px;
  }
  .ga-meta-fam {
    font-size: 12.5px;
    color: var(--ink-3);
    letter-spacing: 0.06em;
    transition: color 0.18s ease, opacity 0.18s ease;
  }
  .ga-meta-fam.s1 { color: var(--bengara); }
  .ga-meta-fam.s2 { color: var(--ochre); }
  .ga-stage {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 8px 6px 14px;
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }
  .ga-canvas {
    width: 100%;
    max-width: 396px;
    display: flex;
    flex-direction: column;
    align-items: center;
    transition: opacity 0.16s ease, transform 0.16s ease;
  }
  .ga-head {
    font-family: var(--serif-jp);
    font-size: clamp(29px, 7.8vw, 36px);
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.38;
    letter-spacing: 0.03em;
    word-break: keep-all;
  }
  .ga-reveal {
    margin-top: 22px;
    min-height: 168px;
    width: 100%;
    opacity: 0;
    transform: translateY(5px);
    transition: opacity 0.22s ease, transform 0.22s ease;
    pointer-events: none;
  }
  .ga-reveal.shown {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
  }
  .ga-meaning {
    font-size: 18px;
    font-weight: 500;
    color: var(--sumi);
    line-height: 1.5;
    letter-spacing: 0.015em;
    text-wrap: balance;
  }
  .ga-rule {
    margin: 9px auto 0;
    max-width: 344px;
    font-size: 13.5px;
    color: var(--ink-3);
    line-height: 1.62;
    text-wrap: balance;
  }
  .ga-divider {
    width: 28px;
    height: 1px;
    background: var(--hairline-strong);
    margin: 18px auto 16px;
  }
  .ga-ex {
    max-width: 356px;
    margin: 0 auto;
    text-align: center;
  }
  .ga-ex-ja {
    font-family: var(--serif-jp);
    font-size: 16px;
    color: var(--sumi);
    line-height: 1.66;
    text-wrap: balance;
  }
  .ga-ex-zh {
    margin-top: 5px;
    font-size: 13px;
    color: var(--ink-3);
    line-height: 1.54;
    text-wrap: balance;
  }
  .ga-summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    margin: 22px 0 8px;
    padding: 14px 0;
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
  }
  .ga-stat-cell { text-align: center; }
  .ga-stat-num {
    font-family: var(--serif-jp);
    font-size: 22px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .ga-stat-num.s1 { color: var(--bengara); }
  .ga-stat-num.s2 { color: var(--ochre); }
  .ga-stat-num.s3 { color: var(--sumi); }
  .ga-stat-num.s4 { color: var(--moss); }
  .ga-stat-lbl {
    margin-top: 4px;
    font-size: 12px;
    color: var(--ink-3);
    letter-spacing: 0.04em;
  }

  /* Monochrome Karesansui 4-Stop Zen Tactile Rail (静默枯山水墨点 · 轻点或沿线滑选) */
  .ga-spec-wrap {
    flex-shrink: 0;
    padding: 6px 0 6px;
    user-select: none;
    -webkit-user-select: none;
  }
  .ga-spec-rail {
    position: relative;
    padding: 10px 0 6px;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
    cursor: pointer;
  }
  .ga-spec-line {
    position: absolute;
    left: 12.5%;
    right: 12.5%;
    top: 19px;
    height: 1px;
    background: var(--hairline-strong);
    pointer-events: none;
  }
  .ga-spec-stops {
    position: relative;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    z-index: 2;
  }
  .ga-spec-stop {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 11px;
    padding: 4px 0 6px;
    color: var(--ink-3);
    transition: transform 0.14s ease, color 0.14s ease;
  }
  .ga-spec-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--washi);
    border: 1.5px solid var(--ink-3);
    transition: transform 0.15s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  }
  .ga-spec-stop.s1.active .ga-spec-dot { border-color: var(--bengara); background: var(--bengara); box-shadow: 0 0 0 7px rgba(158, 62, 54, 0.14); transform: scale(1.42); }
  .ga-spec-stop.s2.active .ga-spec-dot { border-color: var(--ochre); background: var(--ochre); box-shadow: 0 0 0 7px rgba(176, 125, 58, 0.16); transform: scale(1.42); }
  .ga-spec-stop.s3.active .ga-spec-dot { border-color: var(--sumi); background: var(--sumi); box-shadow: 0 0 0 7px var(--tap-bg); transform: scale(1.42); }
  .ga-spec-stop.s4.active .ga-spec-dot { border-color: var(--moss-solid); background: var(--moss-solid); box-shadow: 0 0 0 7px rgba(43, 95, 73, 0.16); transform: scale(1.42); }
  .ga-spec-name {
    font-size: 13.5px;
    font-weight: 400;
    letter-spacing: 0.08em;
    color: var(--ink-2);
    transition: color 0.14s ease, font-weight 0.14s ease;
  }
  .ga-spec-stop.s1.active .ga-spec-name { color: var(--bengara); font-weight: 600; }
  .ga-spec-stop.s2.active .ga-spec-name { color: var(--ochre); font-weight: 600; }
  .ga-spec-stop.s3.active .ga-spec-name { color: var(--sumi); font-weight: 600; }
  .ga-spec-stop.s4.active .ga-spec-name { color: var(--moss); font-weight: 600; }
  .ga-spec-card-fade {
    opacity: 0 !important;
    transform: translateY(-5px) !important;
    transition: opacity 0.15s ease, transform 0.15s ease !important;
  }
  @media (max-height: 700px) {
    .ga-head { font-size: 27px; }
    .ga-reveal { margin-top: 14px; min-height: 134px; }
    .ga-meaning { font-size: 16.5px; }
    .ga-rule { margin-top: 6px; font-size: 12.8px; }
    .ga-divider { margin: 12px auto 11px; }
    .ga-ex-ja { font-size: 14.8px; }
  }

  /* Quiet inline 4-step controls inside Zen Ledger ("总表 → 语法") */
  .li-ga-tag {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.03em;
    color: var(--ink-3);
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--soft-bg);
    white-space: nowrap;
  }
  .li-ga-tag.s1 { color: var(--bengara); background: rgba(158, 62, 54, 0.08); }
  .li-ga-tag.s2 { color: var(--ochre); background: rgba(176, 125, 58, 0.11); }
  .li-ga-tag.s3 { color: var(--sumi); background: var(--soft-bg); }
  .li-ga-tag.s4 { color: var(--moss); background: var(--moss-soft); }
  .li-ga-bar {
    margin-top: 10px;
    padding-left: 16.5px;
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }
  .li-ga-sublist {
    margin-top: 8px;
    padding-left: 16.5px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .li-ga-subrow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    padding: 4px 0;
    border-top: 1px solid var(--hairline);
  }
  .li-ga-subrow:first-child { border-top: none; }
  .li-ga-subname {
    font-family: var(--serif-jp);
    font-size: 13.5px;
    color: var(--sumi);
    min-width: 92px;
  }
  .li-ga-subbtns {
    display: inline-flex;
    align-items: center;
    gap: 12px;
  }
  .li-ga-lbl {
    font-size: 12px;
    color: var(--ink-3);
  }
  .li-ga-btn {
    font-size: 13px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 4px 2px;
    border-bottom: 1.5px solid transparent;
    transition: color 0.15s ease, border-color 0.15s ease;
  }
  .li-ga-btn.s1.on { color: var(--bengara); border-bottom-color: var(--bengara); font-weight: 600; }
  .li-ga-btn.s2.on { color: var(--ochre); border-bottom-color: var(--ochre); font-weight: 600; }
  .li-ga-btn.s3.on { color: var(--sumi); border-bottom-color: var(--sumi); font-weight: 600; }
  .li-ga-btn.s4.on { color: var(--moss); border-bottom-color: var(--moss); font-weight: 600; }
  .dash-roi-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 0 12px;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--hairline);
  }
  .dash-roi-txt {
    font-size: 13px;
    color: var(--ink-2);
    line-height: 1.5;
    font-variant-numeric: tabular-nums;
  }
  .dash-roi-txt b {
    color: var(--sumi);
    font-weight: 600;
  }
  .dash-roi-btn {
    flex-shrink: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--moss);
    white-space: nowrap;
    padding: 4px 0;
  }
  .li-hes {
    font-size: 11px;
    font-weight: 500;
    color: var(--ochre);
    background: rgba(176, 125, 58, 0.11);
    padding: 1px 6px;
    border-radius: 4px;
    white-space: nowrap;
  }
  .li-stale {
    font-size: 11px;
    font-weight: 500;
    color: var(--ink-3);
    background: var(--soft-bg);
    padding: 1px 6px;
    border-radius: 4px;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* ================= 6. NATIVE ZEN BODY MODULE ("体律" · Open-Washi Zen Ma & Kanso) ================= */
  #green-board.hidden, #body-view.hidden, .zen-panel.hidden { display: none !important; }
  #body-view {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .zb-subnav {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0 8px;
    gap: 8px;
  }
  .zb-subtabs { display: flex; align-items: center; gap: 20px; position: relative; }
  .zb-sub-bar {
    position: absolute;
    left: 0;
    bottom: -1px;
    height: 1.5px;
    width: 28px;
    background: var(--sumi);
    border-radius: 2px;
    pointer-events: none;
    transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1), width 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .zb-subtab { font-size: 14.5px; font-weight: 500; color: var(--ink-3); padding: 4px 0; position: relative; letter-spacing: 0.04em; transition: color 0.18s ease; }
  .zb-subtab.active { color: var(--sumi); font-weight: 600; }
  .zb-date-tag { font-size: 12.5px; color: var(--ink-3); font-variant-numeric: tabular-nums; letter-spacing: 0.03em; }

  .zb-ptr {
    flex-shrink: 0;
    height: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    opacity: 0;
    transition: height 0.24s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
  }
  .zb-ptr.dragging { transition: none; }
  .zb-ptr-svg { width: 18px; height: 18px; display: block; }
  .zb-ptr.syncing .zb-ptr-svg { animation: zbSpin 0.85s linear infinite; }
  @keyframes zbSpin { to { transform: rotate(360deg); } }
  .zb-ptr-lbl { font-size: 12px; color: var(--ink-3); letter-spacing: 0.04em; }

  .zb-stage {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    display: flex;
    flex-direction: column;
    padding: 0 0 18px;
  }
  .zb-stage::-webkit-scrollbar { display: none; }
  .zb-panel { display: none; flex-direction: column; flex: 1; min-height: 100%; will-change: transform, opacity; }
  .zb-panel.active { display: flex; }
  .zb-panel.zb-slide-r { animation: zbSlideR 0.23s cubic-bezier(0.22, 1, 0.36, 1); }
  .zb-panel.zb-slide-l { animation: zbSlideL 0.23s cubic-bezier(0.22, 1, 0.36, 1); }
  @keyframes zbSlideR { from { opacity: 0.28; transform: translateX(16px); } to { opacity: 1; transform: translateX(0); } }
  @keyframes zbSlideL { from { opacity: 0.28; transform: translateX(-16px); } to { opacity: 1; transform: translateX(0); } }

  /* Generous Zen Ma (余白) pushing interactive focal zone into effortless right-thumb reach */
  .zb-ma { flex: 1 1 32px; min-height: 18px; }
  .zb-ma-tail { flex: 0.22 1 8px; min-height: 6px; }

  .zb-context {
    font-size: 13px;
    color: var(--ink-3);
    letter-spacing: 0.05em;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    font-variant-numeric: tabular-nums;
  }
  .zb-tier { font-weight: 500; }
  .zb-tier.green { color: var(--moss); }
  .zb-tier.yellow { color: var(--ochre); }
  .zb-tier.red { color: var(--bengara); }

  .zb-pz-btn {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-3);
    letter-spacing: 0.03em;
    font-variant-numeric: tabular-nums;
    padding: 2px 0;
    white-space: nowrap;
    transition: color 0.16s ease;
  }
  .zb-pz-btn:active { color: var(--sumi); }
  .zb-pz-btn.warn { color: var(--ochre); }
  .zb-pz-btn.urgent { color: var(--bengara); }

  .zb-pz-track {
    width: 100%;
    height: 1.5px;
    background: var(--hairline);
    border-radius: 2px;
    margin: 9px 0 4px;
    overflow: hidden;
  }
  .zb-pz-fill {
    height: 100%;
    width: 4%;
    background: var(--moss);
    border-radius: 2px;
    transition: width 0.35s cubic-bezier(0.22, 1, 0.36, 1), background-color 0.25s ease;
  }
  .zb-pz-fill.warn { background: var(--ochre); }
  .zb-pz-fill.urgent { background: var(--bengara); }

  .zb-title {
    font-family: var(--serif-jp);
    font-size: clamp(22px, 6vw, 26px);
    font-weight: 600;
    line-height: 1.35;
    letter-spacing: 0.02em;
    color: var(--sumi);
    margin: 12px 0 8px;
  }

  .zb-guide-row {
    width: 100%;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    text-align: left;
    padding: 2px 0;
    white-space: normal;
  }
  .zb-guide-txt {
    font-size: 13.5px;
    line-height: 1.58;
    color: var(--ink-2);
    letter-spacing: 0.015em;
  }
  .zb-guide-link {
    flex-shrink: 0;
    font-size: 13px;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    white-space: nowrap;
    transition: color 0.16s ease;
  }
  .zb-guide-row:active .zb-guide-link { color: var(--sumi); }

  /* Dynamic 2-level state selector (pure borderless Zen typography, zero pill clutter) */
  .zb-state-block {
    margin-top: 22px;
    margin-bottom: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .zb-state-bar {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    padding-bottom: 2px;
  }
  .zb-state-btn {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 5px 0 6px;
    border-bottom: 1.5px solid transparent;
    letter-spacing: 0.04em;
    transition: color 0.18s ease, border-color 0.18s ease;
  }
  .zb-state-btn.active { color: var(--sumi); font-weight: 600; border-bottom-color: var(--sumi); }
  .zb-state-btn.active.is-bb { color: var(--bengara); border-bottom-color: var(--bengara); }
  .zb-state-btn.active.is-tired { color: var(--ochre); border-bottom-color: var(--ochre); }
  .zb-state-btn.active.is-rest { color: var(--moss); border-bottom-color: var(--moss); }

  .zb-substate-bar {
    display: none;
    align-items: center;
    gap: 18px;
    padding: 2px 0 2px 11px;
    border-left: 1.5px solid var(--hairline-strong);
    animation: zenModeIn 0.2s ease;
  }
  .zb-substate-bar.open { display: flex; }
  .zb-substate-bar.is-bb { border-left-color: var(--bengara); }
  .zb-substate-bar.is-tired { border-left-color: var(--ochre); }
  .zb-substate-btn {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 4px 0;
    letter-spacing: 0.03em;
    transition: color 0.16s ease;
  }
  .zb-substate-btn.active { color: var(--sumi); font-weight: 600; }
  .zb-substate-btn.active.is-red { color: var(--bengara); }
  .zb-substate-btn.active.is-ochre { color: var(--ochre); }
  .zb-substate-btn.active.is-green { color: var(--moss); }

  .zb-cta-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 2px;
  }
  .zb-btn-primary {
    flex: 1;
    height: 48px;
    padding: 0 20px;
    border-radius: 8px;
    background: var(--sumi);
    color: var(--sheet);
    font-size: 15.5px;
    font-weight: 500;
    letter-spacing: 0.05em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.15s ease, background-color 0.22s ease;
  }
  .zb-btn-primary.is-done { background: var(--moss-solid); color: #FCFBF8; }
  .zb-btn-primary:active { opacity: 0.86; }
  .zb-btn-ghost {
    height: 48px;
    padding: 0 15px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-2);
    letter-spacing: 0.03em;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .zb-btn-ghost:active { background: var(--tap-bg); }

  .zb-btn-quiet {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--ink-3);
    padding: 8px 2px;
    letter-spacing: 0.03em;
    transition: color 0.18s ease;
  }
  .zb-btn-quiet:active { color: var(--sumi); }
  .zb-btn-quiet.active { color: var(--moss); font-weight: 600; }
  .zb-btn-quiet.is-ochre { color: var(--ochre); font-weight: 600; }
  .zb-btn-quiet.is-red { color: var(--bengara); font-weight: 600; }

  .zb-aux-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-top: 8px;
  }
  .zb-aux-grp {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-left: auto;
  }
  .zb-week-quiet {
    font-size: 12.5px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
  }

  .zb-ritual-list { margin-top: 26px; border-top: 1px solid var(--hairline); }
  .zb-ritual-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 15px 0;
    border-bottom: 1px solid var(--hairline);
    gap: 12px;
  }
  .zb-ritual-left { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
  .zb-ritual-name { font-size: 15px; font-weight: 500; color: var(--sumi); letter-spacing: 0.03em; white-space: nowrap; }
  .zb-ritual-hint { font-size: 12.5px; color: var(--ink-3); font-variant-numeric: tabular-nums; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .zb-ritual-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .zb-round-dot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 1.4px solid var(--hairline-strong);
    color: var(--ink-2);
    font-size: 13px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-variant-numeric: tabular-nums;
    transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.14s ease;
  }
  .zb-round-dot:active { transform: scale(0.93); }
  .zb-round-dot.done { background: var(--moss-solid); border-color: var(--moss-solid); color: #FCFBF8; }
  .zb-tap-check { font-size: 14px; font-weight: 500; color: var(--ink-2); padding: 6px 0; letter-spacing: 0.03em; transition: color 0.18s ease; }
  .zb-tap-check.done { color: var(--moss); font-weight: 600; }

  .zb-rep-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 26px;
    padding: 16px 0;
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
    gap: 12px;
  }
  .zb-stepper { display: inline-flex; align-items: center; gap: 14px; }
  .zb-step-btn { width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--hairline-strong); font-size: 16px; color: var(--sumi); display: inline-flex; align-items: center; justify-content: center; transition: background-color 0.14s ease, transform 0.12s ease; }
  .zb-step-btn:active { background: var(--hairline); transform: scale(0.93); }
  .zb-step-val { min-width: 24px; text-align: center; font-family: var(--serif-jp); font-size: 21px; font-weight: 600; font-variant-numeric: tabular-nums; }

  .zb-pacer { display: none; margin-top: 18px; padding: 14px 0 6px; flex-direction: column; align-items: center; gap: 9px; animation: zenModeIn 0.2s ease; }
  .zb-pacer.open { display: flex; }
  .zb-pacer-ring { position: relative; width: 102px; height: 102px; display: flex; align-items: center; justify-content: center; }
  .zb-pacer-svg { width: 102px; height: 102px; display: block; overflow: visible; }
  .zb-pacer-num { position: absolute; font-family: var(--serif-jp); font-size: 30px; font-weight: 600; color: var(--sumi); font-variant-numeric: tabular-nums; }
  .zb-pacer-phase { font-size: 13px; font-weight: 500; color: var(--ink-2); letter-spacing: 0.04em; }
  .zb-pacer-ctrls { display: flex; align-items: center; gap: 20px; }

  .zb-ladder { margin-top: 28px; display: flex; justify-content: space-between; gap: 10px; }
  .zb-ladder-step { flex: 1; display: flex; flex-direction: column; gap: 6px; }
  .zb-ladder-bar { height: 1.8px; background: var(--track); border-radius: 2px; }
  .zb-ladder-step.past .zb-ladder-bar, .zb-ladder-step.cur .zb-ladder-bar { background: var(--moss); }
  .zb-ladder-lbl { font-size: 11.5px; color: var(--ink-3); letter-spacing: 0.04em; }
  .zb-ladder-step.cur .zb-ladder-lbl { color: var(--sumi); font-weight: 600; }

  .zb-stat-pair { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 14px 0 18px; }
  .zb-stat-big { font-family: var(--serif-jp); font-size: 38px; font-weight: 600; letter-spacing: -0.02em; color: var(--sumi); font-variant-numeric: tabular-nums; line-height: 1.08; transition: color 0.16s ease; }
  .zb-stat-big.scrub { color: var(--moss); }
  .zb-stat-unit { font-family: var(--sans); font-size: 13.5px; font-weight: 400; color: var(--ink-3); margin-left: 3px; }
  .zb-stat-sub { font-size: 12.5px; color: var(--ink-3); margin-top: 6px; font-variant-numeric: tabular-nums; }
  .zb-chart-wrap { width: 100%; margin: 2px 0 6px; touch-action: pan-y; cursor: crosshair; }
  .zb-chart-svg { width: 100%; height: auto; aspect-ratio: 360 / 168; display: block; overflow: visible; }
  .zb-chart-sw { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--hairline); }
  .zb-sw-grp { display: flex; gap: 16px; }

  .zb-weigh-drawer { display: none; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--hairline); flex-direction: column; gap: 14px; animation: zenModeIn 0.2s ease; }
  .zb-weigh-drawer.open { display: flex; }
  .zb-dial-row { display: flex; flex-direction: column; gap: 7px; }
  .zb-dial-head { display: flex; justify-content: space-between; align-items: center; }
  .zb-dial-lbl { font-size: 13px; color: var(--ink-3); }
  .zb-dial-ctrl { display: inline-flex; align-items: center; gap: 10px; }
  .zb-dial-val { font-family: var(--serif-jp); font-size: 19px; font-weight: 600; color: var(--sumi); font-variant-numeric: tabular-nums; min-width: 64px; text-align: center; border-bottom: 1px dashed var(--hairline-strong); padding-bottom: 1px; }
  .zb-dial-in { width: 64px; font-family: var(--serif-jp); font-size: 18px; font-weight: 600; text-align: center; color: var(--sumi); background: transparent; border: none; border-bottom: 1.5px solid var(--moss); outline: none; font-variant-numeric: tabular-nums; -webkit-user-select: text; user-select: text; }
  .zb-dial-track { position: relative; height: 28px; border-radius: 6px; background: var(--sheet); border: 1px solid var(--hairline); overflow: hidden; touch-action: none; cursor: ew-resize; }
  .zb-dial-ticks { position: absolute; inset: 0; background-image: repeating-linear-gradient(90deg, transparent 0, transparent 9px, var(--hairline-strong) 9px, var(--hairline-strong) 10px); background-size: 50px 100%; opacity: 0.85; }
  .zb-dial-needle { position: absolute; left: 50%; top: 4px; bottom: 4px; width: 2px; margin-left: -1px; background: var(--moss); border-radius: 2px; pointer-events: none; }
  .zb-dial-foot { display: flex; justify-content: space-between; align-items: center; }
  .zb-res-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--hairline); }
  .zb-waist-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 4px; }
  .zb-waist-in { width: 108px; font-family: var(--serif-jp); font-size: 16px; font-weight: 500; text-align: right; color: var(--sumi); background: transparent; border: none; border-bottom: 1px dashed var(--hairline-strong); padding: 4px 2px; outline: none; font-variant-numeric: tabular-nums; -webkit-user-select: text; user-select: text; }
  .zb-waist-in:focus { border-bottom-color: var(--moss); border-bottom-style: solid; }
  .zb-waist-in::placeholder { font-family: var(--sans); font-size: 12.5px; font-weight: 400; color: var(--ink-3); }

  .zb-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 14px 0 18px; border-bottom: 1px solid var(--hairline); margin-bottom: 4px; }
  .zb-kpi-v { font-family: var(--serif-jp); font-size: 20px; font-weight: 600; color: var(--sumi); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .zb-kpi-l { font-size: 11.5px; color: var(--ink-3); margin-top: 4px; letter-spacing: 0.03em; }
  .zb-ledger-list { margin-top: 2px; }
  .zb-ledger-item { border-bottom: 1px solid var(--hairline); }
  .zb-ledger-row { width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 12.5px 0; font-size: 13.5px; gap: 10px; text-align: left; }
  .zb-ledger-row:active { opacity: 0.65; }
  .zb-ledger-date { color: var(--ink-3); font-variant-numeric: tabular-nums; min-width: 48px; }
  .zb-ledger-main { flex: 1; color: var(--sumi); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .zb-ledger-dots { display: inline-flex; gap: 5px; flex-shrink: 0; }
  .zb-dot { width: 6.5px; height: 6.5px; border-radius: 50%; background: var(--track); }
  .zb-dot.ok { background: var(--moss); }
  .zb-dot.bb { background: var(--bengara); }
  .zb-ed { padding: 4px 0 14px; display: flex; flex-direction: column; gap: 9px; animation: zenModeIn 0.18s ease; }
  .zb-ed-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 12.5px; }
  .zb-ed-lbl { color: var(--ink-3); min-width: 30px; font-size: 12px; }
  .zb-ed-chip { font-size: 12.5px; color: var(--ink-2); padding: 4px 2px; border-bottom: 1px solid transparent; }
  .zb-ed-chip.on { color: var(--moss); font-weight: 600; border-bottom-color: var(--moss); }
  .zb-ed-chip.on-red { color: var(--bengara); font-weight: 600; border-bottom-color: var(--bengara); }

  .zb-sync-foot { margin-top: 16px; display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: 12.5px; color: var(--ink-3); }
  .zb-sync-left { display: flex; align-items: center; gap: 10px; min-width: 0; flex-wrap: wrap; }

  .zb-guide-list { display: flex; flex-direction: column; margin: 4px 0 16px; border-top: 1px solid var(--hairline); }
  .zb-guide-item { padding: 13px 0; border-bottom: 1px solid var(--hairline); }
  .zb-guide-k { font-size: 12px; font-weight: 600; color: var(--moss); letter-spacing: 0.05em; margin-bottom: 5px; }
  .zb-guide-v { font-size: 14.5px; line-height: 1.62; color: var(--sumi); }
  .zb-guide-sub { font-size: 13px; line-height: 1.55; color: var(--ink-3); margin-top: 4px; }
  .zb-guide-item.cur .zb-guide-k::before { content: "● "; font-size: 9px; }

  .zb-modal-links { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: -4px 0 14px; flex-wrap: wrap; }
  .zb-pz-tabs { display: flex; gap: 18px; margin: 2px 0 12px; border-bottom: 1px solid var(--hairline); }
  .zb-pz-tab { font-size: 13.5px; font-weight: 500; color: var(--ink-3); padding: 6px 0 8px; border-bottom: 1.5px solid transparent; }
  .zb-pz-tab.active { color: var(--sumi); font-weight: 600; border-bottom-color: var(--sumi); }
  .zb-pz-note { font-size: 12.5px; color: var(--ink-3); line-height: 1.55; margin: 0 0 12px; }
  .zb-pz-list { display: flex; flex-direction: column; margin-bottom: 16px; max-height: 46vh; overflow-y: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  .zb-pz-list::-webkit-scrollbar { display: none; }
  .zb-pz-wk { font-size: 11.5px; font-weight: 600; color: var(--ink-3); letter-spacing: 0.06em; padding: 12px 0 6px; border-bottom: 1px solid var(--hairline); }
  .zb-pz-row { width: 100%; display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--hairline); text-align: left; }
  .zb-pz-row:active { opacity: 0.7; }
  .zb-pz-mark { width: 16px; flex-shrink: 0; font-size: 12.5px; color: var(--ink-3); text-align: center; padding-top: 2px; }
  .zb-pz-row.done .zb-pz-mark { color: var(--moss); font-weight: 600; }
  .zb-pz-row.cur .zb-pz-mark { color: var(--moss); }
  .zb-pz-info { flex: 1; min-width: 0; }
  .zb-pz-name { font-size: 13.5px; line-height: 1.45; color: var(--sumi); }
  .zb-pz-row.done .zb-pz-name { color: var(--ink-3); }
  .zb-pz-row.cur .zb-pz-name { color: var(--sumi); font-weight: 600; }
  .zb-pz-meta { font-size: 12px; color: var(--ink-3); margin-top: 2px; font-variant-numeric: tabular-nums; }
  .zb-pz-min { flex-shrink: 0; font-size: 12px; color: var(--ink-3); font-variant-numeric: tabular-nums; padding-top: 2px; }

  .zb-ledger-pz { width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--hairline); font-size: 13.5px; text-align: left; }
  .zb-ledger-pz:active { opacity: 0.7; }

  .zb-locked { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; padding: 16px 2px; }
  .zb-locked-title { font-family: var(--serif-jp); font-size: 24px; font-weight: 600; margin: 14px 0 8px; }
  .zb-locked-sub { font-size: 14px; line-height: 1.68; color: var(--ink-3); margin: 0; }
  .zb-pass-row { width: 100%; margin-top: 20px; display: flex; gap: 10px; }
  .zb-pass-in { flex: 1; height: 46px; padding: 0 14px; border: 1px solid var(--hairline-strong); border-radius: 8px; background: var(--sheet); color: var(--sumi); font-size: 15px; -webkit-user-select: text; user-select: text; }

  .zb-toast {
    position: fixed;
    left: 50%;
    top: calc(96px + env(safe-area-inset-top));
    transform: translateX(-50%) translateY(-6px);
    background: var(--sumi);
    color: var(--washi);
    font-size: 12.5px;
    padding: 8px 16px;
    border-radius: 8px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease, transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
    z-index: 60;
    white-space: nowrap;
  }
  .zb-toast.show { opacity: 0.94; transform: translateX(-50%) translateY(0); }
  /* ================= 3F. GLOBAL FLOATING MINI RADIO BAR (跨 Tab 无缝随身听) ================= */
  .radio-mini-bar {
    position: relative;
    width: 100%;
    margin-top: auto;
    margin-bottom: 8px;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--hairline-2);
    border-radius: 12px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.05);
    overflow: hidden;
    cursor: pointer;
    z-index: 80;
    transition: opacity 0.22s ease, transform 0.22s ease;
  }
  .radio-mini-bar.hidden {
    display: none !important;
  }
  .rmb-progress-rail {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: rgba(28, 27, 24, 0.08);
  }
  .rmb-progress-fill {
    height: 100%;
    width: 0%;
    background: var(--moss);
    transition: width 0.3s linear;
  }
  .rmb-body {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px 7px;
    gap: 10px;
  }
  .rmb-left {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
    flex: 1;
  }
  .rmb-wave-icon {
    display: inline-flex;
    align-items: flex-end;
    gap: 2px;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }
  .rmb-bar {
    width: 2.5px;
    height: 4px;
    background: var(--ink-3);
    border-radius: 1px;
    transition: height 0.2s ease, background-color 0.2s ease;
  }
  .rmb-wave-icon.is-playing .rmb-bar {
    background: var(--moss);
    animation: rmbEqualizer 1s infinite ease-in-out alternate;
  }
  .rmb-wave-icon.is-playing .rmb-bar:nth-child(1) { animation-delay: 0.1s; height: 12px; }
  .rmb-wave-icon.is-playing .rmb-bar:nth-child(2) { animation-delay: 0.35s; height: 7px; }
  .rmb-wave-icon.is-playing .rmb-bar:nth-child(3) { animation-delay: 0.2s; height: 14px; }
  @keyframes rmbEqualizer {
    0% { height: 4px; }
    50% { height: 14px; }
    100% { height: 6px; }
  }
  .rmb-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .rmb-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--sumi);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.25;
  }
  .rmb-time {
    font-size: 11px;
    color: var(--ink-3);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
    margin-top: 1px;
  }
  .rmb-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .rmb-play-btn {
    font-size: 12px;
    font-weight: 600;
    color: var(--moss);
    background: rgba(45, 122, 86, 0.09);
    padding: 5px 11px;
    border-radius: 14px;
    transition: all 0.15s ease;
  }
  .rmb-play-btn:active {
    transform: scale(0.95);
    background: rgba(45, 122, 86, 0.18);
  }
  .rmb-jump-btn {
    font-size: 11.5px;
    color: var(--ink-3);
    padding: 4px 6px;
    border-radius: 6px;
    white-space: nowrap;
  }
  .rmb-jump-btn:active {
    color: var(--sumi);
  }
  @media (max-width: 859px), (max-height: 520px) {
    .radio-mini-bar {
      margin-bottom: 6px;
      border-radius: 10px;
    }
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
      <button class="nav-link" id="tab-body" onclick="switchMode('body')">体律</button>
    </nav>
  </header>

  <!-- 2. FOUR ZEN ENSO DAILY RITUALS (円相 · 无字打卡 · 贯穿全站) -->
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
      <div id="radio-player-stage">
        <div class="meta-bar">
          <span class="overline" id="radio-date-pill">锵锵三人 · 文涛 · 文道 · 子东</span>
        </div>

        <div class="radio-center">
          <div class="radio-chap" id="radio-chap-lbl">逐客茶</div>
          <h2 class="radio-topic" id="radio-live-title">日本文化夜话</h2>
          <div class="radio-art-card" id="radio-art-card" style="display:none;" onclick="openStoryArtModal()">
            <img class="radio-art-img" id="radio-art-img" src="" alt="" />
            <div class="radio-art-meta">
              <span class="radio-art-tag" id="radio-art-tag"></span>
            </div>
          </div>
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
          <button type="button" class="rv-finish-strip" id="radio-review-cta" style="display:none;" onclick="openRadioReview()">
            <span>节目已播完 · 进入收尾小节，3 分钟锁住重点</span>
            <span class="rv-finish-go">开始复盘 →</span>
          </button>
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

      <div id="radio-review-stage" class="hidden"></div>
    </div>
  </section>

  <!-- 3C. ONE-HANDED SWIPE SANCTUARY ("记词" · 临考语法全表盘点共用第 3 栏，盘完自动收起) -->
  <section class="zen-panel hidden" id="vocab-view">
    <div class="vc-subnav" id="vc-subnav" style="display:none;">
      <div class="vc-subtabs">
        <button type="button" class="vc-subtab active" id="vsub-vocab" onclick="switchVocabSubMode('vocab')">记词<span class="vc-subtab-cnt" id="vsub-vocab-cnt"></span></button>
        <button type="button" class="vc-subtab" id="vsub-ga" onclick="switchVocabSubMode('ga')">语法盘点<span class="vc-subtab-cnt" id="vsub-ga-cnt"></span></button>
      </div>
      <span class="vc-submeta" id="vc-submeta"></span>
    </div>
    <div class="stage-wrap" id="vocab-stage-box"></div>
  </section>

  <!-- 3D. ZEN LEDGER ("总表") -->
  <section class="zen-panel hidden" id="dash-view">
    <div class="ledger-scroll">
      <div id="night-flash-entry"></div>
      <div id="dash-roi-focus"></div>
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

  <!-- 3E. NATIVE ZEN BODY MODULE ("体律" · Open-Washi Zen · 零明文隐私) -->
  <section class="zen-panel hidden" id="body-view">
    <div class="zb-locked" id="zb-locked" style="display:none;">
      <svg width="38" height="38" viewBox="0 0 28 28" aria-hidden="true">
        <circle cx="14" cy="14" r="10.2" fill="none" stroke="var(--moss)" stroke-width="2.1" stroke-dasharray="55 10" stroke-linecap="round"/>
      </svg>
      <div class="zb-locked-title">体律</div>
      <p class="zb-locked-sub">体重、体脂与运动数据加密锁存。<br />首次输入短口令解锁，本机以后自动记住。</p>
      <div class="zb-pass-row">
        <input class="zb-pass-in" id="zb-pass-in" type="text" autocomplete="off" autocapitalize="none" spellcheck="false" placeholder="输入短口令" onkeydown="if(event.key==='Enter')ZB.unlockPass()" />
        <button class="zb-btn-primary" id="zb-unlock-btn" style="flex:0 0 auto; height:46px; padding:0 22px;" onclick="ZB.unlockPass()">解锁</button>
      </div>
      <div id="zb-lock-err" style="font-size:12.5px; color:var(--bengara); margin-top:10px; min-height:18px;"></div>
    </div>

    <div id="zb-app" style="display:none; flex:1; min-height:0; flex-direction:column;">
      <div class="zb-subnav">
        <div class="zb-subtabs" id="zb-subtabs">
          <button class="zb-subtab active" data-zbt="today" onclick="ZB.setTab('today')">今日</button>
          <button class="zb-subtab" data-zbt="pullup" onclick="ZB.setTab('pullup')">引体</button>
          <button class="zb-subtab" data-zbt="body" onclick="ZB.setTab('body')">体脂</button>
          <button class="zb-subtab" data-zbt="ledger" onclick="ZB.setTab('ledger')">总账</button>
          <span class="zb-sub-bar" id="zb-sub-bar"></span>
        </div>
        <span class="zb-date-tag" id="zb-date-lbl"></span>
      </div>

      <div class="zb-ptr" id="zb-ptr" aria-hidden="true">
        <svg class="zb-ptr-svg" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="8.5" fill="none" stroke="var(--hairline-strong)" stroke-width="1.6"/>
          <circle id="zb-ptr-arc" cx="12" cy="12" r="8.5" pathLength="100" fill="none" stroke="var(--moss)" stroke-width="2" stroke-linecap="round" stroke-dasharray="0 100" transform="rotate(-90 12 12)"/>
        </svg>
        <span class="zb-ptr-lbl" id="zb-ptr-lbl">下拉同步</span>
      </div>

      <div class="zb-stage" id="zb-stage">
        <div class="zb-panel active" id="zb-p-today">
          <div class="zb-ma"></div>
          <div class="zb-context">
            <span class="zb-tier" id="zb-tier-txt"></span>
            <button type="button" class="zb-pz-btn" id="zb-pz-btn" onclick="ZB.openPZList()"></button>
          </div>
          <div class="zb-pz-track"><div class="zb-pz-fill" id="zb-pz-fill"></div></div>
          <h2 class="zb-title" id="zb-title"></h2>
          <button type="button" class="zb-guide-row" id="zb-pelo-row" onclick="ZB.openPeloGuide()">
            <span class="zb-guide-txt" id="zb-pelo-short"></span>
            <span class="zb-guide-link" id="zb-pelo-link">找课 ›</span>
          </button>

          <div class="zb-state-block" id="zb-state-block">
            <div class="zb-state-bar" id="zb-state-bar">
              <button type="button" class="zb-state-btn" id="zb-st-normal" onclick="ZB.setState('normal')">常规</button>
              <button type="button" class="zb-state-btn" id="zb-st-bb" onclick="ZB.setState('bb')">打了篮球</button>
              <button type="button" class="zb-state-btn" id="zb-st-tired" onclick="ZB.setState('tired')">偏累</button>
              <button type="button" class="zb-state-btn" id="zb-st-rest" onclick="ZB.setState('rest')">休息日</button>
            </div>
            <div class="zb-substate-bar" id="zb-substate-bar"></div>
          </div>

          <div class="zb-cta-row">
            <button type="button" class="zb-btn-primary" id="zb-main-btn" onclick="ZB.logCardio('main')"></button>
          </div>

          <div class="zb-aux-row">
            <button type="button" class="zb-btn-quiet" onclick="switchMode('radio', true)">听《锵锵》↗</button>
            <div class="zb-aux-grp">
              <button type="button" class="zb-btn-quiet" id="zb-alt-btn" style="display:none;" onclick="ZB.logCardio('recovery')"></button>
              <span class="zb-week-quiet" id="zb-week-txt"></span>
            </div>
          </div>

          <div class="zb-ritual-list">
            <div class="zb-ritual-row">
              <div class="zb-ritual-left">
                <span class="zb-ritual-name">家里引体</span>
                <span class="zb-ritual-hint" id="zb-pu-hint"></span>
              </div>
              <div class="zb-ritual-right" id="zb-pu-dots"></div>
            </div>
            <div class="zb-ritual-row">
              <div class="zb-ritual-left" onclick="ZB.openProteinGuide()" style="cursor:pointer;">
                <span class="zb-ritual-name">饮食节律 ›</span>
                <span class="zb-ritual-hint" id="zb-diet-hint">蛋白够 · 晚未爆碳</span>
              </div>
              <div class="zb-ritual-right">
                <button type="button" class="zb-tap-check" id="zb-diet-btn" onclick="ZB.toggleDiet()"></button>
              </div>
            </div>
          </div>
          <div class="zb-ma-tail"></div>
        </div>

        <div class="zb-panel" id="zb-p-pullup">
          <div class="zb-ma"></div>
          <div class="zb-context">
            <span id="zb-pu-eyebrow"></span>
            <span id="zb-pu-pr"></span>
          </div>
          <h2 class="zb-title" id="zb-pu-title"></h2>
          <div class="zb-guide-txt" id="zb-pu-sub"></div>

          <div class="zb-rep-row">
            <div>
              <div style="font-size:15px; color:var(--sumi); font-weight:500;">本轮徒手</div>
              <div style="font-size:12.5px; color:var(--ink-3); margin-top:3px;" id="zb-pu-neg"></div>
            </div>
            <div class="zb-stepper">
              <button type="button" class="zb-step-btn" onclick="ZB.adjStrict(-1)">−</button>
              <span class="zb-step-val" id="zb-pu-val">1</span>
              <button type="button" class="zb-step-btn" onclick="ZB.adjStrict(1)">+</button>
            </div>
          </div>

          <div class="zb-pacer" id="zb-pacer">
            <div class="zb-pacer-ring">
              <svg class="zb-pacer-svg" viewBox="0 0 100 100" aria-hidden="true">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--track)" stroke-width="2.6"/>
                <circle id="zb-pacer-arc" cx="50" cy="50" r="42" pathLength="100" fill="none" stroke="var(--moss)" stroke-width="3.2" stroke-linecap="round" stroke-dasharray="100 100" transform="rotate(-90 50 50)"/>
              </svg>
              <div class="zb-pacer-num" id="zb-pacer-num">4</div>
            </div>
            <div class="zb-pacer-phase" id="zb-pacer-phase">准备抓稳单杠</div>
            <div class="zb-pacer-ctrls">
              <button type="button" class="zb-btn-quiet" id="zb-pacer-snd" onclick="ZB.togglePacerSound()">轻音：关</button>
              <button type="button" class="zb-btn-quiet" onclick="ZB.stopPacer(true)">停止</button>
            </div>
          </div>

          <div class="zb-cta-row" style="margin-top:20px;">
            <button type="button" class="zb-btn-primary" id="zb-pu-log" onclick="ZB.logPU()"></button>
          </div>
          <div class="zb-aux-row">
            <div style="display:flex; align-items:center; gap:16px;">
              <button type="button" class="zb-btn-quiet" id="zb-pacer-btn" onclick="ZB.togglePacer()">4 秒慢放节拍</button>
              <button type="button" class="zb-btn-quiet" id="zb-pu-undo" style="display:none;" onclick="ZB.undoPU()">撤销</button>
            </div>
            <button type="button" class="zb-btn-quiet" onclick="ZB.openBandGuide()">换绳路线 ›</button>
          </div>

          <div class="zb-res-row">
            <div class="zb-ritual-left">
              <span class="zb-ritual-name" style="font-size:14px;">全身护肌（可选）</span>
              <span class="zb-ritual-hint" id="zb-res-hint">本周 0/2 次 · 俯卧撑+自重深蹲</span>
            </div>
            <button type="button" class="zb-tap-check" id="zb-res-btn" onclick="ZB.toggleRes()">记 5 分钟</button>
          </div>

          <div class="zb-ladder" id="zb-pu-ladder"></div>
          <div class="zb-ma-tail"></div>
        </div>

        <div class="zb-panel" id="zb-p-body">
          <div class="zb-ma"></div>
          <div class="zb-context">
            <span id="zb-bctx">GE 体脂</span>
            <span id="zb-pace"></span>
          </div>
          <div class="zb-stat-pair">
            <div>
              <div class="zb-stat-big" id="zb-bf-big">--<span class="zb-stat-unit">%</span></div>
              <div class="zb-stat-sub" id="zb-bf-sub"></div>
            </div>
            <div style="text-align:right;">
              <div class="zb-stat-big" style="font-size:24px; color:var(--ink-2);" id="zb-wt-big">--<span class="zb-stat-unit">kg</span></div>
              <div class="zb-stat-sub" id="zb-wt-sub"></div>
            </div>
          </div>
          <div class="zb-chart-wrap" id="zb-chart" data-zb-noswipe="1"></div>
          <div class="zb-chart-sw">
            <div class="zb-sw-grp">
              <button type="button" class="zb-btn-quiet" id="zb-m-bf" onclick="ZB.setMetric('bf')">体脂</button>
              <button type="button" class="zb-btn-quiet" id="zb-m-wt" onclick="ZB.setMetric('wt')">体重</button>
            </div>
            <div class="zb-sw-grp">
              <button type="button" class="zb-btn-quiet" id="zb-r-90" onclick="ZB.setRange('90')">90天</button>
              <button type="button" class="zb-btn-quiet" id="zb-r-all" onclick="ZB.setRange('all')">两年</button>
            </div>
          </div>

          <div class="zb-weigh-drawer" id="zb-wform" data-zb-noswipe="1">
            <div class="zb-dial-row">
              <div class="zb-dial-head">
                <span class="zb-dial-lbl">体重 (kg)</span>
                <div class="zb-dial-ctrl">
                  <button type="button" class="zb-step-btn" style="width:28px;height:28px;font-size:14px;" onclick="ZB.nudgeDial('wt',-0.1)">−</button>
                  <span id="zb-dwt-slot"><button type="button" class="zb-dial-val" id="zb-dwt-val" onclick="ZB.editDial('wt')">81.5</button></span>
                  <button type="button" class="zb-step-btn" style="width:28px;height:28px;font-size:14px;" onclick="ZB.nudgeDial('wt',0.1)">+</button>
                </div>
              </div>
              <div class="zb-dial-track" id="zb-dwt-track" data-zb-noswipe="1"><div class="zb-dial-ticks" id="zb-dwt-ticks"></div><div class="zb-dial-needle"></div></div>
            </div>
            <div class="zb-dial-row">
              <div class="zb-dial-head">
                <span class="zb-dial-lbl">GE 体脂 (%)</span>
                <div class="zb-dial-ctrl">
                  <button type="button" class="zb-step-btn" style="width:28px;height:28px;font-size:14px;" onclick="ZB.nudgeDial('bf',-0.1)">−</button>
                  <span id="zb-dbf-slot"><button type="button" class="zb-dial-val" id="zb-dbf-val" onclick="ZB.editDial('bf')">18.0</button></span>
                  <button type="button" class="zb-step-btn" style="width:28px;height:28px;font-size:14px;" onclick="ZB.nudgeDial('bf',0.1)">+</button>
                </div>
              </div>
              <div class="zb-dial-track" id="zb-dbf-track" data-zb-noswipe="1"><div class="zb-dial-ticks" id="zb-dbf-ticks"></div><div class="zb-dial-needle"></div></div>
            </div>
            <div class="zb-waist-row">
              <span class="zb-dial-lbl">空腹腰围 (cm · 可选)</span>
              <input id="zb-waist-in" class="zb-waist-in" type="number" step="0.1" inputmode="decimal" placeholder="两周记一次" />
            </div>
            <div class="zb-dial-foot">
              <button type="button" class="zb-btn-quiet" id="zb-dskip-btn" onclick="ZB.toggleSkipBf()">仅记体重</button>
              <button type="button" class="zb-btn-primary" style="flex:0 0 auto; height:40px; padding:0 22px; font-size:14px;" onclick="ZB.saveWeigh()">记下</button>
            </div>
          </div>

          <div class="zb-aux-row" style="margin-top:14px;">
            <span style="font-size:12.5px; color:var(--ink-3);" id="zb-wrem"></span>
            <button type="button" class="zb-btn-quiet" id="zb-wbtn" onclick="ZB.toggleWForm()">记一次称重</button>
          </div>
          <div class="zb-ma-tail"></div>
        </div>

        <div class="zb-panel" id="zb-p-ledger">
          <div class="zb-kpis" id="zb-kpis"></div>
          <button type="button" class="zb-ledger-pz" id="zb-ledger-pz" onclick="ZB.openPZList()"></button>
          <div class="zb-ledger-list" id="zb-lrows"></div>
          <div class="zb-sync-foot">
            <div class="zb-sync-left">
              <span id="zb-sync-txt">加密同步就绪</span>
              <button type="button" class="zb-btn-quiet" id="zb-gaps-btn" style="display:none; padding:4px 0; font-size:12.5px;" onclick="ZB.openGapsGuide()"></button>
            </div>
            <button type="button" class="zb-btn-quiet" onclick="ZB.syncNow()">同步</button>
          </div>
        </div>
      </div>
    </div>
    <div class="zb-toast" id="zb-toast"></div>
  </section>

  <!-- 3F. GLOBAL FLOATING MINI RADIO BAR (跨 Tab 无缝随身听) -->
  <aside class="radio-mini-bar hidden" id="radio-mini-bar" onclick="onMiniBarTap(event)">
    <div class="rmb-progress-rail"><div class="rmb-progress-fill" id="rmb-progress-fill"></div></div>
    <div class="rmb-body">
      <div class="rmb-left">
        <span class="rmb-wave-icon" id="rmb-wave-icon">
          <span class="rmb-bar"></span><span class="rmb-bar"></span><span class="rmb-bar"></span>
        </span>
        <div class="rmb-meta">
          <span class="rmb-title" id="rmb-title">锵锵三人行</span>
          <span class="rmb-time" id="rmb-time">00:00 / 60:00</span>
        </div>
      </div>
      <div class="rmb-actions">
        <button type="button" class="rmb-play-btn" id="rmb-play-btn" onclick="onMiniBarPlayToggle(event)" aria-label="播放/暂停">播放</button>
        <button type="button" class="rmb-jump-btn" onclick="onMiniBarJump(event)" aria-label="回到随身听">随身听 ›</button>
      </div>
    </div>
  </aside>

  <!-- 4. RIGHT-THUMB NAV (phone only · 上看下点: top is for reading, bottom-right is for touching; mirrors the old top header, no ornament) -->
  <nav class="thumb-nav" aria-label="切换">
    <div class="thumb-tabs" id="main-thumb-tabs">
      <span class="thumb-ink-bar" id="main-thumb-bar"></span>
      <button class="thumb-link active" id="btab-tutor" onclick="switchMode('tutor')">做题</button>
      <button class="thumb-link" id="btab-radio" onclick="switchMode('radio', true)">随身听</button>
      <button class="thumb-link" id="btab-vocab" onclick="switchMode('vocab')">记词</button>
      <button class="thumb-link" id="btab-body" onclick="switchMode('body')">体律</button>
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
const RADIO_SPEEDS = [0.85, 1.0, 1.15, 1.3];
const ADAPTIVE_KEY = "n3_adaptive_v13_" + DATA.plan_date;
const RADIO_SIG = String((DATA.radio && DATA.radio.script_sig) || "").slice(0, 8);
const LEGACY_RADIO_POS_KEY = "n3_radio_pos_" + (DATA.radio.date || DATA.plan_date);
const RADIO_POS_KEY = LEGACY_RADIO_POS_KEY + (RADIO_SIG ? "_" + RADIO_SIG : "");
const TODAY_TAG = String(DATA.plan_date || "").replace(/-/g, "");
const TRUE_GREEN_EPOCH = Number(DATA.true_green_epoch || 1794761500);
const BAKED_EPOCH = Number(DATA.baked_epoch || 0);
const MIN_REAL_TS = 1700000000;
const VOCAB_BATCH_SIZE = Number(DATA.vocab_daily_count || 24);

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
    const radioSessionLive = (typeof radioHasPlayedOnce !== "undefined") && radioHasPlayedOnce;
    if (document.visibilityState === "visible" && !activeKind && radioIdle && !radioSessionLive) {
      if (typeof reloadFreshEdition === "function") reloadFreshEdition();
      else location.reload();
    } else if (typeof pendingEditionReload !== "undefined") {
      pendingEditionReload = true;
    }
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
      retryCardId: "",
      passStreak: 0,
      reqPasses: 1,
      lastChoiceOrder: null,
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
    hotFamilyDueStep: 0,
    hesitantKeys: {},
    radioMaxSec: 0,
    radioPos: [0, 0],
    radioSig: RADIO_SIG,
    flashProg: [0, 0, 0, 0],
    vocabSess: null,
    radioReview: null,
    gaProg: [0, 0, 0, 0],
    gaMap: {},
    gaSess: null,
    pts: pts,
    tappedWords: [],
    wordLookups: {},
    masteryOverrides: {},
    masteryOverrideTs: {},
    recentRecords: []
  };
}

const GA_STORE_KEY = "n3_ga_map_v1";

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

function mergeGaProgTuple(st, gp) {
  if (!Array.isArray(gp) || gp.length < 3) return false;
  const cur = Array.isArray(st.gaProg) ? st.gaProg : [0, 0, 0, 0];
  const sSeen = Math.max(0, Math.floor(gp[0] || 0));
  const sTgt = Math.max(0, Math.floor(gp[1] || 0));
  const sDone = Math.max(0, Math.floor(gp[2] || 0));
  const sUpd = Math.max(0, Math.floor(gp[3] || 0));
  const nSeen = Math.max(Math.floor(cur[0] || 0), sSeen);
  const nDone = Math.max(Math.floor(cur[2] || 0), sDone);
  const nUpd = Math.max(Math.floor(cur[3] || 0), sUpd);
  let nTgt = (sUpd >= Math.floor(cur[3] || 0) && sTgt > 0) ? sTgt : (Math.floor(cur[1] || 0) || sTgt);
  nTgt = Math.max(nSeen, nTgt);
  const next = [nSeen, nTgt, nDone, nUpd];
  if (String(next) === String(cur)) return false;
  st.gaProg = next;
  return true;
}

function mergeGaMapEntry(st, gid, code, ts, dayTag) {
  if (!gid) return false;
  const c = Math.floor(code || 0);
  const t = Math.floor(ts || 0);
  if (t < MIN_REAL_TS || c < 0 || c > 4) return false;
  if (!st.gaMap || typeof st.gaMap !== "object") st.gaMap = {};
  const cur = st.gaMap[gid];
  const curTs = Array.isArray(cur) ? Math.floor(cur[1] || 0) : 0;
  const curCode = Array.isArray(cur) ? Math.floor(cur[0] || 0) : 0;
  if (t > curTs || (t === curTs && c > curCode)) {
    st.gaMap[gid] = [c, t, String(dayTag || (Array.isArray(cur) ? cur[2] : "") || TODAY_TAG)];
    return true;
  }
  return false;
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
      ps.retryCardId = "";
    } else if (ps.retestAt >= minTs) {
      ps.status = "learning";
      if (!ps.reqPasses || ps.reqPasses < 1) {
        ps.reqPasses = (p.primary && p.primary.is_listening && p.variants && p.variants.length > 0) ? 2 : 1;
      }
    } else {
      ps.status = "unseen";
    }
  });
}

// Seed from repo cloud_state_snapshot + union-merge ALL historical localStorage keys (v5..v13)
function loadAdaptiveState() {
  const base = createFreshAdaptiveState();

  // 0. Seed baked Grammar Audit verdicts from DATA.grammar_audit.items & cross-day local cache
  try {
    const gaItems = (DATA.grammar_audit && Array.isArray(DATA.grammar_audit.items)) ? DATA.grammar_audit.items : [];
    gaItems.forEach(it => {
      if (it && it.gid && it.verdict > 0 && (it.audit_ts || 0) >= MIN_REAL_TS) {
        mergeGaMapEntry(base, it.gid, it.verdict, it.audit_ts, it.audit_date || "");
      }
    });
    const savedGa = JSON.parse(localStorage.getItem(GA_STORE_KEY) || "null");
    if (savedGa && typeof savedGa === "object") {
      Object.keys(savedGa).forEach(gk => {
        const gv = savedGa[gk];
        if (Array.isArray(gv) && gv.length >= 2) mergeGaMapEntry(base, gk, gv[0], gv[1], gv[2] || "");
      });
    }
  } catch (e) {}

  // 1. Seed from cloud_state_snapshot.json / practice_log.jsonl baked into DATA.cloud_sync
  const radioDurCap = Math.max(60, Math.floor((DATA.radio && DATA.radio.duration_sec) || 3400) - 8);
  const clampRadioSec = (s) => Math.max(0, Math.min(radioDurCap, Math.floor(Number(s) || 0)));
  try {
    const cs = DATA.cloud_sync || {};
    const sd = cs.seeded_day || {};
    if (typeof sd.resetAt === "number" && sd.resetAt > base.resetAt) base.resetAt = Math.floor(sd.resetAt);
    if (typeof sd.radioMaxSec === "number" && sd.radioMaxSec > base.radioMaxSec) base.radioMaxSec = Math.floor(sd.radioMaxSec);
    if (Array.isArray(sd.radioPos) && sd.radioPos.length === 2 && (sd.radioPos[1] || 0) > (base.radioPos[1] || 0)) {
      base.radioPos = [clampRadioSec(sd.radioPos[0]), Math.floor(sd.radioPos[1] || 0)];
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
    if (Array.isArray(sd.gaProg)) mergeGaProgTuple(base, sd.gaProg);
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
    const sga = cs.seeded_ga || {};
    Object.keys(sga).forEach(gk => {
      const gv = sga[gk];
      if (Array.isArray(gv) && gv.length >= 2) mergeGaMapEntry(base, gk, gv[0], gv[1], gv[2] || "");
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
        if (Array.isArray(saved.gaProg)) mergeGaProgTuple(base, saved.gaProg);
        if (saved.vocabSess && saved.vocabSess.date === DATA.plan_date && Array.isArray(saved.vocabSess.queue)) {
          if (!base.vocabSess || (saved.vocabSess.updatedAt || 0) >= (base.vocabSess.updatedAt || 0)) {
            base.vocabSess = saved.vocabSess;
          }
        }
        if (saved.radioReview && saved.radioReview.sig === RADIO_SIG && saved.radioReview.date === DATA.plan_date) {
          const curScore = base.radioReview ? ((base.radioReview.done ? 999 : 0) + (base.radioReview.triageIdx || 0) + ((base.radioReview.tailDoneIds || []).length)) : -1;
          const newScore = (saved.radioReview.done ? 999 : 0) + (saved.radioReview.triageIdx || 0) + ((saved.radioReview.tailDoneIds || []).length);
          if (newScore >= curScore) base.radioReview = saved.radioReview;
        }
        if (saved.gaSess && saved.gaSess.date === DATA.plan_date && Array.isArray(saved.gaSess.queue)) {
          if (!base.gaSess || (saved.gaSess.updatedAt || 0) >= (base.gaSess.updatedAt || 0)) {
            base.gaSess = saved.gaSess;
          }
        }
        if (saved.gaMap && typeof saved.gaMap === "object") {
          Object.keys(saved.gaMap).forEach(gk => {
            const gv = saved.gaMap[gk];
            if (Array.isArray(gv) && gv.length >= 2) mergeGaMapEntry(base, gk, gv[0], gv[1], gv[2] || "");
          });
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
        if (Array.isArray(saved.radioPos) && saved.radioPos.length === 2) {
          const sSec = clampRadioSec(saved.radioPos[0]);
          const sTs = Math.floor(saved.radioPos[1] || 0);
          const bSec = Math.floor((base.radioPos && base.radioPos[0]) || 0);
          const bTs = Math.floor((base.radioPos && base.radioPos[1]) || 0);
          // Never let an accidental 0-2s glitch overwrite a real same-day resume spot unless user explicitly finished/reset
          const incomingReal = sSec > 2 || bSec <= 2;
          if (incomingReal && (sTs > bTs || (sTs === bTs && sSec > bSec))) {
            base.radioPos = [sSec, sTs];
          }
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
        if (saved.wordLookups && typeof saved.wordLookups === "object") {
          Object.keys(saved.wordLookups).forEach(wk => {
            const wv = saved.wordLookups[wk];
            if (Array.isArray(wv) && wv.length >= 2) {
              const curW = base.wordLookups[wk] || [0, 0, ""];
              base.wordLookups[wk] = [
                Math.max(curW[0] || 0, Math.floor(wv[0] || 0)),
                Math.max(curW[1] || 0, Math.floor(wv[1] || 0)),
                String(wv[2] || curW[2] || "")
              ];
            }
          });
        }
        if (saved.pts && typeof saved.pts === "object") {
          Object.keys(saved.pts).forEach(rawId => {
            const pid = CARD_TO_POINT_ID[rawId] || rawId;
            const sp = saved.pts[rawId];
            const cur = base.pts[pid];
            if (!sp || !cur) return;
            if (sp.retryCardId) cur.retryCardId = String(sp.retryCardId);
            if (typeof sp.passStreak === "number") cur.passStreak = Math.max(cur.passStreak || 0, Math.floor(sp.passStreak));
            if (typeof sp.reqPasses === "number") cur.reqPasses = Math.max(cur.reqPasses || 1, Math.floor(sp.reqPasses));
            if (sp.lastChoiceOrder && typeof sp.lastChoiceOrder === "object") cur.lastChoiceOrder = sp.lastChoiceOrder;
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

    let bestLocalRadioPos = 0;
    const legacyRadioPos = parseFloat(localStorage.getItem(LEGACY_RADIO_POS_KEY) || "0");
    const savedRadioPos = parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0");
    bestLocalRadioPos = Math.max(bestLocalRadioPos, legacyRadioPos || 0, savedRadioPos || 0);
    // Also check any earlier same-day revision keys (e.g. after a same-day audio re-render)
    const dayPosPrefix = LEGACY_RADIO_POS_KEY + "_";
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(dayPosPrefix)) {
        const v = parseFloat(localStorage.getItem(k) || "0");
        if (v > bestLocalRadioPos) bestLocalRadioPos = v;
      }
    }
    if (bestLocalRadioPos > base.radioMaxSec) base.radioMaxSec = Math.floor(bestLocalRadioPos);
    if (bestLocalRadioPos > 2 && ((base.radioPos[1] || 0) === 0 || (base.radioPos[0] || 0) <= 2)) {
      base.radioPos = [clampRadioSec(bestLocalRadioPos), Math.max(2, base.radioPos[1] || 0)];
    }
    // Safety fallback: if mid-episode (heard >10s, not finished) but radioPos somehow read <=2s, recover near radioMaxSec
    if ((base.radioPos[0] || 0) <= 2 && base.radioMaxSec > 10 && base.radioMaxSec < radioDurCap - 20) {
      base.radioPos = [clampRadioSec(Math.max(0, base.radioMaxSec - 3)), Math.max(2, base.radioPos[1] || 0)];
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
  try {
    if (A.gaMap && Object.keys(A.gaMap).length) {
      localStorage.setItem(GA_STORE_KEY, JSON.stringify(A.gaMap));
    }
  } catch (e) {}
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
  if (action === "recover" || curObj.mstate === `todo:${d}`) {
    return `todo:${d}`;
  }
  if (curObj.tier === "done") return "done";
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
  if (Array.isArray(A.gaProg) && (A.gaProg[0] > 0 || A.gaProg[2] > 0)) {
    pkt.gp = [
      Math.floor(A.gaProg[0] || 0),
      Math.floor(A.gaProg[1] || 0),
      Math.floor(A.gaProg[2] || 0),
      Math.floor(A.gaProg[3] || 0)
    ];
    size += byteLen(JSON.stringify(pkt.gp)) + 7;
  }
  if (A.radioReview && A.radioReview.sig === RADIO_SIG && A.radioReview.date === DATA.plan_date) {
    const rvDoneFlag = A.radioReview.done ? 1 : 0;
    const rvIdx = Math.floor(A.radioReview.triageIdx || 0);
    if (rvDoneFlag || rvIdx > 0) {
      pkt.rv = [rvDoneFlag, rvIdx, Math.floor(A.radioReview.updatedAt || nowUnixSec())];
      size += byteLen(JSON.stringify(pkt.rv)) + 7;
    }
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
  const gaEntries = Object.keys(A.gaMap || {})
    .map(k => {
      const gv = A.gaMap[k];
      return Array.isArray(gv) && gv.length >= 2 ? [k, [Math.floor(gv[0] || 0), Math.floor(gv[1] || 0)]] : null;
    })
    .filter(kv => kv && kv[1][1] >= deltaFloor)
    .sort((x, y) => y[1][1] - x[1][1]);
  if (gaEntries.length) {
    pkt.ga = {};
    size += 7;
    for (const kv of gaEntries) {
      const add = byteLen(JSON.stringify(kv[0]) + ":" + JSON.stringify(kv[1])) + 1;
      if (size + add > CLOUD_BYTE_LIMIT - 220) break;
      pkt.ga[kv[0]] = kv[1];
      size += add;
    }
    if (!Object.keys(pkt.ga).length) delete pkt.ga;
    else pkt.ga = sortedMap(pkt.ga);
  }
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
    gp: Array.isArray(pkt.gp) ? [Math.floor(pkt.gp[0] || 0), Math.floor(pkt.gp[1] || 0), Math.floor(pkt.gp[2] || 0)] : [],
    rv: Array.isArray(pkt.rv) ? [Math.floor(pkt.rv[0] || 0), Math.floor(pkt.rv[1] || 0)] : [],
    ga: sortedMap(pkt.ga || {}),
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
    if (pktVer >= 15 && pkt.ga && typeof pkt.ga === "object") {
      const pDayTag = String(pkt.d || "").replace(/-/g, "") || TODAY_TAG;
      Object.keys(pkt.ga).forEach(gk => {
        const gv = pkt.ga[gk];
        if (Array.isArray(gv) && gv.length >= 2) {
          if (mergeGaMapEntry(A, gk, gv[0], gv[1], gv[2] || pDayTag)) changed = true;
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
    if (pktVer >= 15 && Array.isArray(pkt.gp) && mergeGaProgTuple(A, pkt.gp)) {
      changed = true;
    }
    if (Array.isArray(pkt.rv) && pkt.rv.length >= 2) {
      const rvDoneIn = !!pkt.rv[0];
      const rvIdxIn = Math.max(0, Math.floor(pkt.rv[1] || 0));
      const rvTsIn = Math.floor(pkt.rv[2] || 0);
      const curRv = ensureRadioReviewState(false);
      const curDone = !!curRv.done;
      const curIdx = Math.floor(curRv.triageIdx || 0);
      if ((rvDoneIn && !curDone) || (!curDone && rvIdxIn > curIdx)) {
        curRv.done = curDone || rvDoneIn;
        curRv.triageIdx = Math.max(curIdx, rvIdxIn);
        if (curRv.done) curRv.tailQueue = [];
        curRv.updatedAt = Math.max(curRv.updatedAt || 0, rvTsIn);
        changed = true;
      }
    }

    if (Array.isArray(pkt.rp) && pkt.rp.length === 2) {
      const durCap = Math.max(60, Math.floor((DATA.radio && DATA.radio.duration_sec) || 3400) - 8);
      const rpSec = Math.max(0, Math.min(durCap, Math.floor(pkt.rp[0] || 0)));
      const rpTs = Math.floor(pkt.rp[1] || 0);
      const mySec = Math.floor((A.radioPos && A.radioPos[0]) || 0);
      const myTs = (A.radioPos && A.radioPos[1]) || 0;
      const incomingReal = rpSec > 2 || mySec <= 2;
      if (incomingReal && (rpTs > myTs || (rpTs === myTs && rpSec > mySec))) {
        A.radioPos = [rpSec, rpTs];
        A.radioSig = RADIO_SIG;
        writeLocalRadioPos(rpSec);
        if (radioInitialized && radioPlayer.paused && Math.abs((radioPlayer.currentTime || 0) - rpSec) > 1) {
          applyRadioSeek(rpSec);
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

const GA_SPECTRUM = [
  null,
  { code: 1, key: "blank", cls: "s1", label: "陌生", choice: "盘点:陌生" },
  { code: 2, key: "confuse", cls: "s2", label: "易混", choice: "盘点:易混" },
  { code: 3, key: "passive", cls: "s3", label: "看懂", choice: "盘点:看懂" },
  { code: 4, key: "instinct", cls: "s4", label: "本能", choice: "盘点:本能" }
];

const GA_ITEMS_LIST = (DATA.grammar_audit && Array.isArray(DATA.grammar_audit.items)) ? DATA.grammar_audit.items : [];
const GA_SPLIT_MAP = (DATA.grammar_audit && DATA.grammar_audit.split_map && typeof DATA.grammar_audit.split_map === "object")
  ? DATA.grammar_audit.split_map
  : {};
const GA_BY_GID = {};
const GA_BY_NAME = {};
GA_ITEMS_LIST.forEach(it => {
  if (it && it.gid) GA_BY_GID[it.gid] = it;
  if (it && it.name) GA_BY_NAME[it.name] = it;
});

function getEffectiveGA(gid) {
  const item = GA_BY_GID[gid] || null;
  const bakedCode = item ? Math.floor(item.verdict || 0) : 0;
  const bakedTs = item ? Math.floor(item.audit_ts || 0) : 0;
  const bakedDate = item ? String(item.audit_date || "") : "";
  const loc = (A && A.gaMap && Array.isArray(A.gaMap[gid])) ? A.gaMap[gid] : null;
  const locCode = loc ? Math.floor(loc[0] || 0) : 0;
  const locTs = loc ? Math.floor(loc[1] || 0) : 0;
  const locDate = loc ? String(loc[2] || "") : "";
  if (locTs > bakedTs || (locTs === bakedTs && locCode > bakedCode)) {
    return { code: locCode, ts: locTs, date: locDate };
  }
  return { code: bakedCode, ts: bakedTs, date: bakedDate };
}

function getEffectiveParentGA(gid) {
  const children = GA_SPLIT_MAP[gid];
  if (!Array.isArray(children) || !children.length) return getEffectiveGA(gid);
  let worst = 0;
  let maxTs = 0;
  let lastDate = "";
  children.forEach(cgid => {
    const eff = getEffectiveGA(cgid);
    if (eff.code >= 1 && eff.code <= 4) {
      if (worst === 0 || eff.code < worst) worst = eff.code;
      if (eff.ts > maxTs) {
        maxTs = eff.ts;
        lastDate = eff.date || lastDate;
      }
    }
  });
  return { code: worst, ts: maxTs, date: lastDate };
}

function computeGrammarAuditStats() {
  const total = GA_ITEMS_LIST.length;
  const counts = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
  let audited = 0;
  let todayAudited = 0;
  GA_ITEMS_LIST.forEach(it => {
    const eff = getEffectiveGA(it.gid);
    const c = (eff.code >= 1 && eff.code <= 4) ? eff.code : 0;
    counts[c] = (counts[c] || 0) + 1;
    if (c > 0) {
      audited += 1;
      if (eff.date === TODAY_TAG) todayAudited += 1;
    }
  });
  const remaining = Math.max(0, total - audited);
  const dailyBase = Math.max(0, Number((DATA.grammar_audit && DATA.grammar_audit.daily_target) || 39));
  const activeFrom = String((DATA.grammar_audit && DATA.grammar_audit.active_from) || "2026-11-23");
  const gp = Array.isArray(A.gaProg) ? A.gaProg : [0, 0, 0, 0];
  const sessCleared = (A.gaSess && A.gaSess.date === DATA.plan_date) ? Math.floor(A.gaSess.cleared || 0) : 0;
  const sessTotal = (A.gaSess && A.gaSess.date === DATA.plan_date) ? Math.floor(A.gaSess.total || 0) : 0;
  const gaSeen = Math.max(0, Math.floor(gp[0] || 0), sessCleared, todayAudited);
  const availableToday = gaSeen + remaining;
  const requiredToday = (DATA.plan_date >= activeFrom) && dailyBase > 0 && total > 0 && availableToday > 0;
  const defaultTgt = Math.min(dailyBase, Math.max(0, availableToday));
  const gaDone = total > 0 && (
    remaining === 0 ||
    Math.floor(gp[2] || 0) > 0 ||
    !!(A.gaSess && A.gaSess.date === DATA.plan_date && A.gaSess.done) ||
    (defaultTgt > 0 && gaSeen >= defaultTgt)
  );
  const gaTarget = gaDone
    ? Math.max(gaSeen, sessTotal || Math.floor(gp[1] || 0) || defaultTgt)
    : Math.max(gaSeen, sessTotal || Math.floor(gp[1] || 0) || defaultTgt);
  const gaRatio = gaDone ? 1.0 : (gaSeen > 0 && gaTarget > 0 ? Math.min(0.96, gaSeen / gaTarget) : 0);
  const showSubNav = total > 0 && (remaining > 0 || todayAudited > 0);
  return {
    total,
    audited,
    remaining,
    counts,
    todayAudited,
    gaSeen: gaDone ? Math.max(gaSeen, gaTarget) : gaSeen,
    gaTarget,
    gaRatio,
    gaDone,
    requiredToday,
    showSubNav
  };
}

function computeDaily120Metrics() {
  const totalCards = Math.max(1, DATA.points.length);
  const greenCnt = DATA.points.filter(p => A.pts[p.id] && A.pts[p.id].status === "green").length;
  const quizRatio = Math.min(1.0, greenCnt / totalCards);
  const quizDone = greenCnt >= totalCards;

  const radioDur = Math.max(600, DATA.radio.duration_sec || 2100);
  const targetMins = Math.max(1, Math.round(radioDur / 60));
  const listenedSec = Math.min(radioDur, Math.max(0, A.radioMaxSec || 0));
  const listenedMins = Math.min(targetMins, Math.floor(listenedSec / 60));
  const radioAudioRatio = Math.min(1.0, listenedSec / (radioDur * 0.92));
  const radioAudioDone = radioAudioRatio >= 0.98;
  const rvItemsList = (DATA.radio && Array.isArray(DATA.radio.review_items)) ? DATA.radio.review_items : [];
  const rvTotal = rvItemsList.length;
  const rvSt = (A.radioReview && A.radioReview.sig === RADIO_SIG && A.radioReview.date === DATA.plan_date) ? A.radioReview : null;
  const radioReviewDone = rvTotal === 0 || !!(rvSt && rvSt.done);
  const rvCleared = rvSt ? Math.min(rvTotal, Math.max(0, (rvSt.triageIdx || 0) - ((rvSt.tailQueue && rvSt.tailQueue.length) || 0))) : 0;
  const rvRatio = radioReviewDone ? 1.0 : (rvTotal > 0 ? Math.min(0.95, rvCleared / rvTotal) : 1.0);
  // Podcast integrity + Active Retrieval closure: 85% for full 60m audio + 15% for the closing 5-min review chapter!
  const radioRatio = rvTotal > 0
    ? Math.min(1.0, (radioAudioDone ? 1.0 : radioAudioRatio) * 0.85 + rvRatio * 0.15)
    : radioAudioRatio;
  const radioDone = radioAudioDone && radioReviewDone;

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

  const ga = computeGrammarAuditStats();
  const ritual3Ratio = ga.requiredToday
    ? ((flashDone ? 0.5 : flashRatio * 0.5) + (ga.gaDone ? 0.5 : ga.gaRatio * 0.5))
    : flashRatio;
  const ritual3Done = ga.requiredToday ? (flashDone && ga.gaDone) : flashDone;

  const vDone = vItems.filter(it => it.tier === "done").length;
  const vWip = vItems.filter(it => it.tier === "wip").length;
  const baseDone = Number(DATA.vocab_base_done || 10);
  const vocabBonus = Math.min(8, Math.max(0, (vDone - baseDone) * 0.28 + Math.max(0, vWip - 35) * 0.06));

  // Combined 3-ritual daily completion: 50% quiz + 32% podcast + 18% Position #3 (vocab + pre-exam grammar audit)
  const dailyLockPct = Math.min(100, Math.round((quizRatio * 0.50 + radioRatio * 0.32 + ritual3Ratio * 0.18) * 100));

  // Projected JLPT N3 score (/180): 108 base + 12 quiz + 8 podcast + 4 Position #3 + cross-day vocab mastery lift
  const projScore = Math.min(165, Math.round(108 + quizRatio * 12 + (radioDone ? 8 : radioRatio * 8) + ritual3Ratio * 4 + vocabBonus));

  return {
    totalCards,
    greenCnt,
    quizRatio,
    quizDone,
    targetMins,
    listenedMins: radioAudioDone ? targetMins : listenedMins,
    radioAudioDone,
    radioReviewDone,
    radioRatio: radioDone ? 1.0 : radioRatio,
    radioDone,
    flashSeen: flashDone ? Math.max(flashSeen, flashTarget) : flashSeen,
    flashTarget,
    flashRatio,
    flashDone,
    ga,
    ritual3Ratio,
    ritual3Done,
    allThreeDone: quizDone && radioDone && ritual3Done,
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

  if (A.hotFamily && A.step >= (A.hotFamilyDueStep || 0)) {
    const famSiblings = pool.filter(p => p.family === A.hotFamily && A.pts[p.id].dueStep <= A.step);
    if (famSiblings.length) {
      A.hotFamily = null;
      A.hotFamilyDueStep = 0;
      return famSiblings[0].id;
    }
  }

  const ready = pool.filter(p => A.pts[p.id].dueStep <= A.step);
  if (ready.length) {
    const lastPt = A.lastPointId ? getPointById(A.lastPointId) : null;
    const lastFam = (lastPt && lastPt.family) || "";
    ready.sort((a, b) => {
      const penA = (lastFam && a.family === lastFam) ? -0.4 : 0;
      const penB = (lastFam && b.family === lastFam) ? -0.4 : 0;
      const ma = (a.modality === "memorize" ? 0.25 : (a.modality === "both" ? 0.12 : 0)) + (A.pts[a.id].audioPrimed ? 0.10 : 0) + penA;
      const mb = (b.modality === "memorize" ? 0.25 : (b.modality === "both" ? 0.12 : 0)) + (A.pts[b.id].audioPrimed ? 0.10 : 0) + penB;
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
let quizRecallTimer = null;
let quizChoicesRevealed = true;

function clearQuizRecallTimer() {
  if (quizRecallTimer) {
    clearTimeout(quizRecallTimer);
    quizRecallTimer = null;
  }
}

function revealQuizChoicesNow() {
  clearQuizRecallTimer();
  quizChoicesRevealed = true;
  const veil = document.getElementById("quiz-recall-veil");
  if (veil) veil.style.display = "none";
  const list = document.getElementById("quiz-choice-list");
  if (list) list.classList.remove("recall-veiled");
}

function getPointById(pid) {
  return DATA.points.find(p => p.id === pid) || null;
}

function getQuizForPoint(p, pState) {
  if (pState && pState.retryCardId) {
    if (p.primary && p.primary.id === pState.retryCardId) return p.primary;
    const hitV = (p.variants || []).find(v => v.id === pState.retryCardId);
    if (hitV) return hitV;
  }
  if (pState && pState.useVariant && p.variants && p.variants.length > 0) {
    return p.variants[pState.variantIdx % p.variants.length];
  }
  return p.primary;
}

function canShuffleListeningCard(qObj) {
  if (!qObj || !qObj.is_listening) return true;
  const lp = qObj.listen_parts;
  if (!lp || !lp.stem || !Array.isArray(lp.nums) || lp.nums.length < 3 || !lp.opts) return false;
  return (qObj.choices || []).length === 3 && qObj.choices.every(c => !!lp.opts[c]);
}

function prepareChoices(qObj, salt, pState) {
  const arr = (qObj.choices || []).slice();
  if (arr.length < 2 || !canShuffleListeningCard(qObj)) return arr;

  let seed = ((salt || 0) * 9973 + 17) >>> 0;
  for (let i = 0; i < qObj.id.length; i++) {
    seed = (Math.imul(seed, 31) + qObj.id.charCodeAt(i)) >>> 0;
  }
  function nextRand() {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed;
  }
  for (let i = arr.length - 1; i > 0; i--) {
    const j = nextRand() % (i + 1);
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }

  // On any retry (including missing a 2nd/3rd time), strictly guarantee a DIFFERENT option order than last attempt!
  const prev = pState && pState.lastChoiceOrder && pState.lastChoiceOrder.qid === qObj.id
    ? pState.lastChoiceOrder.order
    : null;
  if (Array.isArray(prev) && prev.length === arr.length) {
    const sameFull = arr.every((v, idx) => v === prev[idx]);
    const prevAnsIdx = prev.indexOf(qObj.answer);
    const curAnsIdx = arr.indexOf(qObj.answer);
    if (sameFull || (arr.length >= 3 && prevAnsIdx >= 0 && curAnsIdx === prevAnsIdx)) {
      const first = arr.shift();
      arr.push(first);
    }
  }
  if (pState) {
    pState.lastChoiceOrder = { qid: qObj.id, order: arr.slice() };
  }
  return arr;
}

function setupCurrentTurn(forcedId) {
  clearQuizRecallTimer();
  quizChoicesRevealed = true;
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
  viewStage = (p && p.teach_first && ps && ps.status === "unseen" && !ps.audioPrimed && p.teach) ? "teach" : "quiz";
  activeQuizObj = getQuizForPoint(p, ps);
  const attemptSalt = (ps.wrongCount || 0) * 7 + (ps.passStreak || 0) * 3 + 1;
  currentChoices = prepareChoices(activeQuizObj, attemptSalt, ps);
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
radioPlayer.preload = "auto";
radioPlayer.setAttribute("playsinline", "");
// Attach as active offscreen DOM node (never display:none, preventing background tab throttling/discard)
radioPlayer.style.position = "fixed";
radioPlayer.style.bottom = "-9999px";
radioPlayer.style.left = "-9999px";
radioPlayer.style.width = "1px";
radioPlayer.style.height = "1px";
radioPlayer.style.opacity = "0.001";
radioPlayer.style.pointerEvents = "none";
try { if (document.body) document.body.appendChild(radioPlayer); } catch (e) {}

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
const INTERJECTION_SET = new Set(["はい", "ええ", "うん", "いや", "あれ", "ほら", "あ", "え", "お"]);
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

let qPlaybackRate = 1.0;

function applyPlaybackRate(kind) {
  const rate = (kind === "exp" || kind === "teach" || kind === "done")
    ? expSpeed
    : (kind === "q" ? (qPlaybackRate || 1.0) : 1.0);
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

let listenSeqQueue = [];
let listenSeqTimer = null;

function stopQuizAudio() {
  playReqSeq += 1;
  listenSeqQueue = [];
  qPlaybackRate = 1.0;
  clearQuizRecallTimer();
  if (listenSeqTimer) {
    clearTimeout(listenSeqTimer);
    listenSeqTimer = null;
  }
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
        listenSeqQueue = [];
        activeKind = null;
        syncAudioButtons();
      }
    });
  }
  syncAudioButtons();
}

function stepListeningSequence(seq) {
  if (seq !== playReqSeq) return;
  if (!listenSeqQueue.length) {
    activeKind = null;
    syncAudioButtons();
    return;
  }
  const item = listenSeqQueue.shift();
  const runUrl = url => {
    if (seq !== playReqSeq) return;
    if (audioBlobMap.has(url)) {
      startResolvedClip(audioBlobMap.get(url), "q", seq);
    } else {
      warmAudio(url).then(resolved => startResolvedClip(resolved || url, "q", seq));
    }
  };
  if (item.waitMs > 0) {
    listenSeqTimer = setTimeout(() => {
      listenSeqTimer = null;
      runUrl(item.url);
    }, item.waitMs);
  } else {
    runUrl(item.url);
  }
}

function playQuizQuestionAudio(qObj, toggleIfSame, rateOverride) {
  if (!qObj) return;
  const nextRate = (typeof rateOverride === "number" && rateOverride > 0) ? rateOverride : 1.0;
  const isSameRate = Math.abs((qPlaybackRate || 1.0) - nextRate) < 0.02;
  if (toggleIfSame && isSameRate && activeKind === "q" && (!player.paused || listenSeqQueue.length > 0 || listenSeqTimer)) {
    stopQuizAudio();
    return;
  }
  qPlaybackRate = nextRate;
  if (canShuffleListeningCard(qObj) && qObj.is_listening && qObj.listen_parts && currentChoices.length === 3) {
    if (!radioPlayer.paused) radioPlayer.pause();
    if (listenSeqTimer) {
      clearTimeout(listenSeqTimer);
      listenSeqTimer = null;
    }
    const lp = qObj.listen_parts;
    const urls = [
      { url: lp.stem, waitMs: 0 },
      { url: lp.nums[0], waitMs: 460 },
      { url: lp.opts[currentChoices[0]], waitMs: 70 },
      { url: lp.nums[1], waitMs: 380 },
      { url: lp.opts[currentChoices[1]], waitMs: 70 },
      { url: lp.nums[2], waitMs: 380 },
      { url: lp.opts[currentChoices[2]], waitMs: 70 }
    ];
    urls.forEach(u => warmAudio(u.url));
    const seq = ++playReqSeq;
    listenSeqQueue = urls;
    activeKind = "q";
    syncAudioButtons();
    stepListeningSequence(seq);
    return;
  }
  playMainClip(qObj.q_audio, "q", false);
}

function playMainClip(url, kind, toggleIfSame) {
  if (!url) return;
  if (!radioPlayer.paused) radioPlayer.pause();
  if (toggleIfSame && activeKind === kind && !player.paused) {
    stopQuizAudio();
    return;
  }
  listenSeqQueue = [];
  if (listenSeqTimer) {
    clearTimeout(listenSeqTimer);
    listenSeqTimer = null;
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
  if (activeKind === "q" && listenSeqQueue.length > 0) {
    stepListeningSequence(playReqSeq);
    return;
  }
  activeKind = null;
  syncAudioButtons();
});

function syncAudioButtons() {
  const onQ = activeKind === "q" && (!player.paused || listenSeqQueue.length > 0 || !!listenSeqTimer);
  const orb = document.getElementById("voice-orb");
  if (orb) orb.classList.toggle("speaking", onQ);
  const qBtn = document.getElementById("q-play-btn");
  if (qBtn) {
    qBtn.classList.toggle("playing", onQ);
    qBtn.textContent = onQ ? "暂停" : "读题";
  }
  const qSlowBtn = document.getElementById("q-slow-btn");
  if (qSlowBtn) {
    const onSlow = onQ && qPlaybackRate < 0.95;
    qSlowBtn.textContent = onSlow ? "暂停 0.85x" : "0.85x 慢听";
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
let radioHasPlayedOnce = false;
let lastRadioPauseMs = 0;
let lastMediaPosSyncMs = 0;
let lastMediaTitle = "";
let mediaSessionHandlersBound = false;
let lastSavedSec = -1;
let lastRenderedSegIdx = -1;
let pendingRadioSeekSec = null;
let radioSeekIssuedTarget = null;
let radioBuffering = false;
let radioBufTimer = null;
let radioPauseSaveTimer = null;
let cachedRadioBlobUrl = null;
let radioUsingLocalBlob = false;
let radioCacheFetchStarted = false;
const RADIO_BLOB_CACHE_NAME = "n3-daily-radio-v1";

function writeLocalRadioPos(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  try {
    localStorage.setItem(LEGACY_RADIO_POS_KEY, String(s));
    localStorage.setItem(RADIO_POS_KEY, String(s));
    const dayPrefix = LEGACY_RADIO_POS_KEY + "_";
    const stale = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(dayPrefix) && k !== RADIO_POS_KEY) stale.push(k);
    }
    stale.forEach(k => { try { localStorage.removeItem(k); } catch (e) {} });
  } catch (e) {}
}

function getEffectiveRadioDuration() {
  return (radioPlayer.duration && isFinite(radioPlayer.duration) && radioPlayer.duration > 10)
    ? radioPlayer.duration
    : (DATA.radio.duration_sec || 2400);
}

function setRadioBufferingUI(on) {
  radioBuffering = !!on;
  if (radioBufTimer) {
    clearTimeout(radioBufTimer);
    radioBufTimer = null;
  }
  syncRadioUI();
}

function upgradeRadioToLocalBlobIfPaused() {
  // Never replace src or call load() once playback has started in this session:
  // destroying WebMediaPlayer tears down Chrome Android's MediaSession and breaks Pixel Buds resume.
  if (radioHasPlayedOnce || !cachedRadioBlobUrl || radioUsingLocalBlob || !radioInitialized) return false;
  if (!radioPlayer.paused) return false;
  const keepT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || lastSavedSec || 0);
  radioUsingLocalBlob = true;
  radioSeekIssuedTarget = null;
  radioPlayer.preload = "auto";
  radioPlayer.src = cachedRadioBlobUrl;
  if (keepT > 0) applyRadioSeek(keepT);
  try { radioPlayer.load(); } catch (e) {}
  return true;
}

function primeRadioLocalBlob(allowNetworkDownload) {
  if (cachedRadioBlobUrl || !DATA.radio || !DATA.radio.audio_url) return;
  if (typeof caches === "undefined" || typeof URL === "undefined" || !URL.createObjectURL) return;
  const audioUrl = DATA.radio.audio_url;
  caches.open(RADIO_BLOB_CACHE_NAME).then(cache => {
    return cache.match(audioUrl).then(hit => {
      if (hit) {
        return hit.blob().then(blob => {
          if (blob && blob.size > 100000 && !cachedRadioBlobUrl) {
            cachedRadioBlobUrl = URL.createObjectURL(blob);
            upgradeRadioToLocalBlobIfPaused();
          }
        });
      }
      if (!allowNetworkDownload || radioCacheFetchStarted) return;
      radioCacheFetchStarted = true;
      return fetch(audioUrl, { cache: "force-cache" }).then(res => {
        if (!res || !res.ok) return;
        const copy = res.clone();
        // Evict previous days' daily_radio.mp3 so phone storage stays fixed at 1 episode (~26MB)
        const cleanup = cache.keys().then(keys =>
          Promise.all(keys.map(k => (k.url && !k.url.endsWith(audioUrl.replace(/^\.\//, ""))) ? cache.delete(k) : null))
        ).catch(() => {});
        return Promise.all([cleanup, cache.put(audioUrl, copy).catch(() => {}), res.blob()]).then(([, , blob]) => {
          if (blob && blob.size > 100000 && !cachedRadioBlobUrl) {
            cachedRadioBlobUrl = URL.createObjectURL(blob);
            upgradeRadioToLocalBlobIfPaused();
          }
        });
      }).catch(() => { radioCacheFetchStarted = false; });
    });
  }).catch(() => {});
}

// Immediately check local CacheStorage on page open (~5ms, 0 network); background-cache today's MP3 once idle
primeRadioLocalBlob(false);
setTimeout(() => primeRadioLocalBlob(true), 400);

function applyRadioSeek(sec) {
  const dur = getEffectiveRadioDuration();
  const target = Math.max(0, Math.min(Math.max(0, dur - 2), Number(sec) || 0));
  pendingRadioSeekSec = target;
  radioSeekIssuedTarget = null;
  lastSavedSec = target;
  if (radioPlayer.readyState >= 1) {
    try {
      radioSeekIssuedTarget = target;
      radioPlayer.currentTime = target;
      if (!radioPlayer.seeking && Math.abs((radioPlayer.currentTime || 0) - target) <= 1.5) {
        pendingRadioSeekSec = null;
        radioSeekIssuedTarget = null;
      }
    } catch (e) {}
  }
  updateRadioLiveDisplay(target);
}

function flushPendingRadioSeek() {
  if (pendingRadioSeekSec === null) return false;
  if (radioPlayer.readyState < 1) return false;
  const dur = getEffectiveRadioDuration();
  const target = Math.max(0, Math.min(Math.max(0, dur - 2), pendingRadioSeekSec));
  if (!radioPlayer.seeking && Math.abs((radioPlayer.currentTime || 0) - target) <= 1.5) {
    pendingRadioSeekSec = null;
    radioSeekIssuedTarget = null;
    updateRadioLiveDisplay(radioPlayer.currentTime || target);
    return true;
  }
  // Never re-issue currentTime while an async network seek is already in flight!
  if (radioPlayer.seeking || radioSeekIssuedTarget === target) {
    return false;
  }
  try {
    radioSeekIssuedTarget = target;
    radioPlayer.currentTime = target;
  } catch (e) {}
  if (!radioPlayer.seeking && Math.abs((radioPlayer.currentTime || 0) - target) <= 1.5) {
    pendingRadioSeekSec = null;
    radioSeekIssuedTarget = null;
    updateRadioLiveDisplay(radioPlayer.currentTime || target);
    return true;
  }
  return false;
}

function persistRadioPositionNow(pushNow) {
  if (!radioInitialized || radioPlayer.ended || pendingRadioSeekSec !== null) return;
  const t = Math.floor(radioPlayer.currentTime || 0);
  if (t > 2) {
    lastSavedSec = t;
    A.radioPos = [t, nowUnixSec()];
    A.radioSig = RADIO_SIG;
    if (t > (A.radioMaxSec || 0)) A.radioMaxSec = t;
    writeLocalRadioPos(t);
    saveAdaptiveState();
    if (pushNow) pushCloudSync(true);
  }
}

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
    pillEl.textContent = rm.radioDone
      ? `锵锵三人 · ${hostsLabel} · 今日已圆满 ✓`
      : (rm.radioAudioDone && !rm.radioReviewDone
        ? `锵锵三人 · ${hostsLabel} · 待收尾复盘`
        : `锵锵三人 · ${hostsLabel}`);
  }
  if (seekEl) {
    const curPct = Math.max(0, Math.min(100, ((t || 0) / dur) * 100));
    const maxPct = rm.radioAudioDone ? 100 : Math.max(curPct, Math.min(100, ((A.radioMaxSec || 0) / dur) * 100));
    seekEl.style.background = `linear-gradient(to right, #2D7A56 0%, #2D7A56 ${curPct.toFixed(1)}%, rgba(45, 122, 86, 0.36) ${curPct.toFixed(1)}%, rgba(45, 122, 86, 0.36) ${maxPct.toFixed(1)}%, rgba(28, 27, 24, 0.10) ${maxPct.toFixed(1)}%, rgba(28, 27, 24, 0.10) 100%)`;
  }
}

function ensureRadioReady() {
  if (!radioInitialized) {
    radioInitialized = true;
    const dur = DATA.radio.duration_sec || 2400;
    const localPos = Math.max(
      parseFloat(localStorage.getItem(RADIO_POS_KEY) || "0") || 0,
      parseFloat(localStorage.getItem(LEGACY_RADIO_POS_KEY) || "0") || 0
    );
    const hasState = Array.isArray(A.radioPos) && A.radioPos.length === 2 && (A.radioPos[1] || 0) > 0;
    let savedPos = hasState ? (A.radioPos[0] || 0) : localPos;
    if (savedPos <= 2 && localPos > 2) savedPos = localPos;
    if (savedPos <= 2 && (A.radioMaxSec || 0) > 10 && (A.radioMaxSec || 0) < dur - 25) {
      savedPos = Math.max(0, (A.radioMaxSec || 0) - 3);
    }
    savedPos = Math.max(0, Math.min(Math.max(0, dur - 8), Math.floor(savedPos || 0)));

    document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
    const seekEl = document.getElementById("radio-seek");
    seekEl.max = Math.ceil(dur);
    document.getElementById("radio-tot-time").textContent = formatMMSS(dur);
    renderRadioChapters(0);
    updateRadioArtwork((DATA.radio.chapters && DATA.radio.chapters[0]) || null);

    radioPlayer.preload = "auto";
    if (cachedRadioBlobUrl) {
      radioUsingLocalBlob = true;
      radioPlayer.src = cachedRadioBlobUrl;
    } else {
      radioUsingLocalBlob = false;
      radioPlayer.src = DATA.radio.audio_url;
      primeRadioLocalBlob(true);
    }
    if (savedPos > 2) {
      applyRadioSeek(savedPos);
    } else {
      lastSavedSec = 0;
      updateRadioLiveDisplay(0);
    }
    try { radioPlayer.load(); } catch (e) {}
  } else {
    upgradeRadioToLocalBlobIfPaused();
    const shownT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
    paintRadioSeekProgress(shownT);
  }
  radioPlayer.defaultPlaybackRate = radioSpeed;
  radioPlayer.playbackRate = radioSpeed;
  if ("preservesPitch" in radioPlayer) radioPlayer.preservesPitch = true;
}

function getCurrentRadioSegTitle() {
  const segs = (DATA.radio && DATA.radio.segments) || [];
  if (lastRenderedSegIdx >= 0 && segs[lastRenderedSegIdx] && segs[lastRenderedSegIdx].title) {
    return segs[lastRenderedSegIdx].title;
  }
  const t = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
  for (let i = 0; i < segs.length; i++) {
    if (t >= segs[i].start && t < segs[i].end && segs[i].title) return segs[i].title;
  }
  return (segs[0] && segs[0].title) || "锵锵三人 · 日本文化随身听";
}

function setMediaSessionPlaybackState(state) {
  if (!("mediaSession" in navigator)) return;
  try {
    navigator.mediaSession.playbackState = state;
  } catch (e) {}
}

function updateMediaSessionPosition(force) {
  if (!("mediaSession" in navigator) || typeof navigator.mediaSession.setPositionState !== "function") return;
  const now = Date.now();
  if (!force && (now - lastMediaPosSyncMs) < 4000) return;
  try {
    const dur = (radioPlayer.duration && isFinite(radioPlayer.duration) && radioPlayer.duration > 0)
      ? radioPlayer.duration
      : (DATA.radio && DATA.radio.duration_sec > 0 ? DATA.radio.duration_sec : 0);
    if (!dur || !isFinite(dur) || dur <= 0) return;
    const rawPos = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
    const pos = Math.max(0, Math.min(dur, isFinite(rawPos) ? rawPos : 0));
    const rate = (radioPlayer.playbackRate && isFinite(radioPlayer.playbackRate) && radioPlayer.playbackRate > 0)
      ? radioPlayer.playbackRate
      : (radioSpeed > 0 ? radioSpeed : 1);
    navigator.mediaSession.setPositionState({
      duration: dur,
      playbackRate: rate,
      position: pos
    });
    lastMediaPosSyncMs = now;
  } catch (e) {}
}

function getCurrentRadioArtworkUrl() {
  const segs = (DATA.radio && DATA.radio.segments) || [];
  const chaps = (DATA.radio && DATA.radio.chapters) || [];
  const t = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
  for (let i = 0; i < segs.length; i++) {
    if (t >= segs[i].start && t < segs[i].end) {
      const c = chaps[segs[i].chapter];
      if (c && c.img) return c.img;
      break;
    }
  }
  return (DATA.radio && DATA.radio.artwork_url) || "./icon-512.png";
}

function updateRadioArtwork(chapObj) {
  const artCard = document.getElementById("radio-art-card");
  const artImg = document.getElementById("radio-art-img");
  const artTag = document.getElementById("radio-art-tag");
  if (!artCard || !artImg) return;
  const imgSrc = (chapObj && chapObj.img) || (DATA.radio && DATA.radio.artwork_url) || "";
  if (!imgSrc) {
    artCard.style.display = "none";
    return;
  }
  if (artImg.getAttribute("src") !== imgSrc) {
    artImg.src = imgSrc;
    artImg.alt = (chapObj && chapObj.title) || "";
  }
  if (artTag && chapObj && chapObj.title) {
    artTag.textContent = chapObj.title.replace(/^[①②③④⑤⑥]\s*/, "");
  }
  artCard.style.display = "flex";
}

function renderReviewStoryGalleryHTML() {
  const storyArts = (DATA.radio && Array.isArray(DATA.radio.story_arts)) ? DATA.radio.story_arts : [];
  if (!storyArts.length) return "";
  return `
    <div class="rv-gallery-wrap">
      <div class="rv-gallery-head">
        <span class="rv-gallery-overline">今日故事画卷 · 触景生情</span>
      </div>
      <div class="rv-gallery-scroll">
        ${storyArts.map((art, idx) => `
          <div class="rv-story-art-card" onclick="openStoryArtModal(${idx})">
            <div class="rv-story-art-img-wrap">
              <img src="${escapeHtml(art.img)}" alt="${escapeHtml(art.title)}" class="rv-story-art-img" loading="lazy" />
            </div>
            <div class="rv-story-art-body">
              <div class="rv-story-art-title">${escapeHtml(art.title)}</div>
              <div class="rv-story-art-sub">${escapeHtml(art.subtitle || "")}</div>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function openStoryArtModal(idx) {
  const storyArts = (DATA.radio && Array.isArray(DATA.radio.story_arts)) ? DATA.radio.story_arts : [];
  let art = null;
  if (typeof idx === "number" && storyArts[idx]) {
    art = storyArts[idx];
  } else {
    const t = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
    const segs = (DATA.radio && DATA.radio.segments) || [];
    let curC = 0;
    for (let i = 0; i < segs.length; i++) {
      if (t >= segs[i].start && t < segs[i].end) { curC = segs[i].chapter; break; }
    }
    art = storyArts.find(s => Array.isArray(s.chapters) && s.chapters.includes(curC)) || storyArts[0];
  }
  if (!art) return;
  const modal = document.getElementById("app-modal");
  const content = document.getElementById("modal-content");
  if (!modal || !content) return;
  content.innerHTML = `
    <div class="story-modal-box">
      <div class="story-modal-img-wrap">
        <img src="${escapeHtml(art.img)}" alt="${escapeHtml(art.title)}" class="story-modal-img" />
      </div>
      <div class="story-modal-body">
        <span class="overline warm">文化夜话 · 故事画卷</span>
        <h3 class="story-modal-title">${escapeHtml(art.title)}</h3>
        <p class="story-modal-sub">${escapeHtml(art.subtitle || "")}</p>
        <button type="button" class="rv-btn-pass" style="margin-top:14px;" onclick="closeModal()">关 闭</button>
      </div>
    </div>
  `;
  modal.classList.add("open");
}

function setupMediaSession(segTitle) {
  if (!("mediaSession" in navigator)) return;
  const title = segTitle || getCurrentRadioSegTitle();
  try {
    if (!navigator.mediaSession.metadata || lastMediaTitle !== title) {
      let artwork = [];
      try {
        const segArt = getCurrentRadioArtworkUrl();
        artwork = [
          { src: new URL(segArt, location.href).href, sizes: "1280x720", type: "image/jpeg" },
          { src: new URL("./icon-192.png", location.href).href, sizes: "192x192", type: "image/png" },
          { src: new URL("./icon-512.png", location.href).href, sizes: "512x512", type: "image/png" }
        ];
      } catch (e) {}
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title,
        artist: (DATA.radio && DATA.radio.hosts) || "文涛 · 文道 · 子东",
        album: "JLPT N3",
        artwork: artwork
      });
      lastMediaTitle = title;
    }
    if (!mediaSessionHandlersBound) {
      const bind = (act, fn) => { try { navigator.mediaSession.setActionHandler(act, fn); } catch (e) {} };
      bind("play", () => toggleRadioPlay(true));
      bind("pause", () => toggleRadioPlay(false));
      bind("stop", () => toggleRadioPlay(false));
      bind("seekbackward", details => seekRadioBy(-(details && details.seekOffset > 0 ? details.seekOffset : 15)));
      bind("seekforward", details => seekRadioBy(details && details.seekOffset > 0 ? details.seekOffset : 15));
      bind("previoustrack", () => seekRadioBy(-15));
      bind("nexttrack", () => seekRadioBy(15));
      bind("seekto", details => {
        if (!details || typeof details.seekTime !== "number" || !isFinite(details.seekTime)) return;
        ensureRadioReady();
        applyRadioSeek(details.seekTime);
        markRadioPosByUser(details.seekTime);
        updateMediaSessionPosition(true);
      });
      mediaSessionHandlersBound = true;
    }
  } catch (e) {}
}

function toggleRadioPlay(forcePlay) {
  const wantPlay = typeof forcePlay === "boolean" ? forcePlay : radioPlayer.paused;
  if (!wantPlay) {
    // NEVER set radioPlayer.muted = true on pause: muting marks the <audio> element inaudible in
    // Chromium's MediaSessionImpl, immediately tearing down Android MediaSession & breaking Pixel Buds resume!
    radioPlayer.muted = false;
    radioPlayer.pause();
    lastRadioPauseMs = Date.now();
    setupMediaSession();
    setMediaSessionPlaybackState("paused");
    updateMediaSessionPosition(true);
    setRadioBufferingUI(false);
    syncRadioUI(false);
    return;
  }
  if (activeKind !== null || (typeof player !== "undefined" && !player.paused) || (typeof wordPlayer !== "undefined" && !wordPlayer.paused)) {
    stopQuizAudio();
  }
  ensureRadioReady();
  radioPlayer.muted = false;
  radioPlayer.volume = 1;
  flushPendingRadioSeek();
  radioPlayer.playbackRate = radioSpeed;
  setupMediaSession();
  setMediaSessionPlaybackState("playing");
  syncRadioUI(true);
  if (radioBufTimer) clearTimeout(radioBufTimer);
  if (!radioUsingLocalBlob && radioPlayer.readyState < 3) {
    radioBufTimer = setTimeout(() => {
      if (!radioPlayer.paused && (radioPlayer.readyState < 3 || radioPlayer.seeking)) {
        radioBuffering = true;
        syncRadioUI(true);
      }
    }, 240);
  }
  const p = radioPlayer.play();
  if (p && typeof p.then === "function") {
    p.then(() => {
      radioHasPlayedOnce = true;
      flushPendingRadioSeek();
      setMediaSessionPlaybackState("playing");
      updateMediaSessionPosition(true);
    }).catch(err => {
      // Only recover via reload if the underlying network stream errored (e.g., Wi-Fi -> 5G handoff)
      if (radioPlayer.error && err && err.name !== "NotAllowedError" && err.name !== "AbortError") {
        const recoverT = Math.max(0, Math.floor((pendingRadioSeekSec !== null ? pendingRadioSeekSec : (radioPlayer.currentTime || lastSavedSec || 0))));
        radioPlayer.src = cachedRadioBlobUrl || DATA.radio.audio_url;
        if (cachedRadioBlobUrl) radioUsingLocalBlob = true;
        if (recoverT > 0) applyRadioSeek(recoverT);
        try { radioPlayer.load(); } catch (e) {}
        const p2 = radioPlayer.play();
        if (p2 && typeof p2.then === "function") {
          p2.then(() => {
            radioHasPlayedOnce = true;
            flushPendingRadioSeek();
            setMediaSessionPlaybackState("playing");
            updateMediaSessionPosition(true);
          }).catch(() => {
            setRadioBufferingUI(false);
            setMediaSessionPlaybackState("paused");
            syncRadioUI(false);
          });
          return;
        }
      }
      setRadioBufferingUI(false);
      setMediaSessionPlaybackState("paused");
      syncRadioUI(false);
    });
  } else {
    radioHasPlayedOnce = true;
    updateMediaSessionPosition(true);
  }
}

function markRadioPosByUser(t) {
  const s = Math.max(0, Math.floor(t || 0));
  A.radioPos = [s, nowUnixSec()];
  A.radioSig = RADIO_SIG;
  setTimeout(() => {
    writeLocalRadioPos(s);
    saveAdaptiveState();
  }, 20);
  scheduleCloudPush(800);
}

function seekRadioBy(delta) {
  ensureRadioReady();
  const dur = getEffectiveRadioDuration();
  const baseT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
  const nextT = Math.max(0, Math.min(dur - 1, baseT + delta));
  applyRadioSeek(nextT);
  markRadioPosByUser(nextT);
  if (radioHasPlayedOnce) updateMediaSessionPosition(true);
}

function jumpRadioChapter(startSec) {
  ensureRadioReady();
  applyRadioSeek(startSec);
  markRadioPosByUser(startSec);
  if (radioPlayer.paused) toggleRadioPlay(true);
}

function onRadioScrub(val) {
  ensureRadioReady();
  const nextT = parseFloat(val) || 0;
  applyRadioSeek(nextT);
  markRadioPosByUser(nextT);
}

function cycleRadioSpeed() {
  radioSpeed = RADIO_SPEEDS[(RADIO_SPEEDS.indexOf(radioSpeed) + 1) % RADIO_SPEEDS.length];
  try { localStorage.setItem("n3_radio_speed", String(radioSpeed)); } catch (e) {}
  radioPlayer.defaultPlaybackRate = radioSpeed;
  radioPlayer.playbackRate = radioSpeed;
  document.getElementById("radio-spd-btn").textContent = `${radioSpeed}x`;
  if (radioHasPlayedOnce) updateMediaSessionPosition(true);
  stampSpeeds();
}

function renderRadioChapters(activeChapIdx) {
  const chaps = DATA.radio.chapters || [];
  const rvMeta = getReviewClosingChapMeta();
  const closingHTML = rvMeta
    ? `<span class="chap-sep" aria-hidden="true"></span><button type="button" class="chap-link chap-review${rvMeta.cls}" id="radio-review-chap" onclick="openRadioReview()">${escapeHtml(rvMeta.label)}</button>`
    : "";
  document.getElementById("radio-chap-pills").innerHTML = chaps.map(c => `
    <button class="chap-link ${c.idx === activeChapIdx ? 'active' : ''}" onclick="jumpRadioChapter(${c.start})">${escapeHtml(c.title.replace(/^[①②③④⑤⑥]\s*/, ""))}</button>
  `).join("") + closingHTML;
}

function updateRadioLiveDisplay(t) {
  try {
    const seekEl = document.getElementById("radio-seek");
    if (seekEl) seekEl.value = Math.floor(t);
    const curTimeEl = document.getElementById("radio-cur-time");
    if (curTimeEl) curTimeEl.textContent = formatMMSS(t);
    if (seekEl && radioPlayer.duration && isFinite(radioPlayer.duration)) {
      seekEl.max = Math.ceil(radioPlayer.duration);
    }
    const totTimeEl = document.getElementById("radio-tot-time");
    if (totTimeEl && radioPlayer.duration && isFinite(radioPlayer.duration)) {
      totTimeEl.textContent = formatMMSS(radioPlayer.duration);
    }

    if (t > (A.radioMaxSec || 0)) {
      const prevMin = Math.floor((A.radioMaxSec || 0) / 60);
      A.radioMaxSec = Math.floor(t);
      if (Math.floor(A.radioMaxSec / 60) !== prevMin) {
        if (!radioPlayer.paused && pendingRadioSeekSec === null) {
          A.radioPos = [Math.floor(t), nowUnixSec()];
          A.radioSig = RADIO_SIG;
          writeLocalRadioPos(t);
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
          const chapLbl = document.getElementById("radio-chap-lbl");
          if (chapLbl) chapLbl.textContent = chapObj.title.replace(/^[①②③④⑤⑥]\s*/, "");
          renderRadioChapters(chapObj.idx);
          updateRadioArtwork(chapObj);
        }
        const titleEl = document.getElementById("radio-live-title");
        if (titleEl) titleEl.textContent = curSeg.title;
        const jaEl = document.getElementById("radio-live-ja");
        if (jaEl) jaEl.innerHTML = annotateJapanese(curSeg.ja_focus || "");
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
            changed = true;
          }
        }
        if (changed) {
          saveAdaptiveState();
          renderGreenBoard();
        }
      }
    }
    syncRadioMiniBar();
  } catch (e) {}
}

function onMiniBarTap(e) {
  if (e && e.target && e.target.closest && e.target.closest(".rmb-play-btn")) return;
  switchMode("radio", false);
}

function onMiniBarPlayToggle(e) {
  if (e) {
    if (e.stopPropagation) e.stopPropagation();
    if (e.preventDefault) e.preventDefault();
  }
  toggleRadioPlay();
}

function onMiniBarJump(e) {
  if (e) {
    if (e.stopPropagation) e.stopPropagation();
    if (e.preventDefault) e.preventDefault();
  }
  switchMode("radio", false);
}

function syncRadioMiniBar() {
  try {
    const bar = document.getElementById("radio-mini-bar");
    if (!bar) return;
    const isRadioTab = (activeMode === "radio");
    const hasRadioSession = (typeof radioHasPlayedOnce !== "undefined" && radioHasPlayedOnce) || (typeof radioPlayer !== "undefined" && !radioPlayer.paused);
    if (isRadioTab || !hasRadioSession) {
      bar.classList.add("hidden");
      return;
    }
    bar.classList.remove("hidden");
    const isPlaying = typeof radioPlayer !== "undefined" && !radioPlayer.paused;
    const playBtn = document.getElementById("rmb-play-btn");
    if (playBtn) playBtn.textContent = isPlaying ? (radioBuffering ? "缓冲中…" : "暂停") : "播放";
    const wave = document.getElementById("rmb-wave-icon");
    if (wave) wave.classList.toggle("is-playing", isPlaying);
    const dur = getEffectiveRadioDuration();
    const curT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : ((typeof radioPlayer !== "undefined" && radioPlayer.currentTime) || 0);
    const curTitle = getCurrentRadioSegTitle();
    const titleEl = document.getElementById("rmb-title");
    if (titleEl) titleEl.textContent = curTitle;
    const timeEl = document.getElementById("rmb-time");
    if (timeEl) timeEl.textContent = `${formatMMSS(curT)} / ${formatMMSS(dur)}`;
    const fillEl = document.getElementById("rmb-progress-fill");
    if (fillEl) {
      const pct = Math.max(0, Math.min(100, (curT / dur) * 100));
      fillEl.style.width = pct.toFixed(1) + "%";
    }
  } catch (e) {}
}

function syncRadioUI(optimisticPlaying) {
  const playing = typeof optimisticPlaying === "boolean" ? optimisticPlaying : !radioPlayer.paused;
  const btn = document.getElementById("radio-play-btn");
  if (btn) btn.textContent = playing ? (radioBuffering ? "缓冲中…" : "暂停") : "播放";
  const tabBtn = document.getElementById("tab-radio");
  if (tabBtn) tabBtn.classList.toggle("is-playing", playing);
  const bTabBtn = document.getElementById("btab-radio");
  if (bTabBtn) bTabBtn.classList.toggle("is-playing", playing);
  syncRadioMiniBar();
}

function recoverRadioPlayback(isHardError) {
  if (!radioInitialized || radioPlayer.ended) return;
  const isPlayingIntent = !radioPlayer.paused || radioHasPlayedOnce;
  if (!isPlayingIntent) return;
  const t = Math.max(0, Math.floor((pendingRadioSeekSec !== null ? pendingRadioSeekSec : (radioPlayer.currentTime || lastSavedSec || 0))));
  if (cachedRadioBlobUrl && !radioUsingLocalBlob) {
    radioUsingLocalBlob = true;
    radioPlayer.src = cachedRadioBlobUrl;
    if (t > 0) applyRadioSeek(t);
    try { radioPlayer.load(); } catch (e) {}
    radioPlayer.play().then(() => {
      syncRadioUI(true);
    }).catch(() => {});
    return;
  }
  if (isHardError) {
    const src = cachedRadioBlobUrl || DATA.radio.audio_url;
    radioPlayer.src = src;
    if (t > 0) applyRadioSeek(t);
    try { radioPlayer.load(); } catch (e) {}
    radioPlayer.play().then(() => {
      syncRadioUI(true);
    }).catch(() => {});
  }
}
radioPlayer.addEventListener("error", () => recoverRadioPlayback(true));
radioPlayer.addEventListener("stalled", () => {
  if (!radioPlayer.paused && !radioUsingLocalBlob) {
    recoverRadioPlayback(false);
  }
});

radioPlayer.addEventListener("play", () => {
  radioHasPlayedOnce = true;
  radioPlayer.muted = false;
  radioPlayer.volume = 1;
  flushPendingRadioSeek();
  setupMediaSession();
  setMediaSessionPlaybackState("playing");
  updateMediaSessionPosition(true);
  syncRadioUI(true);
});
radioPlayer.addEventListener("playing", () => {
  radioHasPlayedOnce = true;
  radioPlayer.muted = false;
  radioPlayer.volume = 1;
  setRadioBufferingUI(false);
  flushPendingRadioSeek();
  setupMediaSession();
  setMediaSessionPlaybackState("playing");
  updateMediaSessionPosition(true);
  syncRadioUI(true);
});
radioPlayer.addEventListener("waiting", () => {
  if (!radioPlayer.paused && !radioUsingLocalBlob) {
    if (radioBufTimer) clearTimeout(radioBufTimer);
    radioBufTimer = setTimeout(() => {
      if (!radioPlayer.paused && (radioPlayer.readyState < 3 || radioPlayer.seeking)) {
        radioBuffering = true;
        syncRadioUI(true);
      }
    }, 240);
  }
});
radioPlayer.addEventListener("canplay", () => {
  flushPendingRadioSeek();
});
radioPlayer.addEventListener("seeked", () => {
  if (pendingRadioSeekSec !== null && Math.abs((radioPlayer.currentTime || 0) - pendingRadioSeekSec) <= 2.0) {
    pendingRadioSeekSec = null;
    radioSeekIssuedTarget = null;
  }
  updateRadioLiveDisplay(radioPlayer.currentTime || 0);
  if (radioHasPlayedOnce) updateMediaSessionPosition(true);
});
radioPlayer.addEventListener("pause", () => {
  lastRadioPauseMs = Date.now();
  radioPlayer.muted = false;
  setRadioBufferingUI(false);
  if (radioInitialized && radioHasPlayedOnce) {
    setupMediaSession();
    setMediaSessionPlaybackState("paused");
    updateMediaSessionPosition(true);
  }
  syncRadioUI(false);
  if (pendingRadioSeekSec !== null) return;
  const t = Math.floor(radioPlayer.currentTime || 0);
  if (t > 2) {
    lastSavedSec = t;
    A.radioPos = [t, nowUnixSec()];
    A.radioSig = RADIO_SIG;
    if (t > (A.radioMaxSec || 0)) A.radioMaxSec = t;
    // Defer synchronous localStorage serialization off the tap frame for 0ms UI response
    if (radioPauseSaveTimer) clearTimeout(radioPauseSaveTimer);
    radioPauseSaveTimer = setTimeout(() => {
      radioPauseSaveTimer = null;
      writeLocalRadioPos(t);
      saveAdaptiveState();
      upgradeRadioToLocalBlobIfPaused();
    }, 30);
    scheduleCloudPush(250);
  } else {
    setTimeout(() => upgradeRadioToLocalBlobIfPaused(), 50);
  }
});
radioPlayer.addEventListener("ended", () => {
  pendingRadioSeekSec = null;
  radioSeekIssuedTarget = null;
  setRadioBufferingUI(false);
  setMediaSessionPlaybackState("paused");
  updateMediaSessionPosition(true);
  const dur = Math.ceil(radioPlayer.duration || DATA.radio.duration_sec || 2100);
  A.radioMaxSec = dur;
  A.radioPos = [0, nowUnixSec()];
  A.radioSig = RADIO_SIG;
  writeLocalRadioPos(0);
  saveAdaptiveState();
  renderGreenBoard();
  syncRadioUI(false);
  updateRadioReviewEntryBadge();
  scheduleCloudPush(100);
});
radioPlayer.addEventListener("loadedmetadata", () => {
  if (pendingRadioSeekSec !== null) {
    flushPendingRadioSeek();
    updateRadioLiveDisplay(pendingRadioSeekSec !== null ? pendingRadioSeekSec : (radioPlayer.currentTime || 0));
  } else {
    updateRadioLiveDisplay(radioPlayer.currentTime || 0);
  }
  if (radioHasPlayedOnce) updateMediaSessionPosition(true);
  renderGreenBoard();
  updateRadioReviewEntryBadge();
});
radioPlayer.addEventListener("timeupdate", () => {
  if (pendingRadioSeekSec !== null) {
    if (!flushPendingRadioSeek()) return;
  }
  const t = radioPlayer.currentTime || 0;
  updateRadioLiveDisplay(t);
  if (!radioPlayer.paused) {
    updateMediaSessionPosition(false);
  }
  if (!radioPlayer.paused && Math.abs(t - lastSavedSec) >= 2) {
    lastSavedSec = t;
    A.radioPos = [Math.floor(t), nowUnixSec()];
    A.radioSig = RADIO_SIG;
    writeLocalRadioPos(t);
    saveAdaptiveState();
    updateRadioReviewEntryBadge();
    if (Date.now() - lastRadioCloudPushMs > 60000) {
      lastRadioCloudPushMs = Date.now();
      scheduleCloudPush(400);
    }
  }
});

// ================= REAL VOICE ACTIVE OUTPUT & PRONUNCIATION MIRROR (Web Speech ja-JP) =================
// Zero-key, zero-server browser-native Japanese speech recognition for Android Chrome & Desktop Chrome.
// Grounded in Swain (1985, 2005) Output Hypothesis, MacLeod et al. (2010) Production Effect, & DeKeyser (2007).
const JA_ASR = (() => {
  let rec = null;
  let active = false;
  let activeTag = "";
  let safetyTimer = null;

  const DAKUTEN_MAP = {
    "が":"か","ぎ":"き","ぐ":"く","げ":"け","ご":"こ",
    "ざ":"さ","じ":"し","ず":"す","ぜ":"せ","ぞ":"そ",
    "だ":"た","ぢ":"ち","づ":"つ","で":"て","ど":"と",
    "ば":"は","び":"ひ","ぶ":"ふ","べ":"へ","ぼ":"ほ",
    "ぱ":"は","ぴ":"ひ","ぷ":"ふ","ぺ":"へ","ぽ":"ほ",
    "ゔ":"う"
  };

  // Common ASR homophone/near-miss readings so Kanji transcripts still get accurate phonetic diagnostics
  const EXTRA_KANA = {
    "予算":"よさん","余算":"よさん","洋三":"ようさん","与三":"よさん","養蚕":"ようさん",
    "書類":"しょるい","種類":"しゅるい","出張":"しゅっちょう","主張":"しゅちょう","首相":"しゅしょう",
    "鍵":"かぎ","柿":"かき","夏季":"かき","下記":"かき","牡蠣":"かき",
    "合格":"ごうかく","広告":"こうこく","降格":"こうかく","広角":"こうかく",
    "設計":"せっけい","世間":"せけん","赤径":"せっけい","整形":"せいけい",
    "読解":"どっかい","妖怪":"ようかい","了解":"りょうかい",
    "現金":"げんきん","景気":"けいき","平均":"へいきん","原因":"げんいん",
    "象徴":"しょうちょう","所長":"しょちょう","署長":"しょちょう",
    "伝統":"でんとう","電灯":"でんとう","転倒":"てんとう",
    "建築":"けんちく","経済":"けいざい","補助金":"ほじょきん",
    "図書館":"としょかん","博物館":"はくぶつかん","辞書":"じしょ","事情":"じじょう"
  };

  const SPOKEN_TRAPS = [
    {
      re: /(?:[\u4e00-\u9faf][ぁ-ん]{0,3}(?:る|た|く|ぐ|す|つ|ぶ|む|ない)|(?:する|した|くる|きた|いる|いた|ある|あった|すぎた|しすぎた|いく|ねる|でる|たべる|のむ|みる|かう|かえる))の(?:時|とき)/,
      tip: "动词接「時」不用加「の」，直接说「〜る時／〜た時」。"
    },
    {
      re: /(?:つもり|ところ|はず|わけ|予定|はずなん|ようとした)たった|たったんです|たったのに|ところたった/,
      tip: "注意浊音「だった」，刚才听成清音「たった」了。"
    },
    {
      re: /はずないんです|はつない|はずないけど|はずないです/,
      tip: "想表达「按理应该」用「はずなんですが」，多出「ない」会翻成否定。"
    },
    {
      re: /(?:上手|静か|元気|大変|好き|嫌い|便利|簡単|親切|暇|幸せそう|おいしそう|美味しそう|楽しそう|高そう|難しそう)わけ/,
      tip: "ナ形容词和「そう」接「わけ」时，中间必须补「な」（如 上手なわけ）。"
    },
    {
      re: /(?:ある|いる|行く|来る|降る|晴れ|雨|休み|いい|良い|高い|安い|忙しい|大変)だと?らしい|とらしい/,
      tip: "传闻「らしい」直接接简体，前面不加「と」或「だ」。"
    },
    {
      re: /(?:休み|休んで|参加して|帰って|早退して)いただけませんか|(?:休み|休んで|参加して|早退して)もらってもいいですか/,
      tip: "自己请假或早退求对方批准，要用使役「帰らせて／休ませていただけませんか」。"
    },
    {
      re: /(?:話|渡|出|直|消|探|返|押|貸|起こ|壊)さされ/,
      tip: "「す」结尾动词使役受身不能缩约，要完整说「話させられる」。"
    },
    {
      re: /(?:する|行く|帰る|休む|食べる|飲む|買う|見る|辞める|やめる|働く|運動する|勉強する|退職する|転職する|引っ越す)にしました|(?:する|行く|帰る|休む|食べる|飲む|買う|見る|辞める|やめる|働く|退職する|転勤する)になりました/,
      tip: "动词原形接「にする／になる」表决定时，中间别漏掉形式名词「こと」。"
    },
    {
      re: /(?:酸っぱい|辛い|美味しい|おいしい|高い|安い|忙しい|楽しい|寒い|暑い|難しい|面白い|すごい|痛い|眠い|大きい|小さい)でした|(?:大好き|好き|静か|元気|便利|簡単|親切|大変)かった/,
      tip: "イ形容词过去式用「〜かったです」，ナ形容词过去式用「〜でした」。"
    },
    {
      re: /たくさんの?方が|たくさん(?:美味しい|おいしい|いい|良い|速い|早い|高い|安い|面白い|上手)/,
      tip: "比较差距大时不用「たくさん」，地道说法是用「ずっと」。"
    },
    {
      re: /まだ.{0,8}(?:食べません|来ません|終わりません|決めません|見ません|買いません|読みません|飲みません|着きません)/,
      tip: "「还没做」表示持续未完成状态，要用「まだ〜ていません」。"
    },
    {
      re: /知ります(?:か|よ|ね)?(?!ん)/,
      tip: "「知道」表示认知状态，用持续体「知っています／知っていますか」。"
    },
    {
      re: /(?:行こよう|おぼてよう)|(?:しよう|行こう|出よう|食べよう|飲もう|買おう|帰ろう|話そう|連絡しよう)した(?:時|とき)/,
      tip: "意志形接「とした時」别漏掉中间的引述助词「と」。"
    },
    {
      re: /(?:仕事|宿題|作業|準備|会議|発表|プロジェクト)を終わる/,
      tip: "带宾语「〜を」表示人为完成，要用他动词「終わらせる」或「終える」。"
    },
    {
      re: /遠慮がちに.{0,14}(?:いいですか|でしょうか|聞いても|伺っても)/,
      tip: "「遠慮がちに」只描写别人神态，自己礼貌发问直接用「よろしければ」。"
    }
  ];

  function supported() {
    return typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function toHira(raw) {
    const cleaned = String(raw || "").replace(/[、。！？.,!?・「」『』（）()【】\s〜~～…・]/g, "");
    let out = "";
    for (let i = 0; i < cleaned.length; i++) {
      const code = cleaned.charCodeAt(i);
      if (code >= 0x30a1 && code <= 0x30f6) out += String.fromCharCode(code - 0x60);
      else out += cleaned[i];
    }
    return out;
  }

  function stripDakuten(hira) {
    return String(hira || "").split("").map(ch => DAKUTEN_MAP[ch] || ch).join("");
  }

  function stripSokuon(hira) {
    return String(hira || "").replace(/っ/g, "");
  }

  function collapseLongVowels(hira) {
    let s = String(hira || "").replace(/ー/g, "");
    s = s.replace(/([あかさたなはまやらわがざだばぱぁゃ])あ/g, "$1");
    s = s.replace(/([いきしちにひみりぎじぢびぴぃ])い/g, "$1");
    s = s.replace(/([うくすつぬふむゆるぐずづぶぷぅゅ])う/g, "$1");
    s = s.replace(/([えけせてねへめれげぜでべぺぇ])[えい]/g, "$1");
    s = s.replace(/([おこそとのほもよろをごぞどぼぽぉょ])[おう]/g, "$1");
    return s;
  }

  function resolveKana(raw) {
    const clean = String(raw || "").replace(/[、。！？.,!?・「」『』（）()【】\s〜~～…・]/g, "");
    if (!clean) return "";
    if (!/[\u4e00-\u9faf\u3400-\u4dbf]/.test(clean)) return toHira(clean);
    if (EXTRA_KANA[clean]) return toHira(EXTRA_KANA[clean]);
    try {
      if (typeof DATA !== "undefined" && DATA) {
        if (DATA.words && DATA.words[clean] && DATA.words[clean].kana) {
          return toHira(DATA.words[clean].kana);
        }
        if (DATA.vocab_cards && DATA.vocab_cards[clean] && DATA.vocab_cards[clean].kana) {
          return toHira(DATA.vocab_cards[clean].kana);
        }
      }
    } catch (e) {}
    return toHira(clean);
  }

  function levenshtein(a, b) {
    const m = a.length, n = b.length;
    if (!m) return n;
    if (!n) return m;
    const dp = new Array(n + 1);
    for (let j = 0; j <= n; j++) dp[j] = j;
    for (let i = 1; i <= m; i++) {
      let prev = dp[0];
      dp[0] = i;
      for (let j = 1; j <= n; j++) {
        const tmp = dp[j];
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[j] = Math.min(dp[j] + 1, dp[j - 1] + 1, prev + cost);
        prev = tmp;
      }
    }
    return dp[n];
  }

  function detectSpokenTraps(rawText) {
    const s = String(rawText || "").trim();
    if (!s) return [];
    const tips = [];
    for (let i = 0; i < SPOKEN_TRAPS.length; i++) {
      if (SPOKEN_TRAPS[i].re.test(s)) {
        tips.push(SPOKEN_TRAPS[i].tip);
      }
    }
    return tips;
  }

  function analyzePronunciation(rawAlts, targetWord, targetKana, targetChunk) {
    const alts = (Array.isArray(rawAlts) ? rawAlts : [rawAlts])
      .map(x => String(x || "").trim())
      .filter(Boolean);
    if (!alts.length) {
      return { ok: false, kind: "empty", heard: "", verdict: "没听清，靠近一点再试一次" };
    }
    const tgtWordH = toHira(targetWord || "");
    const tgtKanaH = toHira(targetKana || resolveKana(targetWord || ""));
    const tgtChunkH = toHira(targetChunk || "");
    const bestRaw = alts[0];

    for (let i = 0; i < alts.length; i++) {
      const a = alts[i];
      const aH = toHira(a);
      const aK = resolveKana(a);
      if (
        (tgtWordH && (aH === tgtWordH || aH.includes(tgtWordH))) ||
        (tgtKanaH && (aH === tgtKanaH || aK === tgtKanaH || (tgtKanaH.length >= 2 && (aH.includes(tgtKanaH) || aK.includes(tgtKanaH))))) ||
        (tgtChunkH && tgtChunkH.length >= 3 && (aH === tgtChunkH || aH.includes(tgtChunkH)))
      ) {
        return {
          ok: true,
          kind: "exact",
          heard: a,
          verdict: "读准了"
        };
      }
    }

    const heardKana = resolveKana(bestRaw);
    const dispHeard = (heardKana && heardKana !== toHira(bestRaw) && /[\u4e00-\u9faf]/.test(bestRaw))
      ? `${bestRaw}（${heardKana}）`
      : bestRaw;

    if (tgtKanaH && heardKana && !/[\u4e00-\u9faf]/.test(heardKana)) {
      if (stripDakuten(heardKana) === stripDakuten(tgtKanaH)) {
        return { ok: false, kind: "voicing", heard: dispHeard, verdict: `清浊音差了一拍，目标「${tgtKanaH}」` };
      }
      if (stripSokuon(heardKana) === stripSokuon(tgtKanaH)) {
        const msg = tgtKanaH.includes("っ") && !heardKana.includes("っ")
          ? `漏了促音「っ」停顿，目标「${tgtKanaH}」`
          : `多出了促音「っ」，目标「${tgtKanaH}」`;
        return { ok: false, kind: "sokuon", heard: dispHeard, verdict: msg };
      }
      if (collapseLongVowels(heardKana) === collapseLongVowels(tgtKanaH)) {
        return { ok: false, kind: "length", heard: dispHeard, verdict: `长短音差了一拍，目标「${tgtKanaH}」` };
      }
      const deepA = stripDakuten(collapseLongVowels(stripSokuon(heardKana)));
      const deepT = stripDakuten(collapseLongVowels(stripSokuon(tgtKanaH)));
      if (deepA === deepT || levenshtein(heardKana, tgtKanaH) <= 2) {
        return { ok: false, kind: "near", heard: dispHeard, verdict: `很接近，再核对一拍「${tgtKanaH}」` };
      }
    }

    return {
      ok: false,
      kind: "miss",
      heard: dispHeard,
      verdict: tgtKanaH ? `和「${tgtKanaH}」有点偏，听示范跟读一遍` : "读音有点偏，再试一次"
    };
  }

  function analyzeSpokenOutput(rawAlts, prompt) {
    const alts = (Array.isArray(rawAlts) ? rawAlts : [rawAlts])
      .map(x => String(x || "").trim())
      .filter(Boolean);
    if (!alts.length) {
      return {
        ok: false,
        usedTarget: false,
        heard: "",
        traps: [],
        verdict: "没听到清晰语音，靠近一点再说一句就行。"
      };
    }
    const stems = Array.isArray(prompt && prompt.target_stems) ? prompt.target_stems : [];
    const stemHiras = stems.map(s => toHira(s)).filter(Boolean);

    let chosen = alts[0];
    let usedTarget = false;
    for (let i = 0; i < alts.length; i++) {
      const a = alts[i];
      const aH = toHira(a);
      const hit = stems.some(s => s && a.includes(s)) || stemHiras.some(sh => sh && aH.includes(sh));
      if (hit) {
        chosen = a;
        usedTarget = true;
        break;
      }
    }

    const traps = detectSpokenTraps(chosen);
    // Also detect voicing slip on target stem itself (e.g. ところたった instead of ところだった)
    if (!usedTarget && stems.length) {
      const chosenNoDak = stripDakuten(toHira(chosen));
      if (stemHiras.some(sh => sh.length >= 4 && chosenNoDak.includes(stripDakuten(sh)))) {
        if (!traps.some(t => t.includes("清音") || t.includes("浊音"))) {
          traps.push(`目标句型「${prompt.title || ""}」的清浊音差了一拍，注意听清浊再说一遍。`);
        }
      }
    }

    const jaLen = chosen.replace(/[^\u3040-\u30ff\u4e00-\u9faf]/g, "").length;
    if (jaLen < 3) {
      return {
        ok: false,
        usedTarget: false,
        heard: chosen,
        traps: traps,
        verdict: "这句话太短了，试着用完整短句说一遍。"
      };
    }

    if (usedTarget && traps.length === 0) {
      return {
        ok: true,
        usedTarget: true,
        heard: chosen,
        traps: [],
        verdict: `句型「${prompt.title || ""}」用对了，表达很自然。`
      };
    }
    if (usedTarget && traps.length > 0) {
      return {
        ok: false,
        usedTarget: true,
        heard: chosen,
        traps: traps,
        verdict: `目标句型用上了，顺手修一个小习惯。`
      };
    }
    return {
      ok: false,
      usedTarget: false,
      heard: chosen,
      traps: traps,
      verdict: `听懂意思了，试着把「${prompt.title || ""}」直接套进去再说一遍。`
    };
  }

  function stop() {
    if (safetyTimer) {
      clearTimeout(safetyTimer);
      safetyTimer = null;
    }
    active = false;
    activeTag = "";
    if (rec) {
      try { rec.onresult = null; rec.onerror = null; rec.onend = null; rec.abort(); } catch (e) {}
      rec = null;
    }
  }

  function start(tag, handlers) {
    stop();
    if (!supported()) {
      if (handlers && handlers.onError) handlers.onError("当前浏览器不支持实时收音，听示范直接跟读即可。");
      return false;
    }
    // Mute every active audio player before opening the mic so playback never leaks into ASR!
    try { if (typeof stopQuizAudio === "function") stopQuizAudio(); } catch (e) {}
    try { if (typeof stopVocabAudioAndTimers === "function") stopVocabAudioAndTimers(); } catch (e) {}
    try { if (typeof stopRadioReviewAudio === "function") stopRadioReviewAudio(); } catch (e) {}
    try {
      if (typeof radioInitialized !== "undefined" && radioInitialized && radioPlayer && !radioPlayer.paused) {
        radioPlayer.pause();
        if (typeof syncRadioUI === "function") syncRadioUI(false);
      }
    } catch (e) {}
    try { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); } catch (e) {}

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    try {
      rec = new SR();
      rec.lang = "ja-JP";
      rec.interimResults = true;
      rec.maxAlternatives = 5;
      rec.continuous = false;
    } catch (e) {
      if (handlers && handlers.onError) handlers.onError("语音识别初始化失败，请稍后重试。");
      return false;
    }

    active = true;
    activeTag = String(tag || "");
    let gotFinal = false;
    let lastInterim = "";

    rec.onresult = (ev) => {
      if (!active || !ev || !ev.results) return;
      const alts = [];
      let isFinal = false;
      for (let i = ev.resultIndex || 0; i < ev.results.length; i++) {
        const res = ev.results[i];
        if (res && res.isFinal) isFinal = true;
        if (res && res.length) {
          for (let j = 0; j < res.length; j++) {
            const tr = String((res[j] && res[j].transcript) || "").trim();
            if (tr && !alts.includes(tr)) alts.push(tr);
          }
        }
      }
      if (!alts.length) return;
      lastInterim = alts[0];
      if (isFinal) {
        gotFinal = true;
        const doneCb = handlers && handlers.onFinal;
        stop();
        if (doneCb) doneCb(alts);
      } else if (handlers && handlers.onInterim) {
        handlers.onInterim(alts[0]);
      }
    };

    rec.onerror = (ev) => {
      if (!active) return;
      const code = String((ev && ev.error) || "");
      const errMap = {
        "not-allowed": "请允许浏览器使用麦克风权限，点地址栏左侧图标打开即可。",
        "service-not-allowed": "请允许浏览器使用麦克风权限，点地址栏左侧图标打开即可。",
        "no-speech": "没听到声音，靠近一点再说一遍。",
        "audio-capture": "未检测到麦克风设备。",
        "network": "语音识别网络暂时连不上，稍后再试。",
        "aborted": ""
      };
      const msg = (code in errMap) ? errMap[code] : "没听清，再试一次就行。";
      const errCb = handlers && handlers.onError;
      stop();
      if (msg && errCb) errCb(msg);
    };

    rec.onend = () => {
      const wasActive = active;
      const endCb = handlers && handlers.onEnd;
      const finalCb = handlers && handlers.onFinal;
      const fallbackTxt = lastInterim;
      stop();
      if (wasActive && !gotFinal && fallbackTxt && finalCb) {
        finalCb([fallbackTxt]);
      } else if (wasActive && endCb) {
        endCb();
      }
    };

    safetyTimer = setTimeout(() => {
      if (active && rec) {
        try { rec.stop(); } catch (e) { stop(); }
      }
    }, 10500);

    try {
      rec.start();
      return true;
    } catch (e) {
      stop();
      if (handlers && handlers.onError) handlers.onError("麦克风启动失败，再点一次试试。");
      return false;
    }
  }

  return {
    supported,
    isActive: (tag) => active && (!tag || activeTag === tag),
    start,
    stop,
    toHira,
    stripDakuten,
    stripSokuon,
    collapseLongVowels,
    resolveKana,
    detectSpokenTraps,
    analyzePronunciation,
    analyzeSpokenOutput
  };
})();
window.JA_ASR = JA_ASR;

function pushSpokenRecord(idTag, pointKey, label, isOk) {
  const tsSec = Math.max(TRUE_GREEN_EPOCH, nowUnixSec());
  const rec = {
    id: `SPK:${idTag}`,
    point: String(pointKey || idTag),
    choice: String(label || "开口:练过"),
    correct: isOk ? "true" : "false",
    ask_again: "false",
    ts: new Date(tsSec * 1000).toISOString()
  };
  const ob = loadOutbox();
  ob.push([rec.id, rec.point, rec.choice, isOk ? 1 : 0, rec.ts]);
  saveOutbox(ob);
  saveAdaptiveState();
  scheduleCloudPush(220);
}

// ================= POST-LISTENING 5-MIN CONTEXTUAL REVIEW ("听后 5 分") =================
// Backed by Encoding Specificity (Tulving 1973), Region of Proximal Learning (Metcalfe 2002),
// Testing Effect (Roediger & Karpicke 2006), & Within-Session Spaced Retrieval (Nakata 2017).
let radioReviewOpen = false;
let rvMode = "triage"; // "triage" | "relearn" | "tail" | "done" | "speak"
let rvRevealed = false;
let rvRevealedAt = 0;
let rvActiveItemId = "";
let rvReturnMode = "triage";
let rvAnimating = false;
let rvClipPlayer = null;
let rvClipEndSec = 0;
let rvClipPlayingKey = "";
let rvSpeakIdx = 0;
let rvSpeakState = { listening: false, interim: "", result: null, revealedModel: false, errorMsg: "" };

function getRadioReviewItems() {
  const arr = (DATA.radio && Array.isArray(DATA.radio.review_items)) ? DATA.radio.review_items : [];
  return arr;
}

function getRadioSpeakingPrompts() {
  const arr = (DATA.radio && Array.isArray(DATA.radio.speaking_prompts)) ? DATA.radio.speaking_prompts : [];
  return arr;
}

function getActiveSpeakingPrompt() {
  const arr = getRadioSpeakingPrompts();
  return arr[rvSpeakIdx] || null;
}

function getReviewItemById(id) {
  return getRadioReviewItems().find(x => x.id === id) || null;
}

function ensureRadioReviewState(forceReset) {
  const items = getRadioReviewItems();
  const validIds = new Set(items.map(x => x.id));
  const prevSpoken = (!forceReset && A.radioReview && A.radioReview.sig === RADIO_SIG && A.radioReview.date === DATA.plan_date && Array.isArray(A.radioReview.spokenIds))
    ? A.radioReview.spokenIds.slice()
    : [];
  if (!forceReset && A.radioReview && A.radioReview.sig === RADIO_SIG && A.radioReview.date === DATA.plan_date) {
    A.radioReview.passedIds = (A.radioReview.passedIds || []).filter(id => validIds.has(id));
    A.radioReview.relearnIds = (A.radioReview.relearnIds || []).filter(id => validIds.has(id));
    A.radioReview.tailQueue = (A.radioReview.tailQueue || []).filter(id => validIds.has(id));
    A.radioReview.tailDoneIds = (A.radioReview.tailDoneIds || []).filter(id => validIds.has(id));
    if (!Array.isArray(A.radioReview.spokenIds)) A.radioReview.spokenIds = [];
    if (!A.radioReview.updatedAt) A.radioReview.updatedAt = nowUnixSec();
    return A.radioReview;
  }
  A.radioReview = {
    sig: RADIO_SIG,
    date: DATA.plan_date,
    triageIdx: 0,
    passedIds: [],
    relearnIds: [],
    tailQueue: [],
    tailDoneIds: [],
    spokenIds: prevSpoken,
    done: items.length === 0,
    updatedAt: nowUnixSec()
  };
  saveAdaptiveState();
  return A.radioReview;
}

function getReviewClosingChapMeta() {
  const items = getRadioReviewItems();
  if (!items.length) return null;
  const st = ensureRadioReviewState(false);
  const rm = computeDaily120Metrics();
  if (st.done) {
    return { label: "复盘 ✓", cls: " is-done", needsClose: false };
  }
  if (st.triageIdx > 0 || (st.tailQueue && st.tailQueue.length > 0)) {
    const doneCnt = Math.min(items.length, st.triageIdx);
    return { label: `复盘 ${doneCnt}/${items.length}`, cls: " is-ready", needsClose: rm.radioAudioDone };
  }
  if (rm.radioAudioDone) {
    return { label: "听后复盘", cls: " is-ready", needsClose: true };
  }
  return { label: "听后复盘", cls: "", needsClose: false };
}

function updateRadioReviewEntryBadge() {
  const meta = getReviewClosingChapMeta();
  const chapBtn = document.getElementById("radio-review-chap");
  if (chapBtn && meta) {
    chapBtn.textContent = meta.label;
    chapBtn.className = "chap-link chap-review" + meta.cls;
  }
  const cta = document.getElementById("radio-review-cta");
  if (cta) {
    const showCta = !!(meta && meta.needsClose);
    cta.style.display = showCta ? "flex" : "none";
    if (showCta) {
      const strip = document.getElementById("radio-chap-pills");
      if (strip && typeof strip.scrollWidth === "number") {
        try { strip.scrollLeft = strip.scrollWidth; } catch (e) {}
      }
    }
  }
}

function stopRadioReviewAudio() {
  rvClipPlayingKey = "";
  rvClipEndSec = 0;
  try {
    if (rvClipPlayer) {
      rvClipPlayer.pause();
      rvClipPlayer.ontimeupdate = null;
      rvClipPlayer.onended = null;
    }
  } catch (e) {}
  try {
    wordPlayer.onended = null;
    wordPlayer.onerror = null;
    wordPlayer.pause();
  } catch (e) {}
  try {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  } catch (e) {}
  syncRvAudioButtons();
}

function syncRvAudioButtons() {
  document.querySelectorAll("[data-rv-aud]").forEach(el => {
    const k = el.getAttribute("data-rv-aud");
    const isPlaying = !!rvClipPlayingKey && rvClipPlayingKey === k;
    el.classList.toggle("playing", isPlaying);
    const ico = el.querySelector(".rv-aud-ico");
    if (ico) ico.textContent = isPlaying ? "⏸" : "▶";
  });
}

function playReviewPodcastClip(item, rateVal, toggleKey, forcePlay) {
  if (!item) return;
  const key = toggleKey || `clip_${rateVal}`;
  if (!forcePlay && rvClipPlayingKey === key && rvClipPlayer && !rvClipPlayer.paused) {
    stopRadioReviewAudio();
    return;
  }
  stopRadioReviewAudio();
  if (radioInitialized && !radioPlayer.paused) {
    radioPlayer.pause();
    syncRadioUI(false);
  }
  const srcUrl = cachedRadioBlobUrl || (DATA.radio && DATA.radio.audio_url) || "";
  if (!srcUrl) return;
  if (!rvClipPlayer) {
    rvClipPlayer = new Audio();
    rvClipPlayer.preload = "metadata";
    rvClipPlayer.playsInline = true;
    try {
      rvClipPlayer.style.display = "none";
      if (document.body) document.body.appendChild(rvClipPlayer);
    } catch (e) {}
  }
  const startS = Math.max(0, Number(item.clip_start || 0));
  const endS = Math.max(startS + 4, Number(item.clip_end || (startS + 14)));
  rvClipEndSec = endS;
  rvClipPlayingKey = key;
  syncRvAudioButtons();

  const beginPlay = () => {
    try {
      rvClipPlayer.currentTime = startS;
      rvClipPlayer.playbackRate = rateVal || 1.0;
      rvClipPlayer.ontimeupdate = () => {
        if (!rvClipPlayer.seeking && (rvClipPlayer.currentTime || 0) >= startS && rvClipEndSec > 0 && (rvClipPlayer.currentTime || 0) >= rvClipEndSec) {
          stopRadioReviewAudio();
        }
      };
      rvClipPlayer.onended = () => stopRadioReviewAudio();
      const pr = rvClipPlayer.play();
      if (pr && typeof pr.catch === "function") pr.catch(() => stopRadioReviewAudio());
    } catch (e) {
      stopRadioReviewAudio();
    }
  };

  if (rvClipPlayer.src !== srcUrl && !String(rvClipPlayer.src || "").endsWith(srcUrl.replace(/^\.\//, ""))) {
    rvClipPlayer.src = srcUrl;
    rvClipPlayer.onloadedmetadata = () => {
      rvClipPlayer.onloadedmetadata = null;
      beginPlay();
    };
    try { rvClipPlayer.load(); } catch (e) {}
  } else if (rvClipPlayer.readyState >= 1) {
    beginPlay();
  } else {
    rvClipPlayer.onloadedmetadata = () => {
      rvClipPlayer.onloadedmetadata = null;
      beginPlay();
    };
    try { rvClipPlayer.load(); } catch (e) {}
  }
}

function playReviewDemoSentence(item) {
  if (!item) return;
  if (rvClipPlayingKey === "demo") {
    stopRadioReviewAudio();
    return;
  }
  stopRadioReviewAudio();
  rvClipPlayingKey = "demo";
  syncRvAudioButtons();
  const demoUrl = item.demo_audio || "";
  const speakText = item.ja_example || item.kana || item.title || "";
  const doneCb = () => {
    if (rvClipPlayingKey === "demo") {
      rvClipPlayingKey = "";
      syncRvAudioButtons();
    }
  };
  if (demoUrl) {
    warmAudio(demoUrl).then(resolved => {
      if (rvClipPlayingKey !== "demo") return;
      try {
        wordPlayer.onended = doneCb;
        wordPlayer.onerror = () => speakUtteranceLang(speakText, "ja-JP", 0.96, doneCb);
        wordPlayer.src = resolved || demoUrl;
        wordPlayer.currentTime = 0;
        wordPlayer.playbackRate = 1.0;
        const pr = wordPlayer.play();
        if (pr && typeof pr.catch === "function") {
          pr.catch(() => speakUtteranceLang(speakText, "ja-JP", 0.96, doneCb));
        }
      } catch (e) {
        speakUtteranceLang(speakText, "ja-JP", 0.96, doneCb);
      }
    });
  } else {
    speakUtteranceLang(speakText, "ja-JP", 0.96, doneCb);
  }
}

function playReviewHookAudio(item) {
  if (!item) return;
  if (rvClipPlayingKey === "hook") {
    stopRadioReviewAudio();
    return;
  }
  stopRadioReviewAudio();
  rvClipPlayingKey = "hook";
  syncRvAudioButtons();
  const hookUrl = item.hook_audio || "";
  const speakText = item.mnemonic || "";
  const doneCb = () => {
    if (rvClipPlayingKey === "hook") {
      rvClipPlayingKey = "";
      syncRvAudioButtons();
    }
  };
  if (hookUrl) {
    warmAudio(hookUrl).then(resolved => {
      if (rvClipPlayingKey !== "hook") return;
      try {
        wordPlayer.onended = doneCb;
        wordPlayer.onerror = () => speakUtteranceLang(speakText, "zh-CN", 1.04, doneCb);
        wordPlayer.src = resolved || hookUrl;
        wordPlayer.currentTime = 0;
        wordPlayer.playbackRate = 1.0;
        const pr = wordPlayer.play();
        if (pr && typeof pr.catch === "function") {
          pr.catch(() => speakUtteranceLang(speakText, "zh-CN", 1.04, doneCb));
        }
      } catch (e) {
        speakUtteranceLang(speakText, "zh-CN", 1.04, doneCb);
      }
    });
  } else if (speakText) {
    speakUtteranceLang(speakText, "zh-CN", 1.04, doneCb);
  } else {
    doneCb();
  }
}

function pushRadioReviewRecord(item, actionLabel, isOk) {
  const tsSec = Math.max(TRUE_GREEN_EPOCH, nowUnixSec());
  const ptKey = item.key || item.title;
  const rec = {
    id: `RV:${item.id}`,
    point: ptKey,
    choice: actionLabel,
    correct: isOk ? "true" : "false",
    ask_again: isOk ? "false" : "true",
    ts: new Date(tsSec * 1000).toISOString()
  };
  if (!Array.isArray(A.recentRecords)) A.recentRecords = [];
  A.recentRecords.push(rec);
  if (A.recentRecords.length > 25) A.recentRecords = A.recentRecords.slice(-25);
  const ob = loadOutbox();
  ob.push([rec.id, rec.point, rec.choice, isOk ? 1 : 0, rec.ts]);
  saveOutbox(ob);
  saveAdaptiveState();
  scheduleCloudPush(120);
}

function advanceRadioReviewPointer() {
  const items = getRadioReviewItems();
  const st = ensureRadioReviewState(false);
  if (st.triageIdx < items.length) {
    rvMode = "triage";
    rvActiveItemId = items[st.triageIdx].id;
    rvRevealed = false;
    rvRevealedAt = 0;
  } else if (st.tailQueue && st.tailQueue.length > 0) {
    rvMode = "tail";
    rvActiveItemId = st.tailQueue[0];
    rvRevealed = false;
    rvRevealedAt = 0;
  } else {
    st.done = true;
    st.updatedAt = nowUnixSec();
    rvMode = "done";
    rvActiveItemId = "";
    rvRevealedAt = 0;
    saveAdaptiveState();
    scheduleCloudPush(80);
  }
  renderGreenBoard();
  paintRadioSeekProgress(radioPlayer.currentTime || 0);
  updateRadioReviewEntryBadge();
}

function openRadioReview(forceRestart) {
  const items = getRadioReviewItems();
  if (!items.length) return;
  if (radioInitialized && !radioPlayer.paused) {
    radioPlayer.pause();
    syncRadioUI(false);
  }
  stopRadioReviewAudio();
  ensureRadioReviewState(!!forceRestart);
  radioReviewOpen = true;
  const pStage = document.getElementById("radio-player-stage");
  const rStage = document.getElementById("radio-review-stage");
  if (pStage) pStage.classList.add("hidden");
  if (rStage) rStage.classList.remove("hidden");
  advanceRadioReviewPointer();
  renderRadioReviewStage();
}

function closeRadioReview() {
  JA_ASR.stop();
  stopRadioReviewAudio();
  clearActiveWordToken();
  radioReviewOpen = false;
  const pStage = document.getElementById("radio-player-stage");
  const rStage = document.getElementById("radio-review-stage");
  if (rStage) rStage.classList.add("hidden");
  if (pStage) pStage.classList.remove("hidden");
  paintRadioSeekProgress(radioPlayer.currentTime || 0);
  updateRadioReviewEntryBadge();
}

function openRadioSpeaking(startIdx) {
  const prompts = getRadioSpeakingPrompts();
  if (!prompts.length) return;
  if (radioInitialized && !radioPlayer.paused) {
    radioPlayer.pause();
    syncRadioUI(false);
  }
  JA_ASR.stop();
  stopRadioReviewAudio();
  ensureRadioReviewState(false);
  radioReviewOpen = true;
  const pStage = document.getElementById("radio-player-stage");
  const rStage = document.getElementById("radio-review-stage");
  if (pStage) pStage.classList.add("hidden");
  if (rStage) rStage.classList.remove("hidden");
  rvMode = "speak";
  rvSpeakIdx = Math.max(0, Math.min(prompts.length, Number(startIdx || 0)));
  rvSpeakState = { listening: false, interim: "", result: null, revealedModel: false, errorMsg: "" };
  renderRadioReviewStage();
}

function playSpeakingPromptAudio(prompt, which) {
  if (!prompt) return;
  const key = which === "model" ? "spk_model" : "spk_q";
  if (rvClipPlayingKey === key) {
    stopRadioReviewAudio();
    return;
  }
  JA_ASR.stop();
  stopRadioReviewAudio();
  rvClipPlayingKey = key;
  syncRvAudioButtons();
  const text = which === "model" ? (prompt.model_ja || "") : (prompt.prompt_ja || "");
  const doneCb = () => {
    if (rvClipPlayingKey === key) {
      rvClipPlayingKey = "";
      syncRvAudioButtons();
    }
  };
  if (which === "model" && prompt.demo_audio && prompt.model_ja === (getReviewItemById(`RVR-${prompt.point_id}`) || {}).ja_example) {
    warmAudio(prompt.demo_audio).then(resolved => {
      if (rvClipPlayingKey !== key) return;
      try {
        wordPlayer.onended = doneCb;
        wordPlayer.onerror = () => speakUtteranceLang(text, "ja-JP", 0.94, doneCb);
        wordPlayer.src = resolved || prompt.demo_audio;
        wordPlayer.currentTime = 0;
        wordPlayer.playbackRate = 1.0;
        const pr = wordPlayer.play();
        if (pr && typeof pr.catch === "function") pr.catch(() => speakUtteranceLang(text, "ja-JP", 0.94, doneCb));
      } catch (e) {
        speakUtteranceLang(text, "ja-JP", 0.94, doneCb);
      }
    });
  } else {
    speakUtteranceLang(text, "ja-JP", 0.94, doneCb);
  }
}

function revealSpeakingModelNow() {
  rvSpeakState.revealedModel = true;
  renderRadioReviewStage();
}

function toggleRadioSpeakingMic() {
  const prompt = getActiveSpeakingPrompt();
  if (!prompt) return;
  if (rvSpeakState.listening || JA_ASR.isActive("rv_speak")) {
    JA_ASR.stop();
    rvSpeakState.listening = false;
    renderRadioReviewStage();
    return;
  }
  rvSpeakState = { listening: true, interim: "", result: null, revealedModel: rvSpeakState.revealedModel, errorMsg: "" };
  renderRadioReviewStage();
  const started = JA_ASR.start("rv_speak", {
    onInterim: (txt) => {
      rvSpeakState.interim = txt;
      const el = document.getElementById("spk-interim-live");
      if (el) el.textContent = txt;
    },
    onFinal: (alts) => {
      rvSpeakState.listening = false;
      rvSpeakState.interim = "";
      rvSpeakState.errorMsg = "";
      const res = JA_ASR.analyzeSpokenOutput(alts, prompt);
      rvSpeakState.result = res;
      rvSpeakState.revealedModel = true;
      const st = ensureRadioReviewState(false);
      if (!Array.isArray(st.spokenIds)) st.spokenIds = [];
      if (!st.spokenIds.includes(prompt.id)) st.spokenIds.push(prompt.id);
      st.updatedAt = nowUnixSec();
      const lbl = res.ok ? "开口:自然达标" : (res.traps && res.traps.length ? `开口:提醒(${res.traps[0].slice(0, 14)})` : "开口:再练目标句型");
      pushSpokenRecord(prompt.id, prompt.key || prompt.title, lbl, res.ok);
      renderRadioReviewStage();
    },
    onError: (msg) => {
      rvSpeakState.listening = false;
      rvSpeakState.errorMsg = msg;
      renderRadioReviewStage();
    },
    onEnd: () => {
      if (rvSpeakState.listening) {
        rvSpeakState.listening = false;
        renderRadioReviewStage();
      }
    }
  });
  if (!started) {
    rvSpeakState.listening = false;
    renderRadioReviewStage();
  }
}

function nextRadioSpeakingPrompt() {
  JA_ASR.stop();
  stopRadioReviewAudio();
  const prompts = getRadioSpeakingPrompts();
  rvSpeakIdx += 1;
  rvSpeakState = { listening: false, interim: "", result: null, revealedModel: false, errorMsg: "" };
  if (rvSpeakIdx >= prompts.length) {
    const st = ensureRadioReviewState(false);
    st.updatedAt = nowUnixSec();
    saveAdaptiveState();
  }
  renderRadioReviewStage();
}

function toggleReviewMicCheck() {
  const item = getReviewItemById(rvActiveItemId);
  if (!item) return;
  const btn = document.getElementById("rv-mic-btn");
  const fb = document.getElementById("rv-mic-feedback");
  if (JA_ASR.isActive("rv_item")) {
    JA_ASR.stop();
    if (btn) { btn.classList.remove("listening"); btn.innerHTML = "试读"; }
    if (fb && fb.textContent === "请开口读出日语…") fb.textContent = "";
    return;
  }
  if (btn) { btn.classList.add("listening"); btn.innerHTML = `<span class="mic-dot"></span>聆听中`; }
  if (fb) { fb.className = "mic-feedback left"; fb.textContent = "请开口读出日语…"; }
  JA_ASR.start("rv_item", {
    onInterim: (txt) => {
      const f = document.getElementById("rv-mic-feedback");
      if (f) { f.className = "mic-feedback left"; f.textContent = `听到：${txt}`; }
    },
    onFinal: (alts) => {
      const b = document.getElementById("rv-mic-btn");
      const f = document.getElementById("rv-mic-feedback");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
      const res = item.kind === "vocab"
        ? JA_ASR.analyzePronunciation(alts, item.title, item.kana, item.ja_example)
        : JA_ASR.analyzeSpokenOutput(alts, {
            title: item.title,
            target_stems: [String(item.title || "").replace(/[〜~～]/g, "").trim()].filter(Boolean)
          });
      if (f) {
        f.className = "mic-feedback left " + (res.ok ? "ok" : "ng");
        f.textContent = res.ok
          ? `✓ ${res.verdict}${res.heard ? " · " + res.heard : ""}`
          : `听到「${res.heard || ""}」· ${res.verdict}`;
      }
      pushSpokenRecord(`RV-${item.id}`, item.key || item.title, res.ok ? "试读:准确" : `试读:${res.verdict.slice(0, 18)}`, res.ok);
    },
    onError: (msg) => {
      const b = document.getElementById("rv-mic-btn");
      const f = document.getElementById("rv-mic-feedback");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
      if (f) { f.className = "mic-feedback left ng"; f.textContent = msg; }
    },
    onEnd: () => {
      const b = document.getElementById("rv-mic-btn");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
    }
  });
}

function renderRadioSpeakingStage(host) {
  const prompts = getRadioSpeakingPrompts();
  if (!prompts.length || rvSpeakIdx >= prompts.length) {
    const practicedHTML = prompts.length
      ? `<div class="rv-done-list">${prompts.map(x => `<span style="color:var(--moss);">${escapeHtml(x.title)}</span>`).join("")}</div>`
      : "";
    host.innerHTML = `
      <div class="meta-bar">
        <button type="button" class="text-btn" onclick="closeRadioReview()">← 回到随身听</button>
        <span class="overline ok">听后开口已完成</span>
      </div>
      <div class="rv-focal">
        <h2 class="point-heading">今日 ${prompts.length} 句开口已练完</h2>
        <p class="logic-line">刚听完就顺嘴把句型说出口，耳朵的被动识别会更快变成嘴上的自然反应。</p>
        ${practicedHTML}
      </div>
      <div class="rv-dock">
        <button type="button" class="ghost-btn" onclick="openRadioSpeaking(0)">再练一遍</button>
        <button type="button" class="rv-btn-pass" onclick="closeRadioReview()">回到随身听</button>
      </div>
    `;
    return;
  }

  const p = prompts[rvSpeakIdx];
  const canRec = JA_ASR.supported();
  const s = rvSpeakState || { listening: false, interim: "", result: null, revealedModel: false, errorMsg: "" };
  const isLast = rvSpeakIdx + 1 >= prompts.length;
  const showLiveArea = !!(s.listening || s.result || s.revealedModel || s.errorMsg);

  let liveHTML = "";
  if (showLiveArea) {
    const trapsHTML = (s.result && Array.isArray(s.result.traps) && s.result.traps.length)
      ? s.result.traps.map(t => `<div class="spk-trap-line">${escapeHtml(t)}</div>`).join("")
      : "";
    liveHTML = `
      <div class="spk-live-area">
        ${s.listening ? `<div class="spk-heard"><span class="spk-heard-lbl">聆听中</span><span id="spk-interim-live">${escapeHtml(s.interim || "请自然说出日语…")}</span></div>` : ""}
        ${s.errorMsg ? `<div class="spk-verdict warn">${escapeHtml(s.errorMsg)}</div>` : ""}
        ${s.result ? `
          <div class="spk-heard"><span class="spk-heard-lbl">你说</span>${escapeHtml(s.result.heard || "")}</div>
          <div class="spk-verdict ${s.result.ok ? "ok" : "warn"}">${s.result.ok ? "✓ " : ""}${escapeHtml(s.result.verdict || "")}</div>
          ${trapsHTML}
        ` : ""}
        ${s.revealedModel ? `
          <div class="spk-model-wrap">
            <span class="spk-model-lbl">地道参考说法</span>
            <div class="spk-model-ja">${annotateJapanese(p.model_ja || "")}</div>
            ${p.model_zh ? `<div class="spk-model-zh">${escapeHtml(p.model_zh)}</div>` : ""}
            ${p.coaching_tip ? `<div class="spk-tip">${escapeHtml(p.coaching_tip)}</div>` : ""}
            <div class="rv-clip-row" style="margin-top:4px;">
              <button type="button" class="rv-clip-btn" data-rv-aud="spk_model" onclick="playSpeakingPromptAudio(getActiveSpeakingPrompt(), 'model')">▶ 听地道说法跟读</button>
            </div>
          </div>
        ` : ""}
      </div>
    `;
  }

  let dockHTML = "";
  if (!canRec) {
    dockHTML = `
      <button type="button" class="ghost-btn" onclick="playSpeakingPromptAudio(getActiveSpeakingPrompt(), 'model')">▶ 听示范跟读</button>
      <button type="button" class="rv-btn-pass" onclick="nextRadioSpeakingPrompt()">${isLast ? "完成开口 ✓" : "下一句 →"}</button>
    `;
  } else if (s.listening) {
    dockHTML = `
      <button type="button" class="rv-btn-mic listening" onclick="toggleRadioSpeakingMic()"><span class="mic-dot"></span>聆听中 · 点此结束</button>
    `;
  } else if (s.result) {
    dockHTML = `
      <button type="button" class="ghost-btn" onclick="toggleRadioSpeakingMic()">再说一遍</button>
      <button type="button" class="rv-btn-pass" onclick="nextRadioSpeakingPrompt()">${isLast ? "完成开口 ✓" : "下一句 →"}</button>
    `;
  } else {
    dockHTML = `
      <button type="button" class="ghost-btn" onclick="nextRadioSpeakingPrompt()">${isLast ? "跳过收尾" : "跳过"}</button>
      <button type="button" class="rv-btn-mic" onclick="toggleRadioSpeakingMic()">按下开口说日语</button>
    `;
  }

  host.innerHTML = `
    <div class="meta-bar">
      <button type="button" class="text-btn" onclick="closeRadioReview()">← 回到随身听</button>
      <span class="overline warm">听后开口 · ${rvSpeakIdx + 1} / ${prompts.length}</span>
    </div>
    <div class="rv-stage-card" id="rv-stage-card">
      <div class="rv-focal is-relearn">
        <div class="rv-story-tag">
          <span>${escapeHtml(p.chapter_title || "")} · 练「${escapeHtml(p.title || "")}」</span>
          ${p.is_new_n2 ? `<span class="rv-n2-dot">· N2 新学</span>` : ""}
        </div>
        <p class="spk-prompt-ja">${annotateJapanese(p.prompt_ja || "")}</p>
        <p class="spk-prompt-zh">${escapeHtml(p.prompt_zh || "")}</p>
        <div class="rv-clip-row">
          <button type="button" class="rv-clip-btn" data-rv-aud="spk_q" onclick="playSpeakingPromptAudio(getActiveSpeakingPrompt(), 'q')">▶ 听问题</button>
          ${!s.revealedModel ? `<button type="button" class="rv-clip-btn quiet" onclick="revealSpeakingModelNow()">看参考说法</button>` : ""}
        </div>
        ${!canRec ? `<p class="spk-tip">当前浏览器不支持实时收音，听示范直接开口跟读即可。</p>` : ""}
        ${liveHTML}
      </div>
      ${lexBoxHTML("rv-inline-lex")}
    </div>
    <div class="rv-dock">${dockHTML}</div>
  `;
  syncRvAudioButtons();
}

function revealRadioReviewCard() {
  if (rvRevealed || rvMode === "relearn" || rvMode === "done" || rvMode === "speak") return;
  rvRevealed = true;
  rvRevealedAt = performance.now();
  const item = getReviewItemById(rvActiveItemId);
  const headEl = document.getElementById("rv-head");
  if (headEl && item && item.title) headEl.textContent = item.title;
  const el = document.getElementById("rv-reveal-area");
  if (el) el.classList.add("shown");
  const hint = document.getElementById("rv-tap-hint");
  if (hint) hint.style.display = "none";
}

function animateRvCardAndRun(dirCls, fn) {
  const card = document.getElementById("rv-stage-card");
  rvAnimating = true;
  JA_ASR.stop();
  stopRadioReviewAudio();
  if (!card) {
    rvAnimating = false;
    fn();
    return;
  }
  card.classList.remove("settling");
  card.classList.add(dirCls);
  setTimeout(() => {
    rvAnimating = false;
    fn();
  }, 210);
}

function handleRadioReviewPass() {
  if (rvAnimating) return;
  const st = ensureRadioReviewState(false);
  const item = getReviewItemById(rvActiveItemId);
  if (!item) return;
  // Dunlosky & Lipko (2007) JOL calibration: require reveal + >=800ms verification before marking as verified pass
  const isVerified = !!(rvRevealed && rvRevealedAt > 0 && (performance.now() - rvRevealedAt) >= 800);

  animateRvCardAndRun("fly-right", () => {
    st.updatedAt = nowUnixSec();
    if (rvMode === "triage") {
      if (!st.passedIds.includes(item.id)) st.passedIds.push(item.id);
      if (isVerified && item.point_id && A.pts[item.point_id]) A.pts[item.point_id].audioPrimed = true;
      st.triageIdx += 1;
      pushRadioReviewRecord(item, isVerified ? "听后复盘:过" : "听后复盘:快过存疑", true);
    } else if (rvMode === "tail") {
      st.tailQueue = (st.tailQueue || []).filter(id => id !== item.id);
      if (!st.tailDoneIds.includes(item.id)) st.tailDoneIds.push(item.id);
      saveAdaptiveState();
    }
    advanceRadioReviewPointer();
    renderRadioReviewStage();
  });
}

function handleRadioReviewRelearn() {
  if (rvAnimating) return;
  const st = ensureRadioReviewState(false);
  const item = getReviewItemById(rvActiveItemId);
  if (!item) return;
  JA_ASR.stop();
  stopRadioReviewAudio();

  rvReturnMode = rvMode;
  st.updatedAt = nowUnixSec();
  if (!st.relearnIds.includes(item.id)) {
    st.relearnIds.push(item.id);
    if (!st.tailQueue.includes(item.id)) st.tailQueue.push(item.id);
    pushRadioReviewRecord(item, "听后复盘:重学", false);
  }
  if (rvMode === "triage") {
    st.triageIdx += 1;
  } else if (rvMode === "tail") {
    // Move to end of tail queue so it re-checks after any other flagged items
    st.tailQueue = (st.tailQueue || []).filter(id => id !== item.id);
    st.tailQueue.push(item.id);
  }
  saveAdaptiveState();
  rvMode = "relearn";
  rvRevealed = true;
  renderRadioReviewStage();
  // Immediately anchor with the exact podcast context clip (Encoding Specificity!)
  playReviewPodcastClip(item, 1.0, "clip_1", true);
}

function finishRadioRelearnStep() {
  if (rvAnimating) return;
  JA_ASR.stop();
  stopRadioReviewAudio();
  advanceRadioReviewPointer();
  renderRadioReviewStage();
}

function bindRadioReviewSwipe(cardEl) {
  if (!cardEl || rvMode === "relearn" || rvMode === "done" || rvMode === "speak") return;
  let sx = 0, sy = 0, stMs = 0, tracking = false, axis = null;
  cardEl.addEventListener("touchstart", e => {
    if (rvAnimating || !e.touches || e.touches.length !== 1) return;
    if (e.target && e.target.closest && e.target.closest("button, .w-tok")) return;
    tracking = true;
    axis = null;
    sx = fpX(e.touches[0]);
    sy = fpY(e.touches[0]);
    stMs = performance.now();
    cardEl.classList.remove("settling");
  }, { passive: true });
  cardEl.addEventListener("touchmove", e => {
    if (!tracking || !e.touches || e.touches.length !== 1) return;
    const dx = fpX(e.touches[0]) - sx;
    const dy = fpY(e.touches[0]) - sy;
    if (!axis) {
      if (Math.hypot(dx, dy) < 10) return;
      axis = Math.abs(dx) > Math.abs(dy) * 1.15 ? "x" : "y";
    }
    if (axis === "x") {
      if (e.cancelable) e.preventDefault();
      cardEl.style.transform = `translate3d(${dx.toFixed(1)}px, ${(dy * 0.14).toFixed(1)}px, 0) rotate(${(dx * 0.025).toFixed(2)}deg)`;
      const stR = document.getElementById("rv-st-right");
      const stL = document.getElementById("rv-st-left");
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
  const endSwipe = (e, cancelled) => {
    if (!tracking) return;
    tracking = false;
    if (cancelled || axis !== "x" || !e.changedTouches || !e.changedTouches.length) {
      if (axis === "x") {
        cardEl.classList.add("settling");
        cardEl.style.transform = "";
      }
      axis = null;
      return;
    }
    const dx = fpX(e.changedTouches[0]) - sx;
    const dt = Math.max(1, performance.now() - stMs);
    const vx = dx / dt;
    axis = null;
    if (dx >= 56 || (dx >= 30 && vx > 0.42)) {
      handleRadioReviewPass();
      return;
    }
    if (dx <= -56 || (dx <= -30 && vx < -0.42)) {
      handleRadioReviewRelearn();
      return;
    }
    cardEl.classList.add("settling");
    cardEl.style.transform = "";
    const stR = document.getElementById("rv-st-right");
    const stL = document.getElementById("rv-st-left");
    if (stR) stR.style.opacity = "0";
    if (stL) stL.style.opacity = "0";
  };
  cardEl.addEventListener("touchend", e => endSwipe(e, false), { passive: true });
  cardEl.addEventListener("touchcancel", e => endSwipe(e, true), { passive: true });
}

function renderRadioReviewStage() {
  const host = document.getElementById("radio-review-stage");
  if (!host) return;
  const items = getRadioReviewItems();
  const st = ensureRadioReviewState(false);

  if (rvMode === "speak") {
    renderRadioSpeakingStage(host);
    return;
  }

  const spPrompts = getRadioSpeakingPrompts();
  const spokenSet = new Set(Array.isArray(st.spokenIds) ? st.spokenIds : []);
  const allSpokenDone = spPrompts.length > 0 && spPrompts.every(x => spokenSet.has(x.id));

  if (rvMode === "done" || !rvActiveItemId) {
    const rmDone = computeDaily120Metrics();
    const relearnedItems = (st.relearnIds || []).map(id => getReviewItemById(id)).filter(Boolean);
    const passedCnt = Math.max(0, items.length - relearnedItems.length);
    const relearnNamesHTML = relearnedItems.length
      ? `<div class="rv-done-list">${relearnedItems.map(x => `<span>${escapeHtml(x.title)}</span>`).join("")}</div>`
      : "";
    const doneOverline = rmDone.radioDone
      ? "收尾小节已收笔 · 随身听圆印圆满"
      : "收尾小节已完成 · 听完正文即可收笔";
    const speakHintLine = spPrompts.length
      ? (allSpokenDone
        ? `<p class="spk-tip" style="margin-top:6px;">今日 ${spPrompts.length} 句听后开口已完成 ✓</p>`
        : `<p class="spk-tip" style="margin-top:6px;">方便开口的话，顺手把今天学的 ${spPrompts.length} 个句型用日语说出口（在外面可随时跳过）。</p>`)
      : "";
    const dockHTML = spPrompts.length && !allSpokenDone
      ? `
        <button type="button" class="ghost-btn" onclick="closeRadioReview()">回到随身听</button>
        <button type="button" class="rv-btn-pass" onclick="openRadioSpeaking(0)">开口说 ${spPrompts.length} 句 →</button>
      `
      : `
        <button type="button" class="ghost-btn" onclick="${spPrompts.length ? "openRadioSpeaking(0)" : "openRadioReview(true)"}">${spPrompts.length ? "再练开口" : "重来一遍"}</button>
        <button type="button" class="rv-btn-pass" onclick="closeRadioReview()">回到随身听</button>
      `;
    host.innerHTML = `
      <div class="meta-bar">
        <button type="button" class="text-btn" onclick="closeRadioReview()">← 回到随身听</button>
        <span class="overline ok">${doneOverline}</span>
      </div>
      <div class="rv-focal">
        <h2 class="point-heading">${relearnedItems.length ? `本次重学 ${relearnedItems.length} 项，其余 ${passedCnt} 项已秒过` : `本期 ${items.length} 个重点全部听懂`}</h2>
        <p class="logic-line">${relearnedItems.length
          ? `下面标出的重点已自动记入明日做题与记词队列，下期《锵锵》也会顺嘴再帮你搭一次桥。`
          : `今天 60 分钟里的表达和词汇都接住了，没有需要单独回炉的卡点。`}</p>
        ${renderReviewStoryGalleryHTML()}
        ${relearnNamesHTML}
        ${speakHintLine}
      </div>
      <div class="rv-dock">${dockHTML}</div>
    `;
    return;
  }

  const item = getReviewItemById(rvActiveItemId);
  if (!item) return;

  const hasKanji = /[\u4e00-\u9faf\u3400-\u4dbf]/.test(item.title || "");
  const kanaHTML = (hasKanji && item.kana)
    ? renderTrapKanaHTML(item.title, item.kana, item.trap_hl || [], item.trap_tag || "")
    : (item.kana && item.kana !== item.title ? escapeHtml(item.kana) : "");
  const clipSecs = Math.max(5, Math.round((item.clip_end || 14) - (item.clip_start || 0)));

  if (rvMode === "relearn") {
    const showMic = JA_ASR.supported();
    host.innerHTML = `
      <div class="meta-bar">
        <button type="button" class="text-btn" onclick="closeRadioReview()">← 随身听</button>
        <span class="overline warm">语境精学 · ${escapeHtml(item.chapter_title || "")}</span>
      </div>
      <div class="rv-stage-card" id="rv-stage-card">
        <div class="rv-focal is-relearn">
          <div class="rv-story-tag">
            <span>${escapeHtml(item.chapter_title || "")}</span>
            ${item.is_new_n2 ? `<span class="rv-n2-dot">· N2 新学</span>` : ""}
          </div>
          ${item.img ? `<div class="rv-relearn-art-wrap" onclick="openStoryArtModal()"><img src="${escapeHtml(item.img)}" class="rv-relearn-art-img" alt="${escapeHtml(item.chapter_title || '')}" /></div>` : ""}
          <h2 class="rv-head">${escapeHtml(item.title)}</h2>
          ${kanaHTML ? `<div class="rv-kana-line">${kanaHTML}</div>` : ""}
          <div class="rv-zh-line">${escapeHtml(item.zh || "")}</div>

          <div class="rv-clip-row">
            <button type="button" class="rv-clip-btn" data-rv-aud="clip_1" onclick="playReviewPodcastClip(getReviewItemById('${item.id}'), 1.0, 'clip_1')"><span class="rv-aud-ico">▶</span> 原声语境 (${clipSecs}s)</button>
            <button type="button" class="rv-clip-btn quiet" data-rv-aud="clip_085" onclick="playReviewPodcastClip(getReviewItemById('${item.id}'), 0.85, 'clip_085')">0.85x 慢听</button>
          </div>

          <p class="rv-quote"><span class="rv-quote-spk">${escapeHtml(item.speaker || "主持")}</span>${annotateJapanese(item.context_line || "")}</p>
          ${item.mnemonic ? `<div class="vc-hook rv-hook" style="margin-top:4px;"><span class="vc-hook-tag">记音</span>${escapeHtml(item.mnemonic)}</div>` : ""}
          ${item.nuance ? `<p class="rv-note-line">${escapeHtml(item.nuance)}</p>` : ""}
          ${item.twin ? `<p class="rv-twin-line">${escapeHtml(item.twin)}</p>` : ""}
          ${item.ja_example && item.ja_example !== item.title ? `<div class="rv-ja-ex">${annotateJapanese(item.ja_example)}</div>` : ""}

          <div class="rv-shadow-row">
            <span class="rv-shadow-hint">顺口跟读一遍，耳朵和嘴一起锁住</span>
            <div class="rv-meta-right">
              <button type="button" class="rv-clip-btn" data-rv-aud="demo" onclick="playReviewDemoSentence(getReviewItemById('${item.id}'))">▶ 示范发音</button>
              ${showMic ? `<button type="button" class="rv-clip-btn quiet mic-btn" id="rv-mic-btn" onclick="toggleReviewMicCheck()">试读</button>` : ""}
            </div>
          </div>
          <div class="mic-feedback left" id="rv-mic-feedback"></div>
        </div>
        ${lexBoxHTML("rv-inline-lex")}
      </div>
      <div class="rv-dock">
        <button type="button" class="rv-btn-pass" onclick="finishRadioRelearnStep()">记住了 · 稍后复查 →</button>
      </div>
    `;
    syncRvAudioButtons();
    return;
  }

  // Phase 1 ("triage") or Phase 3 ("tail" blind re-check)
  const isTail = rvMode === "tail";
  const progressTxt = isTail
    ? `收尾复查 · 仅余 ${st.tailQueue.length} 项`
    : `听后复盘 · ${Math.min(items.length, st.triageIdx + 1)} / ${items.length}`;

  host.innerHTML = `
    <div class="meta-bar">
      <button type="button" class="text-btn" onclick="closeRadioReview()">← 随身听</button>
      <div class="rv-meta-right">
        <span class="overline${isTail ? " warm" : ""}">${progressTxt}</span>
        ${spPrompts.length ? `<button type="button" class="rv-spk-pill" onclick="openRadioSpeaking(0)">开口 ${spPrompts.length} 句 ›</button>` : ""}
      </div>
    </div>
    <div class="rv-stage-card" id="rv-stage-card" onclick="if(!event.target.closest('button,.w-tok'))revealRadioReviewCard()">
      <div class="tutor-stamp right" id="rv-st-right">懂了 · 过 →</div>
      <div class="tutor-stamp left" id="rv-st-left">← 重学这个</div>

      <div class="rv-focal">
        <div class="rv-story-tag">
          <span>${escapeHtml(item.chapter_title || "")}</span>
          ${item.is_new_n2 ? `<span class="rv-n2-dot">· N2 新学</span>` : ""}
          ${isTail ? `<span class="rv-n2-dot">· 刚才重学</span>` : ""}
        </div>
        <h2 class="rv-head" id="rv-head">${escapeHtml(rvRevealed ? item.title : stripGrammarSpoilerTitle(item.title))}</h2>
        <p class="rv-cue-line">${escapeHtml(item.story_cue || "")}</p>

        <div class="rv-clip-row">
          <button type="button" class="rv-clip-btn" data-rv-aud="clip_1" onclick="event.stopPropagation();playReviewPodcastClip(getReviewItemById('${item.id}'), 1.0, 'clip_1')"><span class="rv-aud-ico">▶</span> 听原声语境 (${clipSecs}s)</button>
        </div>

        <div class="rv-tap-hint" id="rv-tap-hint" style="${rvRevealed ? "display:none" : ""}">先回忆意思或读音，轻点核对</div>

        <div class="rv-reveal-area${rvRevealed ? " shown" : ""}" id="rv-reveal-area">
          ${kanaHTML ? `<div class="rv-kana-line">${kanaHTML}</div>` : ""}
          <div class="rv-zh-line">${escapeHtml(item.zh || "")}</div>
          ${item.mnemonic ? `<div class="vc-hook rv-hook" style="margin-bottom:8px;"><span class="vc-hook-tag">记音</span>${escapeHtml(item.mnemonic)}</div>` : ""}
          <p class="rv-quote"><span class="rv-quote-spk">${escapeHtml(item.speaker || "主持")}</span>${annotateJapanese(item.context_line || "")}</p>
        </div>
      </div>
      ${lexBoxHTML("rv-inline-lex")}
    </div>
    <div class="rv-dock">
      <button type="button" class="rv-btn-relearn" onclick="handleRadioReviewRelearn()">${isTail ? "← 再学一遍" : "← 重学这个"}</button>
      <button type="button" class="rv-btn-pass" onclick="handleRadioReviewPass()">${isTail ? "真记住了 →" : "懂了 · 过 →"}</button>
    </div>
  `;
  bindRadioReviewSwipe(document.getElementById("rv-stage-card"));
  syncRvAudioButtons();
  if (rvMode === "triage" || rvMode === "tail") {
    playReviewPodcastClip(item, 1.0, "clip_1", true);
  }
}

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
    if (p.family === A.hotFamily) {
      A.hotFamily = null;
      A.hotFamilyDueStep = 0;
    }
    saveAdaptiveState();
    scheduleCloudPush(120);
  }
  setupCurrentTurn();
  stageEnteredAt = performance.now();
  renderTutor();
  autoPlayCurrentTurn();
}

// Calm zero-guess escape hatch: never force a blind guess, and NEVER count peeking as passed!
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
  ps.greenAt = 0;
  ps.status = "learning";
  ps.wrongCount = (ps.wrongCount || 0) + 1;
  ps.passStreak = 0;
  ps.reqPasses = (activeQuizObj.is_listening && p.variants && p.variants.length > 0) ? 2 : 1;
  ps.retryCardId = activeQuizObj.id;
  ps.dueStep = A.step + 3;
  // Rohrer & Taylor (2007) / Pan (2015): delay same-family contrast by 4 cards instead of immediate blocking!
  A.hotFamily = p.family;
  A.hotFamilyDueStep = A.step + 4;
  A.step += 1;
  A.lastPointId = p.id;
  recomputeStatusesFromCRDT(A);
  const nextMs = applyMasteryAction(p.point_key, p.point, "fail", stamp);
  syncBackendRecord(p, activeQuizObj.id, "不确定", false, false, nextMs, stamp);

  renderTutor();
  playMainClip(activeQuizObj.exp_audio, "exp", false);
}

let lastAnswerHesitant = false;

function submitAnswer(val) {
  if (viewStage !== "quiz" || !activeQuizObj) return;
  const thinkMs = Math.max(0, performance.now() - (stageEnteredAt || 0));
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
  lastAnswerHesitant = !!(isCorrect && !activeQuizObj.is_listening && thinkMs >= 14000 && thinkMs < 90000);

  if (isCorrect) {
    if (!A.hesitantKeys || typeof A.hesitantKeys !== "object") A.hesitantKeys = {};
    if (lastAnswerHesitant) {
      A.hesitantKeys[p.point_key] = 1;
      A.hesitantKeys[p.point] = 1;
      const hOb = loadOutbox();
      hOb.push([`HES:${activeQuizObj.id}`, p.point_key || p.point, "犹豫过关", 1, new Date(stamp * 1000).toISOString()]);
      saveOutbox(hOb);
    } else {
      A.hesitantKeys[p.point_key] = 0;
      A.hesitantKeys[p.point] = 0;
    }
    if (hadWrongToday) {
      ps.passStreak = (ps.passStreak || 0) + 1;
      const needed = ps.reqPasses || ((activeQuizObj.is_listening && p.variants && p.variants.length > 0) ? 2 : 1);
      if (ps.passStreak < needed) {
        // Passed the exact missed listening dialogue once; schedule a variant check 3 steps later before daily pass!
        ps.retryCardId = "";
        if (p.variants && p.variants.length > 0) {
          if (ps.useVariant) ps.variantIdx = (ps.variantIdx || 0) + 1;
          ps.useVariant = true;
        }
        ps.status = "learning";
        ps.dueStep = A.step + 3;
        if (p.family === A.hotFamily) { A.hotFamily = null; A.hotFamilyDueStep = 0; }
        A.step += 1;
        A.lastPointId = p.id;
        recomputeStatusesFromCRDT(A);
        const nextMs = applyMasteryAction(p.point_key, p.point, "recover", stamp);
        syncBackendRecord(p, activeQuizObj.id, val, true, false, nextMs, stamp);
      } else {
        ps.retryCardId = "";
        ps.greenAt = Math.max(stamp, (ps.retestAt || 0) + 1, (A.resetAt || 0) + 1);
        ps.status = "green";
        if (p.family === A.hotFamily) { A.hotFamily = null; A.hotFamilyDueStep = 0; }
        A.step += 1;
        A.lastPointId = p.id;
        recomputeStatusesFromCRDT(A);
        const nextMs = applyMasteryAction(p.point_key, p.point, "recover", ps.greenAt);
        syncBackendRecord(p, activeQuizObj.id, val, true, false, nextMs, ps.greenAt);
      }
    } else {
      ps.retryCardId = "";
      ps.greenAt = Math.max(stamp, (ps.retestAt || 0), (A.resetAt || 0) + 1);
      ps.status = "green";
      if (p.family === A.hotFamily) { A.hotFamily = null; A.hotFamilyDueStep = 0; }
      A.step += 1;
      A.lastPointId = p.id;
      recomputeStatusesFromCRDT(A);
      const nextMs = applyMasteryAction(p.point_key, p.point, "pass", ps.greenAt);
      syncBackendRecord(p, activeQuizObj.id, val, true, false, nextMs, ps.greenAt);
    }
  } else {
    ps.retestAt = Math.max(stamp, (ps.greenAt || 0) + 1);
    ps.greenAt = 0;
    ps.status = "learning";
    ps.wrongCount = (ps.wrongCount || 0) + 1;
    ps.passStreak = 0;
    ps.reqPasses = (activeQuizObj.is_listening && p.variants && p.variants.length > 0) ? 2 : 1;
    ps.retryCardId = activeQuizObj.id;
    ps.dueStep = A.step + 3;
    A.hotFamily = p.family;
    A.hotFamilyDueStep = A.step + 4;
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
    ps.greenAt = 0;
    ps.status = "learning";
    ps.passStreak = 0;
    ps.retryCardId = "";
    if (p && p.variants && p.variants.length > 0) ps.useVariant = true;
    ps.dueStep = A.step + 3;
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
  } else if (viewStage === "quiz" && activeQuizObj) {
    playQuizQuestionAudio(activeQuizObj, false);
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
  const keepWordLookups = A.wordLookups || {};
  const keepRadio = A.radioMaxSec || 0;
  const keepRadioPos = A.radioPos || [0, 0];
  const keepFlashProg = A.flashProg || [0, 0, 0, 0];
  const keepVocabSess = A.vocabSess || null;
  const keepRadioReview = A.radioReview || null;
  const keepGaProg = A.gaProg || [0, 0, 0, 0];
  const keepGaMap = A.gaMap || {};
  const keepGaSess = A.gaSess || null;
  const keepHesitant = A.hesitantKeys || {};
  const keepSt = A.st || 0;
  A = createFreshAdaptiveState();
  A.resetAt = stamp;
  A.masteryOverrides = keepOverrides;
  A.masteryOverrideTs = keepOverrideTs;
  A.tappedWords = keepTapped;
  A.wordLookups = keepWordLookups;
  A.radioMaxSec = keepRadio;
  A.radioPos = keepRadioPos;
  A.flashProg = keepFlashProg;
  A.vocabSess = keepVocabSess;
  A.radioReview = keepRadioReview;
  A.gaProg = keepGaProg;
  A.gaMap = keepGaMap;
  A.gaSess = keepGaSess;
  A.hesitantKeys = keepHesitant;
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
      <circle cx="14" cy="14" r="10.2" fill="var(--moss-solid)"/>
      <path d="M 9.6 14.3 L 12.6 17.2 L 18.7 10.9" fill="none" stroke="#FCFBF8" stroke-width="2.15" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
  }
  if (ratio > 0.005) {
    const pct = Math.max(8, Math.min(97, Math.round(ratio * 100)));
    return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="14" cy="14" r="9.8" fill="none" stroke="var(--hairline-strong)" stroke-width="1.85"/>
      <circle cx="14" cy="14" r="9.8" pathLength="100" fill="none" stroke="var(--moss-solid)" stroke-width="2.35" stroke-linecap="round" stroke-dasharray="${pct} 105" transform="rotate(-90 14 14)"/>
    </svg>`;
  }
  return `<svg class="enso-svg" viewBox="0 0 28 28" aria-hidden="true">
    <circle cx="14" cy="14" r="9.8" fill="none" stroke="var(--hairline-strong)" stroke-width="1.6" stroke-dasharray="3.6 3.2"/>
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
  } else if (idx === 2) {
    if (activeMode !== "vocab") switchMode("vocab");
    else openSessionModal();
  } else {
    if (activeMode !== "body") switchMode("body");
    else openSessionModal();
  }
}

function toggleDashLedger(ev) {
  if (ev) ev.stopPropagation();
  if (activeMode === "body") {
    if (window.ZB && typeof window.ZB.onHorizonRightTap === "function") window.ZB.onHorizonRightTap();
    return;
  }
  if (activeMode === "dash") {
    switchMode(prevNonDashMode || "tutor");
  } else {
    switchMode("dash");
  }
}

function renderGreenBoard() {
  const m = computeDaily120Metrics();
  const bm = (window.ZB && typeof window.ZB.getSummary === "function")
    ? window.ZB.getSummary()
    : { ratio: 0, done: false, label: "体律 0/3", text: "0 / 3 项" };

  const gaLbl = m.ga && m.ga.requiredToday
    ? ` · 语法盘点 ${m.ga.gaDone ? "✓" : m.ga.gaSeen + "/" + m.ga.gaTarget}`
    : "";
  const r3Label = `记词 ${m.flashDone ? "✓" : m.flashSeen + "/" + m.flashTarget}${gaLbl}`;

  const trioEl = document.getElementById("enso-trio");
  if (trioEl) {
    const doneKey = `${m.quizDone ? 1 : 0}${m.radioDone ? 1 : 0}${m.ritual3Done ? 1 : 0}${bm.done ? 1 : 0}`;
    const radioRingLbl = m.radioDone
      ? `随身听 已完成`
      : (m.radioAudioDone && !m.radioReviewDone
        ? `随身听 已听完 · 待收尾复盘`
        : `随身听 ${m.listenedMins}/${m.targetMins}分`);
    const rings = [
      { ratio: m.quizRatio, done: m.quizDone, label: `做题 ${m.greenCnt}/${m.totalCards}` },
      { ratio: m.radioRatio, done: m.radioDone, label: radioRingLbl },
      { ratio: m.ritual3Ratio, done: m.ritual3Done, label: r3Label },
      { ratio: bm.ratio, done: bm.done, label: bm.label }
    ];
    trioEl.innerHTML = rings.map((r, idx) => {
      const newlyDone = r.done && prevEnsoDoneKey && prevEnsoDoneKey[idx] === "0";
      return `<button class="enso-btn${r.done ? " done" : ""}${newlyDone ? " is-done" : ""}" id="enso-${idx + 1}" onclick="onEnsoTap(${idx}, event)" aria-label="${escapeHtml(r.label)}" title="${escapeHtml(r.label)}">${renderEnsoRingSVG(idx, r.ratio, r.done)}</button>`;
    }).join("");
    prevEnsoDoneKey = doneKey;
  }

  const quizPart = m.quizDone ? `做题 ✓` : `做题 ${m.greenCnt}/${m.totalCards}`;
  const radioPart = m.radioDone
    ? `随身听 ✓`
    : (m.radioAudioDone && !m.radioReviewDone ? `听完·待复盘` : `听 ${m.listenedMins}/${m.targetMins}分`);
  const flashPart = m.ritual3Done ? `记词 ✓` : r3Label;
  const bodyPart = bm.done ? `体律 ✓` : bm.label;
  document.getElementById("gm-left-txt").textContent = `${quizPart} · ${radioPart} · ${flashPart} · ${bodyPart}`;

  const rightEl = document.getElementById("gm-right-txt");
  if (rightEl) {
    if (activeMode === "body" && window.ZB && typeof window.ZB.getHorizonHTML === "function") {
      rightEl.classList.remove("active-ledger");
      rightEl.innerHTML = window.ZB.getHorizonHTML();
    } else {
      const ledgerTxt = activeMode === "dash" ? "收起总表" : "总表";
      rightEl.classList.toggle("active-ledger", activeMode === "dash");
      if (m.projScore >= 120) {
        rightEl.innerHTML = `预计 <b class="moss">${m.projScore}分</b><span class="ledger-sep"> · </span><span class="ledger-tag">${ledgerTxt}</span>`;
      } else {
        rightEl.innerHTML = `预计 <b>${m.projScore}分</b><span class="ledger-sep"> · </span><span class="ledger-tag">${ledgerTxt}</span>`;
      }
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
  clearQuizRecallTimer();
  quizChoicesRevealed = true;
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
      : (!m.ritual3Done
          ? `<button class="sumi-btn" onclick="switchMode('vocab')">${(!m.flashDone ? "去单手记词 →" : "去语法盘点 →")}</button>`
          : `<button class="sumi-btn" onclick="switchMode('dash')">查看总表 →</button>`);
    box.innerHTML = `
      <div class="meta-bar"><span class="overline ok">${m.allThreeDone ? "今日日语三修圆满 · 稳过 120 分" : `今日 ${m.totalCards} 道题已全部过关`}</span></div>
      <div class="focal-space">
        <h2 class="point-heading">${m.allThreeDone ? "今日三样皆已圆满" : `${m.totalCards} 道题已全部过关`}</h2>
        <p class="logic-line">${m.allThreeDone
          ? `做题、三人随身听与记词皆已收笔，预计总分稳锁在 ${m.projScore} 分。安心休息，考场稳站 120 分以上。`
          : `做题部分已拿满，当前预计 ${m.projScore} 分。${!m.radioDone ? "顺手听完今日随身听，" : ""}去第 3 栏收完今晚任务，就能把圆印全部点亮。`}</p>
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
            <div class="zp-ja"><span class="zp-dot"></span><span>${annotateJapanese(p.teach.left.ja)}</span></div>
            <div class="zp-sub">${escapeHtml(p.teach.left.sub)}</div>
          </div>
          ${p.teach.right && p.teach.right.ja ? `
          <div class="zen-pair-row">
            <div class="zp-ja"><span class="zp-dot muted"></span><span>${annotateJapanese(p.teach.right.ja)}</span></div>
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
    const isRetrySame = (ps.wrongCount || 0) > 0 && !isVariant;
    const effQ = getEffectiveMastery(p.point_key, p.point);
    // Kang, McDermott & Roediger (2007) + Tullis & Benjamin (2011):
    // Self-paced tap-to-reveal on 2/3 graduation cards — never rush reading with a short countdown!
    const useRecallVeil = !activeQuizObj.is_listening && (ps.wrongCount || 0) === 0 && (effQ.streak || 0) === 2;
    quizChoicesRevealed = !useRecallVeil;

    let label = p.subject;
    if (isRetrySame) label += " · 乱序重考";
    else if (isVariant) label += " · 换题复考";
    else if (useRecallVeil) label += " · 终审盲考";
    else if (ps.audioPrimed) label += " · 随身听已聊";

    const controlsHTML = activeQuizObj.is_listening
      ? `<div class="listen-num-grid">
          ${currentChoices.map((c, cIdx) => `
            <button class="listen-num-btn" onclick="submitAnswer(currentChoices[${cIdx}])">${cIdx + 1}</button>
          `).join("")}
        </div>`
      : `<div class="choice-veil-wrap">
          ${useRecallVeil ? `<button type="button" class="recall-veil-overlay" id="quiz-recall-veil" onclick="revealQuizChoicesNow()"><span class="recall-veil-title">读完题，先在心里想答案</span><span class="recall-veil-sub">想好轻点这里看选项</span></button>` : ""}
          <div class="choice-list${useRecallVeil ? " recall-veiled" : ""}" id="quiz-choice-list">
            ${currentChoices.map((c, cIdx) => `
              <button class="zen-choice" onclick="submitAnswer(currentChoices[${cIdx}])">
                <span>${escapeHtml(c)}</span>
                <span class="kbd-tag">${cIdx + 1}</span>
              </button>
            `).join("")}
          </div>
        </div>`;

    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline">${escapeHtml(label)}</span>
      </div>

      <div class="focal-space">
        <div class="quiz-focal">
          ${activeQuizObj.is_listening ? `
          <div class="listen-medallion-wrap">
            <button class="listen-medallion" id="voice-orb" onclick="playQuizQuestionAudio(activeQuizObj, true)" aria-label="播放">
              <svg class="med-ic" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/></svg>
              <div class="med-waves"><span></span><span></span><span></span></div>
            </button>
          </div>` : `<p class="quiz-ja" onclick="playQuizQuestionAudio(activeQuizObj, true)" title="轻点重听题目">${escapeHtml(activeQuizObj.prompt)}</p>`}
        </div>
      </div>

      <div class="action-dock">
        ${controlsHTML}
        <div class="quiz-aux-row">
          <button class="unsure-btn" onclick="revealWithoutGuess()">
            <span>不确定 · 直接看讲解</span>
            <span class="kbd-tag">0</span>
          </button>
          ${!activeQuizObj.is_listening ? `<button class="dock-replay-btn aux-read-btn" id="q-play-btn" onclick="playQuizQuestionAudio(activeQuizObj, true)">读题</button>` : ""}
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

  const stillNeedsVariantPass = isCorrect && ps.status !== "green";
  let overCls = "overline ng";
  let overTxt = "";
  if (isCorrect && stillNeedsVariantPass) {
    overCls = "overline warm";
    overTxt = q.is_listening && ansIdx > 0
      ? `首轮订正答对 · 正解 ${ansIdx} · 3 题后再过变式题即通关`
      : `首轮订正答对 · 3 题后再过变式题即通关`;
  } else if (isCorrect) {
    overCls = "overline ok";
    const hesTag = lastAnswerHesitant ? " · 略犹豫" : "";
    overTxt = q.is_listening && ansIdx > 0 ? `本题过关 · 正解 ${ansIdx} · ${streakTxt}` : `本题过关 · ${streakTxt}${hesTag}`;
  } else if (isUnsure) {
    overCls = "overline warm";
    overTxt = q.is_listening && ansIdx > 0
      ? `未过关（记 0/3） · 正解 ${ansIdx} · 3 题后乱序重考`
      : "未过关（记 0/3） · 3 题后乱序重考";
  } else {
    overCls = "overline ng";
    overTxt = q.is_listening && ansIdx > 0
      ? `答错未过（记 0/3） · 误选 ${pickedIdx || ""} · 正解 ${ansIdx} · 3 题后乱序重考`
      : `答错未过（记 0/3） · 误选「${pickedVal}」 · 3 题后乱序重考`;
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

  const fullyPassed = isCorrect && !stillNeedsVariantPass;
  const leftStampLabel = fullyPassed ? "← 稍后再考" : "← 3 题后重考";
  const leftStampTone = fullyPassed ? "" : " moss-tone";
  const rightStampLabel = fullyPassed ? "下一题 →" : (stillNeedsVariantPass ? "3 题后复考 →" : "未过 · 3 题后重考 →");
  const mainBtnLabel = fullyPassed ? "下一题 →" : (stillNeedsVariantPass ? "继续（3 题后复考） →" : "未过 · 3 题后重考 →");
  const _twinTitleMap = {
    "VAR-G05": "〜ついでに（顺便做另一件事）",
    "VAR-G10": "〜はずがない（按理绝不可能）",
    "VAR-G13": "〜そうだ（样态 · 眼看就要…）",
    "VAR-G20": "〜ことにしている（个人坚持习惯）",
    "VAR-G22": "〜てしかたがない（…得受不了）",
    "VAR-H01": "食べる／飲む → いただく（謙譲）",
    "VAR-H02": "一段动词 使役形（させる）",
  };
  const resPointTitle = _twinTitleMap[q.id] || (
    p.subject === "词汇" && q.answer && /^[\u3040-\u30ffー]+$/.test(q.answer) && p.point && !p.point.includes(q.answer) && !/[\u4e00-\u9fff]/.test(p.point)
      ? q.answer
      : (p.point || "")
  );

  box.innerHTML = `
    <div class="tutor-stamp right" id="tutor-st-right">${rightStampLabel}</div>
    <div class="tutor-stamp left${leftStampTone}" id="tutor-st-left">${leftStampLabel}</div>
    <div class="meta-bar">
      <span class="${overCls}">${escapeHtml(overTxt)}</span>
      <div class="quiet-actions">
        ${q.is_listening ? `<button class="text-btn" id="q-slow-btn" onclick="playQuizQuestionAudio(activeQuizObj, true, 0.85)">0.85x 慢听</button>` : ""}
        <button class="text-btn" onclick="playQuizQuestionAudio(activeQuizObj, true, 1.0)">原题</button>
        <button class="text-btn" id="ans-spd-btn" onclick="cycleExpSpeed()">${expSpeed}x</button>
      </div>
    </div>

    <div class="focal-space">
      ${(q.is_listening && renderDialogueHTML(q.full_ja, q.answer, q.zh_meaning)) || `<div class="result-ja">${annotateSentenceWithAnswer(q.full_ja, q.answer)}</div>
      ${q.zh_meaning ? `<p class="result-zh">${escapeHtml(q.zh_meaning)}</p>` : ""}`}
      <div class="result-divider"></div>
      ${resPointTitle ? `<div class="res-point-head"><span class="res-point-subj">${escapeHtml(p.subject || "")}</span><span>${escapeHtml(resPointTitle)}</span></div>` : ""}
      ${q.why_line ? `<div class="res-cue"><span class="cue-tag">要点</span><span class="cue-txt">${escapeHtml(q.why_line)}</span></div>` : ""}
      <div class="opt-breakdown${q.is_listening ? " is-listen" : ""}">${optRowsHTML}</div>
    </div>

    <div class="action-dock">
      <div class="dock-row">
        <button class="dock-replay-btn" id="dock-exp-btn" onclick="playMainClip(activeQuizObj.exp_audio, 'exp', true)">讲解</button>
        ${fullyPassed ? `<button class="ghost-btn" onclick="advanceNext(true)">← 再考</button>` : ""}
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

function getLookupContextId() {
  if (activeMode === "radio") {
    const segs = (DATA.radio && DATA.radio.segments) || [];
    const curSeg = segs[lastRenderedSegIdx];
    return curSeg ? `radio:${curSeg.title || lastRenderedSegIdx}` : "radio";
  }
  if (activeQuizObj && activeQuizObj.id) return activeQuizObj.id;
  if (curPointId) return curPointId;
  return activeMode || "tutor";
}

function recordTappedWord(surface) {
  if (!surface || PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return;
  const info = DATA.words[surface];
  if (!info || !info.zh) return;
  if (!Array.isArray(A.tappedWords)) A.tappedWords = [];
  if (!A.wordLookups || typeof A.wordLookups !== "object") A.wordLookups = {};

  const stamp = nowUnixSec();
  const ctxId = getLookupContextId();
  let changed = false;

  if (!A.tappedWords.includes(surface)) {
    A.tappedWords.push(surface);
    if (A.tappedWords.length > 80) A.tappedWords = A.tappedWords.slice(-80);
    changed = true;
  }

  // Record every word/phrase lookup to PM Twin's brain WITHOUT mutating active practice queue (vocabSess)!
  const prevLk = Array.isArray(A.wordLookups[surface]) ? A.wordLookups[surface] : [0, 0, ""];
  if (stamp - (prevLk[1] || 0) >= 15) {
    const nextCnt = (prevLk[0] || 0) + 1;
    A.wordLookups[surface] = [nextCnt, stamp, ctxId];
    const isoTs = new Date(stamp * 1000).toISOString();
    const ob = loadOutbox();
    ob.push([`LK:${surface}`, ctxId, surface, 1, isoTs]);
    saveOutbox(ob);
    changed = true;
  }

  if (changed) {
    refreshMarkedWordTokens();
    saveAdaptiveState();
    scheduleCloudPush(450);
  } else {
    refreshMarkedWordTokens();
  }
}

function buildSubwordBreakdown(surface) {
  if (!surface || surface.length < 4) return "";
  const subs = [];
  const seen = new Set();
  for (let i = 0; i < surface.length; ) {
    let hit = null;
    for (let k = 0; k < DICT_KEYS.length; k++) {
      const w = DICT_KEYS[k];
      if (w.length < 2 || w === surface || PARTICLE_FALLBACK[w] || TRIVIAL_TAP_WORDS.has(w)) continue;
      if (surface.startsWith(w, i) && DATA.words[w] && DATA.words[w].zh) {
        hit = w;
        break;
      }
    }
    if (hit) {
      if (!seen.has(hit)) {
        seen.add(hit);
        const shortZh = String(DATA.words[hit].zh).split(/[；，（(]/)[0].trim();
        if (shortZh) subs.push(`${hit}（${shortZh}）`);
      }
      i += hit.length;
    } else {
      i += 1;
    }
  }
  return subs.length >= 1 ? `词素：${subs.slice(0, 3).join("＋")}` : "";
}

function showInlineWordMeaning(surface, tokEl) {
  const info = DATA.words[surface];
  if (!info) return;

  const targetBoxId = activeMode === "radio"
    ? (radioReviewOpen ? "rv-inline-lex" : "radio-inline-lex")
    : "tutor-inline-lex";
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
  const mnLine = info.mnemonic ? `记音：${info.mnemonic}` : "";
  const subBreak = buildSubwordBreakdown(surface);
  const metaLine = [headDiff, mnLine, info.pos, info.tip, subBreak].filter(Boolean).join(" · ");
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

  const rvClipSilent = !rvClipPlayer || rvClipPlayer.paused;
  if (player.paused && radioPlayer.paused && rvClipSilent) {
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
    const targetBoxId = activeMode === "radio"
      ? (radioReviewOpen ? "rv-inline-lex" : "radio-inline-lex")
      : "tutor-inline-lex";
    const box = document.getElementById(targetBoxId);
    if (box && !box.classList.contains("empty") && (e.target.closest(".focal-space") || e.target.closest(".radio-center") || e.target.closest(".rv-focal"))) {
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
    if (vocabSubMode === "ga") {
      if (e.key === " ") { e.preventDefault(); onGACardTapOrAudio(); }
      else if (e.key === "Enter") { e.preventDefault(); if (gaPendingNext) advancePendingGA(); else onGACardTapOrAudio(); }
      else if (e.key === "1") { e.preventDefault(); commitGASpectrum(1); }
      else if (e.key === "2") { e.preventDefault(); commitGASpectrum(2); }
      else if (e.key === "3") { e.preventDefault(); commitGASpectrum(3); }
      else if (e.key === "4") { e.preventDefault(); commitGASpectrum(4); }
      else if (e.key.toLowerCase() === "z" || e.key === "Backspace") { e.preventDefault(); undoLastGA(); }
      return;
    }
    if (e.key === " ") { e.preventDefault(); onVocabCardTapOrReplay(); }
    else if (e.key === "ArrowRight" || e.key === "2" || e.key === "Enter") { e.preventDefault(); triggerVocabAction("right"); }
    else if (e.key === "ArrowLeft" || e.key === "1") { e.preventDefault(); triggerVocabAction("left"); }
    else if (e.key === "ArrowUp" || e.key === "3") { e.preventDefault(); triggerVocabAction("up"); }
    return;
  }

  if (activeMode === "radio") {
    if (radioReviewOpen) {
      if (e.key === "Escape") { e.preventDefault(); closeRadioReview(); }
      else if (e.key === " ") {
        e.preventDefault();
        const curItem = getReviewItemById(rvActiveItemId);
        if (!rvRevealed && rvMode !== "relearn") revealRadioReviewCard();
        else if (curItem) playReviewPodcastClip(curItem, 1.0, "clip_1");
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        if (rvMode === "relearn") finishRadioRelearnStep();
        else if (rvMode !== "done") handleRadioReviewPass();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (rvMode === "triage" || rvMode === "tail") handleRadioReviewRelearn();
      }
      return;
    }
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
    if (e.key === " ") { e.preventDefault(); playQuizQuestionAudio(activeQuizObj, true); }
    else if (e.key === "Enter" && !quizChoicesRevealed) { e.preventDefault(); revealQuizChoicesNow(); }
    else if (e.key === "1" && currentChoices[0]) { e.preventDefault(); if (!quizChoicesRevealed) { revealQuizChoicesNow(); return; } submitAnswer(currentChoices[0]); }
    else if (e.key === "2" && currentChoices[1]) { e.preventDefault(); if (!quizChoicesRevealed) { revealQuizChoicesNow(); return; } submitAnswer(currentChoices[1]); }
    else if (e.key === "3" && currentChoices[2]) { e.preventDefault(); if (!quizChoicesRevealed) { revealQuizChoicesNow(); return; } submitAnswer(currentChoices[2]); }
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

function positionMainThumbBar(immediate) {
  const wrap = document.getElementById("main-thumb-tabs");
  const bar = document.getElementById("main-thumb-bar");
  const btn = document.getElementById("btab-" + activeMode);
  if (!wrap || !bar || !btn || !wrap.offsetWidth) return;
  const w = Math.max(18, (btn.offsetWidth || 50) - 24);
  const left = (btn.offsetLeft || 0) + ((btn.offsetWidth || 50) - w) / 2;
  if (immediate) bar.style.transition = "none";
  bar.style.width = w + "px";
  bar.style.transform = `translateX(${left}px)`;
  if (immediate) { void bar.offsetWidth; bar.style.transition = ""; }
}
window.addEventListener("resize", () => positionMainThumbBar(true));

function switchMode(m, autoPlayRadio) {
  if (m !== "dash") prevNonDashMode = m;
  activeMode = m;
  clearActiveWordToken();
  JA_ASR.stop();
  if (m !== "tutor") stopQuizAudio();
  if (m !== "vocab") stopVocabAudioAndTimers();
  if (m !== "radio") stopRadioReviewAudio();
  if (m !== "body" && window.ZB && typeof window.ZB.stopPacer === "function") window.ZB.stopPacer(false);

  document.getElementById("app-shell").classList.toggle("wide-mode", m === "dash");
  document.getElementById("tab-tutor").classList.toggle("active", m === "tutor");
  document.getElementById("tab-radio").classList.toggle("active", m === "radio");
  document.getElementById("tab-vocab").classList.toggle("active", m === "vocab");
  const tabBody = document.getElementById("tab-body");
  if (tabBody) tabBody.classList.toggle("active", m === "body");
  ["tutor", "radio", "vocab", "body", "dash"].forEach(k => {
    const b = document.getElementById("btab-" + k);
    if (b) b.classList.toggle("active", m === k);
  });
  positionMainThumbBar(false);

  document.getElementById("tutor-view").classList.toggle("hidden", m !== "tutor");
  document.getElementById("radio-view").classList.toggle("hidden", m !== "radio");
  document.getElementById("vocab-view").classList.toggle("hidden", m !== "vocab");
  const bodyView = document.getElementById("body-view");
  if (bodyView) bodyView.classList.toggle("hidden", m !== "body");
  document.getElementById("dash-view").classList.toggle("hidden", m !== "dash");
  const gb = document.getElementById("green-board");
  if (gb) gb.classList.remove("hidden");

  renderGreenBoard();

  if (m === "radio") {
    ensureRadioReady();
    updateRadioReviewEntryBadge();
    if (!radioReviewOpen && autoPlayRadio && radioPlayer.paused) {
      toggleRadioPlay(true);
    } else {
      syncRadioUI();
    }
  } else if (m === "vocab") {
    enterVocabMode();
  } else if (m === "body") {
    if (window.ZB && typeof window.ZB.onEnter === "function") window.ZB.onEnter();
  } else if (m === "dash") {
    renderDashboard();
  } else {
    renderTutor();
  }
  syncRadioMiniBar();
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
      mnemonic: pre.mnemonic || w.mnemonic || "",
      zh_speak: typeof pre.zh_speak === "string" ? pre.zh_speak : cleanSpeakZh(pre.zh || w.zh || ""),
      hook_spoken: pre.hook_spoken || "",
      reveal_spoken: pre.reveal_spoken || "",
      front_audio: pre.front_audio || "",
      rev_audio: pre.rev_audio || "",
      full_audio: pre.full_audio || "",
      hook_audio: pre.hook_audio || "",
      clean_audio: pre.clean_audio || "",
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
    mnemonic: w.mnemonic || "",
    zh_speak: (!hasKanji || zhOpaque) ? cleanSpeakZh(zh) : "",
    hook_spoken: cleanSpeakZh(w.mnemonic || ""),
    reveal_spoken: cleanSpeakZh(w.mnemonic || zh || ""),
    front_audio: "",
    rev_audio: "",
    full_audio: "",
    hook_audio: "",
    clean_audio: "",
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
  const twinMap = (DATA && DATA.vocab_twins && typeof DATA.vocab_twins === "object") ? DATA.vocab_twins : {};
  const seen = new Set();
  const seenHead = new Set();
  const blockedTwins = new Set(); // Tinkham (1997) / Waring (1997) / Webb & Kagimoto (2011) anti-interference
  const refreshWords = [];
  const out = [];

  function tryAdd(surface, allowRefresh, ignoreTwins) {
    if (!surface || out.length >= maxN || seen.has(surface)) return false;
    if (PARTICLE_FALLBACK[surface] || TRIVIAL_TAP_WORDS.has(surface)) return false;
    const it = byKey[surface] || null;
    const eff = getEffectiveMastery((it && it.key) || surface, surface);
    if (eff.tier === "done" && !allowRefresh) return false;
    if (!ignoreTwins && !allowRefresh && blockedTwins.has(surface)) return false;
    const w = DATA.words[surface] || {};
    const head = w.head || surface;
    if (seenHead.has(head)) return false;
    const zh = (DATA.vocab_cards && DATA.vocab_cards[surface] && DATA.vocab_cards[surface].zh) || w.zh || (it && it.sub) || "";
    if (!zh) return false;
    seen.add(surface);
    seenHead.add(head);
    if (!allowRefresh && Array.isArray(twinMap[surface])) {
      twinMap[surface].forEach(tw => blockedTwins.add(tw));
    }
    if (allowRefresh) refreshWords.push(surface);
    out.push(surface);
    return true;
  }

  // 0) Post-3/3 Long-Lag Maintenance Refresher (Cepeda et al. 2008): reserve up to 2 slots for mastered words unseen >=10d!
  if (maxN >= 16) {
    const staleDone = [];
    vItems.forEach(it => {
      const eff = getEffectiveMastery(it.key, it.name);
      if (eff.tier === "done") {
        const ld = getEffectiveItemLastDate(it);
        const ds = ld ? daysSinceTag(ld) : 0;
        if (ds >= 10) staleDone.push({ name: it.name, ds });
      }
    });
    staleDone.sort((a, b) => b.ds - a.ds || a.name.localeCompare(b.name));
    staleDone.slice(0, 2).forEach(x => tryAdd(x.name, true, true));
  }

  // 1) Recently missed words (from tutor or Grok practice)
  const recentWeak = Array.isArray(DATA.recent_weak_words) ? DATA.recent_weak_words : [];
  recentWeak.slice(0, Math.min(8, maxN)).forEach(sw => tryAdd(sw, false, false));

  // 2) Cross-day due 2/3 & 1/3 reviews (lastDate !== TODAY_TAG) so words graduate to true green steadily,
  //    while always reserving room for fresh 0/3 words each day
  const dueWip2 = [];
  const dueWip1 = [];
  const todoPool = [];
  vItems.forEach(it => {
    const eff = getEffectiveMastery(it.key, it.name);
    if (eff.tier === "todo") {
      todoPool.push(it.name);
    } else if (eff.tier === "wip" && eff.lastDate !== TODAY_TAG) {
      if ((eff.streak || 0) >= 2) dueWip2.push(it.name);
      else dueWip1.push(it.name);
    }
  });
  const rot = (parseInt(TODAY_TAG.slice(-2), 10) || 0) * 5;
  const dueWip = [];
  for (let i = 0; i < dueWip2.length; i++) dueWip.push(dueWip2[(i + rot) % dueWip2.length]);
  for (let i = 0; i < dueWip1.length; i++) dueWip.push(dueWip1[(i + rot) % dueWip1.length]);

  const freshReserve = Math.min(Math.max(8, Math.floor(maxN * 0.42)), todoPool.length);
  const reviewTarget = Math.max(0, maxN - freshReserve);
  for (let i = 0; i < dueWip.length && out.length < reviewTarget; i++) {
    tryAdd(dueWip[i], false, false);
  }

  // 3) Remaining 0/3 待攻克 words (anti-interference enforced)
  todoPool.forEach(nm => tryAdd(nm, false, false));

  // 4) Any leftover due cross-day reviews (anti-interference enforced)
  dueWip.forEach(nm => tryAdd(nm, false, false));

  // 5) Any remaining wip words (anti-interference enforced, then relaxed fallback if pool tiny)
  vItems.forEach(it => {
    const eff = getEffectiveMastery(it.key, it.name);
    if (eff.tier === "wip") tryAdd(it.name, false, false);
  });
  if (out.length < maxN) {
    todoPool.forEach(nm => tryAdd(nm, false, true));
    dueWip.forEach(nm => tryAdd(nm, false, true));
    vItems.forEach(it => {
      const eff = getEffectiveMastery(it.key, it.name);
      if (eff.tier === "wip") tryAdd(it.name, false, true);
    });
  }

  out._refreshWords = refreshWords;
  return out;
}

function ensureVocabSession(forceNewBatch) {
  applyMasteryOverrides();
  if (!forceNewBatch && A.vocabSess && A.vocabSess.date === DATA.plan_date && Array.isArray(A.vocabSess.queue)) {
    const byKey = getVocabMasteryLookup();
    const refSet = new Set(Array.isArray(A.vocabSess.refreshWords) ? A.vocabSess.refreshWords : []);
    const filtered = A.vocabSess.queue.filter(sw => {
      if (refSet.has(sw)) return true;
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
  const refreshWords = Array.isArray(queue._refreshWords) ? queue._refreshWords.slice() : [];
  A.vocabSess = {
    date: DATA.plan_date,
    queue: queue.slice(),
    total: queue.length,
    cleared: 0,
    clearedWords: [],
    failedWords: [],
    refreshWords: refreshWords,
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
  }, 16000);

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
  const revealTxt = String(card.reveal_spoken || card.hook_spoken || (typeof card.zh_speak === "string" ? card.zh_speak : (card.zh || ""))).trim();
  const phraseJa = (card.chunk_ja && card.chunk_ja !== card.word) ? card.chunk_ja : "";
  const speakPhraseStep = () => {
    if (vcToken !== myToken) return;
    if (!phraseJa) {
      if (onDone) onDone();
      return;
    }
    vcTimer = setTimeout(() => {
      if (vcToken !== myToken) return;
      speakUtteranceLang(phraseJa, "ja-JP", 0.98, () => {
        if (vcToken === myToken && onDone) onDone();
      });
    }, 180);
  };
  const speakRevealStep = () => {
    if (vcToken !== myToken) return;
    if (!revealTxt) {
      speakPhraseStep();
      return;
    }
    speakUtteranceLang(revealTxt, "zh-CN", 1.04, speakPhraseStep);
  };
  if (!includeJa) {
    speakRevealStep();
    return;
  }
  if (card.word_audio) {
    playUrlOnWordPlayer(
      card.word_audio,
      myToken,
      () => {
        if (vcToken !== myToken) return;
        vcTimer = setTimeout(speakRevealStep, 140);
      },
      () => {
        speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, speakRevealStep);
      }
    );
  } else {
    speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, speakRevealStep);
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
    if (c.hook_audio) warmAudio(c.hook_audio);
    if (c.clean_audio) warmAudio(c.clean_audio);
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

let vocabSubMode = "vocab";
let gaRevealed = false;
let gaPendingNext = false;
let gaPendingCode = 0;
let gaAnimating = false;
let gaHoverCode = 0;
let lastGACloudPushMs = 0;

function updateVocabSubNav() {
  const navEl = document.getElementById("vc-subnav");
  if (!navEl) return;
  const m = computeDaily120Metrics();
  const ga = m.ga;
  if (!ga || !ga.showSubNav) {
    navEl.style.display = "none";
    if (vocabSubMode === "ga") vocabSubMode = "vocab";
    return;
  }
  navEl.style.display = "flex";
  const bV = document.getElementById("vsub-vocab");
  const bG = document.getElementById("vsub-ga");
  if (bV) bV.classList.toggle("active", vocabSubMode === "vocab");
  if (bG) bG.classList.toggle("active", vocabSubMode === "ga");
  const cV = document.getElementById("vsub-vocab-cnt");
  if (cV) cV.textContent = m.flashDone ? "✓" : "";
  const cG = document.getElementById("vsub-ga-cnt");
  if (cG) cG.textContent = ga.remaining === 0 ? "✓" : (ga.gaDone ? "✓" : `${ga.gaSeen}/${ga.gaTarget}`);
  const metaEl = document.getElementById("vc-submeta");
  if (metaEl) metaEl.textContent = vocabSubMode === "ga" ? `${ga.audited}/${ga.total}` : "";
}

function switchVocabSubMode(sub) {
  const target = (sub === "ga" && GA_ITEMS_LIST.length > 0) ? "ga" : "vocab";
  vocabSubMode = target;
  stopVocabAudioAndTimers();
  updateVocabSubNav();
  if (vocabSubMode === "ga") {
    enterGrammarAuditSubMode();
  } else {
    ensureVocabSession(false);
    vcRevealed = false;
    vcPendingLeft = false;
    vcAnimating = false;
    dealCurrentVocabCard(true);
  }
}

function openGrammarAuditFromAnywhere() {
  vocabSubMode = "ga";
  if (activeMode !== "vocab") {
    switchMode("vocab");
  } else {
    switchVocabSubMode("ga");
  }
}

function enterVocabMode() {
  const m = computeDaily120Metrics();
  if (m.ga && m.ga.requiredToday && m.flashDone && !m.ga.gaDone) {
    vocabSubMode = "ga";
  } else if (!m.ga || !m.ga.showSubNav) {
    vocabSubMode = "vocab";
  }
  updateVocabSubNav();
  if (vocabSubMode === "ga") {
    enterGrammarAuditSubMode();
    return;
  }
  ensureVocabSession(false);
  vcRevealed = false;
  vcPendingLeft = false;
  vcAnimating = false;
  dealCurrentVocabCard(true);
}

function startNextVocabBatch() {
  stopVocabAudioAndTimers();
  vocabSubMode = "vocab";
  ensureVocabSession(true);
  vcRevealed = false;
  vcPendingLeft = false;
  vcAnimating = false;
  updateVocabSubNav();
  dealCurrentVocabCard(true);
}

function onRemoteVocabSync() {
  updateVocabSubNav();
  if (activeMode !== "vocab") return;
  if (vocabSubMode === "ga") {
    if (!gaAnimating && !gaPendingNext) {
      ensureGASession(false);
      renderGrammarAuditStage();
    }
    return;
  }
  if (vcAnimating || vcPendingLeft) return;
  const sess = ensureVocabSession(false);
  if (!sess.queue.length) renderVocabStage();
}

function isEarFirstGradCard(card) {
  if (!card || card.mode !== "kanji_read") return false;
  const eff = getEffectiveMastery(card.key, card.word);
  if ((eff.streak || 0) !== 2) return false;
  const sess = A.vocabSess;
  if (sess && Array.isArray(sess.failedWords) && sess.failedWords.includes(card.word)) return false;
  return !!(card.word_audio || card.front_audio || card.full_audio);
}

function isKanaRecallGradCard(card) {
  // Mondria & Wiersma (2004) / Webb (2005, 2009): 2/3 pure-kana final pass tests L1->L2 productive recall!
  if (!card || card.mode !== "kana_meaning") return false;
  const eff = getEffectiveMastery(card.key, card.word);
  if ((eff.streak || 0) !== 2) return false;
  const sess = A.vocabSess;
  if (sess && Array.isArray(sess.failedWords) && sess.failedWords.includes(card.word)) return false;
  return !!String(card.zh || "").trim();
}

function shouldFadeVocabMnemonic(card) {
  // Wang & Thomas (1995) / Crutcher (1990): fade spoken keyword crutch on 1/3 & 2/3 smooth passes
  if (!card || vcPendingLeft) return false;
  const sess = A.vocabSess;
  if (sess && Array.isArray(sess.failedWords) && sess.failedWords.includes(card.word)) return false;
  const eff = getEffectiveMastery(card.key, card.word);
  return (eff.streak || 0) >= 1;
}

function dealCurrentVocabCard(autoStartAudio) {
  JA_ASR.stop();
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
  const earFirst = isEarFirstGradCard(card);
  const kanaRecall = isKanaRecallGradCard(card);

  // Pyc & Rawson (2009) + Tullis & Benjamin (2011): calm 4.2-4.5s fallback window (tap card anytime for instant 0ms reveal!)
  if (earFirst) {
    // 2/3 Final Auditory Graduation (Tamaoka et al. 2012): play Japanese ear-first with Kanji veiled!
    const earUrl = card.word_audio || card.front_audio || card.full_audio;
    const afterEar = () => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      vcTimer = setTimeout(() => {
        if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
        revealVocabCard(true);
      }, 4200);
    };
    if (earUrl) {
      playUrlOnWordPlayer(
        earUrl,
        myToken,
        afterEar,
        () => speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, afterEar)
      );
    } else {
      speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, afterEar);
    }
  } else if (kanaRecall) {
    // 2/3 Pure Kana Productive Recall (L1->L2): silent Chinese cue on front, calm 4.5s fallback (tap anytime!)
    vcTimer = setTimeout(() => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      revealVocabCard(true);
    }, 4500);
  } else if (card.mode === "kanji_read") {
    // Silent Kanji micro-chunk front: calm 4.5s fallback before auto-reveal (tap reveals instantly)
    vcTimer = setTimeout(() => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      revealVocabCard(true);
    }, 4500);
  } else {
    // Kana / spoken word: play Japanese first, calm 4.2s fallback for meaning retrieval (tap reveals instantly)
    const frontUrl = card.front_audio || card.word_audio;
    const afterFront = () => {
      if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
      vcTimer = setTimeout(() => {
        if (activeMode !== "vocab" || vcToken !== myToken || vcRevealed) return;
        revealVocabCard(true);
      }, 4200);
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
  const kanaRecall = isKanaRecallGradCard(card);
  const fadeMn = !forceFullBilingual && shouldFadeVocabMnemonic(card);
  stopVocabAudioAndTimers();
  vcRevealed = true;

  const chunkEl = document.getElementById("vc-chunk-box");
  if (chunkEl) chunkEl.classList.remove("ear-veil");
  const kFrontEl = document.getElementById("vc-kana-front");
  if (kFrontEl) kFrontEl.classList.add("revealed");
  const revEl = document.getElementById("vc-reveal-box");
  if (revEl) revEl.classList.add("shown");
  const cueEl = document.getElementById("vc-cue-line");
  if (cueEl) {
    if (vcPendingLeft) {
      cueEl.textContent = "顺口念一遍再滑";
      cueEl.className = "vc-cue ng";
    } else {
      cueEl.className = "vc-cue quiet-hide";
    }
  }

  if (!playAudioNow) return;
  const myToken = ++vcToken;
  const needFull = !!forceFullBilingual || card.mode === "kanji_read" || kanaRecall;
  // Wang & Thomas (1995): On 1/3 & 2/3 smooth passes, play crisp native Japanese word+phrase; on 0/3 play mnemonic early
  const targetUrl = (fadeMn && card.clean_audio)
    ? card.clean_audio
    : (needFull ? (card.full_audio || card.rev_audio) : card.rev_audio);

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
  const card = getVocabCardSpec(sess.queue[0]);
  const earFirst = isEarFirstGradCard(card);
  const kanaRecall = isKanaRecallGradCard(card);
  if (!vcRevealed) {
    // Before reveal: replay ONLY the front audio on listening/kana fronts (don't spoil the answer!)
    if (earFirst || (card.mode !== "kanji_read" && !kanaRecall)) {
      stopVocabAudioAndTimers();
      const myToken = ++vcToken;
      const frontUrl = earFirst ? (card.word_audio || card.front_audio || card.full_audio) : (card.front_audio || card.word_audio);
      if (frontUrl) {
        playUrlOnWordPlayer(frontUrl, myToken, null, () => speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, null));
      } else {
        speakUtteranceLang(card.kana || card.word, "ja-JP", 0.98, null);
      }
      return;
    }
    revealVocabCard(true, true);
    return;
  }
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

function playVocabHookAudio(ev) {
  if (ev) ev.stopPropagation();
  replayVocabAudio(ev);
}

function onVocabCardTapOrReplay() {
  if (vcAnimating) return;
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  if (!vcRevealed) {
    revealVocabCard(true, cardNeedsFullOnTap(sess.queue[0]));
  }
  // Once revealed, audio has already spoken — do NOT redundantly restart speech on card/mnemonic tap!
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
  JA_ASR.stop();
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
    if (Array.isArray(sess.refreshWords)) sess.refreshWords = sess.refreshWords.filter(w => w !== word);

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
      const auxEl = document.getElementById("vc-aux-row");
      if (auxEl) auxEl.style.visibility = "hidden";
      const dockEl = document.getElementById("vc-dock-row");
      if (dockEl) {
        dockEl.innerHTML = `
          <button class="vc-btn mid" onclick="replayVocabAudio(event)">再听一遍</button>
          <button class="vc-btn ok" onclick="acknowledgePendingLeft('left')">听清了，稍后再考</button>
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
    if (Array.isArray(sess.refreshWords)) sess.refreshWords = sess.refreshWords.filter(w => w !== word);
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
  const isRefreshWord = Array.isArray(sess.refreshWords) && sess.refreshWords.includes(word);
  const hadFailToday = Array.isArray(sess.failedWords) && sess.failedWords.includes(word);
  if (isRefreshWord && !hadFailToday) {
    setMasteryTier(card.key, "done", stamp);
    setMasteryTier(card.word, "done", stamp);
    sess.refreshWords = sess.refreshWords.filter(w => w !== word);
  } else {
    applyMasteryAction(card.key, card.word, hadFailToday ? "recover" : "pass", stamp);
  }
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
  let tracking = false;
  let hasDragged = false;
  let activePid = null;
  let sx = 0, sy = 0, st = 0;
  const DRAG_DEADZONE = 12;

  cardEl.addEventListener("pointerdown", e => {
    if (vcAnimating) return;
    if (typeof e.button === "number" && e.button !== 0) return;
    if (e.target && e.target.closest && e.target.closest("button")) return;
    tracking = true;
    hasDragged = false;
    activePid = e.pointerId;
    sx = fpX(e);
    sy = fpY(e);
    st = performance.now();
    cardEl.classList.remove("settling");
    try { cardEl.setPointerCapture(e.pointerId); } catch (err) {}
  });

  cardEl.addEventListener("pointermove", e => {
    if (!tracking || e.pointerId !== activePid) return;
    const dx = fpX(e) - sx;
    const dy = fpY(e) - sy;
    if (!hasDragged) {
      if (Math.hypot(dx, dy) < DRAG_DEADZONE) return;
      hasDragged = true;
      cardEl.classList.add("dragging");
    }
    cardEl.style.transform = `translate3d(${dx.toFixed(1)}px, ${(dy * 0.42).toFixed(1)}px, 0) rotate(${(dx * 0.036).toFixed(2)}deg)`;

    const stR = document.getElementById("vc-st-right");
    const stL = document.getElementById("vc-st-left");
    const stU = document.getElementById("vc-st-up");
    if (!vcPendingLeft && dy < -26 && Math.abs(dy) > Math.abs(dx) * 1.25) {
      if (stU) stU.style.opacity = String(Math.min(1, (-dy - 22) / 48));
      if (stR) stR.style.opacity = "0";
      if (stL) stL.style.opacity = "0";
    } else if (dx > 18) {
      if (stR) stR.style.opacity = String(Math.min(1, (dx - 16) / 50));
      if (stL) stL.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    } else if (dx < -18) {
      if (stL) stL.style.opacity = String(Math.min(1, (-dx - 16) / 50));
      if (stR) stR.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    } else {
      if (stR) stR.style.opacity = "0";
      if (stL) stL.style.opacity = "0";
      if (stU) stU.style.opacity = "0";
    }
  });

  function finishGesture(e, isCancel) {
    if (!tracking || e.pointerId !== activePid) return;
    tracking = false;
    activePid = null;
    try { cardEl.releasePointerCapture(e.pointerId); } catch (err) {}
    if (isCancel) {
      if (hasDragged) resetVocabCardTransform();
      hasDragged = false;
      return;
    }
    const dx = fpX(e) - sx;
    const dy = fpY(e) - sy;
    const dt = Math.max(1, performance.now() - st);
    const vx = dx / dt;
    const vy = dy / dt;

    if (!hasDragged || (Math.hypot(dx, dy) < 20 && dt < 650)) {
      if (hasDragged) resetVocabCardTransform();
      hasDragged = false;
      onVocabCardTapOrReplay();
      return;
    }
    hasDragged = false;

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
  updateVocabSubNav();
  const box = document.getElementById("vocab-stage-box");
  if (!box) return;
  if (vocabSubMode === "ga") {
    renderGrammarAuditStage();
    return;
  }
  const sess = ensureVocabSession(false);

  if (!sess.queue.length) {
    const remPool = countRemainingVocabPool();
    const m = computeDaily120Metrics();
    const needGA = m.ga && m.ga.requiredToday && !m.ga.gaDone && m.ga.remaining > 0;
    box.innerHTML = `
      <div class="meta-bar">
        <span class="overline ok">${sess.total > 0 ? (needGA ? `本组 ${sess.total} 词已清零 · 还差今日语法盘点` : `本组 ${sess.total} 词已清零 · 圆印已收笔`) : "核心生词已全部满 3/3"}</span>
      </div>
      <div class="focal-space">
        <h2 class="point-heading">${sess.total > 0 ? "今晚这组词全部过关" : "核心生词已全部掌握"}</h2>
        <p class="logic-line">${needGA
          ? `记词已完成，还有 ${Math.max(1, m.ga.gaTarget - m.ga.gaSeen)} 条语法待盘点。`
          : (remPool > 0
            ? `今日记词已点亮，当前预计 ${m.projScore} 分。总表里还有 ${remPool} 个词未满跨 3 天的 3/3，明天接着巩固就会真正变绿。`
            : `所有核心生词都已跨 3 天答对满 3/3，稳稳锁进长期记忆。`)}</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          <button class="ghost-btn" onclick="${needGA && remPool > 0 ? "startNextVocabBatch()" : "switchMode('dash')"}">${needGA && remPool > 0 ? "再练一组词" : "查看总表"}</button>
          ${needGA
            ? `<button class="sumi-btn" onclick="switchVocabSubMode('ga')">去语法盘点 (${m.ga.gaSeen}/${m.ga.gaTarget}) →</button>`
            : (remPool > 0
              ? `<button class="sumi-btn" onclick="startNextVocabBatch()">再练一组</button>`
              : `<button class="sumi-btn" onclick="switchMode('tutor')">回做题</button>`)}
        </div>
      </div>
    `;
    return;
  }

  const word = sess.queue[0];
  const card = getVocabCardSpec(word);
  const eff = getEffectiveMastery(card.key, card.word);
  const isRequeued = Array.isArray(sess.failedWords) && sess.failedWords.includes(word);
  const isRefresh = Array.isArray(sess.refreshWords) && sess.refreshWords.includes(word);
  const posNum = Math.min(Math.max(1, sess.total), (sess.cleared || 0) + 1);
  const leftLabel = isRequeued
    ? `回炉 · 余 ${sess.queue.length}`
    : (isRefresh
      ? `保鲜 · ${posNum} / ${sess.total}`
      : `${posNum} / ${sess.total}${card.source ? " · " + card.source : ""}`);
  const isKanjiCard = card.mode === "kanji_read";
  const earFirst = isEarFirstGradCard(card);
  const kanaRecall = isKanaRecallGradCard(card);
  const hasTargetKanji = /[\u4e00-\u9faf\u3400-\u4dbf]/.test(card.target || card.word);
  const kanaHtml = (hasTargetKanji && card.kana)
    ? renderTrapKanaHTML(card.target || card.word, card.kana, card.trap_hl, card.trap_tag)
    : "";
  const quietZh = isKanjiCard && !card.zh_opaque;
  const initCue = earFirst
    ? "盲听认词"
    : (kanaRecall
      ? "看意想音"
      : (isKanjiCard ? "默念读音" : "听音想意"));
  const rightStampTxt = earFirst ? "听懂毕业" : (kanaRecall ? "想起毕业" : (isKanjiCard ? "读准了" : "记住"));
  const leftStampTxt = isKanjiCard ? "读音待练" : "没记住";
  const leftBtnTxt = isKanjiCard ? "读音不准" : "没记住";
  const rightBtnTxt = earFirst ? "听懂毕业" : (kanaRecall ? "想起毕业" : (isKanjiCard ? "读准了" : "记住"));
  const kanaFrontTxt = kanaRecall ? (cleanSpeakZh(card.zh) || card.zh) : "";
  const showVocabMic = JA_ASR.supported();

  box.innerHTML = `
    <div class="meta-bar">
      <span class="overline${isRequeued ? " warm" : ""}">${escapeHtml(leftLabel)}</span>
      <div class="vc-meta-right">
        <span id="vc-meta-dots" style="display:inline-flex;align-items:center;gap:6px;">${renderStreakDotsHTML(eff.streak)}</span>
      </div>
    </div>

    <div class="vc-deck-area">
      <div class="vc-card" id="vc-card">
        <div class="vc-stamp right" id="vc-st-right">${rightStampTxt}</div>
        <div class="vc-stamp left" id="vc-st-left">${leftStampTxt}</div>
        <div class="vc-stamp up" id="vc-st-up">太熟封存</div>

        <div class="vc-cue${vcRevealed && !vcPendingLeft ? " quiet-hide" : ""}" id="vc-cue-line">${initCue}</div>
        ${kanaRecall ? `<div class="vc-kana-front${vcRevealed ? " revealed" : ""}" id="vc-kana-front">${escapeHtml(kanaFrontTxt)}</div>` : ""}
        <div class="vc-chunk${(earFirst || kanaRecall) && !vcRevealed ? " ear-veil" : ""}" id="vc-chunk-box">${renderChunkHighlightHTML(card.chunk_ja, card.target)}</div>

        <div class="vc-reveal${vcRevealed ? " shown" : ""}" id="vc-reveal-box">
          ${kanaHtml ? `<div class="vc-kana">${kanaHtml}</div>` : ""}
          <div class="vc-zh${quietZh ? " quiet" : ""}">${escapeHtml(card.zh)}</div>
          ${card.mnemonic ? `<div class="vc-hook"><span class="vc-hook-tag">记音</span>${escapeHtml(card.mnemonic)}</div>` : ""}
          ${card.twin ? `<div class="vc-twin${card.mnemonic ? " sub" : ""}">${escapeHtml(card.twin)}</div>` : ""}
        </div>
        <div class="mic-feedback" id="vc-mic-feedback"></div>
      </div>
    </div>

    <div class="vc-aux-row" id="vc-aux-row">
      <button type="button" class="vc-aux-btn seal" id="vc-seal-btn" onclick="triggerVocabAction('up')">太熟</button>
      <div class="vc-aux-right">
        ${showVocabMic ? `<button type="button" class="vc-aux-btn mic-btn" id="vc-mic-btn" onclick="toggleVocabMicCheck(event)">试读</button>` : ""}
        <button type="button" class="vc-aux-btn replay" id="vc-replay-btn" onclick="replayVocabAudio(event)">重听</button>
      </div>
    </div>

    <div class="vc-dock" id="vc-dock-row">
      <button class="vc-btn ng" onclick="triggerVocabAction('left')">${leftBtnTxt}</button>
      <button class="vc-btn ok" onclick="triggerVocabAction('right')">${rightBtnTxt}</button>
    </div>
  `;

  bindVocabCardGestures(document.getElementById("vc-card"));
}

function toggleVocabMicCheck(ev) {
  if (ev) ev.stopPropagation();
  const sess = A.vocabSess;
  if (!sess || !sess.queue.length) return;
  const word = sess.queue[0];
  const card = getVocabCardSpec(word);
  const btn = document.getElementById("vc-mic-btn");
  const fb = document.getElementById("vc-mic-feedback");
  if (JA_ASR.isActive("vc_word")) {
    JA_ASR.stop();
    if (btn) { btn.classList.remove("listening"); btn.innerHTML = "试读"; }
    if (fb && fb.textContent === "请读出这个日语词…") fb.textContent = "";
    return;
  }
  stopVocabAudioAndTimers();
  if (btn) { btn.classList.add("listening"); btn.innerHTML = `<span class="mic-dot"></span>聆听中`; }
  if (fb) { fb.className = "mic-feedback"; fb.textContent = "请读出这个日语词…"; }
  JA_ASR.start("vc_word", {
    onInterim: (txt) => {
      const f = document.getElementById("vc-mic-feedback");
      if (f) { f.className = "mic-feedback"; f.textContent = `听到：${txt}`; }
    },
    onFinal: (alts) => {
      const b = document.getElementById("vc-mic-btn");
      const f = document.getElementById("vc-mic-feedback");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
      const res = JA_ASR.analyzePronunciation(alts, card.target || card.word, card.kana, card.chunk_ja);
      if (!vcRevealed) revealVocabCard(false, false);
      if (f) {
        f.className = "mic-feedback " + (res.ok ? "ok" : "ng");
        f.textContent = res.ok
          ? `✓ 读准了 · ${res.heard}`
          : `听到「${res.heard}」· ${res.verdict}`;
      }
      pushSpokenRecord(`W-${card.word}`, card.key || card.word, res.ok ? "试读:准确" : `试读:${res.verdict.slice(0, 18)}`, res.ok);
    },
    onError: (msg) => {
      const b = document.getElementById("vc-mic-btn");
      const f = document.getElementById("vc-mic-feedback");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
      if (f) { f.className = "mic-feedback ng"; f.textContent = msg; }
    },
    onEnd: () => {
      const b = document.getElementById("vc-mic-btn");
      if (b) { b.classList.remove("listening"); b.innerHTML = "试读"; }
    }
  });
}

// ================= ATOMIC 1-BY-1 GRAMMAR SELF-AUDIT (ZEN OPEN-CANVAS) =================
function expandGAQueue(rawQueue) {
  const out = [];
  const seen = new Set();
  (Array.isArray(rawQueue) ? rawQueue : []).forEach(gid => {
    const kids = GA_SPLIT_MAP[gid];
    const list = (Array.isArray(kids) && kids.length) ? kids : [gid];
    list.forEach(id => {
      if (id && GA_BY_GID[id] && !seen.has(id)) {
        seen.add(id);
        out.push(id);
      }
    });
  });
  return out;
}

function curateGABatch(limitCnt) {
  const maxN = Math.max(1, Number(limitCnt || (DATA.grammar_audit && DATA.grammar_audit.daily_target) || 39));
  const out = [];
  for (let i = 0; i < GA_ITEMS_LIST.length && out.length < maxN; i++) {
    const it = GA_ITEMS_LIST[i];
    if (!it || !it.gid) continue;
    if (getEffectiveGA(it.gid).code === 0) out.push(it.gid);
  }
  return out;
}

function ensureGASession(forceNewBatch) {
  const dailyTgt = Number((DATA.grammar_audit && DATA.grammar_audit.daily_target) || 39);
  if (!forceNewBatch && A.gaSess && A.gaSess.date === DATA.plan_date && Array.isArray(A.gaSess.queue)) {
    const rawLen = A.gaSess.queue.length;
    const expanded = expandGAQueue(A.gaSess.queue);
    const expandedAdded = Math.max(0, expanded.length - rawLen);
    if (expandedAdded > 0) {
      A.gaSess.total = Math.max((A.gaSess.total || 0) + expandedAdded, (A.gaSess.cleared || 0) + expanded.length);
    }
    const filtered = expanded.filter(gid => getEffectiveGA(gid).code === 0);
    if (filtered.length !== expanded.length || expanded.length !== rawLen) {
      const doneDiff = Math.max(0, expanded.length - filtered.length);
      A.gaSess.queue = filtered;
      A.gaSess.cleared = Math.min(A.gaSess.total || 0, (A.gaSess.cleared || 0) + doneDiff);
      saveAdaptiveState();
    }
    if (A.gaSess.queue.length === 0 && (A.gaSess.total || 0) > 0) {
      A.gaSess.done = true;
    }
    if (!Array.isArray(A.gaSess.undoStack)) A.gaSess.undoStack = [];
    return A.gaSess;
  }
  const queue = curateGABatch(dailyTgt);
  A.gaSess = {
    date: DATA.plan_date,
    queue: queue,
    total: queue.length,
    cleared: 0,
    undoStack: [],
    done: queue.length === 0,
    updatedAt: nowUnixSec()
  };
  saveAdaptiveState();
  return A.gaSess;
}

function recordGAProgress(seenCnt, totalCnt, markDoneNow) {
  const stamp = nowUnixSec();
  const cur = Array.isArray(A.gaProg) ? A.gaProg : [0, 0, 0, 0];
  const nextSeen = Math.max(Math.floor(cur[0] || 0), Math.max(0, Math.floor(seenCnt || 0)));
  const nextTgt = Math.max(nextSeen, Math.floor(totalCnt || 0) || Math.floor(cur[1] || 0));
  const nextDone = markDoneNow ? Math.max(Math.floor(cur[2] || 0), stamp) : Math.floor(cur[2] || 0);
  const changed = mergeGaProgTuple(A, [nextSeen, nextTgt, nextDone, stamp]);
  if (changed) {
    saveAdaptiveState();
    renderGreenBoard();
    updateVocabSubNav();
    if (markDoneNow || Date.now() - lastGACloudPushMs > 8000) {
      lastGACloudPushMs = Date.now();
      scheduleCloudPush(markDoneNow ? 80 : 300);
    }
  }
}

function gaCodeToMasteryTier(code) {
  if (code === 1 || code === 2) return `todo:${TODAY_TAG}`;
  if (code === 3) return "wip2:20261114";
  return "done";
}

function applyGASpectrumVerdict(gid, code, stampSec) {
  const item = GA_BY_GID[gid];
  const spec = GA_SPECTRUM[code];
  if (!item || !spec) return null;
  const stamp = Math.max(TRUE_GREEN_EPOCH, Math.floor(stampSec || nowUnixSec()));
  const prevGa = getEffectiveGA(gid);
  const msTargetKey = item.parent_name || item.name;
  const prevMs = (A.masteryOverrides && A.masteryOverrides[msTargetKey]) ? String(A.masteryOverrides[msTargetKey]) : "";
  const prevMsTs = (A.masteryOverrideTs && A.masteryOverrideTs[msTargetKey]) ? Number(A.masteryOverrideTs[msTargetKey]) : 0;
  const hkKey = item.henkei_key || "";
  const prevHkMs = (hkKey && A.masteryOverrides && A.masteryOverrides[hkKey]) ? String(A.masteryOverrides[hkKey]) : "";
  const prevHkMsTs = (hkKey && A.masteryOverrideTs && A.masteryOverrideTs[hkKey]) ? Number(A.masteryOverrideTs[hkKey]) : 0;

  if (!A.gaMap || typeof A.gaMap !== "object") A.gaMap = {};
  A.gaMap[gid] = [code, stamp, TODAY_TAG];

  const okBit = (code === 1 || code === 2) ? 0 : 1;
  if (item.parent_gid && item.parent_name) {
    const agg = getEffectiveParentGA(item.parent_gid);
    const aggCode = (agg.code >= 1 && agg.code <= 4) ? agg.code : code;
    setMasteryTier(item.parent_name, gaCodeToMasteryTier(aggCode), stamp);
    if (hkKey) setMasteryTier(hkKey, gaCodeToMasteryTier(code), stamp);
  } else {
    setMasteryTier(item.name, gaCodeToMasteryTier(code), stamp);
  }
  applyMasteryOverrides();

  const rec = {
    id: `GA-${gid}`,
    point: item.name,
    choice: spec.choice,
    correct: okBit ? "true" : "false",
    ask_again: "false",
    ts: new Date(stamp * 1000).toISOString()
  };
  if (!Array.isArray(A.recentRecords)) A.recentRecords = [];
  A.recentRecords.push(rec);
  if (A.recentRecords.length > 25) A.recentRecords = A.recentRecords.slice(-25);
  const ob = loadOutbox();
  ob.push([rec.id, rec.point, rec.choice, okBit, rec.ts]);
  saveOutbox(ob);

  saveAdaptiveState();
  return { gid, prevGa, msTargetKey, prevMs, prevMsTs, hkKey, prevHkMs, prevHkMsTs, newTs: stamp, recTs: rec.ts };
}

function enterGrammarAuditSubMode() {
  ensureGASession(false);
  gaRevealed = false;
  gaPendingNext = false;
  gaPendingCode = 0;
  gaAnimating = false;
  gaHoverCode = 0;
  renderGrammarAuditStage();
}

function startNextGABatch() {
  stopVocabAudioAndTimers();
  ensureGASession(true);
  gaRevealed = false;
  gaPendingNext = false;
  gaPendingCode = 0;
  gaAnimating = false;
  gaHoverCode = 0;
  renderGrammarAuditStage();
}

function stripGrammarSpoilerTitle(raw) {
  let s = String(raw || "").trim();
  s = s.replace(/[（(](?![ぁ-んァ-ヶー]+[）)])[^）)]*[）)]/g, "").trim();
  if (s === "そうだ") s = "〜そうだ";
  return s || String(raw || "").trim();
}

function getGAFrontName(item) {
  if (!item) return "";
  return item.front_name || stripGrammarSpoilerTitle(item.name);
}

function syncGARevealedCardHeader(item, markedCode) {
  if (!item) return;
  const eyeEl = document.getElementById("ga-eyebrow");
  if (eyeEl) {
    const sp = markedCode ? GA_SPECTRUM[markedCode] : null;
    eyeEl.textContent = sp ? `${item.family} · ${sp.label}` : item.family;
    eyeEl.className = "ga-meta-fam" + (sp ? " " + sp.cls : "");
  }
  const headEl = document.getElementById("ga-head");
  if (headEl) headEl.textContent = item.name;
}

function playGAAudio(ev) {
  if (ev) ev.stopPropagation();
  const sess = A.gaSess;
  if (!sess || !sess.queue.length) return;
  const item = GA_BY_GID[sess.queue[0]];
  if (!item) return;
  stopVocabAudioAndTimers();
  if (item.audio) {
    playDirectUrl(item.audio);
  } else if (item.ex_ja) {
    speakJapaneseFallback(item.ex_ja);
  } else {
    speakJapaneseFallback(getGAFrontName(item));
  }
}

function onGACardTapOrAudio() {
  if (gaAnimating) return;
  const sess = A.gaSess;
  if (!sess || !sess.queue.length) return;
  if (gaPendingNext) {
    advancePendingGA();
    return;
  }
  if (!gaRevealed) {
    gaRevealed = true;
    const item = GA_BY_GID[sess.queue[0]];
    syncGARevealedCardHeader(item, 0);
    const revEl = document.getElementById("ga-reveal-box");
    if (revEl) revEl.classList.add("shown");
    const audBtn = document.getElementById("ga-aud-btn");
    if (audBtn) audBtn.style.display = "";
  } else {
    playGAAudio();
  }
}

function setGASpectrumPreview(code) {
  gaHoverCode = code || 0;
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById("ga-stop-" + i);
    if (el) el.classList.toggle("active", i === gaHoverCode);
  }
}

function advancePendingGA() {
  if (!gaPendingNext || gaAnimating) return;
  const sess = A.gaSess;
  if (!sess || !sess.queue.length) return;
  const cardEl = document.getElementById("ga-card");
  gaAnimating = true;
  stopVocabAudioAndTimers();
  if (cardEl) cardEl.classList.add("ga-spec-card-fade");
  setTimeout(() => {
    gaAnimating = false;
    gaPendingNext = false;
    gaPendingCode = 0;
    gaRevealed = false;
    gaHoverCode = 0;
    sess.queue.shift();
    sess.cleared = Math.min(sess.total, (sess.cleared || 0) + 1);
    sess.done = sess.queue.length === 0;
    sess.updatedAt = nowUnixSec();
    const st = computeGrammarAuditStats();
    const dailyTgt = Number((DATA.grammar_audit && DATA.grammar_audit.daily_target) || 39);
    const doneDay = sess.done || st.remaining === 0 || st.todayAudited >= dailyTgt;
    saveAdaptiveState();
    recordGAProgress(Math.max(sess.cleared, st.todayAudited), Math.max(sess.total, Math.min(dailyTgt, st.todayAudited + st.remaining)), doneDay);
    renderGreenBoard();
    renderGrammarAuditStage();
  }, 150);
}

function commitGASpectrum(code) {
  if (gaAnimating) return;
  if (gaPendingNext) {
    advancePendingGA();
    return;
  }
  const sess = A.gaSess;
  if (!sess || !sess.queue.length) return;
  const gid = sess.queue[0];
  const spec = GA_SPECTRUM[code];
  if (!spec) return;

  const snapUndo = applyGASpectrumVerdict(gid, code, nowUnixSec());
  if (snapUndo) {
    if (!Array.isArray(sess.undoStack)) sess.undoStack = [];
    sess.undoStack.push(snapUndo);
    if (sess.undoStack.length > 20) sess.undoStack = sess.undoStack.slice(-20);
  }
  scheduleCloudPush(100);

  // If user chose 陌生(1) or 易混(2) BEFORE flipping, unfold meaning & example on open canvas with unified Zen dock
  if (!gaRevealed && (code === 1 || code === 2)) {
    gaRevealed = true;
    gaPendingNext = true;
    gaPendingCode = code;
    syncGARevealedCardHeader(GA_BY_GID[gid], code);
    const revEl = document.getElementById("ga-reveal-box");
    if (revEl) revEl.classList.add("shown");
    const audBtn = document.getElementById("ga-aud-btn");
    if (audBtn) audBtn.style.display = "none";
    const specWrap = document.getElementById("ga-spec-wrap");
    if (specWrap) {
      specWrap.innerHTML = `
        <div class="dock-row">
          <button class="dock-replay-btn" onclick="playGAAudio(event)">听</button>
          <button class="sumi-btn" onclick="advancePendingGA()">下一条 →</button>
        </div>
      `;
    }
    renderGreenBoard();
    updateVocabSubNav();
    return;
  }

  // Smooth fade-out and deal next atomic grammar point
  setGASpectrumPreview(code);
  const cardEl = document.getElementById("ga-card");
  gaAnimating = true;
  stopVocabAudioAndTimers();
  if (cardEl) cardEl.classList.add("ga-spec-card-fade");
  setTimeout(() => {
    gaAnimating = false;
    gaRevealed = false;
    gaPendingNext = false;
    gaPendingCode = 0;
    gaHoverCode = 0;
    sess.queue.shift();
    sess.cleared = Math.min(sess.total, (sess.cleared || 0) + 1);
    sess.done = sess.queue.length === 0;
    sess.updatedAt = nowUnixSec();
    const st = computeGrammarAuditStats();
    const dailyTgt = Number((DATA.grammar_audit && DATA.grammar_audit.daily_target) || 39);
    const doneDay = sess.done || st.remaining === 0 || st.todayAudited >= dailyTgt;
    saveAdaptiveState();
    recordGAProgress(Math.max(sess.cleared, st.todayAudited), Math.max(sess.total, Math.min(dailyTgt, st.todayAudited + st.remaining)), doneDay);
    renderGreenBoard();
    renderGrammarAuditStage();
  }, 150);
}

function undoLastGA(ev) {
  if (ev) ev.stopPropagation();
  if (gaAnimating) return;
  const sess = A.gaSess;
  if (!sess || !Array.isArray(sess.undoStack) || !sess.undoStack.length) return;
  stopVocabAudioAndTimers();
  const last = sess.undoStack.pop();
  const item = GA_BY_GID[last.gid];
  const undoStamp = Math.max(nowUnixSec(), (last.newTs || 0) + 1);
  if (item) {
    if (last.prevGa && last.prevGa.code > 0 && last.prevGa.ts >= MIN_REAL_TS) {
      A.gaMap[last.gid] = [last.prevGa.code, undoStamp, last.prevGa.date || TODAY_TAG];
    } else {
      A.gaMap[last.gid] = [0, undoStamp, TODAY_TAG];
    }
    const msKey = last.msTargetKey || item.parent_name || item.name;
    if (last.prevMs && last.prevMsTs >= TRUE_GREEN_EPOCH) {
      A.masteryOverrides[msKey] = last.prevMs;
      A.masteryOverrideTs[msKey] = undoStamp;
    } else {
      delete A.masteryOverrides[msKey];
      delete A.masteryOverrideTs[msKey];
    }
    if (last.hkKey) {
      if (last.prevHkMs && last.prevHkMsTs >= TRUE_GREEN_EPOCH) {
        A.masteryOverrides[last.hkKey] = last.prevHkMs;
        A.masteryOverrideTs[last.hkKey] = undoStamp;
      } else {
        delete A.masteryOverrides[last.hkKey];
        delete A.masteryOverrideTs[last.hkKey];
      }
    }
    applyMasteryOverrides();
    if (Array.isArray(A.recentRecords) && A.recentRecords.length) {
      for (let i = A.recentRecords.length - 1; i >= 0; i--) {
        if (A.recentRecords[i].id === `GA-${last.gid}` && (!last.recTs || A.recentRecords[i].ts === last.recTs)) {
          A.recentRecords.splice(i, 1);
          break;
        }
      }
    }
    const ob = loadOutbox();
    for (let i = ob.length - 1; i >= 0; i--) {
      if (ob[i][0] === `GA-${last.gid}` && (!last.recTs || ob[i][4] === last.recTs)) {
        ob.splice(i, 1);
        break;
      }
    }
    saveOutbox(ob);
  }
  if (gaPendingNext && sess.queue[0] === last.gid) {
    gaPendingNext = false;
    gaPendingCode = 0;
    gaRevealed = true;
  } else {
    sess.queue = [last.gid].concat((sess.queue || []).filter(id => id !== last.gid));
    sess.cleared = Math.max(0, (sess.cleared || 0) - 1);
    sess.done = false;
    gaRevealed = false;
  }
  sess.updatedAt = undoStamp;
  saveAdaptiveState();
  scheduleCloudPush(250);
  renderGreenBoard();
  updateVocabSubNav();
  renderGrammarAuditStage();
}

function bindGASpectrumGestures() {
  const rail = document.getElementById("ga-spec-rail");
  if (!rail) return;
  let activePid = null;
  let picked = 0;

  function codeFromPointer(e) {
    const rect = rail.getBoundingClientRect();
    const pt = fpXY(e.clientX, e.clientY);
    const ratio = Math.max(0, Math.min(0.999, (pt.x - rect.left) / Math.max(1, rect.width)));
    return Math.min(4, Math.max(1, Math.floor(ratio * 4) + 1));
  }

  rail.addEventListener("pointerdown", e => {
    if (gaAnimating || gaPendingNext) return;
    if (typeof e.button === "number" && e.button !== 0) return;
    activePid = e.pointerId;
    picked = codeFromPointer(e);
    setGASpectrumPreview(picked);
    try { rail.setPointerCapture(e.pointerId); } catch (err) {}
  });

  rail.addEventListener("pointermove", e => {
    if (activePid === null || e.pointerId !== activePid) return;
    const nextCode = codeFromPointer(e);
    if (nextCode !== picked) {
      picked = nextCode;
      setGASpectrumPreview(picked);
    }
  });

  function finishRail(e, cancelled) {
    if (activePid === null || e.pointerId !== activePid) return;
    const finalCode = cancelled ? 0 : codeFromPointer(e);
    activePid = null;
    try { rail.releasePointerCapture(e.pointerId); } catch (err) {}
    if (cancelled || !finalCode) {
      setGASpectrumPreview(0);
      return;
    }
    commitGASpectrum(finalCode);
  }

  rail.addEventListener("pointerup", e => finishRail(e, false));
  rail.addEventListener("pointercancel", e => finishRail(e, true));
}

function renderGrammarAuditStage() {
  updateVocabSubNav();
  const box = document.getElementById("vocab-stage-box");
  if (!box) return;
  const sess = ensureGASession(false);
  const st = computeGrammarAuditStats();
  const m = computeDaily120Metrics();

  if (!sess.queue.length) {
    const allDone = st.remaining === 0;
    const needVocab = !m.flashDone;
    const title = allDone ? "语法已全部盘完" : "今日这组已盘完";
    const desc = allDone
      ? `全表 ${st.total} 条已同步，后续按熟度精准排题。`
      : `已盘 ${st.audited} / ${st.total} 条，余 ${st.remaining} 条。`;
    box.innerHTML = `
      <div class="focal-space">
        <h2 class="point-heading">${title}</h2>
        <div class="ga-summary-grid">
          <div class="ga-stat-cell"><div class="ga-stat-num s1">${st.counts[1] || 0}</div><div class="ga-stat-lbl">陌生</div></div>
          <div class="ga-stat-cell"><div class="ga-stat-num s2">${st.counts[2] || 0}</div><div class="ga-stat-lbl">易混</div></div>
          <div class="ga-stat-cell"><div class="ga-stat-num s3">${st.counts[3] || 0}</div><div class="ga-stat-lbl">看懂</div></div>
          <div class="ga-stat-cell"><div class="ga-stat-num s4">${st.counts[4] || 0}</div><div class="ga-stat-lbl">本能</div></div>
        </div>
        <p class="logic-line">${desc}</p>
      </div>
      <div class="action-dock">
        <div class="dock-row">
          ${!allDone
            ? `<button class="ghost-btn" onclick="startNextGABatch()">再盘一组</button>`
            : `<button class="ghost-btn" onclick="switchMode('dash')">看总表</button>`}
          ${needVocab
            ? `<button class="sumi-btn" onclick="switchVocabSubMode('vocab')">去记词 →</button>`
            : (!allDone
              ? `<button class="sumi-btn" onclick="switchMode('dash')">看总表 →</button>`
              : `<button class="sumi-btn" onclick="switchMode('tutor')">回做题 →</button>`)}
        </div>
      </div>
    `;
    return;
  }

  const gid = sess.queue[0];
  const item = GA_BY_GID[gid];
  if (!item) return;
  const canUndo = Array.isArray(sess.undoStack) && sess.undoStack.length > 0;
  const eyeText = gaRevealed ? item.family : "";
  const headText = gaRevealed ? item.name : getGAFrontName(item);

  box.innerHTML = `
    <div class="ga-meta-bar">
      <span class="ga-meta-fam" id="ga-eyebrow">${escapeHtml(eyeText)}</span>
      <div class="vc-meta-right">
        ${canUndo ? `<button class="text-btn" onclick="undoLastGA(event)">撤销</button>` : ""}
        <button class="text-btn" id="ga-aud-btn" style="${gaRevealed ? "" : "display:none;"}" onclick="playGAAudio(event)">听</button>
      </div>
    </div>

    <div class="ga-stage" onclick="onGACardTapOrAudio()">
      <div class="ga-canvas" id="ga-card">
        <div class="ga-head" id="ga-head">${escapeHtml(headText)}</div>

        <div class="ga-reveal${gaRevealed ? " shown" : ""}" id="ga-reveal-box">
          <div class="ga-meaning">${escapeHtml(item.meaning)}</div>
          ${item.rule ? `<div class="ga-rule">${escapeHtml(item.rule)}</div>` : ""}
          ${item.ex_ja ? `<div class="ga-divider"></div><div class="ga-ex"><div class="ga-ex-ja">${escapeHtml(item.ex_ja)}</div>${item.ex_zh ? `<div class="ga-ex-zh">${escapeHtml(item.ex_zh)}</div>` : ""}</div>` : ""}
        </div>
      </div>
    </div>

    <div class="ga-spec-wrap" id="ga-spec-wrap">
      <div class="ga-spec-rail" id="ga-spec-rail">
        <div class="ga-spec-line"></div>
        <div class="ga-spec-stops">
          <div class="ga-spec-stop s1" id="ga-stop-1"><span class="ga-spec-dot"></span><span class="ga-spec-name">陌生</span></div>
          <div class="ga-spec-stop s2" id="ga-stop-2"><span class="ga-spec-dot"></span><span class="ga-spec-name">易混</span></div>
          <div class="ga-spec-stop s3" id="ga-stop-3"><span class="ga-spec-dot"></span><span class="ga-spec-name">看懂</span></div>
          <div class="ga-spec-stop s4" id="ga-stop-4"><span class="ga-spec-dot"></span><span class="ga-spec-name">本能</span></div>
        </div>
      </div>
    </div>
  `;

  bindGASpectrumGestures();
}

function setLedgerGrammarSpectrum(gid, code, ev) {
  if (ev) ev.stopPropagation();
  if (!gid || !GA_SPECTRUM[code]) return;
  applyGASpectrumVerdict(gid, code, nowUnixSec());
  scheduleCloudPush(100);
  renderGreenBoard();
  updateVocabSubNav();
  renderDashboard();
}

function daysSinceTag(tag8) {
  const s = String(tag8 || "").replace(/[^0-9]/g, "").slice(0, 8);
  if (s.length !== 8 || TODAY_TAG.length !== 8) return 0;
  const t1 = Date.UTC(Number(s.slice(0, 4)), Number(s.slice(4, 6)) - 1, Number(s.slice(6, 8)));
  const t2 = Date.UTC(Number(TODAY_TAG.slice(0, 4)), Number(TODAY_TAG.slice(4, 6)) - 1, Number(TODAY_TAG.slice(6, 8)));
  if (isNaN(t1) || isNaN(t2)) return 0;
  return Math.max(0, Math.round((t2 - t1) / 86400000));
}

function getEffectiveItemLastDate(it) {
  const ovTs = (A.masteryOverrideTs && (A.masteryOverrideTs[it.key] || A.masteryOverrideTs[it.name])) || 0;
  if (ovTs >= TRUE_GREEN_EPOCH) {
    try {
      const dt = new Date((ovTs - 4 * 3600) * 1000);
      const y = dt.getUTCFullYear();
      const m = String(dt.getUTCMonth() + 1).padStart(2, "0");
      const d = String(dt.getUTCDate()).padStart(2, "0");
      const liveTag = `${y}${m}${d}`;
      if (!it.last_date || liveTag > String(it.last_date)) return liveTag;
    } catch (e) {}
  }
  return String(it.last_date || "");
}

function isItemHesitant(it) {
  if (!it || it.tier === "todo") return false;
  const hMap = (A && A.hesitantKeys && typeof A.hesitantKeys === "object") ? A.hesitantKeys : {};
  const liveK = (it.key in hMap) ? hMap[it.key] : ((it.name in hMap) ? hMap[it.name] : undefined);
  if (liveK !== undefined) return !!liveK;
  return !!it.hesitant;
}

function jumpToRoiPillar(modKey) {
  dashMod = modKey;
  dashTier = "wip";
  expandedPt = null;
  renderDashboard();
}

function renderDashboard() {
  applyMasteryOverrides();
  const order = ["grammar", "henkei", "listening", "vocab"];
  const pillarMeta = order.map(k => {
    const m = DATA.mastery[k];
    const c = recalcCounts(k);
    const wip2 = m.items.filter(it => it.tier === "wip" && Number(it.streak || 0) >= 2).length;
    const staleDone = m.items.filter(it => {
      if (it.tier !== "done") return false;
      const ld = getEffectiveItemLastDate(it);
      return !!ld && daysSinceTag(ld) >= 10;
    }).length;
    const hesCnt = m.items.filter(it => isItemHesitant(it)).length;
    return { k, m, c, wip2, staleDone, hesCnt, roi: wip2 * (m.exam_pts || 25) };
  });

  // Metcalfe & Kornell (2005) Region of Proximal Learning: surface highest-ROI 2/3 near-graduation pillar!
  const roiEl = document.getElementById("dash-roi-focus");
  if (roiEl) {
    const best = pillarMeta.slice().sort((a, b) => (b.roi - a.roi) || (b.wip2 - a.wip2))[0];
    const totalWip2 = pillarMeta.reduce((s, x) => s + x.wip2, 0);
    const totalStale = pillarMeta.reduce((s, x) => s + x.staleDone, 0);
    const totalHes = pillarMeta.reduce((s, x) => s + x.hesCnt, 0);
    const dLeft = Number(DATA.days_to_exam || 14);
    const extras = [];
    if (totalHes > 0) extras.push(`略生 ${totalHes} 项`);
    if (totalStale > 0) extras.push(`待保鲜抽查 ${totalStale} 项`);
    const extraStr = extras.length ? ` · ${extras.join(" · ")}` : "";
    if (best && totalWip2 > 0) {
      roiEl.innerHTML = `
        <div class="dash-roi-bar">
          <span class="dash-roi-txt">距考剩 <b>${dLeft} 天</b> · 临门 2/3 共 <b>${totalWip2} 项</b>（${best.m.label}最提分${extraStr}）</span>
          <button type="button" class="dash-roi-btn" onclick="jumpToRoiPillar('${best.k}')">看 ${best.m.label} ›</button>
        </div>`;
    } else {
      roiEl.innerHTML = `
        <div class="dash-roi-bar">
          <span class="dash-roi-txt">距考剩 <b>${dLeft} 天</b> · 临门 2/3 已清空${extraStr || " · 稳步攻克新点即可"}</span>
        </div>`;
    }
  }

  document.getElementById("dash-summary").innerHTML = pillarMeta.map(({ k, m, c }) => {
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
  const ga = dm.ga;
  const remVocab = countRemainingVocabPool();
  const entryEl = document.getElementById("night-flash-entry");
  if (entryEl) {
    if (dashMod === "grammar" && ga && ga.total > 0) {
      const subTxt = ga.remaining > 0
        ? `已盘 ${ga.audited}/${ga.total} · 陌生 ${ga.counts[1] || 0} · 易混 ${ga.counts[2] || 0} · 看懂 ${ga.counts[3] || 0} · 本能 ${ga.counts[4] || 0}`
        : `全表 ${ga.total}/${ga.total} 已盘完 · 陌生 ${ga.counts[1] || 0} · 易混 ${ga.counts[2] || 0} · 看懂 ${ga.counts[3] || 0} · 本能 ${ga.counts[4] || 0}`;
      entryEl.innerHTML = `
        <div class="night-bar">
          <div class="night-bar-txt">
            <div class="night-bar-title">语法盘点</div>
            <div class="night-bar-sub">${subTxt}</div>
          </div>
          ${ga.remaining > 0
            ? `<button class="night-go-btn" onclick="openGrammarAuditFromAnywhere()">去盘点</button>`
            : `<button class="night-go-btn" onclick="switchMode('tutor')">去补漏</button>`}
        </div>
      `;
    } else if (remVocab > 0) {
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
    if (q) {
      if (q === "略生" || q === "犹豫") return isItemHesitant(it);
      if (q === "抽查" || q === "保鲜") {
        const ld = getEffectiveItemLastDate(it);
        return it.tier === "done" && !!ld && daysSinceTag(ld) >= 10;
      }
      return it.name.toLowerCase().includes(q) || (it.sub || "").toLowerCase().includes(q) || (it.family || "").toLowerCase().includes(q);
    }
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
    const splitKids = (dashMod === "grammar" && it.gid && Array.isArray(GA_SPLIT_MAP[it.gid])) ? GA_SPLIT_MAP[it.gid] : null;
    const gaEff = (dashMod === "grammar" && it.gid) ? (splitKids ? getEffectiveParentGA(it.gid) : getEffectiveGA(it.gid)) : null;
    const gaSpec = (gaEff && gaEff.code >= 1 && gaEff.code <= 4) ? GA_SPECTRUM[gaEff.code] : null;
    const gaTagHTML = gaSpec ? `<span class="li-ga-tag ${gaSpec.cls}">${gaSpec.label}</span>` : "";
    const hesHTML = isItemHesitant(it) ? `<span class="li-hes">略生</span>` : "";
    const lastD = it.tier === "done" ? getEffectiveItemLastDate(it) : "";
    const dStale = lastD ? daysSinceTag(lastD) : 0;
    const staleHTML = (it.tier === "done" && dStale >= 10) ? `<span class="li-stale">${dStale}天前·抽查</span>` : "";
    let gaBarHTML = "";
    if (expandedPt === i && dashMod === "grammar" && it.gid) {
      if (splitKids && splitKids.length) {
        gaBarHTML = `<div class="li-ga-sublist">${splitKids.map(cgid => {
          const cit = GA_BY_GID[cgid];
          if (!cit) return "";
          const ceff = getEffectiveGA(cgid);
          return `<div class="li-ga-subrow">
            <span class="li-ga-subname">${escapeHtml(cit.name)}</span>
            <span class="li-ga-subbtns">${[1, 2, 3, 4].map(c => {
              const sp = GA_SPECTRUM[c];
              return `<button type="button" class="li-ga-btn ${sp.cls}${ceff && ceff.code === c ? " on" : ""}" onclick="setLedgerGrammarSpectrum('${cgid}', ${c}, event)">${sp.label}</button>`;
            }).join("")}</span>
          </div>`;
        }).join("")}</div>`;
      } else {
        gaBarHTML = `<div class="li-ga-bar">
          <span class="li-ga-lbl">盘点</span>
          ${[1, 2, 3, 4].map(c => {
            const sp = GA_SPECTRUM[c];
            return `<button type="button" class="li-ga-btn ${sp.cls}${gaEff && gaEff.code === c ? " on" : ""}" onclick="setLedgerGrammarSpectrum('${it.gid}', ${c}, event)">${sp.label}</button>`;
          }).join("")}
        </div>`;
      }
    }
    return `
    <div class="ledger-item" onclick="togglePtNote(${i})">
      <div class="li-row">
        <div class="li-left">
          <span class="li-dot ${it.tier}"></span>
          <span class="li-name">${escapeHtml(it.name)}</span>
          ${gaTagHTML}${hesHTML}
        </div>
        <div class="li-right">
          <span class="li-sub">${escapeHtml(it.sub)}</span>
          ${staleHTML}
          <span class="li-streak ${stCls}">${stNum}/3</span>
          ${canSpeak ? `<button class="li-act" onclick='event.stopPropagation();speakLedgerItem(${JSON.stringify(it.name)}, ${JSON.stringify(it.audio || "")})'>听音</button>` : ""}
          ${it.point_id ? `<button class="li-act" onclick="event.stopPropagation();jumpToPointById('${it.point_id}')">练习</button>` : ""}
        </div>
      </div>
      ${expandedPt === i && (it.note || it.family) ? `<div class="li-note">${escapeHtml([it.family, it.note].filter(Boolean).join(" · "))}</div>` : ""}
      ${gaBarHTML}
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
    const gaEl = document.getElementById("modal-ga-cnt");
    if (gaEl && m.ga) gaEl.textContent = m.ga.remaining === 0 ? `全表 ${m.ga.total}/${m.ga.total} ✓` : `今日 ${m.ga.gaSeen}/${m.ga.gaTarget} · 总 ${m.ga.audited}/${m.ga.total}`;
    const scEl = document.getElementById("modal-proj-score");
    if (scEl) scEl.textContent = `${m.projScore} / 180 分`;
  });
}

function openSessionModal() {
  const m = computeDaily120Metrics();
  const ga = m.ga;
  const bm = (window.ZB && typeof window.ZB.getSummary === "function")
    ? window.ZB.getSummary()
    : { done: false, text: "0 / 3 项" };
  const gaRow = (ga && ga.showSubNav)
    ? `　 语法盘点　<strong id="modal-ga-cnt">${ga.remaining === 0 ? `全表 ${ga.total}/${ga.total} ✓` : `今日 ${ga.gaSeen} / ${ga.gaTarget} · 总 ${ga.audited}/${ga.total}`}</strong><br/>`
    : "";
  document.getElementById("modal-content").innerHTML = `
    <h3 class="modal-h">今日四修 · 日语与体律</h3>
    <p class="modal-body">
      ① 做题　　　<strong id="modal-green-cnt">${m.greenCnt} / ${m.totalCards} 题</strong><br/>
      ② 随身听　　<strong id="modal-radio-min">${m.listenedMins} / ${m.targetMins} 分钟</strong><br/>
      ③ 单手记词　<strong id="modal-flash-cnt">${m.flashDone ? "今日已完成" : `${m.flashSeen} / ${m.flashTarget} 词`}</strong><br/>
      ${gaRow}
      ④ 体律　　　<strong id="modal-body-cnt">${bm.done ? "今日已完成" : bm.text}</strong><br/>
      当前预计分　<strong id="modal-proj-score">${m.projScore} / 180 分</strong>
    </p>
    <p class="modal-promise">${ga && ga.requiredToday
      ? `四枚圆印不变，第 3 枚圆印兼含记词与语法盘点，盘完自动收起。`
      : "四枚圆印依次对应做题、随身听、记词与体律；总表里每个词与考点需跨 3 天答对满 3/3 才算真正掌握。"}</p>
    <div class="sync-box">
      <p class="sync-note" id="cloud-sync-status-line">正在对齐云端进度…</p>
      <button class="sync-btn" onclick="manualCloudSync(this)">立即对齐多端进度</button>
    </div>
    <div class="dock-row">
      <button class="ghost-btn" onclick="resetTodayMission()">重做题</button>
      <button class="ghost-btn" onclick="closeModal();switchMode('body')">体律</button>
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
let pendingEditionReload = false;
function reloadFreshEdition() {
  persistRadioPositionNow(true);
  let done = false;
  const go = () => {
    if (done) return;
    done = true;
    location.reload();
  };
  setTimeout(go, 600);
  if (typeof caches !== "undefined" && caches.keys) {
    caches.keys().then(keys =>
      Promise.all(
        keys.map(k =>
          caches.open(k).then(c => Promise.all([c.delete("./"), c.delete("./index.html")])).catch(() => {})
        )
      )
    ).finally(go);
  } else {
    go();
  }
}
function flushPendingEditionReload(allowDuringActiveRadioSession) {
  if (!pendingEditionReload) return;
  // Never reload while backgrounded/screen-off or right after pausing radio:
  // reloading destroys the active Android MediaSession so Pixel Buds tap-to-resume fails!
  if (document.visibilityState !== "visible") return;
  if (!allowDuringActiveRadioSession && typeof radioHasPlayedOnce !== "undefined" && radioHasPlayedOnce) return;
  if (!activeKind && radioPlayer.paused) {
    pendingEditionReload = false;
    reloadFreshEdition();
  }
}
radioPlayer.addEventListener("ended", () => setTimeout(() => flushPendingEditionReload(true), 400));
if (typeof player !== "undefined" && player && player.addEventListener) {
  player.addEventListener("pause", () => setTimeout(() => flushPendingEditionReload(false), 450));
  player.addEventListener("ended", () => setTimeout(() => flushPendingEditionReload(false), 450));
}

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
      if (isNewerDay || isNewerAudio) {
        const targetKey = `${rm.date}_${rm.script_sig || ""}`;
        try {
          const prev = sessionStorage.getItem("n3_edition_reload") || "";
          const parts = prev.split("@");
          if (parts[0] === targetKey && (Date.now() - Number(parts[1] || 0)) < 20000) return;
          sessionStorage.setItem("n3_edition_reload", `${targetKey}@${Date.now()}`);
        } catch (e) {}
        const radioSessionLive = typeof radioHasPlayedOnce !== "undefined" && radioHasPlayedOnce;
        if (document.visibilityState === "visible" && !activeKind && radioPlayer.paused && !radioSessionLive) {
          reloadFreshEdition();
        } else {
          pendingEditionReload = true;
        }
      }
    })
    .catch(() => {})
    .finally(() => { editionCheckBusy = false; });
}

setInterval(() => {
  if (document.visibilityState === "visible") checkNewDailyEdition();
}, 10 * 60 * 1000);

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    tryLockPortrait();
    if (pendingEditionReload && radioPlayer.paused && (!radioHasPlayedOnce || (Date.now() - lastRadioPauseMs) > 90000)) {
      flushPendingEditionReload(true);
    }
    checkNewDailyEdition();
    pullCloudSync(true);
    connectCloudSSE();
    if (activeMode === "body" && window.ZB) window.ZB.onResume();
  } else {
    persistRadioPositionNow(false);
    if (cloudPushTimer) {
      clearTimeout(cloudPushTimer);
      cloudPushTimer = null;
      pushCloudSync(true);
    } else {
      persistRadioPositionNow(true);
    }
  }
});

window.addEventListener("online", () => {
  checkNewDailyEdition();
  pullCloudSync(true);
  connectCloudSSE();
  if (activeMode === "body" && window.ZB) window.ZB.onResume();
});

window.addEventListener("pagehide", () => {
  persistRadioPositionNow(false);
  if (cloudPushTimer) {
    clearTimeout(cloudPushTimer);
    cloudPushTimer = null;
    pushCloudSync(true);
  } else {
    persistRadioPositionNow(true);
  }
});

window.addEventListener("beforeunload", () => {
  persistRadioPositionNow(false);
});

// ================= NATIVE ZEN BODY ENGINE ("体律" · v2 Native-App Polish · 零明文隐私) =================
window.ZB = (function() {
  const VAULT_KEY = "zenbody_vault_v1";
  const STATE_KEY = "zenbody_state_v1";
  const PEND_KEY = "zenbody_pending_push_v1";
  const SUB_ORDER = ["today", "pullup", "body", "ledger"];
  const PZ_PROGS = [
    { id: "dypz", name: "Discover Your Power Zones", short: "Discover PZ", total: 23, offset: 0, entry: "底栏 Programs → 英文原版 Discover Your Power Zones" },
    { id: "byb", name: "Boost Your Base: Power Zones", short: "Boost Base", total: 24, offset: 23, entry: "底栏 Programs（或 Collections）→ Boost Your Base: Power Zones" }
  ];
  const PZ_CH_LABELS = {
    0: {
      1: "第 1 章 · 入门与测区（6 节，分 2–3 周骑 · Bike+ Week 1）",
      2: "第 2 章 · 稳态打底（4 节，约 2 周 · Bike+ Week 2）",
      3: "第 3 章 · 进阶节奏（4 节，约 2 周 · Bike+ Week 3）",
      4: "第 4 章 · 耐力巅峰（4 节，约 2 周 · Bike+ Week 4）",
      5: "第 5 章 · 减量复测（5 节，约 2 周 · Bike+ Week 5）"
    },
    1: {
      1: "第 1 章（3 节，按体能 1–2 周 · Bike+ Week 1）",
      2: "第 2 章（3 节，按体能 1–2 周 · Bike+ Week 2）",
      3: "第 3 章（3 节，按体能 1–2 周 · Bike+ Week 3）",
      4: "第 4 章 · 减量恢复（3 节 · Bike+ Week 4）",
      5: "第 5 章（3 节，按体能 1–2 周 · Bike+ Week 5）",
      6: "第 6 章 · 含 75 分长课（3 节 · Bike+ Week 6）",
      7: "第 7 章 · 含 90 分巅峰（3 节 · Bike+ Week 7）",
      8: "第 8 章 · 结业收官（3 节 · Bike+ Week 8）"
    }
  };
  const PZ_LIST = [
    [0, 1, 1, "15 min Intro to Power Zone Ride", "Matt Wilpers", 15, "easy", "入门认识 7 个功率区，全程坐姿无压力"],
    [0, 1, 2, "20 min Power Zone Beginner Ride", "Matt Wilpers", 20, "easy", "坐姿感受各档发力，为第 3 节 FTP 测试热身"],
    [0, 1, 3, "FTP 基线测试（10分热身 + 20分测试）", "Denis Morton", 30, "test", "先 10 min FTP Warm Up，紧接 20 min FTP Test；全力稳推测出 7 档功率区，结束点 Yes 保存"],
    [0, 1, 4, "30 min Power Zone Endurance Ride", "Christine D'Ercole", 30, "pze", "首节 Zone 2–3 稳态燃脂，配《锵锵三人行》最舒服"],
    [0, 1, 5, "20 min Low Impact Ride", "Matt Wilpers", 20, "easy", "全程坐姿低冲击，练踩踏顺滑度顺便松腿"],
    [0, 1, 6, "30 min Power Zone Endurance Ride", "Olivia Amato", 30, "pze", "Zone 2–3 稳态耐力，第 1 章顺利收尾"],
    [0, 2, 1, "30 min Power Zone Hip Hop Ride", "Matt Wilpers", 30, "hard", "首次触碰 Zone 4 节奏段，挑不打球、腿轻松的日子骑"],
    [0, 2, 2, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "45 分钟 Zone 2–3 黄金燃脂，刚好听大半期《锵锵》"],
    [0, 2, 3, "30 min Power Zone Endurance Ride", "Olivia Amato", 30, "pze", "中段 Zone 2–3 稳态过渡，护腿稳掉脂"],
    [0, 2, 4, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "45 分钟稳态耐力，第 2 章顺利收官"],
    [0, 3, 1, "30 min Power Zone Ride", "Christine D'Ercole", 30, "hard", "Zone 3–4 进阶间歇，稳步拉高阈值"],
    [0, 3, 2, "45 min Power Zone Ride", "Matt Wilpers", 45, "hard", "Zone 3–5 主力强课，挑不打球、双腿轻松的日子骑"],
    [0, 3, 3, "30 min Power Zone Endurance 80s Ride", "Denis Morton", 30, "pze", "80 年代老歌 Zone 2–3 稳态，让双腿喘口气"],
    [0, 3, 4, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "45 分钟稳态燃脂，第 3 章顺利收官"],
    [0, 4, 1, "45 min Power Zone Ride", "Denis Morton", 45, "hard", "巅峰章第 1 场：Zone 3–5 阈值强课，骑完次日自动休整"],
    [0, 4, 2, "45 min Power Zone Ride", "Olivia Amato / Sam Yo", 45, "hard", "巅峰章第 2 场：Zone 3–5 强课（按项目 Week 4 第 2 节骑）"],
    [0, 4, 3, "30 min Power Zone Endurance Ride", "Christine D'Ercole", 30, "pze", "两场强课后回落 Zone 2–3 恢复打底"],
    [0, 4, 4, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟 Zone 2–3 燃脂大课，留给不打球的轻松日配整期《锵锵》"],
    [0, 5, 1, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "进入结业减量章，保持 Zone 2–3 踩踏手感"],
    [0, 5, 2, "20 min Low Impact Ride", "Matt Wilpers", 20, "easy", "20 分钟极轻坐姿松腿，为结业复测蓄力"],
    [0, 5, 3, "30 min Power Zone Endurance Rock Ride", "Christine D'Ercole", 30, "pze", "摇滚稳态 Zone 2–3，轻推保持状态"],
    [0, 5, 4, "30 min Power Zone Endurance Pop Ride", "Olivia Amato", 30, "pze", "测前最后一节轻耐力，保留腿力给结业复测"],
    [0, 5, 5, "结业 FTP 复测（15分热身 + 20分测试）", "Matt Wilpers", 35, "test", "先 15 min FTP Warm Up，紧接 20 min FTP Test；刷新 7 档功率区、正式拿下 Discover 结业！"],
    [1, 1, 1, "30 min Power Zone Endurance Ride", "Matt Wilpers", 30, "pze", "稳态燃脂底盘启动：全 Zone 2–3 不伤打球双腿"],
    [1, 1, 2, "30 min Power Zone Endurance Ride", "Sam Yo", 30, "pze", "Sam Yo 沉稳节奏，全程坐姿稳态燃脂"],
    [1, 1, 3, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "第 1 章长骑：45 分钟 Zone 2–3 稳态"],
    [1, 2, 1, "30 min Power Zone Endurance Ride", "Denis Morton", 30, "pze", "第 2 章起跑：30 分钟 Zone 2–3 稳态"],
    [1, 2, 2, "45 min Power Zone Endurance Ride", "Hannah Frankson", 45, "pze_long", "45 分钟节奏流畅 Zone 2–3 耐力"],
    [1, 2, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟稳态掉脂，挑不打球日配一期《锵锵》"],
    [1, 3, 1, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "第 3 章稳步推进：45 分钟 Zone 2–3 稳态"],
    [1, 3, 2, "45 min Power Zone Endurance Ride", "Christian Vande Velde", 45, "pze_long", "前环法职业车手带队，踩踏效率极高"],
    [1, 3, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟稳态耐力，打牢有氧底盘"],
    [1, 4, 1, "30 min Power Zone Endurance Ride", "Sam Yo", 30, "pze", "第 4 章恢复减量：轻快 30 分钟稳态"],
    [1, 4, 2, "30 min Power Zone Endurance Ride", "Tunde Oyeneyin", 30, "pze", "30 分钟减量维持，让身体吸收前 3 章红利"],
    [1, 4, 3, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "减量章收官，下章体能上一个台阶"],
    [1, 5, 1, "45 min Power Zone Endurance Ride", "Christine D'Ercole", 45, "pze_long", "下半程启动：45 分钟沉稳 Zone 2–3"],
    [1, 5, 2, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "45 分钟核心有氧耐力"],
    [1, 5, 3, "60 min Power Zone Endurance Ride", "Hannah Frankson", 60, "pze_long", "60 分钟长耐力，挑不打球日配《锵锵》"],
    [1, 6, 1, "45 min Power Zone Endurance Ride", "Charlotte Weidenbach", 45, "pze_long", "第 6 章：45 分钟稳态燃脂"],
    [1, 6, 2, "45 min Power Zone Endurance Ride", "Ben Alldis", 45, "pze_long", "Ben Alldis 干脆利落少废话，最适合配播客"],
    [1, 6, 3, "75 min Power Zone Endurance Ride", "Matt Wilpers", 75, "pze_long", "75 分钟长耐力，仅限周末不打球满血日（平时也可换 45 分）"],
    [1, 7, 1, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "第 7 章稳态维持"],
    [1, 7, 2, "45 min Power Zone Endurance Ride", "Erik Jäger", 45, "pze_long", "45 分钟稳态过渡"],
    [1, 7, 3, "90 min Power Zone Endurance Ride", "Matt Wilpers & Denis Morton", 90, "pze_long", "双教练 90 分钟耐力巅峰，仅限周末不打球满血日（累了随时换 45 分）"],
    [1, 8, 1, "45 min Power Zone Endurance Ride", "Ben Alldis", 45, "pze_long", "结业减量章第 1 节：45 分钟稳态"],
    [1, 8, 2, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "结业章第 2 节：45 分钟流畅稳态"],
    [1, 8, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "Boost Your Base 24 节正式毕业收官！"]
  ];
  let VAULT = null;
  let CKEY = null;
  let INITED = false;
  let GESTURES_BOUND = false;
  let SUBTAB = "today";
  let METRIC = "bf";
  let RANGE = "90";
  let PZ_VIEW_PROG = 0;
  let PU_IN = 1;
  let SYNC_NOTE = "";
  let PUSH_T = null;
  let TOAST_T = null;
  let LAST_DAY = "";
  let PREV_ENSO = null;
  let EXP_DAY = null;

  let CHART_PTS = [];
  let SCRUB_IDX = -1;
  let D_WT = 81.5, D_BF = 18.0, D_SKIP_BF = false, D_WT_OFF = 0, D_BF_OFF = 0;
  let PACER_ON = false, PACER_RAF = null, PACER_SND = false, PACER_WL = null, ACTX = null;

  function defState() {
    return {
      v: 1, ts: 0,
      targets: { bf_ge: 14.0, pullups: 5, deadline: "2027-12-31", pu_max_reps: 3, pu_max_rounds: 2 },
      pu_best: 1, pu_best_ts: 0,
      pz: { idx: 1, ts: 0, last: "2026-11-21" },
      vitals: { vo2: null, rhr: null, last_drive_sync: "", gaps: [] },
      trips: [], wb: [], acts: [], days: {}
    };
  }
  let ST = defState();

  function ge(id) { return document.getElementById(id); }
  function toast(msg) {
    const el = ge("zb-toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(TOAST_T);
    TOAST_T = setTimeout(() => el.classList.remove("show"), 2200);
  }

  function ptNow(offH) {
    const now = new Date(Date.now() + (offH || 0) * 3600000);
    if (typeof Intl !== "undefined" && Intl.DateTimeFormat) {
      try {
        const parts = new Intl.DateTimeFormat("en-CA", {
          timeZone: "America/Los_Angeles",
          year: "numeric", month: "2-digit", day: "2-digit",
          hour: "2-digit", minute: "2-digit", hour12: false
        }).formatToParts(now);
        const m = {};
        for (const p of parts) m[p.type] = p.value;
        return { ymd: `${m.year}-${m.month}-${m.day}`, hour: Number(m.hour), minute: Number(m.minute) };
      } catch (e) {}
    }
    const iso = now.toISOString();
    return { ymd: iso.slice(0, 10), hour: Number(iso.slice(11, 13)), minute: Number(iso.slice(14, 16)) };
  }
  function fmtEpochPT(sec) {
    if (!sec) return "";
    try {
      const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "America/Los_Angeles", hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(new Date(sec * 1000));
      const m = {}; for (const p of parts) m[p.type] = p.value;
      return `${m.hour}:${m.minute}`;
    } catch (e) { return ""; }
  }
  function todayYmd() { return ptNow(-4).ymd; }
  function shiftD(ymd, dd) {
    const a = ymd.split("-").map(Number);
    return new Date(Date.UTC(a[0], a[1] - 1, a[2] + dd)).toISOString().slice(0, 10);
  }
  function fmtCn(ymd) {
    const a = ymd.split("-").map(Number);
    const wd = ["周日","周一","周二","周三","周四","周五","周六"][new Date(Date.UTC(a[0], a[1] - 1, a[2], 12)).getUTCDay()];
    return `${a[1]}月${a[2]}日 ${wd}`;
  }
  function mondayOf(ymd) {
    const a = ymd.split("-").map(Number);
    const dow = new Date(Date.UTC(a[0], a[1] - 1, a[2], 12)).getUTCDay();
    return shiftD(ymd, dow === 0 ? -6 : 1 - dow);
  }

  function b64uToBytes(s) {
    const pad = "=".repeat((4 - (s.length % 4)) % 4);
    const bin = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function bytesToB64u(bytes) {
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  async function importRawKey(kB64u) {
    if (typeof crypto === "undefined" || !crypto.subtle) return null;
    return crypto.subtle.importKey("raw", b64uToBytes(kB64u), { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  }
  async function decWithKey(key, str) {
    if (!key || !str || !str.startsWith("z1.")) return null;
    try {
      const raw = b64uToBytes(str.slice(3));
      if (raw.length < 29) return null;
      const buf = await crypto.subtle.decrypt({ name: "AES-GCM", iv: raw.slice(0, 12) }, key, raw.slice(12));
      return JSON.parse(new TextDecoder().decode(buf));
    } catch (e) { return null; }
  }
  async function encWithKey(key, obj) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(JSON.stringify(obj))));
    const comb = new Uint8Array(iv.length + ct.length);
    comb.set(iv, 0); comb.set(ct, iv.length);
    return "z1." + bytesToB64u(comb);
  }

  function saveLocal() { try { localStorage.setItem(STATE_KEY, JSON.stringify(ST)); } catch (e) {} }
  function loadLocal() {
    try {
      const r = localStorage.getItem(STATE_KEY);
      if (r) {
        const p = JSON.parse(r);
        if (p && p.v === 1) ST = mergeS(defState(), p);
      }
    } catch (e) {}
  }

  function mergeS(a, b) {
    if (!b || typeof b !== "object") return a;
    const nw = (b.ts || 0) >= (a.ts || 0) ? b : a;
    const od = nw === b ? a : b;
    const ta = Number(a.pu_best_ts || 0), tb = Number(b.pu_best_ts || 0);
    let puBest, puBestTs;
    if (ta > tb) { puBest = Number(a.pu_best || 1); puBestTs = ta; }
    else if (tb > ta) { puBest = Number(b.pu_best || 1); puBestTs = tb; }
    else { puBest = Math.max(Number(a.pu_best || 1), Number(b.pu_best || 1)); puBestTs = ta; }
    const pza = (a.pz && typeof a.pz === "object") ? a.pz : {};
    const pzb = (b.pz && typeof b.pz === "object") ? b.pz : {};
    const pzaTs = Number(pza.ts || 0), pzbTs = Number(pzb.ts || 0);
    let pzOut;
    if (pzaTs > pzbTs) pzOut = { idx: Math.max(0, Number(pza.idx != null ? pza.idx : 1)), ts: pzaTs, last: String(pza.last || "") };
    else if (pzbTs > pzaTs) pzOut = { idx: Math.max(0, Number(pzb.idx != null ? pzb.idx : 1)), ts: pzbTs, last: String(pzb.last || "") };
    else {
      const ia = pza.idx != null ? Number(pza.idx) : 0, ib = pzb.idx != null ? Number(pzb.idx) : 0;
      const la = String(pza.last || ""), lb = String(pzb.last || "");
      pzOut = { idx: Math.max(ia, ib), ts: pzaTs, last: la >= lb ? la : lb };
    }
    const out = {
      v: 1,
      ts: Math.max(a.ts || 0, b.ts || 0),
      targets: Object.assign({}, od.targets || {}, nw.targets || {}),
      pu_best: puBest,
      pu_best_ts: puBestTs,
      pz: pzOut,
      vitals: Object.assign({}, od.vitals || {}, nw.vitals || {}),
      trips: (nw.trips && nw.trips.length) ? nw.trips : (od.trips || []),
      wb: [], acts: [], days: {}
    };
    if (((a.vitals && a.vitals.last_drive_sync) || "") > ((out.vitals && out.vitals.last_drive_sync) || "")) out.vitals = Object.assign({}, out.vitals, a.vitals);
    if (((b.vitals && b.vitals.last_drive_sync) || "") > ((out.vitals && out.vitals.last_drive_sync) || "")) out.vitals = Object.assign({}, out.vitals, b.vitals);
    const wm = new Map();
    for (const lst of [od.wb || [], nw.wb || []]) {
      for (const r of lst) {
        if (!r || !r[0]) continue;
        const p = wm.get(r[0]);
        if (!p) wm.set(r[0], r.slice());
        else {
          const wVal = (r.length > 4 && r[4]) ? r[4] : ((p.length > 4 && p[4]) ? p[4] : null);
          const merged = [r[0], r[1] || p[1], (r[2] && r[2] > 5) ? r[2] : p[2], (r[2] && r[2] > 5) ? (r[3] || p[3]) : (p[3] || r[3])];
          if (wVal != null) merged.push(wVal);
          wm.set(r[0], merged);
        }
      }
    }
    out.wb = Array.from(wm.values()).sort((x, y) => x[0].localeCompare(y[0]));
    const am = new Map();
    for (const lst of [od.acts || [], nw.acts || []]) {
      for (const r of lst) {
        if (!r || !r[0]) continue;
        am.set(`${r[0]}|${r[1]}|${Math.round((r[2] || 0) / 5)}`, r.slice());
      }
    }
    out.acts = Array.from(am.values()).sort((x, y) => x[0].localeCompare(y[0]));
    const ks = new Set([...Object.keys(a.days || {}), ...Object.keys(b.days || {})]);
    for (const k of ks) {
      const da = (a.days && a.days[k]) || null, db = (b.days && b.days[k]) || null;
      if (!da) out.days[k] = Object.assign({}, db);
      else if (!db) out.days[k] = Object.assign({}, da);
      else out.days[k] = (db.ts || 0) >= (da.ts || 0) ? Object.assign({}, da, db) : Object.assign({}, db, da);
    }
    return out;
  }

  function compactS(st) {
    const cut = shiftD(todayYmd(), -21);
    const cd = {};
    for (const [k, v] of Object.entries(st.days || {})) if (k >= cut) cd[k] = v;
    let wb = st.wb || [];
    if (wb.length > 36) {
      const rec = wb.slice(-20);
      const rset = new Set(rec.map(r => r[0]));
      const byM = new Map();
      for (const r of wb) if (!rset.has(r[0])) byM.set(r[0].slice(0, 7), r);
      wb = [...Array.from(byM.values()).slice(-16), ...rec];
    }
    return { v: 1, ts: st.ts || Math.floor(Date.now() / 1000), targets: st.targets, pu_best: st.pu_best, pu_best_ts: st.pu_best_ts || 0, pz: st.pz || { idx: 1, ts: 0, last: "2026-11-21" }, vitals: st.vitals, trips: st.trips || [], wb, acts: (st.acts || []).slice(-18), days: cd };
  }

  async function pullCloud(silent) {
    if (!VAULT || !CKEY) return;
    let n = 0;
    try {
      const r = await fetch("./body_vault.enc?t=" + Date.now(), { cache: "no-store" });
      if (r.ok) {
        const env = await r.json();
        if (env && env.d) {
          const dec = await decWithKey(CKEY, env.d);
          if (dec && dec.v === 1) { ST = mergeS(ST, dec); n++; }
        }
      }
    } catch (e) {}
    try {
      const r2 = await fetch(`https://ntfy.sh/${encodeURIComponent(VAULT.t)}/json?poll=1&since=all`, { cache: "no-store" });
      if (r2.ok) {
        const lines = (await r2.text()).trim().split("\n").filter(Boolean);
        for (const ln of lines) {
          try {
            const ev = JSON.parse(ln);
            if (ev.event !== "message" || !ev.message) continue;
            const dec = await decWithKey(CKEY, ev.message.trim());
            if (dec && dec.v === 1) { ST = mergeS(ST, dec); n++; }
          } catch (e) {}
        }
      }
      if (n > 0) { saveLocal(); syncPUDefault(); }
      const p = ptNow(0);
      SYNC_NOTE = `云端已同步 · ${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
      render();
      if (!silent) toast("体律已同步最新数据");
    } catch (e) {
      if (n > 0) saveLocal();
      SYNC_NOTE = "离线可用 · 联网后自动同步";
      render();
    }
  }

  async function pushNow() {
    if (!VAULT || !CKEY) return;
    try {
      const pl = compactS(ST);
      let enc = await encWithKey(CKEY, pl);
      if (enc.length > 3850) { pl.wb = pl.wb.slice(-24); pl.acts = pl.acts.slice(-12); enc = await encWithKey(CKEY, pl); }
      const res = await fetch(`https://ntfy.sh/${encodeURIComponent(VAULT.t)}`, { method: "POST", body: enc });
      if (res.ok) {
        try { localStorage.removeItem(PEND_KEY); } catch (e) {}
        const p = ptNow(0);
        SYNC_NOTE = `已加密同步 · ${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
        const el = ge("zb-sync-txt");
        if (el) el.textContent = SYNC_NOTE;
      } else { try { localStorage.setItem(PEND_KEY, "1"); } catch (e) {} }
    } catch (e) { try { localStorage.setItem(PEND_KEY, "1"); } catch (err) {} }
  }
  function schedPush() {
    ST.ts = Math.floor(Date.now() / 1000);
    saveLocal();
    try { localStorage.setItem(PEND_KEY, "1"); } catch (e) {}
    clearTimeout(PUSH_T);
    PUSH_T = setTimeout(pushNow, 320);
  }

  function dayE(ymd) { return (ST.days && ST.days[ymd]) || {}; }
  function actsOn(ymd) { return (ST.acts || []).filter(a => a[0] === ymd); }
  function daysDiff(ymdA, ymdB) {
    if (!ymdA || !ymdB) return 0;
    const tA = Date.parse(ymdA + "T12:00:00Z"), tB = Date.parse(ymdB + "T12:00:00Z");
    if (isNaN(tA) || isNaN(tB)) return 0;
    return Math.max(0, Math.round((tB - tA) / 86400000));
  }
  function getPZIdx() {
    const raw = (ST.pz && ST.pz.idx != null) ? Number(ST.pz.idx) : 1;
    return Math.max(0, Math.min(PZ_LIST.length, isNaN(raw) ? 1 : raw));
  }
  function getPZMeta(idx) {
    if (idx >= PZ_LIST.length) {
      return {
        idx: PZ_LIST.length, allDone: true, pIdx: 1, progName: "Power Zone 全线通关", progShort: "PZ 已通关",
        progTotal: 47, doneInProg: 47, numInProg: 47, remInProg: 0, pct: 100,
        wk: 8, seq: 3, code: "维稳燃脂", shortCode: "PZE",
        title: "45 min Power Zone Endurance Ride", coach: "Matt Wilpers", min: 45, kind: "pze_long",
        cue: "已完成 Discover + Boost Your Base 共 47 节！保持每周 2–3 节 Zone 2–3 稳态燃脂。",
        entry: "底栏 Classes → Cycling → 清空 FILTER → 45 min Power Zone Endurance"
      };
    }
    const r = PZ_LIST[idx];
    const prog = PZ_PROGS[r[0]];
    const doneInProg = idx - prog.offset;
    const numInProg = doneInProg + 1;
    const pct = Math.max(3, Math.round((doneInProg / prog.total) * 100));
    return {
      idx, allDone: false, pIdx: r[0], progName: prog.name, progShort: prog.short,
      progTotal: prog.total, doneInProg, numInProg, remInProg: prog.total - doneInProg, pct,
      wk: r[1], seq: r[2], code: `W${r[1]} 第 ${r[2]} 节`, shortCode: `W${r[1]}·${r[2]}`,
      title: r[3], coach: r[4], min: r[5], kind: r[6], cue: r[7],
      entry: `${prog.entry} → Week ${r[1]} → 第 ${r[2]} 节`
    };
  }
  function bbOn(ymd) {
    const d = dayE(ymd);
    if (d.bb === "none") return null;
    const dr = actsOn(ymd).filter(a => a[1] === "bb");
    if (dr.length) {
      const dur = dr.reduce((s, r) => s + (r[2] || 0), 0);
      const kcal = dr.reduce((s, r) => s + (r[3] || 0), 0);
      const ahr = Math.max(...dr.map(r => r[4] || 0));
      const mhr = Math.max(...dr.map(r => r[5] || 0));
      const autoLvl = (kcal >= 1350 || dur >= 85 || mhr >= 172) ? "max" : ((dur >= 40 || kcal >= 700 || ahr >= 125) ? "high" : "light");
      const lvl = (d.bb === "light" || d.bb === "high" || d.bb === "max") ? d.bb : autoLvl;
      return { level: lvl, dur: Math.round(dur), kcal: Math.round(kcal), maxHr: mhr, src: "drive" };
    }
    if (d.bb === "light" || d.bb === "high" || d.bb === "max") return { level: d.bb, dur: 0, kcal: 0, maxHr: 0, src: "tap" };
    return null;
  }
  function getDayState(ymd) {
    const bb = bbOn(ymd), d = dayE(ymd);
    if (bb) return { mode: "bb", sub: bb.level, bb };
    if (d.tired) return { mode: "tired", sub: d.tired === "sore" ? "sore" : "sleep", bb: null };
    if (d.rest_day) return { mode: "rest", sub: "", bb: null };
    return { mode: "normal", sub: "", bb: null };
  }
  function peloOn(ymd) {
    const dr = actsOn(ymd).filter(a => a[1] === "pelo");
    if (dr.length) return { status: "done", min: Math.round(dr.reduce((s, r) => s + (r[2] || 0), 0)), src: "drive" };
    const d = dayE(ymd);
    if (d.pelo) return { status: d.pelo, min: d.pelo_min || 0, src: "tap" };
    return null;
  }
  function tripOn(ymd) {
    for (const t of (ST.trips || [])) if (ymd >= t.start && ymd <= t.end) return t;
    return null;
  }
  function dayLoad(ymd) {
    const b = bbOn(ymd);
    if (b && b.level === "max") return "max";
    if (b && b.level === "high") return "heavy";
    const p = peloOn(ymd), de = dayE(ymd);
    if (p && p.status === "done") {
      if (de.pz_done != null) {
        const c = getPZMeta(Number(de.pz_done));
        if (c.kind === "test" || c.kind === "hard" || c.min >= 60) return "heavy";
        if (c.kind === "easy") return "easy";
        return "mod";
      }
      if ((p.min || 0) >= 45) return "heavy";
      if ((p.min || 0) >= 25) return "mod";
      return "easy";
    }
    if (p && p.status === "recovery") return "easy";
    if (b && b.level === "light") return "easy";
    return "rest";
  }
  function weekStats(ymd) {
    const mon = mondayOf(ymd);
    let bbH = 0, pM = 0, realPM = 0, puR = 0, res = 0;
    for (let i = 0; i < 7; i++) {
      const d = shiftD(mon, i);
      if (d > ymd) break;
      const b = bbOn(d); if (b && (b.level === "high" || b.level === "max")) bbH++;
      const p = peloOn(d);
      if (p && p.status === "done") {
        pM++;
        const de = dayE(d);
        const cls = de.pz_done != null ? getPZMeta(Number(de.pz_done)) : null;
        if ((cls && cls.kind !== "easy") || (!cls && (p.min || 0) >= 25)) realPM++;
      }
      const deObj = dayE(d);
      puR += (deObj.pu || []).length;
      if (deObj.res) res++;
    }
    const pzGoal = bbH >= 3 ? 1 : (bbH >= 2 ? 2 : 3);
    return { bbH, pM, realPM, hard: bbH + pM, realHard: bbH + realPM, pzGoal, puR, res };
  }
  function streakBefore(ymd) {
    let active = 0, any = 0, activeOn = true, anyOn = true;
    for (let i = 1; i <= 7; i++) {
      const d = shiftD(ymd, -i);
      const ld = dayLoad(d);
      const p = peloOn(d);
      const isActive = ld === "max" || ld === "heavy" || ld === "mod";
      const isAny = isActive || !!(p && p.status === "done");
      if (activeOn && isActive) active++; else activeOn = false;
      if (anyOn && isAny) any++; else anyOn = false;
      if (!activeOn && !anyOn) break;
    }
    return { active, any };
  }
  function bbLast7(ymd) {
    let n = 0;
    for (let i = 0; i < 7; i++) {
      const b = bbOn(shiftD(ymd, -i));
      if (b && (b.level === "high" || b.level === "max")) n++;
    }
    return n;
  }
  function staleLevel(daysGap, recentBB, inTrip, rhr) {
    if (inTrip || rhr >= 46 || !daysGap) return "none";
    if (daysGap >= 14) return "remind";
    if (daysGap >= 10 || (daysGap >= 7 && recentBB < 2)) return "gentle";
    return "none";
  }

  function watchReadiness(ymd) {
    const v = ST.vitals || {};
    const rhr = v.rhr || null;
    const rhrBase = v.rhr_base || 40;
    const rhrFresh = !!(rhr && (!v.rhr_date || daysDiff(v.rhr_date, ymd) <= 1));
    const hrv = v.hrv || null;
    const hrvBase = v.hrv_base || 0;
    const hrv7d = v.hrv_7d || null;
    const hrvSd = v.hrv_sd || (hrvBase ? Math.max(4, Math.round(hrvBase * 0.12)) : 0);
    const hrvLowStreak = Number(v.hrv_low_streak || 0);
    const hrvFresh = !!(hrv && hrvBase >= 30 && v.hrv_date && daysDiff(v.hrv_date, ymd) <= 1);
    const sleepH = v.sleep_h || null;
    const slFresh = !!(sleepH && v.sleep_date && v.sleep_date === ymd);
    // Kiviniemi (2007/2010) & Duking (2021): 7-day rolling mean vs personal SWC (±0.5 SD)
    const swc = Math.max(4, Math.round(0.5 * hrvSd));
    const swcLow = hrvBase - swc;
    const has7d = !!(hrvFresh && hrv7d && hrvSd >= 4);
    const redHRV = hrvFresh && hrv <= hrvBase * 0.75;
    // Full rest lockout ONLY on sustained 2+ low nights or 7-day rolling mean below SWC (fallback to single-day <84% only if 7d unavailable)
    const lowHRV = has7d
      ? (hrv7d < swcLow || hrvLowStreak >= 2)
      : (hrvFresh && hrv < hrvBase * 0.84);
    // Single noisy night dip while 7-day trend stays healthy -> gentle intensity downshift to Zone 2 instead of full lockout!
    const mildHRV = !!(has7d && !redHRV && !lowHRV && hrv < swcLow);

    const parts = [];
    if (rhr) parts.push(`静息 ${rhr}`);
    if (hrv) parts.push(hrv7d ? `HRV ${hrv}（7日 ${hrv7d} · 平日 ${hrvBase}）` : `HRV ${hrv}${hrvBase ? `（平日 ${hrvBase}）` : ""}`);
    if (sleepH) parts.push(`睡眠 ${sleepH}h`);
    return {
      rhr, rhrBase, rhrFresh, hrv, hrv7d, hrvBase, hrvSd, hrvLowStreak, swcLow, hrvFresh, sleepH, slFresh,
      summary: parts.join(" · "),
      redRHR: rhrFresh && rhr >= 46,
      redHRV,
      lowSleep: slFresh && sleepH < 5.8,
      lowHRV,
      mildHRV
    };
  }

  function makePZPlan(opts) {
    const cur = opts.cur, next = getPZMeta(Math.min(PZ_LIST.length, cur.idx + 1));
    const langTip = cur.pIdx === 0 ? "（勿进教练页、避开德语 DE 版；看不到英文版点左下角头像 → Preferences → Class Languages 开启 English）" : "";
    const progSub = cur.allDone
      ? "两套官方 Power Zone 项目已全部通关，按自己节奏保持稳态燃脂即可。"
      : `当前进度 ${cur.doneInProg} / ${cur.progTotal} 节（每周稳推 2–3 节，打球多的周 1–2 节就很好，约 8–10 周从容通关，绝不照官方 5 周硬追）。`;
    const items = [
      { k: "今天骑这节", v: `${cur.title}（${cur.coach} · ${cur.min} 分钟）`, sub: cur.cue, cur: true },
      { k: "Bike+ 一步找到", v: cur.entry, sub: (opts.extraNote || "状态好就照这节骑；如果今天累了随时点「偏累」或「休息日」，不勉强。") + langTip }
    ];
    if (opts.vitalsLine) {
      items.push({ k: "手表与秤实时状态", v: opts.vitalsLine, sub: "已结合你最新的静息心率、HRV、睡眠和运动负荷排课。" });
    }
    items.push({ k: "慢节奏推进", v: `${cur.progName}（${cur.doneInProg}/${cur.progTotal}）`, sub: progSub });
    return {
      tier: opts.tier || "green",
      tierText: opts.tierText,
      title: cur.title,
      shortLine: opts.shortLine || `${cur.code} · ${cur.coach} · ${cur.min} 分`,
      linkText: "找课 ›",
      ctaText: cur.allDone ? `记下 ${cur.min} 分钟` : `骑完这节 · 推进到 ${cur.numInProg}/${cur.progTotal}`,
      ctaDone: false,
      altAction: opts.altAction || null,
      actionType: "pz_main",
      isPZMain: true,
      pzCls: cur,
      rideMin: cur.min,
      guide: {
        title: `今日推荐课程 · ${cur.code}`,
        items,
        showSyllabus: true,
        canOverridePZ: false
      },
      cardioDone: false,
      puTarget: opts.puTarget != null ? opts.puTarget : 2,
      state: opts.state, sub: opts.sub, bb: opts.bb, pelo: opts.pelo, wk: opts.wk,
      cur, next, daysGap: opts.daysGap, stale: opts.stale || "none", isTravel: false
    };
  }

  function planFor(ymd) {
    const trip = tripOn(ymd), st = getDayState(ymd), bb = st.bb;
    const yestYmd = shiftD(ymd, -1), prev2Ymd = shiftD(ymd, -2);
    const bbY = bbOn(yestYmd), bb2 = bbOn(prev2Ymd);
    const peloY = peloOn(yestYmd), dY = dayE(yestYmd);
    const pelo = peloOn(ymd), wk = weekStats(ymd), dObj = dayE(ymd);
    const wr = watchReadiness(ymd);
    const rhr = wr.rhr || 40;
    const curIdx = getPZIdx();
    const cur = getPZMeta(curIdx);
    const lastPZ = (ST.pz && ST.pz.last) || "";
    const daysGap = lastPZ ? daysDiff(lastPZ, ymd) : 0;
    const recentBB = bbLast7(ymd);
    const stale = staleLevel(daysGap, recentBB, !!trip, rhr);
    const streak = streakBefore(ymd);
    const forcePZ = !!dObj.force_pz;
    const yestMaxBB = !!(bbY && bbY.level === "max");
    const yestHeavyBB = !!(bbY && (bbY.level === "high" || bbY.level === "max"));
    const twoHeavyBB = yestHeavyBB && !!(bb2 && (bb2.level === "high" || bb2.level === "max"));
    let yestPZKind = "";
    if (peloY && peloY.status === "done") {
      if (dY.pz_done != null) {
        const yc = getPZMeta(Number(dY.pz_done));
        if (yc.kind === "test") yestPZKind = "test";
        else if (yc.kind === "hard" || yc.min >= 60) yestPZKind = "hard";
      } else if ((peloY.min || 0) >= 45) {
        yestPZKind = "hard";
      }
    }

    // 0. If today's Power Zone main-line class was ALREADY completed, show serene green confirmation!
    if (dObj.pz_done != null && dObj.pelo === "done") {
      const doneCls = getPZMeta(Number(dObj.pz_done));
      const nextCls = getPZMeta(Math.min(PZ_LIST.length, Number(dObj.pz_done) + 1));
      const nextHint = nextCls.allDone
        ? "全部 47 节 Power Zone 项目已通关！"
        : `下节预告：${nextCls.code} · ${nextCls.title}${nextCls.kind === "test" ? "（留给不打球且睡饱日）" : ""}`;
      return {
        tier: "green",
        tierText: `今日已推主线 · ${doneCls.progShort} ${doneCls.numInProg}/${doneCls.progTotal}`,
        title: doneCls.title,
        shortLine: `${doneCls.code} · ${doneCls.coach} · ${nextHint}`,
        linkText: "课表 ›",
        ctaText: `已完成 ${doneCls.code} ✓`,
        ctaDone: true,
        altAction: null,
        actionType: "pz_main",
        isPZMain: true,
        pzCls: doneCls,
        rideMin: doneCls.min,
        guide: {
          title: `今日主线已完成 · ${doneCls.code}`,
          items: [
            { k: "今日已拿下", v: `${doneCls.title}（${doneCls.coach} · ${doneCls.min} 分）`, sub: "再次点击主按钮可撤销本节打卡。", cur: true },
            { k: "下一节安排", v: nextCls.allDone ? "自由稳态燃脂" : `${nextCls.code} · ${nextCls.title}（${nextCls.coach} · ${nextCls.min} 分）`, sub: nextCls.cue }
          ],
          showSyllabus: true,
          canOverridePZ: false
        },
        cardioDone: true, puTarget: (bb && (bb.level === "high" || bb.level === "max")) ? 1 : 2,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: nextCls, daysGap: 0, stale: "none", isTravel: false
      };
    }

    // 1. Travel mode
    if (trip) {
      return {
        tier: "green", tierText: `旅途中 · ${trip.name}`,
        title: "旅途轻松步行",
        shortLine: `主线暂停在 ${cur.code} · 回来无缝接着骑`,
        linkText: "课表 ›",
        ctaText: pelo ? "今日步行已记 ✓" : "记下今日步行",
        ctaDone: !!pelo,
        altAction: null,
        actionType: "travel",
        isPZMain: false, pzCls: cur, rideMin: 30,
        guide: {
          title: `旅途维持 · ${trip.name}`,
          items: [
            { k: "旅途安排", v: "每天自然步行即算心肺达标，不碰单车不焦虑", cur: true },
            { k: "回来后继续", v: `${cur.progName} · ${cur.code}（${cur.title}）`, sub: "Peloton 新版项目支持暂停顺延，回来直接接上。" }
          ],
          showSyllabus: true, canOverridePZ: false
        },
        cardioDone: !!(pelo || bb), puTarget: 0,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap: 0, stale: "none", isTravel: true
      };
    }

    // 2. Watch Red Auto-Protection (High RHR >= 46 OR severe HRV drop <= 75% of baseline)
    if ((wr.redRHR || wr.redHRV) && !forcePZ && st.mode !== "bb" && st.mode !== "rest") {
      const restDone = !!(pelo && pelo.status === "rest");
      const recDone = !!(pelo && pelo.status === "recovery");
      const redWhy = wr.redRHR ? `静息心率 ${rhr} 偏高` : `HRV 骤降至 ${wr.hrv}（平日 ${wr.hrvBase}）`;
      return {
        tier: "red", tierText: `红档 · ${redWhy}`,
        title: "今晚早睡休养，不上车",
        shortLine: `手表检测到身体恢复压力大 · ${cur.code} 顺延 · 引体免练`,
        linkText: "安排 ›",
        ctaText: restDone ? "已确认休养 ✓" : (recDone ? "已轻踩 15 分 ✓" : "好，今晚休养"),
        ctaDone: restDone || recDone,
        altAction: { label: recDone ? "已轻踩 15 分 ✓" : "若想松腿 · 记 15 分排酸", type: "recovery", active: recDone },
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 0,
        guide: {
          title: "手表自动护体 · 恢复优先",
          items: [
            { k: "为什么自动停骑", v: wr.summary || redWhy, sub: "静息心率偏高或 HRV 明显下滑说明神经与心肺正在恢复期，早睡比硬骑更能保状态，引体今天也免练。", cur: true },
            { k: "若想放松身体", v: "Classes → Stretching → 10 min Lower Body Stretch", sub: "先点右侧 FILTER → Clear；教练选 Hannah Corbin 或 Ben Alldis。" },
            { k: "主线慢慢来", v: `恢复后再接回 ${cur.code}：${cur.title}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal} 节，不赶进度。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: restDone || recDone, puTarget: 0,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
      };
    }

    // 3. Basketball dynamic branches!
    if (st.mode === "bb") {
      const bbStat = (bb && bb.dur) ? `已同步篮球 ${bb.dur} 分${bb.kcal ? ` · ${bb.kcal} 大卡` : ""}` : "";
      if (st.sub === "max") {
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 篮球透支 · 彻底休养",
          title: "彻底休养 · 拉伸早睡",
          shortLine: `10 min Lower Body Stretch (Hannah Corbin) · 引体免练`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认彻底休养 ✓" : "已达标 · 彻底休养 ✓",
          ctaDone: true,
          altAction: null,
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "篮球拼透支 · 今晚彻底休养",
            items: [
              { k: "今晚安排", v: "彻底不上单车、不逼拉杠，补水补蛋白早睡", sub: bbStat || "高强度对抗已经把心肺和腿部负荷拉满，睡一觉恢复最快。", cur: true },
              { k: "可选放松课（10 分钟）", v: "Classes → Stretching → 10 min Lower Body Stretch", sub: "先点右侧 FILTER → Clear；教练首选 Hannah Corbin（也可搜 10 min Foam Rolling: Lower Body）。" },
              { k: "主线顺延", v: `下节主线：${cur.code} · ${cur.title}`, sub: `等过一两天腿缓过来再推进，目前 ${cur.doneInProg}/${cur.progTotal} 节。` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: true, puTarget: 0,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }
      if (st.sub === "high") {
        const recDone = !!(pelo && pelo.status === "recovery");
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 正常全场已满额",
          title: recDone ? "15 min Recovery Ride" : "今晚休养，不上主线",
          shortLine: `${bbStat ? bbStat + " · " : ""}打球已达标，腿紧可做 10 分拉伸`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休养 ✓" : (recDone ? "已轻踩 15 分排酸 ✓" : "已达标 · 今晚休养 ✓"),
          ctaDone: true,
          altAction: { label: recDone ? "取消 15 分排酸" : "腿僵想动 · 记 15 分排酸", type: "recovery", active: recDone },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 15,
          guide: {
            title: "全场篮球日 · 休息与排酸方案",
            items: [
              { k: "默认决定", v: "今天心肺已圆满达标，直接休养早睡最掉脂", sub: bbStat || "不要再叠 Power Zone 主线课，保住双腿弹性；引体轻松拉 1 轮即可。", cur: true },
              { k: "若双腿发紧（二选一）", v: "拉伸：10 min Lower Body Stretch（Ben Alldis / Hannah Corbin）", sub: "或极轻排酸骑：Classes → Cycling → 清空 FILTER → 15 min Recovery Ride（Sam Yo，坐姿阻力 ≤35）。" },
              { k: "主线顺延", v: `${cur.code} · ${cur.title}（${cur.coach} · ${cur.min} 分）`, sub: `留给后面不打球的轻松日推进（当前 ${cur.doneInProg}/${cur.progTotal}）。` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: true, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }
      // st.sub === "light" (轻投/半场): offer easy/short PZ optionally, never force heavy!
      if ((cur.kind === "easy" || cur.kind === "pze") || forcePZ) {
        return makePZPlan({
          tier: "green",
          tierText: "绿档 · 轻投后可顺手推一节",
          cur,
          shortLine: `${cur.code} · ${cur.coach} · ${cur.min} 分坐姿稳骑`,
          extraNote: "今天只轻投/半场耗腿不多，精力够就顺手坐姿推一节；觉得今天够了点下方直接休整。",
          altAction: { label: "今天够了 · 改休整", type: "to_rest", active: false },
          puTarget: 2, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap, stale: "none"
        });
      }
      const restDone = !!(pelo && pelo.status === "rest");
      const lightDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "done"));
      return {
        tier: "yellow", tierText: "黄档 · 轻投护腿 · 大课顺延",
        title: lightDone ? "20 min Low Impact Ride" : "今日休整 · 主线大课顺延",
        shortLine: `下节 ${cur.code}（${cur.kind === "test" ? "FTP测试" : cur.min + "分"}）留给不打球的满血日`,
        linkText: "安排 ›",
        ctaText: restDone ? "已确认休整 ✓" : (lightDone ? "已轻骑 20 分钟 ✓" : "好，今日休整"),
        ctaDone: restDone || lightDone,
        altAction: { label: lightDone ? "取消 20 分轻骑" : "还想出汗 · 记 20 分轻骑", type: "light_ride", active: lightDone, min: 20 },
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 20, altMin: 20,
        guide: {
          title: "轻投半场 · 护腿方案",
          items: [
            { k: "默认决定", v: "今天已经活动开了，直接休整留足腿力", sub: `下节主线是 ${cur.code}（${cur.kind === "test" ? "FTP 测试必须满血做才准" : cur.min + " 分钟长/强课"}），留给不打球日再拿下。`, cur: true },
            { k: "若还想微微出汗（可选）", v: "20 min Low Impact Ride（Sam Yo 或 Matt Wilpers）", sub: "底栏 Classes → Cycling → 清空右侧 FILTER → 20 min · Low Impact，全程坐姿轻转腿。" },
            { k: "主线进度", v: `${cur.progName}（${cur.doneInProg}/${cur.progTotal}）`, sub: "打球和单车本来就是交替着来，不急在一两天。" }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: restDone || lightDone, puTarget: 1,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
      };
    }

    // 4. Tired dynamic branches! (Sleep & rest FIRST, zero pressure!)
    if (st.mode === "tired") {
      if (st.sub === "sore") {
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 腿酸发沉 · 安心休整",
          title: "今晚停骑 · 拉伸或早睡",
          shortLine: `10 min Lower Body Stretch (Ben Alldis) · 引体免练`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休养 ✓" : "好，今晚休养",
          ctaDone: restDone,
          altAction: null,
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "腿酸发沉 · 主动回血方案",
            items: [
              { k: "今晚唯一决定", v: "彻底停骑，给股四头肌和膝关节回血", sub: "腿沉硬顶容易伤膝，今晚养好比多骑一节重要得多；引体今天也免练。", cur: true },
              { k: "可选拉伸课（10 分钟）", v: "Classes → Stretching → 清空 FILTER → 10 min · Lower Body Stretch", sub: "教练首选 Ben Alldis 或 Hannah Corbin，太困直接睡也完全行。" },
              { k: "主线顺延", v: `等腿松快再接回 ${cur.code} · ${cur.title}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}，身体永远第一。` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: restDone, puTarget: 0,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }
      // st.sub === "sleep" (没睡好/只是累): Sleep is ALWAYS default #1!
      if (forcePZ) {
        return makePZPlan({
          tier: "yellow",
          tierText: "黄档 · 轻启推主线",
          cur,
          shortLine: `${cur.code} · ${cur.coach} · ${cur.min} 分量力而行`,
          extraNote: "已为你切回主线，全程听身体感觉，累了随时减阻力。",
          puTarget: 0, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap, stale: "none"
        });
      }
      const restDone = !!(pelo && pelo.status === "rest");
      const lightDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "done"));
      return {
        tier: "yellow", tierText: "黄档 · 累了优先早睡",
        title: lightDone ? "15 min Low Impact Ride" : "今晚早睡回血，不上车",
        shortLine: `人都有累的时候 · 睡饱再续 ${cur.code} · 引体免练`,
        linkText: "安排 ›",
        ctaText: restDone ? "已确认早睡 ✓" : (lightDone ? "已轻骑 15 分钟 ✓" : "好，今晚早睡"),
        ctaDone: restDone || lightDone,
        altAction: { label: lightDone ? "取消 15 分轻骑" : "想解乏 · 记 15 分轻骑", type: "light_ride", active: lightDone, min: 15 },
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 15, altMin: 15,
        guide: {
          title: "没睡好或犯累 · 早睡回血方案",
          items: [
            { k: "默认决定", v: "直接早睡，睡眠不足时硬骑反而升皮质醇、掉不了脂", sub: "点「好，今晚早睡」今日即圆满闭环，引体今天也不强求。", cur: true },
            { k: "若只是精神闷想微微出汗（可选）", v: "15–20 min Low Impact Ride（Sam Yo 或 Matt Wilpers）", sub: "底栏 Classes → Cycling → 清空 FILTER → Low Impact，全程坐姿轻踩当散步。" },
            { k: "主线顺延", v: `睡饱后随时接回 ${cur.code}：${cur.title}（${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}，每周骑 2–3 节就很稳。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: restDone || lightDone, puTarget: 0,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
      };
    }

    // 5. Explicit Rest Day (Always calm green, zero scolding, zero forced pull-ups!)
    if (st.mode === "rest") {
      const restDone = !!(pelo && pelo.status === "rest");
      return {
        tier: "green",
        tierText: "休息日 · 安心回血",
        title: "今日正式休息，不上车",
        shortLine: `休息也是训练的一部分 · 下次轻松日续 ${cur.code}`,
        linkText: "安排 ›",
        ctaText: restDone ? "已确认今日休息 ✓" : "确认今日休息",
        ctaDone: restDone,
        altAction: null,
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 0,
        guide: {
          title: "正式休息日 · 彻底放松",
          items: [
            { k: "今日安排", v: "完全不上单车、引体也免练，把睡眠和饮食守住就是进步", sub: "若久坐腰腿僵，可选做 Classes → Stretching → 10 min Full Body Stretch（Ben Alldis）。", cur: true },
            { k: "Power Zone 慢节奏", v: `${cur.progName}（已完成 ${cur.doneInProg}/${cur.progTotal}）`, sub: `每周稳推 2–3 节（打球多时 1–2 节）就能从容通关；下次精力足再续 ${cur.code}。` }
          ],
          showSyllabus: true, canOverridePZ: false
        },
        cardioDone: restDone, puTarget: 0,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
      };
    }

    // 6. Normal Day: Smart Automatic Watch-Readiness, Fatigue & Basketball-Load Protection (when !forcePZ)
    if (!forcePZ) {
      const restDone = !!(pelo && pelo.status === "rest");
      const recDone = !!(pelo && pelo.status === "recovery");

      // 6-watch. Automatic Watch Fatigue Detection (short sleep < 5.8h or sustained 7d/2-night low HRV)
      if (wr.lowSleep || wr.lowHRV) {
        const why = wr.lowSleep
          ? `手表记昨晚仅睡 ${wr.sleepH}h`
          : (wr.hrv7d ? `HRV 7日均值偏低（${wr.hrv7d} vs 平日 ${wr.hrvBase}）` : `手表 HRV 偏低（${wr.hrv} vs 平日 ${wr.hrvBase}）`);
        return {
          tier: "yellow", tierText: `手表护体 · ${why}`,
          title: recDone ? "15 min Low Impact Ride" : "今晚优先早睡，不上主线",
          shortLine: `${wr.summary} · ${cur.code} 留给睡饱日`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认早睡 ✓" : (recDone ? "已轻骑 15 分 ✓" : "好，今晚早睡"),
          ctaDone: restDone || recDone,
          altAction: { label: "精力足 · 照常推主线", type: "override_pz", active: false },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 15,
          guide: {
            title: "手表自动感应 · 优先恢复",
            items: [
              { k: "数据依据", v: wr.summary, sub: `${why}，系统已自动为你减负，今天早睡恢复比硬骑更有用。`, cur: true },
              { k: "如果实际精力很足", v: `点「精力足 · 照常推主线」即可切回 ${cur.code}：${cur.title}`, sub: "手表只是参考，最终听你自己的真实体感。" },
              { k: "下节主线", v: `${cur.code} · ${cur.title}（${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal} 节。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone || recDone, puTarget: wr.lowSleep ? 0 : 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6a. Yesterday max basketball OR 2 heavy basketball days in a row -> Automatic recovery day
      if (yestMaxBB || twoHeavyBB) {
        const why = twoHeavyBB ? "前两天连打高强度篮球" : "昨天篮球拼到透支";
        return {
          tier: "yellow", tierText: `球后回血 · ${why}`,
          title: recDone ? "15 min Recovery Ride" : "今日休整不上车 · 可 10 分拉伸",
          shortLine: `让双腿彻底回血 · ${cur.code} 明天再推`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休整 ✓" : (recDone ? "已轻踩 15 分排酸 ✓" : "好，今日休整"),
          ctaDone: restDone || recDone,
          altAction: { label: recDone ? "取消 15 分排酸" : "腿松快了 · 记 15 分排酸", type: "recovery", active: recDone },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 15,
          guide: {
            title: "球后自动保护 · 回血日",
            items: [
              { k: "为什么自动安排休息", v: `${why}，今天不该再叠主线`, sub: "高强度篮球对膝踝和肌肉消耗很大，休一天再骑效率更高。", cur: true },
              { k: "可选轻排酸", v: "10 min Lower Body Stretch 或 15 min Recovery Ride（Sam Yo）", sub: "腿完全轻松的话，也可以点下方直接照常骑主线。" },
              { k: "下节主线", v: `${cur.code} · ${cur.title}（${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone || recDone, puTarget: 0,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6b. Yesterday was a tough PZ session (FTP test, hard Zone 4-5, or >=60m ride) -> Auto rest day!
      if (yestPZKind) {
        const why = yestPZKind === "test" ? "昨天刚测完 FTP" : "昨天刚骑完强课大课";
        return {
          tier: "green", tierText: `主动休整 · ${why}`,
          title: "今日主动休整，不上车",
          shortLine: `强课后隔天恢复最涨体能 · ${cur.code} 明天再推`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休整 ✓" : "好，今日休整",
          ctaDone: restDone,
          altAction: { label: "精力足 · 照常推主线", type: "override_pz", active: false },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "强课次日 · 自动隔天休整",
            items: [
              { k: "为什么今天休整", v: `${why}，肌肉和神经需要 24–48 小时吸收训练红利`, sub: "隔天练比连轴转更掉体脂，也更不容易伤腿。", cur: true },
              { k: "精力特别足怎么办", v: `随时可点「精力足 · 照常推主线」切到 ${cur.code}`, sub: "系统默认护着你，但永远尊重你自己的体感。" },
              { k: "下节主线", v: `${cur.code} · ${cur.title}（${cur.coach} · ${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6c. 3 consecutive real workout days (or 4 consecutive any-training days) -> Automatic recovery day!
      if (streak.active >= 3 || streak.any >= 4) {
        const sDays = Math.max(streak.active, streak.any);
        return {
          tier: "green", tierText: `连练 ${sDays} 天 · 主动回血日`,
          title: `连动 ${sDays} 天了，今天主动休整`,
          shortLine: `身体在休息日才长耐力掉体脂 · ${cur.code} 明天再推`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休整 ✓" : "好，今日休整",
          ctaDone: restDone,
          altAction: { label: "精力足 · 照常推主线", type: "override_pz", active: false },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: `连续训练 ${sDays} 天 · 自动休整`,
            items: [
              { k: "为什么今天休整", v: `已经连练 ${sDays} 天（篮球+单车合并计算）`, sub: "连轴转容易越练越累、膝盖发紧；歇一天满血回来掉脂更快。", cur: true },
              { k: "如果今天状态特别好", v: `可一键切回推进 ${cur.code}：${cur.title}`, sub: "完全按你真实体感来，不机械绑架。" },
              { k: "本周进度", v: `本周已打球 ${wk.bbH} 场 · 骑主线 ${wk.pM} 节`, sub: `当前总进度 ${cur.doneInProg}/${cur.progTotal} 节。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6d. Weekly total cap reached (Basketball + Cycling combined!) -> Automatic rest day!
      const hitWeekCap = wk.hard >= 5 || wk.realPM >= 4 || (wk.bbH >= 2 && wk.pM >= 2 && (cur.kind === "test" || cur.kind === "hard" || cur.kind === "pze_long"));
      if (hitWeekCap) {
        return {
          tier: "green", tierText: `本周已练够（球${wk.bbH} · 骑${wk.pM}）`,
          title: "本周运动量已满，放心休整",
          shortLine: `你既打球又骑车，每周 4–5 场已超额达标 · ${cur.code} 留给下周`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休整 ✓" : "好，今日休整",
          ctaDone: restDone,
          altAction: { label: "状态极好 · 照常推主线", type: "override_pz", active: false },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "本周配额已满 · 放心休整",
            items: [
              { k: "为什么今天不催你骑", v: `本周已完成 ${wk.bbH} 场篮球 + ${wk.pM} 节主线骑行`, sub: "对每周打球的人来说，单车每周 2–3 节、总有氧 4–5 场就是最科学的黄金节奏。", cur: true },
              { k: "可选微动", v: "出门散步或 10 分钟拉伸即可，彻底放松", sub: "若今天特别想骑车听《锵锵》，点下方随时可推下一节。" },
              { k: "下周衔接", v: `${cur.code} · ${cur.title}（${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal} 节。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6e. Yesterday was normal full basketball AND next PZ class is heavy/long/test -> Protect legs!
      if (yestHeavyBB && (cur.kind === "test" || cur.kind === "hard" || cur.kind === "pze_long")) {
        return {
          tier: "yellow", tierText: "球后护腿 · 大课顺延一天",
          title: recDone ? "15 min Recovery Ride" : "今日休整或 15 分轻排酸",
          shortLine: `昨天刚打完全场 · ${cur.code}（${cur.kind === "test" ? "FTP测试" : cur.min + "分"}）留给明天满血做`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休整 ✓" : (recDone ? "已轻踩 15 分排酸 ✓" : "好，今日休整"),
          ctaDone: restDone || recDone,
          altAction: { label: recDone ? "取消 15 分排酸" : "想松腿 · 记 15 分排酸", type: "recovery", active: recDone },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 15,
          guide: {
            title: "全场球后次日 · 护腿方案",
            items: [
              { k: "今日安排", v: "默认休整回血，或轻踩 15 分钟 Recovery 排酸", sub: `下节主线 ${cur.code} 是 ${cur.kind === "test" ? "FTP 测试（满血测才准）" : cur.min + " 分钟强/长课"}，不放在全场篮球第二天。`, cur: true },
              { k: "若想轻踩排酸（可选）", v: "Classes → Cycling → 清空 FILTER → 15 min Recovery Ride（Sam Yo）", sub: "全程坐姿低阻力，配《锵锵三人行》放松双腿。" },
              { k: "腿完全不酸怎么办", v: `可点下方一键照常推进 ${cur.code}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal} 节。` }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: restDone || recDone, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6f. Seiler (2010) / Stoggl (2014) 80/20 Polarized Guard:
      // 2+ intense basketball games this week already fill the 20% Zone 4-5 quota -> auto-swap hard/test PZ ride to steady Zone 2!
      const z2Done = !!(pelo && pelo.status === "done");
      if (wk.bbH >= 2 && (cur.kind === "hard" || cur.kind === "test")) {
        return {
          tier: "green", tierText: `80/20 极化 · 本周已打 ${wk.bbH} 场球换 Zone 2`,
          title: "30 min Zone 2 Power Zone Endurance",
          shortLine: `篮球已吃满高强度配额 · 今骑纯 Zone 2 稳态燃脂护睡眠`,
          linkText: "安排 ›",
          ctaText: z2Done ? "已骑 30 分 Zone 2 ✓" : "骑完 30 分 Zone 2",
          ctaDone: z2Done,
          altAction: { label: `精力极足 · 照常骑 ${cur.code}`, type: "override_pz", active: false },
          actionType: "z2_swap",
          isPZMain: false, pzCls: cur, rideMin: 30,
          guide: {
            title: "80/20 极化调度 · 稳态燃脂护睡眠",
            items: [
              { k: "为什么自动换 Zone 2", v: `本周已有 ${wk.bbH} 场高强度篮球，已吃满全周 20% 高强度配额`, sub: "Seiler 80/20 耐力研究证实：多球周再叠高强度间歇单车，掉脂变慢且容易诱发失眠；换成纯 Zone 2 稳态燃脂效率最高。", cur: true },
              { k: "Bike+ 一步找到", v: "Classes → Cycling → 清空 FILTER → 30 min Power Zone Endurance（Sam Yo 或 Matt Wilpers）", sub: "全程只踩 Zone 2 轻松聊天心率，边听《锵锵》边稳掉体脂。" },
              { k: "主线顺延", v: `${cur.code} · ${cur.title} 留给下周少打球日满血推`, sub: "如果今天特别想推主线，点下方随时一键切回。" }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: z2Done, puTarget: puStage().targetRounds || 2,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }

      // 6g. Kiviniemi (2007/2010) Single-Night Mild HRV Dip (7-day mean still healthy!):
      // Never lock out a full day over single-night noise; smoothly downshift hard/test ride to Zone 2!
      if (wr.mildHRV && (cur.kind === "hard" || cur.kind === "test")) {
        return {
          tier: "yellow", tierText: `单晚 HRV 略低（7日均 ${wr.hrv7d} 正常）· 降档 Zone 2`,
          title: "30 min Zone 2 Power Zone Endurance",
          shortLine: `${wr.summary} · 单晚微跌不硬停，改轻松稳态燃脂`,
          linkText: "安排 ›",
          ctaText: z2Done ? "已骑 30 分 Zone 2 ✓" : "骑完 30 分 Zone 2",
          ctaDone: z2Done,
          altAction: { label: `体感极佳 · 照常骑 ${cur.code}`, type: "override_pz", active: false },
          actionType: "z2_swap",
          isPZMain: false, pzCls: cur, rideMin: 30,
          guide: {
            title: "7 日 HRV 趋势护航 · 温和降档",
            items: [
              { k: "为什么只降档不硬停", v: wr.summary, sub: "单晚 HRV 波动常受晚餐或睡姿影响，你近 7 天均值仍稳在正常带，所以把强课温柔换成纯 Zone 2 稳态，既不中断节奏也防过劳。", cur: true },
              { k: "Bike+ 一步找到", v: "Classes → Cycling → 清空 FILTER → 30 min Power Zone Endurance（Sam Yo 或 Matt Wilpers）", sub: "全程轻松踩在 Zone 2，下节主线留给明天。" }
            ],
            showSyllabus: true, canOverridePZ: true
          },
          cardioDone: z2Done, puTarget: Math.min(2, puStage().targetRounds || 2),
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, stale: "none", isTravel: false
        };
      }
    }

    // Default Normal Day (Well-rested & under weekly cap): Smoothly advance next PZ class!
    const tier = (stale === "remind" || stale === "gentle") ? "yellow" : "green";
    const tierText = stale === "remind"
      ? "主线歇了两周 · 轻松接回"
      : (stale === "gentle"
        ? `主线歇了 ${daysGap} 天 · 顺手续一节`
        : (cur.kind === "test"
          ? "绿档 · 满血测 FTP"
          : (yestHeavyBB
            ? "绿档 · 球后可轻推主线"
            : `绿档 · 本周主线 ${wk.pM}/${wk.pzGoal} 节`)));
    return makePZPlan({
      tier, tierText, cur,
      vitalsLine: wr.summary,
      extraNote: cur.kind === "test"
        ? "今天没打球且状态正常，正好一口气完成 10 分热身 + 20 分 FTP 测试，锁死你的 7 档专属功率区。"
        : (yestHeavyBB
          ? "昨天打完球但今天这节是轻/稳态课，腿轻松就顺手推一节；觉得累点下方直接改休整。"
          : `每周稳推 ${wk.pzGoal} 节左右就很够（结合你打篮球的量），今天精力正常就照这节骑。`),
      altAction: yestHeavyBB ? { label: "腿还有点累 · 改休整", type: "to_rest", active: false } : null,
      puTarget: puStage().targetRounds || 2, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap, stale
    });
  }

  function puStage() {
    const b = ST.pu_best || 1;
    if (b <= 1) return { idx: 0, name: "阶段一 · 门框单杠", title: "1 徒手 · 2 黑带慢放", sub: "微仰防碰头 · 单膝挂黑带 4 秒慢放", short: "1 徒手+黑带", defStrict: 1, neg: 2, targetRounds: 2 };
    if (b === 2) return { idx: 1, name: "阶段二 · 门框单杠", title: "2 徒手 · 1 红带慢放", sub: "前 2 下直上不晃 · 末下红带 4 秒慢放", short: "2 徒手+红带", defStrict: 2, neg: 1, targetRounds: 2 };
    if (b === 3) return { idx: 2, name: "阶段三 · 不力竭冲 5 连", title: "2 个留余力 · 每日 3 轮", sub: "每轮留 1 下余力不力竭 · 隔 2 小时拉 3 轮攒 6 下 · 每两周测 4 连", short: "2个×3轮", defStrict: 2, neg: 0, targetRounds: 3 };
    if (b === 4) return { idx: 2, name: "阶段三 · 不力竭冲 5 连", title: "3 个留余力 · 每日 3 轮", sub: "每轮留 1 下余力不力竭 · 隔 2 小时拉 3 轮攒 9 下 · 每两周测 5 连", short: "3个×3轮", defStrict: 3, neg: 0, targetRounds: 3 };
    return { idx: 3, name: "阶段四 · 目标达成", title: `轻松 ${b} 连`, sub: "每日 2 轮从容维稳", short: `轻松 ${b} 连`, defStrict: Math.min(5, b), neg: 0, targetRounds: 2 };
  }
  function puCooldown(day, target) {
    const rs = (day && day.pu) || [];
    const tgt = Math.max(1, target || 2);
    if (rs.length >= 1 && rs.length < tgt) {
      const lastTs = rs[rs.length - 1] && rs[rs.length - 1][2];
      const nextN = rs.length + 1;
      if (lastTs) {
        const t1 = fmtEpochPT(lastTs), t2 = fmtEpochPT(lastTs + 7200);
        return (Math.floor(Date.now() / 1000) < lastTs + 7200)
          ? `第 ${rs.length} 轮 ${t1} 已拉 · ${t2} 后第 ${nextN} 轮`
          : `第 ${rs.length} 轮 ${t1} 已拉 · 可拉第 ${nextN} 轮`;
      }
      return `第 ${rs.length} 轮已拉 · 隔 2 小时第 ${nextN} 轮`;
    }
    if (rs.length >= tgt) {
      const tsEnd = rs[rs.length - 1] && rs[rs.length - 1][2];
      return tsEnd ? `今日 ${rs.length} 轮已于 ${fmtEpochPT(tsEnd)} 收工` : `今日 ${rs.length} 轮已收工`;
    }
    return "";
  }
  function syncPUDefault() { PU_IN = puStage().defStrict; }

  function latestWB() {
    const arr = ST.wb || [];
    let lbf = null, lwt = null, bbf = null, lWaist = null;
    for (const r of arr) {
      if (r[1]) lwt = r;
      if (r[2] && r[2] > 5) { lbf = r; if (!bbf || r[2] < bbf[2]) bbf = r; }
      if (r.length > 4 && r[4] && r[4] >= 50 && r[4] <= 150) lWaist = r;
    }
    const wts = arr.filter(r => r[1]).slice(-5);
    const avgWt = wts.length ? +(wts.reduce((s, r) => s + r[1], 0) / wts.length).toFixed(1) : null;
    const bfs = arr.filter(r => r[2] && r[2] > 5);
    let avgBf = null;
    if (bfs.length) {
      const lastT = Date.parse(bfs[bfs.length - 1][0] + "T12:00:00Z");
      const win = [];
      for (let i = bfs.length - 1; i >= 0; i--) {
        const dt = (lastT - Date.parse(bfs[i][0] + "T12:00:00Z")) / 86400000;
        if (dt <= 14 || win.length < 2) win.push(bfs[i][2]);
        if (win.length >= 4) break;
      }
      avgBf = +(win.reduce((s, v) => s + v, 0) / win.length).toFixed(1);
    }
    return { lbf, lwt, bbf, avgWt, avgBf, lWaist };
  }

  function positionSubBar(immediate) {
    const wrap = ge("zb-subtabs"), bar = ge("zb-sub-bar");
    if (!wrap || !bar || !wrap.offsetWidth) return;
    const btn = wrap.querySelector ? wrap.querySelector(`.zb-subtab[data-zbt="${SUBTAB}"]`) : null;
    if (!btn || !btn.offsetWidth) return;
    if (immediate) bar.style.transition = "none";
    bar.style.width = btn.offsetWidth + "px";
    bar.style.transform = `translateX(${btn.offsetLeft || 0}px)`;
    if (immediate) { void bar.offsetWidth; bar.style.transition = ""; }
  }

  function applyBodyHead(today, wb, pt) {
    const bfEl = ge("zb-bf-big"), wtEl = ge("zb-wt-big"), ctxEl = ge("zb-bctx");
    if (pt) {
      if (bfEl) { bfEl.classList.add("scrub"); bfEl.innerHTML = `${pt.bf !== null ? pt.bf.toFixed(1) : "--"}<span class="zb-stat-unit">%</span>`; }
      if (wtEl) { wtEl.classList.add("scrub"); wtEl.innerHTML = `${pt.wt !== null ? pt.wt.toFixed(1) : "--"}<span class="zb-stat-unit">kg</span>`; }
      if (ctxEl) ctxEl.textContent = pt.d;
      if (ge("zb-bf-sub")) ge("zb-bf-sub").textContent = fmtCn(pt.d);
      if (ge("zb-wt-sub")) ge("zb-wt-sub").textContent = pt.ma !== null ? `均线 ${pt.ma.toFixed(1)}${METRIC === "bf" ? "%" : " kg"}` : "";
      return;
    }
    if (bfEl) bfEl.classList.remove("scrub");
    if (wtEl) wtEl.classList.remove("scrub");
    if (ctxEl) ctxEl.textContent = "GE 体脂 · 近均趋势";
    const targetBf = (ST.targets && ST.targets.bf_ge) || 14.0;
    if (wb.lbf) {
      const dispBf = wb.avgBf != null ? wb.avgBf : wb.lbf[2];
      if (bfEl) bfEl.innerHTML = `${dispBf.toFixed(1)}<span class="zb-stat-unit">%</span>`;
      const waistTag = wb.lWaist ? ` · 腰围 ${wb.lWaist[4].toFixed(1)}cm` : "";
      if (ge("zb-bf-sub")) ge("zb-bf-sub").textContent = `单次 ${wb.lbf[2].toFixed(1)}% · 两年低 ${wb.bbf ? wb.bbf[2].toFixed(1) : wb.lbf[2].toFixed(1)}%${waistTag}`;
      const rem = Math.max(0, dispBf - targetBf);
      if (ge("zb-pace")) ge("zb-pace").textContent = rem > 0 ? `近均距 14% 剩 ${rem.toFixed(1)}%` : "已达 14% 目标";
    }
    if (wb.lwt) {
      if (wtEl) wtEl.innerHTML = `${(wb.avgWt || wb.lwt[1]).toFixed(1)}<span class="zb-stat-unit">kg</span>`;
      if (ge("zb-wt-sub")) ge("zb-wt-sub").textContent = `单次 ${wb.lwt[1].toFixed(1)} kg`;
    }
  }

  function renderChart() {
    const wrap = ge("zb-chart");
    if (!wrap) return;
    const today = todayYmd(), cut = shiftD(today, -95);
    const isBF = METRIC === "bf";
    let raw = (ST.wb || []).map(r => ({ d: r[0], wt: r[1] || null, bf: (r[2] && r[2] > 5) ? r[2] : null, v: isBF ? r[2] : r[1] })).filter(p => p.v && p.v > 5);
    if (RANGE === "90") {
      const p90 = raw.filter(p => p.d >= cut);
      if (p90.length >= 2) raw = p90;
    }
    if (raw.length < 2) {
      CHART_PTS = [];
      wrap.innerHTML = `<div style="height:150px;display:flex;align-items:center;justify-content:center;color:var(--ink-3);font-size:13px;">多记两次即绘出曲线</div>`;
      return;
    }
    for (let i = 0; i < raw.length; i++) {
      const ti = Date.parse(raw[i].d + "T12:00:00Z");
      const win = [];
      for (let j = i; j >= 0; j--) {
        if ((ti - Date.parse(raw[j].d + "T12:00:00Z")) / 86400000 <= 14 || win.length < 2) win.push(raw[j].v);
        if (win.length >= 4) break;
      }
      raw[i].ma = +(win.reduce((a, b) => a + b, 0) / win.length).toFixed(2);
    }
    const vals = raw.map(p => p.v);
    const wb = latestWB();
    const targetBf = (ST.targets && ST.targets.bf_ge) || 14.0;
    const estWt = (wb.lwt && wb.lbf) ? +((wb.lwt[1] * (1 - wb.lbf[2] / 100)) / (1 - targetBf / 100)).toFixed(1) : 77.5;
    const target = isBF ? targetBf : estWt;
    const mn = Math.min(...vals, target) - (isBF ? 0.8 : 1.0);
    const mx = Math.max(...vals, target) + (isBF ? 0.8 : 1.0);
    const spanV = Math.max(1, mx - mn);
    const W = 360, H = 168, pL = 4, pR = 36, pT = 16, pB = 22;
    const t0 = Date.parse(raw[0].d + "T12:00:00Z"), t1 = Date.parse(raw[raw.length - 1].d + "T12:00:00Z"), spanT = Math.max(86400000, t1 - t0);
    const xy = raw.map(p => ({
      x: +(pL + ((Date.parse(p.d + "T12:00:00Z") - t0) / spanT) * (W - pL - pR)).toFixed(1),
      y: +(pT + (1 - (p.v - mn) / spanV) * (H - pT - pB)).toFixed(1),
      yMa: +(pT + (1 - (p.ma - mn) / spanV) * (H - pT - pB)).toFixed(1),
      d: p.d, v: p.v, wt: p.wt, bf: p.bf, ma: p.ma
    }));
    CHART_PTS = xy;
    const ty = +(pT + (1 - (target - mn) / spanV) * (H - pT - pB)).toFixed(1);
    const pathD = xy.map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.y}`).join(" ");
    const maD = xy.map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.yMa}`).join(" ");
    const first = xy[0], last = xy[xy.length - 1];
    wrap.innerHTML = `<svg class="zb-chart-svg" id="zb-chart-svg" viewBox="0 0 ${W} ${H}">
      <line x1="${pL}" y1="${ty}" x2="${W - pR}" y2="${ty}" stroke="var(--moss)" stroke-opacity="0.4" stroke-width="1" stroke-dasharray="3 4"/>
      <text x="${W - pR + 5}" y="${ty + 3.5}" fill="var(--moss)" font-size="10.5" font-family="sans-serif">${target}${isBF ? "%" : ""}</text>
      <path d="${maD}" fill="none" stroke="var(--moss)" stroke-opacity="0.42" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="${pathD}" fill="none" stroke="var(--sumi)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
      ${xy.map(p => `<circle cx="${p.x}" cy="${p.y}" r="2.1" fill="var(--washi)" stroke="var(--sumi)" stroke-width="1.2"/>`).join("")}
      <circle cx="${last.x}" cy="${last.y}" r="3.6" fill="var(--moss)"/>
      <line id="zb-c-cur" x1="0" y1="${pT - 4}" x2="0" y2="${H - pB + 2}" stroke="var(--moss)" stroke-opacity="0.55" stroke-width="1" stroke-dasharray="2 3" style="display:none;"/>
      <circle id="zb-c-halo" cx="0" cy="0" r="6" fill="var(--moss)" fill-opacity="0.18" style="display:none;"/>
      <circle id="zb-c-foc" cx="0" cy="0" r="3.6" fill="var(--moss)" stroke="var(--washi)" stroke-width="1.5" style="display:none;"/>
      <text x="${pL}" y="${H - 4}" fill="var(--ink-3)" font-size="10.5" font-family="sans-serif">${first.d.slice(2, 10)}</text>
      <text x="${W - pR}" y="${H - 4}" text-anchor="end" fill="var(--ink-3)" font-size="10.5" font-family="sans-serif">${last.d.slice(2, 10)}</text>
    </svg>`;
  }

  function renderDial() {
    const ws = ge("zb-dwt-slot"), bs = ge("zb-dbf-slot");
    if (ws && (!ws.querySelector || !ws.querySelector("input"))) ws.innerHTML = `<button class="zb-dial-val" id="zb-dwt-val" onclick="ZB.editDial('wt')">${D_WT.toFixed(1)}</button>`;
    if (bs && (!bs.querySelector || !bs.querySelector("input"))) bs.innerHTML = `<button class="zb-dial-val" id="zb-dbf-val" onclick="ZB.editDial('bf')" style="${D_SKIP_BF ? "opacity:0.35;" : ""}">${D_SKIP_BF ? "--" : D_BF.toFixed(1)}</button>`;
    const tw = ge("zb-dwt-ticks"), tb = ge("zb-dbf-ticks");
    if (tw) tw.style.backgroundPosition = `${D_WT_OFF.toFixed(1)}px 0`;
    if (tb) tb.style.backgroundPosition = `${D_BF_OFF.toFixed(1)}px 0`;
    const sb = ge("zb-dskip-btn");
    if (sb) { sb.textContent = D_SKIP_BF ? "改为同时记体脂" : "仅记体重"; sb.className = "zb-btn-quiet" + (D_SKIP_BF ? " active" : ""); }
  }

  function playChime(freq) {
    if (!PACER_SND) return;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      if (!ACTX) ACTX = new Ctx();
      if (ACTX.state === "suspended") ACTX.resume();
      const now = ACTX.currentTime, o = ACTX.createOscillator(), g = ACTX.createGain();
      o.type = "sine"; o.frequency.setValueAtTime(freq || 528, now);
      g.gain.setValueAtTime(0.001, now);
      g.gain.exponentialRampToValueAtTime(0.08, now + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
      o.connect(g); g.connect(ACTX.destination);
      o.start(now); o.stop(now + 0.38);
    } catch (e) {}
  }
  async function grabWL() { try { if (navigator && "wakeLock" in navigator && !PACER_WL) PACER_WL = await navigator.wakeLock.request("screen"); } catch (e) {} }
  function dropWL() { try { if (PACER_WL) { PACER_WL.release().catch(() => {}); PACER_WL = null; } } catch (e) {} }

  function stopPacer(withToast) {
    PACER_ON = false;
    if (PACER_RAF) { cancelAnimationFrame(PACER_RAF); PACER_RAF = null; }
    dropWL();
    const box = ge("zb-pacer"); if (box) box.classList.remove("open");
    const btn = ge("zb-pacer-btn"); if (btn) { btn.textContent = "4 秒慢放节拍"; btn.className = "zb-btn-quiet"; }
    if (withToast) toast("已停止慢放节拍");
  }

  function startPacer() {
    PACER_ON = true;
    const box = ge("zb-pacer"); if (box) box.classList.add("open");
    const btn = ge("zb-pacer-btn"); if (btn) { btn.textContent = "节拍进行中"; btn.className = "zb-btn-quiet active"; }
    grabWL();
    const reps = Math.max(1, 3 - PU_IN);
    const steps = [{ kind: "prep", dur: 3000, label: "准备抓杠 · 顶住下巴" }];
    for (let i = 1; i <= reps; i++) {
      steps.push({ kind: "down", dur: 4000, label: `匀速慢放 · 第 ${i} / ${reps} 次` });
      if (i < reps) steps.push({ kind: "rest", dur: 4000, label: "轻落换气 · 准备下一次" });
    }
    let idx = 0, t0 = performance.now(), lastC = -1;
    const arc = ge("zb-pacer-arc"), num = ge("zb-pacer-num"), ph = ge("zb-pacer-phase");
    function tick(now) {
      if (!PACER_ON) return;
      const cur = steps[idx];
      if (lastC !== idx) { lastC = idx; playChime(cur.kind === "down" ? 440 : 528); }
      const el = now - t0, rat = Math.min(1, el / cur.dur), rem = Math.max(0, (cur.dur - el) / 1000);
      if (ph) ph.textContent = cur.label;
      if (arc) {
        const pct = cur.kind === "down" ? Math.max(0, (1 - rat) * 100) : rat * 100;
        arc.setAttribute("stroke", cur.kind === "down" ? "var(--moss)" : (cur.kind === "prep" ? "var(--ochre)" : "var(--ink-3)"));
        arc.setAttribute("stroke-dasharray", `${pct.toFixed(1)} 100`);
      }
      if (num) num.textContent = String(Math.max(1, Math.ceil(rem)));
      if (el >= cur.dur) {
        idx++;
        if (idx >= steps.length) {
          playChime(660);
          if (arc) { arc.setAttribute("stroke", "var(--moss)"); arc.setAttribute("stroke-dasharray", "100 100"); }
          if (num) num.textContent = "✓";
          if (ph) ph.textContent = "慢放完成，已记入本轮";
          PACER_ON = false; dropWL();
          window.ZB.logPU();
          setTimeout(() => { const b = ge("zb-pacer"); if (b && !PACER_ON) b.classList.remove("open"); }, 1100);
          return;
        }
        t0 = now;
      }
      PACER_RAF = requestAnimationFrame(tick);
    }
    PACER_RAF = requestAnimationFrame(tick);
  }

  function render() {
    const today = todayYmd();
    LAST_DAY = today;
    const plan = planFor(today), day = dayE(today), stg = puStage(), wb = latestWB();
    const puDone = (day.pu || []).length;
    const maxR = stg.targetRounds || 2;
    const dietDone = !!day.diet;
    const resDone = !!day.res;

    const dl = ge("zb-date-lbl"); if (dl) dl.textContent = fmtCn(today);

    const tt = ge("zb-tier-txt");
    if (tt) { tt.textContent = plan.tierText; tt.className = "zb-tier " + (plan.tier === "red" ? "red" : plan.tier === "yellow" ? "yellow" : "green"); }

    const cur = plan.cur;
    const staleCls = plan.stale === "remind" ? " urgent" : (plan.stale === "gentle" ? " warn" : "");
    const pzb = ge("zb-pz-btn");
    if (pzb && cur) {
      pzb.textContent = cur.allDone ? "PZ 47/47 通关 ›" : `${cur.progShort} ${cur.doneInProg}/${cur.progTotal} ›`;
      pzb.className = "zb-pz-btn" + staleCls;
    }
    const pzf = ge("zb-pz-fill");
    if (pzf && cur) {
      pzf.style.width = `${cur.pct}%`;
      pzf.className = "zb-pz-fill" + staleCls;
    }

    if (ge("zb-title")) ge("zb-title").textContent = plan.title;
    if (ge("zb-pelo-short")) ge("zb-pelo-short").textContent = plan.shortLine || "";
    const plk = ge("zb-pelo-link"), prw = ge("zb-pelo-row");
    if (plk) { plk.style.display = plan.guide ? "inline" : "none"; plk.textContent = plan.linkText || "找课 ›"; }
    if (prw) prw.style.pointerEvents = plan.guide ? "auto" : "none";

    // Dynamic 2-level state bar (hide during active travel)
    const stb = ge("zb-state-block");
    if (stb) stb.style.display = plan.isTravel ? "none" : "flex";
    const stMap = [
      ["zb-st-normal", "normal", ""],
      ["zb-st-bb", "bb", " is-bb"],
      ["zb-st-tired", "tired", " is-tired"],
      ["zb-st-rest", "rest", " is-rest"]
    ];
    for (const [id, k, cls] of stMap) {
      const el = ge(id);
      if (el) el.className = "zb-state-btn" + (plan.state === k ? (" active" + cls) : "");
    }
    const subBar = ge("zb-substate-bar");
    if (subBar) {
      if (plan.state === "bb") {
        const opts = [
          ["light", "轻投半场", "is-green"],
          ["high", "正常全场", "is-red"],
          ["max", "拼到透支", "is-red"]
        ];
        subBar.className = "zb-substate-bar open is-bb";
        subBar.innerHTML = opts.map(([k, lbl, c]) => `<button type="button" class="zb-substate-btn${plan.sub === k ? " active " + c : ""}" onclick="ZB.setState('bb','${k}')">${lbl}</button>`).join("");
      } else if (plan.state === "tired") {
        const opts = [
          ["sleep", "没睡好", "is-ochre"],
          ["sore", "腿酸发沉", "is-red"]
        ];
        subBar.className = "zb-substate-bar open is-tired";
        subBar.innerHTML = opts.map(([k, lbl, c]) => `<button type="button" class="zb-substate-btn${plan.sub === k ? " active " + c : ""}" onclick="ZB.setState('tired','${k}')">${lbl}</button>`).join("");
      } else {
        subBar.className = "zb-substate-bar";
        subBar.innerHTML = "";
      }
    }

    const mb = ge("zb-main-btn");
    if (mb) {
      mb.textContent = plan.ctaText;
      mb.className = "zb-btn-primary" + (plan.ctaDone ? " is-done" : "");
    }
    const ab = ge("zb-alt-btn"), wt = ge("zb-week-txt");
    if (ab && wt) {
      if (plan.altAction && plan.altAction.label) {
        ab.style.display = "inline-flex";
        ab.textContent = plan.altAction.label;
        ab.className = "zb-btn-quiet" + (plan.altAction.active ? " active" : "");
        wt.style.display = "none";
      } else {
        ab.style.display = "none";
        wt.style.display = "inline";
        wt.textContent = `本周 球${plan.wk.bbH} · 骑${plan.wk.pM} · 引体${plan.wk.puR}`;
      }
    }

    const cd = puCooldown(day, plan.puTarget);
    if (ge("zb-pu-hint")) {
      if (plan.isTravel) ge("zb-pu-hint").textContent = "旅途免练";
      else if (plan.puTarget === 0) ge("zb-pu-hint").textContent = puDone > 0 ? `随手已拉 ${puDone} 轮` : "今天免练 · 想拉随意";
      else ge("zb-pu-hint").textContent = `${stg.short} · ${puDone}/${plan.puTarget} 轮`;
    }
    const pd = ge("zb-pu-dots");
    if (pd) {
      if (plan.isTravel) pd.innerHTML = `<span style="font-size:12.5px;color:var(--ink-3);">休</span>`;
      else if (plan.puTarget === 0) {
        pd.innerHTML = `<button type="button" class="zb-round-dot ${puDone >= 1 ? "done" : ""}" style="${puDone >= 1 ? "" : "opacity:0.55;"}" onclick="ZB.quickPU(1)">${puDone >= 1 ? "✓" : "1"}</button>`;
      } else {
        let h = "";
        for (let i = 1; i <= plan.puTarget; i++) h += `<button type="button" class="zb-round-dot ${puDone >= i ? "done" : ""}" onclick="ZB.quickPU(${i})">${puDone >= i ? "✓" : i}</button>`;
        pd.innerHTML = h;
      }
    }
    const pTargetG = Math.round(((wb.avgWt || (wb.lwt && wb.lwt[1]) || 81.0) * 1.8) / 5) * 5;
    if (ge("zb-diet-hint")) ge("zb-diet-hint").textContent = dietDone ? `今日已稳住（~${pTargetG}g）›` : `蛋白 ~${pTargetG}g · 晚未爆碳 ›`;
    const db = ge("zb-diet-btn");
    if (db) { db.className = "zb-tap-check" + (dietDone ? " done" : ""); db.textContent = dietDone ? "已达标 ✓" : "记达标"; }

    // Tab 2: Pullup + Optional 5-Min Full-Body Resistance Guard (Schoenfeld 2016 / Longland 2016)
    if (ge("zb-pu-pr")) ge("zb-pu-pr").textContent = `最高 ${ST.pu_best || 1} / 5`;
    if (ge("zb-pu-eyebrow")) ge("zb-pu-eyebrow").textContent = `${stg.name} · ${puDone}/${maxR} 轮`;
    if (ge("zb-pu-title")) ge("zb-pu-title").textContent = stg.title;
    if (ge("zb-pu-sub")) ge("zb-pu-sub").textContent = cd || stg.sub;
    if (ge("zb-pu-val")) ge("zb-pu-val").textContent = String(PU_IN);
    const negN = stg.neg > 0 ? Math.max(0, 3 - PU_IN) : 0;
    if (ge("zb-pu-neg")) ge("zb-pu-neg").textContent = negN > 0 ? `补 ${negN} 次单膝黑带 4 秒慢放` : (maxR >= 3 ? "留 1 下余力不力竭 · 隔 2 小时分轮拉" : "纯徒手 · 直上直下不甩腿");
    const plb = ge("zb-pu-log"), pub = ge("zb-pu-undo");
    if (plb && pub) {
      pub.style.display = puDone > 0 ? "inline-flex" : "none";
      if (puDone >= maxR) { plb.textContent = `今日 ${maxR} 轮已满 ✓`; plb.className = "zb-btn-primary is-done"; }
      else { plb.textContent = `记下第 ${puDone + 1} 轮`; plb.className = "zb-btn-primary"; }
    }
    if (ge("zb-res-hint")) ge("zb-res-hint").textContent = `本周 ${plan.wk.res || 0}/2 次 · 俯卧撑+自重深蹲`;
    const rb = ge("zb-res-btn");
    if (rb) { rb.className = "zb-tap-check" + (resDone ? " done" : ""); rb.textContent = resDone ? "今日已补 ✓" : "记 5 分钟"; }
    const lad = ge("zb-pu-ladder");
    if (lad) {
      const stages = ["黑带", "红带", "多组冲5", "5连"];
      lad.innerHTML = stages.map((lbl, i) => `<div class="zb-ladder-step ${i < stg.idx ? "past" : (i === stg.idx ? "cur" : "")}"><div class="zb-ladder-bar"></div><div class="zb-ladder-lbl">${lbl}</div></div>`).join("");
    }

    // Tab 3: Body Fat
    SCRUB_IDX = -1;
    applyBodyHead(today, wb, null);
    if (ge("zb-m-bf")) ge("zb-m-bf").className = "zb-btn-quiet" + (METRIC === "bf" ? " active" : "");
    if (ge("zb-m-wt")) ge("zb-m-wt").className = "zb-btn-quiet" + (METRIC === "wt" ? " active" : "");
    if (ge("zb-r-90")) ge("zb-r-90").className = "zb-btn-quiet" + (RANGE === "90" ? " active" : "");
    if (ge("zb-r-all")) ge("zb-r-all").className = "zb-btn-quiet" + (RANGE === "all" ? " active" : "");
    if (ge("zb-wrem")) {
      const wStr = wb.lWaist ? ` · 腰围 ${wb.lWaist[4].toFixed(1)}cm` : "";
      ge("zb-wrem").textContent = (wb.lbf ? `上次 ${wb.lbf[0].slice(5)}` : "尚未记录") + wStr;
    }
    renderChart();

    // Tab 4: Ledger
    const kp = ge("zb-kpis");
    const vt = ST.vitals || {};
    const hrvSub = vt.hrv_7d ? `HRV · 7日 ${vt.hrv_7d}` : "HRV";
    if (kp) {
      kp.innerHTML =
        `<div><div class="zb-kpi-v">${vt.rhr || "--"}</div><div class="zb-kpi-l">静息心率</div></div>` +
        `<div><div class="zb-kpi-v">${vt.hrv || "--"}</div><div class="zb-kpi-l">${hrvSub}</div></div>` +
        `<div><div class="zb-kpi-v">${vt.sleep_h ? Number(vt.sleep_h).toFixed(1) + "h" : "--"}</div><div class="zb-kpi-l">睡眠</div></div>` +
        `<div><div class="zb-kpi-v">${ST.pu_best || 1}<span style="font-size:12px;color:var(--ink-3);font-weight:400;">/5</span></div><div class="zb-kpi-l">标准引体</div></div>`;
    }
    const lpz = ge("zb-ledger-pz");
    if (lpz && cur) {
      lpz.innerHTML = `<span style="color:var(--sumi);font-weight:500;">${escapeHtml(cur.progShort)} · ${cur.doneInProg}/${cur.progTotal} 节</span><span style="color:var(--ink-3);font-size:12.5px;">下节 ${escapeHtml(cur.code)} ›</span>`;
    }
    const lr = ge("zb-lrows");
    if (lr) {
      let rh = "";
      for (let i = 0; i < 10; i++) {
        const d = shiftD(today, -i), b = bbOn(d), p = peloOn(d), de = dayE(d), pr = (de.pu || []).length;
        const ps = [];
        if (b) ps.push(b.dur ? `篮球 ${b.dur}分` : (b.level === "max" ? "篮球(透支)" : (b.level === "high" ? "篮球" : "轻投")));
        if (p) {
          if (de.pz_done != null && p.status === "done") {
            const c = getPZMeta(Number(de.pz_done));
            ps.push(`PZ ${c.shortCode} · ${p.min || c.min}分`);
          } else if (p.status === "done") ps.push(`骑行 ${p.min || ""}分`);
          else if (p.status === "recovery") ps.push(`轻骑 ${p.min || 15}分`);
          else if (p.status === "rest") ps.push("休养");
        }
        if (pr > 0) ps.push(`引体 ${pr}轮`);
        if (de.res) ps.push("护肌");
        const wf = (ST.wb || []).find(r => r[0] === d);
        if (wf && wf[2]) ps.push(`${wf[2]}%`);
        let ed = "";
        if (EXP_DAY === d) {
          const bLock = b && b.src === "drive";
          ed = `<div class="zb-ed" data-zb-noswipe="1">
            <div class="zb-ed-row">
              <span class="zb-ed-lbl">心肺</span>
              <button type="button" class="zb-ed-chip ${de.pelo === "done" ? "on" : ""}" onclick="ZB.edCardio('${d}','pelo','done')">Peloton</button>
              <button type="button" class="zb-ed-chip ${de.pelo === "recovery" ? "on" : ""}" onclick="ZB.edCardio('${d}','pelo','recovery')">排酸</button>
              <button type="button" class="zb-ed-chip ${de.pelo === "rest" ? "on" : ""}" onclick="ZB.edCardio('${d}','pelo','rest')">休整</button>
              ${bLock ? `<span style="font-size:12px;color:var(--ink-3);">云盘已记篮球</span>` : `<button type="button" class="zb-ed-chip ${de.bb === "light" ? "on" : ""}" onclick="ZB.edCardio('${d}','bb','light')">轻投</button><button type="button" class="zb-ed-chip ${de.bb === "high" ? "on-red" : ""}" onclick="ZB.edCardio('${d}','bb','high')">全场</button><button type="button" class="zb-ed-chip ${de.bb === "max" ? "on-red" : ""}" onclick="ZB.edCardio('${d}','bb','max')">透支</button>`}
              ${(de.pelo || de.bb) ? `<button type="button" class="zb-ed-chip" style="color:var(--ink-3);" onclick="ZB.edCardio('${d}','clear','')">清空</button>` : ""}
            </div>
            <div class="zb-ed-row">
              <span class="zb-ed-lbl">引体</span>
              <button type="button" class="zb-ed-chip ${pr === 0 ? "on" : ""}" onclick="ZB.edPU('${d}',0)">0 轮</button>
              <button type="button" class="zb-ed-chip ${pr === 1 ? "on" : ""}" onclick="ZB.edPU('${d}',1)">1 轮</button>
              <button type="button" class="zb-ed-chip ${pr === 2 ? "on" : ""}" onclick="ZB.edPU('${d}',2)">2 轮</button>
              <button type="button" class="zb-ed-chip ${pr >= 3 ? "on" : ""}" onclick="ZB.edPU('${d}',3)">3 轮</button>
              <span style="margin-left:auto;"></span>
              <button type="button" class="zb-ed-chip ${de.diet ? "on" : ""}" onclick="ZB.edDiet('${d}')">${de.diet ? "饮食 ✓" : "补记饮食"}</button>
            </div>
          </div>`;
        }
        rh += `<div class="zb-ledger-item"><button type="button" class="zb-ledger-row" onclick="ZB.toggleDay('${d}')"><span class="zb-ledger-date">${d.slice(5)}</span><span class="zb-ledger-main" style="${ps.length ? "" : "color:var(--ink-3);"}">${ps.length ? ps.join(" · ") : "静休"}</span><span class="zb-ledger-dots"><span class="zb-dot ${b ? "bb" : (p ? "ok" : "")}"></span><span class="zb-dot ${pr > 0 ? "ok" : ""}"></span><span class="zb-dot ${de.diet ? "ok" : ""}"></span></span></button>${ed}</div>`;
      }
      lr.innerHTML = rh;
    }
    const gb = ge("zb-gaps-btn");
    const gs = (ST.vitals && ST.vitals.gaps) || [];
    if (gb) {
      if (gs.length) { gb.style.display = "inline-flex"; gb.textContent = `待补通 ${gs.length} 项 ›`; }
      else { gb.style.display = "none"; }
    }
    const vo2Tag = vt.vo2 ? ` · 摄氧量 ${vt.vo2}` : "";
    if (ge("zb-sync-txt")) ge("zb-sync-txt").textContent = (SYNC_NOTE || (vt.last_drive_sync ? `已同步 ${vt.last_drive_sync}` : "加密同步就绪")) + vo2Tag;
    if (typeof renderGreenBoard === "function") renderGreenBoard();
  }

  function bindGesturesOnce() {
    if (GESTURES_BOUND) return;
    GESTURES_BOUND = true;
    const stage = ge("zb-stage"), ptr = ge("zb-ptr"), ptrArc = ge("zb-ptr-arc"), ptrLbl = ge("zb-ptr-lbl");
    if (stage && stage.addEventListener) {
      let trk = false, mode = "", sx = 0, sy = 0, t0 = 0, ldx = 0, ldy = 0, busy = false;
      const toLocal = (dx, dy) => (typeof FP_ANGLE !== "undefined" && FP_ANGLE === 90) ? { dx: -dy, dy: dx } : ((typeof FP_ANGLE !== "undefined" && FP_ANGLE === 270) ? { dx: dy, dy: -dx } : { dx, dy });
      stage.addEventListener("touchstart", e => {
        if (!e.touches || e.touches.length !== 1 || busy) return;
        if (e.target && e.target.closest && e.target.closest("[data-zb-noswipe], input, textarea")) return;
        trk = true; mode = ""; sx = e.touches[0].clientX; sy = e.touches[0].clientY; t0 = Date.now(); ldx = 0; ldy = 0;
      }, { passive: true });
      stage.addEventListener("touchmove", e => {
        if (!trk || !e.touches || e.touches.length !== 1) return;
        const d = toLocal(e.touches[0].clientX - sx, e.touches[0].clientY - sy);
        ldx = d.dx; ldy = d.dy;
        if (!mode) {
          if (Math.hypot(ldx, ldy) < 10) return;
          if (Math.abs(ldx) > Math.abs(ldy) * 1.25) mode = "h";
          else if (ldy > 0 && stage.scrollTop <= 0) { mode = "ptr"; if (ptr) ptr.classList.add("dragging"); }
          else { mode = "v"; return; }
        }
        if (mode === "h") {
          e.preventDefault();
          const idx = SUB_ORDER.indexOf(SUBTAB);
          const edge = (idx === 0 && ldx > 0) || (idx === SUB_ORDER.length - 1 && ldx < 0);
          const dm = edge ? ldx * 0.16 : Math.max(-68, Math.min(68, ldx * 0.42));
          const ap = ge("zb-p-" + SUBTAB);
          if (ap) { ap.style.transition = "none"; ap.style.transform = `translateX(${dm.toFixed(1)}px)`; }
        } else if (mode === "ptr" && ldy > 0) {
          e.preventDefault();
          const pull = Math.min(56, ldy * 0.48), pct = Math.min(100, Math.round((pull / 46) * 100));
          if (ptr) { ptr.style.height = `${pull.toFixed(0)}px`; ptr.style.opacity = `${Math.min(1, pull / 30).toFixed(2)}`; }
          if (ptrArc) ptrArc.setAttribute("stroke-dasharray", `${pct} 100`);
          if (ptrLbl) ptrLbl.textContent = pull >= 46 ? "松手立即同步" : "下拉同步";
        }
      }, { passive: false });
      const endG = async () => {
        if (!trk) return;
        trk = false;
        if (mode === "h") {
          const dt = Date.now() - t0, idx = SUB_ORDER.indexOf(SUBTAB);
          const sr = ldx > 52 || (ldx > 26 && dt < 220), sl = ldx < -52 || (ldx < -26 && dt < 220);
          if (sl && idx < SUB_ORDER.length - 1) window.ZB.setTab(SUB_ORDER[idx + 1], 1);
          else if (sr && idx > 0) window.ZB.setTab(SUB_ORDER[idx - 1], -1);
          else {
            const ap = ge("zb-p-" + SUBTAB);
            if (ap) { ap.style.transition = "transform 0.22s cubic-bezier(0.22, 1, 0.36, 1)"; ap.style.transform = "translateX(0)"; setTimeout(() => { ap.style.transition = ""; ap.style.transform = ""; }, 230); }
          }
        } else if (mode === "ptr") {
          if (ptr) ptr.classList.remove("dragging");
          if (Math.min(56, Math.max(0, ldy * 0.48)) >= 46 && !busy) {
            busy = true;
            if (ptr) { ptr.classList.add("syncing"); ptr.style.height = "38px"; ptr.style.opacity = "1"; }
            if (ptrArc) ptrArc.setAttribute("stroke-dasharray", "68 100");
            if (ptrLbl) ptrLbl.textContent = "同步中…";
            await pullCloud(false);
            setTimeout(() => { if (ptr) { ptr.classList.remove("syncing"); ptr.style.height = "0px"; ptr.style.opacity = "0"; } busy = false; }, 260);
          } else if (ptr) { ptr.style.height = "0px"; ptr.style.opacity = "0"; }
        }
        mode = "";
      };
      stage.addEventListener("touchend", endG, { passive: true });
      stage.addEventListener("touchcancel", endG, { passive: true });
    }

    // Interactive Body Chart Scrubbing
    const cw = ge("zb-chart");
    if (cw && cw.addEventListener) {
      let scOn = false;
      const scrub = (cx, cy) => {
        if (!CHART_PTS.length) return;
        const svg = ge("zb-chart-svg");
        if (!svg || !svg.getBoundingClientRect) return;
        const rect = svg.getBoundingClientRect();
        if (!rect.width) return;
        const ang = typeof FP_ANGLE !== "undefined" ? FP_ANGLE : 0;
        const ratio = ang === 90 ? (rect.bottom - cy) / rect.height : (ang === 270 ? (cy - rect.top) / rect.height : (cx - rect.left) / rect.width);
        const sx = Math.max(0, Math.min(360, ratio * 360));
        let bi = 0, bd = Infinity;
        for (let i = 0; i < CHART_PTS.length; i++) { const dd = Math.abs(CHART_PTS[i].x - sx); if (dd < bd) { bd = dd; bi = i; } }
        if (bi === SCRUB_IDX) return;
        SCRUB_IDX = bi;
        const pt = CHART_PTS[bi];
        const cur = ge("zb-c-cur"), halo = ge("zb-c-halo"), foc = ge("zb-c-foc");
        if (cur && halo && foc) {
          cur.setAttribute("x1", pt.x); cur.setAttribute("x2", pt.x); cur.style.display = "";
          halo.setAttribute("cx", pt.x); halo.setAttribute("cy", pt.y); halo.style.display = "";
          foc.setAttribute("cx", pt.x); foc.setAttribute("cy", pt.y); foc.style.display = "";
        }
        applyBodyHead(todayYmd(), latestWB(), pt);
      };
      const endS = () => {
        if (!scOn && SCRUB_IDX === -1) return;
        scOn = false; SCRUB_IDX = -1;
        ["zb-c-cur", "zb-c-halo", "zb-c-foc"].forEach(id => { const el = ge(id); if (el) el.style.display = "none"; });
        applyBodyHead(todayYmd(), latestWB(), null);
      };
      cw.addEventListener("pointerdown", e => { if (!CHART_PTS.length) return; scOn = true; try { cw.setPointerCapture(e.pointerId); } catch (err) {} scrub(e.clientX, e.clientY); });
      cw.addEventListener("pointermove", e => { if (!scOn && (e.pointerType !== "mouse" || e.buttons === 0)) return; scrub(e.clientX, e.clientY); });
      cw.addEventListener("pointerup", endS);
      cw.addEventListener("pointercancel", endS);
      cw.addEventListener("pointerleave", () => { if (!scOn) endS(); });
    }

    // Zero-Keyboard Tactile Weigh-In Dial Tracks
    [
      { id: "zb-dwt-track", key: "wt", min: 45, max: 120, px: 11 },
      { id: "zb-dbf-track", key: "bf", min: 6, max: 40, px: 13 }
    ].forEach(cfg => {
      const el = ge(cfg.id);
      if (!el || !el.addEventListener) return;
      let dg = false, sp = 0, sv = 0, so = 0;
      const getPos = e => (typeof FP_ANGLE !== "undefined" && FP_ANGLE === 90) ? -e.clientY : ((typeof FP_ANGLE !== "undefined" && FP_ANGLE === 270) ? e.clientY : e.clientX);
      el.addEventListener("pointerdown", e => {
        dg = true; sp = getPos(e); sv = cfg.key === "wt" ? D_WT : D_BF; so = cfg.key === "wt" ? D_WT_OFF : D_BF_OFF;
        if (cfg.key === "bf") D_SKIP_BF = false;
        try { el.setPointerCapture(e.pointerId); } catch (err) {}
      });
      el.addEventListener("pointermove", e => {
        if (!dg) return;
        const dx = getPos(e) - sp;
        const nv = Math.max(cfg.min, Math.min(cfg.max, +(sv + Math.round(-dx / cfg.px) * 0.1).toFixed(1)));
        if (cfg.key === "wt") { D_WT = nv; D_WT_OFF = so + dx; } else { D_BF = nv; D_BF_OFF = so + dx; }
        renderDial();
      });
      const stp = () => { dg = false; };
      el.addEventListener("pointerup", stp);
      el.addEventListener("pointercancel", stp);
    });
  }

  function ensureDay(ymd) {
    const t = ymd || todayYmd();
    if (!ST.days) ST.days = {};
    if (!ST.days[t]) ST.days[t] = { ts: 0, pu: [], diet: 0 };
    ST.days[t].ts = Math.floor(Date.now() / 1000);
    return ST.days[t];
  }

  async function tryRestoreVault() {
    try {
      const h = (location.hash || "").replace(/^#/, "");
      if (h) {
        const p = new URLSearchParams(h);
        const bt = p.get("bt"), bk = p.get("bk");
        if (bt && bk && bt.length >= 16 && bk.length >= 40) {
          VAULT = { t: bt, k: bk };
          localStorage.setItem(VAULT_KEY, JSON.stringify(VAULT));
        }
      }
    } catch (e) {}
    if (!VAULT) {
      try { const s = localStorage.getItem(VAULT_KEY); if (s) VAULT = JSON.parse(s); } catch (e) {}
    }
    if (!VAULT || !VAULT.t || !VAULT.k) return false;
    CKEY = await importRawKey(VAULT.k);
    return !!CKEY;
  }

  async function unlockPass() {
    const inp = ge("zb-pass-in"), err = ge("zb-lock-err"), btn = ge("zb-unlock-btn");
    const pass = (inp && inp.value || "").trim().toLowerCase();
    if (!pass) { if (err) err.textContent = "请先输入口令"; return; }
    if (typeof crypto === "undefined" || !crypto.subtle) { if (err) err.textContent = "请用 HTTPS 打开本页"; return; }
    if (btn) btn.textContent = "解锁中…";
    if (err) err.textContent = "";
    try {
      const r = await fetch("./body_vault.enc?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("fetch");
      const env = await r.json();
      const baseKey = await crypto.subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
      const dKey = await crypto.subtle.deriveKey(
        { name: "PBKDF2", salt: b64uToBytes(env.salt), iterations: env.iter || 310000, hash: "SHA-256" },
        baseKey, { name: "AES-GCM", length: 256 }, false, ["decrypt"]
      );
      const unwrapped = await decWithKey(dKey, env.w);
      if (!unwrapped || !unwrapped.t || !unwrapped.k) {
        if (err) err.textContent = "口令不太对，再试一次";
        if (btn) btn.textContent = "解锁";
        return;
      }
      VAULT = { t: unwrapped.t, k: unwrapped.k };
      CKEY = await importRawKey(VAULT.k);
      try { localStorage.setItem(VAULT_KEY, JSON.stringify(VAULT)); } catch (e) {}
      if (inp) inp.value = "";
      if (btn) btn.textContent = "解锁";
      showApp();
      const dec = await decWithKey(CKEY, env.d);
      if (dec && dec.v === 1) { ST = mergeS(ST, dec); saveLocal(); syncPUDefault(); }
      render();
      positionSubBar(true);
      await pullCloud(true);
      toast("已解锁并记住本设备");
    } catch (e) {
      if (err) err.textContent = "网络或口令异常，请重试";
      if (btn) btn.textContent = "解锁";
    }
  }

  function showApp() {
    const lk = ge("zb-locked"), ap = ge("zb-app");
    if (lk) lk.style.display = "none";
    if (ap) ap.style.display = "flex";
    bindGesturesOnce();
    setTimeout(() => positionSubBar(true), 20);
  }

  async function onEnter() {
    if (!INITED) {
      INITED = true;
      const ok = await tryRestoreVault();
      if (!ok) {
        const lk = ge("zb-locked"), ap = ge("zb-app");
        if (lk) lk.style.display = "flex";
        if (ap) ap.style.display = "none";
        return;
      }
      showApp();
      loadLocal();
      syncPUDefault();
      render();
      positionSubBar(true);
      await pullCloud(true);
      try { if (localStorage.getItem(PEND_KEY)) await pushNow(); } catch (e) {}
    } else if (CKEY) {
      render();
      positionSubBar(true);
      pullCloud(true);
    }
  }

  function onResume() {
    if (!CKEY) return;
    if (todayYmd() !== LAST_DAY) render();
    pullCloud(true);
  }

  let LOCAL_PEEKED = false;
  function getSummary() {
    if (!INITED && !LOCAL_PEEKED) {
      LOCAL_PEEKED = true;
      loadLocal();
    }
    const today = todayYmd(), plan = planFor(today), day = dayE(today);
    const cOk = !!plan.cardioDone;
    const puDone = (day.pu || []).length;
    const pOk = plan.puTarget === 0 || puDone >= plan.puTarget;
    const dOk = !!day.diet;
    const cnt = (cOk ? 1 : 0) + (pOk ? 1 : 0) + (dOk ? 1 : 0);
    const bits = [];
    if (cOk) bits.push("心肺✓");
    if (pOk) bits.push("引体✓");
    if (dOk) bits.push("饮食✓");
    return {
      ratio: cnt / 3,
      done: cnt === 3,
      label: cnt === 3 ? "体律 已完成" : `体律 ${cnt}/3`,
      text: bits.length ? `${cnt} / 3 项（${bits.join(" · ")}）` : "0 / 3 项"
    };
  }

  async function syncCircle() {
    if (CKEY) { await pullCloud(true); return; }
    try {
      if (!localStorage.getItem(VAULT_KEY)) return;
      const ok = await tryRestoreVault();
      if (ok) {
        loadLocal();
        if (typeof renderGreenBoard === "function") renderGreenBoard();
        await pullCloud(true);
      }
    } catch (e) {}
  }

  function getHorizonHTML() {
    if (!INITED && !LOCAL_PEEKED) { LOCAL_PEEKED = true; loadLocal(); }
    const wb = latestWB();
    const tgt = (ST.targets && ST.targets.bf_ge) || 14;
    return wb.lbf ? `GE <b>${wb.lbf[2].toFixed(1)}%</b> → ${tgt}%` : `目标 <b>${tgt}%</b>`;
  }

  function showGuideModal(title, items, extraLinksHtml) {
    const mc = ge("modal-content"), mm = ge("app-modal");
    if (!mc || !mm) return;
    mc.innerHTML = `
      <h3 class="modal-h">${escapeHtml(title)}</h3>
      <div class="zb-guide-list">
        ${items.map(it => `<div class="zb-guide-item${it.cur ? " cur" : ""}"><div class="zb-guide-k">${escapeHtml(it.k)}</div><div class="zb-guide-v">${escapeHtml(it.v)}</div>${it.sub ? `<div class="zb-guide-sub">${escapeHtml(it.sub)}</div>` : ""}</div>`).join("")}
      </div>
      ${extraLinksHtml ? `<div class="zb-modal-links">${extraLinksHtml}</div>` : ""}
      <div class="dock-row">
        <button type="button" class="sumi-btn" onclick="closeModal()">知道了</button>
      </div>`;
    mm.classList.add("open");
  }

  function openPeloGuide() {
    const p = planFor(todayYmd());
    if (!p || !p.guide) return;
    const links = [];
    if (p.guide.canOverridePZ && p.cur && !p.cur.allDone) {
      links.push(`<button type="button" class="zb-btn-quiet active" onclick="ZB.overrideToPZ()">精力足，今天照常骑 ${escapeHtml(p.cur.code)} ›</button>`);
    }
    if (p.guide.showSyllabus) {
      links.push(`<button type="button" class="zb-btn-quiet" onclick="ZB.openPZList()">完整主线课表 ›</button>`);
    }
    showGuideModal(p.guide.title, p.guide.items, links.join(""));
  }

  function openPZList(progHint) {
    const mc = ge("modal-content"), mm = ge("app-modal");
    if (!mc || !mm) return;
    const curIdx = getPZIdx();
    const curMeta = getPZMeta(curIdx);
    const pIdx = (progHint === 0 || progHint === 1) ? progHint : curMeta.pIdx;
    PZ_VIEW_PROG = pIdx;
    const prog = PZ_PROGS[pIdx];
    const chMap = PZ_CH_LABELS[pIdx] || {};
    let rowsHtml = "", lastWk = 0;
    for (let i = 0; i < PZ_LIST.length; i++) {
      const r = PZ_LIST[i];
      if (r[0] !== pIdx) continue;
      if (r[1] !== lastWk) {
        lastWk = r[1];
        rowsHtml += `<div class="zb-pz-wk">${escapeHtml(chMap[r[1]] || ("第 " + r[1] + " 章 · Bike+ Week " + r[1]))}</div>`;
      }
      const isDone = i < curIdx, isCur = i === curIdx;
      const mark = isDone ? "✓" : (isCur ? "●" : "○");
      const kindLbl = r[6] === "test" ? " · FTP测试" : (r[6] === "hard" ? " · 强课" : (r[6] === "easy" ? " · 轻课" : ""));
      rowsHtml += `<button type="button" class="zb-pz-row ${isDone ? "done" : (isCur ? "cur" : "")}" onclick="ZB.setPZIdx(${i})">
        <span class="zb-pz-mark">${mark}</span>
        <span class="zb-pz-info"><div class="zb-pz-name">${escapeHtml(r[3])}</div><div class="zb-pz-meta">第 ${r[2]} 节 · ${escapeHtml(r[4])}${kindLbl}</div></span>
        <span class="zb-pz-min">${r[5]}分</span>
      </button>`;
    }
    const paceNote = pIdx === 0
      ? `你每周还打 2–4 场球，绝不按官方纯骑车的 5 周硬追。每周稳推 2–3 节（球多时 1–2 节），约 8–10 周从容通关；${prog.entry}，Peloton 新版自由推进不锁课，点任意一节可校准进度。`
      : `全 Zone 2–3 稳态燃脂，每周 2–3 节即可（75/90 分长课仅限周末不打球日，累了可换 45 分）。${prog.entry}。点任意一节可校准进度。`;
    mc.innerHTML = `
      <h3 class="modal-h">Power Zone 完整主线课表</h3>
      <div class="zb-pz-tabs">
        <button type="button" class="zb-pz-tab ${pIdx === 0 ? "active" : ""}" onclick="ZB.openPZList(0)">Discover (23节)</button>
        <button type="button" class="zb-pz-tab ${pIdx === 1 ? "active" : ""}" onclick="ZB.openPZList(1)">Boost Base (24节)</button>
      </div>
      <p class="zb-pz-note">${escapeHtml(paceNote)}</p>
      <div class="zb-pz-list">${rowsHtml}</div>
      <div class="dock-row">
        <button type="button" class="sumi-btn" onclick="closeModal()">返回</button>
      </div>`;
    mm.classList.add("open");
  }

  function openBandGuide() {
    const stg = puStage();
    const bIdx = stg.idx === 0 ? 0 : (stg.idx === 1 ? 1 : 2);
    showGuideModal("弹力带换绳与冲 5 连路线", [
      { k: "阶段一 · 1 徒手起步", v: "黑带 25–65 lb（单膝约 10–15 kg）", sub: "每轮 1 个徒手 + 2 个单膝挂黑带 4 秒慢放，每日 2 轮。", cur: bIdx === 0 },
      { k: "阶段二 · 2 徒手过渡", v: "红细带 15–35 lb（单膝约 5–8 kg）", sub: "稳拉 2 个纯徒手后降档，每轮 2 徒手 + 1 红带慢放，每日 2 轮。", cur: bIdx === 1 },
      { k: "阶段三 · 3 连冲 5 连（不力竭多组法）", v: "彻底拆绳 0 lb · 留 1 下余力拉 3 轮", sub: "稳拉 3 个后不再每轮拉满力竭：平时每次轻松拉 2 个、隔 2 小时拉 3 轮（攒 6 下高质量纯拉），每两周满血测一次冲 4 连、5 连。", cur: bIdx === 2 }
    ]);
  }

  function openProteinGuide() {
    const wb = latestWB();
    const wt = wb.avgWt || (wb.lwt && wb.lwt[1]) || 81.0;
    const pLo = Math.round((wt * 1.6) / 5) * 5;
    const pMid = Math.round((wt * 1.8) / 5) * 5;
    const pHi = Math.round((wt * 2.0) / 5) * 5;
    showGuideModal(`每日蛋白锚点 · 目标 ${pLo}–${pHi}g`, [
      { k: "为什么必须吃够", v: `按你近期均重 ${wt.toFixed(1)} kg，减脂护肌甜点约 ${pMid}g / 天`, sub: "多项减脂随机试验（Longland 2016 / Morton 2018）证实：体脂往 14% 压时，每天吃够 1.6–2.0 g/kg 蛋白，掉的才主要是脂肪而不是肌肉。", cur: true },
      { k: "日常顺手凑够 145g 参考", v: "乳清蛋白 1 勺 ≈ 25g · 鸡胸/三文鱼/瘦牛 200g ≈ 45g", sub: "3 个全蛋 ≈ 20g · 一杯希腊酸奶 ≈ 18g · 一盒嫩豆腐/毛豆 ≈ 15g。早晚各 1 份高蛋白 + 午晚正餐有肉鱼，轻松过线。" },
      { k: "配合晚间节律", v: "晚餐先吃蛋白与青菜，睡前 3 小时不爆高糖高油碳水", sub: "蛋白本身饱腹感极强，不用饿肚子也能稳稳守住热量缺口。" }
    ]);
  }

  function openGapsGuide() {
    const gs = (ST.vitals && ST.vitals.gaps) || [];
    if (!gs.length) return;
    showGuideModal("健康数据待补通", gs.map((g, i) => ({ k: `项目 ${i + 1}`, v: g })));
  }

  return {
    onEnter, onResume, unlockPass, stopPacer, getSummary, syncCircle, getHorizonHTML,
    openPeloGuide, openPZList, openBandGuide, openProteinGuide, openGapsGuide,
    _planToday() { return planFor(todayYmd()); },
    _planOn(ymd) { return planFor(ymd); },
    _puStage() { return puStage(); },
    _getState() { return ST; },
    onHorizonRightTap() {
      if (!CKEY) { if (typeof openSessionModal === "function") openSessionModal(); return; }
      if (SUBTAB !== "body") this.setTab("body");
      else if (typeof openSessionModal === "function") openSessionModal();
    },
    setTab(t, dirHint) {
      if (!SUB_ORDER.includes(t)) return;
      if (t === SUBTAB) { positionSubBar(false); return; }
      if (PACER_ON) stopPacer(false);
      const prev = SUB_ORDER.indexOf(SUBTAB), next = SUB_ORDER.indexOf(t);
      const dir = dirHint || (next > prev ? 1 : -1);
      SUBTAB = t;
      document.querySelectorAll(".zb-subtab").forEach(b => b.classList.toggle("active", b.dataset.zbt === t));
      SUB_ORDER.forEach(k => {
        const el = ge("zb-p-" + k);
        if (!el) return;
        el.classList.remove("zb-slide-r", "zb-slide-l");
        el.style.transform = ""; el.style.transition = "";
        el.classList.toggle("active", k === t);
        if (k === t) { void el.offsetWidth; el.classList.add(dir > 0 ? "zb-slide-r" : "zb-slide-l"); }
      });
      const st = ge("zb-stage"); if (st) st.scrollTop = 0;
      if (t === "body") renderChart();
      positionSubBar(false);
    },
    setState(mode, sub) {
      const today = todayYmd(), d = ensureDay(today);
      const hasDriveBB = actsOn(today).some(a => a[1] === "bb");
      d.force_pz = 0;
      if (mode === "normal") {
        d.bb = hasDriveBB ? "none" : null;
        d.tired = 0;
        d.rest_day = 0;
      } else if (mode === "bb") {
        d.tired = 0;
        d.rest_day = 0;
        if (sub === "light" || sub === "high" || sub === "max") d.bb = sub;
        else if (d.bb !== "light" && d.bb !== "high" && d.bb !== "max") {
          const autoB = hasDriveBB ? bbOn(today) : null;
          d.bb = (autoB && autoB.level) ? autoB.level : "high";
        }
      } else if (mode === "tired") {
        d.bb = hasDriveBB ? "none" : null;
        d.rest_day = 0;
        d.tired = (sub === "sore" || sub === "sleep") ? sub : (d.tired === "sore" ? "sore" : "sleep");
      } else if (mode === "rest") {
        d.bb = hasDriveBB ? "none" : null;
        d.tired = 0;
        d.rest_day = 1;
      }
      schedPush(); render();
    },
    setPZIdx(idx) {
      const n = Math.max(0, Math.min(PZ_LIST.length, Number(idx) || 0));
      const nowS = Math.floor(Date.now() / 1000);
      ST.pz = { idx: n, ts: nowS, last: (ST.pz && ST.pz.last) || "" };
      if (typeof closeModal === "function") closeModal();
      const m = getPZMeta(n);
      toast(m.allDone ? "已标记两套主线全部通关" : `已校准：下节 ${m.progShort} ${m.code}`);
      schedPush(); render();
    },
    overrideToPZ() {
      const d = ensureDay();
      d.force_pz = 1;
      if (typeof closeModal === "function") closeModal();
      toast("已切回今日主线课程");
      schedPush(); render();
    },
    logCardio(kind) {
      const today = todayYmd(), p = planFor(today), d = ensureDay(today), nowS = Math.floor(Date.now() / 1000);
      if (p.isTravel) {
        d.pelo = d.pelo ? null : "done"; d.pelo_min = 30;
        toast(d.pelo ? "旅途步行已记" : "已撤销");
      } else if (kind === "recovery") {
        const altT = (p.altAction && p.altAction.type) || "recovery";
        if (altT === "override_pz") {
          this.overrideToPZ();
          return;
        } else if (altT === "to_rest") {
          d.rest_day = 1; d.tired = 0; d.pelo = "rest"; d.pelo_min = 0;
          toast("好，今天安心休整");
        } else if (altT === "light_ride") {
          const mins = (p.altAction && p.altAction.min) || p.altMin || 15;
          d.pelo = d.pelo === "recovery" ? null : "recovery"; d.pelo_min = d.pelo ? mins : 0;
          toast(d.pelo ? `已记轻骑 ${mins} 分钟` : "已撤销");
        } else {
          d.pelo = d.pelo === "recovery" ? null : "recovery"; d.pelo_min = d.pelo ? 15 : 0;
          toast(d.pelo ? "已记 15 分排酸骑" : "已撤销");
        }
      } else if (p.actionType === "pz_main") {
        if (d.pz_done != null && d.pelo === "done") {
          const prevIdx = Number(d.pz_done);
          ST.pz = { idx: Math.max(0, prevIdx), ts: nowS, last: (ST.pz && ST.pz.last === today) ? shiftD(today, -1) : ((ST.pz && ST.pz.last) || "") };
          d.pz_done = null; d.pelo = null; d.pelo_min = 0;
          toast("已撤销本节主线打卡");
        } else {
          const curIdx = getPZIdx(), cls = getPZMeta(curIdx);
          d.pz_done = curIdx; d.pelo = "done"; d.pelo_min = cls.min;
          const nextIdx = Math.min(PZ_LIST.length, curIdx + 1);
          ST.pz = { idx: nextIdx, ts: nowS, last: today };
          if (curIdx === 22) toast("恭喜完成 Discover 全部 23 节！已接力 Boost Your Base");
          else if (curIdx === PZ_LIST.length - 1) toast("恭喜完成全部 47 节 Power Zone 主线！");
          else {
            const nxt = getPZMeta(nextIdx);
            toast(`已拿下 ${cls.code} · 下节 ${nxt.code}`);
          }
        }
      } else if (p.actionType === "z2_swap") {
        const mins = p.rideMin || 30;
        d.pelo = d.pelo === "done" ? null : "done"; d.pelo_min = d.pelo ? mins : 0;
        toast(d.pelo ? `已记 ${mins} 分 Zone 2 稳态燃脂` : "已撤销");
      } else if (p.actionType === "light_ride") {
        const mins = p.rideMin || 20;
        d.pelo = d.pelo === "recovery" ? null : "recovery"; d.pelo_min = d.pelo ? mins : 0;
        toast(d.pelo ? `已记轻骑 ${mins} 分钟` : "已撤销");
      } else {
        d.pelo = d.pelo === "rest" ? null : "rest"; d.pelo_min = 0;
        toast(d.pelo ? "好，今晚安心休养" : "已撤销");
      }
      schedPush(); render();
    },
    quickPU(n) {
      const d = ensureDay(), stg = puStage(), nowS = Math.floor(Date.now() / 1000);
      const maxR = stg.targetRounds || 2;
      if (!Array.isArray(d.pu)) d.pu = [];
      if (d.pu.length >= n) { d.pu = d.pu.slice(0, n - 1); toast(`已撤销第 ${n} 轮`); }
      else {
        while (d.pu.length < n) d.pu.push([stg.defStrict, stg.neg, nowS]);
        toast(n < maxR ? `第 ${n} 轮已记 · 隔 2 小时再拉第 ${n + 1} 轮` : `第 ${n} 轮已记 · 今日引体收工`);
      }
      schedPush(); render();
    },
    adjStrict(delta) { PU_IN = Math.max(0, Math.min(10, PU_IN + delta)); render(); },
    togglePacer() {
      if (PACER_ON) { stopPacer(true); return; }
      const maxR = puStage().targetRounds || 2;
      if ((dayE(todayYmd()).pu || []).length >= maxR) { toast(`今天 ${maxR} 轮已满额，明天继续`); return; }
      startPacer();
    },
    togglePacerSound() {
      PACER_SND = !PACER_SND;
      const b = ge("zb-pacer-snd");
      if (b) { b.textContent = PACER_SND ? "轻音：开" : "轻音：关"; b.className = "zb-btn-quiet" + (PACER_SND ? " active" : ""); }
      if (PACER_SND) playChime(528);
    },
    logPU() {
      const d = ensureDay(), stg = puStage(), maxR = stg.targetRounds || 2;
      if (!Array.isArray(d.pu)) d.pu = [];
      if (d.pu.length >= maxR) { toast(`今天 ${maxR} 轮已满额，明天继续`); return; }
      const nowS = Math.floor(Date.now() / 1000);
      const negAdd = stg.neg > 0 ? Math.max(0, 3 - PU_IN) : 0;
      d.pu.push([PU_IN, negAdd, nowS]);
      if (PU_IN > (ST.pu_best || 1)) { ST.pu_best = PU_IN; ST.pu_best_ts = nowS; toast(`新纪录！标准不甩 ${PU_IN} 个`); }
      else toast(d.pu.length < maxR ? `第 ${d.pu.length} 轮已记 · 隔 2 小时第 ${d.pu.length + 1} 轮` : `今日 ${maxR} 轮引体收工`);
      schedPush(); render();
    },
    undoPU() {
      const d = ensureDay();
      if (Array.isArray(d.pu) && d.pu.length) { d.pu.pop(); schedPush(); render(); toast("已撤销上一轮"); }
    },
    toggleRes() {
      const d = ensureDay();
      d.res = d.res ? 0 : 1;
      schedPush(); render();
      toast(d.res ? "已记 5 分钟居家护肌（俯卧撑+深蹲）" : "已取消今日护肌记录");
    },
    toggleDiet() {
      const d = ensureDay(); d.diet = d.diet ? 0 : 1;
      schedPush(); render(); toast(d.diet ? "今日饮食节律已打卡" : "已取消");
    },
    setMetric(m) { METRIC = m; render(); },
    setRange(r) { RANGE = r; render(); },
    toggleWForm(force) {
      const f = ge("zb-wform"), b = ge("zb-wbtn");
      if (!f || !b) return;
      const open = typeof force === "boolean" ? force : !f.classList.contains("open");
      if (open) {
        const wb = latestWB();
        D_WT = wb.lwt ? +wb.lwt[1].toFixed(1) : 81.5;
        D_BF = wb.lbf ? +wb.lbf[2].toFixed(1) : 18.0;
        D_SKIP_BF = false;
        const winp = ge("zb-waist-in");
        if (winp) winp.value = "";
        renderDial();
      }
      f.classList.toggle("open", open);
      b.textContent = open ? "收起" : "记一次称重";
    },
    nudgeDial(which, delta) {
      if (which === "wt") { D_WT = Math.max(45, Math.min(120, +(D_WT + delta).toFixed(1))); D_WT_OFF -= delta * 100; }
      else { D_SKIP_BF = false; D_BF = Math.max(6, Math.min(40, +(D_BF + delta).toFixed(1))); D_BF_OFF -= delta * 100; }
      renderDial();
    },
    toggleSkipBf() { D_SKIP_BF = !D_SKIP_BF; renderDial(); },
    editDial(which) {
      const slot = ge(which === "wt" ? "zb-dwt-slot" : "zb-dbf-slot");
      if (!slot) return;
      const cur = which === "wt" ? D_WT.toFixed(1) : D_BF.toFixed(1);
      slot.innerHTML = `<input class="zb-dial-in" type="number" step="0.1" inputmode="decimal" value="${cur}" />`;
      const inp = slot.querySelector ? slot.querySelector("input") : null;
      if (!inp) return;
      inp.focus(); if (inp.select) inp.select();
      const done = () => {
        const v = parseFloat(inp.value);
        if (!isNaN(v)) {
          if (which === "wt" && v >= 45 && v <= 120) D_WT = +v.toFixed(1);
          if (which === "bf" && v >= 6 && v <= 40) { D_BF = +v.toFixed(1); D_SKIP_BF = false; }
        }
        slot.innerHTML = "";
        renderDial();
      };
      inp.addEventListener("blur", done);
      inp.addEventListener("keydown", e => { if (e.key === "Enter") inp.blur(); });
    },
    saveWeigh() {
      const wv = +D_WT.toFixed(1), bf = D_SKIP_BF ? null : +D_BF.toFixed(1);
      const winp = ge("zb-waist-in");
      const rawW = winp ? parseFloat(winp.value) : NaN;
      const waist = (!isNaN(rawW) && rawW >= 50 && rawW <= 150) ? +rawW.toFixed(1) : null;
      const t = todayYmd(), d = ensureDay(t);
      d.wt = wv; if (bf !== null) d.bf = bf;
      if (waist !== null) d.waist = waist;
      if (!Array.isArray(ST.wb)) ST.wb = [];
      const ix = ST.wb.findIndex(r => r[0] === t);
      const prevWaist = (ix >= 0 && ST.wb[ix].length > 4) ? ST.wb[ix][4] : null;
      const finalWaist = waist !== null ? waist : prevWaist;
      const row = finalWaist !== null ? [t, wv, bf, "phone", finalWaist] : [t, wv, bf, "phone"];
      if (ix >= 0) ST.wb[ix] = row; else ST.wb.push(row);
      ST.wb.sort((a, b) => a[0].localeCompare(b[0]));
      this.toggleWForm(false); schedPush(); render();
      const wTag = waist !== null ? ` · 腰围 ${waist.toFixed(1)}cm` : "";
      toast(bf !== null ? `已记 ${wv.toFixed(1)} kg · GE ${bf.toFixed(1)}%${wTag}` : `已记体重 ${wv.toFixed(1)} kg${wTag}`);
    },
    toggleDay(ymd) { EXP_DAY = EXP_DAY === ymd ? null : ymd; render(); },
    edCardio(ymd, field, val) {
      const d = ensureDay(ymd);
      if (field === "clear") { d.pelo = null; d.pelo_min = 0; d.bb = null; toast(`${ymd.slice(5)} 已清空`); }
      else if (field === "pelo") { d.pelo = d.pelo === val ? null : val; d.pelo_min = d.pelo === "done" ? 40 : (d.pelo === "recovery" ? 20 : 0); toast(`${ymd.slice(5)} 已更新`); }
      else if (field === "bb") { d.bb = d.bb === val ? null : val; toast(`${ymd.slice(5)} 已更新`); }
      schedPush(); render();
    },
    edPU(ymd, n) {
      const d = ensureDay(ymd), stg = puStage();
      d.pu = [];
      for (let i = 0; i < n; i++) d.pu.push([stg.defStrict, stg.neg]);
      schedPush(); render(); toast(`${ymd.slice(5)} 引体已改为 ${n} 轮`);
    },
    edDiet(ymd) {
      const d = ensureDay(ymd); d.diet = d.diet ? 0 : 1;
      schedPush(); render(); toast(d.diet ? `${ymd.slice(5)} 饮食达标已补记` : `${ymd.slice(5)} 已取消`);
    },
    syncNow() { pullCloud(false); }
  };
})();

function initApp() {
  positionMainThumbBar(true);
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
  else if (m === "body") switchMode("body");
  else if (m === "vocab" || m === "flash") switchMode("vocab");
  else if (m === "radio" || m === "walk") switchMode("radio", false);
  else renderTutor();

  checkNewDailyEdition();
  if (window.ZB && typeof window.ZB.syncCircle === "function") window.ZB.syncCircle();
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
let reloadCount = 0;
function makeAudioEl() {
  const a = makeEl('audio');
  a.paused = true;
  a.muted = false;
  a.volume = 1;
  a.duration = 3600;
  a.currentTime = 0;
  a.readyState = 4;
  a.playbackRate = 1;
  a.loadCount = 0;
  a._ev = {};
  a.addEventListener = function(k, fn) { (this._ev[k] = this._ev[k] || []).push(fn); };
  a._emit = function(k) { (this._ev[k] || []).forEach(fn => fn()); };
  a.play = function() { this.paused = false; this._emit('play'); this._emit('playing'); return Promise.resolve(); };
  a.pause = function() { if (!this.paused) { this.paused = true; this._emit('pause'); } };
  a.load = function() { this.loadCount += 1; };
  return a;
}
const mediaSessionMock = {
  metadata: null,
  playbackState: 'none',
  _handlers: {},
  _posState: null,
  setActionHandler(k, fn) { this._handlers[k] = fn; },
  setPositionState(s) { this._posState = s; }
};
const sb = {
  console, Math, Date, JSON, Object, Array, String, Number, Boolean, Set, Map, RegExp, Error, Promise, URL, URLSearchParams, TextEncoder, TextDecoder,
  performance:{now:()=>Date.now()}, innerWidth:390, innerHeight:844, scrollTo:()=>{}, addEventListener:()=>{}, removeEventListener:()=>{},
  parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  setTimeout:()=>1, clearTimeout:()=>{}, setInterval:()=>1, clearInterval:()=>{}, requestAnimationFrame:()=>1, cancelAnimationFrame:()=>{},
  localStorage:{getItem:k=>(k in store?store[k]:null), setItem:(k,v)=>{store[k]=String(v);}, removeItem:k=>{delete store[k];}},
  sessionStorage:{getItem:()=>null, setItem:()=>{}, removeItem:()=>{}},
  navigator:{userAgent:'Mozilla/5.0 Mobile', serviceWorker:{register:()=>Promise.resolve({update:()=>Promise.resolve()}), getRegistration:()=>Promise.resolve(null), addEventListener:()=>{}}, mediaSession:mediaSessionMock, onLine:true, sendBeacon:()=>true},
  MediaMetadata:function(x){Object.assign(this,x);}, Audio:makeAudioEl, EventSource:function(){return {addEventListener(){},close(){}};},
  fetch:()=>Promise.resolve({ok:true, text:()=>Promise.resolve(''), json:()=>Promise.resolve({})}),
  location:{href:'https://tango13ucla.github.io/n3-audio-tutor/', hostname:'tango13ucla.github.io', search:'', hash:'', reload:()=>{reloadCount += 1;}},
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
sb.switchMode('body');
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
// Self-test 1: Retry option shuffling strictly changes choice order on consecutive retries
const dummyPS = { lastChoiceOrder: null };
const dummyQ = { id: 'TEST-Q', choices: ['A', 'B', 'C'], answer: 'A', is_listening: false };
const ord1 = sb.prepareChoices(dummyQ, 1, dummyPS);
const ord2 = sb.prepareChoices(dummyQ, 8, dummyPS);
const ord3 = sb.prepareChoices(dummyQ, 15, dummyPS);
if (ord1.join('|') === ord2.join('|') || ord2.join('|') === ord3.join('|')) {
  throw new Error('Self-test failed: prepareChoices did not change order on retry!');
}
// Self-test 2: Answering wrong/peeking NEVER promotes mastery to wip1 on same day
const mFail = sb.computeNextMasteryState({ tier: 'todo', streak: 0, mstate: 'todo' }, 'fail', '20261117');
const mRec = sb.computeNextMasteryState({ tier: 'todo', streak: 0, mstate: mFail }, 'recover', '20261117');
if (!mRec.startsWith('todo:')) {
  throw new Error('Self-test failed: recover on failed day promoted mastery (' + mRec + ')!');
}
// Self-test 3: Word lookup records LK:* without mutating vocabSess.queue
const qLenBefore = vm.runInNewContext('A.vocabSess ? A.vocabSess.queue.length : -1', sb);
sb.recordTappedWord('予約しとこう');
const qLenAfter = vm.runInNewContext('A.vocabSess ? A.vocabSess.queue.length : -1', sb);
const lkRec = vm.runInNewContext('A.wordLookups["予約しとこう"]', sb);
if (qLenBefore !== qLenAfter || !Array.isArray(lkRec) || lkRec[0] < 1) {
  throw new Error('Self-test failed: recordTappedWord either mutated vocabSess or missed wordLookups!');
}
// Self-test 4: Every vocab card has a concise phrase (<=10 chars), spoken mnemonic, hook_audio, and zero em dashes
const vcObj = vm.runInNewContext('DATA.vocab_cards || {}', sb);
const vcKeys = Object.keys(vcObj);
if (vcKeys.length < 120) throw new Error('Self-test failed: vocab_cards unexpectedly small: ' + vcKeys.length);
for (const k of vcKeys) {
  const rec = vcObj[k] || {};
  const mn = String(rec.mnemonic || '').trim();
  const hs = String(rec.hook_spoken || '').trim();
  const ch = String(rec.chunk_ja || '').trim();
  if (!mn) throw new Error('Self-test failed: missing mnemonic for vocab card ' + k);
  if (mn.includes('—')) throw new Error('Self-test failed: em dash in mnemonic for ' + k);
  if (!hs) throw new Error('Self-test failed: missing hook_spoken for vocab card ' + k);
  if (!rec.hook_audio) throw new Error('Self-test failed: missing hook_audio for vocab card ' + k);
  if (ch.length > 10) throw new Error('Self-test failed: vocab chunk too long (should be concise phrase <=10 chars) for ' + k + ': ' + ch);
}
sb.switchMode('vocab');
const vcStageHtml = (els['vocab-stage-box'] && els['vocab-stage-box'].innerHTML) || '';
if (!vcStageHtml.includes('vc-hook') || !vcStageHtml.includes('>记音<') || vcStageHtml.includes('记音 ♪')) {
  throw new Error('Self-test failed: vocab card must render calm .vc-hook 记音 without redundant ♪ tap icon!');
}
// Self-test 5: Zen Body Human & Basketball-Aware Dynamic Coach + 47-Session Power Zone Engine
const pNorm = sb.ZB._planToday();
if (!pNorm || !pNorm.isPZMain || !pNorm.title.includes('Power Zone Beginner') || pNorm.stale !== 'none') {
  throw new Error('Self-test 5 failed: normal day did not recommend W1D2 Power Zone Beginner cleanly: ' + JSON.stringify(pNorm));
}
sb.ZB.setState('bb');
const pBBHigh = sb.ZB._planToday();
if (pBBHigh.state !== 'bb' || pBBHigh.sub !== 'high' || pBBHigh.tier !== 'red' || pBBHigh.puTarget !== 1) {
  throw new Error('Self-test 5 failed: bb default high failed: ' + JSON.stringify(pBBHigh));
}
sb.ZB.setState('bb', 'max');
const pBBMax = sb.ZB._planToday();
if (pBBMax.sub !== 'max' || pBBMax.puTarget !== 0 || !pBBMax.title.includes('彻底休养')) {
  throw new Error('Self-test 5 failed: bb max should give full rest & puTarget=0: ' + JSON.stringify(pBBMax));
}
sb.ZB.setState('bb', 'light');
const pBBLight = sb.ZB._planToday();
if (!pBBLight.isPZMain || pBBLight.sub !== 'light' || !pBBLight.altAction || pBBLight.altAction.type !== 'to_rest') {
  throw new Error('Self-test 5 failed: bb light on easy PZ class should offer PZ with to_rest alt: ' + JSON.stringify(pBBLight));
}
sb.ZB.setPZIdx(2); // FTP Test
const pBBLightFtp = sb.ZB._planToday();
if (pBBLightFtp.isPZMain || pBBLightFtp.actionType !== 'rest' || !pBBLightFtp.altAction || pBBLightFtp.altAction.type !== 'light_ride') {
  throw new Error('Self-test 5 failed: bb light on FTP test should default to rest with optional light_ride: ' + JSON.stringify(pBBLightFtp));
}
sb.ZB.setState('tired', 'sleep');
const pSleep = sb.ZB._planToday();
if (pSleep.isPZMain || pSleep.actionType !== 'rest' || pSleep.puTarget !== 0 || !pSleep.title.includes('早睡')) {
  throw new Error('Self-test 5 failed: tired sleep MUST default to sleep/rest with puTarget=0: ' + JSON.stringify(pSleep));
}
sb.ZB.setState('tired', 'sore');
const pSore = sb.ZB._planToday();
if (pSore.tier !== 'red' || pSore.puTarget !== 0 || !pSore.title.includes('拉伸')) {
  throw new Error('Self-test 5 failed: tired sore should recommend stretch rest & puTarget=0: ' + JSON.stringify(pSore));
}
sb.ZB.setState('rest');
const pRest = sb.ZB._planToday();
if (pRest.tier !== 'green' || pRest.puTarget !== 0) {
  throw new Error('Self-test 5 failed: rest day must be calm green & puTarget=0: ' + JSON.stringify(pRest));
}
// Verify auto-recovery days & basketball-aware staleness on synthetic dates
const zst = sb.ZB._getState();
zst.days['2026-12-01'] = { ts: 1, pz_done: 2, pelo: 'done', pelo_min: 30 }; // FTP Test
const pPostFtp = sb.ZB._planOn('2026-12-02');
if (pPostFtp.isPZMain || pPostFtp.actionType !== 'rest' || !pPostFtp.altAction || pPostFtp.altAction.type !== 'override_pz') {
  throw new Error('Self-test 5 failed: day after FTP test should auto-rest with override_pz: ' + JSON.stringify(pPostFtp));
}
zst.days['2026-12-04'] = { ts: 1, bb: 'high' };
zst.days['2026-12-05'] = { ts: 1, pz_done: 3, pelo: 'done', pelo_min: 30 };
zst.days['2026-12-06'] = { ts: 1, bb: 'high' };
const pStreak3 = sb.ZB._planOn('2026-12-07');
if (pStreak3.isPZMain || pStreak3.actionType !== 'rest' || !pStreak3.tierText.includes('连练')) {
  throw new Error('Self-test 5 failed: 3 consecutive active days should trigger auto-rest: ' + JSON.stringify(pStreak3));
}
// Weekly cap >= 5 triggers auto-rest even when next class is PZE
zst.pz = { idx: 3, ts: 1, last: '2026-11-30' };
zst.days['2026-11-23'] = { ts: 1, bb: 'high' };
zst.days['2026-11-24'] = { ts: 1, pz_done: 3, pelo: 'done', pelo_min: 30 };
zst.days['2026-11-26'] = { ts: 1, bb: 'high' };
zst.days['2026-11-27'] = { ts: 1, pz_done: 3, pelo: 'done', pelo_min: 30 };
zst.days['2026-11-28'] = { ts: 1, bb: 'high' };
const pWeekCap = sb.ZB._planOn('2026-11-29');
if (pWeekCap.isPZMain || pWeekCap.actionType !== 'rest') {
  throw new Error('Self-test 5 failed: weekly >=5 combined workouts should auto-rest even for PZE: ' + JSON.stringify(pWeekCap));
}
// 5 days gap should NOT trigger yellow/red panic; 8 days with 2 basketball games still calm
zst.pz = { idx: 3, ts: 1, last: '2026-11-01' };
const pGap5 = sb.ZB._planOn('2026-11-06');
if (pGap5.stale !== 'none' || pGap5.tier !== 'green') {
  throw new Error('Self-test 5 failed: 5-day gap should stay calm green: ' + JSON.stringify(pGap5));
}
zst.days['2026-11-03'] = { ts: 1, bb: 'high' };
zst.days['2026-11-06'] = { ts: 1, bb: 'high' };
const pGap8BB = sb.ZB._planOn('2026-11-09');
if (pGap8BB.stale !== 'none') {
  throw new Error('Self-test 5 failed: 8-day PZ gap with 2 basketball games should stay calm: ' + JSON.stringify(pGap8BB));
}
const pGap8Idle = sb.ZB._planOn('2026-11-18');
if (pGap8Idle.stale !== 'remind') {
  throw new Error('Self-test 5 failed: 17-day idle gap should gently remind: ' + JSON.stringify(pGap8Idle));
}
// Watch auto-readiness: short sleep (<5.8h) -> Yellow early-sleep protection; severe HRV crash -> Red recovery
zst.vitals = { rhr: 38, rhr_date: '2026-12-10', hrv: 124, hrv_base: 102, hrv_date: '2026-12-10', sleep_h: 5.1, sleep_date: '2026-12-10' };
const pShortSleep = sb.ZB._planOn('2026-12-10');
if (pShortSleep.isPZMain || pShortSleep.tier !== 'yellow' || pShortSleep.puTarget !== 0) {
  throw new Error('Self-test 5 failed: watch short sleep <5.8h should auto-protect: ' + JSON.stringify(pShortSleep));
}
zst.vitals = { rhr: 38, rhr_date: '2026-12-11', hrv: 70, hrv_base: 102, hrv_date: '2026-12-11', sleep_h: 7.5, sleep_date: '2026-12-11' };
const pCrashHRV = sb.ZB._planOn('2026-12-11');
if (pCrashHRV.isPZMain || pCrashHRV.tier !== 'red' || pCrashHRV.puTarget !== 0) {
  throw new Error('Self-test 5 failed: severe watch HRV crash should trigger red recovery: ' + JSON.stringify(pCrashHRV));
}
zst.vitals = { rhr: 38, rhr_date: '2026-11-22', hrv: 124, hrv_base: 102, hrv_date: '2026-11-21', sleep_h: 7.5, sleep_date: '2026-11-21', vo2: 52.0 };
// Restore clean today state and test main CTA + undo + modals
sb.ZB.setState('normal');
sb.ZB.setPZIdx(1);
sb.ZB.logCardio('main');
const pDone = sb.ZB._planToday();
if (!pDone.ctaDone || !pDone.cardioDone) {
  throw new Error('Self-test 5 failed: completing PZ main did not mark done');
}
sb.ZB.logCardio('main'); // undo
const pUndone = sb.ZB._planToday();
if (pUndone.ctaDone || pUndone.cur.idx !== 1) {
  throw new Error('Self-test 5 failed: undo did not restore pz idx=1: ' + JSON.stringify(pUndone));
}
sb.ZB.openPeloGuide();
sb.ZB.openPZList(0);
const pzModalHtml = (els['modal-content'] && els['modal-content'].innerHTML) || '';
if (!pzModalHtml.includes('第 1 章') || !pzModalHtml.includes('2–4 场球') || pzModalHtml.includes('—')) {
  throw new Error('Self-test 5 failed: openPZList(0) missing chapter header or basketball pacing note or has em dash!');
}
sb.ZB.openPZList(1);
sb.closeModal();
// Self-test 6: Post-Listening 5-Min Contextual Review (Selective Re-Learn + Tail Check) & Ear-First 2/3 Vocab Graduation
const rvItems = sb.getRadioReviewItems();
if (!Array.isArray(rvItems) || rvItems.length < 6) {
  throw new Error('Self-test 6 failed: expected >=6 episode review_items, got ' + (rvItems && rvItems.length));
}
sb.switchMode('radio', false);
sb.openRadioReview(true);
const rvHtml1 = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!rvHtml1.includes('听后复盘') || !rvHtml1.includes('重学这个') || !rvHtml1.includes('懂了') || rvHtml1.includes('—')) {
  throw new Error('Self-test 6 failed: triage view missing core controls or contains em dash');
}
const clipKey1 = vm.runInNewContext('rvClipPlayingKey', sb);
if (clipKey1 !== 'clip_1') {
  throw new Error('Self-test 6 failed: review card must directly auto-play contextual podcast clip');
}
// Flag ONLY the first item for selective deep contextual re-learn; fast-pass all remaining items!
sb.handleRadioReviewRelearn();
const rvRelearnHtml = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!rvRelearnHtml.includes('语境精学') || !rvRelearnHtml.includes('原声语境') || !rvRelearnHtml.includes('0.85x') || rvRelearnHtml.includes('—')) {
  throw new Error('Self-test 6 failed: selective relearn view missing audio context/0.85x or contains em dash');
}
sb.finishRadioRelearnStep();
// Fast-pass remaining triage items synchronously without animation delay check
const origSetTimeout = sb.setTimeout;
sb.setTimeout = (fn) => { fn(); return 1; };
for (let i = 1; i < rvItems.length; i++) {
  sb.handleRadioReviewPass();
}
const rvTailHtml = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!rvTailHtml.includes('收尾复查') || !rvTailHtml.includes('仅余 1 项')) {
  throw new Error('Self-test 6 failed: expected tail blind re-check on ONLY the 1 re-learned item, got: ' + rvTailHtml.slice(0, 260));
}
sb.handleRadioReviewPass();
const rvDoneHtml = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!rvDoneHtml.includes('本次重学 1 项')) {
  throw new Error('Self-test 6 failed: expected completion summary for 1 re-learned item');
}
sb.setTimeout = origSetTimeout;
sb.closeRadioReview();
// Verify Ear-First 2/3 Vocab Graduation veil activates ONLY on streak===2 kanji cards with audio
const sampleKanji = '予算';
const spec2 = sb.getVocabCardSpec(sampleKanji);
if (!spec2 || spec2.mode !== 'kanji_read') {
  throw new Error('Self-test 6 failed: expected 予算 kanji_read spec');
}
sb.setMasteryTier(sampleKanji, 'wip2:20261121', Math.floor(Date.now() / 1000) + 10);
if (!sb.isEarFirstGradCard(spec2)) {
  throw new Error('Self-test 6 failed: streak=2 kanji card with audio should activate Ear-First graduation');
}
sb.setMasteryTier(sampleKanji, 'wip1:20261121', Math.floor(Date.now() / 1000) + 20);
if (sb.isEarFirstGradCard(spec2)) {
  throw new Error('Self-test 6 failed: streak=1 kanji card must stay silent-kanji front');
}
// Self-test 7: Atomic 1-by-1 Zen Open-Canvas Grammar Audit (zero grouped buckets, zero spoilers, zero waste words)
const gaData = vm.runInNewContext('DATA.grammar_audit', sb);
if (!gaData || !Array.isArray(gaData.items) || gaData.items.length !== 173) {
  throw new Error('Self-test 7 failed: grammar_audit must contain 173 atomic 1-by-1 points, got ' + (gaData && gaData.items ? gaData.items.length : 0));
}
const gaSpoilerRe = /[（(](?![ぁ-んァ-ヶー]+[）)])[^）)]*[）)]/;
for (const it of gaData.items) {
  if (!it.gid || !it.name || !it.front_name || !it.meaning || !it.ex_ja || !it.audio) {
    throw new Error('Self-test 7 failed: incomplete grammar_audit item ' + JSON.stringify(it));
  }
  if (gaSpoilerRe.test(it.front_name)) {
    throw new Error('Self-test 7 failed: semantic spoiler leaked in front_name of ' + it.gid + ': ' + it.front_name);
  }
  if (String(it.name).includes('動詞组') || String(it.name).includes('敬语升级') || String(it.meaning).startsWith('如 ') || String(it.meaning).includes('待验')) {
    throw new Error('Self-test 7 failed: grouped bucket or dirty CSV note leaked in ' + it.gid + ': ' + it.name + ' / ' + it.meaning);
  }
  if (String(it.meaning).includes('—') || String(it.rule || '').includes('—')) {
    throw new Error('Self-test 7 failed: em dash found in grammar_audit item ' + it.gid);
  }
}
const gaById = Object.fromEntries(gaData.items.map(x => [x.gid, x]));
if (!gaById['G-116a'] || gaById['G-116a'].name !== 'いらっしゃる' || !gaById['G-116b'] || gaById['G-116b'].name !== '召し上がる' || !gaById['G-119a'] || gaById['G-119a'].name !== '伺う' || !gaById['G-117a'] || gaById['G-117a'].name !== '〜てくださる' || gaById['G-116'] || gaById['G-119'] || gaById['G-117']) {
  throw new Error('Self-test 7 failed: keigo groups were not cleanly split 1-by-1');
}
if (gaById['G-047'].front_name !== '〜ことがある' || gaById['G-017'].front_name !== '〜ことだ' || gaById['G-134'].front_name !== '〜そうだ' || gaById['G-057'].front_name !== '〜ために ①' || gaById['G-058'].front_name !== '〜ために ②' || gaById['G-010'].front_name !== '〜あいだ（に）' || gaById['G-011'].front_name !== '〜あまり（に）') {
  throw new Error('Self-test 7 failed: unexpected front_name mapping: ' + JSON.stringify(['G-047','G-017','G-134','G-057','G-058','G-010','G-011'].map(k => [k, gaById[k] && gaById[k].front_name])));
}
if (sb.stripGrammarSpoilerTitle('〜ことがある（経験）') !== '〜ことがある' || sb.stripGrammarSpoilerTitle('〜あいだ（に）') !== '〜あいだ（に）') {
  throw new Error('Self-test 7 failed: stripGrammarSpoilerTitle mismatch');
}
// Verify seamless legacy queue expansion (phone mid-session holding G-116 expands automatically to G-116a..f)
const migratedQ = sb.expandGAQueue(['G-116', 'G-119', 'G-004']);
if (migratedQ[0] !== 'G-116a' || migratedQ[5] !== 'G-116f' || migratedQ[6] !== 'G-119a' || migratedQ[migratedQ.length - 1] !== 'G-004') {
  throw new Error('Self-test 7 failed: legacy queue expansion failed: ' + JSON.stringify(migratedQ));
}
const planD = vm.runInNewContext('DATA.plan_date', sb);
const ptsLen = vm.runInNewContext('DATA.points.length', sb);
const m120Init = sb.computeDaily120Metrics();
if (planD === '2026-11-22') {
  if (ptsLen !== 50) throw new Error('Self-test 7 failed: 2026-11-22 deck must stay locked at 50 cards, got ' + ptsLen);
  if (m120Init.ga && m120Init.ga.requiredToday) throw new Error('Self-test 7 failed: 2026-11-22 must NOT require GA in 3rd Enso Dot!');
}
sb.switchMode('vocab');
sb.switchVocabSubMode('ga');
const gaSess = vm.runInNewContext('A.gaSess', sb);
if (!gaSess || !Array.isArray(gaSess.queue) || gaSess.queue.length !== 39) {
  throw new Error('Self-test 7 failed: initial GA batch should have 39 items, got ' + (gaSess && gaSess.queue ? gaSess.queue.length : -1));
}
const firstItem = gaData.items.find(x => x.gid === gaSess.queue[0]);
if (!firstItem || firstItem.pri !== 0) {
  throw new Error('Self-test 7 failed: GA batch must start with priority-0 blind spots (old-green untouched in Nov)!');
}
const gaHtml = (els['vocab-stage-box'] && els['vocab-stage-box'].innerHTML) || '';
if (!gaHtml.includes('ga-stage') || !gaHtml.includes('ga-spec-rail') || !gaHtml.includes('陌生') || !gaHtml.includes('易混') || !gaHtml.includes('看懂') || !gaHtml.includes('本能') || gaHtml.includes('—')) {
  throw new Error('Self-test 7 failed: GA open Zen stage or 4 stops missing, or contains em dash!');
}
for (const banned of ['vc-card', '光谱', '原账', '11月未测', '按住沿线', '这一秒的真实感觉', '脑中过一遍', 'vc-hook-tag', '今日 ']) {
  if (gaHtml.includes(banned)) {
    throw new Error('Self-test 7 failed: un-Zen box or waste word leaked in GA UI: ' + banned);
  }
}
if (gaHtml.includes(`id="ga-eyebrow">${firstItem.family}`)) {
  throw new Error('Self-test 7 failed: unflipped GA card leaked semantic family on eyebrow: ' + firstItem.family);
}
if (!gaHtml.includes(`id="ga-head">${firstItem.front_name}</div>`)) {
  throw new Error('Self-test 7 failed: unflipped GA card did not render clean front_name: ' + firstItem.front_name);
}
// Commit code=1 (陌生) before reveal -> reveals family & full name + unified Zen dock synchronously, sets todo mastery
sb.commitGASpectrum(1);
if (!els['ga-eyebrow'] || !String(els['ga-eyebrow'].textContent || '').includes(firstItem.family) || !els['ga-head'] || els['ga-head'].textContent !== firstItem.name) {
  throw new Error('Self-test 7 failed: revealing GA card did not unveil family & full name: ' + JSON.stringify({eye: els['ga-eyebrow'] && els['ga-eyebrow'].textContent, head: els['ga-head'] && els['ga-head'].textContent}));
}
const gaEntry1 = vm.runInNewContext(`A.gaMap["${firstItem.gid}"]`, sb);
const ov1 = vm.runInNewContext(`A.masteryOverrides[${JSON.stringify(firstItem.name)}]`, sb);
if (!Array.isArray(gaEntry1) || gaEntry1[0] !== 1 || !String(ov1 || '').startsWith('todo:')) {
  throw new Error('Self-test 7 failed: spectrum 1 did not set code=1 and todo mastery: ' + JSON.stringify({gaEntry1, ov1}));
}
// Undo writes CRDT code=0 tombstone cleanly
sb.undoLastGA();
const gaEntryUndo = vm.runInNewContext(`A.gaMap["${firstItem.gid}"]`, sb);
if (!Array.isArray(gaEntryUndo) || gaEntryUndo[0] !== 0) {
  throw new Error('Self-test 7 failed: undoLastGA did not write CRDT code=0 tombstone: ' + JSON.stringify(gaEntryUndo));
}
// Verify atomic split child syncs to parent group & henkei mastery (G-116e なさる -> K-005 + 尊敬語特殊動詞组)
sb.setLedgerGrammarSpectrum('G-116a', 4);
sb.setLedgerGrammarSpectrum('G-116e', 1);
const parentOv = vm.runInNewContext('A.masteryOverrides["尊敬語特殊動詞组"]', sb);
const hkOv = vm.runInNewContext('A.masteryOverrides["K-005"]', sb);
if (!String(parentOv || '').startsWith('todo:') || !String(hkOv || '').startsWith('todo:')) {
  throw new Error('Self-test 7 failed: split child did not aggregate weakest verdict to parent & K-005: ' + JSON.stringify({parentOv, hkOv}));
}
// Test all 4 spectrum stops via ledger inline adjuster + CRDT packet size & round-trip
const testItems = gaData.items.slice(0, 4);
sb.setLedgerGrammarSpectrum(testItems[0].gid, 1);
sb.setLedgerGrammarSpectrum(testItems[1].gid, 2);
sb.setLedgerGrammarSpectrum(testItems[2].gid, 3);
sb.setLedgerGrammarSpectrum(testItems[3].gid, 4);
const ovCheck = [
  vm.runInNewContext(`A.masteryOverrides[${JSON.stringify(testItems[0].name)}]`, sb),
  vm.runInNewContext(`A.masteryOverrides[${JSON.stringify(testItems[1].name)}]`, sb),
  vm.runInNewContext(`A.masteryOverrides[${JSON.stringify(testItems[2].name)}]`, sb),
  vm.runInNewContext(`A.masteryOverrides[${JSON.stringify(testItems[3].name)}]`, sb),
];
if (!String(ovCheck[0]).startsWith('todo:') || !String(ovCheck[1]).startsWith('todo:') || ovCheck[2] !== 'wip2:20261114' || ovCheck[3] !== 'done') {
  throw new Error('Self-test 7 failed: 4-step mastery mapping mismatch: ' + JSON.stringify(ovCheck));
}
const pktGa = sb.buildCompactPacket();
const pktBytes = Buffer.byteLength(JSON.stringify(pktGa), 'utf8');
if (!pktGa.ga || pktGa.ga[testItems[3].gid][0] !== 4 || pktBytes > 3750) {
  throw new Error('Self-test 7 failed: compact packet GA missing or oversized: bytes=' + pktBytes);
}
sb.switchMode('dash');
sb.selectDashMod('grammar');
sb.selectDashTier('todo');
sb.togglePtNote(0);
const dashHtml = (els['point-list'] && els['point-list'].innerHTML) || '';
if (!dashHtml.includes('setLedgerGrammarSpectrum') || !dashHtml.includes('li-ga-tag') || dashHtml.includes('—')) {
  throw new Error('Self-test 7 failed: dashboard grammar ledger missing inline spectrum controls or contains em dash!');
}
// Self-test 8: Peer-Reviewed Research Alignment Across All 5 Tabs (v46 Evidence-First Audit)
// 8.1 Radio speeds include 0.85x slow decoding (Zhao 1997)
const rSpeeds = vm.runInNewContext('RADIO_SPEEDS', sb);
if (!Array.isArray(rSpeeds) || !rSpeeds.includes(0.85)) {
  throw new Error('Self-test 8 failed: RADIO_SPEEDS must include 0.85x');
}
// 8.2 Vocab confusable-twin anti-interference + 2/3 Kana productive recall + Mnemonic fading + clean_audio
const vcTwins = vm.runInNewContext('DATA.vocab_twins || {}', sb);
if (!vcTwins['書類'] || !vcTwins['書類'].includes('種類')) {
  throw new Error('Self-test 8 failed: DATA.vocab_twins missing 書類<->種類 confusable pair');
}
const sampleKana = 'めったに';
const kSpec = sb.getVocabCardSpec(sampleKana);
if (!kSpec || kSpec.mode !== 'kana_meaning' || !kSpec.clean_audio) {
  throw new Error('Self-test 8 failed: めったに missing kana_meaning or clean_audio');
}
sb.setMasteryTier(sampleKana, 'wip2:20261120', Math.floor(Date.now() / 1000) + 30);
if (!sb.isKanaRecallGradCard(kSpec)) {
  throw new Error('Self-test 8 failed: streak=2 kana card must activate L1->L2 productive recall');
}
if (!sb.shouldFadeVocabMnemonic(kSpec)) {
  throw new Error('Self-test 8 failed: streak>=1 non-failed vocab card should fade auto-played mnemonic');
}
sb.setMasteryTier(sampleKana, 'todo:20261122', Math.floor(Date.now() / 1000) + 40);
if (sb.shouldFadeVocabMnemonic(kSpec)) {
  throw new Error('Self-test 8 failed: streak=0 card must NOT fade spoken mnemonic');
}
// 8.3 Delayed hotFamily interleaving (Rohrer & Taylor 2007 / Pan 2015)
const hotStepCheck = vm.runInNewContext('(() => { A.hotFamily = "DUMMY_FAM"; A.hotFamilyDueStep = A.step + 4; return A.hotFamilyDueStep > A.step; })()', sb);
if (!hotStepCheck) {
  throw new Error('Self-test 8 failed: delayed hotFamilyDueStep check failed');
}
// 8.4 Zen Body: 7-day rolling HRV SWC (single-night dip -> Zone 2, multi-night/7d low -> rest) + 80/20 BB->Zone 2 + RIR-1 3-round pullup
zst.pu_best = 3;
const pStg3 = sb.ZB._puStage();
if (!pStg3 || pStg3.targetRounds !== 3 || pStg3.defStrict !== 2) {
  throw new Error('Self-test 8 failed: pu_best=3 should switch to RIR-1 2x3 multi-set: ' + JSON.stringify(pStg3));
}
zst.pz = { idx: 6, ts: 1, last: '2026-12-15' }; // W2D1 hard PZ ride
zst.days['2026-12-14'] = { ts: 1, bb: 'high' };
zst.days['2026-12-16'] = { ts: 1, bb: 'high' };
zst.vitals = { rhr: 38, rhr_date: '2026-12-18', hrv: 112, hrv_7d: 108, hrv_base: 104, hrv_sd: 12, hrv_low_streak: 0, hrv_date: '2026-12-18', sleep_h: 7.5, sleep_date: '2026-12-18' };
const pPolar = sb.ZB._planOn('2026-12-18');
if (!pPolar || !String(pPolar.tierText || '').includes('80/20') || pPolar.isPZMain) {
  throw new Error('Self-test 8 failed: 2+ BB week on hard PZ class should auto-swap to 80/20 Zone 2 PZE: ' + JSON.stringify(pPolar));
}
// Single-night mild HRV dip with healthy 7d mean -> Zone 2 downshift (NOT full red/yellow sleep lockout)
zst.vitals = { rhr: 39, rhr_date: '2026-12-22', hrv: 90, hrv_7d: 103, hrv_base: 104, hrv_sd: 12, hrv_low_streak: 1, hrv_date: '2026-12-22', sleep_h: 7.4, sleep_date: '2026-12-22' };
const pMildHrv = sb.ZB._planOn('2026-12-22');
if (!pMildHrv || pMildHrv.tier === 'red' || !String(pMildHrv.title || '').includes('Zone 2')) {
  throw new Error('Self-test 8 failed: single-night mild HRV dip with normal 7d mean should downshift hard ride to Zone 2: ' + JSON.stringify(pMildHrv));
}
// 2 consecutive low HRV nights + dipped 7d mean -> full early-sleep protection
zst.vitals = { rhr: 39, rhr_date: '2026-12-23', hrv: 88, hrv_7d: 92, hrv_base: 104, hrv_sd: 12, hrv_low_streak: 2, hrv_date: '2026-12-23', sleep_h: 7.4, sleep_date: '2026-12-23' };
const pMultiHrv = sb.ZB._planOn('2026-12-23');
if (!pMultiHrv || pMultiHrv.tier !== 'yellow' || pMultiHrv.isPZMain) {
  throw new Error('Self-test 8 failed: 2-night / 7d-mean low HRV must trigger early-sleep protection: ' + JSON.stringify(pMultiHrv));
}
// 8.5 Dashboard ZPL ROI focus bar & zero em dashes
sb.switchMode('dash');
const roiEl = els['dash-roi-focus'];
if (!roiEl || !roiEl.innerHTML.includes('临门') || roiEl.innerHTML.includes('—')) {
  throw new Error('Self-test 8 failed: dashboard missing ZPL exam-ROI focus line or contains em dash');
}
// 8.6 Quiz 2/3 recall veil is self-paced tap-to-reveal (zero auto-timer rush, full-area overlay)
const qPt = vm.runInNewContext('DATA.points.find(p => p.primary && !p.primary.is_listening)', sb);
sb.setMasteryTier(qPt.point_key, 'wip2:20261121', Math.floor(Date.now() / 1000) + 60);
sb.setupCurrentTurn(qPt.id);
vm.runInNewContext('viewStage = "quiz";', sb);
sb.renderTutor();
const vHtml = (els['voice-card'] && els['voice-card'].innerHTML) || '';
const qRevBefore = vm.runInNewContext('quizChoicesRevealed', sb);
const qTimer = vm.runInNewContext('quizRecallTimer', sb);
if (qRevBefore !== false || qTimer !== null || !vHtml.includes('recall-veil-overlay') || vHtml.includes('—')) {
  throw new Error('Self-test 8 failed: 2/3 quiz veil must be self-paced tap-to-reveal without auto-timer');
}
sb.revealQuizChoicesNow();
if (vm.runInNewContext('quizChoicesRevealed', sb) !== true) {
  throw new Error('Self-test 8 failed: revealQuizChoicesNow did not unveil choices');
}
// 8.7 Podcast closing-chapter review gates Enso Ring #2 (85% after 60m audio -> 100% after review) + sync pkt.rv
sb.ensureRadioReviewState(true);
vm.runInNewContext('A.radioMaxSec = DATA.radio.duration_sec || 3600;', sb);
const mAudOnly = sb.computeDaily120Metrics();
if (!mAudOnly.radioAudioDone || mAudOnly.radioReviewDone || mAudOnly.radioDone || mAudOnly.radioRatio < 0.84 || mAudOnly.radioRatio > 0.86) {
  throw new Error('Self-test 8 failed: 60m audio done without closing review must leave Enso #2 at ~85% open: ' + JSON.stringify(mAudOnly));
}
sb.renderRadioChapters(0);
const chapHtml = (els['radio-chap-pills'] && els['radio-chap-pills'].innerHTML) || '';
if (!chapHtml.includes('radio-review-chap') || !chapHtml.includes('听后复盘') || chapHtml.includes('—')) {
  throw new Error('Self-test 8 failed: chapter strip missing closing 听后复盘 chapter or contains em dash');
}
vm.runInNewContext('A.radioReview.done = true; A.radioReview.triageIdx = (DATA.radio.review_items || []).length; A.radioReview.updatedAt = Math.floor(Date.now()/1000);', sb);
const mRadFull = sb.computeDaily120Metrics();
if (!mRadFull.radioDone || mRadFull.radioRatio !== 1.0) {
  throw new Error('Self-test 8 failed: completing closing review must seal Enso #2 to 100% green: ' + JSON.stringify(mRadFull));
}
const pktRv = sb.buildCompactPacket();
if (!Array.isArray(pktRv.rv) || pktRv.rv[0] !== 1 || Buffer.byteLength(JSON.stringify(pktRv), 'utf8') > 3750) {
  throw new Error('Self-test 8 failed: compact sync packet missing rv completion bit or oversized');
}
// Self-test 9: Real Voice Active Output ("听后开口 2 句") & Pronunciation Mirror ("读音照妖镜")
const spPrompts = sb.getRadioSpeakingPrompts();
if (!Array.isArray(spPrompts) || spPrompts.length < 2) {
  throw new Error('Self-test 9 failed: expected >=2 speaking_prompts, got ' + (spPrompts && spPrompts.length));
}
for (const sp of spPrompts) {
  if (!sp.prompt_ja || !sp.prompt_zh || !sp.model_ja || !Array.isArray(sp.target_stems) || !sp.target_stems.length) {
    throw new Error('Self-test 9 failed: incomplete speaking prompt ' + JSON.stringify(sp));
  }
  if ((sp.prompt_ja + sp.prompt_zh + sp.model_ja + sp.coaching_tip).includes('—')) {
    throw new Error('Self-test 9 failed: em dash found in speaking prompt ' + sp.id);
  }
}
const asr = sb.window.JA_ASR;
if (!asr) throw new Error('Self-test 9 failed: window.JA_ASR missing');
const pExact = asr.analyzePronunciation(['予算'], '予算', 'よさん', '予算を組む');
if (!pExact.ok) throw new Error('Self-test 9 failed: exact kanji match 予算 should pass: ' + JSON.stringify(pExact));
const pLong = asr.analyzePronunciation(['洋三'], '予算', 'よさん', '予算を組む');
if (pLong.ok || pLong.kind !== 'length') throw new Error('Self-test 9 failed: 洋三 vs 予算 should detect long-vowel slip: ' + JSON.stringify(pLong));
const pSok = asr.analyzePronunciation(['主張'], '出張', 'しゅっちょう', '海外出張');
if (pSok.ok || pSok.kind !== 'sokuon') throw new Error('Self-test 9 failed: 主張 vs 出張 should detect sokuon slip: ' + JSON.stringify(pSok));
const pDak = asr.analyzePronunciation(['柿'], '鍵', 'かぎ', '家の鍵');
if (pDak.ok || pDak.kind !== 'voicing') throw new Error('Self-test 9 failed: 柿 vs 鍵 should detect voicing slip: ' + JSON.stringify(pDak));
const pNear = asr.analyzePronunciation(['種類'], '書類', 'しょるい', '書類を出す');
if (pNear.ok || pNear.kind !== 'near') throw new Error('Self-test 9 failed: 種類 vs 書類 should detect near-miss: ' + JSON.stringify(pNear));
// Spoken grammar & habit trap checks
const sOk = asr.analyzeSpokenOutput(['体調が悪いので今日は早めに帰らせてもらってもいいですか'], { title: '〜させてもらう', target_stems: ['させてもら', '帰らせ'] });
if (!sOk.ok || sOk.traps.length !== 0) throw new Error('Self-test 9 failed: valid させてもらう should pass cleanly: ' + JSON.stringify(sOk));
const sCaus = asr.analyzeSpokenOutput(['体調が悪いので今日は早めに帰っていただけませんか'], { title: '〜させてもらう', target_stems: ['させてもら', '帰らせ'] });
if (sCaus.ok || !sCaus.traps.some(t => t.includes('使役'))) throw new Error('Self-test 9 failed: missing causative trap not caught: ' + JSON.stringify(sCaus));
const sDevoice = asr.analyzeSpokenOutput(['もう少しで終電に乗り遅れるところたった'], { title: 'ところだった', target_stems: ['ところだった'] });
if (sDevoice.ok || !sDevoice.traps.some(t => t.includes('だった'))) throw new Error('Self-test 9 failed: だった->たった devoicing trap not caught: ' + JSON.stringify(sDevoice));
const sNoToki = asr.detectSpokenTraps('家を出るの時雨が降りました');
if (!sNoToki.some(t => t.includes('時'))) throw new Error('Self-test 9 failed: V+の時 trap not caught');
const sWakeNa = asr.detectSpokenTraps('日本語が上手わけですね');
if (!sWakeNa.some(t => t.includes('な'))) throw new Error('Self-test 9 failed: na-adj+わけ missing な not caught');
const sHazu = asr.detectSpokenTraps('アイスコーヒーをお願いしたはずないんですが');
if (!sHazu.some(t => t.includes('はずなんですが'))) throw new Error('Self-test 9 failed: はずないんですが trap not caught');
// Graceful fallback render when browser lacks SpeechRecognition
sb.window.SpeechRecognition = undefined;
sb.window.webkitSpeechRecognition = undefined;
sb.openRadioSpeaking(0);
const spFallbackHtml = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!spFallbackHtml.includes('听后开口') || !spFallbackHtml.includes('不支持实时收音') || spFallbackHtml.includes('—')) {
  throw new Error('Self-test 9 failed: speaking fallback UI broken or contains em dash');
}
// Supported SpeechRecognition render in both 听后开口 2 句 & 记词 试读
sb.window.webkitSpeechRecognition = function() {};
sb.openRadioSpeaking(0);
const spMicHtml = (els['radio-review-stage'] && els['radio-review-stage'].innerHTML) || '';
if (!spMicHtml.includes('按下开口说日语') || !spMicHtml.includes('听问题') || spMicHtml.includes('—')) {
  throw new Error('Self-test 9 failed: speaking mic UI missing core controls or contains em dash');
}
sb.closeRadioReview();
sb.switchMode('vocab');
sb.switchVocabSubMode('vocab');
const vcMicHtml = (els['vocab-stage-box'] && els['vocab-stage-box'].innerHTML) || '';
if (!vcMicHtml.includes('vc-mic-btn') || !vcMicHtml.includes('试读') || vcMicHtml.includes('—')) {
  throw new Error('Self-test 9 failed: vocab card missing 试读 pronunciation mirror button or contains em dash');
}
// Self-test 10: Pixel Buds / Android Chrome MediaSession single-tap pause -> single-tap resume regression gate
sb.switchMode('radio', false);
const rpEl = vm.runInNewContext('radioPlayer', sb);
if (!sb.document.body.children.includes(rpEl)) {
  throw new Error('Self-test 10 failed: radioPlayer must be attached to document.body');
}
sb.toggleRadioPlay(true);
if (rpEl.paused || rpEl.muted || mediaSessionMock.playbackState !== 'playing') {
  throw new Error('Self-test 10 failed: play did not activate unmuted playing MediaSession: ' + JSON.stringify({paused:rpEl.paused, muted:rpEl.muted, state:mediaSessionMock.playbackState}));
}
if (!mediaSessionMock._handlers.play || !mediaSessionMock._handlers.pause || !mediaSessionMock._handlers.seekto) {
  throw new Error('Self-test 10 failed: MediaSession play/pause/seekto handlers missing');
}
if (!mediaSessionMock.metadata || !Array.isArray(mediaSessionMock.metadata.artwork) || mediaSessionMock.metadata.artwork.length < 1) {
  throw new Error('Self-test 10 failed: MediaSession metadata/artwork missing');
}
if (!mediaSessionMock._posState || !(mediaSessionMock._posState.duration > 0)) {
  throw new Error('Self-test 10 failed: MediaSession setPositionState not populated');
}
// Simulate background cache blob finishing & SW pendingEditionReload while listening
vm.runInNewContext('cachedRadioBlobUrl = "blob:mock-radio"; pendingEditionReload = true;', sb);
const loadsBeforePause = rpEl.loadCount;
const reloadsBeforePause = reloadCount;
// First Pixel Buds tap -> MediaSession pause
mediaSessionMock._handlers.pause();
if (!rpEl.paused) throw new Error('Self-test 10 failed: first earbud tap did not pause radioPlayer');
if (rpEl.muted) throw new Error('Self-test 10 failed: pausing MUST NEVER set radioPlayer.muted = true (kills Android MediaSession!)');
if (mediaSessionMock.playbackState !== 'paused') {
  throw new Error('Self-test 10 failed: MediaSession playbackState must be paused after pause, got ' + mediaSessionMock.playbackState);
}
sb.upgradeRadioToLocalBlobIfPaused();
if (rpEl.loadCount !== loadsBeforePause) {
  throw new Error('Self-test 10 failed: upgradeRadioToLocalBlobIfPaused called load() after playback started (kills MediaSession!)');
}
sb.flushPendingEditionReload();
if (reloadCount !== reloadsBeforePause) {
  throw new Error('Self-test 10 failed: flushPendingEditionReload reloaded page during active paused radio session!');
}
// Second Pixel Buds tap -> MediaSession play (even when screen is off / hidden!)
sb.document.visibilityState = 'hidden';
mediaSessionMock._handlers.play();
if (rpEl.paused || rpEl.muted || mediaSessionMock.playbackState !== 'playing') {
  throw new Error('Self-test 10 failed: second earbud tap did not resume radioPlayer cleanly: ' + JSON.stringify({paused:rpEl.paused, muted:rpEl.muted, state:mediaSessionMock.playbackState}));
}
if (rpEl.loadCount !== loadsBeforePause) {
  throw new Error('Self-test 10 failed: resuming via Pixel Buds unexpectedly called load()');
}
sb.document.visibilityState = 'visible';

// Self-test 11: Seamless Cross-Tab Radio Playback & Mini Bar Visibility
sb.switchMode('radio', false);
sb.toggleRadioPlay(true);
if (rpEl.paused) throw new Error('Self-test 11 failed: radioPlayer not playing after toggleRadioPlay');
sb.switchMode('vocab');
if (rpEl.paused) throw new Error('Self-test 11 failed: radioPlayer paused on switching to vocab tab!');
const miniBarEl = els['radio-mini-bar'];
if (!miniBarEl || miniBarEl.classList.contains('hidden')) {
  throw new Error('Self-test 11 failed: radio-mini-bar not visible after switching away from radio tab!');
}
sb.switchMode('tutor');
if (rpEl.paused) throw new Error('Self-test 11 failed: radioPlayer paused on switching to tutor tab!');
sb.switchMode('body');
if (rpEl.paused) throw new Error('Self-test 11 failed: radioPlayer paused on switching to body tab!');
sb.switchMode('dash');
if (rpEl.paused) throw new Error('Self-test 11 failed: radioPlayer paused on switching to dash tab!');
sb.switchMode('radio', false);
if (!miniBarEl.classList.contains('hidden')) {
  throw new Error('Self-test 11 failed: radio-mini-bar should be hidden on radio tab!');
}

// Self-test 12: Zen Vocab Frameless Kanso Ergonomics & Zero Redundant Mnemonic Re-Speak
sb.switchMode('vocab');
sb.switchVocabSubMode('vocab');
const zenVcHtml = (els['vocab-stage-box'] && els['vocab-stage-box'].innerHTML) || '';
if (!zenVcHtml.includes('vc-aux-row') || !zenVcHtml.includes('id="vc-replay-btn"') || !zenVcHtml.includes('id="vc-seal-btn"')) {
  throw new Error('Self-test 12 failed: vocab card missing Kanso thumb-zone vc-aux-row (太熟 / 重听)!');
}
if (zenVcHtml.includes('记音 ♪') || zenVcHtml.includes('↑ 太熟') || zenVcHtml.includes('—')) {
  throw new Error('Self-test 12 failed: vocab card contains cluttered ♪ / ↑ 太熟 / em dash!');
}
const metaChunk = zenVcHtml.split('vc-deck-area')[0] || '';
if (metaChunk.includes('<button')) {
  throw new Error('Self-test 12 failed: top meta-bar on vocab screen must remain read-only (上看下点)!');
}
// Reveal card once -> tapping card afterwards must NOT re-trigger speech (vcToken stays stable)
sb.revealVocabCard(true, false);
const tokAfterReveal = vm.runInNewContext('vcToken', sb);
sb.onVocabCardTapOrReplay();
const tokAfterTap = vm.runInNewContext('vcToken', sb);
if (tokAfterTap !== tokAfterReveal) {
  throw new Error('Self-test 12 failed: tapping revealed vocab card/mnemonic redundantly restarted speech!');
}
// Explicit thumb-zone 重听 button MUST still replay audio cleanly
sb.replayVocabAudio();
const tokAfterReplay = vm.runInNewContext('vcToken', sb);
if (tokAfterReplay <= tokAfterReveal) {
  throw new Error('Self-test 12 failed: explicit thumb-zone 重听 did not advance vcToken to replay!');
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
