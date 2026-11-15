#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curated Dual-Mode N3 Micro-Chunk Vocabulary Cards + Bilingual Audio Spec (vocab_cards.py).

Cognitive Science Design:
1. Mode B ("kanji_read"): For Kanji words where Chinese readers get meaning for free via visual Kanji
   but fall into Japanese reading traps (long/short vowels, sokuon っ, rendaku 连浊, kun-yomi).
   - Front: Silent Kanji micro-chunk (zero audio spoiler -> forces active reading generation).
   - Reveal: Native Japanese word+chunk audio + crisp Mandarin meaning & reading trap contrast.
2. Mode A ("kana_meaning"): For pure kana verbs, mimetic ~っ~り / ABAB adverbs, and N3 degree adverbs.
   - Front: Native Japanese word+chunk audio + visual micro-chunk -> forces mental meaning recall.
   - Reveal: Crisp Mandarin meaning + twin contrast note.
"""
import re

HAS_KANJI_RE = re.compile(r"[\u4e00-\u9fff]")

VOCAB_CARDS = {
    # ==================== KANJI READING & KUN-YOMI TRAPS (kanji_read) ====================
    "書類": {
        "mode": "kanji_read",
        "chunk_ja": "書類を出す",
        "target": "書類",
        "kana": "しょるい",
        "trap_hl": ["しょ"],
        "trap_tag": "短音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "文件资料 · 提交文件",
        "twin": "短音 しょ 无长音（对比：種類 しゅるい 种类）",
        "ja_speak": "しょるい。しょるいをだす。",
        "zh_speak": "短音しょ，没有长音。",
    },
    "出張": {
        "mode": "kanji_read",
        "chunk_ja": "海外に出張する",
        "target": "出張",
        "kana": "しゅっちょう",
        "trap_hl": ["っ"],
        "trap_tag": "促音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "出差 · 去海外出差",
        "twin": "中间必带促音 っ（对比：主張 しゅちょう 主张，无促音）",
        "ja_speak": "しゅっちょう。かいがいに、しゅっちょうする。",
        "zh_speak": "注意中间有促音。",
    },
    "内緒": {
        "mode": "kanji_read",
        "chunk_ja": "みんなには内緒だ",
        "target": "内緒",
        "kana": "ないしょ",
        "trap_hl": ["しょ"],
        "trap_tag": "短音",
        "zh_opaque": True,
        "pitch": "⓪",
        "zh": "秘密、保密 · 对大家保密",
        "twin": "尾音是短音 しょ，绝不是 しょう 或 しゅ",
        "ja_speak": "ないしょ。みんなには、ないしょだ。",
        "zh_speak": "秘密，保密。尾音是短音しょ。",
    },
    "貯める": {
        "mode": "kanji_read",
        "chunk_ja": "お金を貯める",
        "target": "貯める",
        "kana": "ためる",
        "trap_hl": ["ため"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "攒钱、积攒 · 把钱存起来",
        "twin": "训读 ためる（音读：貯金 ちょきん 存款）",
        "ja_speak": "ためる。おかねをためる。ためる。",
        "zh_speak": "",
    },
    "備える": {
        "mode": "kanji_read",
        "chunk_ja": "地震に備える",
        "target": "備える",
        "kana": "そなえる",
        "trap_hl": ["そな"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "③",
        "zh": "防备、未雨绸缪 · 防备地震",
        "twin": "固定助词用 に（对比：準備する 办具体事务）",
        "ja_speak": "そなえる。じしんにそなえる。そなえる。",
        "zh_speak": "",
    },
    "沈む": {
        "mode": "kanji_read",
        "chunk_ja": "夕日が沈む",
        "target": "沈む",
        "kana": "しずむ",
        "trap_hl": ["しず"],
        "trap_tag": "训读浊音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "下沉、落下；心情低落",
        "twin": "気持ちが沈む（情绪低落）· 浊音 ず",
        "ja_speak": "しずむ。ゆうひがしずむ。しずむ。",
        "zh_speak": "",
    },
    "許す": {
        "mode": "kanji_read",
        "chunk_ja": "失敗を許す",
        "target": "許す",
        "kana": "ゆるす",
        "trap_hl": ["ゆる"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "②",
        "zh": "原谅；允许 · 原谅失误",
        "twin": "時間が許せば（如果时间允许的话）",
        "ja_speak": "ゆるす。しっぱいをゆるす。ゆるす。",
        "zh_speak": "",
    },
    "輝く": {
        "mode": "kanji_read",
        "chunk_ja": "夜空に星が輝く",
        "target": "輝く",
        "kana": "かがやく",
        "trap_hl": ["かがや"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "③",
        "zh": "闪耀、发光 · 夜空星光闪耀",
        "twin": "目が輝く（两眼放光）",
        "ja_speak": "かがやく。よぞらに、ほしがかがやく。かがやく。",
        "zh_speak": "",
    },
    "余る": {
        "mode": "kanji_read",
        "chunk_ja": "料理が余る",
        "target": "余る",
        "kana": "あまる",
        "trap_hl": ["あま"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "②",
        "zh": "剩下、富余 · 饭菜剩下了",
        "twin": "自动词（对比：残る のこる 留下来未走/未用）",
        "ja_speak": "あまる。りょうりがあまる。あまる。",
        "zh_speak": "",
    },
    "慰める": {
        "mode": "kanji_read",
        "chunk_ja": "落ち込む友達を慰める",
        "target": "慰める",
        "kana": "なぐさめる",
        "trap_hl": ["なぐさ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "④",
        "zh": "安慰 · 安慰沮丧的朋友",
        "twin": "训读 な・ぐ・さ・め・る",
        "ja_speak": "なぐさめる。おちこむともだちを、なぐさめる。なぐさめる。",
        "zh_speak": "",
    },
    "任せる": {
        "mode": "kanji_read",
        "chunk_ja": "私に任せてください",
        "target": "任せ",
        "kana": "まかせる",
        "trap_hl": ["まか"],
        "trap_tag": "训读",
        "zh_opaque": True,
        "pitch": "③",
        "zh": "交给、委托 · 请包在我身上",
        "twin": "お任せ（主厨全权搭配）",
        "ja_speak": "まかせる。わたしに、まかせてください。",
        "zh_speak": "交给，包在我身上。",
    },
    "代表": {
        "mode": "kanji_read",
        "chunk_ja": "チームの代表に選ぶ",
        "target": "代表",
        "kana": "だいひょう",
        "trap_hl": ["ひょう"],
        "trap_tag": "不浊",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "代表 · 选为团队代表",
        "twin": "ひょう 清音不连浊（对比：発表 はっぴょう 半浊音）",
        "ja_speak": "だいひょう。チームのだいひょうにえらぶ。",
        "zh_speak": "注意ひょう不浊化。",
    },
    "減る": {
        "mode": "kanji_read",
        "chunk_ja": "体重が減る",
        "target": "減る",
        "kana": "へる",
        "trap_hl": ["へ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "减少；肚子饿 · 体重下降",
        "twin": "おなかが減る（肚子饿）↔ 増える（ふえる 增加）",
        "ja_speak": "へる。たいじゅうがへる。へる。",
        "zh_speak": "",
    },
    "続く": {
        "mode": "kanji_read",
        "chunk_ja": "雨が三日続く",
        "target": "続く",
        "kana": "つづく",
        "trap_hl": ["づ"],
        "trap_tag": "连浊",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "持续、接着 · 雨连下三天",
        "twin": "第二个假名连浊 づ（他动词：続ける つづける）",
        "ja_speak": "つづく。あめがみっかつづく。",
        "zh_speak": "第二个字连浊づ。",
    },
    "囲む": {
        "mode": "kanji_read",
        "chunk_ja": "みんなで食卓を囲む",
        "target": "囲む",
        "kana": "かこむ",
        "trap_hl": ["かこ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "围住、围绕 · 大家围坐餐桌",
        "twin": "周りを囲む（四周围住）",
        "ja_speak": "かこむ。みんなでしょくたくをかこむ。かこむ。",
        "zh_speak": "",
    },
    "仲直り": {
        "mode": "kanji_read",
        "chunk_ja": "けんかして仲直りする",
        "target": "仲直り",
        "kana": "なかなおり",
        "trap_hl": ["なお"],
        "trap_tag": "训读",
        "zh_opaque": True,
        "pitch": "③",
        "zh": "和好、言归于好 · 吵架后和好",
        "twin": "仲がいい（关系好）＋ 直る（恢复）",
        "ja_speak": "なかなおり。けんかして、なかなおりする。",
        "zh_speak": "吵架后和好。",
    },
    "次々に": {
        "mode": "kanji_read",
        "chunk_ja": "次々に質問が出る",
        "target": "次々に",
        "kana": "つぎつぎに",
        "trap_hl": ["つぎつぎ"],
        "trap_tag": "训读不浊",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "接二连三地、陆续 · 问题接连涌出",
        "twin": "读 つぎつぎに（第二个次不额外连浊）",
        "ja_speak": "つぎつぎに。つぎつぎに、しつもんがでる。つぎつぎに。",
        "zh_speak": "",
    },
    "組む": {
        "mode": "kanji_read",
        "chunk_ja": "来月の予定を組む",
        "target": "組む",
        "kana": "くむ",
        "trap_hl": ["く"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "①",
        "zh": "编排、搭档、交叉 · 排定下月日程",
        "twin": "足を組む（翘二郎腿）· ペアを組む（组搭档）",
        "ja_speak": "くむ。らいげつのよていをくむ。くむ。",
        "zh_speak": "",
    },
    "加える": {
        "mode": "kanji_read",
        "chunk_ja": "塩を少し加える",
        "target": "加える",
        "kana": "くわえる",
        "trap_hl": ["くわ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "③",
        "zh": "加入、添加 · 加一点点盐",
        "twin": "他动词 くわえる（自动词：加わる くわわる 参加）",
        "ja_speak": "くわえる。しおをすこしくわえる。くわえる。",
        "zh_speak": "",
    },
    "やり直す": {
        "mode": "kanji_read",
        "chunk_ja": "最初からやり直す",
        "target": "やり直す",
        "kana": "やりなおす",
        "trap_hl": ["なお"],
        "trap_tag": "训读",
        "zh_opaque": True,
        "pitch": "④",
        "zh": "重做、推倒重来 · 从头重做",
        "twin": "Vます干 ＋ 直す ＝ 重新做某事（考え直す 重新考虑）",
        "ja_speak": "やりなおす。さいしょから、やりなおす。",
        "zh_speak": "重做，推倒重来。",
    },
    "疑問": {
        "mode": "kanji_read",
        "chunk_ja": "ルールに疑問を持つ",
        "target": "疑問",
        "kana": "ぎもん",
        "trap_hl": ["ぎ"],
        "trap_tag": "短音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "疑问 · 对规则抱有疑问",
        "twin": "ぎ 短音浊音（疑問に思う 觉得疑惑）",
        "ja_speak": "ぎもん。ルールにぎもんをもつ。",
        "zh_speak": "开头短音ぎ。",
    },
    "恐ろしい": {
        "mode": "kanji_read",
        "chunk_ja": "恐ろしい事故が起きる",
        "target": "恐ろしい",
        "kana": "おそろしい",
        "trap_hl": ["おそ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "④",
        "zh": "可怕的、惊人的 · 发生骇人事故",
        "twin": "比 怖い（こわい）更客观沉重",
        "ja_speak": "おそろしい。おそろしいじこがおきる。おそろしい。",
        "zh_speak": "",
    },
    "指示": {
        "mode": "kanji_read",
        "chunk_ja": "部長の指示に従う",
        "target": "指示",
        "kana": "しじ",
        "trap_hl": ["しじ"],
        "trap_tag": "短音",
        "zh_opaque": False,
        "pitch": "①",
        "zh": "指示、指令 · 听从部长指示",
        "twin": "两个都是短音 しじ（对比：支持 しじ 同音不同字）",
        "ja_speak": "しじ。ぶちょうのしじにしたがう。",
        "zh_speak": "两拍都是短音。",
    },
    "慣れる": {
        "mode": "kanji_read",
        "chunk_ja": "日本の生活に慣れる",
        "target": "慣れる",
        "kana": "なれる",
        "trap_hl": ["な"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "②",
        "zh": "习惯、适应 · 适应日本生活",
        "twin": "前面对象必用助词 に",
        "ja_speak": "なれる。にほんのせいかつになれる。なれる。",
        "zh_speak": "",
    },
    "守る": {
        "mode": "kanji_read",
        "chunk_ja": "約束の時間を守る",
        "target": "守る",
        "kana": "まもる",
        "trap_hl": ["まも"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "②",
        "zh": "遵守；保护 · 遵守约定时间",
        "twin": "ルールを守る（守规矩）· 家族を守る（守护家人）",
        "ja_speak": "まもる。やくそくのじかんをまもる。まもる。",
        "zh_speak": "",
    },
    "増える": {
        "mode": "kanji_read",
        "chunk_ja": "旅行の荷物が増える",
        "target": "増える",
        "kana": "ふえる",
        "trap_hl": ["ふ"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "②",
        "zh": "增加、增多 · 旅行行李变多了",
        "twin": "自动词 ふえる（他动词：増やす ふやす 增加…）",
        "ja_speak": "ふえる。りょこうのにもつがふえる。ふえる。",
        "zh_speak": "",
    },
    "予算": {
        "mode": "kanji_read",
        "chunk_ja": "予算が足りない",
        "target": "予算",
        "kana": "よさん",
        "trap_hl": ["よ"],
        "trap_tag": "短音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "预算 · 预算不够",
        "twin": "よ 短音无う（对比：予想 よそう 预测）",
        "ja_speak": "よさん。よさんがたりない。",
        "zh_speak": "开头短音よ。",
    },
    "遅れる": {
        "mode": "kanji_read",
        "chunk_ja": "会議に５分遅れる",
        "target": "遅れる",
        "kana": "おくれる",
        "trap_hl": ["おく"],
        "trap_tag": "训读",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "迟到、晚点 · 开会迟到五分钟",
        "twin": "迟到对象用助词 に（会議に遅れる）",
        "ja_speak": "おくれる。かいぎにごふんおくれる。おくれる。",
        "zh_speak": "",
    },
    "通勤": {
        "mode": "kanji_read",
        "chunk_ja": "毎日電車で通勤する",
        "target": "通勤",
        "kana": "つうきん",
        "trap_hl": ["つう"],
        "trap_tag": "长音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "上下班通勤 · 每天坐电车通勤",
        "twin": "开头有长音 つう（对比：通学 つうがく 上学）",
        "ja_speak": "つうきん。まいにちでんしゃでつうきんする。",
        "zh_speak": "开头つう有长音。",
    },
    "発表": {
        "mode": "kanji_read",
        "chunk_ja": "審査の結果を発表する",
        "target": "発表",
        "kana": "はっぴょう",
        "trap_hl": ["っぴょ"],
        "trap_tag": "促音+半浊",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "发表、公布 · 公布审查结果",
        "twin": "促音加半浊音 はっぴょう",
        "ja_speak": "はっぴょう。しんさのけっかをはっぴょうする。",
        "zh_speak": "促音加半浊音。",
    },
    "有料": {
        "mode": "kanji_read",
        "chunk_ja": "ここから先は有料だ",
        "target": "有料",
        "kana": "ゆうりょう",
        "trap_hl": ["ゆう", "りょう"],
        "trap_tag": "长音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "收费、付费 · 往前要收费",
        "twin": "两边都是长音 ゆう・りょう ↔ 無料（むりょう 免费）",
        "ja_speak": "ゆうりょう。ここからさきは、ゆうりょうだ。",
        "zh_speak": "两字都是长音。",
    },
    "払う": {
        "mode": "kanji_read",
        "chunk_ja": "カードで代金を払う",
        "target": "払う",
        "kana": "はらう",
        "trap_hl": ["はら"],
        "trap_tag": "训读",
        "zh_opaque": True,
        "pitch": "②",
        "zh": "支付、付钱 · 刷卡付账",
        "twin": "五段动词：払わない（はらわない）· 払って",
        "ja_speak": "はらう。カードでだいきんをはらう。",
        "zh_speak": "支付，付钱。",
    },
    "封筒": {
        "mode": "kanji_read",
        "chunk_ja": "封筒に書類を入れる",
        "target": "封筒",
        "kana": "ふうとう",
        "trap_hl": ["ふう", "とう"],
        "trap_tag": "长音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "信封 · 把文件装进信封",
        "twin": "两拍长音 ふう・とう",
        "ja_speak": "ふうとう。ふうとうに、しょるいをいれる。",
        "zh_speak": "两拍都是长音。",
    },
    "終電": {
        "mode": "kanji_read",
        "chunk_ja": "終電に間に合う",
        "target": "終電",
        "kana": "しゅうでん",
        "trap_hl": ["しゅう"],
        "trap_tag": "长音",
        "zh_opaque": False,
        "pitch": "⓪",
        "zh": "末班电车 · 赶上末班车",
        "twin": "しゅう 有长音 ↔ 始発（しはつ 首班车）",
        "ja_speak": "しゅうでん。しゅうでんにまにあう。",
        "zh_speak": "开头しゅう有长音。",
    },
    "一日中": {
        "mode": "kanji_read",
        "chunk_ja": "一日中雨が降る",
        "target": "一日中",
        "kana": "いちにちじゅう",
        "trap_hl": ["じゅう"],
        "trap_tag": "浊音",
        "zh_opaque": False,
        "pitch": "④",
        "zh": "一整天 · 下了一整天雨",
        "twin": "表「整个期间」读浊音 じゅう（今週中 こんしゅうじゅう）",
        "ja_speak": "いちにちじゅう。いちにちじゅう、あめがふる。",
        "zh_speak": "尾音读浊音じゅう。",
    },
    "前もって": {
        "mode": "kanji_read",
        "chunk_ja": "前もって予約しておく",
        "target": "前もって",
        "kana": "まえもって",
        "trap_hl": ["まえ", "っ"],
        "trap_tag": "训读+促音",
        "zh_opaque": True,
        "pitch": "④",
        "zh": "事先、提前 · 提前订好位",
        "twin": "常与 〜ておく（提前做好准备）呼应",
        "ja_speak": "まえもって。まえもって、よやくしておく。",
        "zh_speak": "事先，提前。",
    },
    "後にして": {
        "mode": "kanji_read",
        "chunk_ja": "印刷は後にして",
        "target": "後にして",
        "kana": "あとにして",
        "trap_hl": ["あと"],
        "trap_tag": "训读",
        "zh_opaque": True,
        "pitch": "①",
        "zh": "先放一放、留到后面再做",
        "twin": "听力先后顺序题头号反转词（先别做这件！）",
        "ja_speak": "あとにして。いんさつは、あとにして。",
        "zh_speak": "先放一放，留到后面做。",
    },
    "暖簾": {
        "mode": "kanji_read",
        "chunk_ja": "老舗の暖簾を守る",
        "target": "暖簾",
        "kana": "のれん",
        "trap_hl": ["のれん"],
        "trap_tag": "熟字训",
        "zh_opaque": True,
        "pitch": "⓪",
        "zh": "暖帘；百年老字号招牌信誉",
        "twin": "特殊熟字训 のれん",
        "ja_speak": "のれん。しにせののれんをまもる。",
        "zh_speak": "门帘，老字号招牌。",
    },

    # ==================== PURE KANA VERBS & ADVERBS (kana_meaning) ====================
    "こっそり": {
        "mode": "kana_meaning",
        "chunk_ja": "夜中にこっそり抜け出す",
        "target": "こっそり",
        "kana": "こっそり",
        "pitch": "③",
        "zh": "悄悄地、偷偷地 · 半夜偷偷溜出去",
        "twin": "对比：ばったり（迎面撞见）· うっかり（一走神忘事）",
        "ja_speak": "こっそり。よなかに、こっそりぬけだす。",
        "zh_speak": "悄悄地，偷偷地。半夜偷偷溜出去。",
    },
    "ばったり": {
        "mode": "kana_meaning",
        "chunk_ja": "街で友達にばったり会う",
        "target": "ばったり",
        "kana": "ばったり",
        "pitch": "③",
        "zh": "迎面偶遇、撞个正着 · 街上偶遇朋友",
        "twin": "铁板搭配：〜にばったり会う（绝不选 こっそり）",
        "ja_speak": "ばったり。まちでともだちに、ばったりあう。",
        "zh_speak": "迎面偶遇，撞个正着。在街上偶遇朋友。",
    },
    "ぎりぎり": {
        "mode": "kana_meaning",
        "chunk_ja": "終電にぎりぎり間に合う",
        "target": "ぎりぎり",
        "kana": "ぎりぎり",
        "pitch": "⓪",
        "zh": "卡着极限、勉强赶上 · 卡点赶上末班车",
        "twin": "对比：ぴったり（严丝合缝不差一秒）",
        "ja_speak": "ぎりぎり。しゅうでんに、ぎりぎりまにあう。",
        "zh_speak": "卡着死线，勉强赶上。卡点赶上末班电车。",
    },
    "うっかり": {
        "mode": "kana_meaning",
        "chunk_ja": "うっかり傘を忘れる",
        "target": "うっかり",
        "kana": "うっかり",
        "pitch": "③",
        "zh": "一不留神、犯迷糊 · 不小心忘了带伞",
        "twin": "对比：すっかり忘れた（忘得一干二净）",
        "ja_speak": "うっかり。うっかりかさをわすれる。",
        "zh_speak": "一不留神，犯迷糊。不小心忘了带伞。",
    },
    "すっかり": {
        "mode": "kana_meaning",
        "chunk_ja": "約束をすっかり忘れた",
        "target": "すっかり",
        "kana": "すっかり",
        "pitch": "③",
        "zh": "完全彻底地 · 忘得一干二净",
        "twin": "也用于季节彻底变化：すっかり春になった",
        "ja_speak": "すっかり。やくそくを、すっかりわすれた。",
        "zh_speak": "完全彻底地。把约定忘得一干二净。",
    },
    "しっかり": {
        "mode": "kana_meaning",
        "chunk_ja": "手すりにしっかりつかまる",
        "target": "しっかり",
        "kana": "しっかり",
        "pitch": "③",
        "zh": "牢牢地、踏实认真地 · 抓紧扶手",
        "twin": "しっかり勉強する（踏实学习）· しっかり者（靠谱的人）",
        "ja_speak": "しっかり。てすりに、しっかりつかまる。",
        "zh_speak": "牢牢地，踏实地。牢牢抓住扶手。",
    },
    "はっきり": {
        "mode": "kana_meaning",
        "chunk_ja": "意見をはっきり言う",
        "target": "はっきり",
        "kana": "はっきり",
        "pitch": "③",
        "zh": "清清楚楚、明确果断 · 把意见说清楚",
        "twin": "富士山がはっきり見える（看得很清楚）",
        "ja_speak": "はっきり。いけんを、はっきりいう。",
        "zh_speak": "清清楚楚，明确果断。把意见明确说出来。",
    },
    "ぴったり": {
        "mode": "kana_meaning",
        "chunk_ja": "靴のサイズがぴったり合う",
        "target": "ぴったり",
        "kana": "ぴったり",
        "pitch": "③",
        "zh": "严丝合缝、恰到好处 · 鞋码正合适",
        "twin": "３時ぴったりに着く（三点整准时到）",
        "ja_speak": "ぴったり。くつのサイズが、ぴったりあう。",
        "zh_speak": "严丝合缝，恰到好处。鞋码正合适。",
    },
    "ぐったり": {
        "mode": "kana_meaning",
        "chunk_ja": "残業でぐったり疲れる",
        "target": "ぐったり",
        "kana": "ぐったり",
        "pitch": "③",
        "zh": "筋疲力尽、瘫软无力 · 加班累瘫了",
        "twin": "对比：ぐっすり眠る（睡得香甜深沉，只修饰睡觉！）",
        "ja_speak": "ぐったり。ざんぎょうで、ぐったりつかれる。",
        "zh_speak": "筋疲力尽，累瘫了。加班累得一点力气都没有。",
    },
    "ぐっすり": {
        "mode": "kana_meaning",
        "chunk_ja": "朝までぐっすり眠る",
        "target": "ぐっすり",
        "kana": "ぐっすり",
        "pitch": "③",
        "zh": "香甜熟睡 · 一觉睡到天亮",
        "twin": "对比：ぐったり（累瘫）· すっきり（醒来神清气爽）",
        "ja_speak": "ぐっすり。あさまで、ぐっすりねむる。",
        "zh_speak": "睡得香甜深沉。一觉睡到天亮。",
    },
    "うっとり": {
        "mode": "kana_meaning",
        "chunk_ja": "美しい音楽にうっとりする",
        "target": "うっとり",
        "kana": "うっとり",
        "pitch": "③",
        "zh": "陶醉、出神着迷 · 听音乐听入迷了",
        "twin": "对比：がっかり（失望泄气）",
        "ja_speak": "うっとり。うつくしいおんがくに、うっとりする。",
        "zh_speak": "陶醉，出神着迷。听美妙的音乐听入迷了。",
    },
    "がっかり": {
        "mode": "kana_meaning",
        "chunk_ja": "試合の結果にがっかりする",
        "target": "がっかり",
        "kana": "がっかり",
        "pitch": "③",
        "zh": "大失所望、泄气 · 对比赛结果很失望",
        "twin": "肩を落としてがっかり（垂头丧气）",
        "ja_speak": "がっかり。しあいのけっかに、がっかりする。",
        "zh_speak": "大失所望，泄气。对比赛结果很失望。",
    },
    "すっきり": {
        "mode": "kana_meaning",
        "chunk_ja": "運動して気分がすっきりした",
        "target": "すっきり",
        "kana": "すっきり",
        "pitch": "③",
        "zh": "神清气爽、利落舒畅 · 运动完浑身通透",
        "twin": "部屋がすっきり片付く（房间收拾得干净利落）",
        "ja_speak": "すっきり。うんどうして、きぶんがすっきりした。",
        "zh_speak": "神清气爽，通透利落。运动完心情舒畅。",
    },
    "そっくり": {
        "mode": "kana_meaning",
        "chunk_ja": "顔が父親にそっくりだ",
        "target": "そっくり",
        "kana": "そっくり",
        "pitch": "③",
        "zh": "一模一样、酷似 · 长得跟父亲一个模子",
        "twin": "对象用助词 に（父親にそっくり）",
        "ja_speak": "そっくり。かおがちちおやに、そっくりだ。",
        "zh_speak": "一模一样，酷似。长相跟父亲一模一样。",
    },
    "がらがら": {
        "mode": "kana_meaning",
        "chunk_ja": "昼間の電車ががらがらだ",
        "target": "がらがら",
        "kana": "がらがら",
        "pitch": "⓪",
        "zh": "空荡荡没人 · 白天的电车空空荡荡",
        "twin": "反义：ぎっしり（塞得满满当当）· 満員（まんいん）",
        "ja_speak": "がらがら。ひるまのでんしゃが、がらがらだ。",
        "zh_speak": "空荡荡没人。白天的电车空空荡荡。",
    },
    "ぎっしり": {
        "mode": "kana_meaning",
        "chunk_ja": "予定がぎっしり詰まる",
        "target": "ぎっしり",
        "kana": "ぎっしり",
        "pitch": "③",
        "zh": "塞得满满当当 · 日程排得满满的",
        "twin": "反义：がらがら（空空荡荡）",
        "ja_speak": "ぎっしり。よていが、ぎっしりつまる。",
        "zh_speak": "塞得满满当当。日程排得密密麻麻。",
    },
    "ばらばら": {
        "mode": "kana_meaning",
        "chunk_ja": "みんなの意見がばらばらだ",
        "target": "ばらばら",
        "kana": "ばらばら",
        "pitch": "⓪",
        "zh": "零散不齐、七零八落 · 大家意见不统一",
        "twin": "ばらばらに座る（分散开坐）",
        "ja_speak": "ばらばら。みんなのいけんが、ばらばらだ。",
        "zh_speak": "零散不齐，不一致。大家的意见各不相同。",
    },
    "ぼろぼろ": {
        "mode": "kana_meaning",
        "chunk_ja": "古い靴がぼろぼろになる",
        "target": "ぼろぼろ",
        "kana": "ぼろぼろ",
        "pitch": "⓪",
        "zh": "破破烂烂；泪珠大颗滚落 · 旧鞋磨破了",
        "twin": "对比：ばらばら（散落不齐）",
        "ja_speak": "ぼろぼろ。ふるいくつが、ぼろぼろになる。",
        "zh_speak": "破破烂烂。旧鞋子穿得破破烂烂。",
    },
    "からから": {
        "mode": "kana_meaning",
        "chunk_ja": "喉がからからに渇く",
        "target": "からから",
        "kana": "からから",
        "pitch": "⓪",
        "zh": "干透了、渴得冒烟 · 嗓子干得要命",
        "twin": "固定搭配：喉がからからだ",
        "ja_speak": "からから。のどがからからにかわく。",
        "zh_speak": "干透了，渴得冒烟。嗓子干得要命。",
    },
    "ぶらぶら": {
        "mode": "kana_meaning",
        "chunk_ja": "休日に街をぶらぶら歩く",
        "target": "ぶらぶら",
        "kana": "ぶらぶら",
        "pitch": "①",
        "zh": "悠闲溜达闲逛 · 周末在街上闲逛",
        "twin": "对比：うろうろ（迷路或可疑地来回转悠，带焦虑感）",
        "ja_speak": "ぶらぶら。きゅうじつにまちを、ぶらぶらあるく。",
        "zh_speak": "悠闲溜达，闲逛。休息日在街上随便逛逛。",
    },
    "うろうろ": {
        "mode": "kana_meaning",
        "chunk_ja": "道に迷ってうろうろする",
        "target": "うろうろ",
        "kana": "うろうろ",
        "pitch": "①",
        "zh": "迷茫徘徊、团团转 · 迷路了来回打转",
        "twin": "对比：ぶらぶら（惬意散步闲逛）",
        "ja_speak": "うろうろ。みちにまよって、うろうろする。",
        "zh_speak": "徘徊，来回打转。迷路了在原地团团转。",
    },
    "だんだん": {
        "mode": "kana_meaning",
        "chunk_ja": "春になってだんだん暖かくなる",
        "target": "だんだん",
        "kana": "だんだん",
        "pitch": "①",
        "zh": "渐渐地、缓步变化 · 天气渐渐变暖",
        "twin": "对比：どんどん（势头迅猛接连推进，如仕事がどんどん進む）",
        "ja_speak": "だんだん。はるになって、だんだんあたたかくなる。",
        "zh_speak": "渐渐地，一步步平缓变化。入春后渐渐变暖和。",
    },
    "どんどん": {
        "mode": "kana_meaning",
        "chunk_ja": "仕事がどんどん進む",
        "target": "どんどん",
        "kana": "どんどん",
        "pitch": "①",
        "zh": "势头猛进、接二连三 · 工作飞快推进",
        "twin": "对比：だんだん（缓慢渐进变化）",
        "ja_speak": "どんどん。しごとが、どんどんすすむ。",
        "zh_speak": "接二连三，势头猛进。工作飞快往前推进。",
    },
    "そろそろ": {
        "mode": "kana_meaning",
        "chunk_ja": "夜遅いのでそろそろ失礼します",
        "target": "そろそろ",
        "kana": "そろそろ",
        "pitch": "①",
        "zh": "差不多到点该…了 · 时间不早该告辞了",
        "twin": "日常高频开场：そろそろ行きましょう（差不多该走了）",
        "ja_speak": "そろそろ。よるおそいので、そろそろしつれいします。",
        "zh_speak": "差不多到时间该做某事了。时间不早了，我该告辞了。",
    },
    "いよいよ": {
        "mode": "kana_meaning",
        "chunk_ja": "明日はいよいよ試験本番だ",
        "target": "いよいよ",
        "kana": "いよいよ",
        "pitch": "②",
        "zh": "终于到了紧要关头 · 明天终于要正式考试了",
        "twin": "对比：やっと（久等受苦后好不容易才等到过去结果）",
        "ja_speak": "いよいよ。あしたはいよいよ、しけんほんばんだ。",
        "zh_speak": "终于到了关键时刻。明天终于要正式考试了。",
    },
    "めったに": {
        "mode": "kana_meaning",
        "chunk_ja": "平日はめったに外食しない",
        "target": "めったに",
        "kana": "めったに",
        "pitch": "①",
        "zh": "极少、难得（句尾必配否定） · 工作日很少外食",
        "twin": "铁律呼应：めったに〜ない（极少…）",
        "ja_speak": "めったに。へいじつは、めったにがいしょくしない。",
        "zh_speak": "极少，难得，后面必须接否定。工作日很少在外面吃。",
    },
    "せっかく": {
        "mode": "kana_meaning",
        "chunk_ja": "せっかく来たのに閉まっていた",
        "target": "せっかく",
        "kana": "せっかく",
        "pitch": "⓪",
        "zh": "好不容易、难得一番好意 · 白跑一趟关门了",
        "twin": "常配 〜のに（可惜辜负了）或 〜だから（难得…就好好利用）",
        "ja_speak": "せっかく。せっかくきたのに、しまっていた。",
        "zh_speak": "好不容易，难得。好不容易跑来却关门了。",
    },
    "わざわざ": {
        "mode": "kana_meaning",
        "chunk_ja": "雨の中わざわざ来てくれた",
        "target": "わざわざ",
        "kana": "わざわざ",
        "pitch": "①",
        "zh": "专程、特意费心 · 冒雨专程赶来",
        "twin": "对比：せっかく（重在珍贵机会别浪费）· わざと（故意使坏）",
        "ja_speak": "わざわざ。あめのなか、わざわざきてくれた。",
        "zh_speak": "专程，特意费心跑一趟。冒着雨专程赶过来。",
    },
    "やっと": {
        "mode": "kana_meaning",
        "chunk_ja": "３０分待ってやっとバスが来た",
        "target": "やっと",
        "kana": "やっと",
        "pitch": "⓪",
        "zh": "久等之后好不容易终于 · 等半小时车终于来了",
        "twin": "只用于正面期盼终于实现（对比：いよいよ 未来关键时刻来临）",
        "ja_speak": "やっと。さんじゅっぷんまって、やっとバスがきた。",
        "zh_speak": "久等之后，好不容易终于。等了半小时公交车终于来了。",
    },
    "つい": {
        "mode": "kana_meaning",
        "chunk_ja": "夜中に甘い物をつい食べてしまう",
        "target": "つい",
        "kana": "つい",
        "pitch": "①",
        "zh": "不知不觉、没忍住 · 半夜没忍住吃了甜食",
        "twin": "常配 〜てしまう（不小心干了后悔的事）",
        "ja_speak": "つい。よなかにあまいものを、ついたべてしまう。",
        "zh_speak": "不知不觉，一时没忍住。半夜没忍住吃了甜食。",
    },
    "ついてない": {
        "mode": "kana_meaning",
        "chunk_ja": "今日は朝から本当についてない",
        "target": "ついてない",
        "kana": "ついてない",
        "pitch": "④",
        "zh": "倒霉、点背、手气差 · 今天一早起就倒霉",
        "twin": "原形：運がついている（走运）→ ついてない（点背）",
        "ja_speak": "ついてない。きょうはあさから、ほんとうについてない。",
        "zh_speak": "倒霉，点背，运气差。今天从早起就真倒霉。",
    },
    "しゃがむ": {
        "mode": "kana_meaning",
        "chunk_ja": "ひざを曲げてしゃがむ",
        "target": "しゃがむ",
        "kana": "しゃがむ",
        "pitch": "⓪",
        "zh": "蹲下 · 弯膝蹲下来",
        "twin": "五段动词：しゃがんで（蹲着）",
        "ja_speak": "しゃがむ。ひざをまげてしゃがむ。",
        "zh_speak": "蹲下，弯下膝盖蹲下来。",
    },
    "かわいがる": {
        "mode": "kana_meaning",
        "chunk_ja": "うちの子犬をかわいがる",
        "target": "かわいがる",
        "kana": "かわいがる",
        "pitch": "④",
        "zh": "疼爱、宠爱、关照 · 宠爱自家小狗",
        "twin": "後輩をかわいがる（关照疼爱后辈）",
        "ja_speak": "かわいがる。うちのこいぬを、かわいがる。",
        "zh_speak": "疼爱，宠爱，关照晚辈或宠物。",
    },
    "わけ": {
        "mode": "kana_meaning",
        "chunk_ja": "遅れたわけを説明する",
        "target": "わけ",
        "kana": "わけ",
        "pitch": "①",
        "zh": "理由、原因；道理 · 解释迟到的原因",
        "twin": "漢字写「訳」：どういうわけか（不知为何）",
        "ja_speak": "わけ。おくれたわけを、せつめいする。",
        "zh_speak": "理由，原因。解释迟到的原因。",
    },
    "やっぱり": {
        "mode": "kana_meaning",
        "chunk_ja": "迷ったけどやっぱり行く",
        "target": "やっぱり",
        "kana": "やっぱり",
        "pitch": "③",
        "zh": "果然；思来想去还是… · 犹豫了但还是去",
        "twin": "口语高频，正式书面体为 やはり",
        "ja_speak": "やっぱり。まよったけど、やっぱりいく。",
        "zh_speak": "果然，或者思来想去最终还是决定去。",
    },
}


_SHINJITAI_TO_ZH = str.maketrans({
    "書": "书", "類": "类", "張": "张", "貯": "贮", "備": "备", "減": "减", "増": "增",
    "続": "续", "終": "终", "電": "电", "駅": "驿", "買": "买", "売": "卖", "読": "读",
    "聞": "闻", "話": "话", "見": "见", "開": "开", "閉": "闭", "帰": "归", "遅": "迟",
    "選": "选", "運": "运", "動": "动", "働": "动", "頼": "赖", "払": "拂", "貸": "贷",
    "返": "返", "変": "变", "決": "决", "調": "调", "覚": "觉", "捨": "舍", "並": "并",
    "残": "残", "渡": "渡", "過": "过", "進": "进", "乗": "乘", "掃": "扫",
    "議": "议", "質": "质", "問": "问", "題": "题", "練": "练", "習": "习", "経": "经",
    "験": "验", "連": "连", "絡": "络", "説": "说", "談": "谈", "約": "约", "準": "准",
    "確": "确", "認": "认", "参": "参", "賛": "赞", "対": "对", "敗": "败", "結": "结",
    "離": "离", "業": "业", "学": "学", "予": "预", "計": "计", "画": "画", "場": "场",
    "関": "关", "係": "系", "特": "特", "別": "别", "簡": "简", "単": "单", "複": "复",
    "雑": "杂", "険": "险", "歴": "历", "済": "济", "際": "际", "来": "来", "時": "时",
    "間": "间", "気": "气", "節": "节", "温": "温", "写": "写", "真": "真",
    "楽": "乐", "薬": "药", "車": "车", "機": "机", "図": "图", "館": "馆", "術": "术",
    "郵": "邮", "銀": "银", "両": "两", "親": "亲", "姉": "姐", "達": "达", "長": "长",
    "課": "课", "医": "医", "試": "试", "宿": "宿", "強": "强", "転": "转", "駐": "驻",
    "飛": "飞", "国": "国", "会": "会", "社": "社", "発": "发", "表": "表", "現": "现",
    "実": "实", "点": "点", "線": "线", "番": "番", "号": "号", "週": "周",
    "曜": "曜", "毎": "每", "当": "当", "本": "本", "体": "体", "頭": "头", "顔": "颜",
    "声": "声", "音": "音", "色": "色", "紙": "纸", "風": "风", "雨": "雨", "雪": "雪",
})

OPAQUE_KANJI_WORDS = {
    "内緒", "暖簾", "風邪", "支度", "案内", "心配", "我慢", "邪魔", "大事", "大変",
    "大丈夫", "大切", "得意", "苦手", "上手", "下手", "勉強", "残業", "授業", "宿題",
    "都合", "お宅", "一体", "一緒", "始発", "手紙", "娘", "お湯", "湯", "汽車", "怪我",
    "留守", "泥棒", "真面目", "素敵", "平気", "夢中", "無理", "無駄", "油断", "自慢",
    "遠慮", "退屈", "迷惑", "気の毒", "当たり前", "仕方がない", "差し支え", "仲直り",
    "やり直す", "前もって", "後にして", "払う", "任せる", "赤ん坊",
}

# Explicit reading-trap overrides for high-frequency N3 Kanji words outside VOCAB_CARDS:
# (trap_hl_substrings, short_tag, zh_opaque)
KANJI_TRAP_OVERRIDES: dict[str, tuple[list[str], str, bool]] = {
    "種類": (["しゅ"], "短音", False),
    "主張": (["しゅ"], "无促音", False),
    "海外出張": (["っ"], "促音", False),
    "海外出張中": (["っ", "ちゅう"], "促音+不浊", False),
    "私用": (["し"], "短音", False),
    "風邪": (["かぜ"], "熟字训", True),
    "半年": (["とし"], "训读", False),
    "夜中": (["よなか"], "训读", False),
    "三日間": (["っ"], "促音", False),
    "今週中": (["じゅう"], "连浊", False),
    "ダイエット中": (["ちゅう"], "不浊", False),
    "野菜嫌い": (["ぎ"], "连浊", False),
    "旅行先": (["さき"], "不浊", False),
    "人々": (["びと"], "连浊", False),
    "友達": (["だち"], "连浊", False),
    "赤ん坊": (["ぼう"], "浊音", True),
    "貯金": (["ちょ"], "短音", False),
    "準備": (["じゅ", "び"], "短音+浊音", False),
    "案内": (["あんない"], "拨音", True),
    "心配": (["ぱい"], "半浊", True),
    "先輩": (["ぱい"], "半浊", False),
    "結婚": (["っ"], "促音", False),
    "結果": (["っ"], "促音", False),
    "出発": (["っ", "ぱ"], "促音+半浊", False),
    "失敗": (["っ", "ぱ"], "促音+半浊", False),
    "一体": (["っ"], "促音", True),
    "一緒": (["っ", "しょ"], "促音+短音", True),
    "将来": (["しょう"], "长音", False),
    "途中": (["と"], "短音", False),
    "無料": (["む", "りょう"], "短+长音", False),
    "始発": (["し"], "短音", True),
    "部長": (["ぶ", "ちょう"], "短+长音", False),
    "課長": (["か", "ちょう"], "短+长音", False),
    "社長": (["しゃ", "ちょう"], "短+长音", False),
    "医者": (["い", "しゃ"], "短音", False),
    "親切": (["せつ"], "短音", False),
    "支度": (["したく"], "熟字训", True),
    "お宅": (["たく"], "短音", True),
    "都合": (["つごう"], "浊+长音", True),
    "大切": (["せつ"], "短音", True),
    "大丈夫": (["じょうぶ"], "浊+长音", True),
    "我慢": (["がまん"], "浊音", True),
    "邪魔": (["じゃま"], "短音", True),
    "得意": (["とく"], "短音", True),
    "苦手": (["にがて"], "熟字训", True),
    "上手": (["じょうず"], "熟字训", True),
    "下手": (["へた"], "熟字训", True),
    "大人": (["おとな"], "熟字训", False),
    "今朝": (["けさ"], "熟字训", False),
    "昨日": (["きのう"], "熟字训", False),
    "明日": (["あした"], "熟字训", False),
    "今日": (["きょう"], "熟字训", False),
    "人数分": (["ずう"], "长音浊音", False),
    "夕飯": (["ゆう", "はん"], "长音+清音", False),
    "大事": (["じ"], "浊音", True),
    "大変": (["へん"], "不浊", True),
    "元気": (["げん", "き"], "浊+清音", True),
    "天気": (["き"], "清音", False),
    "電車": (["でん", "しゃ"], "浊+短音", False),
    "電話": (["でん"], "浊音", False),
    "約束": (["やく", "そく"], "短音", False),
    "連絡": (["れん", "らく"], "短音", False),
    "説明": (["せつ", "めい"], "短+长音", False),
    "相談": (["そう", "だん"], "长音+浊音", False),
    "練習": (["しゅう"], "长音", False),
    "勉強": (["きょう"], "长音", True),
    "残業": (["ざん", "ぎょう"], "浊+长音", True),
    "授業": (["じゅ", "ぎょう"], "短+长音", True),
    "試験": (["し"], "短音", False),
    "宿題": (["しゅく", "だい"], "短+浊音", True),
}

_KANA_GLIDES = set("ゃゅょャュョァィゥェォぁぃぅぇぉ")
_HANDAKU_CHARS = set("ぱぴぷぺぽパピプペポ")
_DAKU_CHARS = set("がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボ")
_OU_LONG_HEADS = set("おこそとのほもよろごぞどぼぽゃゅょ")
_EI_LONG_HEADS = set("えけせてねへめれげぜでべぺ")


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in s)


def _split_kana_moras(k: str) -> list[str]:
    moras: list[str] = []
    i = 0
    while i < len(k):
        ch = k[i]
        if i + 1 < len(k) and k[i + 1] in _KANA_GLIDES:
            moras.append(k[i : i + 2])
            i += 2
        else:
            moras.append(ch)
            i += 1
    return moras


def _infer_zh_opaque(word: str, zh: str, head: str = "") -> bool:
    for cand in (word, head):
        if cand and cand in OPAQUE_KANJI_WORDS:
            return True
    for op in OPAQUE_KANJI_WORDS:
        if len(op) >= 2 and op in word:
            return True
    if not zh:
        return False
    kanji_chars = HAS_KANJI_RE.findall(word)
    if not kanji_chars:
        return True
    norm_zh = zh.translate(_SHINJITAI_TO_ZH)
    for kc in kanji_chars:
        sc = kc.translate(_SHINJITAI_TO_ZH)
        if kc in zh or sc in zh or sc in norm_zh:
            return False
    return True


def analyze_kanji_reading_trap(word: str, kana: str, zh: str = "", head: str = "") -> tuple[list[str], str, bool]:
    """Returns (trap_hl_list, trap_tag, zh_opaque) for any Kanji word or conjugated chunk."""
    word = str(word or "").strip()
    kana = str(kana or "").strip()
    if not word or not kana or not HAS_KANJI_RE.search(word) or kana == word:
        return ([], "", True)

    if word in VOCAB_CARDS and VOCAB_CARDS[word].get("mode") == "kanji_read":
        vc = VOCAB_CARDS[word]
        return (
            list(vc.get("trap_hl") or []),
            str(vc.get("trap_tag") or ""),
            bool(vc.get("zh_opaque", False)),
        )

    if word in KANJI_TRAP_OVERRIDES:
        hl, tag, opq = KANJI_TRAP_OVERRIDES[word]
        return (list(hl), tag, opq)

    if head and head != word:
        if head in VOCAB_CARDS and VOCAB_CARDS[head].get("mode") == "kanji_read":
            vc = VOCAB_CARDS[head]
            cand_hl = [h for h in (vc.get("trap_hl") or []) if h and h in kana]
            if cand_hl:
                return (cand_hl, str(vc.get("trap_tag") or ""), bool(vc.get("zh_opaque", False)))
        if head in KANJI_TRAP_OVERRIDES:
            cand_hl, tag, opq = KANJI_TRAP_OVERRIDES[head]
            valid_hl = [h for h in cand_hl if h and h in kana]
            if valid_hl:
                return (valid_hl, tag, opq)

    zh_opaque = _infer_zh_opaque(word, zh, head)

    # Isolate the Kanji-bearing stem by stripping identical prefix/suffix kana
    w_hira = _kata_to_hira(word)
    k_hira = _kata_to_hira(kana)
    pre = 0
    while pre < len(w_hira) and pre < len(k_hira) and not HAS_KANJI_RE.match(word[pre]) and w_hira[pre] == k_hira[pre]:
        pre += 1
    w_rem = word[pre:]
    k_rem = kana[pre:]
    w_rem_h = w_hira[pre:]
    k_rem_h = k_hira[pre:]

    suf = 0
    while (
        suf < len(w_rem)
        and suf < len(k_rem)
        and not HAS_KANJI_RE.match(w_rem[len(w_rem) - 1 - suf])
        and w_rem_h[len(w_rem_h) - 1 - suf] == k_rem_h[len(k_rem_h) - 1 - suf]
    ):
        suf += 1

    kanji_core = w_rem[: len(w_rem) - suf] if suf else w_rem
    stem_kana = k_rem[: len(k_rem) - suf] if suf else k_rem
    if not stem_kana:
        stem_kana = kana

    moras = _split_kana_moras(stem_kana)
    has_sokuon = ("っ" in stem_kana) or ("ッ" in stem_kana)
    handaku_moras = [m for m in moras if m[0] in _HANDAKU_CHARS]
    daku_moras = [(idx, m) for idx, m in enumerate(moras) if m[0] in _DAKU_CHARS]

    if has_sokuon and handaku_moras:
        soku = "っ" if "っ" in stem_kana else "ッ"
        return ([soku, handaku_moras[0]], "促音+半浊", zh_opaque)
    if has_sokuon:
        soku = "っ" if "っ" in stem_kana else "ッ"
        return ([soku], "促音", zh_opaque)
    if handaku_moras:
        return ([handaku_moras[0]], "半浊", zh_opaque)

    # Kun-yomi verb / i-adj / okurigana stem (e.g. 休ませて -> やす, 入らないで -> はい, 降りそう -> ふ)
    has_okurigana = suf > 0 and not word.endswith(("する", "します", "した", "して", "しない", "できる", "中"))
    kanji_only_len = len(HAS_KANJI_RE.findall(kanji_core))
    if has_okurigana and kanji_only_len == 1 and len(stem_kana) <= 4:
        tag = "训读浊音" if daku_moras else "训读"
        return ([stem_kana], tag, zh_opaque)

    # Check long vowel unit inside stem_kana (e.g. ちょう, しょう, こう, ゆう, つう, せい, けい)
    for idx in range(len(moras) - 1):
        cur_m, nxt_m = moras[idx], moras[idx + 1]
        tail_ch = _kata_to_hira(cur_m[-1])
        nxt_h = _kata_to_hira(nxt_m)
        if nxt_m == "ー" or (nxt_h == "う" and (tail_ch in _OU_LONG_HEADS or tail_ch in "うくすつぬふむゆるぐずづぶぷ")) or (nxt_h == "い" and tail_ch in _EI_LONG_HEADS):
            span = cur_m + nxt_m
            if cur_m[0] in _DAKU_CHARS and idx > 0:
                return ([span], "连浊+长音", zh_opaque)
            return ([span], "长音", zh_opaque)

    # Rendaku / mid-word voicing
    mid_daku = [m for idx, m in daku_moras if idx > 0]
    if mid_daku:
        return ([mid_daku[0]], "连浊", zh_opaque)
    if daku_moras:
        return ([daku_moras[0][1]], "浊音", zh_opaque)

    # Short vowel mora (Chinese speakers often wrongly lengthen 1-2 mora on-yomi like しょ / しゅ / きょ / と)
    first_m = moras[0] if moras else stem_kana[:1]
    return ([first_m], "短音", zh_opaque)


def build_dynamic_vocab_card(word: str, info: dict | None = None, fallback_note: str = "") -> dict:
    """Builds a clean Dual-Mode card for any word in VOCAB_CARDS or tapped from SENTENCE_LEXICON."""
    if word in VOCAB_CARDS:
        c = dict(VOCAB_CARDS[word])
        c["word"] = word
        if c.get("mode") == "kanji_read" and "trap_hl" not in c:
            hl, tag, opq = analyze_kanji_reading_trap(word, c.get("kana", ""), c.get("zh", ""))
            c["trap_hl"] = hl
            c["trap_tag"] = tag
            c["zh_opaque"] = opq
        return c

    info = info or {}
    kana = str(info.get("kana") or word).strip()
    pitch = str(info.get("pitch") or "").strip()
    zh = str(info.get("zh") or "").strip()
    tip = str(info.get("tip") or fallback_note or "").strip()
    head = str(info.get("head") or word).strip()

    is_kanji = bool(HAS_KANJI_RE.search(word)) and (kana != word)
    mode = "kanji_read" if is_kanji else "kana_meaning"

    # Extract a clean Japanese micro-chunk from tip if available (e.g., "手すりにつかまる（抓紧扶手）")
    chunk_ja = word
    twin = tip
    if tip:
        first_seg = tip.split("／")[0].split("↔")[0].strip()
        m_ja = re.match(r"^([\u3040-\u30ff\u4e00-\u9fffー０-９0-9A-Za-z]{3,18})(?:[（(]([^）)]+)[）)])?$", first_seg)
        if m_ja and word[:2] in m_ja.group(1):
            chunk_ja = m_ja.group(1)
            if m_ja.group(2) and m_ja.group(2) not in zh:
                zh = f"{zh} · {m_ja.group(2)}" if zh else m_ja.group(2)
            twin = "" if first_seg == tip else tip

    if head and head != word and head not in twin:
        twin = f"原形 {head}" + (f" · {twin}" if twin else "")

    trap_hl, trap_tag, zh_opaque = ([], "", True)
    if is_kanji:
        trap_hl, trap_tag, zh_opaque = analyze_kanji_reading_trap(word, kana, zh or fallback_note, head)

    clean_zh_voice = re.sub(r"[（()）·/／↔≠＝〜~]", "，", zh).strip(" ，。")
    zh_speak = (f"{clean_zh_voice}。" if clean_zh_voice else "") if (not is_kanji or zh_opaque) else ""

    return {
        "word": word,
        "mode": mode,
        "chunk_ja": chunk_ja,
        "target": word,
        "kana": kana,
        "trap_hl": trap_hl,
        "trap_tag": trap_tag,
        "zh_opaque": zh_opaque,
        "pitch": pitch,
        "zh": zh or fallback_note,
        "twin": twin,
        "ja_speak": f"{kana}。",
        "zh_speak": zh_speak,
    }
