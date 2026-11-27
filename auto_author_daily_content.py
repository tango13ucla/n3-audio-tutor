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
    _format_n2_pedagogy_instruction,
    _sanitize_generated_turns,
    bilingual_ramp_guidance,
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

            if cid.startswith("GA-"):
                if pt and choice in ("盘点:陌生", "盘点:易混", "盘点:不熟") and not contains_pii(pt):
                    pts = missed_by_day.setdefault(sday, [])
                    if pt not in pts:
                        pts.append(pt)
                continue

            if cid.startswith("HES:") or choice == "犹豫过关":
                continue

            if cid.startswith("N3_SCORE:") or choice.startswith("N3实考:") or cid.startswith("RADIO_FB:") or choice.startswith("评本期:"):
                continue

            if cid.startswith("MOCK:"):
                if pt and not ok and not contains_pii(pt):
                    pts = missed_by_day.setdefault(sday, [])
                    if pt not in pts:
                        pts.append(pt)
                continue

            if cid.startswith("SPK:") or choice.startswith(("开口:", "试读:")):
                if pt and not ok and not contains_pii(pt):
                    pts = missed_by_day.setdefault(sday, [])
                    if pt not in pts:
                        pts.append(pt)
                continue

            if cid.startswith("RV:") or choice.startswith("听后复盘:"):
                if pt and choice in ("听后复盘:重学", "听后复盘:再过") and not contains_pii(pt):
                    pts = missed_by_day.setdefault(sday, [])
                    if pt not in pts:
                        pts.append(pt)
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
    audit_blank_keys: list[str] = []
    audit_confuse_keys: list[str] = []
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
            if _mod == "grammar_points" and _it.get("status") != "green":
                _av = str(_it.get("audit_verdict") or "")
                _wk = str(_it.get("name") or "").strip()
                if _wk:
                    if _av in ("blank", "weak") and _wk not in audit_blank_keys:
                        audit_blank_keys.append(_wk)
                    elif _av == "confuse" and _wk not in audit_confuse_keys:
                        audit_confuse_keys.append(_wk)

    old_prefs = json.loads(PREFS_PATH.read_text(encoding="utf-8")) if PREFS_PATH.exists() else {}
    prefs = json.loads(json.dumps(old_prefs, ensure_ascii=False))
    prefs["schema"] = prefs.get("schema") or "n3-tutor-prefs/3"
    if closed_study_day <= "2026-12-06":
        prefs["exam_date"] = "2026-12-06"
    else:
        try:
            from n2_prep.n2_curriculum_engine import get_phase_info as _get_pi_sum
            prefs["exam_date"] = str(_get_pi_sum(closed_study_day).get("exam_date") or "2027-07-04")
        except Exception:
            prefs["exam_date"] = "2027-07-04"
    prefs["daily_load"] = {prefs["exam_date"]: {"load": "off", "why": "exam_day"}}
    prefs.setdefault("load_caps", {"normal": 60, "light": 25, "off": 10})
    prefs.setdefault("grammar_audit_daily_count", 39)
    grammar_names = {str(p.get("name") or "") for p in (st_live.get("grammar_points") or []) if p.get("name")}
    relearn_all = [
        k for k in (st_live.get("radio_relearn_queue") or {}).keys()
        if k and k not in green_keys and not contains_pii(k)
    ]
    spk_slip_all = [
        k for k in ((st_live.get("speaking_practice") or {}).get("slips") or {}).keys()
        if k and k not in green_keys and not contains_pii(k)
    ]
    relearn_grammar = [k for k in relearn_all + spk_slip_all if k.startswith("〜") or k in grammar_names]
    relearn_vocab = [k for k in relearn_all + spk_slip_all if not k.startswith("〜") and k not in grammar_names]

    prev_focus = [p for p in prefs.get("focus_points", []) if isinstance(p, str)]
    merged_focus: list[str] = []
    # Prioritize live mistakes + active radio/speaking grammar slips first, then self-audited blank/confuse blind spots
    for p in missed_today + relearn_grammar + audit_blank_keys + audit_confuse_keys + prev_focus:
        if p and p not in green_keys and not contains_pii(p) and p not in merged_focus:
            merged_focus.append(p)
    prefs["focus_points"] = merged_focus[:50]

    # Dedicated vocab focus slot so 36+ grammar audit items NEVER evict failed vocab cards, lookups, or radio relearn words!
    prev_focus_vocab = [
        w for w in prefs.get("focus_vocab", [])
        if isinstance(w, str) and not w.startswith("〜") and w not in grammar_names
    ]
    merged_vocab: list[str] = []
    for w in missed_vocab_today + relearn_vocab + prev_focus_vocab:
        if w and w not in green_keys and not w.startswith("〜") and w not in grammar_names and not contains_pii(w) and w not in merged_vocab:
            merged_vocab.append(w)
    prefs["focus_vocab"] = merged_vocab[:28]

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

    conf_pairs = st_live.get("confusion_pairs") or {}
    top_conf = [
        {"point": k, "wrong_choice": v.get("top_wrong", ""), "count": int(v.get("total", 1)), "last_date": v.get("last_date", "")}
        for k, v in sorted(
            conf_pairs.items(),
            key=lambda kv: (-int((kv[1] or {}).get("total") or 0), -int(str((kv[1] or {}).get("last_date") or "0") or 0)),
        )[:20]
        if isinstance(v, dict) and v.get("top_wrong") and not contains_pii(k) and not contains_pii(str(v.get("top_wrong") or ""))
    ]

    fb_hist = [
        h for h in (st_live.get("radio_feedback_history") or [])
        if isinstance(h, dict) and not contains_pii(json.dumps(h, ensure_ascii=False))
    ][-7:]

    try:
        from fsrs_engine import collect_leeches as _collect_leeches
        _leeches = _collect_leeches(st_live, max_items=10)
    except Exception:
        _leeches = {"vocab": [], "points": []}

    summary_obj = {
        "closed_study_day": closed_study_day,
        "summarized_at_pt": now_pt.isoformat(timespec="seconds"),
        "day_events_count": len(day_events),
        "missed_or_unsure_points": missed_today[:30],
        "missed_vocab_words": missed_vocab_today[:20],
        "top_confusion_pairs": top_conf,
        "leech_words": _leeches.get("vocab", []),
        "leech_points": _leeches.get("points", []),
        "looked_up_expressions": looked_up_today[:25],
        "looked_up_words_count": len(sorted_lookups),
        "top_looked_up_words": [
            {"surface": k, "count": int((v or {}).get("count") or 1), "last_ts": str((v or {}).get("last_ts") or "")}
            for k, v in sorted_lookups[:40]
        ],
        "recent_radio_feedback": fb_hist,
        "ever_seen_cards_count": len(ever_seen),
    }
    sum_txt = json.dumps(summary_obj, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(sum_txt, "night_summary.json")
    NIGHT_SUMMARY_PATH.write_text(sum_txt, encoding="utf-8")
    print(
        f"[night-summary] Closed {closed_study_day} at {now_pt.strftime('%H:%M PT')}: "
        f"events={len(day_events)}, missed_quiz={len(missed_today)}, "
        f"missed_vocab={len(missed_vocab_today)}, leeches={len(_leeches.get('vocab', []))}, lookups={len(looked_up_today)}, confusions={len(top_conf)}, radio_fb={len(fb_hist)}"
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
    imm_profile: dict | None = None,
    n2_pedagogy: dict | None = None,
    explicit_point_ids: list[str] | None = None,
) -> dict | None:
    recent_fb = []
    if NIGHT_SUMMARY_PATH.exists():
        try:
            recent_fb = (json.loads(NIGHT_SUMMARY_PATH.read_text(encoding="utf-8")).get("recent_radio_feedback") or [])[:5]
        except Exception:
            recent_fb = []
    vocab_brief = {}
    try:
        import immersion_vocab_engine as _ive
        vocab_brief = _ive.get_prompt_vocab_brief()
    except Exception:
        vocab_brief = {}
    n2_block = _format_n2_pedagogy_instruction(n2_pedagogy, act_role="news" if pair_part == 1 and cid.endswith("_1") else "story")
    ramp_line = bilingual_ramp_guidance(imm_profile or {"ja_ratio": max(0.12, ja_pct / 100.0), "ramp_days": 700, "day_of_365": 1, "phase": "n3_sprint"})
    sys_p = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿（深谙 3,182 期实录里的『人味』与『把一个真实历史事件剥洋葱讲透』的叙事功力）。\n"
        "三位老友（严格还原真实《锵锵三人行》2005-2017原版说话DNA）：窦文涛(W，俗人真性情、好奇心重爱追问荒唐细节、多4到15字短反应绝不当报幕员)、"
        "梁文道(D，港台温厚书卷腔、善用『其实你想想看啊』『某种程度上讲』『说起来挺吊诡的』层层推进，绝不堆砌白皮书统计数字)、"
        "许子东(X，冷幽默学者、敢用『不不不，我的问题是』『对不对？』一句拆穿时代体面背后的人性与社会结构)。\n"
        f"请围绕主题「{theme_desc}」【只讲透这一个 100% 真实发生过的日本或跨国镜像历史事件与国民公共记忆】（适配 40 分钟节目单场：约 6.3 分钟，18 到 24 轮，约 1,850 到 2,100 字），严禁泛泛议论、严禁虚构不存在的假人物或编造故事，故事性要让人听完牢牢记住！\n"
        "【听众底线：学过三年日语的内行听众，严禁一切游客科普与入门老梗！】：\n"
        "绝对禁止京都茶泡饭逐客令、京都人夸手表钢琴、京都观光公害/清水寺/岚山/艺伎、大阪阿姨砍价/指枪喊砰、敬语内外科普/报联相菠菜/鞠躬章、平安夜吃肯德基、红白跨年荞麦面一百零八下钟声、忠犬八公基础科普。\n"
        "欢迎深挖北陆金泽加贺百万石、长崎出岛、北海道、东北、九州等非京阪东深度地方史，跨国日本商业/文化镜像，以及战后政经、法律、公司治理、科学工程与人性深水区；认真呼应 `recent_listener_feedback` 里听众近期 30 秒听后反馈。\n"
        + n2_block +
        "硬性铁律：\n"
        "1. 【100% 真实公共记忆、绝对不要编】：所有人物、年份、地名、事件、公司与名言必须是真实历史与公共记忆。\n"
        "2. 【呼吸感黄金文法节奏（每章严格只放 2 到 3 个核心语法点，每 600 字以上自然带出 1 个）】：先让故事推进两三分钟再由 D/X 顺嘴带出一句地道日文示范并用一两句大白话点透，绝不每两轮就急刹车讲课。\n"
        "3. 【零洋泾浜碎词 · 自然带出词账实词】：严禁在中文句里乱塞 `いえ / くるま / じかん / おかね / せかい / くに / みせ` 这类入门小词切碎句子；可顺着语境自然提到 1 到 2 个 `immersion_vocab_ledger` 里的优先实词。\n"
        f"4. {ramp_line}\n"
        "5. 对白内所有日文词句必须 100% 用纯平假名或纯片假名书写，前后用空格或中文标点与汉字隔开，严禁汉字紧贴假名！多用句号问号，克制少用感叹号！\n"
        "6. 严禁任何英文字母、阿拉伯数字（数字全写中文）、破折号、『哈哈』『噗』、日期或考试倒计时。\n"
        "输出 JSON：{\"short_tab\": \"四字标签\", \"title\": \"章节标题\", \"ja_focus\": \"日文原句(此处可写汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"X\", \"...\"], [\"D\", \"...\"], ...]}"
    )
    usr_p = json.dumps(
        {
            "theme": theme_desc,
            "must_weave_targets": target_items,
            "n2_episode_pedagogy": n2_pedagogy or {},
            "immersion_vocab_ledger": vocab_brief,
            "recent_listener_feedback": recent_fb,
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
        is_n2 = bool(explicit_point_ids and any(str(x).startswith("N2G-") for x in explicit_point_ids))
        st_obj = {
            "id": cid,
            "tier": "n2_cross_border_world" if is_n2 else "uchi_intellectual",
            "short_tab": str(parsed.get("short_tab") or tab_label)[:5],
            "tags": ["跨国镜像", "N2深教", "少而透深故事"] if is_n2 else ["真实日本公共记忆", "少而透深故事", "润物细无声N3"],
            "title": str(parsed.get("title") or theme_desc),
            "point_ids": list(explicit_point_ids) if explicit_point_ids else ["N3-G13", "G-20261114-10", "N3-G55"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": _sanitize_generated_turns(parsed.get("turns") or []),
        }
        if pair_part in (1, 2):
            st_obj["pair_part"] = pair_part
        if validate_generated_story(st_obj, require_light_explain=(ja_pct < 45), min_chars=1600) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
            return st_obj
    except Exception:
        return None
    return None


def _interleave_taste_and_horizon(
    entries: list[tuple[int, bool, int, tuple[str, str, list[str]]]],
) -> list[tuple[str, str, list[str]]]:
    """Within each priority tier, interleave 2 resonance topics with 1 growth-horizon topic (anti-echo-chamber)."""
    by_prio: dict[int, list[tuple[bool, int, tuple[str, str, list[str]]]]] = {}
    for prio, is_horizon, seq, payload in entries:
        by_prio.setdefault(prio, []).append((is_horizon, seq, payload))
    out: list[tuple[str, str, list[str]]] = []
    for prio in sorted(by_prio.keys()):
        bucket = sorted(by_prio[prio], key=lambda x: x[1])
        taste = [p for is_h, _s, p in bucket if not is_h]
        horizon = [p for is_h, _s, p in bucket if is_h]
        ti = hi = 0
        while ti < len(taste) or hi < len(horizon):
            for _ in range(2):
                if ti < len(taste):
                    out.append(taste[ti])
                    ti += 1
            if hi < len(horizon):
                out.append(horizon[hi])
                hi += 1
    return out


def _load_unused_public_memory_topics(used_ids: set[str], existing_titles: set[str]) -> list[tuple[str, str, list[str]]]:
    entries: list[tuple[int, bool, int, tuple[str, str, list[str]]]] = []
    seq = 0
    cat_path = BASE_DIR / "public_memory_catalog.json"
    if cat_path.exists():
        try:
            raw_cat = json.loads(cat_path.read_text(encoding="utf-8"))
            topics = raw_cat.get("topics") if isinstance(raw_cat, dict) else raw_cat
            for tp in (topics or []):
                if tp.get("deprecated_tourist_cliche"):
                    continue
                tid = str(tp.get("id") or "")
                tab = str(tp.get("short_tab") or "公共记忆")[:4]
                title = str(tp.get("title") or "")
                summary = str(tp.get("real_facts") or tp.get("summary") or "")
                targets = list(tp.get("n3_targets") or [])
                if not title or any(tid and tid in uid for uid in used_ids) or title in existing_titles:
                    continue
                prio = int(tp.get("priority", 2))
                is_h = bool(tp.get("growth_horizon", False))
                entries.append((prio, is_h, seq, (tab, f"{title}：{summary}", targets)))
                seq += 1
        except Exception:
            pass

    # Also integrate curated cross-border Japan mirror catalog (high editorial fit for post-N3 / N2 phase)
    cb_path = BASE_DIR / "n2_prep" / "cross_border_japan_catalog.json"
    if cb_path.exists():
        try:
            cb_raw = json.loads(cb_path.read_text(encoding="utf-8"))
            for pil in (cb_raw.get("pillars") or []):
                for tp in (pil.get("topics") or []):
                    if tp.get("deprecated_tourist_cliche"):
                        continue
                    tid = str(tp.get("id") or "")
                    title = str(tp.get("title") or "")
                    angle = str(tp.get("angle") or "")
                    if not title or any(tid and tid in uid for uid in used_ids) or title in existing_titles:
                        continue
                    prio = int(tp.get("priority", 1))
                    is_h = bool(tp.get("growth_horizon", False))
                    entries.append((prio, is_h, seq, ("跨国镜像", f"{title}：{angle}", [])))
                    seq += 1
        except Exception:
            pass

    return _interleave_taste_and_horizon(entries)


def _load_unused_world_topics(used_ids: set[str], existing_titles: set[str]) -> list[tuple[str, str, list[str]]]:
    cat_path = BASE_DIR / "world_perspective_catalog.json"
    if not cat_path.exists():
        return []
    try:
        raw_cat = json.loads(cat_path.read_text(encoding="utf-8"))
        topics = raw_cat.get("topics") if isinstance(raw_cat, dict) else raw_cat
        entries: list[tuple[int, bool, int, tuple[str, str, list[str]]]] = []
        for idx, tp in enumerate(topics or []):
            if tp.get("deprecated_tourist_cliche"):
                continue
            tid = str(tp.get("id") or "")
            tab = str(tp.get("short_tab") or "日本看世界")[:5]
            title = str(tp.get("title") or "")
            angle = str(tp.get("japan_angle") or "")
            targets = list(tp.get("n3_targets") or [])
            if not title or any(tid and tid in uid for uid in used_ids) or title in existing_titles:
                continue
            prio = int(tp.get("priority", 2))
            is_h = bool(tp.get("growth_horizon", False))
            entries.append((prio, is_h, idx, (tab, f"{title}（日本视角：{angle}）", targets)))
        return _interleave_taste_and_horizon(entries)
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
    imm_profile: dict | None = None,
    n2_pedagogy: dict | None = None,
    explicit_point_ids: list[str] | None = None,
) -> dict | None:
    recent_fb = []
    if NIGHT_SUMMARY_PATH.exists():
        try:
            recent_fb = (json.loads(NIGHT_SUMMARY_PATH.read_text(encoding="utf-8")).get("recent_radio_feedback") or [])[:5]
        except Exception:
            recent_fb = []
    vocab_brief = {}
    try:
        import immersion_vocab_engine as _ive
        vocab_brief = _ive.get_prompt_vocab_brief()
    except Exception:
        vocab_brief = {}
    n2_block = _format_n2_pedagogy_instruction(n2_pedagogy, act_role="world")
    ramp_line = bilingual_ramp_guidance(imm_profile or {"ja_ratio": max(0.12, ja_pct / 100.0), "ramp_days": 700, "day_of_365": 1, "phase": "n3_sprint"})
    sys_p = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿，负责每天 40 分钟节目压轴的最后五分之一板块【日本看世界】（约 8 分钟，26 到 34 轮，约 2,300 到 2,600 字，不局限文史哲，主打科学/科技/医学/能源/全球财经/太空/国际新闻）。\n"
        f"请围绕主题「{theme_desc}」从日本媒体与日本社会的视角，把这件世界大事剥洋葱讲透、故事性拉满。\n"
        "三位老友（严格还原原版说话DNA）：窦文涛(W，真性情爱追问、多4到15字短反应)、梁文道(D，港台温厚书卷腔、善用『其实你想想看啊』『某种程度上讲』『挺吊诡的』)、许子东(X，犀利冷幽默、敢用『不不不，我的问题是』『对不对？』抬杠拆台)。\n"
        "听众底线（学过三年日语的内行听众）：严禁游客观光类肤浅话题与入门常识科普；优先吸收 `recent_listener_feedback` 里听众近期反馈的口味偏好与改进建议。\n"
        "编辑审美品味（知己与拓界并重）：既重底层科学原理、制度反差与人类心理，也敢拆解容易被宏大叙事忽略的微观工艺、生命机制与反直觉细节，文风冷静锋利有余味，绝不喊口号不灌鸡汤、多用句号少用感叹号。\n"
        + n2_block +
        "硬性铁律：\n"
        "1. 【呼吸感黄金文法节奏】：自然融入 2 到 3 个核心语法表达（每 600 字左右顺嘴带出 1 个，绝不频繁刹车讲课）。\n"
        "2. 【零洋泾浜碎词 · 自然带出词账实词】：严禁把 `いえ / くるま / じかん / おかね / せかい` 等入门小词撒进中文句子切碎语流；可顺着语境自然提到 1 到 2 个 `immersion_vocab_ledger` 里的优先实词。\n"
        "3. 【凤凰卫视原版《锵锵》真实收尾制式·聊天不停+12秒渐弱淡出】：所有日语点拨必须在倒数第 11 轮之前全部讲完；【最后 10 到 12 轮】必须是总计 270 到 330 字的纯中文活络闲聊（严禁含任何日文假名）！严禁整期回顾、严禁『一壶茶喝完』『咱们明天见』，三人顺着话题幽默细节没完没了地互相打趣抬杠，聊到最后一句依然没聊完留半截『……』！\n"
        f"4. {ramp_line}\n"
        "5. 对白内所有日文纯假名、严禁汉字紧贴假名、严禁英文字母/阿拉伯数字/破折号/哈哈/噗/倒计时。\n"
        "输出 JSON：{\"short_tab\": \"五字标签\", \"title\": \"章节标题\", \"ja_focus\": \"日文原句\", \"turns\": [[\"W\", \"...\"], ...]}"
    )
    usr_p = json.dumps(
        {
            "theme": theme_desc,
            "must_weave_targets": target_items,
            "n2_episode_pedagogy": n2_pedagogy or {},
            "immersion_vocab_ledger": vocab_brief,
            "recent_listener_feedback": recent_fb,
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
        is_n2 = bool(explicit_point_ids and any(str(x).startswith("N2G-") for x in explicit_point_ids))
        st_obj = {
            "id": cid,
            "tier": "world_from_japan",
            "is_world_finale": True,
            "short_tab": str(parsed.get("short_tab") or tab_label)[:5],
            "tags": ["日本看世界", "科学科技国际", "N2复现" if is_n2 else "润物细无声N3"],
            "title": str(parsed.get("title") or theme_desc),
            "point_ids": list(explicit_point_ids) if explicit_point_ids else ["N3-G69", "N3-G65", "N3-G19"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": _sanitize_generated_turns(parsed.get("turns") or []),
        }
        if validate_generated_story(st_obj, require_light_explain=(ja_pct < 45), min_chars=2000) and not contains_pii(json.dumps(st_obj, ensure_ascii=False)):
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

    # 1. Check unplayed Uchi real public-memory reserve & Post-N3 N2/N1 pedagogy!
    from radio_dialogue_bank import SALON_STORIES
    from adaptive_bank import EXTRA_PRIMARY_CARDS, VARIANT_CARDS
    from tutor_data import TUTOR_ITEMS

    _phase_info = {"phase": "n3_sprint", "n2_day": 0}
    _n2_bundle = None
    try:
        from n2_prep.n2_curriculum_engine import get_n2_radio_stories_for_day, get_phase_info
        _phase_info = get_phase_info(study_today)
        if _phase_info.get("phase") in ("n2_climb", "n1_sprint"):
            _st_cur = json.loads((BASE_DIR / "n3_live_state.json").read_text(encoding="utf-8")) if (BASE_DIR / "n3_live_state.json").exists() else {}
            _n2_bundle = get_n2_radio_stories_for_day(
                int(_phase_info.get("n2_day") or 1),
                recent_wrong_ids=[str(x) for x in (_st_cur.get("radio_relearn_queue") or {}).keys()],
                recent_lookup_ids=[str(x) for x in (_st_cur.get("word_lookups") or {}).keys()],
                speaking_slip_points=[str(x) for x in ((_st_cur.get("speaking_practice") or {}).get("slips") or {}).keys()],
                confusion_pairs=_st_cur.get("confusion_pairs") or {},
            )
    except Exception:
        _n2_bundle = None

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
        f"[morning-prepare] {study_today} (phase={_phase_info.get('phase')}): unplayed_uchi={len(unplayed_uchi)}, "
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
    day_compact = study_today.replace("-", "")

    # Post-N3 (N2 Day 4+ -> 2027-12): Always guarantee a dedicated N2/N1 episode anchored to today's
    # exact `plan_n2_episode_pedagogy(n2_day)` (+1/+5/+14 spaced callbacks) instead of falling back to N3!
    is_post_n3 = _phase_info.get("phase") in ("n2_climb", "n1_sprint")
    has_curated_n2_today = bool(_n2_bundle and _n2_bundle.get("stories"))
    n2_ped = (_n2_bundle or {}).get("pedagogy") if isinstance(_n2_bundle, dict) else None
    n2_pids_today: list[str] = []
    n2_target_labels: list[str] = []
    if isinstance(n2_ped, dict):
        for _g in (list(n2_ped.get("primary_new_grammar") or []) + list(n2_ped.get("spaced_callbacks") or [])):
            if isinstance(_g, dict):
                if _g.get("id") and str(_g["id"]) not in n2_pids_today:
                    n2_pids_today.append(str(_g["id"]))
                if _g.get("point") and str(_g["point"]) not in n2_target_labels:
                    n2_target_labels.append(str(_g["point"]))

    if is_post_n3 and not has_curated_n2_today:
        today_n2_auto_ids = [sid for sid in existing_ids if str(sid).startswith(f"n2_auto_{day_compact}_")]
        if len(today_n2_auto_ids) < 4:
            catalog_topics = _load_unused_public_memory_topics(existing_ids | recent_played, existing_titles)
            # Prioritize Cross-Border Japan mirror topics first during N2/N1!
            catalog_topics.sort(key=lambda x: 0 if x[0] == "跨国镜像" else 1)
            topic_themes = catalog_topics[:2] if catalog_topics else [
                ("跨国镜像", "日本百年制造业与全球供应链深度碰撞的真实历史与当代启示", n2_target_labels[:2]),
                ("地方纵深", "非京阪东日本地方城市如何在时代巨变中走出独立格调的真实档案", n2_target_labels[:2]),
            ]
            newly_built = []
            for idx_t in range(4):
                base_label, base_desc, base_targets = topic_themes[(idx_t // 2) % len(topic_themes)]
                part_no = (idx_t % 2) + 1
                part_tag = "上半场真实历史铺陈与悬念" if part_no == 1 else "下半场关键转折与今天日本及世界的余波"
                cid = f"n2_auto_{day_compact}_{idx_t + 1}"
                if cid in existing_ids:
                    continue
                target_slice = (n2_target_labels + base_targets)[:4]
                st_obj = _author_trio_chapter(
                    cid=cid,
                    tab_label=base_label,
                    theme_desc=f"{base_desc}（{part_tag}）",
                    target_items=target_slice,
                    ja_pct=ja_pct,
                    headlines=headlines,
                    exemplars=exemplars,
                    seed_key=f"n2:{study_today}:{idx_t}",
                    pair_part=part_no,
                    imm_profile=imm,
                    n2_pedagogy=n2_ped,
                    explicit_point_ids=n2_pids_today[:4] or None,
                )
                if st_obj:
                    newly_built.append(st_obj)
                    existing_ids.add(cid)
                    added_chapters += 1
            if newly_built:
                existing_auto = newly_built + existing_auto
        w_n2_cid = f"n2_world_auto_{day_compact}"
        if w_n2_cid not in existing_ids:
            w_topics = _load_unused_world_topics(existing_ids | recent_played, existing_titles)
            if w_topics:
                w_tab, w_desc, w_targets = w_topics[0]
                w_obj = _author_world_finale_chapter(
                    cid=w_n2_cid,
                    tab_label=w_tab,
                    theme_desc=w_desc,
                    target_items=(n2_target_labels + w_targets)[:4],
                    ja_pct=ja_pct,
                    exemplars=exemplars,
                    seed_key=f"n2_world:{study_today}",
                    imm_profile=imm,
                    n2_pedagogy=n2_ped,
                    explicit_point_ids=n2_pids_today[:4] or None,
                )
                if w_obj:
                    existing_auto = [w_obj] + existing_auto
                    existing_ids.add(w_n2_cid)
                    added_chapters += 1
    elif len(unplayed_uchi) < 5:
        # Pre-N3 sprint fallback if curated Uchi volumes ever run low (< 5 scenes)
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
            cid = f"uchi_auto_{day_compact}_{idx_t + 1}"
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
                imm_profile=imm,
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
    if not is_post_n3 and len(unplayed_world) < 1:
        w_topics = _load_unused_world_topics(existing_ids | recent_played, existing_titles)
        if w_topics:
            w_tab, w_desc, w_targets = w_topics[0]
            w_cid = f"world_auto_{day_compact}"
            if w_cid not in existing_ids:
                w_obj = _author_world_finale_chapter(
                    cid=w_cid,
                    tab_label=w_tab,
                    theme_desc=w_desc,
                    target_items=(w_targets + combined_last_night[:2])[:4],
                    ja_pct=ja_pct,
                    exemplars=exemplars,
                    seed_key=f"world:{study_today}",
                    imm_profile=imm,
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
            "你是 JLPT N3 命题专家。请为给定的每个考点编写 1 道全新日文例句真题标准四选一变式题（严禁与原句雷同）。\n"
            "要求：\n"
            "1. prompt 用（　　）挖空，choices 含 4 个自然且互斥的选项（严禁近义双正解），answer 必须在 choices 内，full_ja 为填入正确答案后的完整日文句，option_notes 必须为全部 4 个选项逐一给出简洁人话中文解释（绝不可漏写，严禁破折号）。\n"
            "2. 例句场景自然鲜活，兼顾真实成人视野（东京职场与报联相/敬语、科技产品、医学健康、美术馆与建筑、荞麦面与居酒屋、篮球与体能、制造与财经），并在干扰项里刻意打磨『形态接续、纯假名副词/拟态词微差、使役与授受视角』等最容易凭大意猜错的细节，绝不出低幼送分题。\n"
            "3. q_before 与 q_after 为挖空前后的纯日文朗读片段（若考汉字读音则只给 q_before 不泄露目标词读音）。\n"
            "4. exp_zh 为一段干脆利落的中文语音讲解：绝不重复朗读原日文句，也绝不用「这句是说……」复述整句翻译；"
            "第一句直接说人话切入本题核心逻辑与干扰项辨析（严禁机械开头「考语法」「考词汇」），"
            "里面穿插的日文必须 100% 写成纯假名且前后留空格（严禁汉字紧贴假名！），严禁破折号。\n"
            "输出 JSON：{\"items\": [{\"variant_of\": \"...\", \"subject\": \"...\", \"point_key\": \"...\", \"prompt\": \"...\", "
            "\"choices\": [\"...\", \"...\", \"...\", \"...\"], \"answer\": \"...\", \"full_ja\": \"...\", \"zh_meaning\": \"...\", "
            "\"why_line\": \"...\", \"core_rule\": \"...\", \"option_notes\": {\"选项1\": \"...\", \"选项2\": \"...\", \"选项3\": \"...\", \"选项4\": \"...\"}, "
            "\"q_before\": \"...\", \"q_after\": \"...\", \"exp_zh\": \"...\"}]}"
        )
        conf_map = {}
        try:
            _st_conf = json.loads((BASE_DIR / "n3_live_state.json").read_text(encoding="utf-8"))
            conf_map = _st_conf.get("confusion_pairs") or {}
        except Exception:
            conf_map = {}
        batch_enriched = []
        for p_it in batch:
            row = dict(p_it)
            c_info = conf_map.get(str(row.get("point_key") or ""))
            if isinstance(c_info, dict) and c_info.get("top_wrong"):
                row["learner_frequent_wrong_choice"] = c_info["top_wrong"]
            batch_enriched.append(row)
        raw_v = _call_chat_llm(sys_v, json.dumps({"points": batch_enriched}, ensure_ascii=False))
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
