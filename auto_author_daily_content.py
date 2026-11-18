#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Two-Stage Midnight/Pre-Dawn Cloud Orchestrator (auto_author_daily_content.py):
1) `--mode night-summary` (runs at ~02:00 AM PT after pre-midnight study finishes):
   - Pulls all App + Grok answers from cloud store (`sync_cloud_store.py`).
   - Summarizes the just-completed study day (`night_summary.json`), promotes all missed/unsure
     points to the front of `tutor_prefs.json` `focus_points`, and runs `run_brain_algorithm.py --sync-only`
     without touching the active day's audio/HTML before 05:00 AM PT.
2) `--mode morning-prepare` (runs at ~05:00 AM PT when study date flips to the new day):
   - Audits unplayed `uchi_intellectual`《锵锵三人行》chapters and unseen quiz variant cards.
   - Curated reserve modules (`radio_salon_uchi_vol*.py`, `weak_expansion_wave*.py`) always take top priority;
     if on a future day the curated reserve ever runs low, uses `_call_chat_llm` (`GITHUB_MODELS_TOKEN` /
     `GEMINI_API_KEY` / `OPENAI_API_KEY`) to author strictly validated fallback chapters & variant cards into
     `audio/auto_generated_salon.json` and `audio/auto_generated_variants.json` before TTS synthesis begins.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

BASE_DIR = pathlib.Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from daily_news_salon_gen import (
    _call_chat_llm,
    fetch_live_nhk_news,
    load_cloud_qq_style_exemplars,
    load_qq_corpus_exemplars,
    validate_generated_story,
)
from grok_point_resolver import assert_zero_pii_text, contains_pii
import tutor_prefs

PT_TZ = ZoneInfo("America/Los_Angeles")
MIN_REAL_TS = 1_700_000_000

LOG_PATH = BASE_DIR / "practice_log.jsonl"
SNAP_PATH = BASE_DIR / "cloud_state_snapshot.json"
PREFS_PATH = BASE_DIR / "tutor_prefs.json"
NIGHT_SUMMARY_PATH = BASE_DIR / "night_summary.json"
AUTO_SALON_JSON = BASE_DIR / "audio" / "auto_generated_salon.json"
AUTO_VARIANTS_JSON = BASE_DIR / "audio" / "auto_generated_variants.json"


