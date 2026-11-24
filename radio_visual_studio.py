#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Post-Listening Visual Cinema & Synchronized Subtitle Studio (radio_visual_studio.py).

Automatically turns every daily 《锵锵三人行》 episode's 5-minute post-listening review
into a visual documentary experience:
1. Fetches authentic, open-licensed Japanese historical & cultural photographs from
   Japanese Wikipedia & Wikimedia Commons (zero API keys, zero copyright risk, 100% pure cloud).
2. Renders chapter documentary posters (`img/ch_0.jpg` .. `img/ch_5.jpg`) for the main
   radio player, Android lock-screen MediaSession artwork, and completion visual reel.
3. Cuts real self-contained H.264/AAC MP4 documentary clips (`video/rv_0.mp4` .. `video/rv_7.mp4`)
   for every review card: multi-shot Ken Burns pan/zoom with cinema cross-dissolves synced
   with the exact podcast audio slice (`clip_start..clip_end`), plus `-movflags +faststart`
   for <150ms mobile startup.
4. Generates RMS-calibrated synchronized subtitles (`video/rv_0.vtt` WebVTT + structured cue JSON)
   aligned to the actual spoken speech envelope of each clip.
5. Cleans stale previous-day video clips automatically so the GitHub Pages repo stays lean.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "img")
VIDEO_DIR = os.path.join(BASE_DIR, "video")
UA_HEADER = {"User-Agent": "N3AudioTutorVisualStudio/1.0 (https://github.com/tango13ucla/n3-audio-tutor)"}

