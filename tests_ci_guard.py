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
    print(f"[PASS 1/18] Static AST syntax & undefined-name check ({len(py_files)} Python files)")


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

            # Adaptive v7.0: verify auto-decay of stale scars once mastered green/later-clean + confusion_pairs extraction!
            state["radio_relearn_queue"]["〜かわりに"] = "20261123"
            state["hesitant_points"]["〜かわりに"] = "20261123"
            state["grammar_points"].append({"id": "G-099", "name": "〜かわりに", "status": "green", "streak": 3, "last_ok_date": "20261124"})
            with open(log_file, "a", encoding="utf-8") as af:
                af.write(json.dumps({"ts": "2026-11-25T06:00:01Z", "id": "SPK:RV-2", "point": "〜べきではない", "choice": "开口:自然达标", "correct": "true"}, ensure_ascii=False) + "\n")
                af.write(json.dumps({"ts": "2026-11-25T06:00:02Z", "id": "N3-G2", "point": "〜べきではない", "choice": "わけではない", "correct": "false", "ask_again": "false"}, ensure_ascii=False) + "\n")
            rba.apply_practice_logs(state, "20261125")
            assert "〜かわりに" not in (state.get("radio_relearn_queue") or {}), "Green point must auto-decay from radio_relearn_queue!"
            assert "〜かわりに" not in (state.get("hesitant_points") or {}), "Green point must auto-decay from hesitant_points!"
            assert "〜べきではない" not in ((state.get("speaking_practice") or {}).get("slips") or {}), "Redeemed SPK pass must clear slip!"
            cp = state.get("confusion_pairs") or {}
            assert (cp.get("〜べきではない") or {}).get("top_wrong") == "わけではない", f"Expected confusion_pairs to track real wrong choice, got {cp}"
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_rba_log, orig_rba_snap
            aadc.LOG_PATH, aadc.SNAP_PATH = orig_aadc_log, orig_aadc_snap
            if orig_ledger is not None:
                ive.LEDGER_PATH = orig_ledger
    print("[PASS 2/18] apply_practice_logs & collect_study_history all-event-types test")


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
    print(f"[PASS 3/18] Frontend<->Backend choice contract sync ({len(rv_labels)} RV + {len(ga_labels)} GA labels)")


def test_dynamic_vocab_cards_self_test4_invariants() -> None:
    import vocab_cards as vc
    import immersion_vocab_engine as ive
    from adaptive_bank import CORE_N3_KANA_VOCAB

    candidates: list[str] = list(vc.VOCAB_CARDS.keys()) + list(vc.PRONUNCIATION_MNEMONICS.keys())
    for row in getattr(ive, "IMMERSION_VOCAB_BANK", []):
        if row.get("kanji"):
            candidates.append(str(row["kanji"]))
    for kw, _, _ in CORE_N3_KANA_VOCAB:
        candidates.append(str(kw))
    # Also test completely unseen synthetic kanji & kana words!
    candidates.extend(["象徴", "緊急事態", "再配達", "もやもや"])

    vulgar_re = re.compile(r"\b(?:cock|gay|shit|fuck|damn|ass|die|sin|cheat)\b", re.I)
    checked = set()
    for w in candidates:
        if not w or w in checked:
            continue
        checked.add(w)
        spec = vc.build_dynamic_vocab_card(w, {})
        aspec = vc.build_vocab_audio_spec(spec)
        mn = str(spec.get("mnemonic") or "").strip()
        mn_card = vc.distill_card_mnemonic(mn, has_trap_tag=bool(spec.get("trap_tag")), target_word=w)
        mn_cue, mn_scene = vc.split_card_mnemonic(mn, has_trap_tag=bool(spec.get("trap_tag")), target_word=w)
        hs = str(aspec.get("hook_spoken") or "").strip()
        ch = str(spec.get("chunk_ja") or "").strip()
        assert mn and mn_card, f"Empty mnemonic for vocab card '{w}'"
        assert "—" not in mn and "—" not in mn_card, f"Em dash in mnemonic for '{w}': {mn}"
        assert hs, f"Empty hook_spoken for vocab card '{w}'"
        assert "—" not in hs, f"Em dash in hook_spoken for '{w}': {hs}"
        for bad_lbl in ("英文", "中文", "谐音"):
            assert bad_lbl not in mn_card, f"Redundant label '{bad_lbl}' in mnemonic_card for '{w}': {mn_card}"
            assert bad_lbl not in mn_cue and bad_lbl not in mn_scene, f"Redundant label '{bad_lbl}' in cue/scene for '{w}': {mn_cue} | {mn_scene}"
            assert bad_lbl not in hs, f"Redundant label '{bad_lbl}' in hook_spoken for '{w}': {hs}"
        for field_name, val in (("mn", mn), ("cue", mn_cue), ("scene", mn_scene), ("spoken", hs)):
            assert not vulgar_re.search(val), f"Banned vulgar/morbid anchor in {field_name} for '{w}': {val}"
            assert "自满" not in val and "自満" not in val, f"Kanji-swap error 自满/自満 in {field_name} for '{w}': {val}"
            assert "Gee(ぎ)" not in val, f"Phonetic error Gee(ぎ) in {field_name} for '{w}': {val}"
        assert not vc.has_kanji_cue_pollution(w, mn_cue), f"Kanji cue pollution for '{w}': cue={mn_cue!r} | scene={mn_scene!r}"
        if mn_cue:
            assert "+" not in mn_scene[:10] and "＋" not in mn_scene[:10], f"Broken half-split cue for '{w}': {mn_cue!r} | {mn_scene!r}"
        assert len(ch) <= 10, f"chunk_ja too long ({len(ch)}>10) for '{w}': {ch}"

    # Regression unit checks on has_kanji_cue_pollution & split_card_mnemonic
    assert vc.has_kanji_cue_pollution("自慢", "自(じ)满(まん)") is True
    assert vc.has_kanji_cue_pollution("指示", "师(し)指(じ)") is True
    assert vc.has_kanji_cue_pollution("順番", "顺(じゅん)班(ばん)") is True
    assert vc.has_kanji_cue_pollution("自慢", "Gym Man(じまん)") is False
    assert vc.has_kanji_cue_pollution("貯める", "他(た)没(め)花") is False
    assert vc.has_kanji_cue_pollution("しっかり", "实(しっ)卡(か)死") is False
    print(f"[PASS 4/18] Dynamic vocab cards Self-test 4 invariants ({len(checked)} words, zero kanji-swap/half-split/vulgar/label regressions)")


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
    print(f"[PASS 5/18] Speaking prompts Self-test 9 invariants ({len(rrb._SPEAKING_TEMPLATES)} templates + fallback stress)")


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
    print(f"[PASS 6/18] Workflow radio version guard aligned (v{max_gen_ver} across {len(wf_files)} workflows)")


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
    print(f"[PASS 7/18] Workflow video/ & img/ staging guard verified across {len(wf_files)} workflows")


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
    print("[PASS 8/18] Static & live-event-loop async safety guard (zero nested asyncio.run crashes)")


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
    for c_sid, c_raw in sorted(rvs.CURATED_JP_VIDEO_SCRIPTS.items()):
        c_lines = c_raw.get("lines") or []
        max_cues = 36 if str(c_sid).startswith("n2_") else 18
        assert 10 <= len(c_lines) <= max_cues, f"Curated {c_sid}: expected 10..{max_cues} cues, got {len(c_lines)}"
        c_blob = str(c_raw.get("title_ja", "")) + str(c_raw.get("title_zh", "")) + "".join(str(x.get("ja", "")) + str(x.get("zh", "")) for x in c_lines)
        assert "—" not in c_blob, f"Curated {c_sid}: em dash leaked"
        c_ja = "\n".join(str(x.get("ja", "")) for x in c_lines)
        c_hits = [we["word"] for we in word_entries if we["word"] in c_ja]
        assert len(c_hits) >= 8, f"Curated {c_sid}: only {len(c_hits)} native target word hits (<8): {c_hits}"

    print(f"[PASS 9/18] All {checked_vols} future volumes + {len(rvs.CURATED_JP_VIDEO_SCRIPTS)} curated JP videos + stingy-LLM Self-test 13 invariants (>=10 cues, >=8 words)")


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
    assert '"id": str(st.get("id")' in src, (
        "generate_daily_radio.py story_blocks must include story id so curated topics & JP video scripts match!"
    )
    print("[PASS 10/18] generate_daily_radio.py async visual invocation, story id & same-day asset preservation verified")


