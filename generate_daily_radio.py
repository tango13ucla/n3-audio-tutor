#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily ~36 Minute "Qiang Qiang Three" Round-Table Salon Podcast (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json) — Zen v14 Same-Voice Salon Edition.

Key Design:
1) Zero date announcements, zero exam countdowns, zero classroom tone — jumps straight into
   a funny real-life Japanese anecdote at 00:00.0!
2) 100% Same-Person Bilingual Vocal Cords (中文与日文由同一个人自然说出, ZERO JF/JM "tape-recorder" cuts!):
   - M (老文): `ko-KR-HyunsuMultilingualNeural` (-6% Mandarin / -11% Japanese Kana)
   - D (老梁): `fr-FR-RemyMultilingualNeural` (-6% Mandarin / -11% Japanese Kana)
   - F (小夏): `en-US-AvaMultilingualNeural` or `en-US-EmmaMultilingualNeural` (-6% Mandarin / -11% Japanese Kana)
3) Relaxed, Unhurried Bike-Safe Pacing:
   - 6 deep ~6-minute cultural stories per episode (~36 minutes total), each repeating 3–4 N3 expressions
     4–5 times naturally through jokes, cultural lore, and personal fiascos.
   - Generous pauses before/after Japanese quotes (0.62s echo breath after full Japanese sentences) and
     between speaker turns (0.42s) so cycling or zoning out at a traffic light feels effortless.
