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
    ("政治", "https://www.nhk.or.jp/rss/news/cat4.xml"),
    ("経済", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("科学文化", "https://www.nhk.or.jp/rss/news/cat3.xml"),
    ("国際", "https://www.nhk.or.jp/rss/news/cat6.xml"),
]

WORLD_FROM_JAPAN_FEEDS = [
    ("国際", "https://www.nhk.or.jp/rss/news/cat6.xml"),
    ("科学", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ja&gl=JP&ceid=JP:ja"),
    ("世界", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=ja&gl=JP&ceid=JP:ja"),
    ("科技", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ja&gl=JP&ceid=JP:ja"),
    ("医学健康", "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ja&gl=JP&ceid=JP:ja"),
    ("全球财经", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ja&gl=JP&ceid=JP:ja"),
    ("科学文化", "https://www.nhk.or.jp/rss/news/cat3.xml"),
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
    if len(items) < 3:
        # Fallback to Google News Japan RSS if NHK RSS is throttled or unreachable
        try:
            g_url = "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja"
            req = urllib.request.Request(g_url, headers={"User-Agent": "Mozilla/5.0 N3SalonBot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            for it in root.findall(".//item"):
                title = (it.findtext("title") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                items.append({"category": "日本総合", "title": title, "summary": title[:180]})
                if len(items) >= max_items:
                    break
        except Exception:
            pass
    return items


def fetch_live_world_from_japan_news(max_items: int = 10, timeout: float = 8.0) -> list[dict]:
    """Fetches non-Japan world, science, tech, medicine & global economy headlines as reported by Japanese media."""
    items: list[dict] = []
    seen_titles: set[str] = set()
    for cat, url in WORLD_FROM_JAPAN_FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 N3SalonBot/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            count_cat = 0
            for it in root.findall(".//item"):
                title = (it.findtext("title") or "").strip()
                desc = (it.findtext("description") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", desc)
                desc = re.sub(r"\s+", " ", desc).strip()
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


BANNED_CLASSROOM_RE = re.compile(
    r"第[一二三四]个语法|下面我们学习|请大家跟读|本课重点|今天我们来学习"
)
LIGHT_EXPLAIN_CUE_RE = re.compile(
    r"日语|日文|念|读作|缩成|缩音|省成|别跟|弄混|口语里|说法|尊敬语|谦让语"
)


def _strip_json_fence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1].strip()
    return s


_DIGIT_ZH = str.maketrans("0123456789", "零一二三四五六七八九")


def _sanitize_generated_turns(turns: list) -> list[tuple[str, str]]:
    """Lightly normalize harmless LLM formatting slips (em-dashes, digits, Katakana spacing) without masking Kanji+Hiragana errors."""
    cleaned: list[tuple[str, str]] = []
    for entry in turns or []:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        spk = str(entry[0]).strip()
        txt = str(entry[1]).strip()
        txt = txt.replace("——", "，").replace("—", "，")
        txt = re.sub(r"哈哈+", "哎呀", txt)
        txt = re.sub(r"(\d+)%", lambda m: "百分之" + m.group(1).translate(_DIGIT_ZH), txt)
        txt = re.sub(r"\d+", lambda m: m.group(0).translate(_DIGIT_ZH), txt)
        txt = re.sub(r"([\u4e00-\u9fff])([\u30a0-\u30ff])", r"\1 \2", txt)
        txt = re.sub(r"([\u30a0-\u30ff])([\u4e00-\u9fff])", r"\1 \2", txt)
        txt = re.sub(r"\s{2,}", " ", txt).strip()
        cleaned.append((spk, txt))
    return cleaned


def validate_generated_story(st: dict, require_light_explain: bool = True, min_chars: int = 0) -> bool:
    if not isinstance(st, dict):
        return False
    turns = st.get("turns")
    if not isinstance(turns, list) or not (12 <= len(turns) <= 115):
        return False
    if min_chars > 0:
        tot_chars = sum(len(str(e[1])) for e in turns if isinstance(e, (list, tuple)) and len(e) == 2)
        if tot_chars < min_chars:
            return False
    explain_hits = 0
    for entry in turns:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            return False
        spk, txt = str(entry[0]).strip(), str(entry[1]).strip()
        if spk not in ("W", "D", "X") or len(txt) < 2:
            return False
        if re.search(r"哈哈|噗|倒计时|还有\d+天考试|[A-Za-z0-9—]", txt):
            return False
        if BANNED_CLASSROOM_RE.search(txt):
            return False
        if LIGHT_EXPLAIN_CUE_RE.search(txt):
            explain_hits += 1
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
    if require_light_explain and explain_hits < 2:
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
                    raw_body = resp.read().decode("utf-8", errors="replace").strip()
                if not raw_body:
                    continue
                data = json.loads(raw_body)
                content = _strip_json_fence((data.get("choices") or [{}])[0].get("message", {}).get("content") or "")
                if content:
                    json.loads(content)
                    return content
            except Exception as e:
                print(f"[info] live news LLM endpoint ({model}) skipped: {e}")

    if gemini_key:
        for g_model in ("gemini-2.5-pro", "gemini-2.5-flash"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.65},
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=38.0) as resp:
                    raw_body = resp.read().decode("utf-8", errors="replace").strip()
                if not raw_body:
                    continue
                data = json.loads(raw_body)
                content = _strip_json_fence(data["candidates"][0]["content"]["parts"][0]["text"])
                if content:
                    json.loads(content)
                    return content
            except Exception as e:
                print(f"[info] Gemini live news generation ({g_model}) skipped: {e}")

    # Note: GitHub Models inference API (models.github.ai) was permanently retired on 2026-07-30
    # and now returns HTTP 200 text/plain "OK". Only invoke configured live LLM keys above.
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
            if validate_generated_story(cached, require_light_explain=(imm_profile.get("ja_ratio", 0.14) < 0.45), min_chars=2200):
                return cached
        except Exception:
            pass

    headlines = fetch_live_nhk_news(max_items=6)
    if not headlines:
        return None

    ja_pct = int(round(float(imm_profile.get("ja_ratio", 0.14)) * 100))
    phase = imm_profile.get("phase", "n3_sprint")
    ramp_days = int(imm_profile.get("ramp_days", 700))
    day_num = imm_profile.get("day_of_365", 1)

    night_sig = load_last_night_signals()
    night_missed = (night_sig.get("missed_or_unsure_points") or [])[:4]
    night_vocab = (night_sig.get("missed_vocab_words") or [])[:3]
    night_lookups = (night_sig.get("looked_up_expressions") or [
        x.get("surface") for x in (night_sig.get("top_looked_up_words") or [])[:3] if isinstance(x, dict) and x.get("surface")
    ])[:3]
    combined_targets = []
    for x in night_missed + night_vocab + night_lookups + list(focus_points):
        if x and x not in combined_targets:
            combined_targets.append(x)

    exemplars = load_qq_corpus_exemplars(today_str, count=2)
    try:
        import immersion_vocab_engine as _ive
        vocab_brief = _ive.get_prompt_vocab_brief(today_str=today_str)
    except Exception:
        vocab_brief = {}

    sys_prompt = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿（深谙 3,182 期实录里的『人味』与『把一件真实新闻剥洋葱讲透』的叙事功力）。\n"
        "三位老友：窦文涛(W，俗人真性情、爱自嘲好奇、绝不当报幕员)、"
        "梁文道(D，温厚会讲故事、把当日真实新闻放进日本社会背景与公共记忆里剥笋深聊)、"
        "许子东(X，冷幽默学者、一句话点破人情世故与社会真相)。\n"
        "请从今日真实日本新闻里【只挑一两件最有冲突感、最反映日本当下世相的真新闻】彻底剥洋葱讲透（约 9 分钟，26 到 36 轮，约 2,500 到 2,800 字），绝不串烧报菜名、绝不泛泛而谈，故事性要让人听完牢牢记住！\n"
        "核心铁律：\n"
        "1. 【100% 真实新闻，严禁编造人物】：只能聊输入里的真实新闻与真实日本历史社会脉络，绝对不允许虚构任何假朋友、假同事、假邻居故事！\n"
        "2. 【开篇与收束自然衔接】：开篇第一轮 W 直接以『《锵锵三人行》，』切入今日最热日本新闻；最后两轮由 D/W 自然预告待会儿回来要深聊的今日两段日本真实公共记忆大故事（参考 companion_titles），以『待会儿回来，马上……！』收住悬念即可，不要自己抢说『先进广告』，把原版进广告口播留给系统由文涛统一喊出『咱们先去一下广告，《锵锵三人行》，广告之后见！』。\n"
        "3. 【约 1.35 倍自然语法讲解频率（本章约 5 个 N3 语法/词汇点，自然流畅绝不生硬说教）】：自然揉入 5 个目标 N3 表达；其中 3 个由 D/X 用一两句大白话点透意思、接续或易混双胞胎词，W 顺手接一句；另外 2 个在聊天现场一两句话顺嘴点睛带过，像老友聊天一样自然流畅，绝不变成念教材！\n"
        "4. 【365 天 5 次累计毕业制 · 中日无缝融合】：参考输入里的 `immersion_vocab_ledger`：`locked_ja_words`（已累计听满 5 次毕业词）在顺口名词位直接用纯假名说出；新引入的 N3/N2 实用难读词（优先挑 `learning_in_progress` 与 `priority_to_introduce`）上段先『中文也就是纯假名』自然带出一次，下段起直接改用纯假名，绝不堆砌过简单的基础词！\n"
        f"5. 当前处于 {ramp_days} 天双语计划第 {day_num} 天（阶段：{phase}），日语假名占比约 {max(ja_pct, 12)}%。\n"
        "6. 【语音合成硬铁律】：对白文本中凡出现日文词句，必须 100% 写成纯平假名或纯片假名（前后留空格或中文标点），严禁汉字紧贴假名，严禁夹杂单字中文孤岛，严禁破折号（—/——），严禁任何英文字母或阿拉伯数字（数字全写中文），严禁『哈哈』『噗』或考试倒计时。\n"
        "输出严格为 JSON：{\"short_tab\": \"今日时局\", \"title\": \"...\", \"ja_focus\": \"...(此处可正常写日文汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"X\", \"...\"], [\"D\", \"...\"], ...]}"
    )
    usr_prompt = json.dumps({
        "nhk_live_headlines": headlines,
        "last_night_priority_targets": combined_targets[:6],
        "immersion_vocab_ledger": vocab_brief,
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
            "is_news_slot": True,
            "short_tab": str(parsed.get("short_tab") or "今日时局")[:6],
            "tags": ["今日日本时局", "真实日本公共记忆", "润物细无声N3"],
            "title": str(parsed.get("title") or "今日日本时局观察"),
            "point_ids": ["N3-G13", "N3-G23", "N3-G55", "N3-G68", "N3-G67"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": _sanitize_generated_turns(parsed.get("turns") or []),
        }
        if validate_generated_story(story, require_light_explain=(imm_profile.get("ja_ratio", 0.14) < 0.45), min_chars=2200):
            os.makedirs(AUDIO_DIR, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(story, f, ensure_ascii=False, indent=2)
            print(f"[live-news] Generated validated 60m-tier NHK current-affairs roundtable: {story['title']}")
            return story
        print("[info] Generated live news story did not pass strict phonetic/depth gate; using curated 60m Uchi bank.")
    except Exception as e:
        print(f"[info] Failed to parse live news JSON: {e}")
    return None


def maybe_generate_live_world_finale_story(
    today_str: str,
    imm_profile: dict,
    focus_points: list[str],
    companion_titles: list[str],
    dry_test: bool = False,
) -> dict | None:
    """
    Generates the mandatory final-1/5 (~12 min of 60m episode) 'World From Japan's Perspective' finale segment:
    covers non-Japan global news across science, AI, medicine, space, energy, global economy,
    climate, tech & geopolitics through Japanese media/society's eyes, with ~1.35x natural N3 grammar
    density and direct N5/simple-N4 inline Japanese vocabulary.
    """
    if dry_test:
        return None
    cache_path = os.path.join(AUDIO_DIR, f"live_world_finale_{today_str}.json")
    if os.path.exists(cache_path):
        try:
            cached = json.load(open(cache_path, encoding="utf-8"))
            if validate_generated_story(cached, require_light_explain=(imm_profile.get("ja_ratio", 0.14) < 0.45), min_chars=2900):
                return cached
        except Exception:
            pass

    world_headlines = fetch_live_world_from_japan_news(max_items=10)
    if not world_headlines:
        return None

    ja_pct = int(round(float(imm_profile.get("ja_ratio", 0.14)) * 100))
    phase = imm_profile.get("phase", "n3_sprint")
    ramp_days = int(imm_profile.get("ramp_days", 700))
    day_num = imm_profile.get("day_of_365", 1)

    night_sig = load_last_night_signals()
    night_missed = (night_sig.get("missed_or_unsure_points") or [])[:4]
    combined_targets = []
    for x in night_missed + list(focus_points):
        if x and x not in combined_targets:
            combined_targets.append(x)

    exemplars = load_qq_corpus_exemplars(f"world:{today_str}", count=2)
    try:
        import immersion_vocab_engine as _ive
        vocab_brief = _ive.get_prompt_vocab_brief(today_str=today_str)
    except Exception:
        vocab_brief = {}

    sys_prompt = (
        "你是凤凰卫视《锵锵三人行》原班总撰稿，现在负责每天 60 分钟节目压轴的【最后五分之一板块：从日本的角度看世界】（约 12 分钟，30 到 42 轮，约 3,350 到 3,650 字）。\n"
        "核心定位：绝对不要锁死在日本本土，也绝对不要局限于文史哲！要让听众 365 天持续知道全世界正在发生什么重要大事，优先挑选【科学、前沿科技、人工智能、数学物理、国际医学、新能源材料、太空探索、全球财经、气候环境、国际地缘】等非文史哲广谱真新闻！\n"
        "独特视角：必须把一到两件最重磅的世界大事剥洋葱讲透，绝不走马观花报菜名，讲清楚『日本媒体、日本科学家、企业界或日本普通老百姓怎么看待这件世界大事？为什么日本人的反应跟欧美或中国不一样？』故事性要让人听完记得住！\n"
        "三位老友：窦文涛(W，好奇心强、爱把前沿科学或国际新闻拉回普通人生活直觉)、梁文道(D，视野开阔、从日本视角串联全球脉络)、许子东(X，犀利冷幽默、点破各国心态反差)。\n"
        "硬性铁律：\n"
        "1. 【100% 真实国际/科学新闻，严禁编造人物】：只聊输入里的真实世界/科学/科技/医疗/经济新闻，挑一到两件最重磅的彻底聊透，绝不泛泛而谈。\n"
        "2. 【原版锵锵灵魂特色·无结尾的突然收束（聊着聊着突然就结束了）】：开篇第一轮由 W 自然承接前面日本往事把镜头拉出日本看世界（不出现『《锵锵三人行》』开场）；结尾必须坚决贯彻原版锵锵精髓：没有结尾！严禁整期总结回顾、严禁报菜名盘点（绝不出现『回顾今天整桌大餐』『今天学了什么』『不仅日语听得透亮』）、严禁任何刻板告别辞（严禁『一壶茶喝完』『茶香见底』『咱们明天见』）！三人还在兴致盎然地热聊、抖包袱、抬杠或探究一个意犹未尽的趣味细节时，最后一轮对话由 W 或嘉宾自然抛出观点或打趣，直接在最真实生动的聊天现场感中猝然收束，让片尾音乐直接在对白下漫入并渐强盖过对白收尾！\n"
        "3. 【约 1.35 倍自然语法讲解频率（本章约 6 个 N3 语法点，自然流畅绝不生硬）】：自然融入 6 个 N3 高频表达（优先参考目标清单）；3 到 4 个由 D/X 顺嘴用一两句大白话点破意思、接续或双胞胎辨析，另 2 到 3 个轻巧一句带过，保持聊天人味绝不变成枯燥上课。\n"
        "4. 【365 天 5 次累计毕业制 · 中日无缝融合】：参考输入里的 `immersion_vocab_ledger`：`locked_ja_words`（已听满 5 次毕业词）在顺口名词位直接用纯假名说出；新引入的 N3/N2 实用难读词（优先挑 `learning_in_progress` 与 `priority_to_introduce`）上段先『中文也就是纯假名』带出一次，下段起直接改用纯假名，绝不堆砌过简单的基础词！\n"
        f"5. 当前处于 {ramp_days} 天双语计划第 {day_num} 天（阶段：{phase}），日语假名占比约 {max(ja_pct, 12)}%。\n"
        "6. 【语音合成硬铁律】：对白文本中所有日文必须 100% 纯平假名或纯片假名（前后空格或标点隔开），严禁汉字紧贴假名，严禁单字中文孤岛，严禁破折号（—/——），严禁英文字母与阿拉伯数字（全写中文，如『人工智能』『量子』『百分之三十八』），严禁『哈哈』『噗』或考试倒计时。\n"
        "输出严格为 JSON：{\"short_tab\": \"日本看世界\", \"title\": \"...\", \"ja_focus\": \"...(此处可正常写日文汉字假名供屏幕显示)\", "
        "\"turns\": [[\"W\", \"...\"], [\"D\", \"...\"], [\"X\", \"...\"], ...]}"
    )
    usr_prompt = json.dumps({
        "japan_reported_world_and_science_headlines": world_headlines,
        "priority_n3_grammar_targets": combined_targets[:6],
        "immersion_vocab_ledger": vocab_brief,
        "earlier_japan_stories_today": companion_titles[:4],
        "authentic_qqsrx_style_reference": load_cloud_qq_style_exemplars(f"world:{today_str}"),
        "authentic_qiangqiang_cadence_examples": exemplars,
    }, ensure_ascii=False, indent=2)

    raw = _call_chat_llm(sys_prompt, usr_prompt)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        story = {
            "id": f"live_world_finale_{today_str}",
            "tier": "world_from_japan",
            "is_world_finale": True,
            "short_tab": str(parsed.get("short_tab") or "日本看世界")[:6],
            "tags": ["日本看世界", "科学科技国际", "润物细无声N3"],
            "title": str(parsed.get("title") or "从日本看今天的世界科学和国际大事"),
            "point_ids": ["N3-G69", "N3-G65", "N3-G19", "N3-G67", "N3-G71", "N3-G127"],
            "ja_focus": str(parsed.get("ja_focus") or ""),
            "turns": _sanitize_generated_turns(parsed.get("turns") or []),
        }
        if validate_generated_story(story, require_light_explain=(imm_profile.get("ja_ratio", 0.14) < 0.45), min_chars=2900):
            os.makedirs(AUDIO_DIR, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(story, f, ensure_ascii=False, indent=2)
            print(f"[world-finale] Generated validated 60m-tier Japanese-angle world/science finale: {story['title']}")
            return story
        print("[info] Generated world finale did not pass strict phonetic/depth gate; using curated 60m World-from-Japan finale.")
    except Exception as e:
        print(f"[info] Failed to parse world finale JSON: {e}")
    return None
