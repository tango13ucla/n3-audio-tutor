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
                    sday = (dt_utc.astimezone(PT_TZ) - datetime.timedelta(hours=4)).strftime("%Y-%m-%d")
                except Exception:
                    sday = ts_raw[:10]
            if not sday or (cutoff_study_day and sday > cutoff_study_day):
                continue
            by_day_events.setdefault(sday, []).append(ev)
            cid = str(ev.get("id") or "").strip()
            pt = str(ev.get("point") or "").strip()
            ok = str(ev.get("correct", "")).lower() == "true" or ev.get("correct") is True
            ask_again = str(ev.get("ask_again", "")).lower() == "true" or ev.get("ask_again", "") is True
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


def run_night_summary(target_closed_day: str | None = None) -> int:
    subprocess.run([sys.executable, str(BASE_DIR / "sync_cloud_store.py")], cwd=str(BASE_DIR), check=False)
    now_pt = datetime.datetime.now(PT_TZ)
    # At 02:00 AM PT, now_pt - 4h is 22:00 of the just-finished study day; when called from morning-prepare (>=04:00 AM), target_closed_day is yesterday.
    closed_study_day = target_closed_day or (now_pt - datetime.timedelta(hours=4)).strftime("%Y-%m-%d")
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

    subprocess.run([sys.executable, str(BASE_DIR / "run_brain_algorithm.py"), "--sync-only"], cwd=str(BASE_DIR), check=True)
    st_live = json.loads((BASE_DIR / "n3_live_state.json").read_text(encoding="utf-8")) if (BASE_DIR / "n3_live_state.json").exists() else {}
    green_keys: set[str] = set()
    for _mod, _fld in (
        ("grammar_points", "name"),
        ("henkei_points", "id"),
        ("vocab_tracked", "word"),
        ("listening_points", "id"),
    ):
        for _it in st_live.get(_mod, []):
            if _it.get("status") == "green":
                _k = str(_it.get(_fld) or "").strip()
                if _k:
                    green_keys.add(_k)

    old_prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8")) if PREFS_PATH.exists() else {}
    prefs = json.loads(json.dumps(old_prefs, ensure_ascii=False))
    prefs["schema"] = prefs.get("schema") or "n3-tutor-prefs/3"
    prefs["exam_date"] = "2026-12-06"
    prefs["daily_load"] = {"2026-12-06": {"load": "off", "why": "exam_day"}}
    prefs.setdefault("load_caps", {"normal": 50, "light": 25, "off": 10})
    prev_focus = [p for p in prefs.get("focus_points", []) if isinstance(p, str)]
    merged_focus: list[str] = []
    for p in missed_today + missed_vocab_today + prev_focus:
        if p and p not in green_keys and not contains_pii(p) and p not in merged_focus:
            merged_focus.append(p)
    prefs["focus_points"] = merged_focus[:32]
    prefs["ui"] = {"orientation": "portrait"}
    prefs["generated_at"] = now_pt.strftime("%Y-%m-%dT%H:%M%z")
    prefs_txt = json.dumps(prefs, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(prefs_txt, "tutor_prefs.json")
    PREFS_PATH.write_text(prefs_txt, encoding="utf-8")

    # Cloud-native compilation of word/phrase lookup telemetry (zero Mac mini dependency!)
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
    pair_part: int = 0,
) -> dict | None:
    sys_p = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿（深谙 3,182 期实录里的『人味』与『把一个真实历史事件剥洋葱讲透』的叙事功力）。\n"
        "三位老友：窦文涛(W，俗人真性情、好奇心重爱追问荒唐细节、绝不当报幕员)、"
        "梁文道(D，温厚会讲真实历史故事、用真实年份地点人物原话和命运反转层层推进，绝不堆砌白皮书统计数字)、"
        "许子东(X，冷幽默学者、一句话拆穿时代体面背后的人性与社会结构)。\n"
        f"请围绕主题「{theme_desc}」【只讲透这一个 100% 真实发生过的日本历史事件或国民公共记忆】（约 6.5 分钟，20 到 28 轮，日语假名占比约 {max(ja_pct, 16)}%），严禁泛泛议论、严禁虚构不存在的虚构人物或编造故事！\n"
        "硬性铁律：\n"
        "1. 【100% 真实公共记忆、绝对不要编】：所有人物、年份、地名、事件、公司与名言必须是真实日本公共记忆（日本人聊天一提就懂的文化暗号），让听众每天听，听满三年能像本地通一样无缝融入日本社会。\n"
        "2. 【1.3 倍自然语法讲解频率（每章约 4 个 N3 语法点，绝不生硬说教）】：自然融入 4 个 N3 表达（优先用给定目标）；2 到 3 个由 D/X 顺嘴用一两句大白话点明意思、接续或易混双胞胎词，W 顺手接一句；另 1 到 2 个在聊天现场一两句话自然点睛带过，像老友聊天一样顺畅，绝不变成背教科书。\n"
        "3. 【中文为框架，直接自然夹入 N5 与简单 N4 日语熟词】：像 おにぎり、おでん、コンビニ、スーパー、でんしゃ、しんかんせん、えき、テレビ、ニュース、かいしゃ、しゃちょう、ねだん、おかね、こども、かぞく、びょういん、くすり 等日常词直接用纯假名夹进中文句子，不用啰嗦翻译；但任何日文词前后紧挨的中文片段必须至少有 2 个汉字以上，严禁单字中文孤岛！\n"
        "4. 对白内所有日文词句必须 100% 用纯平假名或纯片假名书写，前后用空格或中文标点与汉字隔开，严禁汉字紧贴假名！\n"
        "5. 严禁任何英文字母、阿拉伯数字（数字全写中文）、破折号、『哈哈』『噗』、日期或考试倒计时。\n"
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
            "tags": ["真实日本公共记忆", "少而透深故事", "润物细无声N3"],
            "title": str(parsed.get("title") or theme_desc),
            "point_ids": ["N3-G13", "G-20261114-10", "N3-G55", "N3-G63"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": [[str(s).strip(), str(t).strip()] for s, t in (parsed.get("turns") or [])],
        }
        if pair_part in (1, 2):
            st_obj["pair_part"] = pair_part
        if validate_generated_story(st_obj, require_light_explain=(ja_pct < 45)) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
            return st_obj
    except Exception:
        return None
    return None