# Reject logos, flags, diagrams, icons, maps, seals, charts, and non-photographic assets
BAD_MEDIA_RE = re.compile(
    r"(\.svg|\.gif|\.tif|\.tiff|\.ogg|\.oga|\.pdf|logo|icon|flag[_ -]|map[_ -]|"
    r"commons-logo|wikisource|wikinews|symbol|emblem|crest|seal|stamp|diagram|chart|"
    r"graph|reorganization|markets_of_|内閣印|紋章|市章|県章|社章|地図|路線図|系譜|"
    r"question_book|edit-clear|ambox|padlock|locator|blank|signature|autograph|"
    r"screenshot|cover_art|wordmark|in-game_logo|controller.*isolated)",
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
    "uchi11_s1_news_fallback": {"ja_wiki": ["三越", "銀座", "伊勢丹"], "wm_queries": ["Nihombashi Mitsukoshi Tokyo", "Ginza Tokyo street"]},
    "uchi11_s2a_oilshock_part1": {"ja_wiki": ["オイルショック", "スーパーマーケット"], "wm_queries": ["1973 oil crisis Japan", "Showa supermarket Japan"]},
    "uchi11_s2b_oilshock_part2": {"ja_wiki": ["ホンダ・シビック", "トヨタ・カローラ"], "wm_queries": ["1973 Honda Civic", "Toyota Corolla 1970s"]},
    "uchi11_s3a_tokyotower_part1": {"ja_wiki": ["東京タワー"], "wm_queries": ["Tokyo Tower construction", "Tokyo Tower daytime"]},
    "uchi11_s3b_tokyotower_part2": {"ja_wiki": ["東京タワー", "芝公園"], "wm_queries": ["Tokyo Tower night illuminated", "Tokyo Tower skyline"]},
    "uchi11_s4_world_global_health": {"ja_wiki": ["世界保健機関", "脳科学"], "wm_queries": ["Medical research laboratory microscope", "Brain MRI neuroscience"]},
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
    "uchi16_s1_news_fallback": {"ja_wiki": ["京都市", "清水寺", "祇園"], "wm_queries": ["Kyoto Gion crowded tourists", "Kyoto bus street"]},
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
    # ---- Vol.18 ----
    "uchi18_s1_news_fallback": {"ja_wiki": ["印章", "デジタル庁"], "wm_queries": ["Hanko Japanese seal stamp", "Japanese stamp hanko"]},
    "uchi18_s2a_yodogo_part1": {"ja_wiki": ["よど号ハイジャック事件", "ボーイング727"], "wm_queries": ["Japan Airlines Boeing 727", "Haneda Airport 1970"]},
    "uchi18_s2b_yodogo_part2": {"ja_wiki": ["よど号ハイジャック事件", "羽田空港"], "wm_queries": ["Boeing 727 Japan Airlines", "Tokyo Haneda Airport runway"]},
    "uchi18_s3a_hachiko_part1": {"ja_wiki": ["忠犬ハチ公", "渋谷駅"], "wm_queries": ["Hachiko statue Shibuya", "Hachiko Akita dog photo"]},
    "uchi18_s3b_hachiko_part2": {"ja_wiki": ["忠犬ハチ公", "東京大学"], "wm_queries": ["Hachiko and Ueno statue University of Tokyo", "Hachiko Shibuya Tokyo"]},
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
    "uchi20_s3a_kfc_part1": {"ja_wiki": ["日本ケンタッキー・フライド・チキン", "青山 (東京都港区)"], "wm_queries": ["KFC Japan store Colonel Sanders", "KFC Tokyo Japan"]},
    "uchi20_s3b_kfc_part2": {"ja_wiki": ["日本ケンタッキー・フライド・チキン", "クリスマス"], "wm_queries": ["Colonel Sanders Santa Japan", "Tokyo Christmas illumination"]},
    "uchi20_s4_world_undersea_cables": {"ja_wiki": ["海底ケーブル"], "wm_queries": ["Submarine communications cable ship", "Fiber optic cable ocean"]},
    # ---- Vol.21 ----
    "uchi21_s1_news_fallback": {"ja_wiki": ["ラジオ体操"], "wm_queries": ["Radio calisthenics Japan park", "Radio taiso Japan"]},
    "uchi21_s2a_koshien_part1": {"ja_wiki": ["阪神甲子園球場", "全国高等学校野球選手権大会"], "wm_queries": ["Hanshin Koshien Stadium", "Koshien high school baseball"]},
    "uchi21_s2b_koshien_part2": {"ja_wiki": ["阪神甲子園球場"], "wm_queries": ["Koshien stadium field dirt", "Japanese high school baseball"]},
    "uchi21_s3a_ichiro_part1": {"ja_wiki": ["イチロー"], "wm_queries": ["Ichiro Suzuki batting", "Ichiro Suzuki Mariners"]},
    "uchi21_s3b_ohtani_part2": {"ja_wiki": ["大谷翔平"], "wm_queries": ["Shohei Ohtani batting", "Shohei Ohtani pitching"]},
    "uchi21_s4_world_arctic_shipping": {"ja_wiki": ["北極海航路"], "wm_queries": ["Icebreaker ship Arctic sea route", "Container ship Japan port"]},
    # ---- Vol.22 ----
    "uchi22_s1_news_fallback": {"ja_wiki": ["NHK紅白歌合戦", "除夜の鐘", "年越し蕎麦"], "wm_queries": ["Toshikoshi soba Japan", "Joya no kane temple bell Japan"]},
    "uchi22_s2a_ise_sengu_part1": {"ja_wiki": ["伊勢神宮", "神宮式年遷宮"], "wm_queries": ["Ise Grand Shrine Naiku", "Ise Jingu wooden bridge"]},
    "uchi22_s2b_kongo_gumi_part2": {"ja_wiki": ["金剛組", "四天王寺"], "wm_queries": ["Shitenno-ji Temple Osaka", "Japanese wooden temple carpentry"]},
    "uchi22_s3a_naoshima_part1": {"ja_wiki": ["直島", "安藤忠雄"], "wm_queries": ["Naoshima Yellow Pumpkin Kusama", "Naoshima island Seto Inland Sea"]},
    "uchi22_s3b_naoshima_part2": {"ja_wiki": ["地中美術館", "直島"], "wm_queries": ["Chichu Art Museum Naoshima", "Benesse House Naoshima"]},
    "uchi22_s4_world_humanoid_robots": {"ja_wiki": ["ヒューマノイド", "産業用ロボット"], "wm_queries": ["Humanoid robot Japan ASIMO", "Industrial robot factory Japan"]},
}


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


