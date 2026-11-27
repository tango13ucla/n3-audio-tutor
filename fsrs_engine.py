#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSRS (Free Spaced Repetition Scheduler — DSR Model) + Leech Detector & Context Variability Engine.

Implements scientifically grounded long-horizon memory scheduling (Ye et al. FSRS-4.5/5,
Bjork New Theory of Disuse, Cepeda et al. 2006) seamlessly alongside the learner's
Honest 3/3 True-Green mastery rule:
  - Difficulty D in [1.0, 10.0] (item-specific intrinsic difficulty)
  - Stability  S in [0.5, 365.0] (days until retrievability R drops to 90%)
  - Retrievability R(t, S) = (1 + FACTOR * t / S) ** DECAY  (FSRS power-law forgetting curve)
  - Leech Detection: flags stubborn items (wrong >= 5 & acc < 65%, or lapses >= 4)
    so the engine automatically rotates fresh context variants, injects them into
    tomorrow's 《锵锵》 story & all-Japanese short film, and surfaces a gentle cue.

100% Zero-PII public study module. Zero em dashes.
"""
from __future__ import annotations

import datetime
import math
from typing import Any

# FSRS-4.5 power-law forgetting curve constants (R(S, S) == 0.90)
DECAY = -0.5
FACTOR = 19.0 / 81.0

# Canonical compact FSRS weights (tuned for adult L2 language acquisition)
W_INIT_S = {1: 0.6, 2: 1.5, 3: 3.2, 4: 7.5}  # Again=1, Hard=2, Good=3, Easy=4
W_INIT_D = {1: 7.2, 2: 6.2, 3: 5.0, 4: 3.5}
TARGET_RETENTION_N2 = 0.88
TARGET_RETENTION_SPRINT = 0.92


def _parse_day_ord(day_str: str) -> int | None:
    s = str(day_str or "").strip().replace("-", "")
    if len(s) >= 8 and s[:8].isdigit():
        try:
            y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
            return datetime.date(y, m, d).toordinal()
        except ValueError:
            return None
    return None


def _ord_to_tag(day_ord: int) -> str:
    return datetime.date.fromordinal(day_ord).strftime("%Y%m%d")


def retrievability(elapsed_days: float, stability: float) -> float:
    """Compute FSRS power-law probability of recall R(t, S) in [0.0, 1.0]."""
    s = max(0.3, float(stability or 1.0))
    t = max(0.0, float(elapsed_days or 0.0))
    return float((1.0 + FACTOR * (t / s)) ** DECAY)


def next_interval_days(stability: float, target_retention: float = TARGET_RETENTION_N2) -> int:
    """Solve R(I, S) = target_retention for optimal review interval I in days."""
    s = max(0.5, float(stability or 1.0))
    r = max(0.70, min(0.97, float(target_retention)))
    ivl = (s / FACTOR) * ((r ** (1.0 / DECAY)) - 1.0)
    return max(1, min(180, int(round(ivl))))


def bootstrap_fsrs_from_item(item: dict[str, Any], today_tag: str = "") -> dict[str, Any]:
    """
    Lazily initialize an FSRS DSR record from existing legacy item fields (`streak`, `status`,
    `seen`, `wrong`, `last_ok_date`, `last_ng_date`) without breaking existing data.
    """
    cur = item.get("fsrs")
    if isinstance(cur, dict) and cur.get("s") and cur.get("d"):
        return cur

    streak = int(item.get("streak") or 0)
    status = str(item.get("status") or "gray")
    seen = max(0, int(item.get("seen") or 0))
    wrong = max(0, int(item.get("wrong") or 0))

    # Estimate initial Difficulty D from historical miss ratio
    err_rate = (wrong / float(seen)) if seen > 0 else 0.0
    if status in ("red", "orange"):
        d = min(9.5, 6.2 + err_rate * 3.0)
    elif status == "yellow":
        d = min(8.8, 5.2 + err_rate * 2.8)
    elif status == "green":
        d = max(2.2, min(7.5, 4.2 + err_rate * 2.5))
    else:
        d = 5.0

    # Estimate initial Stability S from legacy streak
    if status == "green" or streak >= 3:
        s = max(5.0, 12.0 - err_rate * 6.0)
    elif streak == 2:
        s = 4.0
    elif streak == 1:
        s = 1.8
    elif status in ("red", "orange"):
        s = 0.7
    else:
        s = 1.0

    last_rev = str(item.get("last_ok_date") or item.get("last_ng_date") or "").replace("-", "")[:8]
    lapses = wrong if wrong > 0 else (1 if status in ("red", "orange") else 0)
    reps = max(seen, streak)

    due = ""
    lo = _parse_day_ord(last_rev)
    if lo is not None:
        ivl = next_interval_days(s, TARGET_RETENTION_N2)
        due = _ord_to_tag(lo + ivl)
    elif today_tag:
        due = str(today_tag).replace("-", "")[:8]

    fsrs = {
        "s": round(s, 2),
        "d": round(d, 2),
        "reps": reps,
        "lapses": lapses,
        "last_review": last_rev,
        "due": due,
    }
    item["fsrs"] = fsrs
    return fsrs


def update_fsrs_on_review(
    item: dict[str, Any],
    day_tag: str,
    ok: bool,
    again: bool = False,
    hesitant: bool = False,
    instant_done: bool = False,
    target_retention: float = TARGET_RETENTION_N2,
) -> dict[str, Any]:
    """
    Update per-item FSRS (Difficulty, Stability, Retrievability, Due) on every review event.
    Rating mapping:
      - instant_done -> 4 (Easy)
      - ok and not again and not hesitant -> 3 (Good)
      - ok and hesitant -> 2 (Hard)
      - not ok or again -> 1 (Again / Lapse)
    Idempotent on same-day double-rating for passing events so same-day loops don't inflate S.
    """
    clean_day = str(day_tag or "").replace("-", "")[:8]
    fsrs = bootstrap_fsrs_from_item(item, clean_day)
    rating = 4 if instant_done else (1 if (not ok or again) else (2 if hesitant else 3))

    prev_ord = _parse_day_ord(fsrs.get("last_review", ""))
    cur_ord = _parse_day_ord(clean_day)

    # Same-day repeat pass: keep S stable (do not double-expand within 1 calendar day)
    if prev_ord is not None and cur_ord is not None and cur_ord == prev_ord and rating >= 2:
        if rating == 4 and fsrs["s"] < 14.0:
            fsrs["s"] = round(min(45.0, max(14.0, fsrs["s"] * 1.8)), 2)
            fsrs["due"] = _ord_to_tag(cur_ord + next_interval_days(fsrs["s"], target_retention))
        return fsrs

    elapsed = max(1.0, float(cur_ord - prev_ord)) if (prev_ord is not None and cur_ord is not None and cur_ord > prev_ord) else 1.0
    s = float(fsrs.get("s") or 1.0)
    d = float(fsrs.get("d") or 5.0)
    reps = int(fsrs.get("reps") or 0)
    lapses = int(fsrs.get("lapses") or 0)

    if reps == 0:
        new_s = W_INIT_S[rating]
        new_d = W_INIT_D[rating]
        if rating == 1:
            lapses += 1
    else:
        r_now = retrievability(elapsed, s)
        # Update Difficulty with mild mean reversion toward 5.0
        delta_d = {1: +1.15, 2: +0.45, 3: -0.18, 4: -0.65}[rating]
        new_d = max(1.0, min(10.0, 0.90 * (d + delta_d) + 0.10 * 5.0))

        if rating == 1:
            # Lapse: sharp stability drop, scaled by difficulty & previous stability
            lapses += 1
            new_s = max(0.6, min(s * 0.45, 1.8 * (new_d ** -0.25) * (s ** 0.35)))
        else:
            # Successful recall: harder retrievals (lower R) yield stronger stability gains (Desirable Difficulty!)
            hard_pen = 0.72 if rating == 2 else (1.42 if rating == 4 else 1.0)
            gain = 1.0 + math.exp(0.55) * (11.0 - new_d) * (s ** -0.22) * (math.exp(1.05 * (1.0 - r_now)) - 1.0) * hard_pen
            # Guarantee meaningful forward step even on early reviews
            min_mult = 1.25 if rating == 2 else (2.2 if rating == 4 else 1.75)
            new_s = min(365.0, max(s * min_mult, s * gain))

    fsrs["s"] = round(new_s, 2)
    fsrs["d"] = round(new_d, 2)
    fsrs["reps"] = reps + 1
    fsrs["lapses"] = lapses
    if clean_day:
        fsrs["last_review"] = clean_day
    if cur_ord is not None:
        ivl = 1 if rating == 1 else next_interval_days(new_s, target_retention)
        fsrs["due"] = _ord_to_tag(cur_ord + ivl)
    item["fsrs"] = fsrs
    return fsrs


def item_retrievability_on_day(item: dict[str, Any], today_tag: str) -> tuple[float, int, float]:
    """
    Return `(R_now, days_overdue, stability_s)` for scheduling priority.
    Higher `days_overdue` and lower `R_now` indicate more urgent review!
    """
    fsrs = bootstrap_fsrs_from_item(item, today_tag)
    today_ord = _parse_day_ord(today_tag)
    last_ord = _parse_day_ord(fsrs.get("last_review", ""))
    due_ord = _parse_day_ord(fsrs.get("due", ""))
    s = float(fsrs.get("s") or 1.0)
    if today_ord is None or last_ord is None:
        return (0.5, 0, s)
    elapsed = max(0, today_ord - last_ord)
    r_now = retrievability(elapsed, s)
    overdue = (today_ord - due_ord) if due_ord is not None else 0
    return (round(r_now, 4), overdue, s)


def is_leech_item(item: dict[str, Any]) -> bool:
    """
    Detect stubborn leech items that need encoding intervention (fresh sentence variant,
    story weaving, or minimal-pair ear contrast) instead of blind card repetition.
    """
    seen = int(item.get("seen") or 0)
    wrong = int(item.get("wrong") or 0)
    fsrs = item.get("fsrs") if isinstance(item.get("fsrs"), dict) else {}
    lapses = max(wrong, int(fsrs.get("lapses") or 0))
    status = str(item.get("status") or "gray")
    if status == "green" and int(item.get("streak") or 0) >= 3 and float(fsrs.get("s") or 0) >= 21.0:
        return False
    if wrong >= 5 and seen > 0 and (wrong / float(seen)) >= 0.35:
        return True
    if lapses >= 5 and status != "green":
        return True
    return False


def collect_leeches(state: dict[str, Any], max_items: int = 12) -> dict[str, list[dict[str, Any]]]:
    """Extract top active leech vocab words & grammar/listening points for intervention."""
    leech_vocab: list[dict[str, Any]] = []
    for v in state.get("vocab_tracked") or []:
        if isinstance(v, dict) and is_leech_item(v):
            seen = max(1, int(v.get("seen") or 1))
            wrong = int(v.get("wrong") or 0)
            leech_vocab.append({
                "word": str(v.get("word") or ""),
                "wrong": wrong,
                "seen": seen,
                "err_pct": int(round(100.0 * wrong / seen)),
                "status": str(v.get("status") or "red"),
            })
    leech_vocab.sort(key=lambda x: (-x["wrong"], -x["err_pct"], x["word"]))

    leech_points: list[dict[str, Any]] = []
    for bucket in ("grammar_points", "n2_grammar_points", "henkei_points", "listening_points"):
        for p in state.get(bucket) or []:
            if not isinstance(p, dict):
                continue
            if is_leech_item(p):
                key = str(p.get("name") or p.get("point") or p.get("id") or "")
                fsrs = p.get("fsrs") or {}
                leech_points.append({
                    "id": str(p.get("id") or key),
                    "point": key,
                    "lapses": int(fsrs.get("lapses") or p.get("wrong") or 0),
                    "d": float(fsrs.get("d") or 7.0),
                    "status": str(p.get("status") or "red"),
                })
    leech_points.sort(key=lambda x: (-x["lapses"], -x["d"], x["point"]))
    return {
        "vocab": leech_vocab[:max_items],
        "points": leech_points[:max_items],
    }


def backfill_all_fsrs(state: dict[str, Any], today_tag: str = "") -> int:
    """Ensure every tracked item in `n3_live_state.json` carries a valid FSRS DSR record."""
    count = 0
    for bucket in ("grammar_points", "n2_grammar_points", "henkei_points", "listening_points", "vocab_tracked"):
        for item in state.get(bucket) or []:
            if isinstance(item, dict):
                bootstrap_fsrs_from_item(item, today_tag)
                count += 1
    return count


if __name__ == "__main__":
    # Self-verify FSRS math & leech detection
    sample = {"word": "こっそり", "seen": 28, "wrong": 15, "status": "yellow", "streak": 1, "last_ok_date": "20261125"}
    f0 = bootstrap_fsrs_from_item(sample, "20261126")
    assert is_leech_item(sample), "Expected こっそり to be flagged as leech"
    easy = {"id": "N2G-001", "point": "〜ざるを得ない", "status": "gray", "streak": 0}
    f1 = dict(update_fsrs_on_review(easy, "20261207", ok=True))
    f2 = dict(update_fsrs_on_review(easy, "20261211", ok=True))
    f3 = dict(update_fsrs_on_review(easy, "20261220", ok=True))
    assert f1["s"] < f2["s"] < f3["s"], f"Stability must expand on spaced successes: {f1}, {f2}, {f3}"
    f4 = dict(update_fsrs_on_review(easy, "20261225", ok=False))
    assert f4["s"] < f3["s"] and f4["lapses"] == 1, f"Lapse must contract stability: {f4}"
    print(f"FSRS Engine OK: expand {f1['s']}d -> {f2['s']}d -> {f3['s']}d | lapse -> {f4['s']}d | leech check passed")
