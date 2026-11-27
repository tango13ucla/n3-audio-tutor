#!/usr/bin/env python3
"""
Adaptive Engine v8.0 — Exam-Grade 4-Choice Distractor Enricher (Zero Blind-Guessing).

Upgrades 2-choice (50% guess floor) and 3-choice (33% guess floor) non-listening
N3 Grammar / Henkei / Vocab cards up to authentic JLPT 4-choice (25% guess floor)
using:
  1. Hand-curated exact morphological & syntactic 4-choice sets
  2. Learner's own verified historical `confusion_pairs` (strictly slot-compatible)
  3. Syntactically pure JLPT N3 distractor pools (strictly separating te-following,
     plain-clause-following, noun-following, suffix, keigo, and adverb slots!)
  4. Exact-stem verb/adjective cousin sets and realistic Chinese-learner phonemic reading traps

Guarantees:
  - NEVER modifies Listening (`is_listening=True`) cards (preserves 3-option `1/2/3` audio sync)
  - NEVER duplicates any existing choice or overlaps `answer`
  - NEVER pairs near-synonyms that would create ambiguous double-correct answers
  - ZERO em-dashes, ZERO PII, deterministic ordering (frontend shuffles on render)
"""
from __future__ import annotations

import re

# Near-synonym pairs that must NEVER be co-injected as distractors for each other
SYNONYM_EXCLUSIONS: list[set[str]] = [
    {"にしたがって", "につれて", "とともに"},
    {"だけでなく", "ばかりか", "ばかりでなく", "のみならず"},
    {"について", "に関して", "をめぐって"},
    {"を通じて", "を通して"},
    {"にもかかわらず", "のに", "くせに", "ものの", "ながらも"},
    {"おかげで", "せいで"},
    {"わけがない", "はずがない"},
    {"にちがいない", "に違いない", "はずだ"},
    {"ように", "みたいに", "のように"},
    {"をもとに", "に基づいて", "によって"},
    {"うちに", "あいだに", "最中に"},
    {"たびに", "ごとに", "おきに"},
    {"とたんに", "たとたん", "しだい"},
    {"向け", "向き"},
    {"ことだ", "べきだ"},
    {"かもしれない", "らしい", "ようだ", "そうだ", "みたいだ"},
    {"参ります", "伺います"},
    {"参りました", "伺いました"},
    {"参って", "伺って"},
    {"参っ", "伺っ"},
    {"おります", "います"},
    {"いたします", "します"},
    {"申します", "申し上げます"},
    {"どんどん", "だんだん"},
    {"ついに", "とうとう", "ようやく"},
    {"まったく", "けっして", "決して", "少しも"},
    {"さっと", "ざっと"},
    {"しかたがない", "しょうがない", "たまらない"},
    {"たために", "たせいで"},
    {"てはいけない", "てはだめだ"},
    {"一方だ", "ばかりだ"},
    {"てほしい", "てもらいたい"},
    {"ずに", "ないまま"},
    {"終えて", "終わらせて"},
]


def _are_near_synonyms(a: str, b: str) -> bool:
    for grp in SYNONYM_EXCLUSIONS:
        if a in grp and b in grp:
            return True
    return False


