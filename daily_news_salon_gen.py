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

NHK_FEEDS = [
    ("主要", "https://www.nhk.or.jp/rss/news/cat0.xml"),
    ("政治", "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("経済", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("科学文化", "https://www.nhk.or.jp/rss/news/cat2.xml"),
    ("国際", "https://www.nhk.or.jp/rss/news/cat3.xml"),
]


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
    if not isinstance(turns, list) or not (7 <= len(turns) <= 22):
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
            ("https://models.github.ai/inference/chat/completions", ("openai/gpt-4.1", "openai/gpt-4o")),
            ("https://models.inference.ai.azure.com/chat/completions", ("gpt-4o", "gpt-4o-mini")),
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
                            "Accept": "application/vnd.github+json",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=42.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                    if content and content.strip():
                        return content
                except Exception as e:
                    print(f"[info] GitHub Models endpoint ({model}) skipped: {e}")
    return None


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

    sys_prompt = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿（已吃透 3,124 期真实文字实录与音频节奏）。主持人是窦文涛(W，俗人切口、插科打诨、高频使用『我跟你说』『不是』『你看』)、"
        "梁文道(D，温厚博学、短促应答『对』『没错』与东亚思想史长句交替)、许子东(X，冷峻幽默、爱用『不不不』『你的意思是说』一针见血拆台)。\n"
        "请根据今日真实日本与世界新闻，创作一段约 4.5 分钟（11到16轮 W/D/X 对白，长短句交错，必须穿插真实《锵锵》短接茬）的开篇时局圆桌。\n"
        "铁律：\n"
        "0. 【原版文涛开场铁律】：第一轮 W 必须直接以『《锵锵三人行》，』连着今日最抓人的具体新闻或包袱单刀直入（把『文道』『子东/许老师』顺嘴嵌进句子里），"
        "严禁写『大家好、文道好、子东好、热茶沏满了』等任何模板化客套点名（真实 1,290 期实录中 98.3% 零客套直接进事儿）。\n"
        f"1. 当前处于 {ramp_days} 天（1/{ramp_days} 慢速养耳）双语演进计划第 {day_num} 天（阶段：{phase}），"
        f"本段日语占比严格控制在约 {ja_pct}%（其余用自然地道的中文把思想与世情讲透，绝不拔苗助长）。\n"
        "2. 视角必须是日本社会内部（ウチ）与知识分子视角；对听众熟知的人物与头衔（如教授 きょうじゅ、部长 ぶちょう、课长 かちょう、社长 しゃちょう、医局 いきょく、先生 せんせい、财前五郎 ざいぜんごろう、东教授 あずまきょうじゅ）直接用日文或首提中文后全程日文。\n"
        "3. 【极其重要·语音合成铁律】：对白文本中凡出现日文词或日文句子，必须100%写成纯平假名或纯片假名（前后留空格或中文标点），"
        "严禁在日文发音串里夹杂任何汉字或英文字母（汉字概念先在中文里说清，念日文时全用假名，例如：到手工资，念 てどり）。\n"
        "4. 严禁出现『哈哈』『噗』等字面笑声，严禁报几月几号或考试倒计时，严禁出现语法术语（如ます形/て形）。\n"
        "5. 自然融入2到3个目标日语表达，并在结尾顺嘴拐弯衔接后续专题（参考伴随标题），零总结腔。\n"
        "输出严格为 JSON 对象：{\"short_tab\": \"今日时局\", \"title\": \"...\", \"ja_focus\": \"...(此处可正常日文汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"D\", \"...\"], [\"X\", \"...\"], ...]}"
    )
    usr_prompt = json.dumps({
        "nhk_live_headlines": headlines,
        "target_japanese_points": focus_points[:5],
        "later_chapters_for_callbacks": companion_titles[:4],
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