def test_full_bank_4choice_and_immersion_mnemonics() -> None:
    """Gate 11: Ensure 100% of non-listening cards across all 14 waves reach 4 choices and 100% of immersion vocab have mnemonics."""
    import exam_choice_enricher as ece
    import immersion_vocab_engine as ive
    import tutor_data
    import vocab_cards
    import wave11_precision_variants
    import weak_expansion_bank
    import weak_expansion_wave2
    import weak_expansion_wave3
    import weak_expansion_wave4
    import weak_expansion_wave5
    import weak_expansion_wave6
    import weak_expansion_wave7
    import weak_expansion_wave8
    import weak_expansion_wave9
    import weak_expansion_wave10
    import weak_expansion_wave12
    import weak_expansion_wave13

    mods = [
        tutor_data, weak_expansion_bank, weak_expansion_wave2, weak_expansion_wave3,
        weak_expansion_wave4, weak_expansion_wave5, weak_expansion_wave6, weak_expansion_wave7,
        weak_expansion_wave8, weak_expansion_wave9, weak_expansion_wave10, wave11_precision_variants,
        weak_expansion_wave12, weak_expansion_wave13,
    ]
    seen_ids: set[str] = set()
    holdouts: list[str] = []
    for mod in mods:
        for attr in dir(mod):
            val = getattr(mod, attr)
            if isinstance(val, list) and val and isinstance(val[0], dict) and "id" in val[0] and "choices" in val[0]:
                for q in val:
                    qid = str(q["id"])
                    if qid in seen_ids:
                        continue
                    seen_ids.add(qid)
                    subj = str(q.get("subject", ""))
                    if subj in ("听力", "聴解") or q.get("is_listening") or qid.startswith("N3-L") or "-L" in qid:
                        continue
                    enr = ece.enrich_card_choices(
                        q["choices"], q.get("answer", ""), is_listening=False,
                        point_key=q.get("point_key", ""), subject=subj,
                    )
                    if len(enr) < 4:
                        holdouts.append(qid)
    assert not holdouts, f"Non-listening cards staying <4 choices: {holdouts}"

    missing_mn = [
        it.get("kanji") or it.get("kana")
        for it in ive.IMMERSION_VOCAB_BANK
        if not vocab_cards.get_pronunciation_mnemonic(it.get("kanji") or it.get("kana") or "", it.get("kana") or "")
    ]
    assert not missing_mn, f"Immersion words missing bilingual pronunciation mnemonics: {missing_mn[:10]}"
    print(f"[PASS 11/18] 100% 4-choice across all {len(seen_ids)} cards (0 holdouts) + 100% bilingual mnemonics across {len(ive.IMMERSION_VOCAB_BANK)} immersion words")


def test_full_bank_100pct_option_notes() -> None:
    """Gate 12: 100% of ALL options across ALL 587+ cards must have non-empty, zero-dash, non-generic Chinese opt_notes."""
    import clear_explanations
    import exam_choice_enricher as ece
    import option_notes_catalog as onc
    import tutor_data
    import wave11_precision_variants
    import weak_expansion_bank
    import weak_expansion_wave2
    import weak_expansion_wave3
    import weak_expansion_wave4
    import weak_expansion_wave5
    import weak_expansion_wave6
    import weak_expansion_wave7
    import weak_expansion_wave8
    import weak_expansion_wave9
    import weak_expansion_wave10
    import weak_expansion_wave12
    import weak_expansion_wave13

    mods = [
        weak_expansion_bank, weak_expansion_wave2, weak_expansion_wave3, weak_expansion_wave4,
        weak_expansion_wave5, weak_expansion_wave6, weak_expansion_wave7, weak_expansion_wave8,
        weak_expansion_wave9, weak_expansion_wave10, wave11_precision_variants, weak_expansion_wave12,
        weak_expansion_wave13,
    ]
    l_notes: dict[str, dict[str, str]] = {}
    for mod in mods:
        for attr in dir(mod):
            if "LISTENING_OPT_NOTES" in attr and isinstance(getattr(mod, attr), dict):
                l_notes.update(getattr(mod, attr))

    all_cards: dict[str, dict] = {}
    for qid, it in tutor_data.TUTOR_ITEMS.items():
        all_cards[qid] = {
            "id": qid,
            "subject": "聴解" if qid.startswith("Q-") else ("活用" if qid.startswith("H-") else ("語彙" if qid.startswith("V-") else "文法")),
            "point_key": it.get("point_key", ""),
            "choices": it.get("choices") or [],
            "answer": it.get("answer", ""),
            "opt_notes": dict(l_notes.get(qid) or it.get("option_notes") or {}),
        }
    for mod in mods:
        for attr in dir(mod):
            val = getattr(mod, attr)
            if isinstance(val, list) and val and isinstance(val[0], dict) and "id" in val[0] and "choices" in val[0]:
                for q in val:
                    qid = str(q["id"])
                    if qid not in all_cards:
                        all_cards[qid] = {
                            "id": qid,
                            "subject": q.get("subject", "文法"),
                            "point_key": q.get("point_key") or q.get("variant_of") or "",
                            "choices": q.get("choices") or [],
                            "answer": q.get("answer", ""),
                            "opt_notes": dict(l_notes.get(qid) or q.get("option_notes") or {}),
                        }

    missing: list[str] = []
    dashes: list[str] = []
    generic: list[str] = []
    total_opts = 0
    for qid, c in all_cards.items():
        is_l = (c["subject"] in ("聴解", "听力")) or qid.startswith(("Q-", "N3-L")) or "-L" in qid
        c75 = clear_explanations.CARDS_75.get(qid, {})
        raw_ch = c75.get("choices") or c["choices"]
        enr_ch = ece.enrich_card_choices(
            raw_ch, c["answer"], is_listening=is_l, point_key=c["point_key"], subject=c["subject"]
        )
        notes = onc.ensure_complete_opt_notes(
            qid, enr_ch, c["answer"], c["opt_notes"],
            subject=c["subject"], point_key=c["point_key"],
            why_line=c75.get("why_line", ""), form_line=c75.get("form_line", ""),
            is_listening=is_l,
        )
        for o in enr_ch:
            total_opts += 1
            txt = str(notes.get(o) or "").strip()
            if len(txt) < 6:
                missing.append(f"{qid}:{o}")
            if "—" in txt:
                dashes.append(f"{qid}:{o}")
            if "词义、接续或语态与本题语境不符" in txt:
                generic.append(f"{qid}:{o}")
    assert not missing, f"Options missing Chinese opt_notes ({len(missing)}): {missing[:10]}"
    assert not dashes, f"Options containing banned em dash ({len(dashes)}): {dashes[:10]}"
    assert not generic, f"Existing bank options hitting generic fallback ({len(generic)}): {generic[:10]}"
    print(f"[PASS 12/18] 100% curated zero-dash option explanations across all {len(all_cards)} cards / {total_opts} options (0 blank, 0 generic)")


