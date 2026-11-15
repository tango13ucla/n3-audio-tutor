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
2) Deep Intellectual & True Japanese "Uchi (内)" Content + 365-Day Progressive Immersion:
   - Moves beyond tourist "Soto (外)" clichés into live Japanese/world current affairs, intellectual history (e.g. 1968 Todai Zenkyoto),
     literary masters (Mishima, Tanizaki, Dazai, Soseki), science institutions (Kyodai Nobel vs Kozasei), and closed-door Japanese family/work life,
     with cross-chapter callbacks ("前后照应") across a ~40-minute episode.
   - Tracks `tutor_prefs.immersion_profile(day)`: ~10% Japanese up through 2026-12-06 N3 exam, then smoothly increases day by day
     (12% -> 50% -> 92%) over 365 days with the exact same three hosts into a near-pure Japanese intellectual podcast.
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
import numpy as np

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
from daily_news_salon_gen import maybe_generate_live_news_story
from radio_dialogue_bank import MODALITY_MAP, SALON_STORIES
import tutor_prefs
from tutor_data import TUTOR_ITEMS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
RADIO_MP3_PATH = os.path.join(AUDIO_DIR, "daily_radio.mp3")
RADIO_META_PATH = os.path.join(AUDIO_DIR, "daily_radio_meta.json")
RADIO_HISTORY_PATH = os.path.join(AUDIO_DIR, "radio_history.json")

SR = 24000
PT_TZ = ZoneInfo("America/Los_Angeles")
EXAM_DATE = datetime.date(2026, 12, 6)
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
COMM_KWARGS = {"proxy": PROXY_URL} if PROXY_URL else {}
MAX_TRIES = 5 if os.environ.get("GITHUB_ACTIONS") == "true" else 1
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Matches Japanese spans (inline words spoken smoothly in-flow; full sentences spoken clearly at -12%/-13%)
JA_SPAN_RE = re.compile(r"([\u3040-\u30ffー・]+(?:[、。！？\s]+[\u3040-\u30ffー・]+)*[。！？]?)")

# Split Mandarin ONLY on genuine comic slip-of-the-tongue self-corrections ("……呸，" / "……哦不对")
SLIP_SPLIT_RE = re.compile(
    r"…+(?=(?:呸|不对|哦不对|哎不对|害，哪有|哦日本哪儿|哦不用两大碗|哦三分钟|哦四回|哦一千|少说了俩零|哪有扫码枪))"
)

EXCITED_TURN_RE = re.compile(
    r"^(?:《锵锵三人行》|欢迎继续|欢迎回到|好家伙|神了|哎哟|等会儿|学会了|妙啊|太有画面|真是服了|这下记得)"
)
REFLECT_TURN_RE = re.compile(
    r"^(?:其实|前两天|如果有人|话说回来|所以你想想|而且讲句老实话)"
)
LATCH_START_RE = re.compile(
    r"^(?:神了|等会儿|等等|那我肯定|对极了|对啊|对，|可不嘛|一点儿没错|一点儿不差|"
    r"完全正确|太准了|问到点子上了|哎哟|哦！|妙啊|我知道|我就干过)"
)

GENERIC_POINT_LABELS = {"口语听辨", "高频假名副词", "核心词汇", "语法", "活用"}


