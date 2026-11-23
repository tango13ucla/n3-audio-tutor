#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
365-Day Cumulative Podcast Bilingual Immersion & 5-Hit Graduation Engine (immersion_vocab_engine.py).

Implements Yangfan's cumulative ear-acquisition rule for 《锵锵三人行》 (N3 now + N2/N1 across 365-700 days):
1. Tracks every target Japanese vocabulary word's cumulative exposures across aired episodes in
   `audio/podcast_vocab_ledger.json` (100% Zero-PII, idempotent on same-day rebuilds via per-date counts).
2. Prioritizes genuinely useful, pronunciation-tricky N3/N2 & adult practical nouns (such as `辞書/じしょ`,
   `予算/よさん`, `制度/せいど`, `裁判/さいばん`, `歴史/れきし`, `経済/けいざい`, `社会/しゃかい`, etc.)
   rather than wasting slots on overly elementary N5 words.
3. Three-stage ear-acquisition lifecycle per word:
   - New (`prior_exposures == 0`, up to `DAILY_NEW_BUDGET = 12` fresh words/episode):
     1st clean mention pairs Chinese + Japanese right next to each other (`预算也就是{{预算|よさん}}`),
     or stays plain Chinese if embedded in a tight modifier compound; 2nd+ mentions in the SAME episode
     switch directly to seamless inline Japanese (`{{预算|よさん}}`).
   - Learning (`1 <= prior_exposures < 5`):
     If `prior_exposures <= 2`, 1st clean mention gives one gentle bridge (`预算也就是{{预算|よさん}}`)
     and subsequent mentions switch directly to `{{预算|よさん}}`; if `prior_exposures in (3, 4)`,
     switches directly to `{{预算|よさん}}` from the first mention.
   - Permanently Graduated (`prior_exposures >= 5`, `status = "locked_ja"`):
     Locked in as a permanent Japanese word across ALL future episodes (curated, live news, & N2/N1)!
4. Every inline Japanese word is encoded as `{{zh_carrier|ja_kana}}` so `generate_daily_radio.py`'s
   Calibrated Carrier-Swap Engine splices the exact Japanese pronunciation into an unbroken Mandarin
   breath with ZERO awkward Chinese-Japanese gaps.
