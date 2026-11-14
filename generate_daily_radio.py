#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily ~35 Minute "Qiang Qiang Three" Round-Table Salon Podcast (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json) — Zen v12 Edition.

Key Design:
1) Zero date announcements, zero exam countdowns, zero stiff intro preambles — jumps straight into
   three friends chatting at 00:00.0!
2) Three Distinct Real-Human Conversational Multilingual Voices:
   - M (老文): `ko-KR-HyunsuMultilingualNeural` (+0%)
   - D (老梁): `fr-FR-RemyMultilingualNeural` (+0%)
   - F (小夏): `en-US-AvaMultilingualNeural` (+0%)
   - JF / JM: `ja-JP-NanamiNeural` / `ja-JP-KeitaNeural` (-2%) for native Japanese scenes & examples
3) Same-speaker punctuation-aware Mandarin/Kana prosody + -68dB digital-zero-only trim so voiceless
   Japanese consonants and human breath remain 100% intact.
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
from radio_dialogue_bank import DEEP_BANTER_TOPICS, LISTENING_THEATRE, MODALITY_MAP, VOCAB_RECALL_ITEMS
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

KANA_RE = re.compile(r"([\u3040-\u30ffー]+)")


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


async def detect_voice_map() -> tuple[dict, set]:
    vmap = {
        "M": ("zh-CN-YunxiNeural", "+0%"),
        "D": ("zh-CN-YunyangNeural", "+0%"),
        "F": ("zh-CN-XiaoxiaoNeural", "+0%"),
        "JF": ("ja-JP-NanamiNeural", "-2%"),
        "JM": ("ja-JP-KeitaNeural", "-2%"),
        "JFS": ("ja-JP-NanamiNeural", "-8%"),
    }
    multilingual_speakers = set()
    if edge_tts is None:
        return vmap, multilingual_speakers
    try:
        voices = await edge_tts.list_voices(**COMM_KWARGS)
        short_names = {v.get("ShortName", "") for v in voices}
        for cand_m in (
            "ko-KR-HyunsuMultilingualNeural",
            "en-US-BrianMultilingualNeural",
        ):
            if cand_m in short_names:
                vmap["M"] = (cand_m, "+0%")
                multilingual_speakers.add("M")
                break
        for cand_d in (
            "fr-FR-RemyMultilingualNeural",
            "en-US-BrianMultilingualNeural",
        ):
            if cand_d in short_names and cand_d != vmap["M"][0]:
                vmap["D"] = (cand_d, "+0%")
                multilingual_speakers.add("D")
                break
        for cand_f in (
            "en-US-AvaMultilingualNeural",
            "en-US-EmmaMultilingualNeural",
        ):
            if cand_f in short_names:
                vmap["F"] = (cand_f, "+0%")
                multilingual_speakers.add("F")
                break
        print(
            f"Salon 3-host voices: M={vmap['M'][0]}, D={vmap['D'][0]}, F={vmap['F'][0]}, "
            f"multilingual={sorted(multilingual_speakers)}"
        )
    except Exception as e:
        print(f"[info] list_voices fallback: {e}")
    return vmap, multilingual_speakers


def expand_turn_events(spk: str, val, multilingual_speakers: set) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if spk in ("M", "D", "F") and KANA_RE.search(txt):
        kana_spk = spk if spk in multilingual_speakers else ("JF" if spk == "F" else "JM")
        parts = KANA_RE.split(txt)
        out = []
        pending_pause = 0.0
        for idx, pt in enumerate(parts):
            if not pt:
                continue
            if idx % 2 == 1:
                ks = pt.strip()
                if not ks:
                    continue
                if out:
                    out.append(("PAUSE", round(pending_pause or 0.04, 2)))
                out.append((kana_spk, ks if ks.endswith("。") else ks + "。"))
                pending_pause = 0.04
            else:
                lead_m = re.match(r"^[\s』」）]*([。！？；，、：]+)[\s『「（]*", pt)
                if lead_m:
                    pchars = lead_m.group(1)
                    if any(c in pchars for c in "。！？；"):
                        pending_pause = max(pending_pause, 0.24)
                    else:
                        pending_pause = max(pending_pause, 0.13)
                    pt = pt[lead_m.end():]
                pt_s = pt.strip()
                if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                    continue
                if out:
                    out.append(("PAUSE", round(pending_pause or 0.04, 2)))
                out.append((spk, pt_s))
                if pt_s[-1] in "。！？；":
                    pending_pause = 0.22
                elif pt_s[-1] in "，、：":
                    pending_pause = 0.12
                else:
                    pending_pause = 0.04
        return out if out else [(spk, txt)]
    return [(spk, txt)]