# Slot-exact JLPT N3 distractor pools (STRICTLY separated by syntactic attachment!)
SLOT_POOLS: list[list[str]] = [
    # 1. Compound postpositions / clause linkers
    [
        "にしては", "にとって", "によって", "に対して", "について", "にかけて",
        "において", "にわたって", "をめぐって", "を通じて", "を通して",
        "をはじめ", "をもとに", "に基づいて", "にもかかわらず", "どころか",
        "ばかりか", "ばかりでなく", "だけでなく", "かわりに", "わりに",
        "たびに", "ついでに", "せいで", "おかげで", "くせに", "ものの",
        "ながらも", "からこそ", "からには", "ことから", "うえで", "うちに",
        "最中に", "あいだに", "とたんに", "しだい", "きり", "あげく",
        "すえに", "ばかりに", "として", "としても", "とすると", "としたら",
        "というより", "というのは", "を中心に", "に代わって", "にかかわらず",
        "のかわりに", "のために", "のように", "みたいに", "のわりに", "のせいで",
        "のおかげで", "のうえで", "のうちに", "のたびに", "のついでに",
    ],
    # 2. Bare particles & short clause connectors
    [
        "さえ", "しか", "こそ", "なんて", "なんか", "ほど", "くらい", "ばかり",
        "だけ", "まで", "でも", "のに", "ので", "から", "たら", "なら", "ば",
        "と", "ても", "つつ", "ながら", "まま", "っぱなし", "きり", "のみ",
    ],
    # 3. Plain-form-following sentence-final modals (NEVER mix bare te-auxiliaries here!)
    [
        "わけだ", "わけがない", "わけではない", "わけにはいかない",
        "はずだ", "はずがない", "にちがいない", "かもしれない",
        "ことはない", "ことになっている", "ことにしている", "ことになった",
        "ことだ", "ということだ", "ものだ", "ものではない",
        "べきだ", "べきではない", "しかない", "ほかない",
        "ところだ", "ところだった", "ばかりだ", "たばかりだ",
        "ような気がする", "ようにする", "ようになる", "ようになった",
        "ようにしている", "らしい", "ようだ", "そうだ", "みたいだ",
        "ずにはいられない", "に決まっている", "とは限らない", "に限る",
    ],
    # 4. Te-form-following auxiliaries (follows 〜て / 〜で ONLY!)
    [
        "たまらない", "かまわない", "いけない", "しかたがない", "しょうがない",
        "ばかりいる", "ほしい", "みる", "おく", "しまう", "くる", "いく",
        "おこう", "しまおう", "みよう", "はじめて", "からでないと", "はいけない",
    ],
    # 5. Full te-prefixed auxiliary expressions
    [
        "てたまらない", "てもかまわない", "てばかりいる", "てはいけない",
        "てしまう", "ておく", "てみる", "てほしい", "てはじめて", "てからでないと",
        "なくてもいい", "なければならない", "てもしかたがない",
    ],
    # 6. Short nominal / verb-stem suffixes
    [
        "向き", "向け", "がち", "だらけ", "気味", "っぽい", "らしい",
        "やすい", "にくい", "がたい", "きる", "きれない", "かけ", "っぱなし",
        "そう", "よう", "みたい", "すぎ", "すぎる", "わけ", "はず",
        "こと", "もの", "ところ", "ばかり", "べき", "しだい", "きり",
    ],
    # 7. Frequency / interval suffixes
    ["ぶりに", "おきに", "ごとに", "たびに", "までに", "うちに"],
    # 8. Receiving / giving verbs
    ["くれた", "もらった", "あげた", "いただいた", "くださった", "さしあげた"],
    ["くれる", "もらう", "あげる", "いただく", "くださる", "さしあげる"],
    ["くれて", "もらって", "あげて", "いただいて", "くださって", "さしあげて"],
    # 9. Aspect auxiliaries
    ["きた", "いった", "おいた", "みた", "しまった", "あった", "いた"],
    ["いく", "くる", "おく", "みる", "しまう", "ある", "いる"],
    ["なってきた", "なっていった", "なっておいた", "なってしまった"],
    ["なってくる", "なっていく", "なっておく", "なってしまう"],
    # 10. Keigo — masu form
    [
        "いらっしゃいます", "おっしゃいます", "召し上がります", "ご覧になります",
        "参ります", "申します", "いたします", "おります", "伺います",
        "いただきます", "差し上げます", "拝見します", "くださいます",
        "ご存じです", "存じております",
    ],
    # 11. Keigo — mashita form
    [
        "いらっしゃいました", "おっしゃいました", "召し上がりました", "ご覧になりました",
        "参りました", "申しました", "いたしました", "おりました", "伺いました",
        "いただきました", "差し上げました", "拝見しました", "くださいました",
    ],
    # 12. Keigo — te-form
    [
        "いらっしゃって", "おっしゃって", "召し上がって", "ご覧になって",
        "参って", "申して", "いたして", "伺って", "いただいて", "拝見して", "くださって",
    ],
    # 13. Keigo — masu-stem fragments
    [
        "拝見し", "ご覧になり", "お聞きになり", "伺い", "お休みになり", "お休みいたし",
        "いたし", "いらっしゃい", "おっしゃい", "お召し上がりになり", "存じており",
        "お知り", "ご案内し", "お伝えし", "お待ちし", "お越しになり",
    ],
    # 14. Keigo — temo conditional
    ["いただいても", "召し上がっても", "ご覧になっても", "おっしゃっても", "伺っても", "参っても"],
    # 15. Mimetic / -ri adverbs (4-mora)
    [
        "ぎっしり", "ぎりぎり", "ぐっすり", "ぐったり", "がっかり", "すっかり",
        "すっきり", "しっかり", "うっかり", "そっくり", "うっとり", "ばったり",
        "こっそり", "はっきり", "ぼんやり", "のんびり", "ぴったり", "びっくり",
        "さっぱり", "あっさり", "じっくり", "ゆっくり", "きっちり",
    ],
    # 16. Reduplicated onomatopoeia (ABAB 4-mora)
    [
        "からから", "がらがら", "ばらばら", "ぼろぼろ", "ぶらぶら", "うろうろ",
        "いらいら", "わくわく", "どきどき", "にこにこ", "ぺこぺこ", "びしょびしょ",
        "ざわざわ", "どんどん", "だんだん", "さまざま", "ますます",
    ],
    # 17. N3 high-frequency adverbs
    [
        "めったに", "たいてい", "せっかく", "わざわざ", "いよいよ", "ようやく",
        "ちょうど", "かならず", "必ずしも", "けっして", "決して", "まったく",
        "さっそく", "いきなり", "ついに", "とうとう", "まるで", "たとえ",
        "もしも", "さっき", "たまに", "すでに", "やはり", "もっとも",
        "むしろ", "かえって", "さすがに", "わざと", "つい", "ふと",
        "じっと", "さっと", "ざっと", "ぐっと",
    ],
    # 18. Short colloquial contractions
    ["ちゃう", "じゃう", "とく", "どく", "てる", "てく", "なきゃ", "なくちゃ", "って", "といた", "ちゃった"],
    # 19. Casual / emotional idioms
    ["ついてない", "たまらない", "かまわない", "しょうがない", "しかたがない", "もったいない", "くだらない", "つまらない"],
]

