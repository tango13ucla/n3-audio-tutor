#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity N3 Central Brain Algorithm v5.0 (Cross-Day 3/3 True Green + Dual-Hand Sync)
Merges answers from Phone/Desktop Audio PWA (practice_log.jsonl & cloud_state_snapshot.json)
and Grok Bots across ALL 4 modules (grammar, henkei, vocab, listening).

Honest Mastery Rule (Zero Fake Green):
- Stage 0/3 ("todo" -> red): Unfamiliar or lapsed today.
- Stage 1/3 ("wip1:YYYYMMDD" -> yellow, streak=1): Passed once cleanly on 1 study date.
- Stage 2/3 ("wip2:YYYYMMDD" -> yellow, streak=2): Passed cleanly across 2 distinct study dates.
- Stage 3/3 ("done" -> green, streak=3): Passed cleanly across 3 distinct study dates (or explicitly sealed as 太熟).
Same-day repeat passes NEVER advance more than +1 step per study date!
"""
from __future__ import annotations
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
TRUE_GREEN_EPOCH = 1794761500


def _iso_to_day_tag(ts_iso: str, fallback_tag: str) -> str:
    if not ts_iso:
        return fallback_tag
    try:
        s = str(ts_iso).strip().replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_pt = dt.astimezone(PT_TZ) - datetime.timedelta(hours=5)
        return dt_pt.strftime("%Y%m%d")
    except Exception:
        return fallback_tag


def _cur_streak(item: dict) -> int:
    if "streak" in item and isinstance(item["streak"], int):
        return max(0, min(3, item["streak"]))
    st = item.get("status", "red")
    if st == "green":
        return 3
    if st == "yellow":
        return 1
    return 0


def _apply_cross_day_step(item: dict, day_tag: str, ok: bool, again: bool, instant_done: bool = False) -> None:
    if instant_done:
        item["streak"] = 3
        item["last_ok_date"] = day_tag
        item["status"] = "green"
        return
    if not ok or again:
        item["streak"] = 0
        item["last_ng_date"] = day_tag
        item["status"] = "red"
        return

    # Correct answer / Right-Swipe
    if item.get("last_ng_date") == day_tag:
        # Lapsed earlier on this same day: recovering today reaches at most 1/3
        item["streak"] = 1
        item["last_ok_date"] = day_tag
        item["status"] = "yellow"
        return

    if item.get("last_ok_date") == day_tag:
        # Already advanced on this study date: do not double-promote on same day
        s = max(1, _cur_streak(item))
        item["streak"] = s
        item["status"] = "green" if s >= 3 else "yellow"
        return

    new_s = min(3, _cur_streak(item) + 1)
    item["streak"] = new_s
    item["last_ok_date"] = day_tag
    item["status"] = "green" if new_s >= 3 else "yellow"


def _apply_tier_override(item: dict, tier_raw: str) -> bool:
    t = str(tier_raw or "").strip()
    if not t:
        return False
    if t == "done":
        item["streak"] = 3
        item["status"] = "green"
        return True
    if t.startswith("todo"):
        parts = t.split(":", 1)
        item["streak"] = 0
        item["status"] = "red"
        if len(parts) == 2 and len(parts[1]) == 8:
            item["last_ng_date"] = parts[1]
        return True
    if t.startswith("wip2"):
        parts = t.split(":", 1)
        item["streak"] = 2
        item["status"] = "yellow"
        if len(parts) == 2 and len(parts[1]) == 8:
            item["last_ok_date"] = parts[1]
        return True
    if t.startswith("wip"):
        parts = t.split(":", 1)
        item["streak"] = 1
        item["status"] = "yellow"
        if len(parts) == 2 and len(parts[1]) == 8:
            item["last_ok_date"] = parts[1]
        return True
    return False


def _load_extra_vocab_meta() -> dict:
    meta = {}
    try:
        import sys
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        from adaptive_bank import CORE_N3_KANA_VOCAB, EXTRA_WORDS
        from sentence_lexicon import SENTENCE_LEXICON
        from tutor_data import WORD_DICT
        from vocab_cards import VOCAB_CARDS
        for src in (SENTENCE_LEXICON, WORD_DICT, EXTRA_WORDS):
            for w, info in src.items():
                if isinstance(info, dict) and info.get("zh"):
                    meta[w] = {
                        "category": "核心词汇",
                        "note": info.get("tip") or info.get("zh") or "",
                    }
        for w, vc in VOCAB_CARDS.items():
            meta[w] = {
                "category": "汉字读音与训读" if vc.get("mode") == "kanji_read" else "高频假名与副词",
                "note": vc.get("twin") or vc.get("zh") or "",
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
        "category": info.get("category") or "今日生词",
        "status": init_status,
        "seen": 0,
        "wrong": 0,
        "streak": 3 if init_status == "green" else (1 if init_status == "yellow" else 0),
        "classroom_note": info.get("note") or "",
    }
    state.setdefault("vocab_tracked", []).append(entry)
    v_map[word] = entry
    return entry


def apply_practice_logs(state: dict, fallback_day_tag: str) -> int:
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
                is_vocab_card = (
                    rec_id.startswith("FLASH-")
                    or rec_id.startswith("VC-")
                    or choice.startswith("闪卡:")
                    or choice.startswith("记词:")
                )
                dedup_key = f"{ts}|{rec_id}|{pt}|{choice}" if ts else ""
                if ts and (dedup_key in seen_ts or (ts in seen_ts and not is_vocab_card)):
                    continue
                if dedup_key:
                    seen_ts.add(dedup_key)

                # Never auto-promote passive timer events
                if choice == "闪卡:顺过":
                    continue

                applied += 1
                day_tag = _iso_to_day_tag(ts, fallback_day_tag)
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                instant_seal = choice in ("记词:太熟", "闪卡:太熟")

                if pt in g_map and not is_vocab_card:
                    _apply_cross_day_step(g_map[pt], day_tag, ok, again, instant_seal)
                elif (pt in h_map or pt in h_name_map) and not is_vocab_card:
                    hp = h_map.get(pt) or h_name_map.get(pt)
                    _apply_cross_day_step(hp, day_tag, ok, again, instant_seal)
                elif (pt in l_map or pt in l_name_map) and not is_vocab_card:
                    lp = l_map.get(pt) or l_name_map.get(pt)
                    _apply_cross_day_step(lp, day_tag, ok, again, instant_seal)
                elif pt in v_map or is_vocab_card:
                    vp = v_map.get(pt)
                    if vp is None and is_vocab_card and pt in extra_meta:
                        vp = _enroll_vocab_if_needed(state, v_map, pt, extra_meta, "red")
                    if vp is not None:
                        vp["seen"] = vp.get("seen", 0) + 1
                        if not ok and not instant_seal:
                            vp["wrong"] = vp.get("wrong", 0) + 1
                        _apply_cross_day_step(vp, day_tag, ok, again, instant_seal)

    # Reconcile latest post-epoch masteryOverrides & 3-ritual progress from cloud_state_snapshot.json
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, encoding="utf-8") as sf:
                snap = json.load(sf)
            ov_seen = state.setdefault("_applied_override_ts", {})
            for mk, mv in (snap.get("masteryOverrides") or {}).items():
                if not (isinstance(mv, list) and len(mv) >= 2):
                    continue
                tier = str(mv[0] or "")
                ts_i = int(mv[1] or 0)
                if ts_i < TRUE_GREEN_EPOCH or ts_i <= int(ov_seen.get(mk) or 0):
                    continue
                target_item = None
                if mk in g_map:
                    target_item = g_map[mk]
                elif mk in h_map or mk in h_name_map:
                    target_item = h_map.get(mk) or h_name_map.get(mk)
                elif mk in l_map or mk in l_name_map:
                    target_item = l_map.get(mk) or l_name_map.get(mk)
                elif mk in v_map or mk in extra_meta:
                    target_item = v_map.get(mk) or _enroll_vocab_if_needed(state, v_map, mk, extra_meta, "red")
                if target_item is not None and _apply_tier_override(target_item, tier):
                    ov_seen[mk] = ts_i
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

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "sync_cloud_store.py")], check=True)

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    study_dt = (now_pt - datetime.timedelta(hours=5)).date()
    days_left = max(0, (EXAM_DATE - study_dt).days)
    state["days_left"] = days_left
    state["study_date"] = study_dt.strftime("%Y-%m-%d")
    state["updated_at"] = now_pt.strftime("%Y-%m-%d %H:%M PT")

    count = apply_practice_logs(state, study_dt.strftime("%Y%m%d"))
    recompute_summary(state)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if quiz_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
    elif not sync_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_daily_radio.py")], check=True)

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v5 synced {count} records (sync_only={sync_only}, quiz_only={quiz_only}); days_left={days_left}.")


if __name__ == "__main__":
    main()
