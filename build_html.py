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


def _is_active_miss(p: dict) -> bool:
    st = resolve_point_status(p["point_key"])
    if st == "green":
        return False
    if st in ("red", "orange"):
        return True
    qid = p["id"]
    pk = p["point_key"]
    return (qid in recent_weak_keys) or (pk in recent_weak_keys)


def _spaced_wave_key(p: dict, allow_miss_top: bool = True):
    qid = p["id"]
    pk = p["point_key"]
    st = resolve_point_status(pk)
    streak = resolve_point_streak(pk)
    dsl = _days_since_last(qid)
    is_miss = _is_active_miss(p)
    in_focus = 1 if (qid in MEMORY_FOCUS or pk in MEMORY_FOCUS) else 0
    if st == "green":
        return (5, -dsl, -p["exam_weight"], qid)
    if is_miss and allow_miss_top:
        return (0, -p["roi_score"], -p["exam_weight"], qid)
    if dsl >= 999:
        # Tier 1: Brand-new unseen N3 syllabus point — rollout systematically by exam ROI!
        return (1, -p["exam_weight"], -in_focus, -p["roi_score"], qid)
    min_gap = 1 if _days_to_exam <= 4 else 2
    if dsl >= min_gap and not is_miss:
        # Tier 2: Spaced-repetition due (healthy >= 2-day confirmation gap before exam week)
        return (2, -dsl, streak, -p["exam_weight"], -in_focus, qid)
    if is_miss:
        # Tier 3: Overflow active misses beyond the 50% per-subject miss cap
        return (3, -p["roi_score"], -p["exam_weight"], qid)
    # Tier 4: Recently practiced yellow (days_since == 1) — only used when fresh & due are exhausted
    return (4, streak, -p["exam_weight"], -p["roi_score"], qid)


def select_balanced_spaced_deck(candidates: list[dict], cap: int) -> list[dict]:
    by_id = {p["id"]: p for p in candidates}
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    # Step A: Exact same-day deck lock (never reshuffle mid-day once today's 50 cards are generated)
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

    # Step C: Exam-ROI Balanced Subject Quotas (24 Grammar / 10 Listening / 8 Henkei / 8 Vocab for cap=50)
    remaining_cap = cap - len(chosen)
    if remaining_cap == 50:
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

    # Third pass: only if entire N3 syllabus non-green pool < cap, fill remaining with oldest green review cards
    if len(chosen) < cap:
        greens = [p for p in candidates if p["id"] not in chosen_ids]
        greens.sort(key=lambda p: _spaced_wave_key(p, allow_miss_top=False))
        for p in greens:
            if len(chosen) >= cap:
                break
            chosen.append(p)
            chosen_ids.add(p["id"])

    return chosen[:cap]


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
    mn_txt = clean_zen_text(vc_spec.get("mnemonic") or get_pronunciation_mnemonic(w, str(w_info.get("head") or "")))
    base_note = clean_zen_text(vc_spec.get("twin") or w_info.get("tip") or p.get("classroom_note") or "")
    combined_note = " · ".join(x for x in ([f"记音：{mn_txt}"] if mn_txt else []) + ([base_note] if base_note else []))
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
recent_weak_words = [
    it["name"]
    for it in vocab_items
    if it["tier"] != "done" and (it["name"] in recent_weak_keys or it["name"] in MEMORY_FOCUS)
]