# Explicit hand-verified 4-choice morphological / syntactic sets (100% textbook Japanese!)
EXACT_MORPH_SETS: list[list[str]] = [
    ["降るそうだ", "降りそうだ", "降るらしい", "降ったそうだ"],
    ["おいしいそうだ", "おいしそうだ", "おいしいらしい", "おいしかったそうだ"],
    ["読めば", "読むと", "読んだら", "読むなら"],
    ["出れば", "出るので", "出たのに", "出るなら"],
    ["決まりしだい", "決まったしだい", "決めるしだい", "決まってしだい"],
    ["ひきがち", "ひく最中", "ひきかけ", "ひきやすい"],
    ["しがち", "しっぱなし", "しかけ", "しやすい"],
    ["読める", "読まれる", "読ませる", "読ませられる"],
    ["泳げる", "泳ぎられる", "泳がせる", "泳がれる"],
    ["通えます", "通われます", "通わせます", "通わせられます"],
    ["話せます", "話されます", "話させます", "話させられます"],
    ["閉まった", "閉めた", "閉められた", "閉まっている"],
    ["閉めて", "閉まって", "閉められて", "閉めさせて"],
    ["開いた", "開けた", "開かれた", "開けられた"],
    ["開いて", "開けて", "開かれて", "開けさせて"],
    ["消えて", "消して", "消されて", "消させて"],
    ["消えた", "消した", "消された", "消させた"],
    ["落ちて", "落として", "落とされて", "落ちさせて"],
    ["落ちた", "落とした", "落とされた", "落ちていた"],
    ["届いた", "届けた", "届って", "届けられた"],
    ["届いて", "届けて", "届って", "届けられて"],
    ["壊れて", "壊して", "壊されて", "壊させて"],
    ["壊れた", "壊した", "壊されて", "壊させた"],
    ["上がって", "上げて", "上げられて", "上がらせて"],
    ["上がった", "上げた", "上げられた", "上がらせた"],
    ["終えて", "終わって", "終えられて", "終わられて"],
    ["終わらせて", "終わって", "終わられて", "終えられて"],
    ["帰って", "帰らせて", "帰て", "帰されて"],
    ["帰った", "帰らせた", "帰て", "帰された"],
    ["起きられる", "起こせる", "起きれる", "起こされる"],
    ["食べさせた", "食べられた", "食べさせられた", "食べなかった"],
    ["食べられます", "食べれます", "食べさせます", "食べさせられます"],
    ["着られます", "着れます", "着させます", "着させられます"],
    ["調べられます", "調べれます", "調べさせます", "調べさせられます"],
    ["来られます", "来れます", "来させます", "来させられます"],
    ["調べさせられ", "調べされ", "調べられ", "調べさせ"],
    ["使わせて", "使って", "使われて", "使わせられて"],
    ["飲まされた", "飲みさせられた", "飲ませた", "飲まれた"],
    ["待たされた", "待たせた", "待たれた", "待っていた"],
    ["歩かせた", "歩かされた", "歩かれた", "歩けた"],
    ["着られる", "着れる", "着させる", "着させられる"],
    ["見られる", "見れる", "見させる", "見させられる"],
    ["来られる", "来れる", "来させる", "来させられる"],
    ["行こう", "行よう", "行くよう", "行けよう"],
    ["よさそう", "いいそう", "よいそう", "よさそうだ"],
    ["なさそう", "ないそう", "なくそう", "なさそうだ"],
    ["おっしゃっていました", "申していました", "いらっしゃっていました", "召し上がっていました"],
    ["伺っ", "いらっしゃっ", "おっしゃっ", "召し上がっ"],
    ["拝見", "ご覧", "ご案内", "お渡し"],
    ["いただき", "さしあげ", "くださり", "まいり"],
    ["帰るしかない", "帰ることはない", "帰るはずがない", "帰るわけがない"],
    ["貼ってあります", "貼っています", "貼っておきます", "貼ってしまいます"],
    ["てはじめて", "たついでに", "たとたんに", "てからでないと"],
    ["ずに", "ないでいる", "なくて", "ないうちに"],
    ["たところ", "たばかり", "たとたん", "たあとで"],
    ["っぽく", "らしく", "みたいに", "そうに"],
    ["一方だ", "一方で", "べきだ", "ところだ"],
    ["ばかりだ", "べきだ", "ところだ", "ことだ"],
    ["ようにし", "ようになっ", "ことにし", "ことになっ"],
    ["だものだ", "だところだ", "だはずだ", "だわけだ"],
    ["ばよかった", "ばいい", "ば大丈夫だ", "ば済む"],
    ["たこと", "ること", "たところ", "るつもり"],
    ["たあとで", "るまえに", "たばかりで", "ているうちに"],
    ["たために", "るために", "たおかげで", "たわりに"],
    ["しかたがない", "かまわない", "ばかりいる", "はいけない"],
    ["たっけ", "たものだ", "たはずだ", "たばかりだ"],
    ["てほしい", "たい", "てあげたい", "てみたい"],
    ["みたいだ", "らしいだ", "はずだ", "ところだ"],
    ["何もない", "たくさんある", "少しはある", "かなりある"],
    ["せてもらっ", "れ", "させられ", "てあげ"],
    ["ように", "ことに", "ために", "ものに"],
    ["はずなんですが", "はずがないんですが", "わけなんですが", "ばかりなんですが"],
    ["しょるい", "しょうるい", "しゅるい", "じょるい"],
    ["しゅっちょう", "しゅちょう", "しゅうちょう", "しゅっちょ"],
    ["しじ", "じし", "しち", "じじ"],
    ["ぎもん", "きもん", "ぎぶん", "きぶん"],
    ["なぐさめた", "あきらめた", "まとめた", "たしかめた"],
    ["なぐさめる", "あらためる", "たしかめる", "まとめる"],
    ["くんだ", "ぐんだ", "くんで", "くった"],
    ["ためる", "ちょめる", "とめる", "つめる"],
    ["泣かずにはいられなかった", "泣かないではいなかった", "泣くわけにはいかなかった", "泣きようがなかった"],
    ["一直开着没关", "刚刚才打开", "快要关掉了", "打算立刻打开"],
    ["被医生叮嘱要吃药", "听说医生吃了药", "好像医生给了药", "为了见医生才吃药"],
    ["踏まれて", "踏ませて", "踏んで", "踏まれさせて"],
    ["来られる（こられる）", "来れる（これる）", "来させる（こさせる）", "来られる（きられる）"],
    ["ないしょ", "ないしょう", "うちしょ", "ないちょ"],
    ["ダメなわけだ", "ダメわけだ", "ダメだわけだ", "ダメのわけだ"],
    ["あるはずなのだが", "あるはずないのだが", "あるわけないのだが", "あるわけなのだが"],
    ["あるらしい", "あるとらしい", "あるだらしい", "あるのらしい"],
    ["行くことになった", "行きますになった", "行くものになった", "行くようになった"],
    ["ためた", "ちょめた", "とめた", "つめた"],
    ["あまった", "たまった", "かわった", "おわった"],
    ["あまって", "たまって", "かわって", "おわって"],
    ["くわえて", "かえて", "かこんで", "かたづけて"],
    ["くわえた", "そろえた", "かかえた", "まとめた"],
    ["くわえる", "かかえる", "かまえる", "そなえる"],
    ["ゆるす", "のこす", "わたす", "もどす"],
    ["ゆるされない", "はずされない", "わたされない", "のこされない"],
    ["うなずいて", "さけんで", "しゃがんで", "かたづけて"],
    ["かわいがって", "いやがって", "うらやましがって", "こわがって"],
    ["すませよう", "すまそう", "すませた", "すんだ"],
    ["許した", "残した", "渡した", "戻した"],
    ["許して", "残して", "渡して", "戻して"],
    ["休ませていただけない", "休まれていただけない", "休めていただけない", "休んでいただけない"],
    ["てばかりいて", "たばかりで", "ておいて", "てしまって", "てばかりで"],
    ["ないこともない", "ることはない", "るわけがない", "るはずがない"],
    ["た結果", "たばかりに", "たせいで", "たおかげで"],
    ["できしだい", "できたしだい", "できるしだい", "できてしだい"],
    ["させてもらっ", "せてもらっ", "られ", "させてくれ"],
    ["くむ", "ぐむ", "かむ", "こむ"],
    ["買おう", "買よう", "買ろう", "買こう"],
    ["するしかない", "することはない", "するはずがない", "するわけがない"],
    ["なんともない", "すごく痛い", "歩けないほどだ", "かなりひどい"],
    ["省略してはいけない", "省略してもいい", "省略したほうがいい", "省略することはない"],
    ["いちいち", "いっさい", "いつのまにか", "いったい"],
    ["か何か", "かどこか", "かだれか", "かいつか"],
    ["読んだきり", "読むきり", "読んだたびに", "読んだうえで"],
    ["たきり", "たうえで", "たとたん", "たわりに"],
    ["たとたんに", "たきり", "たわりに", "たうえで"],
    ["走りきった", "走ってきった", "走りかけた", "走るきった"],
    ["読みきれない", "読むきれない", "読みきった", "読んでくれない"],
    ["強くても", "強ければ", "強いために", "強いので"],
    ["抜けたとたん", "抜けるとたん", "抜けたうえで", "抜けたきり"],
    ["だけしか", "だけでも", "だけなら", "だけあって"],
    ["飲んでばかりいる", "飲んだばかりいる", "飲みばかりいる", "飲むばかりいる"],
    ["重ねるとともに", "重ねたとともに", "重ねるにとって", "重ねるわりに"],
    ["苦しくはなかった", "苦しかった", "苦しすぎた", "苦しいはずだ"],
    ["をはじめとする", "をはじめとして", "をきっかけに", "を中心として"],
    ["嫌いではない", "とても嫌いだ", "嫌いすぎる", "かなり嫌いだ"],
    ["遅れ気味", "遅れる気味", "遅れて気味", "遅れた気味"],
    ["疲れ気味", "疲れだらけ", "疲れっぱなし", "疲れきり"],
    ["安くはない", "安い", "安すぎる", "安そうだ"],
    ["寝るに限る", "寝たに限る", "寝るとは限らない", "寝てに限る"],
    ["使うしかない", "使ったしかない", "使うことはない", "使ってしかない"],
    ["便利なうえに", "便利のうえに", "便利なうえで", "便利だうえに"],
    ["消してしまうところだった", "消してしまったところだった", "消してしまうはずだった", "消してしまうわけだった"],
    ["切ろうとしたとき", "切ろうしたとき", "切ろうとしたのとき", "切るようとしたとき"],
    ["詰め込むことはない", "詰め込んだことはない", "詰め込むしかない", "詰め込むわけにはいかない"],
    ["伺う", "お聞きになる", "お伺いになる", "おっしゃる"],
    ["ようとした", "たばかりだ", "てしまった", "ておいた"],
    ["なさ", "いたし", "いらっしゃ", "おっしゃ"],
    ["忘れません", "忘れます", "忘れました", "忘れなかった"],
    ["下がらなかった", "下がった", "下げなかった", "下がりすぎた"],
    ["叱られた", "叱らせた", "叱った", "叱っていた"],
    ["話させられた", "話さされた", "話しさせられた", "話させた"],
    ["走って", "走て", "走んで", "走らせて"],
    ["印刷されなかった", "印刷された", "印刷しなかった", "印刷した"],
]

