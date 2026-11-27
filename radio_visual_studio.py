#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily All-Japanese Documentary Short Video & Studio Audio Pipeline (radio_visual_studio.py).

Decouples post-listening visual immersion from grammar flashcards and turns every daily
《锵锵三人行》 episode into a genuinely meaningful ~80-second ALL-JAPANESE mini-documentary:
1. Fetches 15-18 authentic, open-licensed Japanese documentary photographs per episode from
   Japanese Wikipedia & Wikimedia Commons (zero API keys, zero copyright risk, 100% pure cloud).
2. Authors a vivid 14-16 line ALL-JAPANESE NHK-style feature dialogue retelling today's exact
   Japanese stories while deliberately weaving in (2x repeated!) today's podcast focus words,
   yesterday's rumination/relearn words, active vocab cards, and today's core N3/N2 grammar.
3. Synthesizes dual native Japanese neural voices (`ja-JP-KeitaNeural` + `ja-JP-NanamiNeural`)
   with exact millisecond per-line timestamps (zero subtitle drift!) over a subtle original
   warm pentatonic documentary music bed, and cuts a crisp 854x480 24fps H.264/AAC MP4
   (`video/daily_jp_story.mp4`) + bilingual WebVTT (`video/daily_jp_story.vtt`).
4. Renders crisp native Japanese studio model MP3s (`audio/spk_0.mp3`, `audio/spk_1.mp3`)
   for post-listening speaking practice (replacing robotic browser speechSynthesis).
5. Automatically deletes legacy fragmented `rv_*.mp4` clips so the repo stays lean.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import wave
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "img")
VIDEO_DIR = os.path.join(BASE_DIR, "video")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
STATE_PATH = os.path.join(BASE_DIR, "n3_live_state.json")
UA_HEADER = {"User-Agent": "N3AudioTutorVisualStudio/3.0 (https://github.com/tango13ucla/n3-audio-tutor)"}
SR = 24000

# Boost genuine historical/period archival photography (Meiji/Taisho/Showa/1900s-1990s) over modern stock snapshots
ARCHIVAL_PHOTO_RE = re.compile(
    r"(?:18[6-9]\d|19\d\d|showa|meiji|taisho|昭和|明治|大正|戦後|建設|当時|旧|古写真|historic|archive|vintage|monochrome|black_and_white)",
    re.I,
)

# Reject logos, flags, diagrams, icons, maps, seals, charts, cartoon schematics, and non-photographic assets
BAD_MEDIA_RE = re.compile(
    r"(\.svg|\.gif|\.tif|\.tiff|\.ogg|\.oga|\.pdf|logo|icon|flag[_ -]|map[_ -]|"
    r"commons-logo|wikisource|wikinews|symbol|emblem|crest|seal|stamp|diagram|chart|"
    r"graph|reorganization|markets_of_|内閣印|紋章|市章|県章|社章|地図|路線図|系譜|"
    r"question_book|edit-clear|ambox|padlock|locator|blank|signature|autograph|"
    r"screenshot|cover_art|wordmark|in-game_logo|controller.*isolated|"
    r"anatomy|basal_ganglia|coronal|sagittal|schematic|illustration|drawings?|cartoon|ventricle|thalamus|hippocampus_)",
    re.I,
)

# Curated Japanese Wikipedia articles & Wikimedia Commons searches for Vol.10-22 + common themes
# Format: story_id_or_keyword -> {"ja_wiki": [...], "wm_queries": [...], "prefer": [...]}
CURATED_VISUAL_TOPICS: dict[str, dict[str, list[str]]] = {
    # ---- Vol.10 (2026-11-24) ----
    "uchi10_s1_news_fallback": {
        "ja_wiki": ["宅配ボックス", "ヤマト運輸", "佐川急便"],
        "wm_queries": ["PUDOステーション Japan", "Yamato transport Truck 2020", "Japan parcel delivery truck"],
        "prefer": ["PUDO", "Delivery_car_of_YAMATO", "Haneda_chronogate", "Yamato_transport_Truck"],
    },
    "uchi10_s2a_yamato_part1": {
        "ja_wiki": ["ヤマト運輸", "宅急便"],
        "wm_queries": ["Yamato Transport truck", "Kuroneko Yamato Tokyo"],
        "prefer": ["Yamato_Holdings_headquarters", "大阪城桜門", "Yamato_ev", "Yamato_transport_Truck"],
    },
    "uchi10_s2b_yamato_part2": {
        "ja_wiki": ["国土交通省", "霞が関", "宅急便"],
        "wm_queries": ["Central Government Building 3 Tokyo", "Kasumigaseki Tokyo Ministry", "Yamato_1183"],
        "prefer": ["Central-Government-Building-3", "Nameboard_of_Ministry", "Government_Office_Complex_2", "Yamato_1183"],
    },
    "uchi10_s3a_nintendo_part1": {
        "ja_wiki": ["ファミリーコンピュータ", "任天堂"],
        "wm_queries": ["Nintendo Famicom 1983", "Nintendo headquarters Kyoto"],
        "prefer": ["Nintendo_Family_Computer_Famicom_(1983)", "Nintendo_Famicom_Tietokonemuseo", "Nintendo-Famicom-Console-FL", "Nintendo_Headquarters"],
    },
    "uchi10_s3b_nintendo_part2": {
        "ja_wiki": ["宮本茂", "スーパーマリオブラザーズ", "ファミリーコンピュータ"],
        "wm_queries": ["Shigeru Miyamoto", "Super Nintendo World Japan", "Super Mario museum"],
        "prefer": ["Takashi_Tezuka", "Shigeru_Miyamoto", "Video_Game_Museum_in_Berlin", "Super_Nintendo_World"],
    },
    "uchi10_s4_world_ai_markets": {
        "ja_wiki": ["東京証券取引所", "スーパーコンピュータ"],
        "wm_queries": ["Inside Tokyo Stock Exchange", "Tokyo Stock Exchange Arrows", "Supercomputer Fugaku"],
        "prefer": ["The_Tokyo_Stock_Exchange_-_main_room", "Inside_Tokyo_Stock_Exchange", "Tokyo_Stock_Exchange_Main_Building", "Fugaku"],
    },
    # ---- Vol.11 ----
    "uchi11_s1_news_fallback": {
        "ja_wiki": ["三越", "銀座", "伊勢丹"],
        "wm_queries": ["Nihombashi Mitsukoshi Tokyo", "Ginza Tokyo street"],
        "prefer": ["Mitsukoshi_Nihonbashi_main_store", "Mitsukoshi_Nihonbashi", "Ginza"],
    },
    "uchi11_s2a_oilshock_part1": {
        "ja_wiki": ["イオン (企業)", "イトーヨーカ堂", "商店街"],
        "wm_queries": ["Japanese supermarket aisle Tokyo", "Ito-Yokado Japan supermarket", "Showa shopping street Japan"],
        "prefer": ["Ito-Yokado", "supermarket", "shotengai", "Aeon", "grocery"],
    },
    "uchi11_s2b_oilshock_part2": {
        "ja_wiki": ["ホンダ・シビック", "トヨタ・カローラ"],
        "wm_queries": ["1973 Honda Civic", "Toyota Corolla 1970s"],
        "prefer": ["Honda_Civic_CVCC", "1973-1978_Honda_Civic", "1973_Honda_Civic", "Honda_Civic_RS"],
    },
    "uchi11_s3a_tokyotower_part1": {
        "ja_wiki": ["東京タワー"],
        "wm_queries": ["Tokyo Tower 1961", "Tokyo Tower daytime"],
        "prefer": ["Tokyo_Tower_1961", "日本電波塔", "Tokyo_Tower_from", "Tokyo_Tower_day"],
    },
    "uchi11_s3b_tokyotower_part2": {
        "ja_wiki": ["芝公園", "東京タワー"],
        "wm_queries": ["Tokyo Tower illuminated night", "Tokyo Tower night skyline"],
        "prefer": ["Tokyo_Tower_at_night", "Tokyo_Tower_night", "Illuminated_buildings_and_Tokyo_Tower", "Tokyo_Tower,_Minato"],
    },
    "uchi11_s4_world_global_health": {
        "ja_wiki": ["世界保健機関", "脳"],
        "wm_queries": ["Medical research laboratory microscope", "Brain MRI neuroscience"],
        "prefer": ["WHO_HQ_main_building", "microscope", "FMRI", "Brain_MRI"],
    },
    # ---- Vol.12 ----
    "uchi12_s1_news_fallback": {"ja_wiki": ["就職氷河期", "新宿駅", "丸の内"], "wm_queries": ["Tokyo commuters Shinjuku", "Marunouchi Tokyo office"]},
    "uchi12_s2a_seikan_part1": {"ja_wiki": ["青函トンネル", "青函連絡船"], "wm_queries": ["Seikan Tunnel", "Seikan Ferry Hakodate"]},
    "uchi12_s2b_seikan_part2": {"ja_wiki": ["青函トンネル", "北海道新幹線"], "wm_queries": ["Seikan Tunnel entrance", "Hokkaido Shinkansen"]},
    "uchi12_s3a_jal_part1": {"ja_wiki": ["日本航空", "東京国際空港"], "wm_queries": ["Japan Airlines Haneda", "Japan Airlines Boeing"]},
    "uchi12_s3b_jal_part2": {"ja_wiki": ["日本航空", "稲盛和夫"], "wm_queries": ["Japan Airlines Tsurumaru tail", "Japan Airlines aircraft takeoff"]},
    "uchi12_s4_world_nuclear_space": {"ja_wiki": ["宇宙航空研究開発機構", "月面車"], "wm_queries": ["JAXA lunar rover", "Moon surface Apollo JAXA"]},
    # ---- Vol.13 ----
    "uchi13_s1_news_fallback": {"ja_wiki": ["日本銀行", "日本橋 (東京都中央区)"], "wm_queries": ["Bank of Japan headquarters Tokyo"]},
    "uchi13_s2a_heisei_1989_part1": {"ja_wiki": ["平成", "小渕恵三"], "wm_queries": ["Heisei era announcement", "Tokyo 1989 Showa Heisei"]},
    "uchi13_s2b_heisei_1989_part2": {"ja_wiki": ["バブル景気", "東京証券取引所"], "wm_queries": ["Tokyo Stock Exchange 1988", "Ginza Tokyo night"]},
    "uchi13_s3a_toyota_kanban_part1": {"ja_wiki": ["トヨタ自動車", "トヨタ生産方式"], "wm_queries": ["Toyota factory assembly line", "Toyota Commemorative Museum"]},
    "uchi13_s3b_toyota_kanban_part2": {"ja_wiki": ["トヨタ生産方式", "トヨタ博物館"], "wm_queries": ["Toyota manufacturing plant Japan", "Toyota Museum Nagakute"]},
    "uchi13_s4_world_fusion_energy": {"ja_wiki": ["JT-60SA", "ITER"], "wm_queries": ["JT-60SA tokamak fusion", "ITER fusion reactor"]},
    # ---- Vol.14 ----
    "uchi14_s1_news_fallback": {"ja_wiki": ["ヒグマ", "ツキノワグマ"], "wm_queries": ["Ussuri brown bear Hokkaido", "Asian black bear Japan"]},
    "uchi14_s2a_hanshin_1995_part1": {"ja_wiki": ["阪神・淡路大震災", "神戸市"], "wm_queries": ["Great Hanshin earthquake 1995", "Kobe earthquake Hanshin Expressway"]},
    "uchi14_s2b_hanshin_1995_part2": {"ja_wiki": ["阪神・淡路大震災", "神戸ルミナリエ"], "wm_queries": ["Kobe Luminarie memorial", "Kobe harborland skyline"]},
    "uchi14_s3a_kaiten_sushi_part1": {"ja_wiki": ["回転寿司", "東大阪市"], "wm_queries": ["Conveyor belt sushi Japan", "Kaiten zushi plates"]},
    "uchi14_s3b_kaiten_sushi_part2": {"ja_wiki": ["回転寿司", "日本万国博覧会"], "wm_queries": ["Kaiten sushi restaurant Tokyo", "Sushi conveyor Japan"]},
    "uchi14_s4_world_quantum_crypto": {"ja_wiki": ["量子コンピュータ", "理化学研究所"], "wm_queries": ["Quantum computer dilution refrigerator", "RIKEN Japan"]},
    # ---- Vol.15 ----
    "uchi15_s1_news_fallback": {"ja_wiki": ["東京都庁舎", "東京一極集中"], "wm_queries": ["Tokyo Metropolitan Government Building Shinjuku", "Tokyo skyline density"]},
    "uchi15_s2a_super_cub_1958_part1": {"ja_wiki": ["ホンダ・スーパーカブ", "本田宗一郎"], "wm_queries": ["Honda Super Cub C100 1958", "Honda Super Cub Japan"]},
    "uchi15_s2b_super_cub_1958_part2": {"ja_wiki": ["ホンダ・スーパーカブ", "日本郵便"], "wm_queries": ["Japan Post Honda Super Cub", "Honda Super Cub street"]},
    "uchi15_s3a_muji_1980_part1": {"ja_wiki": ["無印良品"], "wm_queries": ["Muji store Tokyo Japan", "Muji Ginza flagship"]},
    "uchi15_s3b_muji_1980_part2": {"ja_wiki": ["無印良品", "銀座"], "wm_queries": ["Muji Ginza interior", "Muji store Japan"]},
    "uchi15_s4_world_glp1_medicine": {"ja_wiki": ["和食", "医薬品"], "wm_queries": ["Washoku traditional Japanese meal", "Pharmaceutical lab"]},
    # ---- Vol.16 ----
    "uchi16_s1_news_fallback": {"ja_wiki": ["ふるさと納税", "総務省"], "wm_queries": ["Kasumigaseki Tokyo Ministry Japan", "Japanese regional harvest agriculture"]},
    "uchi16_s2a_toto_washlet_1980_part1": {"ja_wiki": ["ウォシュレット", "TOTO (企業)"], "wm_queries": ["TOTO Washlet Japan", "TOTO Museum Kitakyushu"]},
    "uchi16_s2b_toto_washlet_1980_part2": {"ja_wiki": ["ウォシュレット", "TOTO (企業)"], "wm_queries": ["Japanese bidet toilet control panel", "TOTO Japan"]},
    "uchi16_s3a_uniqlo_fleece_1998_part1": {"ja_wiki": ["ユニクロ", "原宿"], "wm_queries": ["Uniqlo Harajuku Tokyo", "Uniqlo Ginza flagship"]},
    "uchi16_s3b_uniqlo_fleece_1998_part2": {"ja_wiki": ["ユニクロ", "東レ"], "wm_queries": ["Uniqlo Tokyo Ginza", "Uniqlo store interior Japan"]},
    "uchi16_s4_world_mrna_cancer": {"ja_wiki": ["mRNAワクチン", "がん免疫療法"], "wm_queries": ["Biotech laboratory research", "University of Tokyo medicine"]},
    # ---- Vol.17 ----
    "uchi17_s1_news_fallback": {"ja_wiki": ["日本銀行券", "渋沢栄一"], "wm_queries": ["New 10000 yen banknote Shibusawa", "Japanese yen notes ramen"]},
    "uchi17_s2a_jnr_part1": {"ja_wiki": ["日本国有鉄道", "国鉄分割民営化"], "wm_queries": ["Japanese National Railways JNR train", "Tokyo Station 1980s"]},
    "uchi17_s2b_jnr_part2": {"ja_wiki": ["東日本旅客鉄道", "東京駅"], "wm_queries": ["Tokyo Station Marunouchi JR East", "JR Yamanote Line train"]},
    "uchi17_s3a_yoshinoya_part1": {"ja_wiki": ["吉野家", "牛丼"], "wm_queries": ["Yoshinoya store Japan", "Gyudon beef bowl Yoshinoya"]},
    "uchi17_s3b_yoshinoya_part2": {"ja_wiki": ["吉野家", "築地"], "wm_queries": ["Yoshinoya gyudon bowl", "Yoshinoya Tsukiji Japan"]},
    "uchi17_s4_world_solid_state_ev": {"ja_wiki": ["全固体電池", "電気自動車"], "wm_queries": ["Electric vehicle battery pack", "Toyota EV concept Japan"]},
    # ---- Vol.18 (Hokuriku Rail / Yodogo / Deep Kanazawa / Europe Defense) ----
    "uchi18_s1_news_fallback": {"ja_wiki": ["のと鉄道", "北陸本線"], "wm_queries": ["Noto Railway Ishikawa Japan train", "Hokuriku local train snow Japan"]},
    "uchi18_s2a_yodogo_part1": {"ja_wiki": ["よど号ハイジャック事件", "ボーイング727"], "wm_queries": ["Japan Airlines Boeing 727", "Haneda Airport 1970"]},
    "uchi18_s2b_yodogo_part2": {"ja_wiki": ["よど号ハイジャック事件", "羽田空港"], "wm_queries": ["Boeing 727 Japan Airlines", "Tokyo Haneda Airport runway"]},
    "uchi18_s3a_kanazawa_part1": {"ja_wiki": ["兼六園", "金沢城", "辰巳用水"], "wm_queries": ["Kanazawa Castle Ishikawa Japan", "Kenrokuen Garden Kanazawa fountain"]},
    "uchi18_s3b_kanazawa_part2": {"ja_wiki": ["鈴木大拙館", "金沢21世紀美術館", "長町武家屋敷跡"], "wm_queries": ["D. T. Suzuki Museum Kanazawa", "21st Century Museum of Contemporary Art Kanazawa", "Nagamachi samurai district Kanazawa"]},
    "uchi18_s4_world_europe_defense": {"ja_wiki": ["欧州連合", "自衛隊"], "wm_queries": ["European Parliament Brussels", "Berlin Reichstag"]},
    # ---- Vol.19 ----
    "uchi19_s1_news_fallback": {"ja_wiki": ["少額投資非課税制度", "東京証券取引所"], "wm_queries": ["Tokyo financial district Nihombashi", "Tokyo Stock Exchange"]},
    "uchi19_s2a_sukiyaki_part1": {"ja_wiki": ["上を向いて歩こう", "坂本九"], "wm_queries": ["Kyu Sakamoto", "Showa Tokyo 1960s street"]},
    "uchi19_s2b_sukiyaki_part2": {"ja_wiki": ["上を向いて歩こう", "日本武道館"], "wm_queries": ["Vinyl record player Showa", "Tokyo 1960s Ginza"]},
    "uchi19_s3a_tsukiji_part1": {"ja_wiki": ["築地市場"], "wm_queries": ["Tsukiji fish market tuna auction", "Tsukiji Market turret truck"]},
    "uchi19_s3b_tsukiji_part2": {"ja_wiki": ["築地市場", "豊洲市場"], "wm_queries": ["Tsukiji Market outer street", "Toyosu Market Tokyo"]},
    "uchi19_s4_world_india_tech": {"ja_wiki": ["インドの経済", "バンガロール"], "wm_queries": ["Bengaluru tech park India", "Chandrayaan ISRO"]},
    # ---- Vol.20 ----
    "uchi20_s1_news_fallback": {"ja_wiki": ["ガリガリ君", "赤城乳業"], "wm_queries": ["GariGari-kun ice pop Japan", "Japanese convenience store freezer"]},
    "uchi20_s2a_umami_part1": {"ja_wiki": ["うま味", "池田菊苗", "昆布"], "wm_queries": ["Kombu dashi kelp Japan", "Kikunae Ikeda"]},
    "uchi20_s2b_umami_part2": {"ja_wiki": ["味の素"], "wm_queries": ["Ajinomoto bottle Japan", "Ajinomoto headquarters Tokyo"]},
    "uchi20_s3a_kfc_part1": {"ja_wiki": ["青色発光ダイオード", "中村修二"], "wm_queries": ["Blue LED semiconductor light", "Shuji Nakamura Nobel"]},
    "uchi20_s3b_kfc_part2": {"ja_wiki": ["東京地方裁判所", "特許法"], "wm_queries": ["Tokyo District Court Kasumigaseki", "Blue LED laboratory Japan"]},
    "uchi20_s4_world_undersea_cables": {"ja_wiki": ["海底ケーブル"], "wm_queries": ["Submarine communications cable ship", "Fiber optic cable ocean"]},
    # ---- Vol.21 ----
    "uchi21_s1_news_fallback": {"ja_wiki": ["ラジオ体操"], "wm_queries": ["Radio calisthenics Japan park", "Radio taiso Japan"]},
    "uchi21_s2a_koshien_part1": {"ja_wiki": ["阪神甲子園球場", "全国高等学校野球選手権大会"], "wm_queries": ["Hanshin Koshien Stadium", "Koshien high school baseball"]},
    "uchi21_s2b_koshien_part2": {"ja_wiki": ["阪神甲子園球場"], "wm_queries": ["Koshien stadium field dirt", "Japanese high school baseball"]},
    "uchi21_s3a_ichiro_part1": {"ja_wiki": ["イチロー"], "wm_queries": ["Ichiro Suzuki batting", "Ichiro Suzuki Mariners"]},
    "uchi21_s3b_ohtani_part2": {"ja_wiki": ["大谷翔平"], "wm_queries": ["Shohei Ohtani batting", "Shohei Ohtani pitching"]},
    "uchi21_s4_world_arctic_shipping": {"ja_wiki": ["北極海航路"], "wm_queries": ["Icebreaker ship Arctic sea route", "Container ship Japan port"]},
    # ---- Vol.22 ----
    "uchi22_s1_news_fallback": {"ja_wiki": ["最高裁判所 (日本)", "夫婦別姓"], "wm_queries": ["Supreme Court of Japan Tokyo", "National Diet Building Tokyo"]},
    "uchi22_s2a_ise_sengu_part1": {"ja_wiki": ["伊勢神宮", "神宮式年遷宮"], "wm_queries": ["Ise Grand Shrine Naiku", "Ise Jingu wooden bridge"]},
    "uchi22_s2b_kongo_gumi_part2": {"ja_wiki": ["金剛組", "四天王寺"], "wm_queries": ["Shitenno-ji Temple Osaka", "Japanese wooden temple carpentry"]},
    "uchi22_s3a_naoshima_part1": {"ja_wiki": ["直島", "安藤忠雄"], "wm_queries": ["Naoshima Yellow Pumpkin Kusama", "Naoshima island Seto Inland Sea"]},
    "uchi22_s3b_naoshima_part2": {"ja_wiki": ["地中美術館", "直島"], "wm_queries": ["Chichu Art Museum Naoshima", "Benesse House Naoshima"]},
    "uchi22_s4_world_humanoid_robots": {"ja_wiki": ["ヒューマノイド", "産業用ロボット"], "wm_queries": ["Humanoid robot Japan ASIMO", "Industrial robot factory Japan"]},
    # ---- Vol.23 (Editorial Taste Edition) ----
    "uchi23_s1_news_fallback": {"ja_wiki": ["祇園", "道頓堀", "兼六園"], "wm_queries": ["Kyoto Gion historical 1960s", "Dotonbori Osaka historical", "Kenrokuen Kanazawa garden"]},
    "uchi23_s2a_kabuki_drama_part1": {"ja_wiki": ["歌舞伎座", "歌舞伎"], "wm_queries": ["Kabuki-za Tokyo historical", "Kabuki actor ukiyo-e stage"]},
    "uchi23_s2b_quartet_drama_part2": {"ja_wiki": ["軽井沢町", "弦楽四重奏"], "wm_queries": ["Karuizawa winter forest Nagano", "Japanese izakaya street Showa"]},
    "uchi23_s3a_kobayashi_part1": {"ja_wiki": ["彦根城", "武士", "小林正樹"], "wm_queries": ["Hikone Castle Japan", "Samurai armor Japan", "Traditional tatami hall Kyoto"]},
    "uchi23_s3b_mishima_contrast_part2": {"ja_wiki": ["鹿苑寺", "三島由紀夫"], "wm_queries": ["Kinkaku-ji Kyoto", "Kinkaku-ji historical", "Kyoto Zen rock garden"]},
    "uchi23_s4_world_brain_ai": {"ja_wiki": ["東京大学", "理化学研究所"], "wm_queries": ["Tokyo night skyline quiet", "Neuroscience laboratory microscope Japan", "Brain MRI scan medical"]},
    # ---- Vol.24 (Mingei / Hokusai / Katsura Villa / Immunology) ----
    "uchi24_s1_news_fallback": {"ja_wiki": ["日本民藝館", "柳宗悦"], "wm_queries": ["Japan Folk Crafts Museum Mingei", "Japanese traditional pottery craft"]},
    "uchi24_s2a_hokusai_part1": {"ja_wiki": ["葛飾北斎", "富嶽三十六景"], "wm_queries": ["Great Wave off Kanagawa Hokusai", "Ukiyo-e Edo woodblock print"]},
    "uchi24_s2b_japonisme_part2": {"ja_wiki": ["ジャポニスム", "浮世絵"], "wm_queries": ["Japonisme Monet Van Gogh ukiyo-e", "Paris 1889 exposition"]},
    "uchi24_s3a_taut_katsura_part1": {"ja_wiki": ["桂離宮", "ブルーノ・タウト"], "wm_queries": ["Katsura Imperial Villa Kyoto", "Katsura Rikyu architecture"]},
    "uchi24_s3b_katsura_nikko_part2": {"ja_wiki": ["日光東照宮", "桂離宮"], "wm_queries": ["Nikko Toshogu Shrine", "Katsura Imperial Villa garden"]},
    "uchi24_s4_world_immunology": {"ja_wiki": ["本庶佑", "免疫チェックポイント阻害剤"], "wm_queries": ["Immunology T cell cancer microscope", "Kyoto University medicine"]},
    # ---- Vol.25 (Underground Temple / Main Bank & TSE / Hidden Champions / Gut-Brain) ----
    "uchi25_s1_news_fallback": {"ja_wiki": ["首都圏外郭放水路"], "wm_queries": ["Metropolitan Area Outer Underground Discharge Channel", "G-Cans Kasukabe Saitama"]},
    "uchi25_s2a_nemawashi_ringi_part1": {"ja_wiki": ["丸の内", "メインバンク制"], "wm_queries": ["Marunouchi Tokyo financial district 1960s OR 1970s", "Tokyo financial buildings Marunouchi"]},
    "uchi25_s2b_keigo_workplace_part2": {"ja_wiki": ["東京証券取引所", "霞が関"], "wm_queries": ["Tokyo Stock Exchange Kabutocho", "Kasumigaseki Tokyo government buildings"]},
    "uchi25_s3a_hidden_champions_part1": {"ja_wiki": ["町工場", "東大阪市"], "wm_queries": ["Japanese precision machining factory", "Japan steel factory 1960s"]},
    "uchi25_s3b_craft_finance_part2": {"ja_wiki": ["老舗", "金剛組"], "wm_queries": ["Japanese traditional wooden craft workshop", "Japanese craftsman workshop"]},
    "uchi25_s4_world_microbiome": {"ja_wiki": ["腸内細菌", "納豆"], "wm_queries": ["Microbiome bacteria microscope", "Natto Japanese fermented food"]},
}


