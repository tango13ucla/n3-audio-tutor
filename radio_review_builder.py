#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post-Listening 5-Minute Contextual Review Builder (radio_review_builder.py).

Grounded in Second Language Acquisition & Cognitive Memory Science:
- Tulving & Thomson (1973) Encoding Specificity + Bolger et al. (2008) Instance-Based Memory:
  Every review card anchors directly to the exact story chapter, host line, and timestamped
  audio clip inside today's 60-minute 《锵锵三人行》 episode (`daily_radio.mp3`).
- Metcalfe (2002, 2005) Region of Proximal Learning + Vandergrift & Goh (2012, 2022):
  Curates a tight 10-12 item deck so the learner can fast-verify known items in seconds
  and selectively tap "重学这个" ONLY on the 1-2 fuzzy items (or brand-new N2 items from scratch).
- 100% Zero-PII public study module.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
AUDIO_MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")

SWAP_TOKEN_RE = re.compile(r"\{\{([^|]+)\|([^}]+)\}\}")
JA_SPAN_RE = re.compile(r"[ぁ-んァ-ヶー・一-龥]+(?:[、，。！？\s]*[ぁ-んァ-ヶー・一-龥]+)*")
PURE_KANA_SENT_RE = re.compile(r"[ぁ-んァ-ヶー]{2,}[^。！？\n]{4,60}")
SPK_NAMES = {"W": "文涛", "D": "文道", "X": "子东"}