"""
from __future__ import annotations
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
LEDGER_PATH = os.path.join(AUDIO_DIR, "podcast_vocab_ledger.json")
RADIO_HISTORY_PATH = os.path.join(AUDIO_DIR, "radio_history.json")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")

GRADUATION_THRESHOLD = 8
MIN_GRADUATION_DAYS = 3
DAILY_NEW_BUDGET = 12
MAX_INLINE_PER_SENTENCE = 3

# Protected spans that must NEVER be partially rewritten (titles, quotes, proper names)
PROTECTED_SPAN_RE = re.compile(r"《[^》]*》|『[^』]*』|「[^」]*」|“[^”]*”")
JA_KANA_TOKEN_RE = re.compile(r"[\u3040-\u30ffー・]+")
SWAP_TOKEN_RE = re.compile(r"\{\{([^|]+)\|([^}]+)\}\}")

# Explicit grammar-teaching sentences where we should NOT add new `也就是` bridges
GRAMMAR_META_RE = re.compile(
    r"日语里|日文里|日语叫|日文叫|日语说法|日文说法|说法，叫|念作|读作|句型|双胞胎|词尾|辞书形|过去形|连用形|使役形|形容词|动词|助词|拟态副词|后缀|前缀|音译"
)
BROADCAST_FRAME_RE = re.compile(
    r"《锵锵三人行》|广告之后见|先去一下广告|先去下广告|先去段广告|再去一下广告|再去下广告|明天见|下回接着聊|下期见"
)

# Characters that naturally follow a standalone noun for a silky `{zh}也就是{{zh|kana}}` bridge
BRIDGE_AFTER_OK_RE = re.compile(
    r"^(?:$|[，。！？；：、]|的|里|上|中|下|前|后|时|呢|啊|吧|吗|也|都|就|才|却|和|与|跟|或|还|不|没|很|太|真|会|能|要|在|被|把|让|给|向|对|比|从|到|越|更|全|只)"
)
# Dual verb/noun words (like 设计/调查/研究/习惯/努力/发现/准备/投资/讨论/批评/选择/判断/解决/改革/消费/生产/实验/发明/开发/治疗/竞争)
# must NOT be swapped when used as an active Chinese verb (`设计了一座`, `发现这个`, `努力去干`, `习惯把`)!
DUAL_VERB_NOUN_KANAS = {
    "せっけい", "ちょうさ", "けんきゅう", "しゅうかん", "どりょく", "はっけん", "じゅんび",
    "とうし", "ぎろん", "ひはん", "せんたく", "はんだん", "かいけつ", "かいかく", "しょうひ",
    "せいさん", "じっけん", "はつめい", "かいはつ", "ちりょう", "きょうそう", "ごかい",
    "こうかい", "よやく", "やくそく", "へんか", "せいこう", "しっぱい", "けいかく", "とうけい",
}
VERB_USE_AFTER_RE = re.compile(r"^[了着过出到完起下开掉把去来地给进回住成上得一这那各两三四五六七八九十百千万]")
VERB_USE_BEFORE_RE = re.compile(r"[在正要会能敢肯想愿爱总老刚已曾没别该应必须试图努力早就才更越最]")


def _e(
    kana: str,
    kanji: str,
    zh: list[str],
    tier: str = "n3_core",
    carrier: str | None = None,
    forbid_before: str = "",
    forbid_after: str = "",
) -> dict:
    return {
        "kana": kana,
        "kanji": kanji,
        "zh": sorted(set(zh), key=len, reverse=True),
        "carrier": carrier or zh[0],
        "tier": tier,
        "forbid_before": forbid_before,
        "forbid_after": forbid_after,
    }


# ==============================================================================
# Curated 365-Day Adult / N3 / N2 / Practical Immersion Vocabulary Bank
# Strict linguistic vetting: concrete nouns & concepts that fit naturally inside
# Mandarin sentences without breaking idioms, proper nouns, or syntax.
# ==============================================================================
IMMERSION_VOCAB_BANK: list[dict] = [
    # --- Tier 0: Explicit User Priority (pronunciation-tricky everyday & intellectual words) ---
    _e("じしょ", "辞書", ["字典", "辞典", "词典"], "user_priority", "字典",
       forbid_before=r"[英汉中日法德牛津现代新华古今]", forbid_after=r"[学编]"),
    _e("としょかん", "図書館", ["图书馆"], "user_priority", "图书馆"),
    _e("はくぶつかん", "博物館", ["博物馆"], "user_priority", "博物馆"),
    _e("しょるい", "書類", ["书面文件", "文件"], "user_priority", "文件",
       forbid_before=r"[红头机密官方]", forbid_after=r"[夹袋柜]"),
    _e("しゅっちょう", "出張", ["出差"], "user_priority", "出差",
       forbid_after=r"[费补贴]"),

    # --- Tier 1: High-Frequency N3/N2 Public Affairs, Economy, Tech & Society ---
    _e("よさん", "予算", ["预算"], "n3_core", "预算", forbid_after=r"[案委]"),
    _e("せいど", "制度", ["制度"], "n3_core", "制度", forbid_after=r"[化性]"),
    _e("せいふ", "政府", ["政府"], "n3_core", "政府",
       forbid_before=r"[日本美国中国地方中央联邦特区自治]", forbid_after=r"[间军]"),
    _e("せいじ", "政治", ["政治"], "n3_core", "政治",
       forbid_before=r"[地缘国际]", forbid_after=r"[家局学课]"),
    _e("こっかい", "国会", ["国会"], "n3_core", "国会", forbid_after=r"[议山]"),
    _e("しゅしょう", "首相", ["首相"], "n3_core", "首相", forbid_after=r"[府官]"),
    _e("かんりょう", "官僚", ["官僚"], "n2_core", "官僚", forbid_after=r"[主制]"),
    _e("せんきょ", "選挙", ["选举"], "n3_core", "选举", forbid_after=r"[人权法]"),
    _e("せいさく", "政策", ["政策"], "n3_core", "政策", forbid_after=r"[性]"),
    _e("かいかく", "改革", ["改革"], "n3_core", "改革", forbid_after=r"[开放派]"),
    _e("ほうりつ", "法律", ["法律"], "n3_core", "法律", forbid_after=r"[界师]"),
    _e("さいばん", "裁判", ["审判", "法庭", "裁判"], "n3_core", "审判",
       forbid_after=r"[员长所官]"),
    _e("けいやく", "契約", ["合同", "契约"], "n3_core", "合同", forbid_after=r"[工书]"),
    _e("けんり", "権利", ["权利"], "n3_core", "权利"),
    _e("ぎむ", "義務", ["义务"], "n3_core", "义务", forbid_after=r"[教育兵]"),
    _e("れきし", "歴史", ["历史"], "n3_core", "历史",
       forbid_before=r"[亚欧中]", forbid_after=r"[学剧观性]"),
    _e("けいざい", "経済", ["经济"], "n3_core", "经济",
       forbid_before=r"[日本中国全球世界市场实体民营数字]", forbid_after=r"[学界报体]"),
    _e("しゃかい", "社会", ["社会"], "n3_core", "社会",
       forbid_before=r"[全日本现代人类资本]", forbid_after=r"[学主派界]"),
    _e("しじょう", "市場", ["市场"], "n3_core", "市场",
       forbid_before=r"[批发资本金融股市国际全球]", forbid_after=r"[化经济]"),
    _e("きぎょう", "企業", ["企业"], "n3_core", "企业",
       forbid_before=r"[大中小国有民营跨国日本中国]", forbid_after=r"[家化]"),
    _e("さんぎょう", "産業", ["产业"], "n3_core", "产业",
       forbid_before=r"[夕阳支柱高新传统第一二三]", forbid_after=r"[化链园]"),
    _e("きょうそう", "競争", ["竞争"], "n3_core", "竞争", forbid_after=r"[力对手]"),
    _e("とうし", "投資", ["投资"], "n3_core", "投资", forbid_after=r"[者人方商行]"),
    _e("りえき", "利益", ["利润", "利益"], "n3_core", "利润", forbid_after=r"[率链]"),
    _e("あかじ", "赤字", ["赤字", "亏损"], "n2_core", "赤字"),
    _e("ぶっか", "物価", ["物价"], "n3_core", "物价"),
    _e("ぜいきん", "税金", ["税金", "税收"], "n3_core", "税金"),
    _e("ねんきん", "年金", ["养老金", "年金"], "n3_core", "年金", forbid_before=r"[国民厚生]"),
    _e("ほけん", "保険", ["保险"], "n3_core", "保险", forbid_before=r"[社会医疗人寿车]", forbid_after=r"[费公司丝箱]"),
    _e("ほじょきん", "補助金", ["补贴"], "n2_core", "补贴", forbid_before=r"[减产配偶]"),
    _e("きゅうりょう", "給料", ["工资", "薪水"], "n3_core", "工资", forbid_before=r"[最低平均]"),
    _e("しょうひ", "消費", ["消费"], "n3_core", "消费", forbid_after=r"[者税品力观]"),
    _e("せいさん", "生産", ["生产"], "n3_core", "生产", forbid_before=r"[国民总]", forbid_after=r"[力线值率商]"),
    _e("りゅうつう", "流通", ["流通"], "n2_core", "流通", forbid_after=r"[业]"),
    _e("ゆしゅつ", "輸出", ["出口"], "n3_core", "出口", forbid_before=r"[进出安全高速地]", forbid_after=r"[处口税]"),
    _e("ゆにゅう", "輸入", ["进口"], "n3_core", "进口", forbid_before=r"[进出]", forbid_after=r"[处口税]"),
    _e("ぼうえき", "貿易", ["贸易"], "n3_core", "贸易", forbid_after=r"[战商]"),
    _e("きんゆう", "金融", ["金融"], "n2_core", "金融", forbid_after=r"[厅界业机]"),
    _e("かぶか", "株価", ["股价"], "n2_core", "股价"),
    _e("コスト", "コスト", ["成本"], "n3_core", "成本"),
    _e("リスク", "リスク", ["风险"], "n3_core", "风险"),
    _e("データ", "データ", ["数据"], "n3_core", "数据", forbid_after=r"[库线]"),
    _e("システム", "システム", ["系统"], "n3_core", "系统", forbid_after=r"[性化]"),
    _e("エネルギー", "エネルギー", ["能源"], "n3_core", "能源", forbid_before=r"[新清洁绿核]"),
    _e("ルール", "ルール", ["规则", "规矩"], "n3_core", "规则"),
    _e("ストレス", "ストレス", ["压力"], "n3_core", "压力"),
    _e("スマホ", "スマホ", ["手机"], "n3_core", "手机", forbid_after=r"[壳膜号]"),

    # --- Tier 1b: Science, Engineering, Industry, Environment & Medicine ---
    _e("けんきゅう", "研究", ["研究"], "n3_core", "研究", forbid_after=r"[所院员生者]"),
    _e("じっけん", "実験", ["实验"], "n3_core", "实验", forbid_after=r"[室]"),
    _e("はつめい", "発明", ["发明"], "n3_core", "发明", forbid_after=r"[家者]"),
    _e("はっけん", "発見", ["发现"], "n3_core", "发现", forbid_after=r"[者]"),
    _e("かいはつ", "開発", ["开发", "研发"], "n3_core", "开发", forbid_after=r"[商者区]"),
    _e("とっきょ", "特許", ["专利"], "n2_core", "专利", forbid_after=r"[权局费]"),
    _e("ろんぶん", "論文", ["论文"], "n3_core", "论文"),
    _e("きょうじゅ", "教授", ["教授"], "n3_core", "教授", forbid_before=r"[副助名大]"),
    _e("はかせ", "博士", ["博士"], "n3_core", "博士", forbid_after=r"[后生]"),
    _e("でんち", "電池", ["电池"], "n3_core", "电池", forbid_before=r"[太阳能固态锂干蓄]"),
    _e("はんどうたい", "半導体", ["半导体"], "n2_core", "半导体"),
    _e("ざいりょう", "材料", ["材料"], "n3_core", "材料", forbid_before=r"[新原建筑科学]"),
    _e("しげん", "資源", ["资源"], "n3_core", "资源", forbid_before=r"[人力自然水矿]"),
    _e("えいせい", "衛星", ["卫星"], "n2_core", "卫星", forbid_before=r"[人造气象通信]"),
    _e("せっけい", "設計", ["设计"], "n3_core", "设计", forbid_after=r"[师图院]"),
    _e("けんちく", "建築", ["建筑"], "n3_core", "建筑", forbid_after=r"[师学界物]"),
    _e("ひょうじゅん", "標準", ["标准"], "n3_core", "标准", forbid_after=r"[化轨语]"),
    _e("こうりつ", "効率", ["效率"], "n2_core", "效率", forbid_after=r"[化]"),
    _e("ひんしつ", "品質", ["质量", "品质"], "n3_core", "质量"),
    _e("そくど", "速度", ["速度"], "n3_core", "速度", forbid_before=r"[加高超光音]"),
    _e("きぼ", "規模", ["规模"], "n2_core", "规模", forbid_before=r"[大小超]"),
    _e("すうじ", "数字", ["数字"], "n3_core", "数字", forbid_after=r"[化经济]"),
    _e("とうけい", "統計", ["统计"], "n2_core", "统计", forbid_after=r"[学局]"),
    _e("へいきん", "平均", ["平均"], "n3_core", "平均", forbid_after=r"[值数年龄工资]"),
    _e("かんきょう", "環境", ["环境"], "n3_core", "环境", forbid_before=r"[大生活自然生态]"),
    _e("きこう", "気候", ["气候"], "n3_core", "气候"),
    _e("さいがい", "災害", ["灾害"], "n3_core", "灾害", forbid_before=r"[自然]"),
    _e("じしん", "地震", ["地震"], "n3_core", "地震", forbid_before=r"[大海槽大关东阪神]"),
    _e("たいふう", "台風", ["台风"], "n3_core", "台风"),
    _e("いりょう", "医療", ["医疗"], "n3_core", "医疗", forbid_after=r"[费保险界]"),
    _e("ちりょう", "治療", ["治疗"], "n3_core", "治疗", forbid_after=r"[法费]"),
    _e("かんじゃ", "患者", ["患者", "病人"], "n3_core", "患者"),
    _e("けんこう", "健康", ["健康"], "n3_core", "健康", forbid_after=r"[险码]"),

    # --- Tier 1c: Culture, Media, Cities, Human Nature & Intellectual Discourse ---
    _e("ぶんか", "文化", ["文化"], "n3_core", "文化",
       forbid_before=r"[日本中国企业流行饮食次]", forbid_after=r"[大界人厅]"),
    _e("でんとう", "伝統", ["传统"], "n3_core", "传统", forbid_after=r"[大老型]"),
    _e("げんだい", "現代", ["现代"], "n3_core", "现代", forbid_after=r"[化人史]"),
    _e("みらい", "未来", ["未来"], "n3_core", "未来", forbid_after=r"[大屋顶主义]"),
    _e("じだい", "時代", ["时代"], "n3_core", "时代",
       forbid_before=r"[昭和平成令和明治大正江户战后黄金旧新大]"),
    _e("せだい", "世代", ["世代"], "n2_core", "世代", forbid_before=r"[冰河期团块年轻老]"),
    _e("こくさい", "国際", ["国际"], "n3_core", "国际", forbid_after=r"[化法机场]"),
    _e("こくみん", "国民", ["国民"], "n3_core", "国民", forbid_after=r"[党生产年金]"),
    _e("しみん", "市民", ["市民"], "n3_core", "市民"),
    _e("じんこう", "人口", ["人口"], "n3_core", "人口", forbid_before=r"[总全国]"),
    _e("こうれいか", "高齢化", ["老龄化"], "n2_core", "老龄化"),
    _e("しょうしか", "少子化", ["少子化"], "n2_core", "少子化"),
    _e("いみん", "移民", ["移民"], "n2_core", "移民", forbid_after=r"[局法]"),
    _e("がいこう", "外交", ["外交"], "n2_core", "外交", forbid_after=r"[官部]"),
    _e("せんそう", "戦争", ["战争"], "n3_core", "战争", forbid_before=r"[世界冷核贸易]"),
    _e("へいわ", "平和", ["和平"], "n3_core", "和平", forbid_after=r"[主义]"),
    _e("じゆう", "自由", ["自由"], "n3_core", "自由", forbid_after=r"[党化度主]"),
    _e("ぶき", "武器", ["武器"], "n3_core", "武器", forbid_before=r"[自主核热冷]"),
    _e("あんぜん", "安全", ["安全"], "n3_core", "安全", forbid_after=r"[带帽感阀网门局]"),
    _e("きけん", "危険", ["危险"], "n3_core", "危险", forbid_after=r"[性品]"),
    _e("きき", "危機", ["危机"], "n2_core", "危机", forbid_before=r"[金融石油能源信任]"),
    _e("じこ", "事故", ["事故"], "n3_core", "事故", forbid_before=r"[交通核]"),
    _e("じけん", "事件", ["事件"], "n3_core", "事件", forbid_before=r"[大悬]"),
    _e("はんざい", "犯罪", ["犯罪"], "n3_core", "犯罪", forbid_after=r"[率者]"),
    _e("けいさつ", "警察", ["警察"], "n3_core", "警察", forbid_after=r"[局厅署]"),
    _e("しょうこ", "証拠", ["证据"], "n2_core", "证据"),
    _e("べんごし", "弁護士", ["律师"], "n3_core", "律师"),
    _e("さくひん", "作品", ["作品"], "n3_core", "作品", forbid_before=r"[代表名艺]"),
    _e("しょうせつ", "小説", ["小说"], "n3_core", "小说", forbid_after=r"[家]"),
    _e("かんとく", "監督", ["导演"], "n3_core", "导演"),
    _e("はいゆう", "俳優", ["演员"], "n3_core", "演员"),
    _e("ぶたい", "舞台", ["舞台"], "n3_core", "舞台", forbid_before=r"[大历史国际世界]"),
    _e("げんば", "現場", ["现场"], "n3_core", "现场", forbid_before=r"[第一案发聊天]"),
    _e("ざっし", "雑誌", ["杂志"], "n3_core", "杂志", forbid_after=r"[社]"),
    _e("ばんぐみ", "番組", ["节目"], "n3_core", "节目", forbid_before=r"[电视广播]"),
    _e("ほうそう", "放送", ["广播"], "n3_core", "广播", forbid_after=r"[体操局剧台]"),
    _e("ほうどう", "報道", ["报道"], "n3_core", "报道", forbid_before=r"[新闻媒体]"),
    _e("きしゃ", "記者", ["记者"], "n3_core", "记者", forbid_after=r"[会团]"),
    _e("かいぎ", "会議", ["会议"], "n3_core", "会议", forbid_after=r"[室]"),
    _e("きろく", "記録", ["记录"], "n3_core", "记录", forbid_after=r"[片者]"),
    _e("しりょう", "資料", ["资料"], "n3_core", "资料", forbid_after=r"[库室]"),
    _e("じょうほう", "情報", ["信息", "情报"], "n3_core", "信息", forbid_after=r"[化网局]"),
    _e("くうこう", "空港", ["机场"], "n3_core", "机场", forbid_before=r"[羽田成田关西国际]"),
    _e("こうつう", "交通", ["交通"], "n3_core", "交通", forbid_after=r"[工具事故警]"),
    _e("とし", "都市", ["都市", "城市"], "n3_core", "城市", forbid_before=r"[大国际超级卫星]"),
    _e("こきゃく", "顧客", ["顾客"], "n2_core", "顾客"),
    _e("きょういく", "教育", ["教育"], "n3_core", "教育", forbid_before=r"[义务高等精英]", forbid_after=r"[部界学]"),
    _e("てつがく", "哲学", ["哲学"], "n2_core", "哲学", forbid_after=r"[家]"),
    _e("ぶんがく", "文学", ["文学"], "n3_core", "文学", forbid_after=r"[家史界奖]"),
    _e("げいじゅつ", "芸術", ["艺术"], "n3_core", "艺术", forbid_after=r"[家品界]"),
    _e("しゅうきょう", "宗教", ["宗教"], "n2_core", "宗教", forbid_after=r"[界]"),
    _e("しあい", "試合", ["比赛"], "n3_core", "比赛"),
    _e("かんきゃく", "観客", ["观众"], "n3_core", "观众"),

    # --- Tier 1d: Core Abstract Nouns & Mental/Social Concepts (Super High Payoff!) ---
    _e("げんいん", "原因", ["原因"], "n3_core", "原因", forbid_before=r"[根本历史客观主要]"),
    _e("えいきょう", "影響", ["影响"], "n3_core", "影响", forbid_after=r"[力]"),
    _e("かんけい", "関係", ["关系"], "n3_core", "关系", forbid_before=r"[没不有国际人际劳资]"),
    _e("じょうけん", "条件", ["条件"], "n3_core", "条件", forbid_before=r"[无先决必备]"),
    _e("へんか", "変化", ["变化"], "n3_core", "变化"),
    _e("かいけつ", "解決", ["解决"], "n3_core", "解决", forbid_after=r"[方案办法]"),
    _e("たいさく", "対策", ["对策"], "n2_core", "对策"),
    _e("けいかく", "計画", ["计划"], "n3_core", "计划", forbid_before=r"[五年经济]"),
    _e("ちょうさ", "調査", ["调查"], "n3_core", "调查", forbid_after=r"[团局员]"),
    _e("はんだん", "判断", ["判断"], "n3_core", "判断", forbid_after=r"[力]"),
    _e("せんたく", "選択", ["选择"], "n3_core", "选择", forbid_after=r"[题权]"),
    _e("ぎろん", "議論", ["讨论", "争论"], "n2_core", "讨论"),
    _e("いけん", "意見", ["意见"], "n3_core", "意见"),
    _e("ひはん", "批判", ["批评", "批判"], "n2_core", "批评", forbid_after=r"[性家]"),
    _e("せきにん", "責任", ["责任"], "n3_core", "责任", forbid_after=r"[感人制]"),
    _e("じゅんび", "準備", ["准备"], "n3_core", "准备"),
    _e("けいけん", "経験", ["经验"], "n3_core", "经验", forbid_after=r"[者论]"),
    _e("きおく", "記憶", ["记忆"], "n3_core", "记忆", forbid_before=r"[公共集体国民]", forbid_after=r"[力]"),
    _e("いんしょう", "印象", ["印象"], "n3_core", "印象", forbid_after=r"[派]"),
    _e("ひみつ", "秘密", ["秘密"], "n3_core", "秘密", forbid_after=r"[武器警察]"),
    _e("しょうちょう", "象徴", ["象征"], "n2_core", "象征", forbid_after=r"[性]"),
    _e("かち", "価値", ["价值"], "n3_core", "价值", forbid_after=r"[观]"),
    _e("たちば", "立場", ["立场"], "n3_core", "立场"),
    _e("しゅうかん", "習慣", ["习惯"], "n3_core", "习惯", forbid_before=r"[生活饮食]"),
    _e("じょうしき", "常識", ["常识"], "n3_core", "常识"),
    _e("きょうみ", "興味", ["兴趣"], "n3_core", "兴趣"),
    _e("どりょく", "努力", ["努力"], "n3_core", "努力"),
    _e("しっぱい", "失敗", ["失败"], "n3_core", "失败", forbid_after=r"[者]"),
    _e("せいこう", "成功", ["成功"], "n3_core", "成功", forbid_after=r"[者率]"),
    _e("もくひょう", "目標", ["目标"], "n3_core", "目标"),
    _e("もくてき", "目的", ["目的"], "n3_core", "目的", forbid_after=r"[地性]"),
    _e("ほうほう", "方法", ["方法"], "n3_core", "方法", forbid_after=r"[论]"),
    _e("ほうこう", "方向", ["方向"], "n3_core", "方向", forbid_after=r"[盘感性]"),
    _e("げんじつ", "現実", ["现实"], "n3_core", "现实", forbid_after=r"[主义感]"),
    _e("りそう", "理想", ["理想"], "n3_core", "理想", forbid_after=r"[主义乡]"),
    _e("むじゅん", "矛盾", ["矛盾"], "n2_core", "矛盾"),
    _e("げんかい", "限界", ["极限"], "n2_core", "极限"),
    _e("ほんしつ", "本質", ["本质"], "n2_core", "本质"),
    _e("こうぞう", "構造", ["结构"], "n2_core", "结构", forbid_after=r"[性化]"),
    _e("はいけい", "背景", ["背景"], "n2_core", "背景", forbid_before=r"[历史社会大]"),
    _e("しんよう", "信用", ["信用"], "n3_core", "信用", forbid_after=r"[卡社]"),
    _e("ゆうき", "勇気", ["勇气"], "n3_core", "勇气"),
    _e("こうかい", "後悔", ["后悔"], "n3_core", "后悔"),
    _e("ごかい", "誤解", ["误会", "误解"], "n3_core", "误会"),
    _e("ふあん", "不安", ["不安"], "n3_core", "不安", forbid_after=r"[全定]"),
    _e("どくりつ", "独立", ["独立"], "n3_core", "独立", forbid_after=r"[性日]"),
    _e("びょうどう", "平等", ["平等"], "n3_core", "平等"),
    _e("せいぎ", "正義", ["正义"], "n2_core", "正义", forbid_after=r"[感]"),
    _e("ちつじょ", "秩序", ["秩序"], "n2_core", "秩序"),
    _e("やくそく", "約束", ["约定", "承诺"], "n3_core", "约定"),
    _e("よやく", "予約", ["预约", "预订"], "n3_core", "预约"),
    _e("めいわく", "迷惑", ["添麻烦", "困扰"], "n3_core", "困扰"),
    _e("ゆだん", "油断", ["大意"], "n2_core", "大意"),
    _e("れいぎ", "礼儀", ["礼仪"], "n3_core", "礼仪"),
    _e("たいど", "態度", ["态度"], "n3_core", "态度"),
    _e("きもち", "気持ち", ["心情"], "n3_core", "心情"),

    # --- Tier 2: Pre-existing N4/N5 Inline Words (tracked for ledger & carrier-swap, NOT consuming new-word budget) ---
    _e("せかい", "世界", ["世界"], "n4_existing", "世界", forbid_before=r"[全第一二三]"),
    _e("かいしゃ", "会社", ["公司"], "n4_existing", "公司", forbid_before=r"[大总分母子跨国]"),
    _e("じかん", "時間", ["时间"], "n4_existing", "时间", forbid_after=r"[差表轴]"),
    _e("ニュース", "ニュース", ["新闻"], "n4_existing", "新闻", forbid_before=r"[朝日读卖每日经济日经产经真热假]"),
    _e("テレビ", "テレビ", ["电视"], "n4_existing", "电视", forbid_after=r"[台剧机]"),
    _e("しんぶん", "新聞", ["报纸"], "n4_existing", "报纸"),
    _e("でんしゃ", "電車", ["电车"], "n4_existing", "电车"),
    _e("しんかんせん", "新幹線", ["新干线"], "n4_existing", "新干线", forbid_before=r"[东海道东北山阳]"),
    _e("スーパー", "スーパー", ["超市"], "n4_existing", "超市"),
    _e("コンビニ", "コンビニ", ["便利店"], "n4_existing", "便利店"),
    _e("こうじょう", "工場", ["工厂"], "n4_existing", "工厂", forbid_before=r"[大老总分]"),
    _e("しゃちょう", "社長", ["社长"], "n4_existing", "社长"),
    _e("しゃいん", "社員", ["员工"], "n4_existing", "员工", forbid_before=r"[老新大兼职正式]"),
    _e("ねだん", "値段", ["价格"], "n4_existing", "价格"),
    _e("ぎじゅつ", "技術", ["技术"], "n4_existing", "技术", forbid_before=r"[高新黑核心尖端关键]"),
    _e("かがく", "科学", ["科学"], "n4_existing", "科学", forbid_after=r"[家院界馆]"),
    _e("ぎんこう", "銀行", ["银行"], "n4_existing", "银行", forbid_before=r"[日本中央人民商业大]"),
    _e("びょういん", "病院", ["医院"], "n4_existing", "医院", forbid_before=r"[大公立私立大学]"),
    _e("かぞく", "家族", ["家人", "家庭"], "n4_existing", "家人", forbid_after=r"[西餐厅]"),
    _e("おにぎり", "おにぎり", ["饭团"], "n4_existing", "饭团"),
    _e("べんとう", "弁当", ["便当"], "n4_existing", "便当"),
    _e("コーヒー", "コーヒー", ["咖啡"], "n4_existing", "咖啡", forbid_after=r"[馆店厅]"),
    _e("おんがく", "音楽", ["音乐"], "n4_existing", "音乐", forbid_after=r"[会厅家剧]"),
    _e("りょこう", "旅行", ["旅行"], "n4_existing", "旅行", forbid_before=r"[修学]"),
    _e("えいが", "映画", ["电影"], "n4_existing", "电影", forbid_after=r"[院节]"),
    _e("ホテル", "ホテル", ["酒店", "旅馆"], "n4_existing", "酒店"),
    _e("うちゅう", "宇宙", ["宇宙", "太空"], "n4_existing", "宇宙"),
    _e("まんが", "漫画", ["漫画"], "n4_existing", "漫画", forbid_after=r"[家]"),
    _e("くすり", "薬", ["药品"], "n4_existing", "药品"),
    _e("おでん", "おでん", ["关东煮"], "n4_existing", "关东煮"),
    _e("ラーメン", "ラーメン", ["拉面"], "n4_existing", "拉面"),
    _e("パン", "パン", ["面包"], "n4_existing", "面包"),
    _e("くるま", "車", ["汽车"], "n4_existing", "汽车"),
    _e("ひこうき", "飛行機", ["飞机"], "n4_existing", "飞机"),
    _e("ちかてつ", "地下鉄", ["地铁"], "n4_existing", "地铁"),
    _e("がくせい", "学生", ["学生"], "n4_existing", "学生", forbid_before=r"[大小中留]"),
    _e("てんいん", "店員", ["店员"], "n4_existing", "店员"),
    _e("ともだち", "友達", ["朋友"], "n4_existing", "朋友", forbid_before=r"[男女老好小]"),
    _e("りょうり", "料理", ["料理"], "n4_existing", "料理", forbid_before=r"[怀石日本中华]"),
    _e("せいかつ", "生活", ["生活"], "n4_existing", "生活", forbid_after=r"[费方式节奏习惯]"),
    _e("ラジオ", "ラジオ", ["收音机"], "n4_existing", "收音机"),
    _e("バス", "バス", ["巴士"], "n4_existing", "巴士"),
]

VOCAB_BY_KANA: dict[str, dict] = {e["kana"]: e for e in IMMERSION_VOCAB_BANK}

# Reverse lookup map for Carrier-Swap of ANY pre-existing bare inline Japanese word in authored scripts!
JA_TO_CARRIER_ZH: dict[str, str] = {e["kana"]: e["carrier"] for e in IMMERSION_VOCAB_BANK}
JA_TO_CARRIER_ZH.update({
    "おかね": "资金",
    "こども": "孩子",
    "えき": "车站",
    "みせ": "店铺",
    "いえ": "家里",
    "くに": "国家",
    "なつ": "夏天",
    "ふゆ": "冬天",
    "はる": "春天",
    "あき": "秋天",
    "ほん": "书籍",
    "へや": "房间",
    "まち": "街头",
    "あめ": "雨水",
    "おかし": "零食",
    "おきゃくさん": "客人",
    "ぶんこぼん": "文库本",
    "ウォークマン": "随身听",
    "びちくまい": "储备米",
    "げんたんせいさく": "减产政策",
    "ばんぱく": "世博会",
    "まいご": "走失儿童",
    "ねんしゅうのかべ": "年收门槛",
    "はたらきぞん": "干多反亏",
    "にほん": "日本",
    "とうきょう": "东京",
    "おおさか": "大阪",
    "きょうと": "京都",
    "しんじゅく": "新宿",
    "しぶや": "涩谷",
    "ぎんざ": "银座",
    "でんわ": "电话",
    "おちゃ": "热茶",
    "ビール": "啤酒",
    "カレーライス": "咖喱饭",
    "きっさてん": "咖啡馆",
    "まちや": "老宅",
    "おいらん": "花魁",
    "ぶぶづけ": "茶泡饭",
    "おちゃづけ": "茶泡饭",
    "かいせきりょうり": "怀石料理",
    "うち": "内部",
    "そと": "外部",
    "ほんね": "真心话",
    "たてまえ": "场面话",
    "そんたく": "揣摩上意",
    "おともれ": "漏音",
    "さつじんロボット": "自主武器",
    "ペロブスカイト": "钙钛矿",
    "ヨウ素": "碘元素",
    "かんばんほうしき": "看板方式",
    "ジャストインタイム": "准时生产",
})


def get_carrier_zh(ja_kana: str) -> str:
    """Returns a clean, natural Chinese carrier word for seamless WordBoundary Carrier-Swap."""
    k = (ja_kana or "").strip("。！？、 ")
    if k in JA_TO_CARRIER_ZH:
        return JA_TO_CARRIER_ZH[k]
    if len(k) <= 1:
        return "这字"
    if len(k) <= 8:
        return "这词"
    return "这话"


def _load_active_weak_words() -> set[str]:
    """Reads non-green tracked vocab words & recent lookup words (zero-PII) to prioritize them."""
    weak: set[str] = set()
    if not os.path.exists(STATE_PATH):
        return weak
    try:
        st = json.load(open(STATE_PATH, encoding="utf-8"))
        for v in st.get("vocab_tracked") or []:
            if v.get("status") != "green":
                w = str(v.get("word") or "").strip()
                k = str(v.get("kana") or "").strip()
                if w:
                    weak.add(w)
                if k:
                    weak.add(k)
        for k in (st.get("word_lookups") or {}).keys():
            if k:
                weak.add(str(k).strip())
    except Exception:
        pass
    return weak


def _seed_historical_daily_counts(salon_stories: list[dict], before_date: str) -> dict[str, dict[str, int]]:
    """
    Reconstructs real historical Japanese exposure counts from `audio/radio_history.json`
    for all aired dates `< before_date` so words Yangfan already heard 5+ times start accurately locked!
    """
    daily_counts: dict[str, dict[str, int]] = {}
    if not os.path.exists(RADIO_HISTORY_PATH):
        return daily_counts
    try:
        rhist = (json.load(open(RADIO_HISTORY_PATH, encoding="utf-8")).get("recent_days") or {})
        by_id = {str(st.get("id") or ""): st for st in (salon_stories or [])}
        for d_str in sorted(rhist.keys()):
            if d_str >= before_date:
                continue
            day_map: dict[str, int] = {}
            for sid in (rhist.get(d_str) or []):
                st = by_id.get(str(sid))
                if not st:
                    continue
                for _, txt in (st.get("turns") or []):
                    for tok in JA_KANA_TOKEN_RE.findall(str(txt)):
                        if tok in VOCAB_BY_KANA:
                            day_map[tok] = day_map.get(tok, 0) + 1
            if day_map:
                daily_counts[d_str] = day_map
    except Exception:
        pass
    return daily_counts


def _load_verified_mastery_sets() -> tuple[set[str], set[str]]:
    """
    Closed-loop mastery bridge (Uchihara/Webb 2019/2023 + Testing Effect):
    - `verified_kanas`: words mastered true-green (3/3) in Vocab OR genuinely verified ('听后复盘:过', never fast-skip)
      in Post-Listening Review -> can lock into pure Japanese early (>=3 podcast hits across >=1 day, or immediately if green)!
    - `recent_fail_kanas`: words recently flagged for relearn or missed in Vocab -> auto-hold in bridge mode.
    """
    verified: set[str] = set()
    recent_fail: set[str] = set()
    kanji_to_kana = {e["kanji"]: e["kana"] for e in IMMERSION_VOCAB_BANK}

    def _to_kana(raw: str) -> str:
        s = str(raw or "").strip()
        if s in VOCAB_BY_KANA:
            return s
        return kanji_to_kana.get(s, "")

    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
            for v in st.get("vocab_tracked") or []:
                k = _to_kana(v.get("word") or "")
                if not k:
                    continue
                sv = str(v.get("status") or "")
                if sv == "green":
                    verified.add(k)
                elif sv in ("red", "orange"):
                    recent_fail.add(k)
            for pt in (st.get("radio_verified_points") or {}).keys():
                k = _to_kana(pt)
                if k:
                    verified.add(k)
            for pt in (st.get("radio_relearn_queue") or {}).keys():
                k = _to_kana(pt)
                if k:
                    recent_fail.add(k)
        except Exception:
            pass
    # Recent fails override early verification
    verified -= recent_fail
    return verified, recent_fail


def load_ledger(salon_stories: list[dict] | None = None, today_str: str = "") -> dict:
    if os.path.exists(LEDGER_PATH):
        try:
            data = json.load(open(LEDGER_PATH, encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("daily_counts"), dict):
                # Upgrade legacy 5-hit/2-day ledgers cleanly to evidence-based 8-hit/3-day standard
                if int(data.get("graduation_threshold") or 0) < GRADUATION_THRESHOLD:
                    data["graduation_threshold"] = GRADUATION_THRESHOLD
                if int(data.get("min_graduation_days") or 0) < MIN_GRADUATION_DAYS:
                    data["min_graduation_days"] = MIN_GRADUATION_DAYS
                return data
        except Exception:
            pass
    seeded = _seed_historical_daily_counts(salon_stories or [], before_date=(today_str or "9999-99-99"))
    return {
        "schema": "podcast-immersion-ledger/2",
        "graduation_threshold": GRADUATION_THRESHOLD,
        "min_graduation_days": MIN_GRADUATION_DAYS,
        "daily_new_budget": DAILY_NEW_BUDGET,
        "user_priority_words": ["じしょ", "としょかん", "はくぶつかん", "しょるい", "しゅっちょう"],
        "daily_counts": seeded,
        "words": {},
    }


def compute_prior_counts(ledger: dict, before_date: str) -> dict[str, int]:
    """Returns exact cumulative counts across all aired dates strictly `< before_date` (100% idempotent)."""
    totals: dict[str, int] = {}
    for d_str, cmap in (ledger.get("daily_counts") or {}).items():
        if d_str < before_date and isinstance(cmap, dict):
            for kana, cnt in cmap.items():
                totals[kana] = totals.get(kana, 0) + int(cnt)
    return totals


def compute_prior_days(ledger: dict, before_date: str) -> dict[str, int]:
    """Returns distinct aired dates count per word strictly `< before_date` (Cepeda / Nakata cross-day spacing)."""
    days_map: dict[str, int] = {}
    for d_str, cmap in (ledger.get("daily_counts") or {}).items():
        if d_str < before_date and isinstance(cmap, dict):
            for kana, cnt in cmap.items():
                if int(cnt) > 0:
                    days_map[kana] = days_map.get(kana, 0) + 1
    return days_map


def get_active_relearn_holds(ledger: dict, before_date: str = "") -> set[str]:
    """Words flagged as '重学' in post-listening review stay in gentle bridge mode until heard >=2 times after hold date."""
    holds = ledger.get("relearn_hold") or {}
    daily = ledger.get("daily_counts") or {}
    active: set[str] = set()
    for kana, hold_date in holds.items():
        if not hold_date:
            continue
        post_hits = 0
        for d_str, cmap in daily.items():
            if d_str > str(hold_date) and (not before_date or d_str < before_date):
                post_hits += int((cmap or {}).get(kana, 0))
        if post_hits < 2:
            active.add(kana)
    return active


def flag_relearn_words(words_or_kanas: list[str], flag_date: str) -> list[str]:
    """Persist post-listening '重学' flags into podcast_vocab_ledger.json so next episode re-bridges them gently."""
    if not words_or_kanas:
        return []
    kanji_to_kana = {e["kanji"]: e["kana"] for e in IMMERSION_VOCAB_BANK}
    matched: list[str] = []
    ledger = load_ledger(today_str=flag_date)
    holds = ledger.setdefault("relearn_hold", {})
    changed = False
    for raw in words_or_kanas:
        s = str(raw or "").strip()
        k = s if s in VOCAB_BY_KANA else kanji_to_kana.get(s, "")
        if k and (not holds.get(k) or str(flag_date) >= str(holds.get(k))):
            holds[k] = str(flag_date)
            matched.append(k)
            changed = True
    if changed:
        ledger["words"] = _rebuild_words_summary(ledger)
        os.makedirs(AUDIO_DIR, exist_ok=True)
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
    return matched


def _rebuild_words_summary(ledger: dict) -> dict:
    threshold = max(GRADUATION_THRESHOLD, int(ledger.get("graduation_threshold") or GRADUATION_THRESHOLD))
    min_days = max(MIN_GRADUATION_DAYS, int(ledger.get("min_graduation_days") or MIN_GRADUATION_DAYS))
    daily = ledger.get("daily_counts") or {}
    verified_kanas, recent_fail_kanas = _load_verified_mastery_sets()
    active_holds = get_active_relearn_holds(ledger) | recent_fail_kanas
    sorted_dates = sorted(daily.keys())
    running: dict[str, int] = {}
    days_seen: dict[str, int] = {}
    meta: dict[str, dict] = {}
    for d_str in sorted_dates:
        cmap = daily.get(d_str) or {}
        for kana, cnt in cmap.items():
            cnt_i = int(cnt)
            if cnt_i <= 0:
                continue
            prev = running.get(kana, 0)
            nxt = prev + cnt_i
            running[kana] = nxt
            days_seen[kana] = days_seen.get(kana, 0) + 1
            early_lock = (kana in verified_kanas and nxt >= 3 and days_seen[kana] >= 1)
            can_lock = ((nxt >= threshold and days_seen[kana] >= min_days) or early_lock) and (kana not in active_holds)
            if kana not in meta:
                entry = VOCAB_BY_KANA.get(kana) or {}
                meta[kana] = {
                    "kanji": entry.get("kanji", kana),
                    "zh": entry.get("zh", [get_carrier_zh(kana)]),
                    "tier": entry.get("tier", "n3_core"),
                    "exposures": nxt,
                    "days_seen": days_seen[kana],
                    "status": "locked_ja" if can_lock else "learning",
                    "first_date": d_str,
                    "graduated_date": d_str if can_lock else "",
                    "last_date": d_str,
                }
            else:
                meta[kana]["exposures"] = nxt
                meta[kana]["days_seen"] = days_seen[kana]
                meta[kana]["last_date"] = d_str
                if can_lock and meta[kana]["status"] != "locked_ja":
                    meta[kana]["status"] = "locked_ja"
                    meta[kana]["graduated_date"] = d_str
                elif kana in active_holds:
                    meta[kana]["status"] = "learning"
    return meta


def save_ledger(ledger: dict, today_str: str, today_counts: dict[str, int]) -> dict:
    if not isinstance(ledger.get("daily_counts"), dict):
        ledger["daily_counts"] = {}
    ledger["graduation_threshold"] = max(GRADUATION_THRESHOLD, int(ledger.get("graduation_threshold") or GRADUATION_THRESHOLD))
    ledger["min_graduation_days"] = max(MIN_GRADUATION_DAYS, int(ledger.get("min_graduation_days") or MIN_GRADUATION_DAYS))
    ledger["daily_counts"][today_str] = {k: int(v) for k, v in sorted(today_counts.items()) if int(v) > 0}
    ledger["updated_date"] = today_str
    ledger["words"] = _rebuild_words_summary(ledger)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
    return ledger


def _protected_ranges(text: str, boundary_re: re.Pattern | None = None) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for m in PROTECTED_SPAN_RE.finditer(text):
        ranges.append((m.start(), m.end()))
    for m in SWAP_TOKEN_RE.finditer(text):
        ranges.append((m.start(), m.end()))
    if boundary_re is not None:
        for m in boundary_re.finditer(text):
            ranges.append((m.start(), m.end()))
    return ranges


def _overlaps(a: int, b: int, ranges: list[tuple[int, int]]) -> bool:
    for r0, r1 in ranges:
        if a < r1 and b > r0:
            return True
    return False


def _is_safe_match(text: str, start: int, end: int, entry: dict, prot: list[tuple[int, int]]) -> bool:
    if _overlaps(start, end, prot):
        return False
    prev_ch = text[start - 1] if start > 0 else ""
    next_ch = text[end] if end < len(text) else ""
    fb = entry.get("forbid_before") or ""
    if fb and prev_ch and re.match(fb, prev_ch):
        return False
    fa = entry.get("forbid_after") or ""
    if fa and next_ch and re.match(fa, next_ch):
        return False
    # Never replace inside a 4-character idiom/compound where the word is glued directly inside
    # a known proper-name suffix (e.g. `省`, `庁`, `館`, `社`, `党`, `会`, `局`, `院`, `学`)
    if next_ch in "省厅馆社党局院学界家主义":
        return False
    # For dual verb/noun Chinese words (设计/研究/习惯/努力/发现/...), ONLY swap in genuine noun slots!
    if entry.get("kana") in DUAL_VERB_NOUN_KANAS:
        if next_ch and VERB_USE_AFTER_RE.match(next_ch):
            return False
        if prev_ch and VERB_USE_BEFORE_RE.match(prev_ch):
            return False
    # Never replace immediately adjacent to kana
    if prev_ch and re.match(r"[\u3040-\u30ff]", prev_ch):
        return False
    if next_ch and re.match(r"[\u3040-\u30ff]", next_ch):
        return False
    return True


def _is_clean_bridge_slot(text: str, end: int) -> bool:
    after = text[end : end + 1]
    return bool(BRIDGE_AFTER_OK_RE.match(after))


def apply_immersion_to_stories(
    story_blocks: list[dict],
    today_str: str,
    salon_stories: list[dict] | None = None,
    mandarin_boundary_re: re.Pattern | None = None,
    commit_ledger: bool = True,
    ledger_override: dict | None = None,
) -> tuple[list[dict], dict]:
    """
    Transforms `story_blocks` (modifying each block's `raw_turns` copy cleanly) according to the
    cumulative 5-hit Japanese graduation ledger:
      - `prior_E >= 5` (`locked_ja`): always direct seamless `{{carrier|kana}}`
      - `1 <= prior_E < 5` (`learning`): brief bridge on 1st clean mention if `prior_E <= 2`, then direct `{{carrier|kana}}`
      - `prior_E == 0` (`new`, top `DAILY_NEW_BUDGET` words in today's episode):
        1st clean mention bridges `{zh}也就是{{carrier|kana}}` (or stays plain Chinese in tight modifier),
        2nd+ mentions in the SAME episode switch directly to `{{carrier|kana}}`!
    Returns `(updated_blocks, report_dict)`.
    """
    ledger = ledger_override if ledger_override is not None else load_ledger(salon_stories=salon_stories, today_str=today_str)
    threshold = max(GRADUATION_THRESHOLD, int(ledger.get("graduation_threshold") or GRADUATION_THRESHOLD))
    min_days = max(MIN_GRADUATION_DAYS, int(ledger.get("min_graduation_days") or MIN_GRADUATION_DAYS))
    new_budget = int(ledger.get("daily_new_budget") or DAILY_NEW_BUDGET)
    prior_counts = compute_prior_counts(ledger, before_date=today_str)
    prior_days = compute_prior_days(ledger, before_date=today_str)
    verified_kanas, recent_fail_kanas = _load_verified_mastery_sets()
    active_holds = get_active_relearn_holds(ledger, before_date=today_str) | recent_fail_kanas
    weak_words = _load_active_weak_words()
    user_prio = set(ledger.get("user_priority_words") or ["じしょ"])

    # Only eligible Chinese-to-Japanese promotion entries (exclude overly elementary N5 words from NEW budget)
    promo_entries = [e for e in IMMERSION_VOCAB_BANK if e["tier"] != "n4_existing"]
    # Build longest-first surface -> entry lookup
    zh_to_entry: dict[str, dict] = {}
    for ent in promo_entries:
        for z in ent["zh"]:
            if z not in zh_to_entry:
                zh_to_entry[z] = ent
    all_zh_forms = sorted(zh_to_entry.keys(), key=len, reverse=True)
    zh_scan_re = re.compile("|".join(re.escape(z) for z in all_zh_forms)) if all_zh_forms else None

    # Pass 1: Audit today's raw stories to see which words naturally occur and how often!
    ep_zh_hits: dict[str, int] = {}
    ep_bridgeable_hits: dict[str, int] = {}
    existing_ja_hits: dict[str, int] = {}

    for b_idx, blk in enumerate(story_blocks):
        turns = blk.get("raw_turns") or []
        for t_idx, (spk, txt_raw) in enumerate(turns):
            txt = str(txt_raw)
            for tok in JA_KANA_TOKEN_RE.findall(txt):
                if tok in VOCAB_BY_KANA:
                    existing_ja_hits[tok] = existing_ja_hits.get(tok, 0) + 1
            if not zh_scan_re or BROADCAST_FRAME_RE.search(txt) or GRAMMAR_META_RE.search(txt):
                continue
            if b_idx == 0 and t_idx == 0:
                continue
            prot = _protected_ranges(txt, mandarin_boundary_re)
            for m in zh_scan_re.finditer(txt):
                ent = zh_to_entry[m.group(0)]
                if _is_safe_match(txt, m.start(), m.end(), ent, prot):
                    k = ent["kana"]
                    ep_zh_hits[k] = ep_zh_hits.get(k, 0) + 1
                    if _is_clean_bridge_slot(txt, m.end()):
                        ep_bridgeable_hits[k] = ep_bridgeable_hits.get(k, 0) + 1

    # Decide active word sets for today:
    # - Natural passive audio lock requires >= 8 hits across >= 3 distinct days (Uchihara/Webb 2019/2023)
    # - Closed-loop verified mastery (true-green Vocab or verified Post-Listening Review pass) unlocks early (>= 3 hits across >= 1 day)!
    locked_set = {
        k for k, c in prior_counts.items()
        if (
            (c >= threshold and prior_days.get(k, 0) >= min_days)
            or (k in verified_kanas and c >= 3 and prior_days.get(k, 0) >= 1)
        )
        and k not in active_holds
        and k in VOCAB_BY_KANA
    }
    learning_set = {
        k for k, c in prior_counts.items()
        if c >= 1 and k not in locked_set and k in VOCAB_BY_KANA
    } | {k for k in active_holds if k in VOCAB_BY_KANA}

    # Score candidate brand-new words (`prior_E == 0`) that actually appear in today's stories!
    new_candidates: list[tuple[float, str]] = []
    for k, hit_cnt in ep_zh_hits.items():
        if k in locked_set or k in learning_set:
            continue
        ent = VOCAB_BY_KANA.get(k)
        if not ent or ent["tier"] == "n4_existing":
            continue
        if hit_cnt < 2 and k not in user_prio and ent["kanji"] not in weak_words and k not in weak_words:
            # Prefer words that appear >= 2 times in today's episode so he gets bridge -> direct switch!
            continue
        if ep_bridgeable_hits.get(k, 0) == 0 and hit_cnt < 2:
            continue
        score = 0.0
        if k in user_prio or ent["tier"] == "user_priority":
            score += 120.0
        if k in weak_words or ent["kanji"] in weak_words:
            score += 65.0
        if hit_cnt >= 4:
            score += 42.0
        elif hit_cnt == 3:
            score += 36.0
        elif hit_cnt == 2:
            score += 24.0
        if ep_bridgeable_hits.get(k, 0) >= 1:
            score += 12.0
        # Slight boost for pronunciation-tricky readings (long vowels, sokuon, dakuten, yoon)
        if re.search(r"[っゃゅょがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽー]", k) or re.search(r"(?:おう|えい|うう|ゆう|しょう|ちょう|きゅう|じゅう|りゅう)", k):
            score += 8.0
        # Deterministic tie-breaker by kana so rebuilds are 100% reproducible
        new_candidates.append((score, k))

    new_candidates.sort(key=lambda x: (-x[0], x[1]))
    today_new_set = {k for _, k in new_candidates[:new_budget]}
    active_set = locked_set | learning_set | today_new_set

    # Pass 2: Transform turns sequentially across the episode so early paragraphs introduce
    # (Chinese + Japanese bridge, or plain Chinese in tight modifier) and later paragraphs switch to direct Japanese!
    ep_ja_delivered: dict[str, int] = {}
    ep_bridged: set[str] = set()
    ep_seen_zh: dict[str, int] = {}
    today_final_counts: dict[str, int] = dict(existing_ja_hits)

    # Split a turn into sentences so we respect `MAX_INLINE_PER_SENTENCE` cleanly
    sent_re = re.compile(r"[^。！？]+[。！？]+[”』」）]*|[^。！？]+$")

    new_blocks = []
    for b_idx, blk in enumerate(story_blocks):
        b_copy = dict(blk)
        new_turns = []
        turns = blk.get("raw_turns") or []
        for t_idx, (spk, txt_raw) in enumerate(turns):
            txt = str(txt_raw)
            if (
                not zh_scan_re
                or spk not in ("W", "D", "X")
                or (b_idx == 0 and t_idx == 0)
                or BROADCAST_FRAME_RE.search(txt)
                or GRAMMAR_META_RE.search(txt)
            ):
                new_turns.append((spk, txt))
                continue

            sentences = sent_re.findall(txt) or [txt]
            rebuilt_sents = []
            turn_bridge_used = False

            for sent in sentences:
                # Skip sentences containing a full Japanese demo after colon `：`
                if "：" in sent and len(JA_KANA_TOKEN_RE.findall(sent.split("：", 1)[1])) >= 1:
                    rebuilt_sents.append(sent)
                    continue
                existing_inline_cnt = len(JA_KANA_TOKEN_RE.findall(sent)) + len(SWAP_TOKEN_RE.findall(sent))
                if existing_inline_cnt >= MAX_INLINE_PER_SENTENCE:
                    rebuilt_sents.append(sent)
                    continue

                prot = _protected_ranges(sent, mandarin_boundary_re)
                edits: list[tuple[int, int, str]] = []
                sent_swaps_added = 0
                used_kana_in_sent: set[str] = set()

                for m in zh_scan_re.finditer(sent):
                    if existing_inline_cnt + sent_swaps_added >= MAX_INLINE_PER_SENTENCE:
                        break
                    zh_hit = m.group(0)
                    ent = zh_to_entry[zh_hit]
                    k = ent["kana"]
                    if k not in active_set:
                        continue
                    if not _is_safe_match(sent, m.start(), m.end(), ent, prot):
                        continue

                    prior_e = prior_counts.get(k, 0)
                    deliv = ep_ja_delivered.get(k, 0)
                    seen_plain = ep_seen_zh.get(k, 0)
                    is_clean = _is_clean_bridge_slot(sent, m.end())

                    replacement = None
                    needs_relearn_bridge = (k in active_holds and deliv == 0)
                    if not needs_relearn_bridge and (k in locked_set or (prior_e >= 3 and prior_days.get(k, 0) >= 1) or deliv >= 1):
                        # Already locked, or well into multi-day learning, or already introduced earlier in THIS episode -> DIRECT JAPANESE!
                        replacement = f"{{{{{zh_hit}|{k}}}}}"
                        ep_ja_delivered[k] = deliv + 1
                        today_final_counts[k] = today_final_counts.get(k, 0) + 1
                    elif k in learning_set or k in today_new_set:
                        # First introduction in this episode (or gentle post-review relearn rescue):
                        if is_clean and not turn_bridge_used and k not in used_kana_in_sent:
                            # Natural paired bridge: `{zh}也就是{{zh|kana}}` (e.g., `预算也就是よさん`)!
                            replacement = f"{zh_hit}也就是{{{{{zh_hit}|{k}}}}}"
                            turn_bridge_used = True
                            ep_bridged.add(k)
                            ep_ja_delivered[k] = deliv + 1
                            today_final_counts[k] = today_final_counts.get(k, 0) + 1
                        elif seen_plain >= 1:
                            # We already said it in plain Chinese in an earlier paragraph -> switch directly to Japanese now!
                            replacement = f"{{{{{zh_hit}|{k}}}}}"
                            ep_ja_delivered[k] = deliv + 1
                            today_final_counts[k] = today_final_counts.get(k, 0) + 1
                        else:
                            # Tight modifier slot on 1st mention -> leave as plain Chinese first ("上段先用中文讲")!
                            ep_seen_zh[k] = seen_plain + 1
                            continue

                    if replacement is not None:
                        edits.append((m.start(), m.end(), replacement))
                        sent_swaps_added += 1
                        used_kana_in_sent.add(k)

                if edits:
                    pieces = []
                    pos = 0
                    for e0, e1, rep in edits:
                        pieces.append(sent[pos:e0])
                        pieces.append(rep)
                        pos = e1
                    pieces.append(sent[pos:])
                    rebuilt_sents.append("".join(pieces))
                else:
                    rebuilt_sents.append(sent)

            new_turns.append((spk, "".join(rebuilt_sents)))
        b_copy["raw_turns"] = new_turns
        new_blocks.append(b_copy)

    # Compute cross-day graduation report
    newly_graduated = []
    today_spotlight = []
    for k, cnt in sorted(today_final_counts.items(), key=lambda x: (-x[1], x[0])):
        prev = prior_counts.get(k, 0)
        prev_d = prior_days.get(k, 0)
        tot = prev + cnt
        tot_d = prev_d + (1 if cnt > 0 else 0)
        was_locked = (prev >= threshold and prev_d >= min_days and k not in active_holds)
        now_locked = (tot >= threshold and tot_d >= min_days and k not in active_holds)
        ent = VOCAB_BY_KANA.get(k) or {}
        if not was_locked and now_locked:
            newly_graduated.append({"kana": k, "kanji": ent.get("kanji", k), "zh": ent.get("carrier", k), "total": tot, "days_seen": tot_d})
        if (k in today_new_set or k in active_holds) and ep_ja_delivered.get(k, 0) > 0:
            today_spotlight.append({
                "kana": k,
                "kanji": ent.get("kanji", k),
                "zh": ent.get("carrier", k),
                "hits_today": cnt,
                "total": tot,
                "days_seen": tot_d,
                "status": "locked_ja" if now_locked else "learning",
            })

    if commit_ledger:
        ledger = save_ledger(ledger, today_str, today_final_counts)
    else:
        if ledger_override is not None:
            ledger_override.setdefault("daily_counts", {})[today_str] = dict(today_final_counts)
            ledger_override["words"] = _rebuild_words_summary(ledger_override)
            ledger = ledger_override
        else:
            tmp_daily = dict(ledger.get("daily_counts") or {})
            tmp_daily[today_str] = dict(today_final_counts)
            ledger = dict(ledger, daily_counts=tmp_daily)
            ledger["words"] = _rebuild_words_summary(ledger)

    words_meta = ledger.get("words") or {}
    locked_total = sum(1 for w in words_meta.values() if w.get("status") == "locked_ja")
    learning_total = sum(1 for w in words_meta.values() if w.get("status") == "learning")

    report = {
        "graduation_threshold": threshold,
        "locked_total": locked_total,
        "learning_total": learning_total,
        "today_new_count": len(today_spotlight),
        "today_graduated": newly_graduated[:15],
        "today_spotlight": today_spotlight[:15],
        "today_total_inline_hits": sum(today_final_counts.values()),
        "_today_counts": dict(today_final_counts),
    }
    return new_blocks, report


def commit_episode_counts(today_str: str, today_counts: dict[str, int], salon_stories: list[dict] | None = None) -> dict:
    ledger = load_ledger(salon_stories=salon_stories, today_str=today_str)
    return save_ledger(ledger, today_str, today_counts)


def get_prompt_vocab_brief(today_str: str = "") -> dict:
    """
    Returns a compact prompt-ready brief of Yangfan's locked_ja words, learning words (1-4 hits),
    and explicit priority words (e.g. 辞書/じしょ) for `daily_news_salon_gen.py` & `n2_prep/`.
    """
    ledger = load_ledger(today_str=today_str)
    words = ledger.get("words") or _rebuild_words_summary(ledger)
    locked = [f"{v.get('kanji', k)}({k})" for k, v in sorted(words.items(), key=lambda x: -x[1].get("exposures", 0)) if v.get("status") == "locked_ja"][:30]
    learning = [f"{v.get('kanji', k)}({k}:{v.get('exposures', 0)}/5)" for k, v in sorted(words.items(), key=lambda x: -x[1].get("exposures", 0)) if v.get("status") == "learning"][:20]
    priority = [
        f"{VOCAB_BY_KANA[k]['kanji']}({k})"
        for k in (ledger.get("user_priority_words") or ["じしょ"])
        if k in VOCAB_BY_KANA and (words.get(k) or {}).get("status") != "locked_ja"
    ]
    return {
        "graduation_threshold": int(ledger.get("graduation_threshold") or GRADUATION_THRESHOLD),
        "locked_ja_words": locked,
        "learning_in_progress": learning,
        "priority_to_introduce": priority,
    }


if __name__ == "__main__":
    import datetime
    from radio_dialogue_bank import SALON_STORIES
    import generate_daily_radio as gdr

    sim_ledger = load_ledger(salon_stories=SALON_STORIES, today_str="2026-11-22")
    print(f"Seeded prior dates: {sorted((sim_ledger.get('daily_counts') or {}).keys())}")
    base_d = datetime.date(2026, 11, 22)
    for offset in range(15):
        vnum = 8 + offset
        d = (base_d + datetime.timedelta(days=offset)).isoformat()
        sts = [s for s in SALON_STORIES if s["id"].startswith(f"uchi{vnum}_")]
        if not sts:
            continue
        blks = [{"id": s["id"], "raw_turns": list(s["turns"])} for s in sts]
        out_blks, rep = apply_immersion_to_stories(
            blks,
            d,
            salon_stories=SALON_STORIES,
            mandarin_boundary_re=gdr.MANDARIN_BOUNDARY_RE,
            commit_ledger=False,
            ledger_override=sim_ledger,
        )
        grad_s = [(x["zh"], x["kana"]) for x in rep["today_graduated"][:6]]
        spot_s = [(x["zh"], x["kana"], x["hits_today"]) for x in rep["today_spotlight"][:6]]
        print(f"Day {offset+1:2d} ({d} Vol.{vnum:2d}) | LOCKED={rep['locked_total']:3d} | LEARN={rep['learning_total']:2d} | hits={rep['today_total_inline_hits']:3d} | new={spot_s} | grad={grad_s}")
        if offset < 3:
            shown = 0
            for ob in out_blks:
                for spk, txt in ob["raw_turns"]:
                    if "{{" in txt and "也就是" in txt and shown < 2:
                        print(f"   [BRIDGE] {spk}: {txt[:95]}")
                        shown += 1

