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


def _short_zh(s: str, max_chars: int = 16) -> str:
    txt = _clean_text(s)
    # Strip verbose grammar formula prefixes ("名词＋によって ＝ ...") and second half after "；"
    txt = re.split(r"[；;。]", txt)[0].strip()
    if "＝" in txt:
        txt = txt.split("＝", 1)[1].strip()
    elif "=" in txt:
        txt = txt.split("=", 1)[1].strip()
    if len(txt) > max_chars:
        txt = txt[:max_chars].rstrip("，、／/ ") + "…"
    return txt


def _short_ja_example(s: str, stems: list[str], fallback_short: str = "", max_chars: int = 24) -> str:
    txt = _clean_text(s)
    fb = _clean_text(fallback_short)
    if txt and len(txt) <= max_chars and (not fb or re.search(r"[\u4e00-\u9faf]", txt)):
        return txt
    loose_stems = list(dict.fromkeys(stems + [st[:-1] for st in stems if len(st) >= 4]))
    parts = [p.strip("、，。 ") for p in re.split(r"[、，。]", txt) if p.strip("、，。 ")]
    for p in parts:
        if (
            any(st in p for st in loose_stems)
            and 5 <= len(p) <= max_chars
            and (not fb or re.search(r"[\u4e00-\u9faf]", p))
            and not re.search(r"(とともに|によって|かわりに|うえで|最中に|のに|ので|から|が)$", p)
        ):
            return p + "。"
    if fb and len(fb) <= max_chars:
        return fb
    return txt


