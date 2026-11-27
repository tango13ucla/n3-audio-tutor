#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SLA Linguistics Pack (v86):
  1. 18 Fossilized Classroom Oral-Slip 3-Second Reflex Drills (DeKeyser Skill Acquisition
     + Selinker Anti-Fossilization), mined directly from recurring N3->N2 spoken errors.
  2. 24 Chinese-L1 High-Variability Phonetic Training (HVPT) Minimal-Pair Blind Ear Drills
     (Logan, Lively & Pisoni 1991; Hirata 2015; Shport 2016) covering Voicing (清浊音),
     Gemination (促音), Vowel Length (长短音), and Pitch Accent (高低声调).
  3. 6-Speaker Native Tokyo HVPT Acoustic Persona Profiles (zero foreign accents:
     100% native Tokyo `ja-JP-KeitaNeural` & `ja-JP-NanamiNeural` with pitch/rate/timbre diversity).
  4. Weekend Real-Tutor 3-Phrase Targeted Output Mission Builder (Long Interaction Hypothesis).

100% Zero-PII public study module. Zero em dashes.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

# ==============================================================================
# 1. 6-SPEAKER NATIVE TOKYO HVPT PERSONAS (100% Native Japanese Pitch Accent)
# ==============================================================================
HVPT_SPEAKER_PROFILES: list[dict[str, str]] = [
    {"id": "f_tokyo_clear", "gender": "F", "label": "东京女声 · 标准", "voice": "ja-JP-NanamiNeural", "rate": "+0%", "pitch": "+0Hz", "eq": "equalizer=f=3200:width_type=q:width=1.2:g=1.2"},
    {"id": "m_tokyo_clear", "gender": "M", "label": "东京男声 · 标准", "voice": "ja-JP-KeitaNeural", "rate": "+0%", "pitch": "+0Hz", "eq": "equalizer=f=2400:width_type=q:width=1.2:g=1.0"},
    {"id": "f_tokyo_brisk", "gender": "F", "label": "职场女同事 · 轻快", "voice": "ja-JP-NanamiNeural", "rate": "+10%", "pitch": "+6Hz", "eq": "highpass=f=120,equalizer=f=3800:width_type=q:width=1.4:g=2.0"},
    {"id": "m_tokyo_deep", "gender": "M", "label": "资深前辈 · 低沉", "voice": "ja-JP-KeitaNeural", "rate": "-5%", "pitch": "-7Hz", "eq": "equalizer=f=220:width_type=q:width=1.1:g=2.5,lowpass=f=6800"},
    {"id": "f_tokyo_warm", "gender": "F", "label": "咖啡馆女声 · 松弛", "voice": "ja-JP-NanamiNeural", "rate": "+5%", "pitch": "-5Hz", "eq": "equalizer=f=280:width_type=q:width=1.2:g=1.8,lowpass=f=7200"},
    {"id": "m_tokyo_fast", "gender": "M", "label": "东京电台男声 · 偏快", "voice": "ja-JP-KeitaNeural", "rate": "+12%", "pitch": "+5Hz", "eq": "highpass=f=100,equalizer=f=3000:width_type=q:width=1.3:g=1.8"},
]