def synth_gemini_turn_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    voice_map_g = {"F": "Aoede", "JF": "Aoede", "JFS": "Aoede", "M": "Puck", "D": "Charon", "JM": "Puck"}
    voice_name = voice_map_g.get(spk, "Puck")
    prompt = (
        f"Speak naturally like witty, cultured Chinese friends chatting around a table on Qiang Qiang San Ren Xing: {text}"
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
        if GEMINI_API_KEY and genai is not None and spk in ("M", "D", "F"):
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

    voice_map, multilingual_speakers = await detect_voice_map()
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

    def daily_rank(item):
        pid = item["point_id"]
        jitter = rng.uniform(-0.18, 0.18)
        return -(scores.get(pid, 2.0) + jitter)

    ch1_topics = sorted(DEEP_BANTER_TOPICS, key=daily_rank)[:19]
    ch2_scenes = sorted(LISTENING_THEATRE, key=daily_rank)[:6]
    ch3_vocabs = sorted(VOCAB_RECALL_ITEMS, key=daily_rank)[:14]

    # ZERO INTRO PREAMBLE, ZERO DATE, ZERO COUNTDOWN — JUMP STRAIGHT INTO SALON BANTER AT 00:00!
    raw_blocks = []

    for tp in ch1_topics:
        evs = []
        turns = tp["turns"]
        for idx, (spk, val) in enumerate(turns):
            if spk == "PAUSE":
                evs.append(("PAUSE", float(val)))
            else:
                evs.append((spk, str(val)))
                if idx + 1 < len(turns) and turns[idx + 1][0] != "PAUSE":
                    next_spk = turns[idx + 1][0]
                    gap = 0.24 if next_spk in ("JF", "JM", "JFS") or spk in ("JF", "JM", "JFS") else 0.18
                    evs.append(("PAUSE", gap))
        evs.append(("PAUSE", 0.55))
        raw_blocks.append({
            "chapter": 0,
            "point_id": tp["point_id"],
            "title": tp["title"],
            "ja_focus": tp["ja_main"],
            "events": evs,
        })

    for idx_s, sc in enumerate(ch2_scenes):
        evs = []
        if idx_s == 0:
            evs.extend([
                ("M", "聊了这么多语法背后的日本人心思，咱们直接切进东京街头的真实现场，竖起耳朵听几段原速对话。"),
                ("PAUSE", 0.18),
                ("D", "日本人口语里最爱吃音、留半截话，光看字面特容易上当。"),
                ("PAUSE", 0.24),
            ])
        evs.extend([("M", sc["intro_m"]), ("PAUSE", 0.28)])
        for d_spk, d_line in sc["dialogue"]:
            evs.append((d_spk, d_line))
            evs.append(("PAUSE", 0.24))
        evs.extend([
            ("PAUSE", 1.2),
            ("M", sc["unpack_m"]),
            ("PAUSE", 0.18),
            ("D", sc["unpack_d"]),
            ("PAUSE", 0.18),
            ("F", sc["unpack_f"]),
            ("PAUSE", 0.28),
        ])
        for d_spk, d_line in sc["dialogue"]:
            evs.append((d_spk, d_line))
            evs.append(("PAUSE", 0.24))
        evs.append(("PAUSE", 0.55))
        raw_blocks.append({
            "chapter": 1,
            "point_id": sc["point_id"],
            "title": sc["title"],
            "ja_focus": sc["dialogue"][0][1],
            "events": evs,
        })

    for idx_v, vc in enumerate(ch3_vocabs):
        evs = []
        if idx_v == 0:
            evs.extend([
                ("D", "日语里还有一类特别有灵气的词，全是假名拟态词，再加上几个专坑中国人的汉字读音。咱们挨个把画面勾出来。"),
                ("PAUSE", 0.30),
            ])
        evs.extend([
            ("JF", vc["word_ja"]),
            ("PAUSE", 0.32),
            ("M", vc["hook_m"]),
            ("PAUSE", 0.18),
            ("D", vc["hook_d"]),
            ("PAUSE", 0.18),
            ("F", vc["hook_f"]),
            ("PAUSE", 0.24),
            ("JM", vc["sent_ja"]),
            ("PAUSE", 0.55),
        ])
        raw_blocks.append({
            "chapter": 2,
            "point_id": vc["point_id"],
            "title": vc["title"],
            "ja_focus": vc["sent_ja"],
            "events": evs,
        })

    cooldown_sentences = []
    for tp in ch1_topics[:12]:
        cooldown_sentences.append((tp["point_id"], tp["title"], tp["ja_main"]))
        if len(cooldown_sentences) < 20 and tp.get("ja_alt"):
            cooldown_sentences.append((tp["point_id"], tp["title"], tp["ja_alt"]))
    cooldown_sentences = cooldown_sentences[:18]

    ch4_evs = [
        ("M", "最后咱们把中文全撤掉，把刚才聊透的这些地道日文原句连起来过一遍耳朵。"),
        ("PAUSE", 0.18),
        ("F", "不用刻意去翻中文，听听看那个画面是不是已经自己跳出来了。"),
        ("PAUSE", 0.50),
    ]
    for i, (_, _, ja_s) in enumerate(cooldown_sentences):
        spk = "JF" if i % 2 == 0 else "JM"
        ch4_evs.append((spk, ja_s))
        ch4_evs.append(("PAUSE", 1.25))

    ch4_evs.extend([
        ("D", "今天这壶茶就聊到这儿，刚才顺过的考点都已经记进进度里了。"),
        ("PAUSE", 0.18),
        ("M", "得空去把那五十道题刷绿，做完题加上听完这一桌闲聊，一百二十分稳稳揣兜里。咱们下回接着聊。"),
        ("PAUSE", 0.35),
    ])

    raw_blocks.append({
        "chapter": 3,
        "point_id": None,
        "title": "纯日语原速浸润",
        "ja_focus": cooldown_sentences[0][2] if cooldown_sentences else "今日も良い一日を。",
        "events": ch4_evs,
    })

    blocks = []
    for b in raw_blocks:
        expanded_evs = []
        for spk, val in b["events"]:
            expanded_evs.extend(expand_turn_events(spk, val, multilingual_speakers))
        nb = dict(b)
        nb["events"] = expanded_evs
        blocks.append(nb)

    sig_payload = f"v12_salon_3host:{engine_tag}:" + json.dumps(voice_map, sort_keys=True) + json.dumps(blocks, ensure_ascii=False)
    script_sig = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()[:14]
    if os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                print(f"Daily 3-host salon radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v12_")
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
        print(f"Synthesized {sum(1 for x in ok_results if x)} / {len(unique_turns)} unique 3-host salon turns.")

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
            {"idx": 0, "title": "语法", "start": chapter_starts.get(0, 0.0)},
            {"idx": 1, "title": "听力", "start": chapter_starts.get(1, 0.0)},
            {"idx": 2, "title": "词汇", "start": chapter_starts.get(2, 0.0)},
            {"idx": 3, "title": "纯日", "start": chapter_starts.get(3, 0.0)},
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
        print(f"Built 3-host salon radio episode: {final_dur:.1f}s ({mins} mins), size={os.path.getsize(RADIO_MP3_PATH)} bytes.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
