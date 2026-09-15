"""Offline checks of the research boundaries, using tiny repositories and payloads."""

import base64
import copy
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from cpp_loc import audit, extract, filters, gitutil, integrity, leakage, reports, splits
from cpp_loc.provenance import assistance, chronology, identity, json_bytes, sha256, task_kind
from cpp_loc.schema import validate_runner
from scripts.prepare import file_hashes, runner_row, verify_manifest, write_json, write_rows
from tests.conftest import commit, git
from tests.test_schema import make


def candidate(inst="r__1", date="2025-01-01T00:00:00Z", report="1", repo="o/r"):
    row = asdict(make(instance_id=inst, repo=repo, problem_statement="Bug: a.c crashes"))
    row["fix_commit"] = sha256(inst)[:40]
    row["metadata"]["integrity"] = {
        "git": {
            "errors": [],
            "committer_at": date,
            "primary_files": ["a.c"],
            "changes": [{"status": "M", "old_path": "a.c", "new_path": "a.c"}],
            "base_files_present": ["a.c"],
            "backports": [],
            "fixes_targets": [],
        },
        "reports": {
            "selected": {"task": {"kind": "bug"}, "annotation": {"kind": "explicit_bug_report"}},
            "references": [{"state": "report", "identity": repo + "|" + report}],
            "historical_selected_identity": repo + "|" + report,
        },
        "chronology": {k: {"state": "supported-pre-fix"} for k in ("creation", "text_version")},
        "ai_assisted": {"status": "not-observed"},
    }
    ev = splits.evidence(row)
    ev["eligibility"] = integrity.eligibility(row, ev)
    return row


def cache_payload(src, ref, payload):
    src.cache_path(ref).write_text(json.dumps(payload), encoding="utf-8")