# ==============================================================================
# 2. 18 ANTI-FOSSILIZATION 3-SECOND ORAL REFLEX DRILLS
# ==============================================================================
# Directly attacks real-life N4/N3 spoken slips that survive multiple-choice mastery.
FOSSIL_SLIP_DRILLS: list[dict[str, Any]] = [
    {
        "id": "SL01",
        "category": "形容词过去",
        "cue_zh": "好酸啊，用礼貌过去式说「很酸」",
        "prompt_hint": "酸っぱい（过去）",
        "target_ja": "酸っぱかったです",
        "target_kana": "すっぱかったです",
        "accept_kana": ["すっぱかったです", "すっぱかった"],
        "traps": {
            "すっぱいでした": "い形容词过去绝不能直接加でした，必须去い变かった再加です：すっぱかったです。",
            "すっぱいかったです": "要把词尾的い去掉再加かったです：すっぱかったです。",
        },
        "rule_zh": "い形容词变过去，去い加かったです，绝不说酸っぱいでした。",
        "speaker_idx": 0,
    },
    {
        "id": "SL02",
        "category": "形容词过去",
        "cue_zh": "那道菜很辣，用礼貌过去式说「很辣」",
        "prompt_hint": "辛い（过去）",
        "target_ja": "辛かったです",
        "target_kana": "からかったです",
        "accept_kana": ["からかったです", "からかった"],
        "traps": {
            "からいでした": "い形容词过去不接でした，要去い变からかったです。",
        },
        "rule_zh": "辛い是い形容词，过去式直出からかったです。",
        "speaker_idx": 1,
    },
    {
        "id": "SL03",
        "category": "形容词过去",
        "cue_zh": "小时候非常喜欢，用礼貌过去式说「非常喜欢」",
        "prompt_hint": "大好き（过去）",
        "target_ja": "大好きでした",
        "target_kana": "だいすきでした",
        "accept_kana": ["だいすきでした", "だいすきだった"],
        "traps": {
            "だいすきかったです": "好き、大好き是な形容词，过去式用でした，绝不加かった。",
        },
        "rule_zh": "大好き是な形容词，过去式直出だいすきでした，不加かった。",
        "speaker_idx": 2,
    },
    {
        "id": "SL04",
        "category": "接续防多の",
        "cue_zh": "「睡觉的时候」用日语怎么说？",
        "prompt_hint": "寝る ＋ 時",
        "target_ja": "寝る時",
        "target_kana": "ねるとき",
        "accept_kana": ["ねるとき", "ねるときは", "ねるときに"],
        "traps": {
            "ねるのとき": "动词直接连「時」，中间绝不能插「の」，直接说ねるとき。",
        },
        "rule_zh": "动词接時绝不加の，直接一口气念ねるとき。",
        "speaker_idx": 3,
    },
    {
        "id": "SL05",
        "category": "接续防多の",
        "cue_zh": "「运动过度的时候」用日语怎么说？",
        "prompt_hint": "しすぎた ＋ 時",
        "target_ja": "しすぎた時",
        "target_kana": "しすぎたとき",
        "accept_kana": ["しすぎたとき", "しすぎたときは", "しすぎたときに", "うんどうしすぎたとき"],
        "traps": {
            "しすぎたのとき": "动词た形接時同样绝不加の，直接说しすぎたとき。",
        },
        "rule_zh": "不管原形还是た形，动词碰上時一律不加の。",
        "speaker_idx": 4,
    },
    {
        "id": "SL06",
        "category": "动词名词化",
        "cue_zh": "「阅读是没问题的」用日语怎么说？",
        "prompt_hint": "読む ＋ は大丈夫",
        "target_ja": "読むのは大丈夫",
        "target_kana": "よむのはだいじょうぶ",
        "accept_kana": ["よむのはだいじょうぶ", "よむのはだいじょうぶです", "よむことはだいじょうぶ"],
        "traps": {
            "よむはだいじょうぶ": "动词当主语不能直接撞は，中间必须垫上「の」变成よむのは。",
            "よむはだいじょうぶです": "动词当主语必须加の，说よむのはだいじょうぶです。",
        },
        "rule_zh": "动词短语当主语，必须先加の或こと名词化：よむのは大丈夫。",
        "speaker_idx": 5,
    },
    {
        "id": "SL07",
        "category": "わけ接续",
        "cue_zh": "「难怪这么擅长」用 上手 和 わけだ 怎么说？",
        "prompt_hint": "上手 ＋ わけだ",
        "target_ja": "上手なわけだ",
        "target_kana": "じょうずなわけだ",
        "accept_kana": ["じょうずなわけだ", "じょうずなわけです"],
        "traps": {
            "じょうずわけだ": "な形容词修饰形式名词わけ，中间绝不能漏掉「な」：じょうずなわけだ。",
            "じょうずわけです": "漏了「な」，要念じょうずなわけです。",
        },
        "rule_zh": "な形容词碰上わけ，中间一定卡一颗な：上手なわけだ。",
        "speaker_idx": 0,
    },
    {
        "id": "SL08",
        "category": "わけ接续",
        "cue_zh": "「怪不得看起来很幸福」用 幸せそう 和 わけです 怎么说？",
        "prompt_hint": "幸せそう ＋ わけです",
        "target_ja": "幸せそうなわけです",
        "target_kana": "しあわせそうなわけです",
        "accept_kana": ["しあわせそうなわけです", "しあわせそうなわけだ"],
        "traps": {
            "しあわせそうわけです": "样态そうだ按な形容词算，接わけ必须补上な：しあわせそうなわけです。",
        },
        "rule_zh": "样态そう也是な形容词，接わけ必带な：幸せそうなわけです。",
        "speaker_idx": 1,
    },
    {
        "id": "SL09",
        "category": "使役请假",
        "cue_zh": "向老板礼貌请假：「下周能让我休假吗？」",
        "prompt_hint": "休む（求允许）",
        "target_ja": "休ませていただけませんか",
        "target_kana": "やすませていただけませんか",
        "accept_kana": ["やすませていただけませんか", "らいしゅうやすませていただけませんか", "やすませてください"],
        "traps": {
            "やすみていただけませんか": "是自己休假求对方批准，必须用使役「休ませて」再接いただけませんか。",
            "やすんでいただけませんか": "休んでいただけませんか是请老板去休假，自己请假必用休ませていただけませんか。",
        },
        "rule_zh": "动作是自己做、求对方批准，铁定用使役させていただけませんか。",
        "speaker_idx": 2,
    },
    {
        "id": "SL10",
        "category": "使役请求",
        "cue_zh": "向团队主动请缨：「能让我参加吗？」",
        "prompt_hint": "参加する（求允许）",
        "target_ja": "参加させていただけませんか",
        "target_kana": "さんかさせていただけませんか",
        "accept_kana": ["さんかさせていただけませんか", "さんかさせてください", "さんかさせてもらえますか"],
        "traps": {
            "さんかしていただけませんか": "参加していただけませんか是邀请对方参加，自己想加入要说参加させていただけませんか。",
        },
        "rule_zh": "我想加入求批准，する变させて：参加させていただけませんか。",
        "speaker_idx": 3,
    },
    {
        "id": "SL11",
        "category": "决定漏こと",
        "cue_zh": "「我决定每天运动」用 ことにしました 怎么说？",
        "prompt_hint": "運動する ＋ ことにしました",
        "target_ja": "運動することにしました",
        "target_kana": "うんどうすることにしました",
        "accept_kana": ["うんどうすることにしました", "まいにちうんどうすることにしました", "うんどうすることにした"],
        "traps": {
            "うんどうするにしました": "动词原形不能直接撞にしました，中间必须垫形式名词「こと」。",
        },
        "rule_zh": "决定做某事，动词原形后面先垫こと再接にしました。",
        "speaker_idx": 4,
    },
    {
        "id": "SL12",
        "category": "认知持续体",
        "cue_zh": "问日本朋友：「你知道那部剧吗？」只说「你知道吗？」",
        "prompt_hint": "知る（知道吗）",
        "target_ja": "知っていますか",
        "target_kana": "しっていますか",
        "accept_kana": ["しっていますか", "しってる", "しってますか"],
        "traps": {
            "しりますか": "知道是已经进入脑子的持续状态，绝不说知りますか，要说知っていますか。",
        },
        "rule_zh": "知道是持续状态，开口永远是知っていますか，否定才用知りません。",
        "speaker_idx": 5,
    },
    {
        "id": "SL13",
        "category": "まだ持续否定",
        "cue_zh": "「我还没吃饭呢」用日语怎么说？",
        "prompt_hint": "まだ ＋ 食べる（还没吃）",
        "target_ja": "まだ食べていません",
        "target_kana": "まだたべていません",
        "accept_kana": ["まだたべていません", "まだたべてない", "まだたべていない"],
        "traps": {
            "まだたべません": "まだ表示到现在为止还没做，必须用持续否定ていません，不能说食べません。",
        },
        "rule_zh": "还没做某事，まだ铁定配ていません，绝不直接配ません。",
        "speaker_idx": 0,
    },
    {
        "id": "SL14",
        "category": "す结尾使役被动",
        "cue_zh": "「被逼着在大家面前讲了话」，話す的使役被动礼貌过去怎么说？",
        "prompt_hint": "話す（使役被动过去）",
        "target_ja": "話させられました",
        "target_kana": "はなさせられました",
        "accept_kana": ["はなさせられました", "はなさせられた"],
        "traps": {
            "はなさされました": "す结尾五段动词绝不能缩约成さされる，必须完整念話させられました。",
        },
        "rule_zh": "す结尾动词变使役被动严禁缩约，完整念はなさせられました。",
        "speaker_idx": 1,
    },
    {
        "id": "SL15",
        "category": "自动他动使役",
        "cue_zh": "「赶紧把工作收尾」，带着宾语 仕事を，用 終わらせる 怎么说？",
        "prompt_hint": "仕事を ＋ 終わらせる",
        "target_ja": "仕事を終わらせる",
        "target_kana": "しごとをおわらせる",
        "accept_kana": ["しごとをおわらせる", "しごとをおわらせます", "しごとをおえる", "しごとをおわらせるように"],
        "traps": {
            "しごとをおわる": "終わる是自动词不能带仕事を，人为主动收尾要说仕事を終わらせる。",
        },
        "rule_zh": "前面有仕事を，必须用他动或使役終わらせる，不能接自动词終わる。",
        "speaker_idx": 2,
    },
    {
        "id": "SL16",
        "category": "传闻防多と",
        "cue_zh": "听说「明天好像是晴天」，用 らしい 怎么说？",
        "prompt_hint": "晴れ ＋ らしいです",
        "target_ja": "晴れらしいです",
        "target_kana": "はれらしいです",
        "accept_kana": ["はれらしいです", "あしたははれらしいです", "はれらしい"],
        "traps": {
            "はれだとらしい": "传闻らしい前面绝不能加と，名词也直接去掉だ，说晴れらしいです。",
            "はれとらしいです": "らしい前面不加と，直接接晴れらしいです。",
        },
        "rule_zh": "传闻らしい前不加と、名词去だ，干脆念晴れらしいです。",
        "speaker_idx": 3,
    },
    {
        "id": "SL17",
        "category": "比较差距大",
        "cue_zh": "「好吃得多！」用 ずっと 怎么说？",
        "prompt_hint": "ずっと ＋ 美味しかった",
        "target_ja": "ずっと美味しかったです",
        "target_kana": "ずっとおいしかったです",
        "accept_kana": ["ずっとおいしかったです", "ずっとおいしかった"],
        "traps": {
            "たくさんおいしかったです": "比较程度差距大不用たくさん，一律用ずっと：ずっと美味しかったです。",
        },
        "rule_zh": "比另一个好得多，差距副词永远是ずっと，绝不用たくさん。",
        "speaker_idx": 4,
    },
    {
        "id": "SL18",
        "category": "受益视角",
        "cue_zh": "「当地朋友带我逛了逛」，用受益视角 てもらいました 怎么说？",
        "prompt_hint": "友達に ＋ 案内してもらう",
        "target_ja": "友達に案内してもらいました",
        "target_kana": "ともだちにあんないしてもらいました",
        "accept_kana": ["ともだちにあんないしてもらいました", "あんないしてもらいました", "ともだちにあんないしてもらった"],
        "traps": {
            "ともだちはあんないしました": "别人帮我做了好事，日语里以我为主语用友達に案内してもらいました最地道。",
        },
        "rule_zh": "承蒙朋友帮忙带路，用「对方に ＋ てもらいました」表达受益视角。",
        "speaker_idx": 5,
    },
]