# ==============================================================================
# Authentic 《锵锵三人行》 Rotating Opening Greetings, Ad Bumpers & Closings
# (100% Zero Date / Zero Exam Countdown — True Intellectual Gentlemen Salon Vibe)
# ==============================================================================
OPENING_GREETINGS_POOL = [
    [
        ("W", "《锵锵三人行》！哎，文道好，子东好，各位好！"),
        ("D", "文涛好，大家好。"),
        ("X", "文涛好，各位好。"),
        ("W", "今儿咱们老哥仨坐一块儿啊，热茶刚沏满。咱们不聊游客明信片上那套表皮风光，专门掀开帘子，往日本政坛时局、文坛旧案，还有普通日本人关起门来算计的真日子里头扎进去聊。来，先看今儿头一桩热闹事儿！"),
    ],
    [
        ("W", "《锵锵三人行》！欢迎文道，欢迎子东，二位好，各位好！"),
        ("D", "文涛好，各位听众朋友好。"),
        ("X", "文涛好，大家好。看你今儿面前摊着一摞剪报，又是国会吵架又是老作家八卦，准备从哪头开刀啊？"),
        ("W", "知我者许老师也！咱们表面上是插科打诨扯闲篇儿，底子里头聊的都是东亚社会骨头缝里的真问题，从眼下新闻一路串到历史、文学和科学体制，前后都能对上账！"),
    ],
    [
        ("W", "《锵锵三人行》！文道、子东，二位好，各位好！"),
        ("D", "文涛好，大家好。"),
        ("X", "文涛好，各位好。"),
        ("W", "日本社会最妙的地方，就是它永远分两层：给外人看的那层叫外，念 そと；自家人关上玄关门算账叹气那层叫内，念 うち。今儿咱们就着这壶热茶，专门钻进日本人的 うち 里头探探虚实！"),
    ],
    [
        ("W", "《锵锵三人行》！各位好，今天还是咱们仨坐镇啊，文道好，子东好！"),
        ("D", "文涛好，大家好。"),
        ("X", "文涛好，各位好。"),
        ("W", "每次跟你们二位同桌我就来劲，一个满脑子政治思想史，一个专扒大文豪和现代家庭的底牌。今儿咱们前前后后串成一条大长线，先从眼皮底下热气腾腾的时局说起！"),
    ],
]

AD_BREAK_1_POOL = [
    (
        [("W", "哎，聊到这个节骨眼儿上咱们先打住一下，去一下广告，喝口热茶回头接着往深里头扒。《锵锵三人行》，广告之后见！")],
        [("W", "欢迎继续回到《锵锵三人行》！刚才前头铺了政经和历史的底子，茶添满了，咱们顺着这条暗线接着往下聊啊。")],
    ),
    (
        [("W", "得，这事儿越往骨子里琢磨越有嚼头，咱们先去下广告，马上回来接着聊。《锵锵三人行》，广告之后见！")],
        [("W", "《锵锵三人行》，欢迎回来！咱们话不停嘴，顺着刚才的话茬儿往文学和体制深水区里头走啊。")],
    ),
    (
        [("W", "好，说到这儿咱们先喘口气，去一下广告，后头还有几位日本文坛与科学界的奇人等着二位开方子呢。《锵锵三人行》，广告之后见！")],
        [("W", "好，欢迎继续收听《锵锵三人行》，咱们接着刚才的兴头往下侃！")],
    ),
]

AD_BREAK_2_POOL = [
    (
        [("W", "你看这历史文脉和制度骨架一摆出来，很多怪事儿就全通了。咱们再去一下广告，回来钻进今天东京人关起门来的家庭与职场。《锵锵三人行》，广告之后见！")],
        [("W", "欢迎回到《锵锵三人行》！前头聊了庙堂和书斋，最后这一大段咱们直接推开日本中产家庭的客厅门瞧瞧！")],
    ),
    (
        [("W", "行，聊到这儿咱们再去下广告，稍事休息马上回来。《锵锵三人行》，广告之后见！")],
        [("W", "《锵锵三人行》，咱们回来接着聊，把最后这几桩日本人关起门来最扎心的家务事端上桌！")],
    ),
    (
        [("W", "哎，先别急，咱们去一下广告，广告之后把前头埋的伏笔全拢到今天日本人的饭桌和房产证上。《锵锵三人行》，广告之后见！")],
        [("W", "继续回到《锵锵三人行》，咱们接着把最后这几段聊透！")],
    ),
]

