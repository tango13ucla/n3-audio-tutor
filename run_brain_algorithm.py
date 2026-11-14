#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity N3 Central Brain Algorithm v4.0 (Live Cloud Relay + Dual-Hand Sync)
1. Drains real-time phone/desktop answers from silent cloud relay into practice_log.jsonl.
2. Merges answers from Phone/Desktop Audio PWA and Grok Bots across ALL 4 modules.
3. Recomputes S0-S3 mastery state, summary counts, and PT countdown.
4. Supports --drain-only (fast 6h persistence + HTML update) and full mode (with neural audio + 35m custom podcast).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.request
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
EXAM_DATE = datetime.date(2026, 12, 6)
PT_TZ = ZoneInfo("America/Los_Angeles")
CLOUD_SYNC_TOPIC = "n3pwa_8c4e91f2a7d03b65e2194f8a0c7d3e52"


def drain_cloud_relay() -> int:
    """Pulls recent phone/desktop quiz answers from silent cloud relay into practice_log.jsonl."""
    existing_ts = set()
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        existing_ts.add(str(json.loads(ln).get("ts", "")))
                    except Exception:
                        pass
        except Exception:
            pass

    url = f"https://ntfy.sh/{CLOUD_SYNC_TOPIC}/json?since=all&poll=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "n3-brain-sync/4.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[relay] Cloud relay check skipped ({exc}).")
        return 0

    new_records = {}
    for ln in raw_text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
            if ev.get("event") != "message" or not ev.get("message"):
                continue
            payload = json.loads(ev["message"])
            batch = payload.get("logs", []) if isinstance(payload, dict) and "logs" in payload else [payload]
            for rec in batch:
                if not isinstance(rec, dict):
                    continue
                ts = str(rec.get("ts", "")).strip()
                pt = str(rec.get("point", "")).strip()
                if not ts or not pt or ts in existing_ts or ts in new_records:
                    continue
                new_records[ts] = {
                    "id": str(rec.get("id", ""))[:40],
                    "point": pt[:80],
                    "correct": str(rec.get("correct", "false")).lower() == "true",
                    "ask_again": str(rec.get("ask_again", "false")).lower() == "true",
                    "source": "pwa",
                    "ts": ts,
                }
        except Exception:
            continue

    if not new_records:
        return 0

    sorted_recs = [new_records[k] for k in sorted(new_records.keys())]
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for r in sorted_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[relay] Drained {len(sorted_recs)} new phone/desktop answer(s) into practice_log.jsonl.")
    return len(sorted_recs)


def step_status(cur_status: str, ok: bool, again: bool) -> str:
    if not ok:
        return "red"
    if again:
        return "orange"
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
            ts = str(rec.get("ts", "")).strip()
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
                if not ok:
                    vp["wrong"] = vp.get("wrong", 0) + 1
                    vp["streak"] = 0
                    vp["status"] = "red"
                elif again:
                    vp["streak"] = 0
                    vp["status"] = "orange"
                else:
                    vp["streak"] = vp.get("streak", 0) + 1
                    vp["status"] = "green" if vp["streak"] >= 2 else "yellow"

    state["_processed_log_ts"] = sorted(seen_ts)[-4000:]
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--drain-only", action="store_true", help="Drain cloud answers & rebuild HTML without re-synthesizing podcast")
    args = parser.parse_args()

    drained = drain_cloud_relay()

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

    if not args.drain_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_daily_radio.py")], check=True)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v4 synced {count} records (drained={drained}, drain_only={args.drain_only}); days_left={days_left}.")


if __name__ == "__main__":
    main()
