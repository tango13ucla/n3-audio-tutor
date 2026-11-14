#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily ~36 Minute "Qiang Qiang Three" Cultural Salon Podcast (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json) — Zen v15 Trio Edition.

Hosts: 文涛 (W) · 文道 (D) · 子东 (X)
Key Design:
1) Zero date announcements, zero exam countdowns, zero classroom tone — cold-opens at 00:00.0
   into witty, culturally rich Japanese anthropology, literature, and everyday urban stories.
2) 100% Same-Person Bilingual Vocal Cords with Exact Speed Differential:
    - W (文涛): `en-US-BrianMultilingualNeural` (+6% Mandarin / -35% Japanese, +2Hz lively warmth)
    - D (文道): `it-IT-GiuseppeMultilingualNeural` (+4% Mandarin / -35% Japanese, -2Hz warm scholar baritone)
    - X (子东): `fr-FR-RemyMultilingualNeural` (+5% Mandarin / -35% Japanese, -2Hz dry scholar wit)
3) Smart Daily Morning Selection & Fresh Rotation:
   - Pulls live mastery + recent misses & "不确定" clicks from `practice_log.jsonl`, while rotating
     against `audio/radio_history.json` so consecutive mornings serve fresh stories from the 12-story bank.
"""
import asyncio
import concurrent.futures
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import wave
from zoneinfo import ZoneInfo

try:
    import certifi
    if os.environ.get("SSL_CERT_FILE") and os.path.exists(os.environ["SSL_CERT_FILE"]):
        certifi.where = lambda: os.environ["SSL_CERT_FILE"]
    import edge_tts
except Exception:
    edge_tts = None

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

from adaptive_bank import EXTRA_PRIMARY_CARDS, POINT_META
from radio_dialogue_bank import MODALITY_MAP, SALON_STORIES
from tutor_data import TUTOR_ITEMS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
RADIO_MP3_PATH = os.path.join(AUDIO_DIR, "daily_radio.mp3")
RADIO_META_PATH = os.path.join(AUDIO_DIR, "daily_radio_meta.json")
RADIO_HISTORY_PATH = os.path.join(AUDIO_DIR, "radio_history.json")

PT_TZ = ZoneInfo("America/Los_Angeles")
EXAM_DATE = datetime.date(2026, 12, 6)
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 4 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Keeps multi-clause Japanese quotes together in ONE continuous slow (-35%) utterance by the SAME speaker!
JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー]+(?:[、。！？\s]+[\u3040-\u30ffー]+)*[。！？]?)")


def resolve_point_key(point_id: str) -> str:
    if point_id in TUTOR_ITEMS:
        return TUTOR_ITEMS[point_id].get("point_key", point_id)
    for ext in EXTRA_PRIMARY_CARDS:
        if ext["id"] == point_id:
            return ext["point_key"]
    return point_id


def load_recent_mistakes() -> tuple[set, set]:
    """Returns (all_recent_weak_keys, very_recent_weak_keys_last_25)."""
    wrong_all = set()
    wrong_hot = set()
    if not os.path.exists(LOG_PATH):
        return wrong_all, wrong_hot
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()][-150:]
        total = len(lines)
        for idx, ln in enumerate(lines):
            rec = json.loads(ln)
            is_weak = (
                str(rec.get("correct", "")).lower() == "false"
                or str(rec.get("ask_again", "")).lower() == "true"
                or str(rec.get("choice", "")).strip() == "不确定"
            )
            if is_weak:
                pt = str(rec.get("point", "")).strip()
                qid = str(rec.get("id", "")).strip()
                if pt:
                    wrong_all.add(pt)
                if qid:
                    wrong_all.add(qid)
                if idx >= max(0, total - 25):
                    if pt:
                        wrong_hot.add(pt)
                    if qid:
                        wrong_hot.add(qid)
    except Exception:
        pass
    return wrong_all, wrong_hot


def load_mastery_priority(state: dict, recent_wrong_keys: set, hot_wrong_keys: set) -> dict:
    status_by_key = {}
    for p in state.get("grammar_points", []):
        status_by_key[p["name"]] = p.get("status", "yellow")
    for p in state.get("henkei_points", []):
        status_by_key[p["id"]] = p.get("status", "red")
    for p in state.get("listening_points", []):
        status_by_key[p["id"]] = p.get("status", "red")
    for p in state.get("vocab_tracked", []):
        status_by_key[p["word"]] = p.get("status", "red")

    scores = {}
    for pid, meta in POINT_META.items():
        pkey = resolve_point_key(pid)
        st = status_by_key.get(pkey, "red")
        w = float(meta.get("weight", 2.4))
        mult = 1.0 if st == "red" else (0.92 if st in ("orange", "gray") else (0.65 if st == "yellow" else 0.18))
        if pkey in recent_wrong_keys or pid in recent_wrong_keys:
            mult += 0.45
        if pkey in hot_wrong_keys or pid in hot_wrong_keys:
            mult += 0.55
        mod = MODALITY_MAP.get(pid, "both")
        mod_boost = 1.15 if mod == "listen" else (1.08 if mod == "both" else 0.92)
        scores[pid] = round(w * mult * mod_boost, 4)
    return scores


def load_previous_day_stories(today_str: str) -> set:
    if not os.path.exists(RADIO_HISTORY_PATH):
        return set()
    try:
        with open(RADIO_HISTORY_PATH, encoding="utf-8") as f:
            hist = json.load(f)
        by_date = hist.get("recent_days") or {}
        prior_dates = sorted(d for d in by_date.keys() if d < today_str)
        if prior_dates:
            return set(by_date.get(prior_dates[-1]) or [])
    except Exception:
        pass
    return set()


def save_today_stories(today_str: str, story_ids: list) -> None:
    hist = {"recent_days": {}}
    if os.path.exists(RADIO_HISTORY_PATH):
        try:
            with open(RADIO_HISTORY_PATH, encoding="utf-8") as f:
                hist = json.load(f)
                if not isinstance(hist.get("recent_days"), dict):
                    hist["recent_days"] = {}
        except Exception:
            hist = {"recent_days": {}}
    hist["last_date"] = today_str
    hist["recent_days"][today_str] = list(story_ids)
    # Keep last 10 days clean
    keep_dates = sorted(hist["recent_days"].keys())[-10:]
    hist["recent_days"] = {k: hist["recent_days"][k] for k in keep_dates}
    with open(RADIO_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


async def detect_voice_map() -> dict:
    """
    Maps brisk conversational Mandarin (+4% to +6%) and crystal-clear slow Japanese (-35%)
    to the EXACT SAME Multilingual Conversational Neural voice for each of the 3 male hosts:
    - W (文涛): BrianMultilingualNeural (lively, cheeky, casual Copilot prosody)
    - D (文道): GiuseppeMultilingualNeural (warm, steady, scholarly baritone prosody)
    - X (子东): RemyMultilingualNeural (crisp, dry intellectual scholar cadence)
    """
    w_voice = "en-US-BrianMultilingualNeural"
    d_voice = "it-IT-GiuseppeMultilingualNeural"
    x_voice = "fr-FR-RemyMultilingualNeural"

    if edge_tts is not None:
        try:
            voices = await edge_tts.list_voices(**COMM_KWARGS)
            short_names = {v.get("ShortName", "") for v in voices}
            for cand_w in ("en-US-BrianMultilingualNeural", "ko-KR-HyunsuMultilingualNeural"):
                if cand_w in short_names:
                    w_voice = cand_w
                    break
            for cand_d in ("it-IT-GiuseppeMultilingualNeural", "ko-KR-HyunsuMultilingualNeural"):
                if cand_d in short_names and cand_d != w_voice:
                    d_voice = cand_d
                    break
            for cand_x in ("fr-FR-RemyMultilingualNeural", "ko-KR-HyunsuMultilingualNeural", "en-AU-WilliamMultilingualNeural"):
                if cand_x in short_names and cand_x not in (w_voice, d_voice):
                    x_voice = cand_x
                    break
            print(f"Qiang-Qiang trio voices: W(文涛)={w_voice}, D(文道)={d_voice}, X(子东)={x_voice}")
        except Exception as e:
            print(f"[info] list_voices fallback to default trio voices: {e}")

    vmap = {
        "W": (w_voice, "+6%", "+2Hz"),
        "W_JA": (w_voice, "-35%", "+2Hz"),
        "D": (d_voice, "+4%", "-2Hz"),
        "D_JA": (d_voice, "-35%", "-2Hz"),
        "X": (x_voice, "+5%", "-2Hz"),
        "X_JA": (x_voice, "-35%", "-2Hz"),
    }
    # Legacy speaker code aliases for safety
    vmap["M"] = vmap["W"]
    vmap["M_JA"] = vmap["W_JA"]
    vmap["F"] = vmap["X"]
    vmap["F_JA"] = vmap["X_JA"]
    return vmap


def expand_turn_events(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if spk in ("W", "D", "X", "M", "F") and JA_SPAN_RE.search(txt):
        ja_spk = f"{spk}_JA"
        parts = JA_SPAN_RE.split(txt)
        out = []
        pending_pause = 0.0
        for idx, pt in enumerate(parts):
            if not pt:
                continue
            if idx % 2 == 1:
                ks = re.sub(r"\s+", "", pt.strip())
                if not ks:
                    continue
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.20), 2)))
                ended_punct = ks[-1] in "。！？"
                ja_utterance = ks if ended_punct else (ks + "。")
                out.append((ja_spk, ja_utterance))
                # Clear breathing echo after slow (-35%) Japanese so every mora settles into memory
                if ended_punct and len(ks) >= 7:
                    pending_pause = 0.56
                elif ended_punct:
                    pending_pause = 0.34
                else:
                    pending_pause = 0.22
            else:
                lead_m = re.match(r"^[\s』」）]*([。！？；，、：]+)[\s『「（]*", pt)
                if lead_m:
                    pchars = lead_m.group(1)
                    if any(c in pchars for c in "。！？；"):
                        pending_pause = max(pending_pause, 0.36)
                    else:
                        pending_pause = max(pending_pause, 0.20)
                    pt = pt[lead_m.end():]
                pt_s = pt.strip()
                if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                    continue
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.16), 2)))
                out.append((spk, pt_s))
                if pt_s[-1] in "。！？；":
                    pending_pause = 0.24
                elif pt_s[-1] in "，、：":
                    pending_pause = 0.18
                else:
                    pending_pause = 0.16
        return out if out else [(spk, txt)]
    return [(spk, txt)]


def synth_gemini_turn_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    voice_map_g = {
        "W": "Puck",
        "W_JA": "Puck",
        "D": "Charon",
        "D_JA": "Charon",
        "X": "Orus",
        "X_JA": "Orus",
    }
    voice_name = voice_map_g.get(spk, "Puck")
    prompt = (
        f"Speak briskly and warmly with lively human wit like three close male friends on Qiang Qiang Three: {text}"
        if not spk.endswith("_JA")
        else f"Speak this Japanese phrase slowly, clearly, and distinctly: {text}"
    )
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_TTS_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=voice_name)
                    )
                ),
            ),
        )
        pcm = resp.candidates[0].content.parts[0].inline_data.data
        if not pcm:
            return False
        wav_path = out_mp3 + ".wav"
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame", out_mp3],
            check=True,
        )
        try:
            os.remove(wav_path)
        except OSError:
            pass
        return os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0
    except Exception:
        return False


async def synth_turn(spk: str, voice_cfg: tuple, text: str, out_path: str, sem: asyncio.Semaphore) -> bool:
    voice, rate, pitch = voice_cfg[0], voice_cfg[1], (voice_cfg[2] if len(voice_cfg) > 2 else "+0Hz")
    async with sem:
        if GEMINI_API_KEY and genai is not None:
            ok = await asyncio.to_thread(synth_gemini_turn_sync, spk, text, out_path)
            if ok:
                return True
        if edge_tts is None:
            return False
        speak_txt = text
        if len(speak_txt) <= 2 and speak_txt[-1] not in "。！？，、：":
            speak_txt = speak_txt + "。"
        for attempt in range(MAX_TRIES):
            use_voice = "ko-KR-HyunsuMultilingualNeural" if (attempt == MAX_TRIES - 1 and MAX_TRIES > 1 and attempt >= 2) else voice
            use_txt = (speak_txt + "。") if (attempt >= 1 and speak_txt[-1] not in "。！？") else speak_txt
            try:
                buf = bytearray()
                try:
                    comm = edge_tts.Communicate(use_txt, use_voice, rate=rate, pitch=pitch, **COMM_KWARGS)
                except TypeError:
                    comm = edge_tts.Communicate(use_txt, use_voice, rate=rate, **COMM_KWARGS)

                async def _pull():
                    async for chunk in comm.stream():
                        if chunk["type"] == "audio":
                            buf.extend(chunk["data"])

                await asyncio.wait_for(_pull(), timeout=22.0)
                if buf:
                    with open(out_path, "wb") as f:
                        f.write(buf)
                    return True
            except Exception as e:
                if attempt + 1 < MAX_TRIES:
                    await asyncio.sleep(0.6 * (attempt + 1))
                elif MAX_TRIES > 1:
                    print(f"[warn] radio turn synth failed ({use_voice}): {e}")
    return False


def trim_clip_silence(raw_path: str, trimmed_path: str) -> None:
    af_chain = (
        "silenceremove=start_periods=1:start_duration=0.0:start_threshold=-68dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0.0:start_threshold=-68dB,areverse,"
        "afade=t=in:st=0:d=0.008,areverse,afade=t=in:st=0:d=0.008,areverse"
    )
    res = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", raw_path,
            "-af", af_chain,
            "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame",
            trimmed_path,
        ],
        check=False,
    )
    if res.returncode != 0 or not os.path.exists(trimmed_path) or os.path.getsize(trimmed_path) < 256:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", raw_path,
                "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame",
                trimmed_path,
            ],
            check=True,
        )


def make_silence_mp3(sec: float, out_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", f"{sec:.2f}",
            "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k",
            out_path,
        ],
        check=True,
    )


def probe_duration(path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            text=True,
        ).strip()
        return float(out)
    except Exception:
        return os.path.getsize(path) / 6000.0


async def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    if edge_tts is None or shutil.which("ffmpeg") is None:
        print("Skipping live radio MP3 synthesis (edge_tts or ffmpeg unavailable in local sandbox).")
        return

    voice_map = await detect_voice_map()
    engine_tag = (
        f"gemini:{GEMINI_TTS_MODEL}"
        if (GEMINI_API_KEY and genai is not None)
        else f"edge:{voice_map['W'][0]}:{voice_map['D'][0]}:{voice_map['X'][0]}"
    )

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    today_str = now_pt.strftime("%Y-%m-%d")
    days_left = max(0, (EXAM_DATE - now_pt.date()).days)

    recent_wrong, hot_wrong = load_recent_mistakes()
    scores = load_mastery_priority(state, recent_wrong, hot_wrong)
    yesterday_stories = load_previous_day_stories(today_str)
    rng = random.Random(today_str)

    def story_rank(st: dict) -> float:
        pids = st.get("point_ids") or []
        pt_vals = sorted((scores.get(pid, 2.2) for pid in pids), reverse=True)
        top_avg = sum(pt_vals[:3]) / max(1, len(pt_vals[:3])) if pt_vals else 2.2
        has_hot_miss = any((pid in hot_wrong or resolve_point_key(pid) in hot_wrong) for pid in pids)
        repeat_penalty = 1.45 if (st["id"] in yesterday_stories and not has_hot_miss) else 0.0
        jitter = rng.uniform(-0.15, 0.15)
        return -(top_avg - repeat_penalty + jitter)

    ranked_ids = {st["id"] for st in sorted(SALON_STORIES, key=story_rank)[:6]}
    selected_stories = [st for st in SALON_STORIES if st["id"] in ranked_ids]
    save_today_stories(today_str, [st["id"] for st in selected_stories])

    closing_turns = [
        ("D", "哎，不知不觉咱们这壶热茶又喝见底了。其实你看，不管是在涩谷赶末班车，还是在京都喝那碗不敢真喝的茶泡饭，日本人的性子全藏在他们说话留的那半截尾巴里。"),
        ("X", "对，平时当闲篇儿听个乐呵，把这些市井掌故和男女心眼儿听熟了，下次再听见那些词尾，不用过脑子，画面自己就跳出来了。"),
        ("W", "得嘞，那咱们今儿就先侃到这儿，您路上慢点儿骑，咱们下回接着聊！"),
    ]

    # ZERO INTRO PREAMBLE, ZERO DATE, ZERO COUNTDOWN — COLD OPEN INTO CULTURAL SALON AT 00:00.0!
    raw_blocks = []
    for ch_idx, st in enumerate(selected_stories):
        evs = []
        turns = list(st["turns"])
        if ch_idx == len(selected_stories) - 1:
            turns.append(("PAUSE", 0.85))
            turns.extend(closing_turns)

        for idx, (spk, val) in enumerate(turns):
            if spk == "PAUSE":
                evs.append(("PAUSE", float(val)))
            else:
                evs.append((spk, str(val)))
                if idx + 1 < len(turns) and turns[idx + 1][0] != "PAUSE":
                    evs.append(("PAUSE", 0.34))

        # Calm tea-sipping breather between round-table stories
        evs.append(("PAUSE", 1.50 if ch_idx + 1 < len(selected_stories) else 0.45))
        pids = list(st.get("point_ids") or [])
        raw_blocks.append({
            "chapter": ch_idx,
            "short_tab": st["short_tab"],
            "point_id": pids[0] if pids else "",
            "point_ids": pids,
            "title": st["title"],
            "ja_focus": st["ja_focus"],
            "events": evs,
        })

    blocks = []
    for b in raw_blocks:
        expanded_evs = []
        for spk, val in b["events"]:
            expanded_evs.extend(expand_turn_events(spk, val))
        nb = dict(b)
        nb["events"] = expanded_evs
        blocks.append(nb)

    sig_payload = f"v17_qq3_wdx:{engine_tag}:" + json.dumps(voice_map, sort_keys=True) + json.dumps(blocks, ensure_ascii=False)
    script_sig = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()[:14]
    if os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                print(f"Daily Qiang-Qiang trio radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v17_")
    try:
        pause_durations = sorted({round(float(val), 2) for b in blocks for k, val in b["events"] if k == "PAUSE"})
        silence_files = {}
        for sec in pause_durations:
            sf = os.path.join(tmpdir, f"sil_{int(round(sec * 100)):04d}.mp3")
            make_silence_mp3(sec, sf)
            silence_files[sec] = (sf, probe_duration(sf))

        unique_turns = {}
        for b in blocks:
            for k, val in b["events"]:
                if k != "PAUSE":
                    key = (k, val)
                    if key not in unique_turns:
                        thash = hashlib.sha256(f"{k}:{val}".encode("utf-8")).hexdigest()[:12]
                        unique_turns[key] = (
                            os.path.join(tmpdir, f"raw_{thash}.mp3"),
                            os.path.join(tmpdir, f"trim_{thash}.mp3"),
                        )

        sem = asyncio.Semaphore(12)
        ok_results = await asyncio.gather(
            *(synth_turn(k, voice_map[k], txt, raw_p, sem) for (k, txt), (raw_p, _) in unique_turns.items())
        )
        print(f"Synthesized {sum(1 for x in ok_results if x)} / {len(unique_turns)} unique Qiang-Qiang trio clips.")

        turn_durs = {}
        trimmed_paths = {}

        def _trim_and_probe(item):
            key, (raw_p, trim_p) = item
            if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                trim_clip_silence(raw_p, trim_p)
                return key, trim_p, probe_duration(trim_p)
            return key, None, 0.0

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for key, trim_p, dur in pool.map(_trim_and_probe, unique_turns.items()):
                if trim_p:
                    trimmed_paths[key] = trim_p
                    turn_durs[key] = dur

        concat_lines = []
        cursor = 0.0
        chapter_starts = {}
        segments_meta = []

        for b in blocks:
            ch = b["chapter"]
            if ch not in chapter_starts:
                chapter_starts[ch] = round(cursor, 1)
            seg_start = cursor
            for k, val in b["events"]:
                if k == "PAUSE":
                    sec = round(float(val), 2)
                    sf, sdur = silence_files[sec]
                    concat_lines.append(f"file '{sf}'")
                    cursor += sdur
                else:
                    key = (k, val)
                    if key in turn_durs:
                        concat_lines.append(f"file '{trimmed_paths[key]}'")
                        cursor += turn_durs[key]
            seg_end = cursor
            segments_meta.append({
                "chapter": ch,
                "point_id": b["point_id"] or "",
                "point_ids": b["point_ids"],
                "title": b["title"],
                "ja_focus": b["ja_focus"],
                "start": round(seg_start, 1),
                "end": round(seg_end, 1),
            })

        concat_txt = os.path.join(tmpdir, "concat.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(concat_lines) + "\n")

        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", concat_txt,
                "-vn", "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame",
                RADIO_MP3_PATH,
            ],
            check=True,
        )

        final_dur = round(probe_duration(RADIO_MP3_PATH), 1)
        mins = max(1, round(final_dur / 60.0))
        chapters_meta = [
            {"idx": b["chapter"], "title": b["short_tab"], "start": chapter_starts.get(b["chapter"], 0.0)}
            for b in blocks
        ]
        meta_obj = {
            "date": today_str,
            "display_date": "锵锵三人",
            "days_left": days_left,
            "script_sig": script_sig,
            "audio_url": f"./audio/daily_radio.mp3?v={today_str}_{script_sig[:6]}",
            "duration_sec": final_dur,
            "duration_label": f"{mins} 分钟",
            "hosts": "文涛 · 文道 · 子东",
            "chapters": chapters_meta,
            "segments": segments_meta,
        }
        with open(RADIO_META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta_obj, f, ensure_ascii=False, indent=2)
        print(f"Built Qiang-Qiang trio episode: {final_dur:.1f}s ({mins} mins), stories={[s['short_tab'] for s in selected_stories]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
