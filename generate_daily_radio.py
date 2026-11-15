#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily ~38 Minute "Qiang Qiang Three" Cultural Salon Podcast (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json) — Zen v23 Human Prosody Edition.

Hosts: 文涛 (W) · 文道 (D) · 子东 (X)
Key Design:
1) Zero date announcements, zero exam countdowns, zero classroom tone — cold-opens at 00:00.0
   into witty, culturally rich Japanese anthropology, literature, and everyday urban stories.
2) 5-Gear Dynamic Mandarin Prosody Sculptor (抑扬顿挫 · 有快有慢 · 口误改口 · 停顿找词)
   + 100% Same-Person Bilingual Vocal Cords (each host speaks slow Japanese in his OWN voice & accent):
    - W (文涛): `en-US-BrianMultilingualNeural` (bright, quick, lively northern host cadence; -4% to +19%)
    - D (文道): `ko-KR-HyunsuMultilingualNeural` (deep, warm, unhurried East Asian scholar baritone; -6% to +11%)
    - X (子东): `fr-FR-RemyMultilingualNeural` (crisp, dry intellectual critic wit; -5% to +15%)
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
MAX_TRIES = 5 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Keeps multi-clause Japanese quotes together in ONE continuous slow (-33%) utterance by the SAME speaker!
JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー]+(?:[、。！？\s]+[\u3040-\u30ffー]+)*[。！？]?)")

# Prosodic gear cue detectors for human-like fast/slow & pitch modulation
RUSH_CUE_RE = re.compile(
    r"(呸[，！]?|嘴瓢|说反了|说劈叉|不对不对|哦不对|哎不对|不是里见|不是东京|"
    r"哪有十把|哪有扫码枪|少说了俩零|哦四回|哦一千|哦不用两大碗|哦三分钟|哦日本哪儿|"
    r"害，|等会儿|等等[，！]|你先打住|神了！|好家伙|我的天|我的老天爷|哎哟喂|啧，你听听|啧啧)"
)
LOW_CUE_RE = re.compile(
    r"(说白了|讲句老实话|潜台词就是|背地里|片叶不沾身|杀人诛心|憋出内伤|心酸|"
    r"叹口气|神神秘秘|压低声音|柔声细气|特温柔地问|轻声嘱咐|低眉顺眼|全靠舌头底下|连根头发丝儿)"
)
FAST_CUE_RE = re.compile(
    r"(结果你们猜|一拍大腿|一拍胸脯|噌一下|百米冲刺|傻眼了|可不嘛|真绝了|"
    r"太准了|一点儿没错|完全正确|对极了|问到点子上了|那我肯定)"
)
LATCH_START_RE = re.compile(
    r"^(神了|等会儿|等等|那我肯定|对极了|对啊|对，|可不嘛|一点儿没错|一点儿不差|"
    r"完全正确|太准了|问到点子上了|哎哟|哦！|妙啊|我知道|我就干过)"
)
REFLECT_START_RE = re.compile(r"^(其实|前两天|如果有人|话说回来|而且讲句老实话)")


def resolve_point_key(point_id: str) -> str:
    if point_id in TUTOR_ITEMS:
        return TUTOR_ITEMS[point_id].get("point_key", point_id)
    for ext in EXTRA_PRIMARY_CARDS:
        if ext["id"] == point_id:
            return ext["point_key"]
    return point_id


GENERIC_POINT_LABELS = {"口语听辨", "高频假名副词", "核心词汇", "语法", "活用"}


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
                if pt and pt not in GENERIC_POINT_LABELS:
                    wrong_all.add(pt)
                if qid:
                    wrong_all.add(qid)
                if idx >= max(0, total - 25):
                    if pt and pt not in GENERIC_POINT_LABELS:
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


