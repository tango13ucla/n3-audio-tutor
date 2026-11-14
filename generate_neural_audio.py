#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesizes & verifies Studio Neural TTS MP3 files for:
- All 50 Core N3 Exam Pillars (35 base + 15 Tier-S additions)
- All 24 Reverse-Angle Variant Quizzes (VAR-*)
- Full Word Pronunciation Dictionary (WORD_DICT + EXTRA_WORDS + CORE_N3_KANA_VOCAB)
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
    import edge_tts
except Exception:
    edge_tts = None

from adaptive_bank import CORE_N3_KANA_VOCAB, EXTRA_PRIMARY_CARDS, EXTRA_WORDS, VARIANT_CARDS
from tutor_data import KANA_ADVERBS_36, TUTOR_ITEMS, WORD_DICT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
WORDS_AUDIO_DIR = os.path.join(AUDIO_DIR, "words")
MANIFEST_PATH = os.path.join(AUDIO_DIR, "audio_manifest.json")
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 3 if os.environ.get("GITHUB_ACTIONS") == "true" else 1

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
    "Q-20261114-005": [
        ("ja-JP-KeitaNeural", "-4%", "部長、実は来週の金曜日、私用で会社を休ませていただけないでしょうか。"),
        ("ja-JP-NanamiNeural", "-5%", "1番。うん、引き継ぎをしておけば大丈夫だよ。"),
        ("ja-JP-NanamiNeural", "-5%", "2番。えっ、私に来週休んでほしいの？"),
        ("ja-JP-NanamiNeural", "-5%", "3番。金曜日ならもう休みましたよ。"),
    ],
}

KANJI_FORCE_KANA = {"半年", "内緒", "貯める", "貯金", "出張", "主張", "書類", "万年筆", "封筒", "終電", "寮"}


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
            if re.search(r"[\u3040-\u30ffー]", inner) or inner in KANJI_FORCE_KANA:
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


async def synth_ja(text: str, out_path: str, rate: str = "-4%") -> bool:
    if edge_tts is None:
        return False
    for attempt in range(MAX_TRIES):
        try:
            buf = bytearray()
            comm = edge_tts.Communicate(text, "ja-JP-NanamiNeural", rate=rate, **COMM_KWARGS)
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
                print(f"[warn] synth_ja failed for {out_path}: {e}")
    return False


async def synth_dialogue(turns, out_path: str) -> bool:
    if edge_tts is None:
        return False
    for attempt in range(MAX_TRIES):
        try:
            buf = bytearray()
            for voice, rate, line in turns:
                comm = edge_tts.Communicate(line, voice, rate=rate, **COMM_KWARGS)
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
                print(f"[warn] synth_dialogue failed for {out_path}: {e}")
    return False