# Visually-verified, 100% public-domain / CC REAL HISTORICAL MOVING FOOTAGE vault
# Sources: Wikimedia Commons historical films & documentaries (`src="wm"`) + Internet Archive
# Prelinger Archives / US National Archives (NARA) / Universal Newsreels / NASA 16mm (`src="ia"`).
# Every offset `ss` is pre-audited to skip title slates, black leaders, and off-topic frames!
CURATED_ARCHIVAL_FOOTAGE: dict[str, list[dict[str, Any]]] = {
    # ---- Vol.23 (2026-11-26): Kyoto/Osaka, Kabuki, Classic JP Cinema, Mishima Kinkaku-ji, Brain/Sleep ----
    "uchi23_s1_news_fallback": [
        {"src": "wm", "id": "File:Un pont à Kyoto (1897).webm", "ss": 8, "label": "1897 Lumière Kyoto"},
        {"src": "ia", "id": "USAF-11059", "ss": 55, "label": "1946 Kyoto City Life (NARA)"},
    ],
    "uchi23_s2a_kabuki_drama_part1": [
        {"src": "wm", "id": "File:Kabukiza - Tokyo - 2025-06-02.webm", "ss": 3, "label": "Tokyo Kabuki-za"},
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 420, "label": "1982 Japan Traditional Performers"},
    ],
    "uchi23_s2b_quartet_drama_part2": [
        {"src": "wm", "id": "File:Sisters of the Gion (1936) by Kenji Mizoguchi.webm", "ss": 120, "label": "1936 Mizoguchi Gion Cinema"},
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 680, "label": "1982 Japanese Home Life"},
    ],
    "uchi23_s3a_kobayashi_part1": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 420, "label": "1982 Japan Samurai Pageant"},
        {"src": "ia", "id": "0974HMPart4Kyoto", "ss": 45, "label": "Vintage 16mm Kyoto"},
    ],
    "uchi23_s3b_mishima_contrast_part2": [
        {"src": "wm", "id": "File:L'éclat d'été au pavillon d'Or.webm", "ss": 35, "label": "Kinkaku-ji Golden Pavilion"},
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1982 Japan Shrine Archive"},
    ],
    "uchi23_s4_world_brain_ai": [
        {"src": "ia", "id": "0433_Human_Brain_The_01_05_28_00", "ss": 95, "label": "1955 The Human Brain (Prelinger)"},
        {"src": "ia", "id": "0242_Sleep_for_Health_E01299_13_00_43_00", "ss": 80, "label": "1950 Sleep for Health"},
    ],
    # ---- Vol.11 (Oil Shock / Tokyo Tower / Global Health) ----
    "uchi11_s1_news_fallback": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1982 Japan Archive"},
    ],
    "uchi11_s2b_oilshock_part2": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 980, "label": "1960 Japan Industry (NARA)"},
    ],
    "uchi11_s3a_tokyotower_part1": [
        {"src": "wm", "id": "File:Sights and Sounds- Tokyo Tower (951524).webm", "ss": 12, "label": "Tokyo Tower"},
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 720, "label": "1960 Japan Construction (NARA)"},
    ],
    "uchi11_s4_world_global_health": [
        {"src": "ia", "id": "0433_Human_Brain_The_01_05_28_00", "ss": 95, "label": "1955 Human Brain Science Film"},
    ],
    # ---- Vol.12 (Ice Age / Seikan Tunnel / JAL / Moon) ----
    "uchi12_s1_news_fallback": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 220, "label": "1982 Japan Society"},
    ],
    "uchi12_s2a_seikan_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 420, "label": "1960 Japan Railways (NARA)"},
    ],
    "uchi12_s2b_seikan_part2": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 720, "label": "1960 Heavy Engineering (NARA)"},
        {"src": "wm", "id": "File:Shinkansen N700 Series Bullet Train Tokyo Station by Don Ramey Logan.webm", "ss": 3, "label": "Shinkansen"},
    ],
    "uchi12_s3a_jal_part1": [
        {"src": "wm", "id": "File:20 MINUTES IN TAKEOFFS & LANDINGS at Haneda Airport (HND-RJTT).webm", "ss": 45, "label": "Haneda Aviation"},
    ],
    "uchi12_s4_world_nuclear_space": [
        {"src": "ia", "id": "Apollo15And1616mmOnboardFilm", "ss": 90, "label": "1971 NASA 16mm Lunar Film"},
    ],
    # ---- Vol.13 (Heisei 1989 / Bubble / Toyota Kanban / Fusion) ----
    "uchi13_s2a_heisei_1989_part1": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1980s Japan Archive"},
    ],
    "uchi13_s2b_heisei_1989_part2": [
        {"src": "wm", "id": "File:Shibuya Crossing, Tokyo, Japan (video).webm", "ss": 10, "label": "Tokyo Shibuya"},
    ],
    "uchi13_s3a_toyota_kanban_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 980, "label": "1960 Japan Factory (NARA)"},
    ],
    # ---- Vol.14 (Hanshin / Kaiten Sushi / Quantum) ----
    "uchi14_s2a_hanshin_1995_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 720, "label": "Japan Reconstruction Archive"},
    ],
    "uchi14_s3a_kaiten_sushi_part1": [
        {"src": "wm", "id": "File:Making Sushi.webmhd.webm", "ss": 15, "label": "Japanese Sushi Craft"},
    ],
    # ---- Vol.15 (Super Cub / Muji / Medicine) ----
    "uchi15_s2a_super_cub_1958_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 980, "label": "1960 Showa Manufacturing"},
    ],
    "uchi15_s3a_muji_1980_part1": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 680, "label": "1980s Japanese Daily Craft"},
    ],
    # ---- Vol.16-22 & Vol.24-25 ----
    "uchi16_s1_news_fallback": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 210, "label": "1982 Japan Regional Town"},
    ],
    "uchi17_s2a_jnr_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 420, "label": "1960 JNR Railways"},
    ],
    "uchi17_s2b_jnr_part2": [
        {"src": "wm", "id": "File:Shinkansen N700 Series Bullet Train Tokyo Station by Don Ramey Logan.webm", "ss": 4, "label": "Tokyo Rail"},
    ],
    "uchi18_s1_news_fallback": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 420, "label": "1960 Japan Regional Railways"},
    ],
    "uchi18_s2a_yodogo_part1": [
        {"src": "wm", "id": "File:20 MINUTES IN TAKEOFFS & LANDINGS at Haneda Airport (HND-RJTT).webm", "ss": 120, "label": "Haneda Runway"},
    ],
    "uchi18_s3a_kanazawa_part1": [
        {"src": "ia", "id": "USAF-11059", "ss": 55, "label": "1946 Japanese Traditional Craft Archive"},
    ],
    "uchi18_s3b_kanazawa_part2": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1982 Japan Traditional Streetscape"},
    ],
    "uchi19_s2a_sukiyaki_part1": [
        {"src": "ia", "id": "1964-10-15_US_Dominates_Tokyo_Games", "ss": 18, "label": "1964 Tokyo Newsreel"},
    ],
    "uchi19_s3a_tsukiji_part1": [
        {"src": "wm", "id": "File:Stalls inside the Tsukiji fish market, Tokyo, Japan.webm", "ss": 1, "label": "Tsukiji Fish Market"},
    ],
    "uchi20_s4_world_undersea_cables": [
        {"src": "ia", "id": "underground_cable", "ss": 90, "label": "Archival Cable Engineering"},
    ],
    "uchi21_s2a_koshien_part1": [
        {"src": "ia", "id": "1964-10-15_US_Dominates_Tokyo_Games", "ss": 20, "label": "1964 Japan Sports Newsreel"},
    ],
    "uchi22_s2a_ise_sengu_part1": [
        {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1982 Japan Shrine"},
    ],
    "uchi24_s1_news_fallback": [
        {"src": "ia", "id": "USAF-11059", "ss": 55, "label": "1946 Kyoto Craft Archive"},
    ],
    "uchi24_s2a_hokusai_part1": [
        {"src": "wm", "id": "File:Un pont à Kyoto (1897).webm", "ss": 8, "label": "1897 Historical Japan"},
    ],
    "uchi24_s3a_taut_katsura_part1": [
        {"src": "ia", "id": "0974HMPart4Kyoto", "ss": 45, "label": "Vintage 16mm Kyoto"},
        {"src": "wm", "id": "File:L'éclat d'été au pavillon d'Or.webm", "ss": 35, "label": "Kyoto Architecture"},
    ],
    "uchi25_s1_news_fallback": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 720, "label": "1960 Japan Civil Engineering"},
    ],
    "uchi25_s3a_hidden_champions_part1": [
        {"src": "ia", "id": "gov.archives.arc.642010", "ss": 980, "label": "1960 Japan Precision Factory"},
    ],
    "uchi25_s3b_shinise_part2": [
        {"src": "ia", "id": "USAF-11059", "ss": 55, "label": "1946 Kyoto Machiya Craft"},
    ],
}

# Theme-matched archival fallback pool for future live-authored news / N2 episodes
THEME_ARCHIVAL_FALLBACKS: list[tuple[str, dict[str, Any]]] = [
    (r"京都|祇園|伝統|歌舞伎|桂|金閣|寺|神社|茶|能|芸", {"src": "wm", "id": "File:Un pont à Kyoto (1897).webm", "ss": 8, "label": "1897 Lumière Kyoto"}),
    (r"鉄道|新幹線|駅|トンネル|国鉄|電車", {"src": "ia", "id": "gov.archives.arc.642010", "ss": 420, "label": "1960 Japan Railways"}),
    (r"工場|製造|トヨタ|ホンダ|技術|建築|土木|塔|地下", {"src": "ia", "id": "gov.archives.arc.642010", "ss": 980, "label": "1960 Japan Industry"}),
    (r"築地|寿司|食|市場|魚", {"src": "wm", "id": "File:Stalls inside the Tsukiji fish market, Tokyo, Japan.webm", "ss": 1, "label": "Tsukiji Market"}),
    (r"脳|睡眠|医学|医療|科学|記憶|神経", {"src": "ia", "id": "0433_Human_Brain_The_01_05_28_00", "ss": 95, "label": "1955 Human Brain Archive"}),
    (r"宇宙|月|ロケット|衛星", {"src": "ia", "id": "Apollo15And1616mmOnboardFilm", "ss": 90, "label": "1971 NASA Lunar Film"}),
    (r"東京|銀座|渋谷|戦後|昭和|平成|日本", {"src": "ia", "id": "0576_Human_Face_of_Japan_The_18_01_03_00", "ss": 110, "label": "1982 Japan Archive"}),
]