# ==============================================================================
# 3. 24 CHINESE-L1 MINIMAL-PAIR BLIND EAR DRILLS (HVPT)
# ==============================================================================
# Every pair contrasts ONE critical Japanese acoustic cue where Mandarin L1 causes interference.
MINIMAL_PAIR_DRILLS: list[dict[str, Any]] = [
    # --- Voicing / VOT (清浊音: 6 pairs) ---
    {
        "id": "MP01", "axis": "清浊音",
        "a": {"ja": "だった", "kana": "だった", "zh": "曾经是（过去式）", "pitch": "HL"},
        "b": {"ja": "たった", "kana": "たった", "zh": "仅仅 / 站起来了", "pitch": "HL"},
        "tip": "浊音「だ」开口一瞬间声带直接震动；清音「た」只有气流送出。",
        "focus_phoneme": "だ vs た",
    },
    {
        "id": "MP02", "axis": "清浊音",
        "a": {"ja": "合格", "kana": "ごうかく", "zh": "合格、考过", "pitch": "LHHH"},
        "b": {"ja": "広告", "kana": "こうこく", "zh": "广告", "pitch": "LHHH"},
        "tip": "合格开头是浊音「ご」带喉咙震动，后半是「かく」不是「こく」。",
        "focus_phoneme": "ご vs こ",
    },
    {
        "id": "MP03", "axis": "清浊音",
        "a": {"ja": "鍵", "kana": "かぎ", "zh": "钥匙", "pitch": "LH"},
        "b": {"ja": "柿", "kana": "かき", "zh": "柿子", "pitch": "LH"},
        "tip": "第二拍浊音「ぎ」柔和沉下，清音「き」干脆利落。",
        "focus_phoneme": "ぎ vs き",
    },
    {
        "id": "MP04", "axis": "清浊音",
        "a": {"ja": "現金", "kana": "げんきん", "zh": "现金", "pitch": "LHLL"},
        "b": {"ja": "献金", "kana": "けんきん", "zh": "捐款、政治献金", "pitch": "LHHH"},
        "tip": "现金起音是浊音「げん」，千万别清化成「けん」。",
        "focus_phoneme": "げ vs け",
    },
    {
        "id": "MP05", "axis": "清浊音",
        "a": {"ja": "大学", "kana": "だいがく", "zh": "大学", "pitch": "LHHH"},
        "b": {"ja": "退学", "kana": "たいがく", "zh": "退学", "pitch": "LHHH"},
        "tip": "一拍清浊之差，大学变成退学：注意第一拍「だ」喉部发沉。",
        "focus_phoneme": "だ vs た",
    },
    {
        "id": "MP06", "axis": "清浊音",
        "a": {"ja": "技術", "kana": "ぎじゅつ", "zh": "技术", "pitch": "HLL"},
        "b": {"ja": "記述", "kana": "きじゅつ", "zh": "记述、笔答", "pitch": "LHH"},
        "tip": "技术首音浊化「ぎ」且头高降调；记述清音「き」平滑上扬。",
        "focus_phoneme": "ぎ vs き",
    },
    # --- Gemination / Sokuon (促音拍长: 6 pairs) ---
    {
        "id": "MP07", "axis": "促音",
        "a": {"ja": "出張", "kana": "しゅっちょう", "zh": "出差", "pitch": "LHHHH"},
        "b": {"ja": "主張", "kana": "しゅちょう", "zh": "主张、观点", "pitch": "LHHH"},
        "tip": "出差中间必须空出整整一拍憋气停顿「っ」，主张顺滑连读。",
        "focus_phoneme": "しゅっ vs しゅ",
    },
    {
        "id": "MP08", "axis": "促音",
        "a": {"ja": "切手", "kana": "きって", "zh": "邮票", "pitch": "LHH"},
        "b": {"ja": "来て", "kana": "きて", "zh": "请过来", "pitch": "HL"},
        "tip": "切手占三拍（き・っ・て），来て只有两拍（き・て）。",
        "focus_phoneme": "っ停一拍",
    },
    {
        "id": "MP09", "axis": "促音",
        "a": {"ja": "作家", "kana": "さっか", "zh": "作家", "pitch": "LHH"},
        "b": {"ja": "坂", "kana": "さか", "zh": "坡道", "pitch": "LH"},
        "tip": "作家在「さ」之后卡住一拍再爆出「か」，坂两拍直出。",
        "focus_phoneme": "っ停一拍",
    },
    {
        "id": "MP10", "axis": "促音",
        "a": {"ja": "決定", "kana": "けってい", "zh": "决定", "pitch": "LHHH"},
        "b": {"ja": "経て", "kana": "へて", "zh": "经过", "pitch": "HL"},
        "tip": "听中间有没有明显的一拍静音闸门：け・っ・て・い。",
        "focus_phoneme": "けっ vs へ",
    },
    {
        "id": "MP11", "axis": "促音",
        "a": {"ja": "実施", "kana": "じっし", "zh": "实施、实行", "pitch": "LHH"},
        "b": {"ja": "指示", "kana": "しじ", "zh": "指示、指令", "pitch": "HL"},
        "tip": "实施先浊后促「じっし」，指示先清后浊且无促音「しじ」。",
        "focus_phoneme": "じっし vs しじ",
    },
    {
        "id": "MP12", "axis": "促音",
        "a": {"ja": "納得", "kana": "なっとく", "zh": "心服口服、接受", "pitch": "LHHH"},
        "b": {"ja": "納豆", "kana": "なっとう", "zh": "纳豆", "pitch": "LHLL"},
        "tip": "两个都有促音，但納得结尾是短促清脆的「く」，納豆结尾拉长「う」。",
        "focus_phoneme": "く vs う",
    },
    # --- Vowel Length (长短元音: 6 pairs) ---
    {
        "id": "MP13", "axis": "长短音",
        "a": {"ja": "書類", "kana": "しょるい", "zh": "书面文件", "pitch": "LHH"},
        "b": {"ja": "将来", "kana": "しょうらい", "zh": "将来", "pitch": "HLLL"},
        "tip": "書類的「しょ」干脆一拍绝不拖长，将来「しょう」拉满两拍。",
        "focus_phoneme": "しょ vs しょう",
    },
    {
        "id": "MP14", "axis": "长短音",
        "a": {"ja": "おばさん", "kana": "おばさん", "zh": "阿姨", "pitch": "LHHH"},
        "b": {"ja": "おばあさん", "kana": "おばあさん", "zh": "奶奶", "pitch": "LHLLL"},
        "tip": "阿姨的「ば」只有一拍，奶奶「ばあ」拉满两拍，读错容易得罪人。",
        "focus_phoneme": "ば vs ばあ",
    },
    {
        "id": "MP15", "axis": "长短音",
        "a": {"ja": "ビル", "kana": "びる", "zh": "大楼", "pitch": "HL"},
        "b": {"ja": "ビール", "kana": "びーる", "zh": "啤酒", "pitch": "HLL"},
        "tip": "大楼两拍短促「びる」，啤酒首音拉长一拍「びーる」。",
        "focus_phoneme": "ビ vs ビー",
    },
    {
        "id": "MP16", "axis": "长短音",
        "a": {"ja": "雪", "kana": "ゆき", "zh": "雪", "pitch": "LH"},
        "b": {"ja": "勇気", "kana": "ゆうき", "zh": "勇气", "pitch": "HLL"},
        "tip": "雪一拍起音「ゆ・き」，勇气拉满两拍头高降「ゆ・う・き」。",
        "focus_phoneme": "ゆ vs ゆう",
    },
    {
        "id": "MP17", "axis": "长短音",
        "a": {"ja": "ここ", "kana": "ここ", "zh": "这里", "pitch": "LH"},
        "b": {"ja": "高校", "kana": "こうこう", "zh": "高中", "pitch": "LHHH"},
        "tip": "这里两短拍，高中两个长音拉满四拍。",
        "focus_phoneme": "ここ vs こうこう",
    },
    {
        "id": "MP18", "axis": "长短音",
        "a": {"ja": "都合", "kana": "つごう", "zh": "方便与否、安排", "pitch": "LHH"},
        "b": {"ja": "事故", "kana": "じこ", "zh": "事故", "pitch": "HL"},
        "tip": "都合尾音「ごう」拉长，事故两拍短收「じこ」。",
        "focus_phoneme": "ごう vs こ",
    },
    # --- Pitch Accent (高低声调: 6 pairs) ---
    {
        "id": "MP19", "axis": "高低声调",
        "a": {"ja": "雨が降る", "kana": "あめがふる", "zh": "下雨（雨：高→低）", "pitch": "HL"},
        "b": {"ja": "飴を買う", "kana": "あめをかう", "zh": "买糖（糖：低→高平板）", "pitch": "LH"},
        "tip": "雨（あめ）第一拍高、第二拍掉下去；糖（あめ）低起走平不掉。",
        "focus_phoneme": "あ↓め vs あ↑め",
    },
    {
        "id": "MP20", "axis": "高低声调",
        "a": {"ja": "箸を使う", "kana": "はしをつかう", "zh": "用筷子（箸：高→低）", "pitch": "HL"},
        "b": {"ja": "橋を渡る", "kana": "はしをわたる", "zh": "过桥（橋：低→高→掉）", "pitch": "LHL"},
        "tip": "筷子「は」最高立刻跌；桥「は」低起、「し」升高后助词才跌。",
        "focus_phoneme": "は↓し vs は↑し↓",
    },
    {
        "id": "MP21", "axis": "高低声调",
        "a": {"ja": "今すぐ", "kana": "いますぐ", "zh": "现在立刻（今：高→低）", "pitch": "HL"},
        "b": {"ja": "居間で休む", "kana": "いまでやすむ", "zh": "在客厅休息（居間：低→高）", "pitch": "LHL"},
        "tip": "现在「い」高起急降；客厅「い」低起抬到「ま」。",
        "focus_phoneme": "い↓ま vs い↑ま",
    },
    {
        "id": "MP22", "axis": "高低声调",
        "a": {"ja": "熱いお茶", "kana": "あついおちゃ", "zh": "烫茶（熱い：中高降）", "pitch": "LHL"},
        "b": {"ja": "厚い本", "kana": "あついほん", "zh": "厚书（厚い：平板不降）", "pitch": "LHH"},
        "tip": "烫（熱い）在「つ」后掉下来；厚（厚い）一路平板托住不跌。",
        "focus_phoneme": "あつ↓い vs あつ↑い",
    },
    {
        "id": "MP23", "axis": "高低声调",
        "a": {"ja": "帰る時間", "kana": "かえるじかん", "zh": "回家时间（帰る：高→低）", "pitch": "HLL"},
        "b": {"ja": "変える予定", "kana": "かえるよてい", "zh": "更改计划（変える：低→高）", "pitch": "LHH"},
        "tip": "回家「か」高起下降；改变「か」低起走平。",
        "focus_phoneme": "か↓える vs か↑える",
    },
    {
        "id": "MP24", "axis": "高低声调",
        "a": {"ja": "酒を飲む", "kana": "さけをのむ", "zh": "喝酒（酒：低→高平板）", "pitch": "LH"},
        "b": {"ja": "鮭を焼く", "kana": "さけをやく", "zh": "烤三文鱼（鮭：高→低）", "pitch": "HL"},
        "tip": "酒是平板型「さ↑け」；三文鱼是头高型「さ↓け」。",
        "focus_phoneme": "さ↑け vs さ↓け",
    },
]