_HIRAGANA_ONLY = re.compile(r"^[\u3040-\u309fー]+$")

_DAKUTEN_SWAP = {
    "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
    "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
    "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
    "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
    "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
    "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
    "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ",
    "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
}


def _generate_phonemic_traps(existing: list[str], answer: str) -> list[str]:
    """Generate realistic Chinese-learner hiragana reading traps (long vowel on o-row, dakuten, sokuon)."""
    if not existing or not all(_HIRAGANA_ONLY.match(c) for c in existing):
        return []
    if len(answer) < 2 or len(answer) > 7:
        return []
    cands: list[str] = []
    # 1. Long vowel toggle strictly on お-row (never creates awkward るうい!)
    o_row = "おこそとのほもよろをごぞどぼぽょ"
    for i, ch in enumerate(answer):
        if ch in o_row:
            if i + 1 < len(answer) and answer[i + 1] == "う":
                cands.append(answer[: i + 1] + answer[i + 2 :])
            else:
                cands.append(answer[: i + 1] + "う" + answer[i + 1 :])
    # 2. Dakuten swap
    for i in range(len(answer)):
        if answer[i] in _DAKUTEN_SWAP:
            cands.append(answer[:i] + _DAKUTEN_SWAP[answer[i]] + answer[i + 1 :])
    # 3. Sokuon toggle strictly before k/s/t/p kana
    if "っ" in answer:
        cands.append(answer.replace("っ", "", 1))
    elif len(answer) >= 3:
        for i in range(1, len(answer) - 1):
            if answer[i] in "かきくけこさしすせそたちつてとぱぴぷぺぽ":
                cands.append(answer[:i] + "っ" + answer[i:])
                break
    out: list[str] = []
    seen = set(existing)
    for c in cands:
        if c and c not in seen and 2 <= len(c) <= 8:
            seen.add(c)
            out.append(c)
    return out


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _stem_verb_morph_traps(existing: list[str], answer: str) -> list[str]:
    """If existing choices share a common Kanji verb stem, craft exact-stem morphological cousins."""
    if len(existing) < 2:
        return []
    c0, c1 = existing[0], existing[1]
    plen = _common_prefix_len(c0, c1)
    if plen < 1:
        return []
    prefix = c0[:plen]
    if not re.search(r"[\u4e00-\u9fff]", prefix):
        return []
    s0, s1 = c0[plen:], c1[plen:]
    s_set = {s0, s1}
    suffix_groups = [
        ["た", "て", "ない", "れる", "られる", "せた", "された", "させられた", "ている"],
        ["えた", "した", "された", "させた", "える", "す"],
        ["いた", "けた", "かれた", "けられた", "く", "ける"],
        ["まった", "めた", "められた", "ませた"],
        ["れた", "した", "された", "させた"],
        ["った", "た", "せた", "された", "て"],
        ["る", "れる", "られる", "させる", "させられる", "ない"],
        ["ます", "ました", "ません", "ませんでした", "ております"],
        ["ながら", "つつ", "うちに", "最中に", "とたんに", "しだい", "がち", "やすい", "にくい", "きる", "きれない", "かける", "っぱなし"],
        ["そうだ", "ようだ", "らしい", "はずだ", "わけだ", "べきだ"],
        ["ことにしている", "ことになっている", "ことになった", "ようになった", "ようにしている"],
        ["てくる", "ていく", "ておく", "てみる", "てしまう"],
        ["てきた", "ていった", "ておいた", "てみた", "てしまった"],
        ["ばかりいる", "ばかりだ", "ところだ", "たばかりだ", "ている"],
        ["てたまらない", "てもかまわない", "てはいけない", "てばかりいる"],
    ]
    out: list[str] = []
    seen = set(existing)
    for grp in suffix_groups:
        if any(s in grp for s in s_set):
            for suf in grp:
                cand = prefix + suf
                if cand not in seen and cand != answer and 2 <= len(cand) <= 14:
                    seen.add(cand)
                    out.append(cand)
            if len(out) >= 3:
                break
    return out


