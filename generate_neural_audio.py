#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesizes Studio Neural TTS MP3 files (Cloud-Resilient + Local Studio Cache):
1) Conversational Voice-Tutor Question Prompts (*_q.mp3)
2) Explanations + Complete Sentence Read-Throughs (*_exp.mp3)
3) Individual Word Pronunciation Clips for Answer-Zone Hover/Tap Dictionary (audio/words/*.mp3)
If studio MP3s already exist on disk and network/edge-tts is offline in a sandbox,
preserves all cached studio MP3s cleanly without failing.
"""
import asyncio
import glob
import hashlib
import json
import os
import re

try:
    import certifi
    if os.environ.get("SSL_CERT_FILE") and os.path.exists(os.environ["SSL_CERT_FILE"]):
        certifi.where = lambda: os.environ["SSL_CERT_FILE"]
except Exception:
    pass

try:
    import edge_tts
except ImportError:
    edge_tts = None

from tutor_data import TUTOR_ITEMS, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
WORDS_AUDIO_DIR = os.path.join(AUDIO_DIR, "words")
MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

LISTENING_DIALOGUES = {
    "Q-20261114-001": [
        ("ja-JP-NanamiNeural", "-4%", "あ、もう五時だ。早く帰って、夕飯の支度しないと。"),
        ("ja-JP-KeitaNeural", "-5%", "1番。じゃあ、今日は作らなくていいね。"),
        ("ja-JP-KeitaNeural", "-5%", "2番。ほんとだ、急いで帰ろう。"),
        ("ja-JP-KeitaNeural", "-5%", "3番。夕飯、おいしかったね。"),
    ],
    "Q-20261114-002": [
        ("ja-JP-NanamiNeural", "-4%", "袋にお入れしましょうか？"),
        ("ja-JP-KeitaNeural", "-4%", "あ、袋はいいです。そのまま持って帰りますから。"),
        ("ja-JP-NanamiNeural", "-5%", "客は、袋をどうすると言っていますか？"),
    ],
    "Q-20261114-003": [
        ("ja-JP-NanamiNeural", "-4%", "ねえ、聞いた？駅前のパン屋さん、来月で閉まっちゃうんだって。"),
        ("ja-JP-KeitaNeural", "-5%", "1番。えっ、本当？あそこ好きだったのに。"),
        ("ja-JP-KeitaNeural", "-5%", "2番。うん、私が閉めたんだよ。"),
        ("ja-JP-KeitaNeural", "-5%", "3番。パン、買ってきてくれたの？"),
    ],
    "Q-20261114-004": [
        ("ja-JP-KeitaNeural", "-4%", "会議の前に、この資料、人数分コピーしといてくれる？"),
        ("ja-JP-NanamiNeural", "-5%", "1番。はい、すぐコピーしておきます。"),
        ("ja-JP-NanamiNeural", "-5%", "2番。昨日もう会議は終わりましたよ。"),
        ("ja-JP-NanamiNeural", "-5%", "3番。コピー機は使いません。"),
    ],
}


def split_zh_ja_segments(text: str):
    tokens = re.split(r"(「[^」]+」)", text)
    segs = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("「") and tok.endswith("」"):
            inner = tok[1:-1].strip()
            if not inner:
                continue
            if re.search(r"[\u3040-\u30ffー]", inner) or inner in ("貯金", "内緒"):
                segs.append(("ja", inner))
            else:
                segs.append(("zh", inner))
        else:
            sub = re.split(r"([\u4e00-\u9fff]*[\u3040-\u30ffー〜]+[\u4e00-\u9fff\u3040-\u30ffー〜]*)", tok)
            for s in sub:
                s_clean = s.strip()
                if not re.search(r"[\w\u3040-\u9fff]", s_clean):
                    continue
                if re.search(r"[\u3040-\u30ff]", s_clean):
                    segs.append(("ja", s_clean))
                else:
                    segs.append(("zh", s_clean))
    return segs


async def synth_ja(text: str, out_path: str, rate: str = "-4%"):
    if edge_tts is None:
        return
    try:
        comm = edge_tts.Communicate(text, "ja-JP-NanamiNeural", rate=rate, proxy=PROXY_URL)
        await comm.save(out_path)
    except Exception as exc:
        if not os.path.exists(out_path):
            print(f"[audio] skipped offline synthesis for {os.path.basename(out_path)}: {exc}")


async def synth_dialogue(turns, out_path: str):
    if edge_tts is None:
        return
    try:
        buf = bytearray()
        for voice, rate, line in turns:
            comm = edge_tts.Communicate(line, voice, rate=rate, proxy=PROXY_URL)
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
        with open(out_path, "wb") as f:
            f.write(buf)
    except Exception as exc:
        if not os.path.exists(out_path):
            print(f"[audio] skipped offline dialogue for {os.path.basename(out_path)}: {exc}")


async def synth_bilingual(text: str, out_path: str):
    if edge_tts is None:
        return
    try:
        segs = split_zh_ja_segments(text)
        buf = bytearray()
        for lang, seg in segs:
            voice = "ja-JP-NanamiNeural" if lang == "ja" else "zh-CN-XiaoxiaoNeural"
            rate = "-2%" if lang == "ja" else "+5%"
            comm = edge_tts.Communicate(seg, voice, rate=rate, proxy=PROXY_URL)
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
        with open(out_path, "wb") as f:
            f.write(buf)
    except Exception as exc:
        if not os.path.exists(out_path):
            print(f"[audio] skipped offline bilingual for {os.path.basename(out_path)}: {exc}")


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

    plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
    with open(plans[-1], encoding="utf-8") as f:
        plan = json.load(f)

    all_qs = []
    for sec in ("grammar", "henkei", "vocab", "listening"):
        for kind in ("formal", "quick"):
            for q in plan.get(sec, {}).get(kind, []):
                all_qs.append((sec, q))

    sem = asyncio.Semaphore(10)
    new_manifest = {"words": dict(old_manifest.get("words", {}))}

    async def process_question(sec, q):
        qid = q["id"]
        t_item = TUTOR_ITEMS.get(qid, {})
        turns = LISTENING_DIALOGUES.get(qid)

        q_file = f"{qid}_q.mp3"
        q_abs = os.path.join(AUDIO_DIR, q_file)
        if turns:
            q_sig = "dlg:" + json.dumps(turns, ensure_ascii=False)
            q_hash = hashlib.sha256(q_sig.encode("utf-8")).hexdigest()[:12]
            if (old_manifest.get(q_file) != q_hash and not os.path.exists(q_abs)) or not os.path.exists(q_abs):
                async with sem:
                    await synth_dialogue(turns, q_abs)
            new_manifest[q_file] = old_manifest.get(q_file, q_hash) if os.path.exists(q_abs) else q_hash
            q_rel = f"./audio/{q_file}"
        else:
            vq = t_item.get("voice_q") or q.get("stem", "")
            q_hash = hashlib.sha256(vq.encode("utf-8")).hexdigest()[:12]
            if not os.path.exists(q_abs):
                async with sem:
                    await synth_bilingual(vq, q_abs)
            new_manifest[q_file] = old_manifest.get(q_file, q_hash) if os.path.exists(q_abs) else q_hash
            q_rel = f"./audio/{q_file}"

        exp_txt = t_item.get("voice_exp") or q.get("hook_zh") or ""
        exp_hash = hashlib.sha256(exp_txt.encode("utf-8")).hexdigest()[:12]
        exp_file = f"{qid}_exp.mp3"
        exp_abs = os.path.join(AUDIO_DIR, exp_file)
        if not os.path.exists(exp_abs):
            async with sem:
                await synth_bilingual(exp_txt, exp_abs)
        new_manifest[exp_file] = old_manifest.get(exp_file, exp_hash) if os.path.exists(exp_abs) else exp_hash
        exp_rel = f"./audio/{exp_file}"

        new_manifest[f"meta:{qid}"] = {
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "spoken_text": exp_txt,
        }

    async def process_word(surface, info):
        speak_str = surface.replace("〜", "")
        if surface in ("半年", "内緒", "貯める", "貯金"):
            speak_str = info["kana"]
        w_hash = hashlib.sha256(speak_str.encode("utf-8")).hexdigest()[:10]
        w_file = f"w_{w_hash}.mp3"
        w_abs = os.path.join(WORDS_AUDIO_DIR, w_file)
        if not os.path.exists(w_abs):
            async with sem:
                await synth_ja(speak_str, w_abs, rate="-4%")
        new_manifest["words"][surface] = f"./audio/words/{w_file}"

    await asyncio.gather(
        *(process_question(sec, q) for sec, q in all_qs),
        *(process_word(surf, info) for surf, info in WORD_DICT.items()),
    )

    done_txt = "今天这一组全部过关了，去休息吧，明天继续。"
    done_hash = hashlib.sha256(done_txt.encode("utf-8")).hexdigest()[:12]
    done_abs = os.path.join(AUDIO_DIR, "done.mp3")
    if not os.path.exists(done_abs):
        await synth_bilingual(done_txt, done_abs)
    new_manifest["done.mp3"] = old_manifest.get("done.mp3", done_hash) if os.path.exists(done_abs) else done_hash

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Verified/synthesized {len(all_qs)} tutor Q/Exp pairs + {len(WORD_DICT)} word pronunciations.")


if __name__ == "__main__":
    asyncio.run(main())