def _clean_text(s: str) -> str:
    s = str(s or "").strip()
    s = s.replace("——", "，").replace("—", "，")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _readable_turn(txt: str, vocab_by_kana: dict[str, dict]) -> str:
    """Convert internal `{zh}也就是{{zh|kana}}` & `{{zh|kana}}` markers to clean readable text."""
    def _rep_bridge(m: re.Match) -> str:
        zh = m.group(1).strip()
        kana = m.group(2).strip()
        ent = vocab_by_kana.get(kana) or {}
        kanji = ent.get("kanji") or zh
        return kana if kanji == kana else f"{kanji}（{kana}）"

    def _rep(m: re.Match) -> str:
        zh = m.group(1).strip()
        kana = m.group(2).strip()
        ent = vocab_by_kana.get(kana) or {}
        kanji = ent.get("kanji") or zh
        if kanji == kana:
            return kana
        return f"{kanji}（{kana}）"

    out = re.sub(r"([\u4e00-\u9fff]{1,6})也就是\{\{\1\|([^}]+)\}\}", _rep_bridge, str(txt or ""))
    out = SWAP_TOKEN_RE.sub(_rep, out)
    out = re.sub(r"\s+([，。！？；：、])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return _clean_text(out)


_GRAMMAR_KANJI_TO_KANA = [
    ("にもかかわらず", "にもかかわらず"),
    ("ざるを得ない", "ざるをえない"),
    ("とは限らない", "とはかぎらない"),
    ("必ずしも", "かならずしも"),
    ("に限る", "にかぎる"),
    ("に限らず", "にかぎらず"),
    ("に限って", "にかぎって"),
    ("に関して", "にかんして"),
    ("に対して", "にたいして"),
    ("に基づいて", "にもとづいて"),
    ("に基づき", "にもとづき"),
    ("に従って", "にしたがって"),
    ("に伴って", "にともなって"),
    ("に応じて", "におうじて"),
    ("に比べて", "にくらべて"),
    ("に加えて", "にくわえて"),
    ("恐れがある", "おそれがある"),
    ("次第", "しだい"),
    ("同時に", "どうじに"),
    ("一方", "いっぽう"),
    ("反面", "はんめん"),
    ("最中", "さいちゅう"),
    ("途端", "とたん"),
    ("結果", "けっか"),
    ("向け", "むけ"),
    ("気味", "ぎみ"),
    ("通り", "どおり"),
    ("通り", "とおり"),
    ("上で", "うえで"),
    ("上に", "うえに"),
    ("末に", "すえに"),
    ("得る", "える"),
    ("得ない", "えない"),
    ("得る", "うる"),
    ("難い", "がたい"),
    ("兼ねる", "かねる"),
    ("切る", "きる"),
    ("抜く", "ぬく"),
    ("込む", "こむ"),
    ("直す", "なおす"),
]


def _strip_point_stem(point_name: str) -> list[str]:
    """Extract searchable Japanese stems (both Kanji and hiragana TTS forms) from a grammar/vocab label."""
    raw = str(point_name or "").strip()
    raw = re.sub(r"[（(][^）)]*[）)]", "", raw).strip()
    parts = re.split(r"[/／・]", raw)
    stems: list[str] = []
    for p in parts:
        p = p.strip().replace("〜", "").replace("~", "").replace("～", "").strip()
        if len(p) >= 2:
            stems.append(p)
            p_kana = p
            for kj, kn in _GRAMMAR_KANJI_TO_KANA:
                if kj in p_kana:
                    p_kana = p_kana.replace(kj, kn)
            if p_kana != p and len(p_kana) >= 2:
                stems.append(p_kana)
            # Also add kana-only tail if mixed with leading particle/kanji
            m_tail = re.search(r"[ぁ-んァ-ヶー]{3,}$", p_kana)
            if m_tail and m_tail.group(0) != p_kana:
                stems.append(m_tail.group(0))
    return list(dict.fromkeys(stems))


def _load_card_index() -> tuple[dict[str, dict], dict[str, dict], dict[str, Any]]:
    """Load unified N3 (+ N2 prep) point metadata, vocab mnemonics, and audio manifest."""
    import sys
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    cards_by_id: dict[str, dict] = {}
    try:
        from adaptive_bank import EXTRA_PRIMARY_CARDS
        from clear_explanations import CARDS_75
        from tutor_data import TUTOR_ITEMS
        for src in (TUTOR_ITEMS, CARDS_75, EXTRA_PRIMARY_CARDS):
            for c in src:
                if isinstance(c, dict) and c.get("id"):
                    cid = str(c["id"])
                    if cid not in cards_by_id:
                        cards_by_id[cid] = dict(c)
                    else:
                        merged = dict(cards_by_id[cid])
                        for k, v in c.items():
                            if v and not merged.get(k):
                                merged[k] = v
                        cards_by_id[cid] = merged
    except Exception:
        pass

    # N2 zero-base grammar syllabus (active from 2026-12-07 onward)
    n2_by_id: dict[str, dict] = {}
    try:
        n2_dir = os.path.join(BASE_DIR, "n2_prep")
        if os.path.isdir(n2_dir) and n2_dir not in sys.path:
            sys.path.insert(0, n2_dir)
        from n2_grammar_syllabus import N2_GRAMMAR_SYLLABUS
        for g in N2_GRAMMAR_SYLLABUS:
            if isinstance(g, dict) and g.get("id"):
                n2_by_id[str(g["id"])] = g
    except Exception:
        pass

    manifest: dict[str, Any] = {}
    if os.path.exists(AUDIO_MANIFEST_PATH):
        try:
            manifest = json.load(open(AUDIO_MANIFEST_PATH, encoding="utf-8"))
        except Exception:
            manifest = {}

    return cards_by_id, n2_by_id, manifest


def _load_mastery_status() -> dict[str, tuple[str, int]]:
    """Map canonical point_key/word -> (status, streak) from n3_live_state.json."""
    out: dict[str, tuple[str, int]] = {}
    if not os.path.exists(STATE_PATH):
        return out
    try:
        st = json.load(open(STATE_PATH, encoding="utf-8"))
        for g in st.get("grammar_points") or []:
            out[str(g.get("name") or "")] = (str(g.get("status") or "yellow"), int(g.get("streak") or 0))
        for h in st.get("henkei_points") or []:
            k = str(h.get("id") or "")
            nm = str(h.get("name") or "")
            val = (str(h.get("status") or "yellow"), int(h.get("streak") or 0))
            if k:
                out[k] = val
            if nm:
                out[nm] = val
        for l in st.get("listening_points") or []:
            k = str(l.get("id") or "")
            val = (str(l.get("status") or "yellow"), int(l.get("streak") or 0))
            if k:
                out[k] = val
        for v in st.get("vocab_tracked") or []:
            w = str(v.get("word") or "")
            if w:
                out[w] = (str(v.get("status") or "yellow"), int(v.get("streak") or 0))
    except Exception:
        pass
    return out


def _estimate_turn_timings_from_segments(
    story_blocks: list[dict],
    segments_meta: list[dict],
    audio_mp3_path: str = "",
) -> dict[tuple[int, int], tuple[float, float]]:
    """
    Fallback estimator for already-rendered episodes (like Vol.8) where mixer.sec wasn't logged yet.
    Uses weighted speech duration per turn scaled strictly to each chapter's exact `[start, end]`,
    then snaps clip starts/ends to nearby low-energy pauses in `daily_radio.mp3` when available.
    """
    timings: dict[tuple[int, int], tuple[float, float]] = {}
    seg_by_ch = {int(s.get("chapter", i)): s for i, s in enumerate(segments_meta)}

    # Optional RMS envelope from daily_radio.mp3 for pause-boundary snapping (100ms frames)
    rms_frames = None
    frame_hop_sec = 0.10
    if audio_mp3_path and os.path.exists(audio_mp3_path) and shutil.which("ffmpeg"):
        try:
            import numpy as np
            proc = subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-i", audio_mp3_path,
                    "-ac", "1", "-ar", "4000", "-f", "f32le", "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            pcm = np.frombuffer(proc.stdout, dtype=np.float32)
            hop = 400  # 100ms at 4kHz
            n_f = len(pcm) // hop
            if n_f > 100:
                frames = pcm[: n_f * hop].reshape(n_f, hop)
                rms_frames = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
        except Exception:
            rms_frames = None

    def _snap_pause(sec: float, lo: float, hi: float, search_win: float = 2.4) -> float:
        if rms_frames is None:
            return round(max(lo, min(hi, sec)), 1)
        idx_c = int(round(sec / frame_hop_sec))
        r = int(round(search_win / frame_hop_sec))
        a = max(int(round(lo / frame_hop_sec)), idx_c - r)
        b = min(len(rms_frames) - 1, int(round(hi / frame_hop_sec)), idx_c + r)
        if b <= a:
            return round(max(lo, min(hi, sec)), 1)
        sub = rms_frames[a : b + 1]
        best = a + int(sub.argmin())
        return round(best * frame_hop_sec, 1)

    for ch_idx, blk in enumerate(story_blocks):
        seg = seg_by_ch.get(ch_idx)
        if not seg:
            continue
        s0 = float(seg.get("start", 0.0))
        s1 = float(seg.get("end", s0 + 480.0))
        # Account for opening theme (~7s) in chapter 0 and ad-break bumper (~8s) at chapter tail
        usable_start = s0 + (7.5 if ch_idx == 0 else 2.5)
        usable_end = max(usable_start + 30.0, s1 - (10.0 if ch_idx in (0, 2, len(story_blocks) - 1) else 1.5))
        usable_dur = usable_end - usable_start
        turns = blk.get("raw_turns") or []
        if not turns:
            continue
        weights: list[float] = []
        for _spk, txt_raw in turns:
            txt = SWAP_TOKEN_RE.sub(lambda m: m.group(2), str(txt_raw or ""))
            ja_chars = len(re.findall(r"[ぁ-んァ-ヶー]", txt))
            zh_chars = len(re.findall(r"[\u4e00-\u9fff]", txt))
            punc = len(re.findall(r"[，。！？；：]", txt))
            # Japanese is spoken ~25% slower than Mandarin in v40 radio
            w = max(4.0, zh_chars * 1.0 + ja_chars * 1.25 + punc * 1.3)
            weights.append(w)
        tot_w = sum(weights) or 1.0
        cur = usable_start
        for t_idx, w in enumerate(weights):
            dur = usable_dur * (w / tot_w)
            t0 = cur
            t1 = cur + dur
            cur = t1
            timings[(ch_idx, t_idx)] = (
                _snap_pause(t0, s0, s1, 1.8),
                _snap_pause(t1, s0, s1, 1.8),
            )
    return timings


def _extract_snippet(readable_txt: str, anchor: str = "", max_chars: int = 86) -> str:
    """Pull the tightest crisp sentence around `anchor` from a host turn."""
    txt = _clean_text(readable_txt)
    if len(txt) <= max_chars:
        return txt
    sents = re.findall(r"[^。！？]+[。！？]?", txt)
    if anchor:
        for s in sents:
            if anchor in s:
                s = s.strip()
                if len(s) <= max_chars + 16:
                    return s
                idx = s.find(anchor)
                lo = max(0, idx - 26)
                hi = min(len(s), lo + max_chars)
                piece = s[lo:hi].strip("，、； ")
                return ("…" if lo > 0 else "") + piece + ("…" if hi < len(s) else "")
    for s in sents:
        s = s.strip()
        if len(s) >= 16:
            return s[:max_chars] + ("…" if len(s) > max_chars else "")
    return txt[:max_chars] + "…"


def _extract_ja_demo_from_turn(txt: str) -> str:
    """Extract an inline Japanese demo sentence after `：` / `叫` inside a teaching turn if present."""
    clean = SWAP_TOKEN_RE.sub(lambda m: m.group(2), str(txt or ""))
    # Look for a long kana sentence after colon `：`
    m = re.search(r"：\s*([ぁ-んァ-ヶー、，。！？\s]{8,70})", clean)
    if m:
        cand = re.sub(r"\s+", "", m.group(1)).strip("，、。！？ ")
        if len(cand) >= 8:
            return cand + "。"
    return ""


def _resolve_word_audio(word: str, manifest: dict[str, Any]) -> str:
    vc_map = manifest.get("vocab_cards") or {}
    vc_aud = vc_map.get(word) or {}
    for k in ("full", "rev", "front"):
        if vc_aud.get(k):
            return str(vc_aud[k])
    w_map = manifest.get("words") or {}
    if w_map.get(word):
        return str(w_map[word])
    return ""


def _resolve_hook_audio(word: str, manifest: dict[str, Any]) -> str:
    vc_map = manifest.get("vocab_cards") or {}
    vc_aud = vc_map.get(word) or {}
    if vc_aud.get("hook"):
        return str(vc_aud["hook"])
    return ""


def _resolve_point_audio(point_id: str, manifest: dict[str, Any]) -> str:
    for suffix in ("_q.mp3", "_exp.mp3"):
        rel = f"./audio/{point_id}{suffix}"
        if os.path.exists(os.path.join(BASE_DIR, "audio", f"{point_id}{suffix}")):
            return rel
    return ""


def build_episode_review_items(
    story_blocks: list[dict],
    segments_meta: list[dict],
    imm_vocab_report: dict,
    turn_timings: dict[tuple[int, int], tuple[float, float]] | None = None,
    audio_mp3_path: str = "",
    max_total: int = 12,
) -> list[dict]:
    """
    Build the 10-12 item 5-Minute Post-Listening Contextual Review deck directly from
    what today's 60-minute 《锵锵三人行》 actually taught.
    """
    import sys
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    import immersion_vocab_engine as ive
    import vocab_cards as vc

    cards_by_id, n2_by_id, manifest = _load_card_index()
    mastery_map = _load_mastery_status()
    seg_by_ch = {int(s.get("chapter", i)): s for i, s in enumerate(segments_meta)}

    if not turn_timings:
        turn_timings = _estimate_turn_timings_from_segments(story_blocks, segments_meta, audio_mp3_path=audio_mp3_path)

    # Load focus_points for prioritization
    focus_set: set[str] = set()
    try:
        import tutor_prefs
        focus_set = tutor_prefs.focus_set(tutor_prefs.load_prefs())
    except Exception:
        pass

    # -------- PART A: Grammar & Expression items taught in today's chapters --------
    grammar_candidates: list[tuple[float, dict]] = []
    seen_keys: set[str] = set()

    for ch_idx, blk in enumerate(story_blocks):
        seg = seg_by_ch.get(ch_idx) or {}
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start + 480.0))
        short_tab = str(blk.get("short_tab") or f"第{ch_idx + 1}章").strip()
        story_title = _clean_text(str(blk.get("title") or short_tab))
        story_cue = story_title.split("：")[0] if "：" in story_title else story_title[:28]
        turns = blk.get("raw_turns") or []

        pids = list(blk.get("point_ids") or [])
        for p_order, pid in enumerate(pids):
            c = cards_by_id.get(pid)
            n2g = n2_by_id.get(pid)
            is_n2 = n2g is not None
            if not c and not n2g:
                continue

            if is_n2:
                key = str(n2g.get("point") or pid)
                title = key
                zh = _clean_text(str(n2g.get("soul_meaning") or ""))
                nuance = _clean_text(f"接续：{n2g.get('connection', '')}。{n2g.get('soul_meaning', '')}")
                twin = _clean_text(str(n2g.get("vs_twin") or ""))
                kind = "grammar"
                ja_fallback = str(blk.get("ja_focus") or "")
            else:
                key = str(c.get("point_key") or c.get("point") or pid).strip()
                raw_disp = str(c.get("point_display") or key).strip()
                title = re.sub(r"[（(][^）)]*[）)]", "", raw_disp).strip() or key
                m_paren = re.search(r"[（(]([^）)]+)[）)]", raw_disp)
                zh = _clean_text(m_paren.group(1) if m_paren else str(c.get("zh_meaning") or c.get("core_rule") or ""))
                if len(zh) > 34:
                    zh = zh[:34].rstrip("，、；") + "…"
                nuance = _clean_text(str(c.get("core_rule") or c.get("why_line") or ""))
                tl = c.get("teach_left") or {}
                tr = c.get("teach_right") or {}
                twin_parts = []
                if isinstance(tl, dict) and tl.get("ja") and tl.get("sub"):
                    twin_parts.append(f"{tl['ja']}：{tl['sub']}")
                if isinstance(tr, dict) and tr.get("ja") and tr.get("sub"):
                    twin_parts.append(f"对比 {tr['ja']}：{tr['sub']}")
                twin = _clean_text(" · ".join(twin_parts))
                subj = str(c.get("subject") or "")
                kind = "vocab" if ("词" in subj or "語彙" in subj or pid.startswith(("V-", "N3-V"))) else "grammar"
                ja_fallback = str(c.get("full_ja") or blk.get("ja_focus") or "")

            if not key or key in seen_keys:
                continue

            # Locate the exact host turn that actually taught or demonstrated this point!
            stems = _strip_point_stem(title) + _strip_point_stem(key)
            stems = list(dict.fromkeys(s for s in stems if len(s) >= 2))
            best_t_idx = -1
            best_t_score = -1
            matched_stem = stems[0] if stems else ""
            for t_idx, (_spk, t_raw) in enumerate(turns):
                t_str = str(t_raw or "")
                t_plain = SWAP_TOKEN_RE.sub(lambda m: m.group(2), t_str)
                hit_s = ""
                for s in stems:
                    if s in t_plain:
                        hit_s = s
                        break
                if not hit_s:
                    continue
                t_sc = 10
                if re.search(r"叫|说法|句型|双胞胎|接|意思|区别|对比|反义|专门|高频|记法", t_str):
                    t_sc += 25
                if "：" in t_str and len(re.findall(r"[ぁ-んァ-ヶー]", t_plain)) >= 8:
                    t_sc += 20
                if t_sc > best_t_score:
                    best_t_score = t_sc
                    best_t_idx = t_idx
                    matched_stem = hit_s

            if best_t_idx < 0:
                continue

            spk_code, t_raw = turns[best_t_idx]
            readable = _readable_turn(str(t_raw), ive.VOCAB_BY_KANA)
            ctx_line = _extract_snippet(readable, matched_stem, max_chars=92)
            ja_ex = _extract_ja_demo_from_turn(str(t_raw)) or ja_fallback
            # Prefer crisp sentence from chapter's `ja_focus` if it contains our stem (exact Japanese orthography!)
            chap_ja = str(blk.get("ja_focus") or "")
            if chap_ja:
                for js in re.split(r"(?<=[。！？])", chap_ja):
                    js = js.strip()
                    if js and any(s in js for s in stems):
                        ja_ex = js
                        break

            # Clip window: cover the teaching turn (and if the prior turn was a short question leading into it, include 2s lead-in)
            t0, t1 = turn_timings.get((ch_idx, best_t_idx), (seg_start + 30.0, min(seg_end, seg_start + 46.0)))
            clip_s = max(seg_start, round(t0 - 1.0, 1))
            clip_e = min(seg_end, round(t1 + 1.2, 1))
            # Keep clip tight and pleasant (8–22 seconds)
            if clip_e - clip_s < 7.0:
                clip_e = min(seg_end, round(clip_s + 11.0, 1))
            elif clip_e - clip_s > 24.0:
                clip_e = round(clip_s + 22.0, 1)

            st_val, streak_val = mastery_map.get(key, ("yellow", 0))
            prio = 0.0
            if is_n2:
                prio += 200.0
            if st_val in ("red", "orange"):
                prio += 80.0
            elif st_val != "green":
                prio += 45.0 - streak_val * 8.0
            if pid in focus_set or key in focus_set:
                prio += 35.0
            if best_t_score >= 30:
                prio += 20.0
            # Small bonus for first point per chapter so all chapters get represented
            prio -= p_order * 3.0

            mn = vc.get_pronunciation_mnemonic(title, key) if kind == "vocab" else ""
            demo_aud = _resolve_point_audio(pid, manifest)
            if not demo_aud and kind == "vocab":
                demo_aud = _resolve_word_audio(title, manifest) or _resolve_word_audio(key, manifest)

            seen_keys.add(key)
            grammar_candidates.append((
                prio,
                {
                    "id": f"RVR-{pid}",
                    "kind": kind,
                    "key": key,
                    "point_id": pid,
                    "title": title,
                    "kana": key if kind == "vocab" and not vc.HAS_KANJI_RE.search(key) else "",
                    "trap_hl": [],
                    "trap_tag": "",
                    "zh": zh,
                    "chapter_idx": ch_idx,
                    "chapter_title": short_tab,
                    "story_cue": story_cue,
                    "speaker": SPK_NAMES.get(spk_code, "文道"),
                    "context_line": ctx_line,
                    "ja_example": _clean_text(ja_ex),
                    "nuance": nuance,
                    "twin": twin,
                    "mnemonic": _clean_text(mn),
                    "clip_start": clip_s,
                    "clip_end": clip_e,
                    "demo_audio": demo_aud,
                    "hook_audio": (_resolve_hook_audio(title, manifest) or _resolve_hook_audio(key, manifest)) if kind == "vocab" else "",
                    "is_new_n2": is_n2,
                    "status": st_val,
                    "streak": streak_val,
                },
            ))

    # Select balanced grammar/expression items: guarantee breadth across chapters (1 per chapter first, up to 7 total)
    picked_grammar: list[dict] = []
    picked_ids: set[str] = set()
    by_chap: dict[int, list[tuple[float, dict]]] = {}
    for sc, item in grammar_candidates:
        by_chap.setdefault(item["chapter_idx"], []).append((sc, item))
    for ch_idx in sorted(by_chap.keys()):
        by_chap[ch_idx].sort(key=lambda x: (-x[0], x[1]["id"]))
        top_item = by_chap[ch_idx][0][1]
        picked_grammar.append(top_item)
        picked_ids.add(top_item["id"])
    # Fill up to 7 grammar slots with highest remaining priority (e.g. N2 new items or weak points)
    rem_grammar = sorted(
        [(sc, it) for sc, it in grammar_candidates if it["id"] not in picked_ids],
        key=lambda x: (-x[0], x[1]["chapter_idx"], x[1]["id"]),
    )
    max_grammar = min(7, max(6, max_total - 5))
    for _sc, it in rem_grammar:
        if len(picked_grammar) >= max_grammar:
            break
        picked_grammar.append(it)
        picked_ids.add(it["id"])

    # -------- PART B: Podcast Spotlight Vocabulary taught/bridged in today's episode --------
    spotlight_list = list((imm_vocab_report or {}).get("today_spotlight") or [])
    vocab_candidates: list[tuple[float, dict]] = []

    for sp_item in spotlight_list:
        kana = str(sp_item.get("kana") or "").strip()
        kanji = str(sp_item.get("kanji") or kana).strip()
        zh = str(sp_item.get("zh") or "").strip()
        if not kana or kanji in seen_keys or kana in seen_keys:
            continue
        ent = ive.VOCAB_BY_KANA.get(kana) or {}

        # Find the exact turn where this word was bridged (`也就是{{...|kana}}`) or spoken in Japanese
        best_hit: tuple[int, int, str, str, int] | None = None
        for ch_idx, blk in enumerate(story_blocks):
            turns = blk.get("raw_turns") or []
            for t_idx, (spk_code, t_raw) in enumerate(turns):
                t_str = str(t_raw or "")
                hit_q = 0
                if f"|{kana}}}}}" in t_str:
                    hit_q = 30 if f"也就是{{{{{zh}|{kana}}}}}" in t_str or "也就是{{" in t_str else 18
                elif kana in t_str:
                    hit_q = 12
                if hit_q > 0:
                    if best_hit is None or hit_q > best_hit[4]:
                        best_hit = (ch_idx, t_idx, spk_code, t_str, hit_q)
                    if hit_q >= 30:
                        break
            if best_hit is not None and best_hit[4] >= 30:
                break

        if best_hit is None:
            continue

        ch_idx, t_idx, spk_code, t_raw, _hq = best_hit
        blk = story_blocks[ch_idx]
        seg = seg_by_ch.get(ch_idx) or {}
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start + 480.0))
        short_tab = str(blk.get("short_tab") or f"第{ch_idx + 1}章").strip()
        story_title = _clean_text(str(blk.get("title") or short_tab))
        story_cue = story_title.split("：")[0] if "：" in story_title else story_title[:28]

        readable = _readable_turn(t_raw, ive.VOCAB_BY_KANA)
        anchor = f"{kanji}（{kana}）" if kanji != kana else kana
        ctx_line = _extract_snippet(readable, anchor if anchor in readable else kanji, max_chars=86)

        t0, t1 = turn_timings.get((ch_idx, t_idx), (seg_start + 30.0, min(seg_end, seg_start + 46.0)))
        clip_s = max(seg_start, round(t0 - 0.8, 1))
        clip_e = min(seg_end, round(t1 + 1.0, 1))
        if clip_e - clip_s < 7.0:
            clip_e = min(seg_end, round(clip_s + 10.0, 1))
        elif clip_e - clip_s > 22.0:
            clip_e = round(clip_s + 20.0, 1)

        has_kanji = bool(vc.HAS_KANJI_RE.search(kanji))
        trap_hl, trap_tag, _opq = vc.analyze_kanji_reading_trap(kanji, kana, zh) if has_kanji else ([], "", True)
        mn = vc.get_pronunciation_mnemonic(kanji, kanji)
        vc_spec = vc.VOCAB_CARDS.get(kanji) or {}
        ja_ex = str(vc_spec.get("chunk_ja") or f"{kanji}（{kana}）")
        twin = _clean_text(str(vc_spec.get("twin") or ""))
        st_val, streak_val = mastery_map.get(kanji, ("yellow", 0))

        v_prio = 0.0
        if ent.get("tier") == "user_priority":
            v_prio += 120.0
        elif ent.get("tier") == "n2_core":
            v_prio += 70.0
        else:
            v_prio += 40.0
        if sp_item.get("status") != "locked_ja":
            v_prio += 25.0
        if trap_tag:
            v_prio += 12.0
        if mn:
            v_prio += 10.0
        v_prio += min(12.0, float(sp_item.get("hits_today") or 1) * 2.5)

        seen_keys.add(kanji)
        vocab_candidates.append((
            v_prio,
            {
                "id": f"RVW-{kana}",
                "kind": "vocab",
                "key": kanji,
                "point_id": "",
                "title": kanji,
                "kana": kana,
                "trap_hl": trap_hl,
                "trap_tag": trap_tag,
                "zh": zh,
                "chapter_idx": ch_idx,
                "chapter_title": short_tab,
                "story_cue": story_cue,
                "speaker": SPK_NAMES.get(spk_code, "文道"),
                "context_line": ctx_line,
                "ja_example": _clean_text(ja_ex),
                "nuance": f"本期播客出现 {int(sp_item.get('hits_today') or 1)} 次 · 累计 {int(sp_item.get('total') or 1)} 次",
                "twin": twin,
                "mnemonic": _clean_text(mn),
                "clip_start": clip_s,
                "clip_end": clip_e,
                "demo_audio": _resolve_word_audio(kanji, manifest),
                "hook_audio": _resolve_hook_audio(kanji, manifest),
                "is_new_n2": ent.get("tier") == "n2_core",
                "status": st_val,
                "streak": streak_val,
            },
        ))

    vocab_candidates.sort(key=lambda x: (-x[0], x[1]["chapter_idx"], x[1]["title"]))
    vocab_slots = max(4, max_total - len(picked_grammar))
    picked_vocab = [it for _sc, it in vocab_candidates[:vocab_slots]]

    # Order naturally: N2 brand-new grammar first, then chronological podcast story flow!
    combined = picked_grammar + picked_vocab
    combined.sort(key=lambda x: (0 if (x.get("is_new_n2") and x["kind"] == "grammar") else 1, x["chapter_idx"], x["clip_start"]))
    return combined[:max_total]


