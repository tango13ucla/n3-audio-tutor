#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N3 Live Dashboard Data Compiler & Static App Generator
Reads latest Google Drive N3 snapshots/ledgers and compiles 100% point-level live mastery state.
"""
import json, os, re, datetime
from collections import Counter

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.environ.get("N3_SNAP_DIR", os.path.join(OUT_DIR, "snapshots", "extracted_main"))

def norm_g(s):
    s = s.strip()
    s = s.replace("（", "(").replace("）", ")").replace("／", "/")
    return s

def classify_grammar_family(name):
    n = name
    if any(k in n for k in ["くれる", "もらう", "尊敬", "謙譲", "授受", "てほしい"]):
        return "1. 授受・敬語・依頼"
    if any(k in n for k in ["ところ", "最中に", "うちに", "あいだ", "たびに", "とたん", "しだい", "てはじめて", "たあとで", "うえで", "きり", "ぶりに", "ごとに", "までに"]):
        return "2. 時間・局面・順序"
    if any(k in n for k in ["はず", "わけ", "べき", "にちがいない", "とは限らない", "ものだ", "たものだ", "ことだ", "ことにする", "ことになる", "ことになっている", "ことはない", "ないことはない", "しかない"]):
        return "3. 判断・推量・道理・決定"
    if any(k in n for k in ["わりに", "にしては", "にしても", "くせに", "のに", "ながらも", "といっても", "かわりに", "にもかかわらず", "たって", "たとえ", "いくら", "どんなに"]):
        return "4. 逆接・対比・基準外"
    if any(k in n for k in ["にしたがって", "につれて", "とともに", "ば〜ほど", "一方だ", "ばかりだ", "ていく", "てくる", "ようになる", "ようにする", "ようとする"]):
        return "5. 変化・比例・習慣化"
    if any(k in n for k in ["おかげ", "せい", "あまり", "による", "によって", "ため", "た結果", "からこそ", "に基づいて"]):
        return "6. 原因・理由・根拠"
    if any(k in n for k in ["さえ", "ばかり", "だけ", "しか", "こそ", "なんか", "なんて", "をはじめ", "を中心に", "だけでなく", "うえに", "はもちろん"]):
        return "7. 限定・強調・添加"
    if any(k in n for k in ["そうだ", "らしい", "らしく", "みたい", "ように", "ような", "ふり", "っぽい", "がち", "気味", "ということだ", "によると", "って", "ように言う"]):
        return "8. 伝聞・様態・傾向"
    if any(k in n for k in ["ずにはいられない", "ずに", "っぱなし", "かけ", "きる", "きれない", "だらけ", "てしまう", "ちゃう", "ておく", "まま", "てたまらない", "がたい", "やすい", "すぎる", "めったに", "決して", "少しも", "別に"]):
        return "9. アスペクト・感情強制・否定呼応"
    return "10. 対象・立場・条件・その他"

# 1. Parse Chinese meanings from n3_digest.md
meanings = {}
with open(f"{SNAP_DIR}/grammar/n3_digest.md") as f:
    for line in f:
        m = re.match(r"^- ([^:：]+)[：:](.+)$", line.strip())
        if m:
            k = norm_g(m.group(1))
            meanings[k] = m.group(2).strip()
            if not k.startswith("〜"):
                meanings["〜" + k] = m.group(2).strip()

extra_meanings = {
    "〜ことになっている": "（规章/安排）规定是……、定好了要……",
    "〜っぱなし": "一直开着/放任不管（维持某状态不收拾）",
    "〜うえに": "不仅……而且……（同向叠加）",
    "〜だけでなく": "不仅……而且……",
    "〜はもちろん": "……自不必说，（连后项也……）",
    "〜にしたがって": "随着……（一方变化，另一方随之变化）",
    "〜ように言う": "叮嘱/转告让对方做……（间接祈使）",
    "せっかく〜のに": "好不容易/特意……却（白费了）",
    "〜ことはない": "没必要……、用不着……（接ない形则为「也不是不」）",
    "〜にもかかわらず": "尽管……却仍然……",
    "〜としたら": "假设……的话",
}
meanings.update(extra_meanings)

# 2. Parse 136 core grammar points from n3_progress_two_stage.md (10-26 baseline)
grammar_points = {}
with open(f"{SNAP_DIR}/grammar/n3_progress_two_stage.md") as f:
    for line in f:
        if line.startswith("| ") and not line.startswith("| 语法点") and not line.startswith("|---"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                raw_name, old_tier, seq, st = cols[0], cols[1], cols[2], cols[3]
                if "退出" in st:
                    status = "red"   # 答错退出·待补全
                elif ("牢固" in st) and ("不算牢固" not in st) and ("成牢固" not in st) and ("未达成" not in st):
                    status = "green" # 牢固毕业
                else:
                    status = "yellow" # 初步眼熟·差句子实战确认
                k = norm_g(raw_name)
                m_zh = meanings.get(k) or meanings.get(k.lstrip("〜")) or ""
                grammar_points[raw_name] = {
                    "id": f"G-{len(grammar_points)+1:03d}",
                    "name": raw_name,
                    "pool": "核心136点",
                    "family": classify_grammar_family(raw_name),
                    "meaning": m_zh,
                    "status": status,
                    "history": seq,
                    "note": st,
                    "exam_alert": ""
                }

# Add the 11 extra N3 high-freq points tracked by Grammar Bot
extra_init = [
    ("〜ことになっている", "orange", "G019❌→G031✅→G110✅→G167✅(还是要考)→11-12快速✅", "11-08选「还是要考」，制度vs个人决定需再锁死"),
    ("〜っぱなし", "red", "G020✅→11-09快速Q17不知道❌→11-10快速✅", "11-09快速答不知道从初步扣除，待正式句子题收复"),
    ("〜うえに", "green", "G028❌→G032✅→G117❌→G141✅(不用再考了)", "11-07标「不用再考了」牢固毕业，约11-21抽查"),
    ("〜だけでなく", "green", "G113✅(还是要考)→G164✅(不用再考了)", "11-08标「不用再考了」牢固毕业，约11-22抽查"),
    ("〜はもちろん", "green", "11-09正式D6-2✅(不用再考了)", "11-09标「不用再考了」牢固毕业，约11-23抽查"),
    ("〜にしたがって", "orange", "D6-2❌(选ついでに)→G115❌(再选ついでに)→G159❌(三选ついでに!)→11-09快速❌→11-09正式✅(还是要考)", "三次误选ついでに！11-09选「还是要考」重点盯防"),
    ("〜ように言う", "red", "D5-2❌(选ことに)→G036✅→G163✅→11-09快速❌(误选听说そうだ)", "11-09快速与传闻そうだ混淆扣除，待正式复考"),
    ("せっかく〜のに", "green", "G116❌→G161不知道❌→11-11正式D1-2✅(不用再考了)", "11-11标「不用再考了」牢固毕业，约11-25抽查"),
    ("〜ことはない", "red", "G014✅→G114❌", "11-03正式题G114答错，待复考区分「不必」与「ないことはない」"),
    ("〜にもかかわらず", "yellow", "10-26补题D5-1✅", "初步通过，待隔期确认"),
    ("〜としたら", "yellow", "G002(10-25)✅", "初步通过，待隔期句子确认"),
]
for ename, est, ehist, enote in extra_init:
    grammar_points[ename] = {
        "id": f"GX-{len(grammar_points)-135:02d}",
        "name": ename,
        "pool": "真题补漏11点",
        "family": classify_grammar_family(ename),
        "meaning": meanings.get(ename, ""),
        "status": est,
        "history": ehist,
        "note": enote,
        "exam_alert": ""
    }

# 3. Apply post-10-26 updates from n3_grammar_ledger.md up to 2026-11-12 11:36 PT
updates = {
    "〜たびに": ("green", "G027✅→G119❌→G158✅(11-08标「不用再考了」牢固，11-22抽查)"),
    "〜にちがいない": ("green", "9战7败后 G106✅→G160✅(11-08标「不用再考了」牢固，11-22抽查)"),
    "〜べきだ": ("green", "G038❌(选はず)→G105✅→G166✅(11-08标「不用再考了」牢固，11-22抽查)"),
    "〜ないことはない": ("green", "G157❌(选はずがない)→11-10正式D1-1✅(标「不用再考了」牢固，11-24抽查)"),
    "〜わりに": ("green", "G165✅(还是要考)→11-09快速❌(选かわりに)→11-12正式D1-1✅(标「不用再考了」牢固，11-26抽查)"),
    "〜どんなに〜ても": ("yellow", "G120(11-04)✅ 初步掌握"),
    "〜のに": ("yellow", "提前3❌→G107(11-03)✅ 回到初步"),
    "〜かけだ": ("yellow", "G025❌→G035(10-27)✅ 回到初步，待牢固确认"),
    "〜とおりに": ("yellow", "G026❌(选うちに)→G037(10-27)✅→11-08快速✅ 初步掌握"),
    "〜はずがない": ("green", "Q130(10-21)✅ → G030(10-26)✅ 间隔5天连对牢固"),
    # Orange ("还是要考" active points)
    "〜さえ〜ば": ("orange", "G029❌→G034❌→G040✅→11-09正式D1-2✅(选「还是要考」)→11-12快速✅"),
    "〜による／によって": ("orange", "10-25❌→G168(11-08)❌(选にとって)→11-09正式✅(选「还是要考」)→11-12快速✅"),
    "〜ば〜ほど": ("orange", "G118✅→11-09正式D5-2✅(选「还是要考」)"),
    "〜ずにはいられない": ("orange", "四连败后 11-09快速❌→11-09正式✅(选「还是要考」)→11-10快速✅"),
    # Red (Recent wrong / deducted as of 11-12)
    "〜てくれる／もらう": ("red", "G024✅ → 11-12快速Q1「请老师教了我」误选「先生に教えてくれた」❌ 从初步扣除，头号急补！"),
    "〜ところだ": ("red", "G022❌→G033❌→G039✅→11-09正式✅(还是要考) → 11-12快速Q2「〜たところだ」误选「正要」❌ 扣除，头号急补！"),
    "〜わけだ": ("red", "G111(11-03)✅ → G162(11-08)选「不知道」❌ 退出待复考"),
}
for k, (st, note) in updates.items():
    if k in grammar_points:
        grammar_points[k]["status"] = st
        grammar_points[k]["note"] = note

# Flag Mock #2 & Bot-ban alerts
mock_alerts = {
    "〜にしては": "🔥 Bunpro模考2四度牵涉头号混淆磁铁",
    "〜からこそ": "⚠️ 模考2 Q8实错 + 曾被语法Bot误判N2屏蔽",
    "〜ものだ": "⚠️ 模考2 Q17实错 + 曾被语法Bot误判N2屏蔽",
    "〜ことだ（忠告）": "⚠️ 曾被语法Bot误判N2屏蔽",
    "〜どころか": "⚠️ 曾被语法Bot误判N2屏蔽",
    "〜しだい": "⚠️ 曾被语法Bot误判N2屏蔽",
    "〜最中に": "🔥 模考2 Q11实错（误选ところ）",
    "〜ずにはいられない": "🔥 模考2 Q23实错（误选ぎみ）",
    "〜うちに": "🔥 模考2 Q21实错（误选にしては）",
    "〜ついでに": "🔥 模考2 Q13实错 + 多次把にしたがって误选为它",
    "〜にとって": "模考2 Q2实错（误选に対して）",
    "〜に基づいて": "模考2 Q4实错",
    "〜向き": "模考2 Q12 向け/向き混淆",
}
for k, al in mock_alerts.items():
    if k in grammar_points:
        grammar_points[k]["exam_alert"] = al

# 4. Parse all 250 Henkei points from henkei/points.md + henkei/ledger.md
henkei_points = []
cur_cat = ""
cur_sub = ""
with open(f"{SNAP_DIR}/henkei/points.md") as f:
    for line in f:
        l = line.strip()
        if l.startswith("## ") and not l.startswith("## 汇总"):
            cur_cat = l[3:].strip()
        elif l.startswith("### "):
            cur_sub = l[4:].strip()
        elif l.startswith("| ") and re.match(r"^\|\s*[VAKT]-\d{3}\s*\|", l):
            cols = [c.strip() for c in l.strip("|").split("|")]
            pid = cols[0]
            if pid.startswith("T-") and len(cols) >= 4:
                title = f"{cols[1]} ↔ {cols[2]}"
                example = cols[3]
            else:
                title = cols[1]
                example = cols[2] if len(cols) > 2 else ""
            # Determine N3 Exam Priority Tier
            num = int(pid.split("-")[1])
            if pid.startswith("K-") or pid.startswith("T-"):
                tier = "core_n3"
            elif pid.startswith("V-") and (27 <= num <= 63 or num in (69, 85, 86)):
                tier = "core_n3"
            elif pid.startswith("A-") and num >= 38:
                tier = "core_n3"
            else:
                tier = "basic_n5n4"
            henkei_points.append({
                "id": pid,
                "category": cur_cat,
                "subcategory": cur_sub,
                "name": title,
                "example": example,
                "tier": tier,
                "status": "gray",
                "note": "未单测（待按考频抽检）"
            })

henkei_live_map = {
    "V-007": ("green", "11-09 正式 書く→書いて ✅ 标「不用再考了」牢固"),
    "V-018": ("green", "11-12 正式 行く→行かない ✅ 标「不用再考了」牢固"),
    "V-027": ("red", "11-11 正式 読む→読める 误选「読めれる」(ら抜き混淆) ❌；11-12 快速复习✅ 待正式确认"),
    "V-030": ("red", "11-09 正式 来られる ✅(选还是要考) → 11-12 快速误选「来れる」(ら抜き) ❌ 待复考"),
    "V-031": ("red", "ら抜き言葉高频陷阱（来れる/読めれる连续踩坑）"),
    "V-032": ("orange", "11-12 正式 足を踏まれた ✅ 选「还是要考」"),
    "V-037": ("orange", "11-12 正式 薬を飲ませた ✅ 选「还是要考」"),
    "K-001": ("orange", "11-10 & 11-11 正式 いらっしゃる ✅ 两次均选「还是要考」"),
    "K-003": ("red", "11-10 正式 召し上がる ✅(还是要考) → 11-12 快速误判为「谦让语」❌ 从初步扣除！"),
    "K-012": ("red", "11-12 快速「吃喝的谦让语」误选 召し上がる ❌（尊敬/谦让方向颠倒）"),
    "K-041": ("red", "尊敬语与谦让语主语方向颠倒高危点（召し上がる vs いただく）"),
    "T-001": ("red", "11-10 開く他动词误选「開きます」❌；窓を開けたまま ✅(选还是要考)"),
    "T-002": ("red", "11-10 窓を（閉めて）误选自动词「閉まって」❌（を+自动词典型失分）"),
    "T-004": ("red", "11-10 電気を（消して）误选自动词「消えて」❌（第三次 を+自动词错误）"),
    "T-044": ("red", "11-10 落として✅(还是要考) → 11-11 落とす误选「自己掉了」❌ → 11-12 误选可能形「落とせる」❌"),
}
for hp in henkei_points:
    if hp["id"] in henkei_live_map:
        hp["status"], hp["note"] = henkei_live_map[hp["id"]]

# 5. Parse Listening points (403 total, mark core 165)
with open(f"{SNAP_DIR}/points.json") as f:
    l_raw = json.load(f)

overrides = {}
with open(f"{SNAP_DIR}/listening_state/mastery_overrides.jsonl") as f:
    for line in f:
        if line.strip():
            o = json.loads(line)
            overrides[o["point_id"]] = o["choice"]

checks_wrong = set()
checks_seen = Counter()
with open(f"{SNAP_DIR}/listening_state/checks_log.jsonl") as f:
    for line in f:
        if line.strip():
            c = json.loads(line)
            pid = c["point_id"]
            checks_seen[pid] += 1
            if not c["correct"]:
                checks_wrong.add(pid)
            elif pid in checks_wrong:
                # keep note that it was missed before, check latest
                pass

# Get latest check status per point
latest_check = {}
with open(f"{SNAP_DIR}/listening_state/checks_log.jsonl") as f:
    for line in f:
        if line.strip():
            c = json.loads(line)
            latest_check[c["point_id"]] = c["correct"]

srs_latest = {}
with open(f"{SNAP_DIR}/srs_log.jsonl") as f:
    for line in f:
        if line.strip():
            s = json.loads(line)
            for pid in s.get("point_ids", []):
                srs_latest[pid] = s["correct"]

listening_points = []
for idx, p in enumerate(l_raw):
    pid = p["id"]
    is_core = idx < 165 or pid in srs_latest or pid in latest_check or pid in overrides
    ov = overrides.get(pid)
    box = p.get("box", 0)
    if pid in latest_check and not latest_check[pid]:
        st = "red"
        note = f"快速/微题最新答错（{p.get('trap','')}）"
    elif pid in srs_latest and not srs_latest[pid] and box == 0:
        st = "red"
        note = f"正式语音题答错/不知道（{p.get('trap','')}）"
    elif ov == "mastered" or box >= 2:
        st = "green"
        note = "已掌握（标不用再考或连对进Box 2）"
    elif ov == "retest":
        st = "orange"
        note = "已答对但你选了「还是要考」"
    elif box == 1 or (pid in srs_latest and srs_latest[pid]) or (pid in latest_check and latest_check[pid]):
        st = "yellow"
        note = "初步答对，待隔期语音确认"
    else:
        st = "gray"
        note = "未测"
    listening_points.append({
        "id": pid,
        "category": p.get("category", "未分类"),
        "qtype": p.get("qtype", "即時応答"),
        "name": p.get("spoken", pid),
        "full": p.get("full", ""),
        "meaning": p.get("meaning_zh", ""),
        "trap": p.get("trap", ""),
        "is_core165": is_core,
        "status": st,
        "note": note
    })

# 6. Parse Vocab tracked words + categorize
with open(f"{SNAP_DIR}/vocab_state/progress.json") as f:
    v_words = json.load(f)["words"]

def classify_vocab(w):
    if re.fullmatch(r"[ぁ-んー]+", w):
        if "っ" in w and w.endswith("り"):
            return "1. 拟声拟态（〜っ〜り家族）"
        if len(w) == 4 and w[:2] == w[2:]:
            return "2. 叠词副词（ABAB家族）"
        return "3. 纯假名和语动词/副词"
    return "4. 汉字词读音（连浊/长短音/训读）与搭配"

vocab_tracked = []
for w, info in v_words.items():
    if info.get("mastered"):
        st = "green"
    elif info.get("streak", 0) == 0 or info.get("quick_wrong"):
        st = "red"
    else:
        st = "yellow"
    vocab_tracked.append({
        "word": w,
        "category": classify_vocab(w),
        "status": st,
        "seen": info.get("seen", 0) + info.get("quick_seen", 0),
        "wrong": info.get("wrong", 0) + info.get("quick_wrongs", 0),
        "streak": info.get("streak", 0),
        "due": info.get("due") or "已毕业",
        "note": f"累计见 {info.get('seen',0)+info.get('quick_seen',0)} 次｜错 {info.get('wrong',0)+info.get('quick_wrongs',0)} 次｜当前连对 {info.get('streak',0)}"
    })
vocab_tracked.sort(key=lambda x: ({"red":0,"yellow":1,"green":2}[x["status"]], -x["wrong"]))

# Summary counts
g_list = list(grammar_points.values())
g_cnt = Counter(x["status"] for x in g_list)
h_cnt = Counter(x["status"] for x in henkei_points)
h_core_cnt = Counter(x["status"] for x in henkei_points if x["tier"] == "core_n3")
l_core = [x for x in listening_points if x["is_core165"]]
l_cnt = Counter(x["status"] for x in l_core)
v_cnt = Counter(x["status"] for x in vocab_tracked)

payload = {
    "updated_at": "2026-11-12 13:50 PT",
    "exam_date": "2026-12-06",
    "days_left": 24,
    "target_score": "120+ / 180",
    "mocks": [
        {"name": "Bunpro 模考 Set 1", "date": "2026-07-24", "vocab": "30/36 (83%)", "grammar": "21/39 (合并 54%)", "reading": "合并计分", "listening": "17/28 (61%)", "total": "68/103 (66%)", "status": "done"},
        {"name": "Bunpro 模考 Set 2", "date": "2026-10-20", "vocab": "28/36 (78%)", "grammar": "9/23 (39%) 🚨", "reading": "13/16 (81%) ✅", "listening": "19/28 (68%)", "total": "69/103 (67%)", "status": "done"},
        {"name": "Bunpro 模考 Set 3", "date": "进行中 (11/13-14收尾)", "vocab": "30/36 (83%) ✅", "grammar": "待考", "reading": "待考", "listening": "待考", "total": "待合算", "status": "wip"},
        {"name": "官方公式問題集 (2018)", "date": "计划 11/16-17", "vocab": "按需抽测", "grammar": "待限时全卷", "reading": "维持手感", "listening": "待限时全卷", "listening_note": "此前仅拆过問題5", "total": "待考", "status": "todo"},
        {"name": "Bunpro 模考 Set 4", "date": "计划 11/21-22", "vocab": "待考", "grammar": "待考", "reading": "待考", "listening": "待考", "total": "目标 ≥115估分", "status": "todo"},
        {"name": "Bunpro 模考 Set 5", "date": "计划 11/28-29", "vocab": "待考", "grammar": "待考", "reading": "待考", "listening": "待考", "total": "目标 120+估分", "status": "todo"},
    ],
    "summary": {
        "grammar": {"total": len(g_list), "core136": 136, "extra": 11, "counts": dict(g_cnt)},
        "henkei": {"total": len(henkei_points), "core_n3_total": sum(1 for x in henkei_points if x["tier"]=="core_n3"), "basic_total": sum(1 for x in henkei_points if x["tier"]!="core_n3"), "counts": dict(h_cnt), "core_counts": dict(h_core_cnt)},
        "listening": {"total_all": len(listening_points), "core165_total": len(l_core), "counts": dict(l_cnt)},
        "vocab": {"verified_pool": 2746, "bot_target_pool": 1467, "multi_source_core": 409, "active_tracked": len(vocab_tracked), "counts": dict(v_cnt)}
    },
    "grammar_points": g_list,
    "henkei_points": henkei_points,
    "listening_points": listening_points,
    "vocab_tracked": vocab_tracked
}

with open(f"{OUT_DIR}/n3_live_state.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print("=== COMPILED LIVE SUMMARY ===")
print("Grammar (147 total):", dict(g_cnt))
print("  Red list:", [x["name"] for x in g_list if x["status"]=="red"])
print("  Orange list:", [x["name"] for x in g_list if x["status"]=="orange"])
print("  Green list:", [x["name"] for x in g_list if x["status"]=="green"])
print("Henkei (250 total / Core N3):", dict(h_cnt), "Core:", dict(h_core_cnt))
print("Listening (Core pool):", len(l_core), dict(l_cnt))
print("Vocab (46 tracked):", dict(v_cnt))
