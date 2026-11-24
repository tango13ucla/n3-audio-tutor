#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fast CI & Pre-Push Guard for n3-audio-tutor (zero external dependencies).
Prevents cold-branch NameErrors (like the 2026-11-24 `SPK:` `is_correct` bug)
and workflow/radio version-check drift from ever blocking daily refreshes again.
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
    print(f"[PASS] Static AST syntax & undefined-name check ({len(py_files)} Python files)")


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
        {"ts": "2026-11-24T06:00:08Z", "id": "RV:3", "point": "〜に関して", "choice": "听后复盘:快过存疑", "correct": "true"},
        {"ts": "2026-11-24T06:00:09Z", "id": "GA-G-001", "point": "〜につれて", "choice": "盘点:本能", "correct": "true"},
        {"ts": "2026-11-24T06:00:10Z", "id": "GA-G-116a", "point": "尊敬語", "choice": "盘点:陌生", "correct": "false"},
        {"ts": "2026-11-24T06:00:11Z", "id": "VC-辞書", "point": "辞書", "choice": "记词:没记住", "correct": "false"},
        {"ts": "2026-11-24T06:00:12Z", "id": "FLASH-暖簾", "point": "暖簾", "choice": "闪卡:顺过", "correct": "true"},
        {"ts": "2026-11-24T06:00:13Z", "id": "N3-G1", "point": "〜に関して", "choice": "に関して", "correct": "true", "ask_again": "false"},
        {"ts": "2026-11-24T06:00:14Z", "id": "N3-G2", "point": "〜べきではない", "choice": "不确定", "correct": "false", "ask_again": "true"},
        {"ts": "2026-11-24T06:00:15Z", "id": "GROK-1", "point": "〜につれて", "choice": "Grok:还是要考", "correct": "true", "ask_again": "true", "source": "grok"},
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
            assert "辞書" in (state.get("word_lookups") or {}), "Expected lookup recorded"

            _, ever_seen, missed, missed_v, lookups = aadc.collect_study_history(cutoff_study_day="2026-11-24")
            for bad_prefix in ("SPK:", "RV:", "HES:", "LK:", "GA-", "VC-", "GROK-"):
                assert not any(c.startswith(bad_prefix) for c in ever_seen), f"ever_seen polluted with {bad_prefix}: {ever_seen}"
            assert "N3-G1" in ever_seen and "N3-G2" in ever_seen
            assert "辞書" in (missed_v.get("2026-11-23") or missed_v.get("2026-11-24") or [])
        finally:
            rba.LOG_PATH, rba.SNAPSHOT_PATH = orig_rba_log, orig_rba_snap
            aadc.LOG_PATH, aadc.SNAP_PATH = orig_aadc_log, orig_aadc_snap
    print("[PASS] apply_practice_logs & collect_study_history all-event-types test")


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
    print(f"[PASS] Workflow radio version guard aligned (v{max_gen_ver} across {len(wf_files)} workflows)")


def main() -> int:
    test_all_python_files_syntax_and_names()
    test_apply_practice_logs_all_event_types()
    test_workflows_radio_version_alignment()
    print("[ALL PASS] tests_ci_guard.py green!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