def _load_unused_public_memory_topics(used_ids: set[str], existing_titles: set[str]) -> list[tuple[str, str, list[str]]]:
    cat_path = BASE_DIR / "public_memory_catalog.json"
    if not cat_path.exists():
        return []
    try:
        raw_cat = json.loads(cat_path.read_text(encoding="utf-8"))
        topics = raw_cat.get("topics") if isinstance(raw_cat, dict) else raw_cat
        out = []
        for tp in (topics or []):
            tid = str(tp.get("id") or "")
            tab = str(tp.get("short_tab") or "公共记忆")[:4]
            title = str(tp.get("title") or "")
            summary = str(tp.get("real_facts") or tp.get("summary") or "")
            targets = list(tp.get("n3_targets") or [])
            if not title or any(tid and tid in uid for uid in used_ids) or title in existing_titles:
                continue
            out.append((tab, f"{title}：{summary}", targets))
        return out
    except Exception:
        return []


def _load_unused_world_topics(used_ids: set[str], existing_titles: set[str]) -> list[tuple[str, str, list[str]]]:
    cat_path = BASE_DIR / "world_perspective_catalog.json"
    if not cat_path.exists():
        return []
    try:
        raw_cat = json.loads(cat_path.read_text(encoding="utf-8"))
        topics = raw_cat.get("topics") if isinstance(raw_cat, dict) else raw_cat
        out = []
        for tp in (topics or []):
            tid = str(tp.get("id") or "")
            tab = str(tp.get("short_tab") or "日本看世界")[:5]
            title = str(tp.get("title") or "")
            angle = str(tp.get("japan_angle") or "")
            targets = list(tp.get("n3_targets") or [])
            if not title or any(tid and tid in uid for uid in used_ids) or title in existing_titles:
                continue
            out.append((tab, f"{title}（日本视角：{angle}）", targets))
        return out
    except Exception:
        return []