def build_episode_review_items(
    story_blocks: list[dict],
    segments_meta: list[dict],
    imm_vocab_report: dict,
    turn_timings: dict[tuple[int, int], tuple[float, float]] | None = None,
    audio_mp3_path: str = "",
    max_total: int = 8,
) -> list[dict]:
    """
    Build the concise 8-card Zen Tinder Post-Listening Review deck directly from
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

            short_ex_fallback = ""
            if is_n2:
                key = str(n2g.get("point") or pid)
                title = key
                zh = _short_zh(str(n2g.get("soul_meaning") or ""))
                nuance = _clean_text(f"接续：{n2g.get('connection', '')}。{n2g.get('soul_meaning', '')}")
                twin = _clean_text(str(n2g.get("vs_twin") or ""))
                kind = "grammar"
                ja_fallback = str(blk.get("ja_focus") or "")
            else:
                key = str(c.get("point_key") or c.get("point") or pid).strip()
                raw_disp = str(c.get("point_display") or key).strip()
                title = re.sub(r"[（(][^）)]*[）)]", "", raw_disp).strip() or key
                m_paren = re.search(r"[（(]([^）)]+)[）)]", raw_disp)
                zh = _short_zh(m_paren.group(1) if m_paren else str(c.get("zh_meaning") or c.get("core_rule") or ""))
                nuance = _clean_text(str(c.get("core_rule") or c.get("why_line") or ""))
                tl = c.get("teach_left") or {}
                tr = c.get("teach_right") or {}
                if isinstance(tl, dict) and tl.get("ja"):
                    short_ex_fallback = str(tl["ja"])
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
                    "full_context": readable,
                    "ja_example": _short_ja_example(ja_ex, stems, fallback_short=short_ex_fallback, max_chars=24),
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

    # Select balanced grammar/expression items: guarantee breadth across chapters (1 per chapter, up to 6 for an 8-card Zen deck)
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
    # Fill remaining grammar slots up to max_grammar
    rem_grammar = sorted(
        [(sc, it) for sc, it in grammar_candidates if it["id"] not in picked_ids],
        key=lambda x: (-x[0], x[1]["chapter_idx"], x[1]["id"]),
    )
    max_grammar = min(6, max(4, max_total - 2))
    picked_grammar = picked_grammar[:max_grammar]
    picked_ids = {it["id"] for it in picked_grammar}
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
                "full_context": readable,
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
    vocab_slots = max(2, max_total - len(picked_grammar))
    picked_vocab = [it for _sc, it in vocab_candidates[:vocab_slots]]

    # Order naturally: N2 brand-new grammar first, then chronological podcast story flow!
    combined = picked_grammar + picked_vocab
    combined.sort(key=lambda x: (0 if (x.get("is_new_n2") and x["kind"] == "grammar") else 1, x["chapter_idx"], x["clip_start"]))
    return combined[:max_total]


# ==============================================================================
# Post-Listening Crisp Spoken Prompts (Zen Short-Phrase Output inside Tinder Deck)
# Every prompt stays ultra-brief: 6-10 char Chinese cue + 1 crisp short Japanese sentence.
# ==============================================================================
_SPEAKING_TEMPLATES: dict[str, dict[str, Any]] = {
    "させてもらう": {
        "prompt_short": "让我早点回去",
        "prompt_ja": "早めに帰りたいとき",
        "prompt_zh": "客气请示让我早点回去",
        "target_stems": ["させてもら", "させていただ", "帰らせ", "休ませ", "いかせてもら", "行かせてもら"],
        "model_ja": "早めに帰らせてもらえますか。",
        "model_zh": "能让我早点回去吗？",
        "coaching_tip": "求准许用使役形「帰らせて」",
    },
    "に基づいて": {
        "prompt_short": "根据数据定计划",
        "prompt_ja": "データを使って計画を立てた",
        "prompt_zh": "根据这份数据制定了计划",
        "target_stems": ["に基づいて", "にもとづいて", "に基づき", "にもとづき", "に基づく", "にもとづく"],
        "model_ja": "データに基づいて計画を立てました。",
        "model_zh": "根据数据制定了计划。",
        "coaching_tip": "名词直接接「に基づいて」",
    },
    "ところだった": {
        "prompt_short": "差点错过末班车",
        "prompt_ja": "終電に遅れそうになった",
        "prompt_zh": "差一点没赶上末班车",
        "target_stems": ["ところだった", "ところでした"],
        "model_ja": "もう少しで乗り遅れるところだった。",
        "model_zh": "差一点就误车了。",
        "coaching_tip": "注意浊音「だった」别清化",
    },
    "最中に": {
        "prompt_short": "开会正酣来电话",
        "prompt_ja": "会議の途中で電話が来た",
        "prompt_zh": "正在开会当口来了电话",
        "target_stems": ["最中に", "最中は", "さいちゅうに", "さいちゅうは"],
        "model_ja": "会議の最中に電話が来ました。",
        "model_zh": "正在开会时来了电话。",
        "coaching_tip": "Nの／Vている ＋ 最中に",
    },
    "かわりに": {
        "prompt_short": "不喝咖啡改喝茶",
        "prompt_ja": "コーヒーをやめてお茶にする",
        "prompt_zh": "不喝咖啡，改喝茶",
        "target_stems": ["かわりに", "代わりに", "かわり", "代わり"],
        "model_ja": "コーヒーのかわりにお茶にします。",
        "model_zh": "不喝咖啡改喝茶。",
        "coaching_tip": "名词接「のかわりに」",
    },
    "とともに": {
        "prompt_short": "随技术一起变化",
        "prompt_ja": "技術が進んで働き方が変わった",
        "prompt_zh": "随着技术进步，工作方式变了",
        "target_stems": ["とともに", "と共に"],
        "model_ja": "技術の進歩とともに変わりました。",
        "model_zh": "随着技术进步改变了。",
        "coaching_tip": "名词／原形 ＋ とともに",
    },
    "によって": {
        "prompt_short": "因人而异感想不同",
        "prompt_ja": "人それぞれ感想が違う",
        "prompt_zh": "看的人不同，感想也不同",
        "target_stems": ["によって", "による", "により", "によっては"],
        "model_ja": "見る人によって感想が違います。",
        "model_zh": "看的人不同感想也不同。",
        "coaching_tip": "因人而异用「人によって」",
    },
    "につれて": {
        "prompt_short": "临近考试越紧张",
        "prompt_ja": "試験が近づいて緊張してきた",
        "prompt_zh": "越临近考试越紧张",
        "target_stems": ["につれて", "につれ"],
        "model_ja": "試験が近づくにつれて緊張します。",
        "model_zh": "越临近考试越紧张。",
        "coaching_tip": "动词原形 ＋ につれて",
    },
    "わけだ": {
        "prompt_short": "难怪日语这么好",
        "prompt_ja": "十年住んでいたから上手なんだ",
        "prompt_zh": "难怪日语这么好",
        "target_stems": ["わけだ", "わけです", "わけですね", "わけだね"],
        "model_ja": "だから日本語が上手なわけですね。",
        "model_zh": "难怪日语这么好啊。",
        "coaching_tip": "ナ形接わけ别漏「な」",
    },
    "わけではない": {
        "prompt_short": "倒也不是讨厌甜食",
        "prompt_ja": "甘いものが嫌いじゃないけど控えている",
        "prompt_zh": "并不是讨厌甜食",
        "target_stems": ["わけではない", "わけではありません", "わけじゃない", "わけじゃありません"],
        "model_ja": "甘いものが嫌いなわけではないです。",
        "model_zh": "倒也不是讨厌甜食。",
        "coaching_tip": "ナ形接わけ保留「な」",
    },
    "はずだ": {
        "prompt_short": "刚才应该点过咖啡",
        "prompt_ja": "さっきコーヒーを頼んだと思う",
        "prompt_zh": "刚才应该点过咖啡来着",
        "target_stems": ["はずなん", "はずだ", "はずです", "はずで"],
        "model_ja": "さっきコーヒーを頼んだはずなんですが。",
        "model_zh": "我刚才应该点过咖啡来着。",
        "coaching_tip": "盯紧「はずなんですが」别滑成ない",
    },
    "らしい": {
        "prompt_short": "听说明天会下雨",
        "prompt_ja": "明日は雨だと聞いた",
        "prompt_zh": "听说明天会下雨",
        "target_stems": ["らしい"],
        "model_ja": "明日は雨が降るらしいです。",
        "model_zh": "听说明天会下雨。",
        "coaching_tip": "直接接简体，不加「と／だ」",
    },
    "ことにする": {
        "prompt_short": "决定每天运动一下",
        "prompt_ja": "毎日運動しようと決めた",
        "prompt_zh": "自己决定每天运动",
        "target_stems": ["ことにし", "ことにする", "ことにします"],
        "model_ja": "毎日運動することにしました。",
        "model_zh": "我决定每天运动。",
        "coaching_tip": "中间垫住「こと」",
    },
    "ことになる": {
        "prompt_short": "定下来要去东京",
        "prompt_ja": "来年から東京で働くことが決まった",
        "prompt_zh": "定下来明年去东京工作",
        "target_stems": ["ことにな", "ことになる", "ことになります"],
        "model_ja": "来年東京で働くことになりました。",
        "model_zh": "定下来明年去东京工作。",
        "coaching_tip": "客观决定用「ことになった」",
    },
    "ようとする": {
        "prompt_short": "刚要出门就下雨",
        "prompt_ja": "家を出る瞬間に雨が降った",
        "prompt_zh": "正准备出门就下起雨来",
        "target_stems": ["ようとした", "おうとした", "こうとした", "そうとした", "とうとした", "のうとした", "もうとした", "ろうとした", "ようとして"],
        "model_ja": "家を出ようとした時、雨が降りました。",
        "model_zh": "刚要出门就下雨了。",
        "coaching_tip": "「時」前面别多加「の」",
    },
    "がち": {
        "prompt_short": "一忙就容易忘事",
        "prompt_ja": "忙しいと忘れやすい",
        "prompt_zh": "一忙就容易忘记",
        "target_stems": ["がち"],
        "model_ja": "忙しいと約束を忘れがちです。",
        "model_zh": "一忙就容易忘约定。",
        "coaching_tip": "去ます形／名词 ＋ がち",
    },
    "気味": {
        "prompt_short": "最近感觉有点累",
        "prompt_ja": "最近ちょっと疲れている",
        "prompt_zh": "最近稍微有点累",
        "target_stems": ["気味", "ぎみ"],
        "model_ja": "最近ちょっと疲れ気味です。",
        "model_zh": "最近有点累。",
        "coaching_tip": "疲れ気味／風邪気味",
    },
    "ながらも": {
        "prompt_short": "明知不好还熬夜",
        "prompt_ja": "体に悪いと分かっていて夜更かしする",
        "prompt_zh": "明知不好还是忍不住熬夜",
        "target_stems": ["ながらも", "ながら"],
        "model_ja": "悪いと知りながらも夜更かしします。",
        "model_zh": "明知不好还是会熬夜。",
        "coaching_tip": "去ます形 ＋ ながらも",
    },
    "うえで": {
        "prompt_short": "确认完之后再回复",
        "prompt_ja": "よく確認してから返事する",
        "prompt_zh": "确认完内容后再回复",
        "target_stems": ["うえで", "上で"],
        "model_ja": "確認したうえで、お返事します。",
        "model_zh": "确认完之后再回复。",
        "coaching_tip": "动词た形 ＋ うえで",
    },
    "おかげで": {
        "prompt_short": "多亏每天听一点",
        "prompt_ja": "毎日聴いたから聞き取れるようになった",
        "prompt_zh": "多亏每天听，能听懂了",
        "target_stems": ["おかげで", "お陰で"],
        "model_ja": "毎日聴いたおかげで聞き取れます。",
        "model_zh": "多亏每天听，能听懂了。",
        "coaching_tip": "好结果归功于「おかげで」",
    },
    "せいで": {
        "prompt_short": "都怪昨晚没睡好",
        "prompt_ja": "昨日寝られなくて眠い",
        "prompt_zh": "都怪没睡好今天很困",
        "target_stems": ["せいで", "せいだ", "せいです"],
        "model_ja": "寝られなかったせいで眠いです。",
        "model_zh": "都怪没睡好现在很困。",
        "coaching_tip": "坏结果用「せいで」",
    },
    "ざるを得ない": {
        "prompt_short": "这次只好放弃了",
        "prompt_ja": "急な仕事で諦めるしかない",
        "prompt_zh": "没办法这次只好放弃",
        "target_stems": ["ざるを得ない", "ざるをえない", "ざるを得ません", "ざるをえません", "ざるを得なかった"],
        "model_ja": "今回は諦めざるを得ません。",
        "model_zh": "这次只好放弃了。",
        "coaching_tip": "ない形去ない ＋ ざるを得ない",
    },
    "わけにはいかない": {
        "prompt_short": "现在实在不能放弃",
        "prompt_ja": "大事な本番なので諦められない",
        "prompt_zh": "现在实在不能放弃",
        "target_stems": ["わけにはいかない", "わけにはいきません", "わけにいかない"],
        "model_ja": "ここで諦めるわけにはいきません。",
        "model_zh": "现在实在不能放弃。",
        "coaching_tip": "动词原形 ＋ わけにはいかない",
    },
    "とは限らない": {
        "prompt_short": "贵的未必最好",
        "prompt_ja": "高いものが一番良いとは言い切れない",
        "prompt_zh": "贵的东西未必最好",
        "target_stems": ["とは限らない", "とはかぎらない", "とは限りません", "とはかぎりません"],
        "model_ja": "高いものが良いとは限りません。",
        "model_zh": "贵的东西未必最好。",
        "coaching_tip": "常配「必ずしも〜とは限らない」",
    },
    "にもかかわらず": {
        "prompt_short": "尽管大雨还是来了",
        "prompt_ja": "大雨なのにみんな集まった",
        "prompt_zh": "尽管下大雨大家还是来了",
        "target_stems": ["にもかかわらず", "にも関わらず", "にも拘らず"],
        "model_ja": "大雨にもかかわらず集まりました。",
        "model_zh": "尽管下大雨还是聚集起来了。",
        "coaching_tip": "名词直接接「にもかかわらず」",
    },
    "しかない": {
        "prompt_short": "没办法只好合作",
        "prompt_ja": "ほかに方法がないので協力する",
        "prompt_zh": "别无选择，只好互相合作",
        "target_stems": ["しかない", "しか無い", "しかありません", "しかなかった", "しかなく"],
        "model_ja": "お互いに協力するしかないです。",
        "model_zh": "只好互相配合了。",
        "coaching_tip": "动词原形直接接「しかない」",
    },
    "ようになる": {
        "prompt_short": "渐渐能听懂日语",
        "prompt_ja": "前より日本語が聞き取れる",
        "prompt_zh": "慢慢变得能听懂日语了",
        "target_stems": ["ようになる", "ようになった", "ようになります", "ようになりました", "ようになって"],
        "model_ja": "少しずつ聞き取れるようになりました。",
        "model_zh": "渐渐变得能听懂了。",
        "coaching_tip": "可能形 ＋ ようになる",
    },
    "さえ": {
        "prompt_short": "忙到连午饭没空吃",
        "prompt_ja": "忙しくて昼ご飯も食べられない",
        "prompt_zh": "忙得连吃午饭的时间都没有",
        "target_stems": ["さえ"],
        "model_ja": "昼ご飯を食べる時間さえないです。",
        "model_zh": "连吃午饭的时间都没有。",
        "coaching_tip": "名词直接接「さえ」举极端例子",
    },
    "だらけ": {
        "prompt_short": "房间里满是灰尘",
        "prompt_ja": "部屋にほこりがたくさんある",
        "prompt_zh": "房间里满是灰尘",
        "target_stems": ["だらけ"],
        "model_ja": "この部屋はほこりだらけです。",
        "model_zh": "这房间满是灰尘。",
        "coaching_tip": "名词 ＋ だらけ，多带嫌弃语气",
    },
    "てばかりいる": {
        "prompt_short": "光顾着刷手机了",
        "prompt_ja": "最近スマホばかり見ている",
        "prompt_zh": "最近老是光顾着刷手机",
        "target_stems": ["てばかりい", "でばかりい", "てばかり"],
        "model_ja": "最近スマホを見てばかりいます。",
        "model_zh": "最近老是光顾着看手机。",
        "coaching_tip": "反复只做某事用「てばかりいる」，别跟「たばかり」混",
    },
    "きる": {
        "prompt_short": "这本厚书两天读完",
        "prompt_ja": "分厚い本を二日で全部読んだ",
        "prompt_zh": "把这本厚书一口气全读完了",
        "target_stems": ["きった", "きりました", "きれない", "きれません", "きる", "きれる"],
        "model_ja": "分厚い本を二日で読み切りました。",
        "model_zh": "两天把厚书全部读完了。",
        "coaching_tip": "去ます形 ＋ きる（彻底完成）／きれない（做不完）",
    },
    "ほど": {
        "prompt_short": "今年没去年那么热",
        "prompt_ja": "去年のほうが今年より暑かった",
        "prompt_zh": "今年没有去年那么热",
        "target_stems": ["ほど", "ほど〜ない"],
        "model_ja": "今年は去年ほど暑くないです。",
        "model_zh": "今年没有去年那么热。",
        "coaching_tip": "「Bほど〜ない」配否定，别误用「より」",
    },
    "ような気がする": {
        "prompt_short": "总觉得以前见过面",
        "prompt_ja": "前にも会ったことがある気がする",
        "prompt_zh": "总觉得在哪里见过您",
        "target_stems": ["ような気がし", "ような気がする", "ような気がします"],
        "model_ja": "どこかで会ったような気がします。",
        "model_zh": "总觉得在哪里见过。",
        "coaching_tip": "简体 ＋ ような気がする（直觉隐约觉得）",
    },
    "からこそ": {
        "prompt_short": "正因为难才值得做",
        "prompt_ja": "難しいからやりがいがある",
        "prompt_zh": "正因为有难度才值得去做",
        "target_stems": ["からこそ"],
        "model_ja": "難しいからこそ、やりがいがあります。",
        "model_zh": "正因为难才更有成就感。",
        "coaching_tip": "简体／名词だ ＋ からこそ（强调唯一原因）",
    },
    "てもかまわない": {
        "prompt_short": "迟到几分钟没关系",
        "prompt_ja": "少し遅れても大丈夫です",
        "prompt_zh": "稍微晚到一会儿也没关系",
        "target_stems": ["てもかまわない", "てもかまいません", "ても構わない", "ても構いません", "でもかまわない"],
        "model_ja": "少し遅れてもかまいません。",
        "model_zh": "稍微晚一点也没关系。",
        "coaching_tip": "て形 ＋ もかまわない（口语礼貌放行）",
    },
    "にしたがって": {
        "prompt_short": "越往山顶走越凉快",
        "prompt_ja": "山を登るほど涼しくなった",
        "prompt_zh": "随着往山上走，越来越凉快",
        "target_stems": ["にしたがって", "に従って", "にしたがい", "に従い"],
        "model_ja": "山を登るにしたがって涼しくなります。",
        "model_zh": "随着爬山变凉快了。",
        "coaching_tip": "动词原形／名词 ＋ にしたがって",
    },
    "に限る": {
        "prompt_short": "累时早点睡觉最好",
        "prompt_ja": "疲れた時は早く寝るのが一番だ",
        "prompt_zh": "累的时候还是早睡最好",
        "target_stems": ["に限る", "にかぎる", "に限ります", "にかぎります"],
        "model_ja": "疲れた時は早く寝るに限ります。",
        "model_zh": "累的时候还是早睡最管用。",
        "coaching_tip": "名词／原形 ＋ に限る（个人力推最佳选）",
    },
    "にくい": {
        "prompt_short": "这个生词不太好读",
        "prompt_ja": "この言葉は発音するのが難しい",
        "prompt_zh": "这个词发起来有点拗口",
        "target_stems": ["にくい", "にくかった", "にくいです"],
        "model_ja": "この言葉は少し発音しにくいです。",
        "model_zh": "这个词稍微有点难读。",
        "coaching_tip": "去ます形 ＋ にくい（别读成苦い にがい）",
    },
    "てもらう": {
        "prompt_short": "承蒙当地朋友带路",
        "prompt_ja": "地元の友達が町を案内してくれた",
        "prompt_zh": "让当地的朋友带我逛了逛",
        "target_stems": ["てもらった", "てもらいました", "ていただいた", "ていただきました", "てもらう"],
        "model_ja": "地元の友達に案内してもらいました。",
        "model_zh": "请当地朋友带我逛了逛。",
        "coaching_tip": "受益视角用「人＋に＋Vてもらう」",
    },
    "させられる": {
        "prompt_short": "会上被点名发了言",
        "prompt_ja": "会議で急に意見を言うことになった",
        "prompt_zh": "在会上被要求突然发言了",
        "target_stems": ["させられた", "させられました", "させられる", "わされた", "わされました"],
        "model_ja": "会議で急に話させられました。",
        "model_zh": "在会上被迫突然发言了。",
        "coaching_tip": "す结尾动词绝不缩约，必说「話させられる」",
    },
    "お〜になる": {
        "prompt_short": "部长已经看过邮件吗",
        "prompt_ja": "部長はもうメールを見ましたか",
        "prompt_zh": "礼貌问部长是否已看过邮件",
        "target_stems": ["お読みにな", "お聞きにな", "ご覧にな", "お越しにな", "お帰りにな"],
        "model_ja": "部長はもうメールをお読みになりましたか。",
        "model_zh": "部长已经看过邮件了吗？",
        "coaching_tip": "尊敬语「お＋去ます形＋になる」不加「に」以外乱变",
    },
    "にしては": {
        "prompt_short": "按初学来说讲得真好",
        "prompt_ja": "まだ半年しか勉強していないのに上手だ",
        "prompt_zh": "按才学半年来说日语说得真地道",
        "target_stems": ["にしては"],
        "model_ja": "半年にしては、すごく上手ですね。",
        "model_zh": "按才学半年来说，说得真不错呢。",
        "coaching_tip": "和「にとって（对…而言）」区分，超出标准才用「にしては」",
    },
    "てたまらない": {
        "prompt_short": "夏天热得实在受不了",
        "prompt_ja": "今日はすごく暑くて我慢できない",
        "prompt_zh": "今天实在热得受不了",
        "target_stems": ["たまらない", "たまりません"],
        "model_ja": "今日は暑くてたまらないですね。",
        "model_zh": "今天真是热得受不了啊。",
        "coaching_tip": "前面接て形，别说成「かまわない（不要紧）」",
    },
    "ように言う": {
        "prompt_short": "医生叮嘱我早点睡",
        "prompt_ja": "医者に早く寝てと言われた",
        "prompt_zh": "医生叮嘱我要早点睡觉",
        "target_stems": ["ように言", "ようにい", "ように注意"],
        "model_ja": "医者に早く寝るように言われました。",
        "model_zh": "医生叮嘱我要早点睡。",
        "coaching_tip": "转述叮嘱用「V辞書形＋ように言う」，不是「ことに言う」",
    },
    "ところだ": {
        "prompt_short": "现在正要出门去车站",
        "prompt_ja": "今ちょうど家を出る直前です",
        "prompt_zh": "现在正准备出门",
        "target_stems": ["ところだ", "ところです", "ところでした"],
        "model_ja": "今ちょうど家を出るところです。",
        "model_zh": "现在正要出门呢。",
        "coaching_tip": "「出るところ」是正要出门，「出たばかり」才是刚出门",
    },
    "っぽい": {
        "prompt_short": "他说话有点孩子气",
        "prompt_ja": "彼の発言は少し子どものようだ",
        "prompt_zh": "觉得他说话有点孩子气",
        "target_stems": ["っぽい", "っぽく", "っぽかった"],
        "model_ja": "言い方が少し子どもっぽいですね。",
        "model_zh": "说话方式有点孩子气呢。",
        "coaching_tip": "带主观印象或略贬色彩用「っぽい」，正面典型才用「らしい」",
    },
    "ことから": {
        "prompt_short": "因外形得名的经典故事",
        "prompt_ja": "形が似ているのでその名前がついた",
        "prompt_zh": "因为外形相似而得了这个名字",
        "target_stems": ["ことから"],
        "model_ja": "形が似ていることから、その名がつきました。",
        "model_zh": "因为形状相似，才得了这个名字。",
        "coaching_tip": "表命名由来或判断依据用「ことから」，别混成「にもかかわらず」",
    },
    "というより": {
        "prompt_short": "与其说难不如说太繁琐",
        "prompt_ja": "難しいというより手順が多すぎる",
        "prompt_zh": "与其说难，不如说步骤太繁琐",
        "target_stems": ["というより"],
        "model_ja": "難しいというより、手順が多いですね。",
        "model_zh": "与其说难，不如说步骤多。",
        "coaching_tip": "否定前项更贴切改口用「というより」",
    },
    "にかけて": {
        "prompt_short": "从明早到中午一直下雨",
        "prompt_ja": "明日の朝から昼まで雨が続く",
        "prompt_zh": "从明早到中午断续有雨",
        "target_stems": ["にかけて"],
        "model_ja": "明日の朝から昼にかけて雨が降るそうです。",
        "model_zh": "听说从明早到中午会下雨。",
        "coaching_tip": "时间空间跨度用「〜から〜にかけて」，别混成「について」",
    },
    "たとたん": {
        "prompt_short": "一推开门冷风就灌进来",
        "prompt_ja": "ドアを開けた瞬間に冷たい風が入った",
        "prompt_zh": "一开门冷风一下子就吹进来了",
        "target_stems": ["たとたん", "た途端"],
        "model_ja": "ドアを開けたとたん、冷たい風が入ってきました。",
        "model_zh": "刚一开门，冷风就灌进来了。",
        "coaching_tip": "「Vた＋とたん」表瞬间突发意外，后句不可用意志表达",
    },
    "ばかりか": {
        "prompt_short": "不光会说日语还会做菜",
        "prompt_ja": "日本語だけでなく和食も上手に作れる",
        "prompt_zh": "不光会日语，连日料都会做",
        "target_stems": ["ばかりか", "ばかりでなく"],
        "model_ja": "日本語ばかりか、和食まで作れるんです。",
        "model_zh": "不仅会日语，连和食都能做呢。",
        "coaching_tip": "递进「〜ばかりか、〜まで」常成对呼应",
    },
    "にちがいない": {
        "prompt_short": "看灯光他肯定还没睡",
        "prompt_ja": "部屋の明かりがついているから起きているはずだ",
        "prompt_zh": "灯还亮着，他肯定还没睡",
        "target_stems": ["にちがいない", "に違いない", "ちがいない"],
        "model_ja": "まだ起きているにちがいありません。",
        "model_zh": "他肯定还醒着呢。",
        "coaching_tip": "强把握断定「肯定没错」用「にちがいない」，反义才是「はずがない」",
    },
    "たとえ〜ても": {
        "prompt_short": "就算下大雨也照常出发",
        "prompt_ja": "もし大雨が降っても予定通り出発する",
        "prompt_zh": "就算下大雨也要按计划出发",
        "target_stems": ["たとえ", "ても"],
        "model_ja": "たとえ雨が降っても、予定通り出発します。",
        "model_zh": "就算下雨，我也按计划出发。",
        "coaching_tip": "「たとえ」后面必配「〜ても／〜でも」遥相呼应",
    },
    "たものだ": {
        "prompt_short": "小时候常去河边玩",
        "prompt_ja": "子どものころ、よく川で遊んでいた",
        "prompt_zh": "怀念小时候常去河边玩",
        "target_stems": ["たものだ", "たものです"],
        "model_ja": "子どものころ、よく川で遊んだものです。",
        "model_zh": "小时候常常去河边玩啊。",
        "coaching_tip": "怀念过去习惯用「Vた＋ものだ」，别说成「だところだ」",
    },
    "しだい": {
        "prompt_short": "结果一出来立刻通知您",
        "prompt_ja": "結果が分かったらすぐ連絡します",
        "prompt_zh": "结果一明朗就立刻联系您",
        "target_stems": ["しだい", "次第"],
        "model_ja": "結果が分かりしだい、すぐご連絡します。",
        "model_zh": "结果一出来就立刻联系您。",
        "coaching_tip": "接动词ます词干（分かり＋しだい），绝不接た形",
    },
    "ということだ": {
        "prompt_short": "听说下周新店就要开业",
        "prompt_ja": "来週新しい店が開くらしい",
        "prompt_zh": "听说下周那家新店就要开业了",
        "target_stems": ["ということだ", "ということです", "とのことだ"],
        "model_ja": "来週、新しい店が開くということです。",
        "model_zh": "听说下周新店就要开业了。",
        "coaching_tip": "正式传闻「听说…」用「简体＋ということだ」",
    },
    "をはじめ": {
        "prompt_short": "以京都为首遍布古寺",
        "prompt_ja": "京都を代表として関西には古い寺が多い",
        "prompt_zh": "以京都为首，关西有很多古寺",
        "target_stems": ["をはじめ", "を始め"],
        "model_ja": "京都をはじめ、関西には古いお寺が多いです。",
        "model_zh": "以京都为首，关西有很多古老的寺庙。",
        "coaching_tip": "举最有代表性的首例用「N＋をはじめ」",
    },
    "せっかく〜のに": {
        "prompt_short": "好不容易来一趟却下雨了",
        "prompt_ja": "わざわざ来たのに雨が降ってしまった",
        "prompt_zh": "好不容易来一趟，结果下雨了真可惜",
        "target_stems": ["せっかく", "のに"],
        "model_ja": "せっかく来たのに、雨が降ってしまいました。",
        "model_zh": "好不容易来一趟，居然下起雨来了。",
        "coaching_tip": "「せっかく＋〜のに」表达白费一番心血的惋惜",
    },
    "ことはない": {
        "prompt_short": "没必要为小事一直担心",
        "prompt_ja": "そんな小さなことを心配する必要はない",
        "prompt_zh": "没必要为那么点小事担心",
        "target_stems": ["ことはない", "ことはありません"],
        "model_ja": "そんなに心配することはありませんよ。",
        "model_zh": "没必要那么担心哦。",
        "coaching_tip": "「V辞書形＋ことはない」意为「没必要」，不是「不可能」",
    },
    "ばかりに": {
        "prompt_short": "只因睡过头错过了末班车",
        "prompt_ja": "寝坊したせいで大事な会議に遅れた",
        "prompt_zh": "只因为睡过头，结果重要会议迟到了",
        "target_stems": ["ばかりに"],
        "model_ja": "寝坊したばかりに、大事な会議に遅れました。",
        "model_zh": "就因为睡过头，害得重要会议迟到了。",
        "coaching_tip": "只因单一过失酿成糟糕后果，用「〜ばかりに」",
    },
    "まるで〜のように": {
        "prompt_short": "今天暖和得简直像春天",
        "prompt_ja": "今日は冬なのに春みたいに暖かい",
        "prompt_zh": "今天暖和得简直像春天一样",
        "target_stems": ["まるで", "のように", "みたいに"],
        "model_ja": "今日はまるで春のように暖かいですね。",
        "model_zh": "今天暖和得简直像春天一样呢。",
        "coaching_tip": "「まるで＋Nのように」表夸张比喻，别混成「のために」",
    },
}


def _expand_conjugation_stems(stems: list[str]) -> list[str]:
    """Expand dictionary-form grammar stems to natural spoken conjugations & Kanji/Kana variants."""
    out: list[str] = []
    for raw in stems:
        s = str(raw or "").strip()
        if not s:
            continue
        out.append(s)
        if s.endswith("なる"):
            base = s[:-2]
            out.extend([base + "なった", base + "なります", base + "なりました", base + "なって"])
        elif s.endswith("する"):
            base = s[:-2]
            out.extend([base + "した", base + "します", base + "しました", base + "して"])
        elif s.endswith("ない"):
            base = s[:-2]
            out.extend([base + "ありません", base + "なかった", base + "ありませんでした", base + "なく"])
        elif s.endswith("だ"):
            base = s[:-1]
            out.extend([base + "です", base + "だった", base + "でした", base + "ですね", base + "だね"])
        elif s.endswith("もらう"):
            base = s[:-3]
            out.extend([base + "もらえ", base + "もらった", base + "もらいます", base + "いただき", base + "いただけ"])
        if "うえで" in s:
            out.append(s.replace("うえで", "上で"))
        if "上で" in s:
            out.append(s.replace("上で", "うえで"))
        if "につれて" in s:
            out.extend([s.replace("につれて", "に連れて"), s.replace("につれて", "につれ")])
        if "かわりに" in s:
            out.append(s.replace("かわりに", "代わりに"))
        if "とともに" in s:
            out.append(s.replace("とともに", "と共に"))
    return list(dict.fromkeys(x for x in out if x))


def _match_speaking_template(title: str, key: str) -> dict[str, Any] | None:
    stems = _strip_point_stem(title) + _strip_point_stem(key)
    for t_key, tpl in _SPEAKING_TEMPLATES.items():
        if t_key in title or t_key in key:
            return tpl
        for s in stems:
            if t_key == s or t_key in s or s in t_key:
                return tpl
    return None


def _load_speaking_adaptive_signals() -> tuple[set[str], set[str]]:
    """Load unresolved speaking slips & active confusion-pair grammar keys from n3_live_state.json (zero-PII)."""
    slips: set[str] = set()
    confs: set[str] = set()
    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
            for k in ((st.get("speaking_practice") or {}).get("slips") or {}).keys():
                if k:
                    slips.add(str(k).strip())
            for k in (st.get("confusion_pairs") or {}).keys():
                if k:
                    confs.add(str(k).strip())
        except Exception:
            pass
    return slips, confs


def build_episode_speaking_prompts(
    story_blocks: list[dict],
    review_items: list[dict],
    max_prompts: int = 2,
) -> list[dict]:
    """
    Build 2 crisp episode-anchored speaking prompt cards directly tied to today's
    40-minute 《锵锵》 stories, unresolved speaking slips, and active confusion pairs (works for N3 & N2).
    """
    grammar_items = [it for it in (review_items or []) if it.get("kind") == "grammar"]
    if not grammar_items:
        return []

    spk_slips, active_confs = _load_speaking_adaptive_signals()
    mastery_map = _load_mastery_status()

    scored: list[tuple[float, dict, dict | None]] = []
    for it in grammar_items:
        title = str(it.get("title") or "")
        key = str(it.get("key") or title)
        tpl = _match_speaking_template(title, key)
        sc = 0.0
        if it.get("is_new_n2"):
            sc += 120.0
        if key in spk_slips or title in spk_slips:
            sc += 75.0
        if key in active_confs or title in active_confs:
            sc += 45.0
        if tpl is not None:
            sc += 60.0
        if it.get("status") in ("red", "orange"):
            sc += 35.0
        elif it.get("status") != "green":
            sc += 20.0
        if any(
            k in title or k in key
            for k in (
                "させてもらう", "させられる", "ところだった", "わけだ", "はず", "らしい",
                "ことにする", "ようとする", "に基づいて", "てばかり", "きる", "がち",
                "気味", "にくい", "てもらう", "からこそ", "ほど", "に限る", "敬語", "お〜になる",
            )
        ):
            sc += 28.0
        scored.append((sc, it, tpl))

    # Rescue slot: if learner has an unresolved speaking slip or active confusion pair with a gold template
    # that did NOT happen to appear in today's pre-authored stories, allow slot #2 to bring it back for redemption!
    in_episode_keys = {str(it.get("key") or it.get("title") or "") for it in grammar_items}
    rescue_candidates: list[tuple[float, dict, dict]] = []
    for cand_key in list(spk_slips) + list(active_confs):
        if not cand_key or cand_key in in_episode_keys:
            continue
        st_val, _streak = mastery_map.get(cand_key, ("red", 0))
        if st_val == "green" and cand_key not in spk_slips:
            continue
        tpl = _match_speaking_template(cand_key, cand_key)
        if tpl is None:
            continue
        r_sc = 115.0 if cand_key in spk_slips else 95.0
        if st_val in ("red", "orange"):
            r_sc += 25.0
        synth_it = {
            "id": f"RVR-SLIP-{abs(hash(cand_key)) % 9999}",
            "kind": "grammar",
            "key": cand_key,
            "point_id": f"SLIP-{len(rescue_candidates) + 1}",
            "title": cand_key,
            "zh": str(tpl.get("prompt_short") or ""),
            "chapter_idx": 99,
            "chapter_title": "昨日错点补练" if cand_key in active_confs else "开口回炉",
            "story_cue": "把上次卡壳的句型亲口说顺",
            "ja_example": str(tpl.get("model_ja") or ""),
            "clip_start": 0.0,
            "clip_end": 12.0,
            "demo_audio": "",
            "is_new_n2": False,
            "img": str((grammar_items[0] or {}).get("img") or ""),
        }
        rescue_candidates.append((r_sc, synth_it, tpl))
    rescue_candidates.sort(key=lambda x: (-x[0], x[1]["key"]))

    scored.sort(key=lambda x: (-x[0], x[1].get("chapter_idx", 0), x[1].get("id", "")))

    picked: list[tuple[dict, dict | None]] = []
    used_chapters: set[int] = set()
    used_keys: set[str] = set()

    # Slot 1 ALWAYS comes from today's episode so speaking stays anchored to what he just heard;
    # if an unresolved speaking slip exists outside today's episode, reserve slot 2 for direct oral redemption!
    if scored:
        _sc0, it0, tpl0 = scored[0]
        picked.append((it0, tpl0))
        used_chapters.add(int(it0.get("chapter_idx", -1)))
        used_keys.add(str(it0.get("key") or it0.get("title") or ""))

    if max_prompts >= 2 and rescue_candidates:
        for _rsc, rit, rtpl in rescue_candidates:
            rk = str(rit.get("key") or "")
            if rk and rk not in used_keys:
                # Only preempt slot 2 if today's 2nd best episode item isn't already a red/orange slip itself
                ep_second_is_slip = len(scored) >= 2 and (
                    str(scored[1][1].get("key") or "") in spk_slips
                    or scored[1][1].get("status") in ("red", "orange")
                )
                if not ep_second_is_slip or rk in spk_slips:
                    picked.append((rit, rtpl))
                    used_keys.add(rk)
                    break

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
        zh = _short_zh(str(it.get("zh") or ""))
        ex_ja = _clean_text(str(it.get("ja_example") or ""))
        stems = _strip_point_stem(title) + _strip_point_stem(key)

        if tpl is not None:
            t_stems = _expand_conjugation_stems(list(tpl["target_stems"]) + stems)
            prompt_short = _clean_text(tpl.get("prompt_short") or tpl["prompt_zh"])
            prompt_ja = _clean_text(tpl["prompt_ja"])
            prompt_zh = _clean_text(tpl["prompt_zh"])
            model_ja = _clean_text(tpl["model_ja"])
            model_zh = _clean_text(tpl["model_zh"])
            tip = _clean_text(tpl["coaching_tip"])
        else:
            t_stems = _expand_conjugation_stems(stems)
            clean_pt = title.replace("〜", "").replace("~", "").strip()
            prompt_short = _short_zh(zh or f"用{clean_pt}造短句", max_chars=12) or "试着开口说一句"
            prompt_ja = _clean_text(f"「{title}」で一言")
            prompt_zh = _clean_text(f"用「{title}」说个短句")
            raw_model = _short_ja_example(ex_ja, t_stems, max_chars=20) or _clean_text(f"{clean_pt}で話します。")
            model_ja = raw_model[:24]
            model_zh = zh or "参考短句"
            tip = _short_zh(f"顺口带出「{title}」", max_chars=18)

        safe_stems = [s for s in t_stems if len(s) >= 2] or [s for s in t_stems if s] or [title.replace("〜", "").replace("~", "").strip() or title]
        prompts.append({
            "id": f"SPK-{pid}",
            "point_id": pid,
            "key": key,
            "title": title,
            "zh": zh,
            "chapter_idx": int(it.get("chapter_idx", 0)),
            "chapter_title": ch_title,
            "story_cue": story_cue,
            "prompt_short": prompt_short.replace("—", "")[:14],
            "prompt_ja": prompt_ja.replace("—", ""),
            "prompt_zh": prompt_zh.replace("—", ""),
            "target_stems": safe_stems,
            "model_ja": model_ja.replace("—", "")[:26],
            "model_zh": model_zh.replace("—", ""),
            "coaching_tip": tip.replace("—", ""),
            "clip_start": float(it.get("clip_start", 0.0)),
            "clip_end": float(it.get("clip_end", 14.0)),
            "demo_audio": str(it.get("demo_audio") or ""),
            "is_new_n2": bool(it.get("is_new_n2")),
            "img": str(it.get("img") or ""),
        })

    return prompts


if __name__ == "__main__":
    # Safe backfill for today's already-rendered episode (preserves script_sig, daily_radio.mp3 & story_arts!)
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
    blocks_imm, rep = ive.apply_immersion_to_stories(
        blocks,
        today_str=today_str,
        salon_stories=SALON_STORIES,
        mandarin_boundary_re=gdr.MANDARIN_BOUNDARY_RE,
        commit_ledger=False,
    )
    # Preserve exact mixer-captured clip_start/clip_end from existing review_items if present
    existing_items = meta.get("review_items") or []
    existing_timings = {
        str(x.get("id")): (x.get("clip_start"), x.get("clip_end"))
        for x in existing_items
        if isinstance(x, dict) and x.get("id") and x.get("clip_start") is not None
    }
    items = build_episode_review_items(
        blocks_imm,
        meta.get("segments") or [],
        meta.get("immersion_vocab") or rep,
        turn_timings=None,
        audio_mp3_path=mp3_path,
        max_total=8,
    )
    if existing_items:
        by_new_id = {str(x.get("id")): x for x in items}
        merged_items = []
        for ex in existing_items:
            eid = str(ex.get("id") or "")
            fresh = by_new_id.get(eid)
            if fresh and fresh.get("full_context"):
                ex["full_context"] = fresh["full_context"]
            elif not ex.get("full_context"):
                # Match full turn from blocks_imm directly
                ch_i = int(ex.get("chapter_idx", 0))
                if 0 <= ch_i < len(blocks_imm):
                    core = str(ex.get("context_line") or "").strip("…")[:14]
                    for _spk, t_raw in blocks_imm[ch_i].get("raw_turns") or []:
                        rd = _readable_turn(str(t_raw), ive.VOCAB_BY_KANA)
                        if core and core in rd:
                            ex["full_context"] = rd
                            break
            merged_items.append(ex)
        items = merged_items
    else:
        for it in items:
            if it["id"] in existing_timings:
                it["clip_start"], it["clip_end"] = existing_timings[it["id"]]

    speaking_prompts = build_episode_speaking_prompts(blocks_imm, items, max_prompts=2)
    chapters_meta = meta.get("chapters") or []

    try:
        import radio_visual_studio as rvs
        vis = rvs.build_episode_visuals(
            today_str=today_str,
            script_sig=str(meta.get("script_sig") or ""),
            story_blocks=blocks_imm,
            chapters_meta=chapters_meta,
            review_items=items,
            speaking_prompts=speaking_prompts,
            audio_mp3_path=mp3_path,
            imm_vocab_report=meta.get("immersion_vocab") or rep,
        )
        if vis.get("artwork_url"):
            meta["artwork_url"] = vis["artwork_url"]
        if vis.get("story_arts"):
            meta["story_arts"] = vis["story_arts"]
        if vis.get("jp_video"):
            meta["jp_video"] = vis["jp_video"]
    except Exception as exc:
        print(f"[warn] radio_visual_studio failed during backfill: {exc}")

    meta["chapters"] = chapters_meta
    meta["review_items"] = items
    meta["speaking_prompts"] = speaking_prompts
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    jpv = meta.get("jp_video") or {}
    print(
        f"Enriched {meta_path}: review_items={len(items)}, speaking_prompts={len(speaking_prompts)}, "
        f"jp_video={jpv.get('duration_label', 'none')} ({len(jpv.get('target_words') or [])} words), "
        f"story_arts={len(meta.get('story_arts') or [])} (script_sig preserved: {meta.get('script_sig')})"
    )