def _probe_image_dims(path: str) -> tuple[int, int]:
    """Use ffprobe to verify a downloaded image is decodable and check its dimensions."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=6,
        ).decode("utf-8").strip()
        if "x" in out:
            w, h = out.splitlines()[0].split("x", 1)
            return int(w), int(h)
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
                # Normalize thumb.wikimedia.org -> upload.wikimedia.org if needed and request 960px thumb
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
    title = str(story_block.get("title") or "").strip()
    ja_focus = str(story_block.get("ja_focus") or "").strip()

    # Fallback: match any curated keyword or auto-search ja.wikipedia from Japanese/Kanji phrases
    ja_wiki: list[str] = []
    wm_queries: list[str] = []

    # Extract kanji noun clusters (2-6 chars) from ja_focus and short_tab
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
        w, h = _probe_image_dims(raw_path)
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


def _render_fallback_zen_still(dest_jpg: str, accent_hex: str = "2B5F49") -> None:
    """Offline safety net: render a warm subtle Kyoto paper/ink gradient 16:9 frame via ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=0x1d1c19:s=960x540:d=1",
            "-vf", "geq=r='min(255,29+14*sin(X/240)+8*cos(Y/180))':g='min(255,28+16*sin(X/260)+7*cos(Y/180))':b='min(255,25+12*sin(X/280)+6*cos(Y/200))'",
            "-frames:v", "1", "-q:v", "4", dest_jpg,
        ],
        check=False,
    )


def _render_chapter_poster(src_img: str, dest_jpg: str) -> bool:
    """Create a crisp 960x540 16:9 warm editorial documentary poster JPEG."""
    vf = (
        "scale=960:540:force_original_aspect_ratio=increase,"
        "crop=960:540:(iw-960)/2:(ih-540)/2,"
        "eq=saturation=0.95:contrast=1.04:brightness=-0.02,"
        "vignette=angle=PI/5"
    )
    res = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", src_img,
            "-vf", vf,
            "-frames:v", "1", "-q:v", "4", dest_jpg,
        ],
        check=False,
    )
    return res.returncode == 0 and os.path.exists(dest_jpg) and os.path.getsize(dest_jpg) > 4000