def slip_audio_basename(sid: str, slot: str) -> str:
    return f"sl_{sid.lower()}_{slot}.mp3"


def mp_audio_basename(mpid: str, side: str) -> str:
    return f"mp_{mpid.lower()}_{side}.mp3"


# ==============================================================================
# 4. WEEKEND REAL-TUTOR 3-PHRASE TARGETED OUTPUT MISSION BUILDER
# ==============================================================================
_CONVERSATION_STARTERS: dict[str, tuple[str, str]] = {
    "〜がちだ": ("最近、忙しくて野菜が不足しがちなんです。", "和老师聊近况或饮食习惯时顺口用出"),
    "〜気味だ": ("ちょっと疲れ気味なので、昨日は早めに寝ました。", "开场寒暄聊身体或工作状态时顺口用出"),
    "〜わけにはいかない": ("大切な仕事なので、途中で投げ出すわけにはいかないんです。", "聊工作项目或学习目标时顺口用出"),
    "〜ざるを得ない": ("予定が重なって、計画を変えざるを得ませんでした。", "聊最近行程变动或工作取舍时顺口用出"),
    "〜どころか": ("忙しくて休むどころか、週末も予定がいっぱいです。", "被问周末过得怎样时自然吐槽用出"),
    "〜てたまらない": ("次の旅行が楽しみでたまらないです。", "聊近期期待的事或日本旅行时用出"),
    "〜させてもらう": ("来週、少し早めに帰らせてもらう予定です。", "聊请假、调班或生活安排时用出"),
    "〜うえで": ("実際に試したうえで、決めようと思っています。", "聊做决定或评估方案时用出"),
    "〜にしたがって": ("練習を続けるにしたがって、少しずつ慣れてきました。", "聊日语或运动进步过程时用出"),
    "〜からこそ": ("難しいからこそ、やりがいがありますよね。", "和老师讨论兴趣、工作或读书感受时用出"),
    "〜に限る": ("疲れた日は、早く寝るに限りますね。", "聊放松方式、美食或生活小窍门时用出"),
    "〜てもかまわない": ("少し遅れてもかまわないですよ。", "和老师约时间或聊规则弹性时用出"),
    "〜ところだ": ("ちょうど今、復習を終えたところです。", "上课刚连线打招呼时顺手用出"),
    "こっそり": ("実はこっそり新しい趣味を始めました。", "聊小秘密或最近悄悄在做的事时用出"),
    "はっきり": ("まだはっきり決まっていないんですが…", "聊尚未敲定的计划时顺口用出"),
    "納得": ("先生の話を聞いて、やっと納得できました。", "听完老师讲解瞬间顺口回应"),
    "ぼろぼろ": ("長く使っているので、靴がもうぼろぼろです。", "聊用了很久的旧物或累瘫状态时用出"),
    "うろうろ": ("知らない街をうろうろ歩くのが好きなんです。", "聊旅行习惯或周末散步时用出"),
    "からから": ("たくさん走ったので、のどがからからです。", "打完球或运动后聊口渴状态时自然用出"),
    "がらがら": ("平日の朝だったので、カフェはがらがらでした。", "聊餐厅、图书馆或电车很空旷时顺口用出"),
    "ぼんやり": ("少し寝不足で、朝から頭がぼんやりしています。", "聊有点犯困发呆或记忆模糊时顺口用出"),
    "そっくり": ("その店の味、地元の料理にそっくりなんです。", "聊两样东西或两个人长得很像时用出"),
    "〜ばかりに": ("確認を省いたばかりに、やり直すことになりました。", "自嘲一件小失误引发麻烦时顺口用出"),
    "〜しだい": ("日程が決まりしだい、すぐご連絡しますね。", "约下次上课或行程敲定时顺口用出"),
    "〜わけがない": ("一度も練習していないのに、急にうまくいくわけがないですよね。", "聊学习或运动心得时带一点幽默感用出"),
    "〜にかけて": ("秋から冬にかけて、この街は一番きれいですね。", "和老师聊季节变化或旅行时间段时用出"),
    "〜おきに": ("このバスは十分おきに来るので便利です。", "聊通勤交通或日常固定频率时用出"),
    "〜をはじめ": ("東京をはじめ、地方の小さな街にも行ってみたいです。", "聊日本各地或兴趣领域举例时用出"),
}


