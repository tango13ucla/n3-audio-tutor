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
SNAPSHOT_PATH = os.path.join(BASE_DIR, "cloud_state_snapshot.json")
EXAM_DATE = datetime.date(2026, 12, 6)
PT_TZ = ZoneInfo("America/Los_Angeles")


def drain_cloud_relay() -> int:
    import sys
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    import sync_cloud_store as scs
    return int(scs.main() or 0)


def step_status(cur_status: str, ok: bool, again: bool) -> str:
    if not ok:
        return "red"
    if again:
        return "orange"
    return "green" if cur_status in ("yellow", "green") else "yellow"


def _load_extra_vocab_meta() -> dict:
    meta = {}
    try:
        import sys
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        from adaptive_bank import CORE_N3_KANA_VOCAB, EXTRA_WORDS
        from sentence_lexicon import SENTENCE_LEXICON
        from tutor_data import WORD_DICT
        for src in (SENTENCE_LEXICON, WORD_DICT, EXTRA_WORDS):
            for w, info in src.items():
                if isinstance(info, dict) and info.get("zh"):
                    meta[w] = {
                        "category": "核心词汇",
                        "note": info.get("tip") or info.get("zh") or "",
                    }
        for kw, pitch, desc in CORE_N3_KANA_VOCAB:
            meta.setdefault(kw, {
                "category": "高频假名副词",
                "note": f"声调 {pitch} · {desc}",
            })
    except Exception:
        pass
    return meta


def _enroll_vocab_if_needed(state: dict, v_map: dict, word: str, extra_meta: dict, init_status: str) -> dict | None:
    if not word or word in v_map:
        return v_map.get(word)
    info = extra_meta.get(word, {})
    entry = {
        "word": word,
        "category": info.get("category") or "睡前闪卡生词",
        "status": init_status,
        "seen": 0,
        "wrong": 0,
        "streak": 0,
        "classroom_note": info.get("note") or "",
    }
    state.setdefault("vocab_tracked", []).append(entry)
    v_map[word] = entry
    return entry