"""
import asyncio
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

PT_TZ = ZoneInfo("America/Los_Angeles")
EXAM_DATE = datetime.date(2026, 12, 6)
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 4 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Keeps multi-clause Japanese quotes (e.g. "ああ、もうごじだ。はやくかえって、ゆうはんのしたくしないと。")
# together in ONE continuous natural Japanese utterance by the SAME speaker!
JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー]+(?:[、。！？\s]+[\u3040-\u30ffー]+)*[。！？]?)")


def resolve_point_key(point_id: str) -> str:
    if point_id in TUTOR_ITEMS:
        return TUTOR_ITEMS[point_id].get("point_key", point_id)
    for ext in EXTRA_PRIMARY_CARDS:
        if ext["id"] == point_id:
            return ext["point_key"]
    return point_id


def load_mastery_priority(state: dict, recent_wrong_keys: set) -> dict:
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
        mod = MODALITY_MAP.get(pid, "both")
        mod_boost = 1.15 if mod == "listen" else (1.08 if mod == "both" else 0.92)
        scores[pid] = round(w * mult * mod_boost, 4)
    return scores


def load_recent_mistakes() -> set:
    wrong = set()
    if not os.path.exists(LOG_PATH):
        return wrong
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()][-120:]
        for ln in lines:
            rec = json.loads(ln)
            if str(rec.get("correct", "")).lower() == "false" or str(rec.get("ask_again", "")).lower() == "true":
                wrong.add(str(rec.get("point", "")).strip())
                wrong.add(str(rec.get("id", "")).strip())
    except Exception:
        pass
    return wrong


async def detect_voice_map() -> dict:
    """
    Maps both Mandarin (`M`, `D`, `F` at -6%) and Japanese spans (`M_JA`, `D_JA`, `F_JA` at -11%)
    to the EXACT SAME Multilingual Neural human voice for each of the 3 friends!
    """
    m_voice = "ko-KR-HyunsuMultilingualNeural"
    d_voice = "fr-FR-RemyMultilingualNeural"
    f_voice = "en-US-AvaMultilingualNeural"

    if edge_tts is not None:
        try:
            voices = await edge_tts.list_voices(**COMM_KWARGS)
            short_names = {v.get("ShortName", "") for v in voices}
            for cand_m in ("ko-KR-HyunsuMultilingualNeural", "en-US-BrianMultilingualNeural"):
                if cand_m in short_names:
                    m_voice = cand_m
                    break
            for cand_d in ("fr-FR-RemyMultilingualNeural", "en-US-BrianMultilingualNeural"):
                if cand_d in short_names and cand_d != m_voice:
                    d_voice = cand_d
                    break
            for cand_f in ("en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural"):
                if cand_f in short_names:
                    f_voice = cand_f
                    break
            print(f"Salon same-person bilingual voices: M={m_voice}, D={d_voice}, F={f_voice}")
        except Exception as e:
            print(f"[info] list_voices fallback to default multilingual voices: {e}")

    return {
        "M": (m_voice, "-6%"),
        "M_JA": (m_voice, "-11%"),
        "D": (d_voice, "-6%"),
        "D_JA": (d_voice, "-11%"),
        "F": (f_voice, "-6%"),
        "F_JA": (f_voice, "-11%"),
    }


def expand_turn_events(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if spk in ("M", "D", "F") and JA_SPAN_RE.search(txt):
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
                    out.append(("PAUSE", round(max(pending_pause, 0.18), 2)))
                ended_punct = ks[-1] in "。！？"
                ja_utterance = ks if ended_punct else (ks + "。")
                out.append((ja_spk, ja_utterance))
                # Generous echo breath after full Japanese sentences so bike riders can absorb the sound effortlessly
                if ended_punct and len(ks) >= 7:
                    pending_pause = 0.62
                elif ended_punct:
                    pending_pause = 0.36
                else:
                    pending_pause = 0.20
            else:
                lead_m = re.match(r"^[\s』」）]*([。！？；，、：]+)[\s『「（]*", pt)
                if lead_m:
                    pchars = lead_m.group(1)
                    if any(c in pchars for c in "。！？；"):
                        pending_pause = max(pending_pause, 0.42)
                    else:
                        pending_pause = max(pending_pause, 0.24)
                    pt = pt[lead_m.end():]
                pt_s = pt.strip()
                if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                    continue
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.18), 2)))
                out.append((spk, pt_s))
                if pt_s[-1] in "。！？；":
                    pending_pause = 0.28
                elif pt_s[-1] in "，、：":
                    pending_pause = 0.22
                else:
                    pending_pause = 0.18
        return out if out else [(spk, txt)]
    return [(spk, txt)]


def synth_gemini_turn_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    voice_map_g = {
        "F": "Aoede",
        "F_JA": "Aoede",
        "M": "Puck",
        "M_JA": "Puck",
        "D": "Charon",
        "D_JA": "Charon",
    }
    voice_name = voice_map_g.get(spk, "Puck")
    prompt = (
        f"Speak at a relaxed, unhurried pace like witty Chinese friends chatting leisurely around a tea table: {text}"
        if spk in ("M", "D", "F")
        else text
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


async def synth_turn(spk: str, voice: str, rate: str, text: str, out_path: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        if GEMINI_API_KEY and genai is not None:
            ok = await asyncio.to_thread(synth_gemini_turn_sync, spk, text, out_path)
            if ok:
                return True
        if edge_tts is None:
            return False
        for attempt in range(MAX_TRIES):
            try:
                buf = bytearray()
                comm = edge_tts.Communicate(text, voice, rate=rate, **COMM_KWARGS)
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.extend(chunk["data"])
                if buf:
                    with open(out_path, "wb") as f:
                        f.write(buf)
                    return True
            except Exception as e:
                if attempt + 1 < MAX_TRIES:
                    await asyncio.sleep(0.7 * (attempt + 1))
                elif MAX_TRIES > 1:
                    print(f"[warn] radio turn synth failed ({voice}): {e}")
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
        else f"edge:{voice_map['M'][0]}:{voice_map['D'][0]}:{voice_map['F'][0]}"
    )

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    today_str = now_pt.strftime("%Y-%m-%d")
    days_left = max(0, (EXAM_DATE - now_pt.date()).days)

    recent_wrong = load_recent_mistakes()
    scores = load_mastery_priority(state, recent_wrong)
    rng = random.Random(today_str)

    def story_rank(st: dict) -> float:
        pids = st.get("point_ids") or []
        pt_vals = sorted((scores.get(pid, 2.2) for pid in pids), reverse=True)
        top_avg = sum(pt_vals[:3]) / max(1, len(pt_vals[:3])) if pt_vals else 2.2
        jitter = rng.uniform(-0.18, 0.18)
        return -(top_avg + jitter)

    ranked_ids = {st["id"] for st in sorted(SALON_STORIES, key=story_rank)[:6]}
    selected_stories = [st for st in SALON_STORIES if st["id"] in ranked_ids]

    closing_turns = [
        ("D", "哎，不知不觉咱们这壶茶都喝见底了。今天聊的这些便利店、饭局、电车里的弯弯绕，其实全藏在日本人的日常口头禅里。"),
        ("F", "对，骑车或者走路的时候听个乐呵，耳根子混熟了，下次再听见这些尾巴，画面自己就跳出来了。"),
        ("M", "行，那咱们今天就先唠到这儿，路上慢点儿骑，咱们下回接着聊！"),
    ]

    # ZERO INTRO PREAMBLE, ZERO DATE, ZERO COUNTDOWN — COLD OPEN INTO FUNNY ANECDOTE AT 00:00.0!
    raw_blocks = []
    for ch_idx, st in enumerate(selected_stories):
        evs = []
        turns = list(st["turns"])
        if ch_idx == len(selected_stories) - 1:
            turns.append(("PAUSE", 0.90))
            turns.extend(closing_turns)

        for idx, (spk, val) in enumerate(turns):
            if spk == "PAUSE":
                evs.append(("PAUSE", float(val)))
            else:
                evs.append((spk, str(val)))
                if idx + 1 < len(turns) and turns[idx + 1][0] != "PAUSE":
                    evs.append(("PAUSE", 0.42))

        # Calm tea-sipping breather between round-table stories
        evs.append(("PAUSE", 1.60 if ch_idx + 1 < len(selected_stories) else 0.50))
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

    sig_payload = f"v14_qq3_samevoice:{engine_tag}:" + json.dumps(voice_map, sort_keys=True) + json.dumps(blocks, ensure_ascii=False)
    script_sig = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()[:14]
    if os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                print(f"Daily 3-host salon radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v14_")
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

        sem = asyncio.Semaphore(8)
        ok_results = await asyncio.gather(
            *(synth_turn(k, voice_map[k][0], voice_map[k][1], txt, raw_p, sem) for (k, txt), (raw_p, _) in unique_turns.items())
        )
        print(f"Synthesized {sum(1 for x in ok_results if x)} / {len(unique_turns)} unique same-voice salon clips.")

        turn_durs = {}
        trimmed_paths = {}
        for key, (raw_p, trim_p) in unique_turns.items():
            if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                trim_clip_silence(raw_p, trim_p)
                trimmed_paths[key] = trim_p
                turn_durs[key] = probe_duration(trim_p)

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
            "display_date": "三人闲聊",
            "days_left": days_left,
            "script_sig": script_sig,
            "audio_url": f"./audio/daily_radio.mp3?v={today_str}_{script_sig[:6]}",
            "duration_sec": final_dur,
            "duration_label": f"{mins} 分钟",
            "hosts": "老文 · 老梁 · 小夏",
            "chapters": chapters_meta,
            "segments": segments_meta,
        }
        with open(RADIO_META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta_obj, f, ensure_ascii=False, indent=2)
        print(f"Built Qiang-Qiang salon radio episode: {final_dur:.1f}s ({mins} mins), size={os.path.getsize(RADIO_MP3_PATH)} bytes.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