# ==============================================================================
# Post-Listening Guided Oral Output ("听后开口 2 句")
# Backed by Swain (1985, 2005) Output Hypothesis & DeKeyser (2007) Skill Acquisition:
# Immediately after 60m listening comprehension, push 2 short syntactic-encoding turns
# anchored directly to today's episode chapters & target grammar patterns.
# ==============================================================================
_SPEAKING_TEMPLATES: dict[str, dict[str, Any]] = {
    "させてもらう": {
        "prompt_ja": "体調があまり良くない日、上司に「今日は早めに帰りたい」と丁寧に頼むなら、どう言いますか。",
        "prompt_zh": "场景：今天身体不太舒服，客气请求主管让你早点回去，用「〜させてもらう／いただく」说一句。",
        "target_stems": ["させてもら", "させていただ", "帰らせ", "休ませ", "いかせてもら", "行かせてもら"],
        "model_ja": "体調が悪いので、今日は早めに帰らせてもらってもいいですか。",
        "model_zh": "我身体不太舒服，今天能让我早点回去吗？",
        "coaching_tip": "动作是「我自己回去」，求对方准许，必须用使役形「帰らせて」而不是「帰って」。",
    },
    "に基づいて": {
        "prompt_ja": "会議で「このデータを使って計画を立てました」と、もう少し自然なビジネス日本語で説明するならどう言いますか。",
        "prompt_zh": "场景：开会汇报「我们是根据这份数据定计划的」，用「〜に基づいて」说一句。",
        "target_stems": ["に基づいて", "にもとづいて", "に基づき", "にもとづき", "に基づく", "にもとづく"],
        "model_ja": "今回の調査データに基づいて、新しい計画を立てました。",
        "model_zh": "我们根据这次的调查数据制定了新计划。",
        "coaching_tip": "名词直接加「に基づいて」，专门表达以数据、事实、规章为根据。",
    },
    "ところだった": {
        "prompt_ja": "駅まで走って、あと数秒で終電に乗り遅れそうになった経験を、友達にどう話しますか。",
        "prompt_zh": "场景：差点没赶上末班车，惊险逃过一劫，用「もう少しで〜ところだった」说一句。",
        "target_stems": ["ところだった", "ところでした"],
        "model_ja": "もう少しで終電に乗り遅れるところだったよ。",
        "model_zh": "差一点就错过末班车了。",
        "coaching_tip": "动词原形接「ところだった」，注意浊音「だった」别滑成清音「たった」。",
    },
    "最中に": {
        "prompt_ja": "お風呂に入っていたり、大事な会議をしていたりするちょうどその時に、電話がかかってきた状況をどう言いますか。",
        "prompt_zh": "场景：正开着重要会议或正洗澡时，突然来电话打断，用「〜最中に」说一句。",
        "target_stems": ["最中に", "最中は", "さいちゅうに", "さいちゅうは"],
        "model_ja": "大事な会議をしている最中に、急に電話がかかってきました。",
        "model_zh": "正在开重要会议当口，突然来了电话。",
        "coaching_tip": "「〜ている最中に」或「名词＋の最中に」，强调正干得起劲时被意外打断。",
    },
    "かわりに": {
        "prompt_ja": "今日はコーヒーをやめてお茶を飲む、あるいは誰かの代わりに会議に出る状況を、一言いってみましょう。",
        "prompt_zh": "场景：不喝咖啡改喝茶，或者替同事去开会，用「〜かわりに」说一句。",
        "target_stems": ["かわりに", "代わりに", "かわり", "代わり"],
        "model_ja": "今日はコーヒーのかわりに、温かいお茶を飲むことにしました。",
        "model_zh": "今天不喝咖啡，决定改喝热茶。",
        "coaching_tip": "名词用「〜のかわりに」，动词简体直接接「かわりに」，表示替代或交换。",
    },
    "とともに": {
        "prompt_ja": "年を重ねたり、技術が進んだりするにつれて生活が変わってきたことを、どう表現しますか。",
        "prompt_zh": "场景：随着科技进步或年纪增长，生活方式也在变化，用「〜とともに」说一句。",
        "target_stems": ["とともに", "と共に"],
        "model_ja": "技術の進歩とともに、働き方も大きく変わってきました。",
        "model_zh": "随着技术进步，工作方式也大大改变了。",
        "coaching_tip": "名词或动词原形接「とともに」，表示伴随某种趋势一起变化。",
    },
    "によって": {
        "prompt_ja": "同じ映画や料理でも、人それぞれ感想が違うと言いたいとき、日本語でどう言いますか。",
        "prompt_zh": "场景：同一部电影每个人感想都不同，用「人によって」说一句。",
        "target_stems": ["によって", "による", "により", "によっては"],
        "model_ja": "同じ映画でも、見る人によって感想がぜんぜん違います。",
        "model_zh": "就算是同一部电影，不同人看感想也完全不同。",
        "coaching_tip": "表示「因人而异／凭某种手段」用「によって」，别和「にとって（对某人来说）」混用。",
    },
    "につれて": {
        "prompt_ja": "試験の日が近づくほど緊張してきた気持ちを、そのまま日本語で言ってみましょう。",
        "prompt_zh": "场景：随着考试临近，心里越来越紧张，用「〜につれて」说一句。",
        "target_stems": ["につれて", "につれ"],
        "model_ja": "試験の日が近づくにつれて、だんだん緊張してきました。",
        "model_zh": "随着考试日期临近，渐渐紧张起来了。",
        "coaching_tip": "「动词原形／变化名词＋につれて」，前后都是自然而然的同步变化。",
    },
    "わけだ": {
        "prompt_ja": "相手が東京に十年住んでいたと聞いて、「なるほど、だから日本語が上手なんですね」と納得したとき、どう言いますか。",
        "prompt_zh": "场景：恍然大悟「难怪日语这么好」，用「〜わけだ／わけです」说一句。",
        "target_stems": ["わけだ", "わけです", "わけですね", "わけだね"],
        "model_ja": "東京に十年も住んでいたんですね。だから日本語が上手なわけですね。",
        "model_zh": "原来在东京住了十年啊，难怪日语这么好。",
        "coaching_tip": "ナ形容词和「そう」接「わけ」时，中间一定别漏掉「な」（上手なわけ）。",
    },
    "わけではない": {
        "prompt_ja": "甘いものが嫌いなわけじゃないけど、今はダイエット中なので控えている、と柔らかく断るならどう言いますか。",
        "prompt_zh": "场景：委婉澄清「并不是讨厌甜食，只是最近在控制」，用「〜わけではない」说一句。",
        "target_stems": ["わけではない", "わけではありません", "わけじゃない", "わけじゃありません"],
        "model_ja": "甘いものが嫌いなわけではないんですが、今は少し控えています。",
        "model_zh": "倒也不是讨厌甜食，只是最近稍微克制一下。",
        "coaching_tip": "部分否定用「〜わけではない」，ナ形容词接「わけ」同样必须保留「な」。",
    },
    "はずだ": {
        "prompt_ja": "さっきアイスコーヒーを頼んだのに来ていないとき、店員さんに丁寧に確認するならどう言いますか。",
        "prompt_zh": "场景：明明点过冰咖啡却一直没上，礼貌向店员确认，用「〜はずなんですが」说一句。",
        "target_stems": ["はずなん", "はずだ", "はずです", "はずで"],
        "model_ja": "すみません、さっきアイスコーヒーをお願いしたはずなんですが。",
        "model_zh": "不好意思，我刚才应该点过一杯冰咖啡来着。",
        "coaching_tip": "盯紧「はずなんですが」，千万别多滑出一个「ない」变成否定「はずないんですが」。",
    },
    "らしい": {
        "prompt_ja": "ニュースや友達から「明日は雨が降る」と聞いたとき、伝聞でどう伝えますか。",
        "prompt_zh": "场景：听说「明天会下雨」，用传闻「〜らしいです」转述一句。",
        "target_stems": ["らしい"],
        "model_ja": "天気予報によると、明日は一日中雨が降るらしいです。",
        "model_zh": "听天气预报说明天会下一整天雨。",
        "coaching_tip": "传闻「らしい」直接接简体，前面绝对不要多加「と」或「だ」。",
    },
    "ことにする": {
        "prompt_ja": "健康のために、これから毎日少しずつ運動しようと自分で決めたことを、どう話しますか。",
        "prompt_zh": "场景：为了健康自己决定每天运动一点，用「〜ことにした／ことにしている」说一句。",
        "target_stems": ["ことにし", "ことにする", "ことにします"],
        "model_ja": "健康のために、毎日三十分は運動をすることにしました。",
        "model_zh": "为了健康，我决定每天至少运动三十分钟。",
        "coaching_tip": "动词原形不能直接撞「にする」，中间一定垫住「こと」（することにしました）。",
    },
    "ことになる": {
        "prompt_ja": "会社の都合で、来年から東京で働くことが決まったと友達に報告するならどう言いますか。",
        "prompt_zh": "场景：客观安排下来「明年要去东京工作」，用「〜ことになった」说一句。",
        "target_stems": ["ことにな", "ことになる", "ことになります"],
        "model_ja": "来年から東京のオフィスで働くことになりました。",
        "model_zh": "定下来明年起要去东京办公室工作了。",
        "coaching_tip": "外部或公司定下的决定用「〜ことになりました」，同样别漏中间的「こと」。",
    },
    "ようとする": {
        "prompt_ja": "ちょうど家を出ようとした瞬間に雨が降り出した場面を、日本語で言ってみましょう。",
        "prompt_zh": "场景：正准备出门那一刻下起雨来，用「〜ようとした時」说一句。",
        "target_stems": ["ようとした", "おうとした", "こうとした", "そうとした", "とうとした", "のうとした", "もうとした", "ろうとした", "ようとして"],
        "model_ja": "家を出ようとした時、急に雨が降り出しました。",
        "model_zh": "正准备出门的时候，突然下起雨来了。",
        "coaching_tip": "意志形接「とした時」，别漏中间的「と」，也别在「時」前面多加「の」。",
    },
    "がち": {
        "prompt_ja": "忙しいとつい運動をサボったり、約束を忘れたりしやすい自分のクセをどう言いますか。",
        "prompt_zh": "场景：一忙起来就容易忘记或偷懒，用「〜がち」说一句。",
        "target_stems": ["がち"],
        "model_ja": "仕事が忙しいと、つい運動をサボりがちになります。",
        "model_zh": "工作一忙起来，就不知不觉容易偷懒不运动。",
        "coaching_tip": "动词ます形去ます或名词直接接「がち」，表示反复出现的消极倾向。",
    },
    "気味": {
        "prompt_ja": "最近ちょっと疲れていたり、風邪を引きかけていたりするとき、控えめにどう伝えますか。",
        "prompt_zh": "场景：觉得自己有点累或有点要感冒，用「〜気味」说一句。",
        "target_stems": ["気味", "ぎみ"],
        "model_ja": "今週はずっと忙しくて、少し疲れ気味です。",
        "model_zh": "这周一直很忙，感觉有点累了。",
        "coaching_tip": "「疲れ気味／風邪気味」形容当下刚冒头的一点点身体或状态苗头。",
    },
    "ながらも": {
        "prompt_ja": "体に良くないと分かっていながら、つい夜更かししてしまうことをどう言いますか。",
        "prompt_zh": "场景：明知道熬夜不好却还是忍不住晚睡，用「〜ながらも」说一句。",
        "target_stems": ["ながらも", "ながら"],
        "model_ja": "体に良くないと知りながらも、つい夜更かししてしまいます。",
        "model_zh": "明知道对身体不好，还是忍不住熬夜。",
        "coaching_tip": "动词ます形去ます＋ながらも，表示「虽然心里明白…但还是…」。",
    },
    "うえで": {
        "prompt_ja": "よく調べたあとで決めたいと相手に伝えるとき、丁寧な日本語でどう言いますか。",
        "prompt_zh": "场景：想仔细调查完再做决定，用「〜たうえで」说一句。",
        "target_stems": ["うえで", "上で"],
        "model_ja": "内容をよく確認したうえで、明日お返事します。",
        "model_zh": "仔细确认完内容之后，我明天再回复您。",
        "coaching_tip": "动词た形或名词＋の＋うえで，表示先做完前置功课再进入下一步。",
    },
    "おかげで": {
        "prompt_ja": "毎日少しずつ続けたから前より聞き取れるようになった、と感謝を込めて言ってみましょう。",
        "prompt_zh": "场景：多亏每天听一点，现在比以前听得懂了，用「〜おかげで」说一句。",
        "target_stems": ["おかげで", "お陰で"],
        "model_ja": "毎日ラジオを聴いたおかげで、前よりずっと聞き取れるようになりました。",
        "model_zh": "多亏每天听播客，比以前听得懂多了。",
        "coaching_tip": "好结果归功于某事用「おかげで」，顺手用上「ずっと」表示差距大。",
    },
    "せいで": {
        "prompt_ja": "昨日あまり寝られなかったせいで今日は眠い、とカジュアルに話すならどう言いますか。",
        "prompt_zh": "场景：都怪昨晚没睡好今天很困，用「〜せいで」说一句。",
        "target_stems": ["せいで", "せいだ", "せいです"],
        "model_ja": "昨日あまり寝られなかったせいで、今日は少し眠いです。",
        "model_zh": "都怪昨晚没怎么睡好，今天有点困。",
        "coaching_tip": "坏结果归咎原因用「せいで」，名词接「のせいで」、动词直接简体接。",
    },
    "ざるを得ない": {
        "prompt_ja": "本当は行きたかったのに、急な仕事が入って諦めるしかないとき、どう言いますか。",
        "prompt_zh": "场景：本来想去但突发工作只能放弃，用「〜ざるを得ない」说一句。",
        "target_stems": ["ざるを得ない", "ざるをえない", "ざるを得ません", "ざるをえません", "ざるを得なかった"],
        "model_ja": "急な仕事が入ったので、今回は諦めざるを得ません。",
        "model_zh": "突然插进来工作，这次只好放弃了。",
        "coaching_tip": "动词ない形去ない＋ざるを得ない（する变せざるを得ない），语气偏正式无奈。",
    },
    "わけにはいかない": {
        "prompt_ja": "もうすぐ大事な本番なので、ここで休むわけにはいかないと言いたいとき、どう言いますか。",
        "prompt_zh": "场景：快考试了实在不能松懈，用「〜わけにはいかない」说一句。",
        "target_stems": ["わけにはいかない", "わけにはいきません", "わけにいかない"],
        "model_ja": "もうすぐ試験なので、ここで諦めるわけにはいきません。",
        "model_zh": "马上就考试了，现在实在不能放弃。",
        "coaching_tip": "动词原形接「わけにはいかない」，表示情理或责任上绝不允许这样做。",
    },
    "とは限らない": {
        "prompt_ja": "高いものが必ずしも一番良いとは限らない、と自分の意見を言うならどう言いますか。",
        "prompt_zh": "场景：贵的东西未必就是最好的，用「必ずしも〜とは限らない」说一句。",
        "target_stems": ["とは限らない", "とはかぎらない", "とは限りません", "とはかぎりません"],
        "model_ja": "高いものが必ずしも一番良いとは限りません。",
        "model_zh": "贵的东西未必就是最好的。",
        "coaching_tip": "常与「必ずしも」呼应，客观反驳「未必总是那样」。",
    },
    "にもかかわらず": {
        "prompt_ja": "激しい雨が降っているのに、たくさんの人が集まった場面を少し硬めにどう言いますか。",
        "prompt_zh": "场景：尽管下着大雨还是来了很多人，用「〜にもかかわらず」说一句。",
        "target_stems": ["にもかかわらず", "にも関わらず", "にも拘らず"],
        "model_ja": "激しい雨にもかかわらず、大勢の人が集まりました。",
        "model_zh": "尽管下着大雨，还是聚集了很多人。",
        "coaching_tip": "名词直接接「にもかかわらず」（不加だ），表达超出预期的强转折。",
    },
}