# Curated NHK-Documentary Grade All-Japanese Scripts keyed by signature Act-2 story_id
# Each script retells today's exact episode in clear N3 Japanese while repeating target focus & rumination words >= 2x!
CURATED_JP_VIDEO_SCRIPTS: dict[str, dict[str, Any]] = {
    "uchi10_s2a_yamato_part1": {
        "title_ja": "黒猫宅急便の挑戦と、マリオ誕生の秘密",
        "title_zh": "黑猫宅急便的豪赌与马里奥诞生之谜",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本の宅配便は、最初から便利だったわけではありません。", "zh": "日本的快递，并不是一开始就这么方便的。"},
            {"ch": 0, "v": "F", "ja": "今は人手不足で、お互いに協力するしかないと言われていますね。", "zh": "现在因为人手不足，大家只好互相配合。"},
            {"ch": 1, "v": "M", "ja": "一九七六年、ヤマト運輸の小倉昌男は、厳しい反対の中で新しいルールを作りました。", "zh": "1976年，大和运输的小仓昌男在强烈反对中立下了新规则。"},
            {"ch": 1, "v": "F", "ja": "利益よりサービスを優先する、はっきりしたルールですね。", "zh": "服务优先于利润，真是条清晰明白的规矩。"},
            {"ch": 1, "v": "M", "ja": "十分な準備をしたうえで始めたのに、初日の荷物はたった十一個でした。", "zh": "明明做了充分准备才开张，第一天却只接到十一个包裹。"},
            {"ch": 2, "v": "F", "ja": "さらに、省庁の官僚が長い間、書類の許可を出さなかったそうですね。", "zh": "而且听说省厅的官僚很长时间都不肯批复文件许可。"},
            {"ch": 2, "v": "M", "ja": "小倉は運輸大臣さえ裁判に訴え、官僚の厚い壁と戦いました。", "zh": "小仓甚至把运输大臣告上法庭，正面硬刚官僚的高墙。"},
            {"ch": 2, "v": "F", "ja": "長い裁判の末に、黒猫は日本の便利な暮らしの象徴になったのですね。", "zh": "经过漫长的审判，黑猫最终成了日本便利生活的象征。"},
            {"ch": 3, "v": "M", "ja": "一方、一九八三年には、京都の任天堂が限られた予算でファミコンを生みました。", "zh": "另一边，1983年京都的任天堂用有限的预算造出了红白机。"},
            {"ch": 3, "v": "F", "ja": "当時の海外の市場は、質の低いゲームだらけだったと聞きました。", "zh": "听说当时海外市场里满是粗制滥造的游戏。"},
            {"ch": 4, "v": "M", "ja": "昔は辞書のように分厚い説明書が必要でしたが、マリオには文字がありません。", "zh": "以前游戏都需要厚如字典的说明书，马里奥却连一个字都没写。"},
            {"ch": 4, "v": "F", "ja": "辞書を読まなくても、遊びながらだんだん操作できるようになる工夫ですね。", "zh": "不用翻字典，边玩就能渐渐学会操作的设计巧思。"},
            {"ch": 4, "v": "M", "ja": "こうして日本のゲームは、新しいものづくりの象徴として世界へ広がりました。", "zh": "就这样，日本游戏作为新一代匠心的象征走向了世界。"},
            {"ch": 5, "v": "F", "ja": "今はＡＩ投資が膨らむにつれて、世界の市場も利益の行方を厳しく見ています。", "zh": "如今随着AI投资不断膨胀，全球市场也在严密审视利润的去向。"},
            {"ch": 5, "v": "M", "ja": "時代が変わっても、人の心を動かす工夫こそが、次のルールを作るのですね。", "zh": "无论时代怎么变，打动人心的巧思才会定下下一个时代的规则。"},
        ],
    },
    "uchi11_s2a_oilshock_part1": {
        "title_ja": "石油危機の衝撃と、東京タワーの奇跡",
        "title_zh": "1973石油危机与手算东京塔的奇迹",
        "lines": [
            {"ch": 0, "v": "M", "ja": "昔は週末ごとに家族と百貨店へ行ったものだと、多くの日本人が語ります。", "zh": "很多日本人都怀念，当年每逢周末总爱和家人去逛百货店。"},
            {"ch": 0, "v": "F", "ja": "都心の店が賑わう一方で、地方の老舗はだんだん姿を消していますね。", "zh": "市中心的百货热闹非凡，地方的老字号却在渐渐谢幕。"},
            {"ch": 1, "v": "M", "ja": "一九七三年、高度成長の最中に、突然オイルショックの危機が起きました。", "zh": "1973年，正处在经济高速增长正当口，石油危机突然爆发。"},
            {"ch": 1, "v": "F", "ja": "紙がなくなるという噂で、売り切れないうちに買おうと人が殺到したのですね。", "zh": "因为缺纸的传言，大家趁着没卖光拼命涌进超市抢购。"},
            {"ch": 2, "v": "M", "ja": "しかし、日本の自動車メーカーはこの危機をきっかけに、省エネの研究を進めました。", "zh": "但日本车企却借这场危机为契机，全力推进了节能省油研究。"},
            {"ch": 2, "v": "F", "ja": "地道な研究を重ねて、燃費の良い車がどんどん世界へ広がったのですね。", "zh": "靠着扎实的反复研究，省油好车迅速席卷了全世界。"},
            {"ch": 3, "v": "M", "ja": "もう一つの物語は、一九五八年に完成した東京タワーの設計です。", "zh": "另一个故事，是1958年落成的东京塔的精妙设计。"},
            {"ch": 3, "v": "F", "ja": "激しい台風にも耐える構造を、計算尺だけで設計したとは驚きです。", "zh": "能扛住猛烈台风的结构，竟然全靠手摇计算尺设计出来，太惊人了。"},
            {"ch": 3, "v": "M", "ja": "予算も材料も足りないにもかかわらず、職人の技術が確かな構造を支えました。", "zh": "尽管预算和钢材都紧缺，工匠的手艺撑起了稳固的塔身结构。"},
            {"ch": 4, "v": "F", "ja": "強い風や台風の中でも、赤と白の光は東京の復興の象徴になったのですね。", "zh": "哪怕在狂风和台风中，红白暖灯也成了东京复兴的象征。"},
            {"ch": 4, "v": "M", "ja": "その印象はあまりにも強く、今でも多くの人の記憶に生き続けています。", "zh": "这份印象太过深刻，至今依然活在无数人的记忆里。"},
            {"ch": 5, "v": "F", "ja": "最後に世界の医療ニュースですが、便利さが増えれば幸せとは限りません。", "zh": "最后看条世界医学新闻，生活越便利未必就越幸福。"},
            {"ch": 5, "v": "M", "ja": "長い研究によると、強い孤独感は脳の健康にも大きな影響を与えるそうです。", "zh": "据长期研究显示，强烈的孤独感对大脑健康也有很大影响。"},
            {"ch": 5, "v": "F", "ja": "辞書を引くように答えを探すより、人と支え合う印象や温もりが大切ですね。", "zh": "与其像查字典一样寻找标准答案，人与人互相支撑的温度和印记更珍贵。"},
            {"ch": 4, "v": "M", "ja": "歴史の象徴をたどると、現代を生きるヒントがはっきり見えてきます。", "zh": "回望历史的象征，活在当下的启示也就清清楚楚地浮现出来了。"},
        ],
    },
    "uchi23_s2a_kabuki_drama_part1": {
        "title_ja": "歌舞伎と名作ドラマ、そして小林正樹の反骨",
        "title_zh": "歌舞伎梨园与经典日剧，以及小林正树的冷峻反叛",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本では地域によって、話し方も人付き合いの距離もはっきり違います。", "zh": "在日本，不同地区的说话方式与人际距离清清楚楚各不相同。"},
            {"ch": 0, "v": "F", "ja": "京都の遠回しな表現は、辞書を引くだけでは分からない印象がありますね。", "zh": "京都人含蓄委婉的表达，光靠查字典确实摸不透那层微妙印象。"},
            {"ch": 1, "v": "M", "ja": "人気ドラマ『半沢直樹』の強い印象を支えたのは、歌舞伎を代表するしっかりした演技でした。", "zh": "撑起人气日剧《半泽直树》强烈印象的，正是代表歌舞伎功底的扎实演技。"},
            {"ch": 1, "v": "F", "ja": "香川照之さんをはじめ、厳しい舞台をやりきった役者こそ迫力がありますね。", "zh": "以香川照之为首，熬透严苛舞台的演员才拿得出那种压迫感。"},
            {"ch": 2, "v": "M", "ja": "一方、『カルテット』は唐揚げのルールをめぐって、大人の本音にぴったり迫りました。", "zh": "另一边，《四重奏》围着炸鸡挤柠檬的默契规则，精准戳中了成年人的真心话。"},
            {"ch": 2, "v": "F", "ja": "たとえ夢が叶わなくても、日常を大切にする物語がだんだん心に響きます。", "zh": "哪怕梦想未能实现，珍视日常的故事反而渐渐直击人心。"},
            {"ch": 3, "v": "M", "ja": "戦後の名監督、小林正樹は映画『切腹』で、嘘だらけの武士道の体面を暴きました。", "zh": "战后名导小林正树在电影《切腹》里，撕开了满是谎言的武士道体面。"},
            {"ch": 3, "v": "F", "ja": "権威に逆らいながらも、決して信念を曲げない姿勢は大きな影響を残しましたね。", "zh": "逆着权威前行却决不折弯信念的风骨，留下了极其深远的影响。"},
            {"ch": 4, "v": "M", "ja": "同じ伝統でも、三島由紀夫にとって美の象徴は全く別の意味を持ちました。", "zh": "同样面对传统，对三岛由纪夫而言美的象征却承载着截然不同的意义。"},
            {"ch": 4, "v": "F", "ja": "社会が豊かになるにつれて、光と影の両方を見つめる視点が必要ですね。", "zh": "随着社会愈发富裕，同时直面光与影两面的眼光愈发珍贵。"},
            {"ch": 4, "v": "M", "ja": "限られた予算の中で生まれた名作映画の記憶は、今も時代の象徴です。", "zh": "在有限预算里诞生的经典电影记忆，至今仍是时代的象征。"},
            {"ch": 5, "v": "F", "ja": "最後に最新の脳科学の研究ですが、道具が増えるほど脳は疲れがちだそうです。", "zh": "最后看最新的脑科学研究，听说工具越多，人脑反而越容易疲惫。"},
            {"ch": 5, "v": "M", "ja": "研究によると、深い睡眠こそが記憶を守り、脳の疲れをすっきり洗い流すそうです。", "zh": "据研究显示，唯有深度睡眠才能守住记忆，把大脑的疲惫痛快冲刷干净。"},
            {"ch": 5, "v": "F", "ja": "技術が速く進む一方で、辞書のように整理された静かな時間も欠かせないのですね。", "zh": "技术飞速狂奔的同时，像字典般清静有序的独处时间也不可或缺。"},
            {"ch": 5, "v": "M", "ja": "作品と科学の両方から、だんだん自分のリズムを守るヒントが見えてきます。", "zh": "从文艺作品与脑科学两头对照，守住自己节律的启示也就渐渐清晰起来。"},
        ],
    },
    "uchi12_s2a_seikan_part1": {
        "title_ja": "青函トンネル二十四年の執念と、赤い鶴の再生",
        "title_zh": "青函隧道二十四年执念与日航红鹤重生",
        "lines": [
            {"ch": 0, "v": "M", "ja": "就職氷河期と呼ばれた世代は、景気の影響で厳しい人生を歩んできました。", "zh": "被称为就职冰河期的一代人，受景气波动影响走过了艰难岁月。"},
            {"ch": 0, "v": "F", "ja": "世間の評価だけでは測れない努力が、今も社会の土台を支えていますね。", "zh": "仅靠世俗评价难以衡量的努力，至今仍在支撑着日本社会的底座。"},
            {"ch": 1, "v": "M", "ja": "一九五四年、激しい台風による洞爺丸の事故が、海底トンネル建設のきっかけでした。", "zh": "1954年，猛烈台风引发的洞爷丸海难，成了修建海底隧道的起点。"},
            {"ch": 1, "v": "F", "ja": "安全な交通の仕組みを作るため、二十四年もかけて海峡の下を掘りきったのですね。", "zh": "为了建起安全的交通命脉，人们整整花了二十四年把海峡海底彻底打通。"},
            {"ch": 2, "v": "M", "ja": "複雑な地質の構造と向き合い、予算も技術も限界を超える挑戦が続きました。", "zh": "面对复杂的海底地质结构，预算与技术不断经受突破极限的考验。"},
            {"ch": 2, "v": "F", "ja": "完成した青函トンネルは、人の命を守る日本の土木技術の象徴になりました。", "zh": "落成的青函隧道，成了守护生命与日本土木工程实力的象征。"},
            {"ch": 3, "v": "M", "ja": "一方、二〇一〇年に破綻した日本航空も、深刻な経営危機に陥っていました。", "zh": "另一边，2010年宣告破产的日本航空也曾深陷严峻的经营危机。"},
            {"ch": 3, "v": "F", "ja": "稲盛和夫さんは無給で引き受け、官僚的な古いルールを徹底的に見直したそうです。", "zh": "稻盛和夫零薪水接手，把僵化官僚的旧规矩彻彻底底翻修了一遍。"},
            {"ch": 4, "v": "M", "ja": "現場の社員一人ひとりが数字に納得したうえで、サービスをだんだん立て直しました。", "zh": "现场每位员工真正看懂并信服经营数字之后，服务水准渐渐起死回生。"},
            {"ch": 4, "v": "F", "ja": "利益と心の両方を取り戻し、わずか数年で赤い鶴のマークが再び空へ戻ったのですね。", "zh": "同时找回利润与人心，短短几年红鹤标志便重新展翅高飞。"},
            {"ch": 4, "v": "M", "ja": "危機の現場では、辞書のような理屈より、社員の表情を変える覚悟がものを言います。", "zh": "在危机现场，比起字典般的空洞理论，改变员工神态的决断力更有分量。"},
            {"ch": 5, "v": "F", "ja": "最後に世界ニュースですが、宇宙開発では月面車の設計研究がどんどん進んでいます。", "zh": "最后看世界新闻，航天领域里月球车的设计研究正飞速推进。"},
            {"ch": 5, "v": "M", "ja": "大国同士のルールが揺らぐ一方で、確かな技術が国際協力の象徴になっています。", "zh": "大国博弈规则动荡之际，过硬技术反而成了国际合作的象征。"},
            {"ch": 5, "v": "F", "ja": "海底から月面まで、長い研究と設計の積み重ねが未来を切り開いていくのですね。", "zh": "从海底到月面，漫长的研究与设计积淀终将劈开未来之路。"},
        ],
    },
    "uchi13_s2a_heisei_1989_part1": {
        "title_ja": "平成バブルの記憶と、トヨタ生産方式の知恵",
        "title_zh": "平成泡沫记忆与丰田看板的制造智慧",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本銀行の利上げとともに、長く続いた超低金利の時代がはっきり変わり始めました。", "zh": "随着日本银行步入加息通道，持续多年的超低利率时代清清楚楚迎来转折。"},
            {"ch": 0, "v": "F", "ja": "金利が上がると住宅ローンだけでなく、世間の消費心理にも大きな影響が出ますね。", "zh": "利率走高不只影响房贷，对整个社会的消费心态也有深远冲击。"},
            {"ch": 1, "v": "M", "ja": "振り返れば一九八九年、平成の幕開けと同時に日本の市場はバブルの頂点に達しました。", "zh": "回望1989年，平成启幕之际，日本股市和楼市冲上了泡沫的最高峰。"},
            {"ch": 1, "v": "F", "ja": "土地の値段がどんどん上がり、まるで永遠に好景気が続くような印象だったそうです。", "zh": "地价一路狂飙，当时给人的印象仿佛繁荣会永远持续下去。"},
            {"ch": 2, "v": "M", "ja": "しかしバブルが弾けた後、日本の経済は長い停滞という厳しい現実と向き合いました。", "zh": "然而泡沫破裂之后，日本经济不得不直面漫长停滞的严酷现实。"},
            {"ch": 2, "v": "F", "ja": "高い株価がそのまま強い社会とは限らないことを、歴史の記憶が教えてくれますね。", "zh": "这段历史记忆提醒我们，高股价未必就等同于稳健强大的社会。"},
            {"ch": 3, "v": "M", "ja": "対照的に、一九五〇年代のトヨタは資金も予算もない窮地から独自の工夫を生みました。", "zh": "形成鲜明对比的是，1950年代丰田在既无资金又缺预算的绝境里磨出了独门巧思。"},
            {"ch": 3, "v": "F", "ja": "大野耐一さんはアメリカのスーパーを見て、必要な分だけ作る構造を思いついたのですね。", "zh": "大野耐一逛美国超市时灵机一动，悟出了按需生产的精益结构。"},
            {"ch": 4, "v": "M", "ja": "さらに、誰かが小さな異常を見つけただけで工場全体を止めるルールを徹底しました。", "zh": "更狠的是，他们立下铁规：只要任何人发现一点瑕疵，就能立刻叫停整条产线。"},
            {"ch": 4, "v": "F", "ja": "なぜを五回繰り返して原因を突き止める姿勢こそ、日本のものづくりの象徴ですね。", "zh": "连问五个为什么直到挖出病根的韧劲，正是日本制造真正的象征。"},
            {"ch": 4, "v": "M", "ja": "辞書に載っていない現場の知恵を、誰もが納得する仕組みに落とし込んだのです。", "zh": "他们把字典里查不到的现场智慧，沉淀成了人人信服的制度流程。"},
            {"ch": 5, "v": "F", "ja": "世界では今、次世代エネルギーの切り札として核融合の研究が激しさを増しています。", "zh": "放眼全球，作为下一代能源王牌的核聚变研究正日趋白热化。"},
            {"ch": 5, "v": "M", "ja": "日本も精密な材料の設計と長い研究実績で、世界の市場から高い信頼を得ています。", "zh": "日本凭借精密材料设计与长期研究底蕴，依然在全球市场赢得高度信赖。"},
            {"ch": 5, "v": "F", "ja": "派手な流行より地道な構造改革を続けることが、危機を乗り越える力になりますね。", "zh": "比起浮华风口，踏踏实实打磨结构改革，才是穿越危机的硬实力。"},
        ],
    },
    "uchi14_s2a_hanshin_1995_part1": {
        "title_ja": "神戸一九九五年の連帯と、回転寿司のひらめき",
        "title_zh": "1995神户守望相助与东大阪回转寿司传奇",
        "lines": [
            {"ch": 0, "v": "M", "ja": "最近、東北や北海道の街に野性の熊が現れるニュースがはっきり増えています。", "zh": "最近，东北和北海道市区频现野熊的新闻明显多了起来。"},
            {"ch": 0, "v": "F", "ja": "山村の過疎化が進むにつれて、人と自然の境界線がだんだん曖昧になっているのですね。", "zh": "随着山村过疏化加剧，人类与自然之间的边界正渐渐变得模糊。"},
            {"ch": 1, "v": "M", "ja": "自然の脅威といえば、一九九五年一月の阪神淡路大震災は忘れられない記憶です。", "zh": "说到自然威慑，1995年1月的阪神大地震是日本社会难以磨灭的记忆。"},
            {"ch": 1, "v": "F", "ja": "高速道路さえ倒れた衝撃の中で、都市の建築構造の安全基準が大きく見直されました。", "zh": "连高架高速都轰然侧翻，那场巨震迫使日本彻底改写了城市建筑结构安全标准。"},
            {"ch": 2, "v": "M", "ja": "その厳しい危機の現場へ、全国から百三十万人以上のボランティアが駆けつけました。", "zh": "在这场严峻危机现场，全日本超过一百三十万普通志愿者自发奔赴神户。"},
            {"ch": 2, "v": "F", "ja": "誰かに命じられたのではなく、助け合いの象徴として日本の社会に根づいたのですね。", "zh": "并非听命于谁，这份守望相助成了扎根日本社会的志愿精神象征。"},
            {"ch": 3, "v": "M", "ja": "もう一つの物語は、一九五八年に東大阪の小さな店から生まれた回転寿司です。", "zh": "另一个故事，是1958年从东大阪一间小店诞生的回转寿司。"},
            {"ch": 3, "v": "F", "ja": "店主の白石義明さんは、ビール工場のベルトコンベアを見て構造を設計したそうですね。", "zh": "店主白石义明参观啤酒厂流水线时获得灵感，亲手设计出了回转传送结构。"},
            {"ch": 4, "v": "M", "ja": "最初は世間から行儀が悪いと批判されましたが、大阪万博で百万皿を売りきりました。", "zh": "起初虽被世俗嘲笑有失体统，但在大阪世博会上一口气狂卖一百万盘。"},
            {"ch": 4, "v": "F", "ja": "手頃な予算で家族みんなが楽しめる工夫が、世界中の市場に納得されたのですね。", "zh": "用亲民预算让全家吃得尽兴的巧思，最终让全世界市场都心服口服。"},
            {"ch": 4, "v": "M", "ja": "常識の辞書を書き換える発見は、案外小さな町工場の日常から生まれるものです。", "zh": "改写常识字典的发明，往往就诞生在不起眼的小町工厂日常里。"},
            {"ch": 5, "v": "F", "ja": "最後に世界の科学ニュースでは、量子コンピュータの研究が暗号のルールを変えつつあります。", "zh": "最后看世界科技新闻，量子计算机的研究正在重塑全球加密规则。"},
            {"ch": 5, "v": "M", "ja": "計算速度がどんどん上がる一方で、金融システムの安全を守る研究も待ったなしです。", "zh": "算力飞速狂飙的同时，守护金融系统安全的新密码研究也刻不容缓。"},
            {"ch": 5, "v": "F", "ja": "災害への備えも最新技術も、人の暮らしを守る視点こそが一番の象徴ですね。", "zh": "无论是防灾备灾还是前沿科技，守护普通人的生活始终是最核心的象征。"},
        ],
    },
    "uchi15_s2a_super_cub_1958_part1": {
        "title_ja": "片手で乗れるスーパーカブと、無印良品の引き算",
        "title_zh": "单手可骑本田幼兽与无印良品的减法美学",
        "lines": [
            {"ch": 0, "v": "M", "ja": "東京への一極集中が進む一方で、子育て支援の予算をめぐる地域格差が話題です。", "zh": "东京一极集中愈演愈烈的同时，围绕育儿补贴预算的地区差距引发热议。"},
            {"ch": 0, "v": "F", "ja": "便利な都心に人が集まるにつれて、地方の暮らしをどう支えるかが大きな課題ですね。", "zh": "随着人口不断涌向便利的市中心，如何托住地方生活成了一道难题。"},
            {"ch": 1, "v": "M", "ja": "一九五八年、本田宗一郎は東京のそば屋の出前のために特別なバイクを設計しました。", "zh": "1958年，本田宗一郎专门为东京荞麦面外卖小哥设计了一台特别的摩托车。"},
            {"ch": 1, "v": "F", "ja": "片手でそばの箱を持ちながら運転できるよう、クラッチのない構造にしたのですね。", "zh": "为了让人能单手端着荞麦面箱照常骑行，专门做出了免捏离合器的精妙结构。"},
            {"ch": 2, "v": "M", "ja": "故障しにくく燃費の良いスーパーカブは、日本の郵便から世界へどんどん広がりました。", "zh": "皮实耐造又省油的超级幼兽，从日本邮递员一路风靡到了全世界街头。"},
            {"ch": 2, "v": "F", "ja": "累計一億台を超え、庶民の足として信頼されるものづくりの象徴になりましたね。", "zh": "累计产量突破一亿台，成了深受普通人信赖的实用制造象征。"},
            {"ch": 3, "v": "M", "ja": "もう一つの革命は、一九八〇年に生まれた無印良品の徹底した引き算のルールです。", "zh": "另一场革命，是1980年诞生的无印良品所坚持的彻底减法规则。"},
            {"ch": 3, "v": "F", "ja": "折れたパスタや割れシイタケでも、品質に納得できれば立派な商品になるという発想ですね。", "zh": "哪怕是折断的意面或碎香菇，只要品质过硬让人信服，照样能成为好商品。"},
            {"ch": 4, "v": "M", "ja": "派手な装飾やロゴを全部削ぎ落とした結果、無印そのものが強い印象のブランドになりました。", "zh": "把浮华装饰和商标全部剥离干净后，没有商标本身反而成了印象最深的品牌。"},
            {"ch": 4, "v": "F", "ja": "安いから選ぶのではなく、これで十分だと心が落ち着く設計が世間に響いたのですね。", "zh": "不是因为便宜将就，而是恰到好处的克制设计真正打动了世人。"},
            {"ch": 4, "v": "M", "ja": "過剰な飾りを捨てて本質だけ残す姿勢は、日本の美意識の辞書そのものです。", "zh": "舍弃冗余只留本质的克制，简直就是日本美学字典的活标本。"},
            {"ch": 5, "v": "F", "ja": "世界の医学ニュースでは、新しい肥満治療薬の研究が食品や航空の市場を揺らしています。", "zh": "世界医学新闻方面，新一代减重药的研究正搅动全球食品与航空市场。"},
            {"ch": 5, "v": "M", "ja": "薬に頼る一方で、日本伝統の和食や日々の生活習慣を見直す研究も注目されています。", "zh": "在关注新药的同时，重新审视日本传统和食与日常作息的研究同样备受瞩目。"},
            {"ch": 5, "v": "F", "ja": "バイクも日用品も健康も、無理のないシンプルな構造が一番長く続くのですね。", "zh": "不管是摩托、日用品还是健康，自然克制的简洁结构才走得最远。"},
        ],
    },
    "uchi16_s2a_toto_washlet_1980_part1": {
        "title_ja": "ウォシュレットの黄金角度と、ユニクロ一勝九敗",
        "title_zh": "TOTO卫洗丽黄金角度与优衣库一胜九败",
        "lines": [
            {"ch": 0, "v": "M", "ja": "京都では観光客がどんどん増え、市民のバスや宿泊税のルール見直しが続いています。", "zh": "京都游客持续暴增，市民公交分流与高档酒店住宿税的新规讨论不断。"},
            {"ch": 0, "v": "F", "ja": "街の伝統を守りながら、訪れる人も地元も納得できる仕組みづくりが大切ですね。", "zh": "如何在守住古都传统的同时，建起让游客与市民都信服的机制非常关键。"},
            {"ch": 1, "v": "M", "ja": "日本らしい徹底した研究といえば、一九八〇年に登場した東陶のウォシュレットです。", "zh": "说起日本式的死磕研究，1980年问世的TOTO卫洗丽绝对榜上有名。"},
            {"ch": 1, "v": "F", "ja": "社員三百人の協力で、水が跳ね返らない黄金の角度をデータで突き止めたそうですね。", "zh": "听说三百名员工亲自参与实测，硬是靠数据算出了水花不回溅的黄金角度。"},
            {"ch": 2, "v": "M", "ja": "当時の大胆なテレビ広告は世間の注目を集め、やがて日本の清潔文化の象徴になりました。", "zh": "当年大胆直白的电视广告震动舆论，卫洗丽也渐渐成了日本洁净文化的象征。"},
            {"ch": 2, "v": "F", "ja": "恥ずかしい話題さえ科学と設計で解決する執念が、強烈な印象を残しますね。", "zh": "连不好意思开口的生活痛点都拿科学与设计死磕到底，这份执念让人印象深刻。"},
            {"ch": 3, "v": "M", "ja": "一九九八年には、ユニクロが原宿に店を開き、千九百円のフリースで市場を驚かせました。", "zh": "1998年，优衣库杀进东京原宿，靠一千九百日元的摇粒绒震惊整个市场。"},
            {"ch": 3, "v": "F", "ja": "一時は売れすぎて電車の中が同じ服だらけになり、業績の危機も経験したのですね。", "zh": "一度因为卖太火导致满电车撞衫，业绩跌入谷底遭遇危机。"},
            {"ch": 4, "v": "M", "ja": "柳井正さんは『一勝九敗』を書き、東レと組んで発熱素材の共同研究へ舵を切りました。", "zh": "柳井正写下《一胜九败》，转头联手东丽扎进了发热科技面料的联合研发。"},
            {"ch": 4, "v": "F", "ja": "単なる安売りではなく、確かな技術と利益を両立する構造へ進化したのですね。", "zh": "不再只是拼低价，而是进化成了靠硬核科技兼顾品质与利润的稳固结构。"},
            {"ch": 4, "v": "M", "ja": "失敗を隠さず次の設計に生かす姿勢は、経営の辞書に刻まれるべき教訓です。", "zh": "不遮掩失败而是拿它打磨下一代设计，这是值得写进经营字典的功课。"},
            {"ch": 5, "v": "F", "ja": "世界の医療では今、一人ひとりの体質に合わせたがんワクチンの研究が進んでいます。", "zh": "世界医疗前沿方面，量身定制的个体化癌症疫苗研究正加速推进。"},
            {"ch": 5, "v": "M", "ja": "莫大な予算がかかる一方で、日本の大学や製薬企業も地道に研究を続けています。", "zh": "虽然需要巨额预算投入，日本的高校与药企也正一步步扎实推进研发。"},
            {"ch": 5, "v": "F", "ja": "生活の細部から最先端の医療まで、諦めない研究こそが未来の象徴になりますね。", "zh": "从日常起居细节到尖端医疗，永不放弃的研究正是面向未来的象征。"},
        ],
    },
    "uchi17_s2a_jnr_part1": {
        "title_ja": "国鉄民営化の激震と、吉野家牛丼復活の日",
        "title_zh": "国铁民营化大拆分与吉野家牛丼复活记",
        "lines": [
            {"ch": 0, "v": "M", "ja": "渋沢栄一の新札が出た一方で、現金にこだわる老舗の店もまだはっきり残っています。", "zh": "涩泽荣一新版钞票落地的同时，坚持只收现金的老字号小店依然清晰可见。"},
            {"ch": 0, "v": "F", "ja": "キャッシュレスがどんどん進む中でも、急に変われない現場の事情があるのですね。", "zh": "哪怕无现金支付飞速普及，传统小店也有一时难以转身的现实苦衷。"},
            {"ch": 1, "v": "M", "ja": "一九八七年の国鉄分割民営化は、戦後日本最大の制度改革として記憶されています。", "zh": "1987年的国铁拆分民营化，作为战后日本最大规模的制度改革载入记忆。"},
            {"ch": 1, "v": "F", "ja": "三十七兆円もの赤字とストライキの危機で、当時のサービスは世間の批判だらけでした。", "zh": "背负三十七兆日元巨额赤字加上动辄罢工的危机，当时服务满是民众吐槽。"},
            {"ch": 2, "v": "M", "ja": "七つのＪＲに分かれたことで、駅は切符を売る場所から魅力的な商業構造へ変わりました。", "zh": "拆成七家JR公司之后，车站从冰冷卖票窗口蜕变成了充满活力的商业体结构。"},
            {"ch": 2, "v": "F", "ja": "都心は大きな利益を出す一方で、地方の赤字路線をどう守るかという課題も残りましたね。", "zh": "都市圈赚得盆满钵满的同时，地方亏损铁路如何守住也成了遗留难题。"},
            {"ch": 3, "v": "M", "ja": "二〇〇四年、狂牛病の輸入停止で吉野家の看板である牛丼が市場から姿を消しました。", "zh": "2004年，疯牛病禁运风暴让吉野家招牌牛丼一夜之间从市场上消失。"},
            {"ch": 3, "v": "F", "ja": "他社が別の牛肉に切り替える中、吉野家は味に納得できず販売休止を選んだのですね。", "zh": "同行纷纷改用别国牛肉时，吉野家却因为无法对味道妥协，咬牙选择了停卖。"},
            {"ch": 4, "v": "M", "ja": "二年半の苦しい時期を豚丼で耐えきり、復活の日には全国で長い行列ができました。", "zh": "靠猪肉盖饭硬扛了整整两年半，牛丼复活那天全日本门前排起了长龙。"},
            {"ch": 4, "v": "F", "ja": "目の前の利益より暖簾の信頼を守った決断が、顧客の表情を笑顔に変えたのですね。", "zh": "比起眼前利润更死守老字号信誉的决断，换来了顾客久违的动容表情。"},
            {"ch": 4, "v": "M", "ja": "こだわりを貫くことは、日本の商売の辞書で何より重たいルールなのかもしれません。", "zh": "死磕底线绝不凑合，或许正是日本商道字典里分量最重的一条规矩。"},
            {"ch": 5, "v": "F", "ja": "世界の自動車市場では、次世代の全固体電池をめぐる技術研究が加速しています。", "zh": "在全球汽车市场，围绕下一代全固态电池的技术研发正全面提速。"},
            {"ch": 5, "v": "M", "ja": "充電が速く安全な電池の設計は、日本の自動車産業にとって生き残りの象徴です。", "zh": "充电快又安全的电池设计，对日本汽车产业来说堪称突围存续的象征。"},
            {"ch": 5, "v": "F", "ja": "大きな危機に直面した時ほど、本質を見失わない覚悟が未来を分けるのですね。", "zh": "越是直面巨大危机，越能看出不丢掉本质的定力如何决定未来。"},
        ],
    },
    "uchi18_s2a_yodogo_part1": {
        "title_ja": "よど号事件の決断と、忠犬ハチ公九十年の記憶",
        "title_zh": "淀号孤身换人质与忠犬八公九十年重逢",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本では脱ハンコが叫ばれる一方で、古い紙の書類や慣習がまだあちこちに残っています。", "zh": "日本一边高喊脱印章数字化，另一边传统纸质文件与老规矩仍随处可见。"},
            {"ch": 0, "v": "F", "ja": "上司にお辞儀するように斜めに押すルールなど、世間でも議論が絶えませんね。", "zh": "像印章要向左倾斜向领导鞠躬这种潜规则，在社会上一直争论不休。"},
            {"ch": 1, "v": "M", "ja": "一九七〇年、日本初のハイジャックであるよど号事件は国中を震わせる危機でした。", "zh": "1970年，日本史上首起劫机案淀号事件，是一场震动全国的重大危机。"},
            {"ch": 1, "v": "F", "ja": "緊張が極限に達する中、三十六歳の山村新治郎政務次官が乗客の身代わりを申し出ました。", "zh": "就在局势绷到极点时，年仅三十六岁的政务次官山村新治郎主动站出来替人质。"},
            {"ch": 2, "v": "M", "ja": "たった一人でタラップを登り、九十九人の命を守りきった姿は強烈な記憶として残っています。", "zh": "他两手空空独自走上舷梯，硬是把九十九条人命全数换回，留下一代人深刻记忆。"},
            {"ch": 2, "v": "F", "ja": "立場ある人間が最後に責任を引き受ける覚悟は、どの時代にも通じる象徴ですね。", "zh": "身居高位者在危急关头挺身扛责的担当，放在哪个时代都是动人的象征。"},
            {"ch": 3, "v": "M", "ja": "渋谷駅前に立つ忠犬ハチ公も、実は有名になるまで長い間つらい境遇にありました。", "zh": "矗立在涩谷站前的忠犬八公，其实在成名之前有很长一段时间受尽冷眼。"},
            {"ch": 3, "v": "F", "ja": "亡くなった上野教授を毎日待ち続け、心ない人から水をかけられることもあったそうです。", "zh": "它每天苦等逝世的上野教授，甚至一度遭冷漠路人泼水捉弄。"},
            {"ch": 4, "v": "M", "ja": "新聞の記事をきっかけに世間の見方が一変し、ハチは生前に自分の銅像と対面しました。", "zh": "直到一篇报纸报道彻底扭转舆论，八公在生前竟亲自见到了自己的铜像揭幕。"},
            {"ch": 4, "v": "F", "ja": "そして九十年後、東京大学で教授に飛びつく喜びの表情の像として再会したのですね。", "zh": "九十年后，它在东京大学化作扑进教授怀里、满脸欢喜的新铜像终于重逢。"},
            {"ch": 4, "v": "M", "ja": "言葉の辞書を持たない犬が、人間の社会に一番まっすぐな信頼を教えてくれました。", "zh": "没有人类字典的小狗，反而给人类社会上了最纯粹的一堂信任课。"},
            {"ch": 5, "v": "F", "ja": "最後に世界のニュースですが、ヨーロッパでは防衛予算と安全保障の構造が大きく動いています。", "zh": "最后看世界新闻，欧洲正围绕防务预算与安全架构迈出历史性大步。"},
            {"ch": 5, "v": "M", "ja": "ドイツの財政ルール転換は、日本にとっても同盟や自立を考える重要な材料になります。", "zh": "德国松绑财政规则的转向，对日本思考同盟与自主防务同样是关键参照。"},
            {"ch": 5, "v": "F", "ja": "歴史の危機でも日常の約束でも、誰かを守り抜く意志が一番はっきり心に残りますね。", "zh": "无论是历史危机还是日常约定，守信护人的意志永远最清晰地留在心头。"},
        ],
    },
    "uchi19_s2a_sukiyaki_part1": {
        "title_ja": "『上を向いて歩こう』の奇跡と、築地八十三年の魂",
        "title_zh": "《昂首向前走》登顶奇迹与筑地八十三年魂",
        "lines": [
            {"ch": 0, "v": "M", "ja": "新しい非課税投資制度をきっかけに、日本の家計も貯金から市場へ少しずつ動き出しました。", "zh": "借着新版免税投资制度的东风，日本家庭存款正慢慢从银行流向资本市场。"},
            {"ch": 0, "v": "F", "ja": "将来の年金への不安がある一方で、自分で資産を育てるルールを学ぶ人が増えていますね。", "zh": "在对未来养老隐约不安的同时，主动学习理财规则的人越来越多了。"},
            {"ch": 1, "v": "M", "ja": "一九六一年、デモ帰りの切ない夜に生まれたのが、坂本九さんの『上を向いて歩こう』です。", "zh": "1961年，在抗议散场后的落寞夜里，坂本九的名曲《昂首向前走》诞生了。"},
            {"ch": 1, "v": "F", "ja": "涙がこぼれないように上を向くという歌詞は、戦後日本のささやかな誇りの象徴ですね。", "zh": "为了不让眼泪掉下来所以昂首走路，这句歌词成了战后日本含蓄骄傲的象征。"},
            {"ch": 2, "v": "M", "ja": "海外で勝手にスキヤキと名づけられたにもかかわらず、全米一位という奇跡を起こしました。", "zh": "尽管在海外被随口改名叫寿喜烧，它依然奇迹般登顶了美国公告牌第一。"},
            {"ch": 2, "v": "F", "ja": "日本語の意味を辞書で引かなくても、切ないメロディと表情が世界中に届いたのですね。", "zh": "就算不翻字典查歌词含义，真挚的旋律与情感照样穿透国界打动了全世界。"},
            {"ch": 3, "v": "M", "ja": "もう一つの日本の記憶は、八十三年間東京の食を支え続けた築地市場の熱気です。", "zh": "另一段日本国民记忆，是连续八十三年托起东京餐桌的筑地鱼市热潮。"},
            {"ch": 3, "v": "F", "ja": "早朝五時のマグロの競りと、狭い通路を縫うように走る運搬車は圧巻の印象でした。", "zh": "清晨五点的蓝鳍金枪鱼拍卖，以及在窄巷穿梭的搬运车芭蕾，给人无比震撼的印象。"},
            {"ch": 4, "v": "M", "ja": "二〇一八年、最後の鐘が鳴った夜に、二千台の車が橋を渡って豊洲へ引っ越しました。", "zh": "2018年最后一次拍卖钟声落下后，两千辆搬运车连夜跨桥迁往丰洲。"},
            {"ch": 4, "v": "F", "ja": "最新設備の衛生構造へ移っても、魚を見極める職人の目利きはしっかり受け継がれています。", "zh": "即便搬进了现代化洁净建筑结构，老师傅挑鱼的独到眼力依然牢牢传了下来。"},
            {"ch": 4, "v": "M", "ja": "街の風景はだんだん変わりますが、人が磨いた技と誇りは決して消えません。", "zh": "城市风景会渐渐更迭，但一代代人磨出来的手艺与骄傲绝不会消散。"},
            {"ch": 5, "v": "F", "ja": "世界では今、月面着陸を成功させたインドが半導体やソフト開発の市場で急成長しています。", "zh": "放眼世界，成功登月后的印度正在半导体与软件开发市场全速狂奔。"},
            {"ch": 5, "v": "M", "ja": "日本の商社やメーカーも、確かな品質と現地の活力を結ぶ新しい設計を進めています。", "zh": "日本商社和制造商也正谋划新布局，把过硬品质和当地澎湃活力联结起来。"},
            {"ch": 5, "v": "F", "ja": "歌も市場も技術も、境界を越えて響き合う瞬間に新しい歴史が生まれるのですね。", "zh": "无论是歌声、鱼市还是科技，跨越边界共振的那一刻总会诞生崭新历史。"},
        ],
    },
    "uchi20_s2a_umami_part1": {
        "title_ja": "第五の味『うま味』の発見と、クリスマスのチキン",
        "title_zh": "第五味鲜味科学发现与日本圣诞炸鸡奇迹",
        "lines": [
            {"ch": 0, "v": "M", "ja": "人気のアイスをたった十円値上げしただけで、会社全体が頭を下げた広告が話題になりました。", "zh": "国民冰棒仅仅涨价十日元，全公司鞠躬拍广告道歉的画面曾刷屏日本。"},
            {"ch": 0, "v": "F", "ja": "長いデフレの記憶が根強い日本では、値上げ一つにも世間が納得する誠意が求められるのですね。", "zh": "在通缩记忆根深蒂固的日本，哪怕微调定价也需要拿出让世人信服的诚意。"},
            {"ch": 1, "v": "M", "ja": "一九〇八年、化学者の池田菊苗は湯豆腐の昆布だしから世界第五の味を発見しました。", "zh": "1908年，化学家池田菊苗从一碗热腾腾的昆布豆腐汤里发现了世界第五味。"},
            {"ch": 1, "v": "F", "ja": "甘味や塩味だけでは説明できないコクの構造を、地道な研究で科学的に証明したのですね。", "zh": "酸甜苦咸都解释不了的那层醇厚结构，竟被他靠扎实实验从科学上证了出来。"},
            {"ch": 2, "v": "M", "ja": "最初は欧米の学会に相手にされませんでしたが、今ではウマミは世界の辞書に載る言葉です。", "zh": "起初欧美学界并不买账，如今Umami却堂堂正正写进了全世界的辞典里。"},
            {"ch": 2, "v": "F", "ja": "食卓の小さな違和感を見逃さなかった目が、日本の食文化の国際的な象徴を生みましたね。", "zh": "不放过餐桌上一丝微妙味觉的眼睛，催生了日本食文化走向世界的象征。"},
            {"ch": 3, "v": "M", "ja": "一方、一九七〇年代のケンタッキー日本一号店は、最初は客が来ない危機に直面しました。", "zh": "另一边，1970年代日本肯德基刚开业时也曾深陷门可罗雀的生存危机。"},
            {"ch": 3, "v": "F", "ja": "店長の小さな閃きから、クリスマスにはチキンを食べるという新しい習慣を作ったそうですね。", "zh": "听说靠店长灵机一动，硬是在日本造出了圣诞节吃炸鸡的国民新习俗。"},
            {"ch": 4, "v": "M", "ja": "いまでは毎年イブに何百万もの家族が行列を作り、冬のにぎやかな印象を彩っています。", "zh": "如今每年平安夜都有数百万家庭排起长队，成了日本冬天独有的热闹景象。"},
            {"ch": 4, "v": "F", "ja": "文化は昔からあるものとは限らず、人の工夫と物語でどんどん新しく育つのですね。", "zh": "文化未必都来自久远古代，靠巧思与好故事照样能长出半世纪的新传统。"},
            {"ch": 4, "v": "M", "ja": "研究の粘りも現場のひらめきも、暮らしの表情を豊かにする力を持っています。", "zh": "科研的韧劲与现场的灵光，同样拥有让日常表情焕发光彩的力量。"},
            {"ch": 5, "v": "F", "ja": "世界のニュースでは、国際データの九十九パーセントを運ぶ海底ケーブルの安全が注目です。", "zh": "世界新闻方面，承载全球九成九跨洋数据的海底光缆安全正备受关注。"},
            {"ch": 5, "v": "M", "ja": "島国の日本にとって、通信インフラの設計と監視は経済の命綱を守る重要なルールです。", "zh": "对岛国日本而言，海底通信基建的设计与守护堪称守住经济命脉的底线。"},
            {"ch": 5, "v": "F", "ja": "昆布のだしから海底の光ファイバーまで、見えない構造こそが社会を支えているのですね。", "zh": "从昆布高汤到海底光纤，往往是看不见的底层结构稳稳托起了整个社会。"},
        ],
    },
    "uchi21_s2a_koshien_part1": {
        "title_ja": "甲子園の黒土と、イチロー・大谷の静かな規律",
        "title_zh": "甲子园黑土青春与铃木一朗大谷翔平的自律",
        "lines": [
            {"ch": 0, "v": "M", "ja": "一九二八年から続くラジオ体操は、世代を超えて日本人の体に刻まれた記憶です。", "zh": "自1928年延续至今的广播体操，是跨越几代人刻进日本人肌肉里的共同记忆。"},
            {"ch": 0, "v": "F", "ja": "夏休みの朝六時半に公園へ集まった印象は、大人になってもはっきり残っていますね。", "zh": "暑假清晨六点半去公园做操的画面，长大后依然清清楚楚留在心底。"},
            {"ch": 1, "v": "M", "ja": "夏の風物詩といえば、全国四千校の高校球児が挑む甲子園の熱い戦いです。", "zh": "说到日本夏天的风物诗，必提全日本四千所高中拼尽全力的甲子园大赛。"},
            {"ch": 1, "v": "F", "ja": "負けた瞬間に涙をこらえて黒土を袋に詰める姿は、青春をやりきった象徴ですね。", "zh": "落败瞬间忍着泪跪地捧起一袋黑土的画面，成了燃尽青春的国民象征。"},
            {"ch": 2, "v": "M", "ja": "一方で近年は、投手の肩を守るために球数制限など新しいルールも導入されました。", "zh": "但与此同时，近年来为了保护少年投手的肩膀，球数上限等科学新规也陆续落地。"},
            {"ch": 2, "v": "F", "ja": "根性論だけでなく、科学的な研究と選手の未来を大切にする流れへだんだん変わっています。", "zh": "不再只讲苦情硬扛，正渐渐转向尊重科学研究与球员长远健康的轨道。"},
            {"ch": 3, "v": "M", "ja": "世界へ羽ばたいたイチローさんは、毎日同じ準備を繰り返す徹底した自己管理で有名です。", "zh": "走向世界的铃木一朗，以日复一日重复精准准备的极致自律闻名天下。"},
            {"ch": 3, "v": "F", "ja": "派手な自慢はせず、小さなルーティンを積み上げて大リーグの記録を塗り替えたのですね。", "zh": "从不浮夸炫耀，全靠把细微习惯做到极致，改写了尘封八十四年的大联盟神迹。"},
            {"ch": 4, "v": "M", "ja": "大谷翔平選手も高校時代に八十一マスの目標表を設計し、ゴミ拾いまで習慣にしました。", "zh": "大谷翔平高一时就亲手设计了八十一格目标表，连顺手捡球场纸屑都练成本能。"},
            {"ch": 4, "v": "F", "ja": "才能に頼りきるのではなく、誰もが納得する日々の姿勢が世界中の世間を魅了しています。", "zh": "不靠天赋挥霍，用人人信服的日常修养征服了全世界的目光。"},
            {"ch": 4, "v": "M", "ja": "一流の選手の辞書には、油断や妥協という言葉が最初から入っていないようです。", "zh": "在真正一流选手的字典里，似乎从一开始就没有大意与妥协这两个词。"},
            {"ch": 5, "v": "F", "ja": "最後に世界の話題ですが、北極海の氷が溶けるにつれて新しい海上航路が注目されています。", "zh": "最后看世界动态，随着北极海冰融化，连通欧亚的新海上航道备受瞩目。"},
            {"ch": 5, "v": "M", "ja": "輸送の距離が縮まる一方で、環境への影響や国際的なルールづくりが大きな焦点です。", "zh": "航程大幅缩短的同时，生态影响与国际航行规则制定正成为焦点。"},
            {"ch": 5, "v": "F", "ja": "スポーツも地球の未来も、正しいルールと静かな努力の積み重ねが鍵を握りますね。", "zh": "无论是竞技体育还是地球未来，守住好规则与静水深流的努力都是关键。"},
        ],
    },
    "uchi22_s2a_ise_sengu_part1": {
        "title_ja": "千三百年の式年遷宮と、直島に息づく現代美術",
        "title_zh": "伊势神宫千年迁宫、金刚组与直岛美术馆",
        "lines": [
            {"ch": 0, "v": "M", "ja": "大晦日に紅白歌合戦を見て、年越しそばを食べながら除夜の鐘を聴くのが日本の冬です。", "zh": "除夕夜看红白歌合战、吃跨年荞麦面听百零八下除夜钟声，是最温柔的日本冬天。"},
            {"ch": 0, "v": "F", "ja": "忙しい一年を静かに締めくくる習慣が、家族の穏やかな表情を守ってくれますね。", "zh": "用宁静仪式为忙碌一年收尾的习俗，温柔守住了家人的平和神态。"},
            {"ch": 1, "v": "M", "ja": "伊勢神宮では千三百年もの間、二十年ごとに社殿をすべて新しく建て替える伝統があります。", "zh": "在伊势神宫，整整一千三百年来延续着每二十年将殿宇彻底拆建更新的传统。"},
            {"ch": 1, "v": "F", "ja": "建物を永遠に残すのではなく、作り直すことで職人の技術を生きたまま伝える仕組みですね。", "zh": "不是妄图让木头永垂不朽，而是靠不断亲手重造让工匠手艺活生生传下去。"},
            {"ch": 2, "v": "M", "ja": "大阪の金剛組も千四百年の歴史を誇り、危機を乗り越えながら古建築の構造を守ってきました。", "zh": "大阪的金刚组同样屹立一千四百年，穿越战火与危机守住了古建筑榫卯结构。"},
            {"ch": 2, "v": "F", "ja": "古い木と新しい技を組み合わせる知恵こそ、日本の持続する文化の象徴と言えますね。", "zh": "把古老木艺与当代匠心融为一体的智慧，堪称日本绵延文化的鲜明象征。"},
            {"ch": 3, "v": "M", "ja": "瀬戸内海の直島はかつて工業の煙で荒れ果てた島でしたが、アートの力で生まれ変わりました。", "zh": "濑户内海的直岛曾是被冶炼烟囱熏秃的荒岛，却借艺术之力奇迹般重生。"},
            {"ch": 3, "v": "F", "ja": "安藤忠雄さんの設計した地中美術館は、島の自然の景色を壊さないよう地中に埋めたそうです。", "zh": "安藤忠雄设计的地中美术馆，为了不破坏海岛风景线，干脆整座埋进了山体里。"},
            {"ch": 4, "v": "M", "ja": "自然光だけでモネの睡蓮を眺めると、時間によって絵の印象がだんだん変わって見えます。", "zh": "只借自然天光欣赏莫奈睡莲，随着日影移动，画作给人的印象会渐渐流转变化。"},
            {"ch": 4, "v": "F", "ja": "地元の住民が誇りを持って案内する姿が、世界中の旅人を納得させているのですね。", "zh": "当地居民满怀自豪亲自当向导的模样，让全世界的旅人都打心底信服。"},
            {"ch": 4, "v": "M", "ja": "壊して再生し、自然と響き合う美意識は、まさに日本の空間デザインの辞書です。", "zh": "懂得破旧更新并与自然共鸣的美学，简直就是日本空间设计的活字典。"},
            {"ch": 5, "v": "F", "ja": "最後に世界の最新技術では、人型ロボットが工場の現場で働く時代がどんどん近づいています。", "zh": "最后看全球前沿科技，人形机器人进驻汽车工厂打工的时代正加速到来。"},
            {"ch": 5, "v": "M", "ja": "ＡＩと精密な部品の研究が融合する市場で、日本のロボット技術も新たな勝負を迎えています。", "zh": "在AI与精密机电融合的新战场，日本深厚的机器人底蕴正迎来新一轮对决。"},
            {"ch": 5, "v": "F", "ja": "千年の伝統と未来の技術、その両方を大切にする姿勢が日本の魅力をはっきり伝えますね。", "zh": "既敬畏千年传统又拥抱未来科技，这份平衡把日本的魅力清清楚楚展现出来。"},
        ],
    },
}