def _detect_pool(existing: list[str], answer: str = "") -> list[str] | None:
    best_pool: list[str] | None = None
    best_score = (0, 0)
    ans = str(answer or "").strip()
    for pool in SLOT_POOLS:
        pset = set(pool)
        hits = sum(1 for c in existing if c in pset)
        ans_hit = 1 if (ans and ans in pset) else 0
        score = (hits, ans_hit)
        if hits > 0 and score > best_score:
            best_score = score
            best_pool = pool
    best_hits = best_score[0]
    if best_pool and best_hits >= 2:
        return best_pool
    if best_pool and best_hits == 1 and all(len(c) <= 8 for c in existing):
        return best_pool
    return None


def enrich_card_choices(
    choices: list[str],
    answer: str,
    *,
    is_listening: bool = False,
    point_key: str = "",
    subject: str = "",
    confusion_pairs: dict | None = None,
    target_count: int = 4,
) -> list[str]:
    """
    Upgrade a non-listening quiz card from 2-choice or 3-choice to authentic JLPT 4-choice.
    Returns original `choices` untouched for listening cards, already-4-choice cards, or sentence choices.
    """
    if is_listening or not choices or not answer:
        return list(choices)
    clean = [str(c).strip() for c in choices if str(c).strip()]
    if len(clean) >= target_count:
        return clean
    if any(re.match(r"^[a-d]\.\s", c) or "。" in c or len(c) > 16 for c in clean):
        return clean

    out = list(clean)
    seen = set(out)
    ans = str(answer).strip()

    def _can_add(cand: str) -> bool:
        c = str(cand or "").strip()
        if not c or c in seen or c == ans or "—" in c or len(c) > 16 or "。" in c:
            return False
        if ans and (c == ans or _are_near_synonyms(c, ans)):
            return False
        return True

    # 1) Exact curated morphological/syntactic set match first
    for mset in EXACT_MORPH_SETS:
        m_hits = sum(1 for c in clean if c in mset)
        if m_hits >= 2 or (ans in mset and m_hits >= 1 and len(clean) == 2):
            for cand in mset:
                if len(out) >= target_count:
                    return out
                if _can_add(cand):
                    out.append(cand)
                    seen.add(cand)
            if len(out) >= target_count:
                return out

    # 2) Detect exact grammatical/lexical slot pool (answer pool wins ties)
    pool = _detect_pool(clean, ans)

    # 3) Prioritize learner's own real historical confusion wrong choice if it fits the detected slot
    if confusion_pairs and point_key and pool:
        cp_obj = confusion_pairs.get(point_key)
        cp_wrong = cp_obj.get("top_wrong") if isinstance(cp_obj, dict) else (cp_obj if isinstance(cp_obj, str) else "")
        if cp_wrong and cp_wrong in pool and _can_add(cp_wrong):
            out.append(cp_wrong)
            seen.add(cp_wrong)

    # 4) Fill from matched grammatical/lexical slot pool (similar length first)
    if pool and len(out) < target_count:
        avg_len = sum(len(c) for c in clean) / max(1, len(clean))
        ranked = sorted(
            [c for c in pool if _can_add(c)],
            key=lambda c: (abs(len(c) - avg_len), pool.index(c)),
        )
        for cand in ranked:
            if len(out) >= target_count:
                break
            if _can_add(cand):
                out.append(cand)
                seen.add(cand)

    # 5) Shared-Kanji-stem morphological traps
    if len(out) < target_count:
        for cand in _stem_verb_morph_traps(clean, ans):
            if len(out) >= target_count:
                break
            if _can_add(cand):
                out.append(cand)
                seen.add(cand)

    # 6) Pure-hiragana Kanji-reading phonemic traps (Vocab cards only)
    if len(out) < target_count and subject in ("語彙", "词汇", "vocab"):
        for cand in _generate_phonemic_traps(clean, ans):
            if len(out) >= target_count:
                break
            if _can_add(cand):
                out.append(cand)
                seen.add(cand)

    return out