def _measure_speech_bounds(audio_path: str, total_dur: float) -> tuple[float, float]:
    """Detect actual speech onset & offset inside a clipped MP3 using 100ms RMS energy."""
    if not os.path.exists(audio_path) or total_dur <= 1.5:
        return 0.3, max(1.0, total_dur - 0.3)
    try:
        raw = subprocess.check_output(
            [
                "ffmpeg", "-v", "error", "-i", audio_path,
                "-ac", "1", "-ar", "4000", "-f", "f32le", "pipe:1",
            ],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        hop = 400  # 100ms
        n_floats = len(raw) // 4
        n_frames = n_floats // hop
        if n_frames < 10:
            return 0.3, max(1.0, total_dur - 0.3)
        rms: list[float] = []
        for fi in range(n_frames):
            chunk = struct.unpack_from(f"<{hop}f", raw, fi * hop * 4)
            s2 = sum(x * x for x in chunk) / hop
            rms.append(math.sqrt(s2))
        peak = max(rms) or 1.0
        thresh = peak * 0.08
        start_idx = 0
        for fi, val in enumerate(rms):
            if val >= thresh:
                start_idx = fi
                break
        end_idx = n_frames - 1
        for fi in range(n_frames - 1, -1, -1):
            if rms[fi] >= thresh:
                end_idx = fi
                break
        t0 = max(0.15, min(2.2, start_idx * 0.1))
        t1 = min(total_dur - 0.15, max(t0 + 2.5, (end_idx + 1) * 0.1))
        return round(t0, 2), round(t1, 2)
    except Exception:
        return 0.4, max(1.5, round(total_dur - 0.4, 2))


def _split_subtitle_phrases(text: str, max_chars: int = 26) -> list[str]:
    """Split a spoken host turn cleanly into readable cinema subtitle lines (never breaking kana runs)."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    clean = clean.replace("——", "，").replace("—", "，")
    if not clean:
        return []

    # First split on strong sentence punctuation, keeping punctuation attached
    raw_sents = [s.strip() for s in re.findall(r"[^。！？；]+[。！？；]?", clean) if s.strip()]
    chunks: list[str] = []
    for sent in raw_sents:
        if len(sent) <= max_chars + 4:
            chunks.append(sent)
            continue
        # Split long sentence on commas / colons / Japanese commas
        parts = [p.strip() for p in re.findall(r"[^，、：:,]+[，、：:,]?", sent) if p.strip()]
        buf = ""
        for p in parts:
            if not buf:
                buf = p
            elif len(buf) + len(p) <= max_chars + 3:
                buf += p
            else:
                chunks.append(buf.strip())
                buf = p
        if buf:
            chunks.append(buf.strip())

    # Merge tiny orphan trailing chunks (<7 chars) into neighbor
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < 7 and len(merged[-1]) + len(c) <= max_chars + 8:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)

    # Hard-wrap any remaining ultra-long clause cleanly outside kana tokens
    final_chunks: list[str] = []
    for c in merged:
        while len(c) > max_chars + 10:
            # Prefer space or punctuation near max_chars
            cut = max_chars
            for pos in range(max_chars, max(12, max_chars - 10), -1):
                if c[pos - 1] in " ，、：；！？。）)」』":
                    cut = pos
                    break
            final_chunks.append(c[:cut].strip())
            c = c[cut:].strip()
        if c:
            final_chunks.append(c)

    return final_chunks


def _build_timed_subtitles(
    full_text: str,
    speaker: str,
    clip_dur: float,
    speech_start: float,
    speech_end: float,
) -> list[dict[str, Any]]:
    phrases = _split_subtitle_phrases(full_text, max_chars=26)
    if not phrases:
        return []
    weights: list[float] = []
    for p in phrases:
        ja_n = len(re.findall(r"[ぁ-んァ-ヶー]", p))
        zh_n = len(re.findall(r"[\u4e00-\u9fff]", p))
        punc_n = len(re.findall(r"[，。！？；：、]", p))
        w = max(5.0, zh_n * 1.0 + ja_n * 1.25 + punc_n * 1.5 + max(0, len(p) - ja_n - zh_n) * 0.45)
        weights.append(w)
    tot_w = sum(weights) or 1.0
    span = max(2.0, speech_end - speech_start)
    cur = speech_start
    cues: list[dict[str, Any]] = []
    for idx, (p, w) in enumerate(zip(phrases, weights)):
        d = span * (w / tot_w)
        s = round(cur, 2)
        e = round(speech_end if idx == len(phrases) - 1 else min(clip_dur - 0.05, cur + d), 2)
        cur = e
        cues.append({
            "s": s,
            "e": max(s + 0.5, e),
            "spk": speaker if idx == 0 else "",
            "txt": p,
        })
    return cues


def _fmt_vtt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60.0
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _write_vtt(cues: list[dict[str, Any]], dest_vtt: str) -> None:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        prefix = f"{c['spk']}：" if c.get("spk") else ""
        lines.append(str(i))
        lines.append(f"{_fmt_vtt_ts(c['s'])} --> {_fmt_vtt_ts(c['e'])}")
        lines.append(f"{prefix}{c['txt']}")
        lines.append("")
    with open(dest_vtt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _render_ken_burns_video(
    shot_paths: list[str],
    audio_slice_path: str,
    clip_dur: float,
    dest_mp4: str,
    shot_rotation: int = 0,
) -> bool:
    """
    Build a smooth 24fps 640x360 H.264/AAC MP4 documentary clip from 1-3 real photos
    using gentle cinema Ken Burns motion + 0.55s xfade cross-dissolves + muxed podcast audio.
    """
    if not shot_paths:
        return False
    # Rotate shot order across cards within the same chapter for visual freshness
    shots = shot_paths[shot_rotation % len(shot_paths):] + shot_paths[:shot_rotation % len(shot_paths)]
    shots = shots[:3]
    n = len(shots)
    fps = 24
    fade = 0.55 if n > 1 else 0.0
    # Compute exact per-shot duration so total matches clip_dur after (n-1) overlaps
    shot_dur = (clip_dur + fade * (n - 1)) / n
    shot_frames = max(36, int(math.ceil(shot_dur * fps)) + 4)

    # 3 distinct gentle cinema camera motions (slow zoom-in, slow zoom-out, slow lateral pan)
    motions = [
        f"zoompan=z='min(1.14,1+0.00055*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={shot_frames}:s=640x360:fps={fps}",
        f"zoompan=z='1.12':x='(iw-iw/zoom)*min(1,on/{shot_frames})':y='ih/2-(ih/zoom/2)':d={shot_frames}:s=640x360:fps={fps}",
        f"zoompan=z='max(1.0,1.14-0.00055*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={shot_frames}:s=640x360:fps={fps}",
    ]

    inputs: list[str] = []
    for sp in shots:
        inputs.extend(["-i", sp])
    inputs.extend(["-i", audio_slice_path])
    audio_idx = n

    fc_parts: list[str] = []
    for i in range(n):
        mot = motions[(i + shot_rotation) % len(motions)]
        # Pre-scale to 1280x720 16:9 before zoompan for ultra-smooth sub-pixel pan/zoom
        fc_parts.append(
            f"[{i}:v]scale=1280:720:force_original_aspect_ratio=increase,"
            f"crop=1280:720:(iw-1280)/2:(ih-720)/2,setsar=1,"
            f"{mot},trim=duration={shot_dur:.3f},setpts=PTS-STARTPTS,"
            f"eq=saturation=0.95:contrast=1.04:brightness=-0.02,vignette=angle=PI/5,format=yuv420p[v{i}]"
        )

    if n == 1:
        v_out = "[v0]"
    else:
        prev = "v0"
        offset = shot_dur - fade
        for i in range(1, n):
            nxt = f"vx{i}"
            fc_parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={fade:.2f}:offset={offset:.3f}[{nxt}]")
            prev = nxt
            offset += shot_dur - fade
        v_out = f"[{prev}]"

    # Subtle 0.25s cinema fade-in at start & fade-out at tail
    fade_out_start = max(0.5, clip_dur - 0.35)
    fc_parts.append(f"{v_out}fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out_start:.2f}:d=0.35[vfinal]")
    filter_complex = ";".join(fc_parts)

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", f"{audio_idx}:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "26",
        "-profile:v", "main", "-level", "3.1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-ac", "1",
        "-t", f"{clip_dur:.2f}",
        "-movflags", "+faststart",
        dest_mp4,
    ]
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0 and os.path.exists(dest_mp4) and os.path.getsize(dest_mp4) > 20000


def build_episode_visuals(
    today_str: str,
    script_sig: str,
    story_blocks: list[dict[str, Any]],
    chapters_meta: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    speaking_prompts: list[dict[str, Any]],
    audio_mp3_path: str,
) -> dict[str, Any]:
    """
    Generate real documentary chapter posters (`img/ch_*.jpg`), per-review-card cut MP4 videos
    (`video/rv_*.mp4`), WebVTT subtitle tracks (`video/rv_*.vtt`), and structured synced subtitles.
    Mutates `chapters_meta`, `review_items`, and `speaking_prompts` in place and returns
    `{"artwork_url": ..., "story_arts": [...]}`.
    """
    if not shutil.which("ffmpeg"):
        print("[visual-studio] ffmpeg not found, skipping video rendering")
        return {}

    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    # Clean stale previous-day auto-generated posters & videos to keep repo lean
    for fn in os.listdir(VIDEO_DIR):
        if re.match(r"^rv_\d+\.(mp4|vtt)$", fn):
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

    ver_tag = f"{today_str}_{str(script_sig or 'v1')[:6]}"
    tmpdir = tempfile.mkdtemp(prefix="n3_vis_")
    used_hashes: set[str] = set()
    chapter_shots: dict[int, list[str]] = {}
    chapter_posters: dict[int, str] = {}
    story_arts: list[dict[str, Any]] = []

    try:
        # 1. Fetch authentic real photos & render crisp 16:9 poster for every chapter
        for blk in story_blocks:
            ch_idx = int(blk.get("chapter", 0))
            shots = _download_chapter_shots(blk, tmpdir, used_hashes, want=3)
            if not shots:
                fb_jpg = os.path.join(tmpdir, f"ch{ch_idx}_fallback.jpg")
                _render_fallback_zen_still(fb_jpg)
                shots = [fb_jpg]
            chapter_shots[ch_idx] = shots

            poster_file = os.path.join(IMG_DIR, f"ch_{ch_idx}.jpg")
            if _render_chapter_poster(shots[0], poster_file):
                rel_poster = f"./img/ch_{ch_idx}.jpg?v={ver_tag}"
                chapter_posters[ch_idx] = rel_poster
                for ch_m in chapters_meta:
                    if int(ch_m.get("idx", -1)) == ch_idx:
                        ch_m["img"] = rel_poster

        # 2. Cut real documentary MP4 video clip + synced subtitles for every review card
        chap_card_counter: dict[int, int] = {}
        chap_first_video: dict[int, tuple[str, str]] = {}

        for rv_idx, item in enumerate(review_items):
            ch_idx = int(item.get("chapter_idx", 0))
            rot = chap_card_counter.get(ch_idx, 0)
            chap_card_counter[ch_idx] = rot + 1

            c_start = float(item.get("clip_start") or 0.0)
            c_end = float(item.get("clip_end") or (c_start + 16.0))
            clip_dur = max(6.0, min(26.0, round(c_end - c_start, 2)))

            # Always attach chapter poster
            poster_rel = chapter_posters.get(ch_idx, "")
            if poster_rel:
                item["img"] = poster_rel

            if not audio_mp3_path or not os.path.exists(audio_mp3_path):
                continue

            slice_mp3 = os.path.join(tmpdir, f"rv_{rv_idx}.mp3")
            fade_out_st = max(0.5, clip_dur - 0.25)
            cut_res = subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{c_start:.2f}", "-t", f"{clip_dur:.2f}",
                    "-i", audio_mp3_path,
                    "-af", f"afade=t=in:st=0:d=0.14,afade=t=out:st={fade_out_st:.2f}:d=0.25",
                    "-c:a", "libmp3lame", "-b:a", "96k",
                    slice_mp3,
                ],
                check=False,
            )
            if cut_res.returncode != 0 or not os.path.exists(slice_mp3):
                continue

            # Calibrate speech onset/offset on the real extracted slice for crisp subtitle sync
            sp_start, sp_end = _measure_speech_bounds(slice_mp3, clip_dur)
            sub_text = str(item.get("full_context") or item.get("context_line") or item.get("ja_example") or "").strip()
            speaker = str(item.get("speaker") or "文道").strip()
            cues = _build_timed_subtitles(sub_text, speaker, clip_dur, sp_start, sp_end)

            dest_mp4 = os.path.join(VIDEO_DIR, f"rv_{rv_idx}.mp4")
            dest_vtt = os.path.join(VIDEO_DIR, f"rv_{rv_idx}.vtt")
            shots = chapter_shots.get(ch_idx) or []
            if _render_ken_burns_video(shots, slice_mp3, clip_dur, dest_mp4, shot_rotation=rot):
                _write_vtt(cues, dest_vtt)
                vid_rel = f"./video/rv_{rv_idx}.mp4?v={ver_tag}"
                vtt_rel = f"./video/rv_{rv_idx}.vtt?v={ver_tag}"
                item["video_url"] = vid_rel
                item["vtt_url"] = vtt_rel
                item["clip_dur"] = clip_dur
                item["subtitles"] = cues
                if ch_idx not in chap_first_video:
                    chap_first_video[ch_idx] = (vid_rel, vtt_rel)

        # 3. Attach posters to speaking prompts
        for sp in speaking_prompts:
            ch_idx = int(sp.get("chapter_idx", 0))
            if chapter_posters.get(ch_idx):
                sp["img"] = chapter_posters[ch_idx]

        # 4. Build `story_arts` gallery (for main player art, lock-screen, completion reel & cinema modal)
        for blk in story_blocks:
            ch_idx = int(blk.get("chapter", 0))
            poster_rel = chapter_posters.get(ch_idx, "")
            if not poster_rel:
                continue
            vid_rel, vtt_rel = chap_first_video.get(ch_idx, ("", ""))
            short_tab = str(blk.get("short_tab") or f"第{ch_idx + 1}章").strip()
            raw_title = str(blk.get("title") or short_tab).strip()
            art_entry: dict[str, Any] = {
                "chapters": [ch_idx],
                "img": poster_rel,
                "title": short_tab,
                "subtitle": raw_title,
            }
            if vid_rel:
                art_entry["video_url"] = vid_rel
                art_entry["vtt_url"] = vtt_rel
            story_arts.append(art_entry)

        artwork_url = chapter_posters.get(0) or (story_arts[0]["img"] if story_arts else "")
        total_vids = sum(1 for it in review_items if it.get("video_url"))
        print(
            f"[visual-studio] Built {len(chapter_posters)} chapter posters + "
            f"{total_vids}/{len(review_items)} synced MP4+VTT review clips for {today_str}"
        )
        return {
            "artwork_url": artwork_url,
            "story_arts": story_arts,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