def _author_world_finale_chapter(
    cid: str,
    tab_label: str,
    theme_desc: str,
    target_items: list[str],
    ja_pct: int,
    exemplars: list[dict],
    seed_key: str = "",
) -> dict | None:
    sys_p = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿，负责每天最后五分之一压轴板块【日本看世界】（约 8 分钟，22 到 28 轮，不局限文史哲，主打科学/科技/医学/能源/全球财经/太空/国际新闻）。\n"
        f"请围绕主题「{theme_desc}」从日本媒体与日本社会的视角，把这件世界大事讲透（日语假名占比约 {max(ja_pct, 16)}%）。\n"
        "硬性铁律：\n"
        "1. 【1.3 倍自然语法频率】：自然融入 4 个 N3 语法表达（2 到 3 个顺嘴两句大白话点破意思与易混词，1 到 2 个自然一句带过），绝不生硬。\n"
        "2. 【直接夹入 N5 与简单 N4 日语词】：中文框架下直接用纯假名夹入 せかい、かがく、ニュース、びょういん、くすり、かいしゃ、おかね、ねだん、でんしゃ、コンビニ、おにぎり、おでん 等熟词，不用翻译；日文词前后相邻中文片段至少 2 个汉字，绝不留单字孤岛。\n"
        "3. 最后一轮由 W 以温暖自然的『《锵锵三人行》，咱们明天见！』作为全期唯一压轴收尾。\n"
        "4. 对白内所有日文纯假名、严禁汉字紧贴假名、严禁英文字母/阿拉伯数字/破折号/哈哈/噗/倒计时。\n"
        "输出 JSON：{\"short_tab\": \"五字标签\", \"title\": \"章节标题\", \"ja_focus\": \"日文原句\", \"turns\": [[\"W\", \"...\"], ...]}"
    )
    usr_p = json.dumps(
        {
            "theme": theme_desc,
            "must_weave_targets": target_items,
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
            "tier": "world_from_japan",
            "is_world_finale": True,
            "short_tab": str(parsed.get("short_tab") or tab_label)[:5],
            "tags": ["日本看世界", "科学科技国际", "润物细无声N3"],
            "title": str(parsed.get("title") or theme_desc),
            "point_ids": ["N3-G69", "N3-G65", "N3-G19", "N3-G67"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": [[str(s).strip(), str(t).strip()] for s, t in (parsed.get("turns") or [])],
        }
        if validate_generated_story(st_obj, require_light_explain=(ja_pct < 45)) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
            return st_obj
    except Exception:
        return None
    return None


def run_morning_prepare() -> int:
    now_pt = datetime.datetime.now(PT_TZ)
    study_today_dt = (now_pt - datetime.timedelta(hours=4)).date()
    study_today = study_today_dt.strftime("%Y-%m-%d")
    yesterday_str = (study_today_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    # Ensure yesterday's night_summary & lookup ledger are completely fresh even if 02:00 AM cron was delayed/skipped!
    run_night_summary(target_closed_day=yesterday_str)

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

    # 1. Check unplayed Uchi real public-memory reserve (5 scenes = 1 full 40-min 3-Act Deep Salon)
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
    cutoff_dt = datetime.date.fromisoformat(study_today) - datetime.timedelta(days=21)
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
    covered_ja_blob = " ".join(str(st.get("ja_focus") or "") for st in unplayed_uchi[:12])
    for st in unplayed_uchi[:12]:
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
    existing_titles = {str(st.get("title") or "") for st in SALON_STORIES} | {
        str(st.get("title") or "") for st in existing_auto if isinstance(st, dict)
    }

    imm = tutor_prefs.immersion_profile(day=study_today)
    ja_pct = int(round(float(imm.get("ja_ratio", 0.14)) * 100))
    headlines = fetch_live_nhk_news(max_items=6)
    exemplars = load_qq_corpus_exemplars(study_today, count=2)
    added_chapters = 0

    # Only synthesize fallback 2-real-story (4-scene) blocks when curated Uchi volumes run low (< 5 scenes);
    # live_news_salon_gen always supplies Act 1 (real daily news), so 4 scenes = 2 deeply told real public-memory stories!
    if len(unplayed_uchi) < 5:
        needed_n = max(0, 4 - len(unplayed_uchi))
        catalog_topics = _load_unused_public_memory_topics(existing_ids | recent_played, existing_titles)
        topic_themes = catalog_topics[:2] if catalog_topics else [
            ("时代拐点", "1964年东京奥运会与东海道新干线通车改变全日本生活节奏的真实国民记忆", ["〜につれて", "〜ばかりだ"]),
            ("商业传奇", "1979年索尼盛田昭夫力排众议推出Walkman随身听改写世界音乐史的真实内幕", ["〜にもかかわらず", "〜ことにする"]),
        ]
        newly_built = []
        for idx_t in range(min(needed_n, len(topic_themes) * 2)):
            base_label, base_desc, base_targets = topic_themes[(idx_t // 2) % len(topic_themes)]
            part_no = (idx_t % 2) + 1
            part_tag = "上半场真实历史铺陈与悬念" if part_no == 1 else "下半场关键转折与今天日本社会的余波"
            cid = f"uchi_auto_{study_today.replace('-', '')}_{idx_t + 1}"
            if cid in existing_ids:
                continue
            target_slice = (base_targets + combined_last_night[idx_t * 2 : idx_t * 2 + 2])[:3] or combined_last_night[:3]
            st_obj = _author_trio_chapter(
                cid=cid,
                tab_label=base_label,
                theme_desc=f"{base_desc}（{part_tag}）",
                target_items=target_slice,
                ja_pct=ja_pct,
                headlines=headlines,
                exemplars=exemplars,
                seed_key=f"{study_today}:{idx_t}",
                pair_part=part_no,
            )
            if st_obj:
                newly_built.append(st_obj)
                existing_ids.add(cid)
                added_chapters += 1
        if newly_built:
            existing_auto = newly_built + existing_auto

    unplayed_world = [
        st for st in SALON_STORIES
        if (st.get("is_world_finale") or st.get("tier") == "world_from_japan")
        and st["id"] not in recent_played
    ]
    if len(unplayed_world) < 1:
        w_topics = _load_unused_world_topics(existing_ids | recent_played, existing_titles)
        if w_topics:
            w_tab, w_desc, w_targets = w_topics[0]
            w_cid = f"world_auto_{study_today.replace('-', '')}"
            if w_cid not in existing_ids:
                w_obj = _author_world_finale_chapter(
                    cid=w_cid,
                    tab_label=w_tab,
                    theme_desc=w_desc,
                    target_items=(w_targets + combined_last_night[:2])[:4],
                    ja_pct=ja_pct,
                    exemplars=exemplars,
                    seed_key=f"world:{study_today}",
                )
                if w_obj:
                    existing_auto = [w_obj] + existing_auto
                    existing_ids.add(w_cid)
                    added_chapters += 1

    if added_chapters > 0:
        AUTO_SALON_JSON.parent.mkdir(parents=True, exist_ok=True)
        AUTO_SALON_JSON.write_text(json.dumps(existing_auto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[morning-prepare] Auto-authored {added_chapters} validated Uchi/World chapters into {AUTO_SALON_JSON.name}")

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