def collect_study_history(cutoff_study_day: str | None = None) -> tuple[
    dict[str, list[dict]],
    set[str],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    by_day_events: dict[str, list[dict]] = {}
    ever_seen_cards: set[str] = set()
    missed_by_day: dict[str, list[str]] = {}
    missed_vocab_by_day: dict[str, list[str]] = {}
    looked_up_by_day: dict[str, list[str]] = {}

    if SNAP_PATH.exists():
        try:
            snap = json.loads(SNAP_PATH.read_text(encoding="utf-8"))
            for d, dobj in (snap.get("dates") or {}).items():
                if cutoff_study_day and d > cutoff_study_day:
                    continue
                for cid, ts in (dobj.get("greenAt") or {}).items():
                    if int(ts or 0) >= MIN_REAL_TS:
                        ever_seen_cards.add(str(cid))
                for cid, ts in (dobj.get("retestAt") or {}).items():
                    if int(ts or 0) >= MIN_REAL_TS:
                        ever_seen_cards.add(str(cid))
                for lk_expr in (dobj.get("lookedUp") or []):
                    lk_s = str(lk_expr).strip()
                    if lk_s and not contains_pii(lk_s):
                        lst = looked_up_by_day.setdefault(d, [])
                        if lk_s not in lst:
                            lst.append(lk_s)
        except Exception:
            pass

    if LOG_PATH.exists():
        for raw in LOG_PATH.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except Exception:
                continue
            ts_raw = str(ev.get("ts") or "").strip()
            sday = ""
            if ts_raw:
                try:
                    dt_utc = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    sday = (dt_utc.astimezone(PT_TZ) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
                except Exception:
                    sday = ts_raw[:10]
            if not sday or (cutoff_study_day and sday > cutoff_study_day):
                continue
            by_day_events.setdefault(sday, []).append(ev)
            cid = str(ev.get("id") or "").strip()
            pt = str(ev.get("point") or "").strip()
            ok = str(ev.get("correct", "")).lower() == "true" or ev.get("correct") is True
            ask_again = str(ev.get("ask_again", "")).lower() == "true" or ev.get("ask_again") is True
            choice = str(ev.get("choice") or "")

            if cid.startswith("LK:"):
                expr = (pt or cid[3:]).strip()
                if expr and not contains_pii(expr):
                    lst = looked_up_by_day.setdefault(sday, [])
                    if expr not in lst:
                        lst.append(expr)
                continue

            if cid.startswith("VC-"):
                w = (pt or cid[3:]).strip()
                if w and not ok and not contains_pii(w):
                    vlst = missed_vocab_by_day.setdefault(sday, [])
                    if w not in vlst:
                        vlst.append(w)
                continue

            if cid and not cid.startswith("GROK-"):
                ever_seen_cards.add(cid)

            if pt and (not ok or ask_again or choice == "不确定"):
                pts = missed_by_day.setdefault(sday, [])
                if not contains_pii(pt) and pt not in pts:
                    pts.append(pt)

    return by_day_events, ever_seen_cards, missed_by_day, missed_vocab_by_day, looked_up_by_day


def run_night_summary() -> int:
    subprocess.run([sys.executable, str(BASE_DIR / "sync_cloud_store.py")], cwd=str(BASE_DIR), check=False)
    now_pt = datetime.datetime.now(PT_TZ)
    # At 02:00 AM PT, now_pt - 5h is 21:00 of the just-finished study day!
    closed_study_day = (now_pt - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    by_day, ever_seen, missed_by_day, missed_vocab_by_day, looked_up_by_day = collect_study_history(
        cutoff_study_day=closed_study_day
    )

    day_events = by_day.get(closed_study_day, [])
    missed_today = list(missed_by_day.get(closed_study_day, []))
    missed_vocab_today = list(missed_vocab_by_day.get(closed_study_day, []))
    looked_up_today = list(looked_up_by_day.get(closed_study_day, []))

    if not missed_today and missed_by_day:
        latest_d = sorted(missed_by_day.keys())[-1]
        missed_today = list(missed_by_day[latest_d])

    old_prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8")) if PREFS_PATH.exists() else {}
    prefs = json.loads(json.dumps(old_prefs, ensure_ascii=False))
    prefs["schema"] = prefs.get("schema") or "n3-tutor-prefs/3"
    prefs["exam_date"] = "2026-12-06"
    prefs["daily_load"] = {"2026-12-06": {"load": "off", "why": "exam_day"}}
    prefs.setdefault("load_caps", {"normal": 50, "light": 25, "off": 10})
    prev_focus = [p for p in prefs.get("focus_points", []) if isinstance(p, str)]
    merged_focus: list[str] = []
    for p in missed_today + missed_vocab_today + prev_focus:
        if p and not contains_pii(p) and p not in merged_focus:
            merged_focus.append(p)
    prefs["focus_points"] = merged_focus[: max(52, len(prev_focus))]
    prefs["ui"] = {"orientation": "portrait"}
    prefs["generated_at"] = now_pt.strftime("%Y-%m-%dT%H:%M%z")
    prefs_txt = json.dumps(prefs, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(prefs_txt, "tutor_prefs.json")
    PREFS_PATH.write_text(prefs_txt, encoding="utf-8")

    subprocess.run([sys.executable, str(BASE_DIR / "run_brain_algorithm.py"), "--sync-only"], cwd=str(BASE_DIR), check=True)

    # Cloud-native compilation of word/phrase lookup telemetry (zero Mac mini dependency!)
    st_live = json.loads((BASE_DIR / "n3_live_state.json").read_text(encoding="utf-8")) if (BASE_DIR / "n3_live_state.json").exists() else {}
    word_lookups = st_live.get("word_lookups") or {}
    sorted_lookups = sorted(
        word_lookups.items(),
        key=lambda kv: (-int((kv[1] or {}).get("count") or 1), str((kv[1] or {}).get("last_ts") or "")),
    )

    ledger_path = BASE_DIR / "lookup_weakness_ledger.md"
    ledger_lines = [
        "# Cloud Lookup & Weakness Telemetry Ledger",
        "",
        f"- Updated: `{now_pt.strftime('%Y-%m-%d %H:%M PT')}`",
        f"- Closed Study Day: `{closed_study_day}`",
        f"- Total Looked-Up Words/Phrases: `{len(sorted_lookups)}`",
        "",
        "| Word / Phrase | Lookups | Last Seen | Contexts |",
        "| :--- | :---: | :--- | :--- |",
    ]
    for surf, lobj in sorted_lookups[:120]:
        cnt = int((lobj or {}).get("count") or 1)
        lts = str((lobj or {}).get("last_ts") or "")[:16].replace("T", " ")
        ctxs = ", ".join((lobj or {}).get("contexts") or [])[:60]
        ledger_lines.append(f"| `{surf}` | {cnt} | `{lts}` | {ctxs} |")
    ledger_txt = "\n".join(ledger_lines) + "\n"
    assert_zero_pii_text(ledger_txt, "lookup_weakness_ledger.md")
    ledger_path.write_text(ledger_txt, encoding="utf-8")

    summary_obj = {
        "closed_study_day": closed_study_day,
        "summarized_at_pt": now_pt.isoformat(timespec="seconds"),
        "day_events_count": len(day_events),
        "missed_or_unsure_points": missed_today[:30],
        "missed_vocab_words": missed_vocab_today[:20],
        "looked_up_expressions": looked_up_today[:25],
        "looked_up_words_count": len(sorted_lookups),
        "top_looked_up_words": [
            {"surface": k, "count": int((v or {}).get("count") or 1), "last_ts": str((v or {}).get("last_ts") or "")}
            for k, v in sorted_lookups[:40]
        ],
        "ever_seen_cards_count": len(ever_seen),
    }
    sum_txt = json.dumps(summary_obj, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(sum_txt, "night_summary.json")
    NIGHT_SUMMARY_PATH.write_text(sum_txt, encoding="utf-8")
    print(
        f"[night-summary] Closed {closed_study_day} at {now_pt.strftime('%H:%M PT')}: "
        f"events={len(day_events)}, missed_quiz={len(missed_today)}, "
        f"missed_vocab={len(missed_vocab_today)}, lookups={len(looked_up_today)}"
    )
    return 0


def _validate_auto_variant(card: dict, base_id: str, existing_ids: set[str]) -> bool:
    cid = str(card.get("id") or "").strip()
    if not cid or cid in existing_ids:
        return False
    choices = card.get("choices")
    ans = str(card.get("answer") or "").strip()
    prompt = str(card.get("prompt") or "").strip()
    full_ja = str(card.get("full_ja") or "").strip()
    if not isinstance(choices, list) or len(choices) < 2 or ans not in choices:
        return False
    if not prompt or not full_ja or contains_pii(json.dumps(card, ensure_ascii=False)):
        return False
    exp_zh = str(card.get("exp_zh") or "").strip()
    if not exp_zh or re.search(r"[\u4e00-\u9fff][\u3040-\u30ff]+|[\u3040-\u30ff]+[\u4e00-\u9fff]", exp_zh):
        return False
    return True


def _author_trio_chapter(
    cid: str,
    tab_label: str,
    theme_desc: str,
    target_items: list[str],
    ja_pct: int,
    headlines: list[dict],
    exemplars: list[dict],
    seed_key: str = "",
) -> dict | None:
    sys_p = (
        "你是凤凰卫视《锵锵三人行》日本深水区版总撰稿（已吃透 3,182 期文字实录与 421 期原声轻重缓急规律）。\n"
        "主持人：窦文涛(W，北方清亮活泛、爱搭茬重复对方短语、偶有口误顺嘴改口)、"
        "梁文道(D，温厚男中音、短应答与东亚制度思想长句交替)、"
        "许子东(X，清瘦冷峻、善用『不不不』『我的问题是』冷幽默拆台)。\n"
        f"请围绕主题「{theme_desc}」创作一章 12 到 16 轮对白的深度圆桌（日语占比约 {ja_pct}%）。\n"
        "硬性铁律：\n"
        "1. 严禁机械按 W->D->X->W->D->X 排排坐念长文！必须有 D 与 X 直接交锋、4 到 15 字短促插话与长短句轻重缓急对比。\n"
        "2. 对白内所有日文词句必须 100% 用纯平假名或纯片假名书写，前后用空格或中文标点与汉字隔开，严禁汉字紧贴假名！\n"
        "3. 严禁任何英文字母、阿拉伯数字（数字全写中文）、『哈哈』『噗』、日期或考试倒计时、语法术语。\n"
        "4. 把目标日语表达自然长在故事冲突里（先中文说透语境与意思，再念地道日文）。\n"
        "输出 JSON：{\"short_tab\": \"四字标签\", \"title\": \"章节标题\", \"ja_focus\": \"日文原句(此处可写汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"X\", \"...\"], [\"D\", \"...\"], ...]}"
    )
    usr_p = json.dumps(
        {
            "theme": theme_desc,
            "must_weave_targets": target_items,
            "nhk_context": headlines[:3],
            "authentic_qqsrx_style_reference": load_cloud_qq_style_exemplars(seed_key or cid),
            "authentic_qiangqiang_examples": exemplars,
        },
        ensure_ascii=False,
    )
    raw = _call_chat_llm(sys_p, usr_p)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        st_obj = {
            "id": cid,
            "tier": "uchi_intellectual",
            "short_tab": str(parsed.get("short_tab") or tab_label)[:5],
            "tags": ["ウチ内幕", "昨晚靶向", "前后照应"],
            "title": str(parsed.get("title") or theme_desc),
            "point_ids": ["N3-G13", "G-20261114-10"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": [[str(s).strip(), str(t).strip()] for s, t in (parsed.get("turns") or [])],
        }
        if validate_generated_story(st_obj) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
            return st_obj
    except Exception:
        return None
    return None


def run_morning_prepare() -> int:
    # Ensure night_summary & lookup ledger are completely fresh even if late cloud sync packets arrived!
    run_night_summary()

    now_pt = datetime.datetime.now(PT_TZ)
    study_today = (now_pt - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    _, ever_seen, missed_by_day, missed_vocab_by_day, looked_up_by_day = collect_study_history(cutoff_study_day=None)

    prior_days = sorted(
        set(missed_by_day.keys()) | set(missed_vocab_by_day.keys()) | set(looked_up_by_day.keys())
    )
    prior_days = [d for d in prior_days if d < study_today]
    last_d = prior_days[-1] if prior_days else ""
    focus_missed = list(missed_by_day.get(last_d, []))
    focus_vocab = list(missed_vocab_by_day.get(last_d, []))
    focus_lookups = list(looked_up_by_day.get(last_d, []))
    combined_last_night = []
    for item in focus_missed + focus_vocab + focus_lookups:
        if item and item not in combined_last_night:
            combined_last_night.append(item)
    if not combined_last_night:
        combined_last_night = tutor_prefs.load_prefs().get("focus_points", [])[:10]

    # 1. Check unplayed Uchi chapter reserve + last night's uncovered items
    from radio_dialogue_bank import SALON_STORIES
    from adaptive_bank import EXTRA_PRIMARY_CARDS, VARIANT_CARDS
    from tutor_data import TUTOR_ITEMS

    def _resolve_pk(pid: str) -> str:
        if pid in TUTOR_ITEMS:
            return str(TUTOR_ITEMS[pid].get("point_key", pid))
        for ext in EXTRA_PRIMARY_CARDS:
            if ext["id"] == pid:
                return str(ext["point_key"])
        return pid

    rhist_path = BASE_DIR / "audio" / "radio_history.json"
    rhist = (json.loads(rhist_path.read_text(encoding="utf-8")).get("recent_days") or {}) if rhist_path.exists() else {}
    cutoff_dt = datetime.date.fromisoformat(study_today) - datetime.timedelta(days=14)
    recent_played = {
        sid
        for d, sids in rhist.items()
        if d < study_today and d >= cutoff_dt.isoformat()
        for sid in (sids or [])
    }
    unplayed_uchi = [
        st for st in SALON_STORIES
        if (str(st.get("id") or "").startswith("uchi") or st.get("tier") == "uchi_intellectual")
        and st["id"] not in recent_played
    ]

    covered_keys = set()
    covered_ja_blob = " ".join(str(st.get("ja_focus") or "") for st in unplayed_uchi[:11])
    for st in unplayed_uchi[:11]:
        for pid in (st.get("point_ids") or []):
            covered_keys.add(pid)
            covered_keys.add(_resolve_pk(pid))
    uncovered_last_night = [
        x for x in combined_last_night
        if x not in covered_keys and x not in covered_ja_blob
    ]
    print(
        f"[morning-prepare] {study_today}: unplayed_uchi={len(unplayed_uchi)}, "
        f"last_night_signals={combined_last_night[:10]}, uncovered={uncovered_last_night[:8]}"
    )

    existing_auto = []
    if AUTO_SALON_JSON.exists():
        try:
            existing_auto = json.loads(AUTO_SALON_JSON.read_text(encoding="utf-8"))
        except Exception:
            existing_auto = []
    existing_ids = {st["id"] for st in SALON_STORIES} | {st.get("id") for st in existing_auto if isinstance(st, dict)}

    imm = tutor_prefs.immersion_profile(day=study_today)
    ja_pct = int(round(float(imm.get("ja_ratio", 0.10)) * 100))
    headlines = fetch_live_nhk_news(max_items=6)
    exemplars = load_qq_corpus_exemplars(study_today, count=2)
    added_chapters = 0

    # Author 1 dedicated chapter targeting last night's uncovered mistakes/lookups when present
    night_cid = f"uchi_night_focus_{study_today.replace('-', '')}"
    if uncovered_last_night and night_cid not in existing_ids:
        st_night = _author_trio_chapter(
            cid=night_cid,
            tab_label="夜话深解",
            theme_desc="东京职场与市井人情背后的潜台词（专门把昨晚练习中卡壳和点查的表达聊透）",
            target_items=uncovered_last_night[:4],
            ja_pct=ja_pct,
            headlines=headlines,
            exemplars=exemplars,
            seed_key=f"{study_today}:night",
        )
        if st_night:
            existing_auto.insert(0, st_night)
            existing_ids.add(night_cid)
            added_chapters += 1

    if len(unplayed_uchi) + added_chapters < 9:
        needed_n = max(0, 10 - (len(unplayed_uchi) + added_chapters))
        topic_themes = [
            ("永田町政局", "日本政界密室协调、预算拉锯与官僚忖度逻辑"),
            ("近代思想史", "丸山真男、福泽谕吉或吉野作造看日本现代社会的组织性格"),
            ("日本文学大家", "夏目漱石、谷崎润一郎、村上春树或松本清张笔下的人性幽微"),
            ("日剧体制解剖", "《白色巨塔》《半泽直树》或《四重奏》原剧经典冲突与成年人潜台词"),
            ("东京中产暗流", "名校受验、职场人事内示、独居养老或地方老家清退的真实算计"),
        ]
        for idx_t in range(min(needed_n, len(topic_themes))):
            tab_label, theme_desc = topic_themes[idx_t]
            cid = f"uchi_auto_{study_today.replace('-', '')}_{idx_t + 1}"
            if cid in existing_ids:
                continue
            target_slice = combined_last_night[idx_t * 2 : idx_t * 2 + 3] or combined_last_night[:3]
            st_obj = _author_trio_chapter(
                cid=cid,
                tab_label=tab_label,
                theme_desc=theme_desc,
                target_items=target_slice,
                ja_pct=ja_pct,
                headlines=headlines,
                exemplars=exemplars,
                seed_key=f"{study_today}:{idx_t}",
            )
            if st_obj:
                existing_auto.insert(0, st_obj)
                existing_ids.add(cid)
                added_chapters += 1

    if added_chapters > 0:
        AUTO_SALON_JSON.parent.mkdir(parents=True, exist_ok=True)
        AUTO_SALON_JSON.write_text(json.dumps(existing_auto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[morning-prepare] Auto-authored {added_chapters} validated Uchi chapters into {AUTO_SALON_JSON.name}")

    # 2. Check unseen quiz variants for active points
    from adaptive_bank import EXTRA_PRIMARY_CARDS, VARIANT_CARDS
    from tutor_data import TUTOR_ITEMS
    by_base: dict[str, list[str]] = {}
    existing_card_ids: set[str] = set()
    for vc in VARIANT_CARDS:
        vid = str(vc.get("id") or "")
        existing_card_ids.add(vid)
        by_base.setdefault(str(vc.get("variant_of") or ""), []).append(vid)

    prim_map: dict[str, dict] = {}
    if isinstance(TUTOR_ITEMS, dict):
        for k, v in TUTOR_ITEMS.items():
            existing_card_ids.add(k)
            prim_map[k] = {"id": k, "subject": v.get("subject", "文法"), "point_key": v.get("point_key", k), "prompt": v.get("prompt_display", ""), "choices": v.get("choices", []), "answer": v.get("answer", "")}
    for ep in EXTRA_PRIMARY_CARDS:
        eid = str(ep.get("id") or "")
        existing_card_ids.add(eid)
        prim_map[eid] = ep

    exhausted_bases = []
    for bid, pinfo in prim_map.items():
        if pinfo.get("subject") == "聴解":
            continue
        all_cids = [bid] + by_base.get(bid, [])
        if not [c for c in all_cids if c not in ever_seen]:
            exhausted_bases.append(pinfo)

    if exhausted_bases:
        print(f"[morning-prepare] Found {len(exhausted_bases)} non-listening points with 0 unseen cards; attempting LLM variant generation...")
        auto_vars = []
        if AUTO_VARIANTS_JSON.exists():
            try:
                auto_vars = json.loads(AUTO_VARIANTS_JSON.read_text(encoding="utf-8"))
            except Exception:
                auto_vars = []
        batch = exhausted_bases[:12]
        sys_v = (
            "你是 JLPT N3 命题专家。请为给定的每个考点编写 1 道全新日文例句二选一变式题（严禁与原句雷同）。\n"
            "要求：\n"
            "1. prompt 用（　　）挖空，choices 含 2 个自然选项，answer 必须在 choices 内，full_ja 为填入正确答案后的完整日文句。\n"
            "2. q_before 与 q_after 为挖空前后的纯日文朗读片段（若考汉字读音则只给 q_before 不泄露目标词读音）。\n"
            "3. exp_zh 为一段自然中文语音讲解，里面穿插的日文必须 100% 写成纯假名且前后留空格（严禁汉字紧贴假名！）。\n"
            "输出 JSON：{\"items\": [{\"variant_of\": \"...\", \"subject\": \"...\", \"point_key\": \"...\", \"prompt\": \"...\", "
            "\"choices\": [\"...\", \"...\"], \"answer\": \"...\", \"full_ja\": \"...\", \"zh_meaning\": \"...\", "
            "\"why_line\": \"...\", \"core_rule\": \"...\", \"option_notes\": {\"选项1\": \"...\", \"选项2\": \"...\"}, "
            "\"q_before\": \"...\", \"q_after\": \"...\", \"exp_zh\": \"...\"}]}"
        )
        raw_v = _call_chat_llm(sys_v, json.dumps({"points": batch}, ensure_ascii=False))
        if raw_v:
            try:
                items = (json.loads(raw_v).get("items") or [])
                added_v = 0
                for idx_v, it in enumerate(items):
                    v_of = str(it.get("variant_of") or "").strip()
                    if v_of not in prim_map:
                        continue
                    cid = f"VARA-{study_today.replace('-', '')}-{idx_v + 1:02d}"
                    it["id"] = cid
                    if _validate_auto_variant(it, v_of, existing_card_ids):
                        auto_vars.append(it)
                        existing_card_ids.add(cid)
                        added_v += 1
                if added_v > 0:
                    AUTO_VARIANTS_JSON.parent.mkdir(parents=True, exist_ok=True)
                    AUTO_VARIANTS_JSON.write_text(json.dumps(auto_vars, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    print(f"[morning-prepare] Auto-authored {added_v} unseen variant cards into {AUTO_VARIANTS_JSON.name}")
            except Exception as e:
                print(f"[info] Auto-variant parse skipped: {e}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("night-summary", "morning-prepare"), required=True)
    args = ap.parse_args()
    if args.mode == "night-summary":
        return run_night_summary()
    return run_morning_prepare()


if __name__ == "__main__":
    sys.exit(main())