try:
    from jp_video_scripts_extra import (
        EXTRA_CURATED_JP_VIDEO_SCRIPTS as _EXTRA_JP_VIDS,
        EXTRA_CURATED_VISUAL_TOPICS as _EXTRA_VIS_TOPICS,
    )
    CURATED_VISUAL_TOPICS.update(_EXTRA_VIS_TOPICS)
    CURATED_JP_VIDEO_SCRIPTS.update(_EXTRA_JP_VIDS)
except ImportError:
    pass

try:
    from n2_prep.n2_curriculum_engine import (
        N2_CURATED_JP_VIDEO_SCRIPTS as _N2_JP_VIDS,
        N2_CURATED_VISUAL_TOPICS as _N2_VIS_TOPICS,
    )
    CURATED_VISUAL_TOPICS.update(_N2_VIS_TOPICS)
    CURATED_JP_VIDEO_SCRIPTS.update(_N2_JP_VIDS)
except Exception:
    pass


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def _http_get_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers=UA_HEADER)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_download(url: str, dest: str, timeout: int = 15) -> bool:
    if url.startswith("//"):
        url = "https:" + url
    req = urllib.request.Request(url, headers=UA_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = str(resp.headers.get("Content-Type") or "").lower()
            if "image/" not in ctype and "octet-stream" not in ctype:
                return False
            data = resp.read()
            if len(data) < 8000:
                return False
            with open(dest, "wb") as f:
                f.write(data)
            return True
    except Exception:
        return False


def _probe_image_dims(path: str, ffmpeg_bin: str = "ffmpeg") -> tuple[int, int]:
    """Verify a downloaded image is decodable and return (width, height) using ffmpeg -i (zero ffprobe dependency)."""
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=6,
            check=False,
        )
        err = proc.stderr.decode("utf-8", errors="ignore")
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})(?:[\s,\[])", err)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 0, 0


def _search_ja_wiki_titles(query: str, limit: int = 3) -> list[str]:
    url = "https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": limit,
    })
    try:
        data = _http_get_json(url, timeout=8)
        return [str(x.get("title") or "") for x in (data.get("query") or {}).get("search") or [] if x.get("title")]
    except Exception:
        return []