def _match_speaking_template(title: str, key: str) -> dict[str, Any] | None:
    stems = _strip_point_stem(title) + _strip_point_stem(key)
    for t_key, tpl in _SPEAKING_TEMPLATES.items():
        if t_key in title or t_key in key:
            return tpl
        for s in stems:
            if t_key == s or t_key in s or s in t_key:
                return tpl
    return None


def build_episode_speaking_prompts(
    story_blocks: list[dict],
    review_items: list[dict],
    max_prompts: int = 2,
) -> list[dict]:
    """
    Build 2 episode-anchored conversational Japanese speaking prompts directly tied
    to today's 60-minute 《锵锵》 stories & target grammar points (works for N3 & N2!).
    """
    grammar_items = [it for it in (review_items or []) if it.get("kind") == "grammar"]
    if not grammar_items:
        return []

    scored: list[tuple[float, dict, dict | None]] = []
    for it in grammar_items:
        title = str(it.get("title") or "")
        key = str(it.get("key") or title)
        tpl = _match_speaking_template(title, key)
        sc = 0.0
        if it.get("is_new_n2"):
            sc += 120.0
        if tpl is not None:
            sc += 60.0
        if it.get("status") in ("red", "orange"):
            sc += 35.0
        elif it.get("status") != "green":
            sc += 20.0
        # Extra boost for high-ROI oral patterns frequently tripped up in live speech
        if any(k in title or k in key for k in ("させてもらう", "ところだった", "わけだ", "はず", "らしい", "ことにする", "ようとする", "に基づいて")):
            sc += 28.0
        scored.append((sc, it, tpl))

    scored.sort(key=lambda x: (-x[0], x[1].get("chapter_idx", 0), x[1].get("id", "")))

    picked: list[tuple[dict, dict | None]] = []
    used_chapters: set[int] = set()
    used_keys: set[str] = set()

    # Pass 1: maximize chapter diversity so both prompts span distinct stories from today's episode
    for _sc, it, tpl in scored:
        if len(picked) >= max_prompts:
            break
        ch = int(it.get("chapter_idx", -1))
        k = str(it.get("key") or it.get("title") or "")
        if ch in used_chapters or k in used_keys:
            continue
        picked.append((it, tpl))
        used_chapters.add(ch)
        used_keys.add(k)

    # Pass 2: backfill if episode had <2 distinct grammar chapters
    for _sc, it, tpl in scored:
        if len(picked) >= max_prompts:
            break
        k = str(it.get("key") or it.get("title") or "")
        if k in used_keys:
            continue
        picked.append((it, tpl))
        used_keys.add(k)

    prompts: list[dict] = []
    for idx, (it, tpl) in enumerate(picked, 1):
        title = _clean_text(str(it.get("title") or ""))
        key = _clean_text(str(it.get("key") or title))
        pid = str(it.get("point_id") or f"SPK{idx}")
        ch_title = _clean_text(str(it.get("chapter_title") or ""))
        story_cue = _clean_text(str(it.get("story_cue") or ""))
        zh = _clean_text(str(it.get("zh") or ""))
        nuance = _clean_text(str(it.get("nuance") or ""))
        ex_ja = _clean_text(str(it.get("ja_example") or ""))
        stems = _strip_point_stem(title) + _strip_point_stem(key)

        if tpl is not None:
            t_stems = list(dict.fromkeys(list(tpl["target_stems"]) + stems))
            prompt_ja = _clean_text(tpl["prompt_ja"])
            prompt_zh = _clean_text(tpl["prompt_zh"])
            model_ja = _clean_text(tpl["model_ja"])
            model_zh = _clean_text(tpl["model_zh"])
            tip = _clean_text(tpl["coaching_tip"])
        else:
            t_stems = list(dict.fromkeys(stems))
            clean_pt = title.replace("〜", "").replace("~", "").strip()
            prompt_ja = _clean_text(f"今日の番組に出てきた「{title}」を使って、自分の生活や仕事のことについて一言いってみましょう。")
            prompt_zh = _clean_text(f"结合今天「{ch_title}」学到的「{title}」（{zh}），用自己的话造一句自然日语。")
            model_ja = ex_ja or _clean_text(f"{clean_pt}を使って話してみます。")
            model_zh = zh or "参考自然表达"
            tip = nuance or f"试着把「{title}」顺口放进完整短句里说出来。"

        prompts.append({
            "id": f"SPK-{pid}",
            "point_id": pid,
            "key": key,
            "title": title,
            "zh": zh,
            "chapter_idx": int(it.get("chapter_idx", 0)),
            "chapter_title": ch_title,
            "story_cue": story_cue,
            "prompt_ja": prompt_ja,
            "prompt_zh": prompt_zh,
            "target_stems": [s for s in t_stems if len(s) >= 2],
            "model_ja": model_ja,
            "model_zh": model_zh,
            "coaching_tip": tip,
            "clip_start": float(it.get("clip_start", 0.0)),
            "clip_end": float(it.get("clip_end", 14.0)),
            "demo_audio": str(it.get("demo_audio") or ""),
            "is_new_n2": bool(it.get("is_new_n2")),
        })

    return prompts


