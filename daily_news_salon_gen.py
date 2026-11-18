#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Japanese & World News Ingestion + 700-Day (`1/700`) Dynamic 《锵锵三人行》 Roundtable Generator.

1) Fetches live daily headlines & summaries from official NHK News Web RSS feeds:
   - 主要 (cat0), 政治 (cat6), 経済 (cat5), 科学・文化 (cat2), 国際 (cat3)
2) When an inference token is available in CI (`GITHUB_MODELS_TOKEN` via GitHub Models,
   `GEMINI_API_KEY`, or `OPENAI_API_KEY`), scripts a fresh Act-1 《锵锵三人行》 current-affairs
   roundtable (`文涛 · 文道 · 子东`) calibrated to today's exact `immersion_profile(day)`:
   - Pre-N3 (<= 2026-12-06): ~10% Japanese (pure Kana in speech spans for 100% clean TTS),
     weaving today's real news with top N3 weak points and foreshadowing later chapters ("前后照应").
   - Post-N3 (2026-12-07 .. Post-N3 Day 700): gently escalates Japanese ratio by `1/700` per day
     (10% -> ~35% at N2 -> ~53% at N1 -> 92% at Day 700) until the show organically becomes a near-all-Japanese podcast!
3) Enforces a strict phonetic & style gate (zero Kanji-Kana collisions, zero fake laughs,
   zero date/countdown pressure). Gracefully returns None if offline or unavailable.