vocab_base_done = sum(1 for it in vocab_items if it["tier"] == "done")
vocab_daily_count = tutor_prefs.vocab_daily_count(MEMORY_PREFS, day=plan_date_str)

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
    "vocab_daily_count": vocab_daily_count,
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
    max-height: 488px;
    min-height: 264px;
    background: var(--sheet);
    border: 1px solid var(--hairline-strong);
    border-radius: 12px;
    padding: 24px 22px 22px;
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
    margin-bottom: 16px;
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
    margin-top: 20px;
    min-height: 136px;
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
    margin-bottom: 7px;
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
  .vc-hook {
    margin-top: 12px;
    padding-top: 11px;
    border-top: 1px solid var(--hairline);
    font-size: 14.5px;
    color: var(--sumi);
    line-height: 1.6;
    letter-spacing: 0.01em;
  }
  .vc-hook-tag {
    display: inline-block;
    margin-right: 6px;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--ochre);
    letter-spacing: 0.08em;
    vertical-align: 1px;
  }
  .vc-twin {
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid var(--hairline);
    font-size: 14px;
    color: var(--ink-2);
    line-height: 1.56;
  }
  .vc-twin.sub {
    margin-top: 7px;
    padding-top: 0;
    border-top: none;
    font-size: 12.8px;
    color: var(--ink-3);
    line-height: 1.5;
  }
  @media (max-height: 700px) {
    .vc-card { padding: 18px 18px 16px; }
    .vc-cue { margin-bottom: 10px; }
    .vc-chunk { font-size: 26px; }
    .vc-reveal { margin-top: 14px; min-height: 118px; }
    .vc-hook { margin-top: 9px; padding-top: 8px; font-size: 13.8px; line-height: 1.52; }
    .vc-twin.sub { margin-top: 5px; font-size: 12.2px; }
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

  .zb-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 14px 0 18px; border-bottom: 1px solid var(--hairline); margin-bottom: 4px; }
  .zb-kpi-v { font-family: var(--serif-jp); font-size: 22px; font-weight: 600; color: var(--sumi); font-variant-numeric: tabular-nums; }
  .zb-kpi-l { font-size: 12px; color: var(--ink-3); margin-top: 4px; letter-spacing: 0.03em; }
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
              <div class="zb-ritual-left">
                <span class="zb-ritual-name">饮食节律</span>
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
const RADIO_SPEEDS = [1.0, 1.15, 1.3];
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
    if (!activeKind && radioIdle) {
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
    radioMaxSec: 0,
    radioPos: [0, 0],
    radioSig: RADIO_SIG,
    flashProg: [0, 0, 0, 0],
    vocabSess: null,
    pts: pts,
    tappedWords: [],
    wordLookups: {},
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
      const ma = (a.modality === "memorize" ? 0.25 : (a.modality === "both" ? 0.12 : 0)) + (A.pts[a.id].audioPrimed ? 0.10 : 0);
      const mb = (b.modality === "memorize" ? 0.25 : (b.modality === "both" ? 0.12 : 0)) + (A.pts[b.id].audioPrimed ? 0.10 : 0);
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

let listenSeqQueue = [];
let listenSeqTimer = null;

function stopQuizAudio() {
  playReqSeq += 1;
  listenSeqQueue = [];
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

function playQuizQuestionAudio(qObj, toggleIfSame) {
  if (!qObj) return;
  if (toggleIfSame && activeKind === "q" && (!player.paused || listenSeqQueue.length > 0 || listenSeqTimer)) {
    stopQuizAudio();
    return;
  }
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
  playMainClip(qObj.q_audio, "q", toggleIfSame);
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
let pendingRadioSeekSec = null;

function writeLocalRadioPos(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  try {
    localStorage.setItem(LEGACY_RADIO_POS_KEY, String(s));
    localStorage.setItem(RADIO_POS_KEY, String(s));
    // Clean stale earlier same-day revision keys so an explicit scrub back to 0 can never be resurrected
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

function applyRadioSeek(sec) {
  const dur = getEffectiveRadioDuration();
  const target = Math.max(0, Math.min(Math.max(0, dur - 2), Number(sec) || 0));
  pendingRadioSeekSec = target;
  lastSavedSec = target;
  if (radioPlayer.readyState >= 1) {
    try {
      radioPlayer.currentTime = target;
      if (Math.abs((radioPlayer.currentTime || 0) - target) <= 1.5) {
        pendingRadioSeekSec = null;
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
  if (Math.abs((radioPlayer.currentTime || 0) - target) > 1.5) {
    try {
      radioPlayer.currentTime = target;
    } catch (e) {}
  }
  if (Math.abs((radioPlayer.currentTime || 0) - target) <= 1.5) {
    pendingRadioSeekSec = null;
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

    radioPlayer.preload = "metadata";
    radioPlayer.src = DATA.radio.audio_url;
    if (savedPos > 2) {
      applyRadioSeek(savedPos);
    } else {
      lastSavedSec = 0;
      updateRadioLiveDisplay(0);
    }
    try { radioPlayer.load(); } catch (e) {}
  } else {
    const shownT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
    paintRadioSeekProgress(shownT);
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
    flushPendingRadioSeek();
    radioPlayer.playbackRate = radioSpeed;
    const p = radioPlayer.play();
    if (p && typeof p.then === "function") {
      p.then(() => { flushPendingRadioSeek(); }).catch(() => {});
    }
  } else {
    radioPlayer.pause();
  }
  syncRadioUI();
}

function markRadioPosByUser(t) {
  const s = Math.max(0, Math.floor(t || 0));
  A.radioPos = [s, nowUnixSec()];
  A.radioSig = RADIO_SIG;
  writeLocalRadioPos(s);
  saveAdaptiveState();
  scheduleCloudPush(800);
}

function seekRadioBy(delta) {
  ensureRadioReady();
  const dur = getEffectiveRadioDuration();
  const baseT = (pendingRadioSeekSec !== null) ? pendingRadioSeekSec : (radioPlayer.currentTime || 0);
  const nextT = Math.max(0, Math.min(dur - 1, baseT + delta));
  applyRadioSeek(nextT);
  markRadioPosByUser(nextT);
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

radioPlayer.addEventListener("play", () => {
  flushPendingRadioSeek();
  syncRadioUI();
});
radioPlayer.addEventListener("playing", () => {
  flushPendingRadioSeek();
  syncRadioUI();
});
radioPlayer.addEventListener("canplay", () => {
  flushPendingRadioSeek();
});
radioPlayer.addEventListener("pause", () => {
  syncRadioUI();
  if (pendingRadioSeekSec !== null) return;
  const t = Math.floor(radioPlayer.currentTime || 0);
  if (t > 2) {
    lastSavedSec = t;
    A.radioPos = [t, nowUnixSec()];
    A.radioSig = RADIO_SIG;
    if (t > (A.radioMaxSec || 0)) A.radioMaxSec = t;
    writeLocalRadioPos(t);
    saveAdaptiveState();
    scheduleCloudPush(200);
  }
});
radioPlayer.addEventListener("ended", () => {
  pendingRadioSeekSec = null;
  const dur = Math.ceil(radioPlayer.duration || DATA.radio.duration_sec || 2100);
  A.radioMaxSec = dur;
  A.radioPos = [0, nowUnixSec()];
  A.radioSig = RADIO_SIG;
  writeLocalRadioPos(0);
  saveAdaptiveState();
  renderGreenBoard();
  syncRadioUI();
  scheduleCloudPush(100);
});
radioPlayer.addEventListener("loadedmetadata", () => {
  if (pendingRadioSeekSec !== null) {
    flushPendingRadioSeek();
    updateRadioLiveDisplay(pendingRadioSeekSec !== null ? pendingRadioSeekSec : (radioPlayer.currentTime || 0));
  } else {
    updateRadioLiveDisplay(radioPlayer.currentTime || 0);
  }
  renderGreenBoard();
});
radioPlayer.addEventListener("timeupdate", () => {
  if (pendingRadioSeekSec !== null) {
    if (!flushPendingRadioSeek()) return;
  }
  const t = radioPlayer.currentTime || 0;
  updateRadioLiveDisplay(t);
  if (!radioPlayer.paused && Math.abs(t - lastSavedSec) >= 2) {
    lastSavedSec = t;
    A.radioPos = [Math.floor(t), nowUnixSec()];
    A.radioSig = RADIO_SIG;
    writeLocalRadioPos(t);
    saveAdaptiveState();
    if (Date.now() - lastRadioCloudPushMs > 60000) {
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
        A.hotFamily = null;
        A.step += 1;
        A.lastPointId = p.id;
        recomputeStatusesFromCRDT(A);
        const nextMs = applyMasteryAction(p.point_key, p.point, "recover", stamp);
        syncBackendRecord(p, activeQuizObj.id, val, true, false, nextMs, stamp);
      } else {
        ps.retryCardId = "";
        ps.greenAt = Math.max(stamp, (ps.retestAt || 0) + 1, (A.resetAt || 0) + 1);
        ps.status = "green";
        A.hotFamily = null;
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
      A.hotFamily = null;
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

  const trioEl = document.getElementById("enso-trio");
  if (trioEl) {
    const doneKey = `${m.quizDone ? 1 : 0}${m.radioDone ? 1 : 0}${m.flashDone ? 1 : 0}${bm.done ? 1 : 0}`;
    const rings = [
      { ratio: m.quizRatio, done: m.quizDone, label: `做题 ${m.greenCnt}/${m.totalCards}` },
      { ratio: m.radioRatio, done: m.radioDone, label: `随身听 ${m.listenedMins}/${m.targetMins}分` },
      { ratio: m.flashRatio, done: m.flashDone, label: `记词 ${m.flashDone ? "已完成" : m.flashSeen + "/" + m.flashTarget}` },
      { ratio: bm.ratio, done: bm.done, label: bm.label }
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
    let label = p.subject;
    if (isRetrySame) label += " · 乱序重考";
    else if (isVariant) label += " · 换题复考";
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
    overTxt = q.is_listening && ansIdx > 0 ? `本题过关 · 正解 ${ansIdx} · ${streakTxt}` : `本题过关 · ${streakTxt}`;
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

  box.innerHTML = `
    <div class="tutor-stamp right" id="tutor-st-right">${rightStampLabel}</div>
    <div class="tutor-stamp left${leftStampTone}" id="tutor-st-left">${leftStampLabel}</div>
    <div class="meta-bar">
      <span class="${overCls}">${escapeHtml(overTxt)}</span>
      <div class="quiet-actions">
        <button class="text-btn" onclick="playQuizQuestionAudio(activeQuizObj, true)">原题</button>
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
  if (m !== "tutor") stopQuizAudio();
  if (m !== "vocab") stopVocabAudioAndTimers();
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
  } else if (m === "body") {
    if (window.ZB && typeof window.ZB.onEnter === "function") window.ZB.onEnter();
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
      mnemonic: pre.mnemonic || w.mnemonic || "",
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
    mnemonic: w.mnemonic || "",
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

  // Note: Tapped words/phrases (A.tappedWords / A.wordLookups) are recorded silently to the cloud brain
  // without immediately altering active practice queues.

  // 1) Recently missed words (from tutor or Grok practice)
  const recentWeak = Array.isArray(DATA.recent_weak_words) ? DATA.recent_weak_words : [];
  recentWeak.slice(0, Math.min(8, maxN)).forEach(sw => tryAdd(sw));

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
    tryAdd(dueWip[i]);
  }

  // 3) Remaining 0/3 待攻克 words (fresh high-yield exam traps & kana verbs/adverbs)
  todoPool.forEach(nm => tryAdd(nm));

  // 4) Any leftover due cross-day reviews
  dueWip.forEach(nm => tryAdd(nm));

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
          ${card.mnemonic ? `<div class="vc-hook"><span class="vc-hook-tag">记音</span>${escapeHtml(card.mnemonic)}</div>` : ""}
          ${card.twin ? `<div class="vc-twin${card.mnemonic ? " sub" : ""}">${escapeHtml(card.twin)}</div>` : ""}
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
  const bm = (window.ZB && typeof window.ZB.getSummary === "function")
    ? window.ZB.getSummary()
    : { done: false, text: "0 / 3 项" };
  document.getElementById("modal-content").innerHTML = `
    <h3 class="modal-h">今日四修 · 日语与体律</h3>
    <p class="modal-body">
      ① 做题　　　<strong id="modal-green-cnt">${m.greenCnt} / ${m.totalCards} 题</strong><br/>
      ② 随身听　　<strong id="modal-radio-min">${m.listenedMins} / ${m.targetMins} 分钟</strong><br/>
      ③ 单手记词　<strong id="modal-flash-cnt">${m.flashDone ? "今日已完成" : `${m.flashSeen} / ${m.flashTarget} 词`}</strong><br/>
      ④ 体律　　　<strong id="modal-body-cnt">${bm.done ? "今日已完成" : bm.text}</strong><br/>
      当前预计分　<strong id="modal-proj-score">${m.projScore} / 180 分</strong>
    </p>
    <p class="modal-promise">四枚圆印依次对应做题、随身听、记词与体律；总表里每个词与考点需跨 3 天答对满 3/3 才算真正掌握。</p>
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
function flushPendingEditionReload() {
  if (!pendingEditionReload) return;
  if (!activeKind && radioPlayer.paused) {
    pendingEditionReload = false;
    reloadFreshEdition();
  }
}
radioPlayer.addEventListener("pause", () => setTimeout(flushPendingEditionReload, 400));
radioPlayer.addEventListener("ended", () => setTimeout(flushPendingEditionReload, 400));
if (typeof player !== "undefined" && player && player.addEventListener) {
  player.addEventListener("pause", () => setTimeout(flushPendingEditionReload, 450));
  player.addEventListener("ended", () => setTimeout(flushPendingEditionReload, 450));
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
        if (!activeKind && radioPlayer.paused) {
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
  const PZ_LIST = [
    [0, 1, 1, "15 min Intro to Power Zone Ride", "Matt Wilpers", 15, "easy", "入门认识 7 个功率区，全程坐姿无压力"],
    [0, 1, 2, "20 min Power Zone Beginner Ride", "Matt Wilpers", 20, "easy", "坐姿感受各档发力，为第 3 节 FTP 测试热身"],
    [0, 1, 3, "FTP 基线测试（10分热身 + 20分测试）", "Denis Morton", 30, "test", "先 10 min FTP Warm Up，紧接 20 min FTP Test；全力稳推测出 7 档功率区，结束点 Yes 保存"],
    [0, 1, 4, "30 min Power Zone Endurance Ride", "Christine D'Ercole", 30, "pze", "首节 Zone 2–3 稳态燃脂，配《锵锵三人行》最舒服"],
    [0, 1, 5, "20 min Low Impact Ride", "Matt Wilpers", 20, "easy", "全程坐姿低冲击，练踩踏顺滑度顺便松腿"],
    [0, 1, 6, "30 min Power Zone Endurance Ride", "Olivia Amato", 30, "pze", "Zone 2–3 稳态耐力，第 1 周顺利收尾"],
    [0, 2, 1, "30 min Power Zone Hip Hop Ride", "Matt Wilpers", 30, "hard", "首次触碰 Zone 4 节奏段，比耐力课更有挑战"],
    [0, 2, 2, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "45 分钟 Zone 2–3 黄金燃脂，刚好听大半期《锵锵》"],
    [0, 2, 3, "30 min Power Zone Endurance Ride", "Olivia Amato", 30, "pze", "中段 Zone 2–3 稳态过渡，护腿稳掉脂"],
    [0, 2, 4, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "45 分钟稳态耐力，第 2 周达标收官"],
    [0, 3, 1, "30 min Power Zone Ride", "Christine D'Ercole", 30, "hard", "Zone 3–4 进阶间歇，稳步拉高阈值"],
    [0, 3, 2, "45 min Power Zone Ride", "Matt Wilpers", 45, "hard", "Zone 3–5 主力强课，挑不打球、双腿轻松的日子骑"],
    [0, 3, 3, "30 min Power Zone Endurance 80s Ride", "Denis Morton", 30, "pze", "80 年代老歌 Zone 2–3 稳态，让双腿喘口气"],
    [0, 3, 4, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "45 分钟稳态燃脂，第 3 周收官"],
    [0, 4, 1, "45 min Power Zone Ride", "Denis Morton", 45, "hard", "巅峰周第 1 场：Zone 3–5 阈值强课"],
    [0, 4, 2, "45 min Power Zone Ride", "Olivia Amato / Sam Yo", 45, "hard", "巅峰周第 2 场：Zone 3–5 强课（按项目 W4 第 2 节骑）"],
    [0, 4, 3, "30 min Power Zone Endurance Ride", "Christine D'Ercole", 30, "pze", "两场强课后回落 Zone 2–3 恢复打底"],
    [0, 4, 4, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟 Zone 2–3 燃脂大课，正好听完整期《锵锵三人行》"],
    [0, 5, 1, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "进入结业减量周，保持 Zone 2–3 踩踏手感"],
    [0, 5, 2, "20 min Low Impact Ride", "Matt Wilpers", 20, "easy", "20 分钟极轻坐姿松腿，为结业复测蓄力"],
    [0, 5, 3, "30 min Power Zone Endurance Rock Ride", "Christine D'Ercole", 30, "pze", "摇滚稳态 Zone 2–3，轻推保持状态"],
    [0, 5, 4, "30 min Power Zone Endurance Pop Ride", "Olivia Amato", 30, "pze", "测前最后一节轻耐力，保留腿力给结业复测"],
    [0, 5, 5, "结业 FTP 复测（15分热身 + 20分测试）", "Matt Wilpers", 35, "test", "先 15 min FTP Warm Up，紧接 20 min FTP Test；刷新 7 档功率区、正式拿下 5 周结业！"],
    [1, 1, 1, "30 min Power Zone Endurance Ride", "Matt Wilpers", 30, "pze", "8 周燃脂底盘启动：全 Zone 2–3 不伤打球双腿"],
    [1, 1, 2, "30 min Power Zone Endurance Ride", "Sam Yo", 30, "pze", "Sam Yo 沉稳节奏，全程坐姿稳态燃脂"],
    [1, 1, 3, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "第 1 周长骑：45 分钟 Zone 2–3 稳态"],
    [1, 2, 1, "30 min Power Zone Endurance Ride", "Denis Morton", 30, "pze", "第 2 周起跑：30 分钟 Zone 2–3 稳态"],
    [1, 2, 2, "45 min Power Zone Endurance Ride", "Hannah Frankson", 45, "pze_long", "45 分钟节奏流畅 Zone 2–3 耐力"],
    [1, 2, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟稳态掉脂，完美配一期《锵锵》"],
    [1, 3, 1, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "第 3 周加量：45 分钟 Zone 2–3 稳态"],
    [1, 3, 2, "45 min Power Zone Endurance Ride", "Christian Vande Velde", 45, "pze_long", "前环法职业车手带队，踩踏效率极高"],
    [1, 3, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "60 分钟稳态耐力，打牢有氧底盘"],
    [1, 4, 1, "30 min Power Zone Endurance Ride", "Sam Yo", 30, "pze", "第 4 周恢复减量周：轻快 30 分钟稳态"],
    [1, 4, 2, "30 min Power Zone Endurance Ride", "Tunde Oyeneyin", 30, "pze", "30 分钟减量维持，让身体吸收前 3 周红利"],
    [1, 4, 3, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "减量周收官，下周体能上一个台阶"],
    [1, 5, 1, "45 min Power Zone Endurance Ride", "Christine D'Ercole", 45, "pze_long", "下半程启动：45 分钟沉稳 Zone 2–3"],
    [1, 5, 2, "45 min Power Zone Endurance Ride", "Matt Wilpers", 45, "pze_long", "45 分钟核心有氧耐力"],
    [1, 5, 3, "60 min Power Zone Endurance Ride", "Hannah Frankson", 60, "pze_long", "60 分钟长耐力，配《锵锵》一气呵成"],
    [1, 6, 1, "45 min Power Zone Endurance Ride", "Charlotte Weidenbach", 45, "pze_long", "第 6 周：45 分钟稳态燃脂"],
    [1, 6, 2, "45 min Power Zone Endurance Ride", "Ben Alldis", 45, "pze_long", "Ben Alldis 干脆利落少废话，最适合配播客"],
    [1, 6, 3, "75 min Power Zone Endurance Ride", "Matt Wilpers", 75, "pze_long", "75 分钟长耐力突破，选周末不打球日骑"],
    [1, 7, 1, "45 min Power Zone Endurance Ride", "Olivia Amato", 45, "pze_long", "第 7 周稳态维持"],
    [1, 7, 2, "45 min Power Zone Endurance Ride", "Erik Jäger", 45, "pze_long", "45 分钟稳态过渡"],
    [1, 7, 3, "90 min Power Zone Endurance Ride", "Matt Wilpers & Denis Morton", 90, "pze_long", "双教练 90 分钟耐力巅峰课，安排在周末满血日"],
    [1, 8, 1, "45 min Power Zone Endurance Ride", "Ben Alldis", 45, "pze_long", "结业减量周第 1 节：45 分钟稳态"],
    [1, 8, 2, "45 min Power Zone Endurance Ride", "Denis Morton", 45, "pze_long", "结业周第 2 节：45 分钟流畅稳态"],
    [1, 8, 3, "60 min Power Zone Endurance Ride", "Matt Wilpers", 60, "pze_long", "8 周 Boost Your Base 正式毕业收官！"]
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
        else wm.set(r[0], [r[0], r[1] || p[1], (r[2] && r[2] > 5) ? r[2] : p[2], (r[2] && r[2] > 5) ? (r[3] || p[3]) : (p[3] || r[3])]);
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
  function weekStats(ymd) {
    const mon = mondayOf(ymd);
    let bbH = 0, pM = 0, puR = 0;
    for (let i = 0; i < 7; i++) {
      const d = shiftD(mon, i);
      if (d > ymd) break;
      const b = bbOn(d); if (b && (b.level === "high" || b.level === "max")) bbH++;
      const p = peloOn(d); if (p && p.status === "done") pM++;
      puR += (dayE(d).pu || []).length;
    }
    return { bbH, pM, hard: bbH + pM, puR };
  }

  function makePZPlan(opts) {
    const cur = opts.cur, next = getPZMeta(Math.min(PZ_LIST.length, cur.idx + 1));
    const langTip = cur.pIdx === 0 ? "（勿进教练页、避开德语 DE 版；看不到英文版点左下角头像 → Preferences → Class Languages 开启 English）" : "";
    const progSub = cur.allDone
      ? "两套官方 Power Zone 项目已全部通关，继续稳态燃脂即可。"
      : `当前进度 ${cur.doneInProg} / ${cur.progTotal} 节；骑完这节还剩 ${Math.max(0, cur.remInProg - 1)} 节完结 ${cur.progName}。Peloton 新版支持按自己节奏推进，打球或休息不会锁课。`;
    return {
      tier: opts.tier || "green",
      tierText: opts.tierText,
      title: cur.title,
      shortLine: opts.shortLine || `${cur.code} · ${cur.coach} · ${cur.min} 分`,
      linkText: "找课 ›",
      ctaText: cur.allDone ? `记下 ${cur.min} 分钟` : `骑完这节 · 推进到 ${cur.numInProg}/${cur.progTotal}`,
      ctaDone: false,
      altAction: null,
      actionType: "pz_main",
      isPZMain: true,
      pzCls: cur,
      rideMin: cur.min,
      guide: {
        title: `今日唯一课程 · ${cur.code}`,
        items: [
          { k: "今天骑这节", v: `${cur.title}（${cur.coach} · ${cur.min} 分钟）`, sub: cur.cue, cur: true },
          { k: "Bike+ 一步找到", v: cur.entry, sub: (opts.extraNote || "直接照着这节骑，不用再去挑别的课。") + langTip },
          { k: "Power Zone 进度督促", v: `${cur.progName}（${cur.doneInProg}/${cur.progTotal}）`, sub: progSub }
        ],
        showSyllabus: true,
        canOverridePZ: false
      },
      cardioDone: false,
      puTarget: opts.puTarget != null ? opts.puTarget : 2,
      state: opts.state, sub: opts.sub, bb: opts.bb, pelo: opts.pelo, wk: opts.wk,
      cur, next, daysGap: opts.daysGap, isTravel: false
    };
  }

  function planFor(ymd) {
    const trip = tripOn(ymd), st = getDayState(ymd), bb = st.bb;
    const bbY = bbOn(shiftD(ymd, -1)), bb2 = bbOn(shiftD(ymd, -2));
    const pelo = peloOn(ymd), wk = weekStats(ymd), dObj = dayE(ymd);
    const rhr = (ST.vitals && ST.vitals.rhr) || 40;
    const curIdx = getPZIdx();
    const cur = getPZMeta(curIdx);
    const lastPZ = (ST.pz && ST.pz.last) || "";
    const daysGap = lastPZ ? daysDiff(lastPZ, ymd) : 0;
    const forcePZ = !!dObj.force_pz;
    const yestHeavyBB = !!(bbY && (bbY.level === "high" || bbY.level === "max"));
    const twoHeavyBB = yestHeavyBB && !!(bb2 && (bb2.level === "high" || bb2.level === "max"));

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
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: nextCls, daysGap: 0, isTravel: false
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
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap: 0, isTravel: true
      };
    }

    // 2. High RHR protection
    if (rhr >= 46 && !forcePZ) {
      const doneRest = !!(pelo && (pelo.status === "rest" || pelo.status === "recovery"));
      return {
        tier: "red", tierText: `红档 · 静息心率 ${rhr} 偏高`,
        title: "今晚早睡休养，不上车",
        shortLine: `心率回到 41 以下立刻续上 ${cur.code} · 可做 10 min 拉伸`,
        linkText: "安排 ›",
        ctaText: doneRest ? "已确认休养 ✓" : "好，今晚休养",
        ctaDone: doneRest,
        altAction: { label: (pelo && pelo.status === "recovery") ? "已轻踩 15 分 ✓" : "若想松腿 · 记 15 分排酸" },
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 0,
        guide: {
          title: "身体恢复优先 · 今晚安排",
          items: [
            { k: "为什么今天不骑", v: `静息心率 ${rhr}（平日基线 39–41）`, sub: "心肺还在恢复期，早睡比硬骑更能保状态。", cur: true },
            { k: "若想放松身体", v: "Classes → Stretching → 10 min Lower Body Stretch", sub: "先点右侧 FILTER → Clear；教练选 Hannah Corbin 或 Ben Alldis。" },
            { k: "主线不掉队", v: `恢复后立刻接回 ${cur.code}：${cur.title}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal} 节。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: doneRest, puTarget: 1,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    // 3. Basketball dynamic branches!
    if (st.mode === "bb") {
      const bbStat = (bb && bb.dur) ? `已同步篮球 ${bb.dur} 分${bb.kcal ? ` · ${bb.kcal} 大卡` : ""}` : "";
      if (st.sub === "max") {
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 篮球透支 · 强制休养",
          title: "禁上单车 · 拉伸早睡",
          shortLine: `10 min Lower Body Stretch (Hannah Corbin) · ${cur.code} 顺延`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认完全休养 ✓" : "好，今晚完全休养",
          ctaDone: restDone || true,
          altAction: null,
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "篮球拼透支 · 今晚强制休养",
            items: [
              { k: "今晚铁律", v: "彻底不上单车，补水补蛋白早睡", sub: bbStat || "高强度对抗已拉爆腿部与神经负荷，再骑只会增加膝踝受伤风险。", cur: true },
              { k: "唯一推荐放松课（10 分钟）", v: "Classes → Stretching → 10 min Lower Body Stretch", sub: "先点右侧 FILTER → Clear；教练首选 Hannah Corbin（也可搜 10 min Foam Rolling: Lower Body）。" },
              { k: "主线督促", v: `下节主线：${cur.code} · ${cur.title}`, sub: `等腿缓过来再推进，目前 ${cur.doneInProg}/${cur.progTotal} 节，距离完结还剩 ${cur.remInProg} 节。` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: true, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
        };
      }
      if (st.sub === "high") {
        const recDone = !!(pelo && pelo.status === "recovery");
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 正常全场已满额",
          title: recDone ? "15 min Recovery Ride" : "今晚休养，不上主线",
          shortLine: `${bbStat ? bbStat + " · " : ""}腿紧做 10 分拉伸或排酸 · ${cur.shortCode} 顺延`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认休养 ✓" : (recDone ? "已轻踩 15 分排酸 ✓" : "好，今晚休养"),
          ctaDone: true,
          altAction: { label: recDone ? "取消 15 分排酸" : "腿僵想动 · 记 15 分排酸" },
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 15,
          guide: {
            title: "全场篮球日 · 休息与排酸方案",
            items: [
              { k: "默认唯一决定", v: "今天心肺已达标，直接休养早睡最掉脂", sub: bbStat || "不要再叠 Power Zone 主线课，保住双腿弹性。", cur: true },
              { k: "若双腿发紧（二选一）", v: "拉伸：10 min Lower Body Stretch（Ben Alldis / Hannah Corbin）", sub: "或极轻排酸骑：Classes → Cycling → 清空 FILTER → 15 min Recovery Ride（Sam Yo，坐姿阻力 ≤35）。" },
              { k: "主线排期", v: `${cur.code} · ${cur.title}（${cur.coach} · ${cur.min} 分）`, sub: `顺延到下一个不打球日推进（当前 ${cur.doneInProg}/${cur.progTotal}）。` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: true, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
        };
      }
      // st.sub === "light" (轻投/半场): SMART check against next PZ class!
      if (cur.kind === "easy" || cur.kind === "pze" || forcePZ) {
        return makePZPlan({
          tier: "green",
          tierText: "绿档 · 轻投后顺手推主线",
          cur,
          shortLine: `${cur.code} · ${cur.coach} · ${cur.min} 分坐姿稳骑`,
          extraNote: "今天只轻投/半场耗腿不多，这节全程坐姿稳踩 Zone 2，正好把主线往前推一格！",
          puTarget: 2, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap
        });
      }
      const lightDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "done"));
      return {
        tier: "yellow", tierText: "黄档 · 轻投护腿日",
        title: "20 min Low Impact Ride",
        shortLine: `Sam Yo · 主线 ${cur.code}（${cur.kind === "test" ? "FTP测试" : cur.min + "分强课"}）留给满血日`,
        linkText: "找课 ›",
        ctaText: lightDone ? "已轻骑 20 分钟 ✓" : "记下轻骑 20 分",
        ctaDone: lightDone,
        altAction: null,
        actionType: "light_ride",
        isPZMain: false, pzCls: cur, rideMin: 20,
        guide: {
          title: "轻投半场 · 护腿选课",
          items: [
            { k: "今晚唯一课程", v: "20 min Low Impact Ride（Sam Yo 或 Matt Wilpers）", sub: "全程坐姿轻转腿配《锵锵三人行》，顺膝盖又保节奏。", cur: true },
            { k: "Bike+ 一步找到", v: "底栏 Classes → Cycling → 清空右侧 FILTER → 20 min · Low Impact", sub: "不站姿、不拉高阻力，骑完双腿反而更轻。" },
            { k: "为什么顺延主线", v: `下节主线是 ${cur.code}：${cur.title}（${cur.min} 分）`, sub: `${cur.kind === "test" ? "FTP 测试必须满血做才准" : "这节偏长/偏强，留给不打球日一次拿下"}；当前 ${cur.doneInProg}/${cur.progTotal}。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: lightDone, puTarget: 2,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    // 4. Tired dynamic branches!
    if (st.mode === "tired") {
      if (st.sub === "sore") {
        const restDone = !!(pelo && pelo.status === "rest");
        return {
          tier: "red", tierText: "红档 · 腿酸发沉 · 停骑休整",
          title: "今晚停骑 · 拉伸 10 分钟",
          shortLine: `10 min Lower Body Stretch (Ben Alldis) · ${cur.code} 明天接回`,
          linkText: "安排 ›",
          ctaText: restDone ? "已确认拉伸休养 ✓" : "好，今晚拉伸休养",
          ctaDone: restDone,
          altAction: null,
          actionType: "rest",
          isPZMain: false, pzCls: cur, rideMin: 0,
          guide: {
            title: "腿酸发沉 · 主动回血方案",
            items: [
              { k: "今晚唯一决定", v: "彻底停骑，给股四头肌和膝关节回血", sub: "腿沉硬顶容易代偿伤膝，今晚养好明天输出翻倍。", cur: true },
              { k: "推荐拉伸课（10 分钟）", v: "Classes → Stretching → 清空 FILTER → 10 min · Lower Body Stretch", sub: "教练首选 Ben Alldis 或 Hannah Corbin，拉完早睡。" },
              { k: "主线督促", v: `下节主线：${cur.code} · ${cur.title}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}，明天腿松快了立刻接上！` }
            ],
            showSyllabus: true, canOverridePZ: false
          },
          cardioDone: restDone, puTarget: 1,
          state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
        };
      }
      // st.sub === "sleep" (没睡好/只是困)
      if (cur.kind === "easy" || forcePZ) {
        return makePZPlan({
          tier: "yellow",
          tierText: "黄档 · 没睡好 · 轻启推主线",
          cur,
          shortLine: `${cur.code} · ${cur.coach} · 仅 ${cur.min} 分坐姿轻松完赛`,
          extraNote: `刚好轮到 ${cur.min} 分钟入门/低冲击轻课，全程坐姿不用拼力气，正好推进一节主线早点睡！`,
          puTarget: 1, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap
        });
      }
      const lightDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "done"));
      return {
        tier: "yellow", tierText: "黄档 · 没睡好 · 降档保节奏",
        title: "20 min Low Impact Ride",
        shortLine: `Sam Yo · 主线 ${cur.code}（${cur.min} 分）留给睡饱日`,
        linkText: "找课 ›",
        ctaText: lightDone ? "已轻骑 20 分钟 ✓" : "记下轻骑 20 分",
        ctaDone: lightDone,
        altAction: { label: (pelo && pelo.status === "rest") ? "已改彻底早睡 ✓" : "实在太困 · 今晚早睡" },
        actionType: "light_ride",
        isPZMain: false, pzCls: cur, rideMin: 20,
        guide: {
          title: "没睡好 · 轻骑保节奏方案",
          items: [
            { k: "今晚唯一课程", v: "20 min Low Impact Ride（Sam Yo 或 Matt Wilpers）", sub: "全程坐姿轻踩 20 分钟出微汗即可，配《锵锵三人行》很助眠。", cur: true },
            { k: "Bike+ 一步找到", v: "底栏 Classes → Cycling → 清空右侧 FILTER → 20 min · Low Impact", sub: "若困到眼皮打架，直接点下方「今晚早睡」不硬撑。" },
            { k: "主线督促", v: `睡饱后接回 ${cur.code}：${cur.title}（${cur.min} 分）`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}，还剩 ${cur.remInProg} 节完结。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: !!(pelo && (pelo.status === "recovery" || pelo.status === "done" || pelo.status === "rest")),
        puTarget: 1,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    // 5. Explicit Rest Day
    if (st.mode === "rest") {
      const restDone = !!(pelo && pelo.status === "rest");
      const warnStall = daysGap >= 3;
      return {
        tier: warnStall ? "yellow" : "green",
        tierText: warnStall ? `休息日 · 注意主线已停 ${daysGap} 天` : "休息日 · 主动休整",
        title: "今日正式休息，不上车",
        shortLine: warnStall ? `别断档！明天务必接回 ${cur.code}（${cur.title}）` : `守住饮食早睡即可 · 下次接回 ${cur.code}`,
        linkText: "安排 ›",
        ctaText: restDone ? "已确认今日休息 ✓" : "确认今日休息",
        ctaDone: restDone,
        altAction: null,
        actionType: "rest",
        isPZMain: false, pzCls: cur, rideMin: 0,
        guide: {
          title: "正式休息日 · 恢复与接续",
          items: [
            { k: "今日安排", v: "完全不上单车，把饮食节律和睡眠守住就是进步", sub: "若久坐腰腿僵，可选做 Classes → Stretching → 10 min Full Body Stretch（Ben Alldis）。", cur: true },
            { k: "Power Zone 主线督促", v: `${cur.progName}（已完成 ${cur.doneInProg}/${cur.progTotal}）`, sub: warnStall ? `主线已停 ${daysGap} 天，明天一定把 ${cur.code}（${cur.title}）骑上，千万别烂尾！` : `休息是为了更好推进，下个运动日直接骑 ${cur.code}：${cur.title}。` }
          ],
          showSyllabus: true, canOverridePZ: false
        },
        cardioDone: restDone, puTarget: 2,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    // 6. Normal day: smart auto-protection ONLY when back-to-back heavy basketball or yesterday heavy BB before FTP/hard class!
    if ((twoHeavyBB || (yestHeavyBB && (cur.kind === "test" || cur.kind === "hard"))) && !forcePZ) {
      const lightDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "done"));
      const why = twoHeavyBB ? "前两天连打高强度篮球" : "昨天刚打完全场篮球";
      return {
        tier: "yellow", tierText: "黄档 · 球后护腿",
        title: "20 min Low Impact Ride",
        shortLine: `${why} · ${cur.code}（${cur.kind === "test" ? "FTP测试" : "高强课"}）留给明天满血做`,
        linkText: "找课 ›",
        ctaText: lightDone ? "已轻骑 20 分钟 ✓" : "记下轻骑 20 分",
        ctaDone: lightDone,
        altAction: null,
        actionType: "light_ride",
        isPZMain: false, pzCls: cur, rideMin: 20,
        guide: {
          title: "球后次日 · 保护性轻骑",
          items: [
            { k: "今日唯一课程", v: "20 min Low Impact Ride（Sam Yo 或 Matt Wilpers）", sub: `${why}，今天坐姿轻踩排酸最护膝。`, cur: true },
            { k: "Bike+ 一步找到", v: "底栏 Classes → Cycling → 清空右侧 FILTER → 20 min · Low Impact", sub: "配《锵锵三人行》轻松转腿 20 分钟。" },
            { k: "主线不掉队", v: `明天满血推进 ${cur.code}：${cur.title}`, sub: cur.kind === "test" ? "FTP 测试在满血日测出的 7 档功率区才最准确。" : `当前 ${cur.doneInProg}/${cur.progTotal}，腿完全不酸也可点下方直接骑主线。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: lightDone, puTarget: 2,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    if (wk.hard >= 5 && (cur.kind === "hard" || cur.kind === "test") && !forcePZ) {
      const recDone = !!(pelo && (pelo.status === "recovery" || pelo.status === "rest" || pelo.status === "done"));
      return {
        tier: "yellow", tierText: `本周已满 ${wk.hard} 场 · 护腿`,
        title: "15 min Recovery Ride",
        shortLine: `Sam Yo · 本周强度已足，${cur.code} 留给下周初`,
        linkText: "找课 ›",
        ctaText: recDone ? "已轻踩 15 分钟 ✓" : "记下排酸 15 分",
        ctaDone: recDone,
        altAction: null,
        actionType: "light_ride",
        isPZMain: false, pzCls: cur, rideMin: 15,
        guide: {
          title: "本周满额 · 轻松排酸方案",
          items: [
            { k: "今日唯一课程", v: "15 min Recovery Ride（Sam Yo 或 Denis Morton）", sub: `本周已完成 ${wk.bbH} 场篮球 + ${wk.pM} 场主线骑行，今天轻踩排酸不透支。`, cur: true },
            { k: "Bike+ 一步找到", v: "底栏 Classes → Cycling → 清空右侧 FILTER → 15 min · Recovery", sub: "也可以直接切到「休息日」早睡。" },
            { k: "主线衔接", v: `下周首日立刻骑 ${cur.code}：${cur.title}`, sub: `当前 ${cur.doneInProg}/${cur.progTotal}。` }
          ],
          showSyllabus: true, canOverridePZ: true
        },
        cardioDone: true, puTarget: 2,
        state: st.mode, sub: st.sub, bb, pelo, wk, cur, next: cur, daysGap, isTravel: false
      };
    }

    // Default Normal Day: DIRECTLY ADVANCE THE EXACT NEXT POWER ZONE CLASS!
    const tier = daysGap >= 5 ? "red" : (daysGap >= 3 ? "yellow" : "green");
    const tierText = daysGap >= 5
      ? `主线停了 ${daysGap} 天 · 今晚务必接回`
      : (daysGap >= 3
        ? `主线已停 ${daysGap} 天 · 今晚接回`
        : (cur.kind === "test" ? "绿档 · 满血测 FTP" : (yestHeavyBB ? "绿档 · 球后稳态推主线" : "绿档 · 推进主线")));
    return makePZPlan({
      tier, tierText, cur,
      extraNote: cur.kind === "test"
        ? "今天没打球且状态正常，正好一口气完成 10 分热身 + 20 分 FTP 测试，锁死你的 7 档专属功率区！"
        : (yestHeavyBB ? "昨天打完球但今天这节是稳态/轻课，正好坐姿 Zone 2 排酸顺便推进主线。" : "直接照这节骑完打卡，自动推进到下一节，不用自己做选择。"),
      puTarget: 2, state: st.mode, sub: st.sub, bb, pelo, wk, daysGap
    });
  }

  function puStage() {
    const b = ST.pu_best || 1;
    if (b <= 1) return { idx: 0, name: "阶段一 · 门框单杠", title: "1 徒手 · 2 黑带慢放", sub: "微仰防碰头 · 单膝挂黑带 4 秒慢放", short: "1 徒手+黑带", defStrict: 1, neg: 2 };
    if (b === 2) return { idx: 1, name: "阶段二 · 门框单杠", title: "2 徒手 · 1 红带慢放", sub: "前 2 下直上不晃 · 末下红带 4 秒慢放", short: "2 徒手+红带", defStrict: 2, neg: 1 };
    if (b <= 4) return { idx: 2, name: "阶段三 · 连做突破", title: `${Math.min(3, b)} 个纯徒手`, sub: "完全脱带直上直下 · 每日 2 轮", short: `${Math.min(3, b)} 个纯拉`, defStrict: Math.min(3, b), neg: 0 };
    return { idx: 3, name: "阶段四 · 目标达成", title: `轻松 ${b} 连`, sub: "每日 2 轮从容维稳", short: `轻松 ${b} 连`, defStrict: Math.min(5, b), neg: 0 };
  }
  function puCooldown(day, target) {
    const rs = (day && day.pu) || [];
    if (rs.length === 1 && target >= 2) {
      const ts1 = rs[0] && rs[0][2];
      if (ts1) {
        const t1 = fmtEpochPT(ts1), t2 = fmtEpochPT(ts1 + 7200);
        return (Math.floor(Date.now() / 1000) < ts1 + 7200)
          ? `第 1 轮 ${t1} 已拉 · ${t2} 后第 2 轮`
          : `第 1 轮 ${t1} 已拉 · 可拉第 2 轮`;
      }
      return "第 1 轮已拉 · 隔 2 小时第 2 轮";
    }
    if (rs.length >= 2) {
      const ts2 = rs[1] && rs[1][2];
      return ts2 ? `今日 2 轮已于 ${fmtEpochPT(ts2)} 收工` : "今日 2 轮已收工";
    }
    return "";
  }
  function syncPUDefault() { PU_IN = puStage().defStrict; }

  function latestWB() {
    const arr = ST.wb || [];
    let lbf = null, lwt = null, bbf = null;
    for (const r of arr) {
      if (r[1]) lwt = r;
      if (r[2] && r[2] > 5) { lbf = r; if (!bbf || r[2] < bbf[2]) bbf = r; }
    }
    const wts = arr.filter(r => r[1]).slice(-5);
    const avgWt = wts.length ? +(wts.reduce((s, r) => s + r[1], 0) / wts.length).toFixed(1) : null;
    return { lbf, lwt, bbf, avgWt };
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
    if (ctxEl) ctxEl.textContent = "GE 体脂";
    const targetBf = (ST.targets && ST.targets.bf_ge) || 14.0;
    if (wb.lbf) {
      if (bfEl) bfEl.innerHTML = `${wb.lbf[2].toFixed(1)}<span class="zb-stat-unit">%</span>`;
      if (ge("zb-bf-sub")) ge("zb-bf-sub").textContent = `两年最低 ${wb.bbf ? wb.bbf[2].toFixed(1) : wb.lbf[2].toFixed(1)}%`;
      const rem = Math.max(0, wb.lbf[2] - targetBf);
      if (ge("zb-pace")) ge("zb-pace").textContent = rem > 0 ? `距 14% 剩 ${rem.toFixed(1)}%` : "已达 14% 目标";
    }
    if (wb.lwt) {
      if (wtEl) wtEl.innerHTML = `${wb.lwt[1].toFixed(1)}<span class="zb-stat-unit">kg</span>`;
      if (ge("zb-wt-sub")) ge("zb-wt-sub").textContent = wb.avgWt ? `近均 ${wb.avgWt}` : "";
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
    const dietDone = !!day.diet;

    const dl = ge("zb-date-lbl"); if (dl) dl.textContent = fmtCn(today);

    const tt = ge("zb-tier-txt");
    if (tt) { tt.textContent = plan.tierText; tt.className = "zb-tier " + (plan.tier === "red" ? "red" : plan.tier === "yellow" ? "yellow" : "green"); }

    const cur = plan.cur;
    const pzb = ge("zb-pz-btn");
    if (pzb && cur) {
      pzb.textContent = cur.allDone ? "PZ 47/47 通关 ›" : `${cur.progShort} ${cur.doneInProg}/${cur.progTotal} ›`;
      pzb.className = "zb-pz-btn" + (plan.daysGap >= 5 ? " urgent" : (plan.daysGap >= 3 ? " warn" : ""));
    }
    const pzf = ge("zb-pz-fill");
    if (pzf && cur) {
      pzf.style.width = `${cur.pct}%`;
      pzf.className = "zb-pz-fill" + (plan.daysGap >= 5 ? " urgent" : (plan.daysGap >= 3 ? " warn" : ""));
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
        ab.className = "zb-btn-quiet" + (plan.pelo && (plan.pelo.status === "recovery" || plan.pelo.status === "rest") ? " active" : "");
        wt.style.display = "none";
      } else {
        ab.style.display = "none";
        wt.style.display = "inline";
        wt.textContent = `本周 球${plan.wk.bbH} · 骑${plan.wk.pM} · 引体${plan.wk.puR}`;
      }
    }

    const cd = puCooldown(day, plan.puTarget);
    if (ge("zb-pu-hint")) ge("zb-pu-hint").textContent = plan.puTarget === 0 ? "旅途免练" : `${stg.short} · ${puDone}/${plan.puTarget} 轮`;
    const pd = ge("zb-pu-dots");
    if (pd) {
      if (plan.puTarget === 0) pd.innerHTML = `<span style="font-size:12.5px;color:var(--ink-3);">休</span>`;
      else {
        let h = "";
        for (let i = 1; i <= plan.puTarget; i++) h += `<button type="button" class="zb-round-dot ${puDone >= i ? "done" : ""}" onclick="ZB.quickPU(${i})">${puDone >= i ? "✓" : i}</button>`;
        pd.innerHTML = h;
      }
    }
    if (ge("zb-diet-hint")) ge("zb-diet-hint").textContent = dietDone ? "今日已稳住" : "蛋白够 · 晚未爆碳";
    const db = ge("zb-diet-btn");
    if (db) { db.className = "zb-tap-check" + (dietDone ? " done" : ""); db.textContent = dietDone ? "已达标 ✓" : "记达标"; }

    // Tab 2: Pullup
    if (ge("zb-pu-pr")) ge("zb-pu-pr").textContent = `最高 ${ST.pu_best || 1} / 5`;
    if (ge("zb-pu-eyebrow")) ge("zb-pu-eyebrow").textContent = `${stg.name} · ${puDone}/2 轮`;
    if (ge("zb-pu-title")) ge("zb-pu-title").textContent = stg.title;
    if (ge("zb-pu-sub")) ge("zb-pu-sub").textContent = cd || stg.sub;
    if (ge("zb-pu-val")) ge("zb-pu-val").textContent = String(PU_IN);
    const negN = Math.max(0, 3 - PU_IN);
    if (ge("zb-pu-neg")) ge("zb-pu-neg").textContent = negN > 0 ? `补 ${negN} 次单膝黑带 4 秒慢放` : "纯徒手 · 直上直下不甩腿";
    const plb = ge("zb-pu-log"), pub = ge("zb-pu-undo");
    if (plb && pub) {
      pub.style.display = puDone > 0 ? "inline-flex" : "none";
      if (puDone >= 2) { plb.textContent = "今日 2 轮已满 ✓"; plb.className = "zb-btn-primary is-done"; }
      else { plb.textContent = `记下第 ${puDone + 1} 轮`; plb.className = "zb-btn-primary"; }
    }
    const lad = ge("zb-pu-ladder");
    if (lad) {
      const stages = ["黑带", "红带", "纯拉", "5连"];
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
      ge("zb-wrem").textContent = wb.lbf ? `上次 ${wb.lbf[0].slice(5)}` : "尚未记录";
    }
    renderChart();

    // Tab 4: Ledger
    const kp = ge("zb-kpis");
    if (kp) kp.innerHTML = `<div><div class="zb-kpi-v">${ST.vitals && ST.vitals.rhr ? ST.vitals.rhr : "--"}</div><div class="zb-kpi-l">静息心率</div></div><div><div class="zb-kpi-v">${ST.vitals && ST.vitals.vo2 ? ST.vitals.vo2 : "--"}</div><div class="zb-kpi-l">摄氧量</div></div><div><div class="zb-kpi-v">${ST.pu_best || 1}<span style="font-size:13px;color:var(--ink-3);font-weight:400;"> / 5</span></div><div class="zb-kpi-l">标准引体</div></div>`;
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
              <button type="button" class="zb-ed-chip ${pr >= 2 ? "on" : ""}" onclick="ZB.edPU('${d}',2)">2 轮</button>
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
    if (ge("zb-sync-txt")) ge("zb-sync-txt").textContent = SYNC_NOTE || (ST.vitals && ST.vitals.last_drive_sync ? `已同步 ${ST.vitals.last_drive_sync}` : "加密同步就绪");
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
      links.push(`<button type="button" class="zb-btn-quiet active" onclick="ZB.overrideToPZ()">腿没事，今天照常骑 ${escapeHtml(p.cur.code)} ›</button>`);
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
    let rowsHtml = "", lastWk = 0;
    for (let i = 0; i < PZ_LIST.length; i++) {
      const r = PZ_LIST[i];
      if (r[0] !== pIdx) continue;
      if (r[1] !== lastWk) {
        lastWk = r[1];
        rowsHtml += `<div class="zb-pz-wk">Week ${r[1]}</div>`;
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
    mc.innerHTML = `
      <h3 class="modal-h">Power Zone 完整主线课表</h3>
      <div class="zb-pz-tabs">
        <button type="button" class="zb-pz-tab ${pIdx === 0 ? "active" : ""}" onclick="ZB.openPZList(0)">Discover (23节)</button>
        <button type="button" class="zb-pz-tab ${pIdx === 1 ? "active" : ""}" onclick="ZB.openPZList(1)">Boost Base (24节)</button>
      </div>
      <p class="zb-pz-note">${escapeHtml(prog.entry)}。点任意一节可把下一节校准到那里；Peloton 新版支持按自己节奏推进，打球休息不会锁课。</p>
      <div class="zb-pz-list">${rowsHtml}</div>
      <div class="dock-row">
        <button type="button" class="sumi-btn" onclick="closeModal()">返回</button>
      </div>`;
    mm.classList.add("open");
  }

  function openBandGuide() {
    const stg = puStage();
    const bIdx = stg.idx === 0 ? 0 : (stg.idx === 1 ? 1 : 2);
    showGuideModal("弹力带换绳路线", [
      { k: "阶段一 · 2026.11–2027.02", v: "现有黑带 25–65 lb（单膝约 10–15 kg）", sub: "每轮 1 个徒手 + 2 个单膝挂黑带 4 秒慢放。", cur: bIdx === 0 },
      { k: "阶段二 · 2027.03–2027.05", v: "换红细带 15–35 lb（单膝约 5–8 kg）", sub: "稳拉 2 个纯徒手后降档，每轮 2 徒手 + 1 红带慢放。", cur: bIdx === 1 },
      { k: "阶段三 · 2027.06–2027.12", v: "彻底拆绳 0 lb（纯徒手 3 → 5+ 连拉）", sub: "门框杠严禁跳上杠，偏客厅侧微仰防碰头；每轮 ≤3 下、每日 ≤2 轮。", cur: bIdx === 2 }
    ]);
  }

  function openGapsGuide() {
    const gs = (ST.vitals && ST.vitals.gaps) || [];
    if (!gs.length) return;
    showGuideModal("健康数据待补通", gs.map((g, i) => ({ k: `项目 ${i + 1}`, v: g })));
  }

  return {
    onEnter, onResume, unlockPass, stopPacer, getSummary, syncCircle, getHorizonHTML,
    openPeloGuide, openPZList, openBandGuide, openGapsGuide,
    _planToday() { return planFor(todayYmd()); },
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
        if (p.state === "tired" && p.sub === "sleep") {
          d.pelo = d.pelo === "rest" ? null : "rest"; d.pelo_min = 0;
          toast(d.pelo ? "好，今晚早睡恢复" : "已撤销");
        } else {
          d.pelo = d.pelo === "recovery" ? null : "recovery"; d.pelo_min = 15;
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
      if (!Array.isArray(d.pu)) d.pu = [];
      if (d.pu.length >= n) { d.pu = d.pu.slice(0, n - 1); toast(`已撤销第 ${n} 轮`); }
      else { while (d.pu.length < n) d.pu.push([stg.defStrict, stg.neg, nowS]); toast(n === 1 ? "第 1 轮已记 · 2 小时后再拉第 2 轮" : "第 2 轮已记 · 今日引体收工"); }
      schedPush(); render();
    },
    adjStrict(delta) { PU_IN = Math.max(0, Math.min(10, PU_IN + delta)); render(); },
    togglePacer() {
      if (PACER_ON) { stopPacer(true); return; }
      if ((dayE(todayYmd()).pu || []).length >= 2) { toast("今天 2 轮已满额，明天继续"); return; }
      startPacer();
    },
    togglePacerSound() {
      PACER_SND = !PACER_SND;
      const b = ge("zb-pacer-snd");
      if (b) { b.textContent = PACER_SND ? "轻音：开" : "轻音：关"; b.className = "zb-btn-quiet" + (PACER_SND ? " active" : ""); }
      if (PACER_SND) playChime(528);
    },
    logPU() {
      const d = ensureDay();
      if (!Array.isArray(d.pu)) d.pu = [];
      if (d.pu.length >= 2) { toast("今天 2 轮已满额，明天继续"); return; }
      const nowS = Math.floor(Date.now() / 1000);
      d.pu.push([PU_IN, Math.max(0, 3 - PU_IN), nowS]);
      if (PU_IN > (ST.pu_best || 1)) { ST.pu_best = PU_IN; ST.pu_best_ts = nowS; toast(`新纪录！标准不甩 ${PU_IN} 个`); }
      else toast(d.pu.length === 1 ? "第 1 轮已记 · 2 小时后再拉第 2 轮" : "第 2 轮已记 · 今日引体收工");
      schedPush(); render();
    },
    undoPU() {
      const d = ensureDay();
      if (Array.isArray(d.pu) && d.pu.length) { d.pu.pop(); schedPush(); render(); toast("已撤销上一轮"); }
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
      const t = todayYmd(), d = ensureDay(t);
      d.wt = wv; if (bf !== null) d.bf = bf;
      if (!Array.isArray(ST.wb)) ST.wb = [];
      const ix = ST.wb.findIndex(r => r[0] === t);
      const row = [t, wv, bf, "phone"];
      if (ix >= 0) ST.wb[ix] = row; else ST.wb.push(row);
      ST.wb.sort((a, b) => a[0].localeCompare(b[0]));
      this.toggleWForm(false); schedPush(); render();
      toast(bf !== null ? `已记 ${wv.toFixed(1)} kg · GE ${bf.toFixed(1)}%` : `已记体重 ${wv.toFixed(1)} kg`);
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
// Self-test 4: Every vocab card has a non-empty bilingual pronunciation mnemonic and zero em dashes
const vcObj = vm.runInNewContext('DATA.vocab_cards || {}', sb);
const vcKeys = Object.keys(vcObj);
if (vcKeys.length < 120) throw new Error('Self-test failed: vocab_cards unexpectedly small: ' + vcKeys.length);
for (const k of vcKeys) {
  const mn = String((vcObj[k] && vcObj[k].mnemonic) || '').trim();
  if (!mn) throw new Error('Self-test failed: missing mnemonic for vocab card ' + k);
  if (mn.includes('—')) throw new Error('Self-test failed: em dash in mnemonic for ' + k);
}
sb.switchMode('vocab');
const vcStageHtml = (els['vocab-stage-box'] && els['vocab-stage-box'].innerHTML) || '';
if (!vcStageHtml.includes('vc-hook')) {
  throw new Error('Self-test failed: vocab card did not render .vc-hook pronunciation mnemonic!');
}
// Self-test 5: Zen Body Dynamic State Coach & 47-Session Power Zone Engine
const pNorm = sb.ZB._planToday();
if (!pNorm || !pNorm.isPZMain || !pNorm.title.includes('Power Zone Beginner')) {
  throw new Error('Self-test 5 failed: normal day did not recommend W1D2 Power Zone Beginner: ' + JSON.stringify(pNorm));
}
sb.ZB.setState('bb');
const pBBHigh = sb.ZB._planToday();
if (pBBHigh.state !== 'bb' || pBBHigh.sub !== 'high' || pBBHigh.tier !== 'red' || pBBHigh.puTarget !== 1) {
  throw new Error('Self-test 5 failed: bb default high failed: ' + JSON.stringify(pBBHigh));
}
sb.ZB.setState('bb', 'max');
const pBBMax = sb.ZB._planToday();
if (pBBMax.sub !== 'max' || !pBBMax.title.includes('禁上单车')) {
  throw new Error('Self-test 5 failed: bb max failed: ' + JSON.stringify(pBBMax));
}
sb.ZB.setState('bb', 'light');
const pBBLight = sb.ZB._planToday();
if (!pBBLight.isPZMain || pBBLight.sub !== 'light') {
  throw new Error('Self-test 5 failed: bb light on easy PZ class should advance PZ: ' + JSON.stringify(pBBLight));
}
sb.ZB.setPZIdx(2); // FTP Test
const pBBLightFtp = sb.ZB._planToday();
if (pBBLightFtp.isPZMain || !pBBLightFtp.title.includes('Low Impact')) {
  throw new Error('Self-test 5 failed: bb light on FTP test should protect with Low Impact: ' + JSON.stringify(pBBLightFtp));
}
sb.ZB.setState('tired', 'sore');
const pSore = sb.ZB._planToday();
if (pSore.tier !== 'red' || !pSore.title.includes('拉伸')) {
  throw new Error('Self-test 5 failed: tired sore should recommend stretch rest: ' + JSON.stringify(pSore));
}
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
sb.ZB.openPZList(1);
sb.closeModal();
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
