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
    return {
        "prefer_tags": [str(t) for t in (r.get("prefer_tags") or [])],
        "avoid_story_ids": {str(s) for s in (r.get("avoid_story_ids") or [])},
    }


def orientation(prefs: dict | None = None) -> str:
    prefs = load_prefs() if prefs is None else prefs
    return "portrait" if (prefs.get("ui") or {}).get("orientation") == "portrait" else "any"
