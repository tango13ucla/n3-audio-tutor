#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Zero-PII Grok Point Resolver & Validator (grok_point_resolver.py).
Used by:
  - sync_cloud_store.py (Cloud-native GitHub Actions ingestion from grok_ntfy_topic)
  - merge_grok_to_tutor.py (Google Sheet N3答题总账 incremental backup merger)
"""
from __future__ import annotations
import datetime
import re
from zoneinfo import ZoneInfo

PT_TZ = ZoneInfo("America/Los_Angeles")

GRAMMAR_ALIASES = {
    "〜てもらう": "〜てくれる／もらう",
    "授受 てもらう": "〜てくれる／もらう",
    "授受 てくれる": "〜てくれる／もらう",
    "授受 てあげる": "〜てくれる／もらう",
    "授受・さしあげる方向": "授受敬语升级",
    "授受 くださる": "授受敬语升级",
    "授受 いただく": "授受敬语升级",
    "めったに〜ない": "〜めったに〜ない",
    "による": "〜による／によって",
    "〜によって": "〜による／によって",
    "によって": "〜による／によって",
    "によると": "〜によると／によれば",
    "〜によると": "〜によると／によれば",
    "によれば": "〜によると／によれば",
    "〜によれば": "〜によると／によれば",
    "とすると": "〜とすると",
    "そうだ": "そうだ（伝聞）",
    "そうだ(伝聞)": "そうだ（伝聞）",
    "そうだ（伝聞）vs 様態": "そうだ（伝聞）",
    "そうだ(样态/伝聞辨析)": "そうだ（伝聞）",
    "ことはない": "〜ことはない",
    "まるで〜ようだ": "まるで〜のように",
    "まるで〜みたいだ": "まるで〜のように",
    "まるで": "まるで〜のように",
    "ていく/てくる": "〜ていく／〜てくる",
    "〜ていく": "〜ていく／〜てくる",
    "〜てくる": "〜ていく／〜てくる",
    "〜ものだ（感慨）": "〜ものだ",
    "〜ということだ（伝聞）": "〜ということだ",
    "〜たばかり": "〜ばかり",
    "たばかり": "〜ばかり",
    "〜かける": "〜かけだ",
    "かける": "〜かけだ",
    "〜たところだ": "〜ところだ",
    "たところだ": "〜ところだ",
    "〜てしかたがない": "〜てたまらない",
    "てしかたがない": "〜てたまらない",
    "〜てしょうがない": "〜てたまらない",
    "てしょうがない": "〜てたまらない",
    "てたまらない": "〜てたまらない",
    "っぱなし": "〜っぱなし",
    "わりに": "〜わりに",
    "からこそ": "〜からこそ",
    "にしたがって": "〜にしたがって",
}

HENKEI_ALIASES = {
    "拝見する": "K-013",
    "来る 可能形": "V-030",
    "来る可能形": "V-030",
    "ら抜き": "V-031",
    "起きる/起こす": "V-031",
    "起きる・起こす": "V-031",
    "開く/開ける": "T-001",
    "閉まる/閉める": "T-002",
    "つく/つける": "T-003",
    "消える/消す": "T-004",
    "始まる/始める": "T-005",
    "終わる/終える": "T-006",
    "変わる/変える": "T-007",
    "壊れる/壊す": "T-008",
    "汚れる/汚す": "T-009",
    "割れる/割る": "T-013",
    "止まる/止める": "T-023",
    "集まる/集める": "T-028",
    "見つかる/見つける": "T-031",
    "決まる/決める": "T-032",
    "続く/続ける": "T-033",
    "届く/届ける": "T-034",
    "直る/直す": "T-040",
    "治る/治す": "T-041",
    "落ちる/落とす": "T-044",
    "召し上がる": "K-003",
    "いらっしゃる": "K-001",
    "いただく": "K-012",
    "使役+ていただく": "K-045",
    "させていただ": "K-045",
    "てくださる": "K-045",
    "使役受身": "V-045",
}

PII_FORBIDDEN_PATTERNS = [
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("external member/candidate ID", re.compile(r"\b(?:F\d{6}|M\d{6})\b")),
    ("SSN or 16-digit card", re.compile(r"\b(?:\d{4}[- ]){3}\d{4}\b|\b\d{3}-\d{2}-\d{4}\b")),
]

CLEAN_JA_WORD_RE = re.compile(r"^[\u3040-\u30ff\u4e00-\u9fffー々〜・]{1,16}$")


def contains_pii(txt: str) -> bool:
    for _label, pat in PII_FORBIDDEN_PATTERNS:
        if pat.search(str(txt or "")):
            return True
    return False


def assert_zero_pii_text(txt: str, label_ctx: str = "payload") -> None:
    for label, pat in PII_FORBIDDEN_PATTERNS:
        if pat.search(txt):
            raise RuntimeError(f"ZERO-PII GUARD BLOCKED ({label}) in {label_ctx}")


def to_pt_iso(raw_ts: str, seq_within_min: int = 1) -> str:
    raw = str(raw_ts or "").strip()
    if "T" in raw and len(raw) >= 19:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=PT_TZ)
            return dt.astimezone(PT_TZ).isoformat()
        except Exception:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            if fmt == "%Y-%m-%d %H:%M":
                dt = dt.replace(second=min(59, max(0, int(seq_within_min))))
            return dt.replace(tzinfo=PT_TZ).isoformat()
        except ValueError:
            continue
    now_pt = datetime.datetime.now(PT_TZ).replace(microsecond=0)
    return now_pt.isoformat()


def build_lookup_sets(state: dict) -> dict:
    g_set = {p["name"] for p in state.get("grammar_points", [])}
    h_set = {p["id"] for p in state.get("henkei_points", [])}
    l_set = {p["id"] for p in state.get("listening_points", [])}
    v_set = {p["word"] for p in state.get("vocab_tracked", [])}
    # Dynamic pair lookup for all 75 T-* / K-* / V-* points (e.g. "消える/消す" -> "T-004")
    h_pair_map = {}
    for hp in state.get("henkei_points", []):
        hid = hp.get("id", "")
        hname = hp.get("name", "")
        if "↔" in hname:
            parts = [re.sub(r"（.*?）|\(.*?\)", "", x).strip() for x in hname.split("↔")]
            if len(parts) == 2 and parts[0] and parts[1]:
                p0 = parts[0].split("／")[0].strip()
                p1 = parts[1].split("／")[0].strip()
                h_pair_map[f"{p0}/{p1}"] = hid
                h_pair_map[f"{p0}・{p1}"] = hid
                h_pair_map[f"{p1}/{p0}"] = hid
    return {
        "g_set": g_set,
        "h_set": h_set,
        "l_set": l_set,
        "v_set": v_set,
        "h_pair_map": h_pair_map,
        "known_all": g_set | h_set | l_set | v_set,
    }


def resolve_grok_points(subj: str, qid: str, pt_raw: str, lookups: dict) -> list[str]:
    g_set = lookups["g_set"]
    h_set = lookups["h_set"]
    l_set = lookups["l_set"]
    v_set = lookups["v_set"]
    h_pair_map = lookups["h_pair_map"]

    combo = f"{qid} {pt_raw}"
    l_ids = re.findall(r"N3L-\d{3}", combo)
    if l_ids:
        matched = [lid for lid in dict.fromkeys(l_ids) if lid in l_set]
        if matched:
            return matched

    h_ids = re.findall(r"\b[VTKA]-\d{3}\b", combo)
    if h_ids:
        matched = [hid for hid in dict.fromkeys(h_ids) if hid in h_set]
        if matched:
            return matched

    base = re.split(r"[（(]", pt_raw)[0].strip()
    q_base = re.split(r"[（(]", qid)[0].strip()
    if subj == "语法":
        for cand in (pt_raw.strip(), base, "〜" + base.lstrip("〜"), q_base, "〜" + q_base.lstrip("〜")):
            if cand in g_set:
                return [cand]
            if cand in GRAMMAR_ALIASES and GRAMMAR_ALIASES[cand] in g_set:
                return [GRAMMAR_ALIASES[cand]]
        for k, v in GRAMMAR_ALIASES.items():
            if (k in pt_raw or k in qid) and v in g_set:
                return [v]
    elif subj == "变形":
        for cand in (pt_raw.strip(), base, q_base):
            if cand in HENKEI_ALIASES and HENKEI_ALIASES[cand] in h_set:
                return [HENKEI_ALIASES[cand]]
            if cand in h_pair_map and h_pair_map[cand] in h_set:
                return [h_pair_map[cand]]
        for k, v in HENKEI_ALIASES.items():
            if (k in pt_raw or k in qid) and v in h_set:
                return [v]
        for pair_k, hid in h_pair_map.items():
            if pair_k in pt_raw or pair_k in qid:
                return [hid]
        if "使役" in pt_raw and "V-037" in h_set:
            return ["V-037"]
        if "受身" in pt_raw and "V-032" in h_set:
            return ["V-032"]
    elif subj == "词汇":
        w = re.split(r"[\s/／・]", base)[0].strip()
        if w in v_set:
            return [w]
        if w and CLEAN_JA_WORD_RE.match(w):
            return [w]
    return []
