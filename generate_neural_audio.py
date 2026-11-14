#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesizes & stitches Studio Human-Teacher Neural TTS MP3 files (generate_neural_audio.py — Zen v11):
- Voice Tier 1 (Optional Studio Key): Google Gemini 2.5 Flash Preview TTS when GEMINI_API_KEY is set.
- Voice Tier 2 (Default Keyless SOTA): Microsoft Conversational Multilingual LLM-Prosody Voice
  (`zh-CN-XiaoxiaoMultilingualNeural` at natural +0% pace) so ONE warm bilingual teacher ("T") speaks
  both Mandarin and inline Japanese kana in a single uninterrupted human breath (zero mid-sentence voice chopping).
- Pure Japanese Question Reading (`q_turns`): `ja-JP-NanamiNeural` / `ja-JP-KeitaNeural` at `-2%`
  with ZERO "请听题", ZERO "空欄", ZERO "选", ZERO spoilers.
- Strips leading/trailing <-55dB digital silence AND applies 12ms cosine micro-fades for zero clicks.
- Synthesizes word pronunciations across WORD_DICT + EXTRA_WORDS + SENTENCE_LEXICON so every tapped word
  has instant meaning + native Japanese audio.
"""
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave

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

from adaptive_bank import CORE_N3_KANA_VOCAB, EXTRA_WORDS
from clear_explanations import CARDS_75
from sentence_lexicon import SENTENCE_LEXICON
from tutor_data import KANA_ADVERBS_36, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
WORDS_AUDIO_DIR = os.path.join(AUDIO_DIR, "words")
MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 4 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

KANA_RE = re.compile(r"([\u3040-\u30ffー]+)")

KANJI_FORCE_KANA = {
    "半年", "内緒", "貯める", "貯金", "出張", "主張", "書類", "万年筆",
    "封筒", "終電", "寮", "私用", "風邪", "一日中", "三日間", "今週中", "夜中",
}


async def detect_voice_map() -> tuple[dict, set]:
    vmap = {
        "JF": ("ja-JP-NanamiNeural", "-2%"),
        "JM": ("ja-JP-KeitaNeural", "-2%"),
        "T": ("zh-CN-XiaoxiaoNeural", "+0%"),
        "F": ("zh-CN-XiaoxiaoNeural", "+0%"),
        "M": ("zh-CN-YunxiNeural", "+0%"),
    }
    multilingual_speakers = set()
    if edge_tts is None:
        return vmap, multilingual_speakers
    try:
        voices = await edge_tts.list_voices(**COMM_KWARGS)
        short_names = {v.get("ShortName", "") for v in voices}
        if "zh-CN-XiaoxiaoMultilingualNeural" in short_names:
            vmap["T"] = ("zh-CN-XiaoxiaoMultilingualNeural", "+0%")
            vmap["F"] = ("zh-CN-XiaoxiaoMultilingualNeural", "+0%")
            multilingual_speakers.update({"T", "F"})
        for cand_m in (
            "zh-CN-YunxiaoMultilingualNeural",
            "zh-CN-YunyiMultilingualNeural",
            "zh-CN-YunfanMultilingualNeural",
        ):
            if cand_m in short_names:
                vmap["M"] = (cand_m, "+0%")
                multilingual_speakers.add("M")
                break
        print(
            f"Card voices selected: T={vmap['T'][0]} ({vmap['T'][1]}), "
            f"JF={vmap['JF'][0]}, JM={vmap['JM'][0]}, multilingual={sorted(multilingual_speakers)}"
        )
    except Exception as e:
        print(f"[info] list_voices fallback: {e}")
    return vmap, multilingual_speakers


def expand_turn_events(spk: str, val, multilingual_speakers: set) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val)
    if spk in ("T", "F", "M") and spk not in multilingual_speakers and KANA_RE.search(txt):
        ja_spk = "JM" if spk == "M" else "JF"
        parts = KANA_RE.split(txt)
        out = []
        for idx, pt in enumerate(parts):
            pt_s = pt.strip()
            if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                continue
            if out:
                out.append(("PAUSE", 0.05))
            out.append((ja_spk if idx % 2 == 1 else spk, pt_s))
        return out if out else [(spk, txt)]
    return [(spk, txt)]


def synth_gemini_tts_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    voice_name = "Aoede" if spk in ("T", "F", "JF") else "Puck"
    prompt = (
        f"Speak naturally like a calm, warm, real human Japanese teacher in a quiet room: {text}"
        if spk in ("T", "F", "M")
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
    except Exception as e:
        print(f"[info] Gemini TTS fallback to Multilingual Neural ({spk}): {e}")
        return False


async def synth_raw_clip(spk: str, voice: str, rate: str, text: str, out_path: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        if GEMINI_API_KEY and genai is not None and spk in ("T", "F", "M"):
            ok = await asyncio.to_thread(synth_gemini_tts_sync, spk, text, out_path)
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
                    print(f"[warn] synth_raw_clip failed ({voice}): {e}")
    return False


def trim_clip_silence(raw_path: str, trimmed_path: str) -> None:
    af_chain = (
        "silenceremove=start_periods=1:start_duration=0.0:start_threshold=-55dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0.0:start_threshold=-55dB,areverse,"
        "afade=t=in:st=0:d=0.012,areverse,afade=t=in:st=0:d=0.012,areverse"
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
            "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame",
            out_path,
        ],
        check=True,
    )


def stitch_turns(turns: list, clip_lookup: dict, silence_lookup: dict, out_path: str, tmpdir: str, tag: str) -> bool:
    lines = []
    for spk, val in turns:
        if spk == "PAUSE":
            sec = round(float(val), 2)
            sf = silence_lookup.get(sec)
            if sf and os.path.exists(sf):
                lines.append(f"file '{sf}'")
        else:
            cp = clip_lookup.get((spk, str(val)))
            if cp and os.path.exists(cp) and os.path.getsize(cp) > 0:
                lines.append(f"file '{cp}'")
            else:
                return False
    if not lines:
        return False
    if len(lines) == 1:
        only_file = lines[0].split("'")[1]
        with open(only_file, "rb") as rf, open(out_path, "wb") as wf:
            wf.write(rf.read())
        return True

    concat_txt = os.path.join(tmpdir, f"concat_{tag}.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", concat_txt,
            "-vn", "-ar", "24000", "-ac", "1", "-b:a", "48k", "-c:a", "libmp3lame",
            out_path,
        ],
        check=True,
    )
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


async def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(WORDS_AUDIO_DIR, exist_ok=True)

    old_manifest = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, encoding="utf-8") as f:
                old_manifest = json.load(f)
        except Exception:
            old_manifest = {}

    old_words = old_manifest.get("words", {})
    new_manifest = {"words": dict(old_words)}
    can_synth = (edge_tts is not None) and (shutil.which("ffmpeg") is not None)

    voice_map, multilingual_speakers = await detect_voice_map()
    engine_tag = f"gemini:{GEMINI_TTS_MODEL}" if (GEMINI_API_KEY and genai is not None) else f"edge:{voice_map['T'][0]}:{voice_map['T'][1]}"

    to_build_q = {}
    to_build_exp = {}
    hashes_q = {}
    hashes_exp = {}

    for qid, card in CARDS_75.items():
        q_expanded = []
        for spk, val in card["q_turns"]:
            q_expanded.extend(expand_turn_events(spk, val, multilingual_speakers))
        q_sig = f"v11q:{voice_map['JF'][0]}:" + json.dumps(q_expanded, ensure_ascii=False)
        q_hash = hashlib.sha256(q_sig.encode("utf-8")).hexdigest()[:12]
        hashes_q[qid] = q_hash
        q_file = f"{qid}_q.mp3"
        q_abs = os.path.join(AUDIO_DIR, q_file)
        if old_manifest.get(q_file) != q_hash or not os.path.exists(q_abs):
            to_build_q[qid] = q_expanded

        e_expanded = []
        for spk, val in card["exp_turns"]:
            e_expanded.extend(expand_turn_events(spk, val, multilingual_speakers))
        e_sig = f"v11e:{engine_tag}:" + json.dumps(e_expanded, ensure_ascii=False)
        e_hash = hashlib.sha256(e_sig.encode("utf-8")).hexdigest()[:12]
        hashes_exp[qid] = e_hash
        e_file = f"{qid}_exp.mp3"
        e_abs = os.path.join(AUDIO_DIR, e_file)
        if old_manifest.get(e_file) != e_hash or not os.path.exists(e_abs):
            to_build_exp[qid] = e_expanded

    sem = asyncio.Semaphore(6)

    if can_synth and (to_build_q or to_build_exp):
        tmpdir = tempfile.mkdtemp(prefix="n3_cards_v11_")
        try:
            needed_clips = {}
            needed_pauses = set()
            for turns in list(to_build_q.values()) + list(to_build_exp.values()):
                for spk, val in turns:
                    if spk == "PAUSE":
                        needed_pauses.add(round(float(val), 2))
                    else:
                        key = (spk, str(val))
                        if key not in needed_clips:
                            chash = hashlib.sha256(f"{spk}:{val}".encode("utf-8")).hexdigest()[:12]
                            raw_p = os.path.join(tmpdir, f"raw_{chash}.mp3")
                            trim_p = os.path.join(tmpdir, f"trim_{chash}.mp3")
                            needed_clips[key] = (raw_p, trim_p)

            silence_lookup = {}
            for sec in sorted(needed_pauses):
                sf = os.path.join(tmpdir, f"sil_{int(round(sec * 100)):03d}.mp3")
                make_silence_mp3(sec, sf)
                silence_lookup[sec] = sf

            await asyncio.gather(
                *(
                    synth_raw_clip(spk, voice_map[spk][0], voice_map[spk][1], txt, raw_p, sem)
                    for (spk, txt), (raw_p, _) in needed_clips.items()
                )
            )

            clip_lookup = {}
            for key, (raw_p, trim_p) in needed_clips.items():
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    trim_clip_silence(raw_p, trim_p)
                    clip_lookup[key] = trim_p

            built_q_cnt = 0
            for qid, turns in to_build_q.items():
                q_abs = os.path.join(AUDIO_DIR, f"{qid}_q.mp3")
                if stitch_turns(turns, clip_lookup, silence_lookup, q_abs, tmpdir, f"q_{qid}"):
                    built_q_cnt += 1

            built_e_cnt = 0
            for qid, turns in to_build_exp.items():
                e_abs = os.path.join(AUDIO_DIR, f"{qid}_exp.mp3")
                if stitch_turns(turns, clip_lookup, silence_lookup, e_abs, tmpdir, f"e_{qid}"):
                    built_e_cnt += 1

            print(f"Synthesized & trimmed {built_q_cnt}/{len(to_build_q)} Q MP3s and {built_e_cnt}/{len(to_build_exp)} Exp MP3s.")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    for qid, card in CARDS_75.items():
        q_file = f"{qid}_q.mp3"
        e_file = f"{qid}_exp.mp3"
        q_abs = os.path.join(AUDIO_DIR, q_file)
        e_abs = os.path.join(AUDIO_DIR, e_file)
        qh = hashes_q[qid]
        eh = hashes_exp[qid]

        if os.path.exists(q_abs):
            new_manifest[q_file] = qh if (qid not in to_build_q or can_synth) else old_manifest.get(q_file, qh)
        if os.path.exists(e_abs):
            new_manifest[e_file] = eh if (qid not in to_build_exp or can_synth) else old_manifest.get(e_file, eh)

        q_ver = new_manifest.get(q_file, qh)[:8]
        e_ver = new_manifest.get(e_file, eh)[:8]
        new_manifest[f"meta:{qid}"] = {
            "q_audio": f"./audio/{q_file}?v={q_ver}" if os.path.exists(q_abs) else "",
            "exp_audio": f"./audio/{e_file}?v={e_ver}" if os.path.exists(e_abs) else "",
            "spoken_text": f"{card['zh_meaning']} {card['why_line']} {card['form_line']}",
        }

    # Word pronunciations across full sentence lexicon
    merged_words = dict(SENTENCE_LEXICON)
    merged_words.update(WORD_DICT)
    merged_words.update(EXTRA_WORDS)
    for w, _, _ in CORE_N3_KANA_VOCAB:
        if w not in merged_words:
            merged_words[w] = {"kana": w}
    for fam in KANA_ADVERBS_36:
        for pr in fam.get("pairs", []):
            for side in ("a", "b"):
                w = pr[side]["w"]
                if w not in merged_words:
                    merged_words[w] = {"kana": w}

    word_sem = asyncio.Semaphore(8)

    async def process_word(surface, info):
        alias = info.get("audio_alias")
        if alias and alias in old_words:
            alias_abs = os.path.join(BASE_DIR, old_words[alias].split("?")[0].lstrip("./"))
            if os.path.exists(alias_abs):
                new_manifest["words"][surface] = old_words[alias]
                return
        speak_str = surface.replace("〜", "").strip()
        if surface in KANJI_FORCE_KANA and info.get("kana"):
            speak_str = info["kana"]
        w_hash = hashlib.sha256(speak_str.encode("utf-8")).hexdigest()[:10]
        w_file = f"w_{w_hash}.mp3"
        w_abs = os.path.join(WORDS_AUDIO_DIR, w_file)
        if not os.path.exists(w_abs) and can_synth:
            await synth_raw_clip("JF", "ja-JP-NanamiNeural", "-3%", speak_str, w_abs, word_sem)
        if os.path.exists(w_abs):
            new_manifest["words"][surface] = f"./audio/words/{w_file}"

    await asyncio.gather(*(process_word(surf, info) for surf, info in merged_words.items()))

    done_txt = "今天这五十个考点全部过关了。再把随身听顺完，一百二十分就稳稳拿住了，好好休息吧。"
    done_hash = hashlib.sha256((f"v11:{engine_tag}:" + done_txt).encode("utf-8")).hexdigest()[:12]
    done_abs = os.path.join(AUDIO_DIR, "done.mp3")
    if (old_manifest.get("done.mp3") != done_hash or not os.path.exists(done_abs)) and can_synth:
        await synth_raw_clip("T", voice_map["T"][0], voice_map["T"][1], done_txt, done_abs, sem)
    if os.path.exists(done_abs):
        new_manifest["done.mp3"] = done_hash

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Verified {len(CARDS_75)} studio v11 Q/Exp pairs + {len(new_manifest['words'])} word pronunciations.")


if __name__ == "__main__":
    asyncio.run(main())
