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
from __future__ import annotations
import asyncio
import concurrent.futures
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
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

from adaptive_bank import (
    CORE_N3_KANA_VOCAB,
    EXTRA_PRIMARY_CARDS,
    EXTRA_WORDS,
    NEW_PRIMARY_CARDS,
    NEW_VARIANT_CARDS,
    VARIANT_CARDS,
)
from clear_explanations import CARDS_75
from direct_explain_rules import build_direct_exp_turns
from phrase_and_word_lexicon import PHRASE_AND_WORD_LEXICON
from sentence_lexicon import SENTENCE_LEXICON
from tutor_data import KANA_ADVERBS_36, TUTOR_ITEMS, WORD_DICT
from vocab_cards import VOCAB_CARDS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
WORDS_AUDIO_DIR = os.path.join(AUDIO_DIR, "words")
GA_AUDIO_DIR = os.path.join(AUDIO_DIR, "ga")
CONJ_AUDIO_DIR = os.path.join(AUDIO_DIR, "conj")
MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 5
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
    ("千五百円", "せんごひゃくえん"),
    ("一万二千円", "いちまんにせんえん"),
    ("八時間", "はちじかん"),
    ("一人暮らし", "ひとりぐらし"),
    ("歩き回って", "あるきまわって"),
    ("飲みかけ", "のみかけ"),
    ("賞味期限", "しょうみきげん"),
    ("新入社員", "しんにゅうしゃいん"),
    ("三人", "さんにん"),
    ("五分", "ごふん"),
    ("三階", "さんかい"),
    ("早起き", "はやおき"),
    ("月曜日", "げつようび"),
    ("頭に入らなかった", "あたまにはいらなかった"),
    ("仕事が入っちゃって", "しごとがはいっちゃって"),
    ("読みかけ", "よみかけ"),
    ("十時から", "じゅうじから"),
    ("三冊", "さんさつ"),
    ("一冊", "いっさつ"),
    ("五十メートル", "ごじゅうメートル"),
    ("三十分", "さんじゅっぷん"),
    ("二次会", "にじかい"),
    ("無断で", "むだんで"),
    ("内定", "ないてい"),
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
            print(f"Quiz Zen v20 Natural voices: T={t_voice} (+8% brisk ZH / +0% JA), JF/JM=+0% normal native speed")
        except Exception as e:
            print(f"[info] list_voices fallback: {e}")

    return {
        "JF": ("ja-JP-NanamiNeural", "+0%"),
        "JM": ("ja-JP-KeitaNeural", "+0%"),
        "T": (t_voice, "+8%"),
        "T_VC": (t_voice, "+5%"),
        "T_JA": (t_voice, "+0%"),
        "EXP_F_JA": (f_ja_voice, "+0%"),
    }


