#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generates the Daily ~40 Minute "Qiang Qiang Three" Intellectual & Uchi Salon Podcast (audio/daily_radio.mp3)
+ Exact Segment & Chapter Timestamp Map (audio/daily_radio_meta.json) — Zen v29 Uchi & 365-Day Edition.

Hosts: 文涛 (W) · 文道 (D) · 子东 (X)
Key Broadcast Architecture (v29):
1) Authentic 《锵锵三人行》 Show Structure & Music Suite (`compose_qq_music.py`):
   - Classic upbeat Jazz-Mambo + "锵！锵！" (`京小锣`) Opening Theme (`qq_intro.mp3`) with real TV ducked voice entry.
   - Authentic trio greeting (`文涛 · 文道 · 子东` greeting each other & listeners, zero date/exam countdown!).
   - 3-Act Phoenix TV structure with 2 classic mid-episode ad breaks ("去一下广告，《锵锵三人行》，广告之后见！" + `qq_bumper.mp3`),
     plus subtle salon page-turn stings (`qq_sting.mp3`) on non-ad transitions.
   - Warm late-night Closing Theme (`qq_outro.mp3`) sneaking in underneath Wen Tao's final farewell and swelling out cleanly.
2) Deep Intellectual & True Japanese "Uchi (内)" Content + 700-Day (`1/700`) Progressive Immersion:
   - Moves beyond tourist "Soto (外)" clichés into live Japanese/world current affairs, intellectual history (e.g. 1968 Todai Zenkyoto),
     literary masters (Mishima, Tanizaki, Dazai, Soseki), science institutions (Kyodai Nobel vs Kozasei), and closed-door Japanese family/work life,
     with cross-chapter callbacks ("前后照应") across a ~40-minute episode.
   - Tracks `tutor_prefs.immersion_profile(day)`: ~10% Japanese up through 2026-12-06 N3 exam, then gently increases by `1/700` per day
     (10% -> ~35% at N2 -> ~53% at N1 -> 92% at Post-N3 Day 700) with the exact same three hosts into a near-pure Japanese intellectual podcast.
3) Zero-Chop Natural Breath Prosody + Lossless 24kHz PCM Studio Mixing:
   - Full Mandarin sentences stay 100% intact in one continuous neural breath (never chopped on commas `,`, never jumping pitch/rate mid-sentence).
   - Inline Japanese words sit smoothly inside the host's conversational flow with zero forced periods (`。`) and sample-accurate 20ms PCM joins.
