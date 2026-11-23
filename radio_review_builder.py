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
    today_str = meta.get("date") or hist.get("last_date") or "2026-11-22"
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
    items = build_episode_review_items(
        blocks_imm,
        meta.get("segments") or [],
        meta.get("immersion_vocab") or rep,
        turn_timings=None,
        audio_mp3_path=mp3_path,
        max_total=12,
    )
    meta["review_items"] = items
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Enriched {meta_path} with {len(items)} contextual review items (script_sig preserved: {meta.get('script_sig')}):")
    for idx, it in enumerate(items, 1):
        print(
            f"  {idx:2d}. [{it['kind']:7s}] {it['title']:14s} | ch={it['chapter_title']} | "
            f"{it['clip_start']:6.1f}s-{it['clip_end']:6.1f}s | {it['context_line'][:44]}"
        )
