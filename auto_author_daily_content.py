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

from daily_news_salon_gen import _call_chat_llm, fetch_live_nhk_news, validate_generated_story
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


def collect_study_history(cutoff_study_day: str | None = None) -> tuple[dict[str, list[dict]], set[str], dict[str, list[str]]]:
    by_day_events: dict[str, list[dict]] = {}
    ever_seen_cards: set[str] = set()
    missed_by_day: dict[str, list[str]] = {}

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
            if cid and not cid.startswith("VC-") and not cid.startswith("GROK-") and not cid.startswith("LK:"):
                ever_seen_cards.add(cid)
            ok = str(ev.get("correct", "")).lower() == "true" or ev.get("correct") is True
            ask_again = str(ev.get("ask_again", "")).lower() == "true" or ev.get("ask_again") is True
            choice = str(ev.get("choice") or "")
            pt = str(ev.get("point") or "").strip()
            if pt and not cid.startswith("VC-") and not cid.startswith("LK:") and (not ok or ask_again or choice == "不确定"):
                pts = missed_by_day.setdefault(sday, [])
                if not contains_pii(pt) and pt not in pts:
                    pts.append(pt)

    return by_day_events, ever_seen_cards, missed_by_day


def run_night_summary() -> int:
    subprocess.run([sys.executable, str(BASE_DIR / "sync_cloud_store.py")], cwd=str(BASE_DIR), check=False)
    now_pt = datetime.datetime.now(PT_TZ)
    # At 02:00 AM PT, now_pt - 5h is 21:00 of the just-finished study day!
    closed_study_day = (now_pt - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    by_day, ever_seen, missed_by_day = collect_study_history(cutoff_study_day=closed_study_day)

    day_events = by_day.get(closed_study_day, [])
    missed_today = missed_by_day.get(closed_study_day, [])
    if not missed_today and missed_by_day:
        latest_d = sorted(missed_by_day.keys())[-1]
        missed_today = missed_by_day[latest_d]

    old_prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8")) if PREFS_PATH.exists() else {}
    prefs = json.loads(json.dumps(old_prefs, ensure_ascii=False))
    prefs["schema"] = prefs.get("schema") or "n3-tutor-prefs/3"
    prefs["exam_date"] = "2026-12-06"
    prefs["daily_load"] = {"2026-12-06": {"load": "off", "why": "exam_day"}}
    prefs.setdefault("load_caps", {"normal": 50, "light": 25, "off": 10})
    prev_focus = [p for p in prefs.get("focus_points", []) if isinstance(p, str)]
    merged_focus: list[str] = []
    for p in missed_today + prev_focus:
        if p and not contains_pii(p) and p not in merged_focus:
            merged_focus.append(p)
    prefs["focus_points"] = merged_focus[:max(48, len(prev_focus))]
    prefs["ui"] = {"orientation": "portrait"}
    prefs["generated_at"] = now_pt.strftime("%Y-%m-%dT%H:%M%z")
    prefs_txt = json.dumps(prefs, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(prefs_txt, "tutor_prefs.json")
    PREFS_PATH.write_text(prefs_txt, encoding="utf-8")

    subprocess.run([sys.executable, str(BASE_DIR / "run_brain_algorithm.py"), "--sync-only"], cwd=str(BASE_DIR), check=True)

    summary_obj = {
        "closed_study_day": closed_study_day,
        "summarized_at_pt": now_pt.isoformat(timespec="seconds"),
        "day_events_count": len(day_events),
        "missed_or_unsure_points": missed_today[:30],
        "ever_seen_cards_count": len(ever_seen),
    }
    sum_txt = json.dumps(summary_obj, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(sum_txt, "night_summary.json")
    NIGHT_SUMMARY_PATH.write_text(sum_txt, encoding="utf-8")
    print(
        f"[night-summary] Closed {closed_study_day} at {now_pt.strftime('%H:%M PT')}: "
        f"events={len(day_events)}, missed_focus={len(missed_today)}, ever_seen_cards={len(ever_seen)}"
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


def run_morning_prepare() -> int:
    subprocess.run([sys.executable, str(BASE_DIR / "sync_cloud_store.py")], cwd=str(BASE_DIR), check=False)
    now_pt = datetime.datetime.now(PT_TZ)
    study_today = (now_pt - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    _, ever_seen, missed_by_day = collect_study_history(cutoff_study_day=None)
    prior_days = sorted(d for d in missed_by_day if d < study_today)
    focus_missed = missed_by_day[prior_days[-1]] if prior_days else tutor_prefs.load_prefs().get("focus_points", [])[:12]

    # 1. Check unplayed Uchi chapter reserve
    from radio_dialogue_bank import SALON_STORIES
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
    print(f"[morning-prepare] {study_today}: unplayed_uchi_chapters={len(unplayed_uchi)}, focus_missed={focus_missed[:10]}")

    if len(unplayed_uchi) < 9:
        imm = tutor_prefs.immersion_profile(day=study_today)
        ja_pct = int(round(float(imm.get("ja_ratio", 0.10)) * 100))
        headlines = fetch_live_nhk_news(max_items=6)
        existing_auto = []
        if AUTO_SALON_JSON.exists():
            try:
                existing_auto = json.loads(AUTO_SALON_JSON.read_text(encoding="utf-8"))
            except Exception:
                existing_auto = []
        existing_ids = {st["id"] for st in SALON_STORIES} | {st.get("id") for st in existing_auto if isinstance(st, dict)}
        needed_n = max(0, 10 - len(unplayed_uchi))
        topic_themes = [
            ("永田町政局", "日本政界密室协调、预算拉锯与官僚忖度逻辑"),
            ("近代思想史", "丸山真男、福泽谕吉或吉野作造看日本现代社会的组织性格"),
            ("日本文学大家", "夏目漱石、谷崎润一郎、村上春树或松本清张笔下的人性幽微"),
            ("日剧体制解剖", "《白色巨塔》《半泽直树》或《四重奏》原剧经典冲突与成年人潜台词"),
            ("东京中产暗流", "名校受验、职场人事内示、独居养老或地方老家清退的真实算计"),
        ]
        added_chapters = 0
        for idx_t in range(min(needed_n, len(topic_themes))):
            tab_label, theme_desc = topic_themes[idx_t]
            target_Slice = focus_missed[idx_t * 2 : idx_t * 2 + 3] or focus_missed[:3]
            sys_p = (
                "你是凤凰卫视《锵锵三人行》日本深水区版总撰稿。主持人：文涛(W，俗趣机敏、偶有顺嘴改口)、"
                "文道(D，政经思想史视野)、子东(X，文学与人性冷幽默)。\n"
                f"请围绕主题「{theme_desc}」创作一章 9 到 10 轮对白的深度圆桌（日语占比约 {ja_pct}%）。\n"
                "硬性铁律：\n"
                "1. 对白内所有日文词句必须 100% 用纯平假名或纯片假名书写，前后用空格或中文标点与汉字隔开，严禁汉字与假名直接相连！\n"
                "2. 对白内严禁出现任何英文字母、阿拉伯数字（数字全写中文如二零二六）、『哈哈』『噗』、日期或考试倒计时、语法术语。\n"
                "3. 自然融入目标日语表达，视角必须是日本内部（ウチ）深层社会肌理。\n"
                "输出 JSON：{\"short_tab\": \"四字内标签\", \"title\": \"章节标题\", \"ja_focus\": \"日文原句(可含汉字)\", "
                "\"turns\": [[\"W\", \"...\"], [\"D\", \"...\"], [\"X\", \"...\"], ...]}"
            )
            usr_p = json.dumps(
                {"theme": theme_desc, "target_points": target_Slice, "nhk_context": headlines[:3]},
                ensure_ascii=False,
            )
            raw = _call_chat_llm(sys_p, usr_p)
            if not raw:
                break
            try:
                parsed = json.loads(raw)
                cid = f"uchi_auto_{study_today.replace('-', '')}_{idx_t + 1}"
                if cid in existing_ids:
                    continue
                st_obj = {
                    "id": cid,
                    "tier": "uchi_intellectual",
                    "short_tab": str(parsed.get("short_tab") or tab_label)[:5],
                    "tags": ["ウチ内幕", "思想人文", "前后照应"],
                    "title": str(parsed.get("title") or theme_desc),
                    "point_ids": ["N3-G13", "G-20261114-10"],
                    "ja_focus": str(parsed.get("ja_focus") or ""),
                    "turns": [[str(s).strip(), str(t).strip()] for s, t in (parsed.get("turns") or [])],
                }
                if validate_generated_story(st_obj) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
                    existing_auto.insert(0, st_obj)
                    existing_ids.add(cid)
                    added_chapters += 1
            except Exception:
                continue
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
