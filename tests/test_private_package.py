import json

import pytest

from scripts import package_private
from scripts.prepare import file_hashes, load_rows, write_json, write_rows
from tests.test_preparation import candidate


def test_private_bundle_quarantines_all_fields_and_keeps_raw_evidence_local(tmp_path, monkeypatch):
    bundle, out = tmp_path / "bundle", tmp_path / "private"
    corpus = bundle / "corpus/demo"
    corpus.mkdir(parents=True)
    ordinary = candidate("ordinary")
    ordinary["metadata"]["report_url"] = "https://example.test/issues/1"
    ordinary["metadata"]["integrity"]["git"]["commit_message"] = {"raw": "LOCAL RAW EVIDENCE"}
    rows = [
        {
            k: ordinary[k]
            for k in ("instance_id", "repo", "base_commit", "problem_statement", "file_changes")
        },
    ]
    rows.append({**rows[0], "instance_id": "phone", "problem_statement": "Phone: +1 202 555 0100"})
    rows.append(
        {**rows[0], "instance_id": "key", "file_changes": [{"file": "ghp_" + "a" * 36 + ".c"}]}
    )
    rows.append({**rows[0], "instance_id": "password", "problem_statement": 'password="example"'})
    paths = write_rows(corpus, "reports", rows)
    evidence = bundle / "companions/demo/v3.1"
    evidence.mkdir(parents=True)
    write_rows(evidence, "records", [ordinary])
    write_json(
        evidence / "groups.json",
        {
            "membership": {ordinary["instance_id"]: "group1"},
            "groups": [{"group_id": "group1", "size": 1}],
        },
    )
    metadata = {
        "license": "other",
        "configs": [
            {
                "config_name": name,
                "data_files": [
                    {"split": "test", "path": [p.relative_to(bundle).as_posix() for p in paths]}
                ],
            }
            for name in ("demo_unfiltered", "demo_diagnostic")
        ],
    }
    (bundle / "README.md").write_text("---\n" + json.dumps(metadata) + "\n---\n")
    write_json(bundle / "release.json", {"output_hashes": file_hashes(bundle)})
    before = file_hashes(bundle)
    monkeypatch.setattr(package_private, "implementation", lambda: {"revision": "committed"})
    result = package_private.package(bundle, out)
    assert result["withheld"] == {
        "key": ["github_token_shape"],
        "phone": ["phone_context"],
        "password": ["literal_credential_context"],
    }
    assert result["retained_unique_instances"] == 1
    for name in ("demo_unfiltered", "demo_diagnostic"):
        assert load_rows(out / "data" / name, "*.jsonl") == rows[:1]
        assert result["counts"][name]["test"] == {"included": 1, "withheld": 3}
    assert not (out / "companions").exists()
    assert "LOCAL RAW EVIDENCE" not in "".join(p.read_text() for p in out.rglob("*") if p.is_file())
    assert (
        load_rows(out / "provenance", "sources-*.jsonl")[0]["report_url"]
        == ordinary["metadata"]["report_url"]
    )
    provenance = load_rows(out / "provenance", "sources-*.jsonl")[0]
    assert provenance["group_id"] == "group1" and provenance["group_size"] == 1
    assert provenance["primary_files"] == ["a.c"]
    assert provenance["eligibility"]["strict_local"] is True
    assert provenance["chronology"] == ordinary["metadata"]["integrity"]["chronology"]
    assert file_hashes(bundle) == before
    paths[0].write_text("changed")
    with pytest.raises(ValueError, match="bundle hash mismatch"):
        package_private.package(bundle, tmp_path / "corrupt")
    with pytest.raises(ValueError, match="invalid bundle path"):
        package_private.contained(bundle, "../escape")
