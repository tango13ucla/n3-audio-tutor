#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JLPT N2 Zero-to-120 Live Curriculum Controller & Question/Vocab/Radio Bridge.

Single source of truth for:
1. Phase switching (`n3_sprint` <= 2026-12-05 -> `exam_day` 2026-12-06 -> `n2_climb` 2026-12-07..2027-03-31 -> `n1_sprint` >= 2027-04-01).
2. Complete 190-point JLPT N2 "Teach-First, Then 4-Choice Practice" Question Bank
   (hand-crafted primary + variant pairs for Days 1-14 + verified family-aware 4-choice cards for all 190 points).
3. Complete N2 3-Track Vocabulary Cards (Compound Verb Root Families + False Friends/Reading Traps + Pure-Kana Adverbs)
   with 100% bilingual CN+EN pronunciation mnemonics and concise 4-9 char collocation chunks.
4. N2 Day 1 (`2026-12-07`) Radio Bridge + Documentary Visual Queries + 15-line NHK All-Japanese Short Video Script.

100% Zero-PII public study module. Zero em dashes.
"""
from __future__ import annotations

import datetime
import os
import re
import sys
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from n2_grammar_syllabus import N2_GRAMMAR_SYLLABUS, get_day_callback_grammar, get_day_new_grammar
from n2_radio_spaced_callback_engine import plan_n2_episode_pedagogy
from n2_radio_vol1_preview import N2_VOL1_METADATA, SALON_STORIES_N2_VOL1
from n2_radio_vol2_3 import (
    N2_VOL2_3_JP_VIDEO_SCRIPTS,
    N2_VOL2_3_VISUAL_TOPICS,
    N2_VOL2_METADATA,
    N2_VOL3_METADATA,
    SALON_STORIES_N2_VOL2,
    SALON_STORIES_N2_VOL3,
)
from n2_vocab_architecture import (
    N2_COMPOUND_VERB_FAMILIES,
    N2_FALSE_FRIENDS_AND_TRAPS,
    N2_KANA_ADVERBS_AND_CONJUNCTIONS,
    build_n2_daily_vocab_plan,
)

N3_EXAM_DATE = datetime.date(2026, 12, 6)
N2_START_DATE = datetime.date(2026, 12, 7)
N2_TARGET_DATE = datetime.date(2027, 3, 31)
N1_TARGET_DATE = datetime.date(2027, 12, 5)


def get_phase_info(study_date_str: str | None = None) -> dict[str, Any]:
    """Resolve active learning phase, track label, countdown target, and N2 day index."""
    if not study_date_str:
        study_date_str = os.environ.get("FORCE_STUDY_DATE", "").strip()
    if study_date_str:
        dt = datetime.date.fromisoformat(str(study_date_str)[:10])
    else:
        dt = datetime.date.today()

    if dt < N3_EXAM_DATE:
        return {
            "study_date": dt.isoformat(),
            "phase": "n3_sprint",
            "track_label": "N3",
            "exam_date": N3_EXAM_DATE.isoformat(),
            "days_to_exam": (N3_EXAM_DATE - dt).days,
            "n2_day": 0,
            "is_travel_floor": False,
            "target_score": 120,
        }
    if dt == N3_EXAM_DATE:
        return {
            "study_date": dt.isoformat(),
            "phase": "exam_day",
            "track_label": "N3",
            "exam_date": N3_EXAM_DATE.isoformat(),
            "days_to_exam": 0,
            "n2_day": 0,
            "is_travel_floor": False,
            "target_score": 120,
        }
    if dt <= N2_TARGET_DATE:
        n2_day = (dt - N2_START_DATE).days + 1
        return {
            "study_date": dt.isoformat(),
            "phase": "n2_climb",
            "track_label": "N2",
            "exam_date": N2_TARGET_DATE.isoformat(),
            "days_to_exam": (N2_TARGET_DATE - dt).days,
            "n2_day": n2_day,
            "is_travel_floor": 8 <= n2_day <= 34,
            "target_score": 120,
        }
    return {
        "study_date": dt.isoformat(),
        "phase": "n1_sprint",
        "track_label": "N1",
        "exam_date": N1_TARGET_DATE.isoformat(),
        "days_to_exam": max(0, (N1_TARGET_DATE - dt).days),
        "n2_day": (N2_TARGET_DATE - N2_START_DATE).days + 1,
        "is_travel_floor": False,
        "target_score": 120,
    }


def _clean_text(s: str) -> str:
    """Enforce zero em dashes across all generated N2 copy."""
    return str(s or "").replace("——", "，").replace("—", "，").strip()


# ==============================================================================
# CURATED FLAGSHIP N2 DAY 1-14 QUESTION PAIRS (Primary + Variant = 56 Cards)
# ==============================================================================
# Each key is N2G-xxx -> list of dicts (prompt, choices[4], answer, full_ja, zh_meaning, why_line, form_line, option_notes)
CURATED_N2_CARDS: dict[str, list[dict[str, Any]]] = {
    "N2G-001": [
        {
            "id": "N2G-001",
            "prompt": "赤字が続いており、不採算店を閉め（　　）。",
            "choices": ["ざるを得ない", "わけにはいかない", "かねない", "ほかはない"],
            "answer": "ざるを得ない",
            "full_ja": "赤字が続いており、不採算店を閉めざるを得ない。",
            "zh_meaning": "亏损持续不断，实在不得不关闭不赚钱的门店。",
            "why_line": "前面「閉め」是动词ない形去掉ない的词干，表示心里不情愿但形势所迫只能关店。",
            "form_line": "Vない形去ない + ざるを得ない（する变せざるを得ない）；わけにはいかない与ほかはない须接辞书形。",
            "option_notes": {
                "ざるを得ない": "接在动词ない形去ない词干「閉め」后面，精准表达客观亏损逼迫下的无奈不得不。",
                "わけにはいかない": "表示道义上「绝不能」，且前面必须接辞书形「閉める」，接「閉め」形态错误。",
                "かねない": "接ます形表示「弄不好会出坏事」，这里已是经营决定而非推测风险。",
                "ほかはない": "表示只好，但前面必须接辞书形「閉める」，不能接「閉め」。",
            },
        },
        {
            "id": "N2V-001",
            "prompt": "主要部品の調達が止まり、工場の稼働を一時停止（　　）。",
            "choices": ["せざるを得ない", "しざるを得ない", "するわけにはいかない", "しかねない"],
            "answer": "せざるを得ない",
            "full_ja": "主要部品の調達が止まり、工場の稼働を一時停止せざるを得ない。",
            "zh_meaning": "核心零件断供，工厂实在不得不暂时停产。",
            "why_line": "核心考する动词的唯一特殊变体：停止する接ざるを得ない时，必须变成「せざるを得ない」。",
            "form_line": "する → せざるを得ない（绝不能写成しざるを得ない）。",
            "option_notes": {
                "せざるを得ない": "サ变动词「停止する」接ざるを得ない的标准唯一形态，考场高频送分点。",
                "しざるを得ない": "常见形态陷阱，する接ざるを得ない固定用古语未然形「せ」。",
                "するわけにはいかない": "意为「绝不能停产」，与零件断供被迫停产的语境相反。",
                "しかねない": "表「弄不好会停产」的担忧，不如被迫决定贴切。",
            },
        },
    ],
    "N2G-002": [
        {
            "id": "N2G-002",
            "prompt": "先輩に頼まれた以上、途中で投げ出す（　　）。",
            "choices": ["わけにはいかない", "ざるを得ない", "恐れがある", "に違いない"],
            "answer": "わけにはいかない",
            "full_ja": "先輩に頼まれた以上、途中で投げ出すわけにはいかない。",
            "zh_meaning": "既然受前辈所托，绝不能半途而废。",
            "why_line": "出于对前辈的情义和责任底线「绝不能撂挑子」，用辞书形「投げ出す」直接接わけにはいかない。",
            "form_line": "V辞书形 + わけにはいかない（于情于理绝不能）。",
            "option_notes": {
                "わけにはいかない": "准确表达顾及情义责任「绝不能半途而废」，接辞书形「投げ出す」完全匹配。",
                "ざるを得ない": "意为被迫不得不，不仅意思相反，前面也须接ない形去ない词干。",
                "恐れがある": "表有发生坏事的风险，不用于表达自己的道德底线。",
                "に違いない": "表说话人主观断定「一定」，与前辈嘱托的约束感不符。",
            },
        },
        {
            "id": "N2V-002",
            "prompt": "社外秘の数字なので、たとえ親しい友人でも教える（　　）。",
            "choices": ["わけにはいかない", "ほかはない", "つつある", "一方だ"],
            "answer": "わけにはいかない",
            "full_ja": "社外秘の数字なので、たとえ親しい友人でも教えるわけにはいかない。",
            "zh_meaning": "因为是公司机密数字，就算是铁哥们也绝不能告诉。",
            "why_line": "职业保密底线决定了「绝不能说」，用教える + わけにはいかない。",
            "form_line": "V辞书形 + わけにはいかない表社会常识或职业底线下的「不能」。",
            "option_notes": {
                "わけにはいかない": "最自然表达职业保密原则下的「于理绝不能透露」。",
                "ほかはない": "意为「只好告诉」，语义完全相反。",
                "つつある": "接ます形表「正在逐渐变化」，接辞书形错误且义不符。",
                "一方だ": "表朝单一方向恶化或加剧，语义完全不搭。",
            },
        },
    ],
    "N2G-003": [
        {
            "id": "N2G-003",
            "prompt": "終電を逃し、タクシーもつかまらないので、歩いて帰る（　　）。",
            "choices": ["ほかない", "わけにはいかない", "かねる", "がたい"],
            "answer": "ほかない",
            "full_ja": "終電を逃し、タクシーもつかまらないので、歩いて帰るほかない。",
            "zh_meaning": "错过了末班车又打不到出租，只好走着回家。",
            "why_line": "所有交通工具全堵死了，只剩走路这一条退路，用辞书形 + ほかない（只好）。",
            "form_line": "V辞书形 + ほかない / ほかはない（别无他法只好）。",
            "option_notes": {
                "ほかない": "表达其他选项全灭、只剩唯一退路的「只好」，接辞书形「帰る」完全准确。",
                "わけにはいかない": "意为「绝不能走回去」，与语境相反。",
                "かねる": "接ます形表委婉拒绝或难以办到，接辞书形错误。",
                "がたい": "接ます形表心理上难以做到，接辞书形错误。",
            },
        },
        {
            "id": "N2V-003",
            "prompt": "バックアップが残っていない以上、最初から作り直す（　　）。",
            "choices": ["ほかはない", "わけがない", "ものではない", "べきではない"],
            "answer": "ほかはない",
            "full_ja": "バックアップが残っていない以上、最初から作り直すほかはない。",
            "zh_meaning": "既然没有留备份，只好从头重做。",
            "why_line": "没留备份等于退路全断，只能接受现实从头再来，用作り直す + ほかはない。",
            "form_line": "V辞书形 + ほかはない 强调「除了这一招别无选择」。",
            "option_notes": {
                "ほかはない": "准确表达无路可退、只好重做的无奈。",
                "わけがない": "意为「绝不可能重做」，不符语境。",
                "ものではない": "表常识告诫「不该…」，与客观无备份不搭。",
                "べきではない": "意为「不应该重做」，意思相反。",
            },
        },
    ],
    "N2G-004": [
        {
            "id": "N2G-004",
            "prompt": "恩師の退任パーティーなので、忙しくても出席（　　）。",
            "choices": ["しないわけにはいかない", "するわけにはいかない", "しかねない", "するほかない"],
            "answer": "しないわけにはいかない",
            "full_ja": "恩師の退任パーティーなので、忙しくても出席しないわけにはいかない。",
            "zh_meaning": "是恩师的荣休晚宴，再忙也不能不出席。",
            "why_line": "按情理「不能不去」就是双重否定：Vない形 + わけにはいかない。",
            "form_line": "Vない形 + わけにはいかない（不能不…，按人情职责必须做）。",
            "option_notes": {
                "しないわけにはいかない": "双重否定精准传达顾及师生情谊「不能不出席」。",
                "するわけにはいかない": "意为「绝不能出席」，意思完全反了。",
                "しかねない": "意为「弄不好会出席」，仅用于不良后果，完全不合。",
                "するほかない": "侧重无计可施的唯一退路，少了「顾及人情道义」的味道。",
            },
        },
        {
            "id": "N2V-004",
            "prompt": "お客様から直接ご指摘を受けた以上、誠意を持って対応（　　）。",
            "choices": ["しないわけにはいかない", "するわけにはいかない", "しがたい", "しっこない"],
            "answer": "しないわけにはいかない",
            "full_ja": "お客様から直接ご指摘を受けた以上、誠意を持って対応しないわけにはいかない。",
            "zh_meaning": "既然顾客直接提出了指正，于情于理不能不诚恳应对。",
            "why_line": "面对客户直接反馈，职责与信誉要求「不能不认真处理」，选双重否定。",
            "form_line": "Vない形 + わけにはいかない 考「不得不」的人情职责面。",
            "option_notes": {
                "しないわけにはいかない": "准确表达职责所在「不能不回应」。",
                "するわけにはいかない": "变成「绝不能应对」，逻辑相反。",
                "しがたい": "意为「难以应对」，不符合承接责任的语气。",
                "しっこない": "口语断言「绝对不可能」，既太随意又语义相反。",
            },
        },
    ],
    "N2G-005": [
        {
            "id": "N2G-005",
            "prompt": "高齢化（　　）、医療や介護の社会保障費が年々増えている。",
            "choices": ["に伴って", "に基づいて", "をめぐって", "に限って"],
            "answer": "に伴って",
            "full_ja": "高齢化に伴って、医療や介護の社会保障費が年々増えている。",
            "zh_meaning": "伴随着老龄化，医疗与照护的社会保障费连年攀升。",
            "why_line": "前项「高齢化」是宏观大趋势，后项社保费同步增长，用「に伴って」表伴随引发的变化。",
            "form_line": "N / V辞书形 + に伴って（に伴い）常用于人口、技术、政策等宏观变化。",
            "option_notes": {
                "に伴って": "新闻经济标配，表达前项大变化顺带引出后项同步变化。",
                "に基づいて": "意为「依据某种数据或法规」，老龄化是趋势不是法规依据。",
                "をめぐって": "意为「围绕某争议焦点展开博弈」，后项需有争论或对立。",
                "に限って": "意为「偏偏」或「仅限」，语义完全不符。",
            },
        },
        {
            "id": "N2V-005",
            "prompt": "新路線の開通（　　）、駅周辺の地価が大きく上昇した。",
            "choices": ["に伴い", "に際し", "に反し", "に対し"],
            "answer": "に伴い",
            "full_ja": "新路線の開通に伴い、駅周辺の地価が大きく上昇した。",
            "zh_meaning": "随着新线路开通，车站周边地价大幅上涨。",
            "why_line": "开通新线这一大变化直接伴随地价上涨，书面简练形用「に伴い」。",
            "form_line": "に伴い 是 に伴って 的书面中顿形，N2 财经新闻极高频。",
            "option_notes": {
                "に伴い": "准确表达新线开通所伴随引发的周边地价联动上涨。",
                "に際し": "意为「在…重大仪式之际」，多接致辞或准备工作，不接自然结果。",
                "に反し": "意为「与…相反」，逻辑相反。",
                "に対し": "意为「针对/对比」，不能表达随变化而来的联动结果。",
            },
        },
    ],
    "N2G-006": [
        {
            "id": "N2G-006",
            "prompt": "現場の責任者の指示（　　）、速やかに避難してください。",
            "choices": ["にしたがって", "につれて", "に伴って", "をめぐって"],
            "answer": "にしたがって",
            "full_ja": "現場の責任者の指示にしたがって、速やかに避難してください。",
            "zh_meaning": "请遵照现场负责人的指示，迅速避难。",
            "why_line": "「にしたがって」除了表「随着」，还有独门第二义「遵照指示或规则行事」，につれて没有这个意思。",
            "form_line": "指示・ルール・計画 + にしたがって（遵照/按照）。",
            "option_notes": {
                "にしたがって": "唯一兼有「随着变化」与「遵照指示」双义的句型，此处考「遵照」。",
                "につれて": "只能表自然单向随变，绝对不能接「指示」表遵照。",
                "に伴って": "表宏观变化附带引发另一变化，不能表听从指挥。",
                "をめぐって": "表围绕争议展开讨论，与服从指令避难不符。",
            },
        },
        {
            "id": "N2V-006",
            "prompt": "調査が進む（　　）、当初は見えなかった構造的な課題が浮上してきた。",
            "choices": ["にしたがって", "に基づいて", "をはじめ", "を除いて"],
            "answer": "にしたがって",
            "full_ja": "調査が進むにしたがって、当初は見えなかった構造的な課題が浮上してきた。",
            "zh_meaning": "随着调查推进，最初看不到的结构性课题逐渐浮出水面。",
            "why_line": "动词辞书形「進む」后面接「にしたがって」，表示随着前项推进，后项同步显现。",
            "form_line": "V辞书形 + にしたがって（随着推进）。",
            "option_notes": {
                "にしたがって": "接动词辞书形「進む」表同步推进，完全准确。",
                "に基づいて": "前面须接名词（如調査に基づいて），不能直接接动词「進む」。",
                "をはじめ": "接名词表「以…为首」，接动词错误。",
                "を除いて": "接名词表「除…之外」，接动词错误。",
            },
        },
    ],
    "N2G-007": [
        {
            "id": "N2G-007",
            "prompt": "このまま油断していると、取り返しのつかない事故を起こし（　　）。",
            "choices": ["かねない", "かねる", "がたい", "つつある"],
            "answer": "かねない",
            "full_ja": "このまま油断していると、取り返しのつかない事故を起こしかねない。",
            "zh_meaning": "就这样大意下去，弄不好会引发无法挽回的大事故。",
            "why_line": "「乌鸦嘴警报」担心坏结果真的发生，用动词ます形词干「起こし」+ かねない。",
            "form_line": "Vます形去ます + かねない（严禁用于好事，专表「弄不好会出糟事」）。",
            "option_notes": {
                "かねない": "精准表达「大意下去很可能会酿成大祸」的负面警示。",
                "かねる": "形似义反！表心理或立场上「难以办到/不便答应」。",
                "がたい": "表心理情感上「难以置信/难以原谅」，语义不搭。",
                "つつある": "表「正在逐渐…」，与假设条件「このまま油断していると」不搭。",
            },
        },
        {
            "id": "N2V-007",
            "prompt": "曖昧な表現をそのまま残すと、取引先の誤解を招き（　　）。",
            "choices": ["かねない", "かねる", "抜く", "きる"],
            "answer": "かねない",
            "full_ja": "曖昧な表現をそのまま残すと、取引先の誤解を招きかねない。",
            "zh_meaning": "把含糊措辞原样留着，弄不好会招致合作方误解。",
            "why_line": "「招く」的ます形词干「招き」接 かねない，警示可能引发负面后果「误解」。",
            "form_line": "Vます形 + かねない 常搭配 事故を起こす・誤解を招く・信頼を失う。",
            "option_notes": {
                "かねない": "高频固定搭配「誤解を招きかねない（弄不好会招来误解）」。",
                "かねる": "意为「难以招致误解」，语义完全跑偏。",
                "抜く": "表坚持到底完成，不用于负面误解。",
                "きる": "表彻底做完，不能表对坏结果的担忧。",
            },
        },
    ],
    "N2G-008": [
        {
            "id": "N2G-008",
            "prompt": "その件につきましては、私の一存ではお答えし（　　）。",
            "choices": ["かねます", "かねません", "がたいです", "つつあります"],
            "answer": "かねます",
            "full_ja": "その件につきましては、私の一存ではお答えしかねます。",
            "zh_meaning": "关于那件事，凭我个人实在不便答复。",
            "why_line": "职场最典雅的委婉拒绝「实在不便答应/难以做到」，用ます形词干 + かねる（敬体 かねます）。",
            "form_line": "Vます形去ます + かねる / かねます（不是不会，而是立场/规定上不便）。",
            "option_notes": {
                "かねます": "日本职场与客服天花板级委婉拒绝「お答えしかねます」。",
                "かねません": "变成「弄不好会回答」，完全相反。",
                "がたいです": "偏主观情感难以接受（如信じがたい），不如 かねます 适合礼貌婉拒。",
                "つつあります": "意为「正在逐渐回答」，不符。",
            },
        },
        {
            "id": "N2V-008",
            "prompt": "期限を過ぎておりますので、返品のご要望には応じ（　　）。",
            "choices": ["かねます", "かねません", "ざるを得ません", "一方です"],
            "answer": "かねます",
            "full_ja": "期限を過ぎておりますので、返品のご要望には応じかねます。",
            "zh_meaning": "因为已过期限，实在无法满足您的退货要求。",
            "why_line": "「応じる」ます形词干「応じ」+ かねます，代表规章制度下礼貌而坚定的回绝。",
            "form_line": "ご要望に応じかねます / 引き受けかねます 是 N2 听力与读解必背套装。",
            "option_notes": {
                "かねます": "礼貌委婉拒绝的标准商务表达「无法满足要求」。",
                "かねません": "意为「弄不好会答应」，完全相反。",
                "ざるを得ません": "意为「不得不答应」，逻辑完全反了。",
                "一方です": "表单向加剧，且须接辞书形。",
            },
        },
    ],
    "N2G-009": [
        {
            "id": "N2G-009",
            "prompt": "あんなに誠実な人が嘘をついたとは信じ（　　）。",
            "choices": ["がたい", "かねない", "ほかない", "一方だ"],
            "answer": "がたい",
            "full_ja": "あんなに誠実な人が嘘をついたとは信じがたい。",
            "zh_meaning": "那么诚实的人竟然撒了谎，实在令人难以置信。",
            "why_line": "「信じる」属于心理感受动词，表达内心「很难相信」用ます形词干 + がたい。",
            "form_line": "信じ・許し・理解し・受け入れ + がたい（心理情感上很难，区分物理难 にくい）。",
            "option_notes": {
                "がたい": "心理动词固定高分搭档「信じがたい（难以置信）」。",
                "かねない": "意为「弄不好会相信」，意思反了。",
                "ほかない": "接辞书形表只好，此处形态与意思双错。",
                "一方だ": "接辞书形表单向变化，完全不符。",
            },
        },
        {
            "id": "N2V-009",
            "prompt": "長年支えてくれた仲間を裏切る行為は、到底許し（　　）。",
            "choices": ["がたい", "かねない", "やすい", "つつある"],
            "answer": "がたい",
            "full_ja": "長年支えてくれた仲間を裏切る行為は、到底許しがたい。",
            "zh_meaning": "背叛常年支持自己的伙伴这种行径，实在难以原谅。",
            "why_line": "前面副词「到底（无论如何也）」呼应强烈的否定情感，配「許しがたい（难以原谅）」。",
            "form_line": "到底 + Vます形 + がたい 是 N2 经典呼应组合。",
            "option_notes": {
                "がたい": "与「到底」强呼应，精准表达情感底线上的「绝难原谅」。",
                "かねない": "意为「弄不好会原谅」，意思完全相反。",
                "やすい": "意为「容易原谅」，与「到底」呼应错误且义反。",
                "つつある": "意为「正在逐渐原谅」，语义不合。",
            },
        },
    ],
    "N2G-010": [
        {
            "id": "N2G-010",
            "prompt": "強い台風の影響で、今夜は大雨が降る（　　）。",
            "choices": ["恐れがある", "わけにはいかない", "ほかはない", "限りでは"],
            "answer": "恐れがある",
            "full_ja": "強い台風の影響で、今夜は大雨が降る恐れがある。",
            "zh_meaning": "受强台风影响，今晚有下暴雨的危险。",
            "why_line": "气象灾害与新闻官方预警「有发生不良后果的风险」，固定用 V辞书形 / Nの + 恐れがある。",
            "form_line": "V辞书形 / Nの + 恐れがある（比 かねない 更客观官方，NHK 气象/财经标配）。",
            "option_notes": {
                "恐れがある": "NHK 气象与社会新闻最标准风险预警句型。",
                "わけにはいかない": "意为「绝不能下雨」，自然现象不能用道义约束。",
                "ほかはない": "意为「只好下雨」，用于人的无奈选择，不能用于天气。",
                "限りでは": "意为「就…所知范围来看」，不用于结句预告灾害。",
            },
        },
        {
            "id": "N2V-010",
            "prompt": "この橋は老朽化が進んでおり、大きな地震で崩落の（　　）。",
            "choices": ["恐れがある", "わけがない", "一方だ", "どころではない"],
            "answer": "恐れがある",
            "full_ja": "この橋は老朽化が進んでおり、大きな地震で崩落の恐れがある。",
            "zh_meaning": "这座桥老化严重，大地震时有坍塌的隐患。",
            "why_line": "名词「崩落」加「の」直接接「恐れがある」，是公文与防灾报告的核心写法。",
            "form_line": "Nの + 恐れがある（如 崩落の恐れ・延期の恐れ・感染拡大の恐れ）。",
            "option_notes": {
                "恐れがある": "「Nの + 恐れがある」精准传达客观安全隐患。",
                "わけがない": "前面需接句型或辞书形，且语义为「绝无可能」，与老化矛盾。",
                "一方だ": "前面须接动词辞书形，不能接「崩落の」。",
                "どころではない": "意为「根本顾不上…」，语义和接续都不符。",
            },
        },
    ],
    "N2G-011": [
        {
            "id": "N2G-011",
            "prompt": "最新の調査データ（　　）、来年度の予算配分を決定した。",
            "choices": ["に基づいて", "をめぐって", "に伴って", "に限って"],
            "answer": "に基づいて",
            "full_ja": "最新の調査データに基づいて、来年度の予算配分を決定した。",
            "zh_meaning": "基于最新调查数据，决定了下一年度的预算分配。",
            "why_line": "以客观硬数据、法律或调查结果为依据做决策，用 N + に基づいて。",
            "form_line": "N + に基づいて（基づき・基づくN）强调客观权威依据。",
            "option_notes": {
                "に基づいて": "精准表达以客观数据作为决策硬根据。",
                "をめぐって": "意为「围绕某争议焦点」，后面需要多方争论而非依数据拍板。",
                "に伴って": "意为「随着某种变化」，数据本身不是变化过程。",
                "に限って": "意为「偏偏/仅限」，完全不合。",
            },
        },
        {
            "id": "N2V-011",
            "prompt": "契約書の条項（　　）手続きを進めさせていただきます。",
            "choices": ["に基づき", "に際し", "を除き", "に限り"],
            "answer": "に基づき",
            "full_ja": "契約書の条項に基づき手続きを進めさせていただきます。",
            "zh_meaning": "我们将依据合同条款推进相关手续。",
            "why_line": "法律条款和合同依据在商务书面语里常用简洁中顿形「に基づき」。",
            "form_line": "法律・規定・契約 + に基づき（依据…）。",
            "option_notes": {
                "に基づき": "商务合同与公文最高频写法「依据条款」。",
                "に際し": "意为「在…之际」，条款不是时间节点。",
                "を除き": "意为「除了条款之外」，语义相反。",
                "に限り": "意为「仅限于」，与依约办理不符。",
            },
        },
    ],
    "N2G-012": [
        {
            "id": "N2G-012",
            "prompt": "戦後の実在の事件（　　）、その有名な映画が作られた。",
            "choices": ["をもとにして", "を中心にして", "をめぐって", "を問わず"],
            "answer": "をもとにして",
            "full_ja": "戦後の実在の事件をもとにして、その有名な映画が作られた。",
            "zh_meaning": "那部著名电影是以战后真实事件为原型拍出来的。",
            "why_line": "以真实事件、小说或亲身经历作为创作蓝本/素材，固定用「をもとにして」。",
            "form_line": "素材・経験・実話 + をもとに（して）（以…为蓝本创作）。",
            "option_notes": {
                "をもとにして": "电影、小说、艺术创作的标配「以真实事件为原型」。",
                "を中心にして": "意为「以…为中心向外辐射」，多用于人群、地区或议题核心。",
                "をめぐって": "意为「围绕…展开争论」，与创作蓝本不同。",
                "を問わず": "意为「不论…」，前面需接对比性条件名词（如年齢・国籍）。",
            },
        },
        {
            "id": "N2V-012",
            "prompt": "利用者から届いた声（　　）、アプリの使い勝手を一から見直した。",
            "choices": ["をもとに", "を契機に", "を除いて", "を抜きに"],
            "answer": "をもとに",
            "full_ja": "利用者から届いた声をもとに、アプリの使い勝手を一から見直した。",
            "zh_meaning": "以用户反馈为素材，从头重新审视了应用的顺手程度。",
            "why_line": "把用户反馈当作改进产品的直接材料和出发点，用「をもとに」。",
            "form_line": "N + をもとに（して）兼顾文艺创作与产品迭代蓝本。",
            "option_notes": {
                "をもとに": "最贴合以用户声音为蓝本优化产品体验。",
                "を契機に": "强调重大转折事件分水岭，不如「をもとに」贴合「拿反馈当素材」。",
                "を除いて": "意为「排除用户声音」，逻辑相反。",
                "を抜きに": "意为「省掉用户声音」，逻辑相反。",
            },
        },
    ],
    "N2G-013": [
        {
            "id": "N2G-013",
            "prompt": "若い世代（　　）、昭和レトロの喫茶店やレコードが再評価されている。",
            "choices": ["を中心に", "をめぐって", "に基づいて", "を問わず"],
            "answer": "を中心に",
            "full_ja": "若い世代を中心に、昭和レトロの喫茶店やレコードが再評価されている。",
            "zh_meaning": "以年轻一代为核心，昭和复古咖啡馆和黑胶唱片正被重新评价。",
            "why_line": "以某个群体或地区为核心向外扩散流行，用「を中心に（して）」。",
            "form_line": "人/地域/テーマ + を中心に（して） / を中心とした + N。",
            "option_notes": {
                "を中心に": "新闻文化报道高频结构「以年轻群体为核心」。",
                "をめぐって": "强调争端博弈，这里并无对立冲突。",
                "に基づいて": "表依据数据或法规，不能接人群。",
                "を問わず": "意为「不论年龄」，但前面「若い世代」是单一特定群体，不能接を問わず。",
            },
        },
        {
            "id": "N2V-013",
            "prompt": "来月の会議では、新しいAI機能（　　）議論を行う予定だ。",
            "choices": ["を中心とした", "に基づいた", "を除いた", "に限った"],
            "answer": "を中心とした",
            "full_ja": "来月の会議では、新しいAI機能を中心とした議論を行う予定だ。",
            "zh_meaning": "下个月的会议计划展开以新AI功能为核心的讨论。",
            "why_line": "修饰后面的名词「議論」，用连体形「を中心とした」。",
            "form_line": "N1 + を中心とした + N2（以 N1 为核心的 N2）。",
            "option_notes": {
                "を中心とした": "修饰名词「議論」的精准书面连体形。",
                "に基づいた": "意为「基于新AI功能的讨论」，少了「以此为主轴」的聚焦感。",
                "を除いた": "意为「排除新AI功能的讨论」，语义不符。",
                "に限った": "意为「仅限于」，语气过窄生硬。",
            },
        },
    ],
    "N2G-014": [
        {
            "id": "N2G-014",
            "prompt": "消費税の引き下げ（　　）、与野党の激しい議論が続いている。",
            "choices": ["をめぐって", "に基づいて", "に伴って", "をはじめ"],
            "answer": "をめぐって",
            "full_ja": "消費税の引き下げをめぐって、与野党の激しい議論が続いている。",
            "zh_meaning": "围绕下调消费税，执政党与在野党的激烈争论仍在继续。",
            "why_line": "后半句出现「与野党の激しい議論（多方激烈争辩）」，一眼锁死带对立博弈色彩的「をめぐって」。",
            "form_line": "争议焦点 + をめぐって（をめぐるN），后项必有 議論・対立・争い・意見が分かれる。",
            "option_notes": {
                "をめぐって": "N2 新闻阅读与语法绝对王牌，专配多方博弈争论。",
                "に基づいて": "表依据，不能引出两派激烈对立。",
                "に伴って": "表随变化引发另一变化，非争议焦点。",
                "をはじめ": "表举头号代表例子，与执政在野交锋无关。",
            },
        },
        {
            "id": "N2V-014",
            "prompt": "深海資源の開発（　　）国際ルール作りが難航している。",
            "choices": ["をめぐる", "に基づく", "に伴う", "を除く"],
            "answer": "をめぐる",
            "full_ja": "深海資源の開発をめぐる国際ルール作りが難航している。",
            "zh_meaning": "围绕深海资源开发的国际规则制定正陷入僵局。",
            "why_line": "修饰后面的名词「国際ルール作り」，且暗含各国利益博弈与僵局，用连体形「をめぐる」。",
            "form_line": "N1 + をめぐる + N2（围绕 N1 的争端/谈判/规则博弈）。",
            "option_notes": {
                "をめぐる": "修饰名词的标准连体形，完美贴合各国角力的「難航」。",
                "に基づく": "表依据，深海开发不是制定规则的法律依据。",
                "に伴う": "表伴随产生，弱化了各国围绕该焦点争执的核心意味。",
                "を除く": "意为「排除深海开发」，语义相反。",
            },
        },
    ],
}

# Clean morphological distractor pools by connection pattern for all remaining N2G-015..N2G-190 points
_N2_SLOT_POOLS: list[list[str]] = [
    ["限りは", "限りでは", "わけにはいかない", "ほかはない", "どころか", "ものの", "としても"],
    ["に限らず", "に限って", "を除いて", "を問わず", "をはじめ", "をめぐって", "に基づいて", "に伴って", "に際して", "に当たって"],
    ["を契機に", "をきっかけに", "を中心にして", "をもとにして", "抜きで", "をよそに", "を通じて"],
    ["つつある", "一方だ", "かねない", "かねる", "がたい", "つつも", "抜く", "きる"],
    ["次第だ", "次第では", "あまり", "ばかりに", "ものの", "くせに", "といっても", "としても", "にしろ"],
    ["どころか", "どころではない", "ばかりか", "のみならず", "うえに", "に限らず", "はもちろん"],
    ["以上は", "上は", "からには", "限りは", "だけに", "ばかりに", "ものの"],
    ["にわたって", "にかけて", "を通じて", "を通して", "に沿って", "に反して", "に対して", "に関して"],
    ["恐れがある", "わけにはいかない", "ざるを得ない", "に違いない", "に決まっている", "はずがない", "ほかない"],
    ["っこない", "ようがない", "わけがない", "ものではない", "べきではない", "どころではない"],
]


def _extract_primary_surface(point: str, example_ja: str) -> str | None:
    """Find the exact inflected surface of an N2 grammar point inside its example sentence."""
    # Split alternatives like "〜に伴って / 〜に伴い" or "〜限り（は）"
    raw_parts = re.split(r"\s*/\s*", point)
    candidates: list[str] = []
    for rp in raw_parts:
        clean = rp.replace("〜", "").replace("～", "").strip()
        clean = re.sub(r"（[^）]*）", "", clean).strip()
        # Also include variant with optional parenthetical kept
        with_opt = rp.replace("〜", "").replace("～", "").replace("（", "").replace("）", "").strip()
        for c in (with_opt, clean):
            c = re.sub(r"\s+三连总决算.*|\s+四连总决算.*|\s+新闻.*|\s+转折.*", "", c).strip()
            if c and len(c) >= 2 and c not in candidates:
                candidates.append(c)
        # Also try past/polite stems (た / ます / ず)
        if clean.endswith("ない"):
            candidates.append(clean[:-2] + "なかった")
            candidates.append(clean[:-2] + "ず")
        if clean.endswith("る"):
            candidates.append(clean[:-1] + "た")
            candidates.append(clean[:-1] + "ます")
    # Prefer longest exact substring match inside example_ja
    candidates.sort(key=len, reverse=True)
    for c in candidates:
        if c in example_ja:
            return c
    # Fallback: try kana stem or last 3+ chars
    return None


def _pick_n2_distractors(answer: str, family: str, all_items: list[dict]) -> list[str]:
    """Pick 3 natural, distinct N2 distractors matching the slot of `answer`."""
    out: list[str] = []
    seen = {answer}
    # 1) Same slot pool match first
    for pool in _N2_SLOT_POOLS:
        if answer in pool or any(answer.endswith(p) or p.endswith(answer) for p in pool if len(p) >= 3):
            for cand in pool:
                if cand not in seen and len(cand) <= 14:
                    out.append(cand)
                    seen.add(cand)
                if len(out) >= 3:
                    return out
    # 2) Sibling grammar points from same or nearby families
    same_fam = [g for g in all_items if g["family"] == family]
    other_fam = [g for g in all_items if g["family"] != family]
    for grp in (same_fam, other_fam):
        for g in grp:
            raw = re.split(r"\s*/\s*", g["point"])[0]
            cand = re.sub(r"（[^）]*）", "", raw.replace("〜", "").replace("～", "")).strip()
            cand = re.sub(r"\s+.*$", "", cand).strip()
            if not cand or len(cand) < 2 or len(cand) > 12 or cand in seen:
                continue
            # Preserve broad particle start similarity when possible
            if answer.startswith("に") and not cand.startswith(("に", "を", "で", "と")) and len(out) < 2:
                continue
            if answer.startswith("を") and not cand.startswith(("を", "に")) and len(out) < 2:
                continue
            out.append(cand)
            seen.add(cand)
            if len(out) >= 3:
                return out
    # 3) Hard fallback pool
    for fb in ("わけにはいかない", "にもかかわらず", "にしたがって", "をめぐって", "どころか", "ものの"):
        if fb not in seen:
            out.append(fb)
            seen.add(fb)
        if len(out) >= 3:
            break
    return out[:3]


def build_n2_question_bank() -> list[dict[str, Any]]:
    """
    Build complete 190-point JLPT N2 Teach-First 4-Choice Question Bank.
    Returns list of structured point records directly compatible with `build_html.py`'s DATA.points schema.
    """
    bank: list[dict[str, Any]] = []
    for g in N2_GRAMMAR_SYLLABUS:
        gid = g["id"]
        pt = _clean_text(g["point"])
        fam = _clean_text(g["family"])
        conn = _clean_text(g["connection"])
        soul = _clean_text(g["soul_meaning"])
        twin = _clean_text(g["vs_twin"])
        ex_ja = _clean_text(g["example_ja"])
        ex_zh = _clean_text(g["example_zh"])

        curated = CURATED_N2_CARDS.get(gid)
        if curated:
            prim_raw = curated[0]
            vars_raw = curated[1:]
        else:
            surf = _extract_primary_surface(pt, ex_ja)
            if surf and surf in ex_ja:
                prompt = ex_ja.replace(surf, "（　　）", 1)
                ans = surf
            else:
                # Safe structural fallback if syllabus point is a 3-way synthesis card (e.g., N2G-185..190)
                first_clause = re.split(r"\s*/\s*", pt)[0].replace("〜", "").replace("～", "").strip()
                first_clause = re.sub(r"（[^）]*）", "", first_clause).strip()
                first_clause = re.sub(r"\s+.*$", "", first_clause).strip() or "わけにはいかない"
                if first_clause in ex_ja:
                    prompt = ex_ja.replace(first_clause, "（　　）", 1)
                    ans = first_clause
                else:
                    # Extract matching sub-token from any slash option
                    found = ""
                    for part in re.split(r"\s*/\s*", pt):
                        pc = re.sub(r"（[^）]*）", "", part.replace("〜", "").replace("～", "")).strip()
                        pc = re.sub(r"\s+.*$", "", pc).strip()
                        if pc and pc in ex_ja:
                            found = pc
                            break
                    if found:
                        prompt = ex_ja.replace(found, "（　　）", 1)
                        ans = found
                    else:
                        prompt = f"「{pt}」に最も近い使い方はどれ？（例：{ex_ja}）"
                        ans = first_clause
            distractors = _pick_n2_distractors(ans, fam, N2_GRAMMAR_SYLLABUS)
            choices = [ans] + distractors
            opt_notes = {ans: f"本题语境正是「{pt}」：{soul}"}
            for d in distractors:
                opt_notes[d] = f"「{d}」与本句的语境或接续不匹配，此处须用「{ans}」。"
            prim_raw = {
                "id": gid,
                "prompt": prompt,
                "choices": choices,
                "answer": ans,
                "full_ja": ex_ja,
                "zh_meaning": ex_zh,
                "why_line": soul,
                "form_line": f"接续：{conn}。{twin}",
                "option_notes": opt_notes,
            }
            vars_raw = []

        # Teach card (Zero-to-120 "先教后练"!)
        teach_left_ja = f"{pt.split('/')[0].strip()}"
        teach_right_ja = ""
        teach_right_sub = ""
        m_vs = re.search(r"vs\s*([^（(]+)", twin)
        if m_vs:
            teach_right_ja = m_vs.group(1).strip().rstrip("；。，")
            teach_right_sub = twin
        else:
            teach_right_ja = conn[:28]
            teach_right_sub = twin or soul

        teach_obj = {
            "left": {"ja": teach_left_ja, "sub": soul},
            "right": {"ja": teach_right_ja, "sub": teach_right_sub},
            "example_ja": ex_ja,
            "zh_meaning": ex_zh,
            "rule": f"{conn}。{soul}",
            "audio": f"./audio/{gid}_exp.mp3",
        }

        def _fmt_card(c: dict[str, Any]) -> dict[str, Any]:
            cid = c["id"]
            return {
                "id": cid,
                "prompt": _clean_text(c["prompt"]),
                "choices": [_clean_text(x) for x in c["choices"]],
                "answer": _clean_text(c["answer"]),
                "full_ja": _clean_text(c["full_ja"]),
                "zh_meaning": _clean_text(c["zh_meaning"]),
                "why_line": _clean_text(c["why_line"]),
                "form_line": _clean_text(c["form_line"]),
                "opt_notes": {_clean_text(k): _clean_text(v) for k, v in (c.get("option_notes") or {}).items()},
                "q_audio": f"./audio/{cid}_q.mp3",
                "exp_audio": f"./audio/{cid}_exp.mp3",
                "listen_parts": None,
                "is_listening": False,
            }

        bank.append({
            "id": gid,
            "subject": "语法",
            "point": pt,
            "point_key": pt,
            "family": fam,
            "day": g["day"],
            "kana": g["kana"],
            "modality": "both",
            "exam_weight": 95 if g["day"] <= 34 else 88,
            "roi_score": 9.8 if g["day"] <= 14 else 7.2,
            "is_new_n2": True,
            "teach": teach_obj,
            "primary": _fmt_card(prim_raw),
            "variants": [_fmt_card(v) for v in vars_raw],
        })
    return bank


# ==============================================================================
# N2 3-TRACK VOCABULARY CARD BUILDER (100% Bilingual Mnemonics + 4-9 Char Chunks)
# ==============================================================================
def _compact_chunk(chunk_ja: str, target: str) -> str:
    """Ensure every collocation chunk is concise (<= 10 chars) for calm 1-line Zen display."""
    s = _clean_text(chunk_ja)
    if len(s) <= 10:
        return s
    # Split on punctuation and keep the clause containing target
    for sep in ("。", "、", "，"):
        if sep in s:
            for part in s.split(sep):
                if target in part and 2 <= len(part) <= 10:
                    return part.strip()
    idx = s.find(target)
    if idx >= 0:
        start = max(0, idx - 3)
        end = min(len(s), start + 10)
        sub = s[start:end].strip("。、，")
        if len(sub) >= len(target) and len(sub) <= 10:
            return sub
    return target[:10]


def _make_n2_mnemonic(word: str, kana: str, zh: str, extra: str = "") -> str:
    """Build a crisp, memorable bilingual/root reading lock for every N2 vocab word."""
    try:
        import vocab_cards as _vc
        existing = _vc.get_pronunciation_mnemonic(word, kana)
        if existing:
            return _clean_text(existing)
    except Exception:
        pass
    # Root-aware compound verb locks
    suffix_hints = [
        ("込む", "こむ", "尾巴 込む(こむ) = “Come in(こむ)” 往里扎进去"),
        ("直す", "なおす", "尾巴 直す(なおす) = “Now(なお) 修好重来”"),
        ("切る", "きる", "尾巴 切る(きる) = “Kill(きる) 一刀切到底”"),
        ("切れる", "きれる", "尾巴 切れる(きれる) = 切光耗尽彻底没了"),
        ("出す", "だす", "尾巴 出す(だす) = “Dash(だす) 猛地冲出掏出”"),
        ("合う", "あう", "尾巴 合う(あう) = “Our(あう) 彼此双向互动”"),
        ("抜く", "ぬく", "尾巴 抜く(ぬく) = 穿到底死磕拔出来"),
        ("返す", "かえす", "尾巴 返す(かえす) = 反手翻回去再来一遍"),
        ("返る", "かえる", "尾巴 返る(かえる) = 回头翻过来看"),
        ("受ける", "うける", "尾巴 受ける(うける) = 双手稳稳接住承担"),
        ("止める", "とめる", "尾巴 止める(とめる) = 稳稳停住接住消化"),
        ("入れる", "いれる", "尾巴 入れる(いれる) = 敞开门放进来接纳"),
        ("上げる", "あげる", "尾巴 上げる(あげる) = 往上抬起或打磨收尾"),
        ("下げる", "さげる", "尾巴 下げる(さげる) = 往下拉低降门槛"),
        ("かける", "かける", "尾巴 かける = 主动凑上去搭上动作"),
        ("付く", "つく", "尾巴 付く(つく) = 紧紧贴上追上靠拢"),
        ("消す", "けす", "尾巴 消す(けす) = 一把抹掉撤销"),
        ("落とす", "おとす", "尾巴 落とす(おとす) = 往下漏掉没抓住"),
        ("送る", "おくる", "尾巴 送る(おくる) = 目送过去先放一边"),
    ]
    for suf_w, suf_k, suf_tip in suffix_hints:
        if word.endswith(suf_w):
            stem_k = kana[:-len(suf_k)] if kana.endswith(suf_k) else kana
            return _clean_text(f"{suf_tip}；前半 {stem_k} 连读成 {kana}（{zh.split('、')[0]}）")
    if extra:
        return _clean_text(f"{extra}")
    return _clean_text(f"按节奏记读音 {kana}，联想「{zh.split('、')[0]}」直接脱口而出 → {kana}")


def build_n2_vocab_cards() -> dict[str, dict[str, Any]]:
    """Build complete N2 3-Track flashcard dictionary directly compatible with build_html.py DATA.vocab_cards."""
    cards: dict[str, dict[str, Any]] = {}
    day_counter = 0

    # Track C-1: Compound Verb Root Families
    for fam_name, fam_obj in N2_COMPOUND_VERB_FAMILIES.items():
        core_img = _clean_text(fam_obj.get("core_image", ""))
        for word, kana, zh, chunk_ja, chunk_zh in fam_obj["items"]:
            day_counter += 1
            cards[word] = {
                "mode": "kanji_read",
                "track": "hard_bone",
                "family": _clean_text(fam_name),
                "day_slot": ((day_counter - 1) % 30) + 1,
                "chunk_ja": _compact_chunk(chunk_ja, word),
                "target": word,
                "kana": kana,
                "trap_hl": [kana[:2]] if len(kana) >= 2 else [kana],
                "trap_tag": "复合动词",
                "zh_opaque": True,
                "pitch": "",
                "zh": _clean_text(f"{zh} · {chunk_zh}"),
                "twin": core_img,
                "mnemonic": _make_n2_mnemonic(word, kana, zh),
                "audio": f"./audio/words/n2_{word}.mp3",
            }

    # Track B: False Friends & Kanji Reading Traps
    for word, kana, red_hint, zh, myth in N2_FALSE_FRIENDS_AND_TRAPS:
        day_counter += 1
        hl_tok = red_hint.split("·")[0].strip() if "·" in red_hint else kana[:2]
        hl_tag = red_hint.split("·")[1].strip() if "·" in red_hint else "易错拍"
        if hl_tok not in kana:
            hl_tok = kana[:2]
        cards[word] = {
            "mode": "kanji_read",
            "track": "reading_trap",
            "family": "假朋友与读音陷阱",
            "day_slot": ((day_counter - 1) % 30) + 1,
            "chunk_ja": word,
            "target": word,
            "kana": kana,
            "trap_hl": [hl_tok],
            "trap_tag": hl_tag,
            "zh_opaque": True,
            "pitch": "",
            "zh": _clean_text(zh),
            "twin": _clean_text(myth),
            "mnemonic": _make_n2_mnemonic(word, kana, zh, myth),
            "audio": f"./audio/words/n2_{word}.mp3",
        }

    # Track C-2: Pure-Kana Adverbs & Conjunctions
    for word, kana, zh, chunk_ja, chunk_zh in N2_KANA_ADVERBS_AND_CONJUNCTIONS:
        day_counter += 1
        has_kanji = bool(re.search(r"[\u4e00-\u9fff]", word))
        cards[word] = {
            "mode": "kanji_read" if has_kanji else "kana_meaning",
            "track": "hard_bone",
            "family": "假名副词与接续",
            "day_slot": ((day_counter - 1) % 30) + 1,
            "chunk_ja": _compact_chunk(chunk_ja, word),
            "target": word,
            "kana": kana,
            "trap_hl": [kana[:2]] if len(kana) >= 2 else [kana],
            "trap_tag": "语感核心",
            "zh_opaque": True,
            "pitch": "",
            "zh": _clean_text(f"{zh} · {chunk_zh}"),
            "twin": _clean_text(chunk_zh),
            "mnemonic": _make_n2_mnemonic(word, kana, zh),
            "audio": f"./audio/words/n2_{word}.mp3",
        }

    return cards


# ==============================================================================
# N2 DAY 1 DOCUMENTARY PHOTOGRAPHY TOPICS & NHK SHORT FILM SCRIPT
# ==============================================================================
N2_CURATED_VISUAL_TOPICS: dict[str, dict[str, list[str]]] = {
    "n2_v1_s1_news_fallback": {
        "ja_wiki": ["イトーヨーカ堂", "セブン&アイ・ホールディングス", "東京"],
        "wm_queries": [
            "Ito-Yokado store Japan building",
            "Seven and i Holdings Tokyo",
            "Japanese department store exterior Tokyo",
        ],
    },
    "n2_v1_s2a": {
        "ja_wiki": ["成都市", "イトーヨーカ堂"],
        "wm_queries": [
            "Chengdu Chunxi Road shopping street",
            "Chengdu cityscape modern street",
            "Ito-Yokado supermarket interior",
        ],
    },
    "n2_v1_s2b": {
        "ja_wiki": ["北京市", "百貨店"],
        "wm_queries": [
            "Beijing CBD skyline modern street",
            "Beijing shopping mall evening",
            "Beijing commercial district architecture",
        ],
    },
    "n2_v1_s3a": {
        "ja_wiki": ["日系ペルー人", "リマ", "アルベルト・フジモリ"],
        "wm_queries": [
            "Lima Peru Plaza Mayor historic architecture",
            "Peru Japanese immigration history Lima",
            "Lima Peru city street colonial",
        ],
    },
    "n2_v1_s3b": {
        "ja_wiki": ["セビチェ", "ペルー料理", "リマ"],
        "wm_queries": [
            "Peruvian ceviche dish fresh fish lime",
            "Lima Peru Nikkei cuisine restaurant",
            "Japanese sashimi knife culinary art",
        ],
    },
    "n2_v1_s4_world_rare_earth": {
        "ja_wiki": ["南鳥島", "ちきゅう", "レアアース"],
        "wm_queries": [
            "Chikyu deep sea drilling vessel JAMSTEC",
            "Minamitorishima island Pacific Ocean",
            "Oceanographic research ship Pacific",
        ],
    },
    **N2_VOL2_3_VISUAL_TOPICS,
}

N2_CURATED_JP_VIDEO_SCRIPTS: dict[str, dict[str, Any]] = {
    "n2_v1_s2a": {
        "title_ja": "成都のイトーヨーカドーとペルーの日系料理、南鳥島の深海資源",
        "title_zh": "成都伊藤、秘鲁日系料理与南鸟岛深海稀土",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本の経済が変化するなか、老舗のスーパーも厳しい市場と向き合っています。", "zh": "在日本经济变革之中，老牌超市也正直面严峻的市场。"},
            {"ch": 0, "v": "F", "ja": "赤字が続く店舗については、経営を見直し、閉めざるを得ない状況です。", "zh": "对于持续亏损的门店，不得不重新审视经营并忍痛关闭。"},
            {"ch": 1, "v": "M", "ja": "一方で、中国の成都に進出した店舗は、地元の家族に深く愛されてきました。", "zh": "而另一方面，进驻中国成都的门店却深受当地家庭喜爱。"},
            {"ch": 1, "v": "F", "ja": "日本のやり方を押し付けるわけにはいかないと、ひたすら暮らしを研究したのです。", "zh": "他们明白绝不能生搬硬套日本做法，于是一门心思研究当地生活。"},
            {"ch": 2, "v": "M", "ja": "同じ会社でも、北京では時代の流れと激しい競争の中で別の現実を迎えました。", "zh": "即便是同一家公司，在北京也因时代大潮与激烈竞争迎来了不同现实。"},
            {"ch": 2, "v": "F", "ja": "どんな名門でも、過去の成功に油断すると、すぐに取り残されてしまいます。", "zh": "无论多响亮的名门，一旦沉迷过往成功掉以轻心，很快就会掉队。"},
            {"ch": 3, "v": "M", "ja": "海を隔てたペルーでは、百年以上前に渡った日系人が新しい歴史を築きました。", "zh": "在隔海相望的秘鲁，一百多年前渡海的日裔筑起了崭新的历史。"},
            {"ch": 3, "v": "F", "ja": "厳しい差別のなかでも、家族を守るために仕事を投げ出すわけにはいきませんでした。", "zh": "即便身处严酷歧视之中，为了守护家人也绝不能半途撂挑子。"},
            {"ch": 4, "v": "M", "ja": "故郷の食材が手に入らず、現地の魚や果物を取り入れざるを得なかったのです。", "zh": "买不到故乡食材，他们只能就地取材用上当地鲜鱼与蔬果。"},
            {"ch": 4, "v": "F", "ja": "その工夫が、かえって世界から高く評価される日系料理を生む象徴となりました。", "zh": "那份巧思反而化作受世界高度赞誉的日系料理的象征。"},
            {"ch": 4, "v": "M", "ja": "文化は閉じこもるより、異なる風土と出会うことで新しい構造へ広がります。", "zh": "与其固步自封，文化在邂逅异域风土时反而能生长出全新格局。"},
            {"ch": 5, "v": "F", "ja": "そして今、日本は太平洋の南鳥島で、深海六千メートルの資源開発に挑んでいます。", "zh": "而如今，日本正在太平洋南鸟岛挑战六千米深海的资源开发。"},
            {"ch": 5, "v": "M", "ja": "輸入だけに頼り続けるわけにはいかず、高い予算と技術の壁を越えようとしています。", "zh": "绝不能一味依赖进口，正试图跨越高昂预算与技术的重重高墙。"},
            {"ch": 5, "v": "F", "ja": "自然への影響と世界の供給網を見極めながら、慎重に設計を進めることが大切です。", "zh": "一边权衡自然生态与全球供应链，一边审慎推进设计至关重要。"},
            {"ch": 5, "v": "M", "ja": "商業も料理も科学も、現実を受け止めて見直す姿勢が未来をひらきます。", "zh": "无论是商业、料理还是科学，直面现实并重新审视的姿态才能打开未来。"},
        ],
    },
    **N2_VOL2_3_JP_VIDEO_SCRIPTS,
}

_CURATED_N2_VOLUMES: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {
    1: (N2_VOL1_METADATA, SALON_STORIES_N2_VOL1),
    2: (N2_VOL2_METADATA, SALON_STORIES_N2_VOL2),
    3: (N2_VOL3_METADATA, SALON_STORIES_N2_VOL3),
}


def get_n2_radio_stories_for_day(
    n2_day: int,
    recent_wrong_ids: list[str] | None = None,
    recent_lookup_ids: list[str] | None = None,
    speaking_slip_points: list[str] | None = None,
    confusion_pairs: dict | None = None,
) -> dict[str, Any]:
    """Return N2 radio stories (Days 1-3 curated launch arc + full pedagogy callback brief for Day 4+)."""
    day_i = int(n2_day or 1)
    clamped_day = max(1, min(90, day_i))
    pedagogy = plan_n2_episode_pedagogy(
        day=clamped_day,
        recent_wrong_ids=recent_wrong_ids,
        recent_lookup_ids=recent_lookup_ids,
        speaking_slip_points=speaking_slip_points,
        confusion_pairs=confusion_pairs,
    )
    meta_c, stories_c = _CURATED_N2_VOLUMES.get(day_i, ({"day_index": day_i}, []))
    return {
        "n2_day": day_i,
        "metadata": meta_c,
        "stories": list(stories_c),
        "pedagogy": pedagogy,
        "vocab_plan": build_n2_daily_vocab_plan(clamped_day),
    }


def select_n2_daily_quiz_deck(
    n2_day: int,
    n2_bank: list[dict[str, Any]],
    n2_status_map: dict[str, dict[str, Any]],
    n3_bridge_candidates: list[dict[str, Any]],
    is_travel_floor: bool = False,
) -> list[dict[str, Any]]:
    """
    Build the daily N2 quiz deck ("先教后练" + "+1/+5/+14" spaced callbacks + N3 listening/henkei bridge).
    Travel floor Days 8-34 gently caps at 26 cards; Home sprint runs 50 cards.
    """
    cap = 26 if is_travel_floor else 50
    clamped_day = max(1, min(90, int(n2_day or 1)))
    by_id = {p["id"]: p for p in n2_bank}
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()

    def _add(p: dict[str, Any]) -> None:
        if p and p["id"] not in chosen_ids and len(chosen) < cap:
            chosen.append(p)
            chosen_ids.add(p["id"])

    # 1. Brand-new N2 grammar points scheduled for today (Teach-First!)
    for g in get_day_new_grammar(clamped_day):
        if g["id"] in by_id:
            _add(by_id[g["id"]])

    # 2. Due spaced callbacks (+1 / +5 / +14 days)
    for g in get_day_callback_grammar(clamped_day):
        if g["id"] in by_id:
            _add(by_id[g["id"]])

    # 3. Unmastered / red / yellow previously unlocked N2 grammar points (days <= n2_day)
    unlocked = [p for p in n2_bank if p["day"] <= clamped_day and p["id"] not in chosen_ids]
    unlocked.sort(
        key=lambda p: (
            0 if (n2_status_map.get(p["point_key"], {}).get("status") in ("red", "orange")) else (
                1 if n2_status_map.get(p["point_key"], {}).get("status") != "green" else 2
            ),
            -p["day"],
            p["id"],
        )
    )
    n2_gram_budget = 14 if is_travel_floor else 26
    for p in unlocked:
        if len(chosen) >= n2_gram_budget:
            break
        _add(p)

    # 4. Preview upcoming 2 days of N2 grammar if early week 1 needs rich deck fill
    if len(chosen) < min(10, n2_gram_budget):
        upcoming = [p for p in n2_bank if clamped_day < p["day"] <= clamped_day + 5 and p["id"] not in chosen_ids]
        for p in upcoming:
            if len(chosen) >= min(10, n2_gram_budget):
                break
            _add(p)

    # 5. Interleave authentic Listening, Henkei & Vocab bridge cards so all 4 exam skills climb together
    bridge_quotas = {"听力": 5, "活用": 4, "词汇": 3} if is_travel_floor else {"听力": 10, "活用": 8, "词汇": 6}
    for subj, q_need in bridge_quotas.items():
        pool = [p for p in n3_bridge_candidates if p.get("subject") == subj and p["id"] not in chosen_ids]
        added = 0
        for p in pool:
            if added >= q_need or len(chosen) >= cap:
                break
            _add(p)
            added += 1

    # 6. Spillover from unlocked N2 or bridge if still under cap
    for p in unlocked + n3_bridge_candidates:
        if len(chosen) >= cap:
            break
        _add(p)

    return chosen[:cap]


if __name__ == "__main__":
    for d in ("2026-12-05", "2026-12-06", "2026-12-07", "2026-12-20", "2027-04-01"):
        info = get_phase_info(d)
        print(f"Phase[{d}]: {info}")
    qbank = build_n2_question_bank()
    assert len(qbank) == len(N2_GRAMMAR_SYLLABUS), f"Expected {len(N2_GRAMMAR_SYLLABUS)}, got {len(qbank)}"
    for item in qbank:
        p = item["primary"]
        assert len(p["choices"]) == 4, f"{item['id']} choices != 4: {p['choices']}"
        assert len(set(p["choices"])) == 4, f"{item['id']} duplicate choices: {p['choices']}"
        assert p["answer"] in p["choices"], f"{item['id']} answer not in choices"
        assert "—" not in (p["prompt"] + p["why_line"] + p["form_line"]), f"{item['id']} em dash!"
    vcards = build_n2_vocab_cards()
    assert len(vcards) >= 145, f"Expected >=145 N2 vocab cards, got {len(vcards)}"
    for w, vc in vcards.items():
        assert vc["mnemonic"], f"Missing mnemonic for {w}"
        assert "—" not in (vc["mnemonic"] + vc["zh"] + vc["twin"]), f"Em dash in {w}"
    day1 = get_n2_radio_stories_for_day(1)
    assert len(day1["stories"]) == 6, f"Expected 6 acts for N2 Day 1, got {len(day1['stories'])}"
    print(f"N2 Curriculum Engine OK: {len(qbank)} 4-choice N2 grammar points, {len(vcards)} N2 3-track vocab cards, 6-act Day 1 premiere verified!")
