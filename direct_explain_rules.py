#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct-to-Chinese Answer Explanation Builder (Zen v20 — Natural Human Tutor, Zero Robotic Filler).

User standing rule (2026-11-23 22:20 PT):
- NEVER say robotic test jargon like "考语法", "考词汇", "考汉字读音" in answer audio (`*_exp.mp3`).
  Hearing "考语法" before every single question sounds completely robotic and stupid ("听着很蠢").
- Start IMMEDIATELY at 0.00s in natural, brisk, conversational Chinese explaining the reasoning,
  grammar function, or word distinction directly (e.g. "前面有 たったいま，说明动作刚结束没几秒..." or
  "讲自然天性和世间常理的时候，动词原形后面接 ものだ...").
- NEVER re-read the Japanese question sentence or dialogue at the start of answer audio.
- Strip redundant "这句是说……" / "这句是在……" translation fluff (already visible on screen).
- Ensure 100% of inline Japanese tokens inside Chinese speech are written in pure Hiragana/Katakana with
  spaces around them so the multilingual neural voice switches phonology seamlessly.
- Strict Rule 4: Absolutely NO dashes ("—" or "——") anywhere in spoken text.
"""
from __future__ import annotations

import re
from typing import Any

KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
KANA_ONLY_RE = re.compile(r"^[\u3040-\u30ffー・]+$")

# Sentences that open with a redundant translation/scene-setter before the real explanation
TRANSLATION_OPENER_RE = re.compile(
    r"^(?:"
    r"这[句一]?话?(?:"
    r"是说|是在|说|吐槽|抱怨|感叹|安慰|庆幸|夸|问|提醒|向|是职场|是电车|是客气|是感谢|"
    r"是约|是在|是日本|是日常|是没赶上|是跟|是摸着|是转述|是正式|是商务|是请假|是天气|"
    r"是礼貌|是面试|是打工|是敬语|是吃货|是请|一开头|对话|画面|挺有画面|很有生活|挺暖心|"
    r"大家肯定|不好意思|狠狠吐槽|在课堂"
    r")"
    r"|同事问现在方不方便"
    r")"
)

EXPLICIT_EXPLAIN_OPENER_RE = re.compile(
    r"^这[句一]?话?(?:考的是|专门帮你|把\s|要注意|跟今天)"
)


def _infer_subject(qid: str, meta: dict[str, Any] | None) -> str:
    m = meta or {}
    pk = str(m.get("point_key") or "")
    if qid.startswith("H-") or pk.startswith("A-") or pk.startswith("K-") or pk.startswith("T-"):
        return "活用"
    if qid.startswith("V-"):
        return "語彙"
    if qid.startswith("Q-"):
        return "聴解"
    return "文法"


def _strip_translation_opener(qid: str, raw_t: str, subj: str) -> str:
    txt = str(raw_t or "").strip()
    if not txt:
        return txt
    if subj == "聴解":
        # Clean any stray fixed ordinal like "的第一项" since listening choices dynamically shuffle on retry
        txt = re.sub(r"的第[一二三123][项句个]", "", txt)
        return txt

    # Special card VAR5-11
    if qid == "VAR5-11":
        m_dot = re.search(r"[。！？]\s*(.+)$", txt)
        if m_dot:
            return "这是 らしい 最经典的接续坑。" + m_dot.group(1).strip()

    # Cards where Sentence 1 IS already an explanation (e.g. VAR4-V05, VAR-V32, VAR3-H13...)
    if EXPLICIT_EXPLAIN_OPENER_RE.match(txt):
        if txt.startswith("这句考的是"):
            return "这里是" + txt[5:]
        if txt.startswith("这句要注意"):
            return txt[2:]
        if txt.startswith("这句把"):
            return "直接把" + txt[3:]
        return txt

    # Standard 2+ sentence card with a redundant Sentence 1 translation/scene-setter
    if TRANSLATION_OPENER_RE.match(txt):
        m = re.match(r"^([^。！？]+[。！？])\s*(.+)$", txt)
        if m:
            rest = m.group(2).strip()
            if len(rest) >= 12:
                return rest

    return txt


def build_direct_exp_text(qid: str, card: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    """Return the direct, zero-reread Chinese+inline-Kana spoken explanation for any quiz card."""
    m = meta or {}
    subj = _infer_subject(qid, m)
    why_line = str(card.get("why_line") or "").strip()

    raw_t = " ".join(str(val).strip() for spk, val in (card.get("exp_turns") or []) if spk == "T").strip()
    if not raw_t:
        raw_t = f"{why_line} {card.get('form_line', '')}".strip()

    body = _strip_translation_opener(qid, raw_t, subj)

    # Clean any robotic test jargon or forced "考语法" prefixes
    body = re.sub(r"考语法\s*", "", body)
    body = re.sub(r"^考的是\s*", "这里是", body)
    body = re.sub(r"^考(?:汉字读音|副词|词汇|口语缩音|特殊尊敬语动词|特殊谦让语动词|动词变形|一段动词|五段动词)?\s*", "", body)
    body = body.replace("——", "，").replace("—", "，")
    body = re.sub(r"([。！？])[。！？]+", r"\1", body)
    body = re.sub(r"\s{2,}", " ", body).strip()
    return body


def build_direct_exp_turns(qid: str, card: dict[str, Any], meta: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """Return direct-to-Chinese exp_turns with ZERO leading Japanese sentence/dialogue re-read."""
    txt = build_direct_exp_text(qid, card, meta)
    return [("T", txt)] if txt else []


if __name__ == "__main__":
    from clear_explanations import CARDS_75
    from tutor_data import TUTOR_ITEMS

    bad = []
    for qid, card in CARDS_75.items():
        turns = build_direct_exp_turns(qid, card, TUTOR_ITEMS.get(qid))
        if len(turns) != 1 or turns[0][0] != "T":
            bad.append((qid, "non-T turns"))
            continue
        t = turns[0][1]
        if len(t) < 15:
            bad.append((qid, f"too short: {t}"))
        if "—" in t:
            bad.append((qid, f"contains dash: {t}"))
        if "考语法" in t:
            bad.append((qid, f"contains 考语法: {t}"))
        if t.startswith("考") and not t.startswith("考虑"):
            bad.append((qid, f"starts with 考: {t}"))
        if re.search(r"^这[句一]?话?(?:是说|是在|吐槽|抱怨|感叹|安慰|庆幸)", t):
            bad.append((qid, f"leading translation fluff: {t}"))

    if bad:
        print(f"FAILED on {len(bad)} cards:")
        for b in bad[:10]:
            print(" ", b)
        raise SystemExit(f"direct_explain_rules self-test FAILED ({len(bad)}): {bad[:5]}")
    print(f"direct_explain_rules self-test PASSED: {len(CARDS_75)}/{len(CARDS_75)} direct-Chinese zero-filler cards green!")