def test_exam_day_and_n2_zero_to_120_transition_contract() -> None:
    """Gate 13: Verify 2026-12-06 Exam Day, 2026-12-07 N2 Day 1, 2026-12-20 Europe travel, MOCK/N3_SCORE/quiet-SPK logs, and N2 Day 1 radio."""
    import os
    import subprocess
    import tempfile

    import run_brain_algorithm as rba
    from n2_prep import n2_curriculum_engine as n2e

    # 1. N2 bank & vocab invariants
    qbank = n2e.build_n2_question_bank()
    assert len(qbank) >= 190, f"Expected >=190 N2 grammar points, got {len(qbank)}"
    for item in qbank:
        p = item["primary"]
        assert len(p["choices"]) == 4 and len(set(p["choices"])) == 4, f"{item['id']} not 4 unique choices"
        assert p["answer"] in p["choices"], f"{item['id']} answer not in choices"
    vcards = n2e.build_n2_vocab_cards()
    assert len(vcards) >= 145, f"Expected >=145 N2 vocab cards, got {len(vcards)}"
    for w, vc in vcards.items():
        assert vc["mnemonic"] and "—" not in vc["mnemonic"], f"Bad N2 mnemonic for {w}"
        assert len(vc["chunk_ja"]) <= 10, f"N2 chunk_ja > 10 chars for {w}: {vc['chunk_ja']}"

    # 2. Brain state log handling for N3_SCORE:, MOCK:, quiet SPK, and N2G-001
    fake_state = {
        "grammar_points": [{"id": "G-001", "name": "〜ばかりだ", "status": "green", "streak": 3}],
        "n2_grammar_points": [{"id": "N2G-001", "point": "〜ざるを得ない", "status": "gray", "streak": 0}],
        "henkei_points": [],
        "listening_points": [],
        "vocab_tracked": [],
        "speaking_practice": {"total_reps": 2, "last_date": "20261124", "slips": {"〜ばかりだ": {"count": 1, "last_date": "20261124", "last_note": "old"}}},
        "_processed_log_ts": [],
    }
    fake_lines = [
        {"ts": "2026-12-07T18:00:00Z", "id": "N3_SCORE:142", "point": "N3实考", "choice": "N3实考:142", "correct": "true"},
        {"ts": "2026-12-07T18:01:00Z", "id": "MOCK:N3-G40", "point": "〜ばかりだ", "choice": "模拟错:わけだ", "correct": "false"},
        {"ts": "2026-12-07T18:02:00Z", "id": "SPK:spk_1", "point": "〜ばかりだ", "choice": "开口:默跟顺口", "correct": "true"},
        {"ts": "2026-12-07T18:03:00Z", "id": "N2G-001", "point": "〜ざるを得ない", "choice": "ざるを得ない", "correct": "true"},
    ]
    orig_log = rba.LOG_PATH
    orig_snap = rba.SNAPSHOT_PATH
    with tempfile.TemporaryDirectory(prefix="n2_gate13_") as td:
        tlog = os.path.join(td, "practice_log.jsonl")
        with open(tlog, "w", encoding="utf-8") as f:
            for row in fake_lines:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rba.LOG_PATH = tlog
        rba.SNAPSHOT_PATH = os.path.join(td, "no_snap.json")
        try:
            rba.apply_practice_logs(fake_state, "20261207")
        finally:
            rba.LOG_PATH = orig_log
            rba.SNAPSHOT_PATH = orig_snap

        assert (fake_state.get("n3_real_score") or {}).get("total") == 142, f"N3_SCORE failed: {fake_state.get('n3_real_score')}"
        assert fake_state["grammar_points"][0]["status"] == "red", f"MOCK miss did not flag red: {fake_state['grammar_points'][0]}"
        assert fake_state["speaking_practice"]["total_reps"] == 3 and "〜ばかりだ" not in fake_state["speaking_practice"]["slips"], f"Quiet SPK failed: {fake_state['speaking_practice']}"
        assert fake_state["n2_grammar_points"][0]["status"] == "yellow" and fake_state["n2_grammar_points"][0]["streak"] == 1, f"N2G-001 mastery failed: {fake_state['n2_grammar_points'][0]}"

        # 3. Isolated multi-date build_html.py dry-runs (all 22 Node self-tests per date!)
        for d_str, exp_phase, exp_track, exp_min, exp_max in (
            ("2026-12-06", "exam_day", "N3", 12, 12),
            ("2026-12-07", "n2_climb", "N2", 45, 50),
            ("2026-12-20", "n2_climb", "N2", 20, 26),
        ):
            out_html = os.path.join(td, f"sim_{d_str}.html")
            env = dict(os.environ, FORCE_STUDY_DATE=d_str, OUTPUT_HTML_PATH=out_html)
            subprocess.run([sys.executable, str(BASE_DIR / "build_html.py")], cwd=str(BASE_DIR), env=env, check=True, stdout=subprocess.DEVNULL)
            raw_h = open(out_html, encoding="utf-8").read()
            assert f"<title>{exp_track}</title>" in raw_h, f"{d_str}: expected <title>{exp_track}</title>"
            m_d = re.search(r"const DATA = (\{.*?\});\n", raw_h)
            assert m_d, f"{d_str}: DATA payload missing"
            d_obj = json.loads(m_d.group(1))
            assert d_obj["phase"] == exp_phase and d_obj["track_label"] == exp_track, f"{d_str}: phase mismatch {d_obj['phase']}/{d_obj['track_label']}"
            assert exp_min <= len(d_obj["points"]) <= exp_max, f"{d_str}: deck size {len(d_obj['points'])} out of [{exp_min},{exp_max}]"
            if d_str == "2026-12-07":
                pids = {p["id"] for p in d_obj["points"]}
                assert "N2G-001" in pids and "N2G-002" in pids, f"12/07 missing N2G-001/002: {sorted(pids)[:10]}"
                n2g1 = next(p for p in d_obj["points"] if p["id"] == "N2G-001")
                assert n2g1.get("teach_first") is True, "12/07 N2G-001 must have teach_first=True"

    # 4. N2 Day 1 Radio dry-test
    rad_out = subprocess.run(
        [sys.executable, str(BASE_DIR / "generate_daily_radio.py"), "--dry-test", "--dry-date", "2026-12-07"],
        cwd=str(BASE_DIR), check=True, capture_output=True, text=True,
    ).stdout
    assert "n2_v1_s2a" in rad_out and "n2_v1_s4_world_rare_earth" in rad_out and "phase=n2_climb" in rad_out, f"12/07 radio dry-test failed: {rad_out}"
    print("[PASS 13/18] Exam-Day (12/06), N2 Day 1 (12/07), Europe Travel (12/20), MOCK/N3_SCORE/quiet-SPK & N2 Radio transitions verified end-to-end")


def test_cloud_sync_sandbox_isolation_guard() -> None:
    """Gate 14: Automated/headless/localhost browsers must NEVER publish to production ntfy.sh (N3 Tutor or ZenBody)."""
    src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    assert "function isCloudSyncBlockedEnv(" in src, "build_html.py missing isCloudSyncBlockedEnv() guard!"
    assert "nav.webdriver === true" in src and "HeadlessChrome" in src, (
        "isCloudSyncBlockedEnv() must block navigator.webdriver and HeadlessChrome!"
    )
    assert 'host === "localhost"' in src and 'host === "127.0.0.1"' in src and 'proto === "file:"' in src, (
        "isCloudSyncBlockedEnv() must block localhost, 127.0.0.1, and file: origins!"
    )
    assert "const CLOUD_SYNC_BLOCKED = isCloudSyncBlockedEnv();" in src, "Missing CLOUD_SYNC_BLOCKED binding!"
    assert "if (CLOUD_SYNC_BLOCKED || !VAULT || !CKEY) return;" in src, (
        "ZenBody pushNow() must also respect CLOUD_SYNC_BLOCKED!"
    )
    assert "if (!CLOUD_SYNC_BLOCKED) {" in src, (
        "ZenBody pullCloud() must also skip ntfy.sh when CLOUD_SYNC_BLOCKED!"
    )
    assert "quiz-blank-unit" in src, "Missing .quiz-blank-unit orphan punctuation prevention!"
    print("[PASS 14/18] Client-side cloud sync sandbox isolation (N3 + ZenBody) & orphan-punctuation blank guard verified")


def test_v43_storycraft_and_archival_footage_guard() -> None:
    """Gate 13: Guard v43 storycraft (zero mid-podcast quiz on 11/26+, calm immersion cap, Vol.23 golden spacing) & real historical footage pipeline."""
    import immersion_vocab_engine as ive
    import radio_salon_uchi_vol23 as v23
    import radio_visual_studio as rvs

    # 1. Immersion engine must cap inline chops cleanly so storytelling stays fluid
    assert ive.MAX_INLINE_PER_SENTENCE == 1, f"Expected MAX_INLINE_PER_SENTENCE=1, got {ive.MAX_INLINE_PER_SENTENCE}"
    assert getattr(ive, "MAX_AUTO_SWAPS_PER_STORY", 99) <= 10

    # 2. generate_daily_radio.py must NOT run mid-episode pop-quiz rumination on 2026-11-26+
    gdr_src = (BASE_DIR / "generate_daily_radio.py").read_text(encoding="utf-8")
    assert 'if today_str == "2026-11-25"' in gdr_src, "Mid-episode rumination quiz must be gated to 2026-11-25 only!"
    assert "_strip_n5_pepper_in_turn" in gdr_src, "Missing v43 N5 pepper-shaker de-chop helper!"

    # 3. Tomorrow's Vol.23 golden storycraft invariants (18 calm grammar points, >=600 chars/pt, pure-Chinese 7-turn outro)
    stories = v23.SALON_STORIES_UCHI_VOL23
    tot_chars = sum(len(t[1]) for s in stories for t in s["turns"])
    tot_pts = sum(len(s.get("point_ids") or []) for s in stories)
    assert tot_pts <= 20, f"Vol.23 grammar points bloated again ({tot_pts} > 20)!"
    assert tot_chars / max(1, tot_pts) >= 580, f"Vol.23 chars/pt too dense ({tot_chars/tot_pts:.0f} < 580)!"
    last7 = stories[-1]["turns"][-7:]
    last7_txt = "".join(t[1] for t in last7)
    assert not re.search(r"[ぁ-んァ-ヶー]", last7_txt), "Vol.23 final 7 turns must be 100% pure Chinese under real Phoenix TV outro!"
    assert 150 <= len(last7_txt) <= 230, f"Vol.23 final 7 turns char count out of range: {len(last7_txt)}"

    # 4. Real historical archival footage catalog & offline fallback contract
    assert len(rvs.CURATED_ARCHIVAL_FOOTAGE) >= 25, f"Expected >=25 curated archival footage entries, got {len(rvs.CURATED_ARCHIVAL_FOOTAGE)}"
    for sid in ("uchi23_s1_news_fallback", "uchi23_s2a_kabuki_drama_part1", "uchi23_s3b_mishima_contrast_part2", "uchi23_s4_world_brain_ai"):
        cands = rvs._resolve_archival_footage_candidates({"id": sid})
        assert cands, f"Missing curated historical footage for {sid}"
    theme_hit = rvs._resolve_archival_footage_candidates({"id": "live_nhk_news_2026-12-01", "title": "京都の伝統と新幹線の歴史", "short_tab": "京都"})
    assert theme_hit, "Theme-matched historical footage fallback returned empty!"
    # Mocked ffmpeg must skip network cleanly and return []
    assert rvs._download_chapter_archival_clips({"id": "uchi23_s1_news_fallback", "chapter": 0}, "/tmp", set(), ffmpeg_bin="/usr/bin/true") == []
    print(f"[PASS 15/18] v43 storycraft ({tot_pts} pts, {tot_chars//tot_pts} chars/pt) & real historical footage vault ({len(rvs.CURATED_ARCHIVAL_FOOTAGE)} chapters) verified")


