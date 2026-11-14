#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JLPT N3 Central Brain Algorithm v2.0 (Dual-Hand Merger + All-4-Module State Machine)
Updates point-level S0-S3 mastery state across Grammar, Henkei, Vocab, and Listening in
n3_live_state.json, recalculates summary metrics & Pacific Time exam countdown, and rebuilds index.html.
"""
from collections import Counter
import datetime
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

from tutor_data import TUTOR_ITEMS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
EXAM_DATE = datetime.date(2026, 12, 6)
PT_TZ = ZoneInfo("America/Los_Angeles")


def apply_single_record(rec: dict, g_map: dict, h_map: dict, h_name_map: dict, v_map: dict, l_map: dict) -> bool:
    qid = str(rec.get("id", "")).strip()
    base_qid = qid[:-5] if qid.endswith("-twin") else qid
    t_item = TUTOR_ITEMS.get(base_qid, {})
    pt = str(t_item.get("point_key") or rec.get("point", "")).strip()

    ok = str(rec.get("correct", "")).lower() == "true"
    again = str(rec.get("ask_again", "")).lower() == "true"

    def next_status(cur: str) -> str:
        if again:
            return "orange"
        if not ok:
            return "red"
        return "green" if cur in ("yellow", "green") else "yellow"

    if pt in g_map:
        gp = g_map[pt]
        gp["status"] = next_status(gp.get("status", "yellow"))
        return True

    hp = h_map.get(pt) or h_name_map.get(pt)
    if hp is None and pt:
        for h_title, h_obj in h_name_map.items():
            if pt in h_title or h_title in pt:
                hp = h_obj
                break
    if hp is not None:
        hp["status"] = next_status(hp.get("status", "gray"))
        return True

    if pt in l_map:
        lp = l_map[pt]
        lp["status"] = next_status(lp.get("status", "gray"))
        return True

    if pt in v_map:
        vp = v_map[pt]
        vp["seen"] = vp.get("seen", 0) + 1
        if not ok or again:
            vp["wrong"] = vp.get("wrong", 0) + 1
            vp["streak"] = 0
            vp["status"] = "red" if not ok else "orange"
        else:
            vp["streak"] = vp.get("streak", 0) + 1
            vp["status"] = "green" if vp["streak"] >= 2 else "yellow"
        return True

    return False


def apply_practice_logs(state: dict) -> int:
    if not os.path.exists(LOG_PATH):
        return 0
    applied = 0
    seen_ts = set(state.get("_processed_log_ts_v2", []))

    g_map = {p["name"]: p for p in state.get("grammar_points", [])}
    h_map = {p["id"]: p for p in state.get("henkei_points", [])}
    h_name_map = {p["name"]: p for p in state.get("henkei_points", [])}
    v_map = {v["word"]: v for v in state.get("vocab_tracked", [])}
    l_map = {p["id"]: p for p in state.get("listening_points", [])}

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
            if apply_single_record(rec, g_map, h_map, h_name_map, v_map, l_map):
                applied += 1

    state["_processed_log_ts_v2"] = sorted(seen_ts)[-3000:]

    if "summary" in state:
        state["summary"]["grammar"]["counts"] = dict(Counter(x["status"] for x in state.get("grammar_points", [])))
        state["summary"]["henkei"]["counts"] = dict(Counter(x["status"] for x in state.get("henkei_points", [])))
        state["summary"]["henkei"]["core_counts"] = dict(
            Counter(x["status"] for x in state.get("henkei_points", []) if x.get("tier") == "core_n3")
        )
        state["summary"]["listening"]["counts"] = dict(
            Counter(x["status"] for x in state.get("listening_points", []) if x.get("is_core165"))
        )
        state["summary"]["vocab"]["counts"] = dict(Counter(x["status"] for x in state.get("vocab_tracked", [])))

    return applied


def main():
    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    days_left = max(0, (EXAM_DATE - now_pt.date()).days)
    state["days_left"] = days_left
    state["updated_at"] = now_pt.strftime("%Y-%m-%d %H:%M PT")

    count = apply_practice_logs(state)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v2 synced {count} records across all 4 modules; days_left={days_left}.")


if __name__ == "__main__":
    main()