def build_tutor_mission(
    live_state: dict[str, Any],
    night_summary: dict[str, Any] | None = None,
    phase: str = "n3_sprint",
    max_items: int = 3,
) -> list[dict[str, Any]]:
    """
    Pick 3 highest-ROI expressions from this week's live errors, leeches & confusion pairs
    for deliberate real-world use in weekend human classes (Long Interaction Hypothesis).
    """
    ns = night_summary or {}
    cands: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    def _push(prio: int, expr: str, why: str) -> None:
        e = str(expr or "").strip()
        if not e or e in seen or re.match(r"^(?:N3L|N2G|V|T|K|A|Q|G|H)-?\d", e) or "组" in e:
            return
        seen.add(e)
        cands.append((prio, e, why))

    # 1. Active speaking slips
    slips = ((live_state.get("speaking_practice") or {}).get("slips") or {})
    for k in slips.keys():
        _push(100, k, "本周开口略卡，真人课趁热用一次")

    # 2. Top confusion pairs
    for cp in (ns.get("top_confusion_pairs") or []):
        pt = str(cp.get("point") or "")
        wc = str(cp.get("wrong_choice") or "")
        if pt:
            _push(90 + min(8, int(cp.get("count") or 1)), pt, f"近期易混「{wc}」，聊一次彻底分清" if wc else "本周高频易混点")

    # 3. Stubborn vocab leeches
    for w in (ns.get("missed_vocab_words") or []):
        _push(82, w, "近期易忘词，在对话里说出口立刻锁牢")

    # 4. Recent missed points
    for pt in (ns.get("missed_or_unsure_points") or []):
        _push(75, pt, "本周待巩固考点，主动造一句实战")

    # 5. Phase-aware curated fallbacks
    fallbacks = (
        ["〜ざるを得ない", "〜わけにはいかない", "納得"]
        if phase in ("n2_climb", "n1_sprint")
        else ["〜がちだ", "〜どころか", "はっきり", "こっそり", "〜させてもらう"]
    )
    for fb in fallbacks:
        _push(50, fb, "高频地道表达，适合课堂自然带出")

    cands.sort(key=lambda x: (-x[0], x[1]))
    mission: list[dict[str, Any]] = []
    for _prio, expr, why in cands:
        if len(mission) >= max_items:
            break
        if expr in _CONVERSATION_STARTERS:
            starter_ja, cue = _CONVERSATION_STARTERS[expr]
        else:
            starter_ja = f"最近、「{expr.lstrip('〜')}」を使って話してみようと思っています。"
            cue = "找一个和最近生活相关的例子顺口带出来"
        mission.append({
            "id": "TM-" + hashlib.md5(expr.encode("utf-8")).hexdigest()[:6],
            "expr": expr,
            "why": why,
            "starter_ja": starter_ja,
            "cue": cue,
        })
    return mission