if __name__ == "__main__":
    # Safe backfill for today's already-rendered episode (preserves script_sig & daily_radio.mp3!)
    import sys
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    import immersion_vocab_engine as ive
    import generate_daily_radio as gdr
    from radio_dialogue_bank import SALON_STORIES

    meta_path = os.path.join(AUDIO_DIR, "daily_radio_meta.json")
    hist_path = os.path.join(AUDIO_DIR, "radio_history.json")
    mp3_path = os.path.join(AUDIO_DIR, "daily_radio.mp3")

    meta = json.load(open(meta_path, encoding="utf-8"))
    hist = json.load(open(hist_path, encoding="utf-8"))
    today_str = meta.get("date") or hist.get("last_date") or "2026-11-23"
    story_ids = (hist.get("recent_days") or {}).get(today_str) or []
    by_sid = {s["id"]: s for s in SALON_STORIES}
    stories = [by_sid[sid] for sid in story_ids if sid in by_sid]
    blocks = [
        {
            "chapter": i,
            "id": st["id"],
            "short_tab": st["short_tab"],
            "title": st["title"],
            "point_ids": list(st.get("point_ids") or []),
            "ja_focus": st.get("ja_focus") or "",
            "raw_turns": list(st["turns"]),
        }
        for i, st in enumerate(stories)
    ]
    # Re-apply immersion in dry mode (commit_ledger=False) so {{zh|kana}} bridge tags match the aired episode!
    blocks_imm, rep = ive.apply_immersion_to_stories(
        blocks,
        today_str=today_str,
        salon_stories=SALON_STORIES,
        mandarin_boundary_re=gdr.MANDARIN_BOUNDARY_RE,
        commit_ledger=False,
    )
    items = meta.get("review_items") or build_episode_review_items(
        blocks_imm,
        meta.get("segments") or [],
        meta.get("immersion_vocab") or rep,
        turn_timings=None,
        audio_mp3_path=mp3_path,
        max_total=12,
    )
    speaking_prompts = build_episode_speaking_prompts(blocks_imm, items, max_prompts=2)
    meta["review_items"] = items
    meta["speaking_prompts"] = speaking_prompts
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Enriched {meta_path}: review_items={len(items)}, speaking_prompts={len(speaking_prompts)} (script_sig preserved: {meta.get('script_sig')}):")
    for idx, sp in enumerate(speaking_prompts, 1):
        print(f"  SPK {idx}. [{sp['title']}] ch={sp['chapter_title']} | Q: {sp['prompt_ja']} | A: {sp['model_ja']}")