def test_process_enrichment_matches_threads_with_cached_reports_and_missing_refs(
    synthetic_repo, tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from scripts import prepare

    repo, shas = synthetic_repo
    clones = tmp_path / "clones"
    clones.mkdir()
    (clones / "llvm").symlink_to(repo, target_is_directory=True)
    src = reports.GitHub(clones / "cache", "llvm/llvm-project", None)
    cache_payload(
        src,
        "1",
        {
            "title": "Bug: crash",
            "body": "drivers/foo.c crashes",
            "labels": [],
            "number": 1,
            "html_url": "https://github.com/llvm/llvm-project/issues/1",
        },
    )
    row = asdict(
        make(
            repo="llvm/llvm-project",
            base_commit=shas["initial"],
            fix_commit=shas["fix"],
            problem_statement="Bug: crash\n\ndrivers/foo.c crashes",
            metadata={"report_refs": {"github_issue": ["1", "2"]}},
        )
    )
    source = tmp_path / "inputs"
    source.mkdir()
    write_rows(source, "instances", [row])
    # The fix exists locally but is deliberately outside the pinned upstream revision.
    (source / "COMMAND.txt").write_text("upstream HEAD: " + shas["initial"] + "\n")
    monkeypatch.setattr(prepare, "implementation", lambda: {"revision": "same-code"})
    for mode in (False, True):
        prepare.enrich_command(
            SimpleNamespace(
                repo="llvm",
                input=source,
                out=tmp_path / str(mode),
                repos_dir=clones,
                reports_only=False,
                workers=2,
                processes=mode,
            )
        )
    assert file_hashes(tmp_path / "False") == file_hashes(tmp_path / "True")
    enriched = prepare.load_rows(tmp_path / "True", "records-*.jsonl")[0]
    evidence = splits.evidence(enriched)
    assert "fix_outside_pinned_upstream" in evidence["eligibility"]["excluded"]
    assert evidence["reports"]["selected"] is not None
    assert {r["state"] for r in evidence["reports"]["references"]} == {
        "report",
        "offline_cache_miss",
    }
    assert len(prepare.load_rows(tmp_path / "True", "payloads-*.jsonl")) == 1


def test_messages_reverts_roots_and_filename_boundaries(synthetic_repo):
    message = (
        "subj\n\nRevert the temporary option before retrying.\n\n"
        "Co-authored-by: Alice\nCo-authored-by: Claude <bot@x>\n"
        "Assisted-by: Codex\n  second line\nClaude-Session: https://example/session\n"
    )
    parsed = filters.message_evidence(message)
    assert parsed["raw"] == message
    assert [t["key"] for t in parsed["trailers"]].count("Co-authored-by") == 2
    assert parsed["trailers"][2]["value"] == "Codex\n  second line"
    assert parsed["removed_lines"][-1]["text"].endswith("\n")
    assert "second line" not in parsed["stripped"]
    assert not filters.is_revert(message)
    assert filters.is_revert("Revert x\n\nbody")
    assert filters.is_revert("undo x\n\nThis reverts commit abcdef.")
    assert assistance(message)["status"] == "observed"
    assert assistance("Co-authored-by: Alice\n")["status"] == "not-observed"
    assert assistance(None)["status"] == "unknown"
    assert not leakage.flags("stdio.c", ["lib/io.c"], "")["basename"]
    assert leakage.flags("lib/io.c:123", ["lib/io.c"], "")["basename"]
    repo, shas = synthetic_repo
    funnel = {}
    list(
        extract.mine(
            repo, "r", "o/r", since=None, references=lambda _: ["1"], refs={}, funnel=funnel
        )
    )
    assert funnel["root commits skipped"] == 1
    assert gitutil.commit_info(repo, shas["fix"])["message"].endswith("https://example.com\n")


@pytest.mark.parametrize("path", ["src/foo.inc", "a.inl", "a.ipp", "a.tpp", "a.tcc"])
def test_inline_fragment_scope(path):
    assert filters.is_target_path(path)
    assert not filters.is_target_path("tests/" + path)


@pytest.mark.parametrize("path", ["a.td", "a.dts", "CMakeLists.txt", "x.py", "tests/a.cpp"])
def test_secondary_changes_not_primary(path):
    assert not filters.is_target_path(path)


@pytest.mark.parametrize(
    "status,old,new",
    [("A", None, "a.c"), ("D", "a.c", None), ("R100", "a.c", "b.c"), ("T", "a.c", "a.c")],
)
def test_unsupported_target_changes_are_not_silently_projected_away(status, old, new):
    row = candidate()
    ev = splits.evidence(row)
    ev["git"]["changes"] = [{"status": status, "old_path": old, "new_path": new}]
    result = integrity.eligibility(row, ev)
    assert "unsupported_target_status" in result["excluded"]
    assert not result["strict_local"]


def test_added_regression_test_allowed_but_extra_non_target_changes_are_visible():
    row = candidate()
    ev = splits.evidence(row)
    ev["git"]["changes"].append({"status": "A", "old_path": None, "new_path": "tests/test.c"})
    result = integrity.eligibility(row, ev)
    assert result["strict_local"] and result["all_non_test_changes_in_scope"]
    ev["git"]["changes"].append({"status": "M", "old_path": "a.td", "new_path": "a.td"})
    result = integrity.eligibility(row, ev)
    assert result["strict_local"] and not result["all_non_test_changes_in_scope"]
    assert len(result["non_target_changes"]) == 2


def test_real_git_statuses_and_base_existence(synthetic_repo):
    repo, shas = synthetic_repo
    row = asdict(make(base_commit=shas["initial"], fix_commit=shas["fix"]))
    ev = integrity.git_evidence(row, repo, shas["too_many"])
    assert ev["errors"] == []
    assert ev["primary_files"] == ["drivers/foo.c", "drivers/foo.h"]
    assert ev["base_files_present"] == ["drivers/foo.c"]
    assert {c["status"] for c in ev["changes"]} == {"M", "A"}
    assert ev["stable_patch_id"]
    base = gitutil.head(repo)
    git(repo, "mv", "drivers/foo.c", "drivers/renamed file.c")
    fix = commit(repo, "move source", {}, "2024-01-01T00:00:00Z")
    changes = gitutil.changes(repo, base, fix)
    assert changes == [
        {"status": "D", "old_path": "drivers/foo.c", "new_path": None},
        {"status": "A", "old_path": None, "new_path": "drivers/renamed file.c"},
    ]
    assert gitutil.parse_changes("R100\0old name.c\0new\tname.c\0")[0]["new_path"] == "new\tname.c"
    with pytest.raises(ValueError):
        gitutil.parse_changes("R100\0old.c\0")


def test_incremental_inventory_equals_full_base_trees(synthetic_repo):
    repo, shas = synthetic_repo
    inventory = gitutil.TreeInventory(repo)
    for sha in [shas["initial"], shas["fix"], shas["too_many"], shas["test_only"], shas["initial"]]:
        inventory.at(sha)
        full = gitutil.tree_files(repo, sha)
        assert inventory.paths == set(full)
        report = "drivers/foo.c:2 drivers/foo.h tools/testing/selftests/foo_test.c"
        assert audit.predict(
            report, inventory.paths, basename_index=inventory.basenames
        ) == audit.predict(report, full)
    (repo / "drivers/foo.c").unlink()
    (repo / "drivers/foo.c").symlink_to("foo.h")
    sha = commit(repo, "change source type", {}, "2026-01-01T00:00:00Z")
    inventory.at(sha)
    assert inventory.paths == set(gitutil.tree_files(repo, sha))
    assert "drivers/foo.c" not in inventory.paths


def test_tree_inventory_handles_more_paths_than_os_argument_limit(synthetic_repo):
    repo, shas = synthetic_repo
    paths = [f"missing/{i:06d}/" + "x" * 100 + ".cpp" for i in range(4000)]
    paths.append("drivers/foo.c")
    assert gitutil.tree_files(repo, shas["initial"], paths) == ["drivers/foo.c"]


def test_commit_metadata_does_not_need_merge_tree_blobs(synthetic_repo):
    repo, shas = synthetic_repo
    tree = git(repo, "rev-parse", shas["fix"] + "^{tree}").strip()
    merge = gitutil.run(
        repo,
        "commit-tree",
        tree,
        "-p",
        shas["initial"],
        "-p",
        shas["fix"],
        input="merge metadata fixture\n",
    ).strip()
    blob = git(repo, "rev-parse", shas["fix"] + ":drivers/foo.c").strip()
    (repo / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    info = gitutil.commit_info(repo, merge)
    assert info["parents"] == [shas["initial"], shas["fix"]]
    assert info["message"] == "merge metadata fixture\n"


def test_invalid_external_paths_and_duplicate_labels_survive_optimization():
    row = candidate()
    ev = splits.evidence(row)
    ev["git"]["primary_files"] = ["../a.c", "../a.c"]
    errors = integrity.eligibility(row, ev)["excluded"]
    assert "invalid_path" in errors and "duplicate_primary_paths" in errors
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    code = (
        "from tests.test_preparation import candidate; "
        "from cpp_loc import integrity, splits; "
        "r=candidate(); e=splits.evidence(r); e['git']['primary_files']=['../a.c']; "
        "raise SystemExit(0 if 'invalid_path' in integrity.eligibility(r,e)['excluded'] else 3)"
    )
    subprocess.run([sys.executable, "-O", "-c", code], env=env, check=True)


def test_cache_offline_miss_never_fetches_and_old_fetch_time_stays_unknown(tmp_path, monkeypatch):
    src = reports.GitHub(tmp_path, "o/r", None)
    src.offline = True
    monkeypatch.setattr(src, "fetch", lambda _: pytest.fail("offline fetch"))
    assert src.report("1") == "offline cache miss"
    payload = {
        "number": 2,
        "title": "Crash",
        "body": "repro",
        "html_url": "https://github.com/o/r/issues/2",
    }
    cache_payload(src, "2", payload)
    evidence = src.report("2")[2]["report_provenance"]
    assert evidence["payload"]["fetched_at"] is None
    assert evidence["raw_text_sha256"] == sha256("Crash\n\nrepro")
    assert not src.cache_path("2").with_suffix(".fetch.json").exists()
    src.offline = False
    monkeypatch.setattr(src, "fetch", lambda _: payload)
    src.get("3")
    fetch = json.loads(src.cache_path("3").with_suffix(".fetch.json").read_text())
    assert fetch["fetched_at"] and set(fetch) == {"fetched_at", "sha256"}


def test_feature_and_multi_issue_ambiguity_distinguish_pull_requests(tmp_path):
    src = reports.GitHub(tmp_path, "o/r", None)
    src.offline = True
    row = candidate()
    row["metadata"]["report_refs"] = {"github_issue": ["1", "2"]}
    cache_payload(
        src,
        "1",
        {
            "title": "Bug: a.c crashes",
            "body": "",
            "html_url": "https://github.com/o/r/issues/1",
            "number": 1,
        },
    )
    cache_payload(src, "2", {"title": "PR", "pull_request": {}})
    refs = integrity.all_reports(row, [src], "Fixes #1; Closes #2")
    assert [r["state"] for r in refs["references"]] == ["report", "pull_request"]
    ev = splits.evidence(row)
    ev["reports"] = refs
    assert "multiple_report_references" not in integrity.eligibility(row, ev)["excluded"]
    cache_payload(
        src,
        "2",
        {
            "title": "Bug: other crash",
            "body": "",
            "html_url": "https://github.com/o/r/issues/2",
            "number": 2,
        },
    )
    ev["reports"] = integrity.all_reports(row, [src], "Fixes #1; Closes #2")
    assert "multiple_report_references" in integrity.eligibility(row, ev)["excluded"]
    assert task_kind("parse ISO 8601 duration", "", ["feature"], "Feature")["kind"] == "feature"
    ev["reports"]["selected"]["task"]["kind"] = "feature"
    assert "task_feature" in integrity.eligibility(row, ev)["excluded"]
    assert task_kind("something", "", [], None)["kind"] == "unknown"
    assert task_kind("LOGICAL_ERROR", "", ["experimental feature"], None)["kind"] == "unknown"
    assert task_kind("crash", "", ["experimental feature"], None)["kind"] == "bug"
    assert task_kind("new capability", "", ["type: feature"], None)["kind"] == "feature"


def test_creation_does_not_certify_consumed_issue_body():
    report = {"created_at": "2024-01-01T00:00:00Z", "resource_updated_at": "2026-01-01T00:00:00Z"}
    checks = chronology(report, "2025-01-01T00:00:00Z")
    assert checks["creation"]["state"] == "supported-pre-fix"
    assert checks["text_version"]["state"] == "unknown"
    assert checks["resource_updated_after_fix"]
    report["resource_updated_at"] = "2024-12-31T00:00:00Z"
    assert (
        chronology(report, "2025-01-01T00:00:00Z")["text_version"]["state"] == "supported-pre-fix"
    )
    assert chronology(report, None)["creation"]["state"] == "unknown"
    assert chronology(report, "2025-01-01")["creation"]["state"] == "unknown"
    assert chronology(report, "2023-01-01T00:00:00Z")["text_version"]["state"] == "post-fix"


def test_mail_and_syzbot_exact_selection_evidence(tmp_path):
    src = reports.Lore(tmp_path, offline=True)
    ref = "https://lore.kernel.org/r/abc%40x/"
    cache_payload(
        src,
        ref,
        base64.b64encode(
            b"Subject: [BUG] crash\nMessage-ID: <abc@x>\n"
            b"Date: Tue, 1 Jan 2024 10:00:00 +0000\n\ncrash repro\n> quoted patch\n-- \nsig\n"
        ).decode(),
    )
    ev = src.report(ref)[2]["report_provenance"]
    assert ev["selected_id"] == "abc@x" and "> quoted patch" in ev["raw_text"]
    assert chronology(ev, "2025-01-01T00:00:00Z")["text_version"]["state"] == "supported-pre-fix"
    assert identity("lore_report", ref, "o/r") == identity(
        "lore_report", "http://lore.kernel.org/all/abc@x/T/#u", "o/r"
    )
    assert identity("pgsql_archive", "http://postgr.es/m/x%40y", "p/p") == identity(
        "pgsql_archive", "https://www.postgresql.org/message-id/flat/x@y", "p/p"
    )
    syz = reports.Syzbot(tmp_path, offline=True)
    cache_payload(
        syz,
        "extid=abc",
        {
            "bug": {
                "id": "canonical",
                "title": "crash",
                "first-crash": "2024-01-01T00:00:00Z",
                "crashes": [{"crash-report-link": "/text?id=late"}],
            },
            "report": "stack",
        },
    )
    ev = syz.report("extid=abc")[2]["report_provenance"]
    assert ev["selected_id"] == "/text?id=late" and ev["selected_crash_at"] is None
    assert chronology(ev, "2025-01-01T00:00:00Z")["text_version"]["state"] == "unknown"


def test_shared_reports_backports_patch_ids_and_shared_fixes_targets():
    rows = [candidate("r__" + str(i), report=str(i)) for i in range(7)]
    splits.evidence(rows[1])["reports"] = copy.deepcopy(splits.evidence(rows[0])["reports"])
    splits.evidence(rows[2])["git"]["backports"] = [{"sha": rows[0]["fix_commit"]}]
    for row in rows[3:5]:
        splits.evidence(row)["git"]["stable_patch_id"] = "same-exact-patch"
    for row in rows[5:]:
        splits.evidence(row)["git"]["fixes_targets"] = [{"sha": "same-introducer"}]
    grouped = splits.groups(rows)
    membership = grouped["membership"]
    assert membership["r__0"] == membership["r__1"] == membership["r__2"]
    assert membership["r__3"] == membership["r__4"]
    assert membership["r__5"] != membership["r__6"]
    assert grouped["shared_fixes_targets_not_grouped"]
    assert json_bytes(grouped) == json_bytes(splits.groups(list(reversed(rows))))
    alien = candidate("alien__1", repo="other/repo")
    splits.evidence(alien)["git"]["stable_patch_id"] = "same-exact-patch"
    assert splits.groups(rows + [alien])["membership"]["alien__1"] != membership["r__3"]


def test_grouping_precedes_filtering_and_quarantines_year_and_buffer_crossings():
    rows = [
        candidate("old", "2025-06-02T00:00:00Z", "139380"),
        candidate("future", "2026-06-29T00:00:00Z", "139380"),
        candidate("buffer", "2026-04-01T00:00:00Z", "other"),
        candidate("buffer_partner", "2025-02-01T00:00:00Z", "other"),
    ]
    splits.evidence(rows[1])["eligibility"]["excluded"] = ["task_feature"]
    result = splits.split(
        rows,
        splits.groups(rows),
        splits.config(test_end="2026-09-01T00:00:00Z", role="evaluation-only", view="diagnostic"),
    )
    assert all(
        "group_crosses_temporal_partition" in a["reasons"] for a in result["membership"].values()
    )


def test_latest_dev_groups_do_not_cross_training_and_insufficient_yield_refuses(tmp_path):
    rows = [candidate(str(i), f"2025-01-{i:02d}T00:00:00Z", str(i)) for i in range(1, 7)]
    splits.evidence(rows[2])["reports"] = copy.deepcopy(splits.evidence(rows[5])["reports"])
    cfg = splits.config(test_end="2026-09-01T00:00:00Z", dev_size=2, view="diagnostic")
    grouped = splits.groups(rows)
    result = splits.split(rows, grouped, cfg)
    assert result["counts"] == {"train": 2, "excluded": 2, "dev": 2}
    assert result["membership"]["3"]["reasons"] == ["group_crosses_train_dev"]
    assert result["membership"]["6"]["reasons"] == ["group_crosses_train_dev"]
    assert {i for i, a in result["membership"].items() if a["partition"] == "dev"} == {"4", "5"}
    again = splits.split(list(reversed(rows)), splits.groups(list(reversed(rows))), cfg)
    assert json_bytes(result) == json_bytes(again)
    for name, manifest in [("a", result), ("b", again)]:
        directory = tmp_path / name
        directory.mkdir()
        write_json(directory / "manifest.json", manifest)
        write_rows(
            directory,
            "dev",
            [
                runner_row(r)
                for r in rows
                if manifest["membership"][r["instance_id"]]["partition"] == "dev"
            ],
        )
    assert file_hashes(tmp_path / "a") == file_hashes(tmp_path / "b")
    bad = splits.split(rows, grouped, splits.config(test_end="2026-09-01T00:00:00Z"))
    assert bad["status"] == "refused" and bad["counts"] == {"excluded": 6}


def test_half_open_cutoffs_unknown_times_and_explicit_end():
    cfg = splits.config(test_end="2026-09-01T00:00:00Z")
    assert splits.partition(cfg["pool_start"], cfg) == "pool"
    assert splits.partition(cfg["buffer_start"], cfg) == "buffer"
    assert splits.partition(cfg["test_start"], cfg) == "test"
    assert splits.partition(cfg["test_end"], cfg) == "after_test"
    assert splits.partition(None, cfg) == "unknown_time"
    row = candidate(date=None)
    result = splits.split(
        [row], splits.groups([row]), splits.config(test_end=cfg["test_end"], role="evaluation-only")
    )
    assert "group_time_unknown" in result["membership"][row["instance_id"]]["reasons"]
    with pytest.raises(ValueError):
        splits.config(test_end="2026-09-01")


def test_training_minimum_is_enforced_after_iterative_dev_quarantine():
    rows = [candidate(str(i), f"2025-01-{i:02d}T00:00:00Z", str(i)) for i in range(1, 7)]
    rows.append(candidate("test", "2026-07-01T00:00:00Z", "test"))
    splits.evidence(rows[2])["reports"] = copy.deepcopy(splits.evidence(rows[5])["reports"])
    grouped = splits.groups(rows)
    cfg = splits.config(
        test_end="2026-09-09T00:00:00Z", view="diagnostic", dev_size=2, min_train_size=3
    )
    result = splits.split(rows, grouped, cfg)
    assert result["status"] == "refused"
    assert result["eligible_before_train_dev"]["pool"] == 6
    assert result["eligible_before_dev"] == {"pool": 4, "test": 1}
    assert (
        result["refusal"]
        == "need 2 dev records plus at least 3 training records; only 4 eligible pool records"
    )
    assert result["counts"] == {"excluded": 7}
    accepted = splits.split(rows, grouped, {**cfg, "min_train_size": 2})
    assert accepted["counts"] == {"train": 2, "dev": 2, "excluded": 2, "test": 1}
    with pytest.raises(ValueError, match="min_train_size must be positive"):
        splits.config(test_end=cfg["test_end"], min_train_size=0)


def test_baseline_is_gold_blind_keeps_incorrect_predictions_and_failures():
    tree = ["src/io.c", "src/stdio.c", "src/a.cpp", "else/a.cpp", "tests/test.c"]
    text = "see /build/project/src/io.c:123 and src/stdio.c:4; a.cpp; tests/test.c"
    predicted = audit.predict(text, tree)
    assert predicted == ["src/io.c", "src/stdio.c"]
    assert audit.predict(r"C:\work\src\io.c:12", tree) == ["src/io.c"]
    assert audit.predict("a.cpp", tree) == []
    assert audit.predict("stdio.c", tree, unique_basename=False) == []
    assert audit.score(predicted, ["src/io.c"])["precision"] == 0.5
    assert audit.score(predicted, ["unrelated.c"])["precision"] == 0
    assert audit.predict(text, tree) == predicted  # changing gold cannot change predictions
    assert audit.score([], ["src/io.c"])["f1"] == 0
    row = candidate()
    failed = audit.baseline_result(row, None, "tree missing")
    summary = audit.baseline_summary([failed])["slices"]["all"]
    assert summary["n"] == 1 and summary["f1"] == 0
    assert summary["status_counts"] == {"inventory_unavailable": 1}


def test_runner_export_only_five_fields_and_no_patch_requirement():
    row = candidate()
    exported = runner_row(row)
    assert set(exported) == {
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "file_changes",
    }
    assert validate_runner(exported, exact=True) == []
    assert validate_runner({**exported, "patch": "oops"}, exact=True)
    assert validate_runner({**exported, "patch": "legacy extra"}) == []


def test_publication_screen_reports_categories_without_exposing_matched_values():
    from scripts.privacy_audit import flags

    text = (
        "contact user@example.com; /home/person/work/a.c; password='example'; "
        "-----BEGIN PRIVATE KEY-----"
    )
    result = flags(text)
    assert result == {
        "email_like": 1,
        "personal_home_path": 1,
        "private_key_marker": 1,
        "literal_credential_context": 1,
    }
    assert "user@example.com" not in json.dumps(result)


def test_frozen_input_hashes_detect_edits(tmp_path):
    write_json(tmp_path / "groups.json", {"members": ["a"]})
    write_json(tmp_path / "manifest.json", {"output_hashes": file_hashes(tmp_path)})
    verify_manifest(tmp_path)
    write_json(tmp_path / "groups.json", {"members": ["b"]})
    with pytest.raises(ValueError, match="manifest mismatch"):
        verify_manifest(tmp_path)


def test_jsonl_reader_preserves_unicode_line_separators_inside_report_text(tmp_path):
    from scripts.prepare import load_rows

    rows = [
        {"problem_statement": "report\u2028text\u0085here\u2029still one JSONL record"},
        {"value": 2},
    ]
    write_rows(tmp_path, "records", rows)
    assert load_rows(tmp_path, "records-*.jsonl") == rows


def test_reclassification_preserves_frozen_evidence_and_recomputes_eligibility(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from scripts import prepare

    row = candidate()
    row["problem_statement"] = "LOGICAL_ERROR\n\nreproducer"
    ev = splits.evidence(row)
    ev["reports"]["selected"].update(
        source="github_issue",
        labels=["experimental feature"],
        issue_type=None,
        raw_text="original raw text",
        raw_text_sha256=sha256("original raw text"),
        task={"kind": "feature"},
        payload={"sha256": "frozen payload hash"},
    )
    original_git = copy.deepcopy(ev["git"])
    source, destination = tmp_path / "v3", tmp_path / "v3.1"
    source.mkdir()
    write_rows(source, "records", [row])
    write_json(source / "snapshot.json", {"source_revision": "pinned"})
    write_json(source / "manifest.json", {"output_hashes": file_hashes(source)})
    original_files = file_hashes(source)
    monkeypatch.setattr(prepare, "implementation", lambda: {"revision": "new rules"})
    prepare.reclassify_command(SimpleNamespace(input=source, out=destination))
    updated = splits.evidence(prepare.load_rows(destination, "records-*.jsonl")[0])
    assert updated["eligibility"]["task"] == "unknown"
    assert "task_feature" not in updated["eligibility"]["excluded"]
    assert updated["git"] == original_git
    for key in ("raw_text", "raw_text_sha256", "payload"):
        assert updated["reports"]["selected"][key] == ev["reports"]["selected"][key]
    assert file_hashes(source) == original_files
    verify_manifest(destination)
