import json
from types import SimpleNamespace

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
    card = json.loads((out / "README.md").read_text().split("---", 2)[1])
    assert card["license_link"].startswith("https://")  # Hub metadata requires an HTTPS URI.
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


def test_versioned_adaptations_are_additive_and_keep_refusals(tmp_path, monkeypatch):
    from cpp_loc import splits
    from scripts import adapt, prepare

    monkeypatch.setattr(prepare, "implementation", lambda: {"revision": "committed"})
    monkeypatch.setattr(package_private, "implementation", lambda: {"revision": "committed"})
    monkeypatch.setattr(prepare, "REPOS", {"demo": {}})
    data, adaptations = tmp_path / "data", tmp_path / "adaptations"
    source = data / "demo/v3.1"
    source.mkdir(parents=True)
    rows = [candidate(str(i), f"2025-01-0{i}T00:00:00Z", str(i)) for i in range(1, 4)]
    rows.append(candidate("future", "2026-07-01T00:00:00Z", "future"))
    for row in rows:
        row["file_changes"] = [{"file": "historical.c"}]
    grouped = splits.groups(rows)
    write_rows(source, "records", rows)
    write_json(source / "groups.json", grouped)
    write_json(source / "snapshot.json", {})
    write_json(source / "manifest.json", {"output_hashes": file_hashes(source)})
    historical = data / "demo/v2"
    historical.mkdir()
    write_rows(historical, "instances", rows)
    cfg = splits.config(**adapt.SCHEDULE, view="diagnostic", dev_size=1)
    frozen = data / "demo/diagnostic-v2"
    prepare.prepare_split(source, frozen, {**cfg, "role": "evaluation-only"})
    added = adaptations / "demo/adaptation-diagnostic-v1"
    result = prepare.prepare_split(source, added, cfg)
    adapt.validate_split(rows, grouped, result, added, frozen)
    refused = adaptations / "demo/adaptation-strict-v1"
    result = prepare.prepare_split(source, refused, {**cfg, "view": "strict", "dev_size": 300})
    assert result["status"] == "refused"
    adapt.validate_split(rows, grouped, result, refused, frozen)
    before = file_hashes(data)
    bundle, private = tmp_path / "bundle", tmp_path / "private"
    prepare.package_command(SimpleNamespace(data_dir=data, adaptation_dir=adaptations, out=bundle))
    package_private.package(bundle, private)
    card = json.loads((private / "README.md").read_text().split("---", 2)[1])
    assert [c["config_name"] for c in card["configs"]] == [
        "demo_unfiltered",
        "demo_diagnostic",
        "demo_adaptation_diagnostic_v1",
    ]
    for name in ("demo_diagnostic", "demo_adaptation_diagnostic_v1"):
        assert (private / "data" / name / "test-000.jsonl").read_bytes() == (
            frozen / "test-000.jsonl"
        ).read_bytes()
    train = load_rows(private / "data/demo_adaptation_diagnostic_v1", "train-*.jsonl")
    assert train[0]["file_changes"] == [{"file": "a.c"}]
    assert load_rows(private / "data/demo_unfiltered", "*.jsonl")[0]["file_changes"] == [
        {"file": "historical.c"}
    ]
    assert (
        json.loads((private / "provenance/demo-adaptation-strict-v1.json").read_text())["status"]
        == "refused"
    )
    assert file_hashes(data) == before

    # Storage can withhold training rows, explicitly counted, while retaining the minimum.
    paths = sorted((bundle / "companions/demo/adaptation-diagnostic-v1").glob("train-*.jsonl"))
    train[0]["problem_statement"] = "Phone: +1 202 555 0100"
    paths[0].write_text("".join(json.dumps(row) + "\n" for row in train))
    hashes = file_hashes(bundle)
    hashes.pop("release.json")
    write_json(bundle / "release.json", {"output_hashes": hashes})
    screened = package_private.package(bundle, tmp_path / "screened")
    assert screened["counts"]["demo_adaptation_diagnostic_v1"]["train"] == {
        "included": 1,
        "withheld": 1,
    }
    # Dropping below the train minimum or dropping any dev/test row refuses storage.
    for path in [paths[0], paths[0].with_name("dev-000.jsonl")]:
        original = path.read_bytes()
        path.write_text(json.dumps(train[0]) + "\n")
        hashes = file_hashes(bundle)
        hashes.pop("release.json")
        write_json(bundle / "release.json", {"output_hashes": hashes})
        with pytest.raises(ValueError, match="screen would violate adaptation split constraints"):
            package_private.package(bundle, tmp_path / ("screen-refused-" + path.stem))
        path.write_bytes(original)
