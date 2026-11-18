#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity N3 Central Brain Algorithm v6.0 (Cross-Day 3/3 True Green + Cloud Grok Brief)
Merges answers from Phone/Desktop Audio PWA (practice_log.jsonl & cloud_state_snapshot.json)
and Grok Bots across ALL 4 modules (grammar, henkei, vocab, listening), and publishes
a live Zero-PII `grok_daily_brief.md` + `grok_daily_brief.json` for Grok's 07:30 PT sync.

Honest Mastery Rule (Zero Fake Green):
- Stage 0/3 ("todo" -> red / orange): Unfamiliar, lapsed today, or explicitly flagged "还是要考".
- Stage 1/3 ("wip1:YYYYMMDD" -> yellow, streak=1): Passed once cleanly on 1 study date.
- Stage 2/3 ("wip2:YYYYMMDD" -> yellow, streak=2): Passed cleanly across 2 distinct study dates.
- Stage 3/3 ("done" -> green, streak=3): Passed cleanly across 3 distinct study dates (or explicitly sealed as 太熟 / 不用再考).
Same-day repeat passes NEVER advance more than +1 step per study date!
"""
from __future__ import annotations
import datetime
import json
import os
import re
import subprocess
from zoneinfo import ZoneInfo

from grok_point_resolver import CLEAN_JA_WORD_RE, assert_zero_pii_text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "cloud_state_snapshot.json")
CONFIG_PATH = os.path.join(BASE_DIR, "cloud_sync_config.json")
GROK_BRIEF_MD_PATH = os.path.join(BASE_DIR, "grok_daily_brief.md")
GROK_BRIEF_JSON_PATH = os.path.join(BASE_DIR, "grok_daily_brief.json")

EXAM_DATE = datetime.date(2026, 12, 6)
PT_TZ = ZoneInfo("America/Los_Angeles")
TRUE_GREEN_EPOCH = 1794761500
MIN_REAL_TS = 1_700_000_000

SKIP_VOCAB_ENROLL = {
    "口语听辨", "高频假名副词", "核心词汇", "语法", "活用",
    "では", "には", "から", "まで", "ので", "のだ", "だよ", "だね",
    "こと", "おく", "ない", "だ",
    "ぱさぱさ", "ずしっと", "万年筆",
}


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
        item["status"] = "orange" if (ok and again) else "red"
        return

    # Correct answer / Right-Swipe
    if item.get("last_ng_date") == day_tag:
        # Lapsed or peeked ("直接看讲解") earlier on this same day: NEVER promote on the day of a miss!
        item["streak"] = 0
        item["status"] = "red"
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


def _can_enroll_word(word: str, extra_meta: dict) -> bool:
    if not word or word in SKIP_VOCAB_ENROLL:
        return False
    if word in extra_meta:
        return True
    if re.match(r"^(?:N3L?|[VTKAQGH])-?\d", word):
        return False
    return bool(CLEAN_JA_WORD_RE.match(word))


def _enroll_vocab_if_needed(state: dict, v_map: dict, word: str, extra_meta: dict, init_status: str) -> dict | None:
    if not word or word in v_map:
        return v_map.get(word)
    if not _can_enroll_word(word, extra_meta):
        return None
    info = extra_meta.get(word, {})
    has_kanji = bool(re.search(r"[\u4e00-\u9fff]", word))
    entry = {
        "word": word,
        "category": info.get("category") or ("汉字读音与训读" if has_kanji else "高频假名与副词"),
        "status": init_status,
        "seen": 0,
        "wrong": 0,
        "streak": 3 if init_status == "green" else (1 if init_status == "yellow" else 0),
        "classroom_note": info.get("note") or "",
    }
    state.setdefault("vocab_tracked", []).append(entry)
    v_map[word] = entry
    return entry


def apply_practice_logs(state: dict, fallback_day_tag: str = "") -> int:
    if not fallback_day_tag:
        now_pt = datetime.datetime.now(PT_TZ)
        fallback_day_tag = (now_pt - datetime.timedelta(hours=5)).strftime("%Y%m%d")

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
                src = str(rec.get("source", "")).strip()
                is_vocab_card = (
                    rec_id.startswith("FLASH-")
                    or rec_id.startswith("VC-")
                    or choice.startswith("闪卡:")
                    or choice.startswith("记词:")
                )
                dedup_key = f"{ts}|{rec_id}|{pt}|{choice}" if ts else ""
                if ts and (dedup_key in seen_ts or (ts in seen_ts and not is_vocab_card and src != "grok")):
                    continue
                if dedup_key:
                    seen_ts.add(dedup_key)

                # Lookup telemetry ("LK:<surface>"): record to brain without mutating active practice queue!
                if rec_id.startswith("LK:") or src == "lookup":
                    surf = rec_id[3:].strip() if rec_id.startswith("LK:") else choice
                    if surf:
                        wlk = state.setdefault("word_lookups", {})
                        cur_lk = wlk.get(surf) or {"count": 0, "last_ts": "", "contexts": []}
                        ctxs = list(cur_lk.get("contexts") or [])
                        if pt and pt not in ctxs:
                            ctxs.append(pt)
                        wlk[surf] = {
                            "count": int(cur_lk.get("count") or 0) + 1,
                            "last_ts": max(str(cur_lk.get("last_ts") or ""), ts),
                            "contexts": ctxs[-12:],
                        }
                    continue

                # Never auto-promote passive timer events
                if choice == "闪卡:顺过":
                    continue

                applied += 1
                day_tag = _iso_to_day_tag(ts, fallback_day_tag)
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                instant_seal = choice in ("记词:太熟", "闪卡:太熟", "Grok:不用再考")

                if pt in g_map and not is_vocab_card:
                    _apply_cross_day_step(g_map[pt], day_tag, ok, again, instant_seal)
                elif (pt in h_map or pt in h_name_map) and not is_vocab_card:
                    hp = h_map.get(pt) or h_name_map.get(pt)
                    _apply_cross_day_step(hp, day_tag, ok, again, instant_seal)
                elif (pt in l_map or pt in l_name_map) and not is_vocab_card:
                    lp = l_map.get(pt) or l_name_map.get(pt)
                    _apply_cross_day_step(lp, day_tag, ok, again, instant_seal)
                else:
                    vp = v_map.get(pt)
                    if vp is None and (is_vocab_card or src == "grok" or pt in extra_meta):
                        vp = _enroll_vocab_if_needed(state, v_map, pt, extra_meta, "red")
                    if vp is not None:
                        vp["seen"] = vp.get("seen", 0) + 1
                        if not ok and not instant_seal:
                            vp["wrong"] = vp.get("wrong", 0) + 1
                        _apply_cross_day_step(vp, day_tag, ok, again, instant_seal)

    # Reconcile latest post-epoch masteryOverrides, tappedWords & 3-ritual progress from cloud_state_snapshot.json
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
                else:
                    target_item = v_map.get(mk) or _enroll_vocab_if_needed(state, v_map, mk, extra_meta, "red")
                if target_item is not None and _apply_tier_override(target_item, tier):
                    ov_seen[mk] = ts_i
                    applied += 1

            for surf, lobj in (snap.get("wordLookups") or {}).items():
                if isinstance(lobj, dict) and surf:
                    wlk = state.setdefault("word_lookups", {})
                    cur_lk = wlk.get(surf) or {"count": 0, "last_ts": "", "contexts": []}
                    ctxs = list(dict.fromkeys(list(cur_lk.get("contexts") or []) + list(lobj.get("contexts") or [])))[-12:]
                    wlk[surf] = {
                        "count": max(int(cur_lk.get("count") or 0), int(lobj.get("count") or 0)),
                        "last_ts": max(str(cur_lk.get("last_ts") or ""), str(lobj.get("last_ts") or "")),
                        "contexts": ctxs,
                    }

            dates = snap.get("dates") or {}
            if dates:
                latest_d = sorted(dates.keys())[-1]
                day = dates.get(latest_d) or {}
                for tw in day.get("tappedWords") or []:
                    tw_s = str(tw or "").strip()
                    if tw_s:
                        wlk = state.setdefault("word_lookups", {})
                        wlk.setdefault(tw_s, {"count": 1, "last_ts": latest_d, "contexts": [f"date:{latest_d}"]})
                r_at = int(day.get("resetAt") or 0)
                g_cnt = sum(
                    1
                    for pid, gts in (day.get("greenAt") or {}).items()
                    if int(gts or 0) >= MIN_REAL_TS
                    and int(gts or 0) > r_at
                    and int(gts or 0) >= int((day.get("retestAt") or {}).get(pid) or 0)
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

    state["_processed_log_ts"] = sorted(seen_ts)[-5000:]
    return applied


def recompute_summary(state: dict) -> None:
    if "vocab_tracked" in state:
        state["vocab_tracked"] = [
            x for x in state["vocab_tracked"]
            if x.get("word") and x.get("word") not in SKIP_VOCAB_ENROLL
        ]
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
            sec[st] = cnt
        sec["total"] = len(items)


def write_cloud_grok_brief(state: dict) -> None:
    """
    Writes a 100% Zero-PII, live cloud briefing (`grok_daily_brief.md` + `.json`)
    served on GitHub Pages (`https://tango13ucla.github.io/n3-audio-tutor/grok_daily_brief.md`)
    so Grok's 07:30 PT morning planner ALWAYS gets fresh cross-channel mastery priorities
    even if Mac mini is asleep!
    """
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    grok_topic = str(cfg.get("grok_ntfy_topic") or "").strip()

    def bucket(items, fmt_fn):
        res = {"red": [], "orange": [], "yellow_1": [], "yellow_2": [], "green": []}
        for x in items:
            st = x.get("status", "gray")
            lbl = fmt_fn(x)
            if st == "red":
                res["red"].append(lbl)
            elif st == "orange":
                res["orange"].append(lbl)
            elif st == "yellow":
                if int(x.get("streak") or 1) >= 2:
                    res["yellow_2"].append(lbl)
                else:
                    res["yellow_1"].append(lbl)
            elif st == "green":
                res["green"].append(lbl)
        return res

    g_b = bucket(state.get("grammar_points", []), lambda x: x["name"])
    h_b = bucket(
        [x for x in state.get("henkei_points", []) if x.get("status") != "gray"],
        lambda x: f"{x['id']} {x['name']}",
    )
    l_b = bucket(
        [x for x in state.get("listening_points", []) if x.get("status") != "gray"],
        lambda x: f"{x['id']} {x['name']}",
    )
    v_b = bucket(state.get("vocab_tracked", []), lambda x: x["word"])

    brief_obj = {
        "schema": "n3-grok-cloud-brief/1",
        "study_date": state.get("study_date", ""),
        "updated_at": state.get("updated_at", ""),
        "days_left": state.get("days_left", 21),
        "grok_cloud_ingest_url": f"https://ntfy.sh/{grok_topic}" if grok_topic else "",
        "grammar": g_b,
        "henkei": h_b,
        "listening": l_b,
        "vocab": v_b,
    }
    json_txt = json.dumps(brief_obj, ensure_ascii=False, indent=2) + "\n"
    assert_zero_pii_text(json_txt, "grok_daily_brief.json")
    with open(GROK_BRIEF_JSON_PATH, "w", encoding="utf-8") as f:
        f.write(json_txt)

    def join_or_none(arr: list[str]) -> str:
        return "、".join(arr) if arr else "（当前无）"

    lines = [
        "# JLPT N3 中央大脑云端实时教务指令单（Zero-PII Cloud Live Brief）",
        "",
        f"- **基准学习日**：`{brief_obj['study_date']}`（距 `2026-12-06` 考试还剩 `{brief_obj['days_left']}` 天）",
        f"- **云端自动合流更新时间**：`{brief_obj['updated_at']}`",
        "- **跨日 3/3 真掌握铁律**：同一天答对多次最多推进 `+1` 格；跨 3 个不同学习日答对（或明确点击「不用再考了 / 太熟」）才进入 🟢 已过关免考名单。",
        "",
        "## 一、 语法 Bot（1. JLPT 语法）今日优先级",
        f"- **🔴 P0 急需攻克（0/3，优先出正式题）**：{join_or_none(g_b['red'])}",
        f"- **🟠 P1 重点复测（答对但要求再考，0/3）**：{join_or_none(g_b['orange'])}",
        f"- **🟡 P2 跨日巩固（2/3 临门一脚）**：{join_or_none(g_b['yellow_2'])}",
        f"- **🟡 P2 跨日巩固（1/3 待隔日验证）**：{join_or_none(g_b['yellow_1'][:35])}" + (f" 等共 {len(g_b['yellow_1'])} 项" if len(g_b["yellow_1"]) > 35 else ""),
        f"- **🟢 已过关免考（3/3，14 天内严禁重复出题）**：{join_or_none(g_b['green'])}",
        "",
        "## 二、 变形活用与敬语 Bot（2. JLPT 单词变形）今日优先级",
        f"- **🔴 P0 急需攻克（0/3）**：{join_or_none(h_b['red'])}",
        f"- **🟠 P1 重点复测（要求再考，0/3）**：{join_or_none(h_b['orange'])}",
        f"- **🟡 P2 跨日巩固（2/3 与 1/3）**：{join_or_none(h_b['yellow_2'] + h_b['yellow_1'])}",
        f"- **🟢 已过关免考（3/3，严禁重复出题）**：{join_or_none(h_b['green'])}",
        "",
        "## 三、 词汇与读音陷阱 Bot（3. JLPT 词汇）今日优先级",
        f"- **🔴 P0 急需攻克（0/3，优先辨析双胞胎假名副词与促音/浊音/训读陷阱）**：{join_or_none(v_b['red'])}",
        f"- **🟠 P1 重点复测（要求再考，0/3）**：{join_or_none(v_b['orange'])}",
        f"- **🟡 P2 跨日巩固（2/3 与 1/3）**：{join_or_none(v_b['yellow_2'] + v_b['yellow_1'])}",
        f"- **🟢 已过关免考（3/3，严禁重复出题）**：{join_or_none(v_b['green'])}",
        "",
        "## 四、 听力口语缩约 Bot（4. JLPT 听力）今日优先级",
        f"- **🔴 P0 急需攻克（0/3）**：{join_or_none(l_b['red'])}",
        f"- **🟠 P1 重点复测（要求再考，0/3）**：{join_or_none(l_b['orange'])}",
        f"- **🟡 P2 跨日巩固（2/3 与 1/3）**：{join_or_none(l_b['yellow_2'] + l_b['yellow_1'])}",
        f"- **🟢 已过关免考（3/3，严禁重复出题）**：{join_or_none(l_b['green'])}",
        "",
        "## 五、 Grok -> 云端大脑免中转直传通道（20:45 PT 归档时同步 POST）",
        f"- 除照常写入 Google Sheet《N3答题总账（Bot练习）》外，`0. JLPT 群` 每次归档可同步向 `{brief_obj['grok_cloud_ingest_url']}` 发送纯考点 JSON（严禁含任何姓名/邮箱等个人信息）：",
        '  `{"a":"n3g","r":[[表行号,"YYYY-MM-DD HH:MM","科目","题目ID","考点","对/错","还是要考/不用再考/快速题不问"]]}`',
        "- 云端 GitHub Actions 每 4 小时及每日清晨自动拉取该通道并合成次日《锵锵三人行》电台、50 道错题靶向新卷与 18 词闪卡，彻底免除本地电脑中转依赖。",
        "",
    ]
    md_txt = "\n".join(lines)
    assert_zero_pii_text(md_txt, "grok_daily_brief.md")
    with open(GROK_BRIEF_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_txt)


def main():
    import sys
    sync_only = ("--sync-only" in sys.argv) or ("--drain-only" in sys.argv)
    quiz_only = ("--quiz-only" in sys.argv)
    radio_only = ("--radio-only" in sys.argv)

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "sync_cloud_store.py")], check=True)

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    study_dt = (now_pt - datetime.timedelta(hours=5)).date()
    days_left = max(0, (EXAM_DATE - study_dt).days)
    state["days_left"] = days_left
    state["study_date"] = study_dt.strftime("%Y-%m-%d")
    state["updated_at"] = now_pt.strftime("%Y-%m-%d %H:%M PT")
    state["_baked_epoch"] = int(now_pt.timestamp())

    count = apply_practice_logs(state, study_dt.strftime("%Y%m%d"))
    recompute_summary(state)
    write_cloud_grok_brief(state)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    if quiz_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
    elif radio_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_daily_radio.py")], check=True)
    elif not sync_only:
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_neural_audio.py")], check=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_daily_radio.py")], check=True)

    subprocess.run([sys.executable, os.path.join(BASE_DIR, "build_html.py")], check=True)
    print(f"Brain algorithm v6 synced {count} records (sync_only={sync_only}, quiz_only={quiz_only}, radio_only={radio_only}); days_left={days_left}.")


if __name__ == "__main__":
    main()