CLOSING_POOL = [
    [
        ("D", "其实啊，不知不觉咱们这壶热茶又喝见底了。你回头串起来看，不管是永田町的密室政治、东大与京大的学风分野，还是中年人面对塔楼和老家清退的叹息，背后全是同一套日本社会的内外法则在咬合运转。"),
        ("X", "对，而且只有从游客看热闹的外面 そと，真正走进日本人关起门来焦灼算计的里面 うち，那些话尾巴上的分寸和潜台词才真正在耳朵里活过来了。"),
        ("W", "得嘞，今儿咱们老哥仨就先白活到这儿，感谢文道，感谢子东，也谢谢各位收听！《锵锵三人行》，咱们明天接着聊，明天见！"),
    ],
    [
        ("D", "你看咱们今儿从时局账本一路聊到文学巨匠和职场冷暖，前前后后一照应就会发现，日本知识分子百年前犯的焦虑，跟今天东京上班族挤电车叹的气，其实是同一条根上长出来的。"),
        ("X", "没错，每天就当听老朋友喝茶扯闲篇儿，把这些政经掌故、文坛八卦和家常暗语一点点浸在耳朵里，日久天长自个儿就长进骨肉里了。"),
        ("W", "行嘞，茶也喝透了，感谢文道、感谢子东，也谢谢各位一路听过来！《锵锵三人行》，咱们明天见！"),
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


def load_previous_day_stories(today_str: str) -> tuple[set, set, set]:
    if not os.path.exists(RADIO_HISTORY_PATH):
        return set(), set(), set()
    try:
        with open(RADIO_HISTORY_PATH, encoding="utf-8") as f:
            hist = json.load(f)
        by_date = hist.get("recent_days") or {}
        prior_dates = sorted(d for d in by_date.keys() if d < today_str)
        prev_1 = set(by_date.get(prior_dates[-1]) or []) if len(prior_dates) >= 1 else set()
        prev_2 = set(by_date.get(prior_dates[-2]) or []) if len(prior_dates) >= 2 else set()
        prev_3 = set(by_date.get(prior_dates[-3]) or []) if len(prior_dates) >= 3 else set()
        return prev_1, prev_2, prev_3
    except Exception:
        return set(), set(), set()


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


def estimate_story_seconds(st: dict) -> float:
    """Empirical v28/v29 studio timing: ~0.206s per spoken char + 2.5s transition sting."""
    chars = sum(len(str(t)) for _, t in (st.get("turns") or []))
    return chars * 0.206 + 2.5


async def detect_voice_map(ja_sentence_rate: str = "-12%") -> dict:
    """
    Coherent, natural host voices (ZERO mid-sentence pitch/rate jumping):
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
        # W (文涛): 自然灵动，绝不忽高忽低跳调
        "W":             (w_voice, "+7%", "+2Hz"),
        "W_MID":         (w_voice, "+7%", "+2Hz"),
        "W_FAST":        (w_voice, "+10%", "+2Hz"),
        "W_LOW":         (w_voice, "+4%", "+1Hz"),
        "W_JA_INLINE":   (w_voice, "+6%", "+2Hz"),
        "W_JA":          (w_voice, w_ja_rate, "+2Hz"),
        # D (文道): 温厚沉稳书卷气
        "D":             (d_voice, "+2%", "-4Hz"),
        "D_MID":         (d_voice, "+2%", "-4Hz"),
        "D_FAST":        (d_voice, "+5%", "-3Hz"),
        "D_LOW":         (d_voice, "+0%", "-4Hz"),
        "D_JA_INLINE":   (d_voice, "+2%", "-4Hz"),
        "D_JA":          (d_voice, d_ja_rate, "-4Hz"),
        # X (子东): 清脆干练冷幽默
        "X":             (x_voice, "+5%", "-1Hz"),
        "X_MID":         (x_voice, "+5%", "-1Hz"),
        "X_FAST":        (x_voice, "+8%", "+0Hz"),
        "X_LOW":         (x_voice, "+3%", "-1Hz"),
        "X_JA_INLINE":   (x_voice, "+5%", "-1Hz"),
        "X_JA":          (x_voice, x_ja_rate, "-1Hz"),
    }
    for g in ("", "_MID", "_FAST", "_LOW", "_JA_INLINE", "_JA"):
        vmap[f"M{g}"] = vmap[f"W{g}"]
        vmap[f"F{g}"] = vmap[f"X{g}"]
    return vmap


def clean_ja_sentence_commas(ks: str) -> str:
    """
    Removes artificial post-particle commas (`でんしゃが、がらがらだ` -> `でんしゃががらがらだ`)
    that made Japanese sentences sound halting, while preserving genuine clause boundaries
    and deliberate mora-by-mora demonstrations (`は、な、さ、せ、ら、れ、た`).
    """
    # Preserve deliberate single-mora spelling demonstrations like は、な、さ、せ、ら、れ、た
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
        # Keep comma after interjections, clause conjunctions, or long clauses (>= 10 mora)
        if prev.endswith(KEEP_ENDINGS) or len(prev) >= 10:
            merged.append(nxt)
        else:
            # Drop unnatural particle comma right after short subject/object/adverbial (は/が/を/に/も/と)
            merged[-1] = prev + nxt
    return "、".join(merged)


def pick_turn_gear(spk: str, full_txt: str) -> str:
    s = full_txt.strip()
    if EXCITED_TURN_RE.search(s):
        return f"{spk}_FAST"
    if REFLECT_TURN_RE.search(s):
        return f"{spk}_LOW"
    return f"{spk}_MID"


def split_mandarin_natural(base_spk: str, pt_s: str, default_gear: str) -> list[tuple[str, object]]:
    """
    Keeps Mandarin sentences completely whole so neural TTS handles comma rhythm & breath naturally!
    Splits ONLY on genuine comic slip-of-the-tongue self-corrections (`SLIP_SPLIT_RE`).
    """
    s = pt_s.strip()
    if not s:
        return []
    # Split only on real self-corrections ("……呸，" / "……哦不对")
    slip_parts = SLIP_SPLIT_RE.split(s)
    events: list[tuple[str, object]] = []
    for idx, sub in enumerate(slip_parts):
        # Convert any remaining rhetorical ellipses `……` into smooth comma continuation inside the same breath
        clean = re.sub(r"…+", "，", sub).strip()
        clean = re.sub(r"，([，。！？；：])", r"\1", clean)
        clean = re.sub(r"^[,，、；：]+", "", clean).strip()
        if not clean or not re.search(r"[\w\u3040-\u9fff]", clean):
            continue
        if idx == 0 and len(slip_parts) > 1:
            # Trailing off right before catching a slip of the tongue
            if clean[-1] not in "。！？，、：":
                clean = clean + "，"
            events.append((default_gear, clean))
            events.append(("PAUSE", 0.16))
        elif idx > 0:
            # Brisk, lively self-correction ("呸，我说反了！")
            events.append((f"{base_spk}_FAST", clean))
            if idx + 1 < len(slip_parts):
                events.append(("PAUSE", 0.14))
        else:
            events.append((default_gear, clean))
    return events


def expand_turn_events(spk: str, val) -> list:
    if spk == "PAUSE":
        return [("PAUSE", float(val))]
    txt = str(val).strip()
    if spk not in ("W", "D", "X", "M", "F"):
        return [(spk, txt)]

    turn_gear = pick_turn_gear(spk, txt)
    ja_full_spk = f"{spk}_JA"
    ja_inline_spk = f"{spk}_JA_INLINE"

    if not JA_SPAN_RE.search(txt):
        evs = split_mandarin_natural(spk, txt, turn_gear)
        return evs if evs else [(turn_gear, txt)]

    parts = JA_SPAN_RE.split(txt)
    out: list[tuple[str, object]] = []
    pending_pause = 0.0

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
                # Inline Japanese word inside Mandarin flow: NO forced period "。", tight 20ms join!
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
            zh_evs = split_mandarin_natural(spk, pt_s, turn_gear)
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


def turn_switch_pause(next_spk: str, next_txt: str) -> float:
    s = str(next_txt).strip()
    if LATCH_START_RE.search(s):
        return 0.14
    if REFLECT_TURN_RE.search(s):
        return 0.34
    if next_spk == "W":
        return 0.21
    if next_spk == "D":
        return 0.28
    return 0.24


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
        # Short <=2-char Chinese words need a period so multilingual G2P never drops them; inline Kana stays bare on pass 0
        if not spk.endswith("_JA_INLINE") and len(speak_txt) <= 2 and speak_txt and speak_txt[-1] not in "。！？":
            speak_txt = speak_txt + "。"
        punct_stripped = speak_txt.rstrip("，、：:； ")
        with_period = (punct_stripped + "。") if (punct_stripped and punct_stripped[-1] not in "。！？") else speak_txt
        no_quotes = re.sub(r'[“”‘’「」『』"]', "", punct_stripped).strip()
        no_quotes_period = (no_quotes + "。") if (no_quotes and no_quotes[-1] not in "。！？") else with_period
        base_spk = spk.split("_")[0]
        alt_voice = (
            "en-AU-WilliamMultilingualNeural"
            if base_spk in ("X", "F")
            else ("ko-KR-HyunsuMultilingualNeural" if base_spk in ("W", "M") else "en-US-BrianMultilingualNeural")
        )
        for attempt in range(MAX_TRIES):
            if attempt == 0:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, pitch, speak_txt
            elif attempt == 1:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, pitch, with_period
            elif attempt == 2:
                use_voice, use_rate, use_pitch, use_txt = voice, rate, "+0Hz", no_quotes_period
            elif attempt == 3:
                use_voice, use_rate, use_pitch, use_txt = voice, "+0%", "+0Hz", no_quotes_period
            else:
                use_voice, use_rate, use_pitch, use_txt = alt_voice, rate, "+0Hz", no_quotes_period
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


def decode_to_pcm_f32(audio_path: str, trim_speech: bool = True) -> np.ndarray:
    """
    Decodes an audio file directly to 24kHz mono float32 [-1.0, 1.0] PCM.
    For speech clips, gently trims leading/trailing dead air (-54dB) while keeping natural
    breath tails and applying a smooth 14ms raised-cosine anti-click envelope.
    """
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
        if spk == "PAUSE":
            raw_evs.append(("PAUSE", float(val)))
        else:
            raw_evs.append((spk, str(val)))
            if idx + 1 < len(turns) and turns[idx + 1][0] != "PAUSE":
                next_spk, next_val = turns[idx + 1]
                raw_evs.append(("PAUSE", turn_switch_pause(next_spk, str(next_val))))
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
    study_dt = (now_pt - datetime.timedelta(hours=5)).date()
    today_str = study_dt.strftime("%Y-%m-%d")
    days_left = max(0, (EXAM_DATE - study_dt).days)
    day_ord = study_dt.toordinal()

    _rp = tutor_prefs.radio_prefs()
    _focus = tutor_prefs.focus_set()
    imm_profile = tutor_prefs.immersion_profile(day=today_str)

    voice_map = await detect_voice_map(ja_sentence_rate=imm_profile["ja_sentence_rate"]) if not dry_test else {
        f"{s}{g}": (s, "+5%", "+0Hz")
        for s in ("W", "D", "X", "M", "F")
        for g in ("", "_MID", "_FAST", "_LOW", "_JA_INLINE", "_JA")
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

    recent_wrong, hot_wrong = load_recent_mistakes()
    scores = load_mastery_priority(state, recent_wrong, hot_wrong)
    prev_1, prev_2, prev_3 = load_previous_day_stories(today_str)
    rng = random.Random(today_str)

    def story_rank(st: dict) -> float:
        pids = st.get("point_ids") or []
        pkeys = [resolve_point_key(pid) for pid in pids]
        pt_vals = sorted((scores.get(pid, 2.2) for pid in pids), reverse=True)
        top_avg = sum(pt_vals[:3]) / max(1, len(pt_vals[:3])) if pt_vals else 2.2
        repeat_penalty = (
            4.5 if st["id"] in prev_1
            else (2.5 if st["id"] in prev_2 else (1.2 if st["id"] in prev_3 else 0.0))
        )
        memory_bonus = 0.0
        if st["id"] in _rp["avoid_story_ids"]:
            memory_bonus -= 9.0
        tier = st.get("tier", "")
        if tier == "live_news":
            memory_bonus += 5.2
        elif tier == "uchi_intellectual":
            memory_bonus += 3.2
        if _focus and any((pid in _focus or pk in _focus) for pid, pk in zip(pids, pkeys)):
            memory_bonus += 0.8
        blob = f'{st.get("title", "")} {" ".join(st.get("tags", []) or [])}'
        if any(tag and tag in blob for tag in _rp["prefer_tags"]):
            memory_bonus += 0.3
        jitter = rng.uniform(-0.12, 0.12)
        return -(top_avg - repeat_penalty + memory_bonus + jitter)

    # Optionally script a fresh daily NHK news Act-1 roundtable calibrated to today's 365-day ja_ratio
    top_focus_labels = [resolve_point_key(pid) for pid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:6]]
    uchi_companion_titles = [st["title"] for st in SALON_STORIES[:5]]
    live_news_story = maybe_generate_live_news_story(
        today_str=today_str,
        imm_profile=imm_profile,
        focus_points=top_focus_labels,
        companion_titles=uchi_companion_titles,
        dry_test=dry_test,
    )
    candidate_pool = ([live_news_story] if live_news_story else []) + list(SALON_STORIES)

    min_ep_min, max_ep_min = _rp["episode_minutes"]
    target_sec = ((min_ep_min + max_ep_min) / 2.0) * 60.0
    max_sec = (max_ep_min + 1.0) * 60.0
    est_sec = 72.0  # Opening theme + greeting + 2 ad bumpers + closing & outro
    picked_ids: set[str] = set()
    for st in sorted(candidate_pool, key=story_rank):
        s_dur = estimate_story_seconds(st)
        if len(picked_ids) >= 8 and (est_sec + s_dur > max_sec or est_sec >= target_sec):
            break
        picked_ids.add(st["id"])
        est_sec += s_dur
        if len(picked_ids) >= 12:
            break
    # Preserve candidate_pool narrative order so cross-chapter callbacks ("前后照应") stay sequential!
    selected_stories = [st for st in candidate_pool if st["id"] in picked_ids]

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
        opening_turns = OPENING_GREETINGS_POOL[day_ord % len(OPENING_GREETINGS_POOL)]
        ad1_out_turns, ad1_in_turns = AD_BREAK_1_POOL[day_ord % len(AD_BREAK_1_POOL)]
        ad2_out_turns, ad2_in_turns = AD_BREAK_2_POOL[(day_ord + 1) % len(AD_BREAK_2_POOL)]
        closing_turns = CLOSING_POOL[day_ord % len(CLOSING_POOL)]

    opening_evs = turns_to_expanded_events(opening_turns)
    ad1_out_evs = turns_to_expanded_events(ad1_out_turns)
    ad1_in_evs = turns_to_expanded_events(ad1_in_turns)
    ad2_out_evs = turns_to_expanded_events(ad2_out_turns)
    ad2_in_evs = turns_to_expanded_events(ad2_in_turns)
    closing_evs = turns_to_expanded_events(closing_turns)

    story_blocks = []
    for ch_idx, st in enumerate(selected_stories):
        pids = list(st.get("point_ids") or [])
        story_blocks.append({
            "chapter": ch_idx,
            "short_tab": st["short_tab"],
            "point_id": pids[0] if pids else "",
            "point_ids": pids,
            "title": st["title"],
            "ja_focus": st["ja_focus"],
            "events": turns_to_expanded_events(list(st["turns"])),
        })

    sig_obj = {
        "ver": "v29_qq3_uchi_40m_365",
        "engine": engine_tag,
        "imm_day": imm_profile["day_of_365"],
        "opening": opening_evs,
        "ad1": [ad1_out_evs, ad1_in_evs],
        "ad2": [ad2_out_evs, ad2_in_evs],
        "closing": closing_evs,
        "stories": story_blocks,
    }
    script_sig = hashlib.sha256(json.dumps(sig_obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:14]

    if not dry_test and os.path.exists(RADIO_MP3_PATH) and os.path.exists(RADIO_META_PATH):
        try:
            old_meta = json.load(open(RADIO_META_PATH, encoding="utf-8"))
            if old_meta.get("date") == today_str and old_meta.get("script_sig") == script_sig and os.path.getsize(RADIO_MP3_PATH) > 1_000_000:
                save_today_stories(today_str, [st["id"] for st in selected_stories])
                print(f"Daily Qiang-Qiang trio radio already up-to-date for {today_str} ({old_meta.get('duration_label')}).")
                return
        except Exception:
            pass

    all_event_lists = [
        opening_evs,
        ad1_out_evs, ad1_in_evs,
        ad2_out_evs, ad2_in_evs,
        closing_evs,
        *(b["events"] for b in story_blocks),
    ]

    tmpdir = tempfile.mkdtemp(prefix="n3_radio_v28_")
    try:
        unique_turns: dict[tuple[str, str], str] = {}
        for ev_list in all_event_lists:
            for k, val in ev_list:
                if k != "PAUSE":
                    key = (k, str(val))
                    if key not in unique_turns:
                        thash = hashlib.sha256(f"{k}:{val}".encode("utf-8")).hexdigest()[:12]
                        unique_turns[key] = os.path.join(tmpdir, f"raw_{thash}.mp3")

        if dry_test:
            print(f"[dry-test] Stories={[b['short_tab'] for b in story_blocks]}, unique_clips={len(unique_turns)}, script_sig={script_sig}")
            # Create synthetic short speech tone clips to test full PCM timeline & ducking assembly
            clip_pcm: dict[tuple[str, str], np.ndarray] = {}
            for key in unique_turns:
                dur_s = min(3.5, max(0.35, len(key[1]) * 0.08))
                t = np.arange(int(SR * dur_s), dtype=np.float32) / SR
                clip_pcm[key] = (0.12 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
        else:
            sem = asyncio.Semaphore(16)
            ok_results = await asyncio.gather(
                *(synth_turn(k, voice_map[k], txt, raw_p, sem) for (k, txt), raw_p in unique_turns.items())
            )
            ok_count = sum(1 for x in ok_results if x)
            print(f"Synthesized {ok_count} / {len(unique_turns)} unique Qiang-Qiang v29 full-breath clips.")
            min_required = max(1, int(len(unique_turns) * 0.98))
            if ok_count < min_required:
                raise RuntimeError(
                    f"TTS clip synthesis below safety threshold ({ok_count}/{len(unique_turns)} < {min_required}); refusing to overwrite daily_radio.mp3"
                )

            clip_pcm = {}

            def _decode_item(item):
                key, raw_p = item
                if os.path.exists(raw_p) and os.path.getsize(raw_p) > 0:
                    return key, decode_to_pcm_f32(raw_p, trim_speech=True)
                return key, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                for key, arr in pool.map(_decode_item, unique_turns.items()):
                    if arr is not None and len(arr) > 0:
                        clip_pcm[key] = arr

        # Load mastered 《锵锵三人行》 music suite into 24kHz float32 PCM
        pcm_intro = decode_to_pcm_f32(music_paths["intro"], trim_speech=False)
        pcm_bumper = decode_to_pcm_f32(music_paths["bumper"], trim_speech=False)
        pcm_sting = decode_to_pcm_f32(music_paths["sting"], trim_speech=False)
        pcm_outro = decode_to_pcm_f32(music_paths["outro"], trim_speech=False)

        mixer = StudioTimelineMixer(est_minutes=52.0)

        def _append_events(ev_list: list[tuple[str, object]]) -> None:
            for idx, (k, val) in enumerate(ev_list):
                if k == "PAUSE":
                    sec = float(val)
                    mixer.advance(sec)
                else:
                    key = (k, str(val))
                    arr = clip_pcm.get(key)
                    if arr is not None:
                        # Smooth 8ms micro-overlap when pause was tight inline join (<=0.025s)
                        mixer.append_clip(arr, gain=1.0)

        # 1) 00:00.0 — Opening Theme (`qq_intro`) + Ducked Entry for Trio Greeting!
        intro_env = make_intro_duck_envelope(len(pcm_intro), duck_start_sec=6.75)
        mixer.place_at(0.0, pcm_intro, gain=intro_env)
        mixer.advance(6.85)  # Wen Tao enters right over the ringing final "锵！锵！" tail!

        chapter_starts: dict[int, float] = {0: 0.0}
        raw_seg_bounds: list[tuple[int, float, float]] = []

        # Trio Opening Greeting leads straight into Story 0
        _append_events(opening_evs)
        mixer.advance(0.45)

        total_stories = len(story_blocks)
        act1_cnt = max(2, (total_stories + 2) // 3)
        act2_cnt = max(2, (total_stories - act1_cnt + 1) // 2)
        ad1_after = act1_cnt - 1
        ad2_after = min(total_stories - 2, act1_cnt + act2_cnt - 1)
        for ch_idx, b in enumerate(story_blocks):
            seg_start = 0.0 if ch_idx == 0 else round(mixer.sec, 1)
            if ch_idx not in chapter_starts:
                chapter_starts[ch_idx] = seg_start

            # If returning from an ad break, Wen Tao welcomes listeners back right at the chapter mark!
            if ch_idx == ad1_after + 1:
                _append_events(ad1_in_evs)
                mixer.advance(0.42)
            elif ch_idx == ad2_after + 1:
                _append_events(ad2_in_evs)
                mixer.advance(0.42)

            # Main Salon Story Dialogue
            _append_events(b["events"])

            # End-of-Story Transitions:
            if ch_idx == ad1_after:
                # End of Act 1 -> Classic Ad Break 1 ("《锵锵三人行》，广告之后见！" + Bumper Music)
                mixer.advance(0.50)
                _append_events(ad1_out_evs)
                bumper_start = max(0.0, mixer.sec - 0.18)
                bumper_end = mixer.place_at(bumper_start, pcm_bumper, gain=0.96)
                mixer.cursor = int(round((bumper_end - 0.28) * SR))
            elif ch_idx == ad2_after:
                # End of Act 2 -> Classic Ad Break 2 ("《锵锵三人行》，广告之后见！" + Bumper Music)
                mixer.advance(0.50)
                _append_events(ad2_out_evs)
                bumper_start = max(0.0, mixer.sec - 0.18)
                bumper_end = mixer.place_at(bumper_start, pcm_bumper, gain=0.96)
                mixer.cursor = int(round((bumper_end - 0.28) * SR))
            elif ch_idx < total_stories - 1:
                # Non-ad story transition -> Subtle 1.9s Jazz/Marimba/Gong-shimmer Salon Sting
                mixer.advance(0.48)
                sting_end = mixer.place_at(mixer.sec, pcm_sting, gain=0.92)
                mixer.cursor = int(round((sting_end + 0.22) * SR))
            else:
                # Final Story -> Trio Closing Sign-Off + Warm 《锵锵三人行》 Outro Music!
                mixer.advance(0.70)
                # Append D and X closing lines first, then measure W's final sign-off so outro sneaks underneath!
                if len(closing_turns) >= 2:
                    pre_close_evs = turns_to_expanded_events(closing_turns[:-1])
                    final_w_evs = turns_to_expanded_events([closing_turns[-1]])
                    _append_events(pre_close_evs)
                    mixer.advance(0.24)
                    w_start_sec = mixer.sec
                    _append_events(final_w_evs)
                    w_end_sec = mixer.sec
                    w_dur = max(0.8, w_end_sec - w_start_sec)
                    # Start outro underscore ~2.1s before Wen Tao finishes "《锵锵三人行》，咱们明天见！"
                    vo_overlap = min(2.2, w_dur * 0.65)
                    outro_start = max(w_start_sec, w_end_sec - vo_overlap)
                    outro_env = make_outro_swell_envelope(len(pcm_outro), voice_over_sec=(w_end_sec - outro_start))
                    outro_end = mixer.place_at(outro_start, pcm_outro, gain=outro_env)
                    mixer.cursor = int(round(outro_end * SR))
                else:
                    _append_events(closing_evs)
                    outro_end = mixer.place_at(mixer.sec, pcm_outro, gain=1.0)
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
        print(f"Built Qiang-Qiang v29 Uchi Episode: {final_dur:.1f}s ({mins} mins), stories={[s['short_tab'] for s in selected_stories]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