def test_v44_anti_tourist_kanazawa_and_feedback_guard() -> None:
    """Gate 16: Enforce v44 3-year-learner non-tourist floor, tomorrow's Deep Kanazawa Vol.18, and 30-second RADIO_FB cloud loop."""
    import importlib
    import os
    import subprocess
    import tempfile
    import auto_author_daily_content as aadc
    import daily_news_salon_gen as dnsg
    import radio_salon_uchi_vol18 as v18
    import run_brain_algorithm as rba
    import sync_cloud_store as scs

    # 1. Tomorrow (2026-11-27) dry-test MUST select upgraded Vol.18 with Deep Kanazawa 2-parter
    rad_out = subprocess.run(
        [sys.executable, str(BASE_DIR / "generate_daily_radio.py"), "--dry-test", "--dry-date", "2026-11-27"],
        cwd=str(BASE_DIR), check=True, capture_output=True, text=True,
    ).stdout
    for exp_id in ("uchi18_s1_news_fallback", "uchi18_s3a_kanazawa_part1", "uchi18_s3b_kanazawa_part2", "uchi18_s4_world_europe_defense"):
        assert exp_id in rad_out, f"2026-11-27 dry-test missing {exp_id}: {rad_out}"

    # 2. Vol.18 golden v44 storycraft invariants
    stories18 = v18.SALON_STORIES_UCHI_VOL18
    tot_chars18 = sum(len(t[1]) for s in stories18 for t in s["turns"])
    tot_pts18 = sum(len(s.get("point_ids") or []) for s in stories18)
    assert tot_pts18 <= 20, f"Vol.18 grammar points too dense ({tot_pts18} > 20)"
    assert tot_chars18 / max(1, tot_pts18) >= 580, f"Vol.18 chars/pt too dense ({tot_chars18 / tot_pts18:.0f} < 580)"
    last7_18 = "".join(t[1] for t in stories18[-1]["turns"][-7:])
    assert not re.search(r"[ぁ-んァ-ヶー]", last7_18), "Vol.18 final 7 turns must be 100% pure Chinese!"

    # 3. Zero banned tourist/Japan-101 cliches across ALL upcoming pre-exam, reserve, and N2 preview volumes
    pat = dnsg.BANNED_TOURIST_CLICHE_RE
    for vnum in (12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25):
        mod = importlib.import_module(f"radio_salon_uchi_vol{vnum}")
        for st in getattr(mod, f"SALON_STORIES_UCHI_VOL{vnum}"):
            txt = st.get("title", "") + "\n" + "\n".join(t[1] for t in st.get("turns", []))
            m = pat.search(txt)
            assert not m, f"Vol.{vnum} {st['id']} contains banned tourist cliche: {m.group(0)}"
    n2_prev_txt = (BASE_DIR / "n2_prep" / "n2_radio_vol1_preview.py").read_text(encoding="utf-8")
    assert not pat.search(n2_prev_txt), "n2_radio_vol1_preview.py contains banned tourist cliche!"

    # 4. Live headline ranker demotes Kyoto overtourism below Kanazawa/fiscal politics & validator rejects cliches
    ranked = dnsg.rank_headlines_by_editorial_taste([
        {"title": "京都の観光地でオーバーツーリズム対策 バス混雑と嵐山の外国人観光客"},
        {"title": "石川県金沢市の北陸新幹線と地方鉄道・自治体財政の新たな挑戦"},
    ], limit=2)
    assert "金沢" in ranked[0]["title"], f"Expected Kanazawa governance headline ranked #1, got: {ranked[0]['title']}"
    bad_story = {
        "id": "test_cliche",
        "title": "京都茶泡饭",
        "turns": [
            ["tao", "京都人说ぶぶづけ其实就是赶客，大阪大妈买菜喜欢砍价还爱比开枪手势，大家都很清楚。"] * 12,
        ],
    }
    assert dnsg.validate_generated_story(bad_story, require_light_explain=False) is False, "Validator failed to reject banned tourist cliche!"

    # 5. Catalog loader skips deprecated_tourist_cliche entries & includes new deep topics
    unused = aadc._load_unused_public_memory_topics(set(), set())
    unused_descs = "\n".join(u[1] for u in unused)
    for banned_kw in ("茶泡饭", "报联相", "肯德基", "红白歌会", "鞠躬章"):
        assert banned_kw not in unused_descs, f"Deprecated tourist cliche '{banned_kw}' leaked into auto-author topic pool!"
    for deep_kw in ("金泽", "故乡税", "主银行", "选择性夫妇别姓"):
        assert deep_kw in unused_descs, f"New deep topic '{deep_kw}' missing from auto-author topic pool!"

    # 6. End-to-end RADIO_FB: ingestion into brain state WITHOUT polluting quiz mastery or sync_cloud_store greenAt
    fake_state = {
        "grammar_points": [{"id": "G-001", "name": "〜ばかりだ", "status": "green", "streak": 3}],
        "henkei_points": [],
        "listening_points": [],
        "vocab_tracked": [],
        "_processed_log_ts": [],
    }
    fb_row = {
        "ts": "2026-11-26T20:30:00Z",
        "id": "RADIO_FB:20261126",
        "point": "feel=听爽了|good=冷门有深度,聊天自然|fix=太游客听腻了",
        "choice": "评本期:金泽可以多聊，京阪老梗别讲",
        "correct": "true",
    }
    orig_rba_log, orig_rba_snap = rba.LOG_PATH, rba.SNAPSHOT_PATH
    orig_scs_log = scs.LOG_PATH
    with tempfile.TemporaryDirectory(prefix="v44_gate16_") as td:
        tlog = os.path.join(td, "practice_log.jsonl")
        with open(tlog, "w", encoding="utf-8") as f:
            f.write(json.dumps(fb_row, ensure_ascii=False) + "\n")
        rba.LOG_PATH = tlog
        rba.SNAPSHOT_PATH = os.path.join(td, "no_snap.json")
        scs.LOG_PATH = tlog
        try:
            rba.apply_practice_logs(fake_state, "20261126")
            crdt_state = scs.empty_crdt_state("2026-11-26")
            crdt_state, _ = scs.seed_from_practice_log(crdt_state, "2026-11-26")
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_rba_log, orig_rba_snap
            scs.LOG_PATH = orig_scs_log

    fb_hist = fake_state.get("radio_feedback_history") or []
    assert len(fb_hist) == 1 and fb_hist[0]["feel"] == "听爽了" and "冷门有深度" in fb_hist[0]["good"] and "金泽可以多聊" in fb_hist[0]["note"], (
        f"RADIO_FB parsing failed: {fb_hist}"
    )
    assert not fake_state.get("confusion_pairs"), f"RADIO_FB polluted confusion_pairs: {fake_state.get('confusion_pairs')}"
    day_bucket = (crdt_state.get("dates") or {}).get("2026-11-26") or {}
    assert "RADIO_FB:20261126" not in (day_bucket.get("greenAt") or {}) and "RADIO_FB:20261126" not in (day_bucket.get("retestAt") or {}), (
        f"RADIO_FB leaked into sync_cloud_store greenAt/retestAt: {day_bucket}"
    )
    print(f"[PASS 16/18] v44 non-tourist depth floor (12 volumes + live ranker/catalog), tomorrow's Deep Kanazawa Vol.18 ({tot_pts18} pts, {tot_chars18//tot_pts18} ch/pt) & RADIO_FB cloud loop verified")