def expand_q_turn(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if not txt or not re.search(r"[\w\u3040-\u30ff\u4e00-\u9fff]", txt):
        return []
    return [(spk, txt)]


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
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return True
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


def _build_n2_q_turns(prompt_str: str, full_ja_str: str) -> list[tuple[str, object]]:
    """Mask the blank with a 0.55s pause so N2 question audio NEVER leaks the answer out loud!"""
    m_bl = re.search(r"[（(]\s*　*\s*[）)]", prompt_str or "")
    if m_bl:
        pre = prompt_str[: m_bl.start()].strip(" 、，")
        post = prompt_str[m_bl.end() :].strip()
        turns_q: list[tuple[str, object]] = []
        if pre:
            turns_q.append(("JF", pre))
        turns_q.append(("PAUSE", 0.55))
        if post and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", post):
            turns_q.append(("JF", post))
        if turns_q:
            return turns_q
    return [("JF", full_ja_str)]


def _clean_n2_spoken_zh(raw_s: str) -> str:
    """Convert N2 grammar formula shorthand into smooth natural spoken Chinese + clean kana spaces."""
    s = str(raw_s or "").strip()
    for src, dst in (
        ("Vない形去ない", "动词否定形去掉ない"),
        ("Vない形", "动词否定形"),
        ("Vます形去ます", "动词礼貌形词干"),
        ("Vます形", "动词礼貌形词干"),
        ("V辞书形", "动词原形"),
        ("V辞書形", "动词原形"),
        ("Vた形", "动词过去形"),
        ("Nの", "名词加の"),
        ("N1", "前项名词"),
        ("N2", "后项名词"),
        (" + ", " 接 "),
        ("＋", " 接 "),
        ("→", " 变成 "),
        (" / ", " 或者 "),
        ("/", "或者"),
    ):
        s = s.replace(src, dst)
    s = re.sub(r"\bN\b", "名词", s)
    s = re.sub(r"\bV\b", "动词", s)
    s = re.sub(r"([\u4e00-\u9fff])([\u3040-\u30ff])", r"\1 \2", s)
    s = re.sub(r"([\u3040-\u30ff])([\u4e00-\u9fff])", r"\1 \2", s)
    return re.sub(r"\s{2,}", " ", s).strip()


async def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(WORDS_AUDIO_DIR, exist_ok=True)
    os.makedirs(GA_AUDIO_DIR, exist_ok=True)
    os.makedirs(CONJ_AUDIO_DIR, exist_ok=True)

    old_manifest = {}
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, encoding="utf-8") as f:
                old_manifest = json.load(f)
        except Exception:
            old_manifest = {}

    vocab_only = "--vocab-only" in sys.argv
    ga_only = "--ga-only" in sys.argv
    partial_only = vocab_only or ga_only
    old_words = old_manifest.get("words", {})
    old_vc_map = old_manifest.get("vocab_cards", {})
    old_vc_hashes = old_manifest.get("vocab_card_hashes", {})
    old_ga_map = old_manifest.get("ga_cards", {})
    old_ga_hashes = old_manifest.get("ga_card_hashes", {})
    old_voice_coach = old_manifest.get("voice_coach", {})
    old_conj_map = old_manifest.get("conj_drills", {})
    old_conj_hashes = old_manifest.get("conj_drill_hashes", {})
    new_manifest = dict(old_manifest) if partial_only else {}
    new_manifest["words"] = dict(old_words)
    new_manifest["vocab_cards"] = dict(old_vc_map)
    new_manifest["vocab_card_hashes"] = dict(old_vc_hashes)
    new_manifest["ga_cards"] = dict(old_ga_map)
    new_manifest["ga_card_hashes"] = dict(old_ga_hashes)
    new_manifest["voice_coach"] = dict(old_voice_coach)
    new_manifest["conj_drills"] = dict(old_conj_map)
    new_manifest["conj_drill_hashes"] = dict(old_conj_hashes)
    can_synth = (edge_tts is not None) and (shutil.which("ffmpeg") is not None)

    voice_map = await detect_voice_map()
    det_tag = f"gemini:{GEMINI_TTS_MODEL}:v20_natural" if (GEMINI_API_KEY and genai is not None) else "edge:Brian+8_0_v20_natural"
    sem = asyncio.Semaphore(16)

    card_meta_lookup = {}
    if isinstance(TUTOR_ITEMS, dict):
        for _tid, _tval in TUTOR_ITEMS.items():
            card_meta_lookup[_tid] = dict(_tval, id=_tid)
    for _src_list in (EXTRA_PRIMARY_CARDS, NEW_PRIMARY_CARDS, VARIANT_CARDS, NEW_VARIANT_CARDS):
        for _it in _src_list:
            if _it.get("id"):
                card_meta_lookup[_it["id"]] = _it
    # Auto-activate N2 neural audio synthesis starting 2026-12-07 (rolling +7 day lookahead)
    _n2_active_vocab = {}
    try:
        from n2_prep.n2_curriculum_engine import build_n2_question_bank, build_n2_vocab_cards, get_phase_info
        _now_pt_na = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-8)))
        _study_d_na = os.environ.get("FORCE_STUDY_DATE", "").strip() or (_now_pt_na - datetime.timedelta(hours=4)).date().isoformat()
        _ph_na = get_phase_info(_study_d_na)
        if _ph_na.get("phase") in ("n2_climb", "n1_sprint"):
            _n2_win = int(_ph_na.get("n2_day") or 1) + 7
            for _np in build_n2_question_bank():
                if int(_np.get("day") or 999) <= _n2_win:
                    for _nc in ([_np["primary"]] + list(_np.get("variants") or [])):
                        _nid = _nc["id"]
                        card_meta_lookup[_nid] = {
                            "id": _nid,
                            "subject": "文法",
                            "point_key": _np["point_key"],
                            "prompt_display": _nc["prompt"],
                            "choices": _nc["choices"],
                            "answer": _nc["answer"],
                            "full_ja": _nc["full_ja"],
                            "zh_meaning": _nc["zh_meaning"],
                            "why_line": _nc["why_line"],
                            "form_line": _nc["form_line"],
                            "option_notes": _nc.get("opt_notes") or {},
                        }
            _n2_active_vocab = build_n2_vocab_cards()
    except Exception:
        _n2_active_vocab = {}

    to_build_q = {}
    to_build_exp = {}
    to_build_lp = {}  # filename -> list of (spk, val) turns for dynamic listening shuffle
    hashes_q = {}
    hashes_exp = {}
    hashes_lp = {}
    listen_specs = {}  # qid -> {"stem_file": ..., "opt_spk": ..., "opt_files": [(choice, fn), ...]}

    LISTEN_OPT_RE = re.compile(r"^(?:いち|に|さん)[。、\s]+")
    for spk_code in ("JF", "JM"):
        for idx_n, num_ja in ((1, "いち。"), (2, "に。"), (3, "さん。")):
            n_fn = f"num_{spk_code}_{idx_n}.mp3"
            n_hash = hashlib.sha256(f"v18lp:{spk_code}:{num_ja}".encode("utf-8")).hexdigest()[:12]
            hashes_lp[n_fn] = n_hash
            if old_manifest.get(n_fn) != n_hash or not os.path.exists(os.path.join(AUDIO_DIR, n_fn)):
                to_build_lp[n_fn] = [(spk_code, num_ja)]

    _all_synth_cards = dict(CARDS_75)
    for _nid, _nmeta in card_meta_lookup.items():
        if str(_nid).startswith(("N2G-", "N2V-")) and _nid not in _all_synth_cards:
            _prompt_ja = str(_nmeta.get("prompt_display") or "").strip()
            _full_ja = str(_nmeta.get("full_ja") or "").strip()
            _why = _clean_n2_spoken_zh(str(_nmeta.get("why_line") or ""))
            _form = _clean_n2_spoken_zh(str(_nmeta.get("form_line") or ""))
            _all_synth_cards[_nid] = {
                "id": _nid,
                "subject": "文法",
                "point_key": _nmeta.get("point_key", ""),
                "choices": _nmeta.get("choices") or [],
                "answer": _nmeta.get("answer", ""),
                "q_turns": _build_n2_q_turns(_prompt_ja, _full_ja),
                "exp_turns": [("T", f"{_why} {_form}".strip())],
            }

    for qid, card in _all_synth_cards.items():
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

        # Split blind listening cards into stem + 3 option clips so retries can shuffle 1/2/3 audio!
        q_turns = card.get("q_turns") or []
        first_opt_idx = next(
            (i for i, (s, v) in enumerate(q_turns) if s in ("JF", "JM") and LISTEN_OPT_RE.match(str(v))),
            None,
        )
        if first_opt_idx is not None and len(card.get("choices") or []) == 3:
            raw_stem = list(q_turns[:first_opt_idx])
            while raw_stem and raw_stem[-1][0] == "PAUSE":
                raw_stem.pop()
            stem_expanded = []
            for s, v in raw_stem:
                stem_expanded.extend(expand_q_turn(s, v))
            opt_turns_raw = [
                (s, LISTEN_OPT_RE.sub("", str(v)).strip())
                for s, v in q_turns[first_opt_idx:]
                if s in ("JF", "JM") and LISTEN_OPT_RE.match(str(v))
            ]
            if stem_expanded and len(opt_turns_raw) == 3:
                opt_spk = opt_turns_raw[0][0]
                stem_fn = f"{qid}_stem.mp3"
                stem_h = hashlib.sha256(("v18lps:" + json.dumps(stem_expanded, ensure_ascii=False)).encode("utf-8")).hexdigest()[:12]
                hashes_lp[stem_fn] = stem_h
                if old_manifest.get(stem_fn) != stem_h or not os.path.exists(os.path.join(AUDIO_DIR, stem_fn)):
                    to_build_lp[stem_fn] = stem_expanded
                opt_files = []
                for o_idx, (o_spk, o_txt) in enumerate(opt_turns_raw):
                    c_label = str(card["choices"][o_idx])
                    o_fn = f"{qid}_opt{o_idx}.mp3"
                    o_turns = [(o_spk, o_txt if o_txt.endswith(("。", "！", "？")) else (o_txt + "。"))]
                    o_h = hashlib.sha256(("v18lpo:" + json.dumps(o_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:12]
                    hashes_lp[o_fn] = o_h
                    if old_manifest.get(o_fn) != o_h or not os.path.exists(os.path.join(AUDIO_DIR, o_fn)):
                        to_build_lp[o_fn] = o_turns
                    opt_files.append((c_label, o_fn))
                listen_specs[qid] = {"stem_fn": stem_fn, "opt_spk": opt_spk, "opt_files": opt_files}

        # Zen v20 Natural Direct-to-Chinese Answer Audio: ZERO robotic filler ("考语法"), natural tutor reasoning!
        direct_turns = build_direct_exp_turns(qid, card, card_meta_lookup.get(qid))
        e_expanded = []
        for spk, val in direct_turns:
            e_expanded.extend(expand_exp_turn(spk, val, False))
        e_sig = f"v20e_natural:{det_tag}:" + json.dumps(e_expanded, ensure_ascii=False)
        e_hash = hashlib.sha256(e_sig.encode("utf-8")).hexdigest()[:12]
        hashes_exp[qid] = e_hash
        e_file = f"{qid}_exp.mp3"
        e_abs = os.path.join(AUDIO_DIR, e_file)
        if old_manifest.get(e_file) != e_hash or not os.path.exists(e_abs):
            to_build_exp[qid] = e_expanded

    built_q_ok = set()
    built_e_ok = set()
    built_lp_ok = set()

    if can_synth and (not partial_only) and (to_build_q or to_build_exp or to_build_lp):
        existing_v20 = sorted(glob.glob("/tmp/n3_cards_v20_*"))
        tmpdir = existing_v20[-1] if existing_v20 else tempfile.mkdtemp(prefix="n3_cards_v20_")
        try:
            needed_clips = {}
            needed_pauses = set()
            for turns in list(to_build_q.values()) + list(to_build_exp.values()) + list(to_build_lp.values()):
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
                if os.path.exists(trim_p) and os.path.getsize(trim_p) > 0:
                    return key, trim_p
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    trim_clip_silence(raw_p, trim_p)
                    return key, trim_p
                return key, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                for key, trim_p in pool.map(_trim_one, needed_clips.items()):
                    if trim_p:
                        clip_lookup[key] = trim_p

                def _stitch_q(item):
                    qid, turns = item
                    return qid, stitch_turns(turns, clip_lookup, silence_lookup, os.path.join(AUDIO_DIR, f"{qid}_q.mp3"), tmpdir, f"q_{qid}")

                def _stitch_e(item):
                    qid, turns = item
                    return qid, stitch_turns(turns, clip_lookup, silence_lookup, os.path.join(AUDIO_DIR, f"{qid}_exp.mp3"), tmpdir, f"e_{qid}")

                def _stitch_lp(item):
                    lp_fn, turns = item
                    return lp_fn, stitch_turns(turns, clip_lookup, silence_lookup, os.path.join(AUDIO_DIR, lp_fn), tmpdir, f"lp_{lp_fn.replace('.mp3', '')}")

                for qid, ok in pool.map(_stitch_q, to_build_q.items()):
                    if ok:
                        built_q_ok.add(qid)
                    else:
                        print(f"[warn] stitch_turns incomplete for Q {qid}")

                for qid, ok in pool.map(_stitch_e, to_build_exp.items()):
                    if ok:
                        built_e_ok.add(qid)
                    else:
                        print(f"[warn] stitch_turns incomplete for Exp {qid}")

                for lp_fn, ok in pool.map(_stitch_lp, to_build_lp.items()):
                    if ok:
                        built_lp_ok.add(lp_fn)
                    else:
                        print(f"[warn] stitch_turns incomplete for LP {lp_fn}")

            print(
                f"Synthesized & trimmed {len(built_q_ok)}/{len(to_build_q)} Q MP3s, "
                f"{len(built_e_ok)}/{len(to_build_exp)} Exp MP3s, and {len(built_lp_ok)}/{len(to_build_lp)} Listening-Part MP3s."
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    if not partial_only:
        for lp_fn, lph in hashes_lp.items():
            lp_abs = os.path.join(AUDIO_DIR, lp_fn)
            if os.path.exists(lp_abs):
                new_manifest[lp_fn] = lph if (lp_fn not in to_build_lp or lp_fn in built_lp_ok) else old_manifest.get(lp_fn, lph)

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
            meta_entry = {
                "q_audio": f"./audio/{q_file}?v={q_ver}" if os.path.exists(q_abs) else "",
                "exp_audio": f"./audio/{e_file}?v={e_ver}" if os.path.exists(e_abs) else "",
                "spoken_text": f"{card['zh_meaning']} {card['why_line']} {card['form_line']}",
            }
            lspec = listen_specs.get(qid)
            if lspec:
                stem_fn = lspec["stem_fn"]
                opt_spk = lspec["opt_spk"]
                num_fns = [f"num_{opt_spk}_1.mp3", f"num_{opt_spk}_2.mp3", f"num_{opt_spk}_3.mp3"]
                all_lp_exist = (
                    os.path.exists(os.path.join(AUDIO_DIR, stem_fn))
                    and all(os.path.exists(os.path.join(AUDIO_DIR, nf)) for nf in num_fns)
                    and all(os.path.exists(os.path.join(AUDIO_DIR, ofn)) for _, ofn in lspec["opt_files"])
                )
                if all_lp_exist:
                    stem_ver = new_manifest.get(stem_fn, hashes_lp.get(stem_fn, ""))[:8]
                    meta_entry["listen_parts"] = {
                        "stem": f"./audio/{stem_fn}?v={stem_ver}",
                        "nums": [f"./audio/{nf}" for nf in num_fns],
                        "opts": {
                            c_lbl: f"./audio/{ofn}?v={new_manifest.get(ofn, hashes_lp.get(ofn, ''))[:8]}"
                            for c_lbl, ofn in lspec["opt_files"]
                        },
                    }
            new_manifest[f"meta:{qid}"] = meta_entry

    # Word pronunciations across full sentence & phrase lexicon
    merged_words = dict(SENTENCE_LEXICON)
    merged_words.update(WORD_DICT)
    merged_words.update(EXTRA_WORDS)
    merged_words.update(PHRASE_AND_WORD_LEXICON)
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

    if not partial_only:
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

    def _to_bilingual_turns(txt: str) -> list:
        txt = str(txt or "").strip()
        if not txt:
            return []
        return expand_exp_turn("T", txt, False) if JA_SPAN_RE.search(txt) else [("T_VC", txt)]

    # Studio Bilingual Vocab Cards (Zen v21: Mnemonic FIRST -> Target Word SECOND -> Full Phrase LAST + direct-touch clips + v84 Hands-Free Voice Coach)
    from vocab_cards import VOICE_COACH_LINES, build_dynamic_vocab_card, build_vocab_audio_spec
    vc_all_cards = {}
    if not ga_only:
        for vw, vspec in VOCAB_CARDS.items():
            c = dict(vspec)
            c["word"] = vw
            vc_all_cards[vw] = c
        if os.path.exists(live_path):
            try:
                with open(live_path, encoding="utf-8") as lf:
                    for vp in json.load(lf).get("vocab_tracked", []):
                        vw = vp.get("word", "")
                        if vw and vw not in vc_all_cards:
                            vc_all_cards[vw] = build_dynamic_vocab_card(vw, merged_words.get(vw, {}))
            except Exception:
                pass
        for kw, _pitch, _desc in CORE_N3_KANA_VOCAB:
            if kw and kw not in vc_all_cards:
                vc_all_cards[kw] = build_dynamic_vocab_card(kw, merged_words.get(kw, {}), fallback_note=_desc)
        for n2_w, n2_vc in _n2_active_vocab.items():
            if n2_w and n2_w not in vc_all_cards:
                c2 = dict(n2_vc)
                c2["word"] = n2_w
                vc_all_cards[n2_w] = c2

    vc_jobs = {}
    vc_specs = {}
    coach_specs = {}
    vc_tag = "edge:Brian_v21_hook_word_phrase"
    for vw, vc in vc_all_cards.items():
        vc_id = hashlib.sha256(vw.encode("utf-8")).hexdigest()[:10]
        mode = vc.get("mode", "kana_meaning")
        aspec = build_vocab_audio_spec(vc)
        word_ja = aspec["word_ja"]
        chunk_ja = aspec["chunk_ja"]
        hook_only_turns = _to_bilingual_turns(aspec["hook_spoken"])
        ask_turns = _to_bilingual_turns(aspec["ask_spoken"])

        # 1) Isolated target word clip (for kana reading tap + front audio on kana/ear-first cards)
        word_turns = [("JF", word_ja)]
        word_file = f"vc_{vc_id}_word.mp3"
        word_hash = hashlib.sha256((f"v21vcw:{vc_tag}:" + json.dumps(word_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        # 2) Isolated full phrase/sentence clip (for tapping the big Japanese phrase/word block!)
        phrase_ja_eff = chunk_ja if (chunk_ja and chunk_ja != word_ja) else word_ja
        phrase_turns = [("JF", phrase_ja_eff)]
        phrase_file = f"vc_{vc_id}_phrase.mp3"
        phrase_hash = hashlib.sha256((f"v21vcp:{vc_tag}:" + json.dumps(phrase_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        # 3) Tap-mnemonic clip: Direct Mnemonic FIRST -> Target Word pronunciation SECOND
        hook_turns = [*hook_only_turns, ("PAUSE", 0.18), ("JF", word_ja)] if hook_only_turns else [("JF", word_ja)]
        hook_file = f"vc_{vc_id}_hook.mp3"
        hook_hash = hashlib.sha256((f"v21vch:{vc_tag}:" + json.dumps(hook_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        # 4) Pure-Japanese clip (Word -> Phrase) for mic pronunciation correction & clean fallback
        clean_turns = [("JF", word_ja)]
        if chunk_ja and chunk_ja != word_ja:
            clean_turns.extend([("PAUSE", 0.18), ("JF", chunk_ja)])
        clean_file = f"vc_{vc_id}_clean.mp3"
        clean_hash = hashlib.sha256((f"v21vcc:{vc_tag}:" + json.dumps(clean_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        # 5) Unified Auto-Reveal & Replay 3-Beat Clip: Mnemonic FIRST -> Target Word SECOND -> Full Phrase LAST
        rev_turns = list(hook_only_turns)
        if rev_turns:
            rev_turns.append(("PAUSE", 0.18))
        rev_turns.append(("JF", word_ja))
        if chunk_ja and chunk_ja != word_ja:
            rev_turns.extend([("PAUSE", 0.24), ("JF", chunk_ja)])
        rev_file = f"vc_{vc_id}_rev.mp3"
        rev_hash = hashlib.sha256((f"v21vcr:{vc_tag}:" + json.dumps(rev_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        # 6) Hands-Free Voice Coach spoken question clip (eyes-free Mandarin prompt, zero reading spoiler!)
        ask_file = f"vc_{vc_id}_ask.mp3"
        ask_hash = hashlib.sha256((f"v84vca:{vc_tag}:" + json.dumps(ask_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

        vc_specs[vw] = {
            "mode": mode,
            "front": (word_file, word_hash, word_turns) if mode != "kanji_read" else None,
            "rev": (rev_file, rev_hash, rev_turns),
            "full": (rev_file, rev_hash, rev_turns),
            "hook": (hook_file, hook_hash, hook_turns),
            "phrase": (phrase_file, phrase_hash, phrase_turns),
            "word": (word_file, word_hash, word_turns),
            "clean": (clean_file, clean_hash, clean_turns),
            "ask": (ask_file, ask_hash, ask_turns) if ask_turns else None,
        }
        for slot_key in ("rev", "hook", "phrase", "word", "clean", "ask"):
            slot_item = vc_specs[vw].get(slot_key)
            if not slot_item:
                continue
            fn, fh, ft = slot_item
            f_abs = os.path.join(WORDS_AUDIO_DIR, fn)
            if old_vc_hashes.get(fn) != fh or not os.path.exists(f_abs):
                vc_jobs[fn] = (fh, ft)

    if not ga_only:
        for ck, cline in VOICE_COACH_LINES.items():
            cturns = _to_bilingual_turns(cline)
            cfn = f"vc_coach_{ck}.mp3"
            chash = hashlib.sha256((f"v84coach:{vc_tag}:" + json.dumps(cturns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
            coach_specs[ck] = (cfn, chash, cturns)
            cf_abs = os.path.join(WORDS_AUDIO_DIR, cfn)
            if old_vc_hashes.get(cfn) != chash or not os.path.exists(cf_abs):
                vc_jobs[cfn] = (chash, cturns)

    vc_built_ok = set()
    if can_synth and vc_jobs:
        vc_tmp = tempfile.mkdtemp(prefix="n3_vc_v21_")
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
            print(f"Synthesized {len(vc_built_ok)}/{len(vc_jobs)} bilingual vocab & voice coach MP3s (v21/v84).")
        finally:
            shutil.rmtree(vc_tmp, ignore_errors=True)

    for vw, spec in vc_specs.items():
        entry = {}
        for slot in ("front", "rev", "full", "hook", "phrase", "word", "clean", "ask"):
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

    for ck, (cfn, chash, _) in coach_specs.items():
        cf_abs = os.path.join(WORDS_AUDIO_DIR, cfn)
        if os.path.exists(cf_abs):
            if cfn not in vc_jobs or cfn in vc_built_ok:
                new_manifest["vocab_card_hashes"][cfn] = chash
            ver = new_manifest["vocab_card_hashes"].get(cfn, chash)[:8]
            new_manifest["voice_coach"][ck] = f"./audio/words/{cfn}?v={ver}"

    # Studio Hands-Free Verb Conjugation & Keigo Voice Drills (v85: 48 drills x 3 studio clips)
    if not ga_only:
        from conjugation_drills import CONJUGATION_DRILLS, build_conj_audio_turns, conj_audio_basename
        cj_jobs = {}
        cj_specs = {}
        cj_tag = "edge:Brian_Nanami_v85_conj"
        for drill in CONJUGATION_DRILLS:
            did = drill["id"]
            raw_turns_map = build_conj_audio_turns(drill)
            slot_spec = {}
            for slot_key in ("ask", "teach", "model"):
                expanded_t = []
                for spk, val in raw_turns_map[slot_key]:
                    if spk == "T_VC":
                        expanded_t.extend(_to_bilingual_turns(str(val)))
                    else:
                        expanded_t.append((spk, val))
                fn = conj_audio_basename(did, slot_key)
                fh = hashlib.sha256((f"v85cj:{cj_tag}:" + json.dumps(expanded_t, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]
                slot_spec[slot_key] = (fn, fh, expanded_t)
                f_abs = os.path.join(CONJ_AUDIO_DIR, fn)
                if old_conj_hashes.get(fn) != fh or not os.path.exists(f_abs):
                    cj_jobs[fn] = (fh, expanded_t)
            cj_specs[did] = slot_spec

        cj_built_ok = set()
        if can_synth and cj_jobs:
            cj_tmp = tempfile.mkdtemp(prefix="n3_cj_v85_")
            try:
                cj_clips = {}
                cj_pauses = set()
                for _, (_, turns) in cj_jobs.items():
                    for spk, val in turns:
                        if spk == "PAUSE":
                            cj_pauses.add(round(float(val), 2))
                        else:
                            key = (spk, str(val))
                            if key not in cj_clips:
                                ch = hashlib.sha256(f"{spk}:{val}".encode("utf-8")).hexdigest()[:12]
                                cj_clips[key] = (os.path.join(cj_tmp, f"raw_{ch}.mp3"), os.path.join(cj_tmp, f"trim_{ch}.mp3"))

                cj_sil = {}
                for sec in sorted(cj_pauses):
                    sf = os.path.join(cj_tmp, f"sil_{int(round(sec * 100)):03d}.mp3")
                    make_silence_mp3(sec, sf)
                    cj_sil[sec] = sf

                await asyncio.gather(
                    *(
                        synth_raw_clip(spk, voice_map[spk][0], voice_map[spk][1], txt, raw_p, sem)
                        for (spk, txt), (raw_p, _) in cj_clips.items()
                    )
                )

                cj_lookup = {}

                def _trim_cj(item):
                    key, (raw_p, trim_p) = item
                    if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                        trim_clip_silence(raw_p, trim_p)
                        return key, trim_p
                    return key, None

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    for key, trim_p in pool.map(_trim_cj, cj_clips.items()):
                        if trim_p:
                            cj_lookup[key] = trim_p

                for fn, (fh, turns) in cj_jobs.items():
                    out_abs = os.path.join(CONJ_AUDIO_DIR, fn)
                    if stitch_turns(turns, cj_lookup, cj_sil, out_abs, cj_tmp, fn.replace(".mp3", "")):
                        cj_built_ok.add(fn)
                        new_manifest["conj_drill_hashes"][fn] = fh
                print(f"Synthesized {len(cj_built_ok)}/{len(cj_jobs)} studio conjugation drill MP3s (v85).")
            finally:
                shutil.rmtree(cj_tmp, ignore_errors=True)

        for did, spec in cj_specs.items():
            entry = {}
            for slot_key in ("ask", "teach", "model"):
                fn, fh, _ = spec[slot_key]
                f_abs = os.path.join(CONJ_AUDIO_DIR, fn)
                if os.path.exists(f_abs):
                    if fn not in cj_jobs or fn in cj_built_ok:
                        new_manifest["conj_drill_hashes"][fn] = fh
                    ver = new_manifest["conj_drill_hashes"].get(fn, fh)[:8]
                    entry[slot_key] = f"./audio/conj/{fn}?v={ver}"
                else:
                    entry[slot_key] = ""
            new_manifest["conj_drills"][did] = entry

    # Studio 3-Beat Grammar Audit Cards (Zen v22: Core Cue FIRST -> Pattern SECOND -> Full Example LAST + direct-touch clips)
    if not vocab_only:
        from grammar_audit_cards import GA_CANONICAL_EXAMPLES, GA_CARD_CURATION
        ga_jobs = {}
        ga_specs = {}
        ga_tag = "edge:Brian_v22_ga_3beat"
        for gid, (meaning, cue, pat_ja, hook_zh, _hl) in sorted(GA_CARD_CURATION.items()):
            safe_gid = re.sub(r"[^A-Za-z0-9_-]", "", gid)
            ex_ja = (GA_CANONICAL_EXAMPLES.get(gid) or ("", ""))[0].strip()
            pat_spoken = pat_ja.strip(" 。") + "。"
            ex_spoken = (ex_ja.strip(" 。") + "。") if ex_ja else pat_spoken
            hook_only_turns = _to_bilingual_turns(hook_zh)

            pat_turns = [("JF", pat_spoken)]
            pat_fn = f"ga_{safe_gid}_pat.mp3"
            pat_h = hashlib.sha256((f"v22gap:{ga_tag}:" + json.dumps(pat_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

            ex_turns = [("JF", ex_spoken)]
            ex_fn = f"ga_{safe_gid}_ex.mp3"
            ex_h = hashlib.sha256((f"v22gae:{ga_tag}:" + json.dumps(ex_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

            hook_turns = [*hook_only_turns, ("PAUSE", 0.18), ("JF", pat_spoken)] if hook_only_turns else [("JF", pat_spoken)]
            hook_fn = f"ga_{safe_gid}_hook.mp3"
            hook_h = hashlib.sha256((f"v22gah:{ga_tag}:" + json.dumps(hook_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

            rev_turns = list(hook_only_turns)
            if rev_turns:
                rev_turns.append(("PAUSE", 0.18))
            rev_turns.append(("JF", pat_spoken))
            if ex_spoken and ex_spoken != pat_spoken:
                rev_turns.extend([("PAUSE", 0.24), ("JF", ex_spoken)])
            rev_fn = f"ga_{safe_gid}_rev.mp3"
            rev_h = hashlib.sha256((f"v22gar:{ga_tag}:" + json.dumps(rev_turns, ensure_ascii=False)).encode("utf-8")).hexdigest()[:10]

            ga_specs[gid] = {
                "pat": (pat_fn, pat_h, pat_turns),
                "ex": (ex_fn, ex_h, ex_turns),
                "hook": (hook_fn, hook_h, hook_turns),
                "rev": (rev_fn, rev_h, rev_turns),
            }
            for slot_key in ("pat", "ex", "hook", "rev"):
                fn, fh, ft = ga_specs[gid][slot_key]
                f_abs = os.path.join(GA_AUDIO_DIR, fn)
                if old_ga_hashes.get(fn) != fh or not os.path.exists(f_abs):
                    ga_jobs[fn] = (fh, ft)

        ga_built_ok = set()
        if can_synth and ga_jobs:
            ga_tmp = tempfile.mkdtemp(prefix="n3_ga_v22_")
            try:
                ga_clips = {}
                ga_pauses = set()
                for _, (_, turns) in ga_jobs.items():
                    for spk, val in turns:
                        if spk == "PAUSE":
                            ga_pauses.add(round(float(val), 2))
                        else:
                            key = (spk, str(val))
                            if key not in ga_clips:
                                ch = hashlib.sha256(f"{spk}:{val}".encode("utf-8")).hexdigest()[:12]
                                ga_clips[key] = (os.path.join(ga_tmp, f"raw_{ch}.mp3"), os.path.join(ga_tmp, f"trim_{ch}.mp3"))

                ga_sil = {}
                for sec in sorted(ga_pauses):
                    sf = os.path.join(ga_tmp, f"sil_{int(round(sec * 100)):03d}.mp3")
                    make_silence_mp3(sec, sf)
                    ga_sil[sec] = sf

                await asyncio.gather(
                    *(
                        synth_raw_clip(spk, voice_map[spk][0], voice_map[spk][1], txt, raw_p, sem)
                        for (spk, txt), (raw_p, _) in ga_clips.items()
                    )
                )

                ga_lookup = {}

                def _trim_ga(item):
                    key, (raw_p, trim_p) = item
                    if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                        trim_clip_silence(raw_p, trim_p)
                        return key, trim_p
                    return key, None

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    for key, trim_p in pool.map(_trim_ga, ga_clips.items()):
                        if trim_p:
                            ga_lookup[key] = trim_p

                for fn, (fh, turns) in ga_jobs.items():
                    out_abs = os.path.join(GA_AUDIO_DIR, fn)
                    if stitch_turns(turns, ga_lookup, ga_sil, out_abs, ga_tmp, fn.replace(".mp3", "")):
                        ga_built_ok.add(fn)
                        new_manifest["ga_card_hashes"][fn] = fh
                print(f"Synthesized {len(ga_built_ok)}/{len(ga_jobs)} studio Grammar Audit MP3s (v22 cue->pat->example).")
            finally:
                shutil.rmtree(ga_tmp, ignore_errors=True)

        for gid, spec in ga_specs.items():
            entry = {}
            for slot in ("pat", "ex", "hook", "rev"):
                fn, fh, _ = spec[slot]
                f_abs = os.path.join(GA_AUDIO_DIR, fn)
                if os.path.exists(f_abs):
                    if fn not in ga_jobs or fn in ga_built_ok:
                        new_manifest["ga_card_hashes"][fn] = fh
                    ver = new_manifest["ga_card_hashes"].get(fn, fh)[:8]
                    entry[slot] = f"./audio/ga/{fn}?v={ver}"
                else:
                    entry[slot] = ""
            new_manifest["ga_cards"][gid] = entry

    if not partial_only:
        done_txt = "今天这五十个考点全部过关了。再去听一段三人闲聊，一百二十分就稳稳拿住了，好好歇会儿吧。"
        done_hash = hashlib.sha256((f"v18:{det_tag}:" + done_txt).encode("utf-8")).hexdigest()[:12]
        done_abs = os.path.join(AUDIO_DIR, "done.mp3")
        if (old_manifest.get("done.mp3") != done_hash or not os.path.exists(done_abs)) and can_synth:
            await synth_raw_clip("T", voice_map["T"][0], voice_map["T"][1], done_txt, done_abs, sem)
        if os.path.exists(done_abs):
            new_manifest["done.mp3"] = done_hash

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Verified {len(CARDS_75)} studio Zen v18 Q/Exp pairs + {len(new_manifest['words'])} word MP3s + {len(new_manifest['vocab_cards'])} vocab cards + {len(new_manifest['ga_cards'])} GA 3-beat cards (vocab_only={vocab_only}, ga_only={ga_only}).")


if __name__ == "__main__":
    asyncio.run(main())
