#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud Multi-Platform Progress Sync Engine (Zero-PII CRDT over ntfy + Git Snapshot, v15)
- Real-time bidirectional sync across Phone Chrome, Phone PWA, Desktop Chrome, Desktop PWA,
  GitHub Actions, Grok Cloud Bridge (`grok_ntfy_topic`), and Antigravity Cloud Brain.
- Pulls snapshots from https://ntfy.sh/<ntfy_topic>/json?poll=1&since=all (CORS=*),
  merges via LWW-Element-Set CRDT with practice_log.jsonl & cloud_state_snapshot.json,
  pulls zero-PII Grok practice batches from https://ntfy.sh/<grok_ntfy_topic>/json?poll=1&since=all,
  appends newly answered records to practice_log.jsonl, and publishes unified state (<3750B).
"""
from __future__ import annotations
import datetime
import glob
import hashlib
import json
import os
import secrets
import time
import urllib.request
from zoneinfo import ZoneInfo

from grok_point_resolver import (
    assert_zero_pii_text,
    build_lookup_sets,
    resolve_grok_points,
    to_pt_iso,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "cloud_sync_config.json")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "cloud_state_snapshot.json")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")

ORIGIN = "https://tango13ucla.github.io"
UA = "N3ZenSync/15.0"
PT_TZ = ZoneInfo("America/Los_Angeles")

TRUE_GREEN_EPOCH = 1794761500
MIN_REAL_TS = 1_700_000_000
BYTE_LIMIT = 3750


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


def _parse_iso_dt(ts_iso: str) -> datetime.datetime | None:
    if not ts_iso:
        return None
    try:
        s = str(ts_iso).strip().replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def _iso_to_study_date(ts_iso: str) -> str:
    dt = _parse_iso_dt(ts_iso)
    if dt is None:
        return ""
    dt_pt = dt.astimezone(PT_TZ) - datetime.timedelta(hours=4)
    return dt_pt.strftime("%Y-%m-%d")


def _iso_to_unix_sec(ts_iso: str) -> int:
    dt = _parse_iso_dt(ts_iso)
    if dt is None:
        return 0
    return int(dt.timestamp())


def get_latest_plan_date() -> str:
    rm_path = os.path.join(BASE_DIR, "audio", "daily_radio_meta.json")
    candidates = []
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                sd_obj = json.load(f)
                sd = str(sd_obj.get("study_date") or "").strip()
                if len(sd) == 10 and sd[4] == "-" and sd[7] == "-":
                    candidates.append(sd)
                ua = str(sd_obj.get("updated_at") or "").strip()
                if len(ua) >= 10 and ua[4] == "-" and ua[7] == "-":
                    candidates.append(ua[:10])
        except Exception:
            pass
    if os.path.exists(rm_path):
        try:
            with open(rm_path, encoding="utf-8") as f:
                rd = str(json.load(f).get("date") or "").strip()
                if len(rd) == 10 and rd[4] == "-" and rd[7] == "-":
                    candidates.append(rd)
        except Exception:
            pass
    if candidates:
        return sorted(candidates)[-1]
    plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
    if plans:
        try:
            with open(plans[-1], encoding="utf-8") as f:
                pdata = json.load(f)
                return pdata.get("plan_date") or pdata.get("date") or "2026-11-15"
        except Exception:
            pass
    return "2026-11-15"


def get_baked_epoch() -> int:
    st_obj = load_json(STATE_PATH, {})
    return int(st_obj.get("_baked_epoch") or 0)


def b36(n) -> str:
    n = int(n or 0)
    if n <= 0:
        return ""
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


def ub36(txt: str) -> int:
    try:
        return int(txt, 36) if txt else 0
    except Exception:
        return 0


def js_join(vals) -> str:
    """String(array) in JavaScript: comma-joined, null/None -> empty."""
    return ",".join("" if v is None else str(v) for v in vals)


def js_num(x) -> str:
    try:
        return "%g" % float(x)
    except Exception:
        return str(x)


def sched_wins(new, cur) -> bool:
    if not isinstance(new, list) or len(new) < 5:
        return False
    if not isinstance(cur, list) or len(cur) < 5:
        return int(new[4] or 0) > 0
    nl, cl = int(new[4] or 0), int(cur[4] or 0)
    if nl != cl:
        return nl > cl
    return js_join(new[:4]) > js_join(cur[:4])


def cursor_wins(new, cur) -> bool:
    if not isinstance(new, list) or len(new) < 5:
        return False
    if not isinstance(cur, list) or len(cur) < 5:
        return int(new[4] or 0) > 0
    nt, ctm = int(new[4] or 0), int(cur[4] or 0)
    if nt != ctm:
        return nt > ctm
    return js_join(new[:4]) > js_join(cur[:4])


def speeds_win(new, cur) -> bool:
    if not isinstance(new, list) or len(new) < 3:
        return False
    if not isinstance(cur, list) or len(cur) < 3:
        return int(new[2] or 0) > 0
    nt, ctm = int(new[2] or 0), int(cur[2] or 0)
    if nt != ctm:
        return nt > ctm
    return f"{js_num(new[0])}|{js_num(new[1])}" > f"{js_num(cur[0])}|{js_num(cur[1])}"


def enc_pid(pid: str, tag: str) -> str:
    return str(pid).replace(f"-{tag}-", "~", 1)


def dec_pid(txt: str, tag: str) -> str:
    return str(txt).replace("~", f"-{tag}-", 1)


def empty_crdt_state(plan_date: str) -> dict:
    return {
        "v": 15,
        "app": "n3-zen",
        "updatedAt": 0,
        "dates": {
            plan_date: {
                "resetAt": 0,
                "radioMaxSec": 0,
                "radioPos": [0, 0],
                "radioSig": "",
                "greenAt": {},
                "retestAt": {},
                "learning": {},
            }
        },
        "masteryOverrides": {},
        "grammarAudit": {},
        "records": [],
    }


def merge_day_bucket(dst: dict, src: dict) -> dict:
    out = {
        "resetAt": max(int(dst.get("resetAt") or 0), int(src.get("resetAt") or 0)),
        "radioMaxSec": max(int(dst.get("radioMaxSec") or 0), int(src.get("radioMaxSec") or 0)),
        "radioPos": list(dst.get("radioPos") or [0, 0]),
        "radioSig": str(dst.get("radioSig") or ""),
        "greenAt": {
            k: int(v)
            for k, v in (dst.get("greenAt") or {}).items()
            if int(v or 0) >= MIN_REAL_TS
        },
        "retestAt": {
            k: int(v)
            for k, v in (dst.get("retestAt") or {}).items()
            if int(v or 0) >= MIN_REAL_TS
        },
        "learning": dict(dst.get("learning") or {}),
    }
    sp = src.get("radioPos") or [0, 0]
    if len(sp) == 2:
        s_ts, d_ts = int(sp[1] or 0), int(out["radioPos"][1] or 0)
        if s_ts > d_ts or (s_ts == d_ts and int(sp[0] or 0) > int(out["radioPos"][0] or 0)):
            out["radioPos"] = [int(sp[0] or 0), int(sp[1] or 0)]
            out["radioSig"] = str(src.get("radioSig") or "")

    out["sched"] = dict(dst.get("sched") or {})
    for pid, tup in (src.get("sched") or {}).items():
        if sched_wins(tup, out["sched"].get(pid)):
            out["sched"][pid] = [int(x or 0) for x in tup[:5]]
    if cursor_wins(src.get("cursor"), dst.get("cursor")):
        c = src.get("cursor")
        out["cursor"] = [str(c[0] or ""), int(c[1] or 0), str(c[2] or ""), str(c[3] or ""), int(c[4] or 0)]
    elif dst.get("cursor"):
        out["cursor"] = dst.get("cursor")
    if speeds_win(src.get("speeds"), dst.get("speeds")):
        v = src.get("speeds")
        out["speeds"] = [float(v[0] or 1), float(v[1] or 1), int(v[2] or 0)]
    elif dst.get("speeds"):
        out["speeds"] = dst.get("speeds")

    for pid, ts in (src.get("greenAt") or {}).items():
        ts_i = int(ts or 0)
        if ts_i >= MIN_REAL_TS and ts_i > int(out["greenAt"].get(pid) or 0):
            out["greenAt"][pid] = ts_i

    for pid, ts in (src.get("retestAt") or {}).items():
        ts_i = int(ts or 0)
        if ts_i >= MIN_REAL_TS and ts_i > int(out["retestAt"].get(pid) or 0):
            out["retestAt"][pid] = ts_i

    for pid, linfo in (src.get("learning") or {}).items():
        if not isinstance(linfo, list) or len(linfo) < 2:
            continue
        cur = out["learning"].get(pid) or [0, 0]
        out["learning"][pid] = [
            max(int(cur[0] or 0), int(linfo[0] or 0)),
            max(int(cur[1] or 0), int(linfo[1] or 0)),
        ]
    # Clean orphaned [1, 0] synthetic learning stubs that have neither real retestAt nor real sched stamp
    for pid in list(out["learning"].keys()):
        sch_tup = out["sched"].get(pid)
        has_real_sched = isinstance(sch_tup, list) and len(sch_tup) >= 5 and int(sch_tup[4] or 0) > 0
        if pid not in out["retestAt"] and not has_real_sched:
            out["learning"].pop(pid, None)

    tw = []
    seen_tw = set()
    for w in list(dst.get("tappedWords") or []) + list(src.get("tappedWords") or []):
        ws = str(w or "").strip()
        if ws and ws not in seen_tw:
            seen_tw.add(ws)
            tw.append(ws)
    if tw:
        out["tappedWords"] = tw[-80:]

    fp_a = dst.get("flashProg") if isinstance(dst.get("flashProg"), list) else [0, 0, 0, 0]
    fp_b = src.get("flashProg") if isinstance(src.get("flashProg"), list) else [0, 0, 0, 0]
    fp_a = [int(x or 0) for x in (fp_a + [0, 0, 0, 0])[:4]]
    fp_b = [int(x or 0) for x in (fp_b + [0, 0, 0, 0])[:4]]
    fp_seen = max(fp_a[0], fp_b[0])
    fp_done = max(fp_a[2], fp_b[2])
    fp_upd = max(fp_a[3], fp_b[3])
    fp_tgt = fp_b[1] if fp_b[3] >= fp_a[3] and fp_b[1] > 0 else (fp_a[1] or fp_b[1])
    if fp_seen > 0 or fp_done > 0:
        out["flashProg"] = [fp_seen, max(fp_seen, fp_tgt), fp_done, fp_upd]

    gp_a = dst.get("gaProg") if isinstance(dst.get("gaProg"), list) else [0, 0, 0, 0]
    gp_b = src.get("gaProg") if isinstance(src.get("gaProg"), list) else [0, 0, 0, 0]
    gp_a = [int(x or 0) for x in (gp_a + [0, 0, 0, 0])[:4]]
    gp_b = [int(x or 0) for x in (gp_b + [0, 0, 0, 0])[:4]]
    gp_seen = max(gp_a[0], gp_b[0])
    gp_done = max(gp_a[2], gp_b[2])
    gp_upd = max(gp_a[3], gp_b[3])
    gp_tgt = gp_b[1] if gp_b[3] >= gp_a[3] and gp_b[1] > 0 else (gp_a[1] or gp_b[1])
    if gp_seen > 0 or gp_done > 0:
        out["gaProg"] = [gp_seen, max(gp_seen, gp_tgt), gp_done, gp_upd]
    return out


def merge_crdt(a: dict, b: dict) -> dict:
    if not isinstance(b, dict) or b.get("app") != "n3-zen":
        return a
    clean_a_ov = {
        mk: mv
        for mk, mv in (a.get("masteryOverrides") or {}).items()
        if isinstance(mv, list) and len(mv) == 2 and int(mv[1] or 0) >= TRUE_GREEN_EPOCH
    }
    clean_a_ga = {
        gk: [int(gv[0] or 0), int(gv[1] or 0), str(gv[2] if len(gv) >= 3 else "")]
        for gk, gv in (a.get("grammarAudit") or {}).items()
        if isinstance(gv, list) and len(gv) >= 2 and int(gv[1] or 0) >= MIN_REAL_TS
    }
    out = {
        "v": 15,
        "app": "n3-zen",
        "updatedAt": max(int(a.get("updatedAt") or 0), int(b.get("updatedAt") or 0)),
        "dates": {},
        "masteryOverrides": clean_a_ov,
        "grammarAudit": clean_a_ga,
        "wordLookups": dict(a.get("wordLookups") or {}),
        "records": [],
    }
    for surf, lobj in (b.get("wordLookups") or {}).items():
        if not isinstance(lobj, dict) or not surf:
            continue
        cur_lk = out["wordLookups"].get(surf) or {"count": 0, "last_ts": "", "contexts": []}
        ctxs = list(dict.fromkeys(list(cur_lk.get("contexts") or []) + list(lobj.get("contexts") or [])))[-12:]
        out["wordLookups"][surf] = {
            "count": max(int(cur_lk.get("count") or 0), int(lobj.get("count") or 0)),
            "last_ts": max(str(cur_lk.get("last_ts") or ""), str(lobj.get("last_ts") or "")),
            "contexts": ctxs,
        }
    all_dates = set((a.get("dates") or {}).keys()) | set((b.get("dates") or {}).keys())
    for d in sorted(all_dates):
        da = (a.get("dates") or {}).get(d) or {}
        db = (b.get("dates") or {}).get(d) or {}
        out["dates"][d] = merge_day_bucket(da, db)

    for mk, mv in (b.get("masteryOverrides") or {}).items():
        if isinstance(mv, list) and len(mv) == 2:
            ts_i = int(mv[1] or 0)
            if ts_i < TRUE_GREEN_EPOCH:
                continue
            cur = out["masteryOverrides"].get(mk)
            if not isinstance(cur, list) or ts_i >= int(cur[1] or 0):
                out["masteryOverrides"][mk] = [str(mv[0]), ts_i]

    for gk, gv in (b.get("grammarAudit") or {}).items():
        if isinstance(gv, list) and len(gv) >= 2:
            code_i = int(gv[0] or 0)
            ts_i = int(gv[1] or 0)
            day_s = str(gv[2] if len(gv) >= 3 else "")
            if ts_i < MIN_REAL_TS or code_i not in (0, 1, 2, 3, 4):
                continue
            cur = out["grammarAudit"].get(gk)
            if not isinstance(cur, list) or ts_i > int(cur[1] or 0) or (ts_i == int(cur[1] or 0) and code_i >= int(cur[0] or 0)):
                out["grammarAudit"][gk] = [code_i, ts_i, day_s or (cur[2] if isinstance(cur, list) and len(cur) >= 3 else "")]

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
    raw_g = pkt.get("g") if isinstance(pkt.get("g"), dict) else {}
    raw_t = pkt.get("t") if isinstance(pkt.get("t"), dict) else {}
    day = {
        "resetAt": int(pkt.get("r") or 0),
        "radioMaxSec": int(pkt.get("m") or 0),
        "radioPos": pkt.get("rp") if isinstance(pkt.get("rp"), list) else [0, 0],
        "radioSig": str(pkt.get("rsig") or "")[:8],
        "greenAt": {k: int(v) for k, v in raw_g.items() if int(v or 0) >= MIN_REAL_TS},
        "retestAt": {k: int(v) for k, v in raw_t.items() if int(v or 0) >= MIN_REAL_TS},
        "learning": pkt.get("w") if isinstance(pkt.get("w"), dict) else {},
    }
    if isinstance(pkt.get("z"), str):
        tag = str(d).replace("-", "")
        g, t, w, sch = {}, {}, {}, {}
        for ent in pkt["z"].split(";"):
            if ":" not in ent:
                continue
            raw_id, rest = ent.split(":", 1)
            pid = dec_pid(raw_id, tag)
            f = (rest.split(".") + [""] * 7)[:7]
            gv = ub36(f[0])
            tv = ub36(f[1])
            if gv >= MIN_REAL_TS:
                g[pid] = gv
            if tv >= MIN_REAL_TS:
                t[pid] = tv
            tup = [ub36(f[2]), int(f[3] or 0) if f[3].isdigit() else 0, ub36(f[4]), ub36(f[5]), ub36(f[6])]
            if tup[4] > 0:
                sch[pid] = tup
            if (tup[2] or tup[3]) and (tv >= MIN_REAL_TS or tup[4] > 0):
                w[pid] = [tup[2], tup[3]]
        day["greenAt"], day["retestAt"], day["learning"], day["sched"] = g, t, w, sch
    if isinstance(pkt.get("c"), list) and len(pkt["c"]) >= 5:
        day["cursor"] = pkt["c"]
    if isinstance(pkt.get("sp"), list) and len(pkt["sp"]) >= 3:
        day["speeds"] = pkt["sp"]
    if isinstance(pkt.get("tw"), list):
        day["tappedWords"] = [str(x) for x in pkt["tw"] if x][:80]
    pkt_ver = int(pkt.get("v") or 0)
    if pkt_ver >= 14 and isinstance(pkt.get("fp"), list) and len(pkt["fp"]) >= 3:
        fp = pkt["fp"]
        day["flashProg"] = [
            int(fp[0] or 0),
            int(fp[1] or 0),
            int(fp[2] or 0),
            int(fp[3] if len(fp) >= 4 and fp[3] else (pkt.get("u") or 0)),
        ]
    if pkt_ver >= 15 and isinstance(pkt.get("gp"), list) and len(pkt["gp"]) >= 3:
        gp = pkt["gp"]
        day["gaProg"] = [
            int(gp[0] or 0),
            int(gp[1] or 0),
            int(gp[2] or 0),
            int(gp[3] if len(gp) >= 4 and gp[3] else (pkt.get("u") or 0)),
        ]
    recs = []
    for item in pkt.get("l") or []:
        if isinstance(item, list) and len(item) >= 4:
            ts_item = item[4] if len(item) >= 5 else ""
            ts_s = _iso_to_unix_sec(str(ts_item))
            rid_item = str(item[0] or "")
            ok_item = bool(item[3])
            if 1795016635 <= ts_s <= 1795016690:
                continue
            if rid_item == "N3-G38" and not ok_item and (
                1795677955 <= ts_s <= 1795677968
                or 1795678230 <= ts_s <= 1795678242
                or 1795678389 <= ts_s <= 1795678402
                or 1795679720 <= ts_s <= 1795679736
            ):
                continue
            if rid_item.startswith("MOCK:") and not ok_item and 1795678878 <= ts_s <= 1795678883:
                continue
            recs.append({
                "id": item[0],
                "point": item[1],
                "choice": item[2],
                "correct": str(ok_item).lower(),
                "ask_again": "false",
                "ts": ts_item,
            })
    raw_ov_map = pkt.get("o") if (pkt_ver >= 14 and isinstance(pkt.get("o"), dict)) else {}
    clean_ov_map = {
        ok_k: ok_v
        for ok_k, ok_v in raw_ov_map.items()
        if not (isinstance(ok_v, list) and len(ok_v) >= 2 and 1795016635 <= int(ok_v[1] or 0) <= 1795016690)
    }
    raw_ga_map = pkt.get("ga") if (pkt_ver >= 15 and isinstance(pkt.get("ga"), dict)) else {}
    clean_ga_map = {}
    day_tag_compact = str(d).replace("-", "")
    for gk, gv in raw_ga_map.items():
        if isinstance(gv, list) and len(gv) >= 2:
            code_i = int(gv[0] or 0)
            ts_i = int(gv[1] or 0)
            ds = str(gv[2] if len(gv) >= 3 and gv[2] else day_tag_compact)
            if ts_i >= MIN_REAL_TS and code_i in (0, 1, 2, 3, 4):
                clean_ga_map[str(gk)] = [code_i, ts_i, ds]
    if d == "2026-11-17" and int(day["retestAt"].get("N3-L11") or 0) in range(1795016635, 1795016691):
        day["retestAt"].pop("N3-L11", None)
        day["learning"].pop("N3-L11", None)
        if isinstance(day.get("sched"), dict):
            day["sched"].pop("N3-L11", None)
    if d == "2026-11-25":
        r_g38 = int(day["retestAt"].get("N3-G38") or 0)
        if (
            1795677955 <= r_g38 <= 1795677968
            or 1795678230 <= r_g38 <= 1795678242
            or 1795678389 <= r_g38 <= 1795678402
            or 1795679720 <= r_g38 <= 1795679736
        ):
            day["retestAt"].pop("N3-G38", None)
            day["learning"].pop("N3-G38", None)
            if isinstance(day.get("sched"), dict):
                day["sched"].pop("N3-G38", None)
            cur_c = day.get("cursor")
            if isinstance(cur_c, list) and cur_c and cur_c[0] == "N3-G38":
                day.pop("cursor", None)
    return {
        "v": 15,
        "app": "n3-zen",
        "updatedAt": int(pkt.get("u") or 0),
        "dates": {d: day},
        "masteryOverrides": clean_ov_map,
        "grammarAudit": clean_ga_map,
        "records": recs,
    }


def pack_compact_ntfy(state: dict, plan_date: str, baked_epoch: int = 0) -> dict:
    day = (state.get("dates") or {}).get(plan_date) or {}
    tag = plan_date.replace("-", "")
    g = {k: int(v) for k, v in (day.get("greenAt") or {}).items() if int(v or 0) >= MIN_REAL_TS}
    t = {k: int(v) for k, v in (day.get("retestAt") or {}).items() if int(v or 0) >= MIN_REAL_TS}
    sch = day.get("sched") or {}
    lrn = day.get("learning") or {}
    parts = []
    for pid in sorted(set(g) | set(t) | set(sch) | set(lrn)):
        tup = sch.get(pid)
        if not (isinstance(tup, list) and len(tup) >= 5):
            lw = lrn.get(pid) or [0, 0]
            tup = [0, 0, int(lw[0] or 0), int(lw[1] or 0), 0]
        gv, tv = int(g.get(pid) or 0), int(t.get(pid) or 0)
        if not gv and not tv and not int(tup[4] or 0):
            continue
        flags = int(tup[1] or 0)
        parts.append(
            f"{enc_pid(pid, tag)}:{b36(gv)}.{b36(tv)}.{b36(tup[0])}.{flags if flags else ''}."
            f"{b36(tup[2])}.{b36(tup[3])}.{b36(tup[4])}"
        )
    pkt = {
        "a": "n3z",
        "v": 15,
        "u": int(state.get("updatedAt") or int(time.time())),
        "d": plan_date,
        "r": int(day.get("resetAt") or 0),
        "m": int(day.get("radioMaxSec") or 0),
        "rp": day.get("radioPos") or [0, 0],
        "z": ";".join(parts),
        "o": {},
        "l": [],
    }
    if day.get("radioSig"):
        pkt["rsig"] = str(day["radioSig"])[:8]
    if isinstance(day.get("cursor"), list):
        pkt["c"] = day["cursor"]
    if isinstance(day.get("speeds"), list):
        pkt["sp"] = day["speeds"]
    if isinstance(day.get("flashProg"), list):
        fp = [int(x or 0) for x in (day["flashProg"] + [0, 0, 0, 0])[:4]]
        if fp[0] > 0 or fp[2] > 0:
            pkt["fp"] = fp
    if isinstance(day.get("gaProg"), list):
        gp = [int(x or 0) for x in (day["gaProg"] + [0, 0, 0, 0])[:4]]
        if gp[0] > 0 or gp[2] > 0:
            pkt["gp"] = gp

    def size(obj) -> int:
        return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    cur = size(pkt)
    if day.get("tappedWords"):
        tw_slice = list(day["tappedWords"])[-25:]
        tw_add = size(tw_slice) + 7
        if cur + tw_add <= BYTE_LIMIT - 600:
            pkt["tw"] = tw_slice
            cur += tw_add

    for r in reversed((state.get("records") or [])[-12:]):
        ok = 1 if str(r.get("correct", "")).lower() == "true" else 0
        item = [r.get("id", ""), r.get("point", ""), r.get("choice", ""), ok, r.get("ts", "")]
        add = size(item) + 1
        if cur + add > BYTE_LIMIT - 500:
            break
        pkt["l"].insert(0, item)
        cur += add

    # Prioritize delta overrides & grammar audit deltas newer than baked_epoch - 7200
    delta_cutoff = max(TRUE_GREEN_EPOCH, int(baked_epoch or 0) - 7200)
    raw_ga = [
        (k, v)
        for k, v in (state.get("grammarAudit") or {}).items()
        if isinstance(v, list) and len(v) >= 2 and int(v[1] or 0) >= delta_cutoff
    ]
    if raw_ga:
        pkt["ga"] = {}
        cur += 7
        for gk, gv in sorted(raw_ga, key=lambda kv: int(kv[1][1]), reverse=True):
            val = [int(gv[0] or 0), int(gv[1] or 0)]
            add = size({gk: val}) - 1
            if cur + add > BYTE_LIMIT - 250:
                break
            pkt["ga"][gk] = val
            cur += add
        if not pkt["ga"]:
            pkt.pop("ga", None)

    raw_ov = [
        (k, v)
        for k, v in (state.get("masteryOverrides") or {}).items()
        if isinstance(v, list) and len(v) == 2 and int(v[1] or 0) >= TRUE_GREEN_EPOCH
    ]
    delta_ov = sorted([kv for kv in raw_ov if int(kv[1][1]) >= delta_cutoff], key=lambda kv: int(kv[1][1]), reverse=True)
    older_ov = sorted([kv for kv in raw_ov if int(kv[1][1]) < delta_cutoff], key=lambda kv: int(kv[1][1]), reverse=True)
    for k, v in delta_ov + older_ov:
        add = size({k: v}) - 1
        if cur + add > BYTE_LIMIT:
            break
        pkt["o"][k] = v
        cur += add
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
    # Purge any legacy synthetic < MIN_REAL_TS seeds already sitting in day
    day["greenAt"] = {k: int(v) for k, v in (day.get("greenAt") or {}).items() if int(v or 0) >= MIN_REAL_TS}
    day["retestAt"] = {k: int(v) for k, v in (day.get("retestAt") or {}).items() if int(v or 0) >= MIN_REAL_TS}

    tag = plan_date.replace("-", "")
    lk_events: dict[str, set[str]] = {}
    listen_pass_streak: dict[str, int] = {}
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
            raw_qid = str(rec.get("id", ""))
            if raw_qid.startswith("LK:"):
                surf = raw_qid[3:].strip() or str(rec.get("choice") or "").strip()
                ts_lk = str(rec.get("ts") or "")
                ctx_lk = str(rec.get("point") or "").strip()
                if surf:
                    ev_set = lk_events.setdefault(surf, set())
                    ev_set.add(ts_lk or f"row_{len(ev_set)}")
                    cur_lk = state.setdefault("wordLookups", {}).get(surf) or {"count": 0, "last_ts": "", "contexts": []}
                    ctxs = list(cur_lk.get("contexts") or [])
                    if ctx_lk and ctx_lk not in ctxs:
                        ctxs.append(ctx_lk)
                    state["wordLookups"][surf] = {
                        "count": max(int(cur_lk.get("count") or 0), len(ev_set)),
                        "last_ts": max(str(cur_lk.get("last_ts") or ""), ts_lk),
                        "contexts": ctxs[-12:],
                    }
                continue
            if raw_qid.startswith("GA-"):
                gid = raw_qid[3:].strip()
                ts_ga = _iso_to_unix_sec(str(rec.get("ts") or ""))
                ch_ga = str(rec.get("choice") or "")
                ga_code_map = {"盘点:陌生": 1, "盘点:易混": 2, "盘点:看懂": 3, "盘点:本能": 4, "盘点:不熟": 1, "盘点:模糊": 2, "盘点:稳熟": 4}
                code_ga = ga_code_map.get(ch_ga, 0)
                if gid and ts_ga >= MIN_REAL_TS and code_ga in (1, 2, 3, 4):
                    ga_map = state.setdefault("grammarAudit", {})
                    cur_ga = ga_map.get(gid)
                    if not isinstance(cur_ga, list) or ts_ga >= int(cur_ga[1] or 0):
                        ga_map[gid] = [code_ga, ts_ga, _iso_to_study_date(str(rec.get("ts") or "")).replace("-", "")]
                continue
            if str(rec.get("source") or "") == "grok":
                continue
            if (
                not raw_qid
                or raw_qid.startswith("GROK-")
                or raw_qid.endswith("-twin")
                or raw_qid.startswith("FLASH-")
                or raw_qid.startswith("VC-")
            ):
                continue
            ts_str = str(rec.get("ts") or "")
            rec_sdate = _iso_to_study_date(ts_str)
            ts_sec = _iso_to_unix_sec(ts_str)
            if rec_sdate != plan_date or ts_sec < MIN_REAL_TS:
                continue
            pid = variant_parent.get(raw_qid, raw_qid)
            is_listen_pid = ("-L" in pid or pid.startswith("Q-20261114-00"))
            if tag in pid or pid.startswith("N3-") or "-20261114-" in pid:
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                if ok and not again:
                    had_fail_today = int(day["retestAt"].get(pid) or 0) >= MIN_REAL_TS
                    if is_listen_pid and had_fail_today:
                        listen_pass_streak[pid] = listen_pass_streak.get(pid, 0) + 1
                        if listen_pass_streak[pid] >= 2 and ts_sec > int(day["greenAt"].get(pid) or 0):
                            day["greenAt"][pid] = ts_sec
                    else:
                        if ts_sec > int(day["greenAt"].get(pid) or 0):
                            day["greenAt"][pid] = ts_sec
                else:
                    listen_pass_streak[pid] = 0
                    if ts_sec > int(day["retestAt"].get(pid) or 0):
                        day["retestAt"][pid] = ts_sec
                    cur_l = day["learning"].get(pid) or [0, 0]
                    day["learning"][pid] = [max(int(cur_l[0]), 1), int(cur_l[1])]
    return state, existing_lines


def pull_grok_ntfy_bus(cfg: dict, existing_log: list[dict]) -> list[dict]:
    """
    Cloud-Native Zero-PII Grok -> Tutor Bridge:
    Polls https://ntfy.sh/<grok_ntfy_topic>/json?poll=1&since=all so GitHub Actions
    automatically ingests Grok daily/realtime practice records without needing Mac mini!
    Accepted payload formats:
      1) Compact batch: {"a": "n3g", "r": [[srow, ts_pt, subj, qid, pt_raw, res_or_ok, again_raw], ...]}
      2) Direct record(s): {"a": "n3g", "records": [{"id": "GROK-...", "point": "...", ...}]}
    """
    topic = str(cfg.get("grok_ntfy_topic") or "").strip()
    if not topic:
        return []
    live_state = load_json(STATE_PATH, {})
    lookups = build_lookup_sets(live_state)
    existing_ids = {str(r.get("id") or "").strip() for r in existing_log if r.get("id")}
    added: list[dict] = []
    minute_counter: dict[str, int] = {}

    url = f"https://ntfy.sh/{topic}/json?poll=1&since=all"
    try:
        st, _, raw = http_req(url, method="GET")
        if st != 200:
            return []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("event") != "message" or not ev.get("message"):
                    continue
                msg_txt = str(ev["message"])
                assert_zero_pii_text(msg_txt, "grok_ntfy_topic")
                pkt = json.loads(msg_txt)
                if not isinstance(pkt, dict) or pkt.get("a") != "n3g":
                    continue

                for row in pkt.get("r") or []:
                    if not isinstance(row, list) or len(row) < 6:
                        continue
                    srow = int(row[0] or 0)
                    ts_pt = str(row[1] or "").strip()
                    subj = str(row[2] or "").strip()
                    qid = str(row[3] or "").strip()
                    pt_raw = str(row[4] or "").strip()
                    res_val = row[5]
                    again_val = row[6] if len(row) >= 7 else 0

                    if isinstance(res_val, str) and ("未作答" in res_val or "不判分" in res_val or "作废" in res_val or not res_val.strip()):
                        continue
                    ok = (res_val == 1 or res_val is True or (isinstance(res_val, str) and res_val.strip().startswith("对")))
                    ask_again = (
                        again_val == 1
                        or again_val is True
                        or (isinstance(again_val, str) and "还是要考" in again_val)
                    )
                    seal_done = (again_val == 2 or (isinstance(again_val, str) and "不用再考" in again_val))

                    pts = resolve_grok_points(subj, qid, pt_raw, lookups)
                    if not pts:
                        continue
                    base_gid = f"GROK-{srow - 1}" if srow > 1 else f"GROK-NTFY-{hashlib.sha1(f'{ts_pt}|{qid}|{pt_raw}'.encode('utf-8')).hexdigest()[:8]}"
                    for idx_p, pt in enumerate(pts):
                        gid = base_gid if idx_p == 0 else f"{base_gid}-{idx_p + 1}"
                        if gid in existing_ids:
                            continue
                        seq = minute_counter.get(ts_pt, 0) + 1
                        minute_counter[ts_pt] = seq
                        rec = {
                            "id": gid,
                            "point": pt,
                            "correct": bool(ok),
                            "ask_again": bool(ask_again),
                            "source": "grok",
                            "ts": to_pt_iso(ts_pt, seq),
                        }
                        if seal_done and ok and not ask_again:
                            rec["choice"] = "Grok:不用再考"
                        existing_ids.add(gid)
                        added.append(rec)

                for rec in pkt.get("records") or []:
                    if not isinstance(rec, dict):
                        continue
                    gid = str(rec.get("id") or "").strip()
                    pt = str(rec.get("point") or "").strip()
                    if not gid.startswith("GROK-") or not pt or gid in existing_ids:
                        continue
                    clean_rec = {
                        "id": gid,
                        "point": pt,
                        "correct": str(rec.get("correct", "")).lower() == "true" or rec.get("correct") is True,
                        "ask_again": str(rec.get("ask_again", "")).lower() == "true" or rec.get("ask_again") is True,
                        "source": "grok",
                        "ts": to_pt_iso(str(rec.get("ts") or ""), 1),
                    }
                    if rec.get("choice") == "Grok:不用再考":
                        clean_rec["choice"] = "Grok:不用再考"
                    existing_ids.add(gid)
                    added.append(clean_rec)
            except Exception:
                continue
        if added:
            print(f"[sync] Pulled {len(added)} new Grok records from cloud grok_ntfy_topic")
    except Exception as e:
        print(f"[sync] grok_ntfy_topic pull skipped: {e}")
    return added


def main():
    plan_date = get_latest_plan_date()
    baked_epoch = get_baked_epoch()
    cfg = load_json(CONFIG_PATH, {})
    if not cfg.get("ntfy_topic"):
        cfg["ntfy_topic"] = "n3zen_" + secrets.token_hex(14)
    if not cfg.get("grok_ntfy_topic"):
        cfg["grok_ntfy_topic"] = "n3grok_" + secrets.token_hex(14)

    raw_snap = load_json(SNAPSHOT_PATH, empty_crdt_state(plan_date))
    if raw_snap.get("app") != "n3-zen":
        raw_snap = empty_crdt_state(plan_date)
    # Normalize through merge_crdt so any legacy < MIN_REAL_TS entries in raw_snap are cleaned
    state = merge_crdt(empty_crdt_state(plan_date), raw_snap)

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

    # Append any newly synced answer records from Phone/Desktop + Grok Cloud Bus into practice_log.jsonl
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
        rid_s = str(r.get("id") or "")
        if rid_s.startswith("LK:"):
            surf = rid_s[3:].strip() or str(r.get("choice") or "").strip()
            ts_lk = str(r.get("ts") or "")
            ctx_lk = str(r.get("point") or "").strip()
            if surf:
                cur_lk = state.setdefault("wordLookups", {}).get(surf) or {"count": 0, "last_ts": "", "contexts": []}
                ctxs = list(cur_lk.get("contexts") or [])
                if ctx_lk and ctx_lk not in ctxs:
                    ctxs.append(ctx_lk)
                inc = 1 if ts_lk > str(cur_lk.get("last_ts") or "") else 0
                state["wordLookups"][surf] = {
                    "count": max(1, int(cur_lk.get("count") or 0) + inc),
                    "last_ts": max(str(cur_lk.get("last_ts") or ""), ts_lk),
                    "contexts": ctxs[-12:],
                }
    for d_key, d_bucket in (state.get("dates") or {}).items():
        for tw in (d_bucket or {}).get("tappedWords") or []:
            tw_s = str(tw or "").strip()
            if tw_s and tw_s not in state.setdefault("wordLookups", {}):
                state["wordLookups"][tw_s] = {"count": 1, "last_ts": d_key, "contexts": [f"date:{d_key}"]}

    grok_cloud_recs = pull_grok_ntfy_bus(cfg, existing_log + new_recs)
    new_recs.extend(grok_cloud_recs)

    if new_recs:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            for r in new_recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[sync] Appended {len(new_recs)} cloud answer records to practice_log.jsonl")

    if not state.get("updatedAt"):
        state["updatedAt"] = int(time.time())

    compact_pkt = pack_compact_ntfy(state, plan_date, baked_epoch=baked_epoch)
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
    return len(new_recs)


if __name__ == "__main__":
    main()