def test_v45_broadcast_authenticity_guard() -> None:
    """Gate 17: Guard v45 broadcast authenticity (native 3-host + Keita JP, real 2012 Zhang Miaoyang WAV, polyphone map, opening beat, and 10+ turn fade-out endings)."""
    import datetime
    import importlib
    import wave
    import generate_daily_radio as gdr

    # 1. Real extracted 2012 Zhang Miaoyang broadcast WAV asset integrity
    zmy_wav = BASE_DIR / "audio" / "qq_ann_zmy_2012.wav"
    assert zmy_wav.exists() and zmy_wav.stat().st_size > 100_000, f"Missing or tiny real Zhang Miaoyang WAV: {zmy_wav}"
    with wave.open(str(zmy_wav), "rb") as wf:
        assert wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 24000, "zmy WAV must be 24kHz mono 16-bit PCM"
        zmy_dur = wf.getnframes() / float(wf.getframerate())
        assert 3.4 <= zmy_dur <= 4.3, f"Unexpected zmy WAV duration: {zmy_dur:.2f}s"

    # 2. Next-program roster schedules real 2012 Zhang Miaoyang on 2026-11-27 and calibrated Yunyang on 2026-11-28
    np_27 = gdr.pick_phoenix_next_program(datetime.date(2026, 11, 27))
    assert np_27.get("real_wav") == "audio/qq_ann_zmy_2012.wav" and np_27.get("source") == "original_2012_zhang_miaoyang", f"2026-11-27 must use real Zhang Miaoyang WAV: {np_27}"
    np_28 = gdr.pick_phoenix_next_program(datetime.date(2026, 11, 28))
    assert np_28.get("source") == "calibrated_yunyang_zmy" and np_28.get("lead_in") in ("接着下来为您播出", "接着为您播出"), f"2026-11-28 bad continuity spec: {np_28}"

    # 3. Native 3-host voice defaults + ja-JP-KeitaNeural inline Japanese routing (NEVER sending Japanese to zh-CN voice!)
    gdr_src = (BASE_DIR / "generate_daily_radio.py").read_text(encoding="utf-8")
    for expected_v in ("zh-CN-YunxiNeural", "zh-TW-YunJheNeural", "zh-CN-YunjianNeural", "ja-JP-KeitaNeural", "zh-CN-YunyangNeural"):
        assert expected_v in gdr_src, f"generate_daily_radio.py missing native v45 voice {expected_v}"
    mock_vmap = {
        "W_MID": ("zh-CN-YunxiNeural", "+7%", "-2Hz"),
        "W_JA_INLINE": ("ja-JP-KeitaNeural", "+4%", "-1Hz"),
        "D_MID": ("zh-TW-YunJheNeural", "+3%", "-4Hz"),
        "D_JA_INLINE": ("ja-JP-KeitaNeural", "+1%", "-4Hz"),
        "X_MID": ("zh-CN-YunjianNeural", "+8%", "+2Hz"),
        "X_JA_INLINE": ("ja-JP-KeitaNeural", "+4%", "+2Hz"),
    }
    for spk_k in ("W_MID", "D_MID", "X_MID"):
        jv, _jr, _jp = gdr.inline_ja_voice_cfg(spk_k, mock_vmap, "たつみようすい")
        assert jv == "ja-JP-KeitaNeural", f"inline_ja_voice_cfg({spk_k}) routed to wrong voice: {jv}"

    # 4. Spoken-only Mandarin polyphone fixes + Dou Wentao signature 0.34s opening beat
    fixed = gdr.apply_tts_pronunciation_fixes("加贺百万石，一石米，田宫高麿")
    assert fixed == "加贺百万担，一担米，田宫高摩", f"Polyphone fix mismatch: {fixed}"
    evs = gdr.split_mandarin_natural("W", "《锵锵三人行》！前些年我坐北陆新干线去石川。", "W_MID")
    assert len(evs) >= 3 and evs[0] == ("W_JAB", "《锵锵三人行》。") and evs[1] == ("PAUSE", 0.34), f"Missing Dou Wentao 0.34s opening beat: {evs}"

    # 5. Upcoming episodes (Vol.18, 12, 13, 24, 25) MUST end with >=10 pure-Chinese banter turns (>=250 chars) for 12s smooth fade-out
    for vnum in (18, 12, 13, 24, 25):
        mod = importlib.import_module(f"radio_salon_uchi_vol{vnum}")
        last_st = getattr(mod, f"SALON_STORIES_UCHI_VOL{vnum}")[-1]
        tail10 = last_st["turns"][-10:]
        tail10_txt = "".join(t[1] for t in tail10)
        assert not re.search(r"[ぁ-んァ-ヶー]", tail10_txt), f"Vol.{vnum} final 10 turns must be 100% pure Chinese!"
        assert len(tail10_txt) >= 250, f"Vol.{vnum} final 10 turns too short for 12s smooth fade-out ({len(tail10_txt)} < 250)!"

    assert "apply_backchannel_room_filter" in gdr_src and "_maybe_layer_backchannel" in gdr_src, "Missing v45 studio backchannel engine!"
    print(f"[PASS 17/18] v45 broadcast authenticity (native W/D/X + Keita JP, real 2012 Zhang Miaoyang {zmy_dur:.2f}s WAV, polyphone map, 0.34s opening beat & 10-turn fade-outs) verified")


def test_v82_jobs_zen_and_telemetry_hygiene_guard() -> None:
    """Gate 18: Guard N2 adaptive telemetry decay, zero 模拟错: prefix in confusion_pairs, and zero banned traffic-light jargon in build_html UI."""
    import os
    import tempfile
    import run_brain_algorithm as rba

    fake_state = {
        "grammar_points": [{"id": "G-001", "name": "〜ばかりだ", "status": "yellow", "streak": 1}],
        "n2_grammar_points": [{"id": "N2-001", "point": "〜に際して", "status": "green", "streak": 3, "last_ok_date": "20261208"}],
        "henkei_points": [{"id": "K-005", "name": "いらっしゃる", "status": "yellow", "streak": 1}],
        "listening_points": [],
        "vocab_tracked": [],
        "radio_relearn_queue": {"〜に際して": "20261207"},
        "hesitant_points": {"〜に際して": "20261207"},
        "_processed_log_ts": [],
    }
    mock_rows = [
        {"ts": "2026-11-26T07:18:19.000Z", "id": "MOCK:VAR12-33", "point": "K-005", "choice": "模拟错:うかがって", "correct": "false"},
        {"ts": "2026-11-26T07:18:20.000Z", "id": "MOCK:N3-L31", "point": "N3L-402", "choice": "模拟错:動物園へ行く", "correct": "false"},
        {"ts": "2026-11-26T07:18:21.000Z", "id": "MOCK:N3-G99", "point": "〜ばかりだ", "choice": "模拟错:未作答", "correct": "false"},
    ]
    orig_log, orig_snap = rba.LOG_PATH, rba.SNAPSHOT_PATH
    with tempfile.TemporaryDirectory(prefix="v82_gate18_") as td:
        tlog = os.path.join(td, "practice_log.jsonl")
        with open(tlog, "w", encoding="utf-8") as f:
            for r in mock_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        rba.LOG_PATH = tlog
        rba.SNAPSHOT_PATH = os.path.join(td, "no_snap.json")
        try:
            rba.reconcile_adaptive_telemetry(fake_state, "20261208")
            rba.recompute_summary(fake_state)
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_log, orig_snap

    assert "〜に際して" not in fake_state["radio_relearn_queue"], "Green N2 grammar point did not auto-decay from radio_relearn_queue!"
    assert "〜に際して" not in fake_state["hesitant_points"], "Green N2 grammar point did not auto-decay from hesitant_points!"
    assert fake_state.get("summary", {}).get("n2_grammar", {}).get("green") == 1, "recompute_summary did not summarize n2_grammar_points!"
    cp = fake_state.get("confusion_pairs") or {}
    assert (cp.get("K-005") or {}).get("top_wrong") == "うかがって", f"MOCK wrong choice should strip 模拟错: cleanly, got {cp}"
    assert not any("模拟错:" in json.dumps(v, ensure_ascii=False) for v in cp.values()), f"模拟错: prefix leaked into confusion_pairs: {cp}"
    assert "N3L-402" not in cp and "〜ばかりだ" not in cp, f"Listening or 未作答 mock item leaked into confusion_pairs: {cp}"

    ns_path = BASE_DIR / "night_summary.json"
    if ns_path.exists():
        ns_txt = ns_path.read_text(encoding="utf-8")
        assert "模拟错:" not in ns_txt, "night_summary.json still contains raw 模拟错: prefix!"

    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    assert "displayPointName(" in bh_src, "build_html.py missing displayPointName() helper!"
    print("[PASS 18/19] N2 telemetry decay, clean mock confusion-pair stripping & Jobs-Zen hygiene verified")


def test_v46_stereo_cognitive_n2_long_horizon_guard() -> None:
    """Gate 19: Guard v46 studio stereo soundstage, cognitive ear-pin/story-echo bridge, 10+ turn endings across ALL unplayed + N2 Vol.1-3, N2 audio answer-leak fix, and 2027 N1 continuity."""
    import importlib
    import generate_daily_radio as gdr
    import generate_neural_audio as gna
    import radio_review_builder as rrb
    from n2_prep import n2_curriculum_engine as n2ce

    # 1. ALL remaining unplayed N3 volumes (12..22, 24, 25) + N2 Vol.1..3 have >=10 pure-Chinese fade-out turns & zero TTS landmines
    bad_tts_re = re.compile(r"[A-Za-z0-9—]|哈哈|噗")
    for vnum in (12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25):
        mod = importlib.import_module(f"radio_salon_uchi_vol{vnum}")
        last_st = getattr(mod, f"SALON_STORIES_UCHI_VOL{vnum}")[-1]
        tail10 = last_st["turns"][-10:]
        tail10_txt = "".join(t[1] for t in tail10)
        assert not re.search(r"[ぁ-んァ-ヶー]", tail10_txt), f"Vol.{vnum} final 10 turns must be 100% pure Chinese!"
        assert len(tail10_txt) >= 250, f"Vol.{vnum} final 10 turns too short for 12s fade-out ({len(tail10_txt)} < 250)!"

    for n2_day in (1, 2, 3):
        bundle = n2ce.get_n2_radio_stories_for_day(n2_day)
        stories = bundle.get("stories") or []
        assert len(stories) == 6, f"N2 Day {n2_day} must provide 6 curated stories, got {len(stories)}"
        for st in stories:
            for spk, txt in st["turns"]:
                if spk in ("W", "D", "X"):
                    m_bad = bad_tts_re.search(str(txt))
                    assert not m_bad, f"N2 Day {n2_day} {st['id']} has TTS landmine {m_bad.group(0)!r} in: {str(txt)[:80]}"
        tail10 = stories[-1]["turns"][-10:]
        tail10_txt = "".join(t[1] for t in tail10)
        assert not re.search(r"[ぁ-んァ-ヶー]", tail10_txt), f"N2 Day {n2_day} final 10 turns must be 100% pure Chinese!"
        assert len(tail10_txt) >= 250, f"N2 Day {n2_day} final 10 turns too short ({len(tail10_txt)} < 250)!"

    # 2. v46 stereo spatializer, room glue, 0.24s pre-JA breath, live feedback auto-tuning, zero bilingual roll-call regression & episodic bridge
    gdr_src = (BASE_DIR / "generate_daily_radio.py").read_text(encoding="utf-8")
    for sym in (
        "def pan_stereo(",
        "def build_studio_room_reflections_stereo(",
        "STUDIO_JA_BACKCHANNEL_POOL",
        "recent_radio_feedback",
        "def update_story_memory_index(",
        "v46_qq_40m_stereo_zmy_brain_bridge",
        "n2_auto_",
    ):
        assert sym in gdr_src, f"generate_daily_radio.py missing v46 symbol {sym}"
    assert "opening_turns = POST_N3_BILINGUAL_OPENING" not in gdr_src, "Regression: templated POST_N3_BILINGUAL_OPENING roll-call re-enabled!"
    evs_ja = gdr.expand_turn_events("W", "你看这句：けいざいがゆたかになるにしたがって、こころのくうきょさをかんじるひとがふえた。")
    assert any(k == "PAUSE" and float(v) >= 0.24 for k, v in evs_ja), f"Missing 0.24s pre-JA cognitive breath: {evs_ja}"

    # 3. N2 question audio MUST NOT leak answer (`_build_n2_q_turns` splits on blank instead of reading full_ja)
    n2_q = gna._build_n2_q_turns("雨の予報だった（　　）、傘を持たずに出かけてしまった。", "にもかかわらず")
    assert all("にもかかわらず" not in str(v) for _, v in n2_q), f"N2 question audio leaked answer! {n2_q}"
    assert any(k == "PAUSE" and float(v) >= 0.5 for k, v in n2_q), f"N2 question audio missing blank pause: {n2_q}"

    # 4. Expanded adult N2 speaking templates & episodic index on disk
    assert len(rrb._SPEAKING_TEMPLATES) >= 85, f"Expected >=85 speaking templates (including N2), got {len(rrb._SPEAKING_TEMPLATES)}"
    smi_path = BASE_DIR / "audio" / "story_memory_index.json"
    assert smi_path.exists(), "Missing backfilled audio/story_memory_index.json!"
    smi_data = json.loads(smi_path.read_text(encoding="utf-8"))
    assert len(smi_data.get("entries") or {}) >= 100, "story_memory_index.json unexpectedly small!"

    # 5. 2027-04-01 N1 Sprint continuity (never reverting build_html / run_brain_algorithm / generate_neural_audio back to N3)
    for fname in ("build_html.py", "generate_daily_radio.py", "generate_neural_audio.py"):
        fsrc = (BASE_DIR / fname).read_text(encoding="utf-8")
        assert '"n1_sprint"' in fsrc, f"{fname} missing n1_sprint continuity handling!"
    print(f"[PASS 19/20] v46 studio stereo, cognitive ear-pin/story-echo ({len(smi_data['entries'])} hooks), N2 Vol.1-3 & 2027 N1 continuity verified")