def apply_practice_logs(state: dict) -> int:
    applied = 0
    seen_ts = set(state.get("_processed_log_ts", []))
    extra_meta = _load_extra_vocab_meta()

    g_map = {p["name"]: p for p in state.get("grammar_points", [])}
    h_map = {p["id"]: p for p in state.get("henkei_points", [])}
    h_name_map = {p["name"]: p for p in state.get("henkei_points", [])}
    v_map = {v["word"]: v for v in state.get("vocab_tracked", [])}
    l_map = {lp["id"]: lp for lp in state.get("listening_points", [])}
    l_name_map = {lp["name"]: lp for lp in state.get("listening_points", [])}

    if os.path.exists(LOG_PATH):
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
                rec_id = str(rec.get("id") or rec.get("question_id") or "").strip()
                pt = str(rec.get("point", "")).strip()
                choice = str(rec.get("choice", "")).strip()
                is_flash = rec_id.startswith("FLASH-") or choice.startswith("闪卡:")
                dedup_key = f"{ts}|{rec_id}|{pt}|{choice}" if ts else ""
                if ts and (dedup_key in seen_ts or (ts in seen_ts and not is_flash)):
                    continue
                if dedup_key:
                    seen_ts.add(dedup_key)
                applied += 1

                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"

                if pt in g_map and not is_flash:
                    gp = g_map[pt]
                    gp["status"] = step_status(gp.get("status", "yellow"), ok, again)
                elif (pt in h_map or pt in h_name_map) and not is_flash:
                    hp = h_map.get(pt) or h_name_map.get(pt)
                    hp["status"] = step_status(hp.get("status", "gray"), ok, again)
                elif (pt in l_map or pt in l_name_map) and not is_flash:
                    lp = l_map.get(pt) or l_name_map.get(pt)
                    lp["status"] = step_status(lp.get("status", "gray"), ok, again)
                elif pt in v_map or is_flash:
                    vp = v_map.get(pt)
                    if vp is None and is_flash and pt in extra_meta:
                        vp = _enroll_vocab_if_needed(state, v_map, pt, extra_meta, "yellow")
                    if vp is not None:
                        vp["seen"] = vp.get("seen", 0) + 1
                        if choice == "闪卡:已熟":
                            vp["streak"] = max(2, vp.get("streak", 0) + 1)
                            vp["status"] = "green"
                        elif choice == "闪卡:顺过":
                            if vp.get("status") in ("red", "orange", "gray"):
                                vp["streak"] = max(1, vp.get("streak", 0))
                                vp["status"] = "yellow"
                        elif not ok:
                            vp["wrong"] = vp.get("wrong", 0) + 1
                            vp["streak"] = 0
                            vp["status"] = "red"
                        elif again:
                            vp["streak"] = 0
                            vp["status"] = "orange"
                        else:
                            vp["streak"] = vp.get("streak", 0) + 1
                            vp["status"] = "green" if vp["streak"] >= 2 else "yellow"

    # Reconcile latest masteryOverrides & 3-ritual progress from cloud_state_snapshot.json
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, encoding="utf-8") as sf:
                snap = json.load(sf)
            ov_seen = state.setdefault("_applied_override_ts", {})
            tier_to_status = {"done": "green", "wip": "yellow", "todo": "red"}
            for mk, mv in (snap.get("masteryOverrides") or {}).items():
                if not (isinstance(mv, list) and len(mv) >= 2):
                    continue
                tier = str(mv[0] or "")
                ts_i = int(mv[1] or 0)
                if tier not in tier_to_status or ts_i <= int(ov_seen.get(mk) or 0):
                    continue
                ov_seen[mk] = ts_i
                st_val = tier_to_status[tier]
                if mk in g_map:
                    g_map[mk]["status"] = st_val
                elif mk in h_map or mk in h_name_map:
                    (h_map.get(mk) or h_name_map.get(mk))["status"] = st_val
                elif mk in l_map or mk in l_name_map:
                    (l_map.get(mk) or l_name_map.get(mk))["status"] = st_val
                elif mk in v_map or mk in extra_meta:
                    vp = v_map.get(mk) or _enroll_vocab_if_needed(state, v_map, mk, extra_meta, st_val)
                    if vp is not None:
                        vp["status"] = st_val
                        if st_val == "green":
                            vp["streak"] = max(2, vp.get("streak", 0))
                        elif st_val == "red":
                            vp["streak"] = 0
                applied += 1

            dates = snap.get("dates") or {}
            if dates:
                latest_d = sorted(dates.keys())[-1]
                day = dates.get(latest_d) or {}
                r_at = int(day.get("resetAt") or 0)
                g_cnt = sum(
                    1
                    for pid, gts in (day.get("greenAt") or {}).items()
                    if int(gts or 0) > r_at and int(gts or 0) >= int((day.get("retestAt") or {}).get(pid) or 0)
                )
                fp = day.get("flashProg") if isinstance(day.get("flashProg"), list) else [0, 0, 0, 0]
                fp = [int(x or 0) for x in (fp + [0, 0, 0, 0])[:4]]
                state["daily_rituals"] = {
                    "date": latest_d,
                    "quiz_green": g_cnt,
                    "radio_max_sec": int(day.get("radioMaxSec") or 0),
                    "flash_seen": fp[0],
                    "flash_target": fp[1],
                    "flash_done": bool(fp[2] > 0),
                }
        except Exception:
            pass

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
    import sys
    sync_only = ("--sync-only" in sys.argv) or ("--drain-only" in sys.argv)
    quiz_only = ("--quiz-only" in sys.argv)

    # 1. Pull latest cross-platform answers from Cloud CRDT Bus into practice_log.jsonl & cloud_state_snapshot.json
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "sync_cloud_store.py")], check=True)

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    study_dt = (now_pt - datetime.timedelta(hours=5)).date()
    days_left = max(0, (EXAM_DATE - study_dt).days)
    state["days_left"] = days_left
    state["study_date"] = study_dt.strftime("%Y-%m-%d")
    state["updated_at"] = now_pt.strftime("%Y-%m-%d %H:%M PT")

    count = apply_practice_logs(state)
    recompute_summary(state)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if quiz_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
    elif not sync_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_daily_radio.py")], check=True)

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v4 synced {count} records (sync_only={sync_only}, quiz_only={quiz_only}); days_left={days_left}.")


if __name__ == "__main__":
    main()