"""
from __future__ import annotations
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
CORPUS_KB_PATH = os.path.join(BASE_DIR, "qq_corpus_knowledge.json")
NIGHT_SUMMARY_PATH = os.path.join(BASE_DIR, "night_summary.json")

NHK_FEEDS = [
    ("主要", "https://www.nhk.or.jp/rss/news/cat0.xml"),
    ("政治", "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("経済", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("科学文化", "https://www.nhk.or.jp/rss/news/cat2.xml"),
    ("国際", "https://www.nhk.or.jp/rss/news/cat3.xml"),
]


def load_qq_corpus_exemplars(day_seed: str, count: int = 2) -> list[dict]:
    if not os.path.exists(CORPUS_KB_PATH):
        return []
    try:
        kb = json.load(open(CORPUS_KB_PATH, encoding="utf-8"))
        exs = kb.get("few_shot_trio_exchanges") or []
        if not exs:
            return []
        offset = sum(ord(c) for c in str(day_seed)) % len(exs)
        return [exs[(offset + i) % len(exs)] for i in range(min(count, len(exs)))]
    except Exception:
        return []


def load_last_night_signals() -> dict:
    if not os.path.exists(NIGHT_SUMMARY_PATH):
        return {}
    try:
        return json.load(open(NIGHT_SUMMARY_PATH, encoding="utf-8"))
    except Exception:
        return {}


def fetch_live_nhk_news(max_items: int = 8, timeout: float = 8.0) -> list[dict]:
    items: list[dict] = []
    seen_titles: set[str] = set()
    for cat, url in NHK_FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 N3SalonBot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            count_cat = 0
            for it in root.findall(".//item"):
                title = (it.findtext("title") or "").strip()
                desc = (it.findtext("description") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                items.append({"category": cat, "title": title, "summary": desc[:180]})
                count_cat += 1
                if count_cat >= 2 or len(items) >= max_items:
                    break
        except Exception:
            continue
        if len(items) >= max_items:
            break
    return items


def validate_generated_story(st: dict) -> bool:
    if not isinstance(st, dict):
        return False
    turns = st.get("turns")
    if not isinstance(turns, list) or not (7 <= len(turns) <= 26):
        return False
    for entry in turns:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return False
        spk, txt = str(entry[0]).strip(), str(entry[1]).strip()
        if spk not in ("W", "D", "X") or len(txt) < 2:
            return False
        # Zero fake laughs, zero exam countdowns, zero ASCII/digits in speech spans
        if re.search(r"哈哈|噗|倒计时|还有\d+天考试|[A-Za-z0-9]", txt):
            return False
        # Zero Kanji immediately glued to Kana (guarantees clean multilingual G2P)
        if re.search(r"[\u4e00-\u9fff][\u3040-\u30ff]+|[\u3040-\u30ff]+[\u4e00-\u9fff]", txt):
            return False
        # Zero single-character Mandarin orphans between Japanese spans
        parts = re.split(r"([\u3040-\u30ffー・]+(?:[、。！？\s]+[\u3040-\u30ffー・]+)*[。！？]?)", txt)
        for p_i, pt in enumerate(parts):
            if p_i % 2 == 0:
                zh_core = re.sub(r"[^\u4e00-\u9fff]", "", pt)
                if 0 < len(zh_core) <= 1:
                    return False
    return True


def _call_chat_llm(system_prompt: str, user_prompt: str) -> str | None:
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    gh_models_token = (os.environ.get("GITHUB_MODELS_TOKEN") or "").strip()

    if openai_key:
        url = "https://api.openai.com/v1/chat/completions"
        for model in ("gpt-4o", "gpt-4o-mini"):
            payload = json.dumps({
                "model": model,
                "temperature": 0.65,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }).encode("utf-8")
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=38.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                if content and content.strip():
                    return content
            except Exception as e:
                print(f"[info] live news LLM endpoint ({model}) skipped: {e}")

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.65},
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=38.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[info] Gemini live news generation skipped: {e}")

    if gh_models_token:
        endpoints = [
            ("https://models.github.ai/inference/chat/completions", ("openai/gpt-4.1", "openai/gpt-4o", "openai/gpt-4o-mini")),
        ]
        for url, models in endpoints:
            for model in models:
                payload = json.dumps({
                    "model": model,
                    "temperature": 0.62,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }).encode("utf-8")
                try:
                    req = urllib.request.Request(
                        url,
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {gh_models_token}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "X-GitHub-Api-Version": "2022-11-28",
                            "User-Agent": "n3-audio-tutor-cloud/1.0",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=42.0) as resp:
                        raw_body = resp.read().decode("utf-8", errors="replace").strip()
                    if not raw_body:
                        continue
                    data = json.loads(raw_body)
                    content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                    if content and content.strip():
                        return content
                except Exception as e:
                    print(f"[info] GitHub Models endpoint ({model}) skipped: {e}")
    return None


def load_cloud_qq_style_exemplars(seed_key: str = "") -> dict:
    """Load real 3,124-episode《锵锵三人行》trio style stats & rotating openings directly in the cloud."""
    corpus_path = os.path.join(BASE_DIR, "qiangqiang_trio_corpus.json")
    if not os.path.exists(corpus_path):
        return {}
    try:
        data = json.load(open(corpus_path, encoding="utf-8"))
        samples = data.get("sample_authentic_trio_openings") or []
        picked = []
        if samples:
            offset = sum(ord(c) for c in str(seed_key)) % len(samples)
            picked = [samples[(offset + i) % len(samples)] for i in range(min(3, len(samples)))]
        return {
            "wentao_opening_stats": data.get("wentao_opening_stats") or {},
            "speaker_turn_char_length": data.get("speaker_turn_char_length") or {},
            "signature_phrases": data.get("signature_phrases") or {},
            "authentic_trio_opening_exemplars": picked,
        }
    except Exception:
        return {}


def maybe_generate_live_news_story(
    today_str: str,
    imm_profile: dict,
    focus_points: list[str],
    companion_titles: list[str],
    dry_test: bool = False,
) -> dict | None:
    if dry_test:
        return None
    cache_path = os.path.join(AUDIO_DIR, f"live_news_{today_str}.json")
    if os.path.exists(cache_path):
        try:
            cached = json.load(open(cache_path, encoding="utf-8"))
            if validate_generated_story(cached):
                return cached
        except Exception:
            pass

    headlines = fetch_live_nhk_news(max_items=6)
    if not headlines:
        return None

    ja_pct = int(round(float(imm_profile.get("ja_ratio", 0.10)) * 100))
    phase = imm_profile.get("phase", "n3_sprint")
    ramp_days = int(imm_profile.get("ramp_days", 700))
    day_num = imm_profile.get("day_of_365", 1)

    night_sig = load_last_night_signals()
    night_missed = (night_sig.get("missed_or_unsure_points") or [])[:5]
    night_vocab = (night_sig.get("missed_vocab_words") or [])[:4]
    night_lookups = (night_sig.get("looked_up_expressions") or [
        x.get("surface") for x in (night_sig.get("top_looked_up_words") or [])[:4] if isinstance(x, dict) and x.get("surface")
    ])[:4]
    combined_targets = []
    for x in night_missed + night_vocab + night_lookups + list(focus_points):
        if x and x not in combined_targets:
            combined_targets.append(x)

    exemplars = load_qq_corpus_exemplars(today_str, count=2)

    sys_prompt = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿（已吃透全部 3,182 期完整实录与 421 期原声轻重缓急规律）。\n"
        "三位老友：窦文涛(W，北方清亮活泛、俗人切口、爱重复接对方最后四五个字搭茬、高频用『我跟你说』『不是』『你看』)、"
        "梁文道(D，温厚男中音、先短句『对』『没错』接话再慢起长句铺陈东亚历史与制度脉络，爱用『你想想看』『换句话说』『吊诡』)、"
        "许子东(X，清瘦冷峻学者、短刀直入『不不不』『我的问题是』『你的意思是说』一针见血拆台)。\n"
        "请根据今日真实日本与世界新闻，并优先揉入听众昨晚刚卡壳的日语薄弱点，创作一段约 4.5 分钟（13到18轮 W/D/X 对白）的开篇时局圆桌。\n"
        "核心铁律：\n"
        "0. 【去排排坐朗读感·真实轻重缓急句法】：严禁机械按 W->D->X->W->D->X 轮流念百字长文！必须有 D 与 X 直接交锋过招，穿插 4 到 15 字的短促抢白、反问或冷幽默拆台，长发言内部写出『快切入 -> 铺事实 -> 沉吟转折 -> 重落点』的呼吸层次。\n"
        "1. 【原版文涛冷开场】：第一轮 W 直接以『《锵锵三人行》，』连着今日最抓人的具体新闻或包袱单刀直入（把『文道』『子东/许老师』顺嘴嵌进句子里），严禁『大家好、文道好、子东好』等模板客套。\n"
        f"2. 当前处于 {ramp_days} 天（1/{ramp_days} 慢速养耳）双语演进计划第 {day_num} 天（阶段：{phase}），日语占比约 {ja_pct}%。\n"
        "3. 对熟知人物与头衔（如教授 きょうじゅ、部长 ぶちょう、课长 かちょう、社长 しゃちょう、医局 いきょく、先生 せんせい、财前五郎 ざいぜんごろう、东教授 あずまきょうじゅ）直接用日文或首提中文后全程日文。\n"
        "4. 【语音合成硬铁律】：对白文本中凡出现日文词句，必须 100% 写成纯平假名或纯片假名（前后留空格或中文标点），严禁汉字紧贴假名，严禁任何英文字母或阿拉伯数字（数字全写中文），严禁『哈哈』『噗』、日期倒计时或语法术语。\n"
        "5. 自然融入 2 到 4 个昨晚薄弱日语表达，结尾顺嘴拐弯引出后续专题。\n"
        "输出严格为 JSON：{\"short_tab\": \"今日时局\", \"title\": \"...\", \"ja_focus\": \"...(此处可正常写日文汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"X\", \"...\"], [\"D\", \"...\"], ...]}"
    )
    usr_prompt = json.dumps({
        "nhk_live_headlines": headlines,
        "last_night_priority_targets": combined_targets[:6],
        "later_chapters_for_callbacks": companion_titles[:4],
        "authentic_qqsrx_style_reference": load_cloud_qq_style_exemplars(today_str),
        "authentic_qiangqiang_cadence_examples": exemplars,
    }, ensure_ascii=False, indent=2)

    raw = _call_chat_llm(sys_prompt, usr_prompt)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        story = {
            "id": f"live_nhk_news_{today_str}",
            "tier": "live_news",
            "short_tab": str(parsed.get("short_tab") or "今日时局")[:6],
            "tags": ["日本时局新闻", "ウチ内幕", "前后照应"],
            "title": str(parsed.get("title") or "今日日本时局观察"),
            "point_ids": ["N3-G13", "N3-G23"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": [(str(s).strip(), str(t).strip()) for s, t in (parsed.get("turns") or [])],
        }
        if validate_generated_story(story):
            os.makedirs(AUDIO_DIR, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(story, f, ensure_ascii=False, indent=2)
            print(f"[live-news] Generated validated NHK current-affairs roundtable: {story['title']}")
            return story
        print("[info] Generated live news story did not pass strict phonetic gate; using curated Uchi bank.")
    except Exception as e:
        print(f"[info] Failed to parse live news JSON: {e}")
    return None
