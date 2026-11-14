#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity N3 Central Brain Algorithm v2.0 (Dual-Hand + All-4-Module Sync)
Merges answers from Phone/Desktop Audio PWA (practice_log.jsonl) and Grok Bots,
updates S0-S3 mastery state across ALL 4 modules (grammar, henkei, vocab, listening),
recomputes summary counts and PT countdown, and compiles index.html.
"""
import datetime
import json
import os
import subprocess
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
EXAM_DATE = datetime.date(2026, 12, 6)
PT_TZ = ZoneInfo("America/Los_Angeles")


def step_status(cur_status: str, ok: bool, again: bool) -> str:
    if again:
        return "orange"
    if not ok:
        return "red"
    return "green" if cur_status in ("yellow", "green") else "yellow"


def apply_practice_logs(state: dict) -> int:
    if not os.path.exists(LOG_PATH):
        return 0
    applied = 0
    seen_ts = set(state.get("_processed_log_ts", []))

    g_map = {p["name"]: p for p in state.get("grammar_points", [])}
    h_map = {p["id"]: p for p in state.get("henkei_points", [])}
    h_name_map = {p["name"]: p for p in state.get("henkei_points", [])}
    v_map = {v["word"]: v for v in state.get("vocab_tracked", [])}
    l_map = {lp["id"]: lp for lp in state.get("listening_points", [])}
    l_name_map = {lp["name"]: lp for lp in state.get("listening_points", [])}

    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ts = rec.get("ts", "")
            if ts and ts in seen_ts:
                continue
            if ts:
                seen_ts.add(ts)
            applied += 1

            pt = str(rec.get("point", "")).strip()
            ok = str(rec.get("correct", "")).lower() == "true"
            again = str(rec.get("ask_again", "")).lower() == "true"

            if pt in g_map:
                gp = g_map[pt]
                gp["status"] = step_status(gp.get("status", "yellow"), ok, again)
            elif pt in h_map or pt in h_name_map:
                hp = h_map.get(pt) or h_name_map.get(pt)
                hp["status"] = step_status(hp.get("status", "gray"), ok, again)
            elif pt in l_map or pt in l_name_map:
                lp = l_map.get(pt) or l_name_map.get(pt)
                lp["status"] = step_status(lp.get("status", "gray"), ok, again)
            elif pt in v_map:
                vp = v_map[pt]
                vp["seen"] = vp.get("seen", 0) + 1
                if not ok or again:
                    vp["wrong"] = vp.get("wrong", 0) + 1
                    vp["streak"] = 0
                    vp["status"] = "red"
                else:
                    vp["streak"] = vp.get("streak", 0) + 1
                    vp["status"] = "green" if vp["streak"] >= 2 else "yellow"

    state["_processed_log_ts"] = sorted(seen_ts)[-3000:]
    return applied


def recompute_summary(state: dict) -> None:
    summary = state.setdefault("summary", {})
    for key, arr_key in (
        ("grammar", "grammar_points"),
        ("henkei", "henkei_points"),
        ("listening", "listening_points"),
        ("vocab", "vocab_tracked"),
    ):
        items = state.get(arr_key, [])
        sec = summary.setdefault(key, {})
        for st in ("green", "yellow", "orange", "red", "gray"):
            cnt = sum(1 for x in items if x.get("status") == st)
            if cnt or st in sec:
                sec[st] = cnt
        sec["total"] = len(items)


def main():
    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    days_left = max(0, (EXAM_DATE - now_pt.date()).days)
    state["days_left"] = days_left
    state["updated_at"] = now_pt.strftime("%Y-%m-%d %H:%M PT")

    count = apply_practice_logs(state)
    recompute_summary(state)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    import sys
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v2 synced {count} records across all 4 modules; days_left={days_left}.")


if __name__ == "__main__":
    main()