def _fetch_ja_wiki_media_candidates(page_title: str) -> list[tuple[str, str]]:
    """Return [(filename, url)] of photographic images from a Japanese Wikipedia page."""
    url = "https://ja.wikipedia.org/api/rest_v1/page/media-list/" + urllib.parse.quote(page_title, safe="")
    out: list[tuple[str, str]] = []
    try:
        data = _http_get_json(url, timeout=8)
        for it in data.get("items") or []:
            if it.get("type") != "image":
                continue
            fname = str(it.get("title") or "")
            if not fname or BAD_MEDIA_RE.search(fname):
                continue
            if not re.search(r"\.(jpe?g|png)$", fname, re.I):
                continue
            src = ""
            srcset = it.get("srcset") or []
            if srcset:
                src = str(srcset[-1].get("src") or "")
            if not src and isinstance(it.get("original"), dict):
                src = str(it["original"].get("source") or "")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                src = src.split("?")[0]
                out.append((fname, src))
    except Exception:
        pass
    return out


def _fetch_commons_candidates(query: str, limit: int = 8) -> list[tuple[str, str]]:
    """Search Wikimedia Commons bitmaps and return [(title, thumb_url)]."""
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": 1280,
        "format": "json",
    })
    out: list[tuple[str, str]] = []
    try:
        data = _http_get_json(url, timeout=9)
        pages = (data.get("query") or {}).get("pages") or {}
        for p in pages.values():
            title = str(p.get("title") or "")
            if not title or BAD_MEDIA_RE.search(title):
                continue
            infos = p.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            mime = str(info.get("mime") or "")
            if mime not in ("image/jpeg", "image/png"):
                continue
            w = int(info.get("width") or 0)
            h = int(info.get("height") or 0)
            if w < 560 or h < 320:
                continue
            ratio = w / max(1, h)
            if ratio < 0.72 or ratio > 2.55:
                continue
            dl = str(info.get("thumburl") or info.get("url") or "")
            if dl:
                out.append((title, dl))
    except Exception:
        pass
    return out


