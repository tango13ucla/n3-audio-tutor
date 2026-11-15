#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesizes & stitches Studio Human-Teacher Neural TTS MP3 files (generate_neural_audio.py — Zen v18):
- Pure Japanese Question & Blind-Listening Reading (`q_turns` -> `*_q.mp3`):
  `ja-JP-NanamiNeural` / `ja-JP-KeitaNeural` at natural native `+0%` normal speed,
  with ZERO "请听题", ZERO "空欄", ZERO spoilers.
- 100% Same-Person Bilingual Teacher Explanation (`exp_turns` -> `*_exp.mp3`):
  Uses warm conversational `en-US-BrianMultilingualNeural` speaking brisk Mandarin at `+5%` (`T`)
  AND crisp, natural normal-speed Japanese at `+0%` (`T_JA`) — including converting the opening Japanese
  sentence to Kana via `pykakasi` + N3 reading overrides so ONE human voice reads both the Japanese
  sentence and the Chinese+Japanese explanation with zero "tape-recorder" voice jumps!
"""
import asyncio
import concurrent.futures
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
    import pykakasi
    _KKS = pykakasi.kakasi()
except Exception:
    _KKS = None

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
from vocab_cards import VOCAB_CARDS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
WORDS_AUDIO_DIR = os.path.join(AUDIO_DIR, "words")
MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 5 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー]+(?:[、。！？\s]+[\u3040-\u30ffー]+)*[。！？]?)")

KANJI_FORCE_KANA = {
    "半年", "内緒", "貯める", "貯金", "出張", "主張", "書類", "万年筆",
    "封筒", "終電", "寮", "私用", "風邪", "一日中", "三日間", "今週中", "夜中",
}

JA_PHRASE_OVERRIDES = [
    ("みんなの前で日本語でスピーチを話させられた", "みんなのまえで、にほんごでスピーチを、はなさせられた"),
    ("みんなの前で話させられた", "みんなのまえで、はなさせられた"),
    ("お風呂に入らないで", "おふろに、はいらないで"),
    ("私が払っておく", "わたしが、はらっておく"),
    ("早く払わなくちゃ", "はやく、はらわなくちゃ"),
    ("泣かずにはいられなかった", "なかずには、いられなかった"),
    ("仕事が入って", "しごとが、はいって"),
    ("四月に入って", "しがつに、はいって"),
    ("しゃがんで話しかけた", "しゃがんで、はなしかけた"),
    ("会議で話し合った", "かいぎで、はなしあった"),
    ("みんなには内緒", "みんなには、ないしょ"),
    ("レシートはここにある", "レシートは、ここにある"),
    ("解き方", "ときかた"),
    ("昼ご飯", "ひるごはん"),
    ("隣の人に", "となりのひとに"),
    ("親切な人が", "しんせつなひとが"),
    ("お金", "おかね"),
    ("ダイエット中", "ダイエットちゅう"),
    ("後にして", "あとにして"),
    ("雨が降りそうだ", "あめがふりそうだ"),
    ("野菜嫌い", "やさいぎらい"),
    ("子どもの頃", "こどものころ"),
    ("日本語", "にほんご"),
    ("日本", "にほん"),
    ("１０年", "じゅうねん"),
    ("十年", "じゅうねん"),
    ("１１時", "じゅういちじ"),
    ("十一時", "じゅういちじ"),
    ("九時", "くじ"),
    ("五時", "ごじ"),
    ("三日間", "みっかかん"),
    ("一日中", "いちにちじゅう"),
    ("一日じゅう", "いちにちじゅう"),
    ("今週中", "こんしゅうじゅう"),
    ("今週じゅう", "こんしゅうじゅう"),
    ("夜中", "よなか"),
    ("半年", "はんとし"),
    ("内緒", "ないしょ"),
    ("海外出張中", "かいがいしゅっちょうちゅう"),
    ("出張", "しゅっちょう"),
    ("主張", "しゅちょう"),
    ("書類", "しょるい"),
    ("種類", "しゅるい"),
    ("私用", "しよう"),
    ("お宅", "おたく"),
    ("風邪", "かぜ"),
    ("人数分", "にんずうぶん"),
    ("夕飯", "ゆうはん"),
    ("支度", "したく"),
    ("昨日", "きのう"),
    ("今日", "きょう"),
    ("明日", "あした"),
    ("上手", "じょうず"),
    ("本当", "ほんとう"),
    ("少子化", "しょうしか"),
]


def ja_sentence_to_kana(text: str) -> str:
    s = str(text).strip()
    for src, dst in JA_PHRASE_OVERRIDES:
        s = s.replace(src, dst)
    if _KKS is not None:
        conv = _KKS.convert(s)
        out_parts = []
        for item in conv:
            orig = item.get("orig", "")
            if re.search(r"[\u4e00-\u9fff0-9０-９]", orig):
                out_parts.append(item.get("hira") or orig)
            else:
                out_parts.append(orig)
        s = "".join(out_parts)
    # Guard against では/には particle misparse before word-initial は
    s = s.replace("まえではなさせ", "まえで、はなさせ").replace("おふろにはいら", "おふろに、はいら")
    return s


async def detect_voice_map() -> dict:
    t_voice = "en-US-BrianMultilingualNeural"
    f_ja_voice = "en-US-AvaMultilingualNeural"
    if edge_tts is not None:
        try:
            voices = await edge_tts.list_voices(**COMM_KWARGS)
            short_names = {v.get("ShortName", "") for v in voices}
            for cand_t in (
                "en-US-BrianMultilingualNeural",
                "ko-KR-HyunsuMultilingualNeural",
                "it-IT-GiuseppeMultilingualNeural",
                "en-US-EmmaMultilingualNeural",
            ):
                if cand_t in short_names:
                    t_voice = cand_t
                    break
            for cand_f in ("en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural"):
                if cand_f in short_names:
                    f_ja_voice = cand_f
                    break
            print(f"Quiz Zen v18 voices: T={t_voice} (+5% ZH / +0% JA), JF/JM=+0% normal native speed")
        except Exception as e:
            print(f"[info] list_voices fallback: {e}")

    return {
        "JF": ("ja-JP-NanamiNeural", "+0%"),
        "JM": ("ja-JP-KeitaNeural", "+0%"),
        "T": (t_voice, "+5%"),
        "T_VC": (t_voice, "+5%"),
        "T_JA": (t_voice, "+0%"),
        "EXP_F_JA": (f_ja_voice, "+0%"),
    }


def expand_q_turn(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    return [(spk, str(val).strip())]


def expand_exp_turn(spk: str, val, two_speaker_dialogue: bool) -> list:
    if spk == "PAUSE":
        return [("PAUSE", round(max(float(val), 0.24), 2))]
    txt = str(val).strip()
    if spk in ("JF", "JM"):
        kana_txt = ja_sentence_to_kana(txt)
        if not kana_txt.endswith(("。", "！", "？")):
            kana_txt += "。"
        target_spk = "EXP_F_JA" if (two_speaker_dialogue and spk == "JF") else "T_JA"
        return [(target_spk, kana_txt)]

    # Teacher bilingual turn ("T"): brisk +5% Mandarin + natural +0% inline Japanese in the SAME voice!
    if JA_SPAN_RE.search(txt):
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
                ks = ks.replace("まえではなさせ", "まえで、はなさせ").replace("おふろにはいら", "おふろに、はいら")
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.08), 2)))
                ended_punct = ks[-1] in "。！？"
                out.append(("T_JA", ks if ended_punct else (ks + "。")))
                pending_pause = 0.14 if len(ks) >= 6 else 0.09
            else:
                lead_m = re.match(r"^[\s』」）]*([。！？；，、：]+)[\s『「（]*", pt)
                if lead_m:
                    pchars = lead_m.group(1)
                    if any(c in pchars for c in "。！？；"):
                        pending_pause = max(pending_pause, 0.24)
                    else:
                        pending_pause = max(pending_pause, 0.12)
                    pt = pt[lead_m.end():]
                pt_s = pt.strip()
                if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                    continue
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.08), 2)))
                out.append(("T", pt_s))
                if pt_s[-1] in "。！？；":
                    pending_pause = 0.22
                elif pt_s[-1] in "，、：":
                    pending_pause = 0.12
                else:
                    pending_pause = 0.08
        return out if out else [("T", txt)]
    return [("T", txt)]


def synth_gemini_tts_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    voice_name = "Aoede" if spk in ("JF", "EXP_F_JA") else "Charon"
    prompt = (
        f"Speak briskly, warmly, and naturally in Mandarin like a witty friend: {text}"
        if spk == "T"
        else f"Speak this Japanese naturally and clearly at normal native conversational speed: {text}"
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
        if GEMINI_API_KEY and genai is not None and spk in ("T", "T_JA", "EXP_F_JA"):
            ok = await asyncio.to_thread(synth_gemini_tts_sync, spk, text, out_path)
            if ok:
                return True
        if edge_tts is None:
            return False
        speak_txt = text
        if spk in ("T", "T_VC", "T_JA", "EXP_F_JA") and len(speak_txt) <= 2 and speak_txt[-1] not in "。！？，、：":
            speak_txt = speak_txt + "。"
        for attempt in range(MAX_TRIES):
            use_voice = (
                "ko-KR-HyunsuMultilingualNeural"
                if (spk in ("T", "T_VC", "T_JA") and attempt == MAX_TRIES - 1 and MAX_TRIES > 1 and attempt >= 2)
                else voice
            )
            use_txt = (speak_txt + "。") if (attempt >= 1 and speak_txt[-1] not in "。！？") else speak_txt
            try:
                buf = bytearray()
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
                    print(f"[warn] synth_raw_clip failed ({use_voice} | {speak_txt!r}): {e!r}")
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
    old_vc_map = old_manifest.get("vocab_cards", {})
    old_vc_hashes = old_manifest.get("vocab_card_hashes", {})
    new_manifest = {
        "words": dict(old_words),
        "vocab_cards": dict(old_vc_map),
        "vocab_card_hashes": dict(old_vc_hashes),
    }
    can_synth = (edge_tts is not None) and (shutil.which("ffmpeg") is not None)

    voice_map = await detect_voice_map()
    det_tag = f"gemini:{GEMINI_TTS_MODEL}:v18" if (GEMINI_API_KEY and genai is not None) else "edge:Brian+5_0_v18"

    to_build_q = {}
    to_build_exp = {}
    hashes_q = {}
    hashes_exp = {}

    for qid, card in CARDS_75.items():
        q_sig = "v18q:+0%:" + json.dumps(card["q_turns"], ensure_ascii=False)
        q_hash = hashlib.sha256(q_sig.encode("utf-8")).hexdigest()[:12]
        hashes_q[qid] = q_hash
        q_file = f"{qid}_q.mp3"
        q_abs = os.path.join(AUDIO_DIR, q_file)
        if old_manifest.get(q_file) != q_hash or not os.path.exists(q_abs):
            q_expanded = []
            for spk, val in card["q_turns"]:
                q_expanded.extend(expand_q_turn(spk, val))
            to_build_q[qid] = q_expanded

        spk_set = {s for s, _ in card["exp_turns"]}
        two_spk = ("JF" in spk_set and "JM" in spk_set)
        e_expanded = []
        for spk, val in card["exp_turns"]:
            e_expanded.extend(expand_exp_turn(spk, val, two_spk))
        e_sig = f"v18e:{det_tag}:" + json.dumps(e_expanded, ensure_ascii=False)
        e_hash = hashlib.sha256(e_sig.encode("utf-8")).hexdigest()[:12]
        hashes_exp[qid] = e_hash
        e_file = f"{qid}_exp.mp3"
        e_abs = os.path.join(AUDIO_DIR, e_file)
        if old_manifest.get(e_file) != e_hash or not os.path.exists(e_abs):
            to_build_exp[qid] = e_expanded

    sem = asyncio.Semaphore(14)
    built_q_ok = set()
    built_e_ok = set()

    if can_synth and (to_build_q or to_build_exp):
        tmpdir = tempfile.mkdtemp(prefix="n3_cards_v18_")
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

            def _trim_one(item):
                key, (raw_p, trim_p) = item
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    trim_clip_silence(raw_p, trim_p)
                    return key, trim_p
                return key, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                for key, trim_p in pool.map(_trim_one, needed_clips.items()):
                    if trim_p:
                        clip_lookup[key] = trim_p

            for qid, turns in to_build_q.items():
                q_abs = os.path.join(AUDIO_DIR, f"{qid}_q.mp3")
                if stitch_turns(turns, clip_lookup, silence_lookup, q_abs, tmpdir, f"q_{qid}"):
                    built_q_ok.add(qid)
                else:
                    print(f"[warn] stitch_turns incomplete for Q {qid}")

            for qid, turns in to_build_exp.items():
                e_abs = os.path.join(AUDIO_DIR, f"{qid}_exp.mp3")
                if stitch_turns(turns, clip_lookup, silence_lookup, e_abs, tmpdir, f"e_{qid}"):
                    built_e_ok.add(qid)
                else:
                    print(f"[warn] stitch_turns incomplete for Exp {qid}")

            print(f"Synthesized & trimmed {len(built_q_ok)}/{len(to_build_q)} Q MP3s (+0%) and {len(built_e_ok)}/{len(to_build_exp)} Exp MP3s (+5% ZH / +0% JA).")
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
            new_manifest[q_file] = qh if (qid not in to_build_q or qid in built_q_ok) else old_manifest.get(q_file, qh)
        if os.path.exists(e_abs):
            new_manifest[e_file] = eh if (qid not in to_build_exp or qid in built_e_ok) else old_manifest.get(e_file, eh)

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
    live_path = os.path.join(BASE_DIR, "n3_live_state.json")
    if os.path.exists(live_path):
        try:
            with open(live_path, encoding="utf-8") as lf:
                for vp in json.load(lf).get("vocab_tracked", []):
                    vw = vp.get("word", "")
                    if vw and vw not in merged_words:
                        merged_words[vw] = {"kana": vw}
        except Exception:
            pass


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
            await synth_raw_clip("JF", "ja-JP-NanamiNeural", "+0%", speak_str, w_abs, word_sem)
        if os.path.exists(w_abs):
            new_manifest["words"][surface] = f"./audio/words/{w_file}"

    await asyncio.gather(*(process_word(surf, info) for surf, info in merged_words.items()))

    # Studio Bilingual Dual-Mode Vocab Cards (Japanese word+chunk + warm Mandarin meaning)
    vc_jobs = {}
    vc_specs = {}
    vc_tag = "edge:Brian_v19"
    for vw, vc in VOCAB_CARDS.items():
        vc_id = hashlib.sha256(vw.encode("utf-8")).hexdigest()[:10]
        mode = vc.get("mode", "kana_meaning")
        ja_s = str(vc.get("ja_speak") or vw).strip()
        zh_s = str(vc.get("zh_speak") or vc.get("zh") or "").strip()
        if mode == "kanji_read":
            rev_turns = [("JF", ja_s), ("PAUSE", 0.22), ("T_VC", zh_s)] if zh_s else [("JF", ja_s)]
            rev_file = f"vc_{vc_id}_rev.mp3"
            rev_hash = hashlib.sha256((f"v19vc:{vc_tag}:" + json.dumps(rev_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
            vc_specs[vw] = {"mode": mode, "front": None, "rev": (rev_file, rev_hash, rev_turns), "full": (rev_file, rev_hash, rev_turns)}
            rev_abs = os.path.join(WORDS_AUDIO_DIR, rev_file)
            if old_vc_hashes.get(rev_file) != rev_hash or not os.path.exists(rev_abs):
                vc_jobs[rev_file] = (rev_hash, rev_turns)
        else:
            front_turns = [("JF", ja_s)]
            rev_turns = [("T_VC", zh_s)] if zh_s else [("JF", ja_s)]
            full_turns = [("JF", ja_s), ("PAUSE", 0.22), ("T_VC", zh_s)] if zh_s else [("JF", ja_s)]
            front_file = f"vc_{vc_id}_front.mp3"
            rev_file = f"vc_{vc_id}_rev.mp3"
            full_file = f"vc_{vc_id}_full.mp3"
            front_hash = hashlib.sha256(("v19vcf:" + json.dumps(front_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
            rev_hash = hashlib.sha256((f"v19vcr:{vc_tag}:" + json.dumps(rev_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
            full_hash = hashlib.sha256((f"v19vcx:{vc_tag}:" + json.dumps(full_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
            vc_specs[vw] = {
                "mode": mode,
                "front": (front_file, front_hash, front_turns),
                "rev": (rev_file, rev_hash, rev_turns),
                "full": (full_file, full_hash, full_turns),
            }
            for fn, fh, ft in (vc_specs[vw]["front"], vc_specs[vw]["rev"], vc_specs[vw]["full"]):
                f_abs = os.path.join(WORDS_AUDIO_DIR, fn)
                if old_vc_hashes.get(fn) != fh or not os.path.exists(f_abs):
                    vc_jobs[fn] = (fh, ft)

    vc_built_ok = set()
    if can_synth and vc_jobs:
        vc_tmp = tempfile.mkdtemp(prefix="n3_vc_v19_")
        try:
            vc_clips = {}
            vc_pauses = set()
            for _, (_, turns) in vc_jobs.items():
                for spk, val in turns:
                    if spk == "PAUSE":
                        vc_pauses.add(round(float(val), 2))
                    else:
                        key = (spk, str(val))
                        if key not in vc_clips:
                            ch = hashlib.sha256(f"{spk}:{val}".encode("utf-8")).hexdigest()[:12]
                            vc_clips[key] = (os.path.join(vc_tmp, f"raw_{ch}.mp3"), os.path.join(vc_tmp, f"trim_{ch}.mp3"))

            vc_sil = {}
            for sec in sorted(vc_pauses):
                sf = os.path.join(vc_tmp, f"sil_{int(round(sec * 100)):03d}.mp3")
                make_silence_mp3(sec, sf)
                vc_sil[sec] = sf

            await asyncio.gather(
                *(
                    synth_raw_clip(spk, voice_map[spk][0], voice_map[spk][1], txt, raw_p, sem)
                    for (spk, txt), (raw_p, _) in vc_clips.items()
                )
            )

            vc_lookup = {}

            def _trim_vc(item):
                key, (raw_p, trim_p) = item
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    trim_clip_silence(raw_p, trim_p)
                    return key, trim_p
                return key, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                for key, trim_p in pool.map(_trim_vc, vc_clips.items()):
                    if trim_p:
                        vc_lookup[key] = trim_p

            for fn, (fh, turns) in vc_jobs.items():
                out_abs = os.path.join(WORDS_AUDIO_DIR, fn)
                if stitch_turns(turns, vc_lookup, vc_sil, out_abs, vc_tmp, fn.replace(".mp3", "")):
                    vc_built_ok.add(fn)
                    new_manifest["vocab_card_hashes"][fn] = fh
            print(f"Synthesized {len(vc_built_ok)}/{len(vc_jobs)} bilingual vocab card MP3s.")
        finally:
            shutil.rmtree(vc_tmp, ignore_errors=True)

    for vw, spec in vc_specs.items():
        entry = {}
        for slot in ("front", "rev", "full"):
            item = spec.get(slot)
            if not item:
                entry[slot] = ""
                continue
            fn, fh, _ = item
            f_abs = os.path.join(WORDS_AUDIO_DIR, fn)
            if os.path.exists(f_abs):
                if fn not in vc_jobs or fn in vc_built_ok:
                    new_manifest["vocab_card_hashes"][fn] = fh
                ver = new_manifest["vocab_card_hashes"].get(fn, fh)[:8]
                entry[slot] = f"./audio/words/{fn}?v={ver}"
            else:
                entry[slot] = ""
        new_manifest["vocab_cards"][vw] = entry

    done_txt = "今天这五十个考点全部过关了。再去听一段三人闲聊，一百二十分就稳稳拿住了，好好歇会儿吧。"
    done_hash = hashlib.sha256((f"v18:{det_tag}:" + done_txt).encode("utf-8")).hexdigest()[:12]
    done_abs = os.path.join(AUDIO_DIR, "done.mp3")
    if (old_manifest.get("done.mp3") != done_hash or not os.path.exists(done_abs)) and can_synth:
        await synth_raw_clip("T", voice_map["T"][0], voice_map["T"][1], done_txt, done_abs, sem)
    if os.path.exists(done_abs):
        new_manifest["done.mp3"] = done_hash

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Verified {len(CARDS_75)} studio Zen v18 Q/Exp pairs + {len(new_manifest['words'])} word MP3s + {len(new_manifest['vocab_cards'])} dual-mode vocab cards.")


if __name__ == "__main__":
    asyncio.run(main())
