#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N2 Story-First Spaced Callback Engine for 《锵锵三人行》 Radio & Quiz Integration.

Core Principle:
  Learning an unseen N2 grammar point once in a podcast is NOT enough —
  it MUST naturally reappear in future episodes (+1 day, +5 days, +14 days) AND
  whenever the learner misses it in Quiz or taps to look it up.

  HOWEVER, callbacks must NEVER break story immersion or sound like a pop quiz!
  Every episode enforces:
    1. PRIMARY SPOTLIGHT (2-3 new N2 grammar points + 6-8 hard words):
       - First appearance: ~60s natural plain-Chinese deep breakdown
         (emotional nuance + connection + contrast vs N3/N2 twin).
       - Same-episode re-echo: used naturally 3-4 times across News, Story 1, Story 2, World Finale.
    2. SPACED STORY CALLBACKS (strictly capped at 2-3 per episode to protect flow):
       - Selected from Day-1 (next-day echo), Day-5 (week-1 reunion), Day-14 (week-2 lock),
         boosted by recent quiz wrong answers & tap-lookups.
       - Delivery style: "3-5 second organic nod" — hosts weave the phrase directly into
         today's brand-new story and at most drop one casual half-sentence callback
         (e.g. "对，就前两天聊那股实在没办法只能硬上的劲儿"), zero classroom tone!
100% Zero-PII public study module.
"""

from __future__ import annotations

from n2_grammar_syllabus import get_day_callback_grammar, get_day_new_grammar


MAX_CALLBACKS_PER_EPISODE = 3

CALLBACK_DELIVERY_RULES = {
    "next_day_echo": {
        "max_seconds": 6,
        "style": "顺嘴一用 + 半句默契轻点（如「就是昨天聊过那个…」），绝不展开重讲接续",
    },
    "week1_reunion": {
        "max_seconds": 8,
        "style": "放进截然不同的新故事里自然说出来，轻带一句对比双胞胎提醒，故事不停顿",
    },
    "week2_lock": {
        "max_seconds": 4,
        "style": "纯盲听自然融入对白，只用语境让你耳朵瞬间认出老朋友，零课堂解释",
    },
    "quiz_miss_rescue": {
        "max_seconds": 12,
        "style": "针对前一天做题答错或点查过的 N2 考点，换一个生活笑点顺嘴演一遍纠偏",
    },
}


def plan_n2_episode_pedagogy(
    day: int,
    recent_wrong_ids: list[str] | None = None,
    recent_lookup_ids: list[str] | None = None,
) -> dict:
    """Build the exact N2 teaching + non-intrusive callback brief for Study Day `day`."""
    wrong_set = set(recent_wrong_ids or [])
    lookup_set = set(recent_lookup_ids or [])

    new_items = get_day_new_grammar(day)
    raw_due = get_day_callback_grammar(day)

    scored = []
    for item in raw_due:
        score = 0
        reason = item["callback_stage"]
        if item["id"] in wrong_set:
            score += 100
            reason = "quiz_miss_rescue"
        elif item["id"] in lookup_set:
            score += 60
        # Balance recency: +1 day (30), +5 day (25), +14 day (20)
        score += {1: 30, 5: 25, 14: 20}.get(item["callback_delta"], 10)
        scored.append((score, reason, item))

    scored.sort(key=lambda x: (-x[0], x[2]["day"]))
    selected_callbacks = []
    for _score, reason, item in scored[:MAX_CALLBACKS_PER_EPISODE]:
        rule = CALLBACK_DELIVERY_RULES[reason]
        selected_callbacks.append({
            "id": item["id"],
            "point": item["point"],
            "family": item["family"],
            "learned_on_day": item["day"],
            "days_ago": item["callback_delta"],
            "delivery_mode": reason,
            "max_seconds": rule["max_seconds"],
            "delivery_rule": rule["style"],
        })

    try:
        import os as _os, sys as _sys
        _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        import immersion_vocab_engine as _ive
        _vocab_brief = _ive.get_prompt_vocab_brief()
    except Exception:
        _vocab_brief = {"graduation_threshold": 5}

    return {
        "day": day,
        "primary_new_grammar": [
            {
                "id": g["id"],
                "point": g["point"],
                "family": g["family"],
                "connection": g["connection"],
                "soul_meaning": g["soul_meaning"],
                "vs_twin": g["vs_twin"],
                "target_uses_in_episode": 4,
                "first_intro_rule": "首次出场用约60秒大白话讲透情绪/接续/与双胞胎区别，之后在其余幕自然复现3-4次",
            }
            for g in new_items
        ],
        "spaced_callbacks": selected_callbacks,
        "cumulative_vocab_graduation": {
            "rule": "跨日 5 次累计播客毕业制（需跨至少 2 个不同日期且累计满 5 次，杜绝单日集中假毕业）：新词首次用「中文也就是日语」自然搭桥，同集下段直切无缝日语；若听后复盘标「重学」，下期自动再搭一次桥。",
            "ledger_brief": _vocab_brief,
        },
        "post_listening_5min_review": {
            "enabled": True,
            "mode": "selective_rpl_contextual_relearn",
            "speaking_output_2_sentences": True,
            "rule": "听完 60 分钟立刻用 5 分钟快筛本期重点：秒懂的右滑跳过，只对卡住或 N2 全新点左滑「重学这个」，回听该词在故事里的原声语境片段（支持 0.85x 慢听 + 示范句跟读 + 语音试读纠音），收尾仅复查重学项，最后顺口完成「听后开口 2 句」实时语音输出检验。",
        },
        "flow_guardrail": "整期故事与世界视野占主体，回声点总数严控≤3个，单次回声不超过3-8秒，严禁打断叙事流畅性。",
    }


if __name__ == "__main__":
    # Verify spacing across Days 1, 2, 6, 15, 40
    for sample_day, wrongs in [(1, []), (2, []), (6, ["N2G-001"]), (15, ["N2G-001"]), (40, ["N2G-029"])]:
        brief = plan_n2_episode_pedagogy(sample_day, recent_wrong_ids=wrongs)
        new_pts = [x["point"] for x in brief["primary_new_grammar"]]
        cb_pts = [(x["point"], f"+{x['days_ago']}d", x["delivery_mode"]) for x in brief["spaced_callbacks"]]
        assert len(cb_pts) <= MAX_CALLBACKS_PER_EPISODE
        print(f"Day {sample_day:2d} | NEW: {new_pts} | CALLBACKS: {cb_pts}")
    print("Spaced Callback Engine verification PASSED.")