def load_previous_day_stories(today_str: str) -> tuple[set, set]:
    if not os.path.exists(RADIO_HISTORY_PATH):
        return set(), set()
    try:
        with open(RADIO_HISTORY_PATH, encoding="utf-8") as f:
            hist = json.load(f)
        by_date = hist.get("recent_days") or {}
        prior_dates = sorted(d for d in by_date.keys() if d < today_str)
        prev_1 = set(by_date.get(prior_dates[-1]) or []) if len(prior_dates) >= 1 else set()
        prev_2 = set(by_date.get(prior_dates[-2]) or []) if len(prior_dates) >= 2 else set()
        return prev_1, prev_2
    except Exception:
        return set(), set()


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
    keep_dates = sorted(hist["recent_days"].keys())[-10:]
    hist["recent_days"] = {k: hist["recent_days"][k] for k in keep_dates}
    with open(RADIO_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


async def detect_voice_map() -> dict:
    """
    Maps 5 dynamic Mandarin prosody gears + slow Japanese (-33%/-34%) to the
    EXACT SAME Multilingual Neural voice for each of the 3 male hosts:
    - W (文涛): en-US-BrianMultilingualNeural (bright, quick, lively chatterbox; +2Hz center)
    - D (文道): ko-KR-HyunsuMultilingualNeural (deep, warm East Asian scholar baritone; -4Hz center)
    - X (子东): fr-FR-RemyMultilingualNeural (crisp, dry intellectual critic cadence; -1Hz center)
    """
    w_voice = "en-US-BrianMultilingualNeural"
    d_voice = "ko-KR-HyunsuMultilingualNeural"
    x_voice = "fr-FR-RemyMultilingualNeural"

    if edge_tts is not None:
        try:
            voices = await edge_tts.list_voices(**COMM_KWARGS)
            short_names = {v.get("ShortName", "") for v in voices}
            for cand_w in ("en-US-BrianMultilingualNeural", "en-AU-WilliamMultilingualNeural"):
                if cand_w in short_names:
                    w_voice = cand_w
                    break
            for cand_d in ("ko-KR-HyunsuMultilingualNeural", "it-IT-GiuseppeMultilingualNeural"):
                if cand_d in short_names and cand_d != w_voice:
                    d_voice = cand_d
                    break
            for cand_x in ("fr-FR-RemyMultilingualNeural", "en-AU-WilliamMultilingualNeural", "it-IT-GiuseppeMultilingualNeural"):
                if cand_x in short_names and cand_x not in (w_voice, d_voice):
                    x_voice = cand_x
                    break
            print(f"Qiang-Qiang trio voices: W(文涛)={w_voice}, D(文道)={d_voice}, X(子东)={x_voice}")
        except Exception as e:
            print(f"[info] list_voices fallback to default trio voices: {e}")

    vmap = {
        # W (文涛): 清亮偏高半度、跳脱脆生、快慢急转
        "W":      (w_voice, "+7%", "+2Hz"),
        "W_MID":  (w_voice, "+7%", "+2Hz"),
        "W_FAST": (w_voice, "+13%", "+4Hz"),
        "W_RUSH": (w_voice, "+19%", "+6Hz"),
        "W_HES":  (w_voice, "-3%", "+1Hz"),
        "W_LOW":  (w_voice, "-4%", "-1Hz"),
        "W_JA":   (w_voice, "-33%", "+2Hz"),
        # D (文道): 东亚温厚低沉、从容儒雅的书房男中音
        "D":      (d_voice, "+1%", "-4Hz"),
        "D_MID":  (d_voice, "+1%", "-4Hz"),
        "D_FAST": (d_voice, "+6%", "-3Hz"),
        "D_RUSH": (d_voice, "+11%", "-2Hz"),
        "D_HES":  (d_voice, "-6%", "-5Hz"),
        "D_LOW":  (d_voice, "-6%", "-6Hz"),
        "D_JA":   (d_voice, "-34%", "-4Hz"),
        # X (子东): 清瘦干脆、冷面毒舌的学者腔调
        "X":      (x_voice, "+5%", "-1Hz"),
        "X_MID":  (x_voice, "+5%", "-1Hz"),
        "X_FAST": (x_voice, "+10%", "+1Hz"),
        "X_RUSH": (x_voice, "+15%", "+2Hz"),
        "X_HES":  (x_voice, "-3%", "-2Hz"),
        "X_LOW":  (x_voice, "-5%", "-3Hz"),
        "X_JA":   (x_voice, "-33%", "-1Hz"),
    }
    for g in ("", "_MID", "_FAST", "_RUSH", "_HES", "_LOW", "_JA"):
        vmap[f"M{g}"] = vmap[f"W{g}"]
        vmap[f"F{g}"] = vmap[f"X{g}"]
    return vmap


def _split_long_clause_on_comma(clause: str, max_len: int = 44) -> list[str]:
    if len(clause) <= max_len or "…" in clause or "，" not in clause:
        return [clause]
    commas = [m.start() for m in re.finditer(r"，", clause)]
    mid = len(clause) // 2
    best = None
    best_dist = 10**9
    for pos in commas:
        left_len = pos + 1
        right_len = len(clause) - left_len
        if left_len >= 12 and right_len >= 12:
            dist = abs(left_len - mid)
            if dist < best_dist:
                best_dist = dist
                best = pos
    if best is None:
        return [clause]
    left = clause[: best + 1].strip()
    right = clause[best + 1 :].strip()
    out = []
    for sub in (left, right):
        if len(sub) > 48 and "，" in sub:
            out.extend(_split_long_clause_on_comma(sub, max_len=48))
        else:
            out.append(sub)
    return out


def split_mandarin_breath_groups(text: str) -> list[str]:
    norm = re.sub(r"…+", "……", text.strip())
    if not norm:
        return []
    raw_atoms = [
        a.strip()
        for a in re.findall(r"[^…！？。；：]+(?:…+|[！？。；：]+)?", norm)
        if a and a.strip()
    ]
    sized = []
    for atom in raw_atoms:
        sized.extend(_split_long_clause_on_comma(atom))

    if len(sized) <= 1:
        return sized

    # Merge tiny (<8 visible chars) non-hesitation fragments so every clip has smooth phrase prosody
    merged = []
    carry = ""
    for seg in sized:
        cur = (carry + seg).strip() if carry else seg
        carry = ""
        vis_len = len(re.sub(r"[\s，、。！？；：…「」『』（）]", "", cur))
        if vis_len < 8 and not cur.endswith("…"):
            carry = cur
        else:
            merged.append(cur)
    if carry:
        if merged and not merged[-1].endswith("…"):
            merged[-1] = merged[-1] + carry
        else:
            merged.append(carry)
    return merged


def expand_mandarin_prosody(base_spk: str, pt_s: str, gear_state: list[str]) -> list[tuple[str, object]]:
    groups = split_mandarin_breath_groups(pt_s)
    if not groups:
        return []
    total = len(groups)
    events = []
    for idx, seg in enumerate(groups):
        prev_gear = gear_state[0]
        if seg.endswith("…"):
            gear = "HES"
            clean = re.sub(r"…+$", "。" if idx == total - 1 else "，", seg)
            clean = re.sub(r"…+", "，", clean)
            pause_after = 0.38
        elif RUSH_CUE_RE.search(seg):
            gear = "RUSH"
            clean = re.sub(r"…+", "，", seg)
            pause_after = 0.13
        elif LOW_CUE_RE.search(seg) or (
            idx == total - 1 and total >= 3 and "！" not in seg and "？" not in seg and not seg.endswith("：")
        ):
            gear = "LOW"
            clean = re.sub(r"…+", "，", seg)
            pause_after = 0.20 if clean.endswith("：") else 0.27
        elif seg.endswith(("？", "！", "？！", "！？")) or FAST_CUE_RE.search(seg):
            gear = "FAST"
            clean = re.sub(r"…+", "，", seg)
            pause_after = 0.18
        else:
            gear = "MID"
            clean = re.sub(r"…+", "，", seg)
            pause_after = 0.21 if clean[-1] in "。；" else 0.16

        # Guarantee adjacent breath-groups never lock into uniform speed & pitch
        if gear == prev_gear and gear not in ("HES", "RUSH"):
            if gear == "MID":
                gear = "FAST" if (idx % 2 == 1 or clean.endswith("：")) else "LOW"
            elif gear == "FAST":
                gear = "RUSH" if (base_spk == "W" and len(clean) <= 18) else "MID"
            elif gear == "LOW":
                gear = "MID"

        gear_state[0] = gear
        events.append((f"{base_spk}_{gear}", clean))
        if idx + 1 < total:
            events.append(("PAUSE", round(pause_after, 2)))
    return events


def expand_turn_events(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if spk not in ("W", "D", "X", "M", "F"):
        return [(spk, txt)]

    ja_spk = f"{spk}_JA"
    parts = JA_SPAN_RE.split(txt) if JA_SPAN_RE.search(txt) else [txt]
    out = []
    pending_pause = 0.0
    gear_state = [""]

    for idx, pt in enumerate(parts):
        if not pt:
            continue
        if idx % 2 == 1:
            ks = re.sub(r"\s+", "", pt.strip())
            if not ks:
                continue
            ended_punct = ks[-1] in "。！？"
            is_short_inline = (not ended_punct) and len(ks) <= 10
            if out:
                min_pre = 0.11 if is_short_inline else 0.20
                out.append(("PAUSE", round(max(pending_pause, min_pre), 2)))
            ja_utterance = ks if ended_punct else (ks + "。")
            out.append((ja_spk, ja_utterance))
            if ended_punct and len(ks) >= 7:
                pending_pause = 0.48
            elif ended_punct:
                pending_pause = 0.28
            elif is_short_inline:
                pending_pause = 0.12
            else:
                pending_pause = 0.18
        else:
            lead_m = re.match(r"^[\s』」）]*([。！？；，、：…]+)[\s『「（]*", pt)
            if lead_m:
                pchars = lead_m.group(1)
                if "…" in pchars:
                    pending_pause = max(pending_pause, 0.36)
                elif any(c in pchars for c in "。！？；"):
                    pending_pause = max(pending_pause, 0.30)
                else:
                    pending_pause = max(pending_pause, 0.15)
                pt = pt[lead_m.end() :]
            pt_s = pt.strip()
            if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                continue
            zh_evs = expand_mandarin_prosody(spk, pt_s, gear_state)
            if not zh_evs:
                continue
            if out:
                out.append(("PAUSE", round(max(pending_pause, 0.13), 2)))
            out.extend(zh_evs)
            last_txt = str(zh_evs[-1][1])
            if pt_s.endswith("…"):
                pending_pause = 0.38
            elif last_txt[-1] in "。！？；":
                pending_pause = 0.24
            elif last_txt[-1] in "，、：":
                pending_pause = 0.16
            else:
                pending_pause = 0.11
    return out if out else [(f"{spk}_MID", txt)]


def turn_switch_pause(next_spk: str, next_txt: str) -> float:
    s = str(next_txt).strip()
    if LATCH_START_RE.search(s):
        return 0.15
    if REFLECT_START_RE.search(s):
        return 0.40
    if next_spk == "W":
        return 0.24
    if next_spk == "D":
        return 0.33
    return 0.27


def synth_gemini_turn_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    base = spk.split("_")[0]
    voice_map_g = {"W": "Puck", "D": "Charon", "X": "Orus"}
    voice_name = voice_map_g.get(base, "Puck")
    prompt = (
        f"Speak naturally with varied human tempo and warm conversational wit like Qiang Qiang Three: {text}"
        if not spk.endswith("_JA")
        else f"Speak this Japanese phrase slowly, clearly, and distinctly in your own voice: {text}"
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
            # Strictly keep each host's OWN voice across all retries — never swap TTS voices!
            use_voice = voice
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

                await asyncio.wait_for(_pull(), timeout=48.0)
                if buf:
                    with open(out_path, "wb") as f:
                        f.write(buf)
                    return True
            except Exception as e:
                if attempt + 1 < MAX_TRIES:
                    await asyncio.sleep(0.6 * (attempt + 1))
                elif MAX_TRIES > 1:
                    print(f"[warn] radio turn synth failed ({use_voice}): {e!r}")
    return False


def trim_clip_silence(raw_path: str, trimmed_path: str) -> None:
    af_chain = (
        "silenceremove=start_periods=1:start_duration=0.0:start_threshold=-62dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0.0:start_threshold=-62dB,areverse,"
        "afade=t=in:st=0:d=0.010,areverse,afade=t=in:st=0:d=0.010,areverse"
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
    study_dt = (now_pt - datetime.timedelta(hours=5)).date()
    today_str = study_dt.strftime("%Y-%m-%d")
    days_left = max(0, (EXAM_DATE - study_dt).days)

    recent_wrong, hot_wrong = load_recent_mistakes()
    scores = load_mastery_priority(state, recent_wrong, hot_wrong)
    yesterday_stories, two_days_ago_stories = load_previous_day_stories(today_str)
    rng = random.Random(today_str)

    def story_rank(st: dict) -> float:
        pids = st.get("point_ids") or []
        pt_vals = sorted((scores.get(pid, 2.2) for pid in pids), reverse=True)
        top_avg = sum(pt_vals[:3]) / max(1, len(pt_vals[:3])) if pt_vals else 2.2
        repeat_penalty = (
            3.5 if st["id"] in yesterday_stories
            else (1.2 if st["id"] in two_days_ago_stories else 0.0)
        )
        jitter = rng.uniform(-0.12, 0.12)
        return -(top_avg - repeat_penalty + jitter)

    ranked_ids = {st["id"] for st in sorted(SALON_STORIES, key=story_rank)[:6]}
    selected_stories = [st for st in SALON_STORIES if st["id"] in ranked_ids]

    closing_pool = [
        [
            ("D", "其实啊……不知不觉咱们这壶热茶又喝见底了。你想想看，不管是在涩谷撒丫子赶末班车，还是在京都面对那碗不敢真喝的茶泡饭，日本人的脾气秉性，全藏在他们说话留的那半截尾巴里。"),
            ("X", "对，平时当闲篇儿听个乐呵，把这些风月掌故和男女心眼儿听熟了，下回再听见那些尾巴，根本不用过脑子，画面自个儿就蹦出来了。"),
            ("W", "得嘞，今儿咱们仨就先白活到这儿！您路上慢点儿走……哦要是骑车就慢点儿蹬，咱们下回接着聊！"),
        ],
        [
            ("D", "其实啊……你看咱们今儿从早高峰车厢一路聊到深夜小酒馆，日本人表面上规矩捆得紧，可一旦钻进巷子端起酒杯，酸甜苦辣和人情冷暖全在几句短话里头露了底。"),
            ("X", "没错，语言本来就不是印在纸上的死条文，把里头这些酒桌潜规则和男女小心思听出味儿来，那些说法自然就长在耳朵里了。"),
            ("W", "行嘞，茶也凉透了，今儿这桌闲篇儿咱们就先撤席！您忙您的去，明儿咱们换壶热茶接着侃！"),
        ],
        [
            ("D", "话说回来……每次咱们仨坐一块儿扯这些日本街头的烟火气，越聊越觉得，所谓地道的表达，其实就是替对方多留半寸台阶、或者替自己多藏半句真心。"),
            ("X", "对，不管是职场上打太极还是酒桌上掏心窝子，听懂了那层窗户纸，日语最难缠的弯弯绕也就顺过来了。"),
            ("W", "好家伙，一眨眼又聊到这会儿了！得，今儿咱们就散摊子，咱们下回接着聊！"),
        ],
    ]
    if today_str == "2026-11-14":
        closing_turns = closing_pool[0]
    else:
        day_ord = study_dt.toordinal()
        closing_turns = closing_pool[1 + (day_ord % (len(closing_pool) - 1))]

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
                    next_spk, next_val = turns[idx + 1]
                    evs.append(("PAUSE", turn_switch_pause(next_spk, str(next_val))))

        # Calm tea-sipping breather between round-table stories
        evs.append(("PAUSE", 1.45 if ch_idx + 1 < len(selected_stories) else 0.45))
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

    sig_payload = f"v25_qq3_script_true:{engine_tag}:" + json.dumps(voice_map, sort_keys=True) + json.dumps(blocks, ensure_ascii=False)
    script_sig = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()[:14]
    if os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                save_today_stories(today_str, [st["id"] for st in selected_stories])
                print(f"Daily Qiang-Qiang trio radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v25_")
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

        sem = asyncio.Semaphore(20)
        ok_results = await asyncio.gather(
            *(synth_turn(k, voice_map[k], txt, raw_p, sem) for (k, txt), (raw_p, _) in unique_turns.items())
        )
        ok_count = sum(1 for x in ok_results if x)
        print(f"Synthesized {ok_count} / {len(unique_turns)} unique Qiang-Qiang trio prosody clips.")
        min_required = max(1, int(len(unique_turns) * 0.95))
        if ok_count < min_required:
            raise RuntimeError(
                f"TTS clip synthesis below safety threshold ({ok_count}/{len(unique_turns)} < {min_required}); refusing to overwrite daily_radio.mp3"
            )

        turn_durs = {}
        trimmed_paths = {}

        def _trim_and_probe(item):
            key, (raw_p, trim_p) = item
            if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                trim_clip_silence(raw_p, trim_p)
                return key, trim_p, probe_duration(trim_p)
            return key, None, 0.0

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
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
        save_today_stories(today_str, [st["id"] for st in selected_stories])
        print(f"Built Qiang-Qiang trio episode: {final_dur:.1f}s ({mins} mins), stories={[s['short_tab'] for s in selected_stories]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
