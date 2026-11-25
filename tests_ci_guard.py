#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Fast CI & Pre-Push Guard for n3-audio-tutor (zero external dependencies).
Guards 6 critical invariants before EVERY publish:
  1. Static AST syntax & undefined-name scan across ALL Python files.
  2. All-event-types practice_log replay (LK:, HES:, SPK:, RV:过/重学/再过/快过存疑, GA-, VC-, FLASH-, quiz, GROK-).
  3. Frontend <-> Backend choice contract sync (scans build_html.py against run_brain_algorithm.py & auto_author_daily_content.py).
  4. Dynamic vocab card stress test across ALL 236 IMMERSION_VOCAB_BANK words + VOCAB_CARDS + CORE_N3_KANA_VOCAB + unseen synthetic words (Self-test 4 invariants).
  5. Speaking prompt templates + fallback stress test (Self-test 9 invariants).
  6. Workflow radio version-check alignment across all 3 GitHub Actions workflows.
"""
from __future__ import annotations

import ast
import builtins
import json
import pathlib
import re
import sys
import tempfile

BASE_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

BUILTIN_NAMES = set(dir(builtins)) | {
    "__name__", "__file__", "__doc__", "__package__", "__spec__",
    "__builtins__", "__annotations__", "__loader__", "__cached__",
}


def _collect_targets(node: ast.AST, out: set[str]) -> None:
    if isinstance(node, ast.Name):
        out.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            _collect_targets(elt, out)
    elif isinstance(node, ast.Starred):
        _collect_targets(node.value, out)
    elif isinstance(node, ast.NamedExpr):
        _collect_targets(node.target, out)


def _check_scope_undefined(tree: ast.AST, filename: str) -> list[str]:
    """Conservative AST undefined-name detector across module/function/comprehension scopes."""
    errors: list[str] = []

    def gather_bound(stmts: list[ast.stmt]) -> set[str]:
        bound: set[str] = set()
        for st in stmts:
            for node in ast.walk(st):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    bound.add(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        if alias.name != "*":
                            bound.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        _collect_targets(t, bound)
                elif isinstance(node, ast.AnnAssign):
                    _collect_targets(node.target, bound)
                elif isinstance(node, ast.AugAssign):
                    _collect_targets(node.target, bound)
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    _collect_targets(node.target, bound)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        if item.optional_vars is not None:
                            _collect_targets(item.optional_vars, bound)
                elif isinstance(node, ast.ExceptHandler) and node.name:
                    bound.add(node.name)
                elif isinstance(node, ast.NamedExpr):
                    _collect_targets(node.target, bound)
                elif isinstance(node, (ast.Global, ast.Nonlocal)):
                    bound.update(node.names)
        return bound

    def has_star_import(node: ast.AST) -> bool:
        for n in ast.walk(node):
            if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
                return True
        return False

    if has_star_import(tree):
        return errors

    mod_bound = BUILTIN_NAMES | gather_bound(getattr(tree, "body", []))

    def visit_node(node: ast.AST, env: set[str], in_annotation: bool = False) -> None:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if not in_annotation and node.id not in env:
                errors.append(f"{filename}:{node.lineno}: undefined name '{node.id}'")
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                visit_node(dec, env)
            for d in node.args.defaults + [x for x in node.args.kw_defaults if x is not None]:
                visit_node(d, env)
            fn_env = set(env)
            for a in (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            ):
                fn_env.add(a.arg)
            fn_env |= gather_bound(node.body)
            for st in node.body:
                visit_node(st, fn_env)
            return

        if isinstance(node, ast.Lambda):
            for d in node.args.defaults + [x for x in node.args.kw_defaults if x is not None]:
                visit_node(d, env)
            lam_env = set(env)
            for a in (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
                + ([node.args.vararg] if node.args.vararg else [])
                + ([node.args.kwarg] if node.args.kwarg else [])
            ):
                lam_env.add(a.arg)
            visit_node(node.body, lam_env)
            return

        if isinstance(node, ast.ClassDef):
            for dec in node.decorator_list:
                visit_node(dec, env)
            for b in node.bases:
                visit_node(b, env)
            for kw in node.keywords:
                visit_node(kw.value, env)
            cls_env = set(env) | gather_bound(node.body)
            for st in node.body:
                visit_node(st, cls_env)
            return

        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            comp_env = set(env)
            for gen in node.generators:
                visit_node(gen.iter, comp_env)
                _collect_targets(gen.target, comp_env)
                for cond in gen.ifs:
                    visit_node(cond, comp_env)
            if isinstance(node, ast.DictComp):
                visit_node(node.key, comp_env)
                visit_node(node.value, comp_env)
            else:
                visit_node(node.elt, comp_env)
            return

        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                visit_node(node.value, env)
            return

        for child in ast.iter_child_nodes(node):
            visit_node(child, env, in_annotation=in_annotation)

    for st in getattr(tree, "body", []):
        visit_node(st, mod_bound)
    return errors


def test_all_python_files_syntax_and_names() -> None:
    py_files = sorted(BASE_DIR.rglob("*.py"))
    all_errs: list[str] = []
    for p in py_files:
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError as e:
            all_errs.append(f"{p.name}: SyntaxError {e}")
            continue
        all_errs.extend(_check_scope_undefined(tree, p.name))
    assert not all_errs, "Static undefined-name/syntax errors:\n" + "\n".join(all_errs)
    print(f"[PASS 1/10] Static AST syntax & undefined-name check ({len(py_files)} Python files)")


def test_apply_practice_logs_all_event_types() -> None:
    import run_brain_algorithm as rba
    import auto_author_daily_content as aadc

    synthetic_records = [
        {"ts": "2026-11-24T06:00:01Z", "id": "LK:辞書", "point": "〜につれて", "choice": "辞書", "correct": "false"},
        {"ts": "2026-11-24T06:00:02Z", "id": "HES:N3-G1", "point": "〜につれて", "choice": "犹豫过关", "correct": "true"},
        {"ts": "2026-11-24T06:00:03Z", "id": "SPK:RV-1", "point": "〜につれて", "choice": "开口:自然达标", "correct": "true"},
        {"ts": "2026-11-24T06:00:04Z", "id": "SPK:W-辞書", "point": "辞書", "choice": "试读:长音偏短", "correct": "false"},
        {"ts": "2026-11-24T06:00:05Z", "id": "SPK:RV-2", "point": "〜べきではない", "choice": "开口:再练句型", "correct": False},
        {"ts": "2026-11-24T06:00:06Z", "id": "RV:1", "point": "〜につれて", "choice": "听后复盘:过", "correct": "true"},
        {"ts": "2026-11-24T06:00:07Z", "id": "RV:2", "point": "〜べきではない", "choice": "听后复盘:重学", "correct": "false"},
        {"ts": "2026-11-24T06:00:08Z", "id": "RV:2b", "point": "象徴", "choice": "听后复盘:再过", "correct": "false"},
        {"ts": "2026-11-24T06:00:09Z", "id": "RV:3", "point": "〜に関して", "choice": "听后复盘:快过存疑", "correct": "true"},
        {"ts": "2026-11-24T06:00:10Z", "id": "GA-G-001", "point": "〜につれて", "choice": "盘点:本能", "correct": "true"},
        {"ts": "2026-11-24T06:00:11Z", "id": "GA-G-116a", "point": "尊敬語", "choice": "盘点:陌生", "correct": "false"},
        {"ts": "2026-11-24T06:00:12Z", "id": "VC-辞書", "point": "辞書", "choice": "记词:没记住", "correct": "false"},
        {"ts": "2026-11-24T06:00:13Z", "id": "FLASH-暖簾", "point": "暖簾", "choice": "闪卡:顺过", "correct": "true"},
        {"ts": "2026-11-24T06:00:14Z", "id": "N3-G1", "point": "〜に関して", "choice": "に関して", "correct": "true", "ask_again": "false"},
        {"ts": "2026-11-24T06:00:15Z", "id": "N3-G2", "point": "〜べきではない", "choice": "不确定", "correct": "false", "ask_again": "true"},
        {"ts": "2026-11-24T06:00:16Z", "id": "GROK-1", "point": "〜につれて", "choice": "Grok:还是要考", "correct": "true", "ask_again": "true", "source": "grok"},
    ]

    with tempfile.TemporaryDirectory() as td:
        import immersion_vocab_engine as ive

        log_file = pathlib.Path(td) / "practice_log.jsonl"
        snap_file = pathlib.Path(td) / "cloud_state_snapshot.json"
        ledger_file = pathlib.Path(td) / "podcast_vocab_ledger.json"
        log_file.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in synthetic_records) + "\n", encoding="utf-8")
        snap_file.write_text("{}", encoding="utf-8")
        orig_ledger = getattr(ive, "LEDGER_PATH", None)
        if orig_ledger and pathlib.Path(orig_ledger).exists():
            ledger_file.write_text(pathlib.Path(orig_ledger).read_text(encoding="utf-8"), encoding="utf-8")

        orig_rba_log, orig_rba_snap = rba.LOG_PATH, rba.SNAPSHOT_PATH
        orig_aadc_log, orig_aadc_snap = aadc.LOG_PATH, aadc.SNAP_PATH
        try:
            rba.LOG_PATH = str(log_file)
            rba.SNAPSHOT_PATH = str(snap_file)
            aadc.LOG_PATH = log_file
            aadc.SNAP_PATH = snap_file
            if orig_ledger is not None:
                ive.LEDGER_PATH = str(ledger_file)

            state = {
                "grammar_points": [
                    {"id": "G-001", "name": "〜につれて", "status": "gray", "streak": 0},
                    {"id": "G-002", "name": "〜べきではない", "status": "yellow", "streak": 2},
                    {"id": "G-003", "name": "〜に関して", "status": "gray", "streak": 0},
                    {"id": "G-116", "name": "尊敬語", "status": "gray", "streak": 0},
                ],
                "henkei_points": [
                    {"id": "K-001", "name": "いらっしゃる", "status": "gray", "streak": 0},
                ],
                "listening_points": [],
                "vocab_tracked": [
                    {"word": "辞書", "status": "gray", "streak": 0},
                ],
            }
            rba.apply_practice_logs(state, "20261124")
            spk = state.get("speaking_practice") or {}
            assert spk.get("total_reps") == 3, f"Expected 3 spoken reps, got {spk}"
            assert "辞書" in (spk.get("slips") or {}), f"Expected 辞書 slip recorded, got {spk}"
            assert "〜べきではない" in (spk.get("slips") or {}), f"Expected 〜べきではない slip recorded, got {spk}"
            assert "〜につれて" not in (spk.get("slips") or {}), f"Passed SPK should not be marked slip: {spk}"
            assert "象徴" in (state.get("radio_relearn_queue") or {}), "Expected 听后复盘:再过 to queue 象徴 for relearn"
            assert "〜べきではない" in (state.get("radio_relearn_queue") or {}), "Expected 听后复盘:重学 to queue 〜べきではない"
            assert "辞書" in (state.get("word_lookups") or {}), "Expected lookup recorded"

            _, ever_seen, missed, missed_v, lookups = aadc.collect_study_history(cutoff_study_day="2026-11-24")
            for bad_prefix in ("SPK:", "RV:", "HES:", "LK:", "GA-", "VC-", "GROK-"):
                assert not any(c.startswith(bad_prefix) for c in ever_seen), f"ever_seen polluted with {bad_prefix}: {ever_seen}"
            assert "N3-G1" in ever_seen and "N3-G2" in ever_seen
            all_missed = [x for vals in missed.values() for x in vals]
            assert "象徴" in all_missed, f"Expected 听后复盘:再过 (象徴) in missed_by_day: {missed}"
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_rba_log, orig_rba_snap
            aadc.LOG_PATH, aadc.SNAP_PATH = orig_aadc_log, orig_aadc_snap
            if orig_ledger is not None:
                ive.LEDGER_PATH = orig_ledger
    print("[PASS 2/10] apply_practice_logs & collect_study_history all-event-types test")


def test_frontend_backend_choice_contract() -> None:
    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    rba_src = (BASE_DIR / "run_brain_algorithm.py").read_text(encoding="utf-8")
    aadc_src = (BASE_DIR / "auto_author_daily_content.py").read_text(encoding="utf-8")

    # Every radio review label emitted by build_html.py MUST be explicitly handled by run_brain_algorithm.py
    rv_labels = set(re.findall(r'"(听后复盘:[^"]+)"', bh_src))
    assert rv_labels, "No 听后复盘:* labels found in build_html.py"
    for lbl in sorted(rv_labels):
        assert lbl in rba_src, f"Frontend emits '{lbl}' but run_brain_algorithm.py does NOT handle it!"

    # Every grammar audit verdict emitted by build_html.py MUST be handled by run_brain_algorithm.py
    ga_labels = set(re.findall(r'"(盘点:[^"]+)"', bh_src))
    assert ga_labels, "No 盘点:* labels found in build_html.py"
    for lbl in sorted(ga_labels):
        assert lbl in rba_src, f"Frontend emits '{lbl}' but run_brain_algorithm.py does NOT handle it!"

    # Relearn labels must also be handled in auto_author_daily_content.py
    for relbl in ("听后复盘:再过", "听后复盘:重学"):
        assert relbl in aadc_src, f"auto_author_daily_content.py missing '{relbl}'"
    print(f"[PASS 3/10] Frontend<->Backend choice contract sync ({len(rv_labels)} RV + {len(ga_labels)} GA labels)")


def test_dynamic_vocab_cards_self_test4_invariants() -> None:
    import vocab_cards as vc
    import immersion_vocab_engine as ive
    from adaptive_bank import CORE_N3_KANA_VOCAB

    candidates: list[str] = list(vc.VOCAB_CARDS.keys())
    for row in getattr(ive, "IMMERSION_VOCAB_BANK", []):
        if row.get("kanji"):
            candidates.append(str(row["kanji"]))
    for kw, _, _ in CORE_N3_KANA_VOCAB:
        candidates.append(str(kw))
    # Also test completely unseen synthetic kanji & kana words!
    candidates.extend(["象徴", "緊急事態", "再配達", "もやもや"])

    checked = set()
    for w in candidates:
        if not w or w in checked:
            continue
        checked.add(w)
        spec = vc.build_dynamic_vocab_card(w, {})
        aspec = vc.build_vocab_audio_spec(spec)
        mn = str(spec.get("mnemonic") or "").strip()
        hs = str(aspec.get("hook_spoken") or "").strip()
        ch = str(spec.get("chunk_ja") or "").strip()
        assert mn, f"Empty mnemonic for vocab card '{w}'"
        assert "—" not in mn, f"Em dash in mnemonic for '{w}': {mn}"
        assert hs, f"Empty hook_spoken for vocab card '{w}'"
        assert "—" not in hs, f"Em dash in hook_spoken for '{w}': {hs}"
        assert len(ch) <= 10, f"chunk_ja too long ({len(ch)}>10) for '{w}': {ch}"
    print(f"[PASS 4/10] Dynamic vocab cards Self-test 4 invariants ({len(checked)} words incl. all 236 immersion words)")


def test_speaking_prompts_self_test9_invariants() -> None:
    import radio_review_builder as rrb

    # Check all curated templates
    for k, sp in rrb._SPEAKING_TEMPLATES.items():
        ps = str(sp.get("prompt_short") or "")
        mj = str(sp.get("model_ja") or "")
        ts = sp.get("target_stems") or []
        blob = ps + str(sp.get("prompt_ja") or "") + str(sp.get("prompt_zh") or "") + mj + str(sp.get("coaching_tip") or "")
        assert ps and len(ps) <= 14, f"Bad template prompt_short for {k}: {ps}"
        assert mj and len(mj) <= 26, f"Bad template model_ja for {k}: {mj}"
        assert ts, f"Empty target_stems for {k}"
        assert "—" not in blob, f"Em dash in template {k}"

    # Also test tpl=None fallback with very long grammar title & 1-char particle!
    mock_items = [
        {"id": "R1", "kind": "grammar", "point_id": "N3-G999", "key": "〜ということになっている", "title": "〜ということになっている", "zh": "按规定应该这样做而且不能随便改", "ja_example": "会議では必ず事前に資料を共有するということになっている。", "chapter_idx": 0},
        {"id": "R2", "kind": "grammar", "point_id": "N3-G998", "key": "〜ば", "title": "〜ば", "zh": "只要……就——假定条件", "ja_example": "", "chapter_idx": 1},
    ]
    built = rrb.build_episode_speaking_prompts([], mock_items, max_prompts=2)
    assert len(built) == 2
    for sp in built:
        assert sp["prompt_short"] and len(sp["prompt_short"]) <= 14, f"Fallback prompt_short violated <=14: {sp}"
        assert sp["model_ja"] and len(sp["model_ja"]) <= 26, f"Fallback model_ja violated <=26: {sp}"
        assert sp["target_stems"], f"Fallback target_stems empty: {sp}"
        blob = sp["prompt_short"] + sp["prompt_ja"] + sp["prompt_zh"] + sp["model_ja"] + sp["coaching_tip"]
        assert "—" not in blob, f"Fallback contains em dash: {sp}"
    print(f"[PASS 5/10] Speaking prompts Self-test 9 invariants ({len(rrb._SPEAKING_TEMPLATES)} templates + fallback stress)")


def test_workflows_radio_version_alignment() -> None:
    gen_src = (BASE_DIR / "generate_daily_radio.py").read_text(encoding="utf-8")
    gen_vers = [int(m) for m in re.findall(r'radio_ver_tag\s*=\s*"v(\d+)_', gen_src)]
    assert gen_vers, "Could not find radio_ver_tag in generate_daily_radio.py"
    max_gen_ver = max(gen_vers)

    wf_dir = BASE_DIR / ".github" / "workflows"
    wf_files = sorted(wf_dir.glob("*.yml"))
    assert len(wf_files) >= 3, f"Expected >=3 workflow files, got {wf_files}"
    for wf in wf_files:
        txt = wf.read_text(encoding="utf-8")
        assert "radio_ver != expected_ver" not in txt, (
            f"{wf.name} still uses fragile exact-inequality `radio_ver != expected_ver`; "
            f"use numeric `cur_ver_num < expected_ver_num`!"
        )
        m = re.search(r"expected_ver_num\s*=\s*(\d+)", txt)
        assert m, f"{wf.name} missing expected_ver_num"
        wf_ver = int(m.group(1))
        assert wf_ver <= max_gen_ver, f"{wf.name} expects v{wf_ver} > generate_daily_radio.py max v{max_gen_ver}"
    print(f"[PASS 6/10] Workflow radio version guard aligned (v{max_gen_ver} across {len(wf_files)} workflows)")


def test_workflows_stage_video_and_img_assets() -> None:
    wf_dir = BASE_DIR / ".github" / "workflows"
    wf_files = sorted(wf_dir.glob("*.yml"))
    for wf in wf_files:
        txt = wf.read_text(encoding="utf-8")
        # Every git-push staging block must preserve video/ and img/ across git reset --hard origin/main
        assert "STAGE_DIR/video" in txt or '"$STAGE_DIR/video"' in txt, (
            f"{wf.name} does not stage video/ into STAGE_DIR before git reset --hard!"
        )
        assert "STAGE_DIR/img" in txt or '"$STAGE_DIR/img"' in txt, (
            f"{wf.name} does not stage img/ into STAGE_DIR before git reset --hard!"
        )
        assert "git add -A video/" in txt or "video/ img/" in txt, (
            f"{wf.name} does not git add video/ and img/ in commit step!"
        )
    print(f"[PASS 7/10] Workflow video/ & img/ staging guard verified across {len(wf_files)} workflows")


def test_async_loop_safety_and_live_visual_studio_invocation() -> None:
    """
    Gate 8: Permanently prevent `RuntimeError: asyncio.run() cannot be called from a running event loop`.
    1) Static AST audit: forbid unguarded `asyncio.run(...)` inside any function definition.
    2) Live runtime test: invoke BOTH `await rvs.build_episode_visuals_async(...)` AND sync
       `rvs.build_episode_visuals(...)` from INSIDE an active `asyncio` event loop!
    """
    import asyncio
    import radio_visual_studio as rvs

    # 1. Static AST audit across ALL Python files in the repo
    violations: list[str] = []
    for p in sorted(BASE_DIR.rglob("*.py")):
        if p.name == "tests_ci_guard.py":
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                src_seg = ast.unparse(node)
                has_asyncio_run = False
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "asyncio"
                        and sub.func.attr == "run"
                    ):
                        has_asyncio_run = True
                if has_asyncio_run and "get_running_loop" not in src_seg:
                    violations.append(f"{p.name}:{node.lineno} def {node.name}() calls unguarded asyncio.run()")
    assert not violations, "Unguarded asyncio.run() inside functions:\n" + "\n".join(violations)

    # 2. Live runtime test INSIDE a running asyncio event loop (with isolated temp dirs + lightweight mocks)
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        orig_img, orig_vid, orig_aud = rvs.IMG_DIR, rvs.VIDEO_DIR, rvs.AUDIO_DIR
        orig_find = rvs._find_ffmpeg
        orig_dl = rvs._download_chapter_shots
        orig_fb = rvs._render_fallback_zen_still
        orig_poster = rvs._render_chapter_poster
        orig_tts = rvs._edge_tts_to_mp3
        orig_build_vid = rvs._build_jp_documentary_video

        try:
            rvs.IMG_DIR = str(td_path / "img")
            rvs.VIDEO_DIR = str(td_path / "video")
            rvs.AUDIO_DIR = str(td_path / "audio")
            rvs._find_ffmpeg = lambda: "/usr/bin/true"
            rvs._download_chapter_shots = lambda blk, work_dir, used_hashes, ffmpeg_bin="ffmpeg", want=3: []

            def _fake_fb(dest_jpg: str, ffmpeg_bin: str = "ffmpeg") -> None:
                pathlib.Path(dest_jpg).write_bytes(b"FAKEJPG" * 200)

            def _fake_poster(src_img: str, dest_jpg: str, ffmpeg_bin: str = "ffmpeg") -> bool:
                pathlib.Path(dest_jpg).write_bytes(b"FAKEPOSTER" * 600)
                return True

            async def _fake_tts(text: str, voice: str, rate: str, dest_mp3: str) -> bool:
                pathlib.Path(dest_mp3).write_bytes(b"ID3" + b"\x00" * 1200)
                return True

            async def _fake_build_vid(**kwargs):
                script = kwargs["script"]
                cues = [
                    {"s": float(i * 4), "e": float(i * 4 + 3.5), "v": ln["v"], "ch": ln["ch"], "ja": ln["ja"], "zh": ln["zh"], "hits": []}
                    for i, ln in enumerate(script["lines"])
                ]
                we = rvs._build_video_word_entries(kwargs["target_words"])
                all_ja = "\n".join(c["ja"] for c in cues)
                hits = [{"word": w["word"], "kana": w["kana"], "zh": w["zh"], "source": w["source"], "hits": 1, "first_sec": 1.0, "times": [1.0]} for w in we if w["word"] in all_ja]
                return {
                    "title_ja": script["title_ja"],
                    "title_zh": script["title_zh"],
                    "video_url": "./video/daily_jp_story.mp4?v=test",
                    "vtt_url": "./video/daily_jp_story.vtt?v=test",
                    "poster_url": "./img/ch_0.jpg?v=test",
                    "duration_sec": 60.0,
                    "duration_label": "01:00",
                    "shot_count": 6,
                    "target_words": hits[:12],
                    "target_grammar": [],
                    "cues": cues,
                }

            rvs._render_fallback_zen_still = _fake_fb
            rvs._render_chapter_poster = _fake_poster
            rvs._edge_tts_to_mp3 = _fake_tts
            rvs._build_jp_documentary_video = _fake_build_vid

            mock_blocks = [
                {"id": "uchi11_s1_news_fallback", "chapter": 0, "short_tab": "百年百货", "title": "百年百货", "ja_focus": "昔は週末ごとに百貨店へ行ったものだ。"},
                {"id": "uchi11_s2a_oilshock_part1", "chapter": 1, "short_tab": "卫生纸骚动", "title": "卫生纸骚动", "ja_focus": "突然オイルショックの危機が起きた。"},
            ]
            mock_chaps = [{"idx": 0, "title": "百年百货"}, {"idx": 1, "title": "卫生纸骚动"}]
            mock_rev = [{"id": "R1", "kind": "vocab", "title": "象徴", "kana": "しょうちょう", "zh": "象征", "chapter_idx": 0}]

            async def _inside_running_loop() -> None:
                # Test A: native async call (what generate_daily_radio.py uses)
                spk_a = [
                    {"id": "SPK-1", "chapter_idx": 0, "model_ja": "よく考えたうえで決めます。"},
                    {"id": "SPK-2", "chapter_idx": 1, "model_ja": "少しずつ話せるようになった。"},
                ]
                out_a = await rvs.build_episode_visuals_async(
                    today_str="2026-11-25",
                    script_sig="abcdef1234",
                    story_blocks=mock_blocks,
                    chapters_meta=mock_chaps,
                    review_items=mock_rev,
                    speaking_prompts=spk_a,
                    audio_mp3_path="",
                    imm_vocab_report={},
                )
                assert all(sp.get("model_audio") for sp in spk_a), f"Async call missing model_audio: {spk_a}"
                assert out_a.get("jp_video") and len(out_a["jp_video"]["cues"]) >= 10, f"Async call bad jp_video: {out_a}"
                assert len(out_a["jp_video"]["target_words"]) >= 8, f"Async call <8 target_words: {out_a['jp_video']['target_words']}"

                # Test B: even legacy sync wrapper called inside a running loop must NEVER raise RuntimeError!
                spk_b = [
                    {"id": "SPK-1", "chapter_idx": 0, "model_ja": "よく考えたうえで決めます。"},
                    {"id": "SPK-2", "chapter_idx": 1, "model_ja": "少しずつ話せるようになった。"},
                ]
                out_b = rvs.build_episode_visuals(
                    today_str="2026-11-25",
                    script_sig="abcdef1234",
                    story_blocks=mock_blocks,
                    chapters_meta=mock_chaps,
                    review_items=mock_rev,
                    speaking_prompts=spk_b,
                    audio_mp3_path="",
                    imm_vocab_report={},
                )
                assert all(sp.get("model_audio") for sp in spk_b), f"Sync-in-loop missing model_audio: {spk_b}"
                assert out_b.get("jp_video") and len(out_b["jp_video"]["target_words"]) >= 8

            asyncio.run(_inside_running_loop())
        finally:
            rvs.IMG_DIR, rvs.VIDEO_DIR, rvs.AUDIO_DIR = orig_img, orig_vid, orig_aud
            rvs._find_ffmpeg = orig_find
            rvs._download_chapter_shots = orig_dl
            rvs._render_fallback_zen_still = orig_fb
            rvs._render_chapter_poster = orig_poster
            rvs._edge_tts_to_mp3 = orig_tts
            rvs._build_jp_documentary_video = orig_build_vid
    print("[PASS 8/10] Static & live-event-loop async safety guard (zero nested asyncio.run crashes)")


def test_all_future_volumes_jp_video_invariants() -> None:
    """
    Gate 9: Verify EVERY queued future episode volume (Vol.10..Vol.22 + synthetic + stingy 4-word LLM)
    strictly satisfies Self-test 13 invariants (>=10 Japanese cues, >=8 matched target_words, 0 em dashes).
    """
    import radio_visual_studio as rvs
    from radio_dialogue_bank import SALON_STORIES

    by_vol: dict[str, list[dict]] = {}
    for st in SALON_STORIES:
        sid = str(st.get("id") or "")
        m = re.match(r"^(uchi\d+)_", sid)
        if m:
            by_vol.setdefault(m.group(1), []).append(st)

    assert len(by_vol) >= 12, f"Expected >=12 uchi volumes in SALON_STORIES, got {sorted(by_vol.keys())}"

    target_words = rvs._collect_daily_target_words({}, [])
    word_entries = rvs._build_video_word_entries(target_words)
    checked_vols = 0

    for vol_key, stories in sorted(by_vol.items()):
        blocks = [
            {
                "id": s.get("id", ""),
                "chapter": idx,
                "short_tab": s.get("short_tab", f"第{idx+1}章"),
                "title": s.get("title", ""),
                "ja_focus": s.get("ja_focus", ""),
            }
            for idx, s in enumerate(stories[:6])
        ]
        # Test deterministic offline script path (what runs whenever a volume has no curated script & no LLM)
        det = rvs._ensure_script_meets_word_and_cue_floor(
            rvs._build_deterministic_jp_video_script(blocks, target_words),
            blocks,
            target_words,
        )
        lines = det.get("lines") or []
        assert 10 <= len(lines) <= 18, f"{vol_key}: expected 10..18 cues, got {len(lines)}"
        blob = det["title_ja"] + det["title_zh"] + "".join(ln["ja"] + ln["zh"] for ln in lines)
        assert "—" not in blob, f"{vol_key}: em dash leaked in JP video script"
        for ln in lines:
            assert len(re.findall(r"[ぁ-んァ-ヶー]", ln["ja"])) >= 4, f"{vol_key}: non-JP line {ln}"
        all_ja = "\n".join(ln["ja"] for ln in lines)
        hits = [we["word"] for we in word_entries if we["word"] in all_ja]
        assert len(hits) >= 8, f"{vol_key}: only {len(hits)} matched target words (<8 -> Self-test 13 would crash!): {hits}"
        checked_vols += 1

    # Also test a deliberately stingy LLM output with only 3 matched words & 10 short lines
    stingy_llm = {
        "title_ja": "テスト物語",
        "title_zh": "测试故事——含破折号",
        "lines": [
            {"ch": 0, "v": "M", "ja": "日本の歴史を振り返ると、象徴と予算と研究が見えてきます。", "zh": "回顾日本历史——可以看到这些词。"}
            for _ in range(10)
        ],
    }
    healed = rvs._ensure_script_meets_word_and_cue_floor(stingy_llm, [{"chapter": 0}], target_words)
    assert "—" not in (healed["title_zh"] + "".join(ln["zh"] for ln in healed["lines"]))
    healed_ja = "\n".join(ln["ja"] for ln in healed["lines"])
    healed_hits = [we["word"] for we in word_entries if we["word"] in healed_ja]
    assert len(healed_hits) >= 8, f"Stingy LLM heal failed (<8 words): {healed_hits}"
    print(f"[PASS 9/10] All {checked_vols} future volumes + stingy-LLM JP video Self-test 13 invariants (>=10 cues, >=8 words)")


def test_generate_daily_radio_async_and_reuse_contract() -> None:
    """Gate 10: Verify generate_daily_radio.py natively awaits visual studio & preserves speaking model_audio on reuse."""
    src = (BASE_DIR / "generate_daily_radio.py").read_text(encoding="utf-8")
    assert "await rvs.build_episode_visuals_async(" in src, (
        "generate_daily_radio.py must call `await rvs.build_episode_visuals_async(...)` inside async main()!"
    )
    assert "rvs.build_episode_visuals(" not in src, (
        "generate_daily_radio.py still contains synchronous `rvs.build_episode_visuals(` inside async main()!"
    )
    assert "prev_spk_audios" in src and 'sp["model_audio"] = ma' in src, (
        "generate_daily_radio.py must preserve speaking_prompts model_audio across same-day re-runs!"
    )
    print("[PASS 10/10] generate_daily_radio.py async visual invocation & same-day asset preservation verified")


def main() -> int:
    test_all_python_files_syntax_and_names()
    test_apply_practice_logs_all_event_types()
    test_frontend_backend_choice_contract()
    test_dynamic_vocab_cards_self_test4_invariants()
    test_speaking_prompts_self_test9_invariants()
    test_workflows_radio_version_alignment()
    test_workflows_stage_video_and_img_assets()
    test_async_loop_safety_and_live_visual_studio_invocation()
    test_all_future_volumes_jp_video_invariants()
    test_generate_daily_radio_async_and_reuse_contract()
    print("[ALL PASS] tests_ci_guard.py 10/10 gates green!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