# ==============================================================================
# 5. STUDIO MULTI-SPEAKER HVPT AUDIO GENERATOR
# ==============================================================================
async def _synth_edge_to_mp3(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    out_mp3: str,
    eq_filter: str = "",
) -> bool:
    import edge_tts

    ffmpeg_bin = shutil.which("ffmpeg")
    raw_mp3 = out_mp3 + ".raw.mp3" if (eq_filter and ffmpeg_bin) else out_mp3
    for attempt in range(3):
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await comm.save(raw_mp3)
            if os.path.exists(raw_mp3) and os.path.getsize(raw_mp3) > 400:
                if raw_mp3 != out_mp3 and ffmpeg_bin:
                    r = subprocess.run(
                        [ffmpeg_bin, "-y", "-i", raw_mp3, "-af", eq_filter, "-c:a", "libmp3lame", "-b:a", "96k", out_mp3],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    try:
                        os.remove(raw_mp3)
                    except OSError:
                        pass
                    if r.returncode == 0 and os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 400:
                        return True
                else:
                    return True
        except Exception:
            await asyncio.sleep(0.5 * (attempt + 1))
    return False


async def generate_all_sla_studio_audio(base_dir: str, force: bool = False) -> dict[str, Any]:
    """
    Pre-synthesize all studio audio for:
      - 18 Fossilized Oral-Slip drills (ask + teach + HVPT model = 54 MP3s)
      - 24 Chinese-L1 Minimal-Pair HVPT blind ear drills (a + b in varied Tokyo speakers = 48 MP3s)
    Updates `audio/audio_manifest.json` cleanly in-place.
    """
    import json

    audio_dir = os.path.join(base_dir, "audio")
    sla_dir = os.path.join(audio_dir, "sla")
    os.makedirs(sla_dir, exist_ok=True)
    manifest_path = os.path.join(audio_dir, "audio_manifest.json")
    manifest = json.loads(open(manifest_path, encoding="utf-8").read()) if os.path.exists(manifest_path) else {}

    sem = asyncio.Semaphore(5)
    coach_voice = "en-US-BrianMultilingualNeural"

    slip_manifest = dict(manifest.get("fossil_slips") or {})
    mp_manifest = dict(manifest.get("minimal_pairs") or {})
    tasks = []

    async def _gen_one(key_bucket: dict, item_id: str, slot: str, fn: str, txt: str, voice: str, rate: str, pitch: str, eq: str = "") -> None:
        dest = os.path.join(sla_dir, fn)
        rel = f"./audio/sla/{fn}"
        if not force and os.path.exists(dest) and os.path.getsize(dest) > 700:
            key_bucket.setdefault(item_id, {})[slot] = rel
            return
        async with sem:
            ok = await _synth_edge_to_mp3(txt, voice, rate, pitch, dest, eq)
            if ok:
                key_bucket.setdefault(item_id, {})[slot] = rel

    # 1. Fossilized oral-slip drills (54 clips)
    for d in FOSSIL_SLIP_DRILLS:
        sid = d["id"]
        sp = HVPT_SPEAKER_PROFILES[int(d.get("speaker_idx", 0)) % len(HVPT_SPEAKER_PROFILES)]
        tasks.append(_gen_one(slip_manifest, sid, "ask", slip_audio_basename(sid, "ask"), d["cue_zh"], coach_voice, "+6%", "+0Hz"))
        tasks.append(_gen_one(slip_manifest, sid, "teach", slip_audio_basename(sid, "teach"), d["rule_zh"], coach_voice, "+5%", "+0Hz"))
        tasks.append(_gen_one(slip_manifest, sid, "model", slip_audio_basename(sid, "model"), d["target_ja"], sp["voice"], sp["rate"], sp["pitch"], sp["eq"]))

    # 2. Minimal-pair HVPT drills (48 clips, deliberately alternating distinct Tokyo speakers!)
    for idx, mp in enumerate(MINIMAL_PAIR_DRILLS):
        mpid = mp["id"]
        sp_a = HVPT_SPEAKER_PROFILES[(idx * 2) % len(HVPT_SPEAKER_PROFILES)]
        sp_b = HVPT_SPEAKER_PROFILES[(idx * 2 + 1) % len(HVPT_SPEAKER_PROFILES)]
        tasks.append(_gen_one(mp_manifest, mpid, "a", mp_audio_basename(mpid, "a"), mp["a"]["ja"], sp_a["voice"], sp_a["rate"], sp_a["pitch"], sp_a["eq"]))
        tasks.append(_gen_one(mp_manifest, mpid, "b", mp_audio_basename(mpid, "b"), mp["b"]["ja"], sp_b["voice"], sp_b["rate"], sp_b["pitch"], sp_b["eq"]))
        mp_manifest.setdefault(mpid, {})["speaker_a"] = sp_a["label"]
        mp_manifest.setdefault(mpid, {})["speaker_b"] = sp_b["label"]

    await asyncio.gather(*tasks)
    manifest["fossil_slips"] = slip_manifest
    manifest["minimal_pairs"] = mp_manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {
        "fossil_slips": len(slip_manifest),
        "minimal_pairs": len(mp_manifest),
    }


if __name__ == "__main__":
    import sys

    base = os.path.dirname(os.path.abspath(__file__))
    if "--synth" in sys.argv:
        res = asyncio.run(generate_all_sla_studio_audio(base, force="--force" in sys.argv))
        print("SLA Studio HVPT Audio generated:", res)
    else:
        assert len(FOSSIL_SLIP_DRILLS) == 18
        assert len(MINIMAL_PAIR_DRILLS) == 24
        assert len(HVPT_SPEAKER_PROFILES) == 6
        for d in FOSSIL_SLIP_DRILLS:
            assert "—" not in (d["cue_zh"] + d["rule_zh"]), f"Em dash in {d['id']}"
        for mp in MINIMAL_PAIR_DRILLS:
            assert "—" not in mp["tip"], f"Em dash in {mp['id']}"
        print("SLA Linguistics Pack OK: 18 fossil slips + 24 HVPT minimal pairs + 6 native Tokyo speakers")
