#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory-driven tutor prefs reader (sanitized; zero personal data).

`tutor_prefs.json` is exported from the private PM Twin memory (learning prefs only;
the calendar is never consulted, exam prep first). It only contains learning knobs:
  - daily_load:   {"YYYY-MM-DD": {"load": "normal|light|off", "why": "..."}}
  - load_caps:    {"normal": 50, "light": 25, "off": 10}  quiz deck size per load
  - focus_points: point keys / names to prioritise in quiz + radio
  - radio:        {"prefer_tags": [...], "avoid_story_ids": [...]}
  - ui:           {"orientation": "portrait" | "any"}
Missing / malformed file => safe defaults (behaviour identical to before).
"""
from __future__ import annotations
import datetime
import json
import os
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFS_PATH = os.path.join(BASE_DIR, "tutor_prefs.json")
PT_TZ = ZoneInfo("America/Los_Angeles")
DEFAULT_CAPS = {"normal": 50, "light": 25, "off": 10}


def load_prefs() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            p = json.load(f)
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


def study_date() -> str:
    now = datetime.datetime.now(PT_TZ)
    return (now - datetime.timedelta(hours=5)).date().isoformat()


def today_load(prefs: dict | None = None, day: str | None = None) -> tuple[str, str]:
    prefs = load_prefs() if prefs is None else prefs
    ent = (prefs.get("daily_load") or {}).get(day or study_date()) or {}
    lv = ent.get("load", "normal")
    return (lv if lv in DEFAULT_CAPS else "normal"), str(ent.get("why", ""))


def deck_cap(prefs: dict | None = None, day: str | None = None) -> int:
    prefs = load_prefs() if prefs is None else prefs
    lv, _ = today_load(prefs, day)
    caps = dict(DEFAULT_CAPS)
    for k, v in (prefs.get("load_caps") or {}).items():
        try:
            if k in caps:
                caps[k] = max(5, min(80, int(v)))
        except Exception:
            pass
    return caps[lv]


def focus_set(prefs: dict | None = None) -> set:
    prefs = load_prefs() if prefs is None else prefs
    return {str(x).strip() for x in (prefs.get("focus_points") or []) if str(x).strip()}


def radio_prefs(prefs: dict | None = None) -> dict:
    prefs = load_prefs() if prefs is None else prefs
    r = prefs.get("radio") or {}
    ep = r.get("episode_minutes")
    if isinstance(ep, list) and len(ep) >= 2:
        ep_bounds = (max(20, int(ep[0])), max(25, int(ep[1])))
    else:
        ep_bounds = (39, 43)
    return {
        "prefer_tags": [str(t) for t in (r.get("prefer_tags") or [])],
        "avoid_story_ids": {str(s) for s in (r.get("avoid_story_ids") or [])},
        "episode_minutes": ep_bounds,
        "perspective": str(r.get("perspective", "uchi_intellectual_and_news")),
        "immersion_365": dict(r.get("immersion_365") or {}),
    }


def immersion_profile(prefs: dict | None = None, day: str | None = None) -> dict:
    """
    Computes today's exact position on the 365-Day Qiang-Qiang Bilingual Immersion Ramp:
      - Pre-N3 (up through 2026-12-06): ~10% Japanese, crisp -12% sentence tempo, Mandarin framing.
      - Post-N3 (2026-12-07 -> Day 365): smooth daily increase (+0.23%/day) from 12% -> 92% Japanese,
        while Japanese sentence tempo eases naturally from -12% -> +0% native broadcast speed.
    """
    rp = radio_prefs(prefs)
    imm = rp.get("immersion_365") or {}
    cur_str = day or study_date()
    try:
        cur_dt = datetime.date.fromisoformat(cur_str)
    except Exception:
        cur_dt = datetime.date.today()
    start_dt = datetime.date.fromisoformat(str(imm.get("start_date", "2026-11-15"))[:10])
    gate_dt = datetime.date.fromisoformat(str(imm.get("n3_gate_date", "2026-12-06"))[:10])
    pre_ratio = float(imm.get("pre_n3_ja_ratio", 0.10))
    post_start = float(imm.get("post_n3_start_ja_ratio", 0.12))
    target_365 = float(imm.get("day_365_target_ja_ratio", 0.92))

    day_num = max(1, (cur_dt - start_dt).days + 1)
    total_post_days = max(1, 365 - max(0, (gate_dt - start_dt).days + 1))

    if cur_dt <= gate_dt:
        ja_ratio = pre_ratio
        phase = "n3_sprint"
        ja_rate_pct = -12
    else:
        days_after_n3 = (cur_dt - gate_dt).days
        prog = min(1.0, days_after_n3 / float(total_post_days))
        ja_ratio = round(post_start + prog * (target_365 - post_start), 4)
        # Smoothly lift Japanese sentence speed from -12% (Dec 7) to +0% native speed by ~Month 8
        ja_rate_pct = min(0, int(round(-12 + min(1.0, prog * 1.35) * 12)))
        phase = "n2_climb" if ja_ratio < 0.50 else ("n1_immersion" if ja_ratio < 0.82 else "native_podcast")

    return {
        "day_of_365": min(365, day_num),
        "phase": phase,
        "ja_ratio": ja_ratio,
        "ja_sentence_rate": f"{ja_rate_pct:+d}%",
        "bilingual_framing": cur_dt > gate_dt,
    }


def orientation(prefs: dict | None = None) -> str:
    prefs = load_prefs() if prefs is None else prefs
    return "portrait" if (prefs.get("ui") or {}).get("orientation") == "portrait" else "any"
