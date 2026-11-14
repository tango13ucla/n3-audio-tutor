#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily 35–40 Minute Two-Host Conversational N3 Radio Show (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json).

Driven by the Master Algorithm:
1) Reads n3_live_state.json + practice_log.jsonl summary (yesterday's mistakes & current mastery).
2) Prioritizes weak/unmastered & ear-suited points (modality="listen" / "both"), rotating daily by PT date.
3) Synthesizes natural two-person Chinese banter (阿哲 YunxiNeural + 小夏 XiaoxiaoNeural) interleaved with
   authentic Japanese scene examples (NanamiNeural + KeitaNeural) and active-recall pauses.
4) Stitches a single continuous lock-screen-proof 48kbps CBR MP3 for 30-40 min walking/biking/commuting.
"""
import asyncio
import datetime
import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo

try:
    import certifi
    if os.environ.get("SSL_CERT_FILE") and os.path.exists(os.environ["SSL_CERT_FILE"]):
        certifi.where = lambda: os.environ["SSL_CERT_FILE"]
    import edge_tts
except Exception:
    edge_tts = None

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

VOICE_MAP = {
    "M": ("zh-CN-YunxiNeural", "+4%"),
    "F": ("zh-CN-XiaoxiaoNeural", "+5%"),
    "JF": ("ja-JP-NanamiNeural", "-2%"),
    "JM": ("ja-JP-KeitaNeural", "-2%"),
    "JFS": ("ja-JP-NanamiNeural", "-12%"),
}


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
            mult += 0.45  # Yesterday's / recent mistakes jump to top of today's radio show!
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


async def synth_turn(speaker: str, text: str, out_path: str, sem: asyncio.Semaphore) -> bool:
    if edge_tts is None:
        return False
    voice, rate = VOICE_MAP[speaker]
    async with sem:
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
                    print(f"[warn] radio turn synth failed ({speaker}): {e}")
    return False


def make_silence_mp3(sec: float, out_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", f"{sec:.2f}",
            "-c:a", "libmp3lame", "-b:a", "48k",
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

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    today_str = now_pt.strftime("%Y-%m-%d")
    month_num = now_pt.month
    day_num = now_pt.day
    days_left = max(0, (EXAM_DATE - now_pt.date()).days)

    recent_wrong = load_recent_mistakes()
    scores = load_mastery_priority(state, recent_wrong)

    # Deterministic daily rotation + priority weighting so every day's episode is fresh & tailored!
    rng = random.Random(today_str)

    def daily_rank(item):
        pid = item["point_id"]
        jitter = rng.uniform(-0.18, 0.18)
        return -(scores.get(pid, 2.0) + jitter)

    ch1_topics = sorted(DEEP_BANTER_TOPICS, key=daily_rank)[:15]
    ch2_scenes = sorted(LISTENING_THEATRE, key=daily_rank)[:6]
    ch3_vocabs = sorted(VOCAB_RECALL_ITEMS, key=daily_rank)[:14]

    done_g = state.get("summary", {}).get("grammar", {}).get("green", 27)
    red_g = state.get("summary", {}).get("grammar", {}).get("red", 15)

    # Build Master Timeline Script: list of timeline blocks
    # Each block: {"chapter": int, "point_id": str|None, "title": str, "ja_focus": str, "events": [(kind, val), ...]}
    blocks = []

    blocks.append({
        "chapter": 0,
        "point_id": None,
        "title": f"{month_num}月{day_num}日 · 双人随身电台",
        "ja_focus": "今日も一緒に頑張りましょう！",
        "events": [
            ("M", f"哈喽，欢迎打开今天专属的日语随身电台！我是阿哲。今天是{month_num}月{day_num}号，距离十二月六号的考试还有{days_left}天。"),
            ("PAUSE", 0.32),
            ("F", f"嗨，我是小夏！不管你现在是在走路、骑单车、坐公交还是在开车，接下来这三十多分钟都完全不用看屏幕，眼睛放心看路，交给耳朵就行。"),
            ("PAUSE", 0.35),
            ("M", f"小夏，我看了一眼咱们最新的掌握度总账，目前语法已经有{done_g}个点稳稳变绿了，阅读更是你的强项，咱们完全不用在已经会的地方浪费时间。"),
            ("PAUSE", 0.32),
            ("F", f"没错！今天这期节目，我们专门挑出了目前最能帮你往一百二十分以上冲刺的薄弱双胞胎语法、占六十分大头的口语听力陷阱，还有中国人最容易按汉字瞎猜的词汇，咱们用大白话一个一个聊透！先进入第一部分：易混语法与敬语深聊。"),
            ("PAUSE", 1.0),
        ],
    })

    # Chapter 1: 15 Deep Two-Host Banter Topics
    for idx, tp in enumerate(ch1_topics):
        evs = []
        for spk, val in tp["turns"]:
            if spk == "PAUSE":
                evs.append(("PAUSE", float(val)))
            else:
                evs.append((spk, str(val)))
                evs.append(("PAUSE", 0.34))
        evs.append(("PAUSE", 0.9))
        blocks.append({
            "chapter": 0,
            "point_id": tp["point_id"],
            "title": tp["title"],
            "ja_focus": tp["ja_main"],
            "events": evs,
        })

    # Chapter 2 Intro + 6 Listening Theatre Scenes
    blocks.append({
        "chapter": 1,
        "point_id": None,
        "title": "听力真题剧场",
        "ja_focus": "耳をすまして聞いてみよう",
        "events": [
            ("M", "聊完了最容易混的语法和敬语，接下来咱们进入第二部分：占卷面整整六十分的听力实战剧场！"),
            ("PAUSE", 0.32),
            ("F", "这一部分最适合走路骑车练耳朵了！每一段我们先不给提示，直接放男女双人原速日语对话，听完给你留两秒钟在脑子里反应，然后我们拆开里面的口语缩音和潜台词，再带你复听一遍！"),
            ("PAUSE", 0.9),
        ],
    })

    for sc in ch2_scenes:
        evs = [
            ("M", sc["intro_m"]),
            ("PAUSE", 0.5),
        ]
        for d_spk, d_line in sc["dialogue"]:
            evs.append((d_spk, d_line))
            evs.append(("PAUSE", 0.38))
        evs.extend([
            ("PAUSE", 2.2),
            ("M", sc["unpack_m"]),
            ("PAUSE", 0.32),
            ("F", sc["unpack_f"]),
            ("PAUSE", 0.5),
        ])
        for d_spk, d_line in sc["dialogue"]:
            evs.append((d_spk, d_line))
            evs.append(("PAUSE", 0.36))
        evs.append(("PAUSE", 1.0))
        blocks.append({
            "chapter": 1,
            "point_id": sc["point_id"],
            "title": sc["title"],
            "ja_focus": sc["dialogue"][0][1],
            "events": evs,
        })

    # Chapter 3 Intro + 14 Eyes-Free Active Recall Vocab & Kana Adverbs
    blocks.append({
        "chapter": 2,
        "point_id": None,
        "title": "词汇与假名副词",
        "ja_focus": "リズムで覚える重要語彙",
        "events": [
            ("F", "耳朵热身得差不多啦！第三部分咱们来玩一个路上最提神的快问快答：专治没有汉字的假名副词和咱们中国人最容易念错长短音的词。"),
            ("PAUSE", 0.32),
            ("M", "规则超简单：先听日文原声念词和短句，停顿两秒钟你在脑子里抢答意思，紧接着我们揭晓画面口诀！"),
            ("PAUSE", 0.9),
        ],
    })

    for vc in ch3_vocabs:
        evs = [
            ("JF", vc["word_ja"]),
            ("PAUSE", 2.2),
            ("M", vc["hook_m"]),
            ("PAUSE", 0.30),
            ("F", vc["hook_f"]),
            ("PAUSE", 0.35),
            ("JM", vc["sent_ja"]),
            ("PAUSE", 1.0),
        ]
        blocks.append({
            "chapter": 2,
            "point_id": vc["point_id"],
            "title": vc["title"],
            "ja_focus": vc["sent_ja"],
            "events": evs,
        })

    # Chapter 4: Pure Native Japanese Wash-Ear Cooldown
    cooldown_sentences = []
    for tp in ch1_topics[:12]:
        cooldown_sentences.append((tp["point_id"], tp["title"], tp["ja_main"]))
        if len(cooldown_sentences) < 20 and tp.get("ja_alt"):
            cooldown_sentences.append((tp["point_id"], tp["title"], tp["ja_alt"]))
    cooldown_sentences = cooldown_sentences[:18]

    ch4_evs = [
        ("M", "不知不觉已经走到最后一部分啦！最后这几分钟，我们把今天聊过的全部地道日文原句，彻底撤掉中文拐杖，纯日语原速连播一遍！"),
        ("PAUSE", 0.32),
        ("F", "你就放松肩膀，像听日剧台词一样顺着听，感受一下刚才聊透的画面是不是已经在耳朵里自动浮现出来了。开始喽！"),
        ("PAUSE", 0.9),
    ]
    for i, (_, _, ja_s) in enumerate(cooldown_sentences):
        spk = "JF" if i % 2 == 0 else "JM"
        ch4_evs.append((spk, ja_s))
        ch4_evs.append(("PAUSE", 1.8))

    ch4_evs.extend([
        ("F", "太棒了！今天这一整期三十多分钟的随身节目到这里就全部听完啦！今天耳熟的这些考点，已经自动帮你记进学习记录里了。"),
        ("PAUSE", 0.32),
        ("M", "等你一会儿有两三分钟空隙掏出手机做题的时候，今天听过的点会直接出题考你，答对就能秒变绿格！路上注意安全，咱们明天见！"),
        ("PAUSE", 0.6),
    ])

    blocks.append({
        "chapter": 3,
        "point_id": None,
        "title": "纯日语原速复听",
        "ja_focus": "日本語だけで総復習",
        "events": ch4_evs,
    })

    script_sig = hashlib.sha256(json.dumps(blocks, ensure_ascii=False).encode("utf-8")).hexdigest()[:14]
    if os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                print(f"Daily two-host radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_")
    try:
        # Pre-build silence clips
        pause_durations = sorted({round(float(val), 2) for b in blocks for k, val in b["events"] if k == "PAUSE"})
        silence_files = {}
        for sec in pause_durations:
            sf = os.path.join(tmpdir, f"sil_{int(round(sec * 100)):04d}.mp3")
            make_silence_mp3(sec, sf)
            silence_files[sec] = (sf, probe_duration(sf))

        # Deduplicate & synthesize all spoken turns concurrently
        unique_turns = {}
        for b in blocks:
            for k, val in b["events"]:
                if k != "PAUSE":
                    key = (k, val)
                    if key not in unique_turns:
                        thash = hashlib.sha256(f"{k}:{val}".encode("utf-8")).hexdigest()[:12]
                        unique_turns[key] = os.path.join(tmpdir, f"t_{thash}.mp3")

        sem = asyncio.Semaphore(5)
        ok_results = await asyncio.gather(
            *(synth_turn(k, txt, path, sem) for (k, txt), path in unique_turns.items())
        )
        print(f"Synthesized {sum(1 for x in ok_results if x)} / {len(unique_turns)} unique two-host dialogue turns.")

        turn_durs = {}
        for key, path in unique_turns.items():
            if os.path.exists(path) and os.path.getsize(path) > 0:
                turn_durs[key] = probe_duration(path)

        # Build concat list & exact chapter/segment timestamps
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
                    path = unique_turns[key]
                    if key in turn_durs:
                        concat_lines.append(f"file '{path}'")
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
            {"idx": 0, "title": "深聊", "start": chapter_starts.get(0, 0.0)},
            {"idx": 1, "title": "听力", "start": chapter_starts.get(1, 0.0)},
            {"idx": 2, "title": "词汇", "start": chapter_starts.get(2, 0.0)},
            {"idx": 3, "title": "纯日", "start": chapter_starts.get(3, 0.0)},
        ]
        meta_obj = {
            "date": today_str,
            "display_date": f"{month_num}月{day_num}日",
            "days_left": days_left,
            "script_sig": script_sig,
            "audio_url": f"./audio/daily_radio.mp3?v={today_str}_{script_sig[:6]}",
            "duration_sec": final_dur,
            "duration_label": f"{mins} 分钟",
            "hosts": "阿哲 · 小夏",
            "chapters": chapters_meta,
            "segments": segments_meta,
        }
        with open(RADIO_META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta_obj, f, ensure_ascii=False, indent=2)
        print(f"Built daily two-host radio episode: {final_dur:.1f}s ({mins} mins), size={os.path.getsize(RADIO_MP3_PATH)} bytes.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
