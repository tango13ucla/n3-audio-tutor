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
    print(f"[PASS 1/6] Static AST syntax & undefined-name check ({len(py_files)} Python files)")


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
        log_file = pathlib.Path(td) / "practice_log.jsonl"
        snap_file = pathlib.Path(td) / "cloud_state_snapshot.json"
        log_file.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in synthetic_records) + "\n", encoding="utf-8")
        snap_file.write_text("{}", encoding="utf-8")

        orig_rba_log, orig_rba_snap = rba.LOG_PATH, rba.SNAPSHOT_PATH
        orig_aadc_log, orig_aadc_snap = aadc.LOG_PATH, aadc.SNAP_PATH
        try:
            rba.LOG_PATH = str(log_file)
            rba.SNAPSHOT_PATH = str(snap_file)
            aadc.LOG_PATH = log_file
            aadc.SNAP_PATH = snap_file

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
    print("[PASS 2/6] apply_practice_logs & collect_study_history all-event-types test")


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
    print(f"[PASS 3/6] Frontend<->Backend choice contract sync ({len(rv_labels)} RV + {len(ga_labels)} GA labels)")


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
    print(f"[PASS 4/6] Dynamic vocab cards Self-test 4 invariants ({len(checked)} words incl. all 236 immersion words)")


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
    print(f"[PASS 5/6] Speaking prompts Self-test 9 invariants ({len(rrb._SPEAKING_TEMPLATES)} templates + fallback stress)")


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
    print(f"[PASS 6/6] Workflow radio version guard aligned (v{max_gen_ver} across {len(wf_files)} workflows)")


def main() -> int:
    test_all_python_files_syntax_and_names()
    test_apply_practice_logs_all_event_types()
    test_frontend_backend_choice_contract()
    test_dynamic_vocab_cards_self_test4_invariants()
    test_speaking_prompts_self_test9_invariants()
    test_workflows_radio_version_alignment()
    print("[ALL PASS] tests_ci_guard.py 6/6 gates green!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
