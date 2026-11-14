#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud Multi-Platform Progress Sync Engine (Zero-PII CRDT over ntfy + Git Snapshot)
- Real-time bidirectional sync across Phone Chrome, Phone PWA, Desktop Chrome, Desktop PWA,
  GitHub Actions, and Antigravity Cloud Brain.
- Pulls all snapshots from https://ntfy.sh/<ntfy_topic>/json?poll=1&since=all (CORS=*),
  merges via LWW-Element-Set CRDT with practice_log.jsonl & cloud_state_snapshot.json,
  appends newly answered records to practice_log.jsonl, and publishes unified state if changed.
"""
import glob
import hashlib
import json
import os
import secrets
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "cloud_sync_config.json")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "cloud_state_snapshot.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")

ORIGIN = "https://tango13ucla.github.io"
UA = "N3ZenSync/12.0"


def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http_req(url: str, method: str = "GET", body: bytes | None = None, headers: dict | None = None, timeout: float = 10.0):
    hdrs = {"User-Agent": UA, "Origin": ORIGIN}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        resp_hdrs = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, resp_hdrs, raw


def get_latest_plan_date() -> str:
    st_path = os.path.join(BASE_DIR, "n3_live_state.json")
    if os.path.exists(st_path):
        try:
            with open(st_path, encoding="utf-8") as f:
                ua = json.load(f).get("updated_at", "")
                if len(ua) >= 10 and ua[4] == "-" and ua[7] == "-":
                    return ua[:10]
        except Exception:
            pass
    plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
    if plans:
        try:
            with open(plans[-1], encoding="utf-8") as f:
                pdata = json.load(f)
                return pdata.get("plan_date") or pdata.get("date") or "2026-11-14"
        except Exception:
            pass
    return "2026-11-14"


def empty_crdt_state(plan_date: str) -> dict:
    return {
        "v": 12,
        "app": "n3-zen",
        "updatedAt": 0,
        "dates": {
            plan_date: {
                "resetAt": 0,
                "radioMaxSec": 0,
                "radioPos": [0, 0],
                "greenAt": {},
                "retestAt": {},
                "learning": {},
            }
        },
        "masteryOverrides": {},
        "records": [],
    }


def merge_day_bucket(dst: dict, src: dict) -> dict:
    out = {
        "resetAt": max(int(dst.get("resetAt") or 0), int(src.get("resetAt") or 0)),
        "radioMaxSec": max(int(dst.get("radioMaxSec") or 0), int(src.get("radioMaxSec") or 0)),
        "radioPos": list(dst.get("radioPos") or [0, 0]),
        "greenAt": dict(dst.get("greenAt") or {}),
        "retestAt": dict(dst.get("retestAt") or {}),
        "learning": dict(dst.get("learning") or {}),
    }
    sp = src.get("radioPos") or [0, 0]
    if len(sp) == 2 and int(sp[1] or 0) > int(out["radioPos"][1] or 0):
        out["radioPos"] = [int(sp[0] or 0), int(sp[1] or 0)]

    for pid, ts in (src.get("greenAt") or {}).items():
        ts_i = int(ts or 0)
        if ts_i > int(out["greenAt"].get(pid) or 0):
            out["greenAt"][pid] = ts_i

    for pid, ts in (src.get("retestAt") or {}).items():
        ts_i = int(ts or 0)
        if ts_i > int(out["retestAt"].get(pid) or 0):
            out["retestAt"][pid] = ts_i

    for pid, linfo in (src.get("learning") or {}).items():
        if not isinstance(linfo, list) or len(linfo) < 2:
            continue
        cur = out["learning"].get(pid) or [0, 0]
        out["learning"][pid] = [
            max(int(cur[0] or 0), int(linfo[0] or 0)),
            max(int(cur[1] or 0), int(linfo[1] or 0)),
        ]
    return out


def merge_crdt(a: dict, b: dict) -> dict:
    if not isinstance(b, dict) or b.get("app") != "n3-zen":
        return a
    out = {
        "v": 12,
        "app": "n3-zen",
        "updatedAt": max(int(a.get("updatedAt") or 0), int(b.get("updatedAt") or 0)),
        "dates": {},
        "masteryOverrides": dict(a.get("masteryOverrides") or {}),
        "records": [],
    }
    all_dates = set((a.get("dates") or {}).keys()) | set((b.get("dates") or {}).keys())
    for d in sorted(all_dates):
        da = (a.get("dates") or {}).get(d) or {}
        db = (b.get("dates") or {}).get(d) or {}
        out["dates"][d] = merge_day_bucket(da, db)

    for mk, mv in (b.get("masteryOverrides") or {}).items():
        cur = out["masteryOverrides"].get(mk)
        if isinstance(mv, list) and len(mv) == 2:
            if not isinstance(cur, list) or int(mv[1] or 0) >= int(cur[1] or 0):
                out["masteryOverrides"][mk] = [str(mv[0]), int(mv[1] or 0)]
        elif isinstance(mv, str) and not cur:
            out["masteryOverrides"][mk] = [mv, 1]

    seen = set()
    merged_recs = []
    for rec in list(a.get("records") or []) + list(b.get("records") or []):
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        key = (str(rec.get("ts", ""))[:19], str(rec.get("id", "")), str(rec.get("choice", "")))
        if key not in seen:
            seen.add(key)
            merged_recs.append(rec)
    merged_recs.sort(key=lambda r: str(r.get("ts", "")))
    out["records"] = merged_recs[-300:]
    return out


def unpack_compact_ntfy(pkt: dict) -> dict | None:
    if not isinstance(pkt, dict) or pkt.get("a") != "n3z":
        return None
    d = pkt.get("d")
    if not d:
        return None
    day = {
        "resetAt": int(pkt.get("r") or 0),
        "radioMaxSec": int(pkt.get("m") or 0),
        "radioPos": pkt.get("rp") if isinstance(pkt.get("rp"), list) else [0, 0],
        "greenAt": pkt.get("g") if isinstance(pkt.get("g"), dict) else {},
        "retestAt": pkt.get("t") if isinstance(pkt.get("t"), dict) else {},
        "learning": pkt.get("w") if isinstance(pkt.get("w"), dict) else {},
    }
    recs = []
    for item in pkt.get("l") or []:
        if isinstance(item, list) and len(item) >= 4:
            recs.append({
                "id": item[0],
                "point": item[1],
                "choice": item[2],
                "correct": str(bool(item[3])).lower(),
                "ask_again": "false",
                "ts": item[4] if len(item) >= 5 else "",
            })
    return {
        "v": 12,
        "app": "n3-zen",
        "updatedAt": int(pkt.get("u") or 0),
        "dates": {d: day},
        "masteryOverrides": pkt.get("o") if isinstance(pkt.get("o"), dict) else {},
        "records": recs,
    }


def pack_compact_ntfy(state: dict, plan_date: str) -> dict:
    day = (state.get("dates") or {}).get(plan_date) or {}
    compact_recs = []
    for r in (state.get("records") or [])[-15:]:
        ok = 1 if str(r.get("correct", "")).lower() == "true" else 0
        compact_recs.append([
            r.get("id", ""),
            r.get("point", ""),
            r.get("choice", ""),
            ok,
            r.get("ts", ""),
        ])
    # Keep most recent 40 mastery overrides in live packet so < 3.6KB inline limit is guaranteed
    ov_items = sorted(
        (state.get("masteryOverrides") or {}).items(),
        key=lambda kv: int(kv[1][1]) if isinstance(kv[1], list) and len(kv[1]) == 2 else 0,
        reverse=True,
    )[:40]
    pkt = {
        "a": "n3z",
        "u": int(state.get("updatedAt") or int(time.time())),
        "d": plan_date,
        "r": int(day.get("resetAt") or 0),
        "m": int(day.get("radioMaxSec") or 0),
        "rp": day.get("radioPos") or [0, 0],
        "g": day.get("greenAt") or {},
        "t": day.get("retestAt") or {},
        "w": day.get("learning") or {},
        "o": dict(ov_items),
        "l": compact_recs,
    }
    raw = json.dumps(pkt, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > 3600:
        pkt["o"] = {}
        pkt["l"] = compact_recs[-6:]
    return pkt


def canonical_fingerprint(pkt: dict) -> str:
    clone = dict(pkt)
    clone.pop("u", None)
    return hashlib.sha1(json.dumps(clone, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def seed_from_practice_log(state: dict, plan_date: str) -> tuple[dict, list[dict]]:
    existing_lines = []
    if not os.path.exists(LOG_PATH):
        return state, existing_lines

    variant_parent = {}
    try:
        from adaptive_bank import VARIANT_CARDS
        for vc in VARIANT_CARDS:
            variant_parent[vc["id"]] = vc["variant_of"]
    except Exception:
        pass

    day = state["dates"].setdefault(
        plan_date,
        {"resetAt": 0, "radioMaxSec": 0, "radioPos": [0, 0], "greenAt": {}, "retestAt": {}, "learning": {}},
    )
    tag = plan_date.replace("-", "")
    idx = 0
    with open(LOG_PATH, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            existing_lines.append(rec)
            idx += 1
            raw_qid = str(rec.get("id", ""))
            if not raw_qid or raw_qid.endswith("-twin"):
                continue
            pid = variant_parent.get(raw_qid, raw_qid)
            if tag in pid or pid.startswith("N3-"):
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                ts_seed = 10 + idx
                if ok and not again:
                    if ts_seed > int(day["greenAt"].get(pid) or 0):
                        day["greenAt"][pid] = ts_seed
                else:
                    if ts_seed > int(day["retestAt"].get(pid) or 0):
                        day["retestAt"][pid] = ts_seed
                    cur_l = day["learning"].get(pid) or [0, 0]
                    day["learning"][pid] = [max(int(cur_l[0]), 1), int(cur_l[1])]
    return state, existing_lines


def main():
    plan_date = get_latest_plan_date()
    cfg = load_json(CONFIG_PATH, {})
    if not cfg.get("ntfy_topic"):
        cfg["ntfy_topic"] = "n3zen_" + secrets.token_hex(14)

    state = load_json(SNAPSHOT_PATH, empty_crdt_state(plan_date))
    if state.get("app") != "n3-zen":
        state = empty_crdt_state(plan_date)

    state, existing_log = seed_from_practice_log(state, plan_date)

    last_remote_fp = ""
    ntfy_poll_url = f"https://ntfy.sh/{cfg['ntfy_topic']}/json?poll=1&since=all"
    try:
        st, hdrs, raw = http_req(ntfy_poll_url, method="GET")
        if st == 200:
            cnt = 0
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("event") == "message" and ev.get("message"):
                        raw_pkt = json.loads(ev["message"])
                        unpacked = unpack_compact_ntfy(raw_pkt)
                        if unpacked:
                            state = merge_crdt(state, unpacked)
                            last_remote_fp = canonical_fingerprint(raw_pkt)
                            cnt += 1
                except Exception:
                    continue
            print(f"[sync] Pulled ntfy ({cnt} snapshots, CORS={hdrs.get('access-control-allow-origin')})")
    except Exception as e:
        print(f"[sync] ntfy pull skipped: {e}")

    # Append any newly synced answer records from Phone/Desktop into practice_log.jsonl
    existing_keys = {
        (str(r.get("ts", ""))[:19], str(r.get("id", "")), str(r.get("choice", "")))
        for r in existing_log
    }
    new_recs = []
    for r in state.get("records") or []:
        k = (str(r.get("ts", ""))[:19], str(r.get("id", "")), str(r.get("choice", "")))
        if r.get("id") and r.get("ts") and k not in existing_keys:
            existing_keys.add(k)
            new_recs.append(r)
    if new_recs:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            for r in new_recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[sync] Appended {len(new_recs)} cloud answer records to practice_log.jsonl")

    if not state.get("updatedAt"):
        state["updatedAt"] = int(time.time())

    compact_pkt = pack_compact_ntfy(state, plan_date)
    cur_fp = canonical_fingerprint(compact_pkt)
    if cur_fp != last_remote_fp:
        try:
            pkt_bytes = json.dumps(compact_pkt, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            st, hdrs, _ = http_req(
                f"https://ntfy.sh/{cfg['ntfy_topic']}",
                method="POST",
                body=pkt_bytes,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            print(f"[sync] Published unified snapshot ({len(pkt_bytes)}B) HTTP {st} (CORS={hdrs.get('access-control-allow-origin')})")
        except Exception as e:
            print(f"[sync] ntfy publish skipped: {e}")
    else:
        print("[sync] Cloud bus already up-to-date (0 duplicate publish)")

    save_json(CONFIG_PATH, cfg)
    save_json(SNAPSHOT_PATH, state)

    day_summary = state.get("dates", {}).get(plan_date) or {}
    reset_at = int(day_summary.get("resetAt") or 0)
    effective_greens = [
        pid
        for pid, gts in (day_summary.get("greenAt") or {}).items()
        if int(gts or 0) > reset_at and int(gts or 0) >= int((day_summary.get("retestAt") or {}).get(pid) or 0)
    ]
    print(f"[sync] Ready for {plan_date}: effective_green={len(effective_greens)}, records_new={len(new_recs)}")


if __name__ == "__main__":
    main()