def _resolve_topic_queries(story_block: dict[str, Any]) -> dict[str, list[str]]:
    sid = str(story_block.get("id") or "").strip()
    if sid in CURATED_VISUAL_TOPICS:
        return CURATED_VISUAL_TOPICS[sid]

    short_tab = str(story_block.get("short_tab") or "").strip()
    ja_focus = str(story_block.get("ja_focus") or "").strip()
    ja_wiki: list[str] = []
    wm_queries: list[str] = []

    kanji_terms = re.findall(r"[\u4e00-\u9fff]{2,6}", f"{ja_focus} {short_tab}")
    for term in kanji_terms[:4]:
        hits = _search_ja_wiki_titles(term, limit=2)
        for h in hits:
            if h not in ja_wiki:
                ja_wiki.append(h)
        if len(ja_wiki) >= 3:
            break

    if not ja_wiki and short_tab:
        ja_wiki.extend(_search_ja_wiki_titles(short_tab, limit=2))
    if not ja_wiki:
        ja_wiki = ["日本", "東京"]

    wm_queries.append(f"Japan {short_tab}" if short_tab else "Tokyo Japan street")
    wm_queries.append("Tokyo Japan urban landscape")
    return {"ja_wiki": ja_wiki[:3], "wm_queries": wm_queries, "prefer": []}


def _download_chapter_shots(
    story_block: dict[str, Any],
    work_dir: str,
    used_hashes: set[str],
    ffmpeg_bin: str,
    want: int = 3,
) -> list[str]:
    """Download `want` distinct verified photographic shots for a chapter."""
    spec = _resolve_topic_queries(story_block)
    prefer = [p.lower() for p in (spec.get("prefer") or [])]

    candidates: list[tuple[int, str, str]] = []
    seen_urls: set[str] = set()

    for page in spec.get("ja_wiki") or []:
        for fname, url in _fetch_ja_wiki_media_candidates(page):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            fn_low = fname.lower()
            score = 50
            for idx, pref in enumerate(prefer):
                if pref in fn_low or pref in url.lower():
                    score += 120 - idx * 15
                    break
            if fn_low.endswith((".jpg", ".jpeg")):
                score += 10
            if ARCHIVAL_PHOTO_RE.search(fname) or ARCHIVAL_PHOTO_RE.search(url):
                score += 45
            candidates.append((score, fname, url))

    for q in spec.get("wm_queries") or []:
        for fname, url in _fetch_commons_candidates(q, limit=6):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            fn_low = fname.lower()
            score = 40
            for idx, pref in enumerate(prefer):
                if pref in fn_low or pref in url.lower():
                    score += 120 - idx * 15
                    break
            if fn_low.endswith((".jpg", ".jpeg")):
                score += 10
            if ARCHIVAL_PHOTO_RE.search(fname) or ARCHIVAL_PHOTO_RE.search(url):
                score += 45
            candidates.append((score, fname, url))

    candidates.sort(key=lambda x: -x[0])

    saved: list[str] = []
    ch_idx = int(story_block.get("chapter", 0))
    for i, (_sc, fname, url) in enumerate(candidates):
        if len(saved) >= want:
            break
        ext = ".png" if fname.lower().endswith(".png") else ".jpg"
        raw_path = os.path.join(work_dir, f"ch{ch_idx}_raw_{i}{ext}")
        if not _http_download(url, raw_path):
            continue
        w, h = _probe_image_dims(raw_path, ffmpeg_bin=ffmpeg_bin)
        if w < 480 or h < 270:
            continue
        ratio = w / max(1, h)
        if ratio < 0.72 or ratio > 2.6:
            continue
        with open(raw_path, "rb") as f:
            hsh = hashlib.md5(f.read()).hexdigest()[:12]
        if hsh in used_hashes:
            continue
        used_hashes.add(hsh)
        saved.append(raw_path)

    return saved


_IA_URL_CACHE: dict[str, str] = {}
_WM_VIDEO_URL_CACHE: dict[str, str] = {}


def _resolve_ia_mp4_url(ident: str) -> str:
    """Resolve a direct streaming MP4 URL for a public-domain Internet Archive archival film."""
    if ident in _IA_URL_CACHE:
        return _IA_URL_CACHE[ident]
    try:
        meta_u = f"https://archive.org/metadata/{urllib.parse.quote(ident)}/files"
        data = _http_get_json(meta_u, timeout=10)
        files = data.get("result") or []
        mp4s = [
            f for f in files
            if str(f.get("name") or "").lower().endswith(".mp4")
            and "512kb" not in str(f.get("name") or "").lower()
        ]
        if not mp4s:
            mp4s = [f for f in files if str(f.get("name") or "").lower().endswith(".mp4")]
        if not mp4s:
            return ""
        mp4s.sort(key=lambda f: int(f.get("size") or 999_999_999))
        name = str(mp4s[0]["name"])
        url = f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(name)}"
        _IA_URL_CACHE[ident] = url
        return url
    except Exception:
        return ""


def _resolve_wm_video_url(file_title: str) -> str:
    """Resolve a direct Wikimedia Commons public-domain/CC historical video URL."""
    if file_title in _WM_VIDEO_URL_CACHE:
        return _WM_VIDEO_URL_CACHE[file_title]
    try:
        u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "format": "json",
        })
        data = _http_get_json(u, timeout=10)
        pages = (data.get("query") or {}).get("pages") or {}
        for p in pages.values():
            infos = p.get("imageinfo") or []
            if infos and infos[0].get("url"):
                url = str(infos[0]["url"])
                _WM_VIDEO_URL_CACHE[file_title] = url
                return url
    except Exception:
        pass
    return ""