async def synth_bilingual(text: str, out_path: str) -> bool:
    if edge_tts is None:
        return False
    for attempt in range(MAX_TRIES):
        try:
            segs = split_zh_ja_segments(text)
            buf = bytearray()
            for lang, seg in segs:
                voice = "ja-JP-NanamiNeural" if lang == "ja" else "zh-CN-XiaoxiaoNeural"
                rate = "-2%" if lang == "ja" else "+5%"
                comm = edge_tts.Communicate(seg, voice, rate=rate, **COMM_KWARGS)
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
                print(f"[warn] synth_bilingual failed for {out_path}: {e}")
    return False


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
    plans = sorted(glob.glob(os.path.join(BASE_DIR, "brain_plan_*.json")))
    with open(plans[-1], encoding="utf-8") as f:
        plan = json.load(f)

    all_items = []
    for sec in ("grammar", "henkei", "vocab", "listening"):
        for kind in ("formal", "quick"):
            for q in plan.get(sec, {}).get(kind, []):
                qid = q["id"]
                t_item = TUTOR_ITEMS.get(qid, {})
                all_items.append({
                    "id": qid,
                    "voice_q": t_item.get("voice_q") or q.get("stem", ""),
                    "voice_exp": t_item.get("voice_exp") or q.get("hook_zh") or "",
                    "dialogue": LISTENING_DIALOGUES.get(qid),
                })

    for ext in EXTRA_PRIMARY_CARDS + VARIANT_CARDS:
        all_items.append({
            "id": ext["id"],
            "voice_q": ext.get("voice_q", ""),
            "voice_exp": ext.get("voice_exp", ""),
            "dialogue": ext.get("dialogue"),
        })

    sem = asyncio.Semaphore(5)
    new_manifest = {"words": dict(old_words)}

    async def process_item(item):
        qid = item["id"]
        turns = item.get("dialogue")

        q_file = f"{qid}_q.mp3"
        q_abs = os.path.join(AUDIO_DIR, q_file)
        if turns:
            q_sig = "dlg:" + json.dumps(turns, ensure_ascii=False)
            q_hash = hashlib.sha256(q_sig.encode("utf-8")).hexdigest()[:12]
            if (old_manifest.get(q_file) != q_hash or not os.path.exists(q_abs)) and edge_tts is not None:
                async with sem:
                    await synth_dialogue(turns, q_abs)
            new_manifest[q_file] = q_hash if os.path.exists(q_abs) else old_manifest.get(q_file, "")
            q_rel = f"./audio/{q_file}" if os.path.exists(q_abs) else ""
        else:
            vq = item.get("voice_q", "")
            q_hash = hashlib.sha256(vq.encode("utf-8")).hexdigest()[:12]
            if (old_manifest.get(q_file) != q_hash or not os.path.exists(q_abs)) and edge_tts is not None:
                async with sem:
                    await synth_bilingual(vq, q_abs)
            new_manifest[q_file] = q_hash if os.path.exists(q_abs) else old_manifest.get(q_file, "")
            q_rel = f"./audio/{q_file}" if os.path.exists(q_abs) else ""

        exp_txt = item.get("voice_exp", "")
        exp_hash = hashlib.sha256(exp_txt.encode("utf-8")).hexdigest()[:12]
        exp_file = f"{qid}_exp.mp3"
        exp_abs = os.path.join(AUDIO_DIR, exp_file)
        if (old_manifest.get(exp_file) != exp_hash or not os.path.exists(exp_abs)) and edge_tts is not None:
            async with sem:
                await synth_bilingual(exp_txt, exp_abs)
        new_manifest[exp_file] = exp_hash if os.path.exists(exp_abs) else old_manifest.get(exp_file, "")
        exp_rel = f"./audio/{exp_file}" if os.path.exists(exp_abs) else ""

        new_manifest[f"meta:{qid}"] = {
            "q_audio": q_rel,
            "exp_audio": exp_rel,
            "spoken_text": exp_txt,
        }

    merged_words = dict(WORD_DICT)
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

    async def process_word(surface, info):
        alias = info.get("audio_alias")
        if alias and alias in old_words:
            alias_abs = os.path.join(BASE_DIR, old_words[alias].lstrip("./"))
            if os.path.exists(alias_abs):
                new_manifest["words"][surface] = old_words[alias]
                return

        speak_str = surface.replace("〜", "")
        if surface in KANJI_FORCE_KANA and info.get("kana"):
            speak_str = info["kana"]
        w_hash = hashlib.sha256(speak_str.encode("utf-8")).hexdigest()[:10]
        w_file = f"w_{w_hash}.mp3"
        w_abs = os.path.join(WORDS_AUDIO_DIR, w_file)
        if not os.path.exists(w_abs) and edge_tts is not None:
            async with sem:
                await synth_ja(speak_str, w_abs, rate="-4%")
        if os.path.exists(w_abs):
            new_manifest["words"][surface] = f"./audio/words/{w_file}"

    await asyncio.gather(
        *(process_item(it) for it in all_items),
        *(process_word(surf, info) for surf, info in merged_words.items()),
    )

    done_txt = "今天的五十个重点考点全部变绿过关了！干得漂亮，安心去休息吧。"
    done_hash = hashlib.sha256(done_txt.encode("utf-8")).hexdigest()[:12]
    done_abs = os.path.join(AUDIO_DIR, "done.mp3")
    if (old_manifest.get("done.mp3") != done_hash or not os.path.exists(done_abs)) and edge_tts is not None:
        await synth_bilingual(done_txt, done_abs)
    if os.path.exists(done_abs):
        new_manifest["done.mp3"] = done_hash

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Verified {len(all_items)} studio Q/Exp pairs + {len(new_manifest['words'])} word pronunciations.")


if __name__ == "__main__":
    asyncio.run(main())
