"""Generate and replay the five non-LLVM adaptations from the authorized frozen archive."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc import gitutil, splits  # noqa: E402
from cpp_loc.provenance import json_bytes, sha256, utc  # noqa: E402
from scripts.prepare import (  # noqa: E402
    file_hashes,
    fresh,
    implementation,
    load_rows,
    prepare_split,
    runner_row,
    verify_manifest,
    write_json,
)

REPOSITORIES = ("clickhouse", "linux", "postgres", "systemd", "qemu")
SCHEDULE = {
    "pool_start": "2024-01-01T00:00:00Z",
    "buffer_start": "2026-03-01T00:00:00Z",
    "test_start": "2026-06-01T00:00:00Z",
    "test_end": "2026-09-09T00:00:00Z",
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def frozen_hashes(archive):
    return {
        path.relative_to(archive).as_posix(): file_hashes(path)
        for name in ("llvm", *REPOSITORIES)
        for path in sorted((archive / "data" / name).iterdir())
        if path.is_dir() and path.name.startswith(("v", "diagnostic-", "splits-"))
    }


def validate_split(rows, grouped, result, directory, frozen):
    """Check exported contents and boundaries independently of split membership selection."""
    verify_manifest(directory)
    cfg, members = result["config"], result["membership"]
    by_id = {r["instance_id"]: r for r in rows}
    seen, group_parts, exported = set(), {}, {}
    for part in ("train", "dev", "test"):
        selected = (
            load_rows(directory, f"{part}-*.jsonl")
            if list(directory.glob(f"{part}-*.jsonl"))
            else []
        )
        exported[part] = selected
        expected_ids = {i for i, a in members.items() if a["partition"] == part}
        check({r["instance_id"] for r in selected} == expected_ids, f"{part}: membership mismatch")
        check(len(selected) == result["counts"].get(part, 0), f"{part}: count mismatch")
        for row in selected:
            inst = row["instance_id"]
            check(inst not in seen, f"duplicate runner ID: {inst}")
            seen.add(inst)
            check(row == runner_row(by_id[inst]), f"runner text/gold/schema mismatch: {inst}")
            ev = splits.evidence(by_id[inst])
            check(not ev["eligibility"]["excluded"], f"ineligible row: {inst}")
            if cfg["view"] == "strict":
                check(not ev["eligibility"]["unknown"], f"unknown strict evidence: {inst}")
            gid = grouped["membership"][inst]
            check(group_parts.setdefault(gid, part) == part, f"group crosses splits: {gid}")
            check(not members[inst]["reasons"], f"exported excluded row: {inst}")
    for group in grouped["groups"]:
        if group["group_id"] not in group_parts:
            continue
        part = group_parts[group["group_id"]]
        expected = "test" if part == "test" else "pool"
        check(
            all(
                splits.partition(splits.evidence(by_id[i])["git"].get("committer_at"), cfg)
                == expected
                for i in group["members"]
            ),
            f"full evidence group crosses time: {group['group_id']}",
        )
        if cfg["view"] == "strict":
            check(group["size"] == 1, "strict group is not singleton")
    if result["refusal"]:
        check(not seen, "refused configuration exported rows")
    else:
        check(len(exported["train"]) >= cfg["min_train_size"], "training minimum failed")
        check(len(exported["dev"]) == cfg["dev_size"], "dev size failed")
        ordered = sorted(
            exported["train"] + exported["dev"],
            key=lambda r: (
                utc(splits.evidence(by_id[r["instance_id"]])["git"]["committer_at"]),
                r["instance_id"],
            ),
        )
        check(
            {r["instance_id"] for r in ordered[-cfg["dev_size"] :]}
            == {r["instance_id"] for r in exported["dev"]},
            "dev is not the latest surviving pool records",
        )
        test_hashes = {k: v for k, v in file_hashes(directory).items() if k.startswith("test-")}
        frozen_tests = {k: v for k, v in file_hashes(frozen).items() if k.startswith("test-")}
        check(test_hashes == frozen_tests, "frozen test bytes changed")


def generate(archive: Path, out: Path):
    code = implementation()
    before = frozen_hashes(archive)
    # Check all recorded final schedules before generating any adaptation.
    for name in ("llvm", *REPOSITORIES):
        for kind in ("diagnostic-v2", "splits-v2"):
            directory = archive / "data" / name / kind
            verify_manifest(directory)
            cfg = json.loads((directory / "manifest.json").read_text())["config"]
            check(
                all(cfg[k] == v for k, v in SCHEDULE.items()),
                f"frozen schedule differs: {directory}",
            )
            check(cfg["dev_size"] == 300, f"frozen dev size differs: {directory}")
    fresh(out)
    receipt = {
        "implementation": code,
        "archive_revision": gitutil.head(archive),
        "schedule": SCHEDULE,
        "frozen_input_hashes": before,
        "repositories": {},
    }
    for name in REPOSITORIES:
        source = archive / "data" / name / "v3.1"
        verify_manifest(source)
        snapshot = json.loads((source / "snapshot.json").read_text())
        check(snapshot["mode"] == "full_integrity", f"missing full Git evidence: {name}")
        for filename, digest in snapshot["input_files"].items():
            check(
                sha256((archive / "data" / name / "v2" / filename).read_bytes()) == digest,
                f"original input changed: {name}/{filename}",
            )
        originals = {
            r["instance_id"]: sha256(json_bytes(r))
            for r in load_rows(archive / "data" / name / "v2", "instances*.jsonl")
        }
        rows = load_rows(source, "records-*.jsonl")
        check(len(rows) == len(originals), f"incomplete extraction population: {name}")
        for row in rows:
            raw = {
                **row,
                "metadata": {k: v for k, v in row["metadata"].items() if k != "integrity"},
            }
            check(
                sha256(json_bytes(raw)) == originals.pop(row["instance_id"], None),
                f"original evidence changed: {row['instance_id']}",
            )
        check(not originals, f"missing original records: {name}")
        grouped = json.loads((source / "groups.json").read_text())
        check(
            json_bytes(splits.groups(rows)) == json_bytes(grouped),
            f"frozen grouping differs: {name}",
        )
        outcomes = {}
        attempts = [("diagnostic", 300, 1, "adaptation-diagnostic-v1")]
        for view, dev_size, minimum, folder in attempts:
            cfg = splits.config(**SCHEDULE, view=view, dev_size=dev_size, min_train_size=minimum)
            directory = out / name / folder
            result = prepare_split(source, directory, cfg)
            frozen = (
                archive / "data" / name / ("diagnostic-v2" if view == "diagnostic" else "splits-v2")
            )
            validate_split(rows, grouped, result, directory, frozen)
            with TemporaryDirectory(prefix="cpp-loc-replay-") as temporary:
                replay = Path(temporary)
                prepare_split(source, replay, cfg)
                check(file_hashes(directory) == file_hashes(replay), f"replay differs: {directory}")
            outcomes[folder] = {
                k: result[k]
                for k in (
                    "status",
                    "refusal",
                    "counts",
                    "eligible_before_train_dev",
                    "eligible_before_dev",
                    "exclusion_counts",
                )
            }
            outcomes[folder]["artifact_hashes"] = file_hashes(directory)
            if folder == "adaptation-diagnostic-v1":
                if result["refusal"]:
                    attempts.append(("diagnostic", 50, 100, "adaptation-diagnostic-small-v1"))
                attempts.append(("strict", 300, 1, "adaptation-strict-v1"))
            print(name, folder, result["counts"], result["refusal"] or result["status"], flush=True)
        receipt["repositories"][name] = {
            "full_population": len(rows),
            "report_backed": sum(bool(r.get("problem_statement")) for r in rows),
            "temporal_population": dict(
                Counter(
                    splits.partition(splits.evidence(r)["git"].get("committer_at"), cfg)
                    for r in rows
                )
            ),
            "source_revision": snapshot["source_revision"],
            "outcomes": outcomes,
        }
    check(before == frozen_hashes(archive), "frozen archive changed during generation")
    receipt["checks"] = {
        "original_population_and_fields": "passed",
        "frozen_groups_including_null_reports": "passed",
        "exact_runner_schema_unique_ids_gold_and_text": "passed",
        "group_separation_and_committer_time_boundaries": "passed",
        "minimum_train_and_latest_dev": "passed",
        "unchanged_frozen_tests_and_llvm": "passed",
        "byte_identical_replay_including_manifests": "passed",
    }
    receipt["output_hashes"] = file_hashes(out)
    write_json(out / "verification.json", receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    generate(args.archive, args.out)