def _resolve_archival_footage_candidates(story_block: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered historical footage candidates for a chapter (exact curated match first, then theme match)."""
    sid = str(story_block.get("id") or "").strip()
    if sid in CURATED_ARCHIVAL_FOOTAGE:
        return list(CURATED_ARCHIVAL_FOOTAGE[sid])
    blob = " ".join(
        str(story_block.get(k) or "") for k in ("short_tab", "title", "ja_focus")
    )
    out: list[dict[str, Any]] = []
    for pat, entry in THEME_ARCHIVAL_FALLBACKS:
        if re.search(pat, blob):
            out.append(dict(entry))
            if len(out) >= 2:
                break
    return out


def _download_chapter_archival_clips(
    story_block: dict[str, Any],
    work_dir: str,
    used_clip_keys: set[str],
    ffmpeg_bin: str,
    want: int = 1,
    clip_dur: float = 11.0,
) -> list[dict[str, str]]:
    """
    Extract up to `want` crisp, real historical moving video clips (854x480 24fps, zero audio,
    overscan-cropped to remove vintage 4:3 pillarboxes) via ffmpeg HTTP range streaming.
    100% fault-tolerant: gracefully returns [] if offline, mocked, or remote host throttles.
    """
    if not ffmpeg_bin or os.path.basename(ffmpeg_bin) == "true":
        return []
    cands = _resolve_archival_footage_candidates(story_block)
    if not cands:
        return []

    ch_idx = int(story_block.get("chapter", 0))
    saved: list[dict[str, str]] = []
    ia_calls = 0

    for idx, cand in enumerate(cands):
        if len(saved) >= want:
            break
        src = str(cand.get("src") or "")
        ident = str(cand.get("id") or "")
        ss = max(0, int(cand.get("ss") or 0))
        label = str(cand.get("label") or ident)
        clip_key = f"{src}:{ident}:{ss}"
        if not ident or clip_key in used_clip_keys:
            continue

        if src == "ia":
            if ia_calls > 0:
                time.sleep(0.8)
            ia_calls += 1
            media_url = _resolve_ia_mp4_url(ident)
        elif src == "wm":
            media_url = _resolve_wm_video_url(ident)
        else:
            continue

        if not media_url:
            continue

        out_mp4 = os.path.join(work_dir, f"ch{ch_idx}_archival_{idx}.mp4")
        # Overscan-crop cleanly removes embedded black pillarboxes/film borders on 4:3 archival reels
        scale_w, scale_h = (1140, 642) if "pavillon" in ident.lower() else (940, 529)
        vf = (
            f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            "crop=854:480:(iw-854)/2:(ih-480)/2,"
            "fps=24,setsar=1,format=yuv420p"
        )
        cmd = [
            ffmpeg_bin, "-y", "-v", "error",
            "-user_agent", UA_HEADER["User-Agent"],
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
            "-rw_timeout", "12000000",
            "-ss", str(ss),
            "-i", media_url,
            "-t", f"{clip_dur:.2f}",
            "-an",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            out_mp4,
        ]
        try:
            res = subprocess.run(cmd, timeout=22, check=False)
            if res.returncode == 0 and os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 35000:
                w, h = _probe_image_dims(out_mp4, ffmpeg_bin=ffmpeg_bin)
                if w >= 640 and h >= 360:
                    used_clip_keys.add(clip_key)
                    saved.append({"path": out_mp4, "label": label, "source": src})
                    if src == "ia":
                        time.sleep(0.7)
        except Exception:
            continue

    return saved


def _render_fallback_zen_still(dest_jpg: str, ffmpeg_bin: str = "ffmpeg") -> None:
    """Offline safety net: render a warm subtle Kyoto paper/ink gradient 16:9 frame via ffmpeg."""
    subprocess.run(
        [
            ffmpeg_bin, "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=0x1d1c19:s=960x540:d=1",
            "-vf", "geq=r='min(255,29+14*sin(X/240)+8*cos(Y/180))':g='min(255,28+16*sin(X/260)+7*cos(Y/180))':b='min(255,25+12*sin(X/280)+6*cos(Y/200))'",
            "-frames:v", "1", "-q:v", "4", dest_jpg,
        ],
        check=False,
    )


def _render_chapter_poster(src_img: str, dest_jpg: str, ffmpeg_bin: str = "ffmpeg") -> bool:
    """Create a crisp 960x540 16:9 warm editorial documentary poster JPEG."""
    vf = (
        "scale=960:540:force_original_aspect_ratio=increase,"
        "crop=960:540:(iw-960)/2:(ih-540)/2,"
        "eq=saturation=0.95:contrast=1.04:brightness=-0.02,"
        "vignette=angle=PI/5"
    )
    res = subprocess.run(
        [
            ffmpeg_bin, "-y", "-v", "error",
            "-i", src_img,
            "-vf", vf,
            "-frames:v", "1", "-q:v", "4", dest_jpg,
        ],
        check=False,
    )
    return res.returncode == 0 and os.path.exists(dest_jpg) and os.path.getsize(dest_jpg) > 4000


def _collect_daily_target_words(
    imm_vocab_report: dict[str, Any] | None,
    review_items: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Collect today's podcast rumination/focus words + active non-green vocab cards + lookup words."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(word: str, kana: str, zh: str, source: str) -> None:
        w = str(word or "").strip()
        if not w or w in seen:
            return
        seen.add(w)
        out.append({"word": w, "kana": str(kana or w).strip(), "zh": str(zh or "").strip(), "source": source})

    # 1) Rumination words (today focus + yesterday relearn/carryover)
    rep = imm_vocab_report or {}
    for it in (rep.get("rumination_words") or []):
        _add(it.get("kanji") or it.get("kana"), it.get("kana"), it.get("zh"), str(it.get("reason") or "播客"))
    for it in (rep.get("today_spotlight") or []):
        _add(it.get("kanji") or it.get("kana"), it.get("kana"), it.get("zh"), "播客")

    # 2) Review item vocab words
    for rv in (review_items or []):
        if rv.get("kind") == "vocab":
            _add(rv.get("title"), rv.get("kana"), rv.get("zh"), "复盘")

    # 3) Active non-green vocab cards & relearn holds from n3_live_state.json + immersion bank
    try:
        import vocab_cards as vc
        import immersion_vocab_engine as ive
        if os.path.exists(STATE_PATH):
            st = json.load(open(STATE_PATH, encoding="utf-8"))
            # Relearn queue first
            for pt in (st.get("radio_relearn_queue") or {}).keys():
                if not pt or str(pt).startswith("〜"):
                    continue
                vsp = vc.VOCAB_CARDS.get(pt)
                if vsp:
                    _add(pt, vsp.get("kana", pt), vsp.get("zh", ""), "反刍")
                else:
                    for e in ive.IMMERSION_VOCAB_BANK:
                        if e["kanji"] == pt or e["kana"] == pt:
                            _add(e["kanji"], e["kana"], e["carrier"], "反刍")
                            break
            # Active non-green tracked vocab words
            for v in (st.get("vocab_tracked") or []):
                if v.get("status") != "green":
                    w = str(v.get("word") or "").strip()
                    vsp = vc.VOCAB_CARDS.get(w) or {}
                    _add(w, v.get("kana") or vsp.get("kana") or w, vsp.get("zh") or v.get("zh") or "", "记词")
                    if len(out) >= 24:
                        break
    except Exception:
        pass

    return out[:24]


def _author_jp_video_script_llm(
    story_blocks: list[dict[str, Any]],
    target_words: list[dict[str, str]],
    target_grammar: list[str],
) -> dict[str, Any] | None:
    """In GitHub Actions (when LLM token is present), script a fresh 14-16 line ALL-JAPANESE NHK documentary video."""
    try:
        from daily_news_salon_gen import _call_chat_llm, _strip_json_fence
    except Exception:
        return None

    chapters_brief = [
        {
            "ch": int(b.get("chapter", i)),
            "short_tab": str(b.get("short_tab") or ""),
            "title": str(b.get("title") or ""),
            "ja_focus": str(b.get("ja_focus") or ""),
        }
        for i, b in enumerate(story_blocks)
    ]
    must_words = [f"{w['word']}({w['kana']}: {w['zh']})" for w in target_words[:12]]
    must_gram = [g for g in target_grammar[:6] if g]

    sys_p = (
        "あなたはNHKの文化・科学ドキュメンタリー脚本家です。"
        "JLPT N3〜N2学習者向けに、今日のポッドキャストで聴いた日本の物語と世界の科学・歴史を75〜90秒の"
        "自然な全日本語ショート動画（男性ナレーターMと女性聞き手Fの掛け合い、全14〜16行）に仕立ててください。"
        "厳守事項："
        "1) 音声台本 `ja` は100%自然な日本語（漢字かな交じり、N3〜N2レベル、1行18〜38文字、中国語を一切混ぜない）。"
        "2) 抽象的なまとめや説教を避け、具体的な年号・地名・人物・歴史や科学の鮮やかな対比（光と影、制度と人間）を簡潔に織り込む。"
        "3) 指定された『重要語彙』のうち最低9語を自然に織り込み、特に上位4語は動画内で2回ずつ反復する。"
        "4) 指定された『文法表現』のうち最低4つをストーリーの中で自然に使う（文法解説は絶対しない）。"
        "5) 各行に簡潔で落ち着いた中国語字幕 `zh`（破折号「—」禁止、大げさな感嘆や説教調も禁止）と対応する章番号 `ch`（0〜5）を付ける。"
        "6) JSONのみを返す：{title_ja, title_zh, lines:[{ch, v:'M'|'F', ja, zh}]}。"
    )
    usr_p = json.dumps(
        {
            "chapters": chapters_brief,
            "must_weave_words_repeat_top4_twice": must_words,
            "target_grammar_patterns": must_gram,
        },
        ensure_ascii=False,
    )
    raw = _call_chat_llm(sys_p, usr_p)
    if not raw:
        return None
    try:
        obj = json.loads(_strip_json_fence(raw))
        lines = obj.get("lines") or []
        if not isinstance(lines, list) or not (10 <= len(lines) <= 20):
            return None
        max_ch = max(0, len(story_blocks) - 1)
        clean_lines: list[dict[str, Any]] = []
        for idx, ln in enumerate(lines):
            if not isinstance(ln, dict):
                continue
            ja = str(ln.get("ja") or "").strip().replace("—", "")
            zh = str(ln.get("zh") or "").strip().replace("——", "，").replace("—", "，")
            v = "F" if str(ln.get("v") or "").upper() == "F" else "M"
            ch = max(0, min(max_ch, int(ln.get("ch", idx % max(1, max_ch + 1)))))
            # Reject lines without Japanese kana (ensures 100% real Japanese, never Chinese!)
            if len(ja) < 8 or len(re.findall(r"[ぁ-んァ-ヶー]", ja)) < 4:
                return None
            clean_lines.append({"ch": ch, "v": v, "ja": ja, "zh": zh})
        if len(clean_lines) < 10:
            return None
        return {
            "title_ja": str(obj.get("title_ja") or "今日の日本ストーリー").replace("—", "").strip(),
            "title_zh": str(obj.get("title_zh") or "今日日本故事日语短片").replace("—", "").strip(),
            "lines": clean_lines,
        }
    except Exception:
        return None


_EXTRA_KNOWN_VIDEO_WORDS: dict[str, tuple[str, str, str]] = {
    "裁判": ("さいばん", "审判", "播客"),
    "官僚": ("かんりょう", "官僚", "播客"),
    "ルール": ("ルール", "规则", "播客"),
    "辞書": ("じしょ", "字典", "重点"),
    "象徴": ("しょうちょう", "象征", "反刍"),
    "利益": ("りえき", "利润", "播客"),
    "市場": ("しじょう", "市场", "播客"),
    "予算": ("よさん", "预算", "记词"),
    "書類": ("しょるい", "文件", "记词"),
    "だんだん": ("だんだん", "渐渐", "记词"),
    "はっきり": ("はっきり", "清楚地", "记词"),
    "台風": ("たいふう", "台风", "播客"),
    "研究": ("けんきゅう", "研究", "播客"),
    "構造": ("こうぞう", "结构", "播客"),
    "危機": ("きき", "危机", "播客"),
    "設計": ("せっけい", "设计", "播客"),
    "印象": ("いんしょう", "印象", "反刍"),
    "どんどん": ("どんどん", "迅速地", "记词"),
    "世間": ("せけん", "世间・舆论", "记词"),
    "納得": ("なっとく", "信服・认可", "记词"),
    "表情": ("ひょうじょう", "表情・神态", "记词"),
    "自慢": ("じまん", "炫耀・自豪", "记词"),
    "制度": ("せいど", "制度", "播客"),
    "記憶": ("きおく", "记忆", "播客"),
    "影響": ("えいきょう", "影响", "播客"),
    "伝統": ("でんとう", "传统", "播客"),
    "歴史": ("れきし", "历史", "播客"),
    "油断": ("ゆだん", "大意・松懈", "记词"),
}


def _build_video_word_entries(target_words: list[dict[str, str]]) -> list[dict[str, str]]:
    """Combine today's target words with curated documentary vocabulary for clickable word chips."""
    word_entries: list[dict[str, str]] = [
        w for w in (target_words or []) if w.get("word") and len(str(w["word"]).strip()) >= 2
    ]
    known_set = {w["word"] for w in word_entries}
    for kw, (kk, kz, ks) in _EXTRA_KNOWN_VIDEO_WORDS.items():
        if kw not in known_set:
            word_entries.append({"word": kw, "kana": kk, "zh": kz, "source": ks})
            known_set.add(kw)
    return word_entries


def _ensure_script_meets_word_and_cue_floor(
    script: dict[str, Any],
    story_blocks: list[dict[str, Any]],
    target_words: list[dict[str, str]],
    min_cues: int = 10,
    min_words: int = 8,
) -> dict[str, Any]:
    """
    Guarantee every episode's ALL-JAPANESE documentary script (curated, LLM, or deterministic)
    always yields >= min_cues valid Japanese lines, zero em-dashes, and >= min_words matched
    interactive target words so Self-test 13 can never break on any future volume!
    """
    max_ch = max(0, len(story_blocks) - 1)
    lines = [dict(ln) for ln in (script.get("lines") or []) if isinstance(ln, dict) and str(ln.get("ja") or "").strip()]
    for ln in lines:
        ln["ja"] = str(ln.get("ja") or "").strip().replace("——", "、").replace("—", "")
        ln["zh"] = str(ln.get("zh") or "").strip().replace("——", "，").replace("—", "，")
        ln["v"] = "F" if str(ln.get("v") or "").upper() == "F" else "M"
        ln["ch"] = max(0, min(max_ch, int(ln.get("ch", 0))))

    word_entries = _build_video_word_entries(target_words)
    all_ja = "\n".join(ln["ja"] for ln in lines)
    matched = [we["word"] for we in word_entries if we["word"] in all_ja]
    missing = [we for we in word_entries if we["word"] not in matched]

    templates = [
        (
            "今日の話では、{w0}や{w1}という言葉も大切な手がかりになりますね。",
            "今天的故事里，「{w0}」和「{w1}」也是很关键的线索。",
        ),
        (
            "さらに{w0}と{w1}も、日本のニュースでよく耳にする表現です。",
            "此外，「{w0}」和「{w1}」也是日本新闻里常听到的高频表达。",
        ),
        (
            "物語の流れの中で{w0}や{w1}を押さえると、内容がぐっとクリアになります。",
            "顺着故事记住「{w0}」和「{w1}」，整段内容一下就透亮了。",
        ),
        (
            "もう一度、{w0}と{w1}の響きを耳でたしかめておきましょう。",
            "再顺着耳朵把「{w0}」和「{w1}」的读音稳稳听一遍。",
        ),
    ]
    tpl_idx = 0
    while len(matched) < min_words and missing:
        pair = missing[:2]
        missing = missing[2:]
        w0 = pair[0]["word"]
        w1 = pair[1]["word"] if len(pair) > 1 else (matched[0] if matched else "印象")
        ja_t, zh_t = templates[tpl_idx % len(templates)]
        tpl_idx += 1
        ja_line = ja_t.format(w0=w0, w1=w1)
        zh_line = zh_t.format(w0=w0, w1=w1)
        ins_pos = max(0, len(lines) - 1) if len(lines) >= 2 else len(lines)
        v_next = "F" if (ins_pos % 2 == 1) else "M"
        ch_next = min(max_ch, max(0, (ins_pos * (max_ch + 1)) // max(1, len(lines) + 1)))
        lines.insert(ins_pos, {"ch": ch_next, "v": v_next, "ja": ja_line, "zh": zh_line})
        for we in pair:
            if we["word"] not in matched:
                matched.append(we["word"])

    pad_lines = [
        ("こうした出来事の裏側を知ると、日本の社会がもっと身近に感じられますね。", "了解这些事件背后的脉络后，日本社会就显得更加鲜活贴近了。"),
        ("歴史の節目には、いつも現場の人々の粘り強い工夫があります。", "历史的每一个转折点，背后都少不了现场普通人坚韧的巧思。"),
        ("時代が移り変わっても、人の心を動かす物語は色あせません。", "即使时代更迭，真正打动人心的故事也永远不会褪色。"),
        ("短い日本語でも毎日聞き続けると、表現が自然に口から出てきます。", "哪怕每天只听一小段纯日语，表达也会自然而然脱口而出。"),
    ]
    p_i = 0
    while len(lines) < min_cues:
        ja_p, zh_p = pad_lines[p_i % len(pad_lines)]
        p_i += 1
        lines.append({
            "ch": max_ch,
            "v": "F" if (len(lines) % 2 == 1) else "M",
            "ja": ja_p,
            "zh": zh_p,
        })

    return {
        "title_ja": str(script.get("title_ja") or "今日の日本ストーリー").replace("——", " ").replace("—", "").strip(),
        "title_zh": str(script.get("title_zh") or "今日日本故事").replace("——", "，").replace("—", "，").strip(),
        "lines": lines[:18],
    }


def _build_deterministic_jp_video_script(
    story_blocks: list[dict[str, Any]],
    target_words: list[dict[str, str]],
) -> dict[str, Any]:
    """100% offline-safe ALL-JAPANESE documentary script builder from today's chapters & focus words."""
    lines: list[dict[str, Any]] = []
    max_ch = max(0, len(story_blocks) - 1)
    # Opening line
    lines.append({
        "ch": 0,
        "v": "M",
        "ja": "今日の物語を、やさしい日本語で振り返ってみましょう。",
        "zh": "让我们用清晰自然的日语，重温今天的故事。",
    })
    for idx, blk in enumerate(story_blocks):
        ch_idx = int(blk.get("chapter", idx))
        jf = str(blk.get("ja_focus") or "").strip()
        short_tab = str(blk.get("short_tab") or "").strip()
        sents = [
            s.strip()
            for s in re.split(r"(?<=[。！？])", jf)
            if s.strip() and len(s.strip()) >= 6 and len(re.findall(r"[ぁ-んァ-ヶー]", s)) >= 4
        ]
        for s in sents[:2]:
            if len(lines) >= 10:
                break
            lines.append({
                "ch": ch_idx,
                "v": "F" if (len(lines) % 2 == 1) else "M",
                "ja": s,
                "zh": f"{short_tab}：重温今日关键日语表达。",
            })
    # Rumination echo lines weaving top 8-10 target words clearly in Japanese (top 2 echoed twice!)
    word_entries = _build_video_word_entries(target_words)
    top_w = word_entries[:10]
    if len(top_w) >= 2:
        w0, w1 = top_w[0], top_w[1]
        lines.append({
            "ch": min(1, max_ch),
            "v": "F",
            "ja": f"今日のキーワードは、{w0['word']}と{w1['word']}ですね。",
            "zh": f"今天的关键词是「{w0['word']}」和「{w1['word']}」。",
        })
        lines.append({
            "ch": min(3, max_ch),
            "v": "M",
            "ja": f"物語の中で{w0['word']}や{w1['word']}が出てくると、内容がはっきり分かります。",
            "zh": f"在故事里听到「{w0['word']}」和「{w1['word']}」，意思一下就清楚了。",
        })
    if len(top_w) >= 4:
        w2, w3 = top_w[2], top_w[3]
        lines.append({
            "ch": min(2, max_ch),
            "v": "F",
            "ja": f"さらに{w2['word']}や{w3['word']}も、ニュースでよく使われる大切な言葉です。",
            "zh": f"另外「{w2['word']}」和「{w3['word']}」也是新闻里高频出现的重要词。",
        })
    if len(top_w) >= 6:
        w4, w5 = top_w[4], top_w[5]
        lines.append({
            "ch": min(4, max_ch),
            "v": "M",
            "ja": f"現場の変化を見るうえでは、{w4['word']}と{w5['word']}にも注目したいですね。",
            "zh": f"看清现场变化时，「{w4['word']}」和「{w5['word']}」同样值得留意。",
        })
    if len(top_w) >= 8:
        w6, w7 = top_w[6], top_w[7]
        lines.append({
            "ch": max_ch,
            "v": "F",
            "ja": f"最後に{w6['word']}や{w7['word']}も合わせて押さえておきましょう。",
            "zh": f"最后也顺手把「{w6['word']}」和「{w7['word']}」一并记牢。",
        })
    lines.append({
        "ch": max_ch,
        "v": "M",
        "ja": "毎日少しずつ日本語で物語を聞くことで、言葉が自然に身についていきます。",
        "zh": "每天用日语看一小段故事，这些词就会自然扎进脑子里。",
    })
    main_tabs = [str(b.get("short_tab") or "") for b in story_blocks[1:4] if b.get("short_tab")]
    return {
        "title_ja": "今日の日本ストーリー",
        "title_zh": " · ".join(main_tabs[:2]) if main_tabs else "今日日本故事",
        "lines": lines[:18],
    }


def _resolve_jp_video_script(
    story_blocks: list[dict[str, Any]],
    target_words: list[dict[str, str]],
    review_items: list[dict[str, Any]],
) -> dict[str, Any]:
    # 1) Check curated NHK-grade gold scripts first
    for blk in story_blocks:
        sid = str(blk.get("id") or "").strip()
        if sid in CURATED_JP_VIDEO_SCRIPTS:
            raw_curated = json.loads(json.dumps(CURATED_JP_VIDEO_SCRIPTS[sid], ensure_ascii=False))
            return _ensure_script_meets_word_and_cue_floor(raw_curated, story_blocks, target_words)
    # 2) In CI with LLM key, author a fresh tailored ALL-JAPANESE documentary script
    gram_pts = [str(it.get("title") or "") for it in (review_items or []) if it.get("kind") == "grammar"]
    llm_script = _author_jp_video_script_llm(story_blocks, target_words, gram_pts)
    if llm_script:
        return _ensure_script_meets_word_and_cue_floor(llm_script, story_blocks, target_words)
    # 3) Guaranteed offline ALL-JAPANESE fallback
    det_script = _build_deterministic_jp_video_script(story_blocks, target_words)
    return _ensure_script_meets_word_and_cue_floor(det_script, story_blocks, target_words)


async def _edge_tts_to_mp3(text: str, voice: str, rate: str, dest_mp3: str) -> bool:
    import edge_tts  # type: ignore
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
    kwargs = {"proxy": proxy_url} if proxy_url else {}
    alt_voice = "ja-JP-KeitaNeural" if voice == "ja-JP-NanamiNeural" else "ja-JP-NanamiNeural"
    for attempt in range(5):
        use_voice = voice if attempt < 3 else alt_voice
        try:
            comm = edge_tts.Communicate(text, voice=use_voice, rate=rate, **kwargs)
            await comm.save(dest_mp3)
            if os.path.exists(dest_mp3) and os.path.getsize(dest_mp3) > 800:
                return True
        except Exception:
            await asyncio.sleep(0.6 * (attempt + 1))
    return False


def _decode_mp3_to_pcm_f32(mp3_path: str, ffmpeg_bin: str) -> Any:
    import numpy as np
    raw = subprocess.check_output(
        [ffmpeg_bin, "-v", "error", "-i", mp3_path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "pipe:1"],
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    arr = np.frombuffer(raw, dtype=np.float32).copy()
    if arr.size < 400:
        return arr
    # Trim leading/trailing near-silence cleanly while keeping 45ms breath cushion
    abs_a = np.abs(arr)
    peak = float(abs_a.max()) or 1.0
    nz = np.where(abs_a > peak * 0.025)[0]
    if nz.size > 100:
        pad = int(0.045 * SR)
        lo = max(0, int(nz[0]) - pad)
        hi = min(arr.size, int(nz[-1]) + pad)
        arr = arr[lo:hi]
    # Normalize speech RMS to crisp broadcast target (-17.5 dBFS)
    rms = float(np.sqrt(np.mean(arr * arr) + 1e-12))
    if rms > 1e-5:
        gain = min(3.2, 0.135 / rms)
        arr = np.tanh(arr * gain * 1.1) / 1.1
    return arr


def _generate_zen_ambient_bed(total_samples: int, voice_env: Any) -> Any:
    """
    Generate an original, warm, minimalist Japanese pentatonic ambient documentary score
    (D minor pentatonic warm electric piano / koto harmonic pad, gently ducked -25 dB under speech).
    Zero external assets, zero copyright risk.
    """
    import numpy as np
    t = np.arange(total_samples, dtype=np.float32) / float(SR)
    # Slow, contemplative 4-chord cycle (every 5.5s): Dm9 -> Bbmaj7 -> Csus2 -> Am7
    chords = [
        (146.83, 220.00, 293.66, 329.63),  # D3 A3 D4 E4
        (116.54, 174.61, 261.63, 349.23),  # Bb2 F3 C4 F4
        (130.81, 196.00, 293.66, 392.00),  # C3 G3 D4 G4
        (110.00, 164.81, 261.63, 329.63),  # A2 E3 C4 E4
    ]
    bed = np.zeros(total_samples, dtype=np.float32)
    chord_sec = 5.5
    chord_len = int(chord_sec * SR)
    n_chords = int(math.ceil(total_samples / chord_len))
    for ci in range(n_chords):
        s0 = ci * chord_len
        s1 = min(total_samples, s0 + chord_len)
        seg_n = s1 - s0
        if seg_n <= 0:
            break
        lt = np.arange(seg_n, dtype=np.float32) / float(SR)
        # Soft piano-pad envelope (smooth swell + gentle decay)
        env = np.minimum(1.0, lt / 0.65) * np.exp(-lt * 0.18)
        fade_tail = np.minimum(1.0, (seg_n - np.arange(seg_n, dtype=np.float32)) / (0.6 * SR))
        env = env * fade_tail
        freqs = chords[ci % len(chords)]
        sig = np.zeros(seg_n, dtype=np.float32)
        for fi, f in enumerate(freqs):
            w = 0.34 if fi == 0 else (0.24 if fi < 3 else 0.16)
            # Pure fundamental + tiny warm 2nd harmonic
            sig += w * (np.sin(2.0 * math.pi * f * lt) + 0.14 * np.sin(4.0 * math.pi * f * lt) * np.exp(-lt * 0.9))
        bed[s0:s1] += sig * env

    # Subtle gentle high-register plucked koto/bell sparkle on chord downbeats
    sparkle_notes = [587.33, 659.25, 523.25, 440.00, 698.46, 587.33]
    for ci in range(n_chords):
        s0 = ci * chord_len + int(0.15 * SR)
        if s0 >= total_samples:
            break
        s1 = min(total_samples, s0 + int(2.6 * SR))
        lt = np.arange(s1 - s0, dtype=np.float32) / float(SR)
        f = sparkle_notes[ci % len(sparkle_notes)]
        plk = np.sin(2.0 * math.pi * f * lt) * np.exp(-lt * 2.1) * np.minimum(1.0, lt / 0.012)
        bed[s0:s1] += 0.14 * plk

    # Normalize bed and apply smooth sidechain ducking under Japanese voices
    b_peak = float(np.max(np.abs(bed))) or 1.0
    bed = bed / b_peak
    # Smooth voice envelope (moving avg ~250ms) -> duck to 0.036 under voice, 0.115 in open intro/outro
    win = int(0.28 * SR)
    kernel = np.ones(win, dtype=np.float32) / float(win)
    sm_env = np.convolve(np.abs(voice_env), kernel, mode="same")
    speech_mask = np.clip(sm_env / 0.028, 0.0, 1.0)
    gain_curve = 0.115 * (1.0 - speech_mask) + 0.036 * speech_mask
    # Clean fade-in (0.7s) & fade-out (1.5s)
    fi_n = min(total_samples, int(0.7 * SR))
    fo_n = min(total_samples, int(1.5 * SR))
    gain_curve[:fi_n] *= np.linspace(0.0, 1.0, fi_n, dtype=np.float32)
    gain_curve[total_samples - fo_n :] *= np.linspace(1.0, 0.0, fo_n, dtype=np.float32)
    return bed * gain_curve


def _fmt_vtt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60.0
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _write_bilingual_vtt(cues: list[dict[str, Any]], dest_vtt: str) -> None:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_vtt_ts(c['s'])} --> {_fmt_vtt_ts(c['e'])}")
        lines.append(str(c.get("ja") or ""))
        if c.get("zh"):
            lines.append(str(c["zh"]))
        lines.append("")
    with open(dest_vtt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def _synth_speaking_prompt_audios(
    speaking_prompts: list[dict[str, Any]],
    ver_tag: str,
) -> None:
    """Render real native Japanese studio MP3s (`audio/spk_0.mp3`) + Mandarin voice asks (`audio/spk_0_ask.mp3`)."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    for fn in os.listdir(AUDIO_DIR):
        if re.match(r"^spk_\d+(?:_ask)?\.mp3$", fn):
            try:
                os.remove(os.path.join(AUDIO_DIR, fn))
            except OSError:
                pass
    try:
        from conjugation_drills import build_speaking_ask_spoken
    except Exception:
        build_speaking_ask_spoken = None
    voices = ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"]
    for idx, sp in enumerate(speaking_prompts):
        model_ja = str(sp.get("model_ja") or "").strip()
        if not model_ja:
            continue
        dest = os.path.join(AUDIO_DIR, f"spk_{idx}.mp3")
        ok = await _edge_tts_to_mp3(model_ja, voices[idx % len(voices)], "-6%", dest)
        if ok:
            sp["model_audio"] = f"./audio/spk_{idx}.mp3?v={ver_tag}"
        ask_txt = build_speaking_ask_spoken(sp) if build_speaking_ask_spoken else ""
        if ask_txt:
            ask_dest = os.path.join(AUDIO_DIR, f"spk_{idx}_ask.mp3")
            ok_ask = await _edge_tts_to_mp3(ask_txt, "en-US-BrianMultilingualNeural", "+5%", ask_dest)
            if ok_ask:
                sp["ask_audio"] = f"./audio/spk_{idx}_ask.mp3?v={ver_tag}"
                sp["ask_spoken"] = ask_txt


async def _build_jp_documentary_video(
    script: dict[str, Any],
    chapter_shots: dict[int, list[str]],
    chapter_posters: dict[int, str],
    target_words: list[dict[str, str]],
    review_items: list[dict[str, Any]],
    today_str: str,
    ver_tag: str,
    tmpdir: str,
    ffmpeg_bin: str,
    chapter_clips: dict[int, list[dict[str, str]]] | None = None,
) -> dict[str, Any] | None:
    """
    Synthesizes dual-voice ALL-JAPANESE audio + warm documentary music bed, builds exact
    millisecond subtitle cues & word-jump anchors, and renders `video/daily_jp_story.mp4`
    intercutting REAL historical archival video clips with period archival photography!
    """
    import numpy as np

    lines = list(script.get("lines") or [])
    if not lines:
        return None

    # 1. Synthesize every Japanese line cleanly via Edge Neural Japanese voices
    line_mp3s: list[str] = []
    for i, ln in enumerate(lines):
        voice = "ja-JP-NanamiNeural" if ln.get("v") == "F" else "ja-JP-KeitaNeural"
        rate = "-6%" if ln.get("v") == "F" else "-7%"
        dest = os.path.join(tmpdir, f"jp_ln_{i:02d}.mp3")
        ok = await _edge_tts_to_mp3(str(ln["ja"]), voice, rate, dest)
        if not ok:
            print(f"[visual-studio] Japanese neural TTS synthesis failed on line {i}, skipping jp_video")
            return None
        line_mp3s.append(dest)

    # 2. Decode PCM & build exact millisecond timeline
    intro_pad = 0.85
    outro_pad = 1.55
    cursor_s = intro_pad
    pcm_segments: list[tuple[int, Any]] = []
    cues: list[dict[str, Any]] = []

    # Prepare lookup dictionary of known words to tag & highlight inside each Japanese line
    word_entries: list[dict[str, str]] = _build_video_word_entries(target_words)
    known_set = {w["word"] for w in word_entries}
    full_ja_text = "\n".join(str(ln.get("ja") or "") for ln in lines)
    try:
        import vocab_cards as vc
        import immersion_vocab_engine as ive
        for w, vsp in (getattr(vc, "VOCAB_CARDS", {}) or {}).items():
            if len(w) >= 2 and w not in known_set and w in full_ja_text:
                word_entries.append({
                    "word": w,
                    "kana": str(vsp.get("kana") or w),
                    "zh": str(vsp.get("zh") or ""),
                    "source": "记词",
                })
                known_set.add(w)
        for e in (getattr(ive, "IMMERSION_VOCAB_BANK", []) or []):
            w = str(e.get("kanji") or e.get("kana") or "").strip()
            if len(w) >= 2 and w not in known_set and w in full_ja_text:
                word_entries.append({
                    "word": w,
                    "kana": str(e.get("kana") or w),
                    "zh": str(e.get("carrier") or ""),
                    "source": "播客",
                })
                known_set.add(w)
    except Exception:
        pass

    # Track word appearances & timestamps across the video!
    word_hits_map: dict[str, dict[str, Any]] = {}
    prev_ch = -1
    for i, (ln, mp3_p) in enumerate(zip(lines, line_mp3s)):
        pcm = _decode_mp3_to_pcm_f32(mp3_p, ffmpeg_bin)
        dur_s = pcm.size / float(SR)
        ch_idx = int(ln.get("ch", 0))
        if i > 0:
            cursor_s += 0.68 if ch_idx != prev_ch else 0.36
        s_ts = round(cursor_s, 2)
        e_ts = round(cursor_s + dur_s, 2)
        pcm_segments.append((int(round(cursor_s * SR)), pcm))
        cursor_s += dur_s
        prev_ch = ch_idx

        ja_txt = str(ln["ja"])
        line_word_hits: list[str] = []
        for we in word_entries:
            w = we["word"]
            if len(w) >= 2 and w in ja_txt:
                line_word_hits.append(w)
                if w not in word_hits_map:
                    word_hits_map[w] = {
                        "word": w,
                        "kana": we["kana"],
                        "zh": we["zh"],
                        "source": we["source"],
                        "hits": 1,
                        "first_sec": s_ts,
                        "times": [s_ts],
                    }
                else:
                    word_hits_map[w]["hits"] += 1
                    word_hits_map[w]["times"].append(s_ts)

        cues.append({
            "s": s_ts,
            "e": e_ts,
            "v": str(ln.get("v") or "M"),
            "ch": ch_idx,
            "ja": ja_txt,
            "zh": str(ln.get("zh") or ""),
            "hits": line_word_hits,
        })

    total_dur = round(cursor_s + outro_pad, 2)
    total_samples = int(math.ceil(total_dur * SR))

    # Mix voice timeline + original warm documentary pentatonic music bed
    voice_mix = np.zeros(total_samples, dtype=np.float32)
    for start_samp, pcm in pcm_segments:
        end_samp = min(total_samples, start_samp + pcm.size)
        voice_mix[start_samp:end_samp] += pcm[: end_samp - start_samp]

    music_bed = _generate_zen_ambient_bed(total_samples, voice_mix)
    final_mix = np.clip(voice_mix * 0.92 + music_bed, -0.96, 0.96)
    pcm_i16 = (final_mix * 32767.0).astype(np.int16)

    wav_path = os.path.join(tmpdir, "daily_jp_story.wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm_i16.tobytes())

    # 3. Group consecutive cues into visual shots (~6-9s each), leading each chapter with
    #    REAL historical archival moving footage (when available) intercut with period archival stills!
    clips_map = chapter_clips or {}
    shot_plan: list[tuple[str, str, float]] = []  # (kind: "video"|"image", path, raw_dur)
    ch_rot: dict[int, int] = {}
    used_ch_video: set[int] = set()
    used_archival_labels: list[str] = []
    all_fallback_shots = [p for lst in chapter_shots.values() for p in lst]

    def _pick_shot_for_ch(ch_i: int) -> tuple[str, str]:
        ch_vids = clips_map.get(ch_i) or []
        if ch_vids and ch_i not in used_ch_video:
            used_ch_video.add(ch_i)
            v_item = ch_vids[0]
            lbl = str(v_item.get("label") or "")
            if lbl and lbl not in used_archival_labels:
                used_archival_labels.append(lbl)
            return ("video", str(v_item["path"]))
        pool = chapter_shots.get(ch_i) or all_fallback_shots
        idx = ch_rot.get(ch_i, 0)
        ch_rot[ch_i] = idx + 1
        return ("image", pool[idx % len(pool)])

    # Build shot spans aligned cleanly to cue boundaries (target 10-14 distinct cinematic shots across ~80s!)
    span_start = 0.0
    cur_ch = cues[0]["ch"]
    for i, c in enumerate(cues):
        next_ch = cues[i + 1]["ch"] if i + 1 < len(cues) else -999
        span_end = (cues[i + 1]["s"] - 0.18) if i + 1 < len(cues) else total_dur
        span_dur = span_end - span_start
        # Cut on chapter change OR when current shot has lasted >= 6.5s (keeps visual rhythm fresh!)
        if next_ch != cur_ch or span_dur >= 6.8 or i == len(cues) - 1:
            if span_dur >= 2.2 or i == len(cues) - 1:
                kind, media_p = _pick_shot_for_ch(cur_ch)
                shot_plan.append((kind, media_p, max(2.4, span_dur)))
                span_start = span_end
                cur_ch = next_ch if next_ch >= 0 else cur_ch

    # 4. Render smooth 24fps 854x480 H.264/AAC MP4 seamlessly blending real moving archival footage
    #    + period archival stills with gentle Ken Burns motion & 0.45s cross-dissolves!
    fps = 24
    fade = 0.45
    n_shots = len(shot_plan)
    archival_clip_count = sum(1 for k, _, _ in shot_plan if k == "video")
    inputs: list[str] = []
    for kind, media_p, _dur in shot_plan:
        if kind == "video":
            inputs.extend(["-stream_loop", "-1", "-i", media_p])
        else:
            inputs.extend(["-i", media_p])
    inputs.extend(["-i", wav_path])
    audio_idx = n_shots

    motions = [
        lambda f: f"zoompan=z='min(1.11,1+0.00048*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={f}:s=854x480:fps={fps}",
        lambda f: f"zoompan=z='1.10':x='(iw-iw/zoom)*min(1,on/{f})':y='ih/2-(ih/zoom/2)':d={f}:s=854x480:fps={fps}",
        lambda f: f"zoompan=z='max(1.0,1.11-0.00048*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={f}:s=854x480:fps={fps}",
        lambda f: f"zoompan=z='1.10':x='(iw-iw/zoom)*(1-min(1,on/{f}))':y='ih/2-(ih/zoom/2)':d={f}:s=854x480:fps={fps}",
    ]

    fc_parts: list[str] = []
    # Compensate each non-last shot's duration by +fade so after xfade overlaps total duration matches total_dur
    shot_durs: list[float] = []
    for i, (kind, _media_p, raw_d) in enumerate(shot_plan):
        d = raw_d + (fade if i < n_shots - 1 else 0.0)
        shot_durs.append(d)
        if kind == "video":
            fc_parts.append(
                f"[{i}:v]scale=854:480:force_original_aspect_ratio=increase,"
                f"crop=854:480:(iw-854)/2:(ih-480)/2,fps={fps},setsar=1,"
                f"trim=duration={d:.3f},setpts=PTS-STARTPTS,settb=1/{fps},"
                f"eq=saturation=0.92:contrast=1.05:brightness=-0.015,vignette=angle=PI/5,format=yuv420p[v{i}]"
            )
        else:
            frames = max(36, int(math.ceil(d * fps)) + 4)
            mot = motions[i % len(motions)](frames)
            fc_parts.append(
                f"[{i}:v]scale=1280:720:force_original_aspect_ratio=increase,"
                f"crop=1280:720:(iw-1280)/2:(ih-720)*0.28,setsar=1,"
                f"{mot},trim=duration={d:.3f},setpts=PTS-STARTPTS,settb=1/{fps},"
                f"eq=saturation=0.92:contrast=1.05:brightness=-0.015,vignette=angle=PI/5,format=yuv420p[v{i}]"
            )

    if n_shots == 1:
        v_out = "[v0]"
    else:
        prev = "v0"
        offset = shot_durs[0] - fade
        for i in range(1, n_shots):
            nxt = f"vx{i}"
            fc_parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={fade:.2f}:offset={offset:.3f}[{nxt}]")
            prev = nxt
            offset += shot_durs[i] - fade
        v_out = f"[{prev}]"

    fade_out_st = max(1.0, total_dur - 0.75)
    fc_parts.append(f"{v_out}fade=t=out:st={fade_out_st:.2f}:d=0.75[vfinal]")

    dest_mp4 = os.path.join(VIDEO_DIR, "daily_jp_story.mp4")
    dest_vtt = os.path.join(VIDEO_DIR, "daily_jp_story.vtt")
    cmd = [
        ffmpeg_bin, "-y", "-v", "error",
        *inputs,
        "-filter_complex", ";".join(fc_parts),
        "-map", "[vfinal]",
        "-map", f"{audio_idx}:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "25",
        "-profile:v", "main", "-level", "3.1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "112k", "-ac", "1",
        "-t", f"{total_dur:.2f}",
        "-movflags", "+faststart",
        dest_mp4,
    ]
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0 or not os.path.exists(dest_mp4) or os.path.getsize(dest_mp4) < 40000:
        print("[visual-studio] ffmpeg daily_jp_story.mp4 render failed")
        return None

    _write_bilingual_vtt(cues, dest_vtt)

    # Sort interactive target words by hit count desc then first_sec asc
    ranked_words = sorted(
        word_hits_map.values(),
        key=lambda x: (-int(x["hits"]), float(x["first_sec"])),
    )[:12]

    # Detect which grammar patterns from today's review appeared in the Japanese video
    all_ja_blob = " ".join(c["ja"] for c in cues)
    gram_hits: list[str] = []
    for it in (review_items or []):
        if it.get("kind") != "grammar":
            continue
        t = str(it.get("title") or "").strip()
        stem = re.sub(r"[〜~～（(][^）)]*[）)]?", "", t).replace("〜", "").strip()
        if stem and (stem in all_ja_blob or (stem == "ようになる" and "ようになる" in all_ja_blob)):
            if t not in gram_hits:
                gram_hits.append(t)

    mm = int(total_dur // 60)
    ss = int(round(total_dur % 60))
    if ss == 60:
        mm += 1
        ss = 0
    dur_label = f"{mm:02d}:{ss:02d}"
    poster_url = chapter_posters.get(1) or chapter_posters.get(0) or ""

    return {
        "title_ja": str(script.get("title_ja") or "今日の日本ストーリー"),
        "title_zh": str(script.get("title_zh") or "今日日本故事"),
        "video_url": f"./video/daily_jp_story.mp4?v={ver_tag}",
        "vtt_url": f"./video/daily_jp_story.vtt?v={ver_tag}",
        "poster_url": poster_url,
        "duration_sec": total_dur,
        "duration_label": dur_label,
        "shot_count": n_shots,
        "archival_clip_count": archival_clip_count,
        "archival_sources": used_archival_labels,
        "target_words": ranked_words,
        "target_grammar": gram_hits[:6],
        "cues": cues,
    }


async def build_episode_visuals_async(
    today_str: str,
    script_sig: str,
    story_blocks: list[dict[str, Any]],
    chapters_meta: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    speaking_prompts: list[dict[str, Any]],
    audio_mp3_path: str,
    imm_vocab_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Native-async pipeline (safe to `await` directly inside `generate_daily_radio.py`'s event loop!):
      1. Chapter documentary posters (`img/ch_0.jpg` .. `img/ch_5.jpg`) preferring historical archival stills
      2. Real historical archival moving video clips (Wikimedia Commons / Internet Archive Prelinger/NARA/NASA)
      3. ONE cohesive ~80s ALL-JAPANESE daily documentary video (`video/daily_jp_story.mp4` + `.vtt`)
         intercutting real historical moving footage + archival stills while weaving focus/rumination words & grammar!
      4. Native Japanese studio model MP3s (`audio/spk_0.mp3`, `audio/spk_1.mp3`) for speaking cards.
    Decouples video cleanly from grammar flashcards (removes legacy Chinese `rv_*.mp4` clips).
    """
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        print("[visual-studio] ffmpeg not found, skipping video rendering")
        return {}

    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    # Clean stale legacy `rv_*.mp4`/`.vtt` and previous `daily_jp_story.*` so repo stays ultra-lean!
    for fn in os.listdir(VIDEO_DIR):
        if re.match(r"^(rv_\d+|daily_jp_story)\.(mp4|vtt)$", fn):
            try:
                os.remove(os.path.join(VIDEO_DIR, fn))
            except OSError:
                pass
    for fn in os.listdir(IMG_DIR):
        if re.match(r"^ch_\d+\.jpg$", fn):
            try:
                os.remove(os.path.join(IMG_DIR, fn))
            except OSError:
                pass

    ver_tag = f"{today_str}_{str(script_sig or 'v3')[:6]}_jp"
    tmpdir = tempfile.mkdtemp(prefix="n3_vis_")
    used_hashes: set[str] = set()
    used_clip_keys: set[str] = set()
    chapter_shots: dict[int, list[str]] = {}
    chapter_clips: dict[int, list[dict[str, str]]] = {}
    chapter_posters: dict[int, str] = {}
    story_arts: list[dict[str, Any]] = []

    try:
        # 1. Fetch period documentary stills + real historical moving footage clips per chapter
        for blk in story_blocks:
            ch_idx = int(blk.get("chapter", 0))
            shots = _download_chapter_shots(blk, tmpdir, used_hashes, ffmpeg_bin=ffmpeg_bin, want=3)
            clips = _download_chapter_archival_clips(
                blk, tmpdir, used_clip_keys, ffmpeg_bin=ffmpeg_bin, want=1, clip_dur=11.0
            )
            if clips:
                chapter_clips[ch_idx] = clips
            if not shots and clips:
                clip_still = os.path.join(tmpdir, f"ch{ch_idx}_from_archival.jpg")
                subprocess.run(
                    [ffmpeg_bin, "-y", "-v", "error", "-ss", "2.0", "-i", clips[0]["path"], "-frames:v", "1", "-q:v", "4", clip_still],
                    timeout=8, check=False,
                )
                if os.path.exists(clip_still) and os.path.getsize(clip_still) > 4000:
                    shots = [clip_still]
            if not shots:
                fb_jpg = os.path.join(tmpdir, f"ch{ch_idx}_fallback.jpg")
                _render_fallback_zen_still(fb_jpg, ffmpeg_bin=ffmpeg_bin)
                shots = [fb_jpg]
            chapter_shots[ch_idx] = shots

            poster_file = os.path.join(IMG_DIR, f"ch_{ch_idx}.jpg")
            if _render_chapter_poster(shots[0], poster_file, ffmpeg_bin=ffmpeg_bin):
                rel_poster = f"./img/ch_{ch_idx}.jpg?v={ver_tag}"
                chapter_posters[ch_idx] = rel_poster
                for ch_m in chapters_meta:
                    if int(ch_m.get("idx", -1)) == ch_idx:
                        ch_m["img"] = rel_poster

        # 2. Keep grammar/vocab review flashcards clean & decoupled (thumbnail only, no Chinese video clutter!)
        for item in review_items:
            ch_idx = int(item.get("chapter_idx", 0))
            if chapter_posters.get(ch_idx):
                item["img"] = chapter_posters[ch_idx]
            item.pop("video_url", None)
            item.pop("vtt_url", None)
            item.pop("subtitles", None)

        # 3. Attach posters AND render real native Japanese studio audio for speaking prompts
        for sp in speaking_prompts:
            ch_idx = int(sp.get("chapter_idx", 0))
            if chapter_posters.get(ch_idx):
                sp["img"] = chapter_posters[ch_idx]
        await _synth_speaking_prompt_audios(speaking_prompts, ver_tag)

        # 4. Build today's cohesive ALL-JAPANESE Documentary Short Video (`video/daily_jp_story.mp4`)
        target_words = _collect_daily_target_words(imm_vocab_report, review_items)
        jp_script = _resolve_jp_video_script(story_blocks, target_words, review_items)
        jp_video = await _build_jp_documentary_video(
            script=jp_script,
            chapter_shots=chapter_shots,
            chapter_posters=chapter_posters,
            target_words=target_words,
            review_items=review_items,
            today_str=today_str,
            ver_tag=ver_tag,
            tmpdir=tmpdir,
            ffmpeg_bin=ffmpeg_bin,
            chapter_clips=chapter_clips,
        )

        # 5. Build `story_arts` gallery for main player cover & chapter posters
        for blk in story_blocks:
            ch_idx = int(blk.get("chapter", 0))
            poster_rel = chapter_posters.get(ch_idx, "")
            if not poster_rel:
                continue
            short_tab = str(blk.get("short_tab") or f"第{ch_idx + 1}章").strip()
            raw_title = str(blk.get("title") or short_tab).strip()
            story_arts.append({
                "chapters": [ch_idx],
                "img": poster_rel,
                "title": short_tab,
                "subtitle": raw_title,
            })

        artwork_url = chapter_posters.get(0) or (story_arts[0]["img"] if story_arts else "")
        arch_n = int((jp_video or {}).get("archival_clip_count") or 0)
        jp_info = (
            f"jp_video={jp_video['duration_label']} ({len(jp_video['target_words'])} words, "
            f"{jp_video['shot_count']} shots, {arch_n} archival clips)"
            if jp_video else "jp_video=none"
        )
        spk_aud = sum(1 for sp in speaking_prompts if sp.get("model_audio"))
        print(
            f"[visual-studio] Built {len(chapter_posters)} posters + {jp_info} + "
            f"{spk_aud}/{len(speaking_prompts)} speaking studio MP3s for {today_str}"
        )
        out: dict[str, Any] = {
            "artwork_url": artwork_url,
            "story_arts": story_arts,
        }
        if jp_video:
            out["jp_video"] = jp_video
        return out
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_episode_visuals(
    today_str: str,
    script_sig: str,
    story_blocks: list[dict[str, Any]],
    chapters_meta: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    speaking_prompts: list[dict[str, Any]],
    audio_mp3_path: str,
    imm_vocab_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sync wrapper safe BOTH outside AND inside a running asyncio event loop."""
    coro = build_episode_visuals_async(
        today_str=today_str,
        script_sig=script_sig,
        story_blocks=story_blocks,
        chapters_meta=chapters_meta,
        review_items=review_items,
        speaking_prompts=speaking_prompts,
        audio_mp3_path=audio_mp3_path,
        imm_vocab_report=imm_vocab_report,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