"""
from __future__ import annotations
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
import sys
import tempfile
import wave
from zoneinfo import ZoneInfo
try:
    import numpy as np
except Exception:
    np = None

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
from compose_qq_music import ensure_qq_music_assets
from daily_news_salon_gen import maybe_generate_live_news_story, maybe_generate_live_world_finale_story
from radio_dialogue_bank import MODALITY_MAP, SALON_STORIES
import tutor_prefs
from tutor_data import TUTOR_ITEMS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
NIGHT_SUMMARY_PATH = os.path.join(BASE_DIR, "night_summary.json")
CORPUS_KB_PATH = os.path.join(BASE_DIR, "qq_corpus_knowledge.json")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
RADIO_MP3_PATH = os.path.join(AUDIO_DIR, "daily_radio.mp3")
RADIO_META_PATH = os.path.join(AUDIO_DIR, "daily_radio_meta.json")
RADIO_HISTORY_PATH = os.path.join(AUDIO_DIR, "radio_history.json")

SR = 24000
PT_TZ = ZoneInfo("America/Los_Angeles")
EXAM_DATE = datetime.date(2026, 12, 6)
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 6 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Matches Japanese spans (inline words spoken smoothly in-flow; full sentences spoken clearly at -12%/-13%)
JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー・]+(?:[、。！？\s]+[\u3040-\u30ffー・]+)*[。！？]?)")

# Split Mandarin ONLY at complete sentence endings (NEVER on commas `，` or `、`) or genuine comic self-corrections
SENTENCE_CHUNK_RE = re.compile(r"[^。！？]+[。！？]+[”』」）]*|[^。！？]+$")
SLIP_SPLIT_RE = re.compile(
    r"…+(?=(?:呸|不对|哦不对|哎不对|害，哪有|哦日本哪儿|哦不用两大碗|哦三分钟|哦四回|哦一千|少说了俩零|哪有扫码枪))"
)

EXCITED_TURN_RE = re.compile(
    r"^(?:《锵锵三人行》|欢迎继续|欢迎回到|好家伙|神了|哎哟|等会儿|学会了|妙啊|太有画面|真是服了|这下记得|"
    r"不不不|岂止是|那当然|对极了|我跟你说|我的问题是|你的意思是|哪儿止|得了吧)"
)
SLOW_PIVOT_RE = re.compile(
    r"^(?:其实|你想想看|换句话说|说白了|某种程度上|话说回来|所以你想|而且讲句老实话|讲句老实话|"
    r"最绝的是|最要命的是|最诛心的是|最吊诡的是|真正可怕的是|真正残酷的是|偏偏|可是你想|但问题是|归根结底|"
    r"正因为|说到底|不知不觉|往深里想|仔细一想|这才是最)"
)
JAB_SENT_RE = re.compile(
    r"^(?:不不不|对极了|对啊|没错|神了|等会儿|岂止是|那当然|一点儿没错|一点儿不差|完全正确|太准了|"
    r"问到点子上了|哎哟|妙啊|我跟你说|我的问题是|你的意思是|你看啊|结果呢|那可不嘛|哪儿啊|哪儿止|未必|恰恰相反)"
)
LAND_END_RE = re.compile(r"(?:[？！][”』」）]*$|(?:对不对|是不是|你说是不是|这才叫绝|一模一样|全在里头了)[。！？][”』」）]*$)")
REFLECT_TURN_RE = SLOW_PIVOT_RE
LATCH_START_RE = re.compile(
    r"^(?:神了|等会儿|等等|那我肯定|对极了|对啊|对，|对。|对！|没错|不是|不不|不，|可不嘛|可不是嘛|一点儿没错|一点儿不差|"
    r"完全正确|太准了|问到点子上了|哎哟|哎，|害，|哦！|妙啊|我知道|我就干过|你看|我跟你说|连个人|结果才|"
    r"岂止是|那当然|我的问题是|你的意思是|这就是|得了吧|拉倒吧|你说得对|你别说|问题就在这儿|哪儿啊|哪儿止|未必|恰恰相反|那可不)"
)

GENERIC_POINT_LABELS = {"口语听辨", "高频假名副词", "核心词汇", "语法", "活用"}

# Dynamic 轻重 (loudness contour in dB) per prosody gear across 起·承·转·合
GEAR_GAIN_DB = {
    "JAB": 0.85,
    "FAST": 0.85,
    "MID": 0.0,
    "SLOW": -0.65,
    "LOW": -0.65,
    "LAND": 0.75,
    "JA_INLINE": 0.35,
    "JA": 0.45,
}


# ==============================================================================
# Authentic 《锵锵三人行》 Non-Templated Cold-Open, Crisp Ad Breaks & Closings
# Distilled from 3,124 Full Episodes + 1,319 Official Speaker Transcripts (98.3% Direct Topic Cold-Open!)
# ==============================================================================
AD_BREAK_1_POOL = [
    (
        [("W", "咱们先去一下广告，《锵锵三人行》，广告之后见。")],
        [("W", "《锵锵三人行》，咱们接着刚才的话茬儿往下说。")],
    ),
    (
        [("W", "得，咱们先去下广告，《锵锵三人行》，广告之后见。")],
        [("W", "接着刚才那笔账往下算啊。")],
    ),
    (
        [("W", "《锵锵三人行》，广告之后见。")],
        [("W", "所以你看文道，顺着刚才这个往下看啊。")],
    ),
]

AD_BREAK_2_POOL = [
    (
        [("W", "咱们再去一下广告，《锵锵三人行》，广告之后见。")],
        [("W", "《锵锵三人行》，咱们接着往下聊。")],
    ),
    (
        [("W", "先去一下广告，《锵锵三人行》，广告之后见。")],
        [("W", "刚才聊了外头的制度，咱们再推门看看普通人家里头。")],
    ),
    (
        [("W", "《锵锵三人行》，广告之后见。")],
        [("W", "接着刚才说的往下走啊。")],
    ),
]

CLOSING_POOL = [
    [
        ("W", "得嘞，不知不觉又聊到这钟点了，《锵锵三人行》，咱们下回接着聊！"),
    ],
    [
        ("W", "行，今儿这桩事儿先聊到这儿，《锵锵三人行》，咱们明天见！"),
    ],
]

# Post-N3 (2026-12-07 -> Day 365) Progressive Japanese Salon Framing Pools
POST_N3_BILINGUAL_OPENING = [
    ("W", "《锵锵三人行》！みなさん、こんばんは！文道好，子东好，各位好！"),
    ("D", "こんばんは。文涛好，大家好。"),
    ("X", "こんばんは。きょうもよろしくおねがいします。"),
    ("W", "咱们老哥仨每天一壶热茶接着聊啊，日文每天多说一点点，今天接着往日本社会真正的 うち 深水区里头走：さっそく、きょうのさいしょのわだいからいきましょう！"),
]

POST_N3_NATIVE_OPENING = [
    ("W", "みなさん、こんばんは。きょうもさんにんで、おちゃをのみながら、にほんのせいじやぶんがく、そしてほんねのしゃかいをじっくりかたっていきましょう。おふたりとも、よろしくおねがいします！"),
    ("D", "こんばんは。きょうもたいへんおもしろいテーマがそろっていますね。よろしくおねがいします。"),
    ("X", "こんばんは。おもてむきのきれいごとではなく、にほんのほんとうのすがたをさぐっていきましょう。"),
]

POST_N3_NATIVE_AD1 = (
    [("W", "はなしがもりあがってきたところですが、ここでいったんコマーシャルです。コマーシャルのあとで、またすぐにおあいしましょう！")],
    [("W", "さあ、ばんぐみにまいりましょう。さきほどのつづきから、さらにふかくほりさげていきますよ！")],
)

POST_N3_NATIVE_AD2 = (
    [("W", "なるほど、すべてがつながってきましたね。ここでふたたびコマーシャルです。さいごのパートもどうぞおたのしみに！")],
    [("W", "おまちどおさまでした。それではきょうのさいごのパートにはいっていきましょう！")],
)

POST_N3_NATIVE_CLOSING = [
    ("D", "きょうもあっというまにおちゃがなくなってしまいましたね。れきしやぶんがくから、げんだいのかぞくのもんだいまで、すべてがひとつにつながっていることがよくわかります。"),
    ("X", "そうですね。まいにちすこしずつ、こうしてにほんのほんねにふれていくことが、いちばんのちかみちだとおもいます。"),
    ("W", "おふたりとも、きょうもありがとうございました。きいてくださったみなさんも、ありがとうございます。それでは、またあしたおあいしましょう！"),
]


def resolve_point_key(point_id: str) -> str:
    if point_id in TUTOR_ITEMS:
        return TUTOR_ITEMS[point_id].get("point_key", point_id)
    for ext in EXTRA_PRIMARY_CARDS:
        if ext["id"] == point_id:
            return ext["point_key"]
    return point_id


def load_recent_mistakes() -> tuple[set, set]:
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


def load_recent_story_ages(today_str: str, max_days: int = 21) -> dict[str, int]:
    """Returns {story_id: days_ago (1 = most recent prior broadcast day)} across up to `max_days`."""
    if not os.path.exists(RADIO_HISTORY_PATH):
        return {}
    try:
        with open(RADIO_HISTORY_PATH, encoding="utf-8") as f:
            hist = json.load(f)
        by_date = hist.get("recent_days") or {}
        prior_dates = sorted(d for d in by_date.keys() if d < today_str)[-max_days:]
        ages: dict[str, int] = {}
        # Iterate oldest -> newest so most recent play overwrites with smallest `days_ago`
        total_prior = len(prior_dates)
        for idx, d_str in enumerate(prior_dates):
            days_ago = total_prior - idx
            for sid in (by_date.get(d_str) or []):
                ages[str(sid)] = days_ago
        return ages
    except Exception:
        return {}


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
    keep_dates = sorted(hist["recent_days"].keys())[-21:]
    hist["recent_days"] = {k: hist["recent_days"][k] for k in keep_dates}
    with open(RADIO_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def estimate_story_seconds(st: dict) -> float:
    """Empirical v36-v38 studio timing: ~0.209s per spoken char + 2.5s transition."""
    chars = sum(len(str(t)) for _, t in (st.get("turns") or []))
    return chars * 0.209 + 2.5


def load_corpus_kb() -> dict:
    if not os.path.exists(CORPUS_KB_PATH):
        return {}
    try:
        with open(CORPUS_KB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_night_summary_signals() -> dict:
    if not os.path.exists(NIGHT_SUMMARY_PATH):
        return {}
    try:
        with open(NIGHT_SUMMARY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def gear_gain_linear(spk_key: str) -> float:
    parts = spk_key.split("_", 1)
    gear = parts[1] if len(parts) > 1 else "MID"
    db = GEAR_GAIN_DB.get(gear, 0.0)
    return float(10.0 ** (db / 20.0))


async def detect_voice_map(ja_sentence_rate: str = "-12%") -> dict:
    """
    Coherent 3-host voices with full 4-stage 起·承·转·合 intra-turn cadence gears
    (ZERO mid-sentence pitch/rate jumping — each complete sentence breathes as one unit):
    - W (文涛): en-US-BrianMultilingualNeural (bright, nimble northern host cadence)
    - D (文道): ko-KR-HyunsuMultilingualNeural (warm, unhurried East Asian scholar baritone)
    - X (子东): fr-FR-RemyMultilingualNeural (crisp, dry literary critic cadence)
    """
    w_voice = "en-US-BrianMultilingualNeural"
    d_voice = "ko-KR-HyunsuMultilingualNeural"
    x_voice = "fr-FR-RemyMultilingualNeural"

    try:
        base_ja_pct = int(ja_sentence_rate.replace("%", "").strip())
    except Exception:
        base_ja_pct = -12
    w_ja_rate = f"{base_ja_pct:+d}%"
    d_ja_rate = f"{max(-15, base_ja_pct - 1):+d}%"
    x_ja_rate = f"{base_ja_pct:+d}%"

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
            print(f"Qiang-Qiang trio voices: W(文涛)={w_voice}, D(文道)={d_voice}, X(子东)={x_voice}, ja_rate={w_ja_rate}")
        except Exception as e:
            print(f"[info] list_voices fallback to default trio voices: {e}")

    vmap = {
        # W (文涛): 清亮活泛 — 急切抢白(+15%) / 自然铺陈(+10%) / 沉吟蓄力(+3%) / 落锤点睛(+6%)
        "W":             (w_voice, "+10%", "+2Hz"),
        "W_MID":         (w_voice, "+10%", "+2Hz"),
        "W_JAB":         (w_voice, "+15%", "+3Hz"),
        "W_FAST":        (w_voice, "+15%", "+3Hz"),
        "W_SLOW":        (w_voice, "+3%", "+1Hz"),
        "W_LOW":         (w_voice, "+3%", "+1Hz"),
        "W_LAND":        (w_voice, "+6%", "+2Hz"),
        "W_JA_INLINE":   (w_voice, "+7%", "+2Hz"),
        "W_JA":          (w_voice, w_ja_rate, "+2Hz"),
        # D (文道): 温厚胸腔男中音 — 短促应答(+9%) / 从容铺陈(+4%) / 思想转折(-2%) / 收束落定(+1%)
        "D":             (d_voice, "+4%", "-4Hz"),
        "D_MID":         (d_voice, "+4%", "-4Hz"),
        "D_JAB":         (d_voice, "+9%", "-3Hz"),
        "D_FAST":        (d_voice, "+9%", "-3Hz"),
        "D_SLOW":        (d_voice, "-2%", "-5Hz"),
        "D_LOW":         (d_voice, "-2%", "-5Hz"),
        "D_LAND":        (d_voice, "+1%", "-4Hz"),
        "D_JA_INLINE":   (d_voice, "+3%", "-4Hz"),
        "D_JA":          (d_voice, d_ja_rate, "-4Hz"),
        # X (子东): 清瘦干练冷幽默 — 短刀拆台(+13%) / 文本细读(+8%) / 反讽沉吟(+1%) / 一针见血(+4%)
        "X":             (x_voice, "+8%", "-1Hz"),
        "X_MID":         (x_voice, "+8%", "-1Hz"),
        "X_JAB":         (x_voice, "+13%", "+0Hz"),
        "X_FAST":        (x_voice, "+13%", "+0Hz"),
        "X_SLOW":        (x_voice, "+1%", "-2Hz"),
        "X_LOW":         (x_voice, "+1%", "-2Hz"),
        "X_LAND":        (x_voice, "+4%", "-1Hz"),
        "X_JA_INLINE":   (x_voice, "+6%", "-1Hz"),
        "X_JA":          (x_voice, x_ja_rate, "-1Hz"),
    }
    for g in ("", "_MID", "_JAB", "_FAST", "_SLOW", "_LOW", "_LAND", "_JA_INLINE", "_JA"):
        vmap[f"M{g}"] = vmap[f"W{g}"]
        vmap[f"F{g}"] = vmap[f"X{g}"]
    return vmap


def clean_ja_sentence_commas(ks: str) -> str:
    """
    Removes artificial post-particle commas (`でんしゃが、がらがらだ` -> `でんしゃががらがらだ`)
    that made Japanese sentences sound halting, while preserving genuine clause boundaries
    and deliberate mora-by-mora demonstrations (`は、な、さ、せ、ら、れ、た`).
    """
    if ks.count("、") >= 4 and all(len(p) <= 2 for p in ks.split("、")):
        return ks
    parts = ks.split("、")
    if len(parts) <= 1:
        return ks
    KEEP_ENDINGS = (
        "て", "で", "から", "けど", "けれど", "のに", "たら", "なら", "ば",
        "し", "り", "ながら", "あと", "まえ", "とき", "ため", "ず",
        "ああ", "ねえ", "えっ", "うん", "はい", "いや", "じゃあ", "でも", "ほら",
    )
    merged = [parts[0]]
    for nxt in parts[1:]:
        prev = merged[-1]
        if prev.endswith(KEEP_ENDINGS) or len(prev) >= 10:
            merged.append(nxt)
        else:
            merged[-1] = prev + nxt
    return "、".join(merged)


def pick_turn_gear(spk: str, full_txt: str) -> str:
    s = full_txt.strip()
    if len(s) <= 16 or EXCITED_TURN_RE.search(s):
        return f"{spk}_JAB"
    if SLOW_PIVOT_RE.search(s):
        return f"{spk}_SLOW"
    return f"{spk}_MID"


def pick_sentence_gear(base_spk: str, sent: str, idx: int, total: int, default_gear: str, is_turn_start: bool, is_turn_end: bool) -> str:
    s = sent.strip().lstrip("“『「（ ")
    if SLOW_PIVOT_RE.search(s):
        return f"{base_spk}_SLOW"
    if JAB_SENT_RE.search(s) or (is_turn_start and idx == 0 and len(s) <= 18):
        return f"{base_spk}_JAB"
    if is_turn_end and idx == total - 1 and (total >= 3 or (total >= 2 and LAND_END_RE.search(s))):
        return f"{base_spk}_LAND"
    if total == 1:
        return default_gear
    return f"{base_spk}_MID"


def split_mandarin_natural(
    base_spk: str,
    pt_s: str,
    default_gear: str,
    is_turn_start: bool = True,
    is_turn_end: bool = True,
) -> list[tuple[str, object]]:
    """
    True 起·承·转·合 sentence-level prosody:
    - Keeps every complete Mandarin sentence (`。！？`) 100% intact in a single breath (NEVER chops on commas `，`).
    - Across multi-sentence turns, varies speed gear (`_JAB` / `_MID` / `_SLOW` / `_LAND`) and inter-sentence breath pauses
      (`0.10s` snappy follow-up vs `0.17s` narrative flow vs `0.30s` contemplative intake before a pivot).
    """
    s = pt_s.strip()
    if not s:
        return []

    raw_sentences = [c.strip() for c in SENTENCE_CHUNK_RE.findall(s) if c and c.strip()]
    if not raw_sentences:
        raw_sentences = [s]

    events: list[tuple[str, object]] = []
    n_sents = len(raw_sentences)

    for s_idx, raw_sent in enumerate(raw_sentences):
        slip_parts = SLIP_SPLIT_RE.split(raw_sent)
        sent_gear = pick_sentence_gear(
            base_spk,
            raw_sent,
            s_idx,
            n_sents,
            default_gear,
            is_turn_start=(is_turn_start and s_idx == 0),
            is_turn_end=(is_turn_end and s_idx == n_sents - 1),
        )
        if events:
            if sent_gear.endswith("_SLOW"):
                events.append(("PAUSE", 0.30))
            elif sent_gear.endswith("_JAB"):
                events.append(("PAUSE", 0.11))
            elif sent_gear.endswith("_LAND"):
                events.append(("PAUSE", 0.23))
            else:
                events.append(("PAUSE", 0.17))

        for sub_idx, sub in enumerate(slip_parts):
            clean = re.sub(r"…+", "，", sub).strip()
            clean = re.sub(r"，([，。！？；：])", r"\1", clean)
            clean = re.sub(r"^[,，、；：]+", "", clean).strip()
            if not clean or not re.search(r"[\w\u3040-\u9fff]", clean):
                continue
            if sub_idx == 0 and len(slip_parts) > 1:
                if clean[-1] not in "。！？，、：":
                    clean = clean + "，"
                events.append((sent_gear, clean))
                events.append(("PAUSE", 0.15))
            elif sub_idx > 0:
                events.append((f"{base_spk}_JAB", clean))
                if sub_idx + 1 < len(slip_parts):
                    events.append(("PAUSE", 0.13))
            else:
                events.append((sent_gear, clean))
    return events


def expand_turn_events(spk: str, val) -> list:
    if spk in ("PAUSE", "LATCH"):
        return [(spk, float(val))]
    txt = str(val).strip()
    if spk not in ("W", "D", "X", "M", "F"):
        return [(spk, txt)]

    turn_gear = pick_turn_gear(spk, txt)
    ja_full_spk = f"{spk}_JA"
    ja_inline_spk = f"{spk}_JA_INLINE"

    if not JA_SPAN_RE.search(txt):
        evs = split_mandarin_natural(spk, txt, turn_gear, is_turn_start=True, is_turn_end=True)
        return evs if evs else [(turn_gear, txt)]

    parts = JA_SPAN_RE.split(txt)
    out: list[tuple[str, object]] = []
    pending_pause = 0.0
    n_parts = len(parts)

    for idx, pt in enumerate(parts):
        if not pt:
            continue
        if idx % 2 == 1:
            ks = re.sub(r"\s+", "", pt.strip())
            if not ks:
                continue
            ended_punct = ks[-1] in "。！？"
            core_ks = ks[:-1] if ended_punct else ks
            prev_zh = parts[idx - 1].rstrip() if idx >= 1 else ""
            after_colon_or_stop = (not prev_zh) or (prev_zh[-1] in "：:。！？")
            is_full_sentence = (
                after_colon_or_stop and len(core_ks) >= 7
            ) or (
                ("、" in core_ks)
                or ("。" in core_ks)
                or ("？" in core_ks)
                or ("！" in core_ks)
                or (ended_punct and len(core_ks) >= 10)
            )
            if is_full_sentence:
                ks_clean = clean_ja_sentence_commas(ks)
                if ks_clean[-1] not in "。！？":
                    ks_clean = ks_clean + "。"
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.20), 3)))
                out.append((ja_full_spk, ks_clean))
                pending_pause = 0.28 if ended_punct else 0.16
            else:
                ks_inline = ks if ended_punct else ks
                if out:
                    out.append(("PAUSE", round(max(pending_pause, 0.02), 3)))
                out.append((ja_inline_spk, ks_inline))
                pending_pause = 0.18 if ended_punct else 0.02
        else:
            lead_m = re.match(r"^[\s』」）“”]*([。！？；，、：…]+)[\s『「（“”]*", pt)
            if lead_m:
                pchars = lead_m.group(1)
                if any(c in pchars for c in "。！？；"):
                    pending_pause = max(pending_pause, 0.22)
                elif "…" in pchars:
                    pending_pause = max(pending_pause, 0.20)
                else:
                    pending_pause = max(pending_pause, 0.08)
                pt = pt[lead_m.end():]
            pt_s = pt.strip()
            if not pt_s or not re.search(r"[\w\u3040-\u9fff]", pt_s):
                continue
            has_later_content = any(bool(p.strip()) for p in parts[idx + 1 : n_parts])
            zh_evs = split_mandarin_natural(
                spk,
                pt_s,
                turn_gear,
                is_turn_start=(not out),
                is_turn_end=(not has_later_content),
            )
            if not zh_evs:
                continue
            if out:
                out.append(("PAUSE", round(max(pending_pause, 0.02), 3)))
            out.extend(zh_evs)
            last_txt = str(zh_evs[-1][1]).rstrip("”』」） ")
            if last_txt and last_txt[-1] in "。！？；":
                pending_pause = 0.22
            elif last_txt and last_txt[-1] in "：:":
                pending_pause = 0.18
            elif last_txt and last_txt[-1] in "，、":
                pending_pause = 0.08
            else:
                pending_pause = 0.02
    return out if out else [(turn_gear, txt)]


def turn_switch_transition(prev_spk: str, prev_txt: str, next_spk: str, next_txt: str) -> tuple[str, float]:
    """
    Calibrated to 421 real 《锵锵三人行》 broadcast episodes (<0.00s median speaker-switch gap):
    - Snappy latches / short interruptions crossfade 58ms-85ms over the ducked tail of the prior speaker.
    - NEVER overlaps if the prior turn ended on Japanese kana or the next turn begins on Japanese kana,
      keeping 100% of Japanese target expressions crystal-clear in the ear.
    """
    p = str(prev_txt).strip()
    s = str(next_txt).strip()
    prev_ends_ja = bool(re.search(r"[\u3040-\u30ffー][。！？、”』」）\s]*$", p))
    next_starts_ja = bool(re.match(r"^[\s“『「（]*[\u3040-\u30ffー]", s))
    if (
        prev_spk != next_spk
        and not prev_ends_ja
        and not next_starts_ja
        and (len(s) <= 14 or LATCH_START_RE.search(s))
    ):
        if p.endswith(("……", "…", "——")):
            return ("LATCH", 0.085)
        return ("LATCH", 0.058)
    if len(s) <= 18 or LATCH_START_RE.search(s):
        return ("PAUSE", 0.038)
    if SLOW_PIVOT_RE.search(s):
        return ("PAUSE", 0.22)
    if next_spk == "W":
        return ("PAUSE", 0.095)
    if next_spk == "D":
        return ("PAUSE", 0.155)
    return ("PAUSE", 0.115)


def synth_gemini_turn_sync(spk: str, text: str, out_mp3: str) -> bool:
    if not (GEMINI_API_KEY and genai is not None and genai_types is not None):
        return False
    base = spk.split("_")[0]
    voice_map_g = {"W": "Puck", "D": "Charon", "X": "Orus"}
    voice_name = voice_map_g.get(base, "Puck")
    if spk.endswith("_JA_INLINE"):
        prompt = f"Speak this Japanese word smoothly at conversational speed in your own voice without dropping pitch at the end: {text}"
    elif spk.endswith("_JA"):
        prompt = f"Speak this Japanese sentence clearly, smoothly, and naturally in your own voice: {text}"
    elif spk.endswith(("_JAB", "_FAST")):
        prompt = f"Speak briskly and snappily like a quick roundtable interjection in Qiang Qiang Three: {text}"
    elif spk.endswith(("_SLOW", "_LOW")):
        prompt = f"Speak unhurriedly and contemplatively with warm intimate weight like a thoughtful turn in Qiang Qiang Three: {text}"
    elif spk.endswith("_LAND"):
        prompt = f"Speak with firm, witty closing emphasis to land the point cleanly: {text}"
    else:
        prompt = f"Speak naturally in one smooth conversational breath like Qiang Qiang Three: {text}"
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
            wf.setframerate(SR)
            wf.writeframes(pcm)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-ar", str(SR), "-ac", "1", "-b:a", "64k", "-c:a", "libmp3lame", out_mp3],
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
        speak_txt = text.rstrip("，、：:； ")
        if not speak_txt:
            speak_txt = text.strip()
        if not spk.endswith("_JA_INLINE") and len(speak_txt) <= 2 and speak_txt and speak_txt[-1] not in "。！？":
            speak_txt = speak_txt + "。"
        punct_stripped = speak_txt.rstrip("，、：:； ")
        with_period = (punct_stripped + "。") if (punct_stripped and punct_stripped[-1] not in "。！？") else speak_txt
        no_quotes = re.sub(r'[“”‘’「」『』"]', "", punct_stripped).strip()
        no_quotes_period = (no_quotes + "。") if (no_quotes and no_quotes[-1] not in "。！？") else with_period
        bare_no_punct = no_quotes.rstrip("。！？、 ") or no_quotes_period
        base_spk = spk.split("_")[0]
        # Never let D (Liang Wendao baritone) fall back to W's en-US-BrianMultilingualNeural!
        alt_voice = (
            "it-IT-GiuseppeMultilingualNeural"
            if base_spk == "D"
            else "en-AU-WilliamMultilingualNeural"
        )
        alt_pitch = "-3Hz" if base_spk == "D" else "+0Hz"
        for attempt in range(MAX_TRIES):
            if attempt == 0:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, pitch, speak_txt
            elif attempt == 1:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, pitch, with_period
            elif attempt == 2:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, "+0Hz", no_quotes_period
            elif attempt == 3:
                use_voice, use_rate, use_pitch, use_txt = voice, "+0%", "+0Hz", no_quotes_period
            elif attempt == 4:
                use_voice, use_rate, use_pitch, use_txt = voice, "+0%", "+0Hz", bare_no_punct
            else:
                use_voice, use_rate, use_pitch, use_txt = alt_voice, rate, alt_pitch, bare_no_punct
            try:
                buf = bytearray()
                try:
                    comm = edge_tts.Communicate(use_txt, use_voice, rate=use_rate, pitch=use_pitch, **COMM_KWARGS)
                except TypeError:
                    comm = edge_tts.Communicate(use_txt, use_voice, rate=use_rate, **COMM_KWARGS)

                async def _pull():
                    async for chunk in comm.stream():
                        if chunk["type"] == "audio":
                            buf.extend(chunk["data"])

                await asyncio.wait_for(_pull(), timeout=55.0)
                if buf:
                    if use_voice != voice:
                        print(f"[fallback-voice] {spk} -> {use_voice} for {speak_txt!r}")
                    with open(out_path, "wb") as f:
                        f.write(buf)
                    return True
            except Exception as e:
                if attempt + 1 < MAX_TRIES:
                    await asyncio.sleep(0.45 * (attempt + 1))
                elif MAX_TRIES > 1:
                    print(f"[warn] radio turn synth failed ({use_voice} | {spk} | {speak_txt!r}): {e!r}")
    return False


def _smooth_band_db(freqs: np.ndarray, f_lo: float, f_hi: float, gain_db: float, width: float = 90.0) -> np.ndarray:
    out = np.zeros_like(freqs, dtype=np.float32)
    if abs(gain_db) < 1e-4:
        return out
    core = (freqs >= f_lo) & (freqs <= f_hi)
    out[core] = gain_db
    w = max(20.0, float(width))
    up = (freqs >= (f_lo - w)) & (freqs < f_lo)
    if np.any(up):
        phase = (freqs[up] - (f_lo - w)) / w
        out[up] = gain_db * (0.5 - 0.5 * np.cos(np.pi * phase))
    dn = (freqs > f_hi) & (freqs <= (f_hi + w))
    if np.any(dn):
        phase = (freqs[dn] - f_hi) / w
        out[dn] = gain_db * (0.5 + 0.5 * np.cos(np.pi * phase))
    return out


def apply_host_vocal_timbre(arr: np.ndarray, spk_key: str) -> np.ndarray:
    """
    Zero-phase spectral vocal timbre sculpting calibrated from 400+ real 《锵锵三人行》 broadcast episodes,
    preserving 100% studio clarity and Japanese phoneme precision while giving W / D / X unmistakable vocal body:
    - W (窦文涛): Bright, forward northern studio presence (+1.65dB @ 1.95-3.65kHz, clean 180Hz trim)
    - D (梁文道): Warm, magnetic chest baritone (+2.15dB @ 105-255Hz, +1.05dB @ 280-680Hz, smooth upper-mids)
    - X (许子东): Lean, incisive scholar diction (-1.35dB low chest, +1.85dB @ 1.15-2.55kHz nasal-mid focus)
    """
    if np is None or len(arr) < 320:
        return arr
    base = spk_key.split("_")[0]
    spec = np.fft.rfft(arr)
    freqs = np.fft.rfftfreq(len(arr), d=1.0 / SR).astype(np.float32)
    hp = np.clip((freqs - 42.0) / 36.0, 0.0, 1.0)
    if base in ("W", "M"):
        eq_db = (
            _smooth_band_db(freqs, 150.0, 250.0, -0.90, 60.0)
            + _smooth_band_db(freqs, 1950.0, 3650.0, 1.65, 340.0)
            + _smooth_band_db(freqs, 4200.0, 6800.0, 0.75, 480.0)
        )
    elif base == "D":
        eq_db = (
            _smooth_band_db(freqs, 105.0, 255.0, 2.15, 50.0)
            + _smooth_band_db(freqs, 280.0, 680.0, 1.05, 120.0)
            + _smooth_band_db(freqs, 2600.0, 4600.0, -1.15, 380.0)
        )
    elif base in ("X", "F"):
        eq_db = (
            _smooth_band_db(freqs, 85.0, 205.0, -1.35, 50.0)
            + _smooth_band_db(freqs, 1150.0, 2550.0, 1.85, 250.0)
            + _smooth_band_db(freqs, 3200.0, 5000.0, 0.45, 380.0)
        )
    else:
        eq_db = np.zeros_like(freqs)

    gain_curve = hp * (10.0 ** (eq_db / 20.0))
    shaped = np.fft.irfft(spec * gain_curve, n=len(arr)).astype(np.float32)

    # Gentle active-speech RMS balancing toward -19.5 dBFS (0.106) so W/D/X sit at matched studio distance
    fl = 480  # 20ms @ 24kHz
    nf = len(shaped) // fl
    if nf >= 2:
        fmat = shaped[: nf * fl].reshape(nf, fl)
        frms = np.sqrt(np.mean(fmat * fmat, axis=1) + 1e-12)
        active = frms[frms > 0.006]
        if len(active) >= 1:
            med_rms = float(np.median(active))
            level_mult = float(np.clip(0.106 / max(med_rms, 1e-4), 0.78, 1.28))
            shaped *= level_mult
    return shaped


def decode_to_pcm_f32(audio_path: str, trim_speech: bool = True, spk_key: str = "") -> np.ndarray:
    """
    Decodes an audio file directly to 24kHz mono float32 [-1.0, 1.0] PCM.
    Supports native 24kHz mono WAV loading without ffmpeg when trim_speech=False,
    plus full ffmpeg speech trimming, 3-host zero-phase vocal timbre shaping & click-free micro-fades.
    """
    if not trim_speech and audio_path.lower().endswith(".wav") and os.path.exists(audio_path):
        try:
            with wave.open(audio_path, "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == SR:
                    raw_w = wf.readframes(wf.getnframes())
                    return np.frombuffer(raw_w, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            pass
    cmd = ["ffmpeg", "-v", "error", "-i", audio_path]
    if trim_speech:
        af = (
            "silenceremove=start_periods=1:start_duration=0.0:start_threshold=-54dB:start_silence=0.018,"
            "areverse,silenceremove=start_periods=1:start_duration=0.0:start_threshold=-54dB:start_silence=0.024,areverse"
        )
        cmd.extend(["-af", af])
    cmd.extend(["-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "1", "pipe:1"])
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    raw_bytes = res.stdout
    if res.returncode != 0 or len(raw_bytes) < 96:
        res2 = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", audio_path, "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "1", "pipe:1"],
            stdout=subprocess.PIPE,
            check=True,
        )
        raw_bytes = res2.stdout

    arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if trim_speech and spk_key:
        arr = apply_host_vocal_timbre(arr, spk_key)
    if trim_speech and len(arr) > 64:
        fade_n = min(int(SR * 0.014), len(arr) // 4)
        if fade_n > 4:
            ramp = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fade_n, dtype=np.float32))
            arr[:fade_n] *= ramp
            arr[-fade_n:] *= ramp[::-1]
    return arr


class StudioTimelineMixer:
    """Sample-accurate 24kHz float32 PCM timeline builder with TV ducking & warm studio room tone."""

    def __init__(self, est_minutes: float = 42.0):
        init_samples = int(SR * est_minutes * 60)
        self.buf = np.zeros(init_samples, dtype=np.float32)
        self.cursor = 0  # in samples
        self.max_written = 0

    def _ensure_cap(self, needed_end: int) -> None:
        if needed_end <= len(self.buf):
            return
        grow = max(needed_end - len(self.buf), int(SR * 300))
        self.buf = np.pad(self.buf, (0, grow), mode="constant")

    @property
    def sec(self) -> float:
        return self.cursor / float(SR)

    def advance(self, delta_sec: float) -> None:
        self.cursor = max(0, self.cursor + int(round(delta_sec * SR)))
        if self.cursor > self.max_written:
            self._ensure_cap(self.cursor)
            self.max_written = self.cursor

    def place_at(self, start_sec: float, clip: np.ndarray, gain: float | np.ndarray = 1.0) -> float:
        if len(clip) == 0:
            return start_sec
        idx = max(0, int(round(start_sec * SR)))
        end = idx + len(clip)
        self._ensure_cap(end)
        self.buf[idx:end] += clip * gain
        if end > self.max_written:
            self.max_written = end
        return end / float(SR)

    def append_clip(self, clip: np.ndarray, gain: float = 1.0, crossfade_sec: float = 0.0) -> None:
        if len(clip) == 0:
            return
        ov = int(round(crossfade_sec * SR)) if crossfade_sec > 0 else 0
        if ov > 0 and self.cursor >= ov:
            duck_curve = np.linspace(1.0, 0.42, ov, dtype=np.float32)
            self.buf[self.cursor - ov : self.cursor] *= duck_curve
            self.cursor -= ov
        end = self.cursor + len(clip)
        self._ensure_cap(end)
        self.buf[self.cursor:end] += clip * gain
        self.cursor = end
        if end > self.max_written:
            self.max_written = end

    def render_mp3(self, out_mp3: str) -> float:
        total_n = max(1, self.max_written)
        audio = self.buf[:total_n].copy()

        # Add ultra-subtle -58 dBFS warm studio room tone so speaker pauses never feel like dead digital vacuum
        rng = np.random.default_rng(20261115)
        white = rng.standard_normal(total_n).astype(np.float32)
        # Simple 2-tap warm low-pass air filter
        room = (white + np.roll(white, 1) + np.roll(white, 2)) * (0.00042)
        # Fade room air softly at very start and very end
        edge_n = min(int(SR * 1.2), total_n // 4)
        if edge_n > 10:
            room[:edge_n] *= np.linspace(0.0, 1.0, edge_n, dtype=np.float32)
            room[-edge_n:] *= np.linspace(1.0, 0.0, edge_n, dtype=np.float32)
        audio += room

        # Soft peak safety ceiling at -1.0 dBFS (0.891) without pumping speech dynamics
        audio = np.where(np.abs(audio) > 0.85, np.tanh(audio * 1.05) * 0.89, audio)
        pcm16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_p = tf.name
        try:
            with wave.open(wav_p, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SR)
                wf.writeframes(pcm16.tobytes())
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", wav_p,
                    "-vn", "-ar", str(SR), "-ac", "1", "-b:a", "64k", "-c:a", "libmp3lame",
                    out_mp3,
                ],
                check=True,
            )
        finally:
            try:
                os.remove(wav_p)
            except OSError:
                pass
        return round(total_n / float(SR), 1)


def make_intro_duck_envelope(n_samples: int, duck_start_sec: float = 6.75) -> np.ndarray:
    """Full level during opening theme, then smoothly ducks -10dB as Wen Tao greets at ~6.85s."""
    env = np.ones(n_samples, dtype=np.float32)
    ds = int(round(duck_start_sec * SR))
    if ds < n_samples:
        rem = n_samples - ds
        # Smooth duck down to 0.30 then fade to 0.0
        duck_curve = np.linspace(1.0, 0.28, min(int(SR * 0.35), rem), dtype=np.float32)
        env[ds : ds + len(duck_curve)] = duck_curve
        if ds + len(duck_curve) < n_samples:
            tail_n = n_samples - (ds + len(duck_curve))
            env[ds + len(duck_curve) :] = np.linspace(0.28, 0.0, tail_n, dtype=np.float32)
    return env


def make_outro_swell_envelope(n_samples: int, voice_over_sec: float) -> np.ndarray:
    """Soft -12dB underscore while Wen Tao finishes his farewell, then swells smoothly to full warm outro!"""
    env = np.ones(n_samples, dtype=np.float32)
    vo_n = min(n_samples, max(0, int(round(voice_over_sec * SR))))
    if vo_n > 0:
        fade_in_n = min(int(SR * 0.45), vo_n)
        env[:vo_n] = 0.25
        if fade_in_n > 4:
            env[:fade_in_n] = np.linspace(0.0, 0.25, fade_in_n, dtype=np.float32)
        swell_n = min(int(SR * 0.55), n_samples - vo_n)
        if swell_n > 4:
            env[vo_n : vo_n + swell_n] = np.linspace(0.25, 1.0, swell_n, dtype=np.float32)
    return env


def turns_to_expanded_events(turns: list[tuple[str, object]]) -> list[tuple[str, object]]:
    raw_evs = []
    for idx, (spk, val) in enumerate(turns):
        if spk in ("PAUSE", "LATCH"):
            raw_evs.append((spk, float(val)))
        else:
            raw_evs.append((spk, str(val)))
            if idx + 1 < len(turns) and turns[idx + 1][0] not in ("PAUSE", "LATCH"):
                next_spk, next_val = turns[idx + 1]
                tr_kind, tr_sec = turn_switch_transition(spk, str(val), next_spk, str(next_val))
                raw_evs.append((tr_kind, tr_sec))
    expanded = []
    for spk, val in raw_evs:
        expanded.extend(expand_turn_events(spk, val))
    return expanded


async def main():
    dry_test = "--dry-test" in sys.argv
    os.makedirs(AUDIO_DIR, exist_ok=True)
    music_paths = ensure_qq_music_assets(force=False)

    if not dry_test and (edge_tts is None or shutil.which("ffmpeg") is None):
        print("Skipping live radio MP3 synthesis (edge_tts or ffmpeg unavailable in local sandbox).")
        return

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    now_pt = datetime.datetime.now(PT_TZ)
    study_dt = (now_pt - datetime.timedelta(hours=4)).date()
    if dry_test and "--dry-date" in sys.argv:
        try:
            _di = sys.argv.index("--dry-date")
            study_dt = datetime.date.fromisoformat(sys.argv[_di + 1])
        except Exception:
            pass
    today_str = study_dt.strftime("%Y-%m-%d")
    days_left = max(0, (EXAM_DATE - study_dt).days)
    day_ord = study_dt.toordinal()

    _rp = tutor_prefs.radio_prefs()
    _focus = tutor_prefs.focus_set()
    imm_profile = tutor_prefs.immersion_profile(day=today_str)

    voice_map = await detect_voice_map(ja_sentence_rate=imm_profile["ja_sentence_rate"]) if not dry_test else {
        f"{s}{g}": (s, "+5%", "+0Hz")
        for s in ("W", "D", "X", "M", "F")
        for g in ("", "_MID", "_JAB", "_FAST", "_SLOW", "_LOW", "_LAND", "_JA_INLINE", "_JA")
    }
    engine_tag = (
        "dry_test"
        if dry_test
        else (
            f"gemini:{GEMINI_TTS_MODEL}"
            if (GEMINI_API_KEY and genai is not None)
            else f"edge:{voice_map['W'][0]}:{voice_map['D'][0]}:{voice_map['X'][0]}"
        )
    )

    night_sig = load_night_summary_signals()
    night_items = set(
        str(x).strip()
        for x in (
            (night_sig.get("missed_or_unsure_points") or [])
            + (night_sig.get("missed_vocab_words") or [])
            + (night_sig.get("looked_up_expressions") or [])
        )
        if str(x).strip()
    )

    recent_wrong, hot_wrong = load_recent_mistakes()
    hot_wrong = hot_wrong | night_items
    scores = load_mastery_priority(state, recent_wrong, hot_wrong)
    recent_ages = load_recent_story_ages(today_str, max_days=21)
    rng = random.Random(today_str)
    pool_order = {st["id"]: idx for idx, st in enumerate(SALON_STORIES)}

    def _uchi_vol_prefix(sid: str) -> str:
        if sid.startswith(("uchi_night_focus_", "uchi_auto_", "world_auto_")):
            return ""
        m = re.match(r"^(uchi\d*_)", sid)
        return m.group(1) if m else ""

    def story_rank(st: dict) -> float:
        pids = st.get("point_ids") or []
        pkeys = [resolve_point_key(pid) for pid in pids]
        pt_vals = sorted((scores.get(pid, 2.2) for pid in pids), reverse=True)
        top_avg = sum(pt_vals[:3]) / max(1, len(pt_vals[:3])) if pt_vals else 2.2
        days_ago = recent_ages.get(st["id"], 0)
        # Hard 21-day anti-repeat gate: any chapter played within 21 days gets heavy penalty so it NEVER beats unplayed chapters
        repeat_penalty = (100.0 - min(21, days_ago) * 2.0) if days_ago > 0 else 0.0
        memory_bonus = 0.0
        if st["id"] in _rp["avoid_story_ids"]:
            memory_bonus -= 50.0
        tier = st.get("tier", "")
        if tier == "live_news":
            memory_bonus += 6.2
        elif tier == "uchi_intellectual":
            memory_bonus += 5.0
            p_idx = pool_order.get(st["id"], 50)
            memory_bonus += max(0.0, 1.5 - 0.04 * p_idx)
        if str(st.get("id") or "").startswith("uchi_night_focus_"):
            memory_bonus += 2.4
        ja_focus_s = str(st.get("ja_focus") or "")
        if night_items and (
            any((pid in night_items or pk in night_items) for pid, pk in zip(pids, pkeys))
            or any(ni in ja_focus_s for ni in night_items if len(ni) >= 2)
        ):
            memory_bonus += 1.15
        if _focus and any((pid in _focus or pk in _focus) for pid, pk in zip(pids, pkeys)):
            memory_bonus += 0.8
        blob = f'{st.get("title", "")} {" ".join(st.get("tags", []) or [])}'
        if any(tag and tag in blob for tag in _rp["prefer_tags"]):
            memory_bonus += 0.3
        jitter = rng.uniform(-0.12, 0.12)
        return -(top_avg - repeat_penalty + memory_bonus + jitter)

    # Script a fresh daily NHK news Act-1 roundtable calibrated to today's ja_ratio + last night's mistakes
    has_today_dated_news = any(
        today_str.replace("-", "") in st["id"] or today_str in st["id"]
        for st in SALON_STORIES
        if st["id"] not in recent_ages
    )
    ranked_focus = [resolve_point_key(pid) for pid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:6]]
    top_focus_labels = []
    for item in list(night_sig.get("missed_or_unsure_points") or [])[:4] + list(night_sig.get("looked_up_expressions") or [])[:3] + ranked_focus:
        if item and item not in top_focus_labels:
            top_focus_labels.append(item)
    top_focus_labels = top_focus_labels[:8]
    _preview_groups: dict[str, list[dict]] = {}
    _preview_order: list[str] = []
    for _pst in SALON_STORIES:
        _pvp = _uchi_vol_prefix(_pst["id"])
        if _pvp and recent_ages.get(_pst["id"], 0) == 0:
            if _pvp not in _preview_groups:
                _preview_groups[_pvp] = []
                _preview_order.append(_pvp)
            _preview_groups[_pvp].append(_pst)
    _next_vp = next((vp for vp in _preview_order if len(_preview_groups[vp]) >= 5), "")
    uchi_companion_titles = [st["title"] for st in (_preview_groups.get(_next_vp) or SALON_STORIES)[:6]]
    live_news_story = (
        None
        if has_today_dated_news
        else maybe_generate_live_news_story(
            today_str=today_str,
            imm_profile=imm_profile,
            focus_points=top_focus_labels,
            companion_titles=uchi_companion_titles,
            dry_test=dry_test,
        )
    )
    live_world_finale_story = (
        maybe_generate_live_world_finale_story(
            today_str=today_str,
            imm_profile=imm_profile,
            focus_points=top_focus_labels,
            companion_titles=uchi_companion_titles,
            dry_test=dry_test,
        )
        if today_str >= "2026-11-22"
        else None
    )
    base_pool = []
    for st in SALON_STORIES:
        if live_news_story and st.get("short_tab") == "今日时局":
            st_copy = dict(st)
            st_copy["short_tab"] = "民生账本"
            base_pool.append(st_copy)
        else:
            base_pool.append(st)
    candidate_pool = (
        ([live_news_story] if live_news_story else [])
        + base_pool
        + ([live_world_finale_story] if live_world_finale_story else [])
    )

    def _is_world_finale_story(st: dict) -> bool:
        sid = str(st.get("id") or "")
        return bool(st.get("is_world_finale")) or st.get("tier") == "world_from_japan" or "_world_" in sid or sid.startswith(("live_world_finale_", "world_auto_"))

    def _is_epilogue_story(st: dict) -> bool:
        if _is_world_finale_story(st):
            return True
        sid = str(st.get("id") or "")
        if sid.endswith("_epilogue") or "_epilogue" in sid:
            return True
        turns = st.get("turns") or []
        if turns:
            last_t = str(turns[-1][1])
            if "锵锵三人行" in last_t and any(w in last_t for w in ("明天见", "下期见", "再见", "回见")):
                return True
        return False

    story_by_id = {st["id"]: st for st in candidate_pool}

    # If today_str already has a Uchi volume assigned in radio_history.json, keep that cohesive volume
    # (auto-including all sibling chapters of the same uchiN_ volume and stripping stray non-Uchi story_* tails)
    pinned_today_ids: list[str] = []
    if os.path.exists(RADIO_HISTORY_PATH):
        try:
            _rh = json.load(open(RADIO_HISTORY_PATH, encoding="utf-8")).get("recent_days") or {}
            _tids = [str(x) for x in (_rh.get(today_str) or []) if x]
            if len(_tids) >= 5 and any(x.startswith("uchi") for x in _tids):
                _clean_tids = [x for x in _tids if not x.startswith("story_") and x in story_by_id]
                _dom_prefixes = [_uchi_vol_prefix(x) for x in _clean_tids if _uchi_vol_prefix(x)]
                if _dom_prefixes:
                    _vpref = _dom_prefixes[0]
                    _full_vol_objs = [st for st in candidate_pool if _uchi_vol_prefix(st["id"]) == _vpref]
                    if live_news_story and live_news_story["id"] not in [st["id"] for st in _full_vol_objs]:
                        _full_vol_objs = [live_news_story] + [st for st in _full_vol_objs if not st.get("is_news_slot")]
                    if live_world_finale_story and live_world_finale_story["id"] not in [st["id"] for st in _full_vol_objs]:
                        _full_vol_objs = [st for st in _full_vol_objs if not _is_world_finale_story(st)] + [live_world_finale_story]
                    pinned_today_ids = [st["id"] for st in _full_vol_objs]
                else:
                    pinned_today_ids = _clean_tids
        except Exception:
            pinned_today_ids = []

    if pinned_today_ids and all(sid in story_by_id for sid in pinned_today_ids):
        selected_stories = [story_by_id[sid] for sid in pinned_today_ids]
    else:
        # Select a complete cohesive unplayed uchiN_ volume in authored narrative order when available
        vol_groups: dict[str, list[dict]] = {}
        vol_order: list[str] = []
        for st in candidate_pool:
            vp = _uchi_vol_prefix(st["id"])
            if vp and recent_ages.get(st["id"], 0) == 0:
                if vp not in vol_groups:
                    vol_groups[vp] = []
                    vol_order.append(vp)
                vol_groups[vp].append(st)
        cohesive_vp = next((vp for vp in vol_order if len(vol_groups[vp]) >= 5), "")
        if cohesive_vp:
            picked_list: list[dict] = []
            if live_news_story:
                picked_list.append(live_news_story)
            for st in candidate_pool:
                if str(st.get("id") or "").startswith(f"uchi_night_focus_{today_str.replace('-', '')}") and st not in picked_list:
                    picked_list.append(st)
            _vol_chapters = list(vol_groups[cohesive_vp])
            if live_news_story and any(st.get("is_news_slot") for st in _vol_chapters):
                # Cleanly replace fallback Act-1 news slot with today's fresh live NHK news
                _vol_chapters = [st for st in _vol_chapters if not st.get("is_news_slot")]
            if live_world_finale_story:
                # Cleanly replace fallback final-1/5 world slot with today's fresh live World-from-Japan finale
                _vol_chapters = [st for st in _vol_chapters if not _is_world_finale_story(st)]
                _vol_chapters.append(live_world_finale_story)
            elif today_str >= "2026-11-22" and not any(_is_world_finale_story(st) for st in _vol_chapters):
                _unplayed_wf = [st for st in candidate_pool if _is_world_finale_story(st) and recent_ages.get(st["id"], 0) == 0]
                if _unplayed_wf:
                    _vol_chapters.append(_unplayed_wf[0])
            picked_list.extend(_vol_chapters)
            selected_stories = picked_list
        else:
            min_ep_min, max_ep_min = _rp["episode_minutes"]
            target_sec = ((min_ep_min + max_ep_min) / 2.0) * 60.0
            max_sec = (max_ep_min + 1.0) * 60.0
            est_sec = 72.0  # Opening theme + greeting + 2 ad bumpers + closing & outro
            picked_ids: set[str] = set()
            has_epilogue = False
            world_pick = None
            if today_str >= "2026-11-22":
                world_cands = [st for st in candidate_pool if _is_world_finale_story(st)]
                world_cands.sort(key=story_rank)
                if world_cands:
                    world_pick = world_cands[0]
                    est_sec += estimate_story_seconds(world_pick)
            for st in sorted(candidate_pool, key=story_rank):
                if _is_world_finale_story(st):
                    continue
                is_ep = _is_epilogue_story(st)
                if is_ep and (has_epilogue or world_pick is not None):
                    continue
                if len(picked_ids) >= 5 and str(st.get("id") or "").startswith("story_") and any(x.startswith("uchi") for x in picked_ids):
                    continue
                s_dur = estimate_story_seconds(st)
                if len(picked_ids) >= 5 and (est_sec + s_dur > max_sec or est_sec >= target_sec):
                    break
                picked_ids.add(st["id"])
                if is_ep:
                    has_epilogue = True
                est_sec += s_dur
                if len(picked_ids) >= 11:
                    break
            # Preserve candidate_pool narrative order so cross-chapter callbacks ("前后照应") stay sequential!
            selected_stories = [st for st in candidate_pool if st["id"] in picked_ids]
            if world_pick is not None:
                selected_stories.append(world_pick)

    # Hard guarantee: World-from-Japan final-1/5 (or epilogue) ALWAYS sits at the very end, NEVER mid-episode!
    _worlds = [st for st in selected_stories if _is_world_finale_story(st)]
    if _worlds:
        _non_w = [st for st in selected_stories if not _is_world_finale_story(st)]
        selected_stories = _non_w + [_worlds[-1]]
    else:
        _non_ep = [st for st in selected_stories if not _is_epilogue_story(st)]
        _eps = [st for st in selected_stories if _is_epilogue_story(st)]
        selected_stories = _non_ep + (_eps[-1:] if _eps else [])

    if imm_profile["ja_ratio"] >= 0.65:
        opening_turns = POST_N3_NATIVE_OPENING
        ad1_out_turns, ad1_in_turns = POST_N3_NATIVE_AD1
        ad2_out_turns, ad2_in_turns = POST_N3_NATIVE_AD2
        closing_turns = POST_N3_NATIVE_CLOSING
    elif imm_profile["bilingual_framing"]:
        opening_turns = POST_N3_BILINGUAL_OPENING
        ad1_out_turns, ad1_in_turns = AD_BREAK_1_POOL[day_ord % len(AD_BREAK_1_POOL)]
        ad2_out_turns, ad2_in_turns = AD_BREAK_2_POOL[(day_ord + 1) % len(AD_BREAK_2_POOL)]
        closing_turns = CLOSING_POOL[day_ord % len(CLOSING_POOL)]
    else:
        opening_turns = []
        ad1_out_turns, ad1_in_turns = AD_BREAK_1_POOL[day_ord % len(AD_BREAK_1_POOL)]
        ad2_out_turns, ad2_in_turns = AD_BREAK_2_POOL[(day_ord + 1) % len(AD_BREAK_2_POOL)]
        closing_turns = CLOSING_POOL[day_ord % len(CLOSING_POOL)]

    story_blocks = []
    for ch_idx, st in enumerate(selected_stories):
        pids = list(st.get("point_ids") or [])
        st_turns = list(st["turns"])
        # Authentic 98.3% Dou Wentao Cold-Open: Story 0 Turn 0 starts directly with "《锵锵三人行》，..." (zero templated roll-call!)
        if ch_idx == 0 and not opening_turns and st_turns:
            spk0, txt0 = st_turns[0][0], str(st_turns[0][1]).strip()
            if "锵锵三人行" not in txt0[:18]:
                st_turns[0] = (spk0, f"《锵锵三人行》，{txt0}")
        elif ch_idx > 0 and st_turns:
            spk0, txt0 = st_turns[0][0], str(st_turns[0][1]).strip()
            txt0_clean = re.sub(r"^《锵锵三人行》[，、：\s]*", "", txt0).strip()
            if txt0_clean and txt0_clean != txt0:
                st_turns[0] = (spk0, f"哎，再说回眼跟前儿这笔账，{txt0_clean}")
        story_blocks.append({
            "chapter": ch_idx,
            "short_tab": st["short_tab"],
            "point_id": pids[0] if pids else "",
            "point_ids": pids,
            "title": st["title"],
            "ja_focus": st["ja_focus"],
            "pair_part": int(st.get("pair_part") or 0),
            "is_world_finale": _is_world_finale_story(st),
            "raw_turns": st_turns,
            "events": turns_to_expanded_events(st_turns),
        })

    # Compute exact ad-break positions upfront (never splitting pair_part=1 from pair_part=2;
    # for 6-scene v37 [News, S1a, S1b, S2a, S2b, WorldFinale], breaks cleanly land after ch 0 and ch 2!)
    total_stories = len(story_blocks)
    if (
        total_stories == 6
        and story_blocks[-1].get("is_world_finale")
        and story_blocks[1].get("pair_part") == 1
        and story_blocks[3].get("pair_part") == 1
    ):
        ad1_after = 0
        ad2_after = 2
    else:
        act1_cnt = max(2, (total_stories + 2) // 3)
        act2_cnt = max(2, (total_stories - act1_cnt + 1) // 2)
        raw_ad1 = act1_cnt - 1
        raw_ad2 = min(total_stories - 2, act1_cnt + act2_cnt - 1)
        valid_breaks = [
            i for i in range(total_stories - 1)
            if story_blocks[i].get("pair_part") != 1
            and not (i == total_stories - 2 and story_blocks[-1].get("is_world_finale"))
        ]
        if len(valid_breaks) < 2:
            valid_breaks = [i for i in range(total_stories - 1) if story_blocks[i].get("pair_part") != 1]
        if len(valid_breaks) >= 2:
            ad1_after = min(valid_breaks[:-1], key=lambda x: abs(x - raw_ad1))
            rem_breaks = [x for x in valid_breaks if x > ad1_after]
            ad2_after = min(rem_breaks, key=lambda x: abs(x - raw_ad2))
        else:
            ad1_after = raw_ad1
            ad2_after = raw_ad2

    # Deduplicate ad-break transitions when authored scenes already cue "进广告 / 广告回来" naturally
    if imm_profile["ja_ratio"] < 0.65:
        if 0 <= ad1_after < total_stories and story_blocks[ad1_after]["raw_turns"]:
            if "广告" in str(story_blocks[ad1_after]["raw_turns"][-1][1])[-70:]:
                ad1_out_turns = []
        if 0 <= ad1_after + 1 < total_stories and story_blocks[ad1_after + 1]["raw_turns"]:
            _head1 = str(story_blocks[ad1_after + 1]["raw_turns"][0][1])[:12]
            if "广告" in _head1 or "回来" in _head1:
                ad1_in_turns = []
        if 0 <= ad2_after < total_stories and story_blocks[ad2_after]["raw_turns"]:
            if "广告" in str(story_blocks[ad2_after]["raw_turns"][-1][1])[-70:]:
                ad2_out_turns = []
        if 0 <= ad2_after + 1 < total_stories and story_blocks[ad2_after + 1]["raw_turns"]:
            _head2 = str(story_blocks[ad2_after + 1]["raw_turns"][0][1])[:12]
            if "广告" in _head2 or "回来" in _head2:
                ad2_in_turns = []

    # If the final chapter's final line already signs off with 《锵锵三人行》, don't tack on a duplicate closing line
    if story_blocks and story_blocks[-1]["raw_turns"]:
        last_line_txt = str(story_blocks[-1]["raw_turns"][-1][1])
        if "锵锵三人行" in last_line_txt and imm_profile["ja_ratio"] < 0.65:
            closing_turns = []

    opening_evs = turns_to_expanded_events(opening_turns) if opening_turns else []
    ad1_out_evs = turns_to_expanded_events(ad1_out_turns) if ad1_out_turns else []
    ad1_in_evs = turns_to_expanded_events(ad1_in_turns) if ad1_in_turns else []
    ad2_out_evs = turns_to_expanded_events(ad2_out_turns) if ad2_out_turns else []
    ad2_in_evs = turns_to_expanded_events(ad2_in_turns) if ad2_in_turns else []
    closing_evs = turns_to_expanded_events(closing_turns) if closing_turns else []

    if today_str >= "2026-11-22":
        radio_ver_tag = "v38_qq_60m_deep_story_135x"
    elif today_str >= "2026-11-19":
        radio_ver_tag = "v36_qq_real_public_memory"
    else:
        radio_ver_tag = "v34_3182_short_banter_latch"
    sig_obj = {
        "ver": radio_ver_tag,
        "engine": engine_tag,
        "imm_day": imm_profile["day_of_365"],
        "opening": opening_evs,
        "ad1": [ad1_out_evs, ad1_in_evs],
        "ad2": [ad2_out_evs, ad2_in_evs],
        "closing": closing_evs,
        "stories": [{k: v for k, v in b.items() if k not in ("raw_turns", "pair_part", "is_world_finale")} for b in story_blocks],
    }
    script_sig = hashlib.sha256(json.dumps(sig_obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:14]

    if not dry_test and os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            # Never overwrite 2026-11-18's already-completed episode tonight; v35 rebuild starts fresh on 2026-11-19!
            if old_meta.get("date") == today_str and (
                old_meta.get("script_sig") == script_sig or today_str <= "2026-11-18"
            ) and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                if today_str > "2026-11-18":
                    save_today_stories(today_str, [st["id"] for st in selected_stories])
                print(f"Daily Qiang-Qiang trio radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    if np is None or (not dry_test and (edge_tts is None or shutil.which("ffmpeg") is None)):
        print(f"[local-skip] Verified {len(story_blocks)} Qiang-Qiang stories (sig={script_sig}); full PCM/TTS synthesis runs in cloud CI.")
        return

    all_event_lists = [
        opening_evs,
        ad1_out_evs, ad1_in_evs,
        ad2_out_evs, ad2_in_evs,
        closing_evs,
        *(b["events"] for b in story_blocks),
    ]

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v34_")
    try:
        unique_turns: dict[tuple[str, str], str] = {}
        for ev_list in all_event_lists:
            for k, val in ev_list:
                if k not in ("PAUSE", "LATCH"):
                    key = (k, str(val))
                    if key not in unique_turns:
                        thash = hashlib.sha256(f"{k}:{val}".encode("utf-8")).hexdigest()[:12]
                        unique_turns[key] = os.path.join(tmpdir, f"raw_{thash}.mp3")

        if dry_test:
            print(f"[dry-test] Stories={[b['short_tab'] for b in story_blocks]}, unique_clips={len(unique_turns)}, script_sig={script_sig}")
            clip_pcm: dict[tuple[str, str], np.ndarray] = {}
            for key in unique_turns:
                dur_s = max(0.32, len(key[1]) * 0.192)
                t = np.arange(int(SR * dur_s), dtype=np.float32) / SR
                raw_tone = (0.11 * np.sin(2.0 * np.pi * 180.0 * t) + 0.05 * np.sin(2.0 * np.pi * 1650.0 * t)).astype(np.float32)
                clip_pcm[key] = apply_host_vocal_timbre(raw_tone, key[0])
        else:
            sem = asyncio.Semaphore(16)
            ok_results = await asyncio.gather(
                *(synth_turn(k, voice_map[k], txt, raw_p, sem) for (k, txt), raw_p in unique_turns.items())
            )
            ok_count = sum(1 for x in ok_results if x)
            print(f"Synthesized {ok_count} / {len(unique_turns)} unique Qiang-Qiang v38 60m short-banter latch clips.")
            min_required = max(1, int(len(unique_turns) * 0.98))
            if ok_count < min_required:
                raise RuntimeError(
                    f"TTS clip synthesis below safety threshold ({ok_count}/{len(unique_turns)} < {min_required}); refusing to overwrite daily_radio.mp3"
                )

            clip_pcm = {}

            def _decode_item(item):
                key, raw_p = item
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    return key, decode_to_pcm_f32(raw_p, trim_speech=True, spk_key=key[0])
                return key, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                for key, arr in pool.map(_decode_item, unique_turns.items()):
                    if arr is not None and len(arr) > 0:
                        clip_pcm[key] = arr

        # Load authentic 《锵锵三人行》 original broadcast music (Intro, Ad-Break Bumper, Outro — ZERO inter-chapter sting!)
        pcm_intro = decode_to_pcm_f32(music_paths["intro"], trim_speech=False)
        pcm_bumper = decode_to_pcm_f32(music_paths["bumper"], trim_speech=False)
        pcm_outro = decode_to_pcm_f32(music_paths["outro"], trim_speech=False)

        mixer = StudioTimelineMixer(est_minutes=68.0)

        def _append_events(ev_list: list[tuple[str, object]]) -> None:
            pending_latch = 0.0
            for idx, (k, val) in enumerate(ev_list):
                if k == "PAUSE":
                    pending_latch = 0.0
                    mixer.advance(float(val))
                elif k == "LATCH":
                    pending_latch = float(val)
                else:
                    key = (k, str(val))
                    arr = clip_pcm.get(key)
                    if arr is not None:
                        mixer.append_clip(arr, gain=gear_gain_linear(k), crossfade_sec=pending_latch)
                    pending_latch = 0.0

        # 1) 00:00.0 — Authentic 《锵锵三人行》 Opening Theme -> Clean Studio Entry!
        intro_dur_sec = len(pcm_intro) / float(SR)
        entry_sec = max(6.8, intro_dur_sec - 0.85)
        intro_env = make_intro_duck_envelope(len(pcm_intro), duck_start_sec=entry_sec - 0.15)
        mixer.place_at(0.0, pcm_intro, gain=intro_env)
        mixer.advance(entry_sec)

        chapter_starts: dict[int, float] = {0: 0.0}
        raw_seg_bounds: list[tuple[int, float, float]] = []

        if opening_evs:
            _append_events(opening_evs)
            mixer.advance(0.28)

        for ch_idx, b in enumerate(story_blocks):
            seg_start = 0.0 if ch_idx == 0 else round(mixer.sec, 1)
            if ch_idx not in chapter_starts:
                chapter_starts[ch_idx] = seg_start

            # If returning from an ad break, resume seamlessly right at the chapter mark!
            if ch_idx == ad1_after + 1 and ad1_in_evs:
                _append_events(ad1_in_evs)
                mixer.advance(0.22)
            elif ch_idx == ad2_after + 1 and ad2_in_evs:
                _append_events(ad2_in_evs)
                mixer.advance(0.22)

            # Main Salon Story Dialogue (for final story without separate closing_turns, sneak outro underneath final turn!)
            is_last_story = (ch_idx == total_stories - 1)
            if is_last_story and not closing_turns and len(b["raw_turns"]) >= 2:
                body_evs = turns_to_expanded_events(b["raw_turns"][:-1])
                final_w_evs = turns_to_expanded_events([b["raw_turns"][-1]])
                _append_events(body_evs)
                mixer.advance(0.18)
                w_start_sec = mixer.sec
                _append_events(final_w_evs)
                w_end_sec = mixer.sec
                w_dur = max(0.8, w_end_sec - w_start_sec)
                vo_overlap = min(2.0, w_dur * 0.45)
                outro_start = max(w_start_sec, w_end_sec - vo_overlap)
                outro_env = make_outro_swell_envelope(len(pcm_outro), voice_over_sec=(w_end_sec - outro_start))
                outro_end = mixer.place_at(outro_start, pcm_outro, gain=outro_env)
                mixer.cursor = int(round(outro_end * SR))
            else:
                _append_events(b["events"])

            # End-of-Story Transitions (ZERO "叮叮" stings between ordinary chapters — ONLY at the 2 "广告之后见" breaks!)
            if ch_idx == ad1_after:
                mixer.advance(0.26)
                if ad1_out_evs:
                    _append_events(ad1_out_evs)
                    mixer.advance(0.18)
                bumper_end = mixer.place_at(mixer.sec, pcm_bumper, gain=0.95)
                mixer.cursor = int(round((bumper_end + 0.24) * SR))
            elif ch_idx == ad2_after:
                mixer.advance(0.26)
                if ad2_out_evs:
                    _append_events(ad2_out_evs)
                    mixer.advance(0.18)
                bumper_end = mixer.place_at(mixer.sec, pcm_bumper, gain=0.95)
                mixer.cursor = int(round((bumper_end + 0.24) * SR))
            elif ch_idx < total_stories - 1:
                # Direct natural conversational continuation — ZERO chime/sting!
                mixer.advance(0.32)
            elif closing_turns:
                mixer.advance(0.35)
                pre_close_evs = turns_to_expanded_events(closing_turns[:-1]) if len(closing_turns) >= 2 else []
                final_w_evs = turns_to_expanded_events([closing_turns[-1]])
                if pre_close_evs:
                    _append_events(pre_close_evs)
                    mixer.advance(0.20)
                w_start_sec = mixer.sec
                _append_events(final_w_evs)
                w_end_sec = mixer.sec
                w_dur = max(0.8, w_end_sec - w_start_sec)
                vo_overlap = min(2.0, w_dur * 0.55)
                outro_start = max(w_start_sec, w_end_sec - vo_overlap)
                outro_env = make_outro_swell_envelope(len(pcm_outro), voice_over_sec=(w_end_sec - outro_start))
                outro_end = mixer.place_at(outro_start, pcm_outro, gain=outro_env)
                mixer.cursor = int(round(outro_end * SR))

            seg_end = round(mixer.sec, 1)
            raw_seg_bounds.append((ch_idx, seg_start, seg_end))

        if dry_test:
            test_mp3 = os.path.join(tmpdir, "dry_test_radio.mp3")
            dur = mixer.render_mp3(test_mp3)
            print(f"[dry-test] Rendered full broadcast timeline MP3: {dur:.1f}s ({os.path.getsize(test_mp3)} bytes)")
            print(f"[dry-test] Act breaks after ch {ad1_after} & {ad2_after}; Chapters: {chapter_starts}")
            return

        final_dur = mixer.render_mp3(RADIO_MP3_PATH)
        mins = max(1, round(final_dur / 60.0))

        # Ensure contiguous gap-free segment bounds [0.0 .. final_dur] for live player highlight
        segments_meta = []
        for i, b in enumerate(story_blocks):
            s_start = 0.0 if i == 0 else chapter_starts.get(i, raw_seg_bounds[i][1])
            s_end = chapter_starts.get(i + 1, final_dur) if (i + 1 < len(story_blocks)) else final_dur
            segments_meta.append({
                "chapter": b["chapter"],
                "point_id": b["point_id"] or "",
                "point_ids": b["point_ids"],
                "title": b["title"],
                "ja_focus": b["ja_focus"],
                "start": round(s_start, 1),
                "end": round(s_end, 1),
            })

        chapters_meta = [
            {"idx": b["chapter"], "title": b["short_tab"], "start": round(chapter_starts.get(b["chapter"], 0.0), 1)}
            for b in story_blocks
        ]
        meta_obj = {
            "date": today_str,
            "radio_ver": radio_ver_tag,
            "display_date": "锵锵三人",
            "days_left": days_left,
            "script_sig": script_sig,
            "audio_url": f"./audio/daily_radio.mp3?v={today_str}_{script_sig[:6]}",
            "duration_sec": final_dur,
            "duration_label": f"{mins} 分钟",
            "hosts": "文涛 · 文道 · 子东",
            "immersion_365": imm_profile,
            "chapters": chapters_meta,
            "segments": segments_meta,
        }
        with open(RADIO_META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta_obj, f, ensure_ascii=False, indent=2)
        save_today_stories(today_str, [st["id"] for st in selected_stories])
        print(f"Built Qiang-Qiang {radio_ver_tag} Uchi Episode: {final_dur:.1f}s ({mins} mins), stories={[s['short_tab'] for s in selected_stories]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