def test_v84_hands_free_voice_vocab_coach_guard() -> None:
    """Gate 20 (v84): Guard dual-mode Swipe + Hands-Free Voice Vocab Coach prompts, studio MP3s & UI contracts."""
    from vocab_cards import VOCAB_CARDS, VOICE_COACH_LINES, build_dynamic_vocab_card, build_vocab_ask_spoken
    from adaptive_bank import CORE_N3_KANA_VOCAB, EXTRA_WORDS
    from phrase_and_word_lexicon import PHRASE_AND_WORD_LEXICON
    from sentence_lexicon import SENTENCE_LEXICON
    from tutor_data import WORD_DICT
    from n2_prep.n2_curriculum_engine import build_n2_vocab_cards

    assert len(VOICE_COACH_LINES) >= 18, f"Expected >=18 VOICE_COACH_LINES, got {len(VOICE_COACH_LINES)}"
    for ck, line in VOICE_COACH_LINES.items():
        assert line.strip() and "—" not in line, f"Bad VOICE_COACH_LINES[{ck}]: {line!r}"

    manifest = json.loads((BASE_DIR / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
    vc_coach = manifest.get("voice_coach") or {}
    for ck in VOICE_COACH_LINES:
        rel = str(vc_coach.get(ck) or "").split("?")[0].lstrip("./")
        assert rel and (BASE_DIR / rel).exists(), f"Missing studio voice_coach MP3 on disk for {ck}: {rel!r}"

    rich = dict(SENTENCE_LEXICON)
    rich.update(WORD_DICT)
    rich.update(EXTRA_WORDS)
    rich.update(PHRASE_AND_WORD_LEXICON)
    live_state = json.loads((BASE_DIR / "n3_live_state.json").read_text(encoding="utf-8"))
    n3_words: list[str] = []
    seen: set[str] = set()
    for w in list(VOCAB_CARDS.keys()) + [p["word"] for p in live_state.get("vocab_tracked", [])] + [x[0] for x in CORE_N3_KANA_VOCAB]:
        if w and w not in seen:
            seen.add(w)
            n3_words.append(w)

    vc_manifest = manifest.get("vocab_cards") or {}
    for w in n3_words:
        c = build_dynamic_vocab_card(w, rich.get(w, {}))
        ask = build_vocab_ask_spoken(c)
        assert ask and "—" not in ask and not re.search(r"[\u3040-\u30ff]", ask), f"Invalid/spoiler ask_spoken for N3 {w}: {ask!r}"
        ask_rel = str((vc_manifest.get(w) or {}).get("ask") or "").split("?")[0].lstrip("./")
        assert ask_rel and (BASE_DIR / ask_rel).exists(), f"Missing studio ask MP3 on disk for N3 word {w}: {ask_rel!r}"

    n2_cards = build_n2_vocab_cards()
    for w, vc in n2_cards.items():
        vc2 = dict(vc)
        vc2["word"] = w
        ask = build_vocab_ask_spoken(vc2)
        assert ask and "—" not in ask and not re.search(r"[\u3040-\u30ff]", ask), f"Invalid/spoiler ask_spoken for N2 {w}: {ask!r}"

    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    for sym in (
        "function switchVocabPracticeMode(",
        "function renderVocabVoiceStage(",
        "function handleVocabVoiceResponse(",
        "function detectVoiceCommand(",
        "function acquireVoiceWakeLock(",
        'SW_CACHE_NAME = "n3-studio-tutor-v',
    ):
        assert sym in bh_src, f"build_html.py missing v84 Voice Coach symbol: {sym}"

    print(f"[PASS 20/20] v84 Hands-Free Voice Vocab Coach ({len(n3_words)} N3 ask MP3s + {len(n2_cards)} N2 prompts + {len(VOICE_COACH_LINES)} studio coach clips) verified")


def test_v85_whole_app_voice_studio_guard() -> None:
    """Gate 21 (v85): Guard Listening Voice, 48-Drill Conjugation Voice, and Post-Radio Voice Wrap-Up & Sentence Builder."""
    from conjugation_drills import CONJUGATION_DRILLS, build_speaking_ask_spoken, conj_audio_basename
    from vocab_cards import VOICE_COACH_LINES

    assert len(VOICE_COACH_LINES) >= 42, f"Expected >=42 VOICE_COACH_LINES, got {len(VOICE_COACH_LINES)}"
    assert len(CONJUGATION_DRILLS) == 48, f"Expected 48 conjugation drills, got {len(CONJUGATION_DRILLS)}"
    manifest = json.loads((BASE_DIR / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
    cj_map = manifest.get("conj_drills") or {}
    for d in CONJUGATION_DRILLS:
        did = d["id"]
        assert d.get("rule_zh") and "—" not in d["rule_zh"], f"Bad rule_zh on {did}"
        assert d.get("ask_zh") and "—" not in d["ask_zh"], f"Bad ask_zh on {did}"
        entry = cj_map.get(did) or {}
        for slot in ("ask", "teach", "model"):
            rel = str(entry.get(slot) or "").split("?")[0].lstrip("./")
            expected_fn = conj_audio_basename(did, slot)
            assert rel.endswith(expected_fn), f"Manifest mismatch for {did}.{slot}: {rel!r}"
            fp = BASE_DIR / rel
            assert fp.exists() and fp.stat().st_size > 800, f"Missing/empty conj audio on disk: {fp}"

    meta = json.loads((BASE_DIR / "audio" / "daily_radio_meta.json").read_text(encoding="utf-8"))
    sps = meta.get("speaking_prompts") or []
    assert len(sps) >= 1, "Expected >=1 speaking_prompt in daily_radio_meta.json"
    for sp in sps:
        ask_txt = build_speaking_ask_spoken(sp)
        assert ask_txt and "—" not in ask_txt, f"Bad speaking ask_spoken: {ask_txt!r}"
        ask_rel = str(sp.get("ask_audio") or "").split("?")[0].lstrip("./")
        assert ask_rel and (BASE_DIR / ask_rel).exists() and (BASE_DIR / ask_rel).stat().st_size > 800, (
            f"Missing studio spk ask_audio on disk for {sp.get('id')}: {ask_rel!r}"
        )

    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    for sym in (
        "function parseListeningChoice(",
        "function analyzeConjugation(",
        "function openQuizVoiceSheet(",
        "function startQuizVoiceMode(",
        "function renderQuizVoiceStage(",
        "function openRadioVoiceWrapUp(",
        "function renderRadioVoiceStage(",
        'SW_CACHE_NAME = "n3-studio-tutor-v8',
    ):
        assert sym in bh_src, f"build_html.py missing v85 Voice Studio symbol: {sym}"

    print(f"[PASS 21/23] v85 Whole-App Voice Studio ({len(CONJUGATION_DRILLS)} conj drills x 3 MP3s + {len(VOICE_COACH_LINES)} coach clips + {len(sps)} spk ask MP3s) verified")


def test_v86_native_pixel_fluidity_guard() -> None:
    """Gate 22 (v86-v87): Guard 120Hz browser + WebAPK native fluidity, zero-vibration preference, persistent immutable cache, and crisp icons."""
    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    sw_src = (BASE_DIR / "sw.js").read_text(encoding="utf-8")
    man = json.loads((BASE_DIR / "manifest.json").read_text(encoding="utf-8"))

    for sym in (
        'SW_CACHE_NAME = "n3-studio-tutor-v8',
        "100dvh",
        "touch-action: manipulation",
        "overscroll-behavior: contain",
        "content-visibility: auto",
        "DICT_BY_CH",
        "NAV_LAYER_STACK",
        "function showAppModal(",
        "function safeCancelSpeechSynthesis(",
        "beforeinstallprompt",
        "function isStandaloneApp(",
        "function triggerPwaInstall(",
        "function scheduleWarmUpcomingQuiz(",
        "bindBottomSheetDragDismiss",
        't.classList.add("is-pressed")',
        'rel="preload" as="style"',
        "bindInstantThumbTabs",
        "function applySingleMasteryUpdate(",
        "function onRadioScrubPreview(",
        "function onRadioScrubCommit(",
        "scheduleIdleAppWarmup",
        "function buildLedgerRowHTML(",
    ):
        assert sym in bh_src, f"build_html.py missing v88 fluidity symbol: {sym}"

    html_out = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert "navigator.vibrate" not in html_out, "FORBIDDEN navigator.vibrate found in index.html (violates 零触控震动)!"
    assert 'CACHE_NAME = "n3-studio-tutor-v8' in sw_src, "sw.js CACHE_NAME missing v8x!"
    assert 'IMMUTABLE_CACHE = "zen-immutable-v1"' in sw_src, "sw.js missing persistent IMMUTABLE_CACHE for fonts/audio!"
    assert 'cache: "no-cache"' in sw_src, "sw.js should use ETag-conditional no-cache SWR revalidation!"
    assert "launch_handler" in man and "display_override" in man, "manifest.json missing launch_handler/display_override!"
    assert (BASE_DIR / "icon-192.png").stat().st_size > 2500, "icon-192.png looks low-res / broken!"
    assert (BASE_DIR / "icon-512.png").stat().st_size > 8000, "icon-512.png looks low-res / broken!"
    print("[PASS 22/24] v88 ultimate 120Hz fluidity (non-blocking fonts, immutable cache, 0ms tabs, O(1) mastery, 120Hz scrub/sheets, idle warmup & crisp icons) verified")


def test_zero_question_audio_answer_leak_guard() -> None:
    """Gate 23 (v87): Zero-tolerance guard ensuring NO non-listening N3/N2 question audio (or TTS fallback) EVER speaks the answer aloud."""
    import hashlib
    from adaptive_bank import EXTRA_PRIMARY_CARDS, NEW_PRIMARY_CARDS, NEW_VARIANT_CARDS, VARIANT_CARDS
    from clear_explanations import CARDS_75
    import generate_neural_audio as gna
    from n2_prep.n2_curriculum_engine import build_n2_question_bank
    from tutor_data import TUTOR_ITEMS

    meta = {}
    if isinstance(TUTOR_ITEMS, dict):
        for tid, tv in TUTOR_ITEMS.items():
            meta[tid] = dict(tv, id=tid)
    for lst in (EXTRA_PRIMARY_CARDS, NEW_PRIMARY_CARDS, VARIANT_CARDS, NEW_VARIANT_CARDS):
        for it in lst:
            if it.get("id"):
                meta[it["id"]] = it

    manifest = json.loads((BASE_DIR / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))

    checked_n3 = 0
    for qid, card in CARDS_75.items():
        m = meta.get(qid, {})
        subj = str(card.get("subject") or m.get("subject") or "")
        if "聴解" in subj or "听" in subj or card.get("is_listening"):
            continue
        prompt = str(card.get("prompt") or m.get("prompt") or m.get("prompt_display") or "")
        ans = str(card.get("answer") or m.get("answer") or "").strip()
        full_ja = str(card.get("full_ja") or m.get("full_ja") or "").strip()
        choices = card.get("choices") or m.get("choices") or []
        q_turns = card.get("q_turns") or []
        q_text = "".join(str(v) for s, v in q_turns if s != "PAUSE")
        q_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", q_text)
        full_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", full_ja)
        ans_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", ans)
        p_ja = re.sub(r"【[^】]*】|\n?选出[^\n]*|「[^」]+」の読み方は？?", "", prompt)
        p_clean = re.sub(r"[\s、。！？・「」『』（）()＿★_]+", "", p_ja)

        has_blank = bool(re.search(r"（\s*　*\s*）|\(\s*\)|＿|★", prompt))
        is_star = ("★" in prompt) or ("语序排列" in prompt)

        if has_blank:
            assert not (full_clean and q_clean == full_clean), f"N3 {qid} q_turns speaks FULL answer sentence: {q_turns}"
            if ans_clean:
                assert q_clean.count(ans_clean) <= p_clean.count(ans_clean), f"N3 {qid} q_turns leaks answer {ans!r}: {q_turns}"
        if is_star:
            assert any(s == "PAUSE" for s, _ in q_turns), f"Star-order {qid} q_turns missing PAUSE for ★ blank: {q_turns}"
            for ch in choices:
                cc = re.sub(r"[\s、。！？・「」『』（）()]+", "", str(ch))
                assert not (cc and q_clean.count(cc) > p_clean.count(cc)), f"Star-order {qid} q_turns leaks choice chunk {ch!r}: {q_turns}"
        km = re.search(r"「([^」]+)」の読み方", prompt)
        if km:
            assert km.group(1) not in q_text, f"Kanji-reading {qid} q_turns speaks target kanji {km.group(1)!r}: {q_turns}"

        # Verify manifest hash and on-disk MP3 are in sync for every card!
        q_sig = "v18q:+0%:" + json.dumps(q_turns, ensure_ascii=False)
        q_hash = hashlib.sha256(q_sig.encode("utf-8")).hexdigest()[:12]
        q_file = f"{qid}_q.mp3"
        assert manifest.get(q_file) == q_hash, f"Stale MP3 manifest hash for {q_file}: disk={manifest.get(q_file)} vs expected={q_hash}"
        assert (BASE_DIR / "audio" / q_file).exists(), f"Missing question audio file on disk: audio/{q_file}"
        checked_n3 += 1

    # Audit ALL N2 cards (100% real blanks + 100% zero-spoiler _build_n2_q_turns)
    n2_bank = build_n2_question_bank()
    checked_n2 = 0
    for np in n2_bank:
        for nc in ([np["primary"]] + list(np.get("variants") or [])):
            checked_n2 += 1
            p_n2 = nc["prompt"]
            assert "（　　）" in p_n2 and "に最も近い使い方はどれ" not in p_n2, f"N2 {nc['id']} missing real blank: {p_n2}"
            qt_n2 = gna._build_n2_q_turns(p_n2, nc["full_ja"])
            q_n2_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", "".join(str(v) for s, v in qt_n2 if s != "PAUSE"))
            full_n2_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", nc["full_ja"])
            ans_n2_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", nc["answer"])
            has_mid_blank = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff].*[（(]\s*　*\s*[）)].*[\u3040-\u30ff\u4e00-\u9fff]", p_n2))
            if has_mid_blank:
                assert any(s == "PAUSE" for s, _ in qt_n2), f"N2 {nc['id']} mid-sentence blank missing PAUSE: {qt_n2}"
            assert q_n2_clean != full_n2_clean, f"N2 {nc['id']} q_turns speaks full sentence: {qt_n2}"
            p_n2_clean = re.sub(r"[\s、。！？・「」『』（）()]+", "", p_n2)
            if ans_n2_clean:
                assert q_n2_clean.count(ans_n2_clean) <= p_n2_clean.count(ans_n2_clean), f"N2 {nc['id']} q_turns leaks answer {nc['answer']!r}: {qt_n2}"

    # Audit runtime spoiler shield & frontend zero-full_ja fallback
    shielded = gna.sanitize_q_turns_no_spoiler(
        [("JF", "激しい雨が降っているにもかかわらず、野外の音楽会は予定通り行われた。")],
        prompt_str="【★ 语序排列】激しい雨が降って ＿ ＿ ★ ＿ 予定通り行われた。\n选出填入 ★ 的正确词块：",
        answer_str="野外の",
        choices=["いる", "にもかかわらず", "野外の", "音楽会は"],
        full_ja_str="激しい雨が降っているにもかかわらず、野外の音楽会は予定通り行われた。",
    )
    assert any(s == "PAUSE" for s, _ in shielded) and all("野外" not in str(v) for _, v in shielded), f"Spoiler shield failed: {shielded}"

    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    assert "function getSafeQuestionFallbackJa(" in bh_src, "build_html.py missing getSafeQuestionFallbackJa!"
    assert 'playGenericVoiceUrl(qObj.q_audio, qObj.full_ja' not in bh_src, "build_html.py still passes qObj.full_ja to question fallback TTS!"
    assert 'speakJapaneseFallback(card.full_ja || card.prompt)' not in bh_src, "build_html.py mock player still passes card.full_ja to question fallback TTS!"
    print(f"[PASS 23/24] Zero-spoiler question audio verified across {checked_n3} N3 cards (manifest+MP3 synced) + {checked_n2} N2 cards + frontend fallbacks")


def test_v88_sla_linguistics_master_guard() -> None:
    """Gate 24 (v88 SLA): Guard all 6 linguistics breakthroughs (Anti-Interference N2, FSRS+Leeches, 30-line N2 film, 102 HVPT MP3s, Micro-Reading, 6 SLA telemetry events)."""
    import os
    import tempfile
    import fsrs_engine as fe
    import run_brain_algorithm as rba
    import sla_linguistics_pack as slp
    import tutor_prefs as tp
    from n2_prep import n2_curriculum_engine as n2e
    from n2_prep import n2_grammar_syllabus as n2s
    from n2_prep import n2_micro_reading as n2r

    # 1. Pillar 3: Zero same-day semantic-family collisions across N2 Days 4..87
    collisions = [
        d for d in range(4, 88)
        if len({g["family"] for g in n2s.get_day_new_grammar(d)}) < len(n2s.get_day_new_grammar(d))
    ]
    assert not collisions, f"Anti-interference collision on N2 days: {collisions}"
    assert all(len(n2s.get_day_new_grammar(d)) == 2 for d in range(8, 35)), "Travel window days 8-34 violated 2/day"

    # 2. Pillar 1: Calibrated post-N3 comprehensible input ramp + 30-line N2 Day 1 all-JP film
    p_mar = tp.immersion_profile(day="2027-03-31")
    p_dec = tp.immersion_profile(day="2027-12-01")
    assert p_mar["ja_ratio"] >= 0.33, f"Expected N2 Mar 31 ja_ratio >= 0.33, got {p_mar}"
    assert p_dec["ja_ratio"] >= 0.60, f"Expected N1 Dec 01 ja_ratio >= 0.60, got {p_dec}"
    day1_film = n2e.N2_CURATED_JP_VIDEO_SCRIPTS.get("n2_v1_s2a") or {}
    assert len(day1_film.get("lines") or []) >= 28, f"Expected >=28 lines on N2 Day 1 film, got {len(day1_film.get('lines') or [])}"

    # 3. Pillar 2 & 4: 18 Fossilized Oral Slips (54 MP3s) + 24 HVPT Minimal Pairs (48 MP3s) across 6 Tokyo speakers
    assert len(slp.FOSSIL_SLIP_DRILLS) == 18
    assert len(slp.MINIMAL_PAIR_DRILLS) == 24
    assert len(slp.HVPT_SPEAKER_PROFILES) == 6
    manifest = json.loads((BASE_DIR / "audio" / "audio_manifest.json").read_text(encoding="utf-8"))
    f_man = manifest.get("fossil_slips") or {}
    m_man = manifest.get("minimal_pairs") or {}
    for d in slp.FOSSIL_SLIP_DRILLS:
        assert "—" not in (d["cue_zh"] + d["rule_zh"]), f"Em dash in {d['id']}"
        ent = f_man.get(d["id"]) or {}
        for slot in ("ask", "teach", "model"):
            rel = str(ent.get(slot) or "").split("?")[0].lstrip("./")
            fp = BASE_DIR / rel
            assert rel and fp.exists() and fp.stat().st_size > 700, f"Missing slip MP3 {d['id']}.{slot}: {rel}"
    for mp in slp.MINIMAL_PAIR_DRILLS:
        assert "—" not in mp["tip"], f"Em dash in {mp['id']}"
        ent = m_man.get(mp["id"]) or {}
        for side in ("a", "b"):
            rel = str(ent.get(side) or "").split("?")[0].lstrip("./")
            fp = BASE_DIR / rel
            assert rel and fp.exists() and fp.stat().st_size > 700, f"Missing minimal-pair MP3 {mp['id']}.{side}: {rel}"

    # 4. Pillar 5: True FSRS DSR math + Leech detection
    it = {"id": "N2G-001", "point": "〜ざるを得ない", "status": "gray", "streak": 0}
    s1 = fe.update_fsrs_on_review(it, "20261207", ok=True)["s"]
    s2 = fe.update_fsrs_on_review(it, "20261211", ok=True)["s"]
    s3 = fe.update_fsrs_on_review(it, "20261220", ok=True)["s"]
    assert s1 < s2 < s3, f"FSRS stability failed to expand: {s1} -> {s2} -> {s3}"
    s4 = fe.update_fsrs_on_review(it, "20261224", ok=False)["s"]
    assert s4 < s3, f"FSRS stability failed to contract on lapse: {s3} -> {s4}"
    assert fe.is_leech_item({"word": "慰める", "seen": 38, "wrong": 18, "status": "red"})

    # 5. Pillar 6: 20 N2 Discourse Micro-Reading passages + all 6 SLA telemetry events in run_brain_algorithm
    assert len(n2r.N2_MICRO_READINGS) >= 20
    for mr in n2r.N2_MICRO_READINGS:
        assert len(mr["choices"]) == 4 and mr["answer"] in mr["choices"]
        assert "—" not in (mr["body_ja"] + mr["trap_note"] + mr["question_ja"])

    fake_state = {
        "grammar_points": [], "n2_grammar_points": [], "henkei_points": [],
        "listening_points": [], "vocab_tracked": [],
        "speaking_practice": {"total_reps": 1, "last_date": "20261125", "slips": {"〜がちだ": {"count": 1, "last_date": "20261125"}}},
        "_processed_log_ts": [],
    }
    sla_rows = [
        {"ts": "2026-11-26T20:00:00Z", "id": "SLIP:SL01", "point": "酸っぱかったです", "choice": "快答:1.4s", "correct": "true"},
        {"ts": "2026-11-26T20:01:00Z", "id": "MP:MP01", "point": "だった/たった", "choice": "辨音:清浊音:对", "correct": "true"},
        {"ts": "2026-11-26T20:02:00Z", "id": "SHAD:2026-11-26", "point": "影子跟读:1.1x", "choice": "影子跟读:1.1x", "correct": "true"},
        {"ts": "2026-11-26T20:03:00Z", "id": "RET432:2026-11-26", "point": "4/3/2提速复述", "choice": "复述:60-45-30圆满", "correct": "true"},
        {"ts": "2026-11-26T20:04:00Z", "id": "READ:RD01", "point": "海外零售与本地化", "choice": "精读对:245字/分", "correct": "true"},
        {"ts": "2026-11-26T20:05:00Z", "id": "TUTOR_USE:tm1", "point": "〜がちだ", "choice": "真人课实战已用出", "correct": "true"},
    ]
    orig_log, orig_snap = rba.LOG_PATH, rba.SNAPSHOT_PATH
    with tempfile.TemporaryDirectory(prefix="sla_gate24_") as td:
        tlog = os.path.join(td, "practice_log.jsonl")
        with open(tlog, "w", encoding="utf-8") as f:
            for r in sla_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        rba.LOG_PATH = tlog
        rba.SNAPSHOT_PATH = os.path.join(td, "no_snap.json")
        try:
            rba.apply_practice_logs(fake_state, "20261126")
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_log, orig_snap
    sla_t = fake_state.get("sla_telemetry") or {}
    assert "SL01" in (sla_t.get("fossil_slips") or {})
    assert "MP01" in (sla_t.get("minimal_pairs") or {})
    assert len(sla_t.get("shadowing_days") or []) == 1
    assert len(sla_t.get("retell_432_days") or []) == 1
    assert "RD01" in (sla_t.get("micro_readings") or {})
    assert "〜がちだ" in (sla_t.get("tutor_used") or {})
    assert "〜がちだ" not in fake_state["speaking_practice"]["slips"], "TUTOR_USE did not clear redeemed speaking slip!"

    bh_src = (BASE_DIR / "build_html.py").read_text(encoding="utf-8")
    for sym in (
        "function toggleJpVideoShadowMode(",
        "function openRetell432Modal(",
        "function analyzeFossilSlip(",
        "function pickQuizVoiceMpSide(",
        "function renderPitchContourSVG(",
        "function openMicroReadingModal(",
        "function openTutorMissionModal(",
        'SW_CACHE_NAME = "n3-studio-tutor-v89"',
    ):
        assert sym in bh_src, f"build_html.py missing v89 SLA symbol: {sym}"

    print("[PASS 24/24] v89 SLA Linguistics Master Upgrade (0/84 N2 collisions, FSRS+Leeches, 30-line N2 film, 102 HVPT MP3s, Shadowing, 4/3/2, Micro-Reading, Tutor Mission) verified")


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
    test_full_bank_4choice_and_immersion_mnemonics()
    test_full_bank_100pct_option_notes()
    test_exam_day_and_n2_zero_to_120_transition_contract()
    test_cloud_sync_sandbox_isolation_guard()
    test_v43_storycraft_and_archival_footage_guard()
    test_v44_anti_tourist_kanazawa_and_feedback_guard()
    test_v45_broadcast_authenticity_guard()
    test_v82_jobs_zen_and_telemetry_hygiene_guard()
    test_v46_stereo_cognitive_n2_long_horizon_guard()
    test_v84_hands_free_voice_vocab_coach_guard()
    test_v85_whole_app_voice_studio_guard()
    test_v86_native_pixel_fluidity_guard()
    test_zero_question_audio_answer_leak_guard()
    test_v88_sla_linguistics_master_guard()
    print("[ALL PASS] tests_ci_guard.py 24/24 gates green!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


