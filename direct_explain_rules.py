#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct-to-Chinese Answer Explanation Builder (Zen v19 — Zero Japanese Re-read, Instant Point Hook).

User standing rule (2026-11-22 22:59 PT):
- NEVER re-read the Japanese question sentence or listening dialogue at the start of answer audio
  (`*_exp.mp3`), because the learner already listened to it while answering (and `原题` is 1 tap away).
- Start IMMEDIATELY at 0.00s in brisk, natural Chinese explaining what this question is testing
  (grammar pattern & core function for 文法; conjugation/keigo/transitivity for 活用; reading/word
  distinction for 語彙; listening cue & logic for 聴解 — never forcing the word "语法" onto
  non-grammar items).
- Strip redundant "这句是说……" translation fluff (already visible on screen) and ensure 100% of
  inline Japanese tokens inside Chinese speech are written in pure Hiragana/Katakana with spaces
  around them so the multilingual neural voice switches phonology seamlessly.
"""
from __future__ import annotations

import re
from typing import Any

KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
KANA_ONLY_RE = re.compile(r"^[\u3040-\u30ffー・]+$")

# Pure-Kana inline Japanese hooks for all 133 N3 Grammar points
GRAMMAR_HOOKS: dict[str, str] = {
    "〜いくら〜ても": "考语法 いくら ても，表无论怎么怎样也。",
    "〜いちいち": "考语法 いちいち，表逐个一一计较。",
    "〜うえで": "考语法 うえで。",
    "〜うちに": "考语法 うちに，表趁着眼下状态还没变。",
    "〜おきに": "考语法 おきに，表每隔固定间隔重复。",
    "〜かけだ": "考语法 かけだ，表动作做到一半还没完。",
    "〜からこそ": "考语法 からこそ，表正因为如此才。",
    "〜かわりに": "考语法 かわりに，表代替或作为交换。",
    "〜か何か": "考语法 かなにか，表举个大概的例子。",
    "〜がたい": "考语法 がたい，表心理或客观上很难做到。",
    "〜がちだ": "考语法 がちだ，表消极情况动不动就发生。",
    "〜きり": "考语法 きり，表只剩下或做完之后再也没。",
    "〜きる／〜きれない": "考语法 きる 和 きれない，表彻底做完或做不完。",
    "〜くらい／ぐらい": "考语法 くらい，表夸张到某种程度。",
    "〜こそ": "考语法 こそ，表强烈强调正是这个。",
    "〜ことから": "考语法 ことから，表从某个事实推断或由此得名。",
    "〜ことがある（経験）": "考语法 たことがある，表曾经有过的经历。",
    "〜ことだ（忠告）": "考语法 ことだ，表诚恳劝告最好去做。",
    "〜ことになっている": "考语法 ことになっている，表既定规章或安排。",
    "〜ことになる": "考语法 ことになる，表外部客观定下来的结果。",
    "〜ことはない": "考语法 ことはない，表用不着、没必要。",
    "〜ごとに": "考语法 ごとに，表每逢或每隔一定单位。",
    "〜さえ": "考语法 さえ，表举极端例子连什么都。",
    "〜さえ〜ば": "考语法 さえ ば，表只要满足最低条件就够了。",
    "〜させてもらう": "考语法 させてもらう，礼貌请求对方准许自己做。",
    "〜しかない": "考语法 しかない，表别无选择只好这样。",
    "〜しだい": "考语法 しだい，表一落定就立刻行动。",
    "〜すぎる": "考语法 すぎる，表程度太过了。",
    "〜ずに": "考语法 ずに，表没做前面就做了后面。",
    "〜ずにはいられない": "考语法 ずにはいられない，表情不自禁忍不住。",
    "〜たあとで": "考语法 たあとで，表做完一件事之后再。",
    "〜たとえ〜ても": "考语法 たとえ ても，表就算极端假设也。",
    "〜たところ": "考语法 たところ，表试着一做就发现结果。",
    "〜ために（原因）": "考语法 ために，表客观原因。",
    "〜ために（目的）": "考语法 ために，表为了达成目标。",
    "〜たものだ": "考语法 たものだ，表怀念过去常常做。",
    "〜だけしか〜ない": "考语法 しか ない，表仅仅只有。",
    "〜だらけ": "考语法 だらけ，表满是、沾满不好的东西。",
    "〜ちゃう／じゃう": "考口语 ちゃう 和 じゃう，就是 てしまう 的缩音。",
    "〜っけ": "考语法 っけ，表努力回想确认刚才的事。",
    "〜っぱなし": "考语法 っぱなし，表放任原状态不管。",
    "〜っぽい": "考语法 っぽい，表像什么或动不动就怎样。",
    "〜ていく／〜てくる": "考语法 ていく 和 てくる，表变化方向。",
    "〜ておく": "考语法 ておく，表提前做好准备。",
    "〜てくれる／もらう": "考授受语法 てくれる 和 てもらう。",
    "〜てしまう": "考语法 てしまう，表全部做完或遗憾不小心。",
    "〜てたまらない": "考语法 てたまらない，表程度强烈到受不了。",
    "〜てはじめて": "考语法 てはじめて，表亲身经历后才头一回明白。",
    "〜てほしい": "考语法 てほしい，表希望别人去做某事。",
    "〜てもかまわない": "考语法 てもかまわない，表就算这样也没关系。",
    "〜ということだ": "考语法 ということだ，表转述听说或总结含义。",
    "〜というより": "考语法 というより，表与其说前者不如说后者。",
    "〜といっても": "考语法 といっても，表虽说如此其实没那么夸张。",
    "〜とおりに": "考语法 とおりに，表原封不动照着做。",
    "〜ところだ": "考语法 ところだ。",
    "〜としたら": "考语法 としたら，表假设如果真这样的话。",
    "〜として": "考语法 として，表作为某种身份或立场。",
    "〜とすると": "考语法 とすると，表假设顺理成章推下去。",
    "〜とともに": "考语法 とともに，表随着变化或同时一起。",
    "〜とは限らない": "考语法 とはかぎらない，表不一定全都如此。",
    "〜と同時に": "考语法 とどうじに，表几乎同时发生或兼具两面。",
    "〜どころか": "考语法 どころか，表别说怎样反而完全相反。",
    "〜ながらも": "考语法 ながらも，表虽然怎样却依然怎样。",
    "〜なければならない": "考语法 なければならない，表必须去做。",
    "〜なんか": "考语法 なんか，表轻描淡写或谦虚举例。",
    "〜なんて": "考语法 なんて，表出乎意料或惊讶感叹。",
    "〜にかけて": "考语法 にかけて，表连续跨越一段时间或区域。",
    "〜にしたがって": "考语法 にしたがって，表随着一方变化另一方跟着变。",
    "〜にしては": "考语法 にしては，表按这个标准却出乎意料。",
    "〜にしても": "考语法 にしても，表就算退一步讲也。",
    "〜について": "考语法 について，表围绕某个主题。",
    "〜につれて": "考语法 につれて，表伴随自然渐变。",
    "〜にとって": "考语法 にとって，表站在某人立场上来看。",
    "〜にもかかわらず": "考语法 にもかかわらず，表尽管如此却仍然。",
    "〜によっては": "考语法 によっては，表因情况而异、有的会怎样。",
    "〜によると／によれば": "考语法 によると，表引出消息来源。",
    "〜による／によって": "考语法 によって，表原因、手段或因人而异。",
    "〜に基づいて": "考语法 にもとづいて，表以事实或数据为依据。",
    "〜に対して": "考语法 にたいして，表针对对象或前后对比。",
    "〜に関して": "考语法 にかんして，表正式书面语的关于。",
    "〜に限る": "考语法 にかぎる，表还是这个最好。",
    "〜のに": "考语法 のに，表逆接明明却。",
    "〜のように／ような": "考语法 のように，表比喻像什么一样。",
    "〜はずだ": "考语法 はずだ，表有依据的推测按理应该。",
    "〜ば〜のに": "考语法 ば のに，表与事实相反的懊悔。",
    "〜ば〜ほど": "考语法 ば ほど，表越怎样越怎样。",
    "〜ばいい／たらいい": "考语法 ばいい，表给出建议怎么做好。",
    "〜ばかり": "考语法 ばかり，表光是、净是同一件事。",
    "〜ばかりだ": "考语法 ばかりだ，表往不好方向一直恶化。",
    "〜ばかりでなく": "考语法 ばかりでなく，表不仅而且。",
    "〜ばかりに": "考语法 ばかりに，表偏偏就因为这一小事酿成遗憾。",
    "〜ばよかった": "考语法 ばよかった，表事后后悔当初要是做了就好了。",
    "〜ふりをする": "考语法 ふりをする，表故意装作某种样子。",
    "〜ぶりに": "考语法 ぶりに，表时隔多久再一次。",
    "〜べきではない": "考语法 べきではない，表理应不该做某事。",
    "〜ほど〜ない": "考语法 ほど ない，表没有前者那么夸张。",
    "〜までに": "考语法 までに，表动作必须完成的截止期限。",
    "〜みたいだ": "考语法 みたいだ，表口语里的好像。",
    "〜めったに〜ない": "考语法 めったに ない，表极少、难得一见。",
    "〜ものだ": "考语法 ものだ。",
    "〜やすい／〜にくい": "考语法 やすい 和 にくい，表容易或难以做到。",
    "〜ようとする": "考语法 ようとする，表刚想动手或试图去做。",
    "〜ような気がする": "考语法 ようなきがする，表隐约总觉得。",
    "〜ようにする": "考语法 ようにする，表有意识努力做到。",
    "〜ようになる": "考语法 ようになる，表能力或状态自然发生变化。",
    "〜ように言う": "考语法 ようにいう，表叮嘱或转告要求对方做。",
    "〜らしい": "考语法 らしい。",
    "〜らしく": "考语法 らしく，表活脱脱像某种典型样子。",
    "〜わけがない": "考语法 わけがない，表按理绝不可能。",
    "〜わけだ": "考语法 わけだ，表顺理成章难怪如此。",
    "〜わけではない": "考语法 わけではない，表部分否定并不是全都如此。",
    "〜わりに": "考语法 わりに，表跟原本条件相比不相称。",
    "〜をはじめ": "考语法 をはじめ，表以最具代表性的为首。",
    "〜を中心に": "考语法 をちゅうしんに，表以什么为核心展开。",
    "〜一度に": "考语法 いちどに，表一次性同时发生。",
    "〜一方だ": "考语法 いっぽうだ，表一直往单方向越演越烈。",
    "〜一方で": "考语法 いっぽうで，表一方面同时另一方面。",
    "〜別に〜ない": "考语法 べつに ない，表倒也没什么特别的。",
    "〜向き": "考语法 むき，表性质上天然适合某类人。",
    "〜向け": "考语法 むけ，表专门面向某类人打造。",
    "〜最中に": "考语法 さいちゅうに，表正干在半截突发插曲。",
    "〜気味": "考语法 ぎみ，表略微有点儿偏向某种状态。",
    "〜結局": "考语法 けっきょく，表折腾半天到头来还是怎样。",
    "そうだ（伝聞）": "考传闻 そうだ，接简体原形表听说。",
    "ところだった": "考语法 ところだった，表差一点就酿成险情。",
    "どんなに〜ても": "考语法 どんなに ても，表无论多么怎样也。",
    "まるで〜のように": "考语法 まるで のように，表简直像什么一样。",
    "尊敬語特殊動詞组": "考特殊尊敬语动词。",
    "少しも〜ない": "考语法 すこしも ない，表一点儿也没有。",
    "必ずしも〜ない": "考语法 かならずしも ない，表部分否定未必一定。",
    "授受敬语升级": "考授受敬语 くださる 和 いただく。",
    "決して〜ない": "考语法 けっして ない，表绝对不、决不。",
    "謙譲語特殊動詞组": "考特殊谦让语动词。",
    # Wave-10 complete 156/156 grammar coverage (N3-G136 .. N3-G158)
    "〜あいだ（に）": "考语法 あいだに 和 あいだ，表期间内完成或全程持续。",
    "〜あまり（に）": "考语法 あまり，表程度太甚以至于失控。",
    "〜くせに": "考语法 くせに，带责备吐槽明明却。",
    "〜ことにする": "考语法 ことにする，表自己主动拍板决定。",
    "〜ついでに": "考语法 ついでに，表办正事顺便捎带做另一件。",
    "〜にちがいない": "考语法 にちがいない，表高度笃定一定是这样。",
    "〜ばかりか": "考语法 ばかりか，表不仅如此甚至连什么都。",
    "〜おかげで": "考语法 おかげで，表多亏带来好结果。",
    "〜せいで": "考语法 せいで，表都怪导致坏结果。",
    "〜たとたん": "考语法 たとたん，表刚一动作瞬间突发变化。",
    "〜たびに": "考语法 たびに，表每当怎样就总是怎样。",
    "〜てばかりいる": "考语法 てばかりいる，吐槽老是光做同一件事。",
    "〜ないことはない": "考语法 ないことはない，双重否定表也不是不能。",
    "〜に比べて": "考语法 にくらべて，表把两项放在一起比较。",
    "〜はずがない": "考语法 はずがない，表有依据断定按理绝不可能。",
    "〜べきだ": "考语法 べきだ，表于情于理应该去做。",
    "〜まま": "考语法 まま，表维持原状态没改变。",
    "〜わけにはいかない": "考语法 わけにはいかない，表顾及情理底线绝不能做。",
    "〜た結果": "考语法 たけっか，表经过一番折腾最终导致结果。",
    "〜うえに": "考语法 うえに，表不仅如此而且更添一层。",
    "〜だけでなく": "考语法 だけでなく，表不仅前者而且还有后者。",
    "〜はもちろん": "考语法 はもちろん，表前者不用说连后者也。",
    "せっかく〜のに": "考语法 せっかく のに，表好不容易却白费真可惜。",
}

# Pure-Kana hooks for all 35 Conjugation / Keigo / Transitivity points (NO forced "语法" word!)
HENKEI_HOOKS: dict[str, str] = {
    "A-042": "考 いい 接 そうだ 的特殊变形 よさそう。",
    "K-001": "考尊敬语 いらっしゃる，尊称对方在、去或来。",
    "K-002": "考尊敬语 おっしゃる，尊称对方说话。",
    "K-003": "考尊敬语 めしあがる，尊称对方吃喝。",
    "K-004": "考尊敬语 ごらんになる，尊称对方看。",
    "K-005": "考尊敬语 なさる，尊称对方做某事。",
    "K-006": "考尊敬语 くださる，尊长主动给我。",
    "K-007": "考尊敬语 おやすみになる，尊称对方歇息就寝。",
    "K-008": "考尊敬语 ごぞんじだ，尊称对方知道。",
    "K-012": "考谦让语 いただく，压低自己吃喝或收受。",
    "K-013": "考谦让语 はいけんする，压低自己拜读查看。",
    "K-014": "考谦让语 うかがう，压低自己去拜访或请教。",
    "K-041": "考敬语方向辨析，尊敬语绝不能用在自己身上。",
    "T-001": "考自动词 あく 和他动词 あける。",
    "T-002": "考自动词 しまる 和他动词 しめる。",
    "T-004": "考自动词 きえる 和他动词 けす。",
    "T-006": "考自动词 おわる 和他动词 おえる。",
    "T-008": "考自动词 こわれる 和他动词 こわす。",
    "T-021": "考自动词 あがる 和他动词 あげる。",
    "T-034": "考自动词 とどく 和他动词 とどける。",
    "T-044": "考自动词 おちる 和他动词 おとす。",
    "V-027": "考五段动词可能形。",
    "V-028": "考一段动词可能形。",
    "V-030": "考 くる 的考试标准可能形 こられる。",
    "V-031": "考一段可能形，考试必须留 ら。",
    "V-032": "考动词变形。",
    "V-033": "考一段动词被动形。",
    "V-037": "考五段动词使役形。",
    "V-038": "考一段动词使役形。",
    "V-041": "考五段动词使役被动形，表被迫做某事。",
    "V-042": "考一段动词使役被动形，表被迫做某事。",
    "V-045": "考五段使役被动短形 される。",
    "V-046": "考五段动词意向形。",
    "V-069": "考他动词加 てある，表人为留下的结果状态。",
    "V-085": "考一段和五段动词判别。",
}

# Pure-Kana hooks for all 32 Listening points (NO Japanese dialogue re-read, NO "语法" word!)
LISTENING_HOOKS: dict[str, str] = {
    "N3L-001": "考口语缩音 てる。",
    "N3L-003": "考口语缩音 てない。",
    "N3L-004": "考口语缩音 てて。",
    "N3L-005": "考浊音口语缩音 でる。",
    "N3L-006": "考口语缩音 とく，表提前做好。",
    "N3L-007": "考口语缩音 といて，表拜托提前做好。",
    "N3L-009": "考口语缩音 ちゃう。",
    "N3L-010": "考口语缩音 ちゃった，带懊恼遗憾。",
    "N3L-012": "考口语缩音 ちゃって，表遗憾的原因。",
    "N3L-013": "考口语缩音 ちゃだめ，表不可以做。",
    "N3L-015": "考口语缩音 なきゃ，表必须去做。",
    "N3L-016": "考口语缩音 なくちゃ，表必须去做。",
    "N3L-017": "考句尾省略 ないと，表必须赶紧做。",
    "N3L-018": "考口语缩音 てく。",
    "N3L-020": "考 てくる，表去办完再回来。",
    "N3L-021": "考口语缩音 わかんない。",
    "N3L-025": "考传闻口语 んだって。",
    "N3L-039": "考惊讶语气 なんて。",
    "N3L-048": "考口语缩音 とかないと，表必须提前做好。",
    "N3L-066": "考句尾省略 にでも，表客气提希望时间。",
    "N3L-071": "考委婉谢绝 いいです。",
    "N3L-085": "考转折后拍板 ことにした。",
    "N3L-086": "考先后顺序，听见 あとにして 先划掉。",
    "N3L-087": "考先后顺序，抓住最先要做的事。",
    "N3L-199": "考礼貌请假 させていただきます。",
    "N3L-244": "考句尾求认同 でしょ。",
    "N3L-262": "考副词 つい，表一不留神没忍住。",
    "N3L-284": "考听到传闻时的自然回应。",
    "N3L-323": "考提醒语气 よ。",
    "N3L-368": "考纠偏修正 じゃなくて，划掉前面选后面。",
    "N3L-402": "考临时改计划，听清最终决定。",
    "N3L-403": "考分辨听说的传闻和亲身经历。",
}

# Sentences that open with a redundant translation/scene-setter before the real explanation
TRANSLATION_OPENER_RE = re.compile(
    r"^(?:"
    r"这[句一]?话?(?:"
    r"是说|是在|说|吐槽|抱怨|感叹|安慰|庆幸|夸|问|提醒|向|是职场|是电车|是客气|是感谢|"
    r"是约|是在|是日本|是日常|是没赶上|是跟|是摸着|是转述|是正式|是商务|是请假|是天气|"
    r"是礼貌|是面试|是打工|是敬语|是吃货|一开头|对话|画面|挺有画面|很有生活|挺暖心|"
    r"大家肯定|不好意思|狠狠吐槽|在课堂"
    r")"
    r"|同事问现在方不方便"
    r")"
)

EXPLICIT_EXPLAIN_OPENER_RE = re.compile(
    r"^这[句一]?话?(?:考的是|专门帮你|把\s|要注意|跟今天)"
)


# Explicit hooks for variant cards that deliberately test the opposite/twin point of their base point_key
CARD_HOOK_OVERRIDES: dict[str, str] = {
    "VAR-G05": "考语法 ついでに，表办一件事顺便做另一件。",
    "VAR-G10": "考语法 はずがない，表有依据推断按理绝不可能。",
    "VAR-G13": "考样态 そうだ，接动词词干表眼看就要怎样。",
    "VAR-G20": "考语法 ことにしている，表自己给自己立的个人习惯。",
    "VAR-G22": "考语法 てしかたがない，跟 てたまらない 一样表程度强到受不了。",
    "VAR-H01": "考谦让语 いただく，压低自己吃喝或收受。",
    "VAR-H02": "考一段动词使役形。",
    "VAR-V28": "考副词 ぐったり。",
}


def _infer_subject(qid: str, meta: dict[str, Any]) -> str:
    s = str(meta.get("subject") or "").strip()
    if s:
        return s
    if qid.startswith(("G-", "GQ-")):
        return "文法"
    if qid.startswith(("H-", "HQ-")):
        return "活用"
    if qid.startswith("V-"):
        return "語彙"
    if qid.startswith("Q-"):
        return "聴解"
    return "文法"


def _strip_translation_opener(qid: str, raw_t: str, subj: str) -> str:
    txt = str(raw_t or "").strip()
    if not txt:
        return txt
    if subj == "聴解":
        # Clean any stray fixed ordinal like "的第一项" since listening choices dynamically shuffle on retry
        txt = re.sub(r"的第[一二三123][项句个]", "", txt)
        return txt

    # Special card VAR5-11: "这句考的是 らしい 最经典的接续坑：看店门口的告示牌，这家面包店每周三休息。..."
    if qid == "VAR5-11":
        m_dot = re.search(r"[。！？]\s*(.+)$", txt)
        if m_dot:
            return "考语法 らしい 最经典的接续坑。" + m_dot.group(1).strip()

    # Cards where Sentence 1 IS already an explanation (e.g. VAR4-V05, VAR-V32, VAR3-H13...)
    if EXPLICIT_EXPLAIN_OPENER_RE.match(txt):
        if txt.startswith("这句考的是"):
            return txt[2:]
        if txt.startswith("这句要注意"):
            return txt[2:]
        if txt.startswith("这句把"):
            return "直接把" + txt[3:]
        return txt

    # Standard 2+ sentence card with a redundant Sentence 1 translation/scene-setter
    if TRANSLATION_OPENER_RE.match(txt):
        m = re.match(r"^([^。！？]+[。！？])\s*(.+)$", txt)
        if m:
            rest = m.group(2).strip()
            if len(rest) >= 12:
                return rest

    return txt


def _contextual_grammar_hook(pk: str, body: str, why_line: str) -> str:
    base = GRAMMAR_HOOKS.get(pk)
    ctx = (why_line or "") + " " + (body or "")
    if pk == "〜うえで":
        if "方面" in ctx or "在……" in ctx or "做某事方面" in ctx:
            return "考语法 うえで，表在做某事的方面。"
        return "考语法 うえで，表做完前面这件事之后再。"
    if pk == "〜ところだ":
        if "刚" in ctx and ("吃完" in ctx or "结束" in ctx or "放" in ctx or "完" in ctx or "过去式" in ctx):
            return "考语法 たところだ，表动作刚刚结束。"
        if "正在" in ctx or "半截" in ctx or "正忙" in ctx or "ているところ" in ctx:
            return "考语法 ているところだ，表动作正做到一半。"
        return "考语法 ところだ，表马上就要开始。"
    if pk == "〜ものだ":
        if "过去" in ctx or "怀念" in ctx or "回想" in ctx or "小时候" in ctx:
            return "考语法 たものだ，表怀念过去常常做。"
        return "考语法 ものだ，表自然天性和世间常理。"
    if pk == "〜らしい":
        if "传闻" in ctx or "听说" in ctx or "据" in ctx or "报道" in ctx or "告示" in ctx:
            return "考语法 らしい，表客观依据的推测或传闻。"
        return "考语法 らしい，表典型特征有某种样子。"
    if base:
        return base
    clean_pk = pk.replace("〜", " ").strip()
    if clean_pk and not KANJI_RE.search(clean_pk):
        return f"考语法 {clean_pk}。"
    return ""


def _vocab_hook(pk: str, ans: str, choices: list[str], body: str) -> str:
    ans_clean = str(ans or "").split("（")[0].strip()
    is_reading = bool(KANJI_RE.search(pk)) and bool(choices) and all(
        KANA_ONLY_RE.match(str(ch).split("（")[0].strip()) for ch in choices if ch
    )
    if is_reading and ans_clean and not KANJI_RE.search(ans_clean):
        return f"考汉字读音 {ans_clean}。"
    if ans_clean and not KANJI_RE.search(ans_clean):
        if any(tag in body for tag in ("拟态", "副词", "清音", "浊音", "重叠")):
            return f"考副词 {ans_clean}。"
        return f"考词汇 {ans_clean}。"
    return ""


def _dedup_hook_and_body(hook: str, body: str) -> str:
    """Fuse hook + body smoothly without echoing the exact same opening words twice."""
    h = (hook or "").strip()
    b = (body or "").strip()
    if not h:
        return b
    if not b:
        return h

    # If body already begins with "考..." or "这题考...", don't double-prefix!
    if re.match(r"^(?:这题考|考的是|考语法|考谦让|考尊敬|考汉字|考副词|考词汇|考口语|考先后)", b):
        return b

    # Only fuse into a single opening clause when body LITERALLY begins with the same grammatical heading
    # e.g. hook="考一段动词可能形。", body="一段动词变可能形，正式考试..."
    if re.match(r"^(?:一段动词|五段动词|动词|形容词)(?:变)?(?:可能形|被动形|使役形|使役被动|意向形)", b):
        return "考" + b

    # If hook has "，表XXX。" and body immediately repeats the exact same meaning phrase in first 28 chars, shorten hook to tag
    if "，" in h:
        hook_tag, hook_desc = h.split("，", 1)
        desc_clean = re.sub(r"^[表专门礼貌]+|[。！？]$", "", hook_desc).strip()
        if desc_clean and len(desc_clean) >= 4:
            overlap = any(
                desc_clean[i : i + 4] in b[:28]
                for i in range(0, max(1, len(desc_clean) - 3))
            )
            if overlap:
                h = hook_tag.rstrip("，。 ") + "。"

    if not h.endswith(("。", "！", "？")):
        h += "。"
    return f"{h}{b}"


def build_direct_exp_text(qid: str, card: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    """Return the direct, zero-reread Chinese+inline-Kana spoken explanation for any quiz card."""
    m = meta or {}
    subj = _infer_subject(qid, m)
    pk = str(m.get("point_key") or "").strip()
    ans = str(m.get("answer") or "").strip()
    choices = list(m.get("choices") or [])
    why_line = str(card.get("why_line") or "").strip()

    raw_t = " ".join(str(val).strip() for spk, val in (card.get("exp_turns") or []) if spk == "T").strip()
    if not raw_t:
        raw_t = f"{why_line} {card.get('form_line', '')}".strip()

    body = _strip_translation_opener(qid, raw_t, subj)

    if qid in CARD_HOOK_OVERRIDES:
        hook = CARD_HOOK_OVERRIDES[qid]
    elif subj == "文法":
        hook = _contextual_grammar_hook(pk, body, why_line)
    elif subj == "活用":
        hook = HENKEI_HOOKS.get(pk, "")
        if pk == "V-032" and "使役" in body[:35] and "被动" not in body[:18]:
            hook = "考一段动词使役形。"
        elif pk == "V-032" and "被动" in body[:35]:
            hook = "考五段动词被动形。"
    elif subj == "語彙":
        hook = _vocab_hook(pk, ans, choices, body)
    elif subj == "聴解":
        hook = LISTENING_HOOKS.get(pk, "")
    else:
        hook = ""

    final_txt = _dedup_hook_and_body(hook, body)
    final_txt = re.sub(r"([。！？])[。！？]+", r"\1", final_txt)
    final_txt = re.sub(r"\s{2,}", " ", final_txt).strip()
    return final_txt


def build_direct_exp_turns(qid: str, card: dict[str, Any], meta: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """Return direct-to-Chinese exp_turns with ZERO leading Japanese sentence/dialogue re-read."""
    txt = build_direct_exp_text(qid, card, meta)
    return [("T", txt)] if txt else []


if __name__ == "__main__":
    from clear_explanations import CARDS_75
    from tutor_data import TUTOR_ITEMS
    from adaptive_bank import EXTRA_PRIMARY_CARDS, NEW_PRIMARY_CARDS, VARIANT_CARDS, NEW_VARIANT_CARDS

    meta_map: dict[str, dict] = {k: dict(v, id=k) for k, v in TUTOR_ITEMS.items()}
    for src in (EXTRA_PRIMARY_CARDS, NEW_PRIMARY_CARDS, VARIANT_CARDS, NEW_VARIANT_CARDS):
        for it in src:
            if it.get("id"):
                meta_map[it["id"]] = it

    bad = []
    for qid, card in CARDS_75.items():
        turns = build_direct_exp_turns(qid, card, meta_map.get(qid))
        if len(turns) != 1 or turns[0][0] != "T":
            bad.append((qid, "non-T turns"))
            continue
        t = turns[0][1]
        if len(t) < 18 or "—" in t or not t.startswith("考"):
            bad.append((qid, t[:50]))
        if re.search(r"这[句一]?话?(?:是说|是在|吐槽|抱怨|感叹|安慰|庆幸)", t):
            bad.append((qid, "zheju:" + t[:50]))
    if bad:
        raise SystemExit(f"direct_explain_rules self-test FAILED ({len(bad)}): {bad[:5]}")
    print(f"direct_explain_rules self-test PASSED: {len(CARDS_75)}/{len(CARDS_75)} direct-Chinese zero-reread cards green!")


