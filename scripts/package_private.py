"""Prepare a screened runner-only copy of a local review bundle for private storage."""

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc.integrity import normalized_path  # noqa: E402
from cpp_loc.provenance import sha256  # noqa: E402
from cpp_loc.schema import validate_runner  # noqa: E402
from scripts.prepare import file_hashes, fresh, implementation, write_json, write_rows  # noqa: E402
from scripts.privacy_audit import RULE, record_flags  # noqa: E402

QUARANTINE = {
    "phone_context",
    "private_key_marker",
    "github_token_shape",
    "aws_access_key_shape",
    "url_credentials",
    "literal_credential_context",
}


def contained(root: Path, name: str) -> Path:
    path = root / name
    if not normalized_path(name) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("invalid bundle path")
    return path


def package(bundle: Path, out: Path) -> dict:
    code = implementation()
    parent = json.loads((bundle / "release.json").read_text())
    for name, expected in parent["output_hashes"].items():
        if sha256(contained(bundle, name).read_bytes()) != expected:
            raise ValueError(f"bundle hash mismatch: {name}")
    metadata = json.loads((bundle / "README.md").read_text().split("---", 2)[1])
    fresh(out)
    counts, withheld, screened, retained, configs = {}, {}, {}, set(), []
    for config in metadata["configs"]:
        name = config["config_name"]
        destination = contained(out, "data/" + name)
        destination.mkdir(parents=True)
        data_files, counts[name] = [], {}
        for part in config["data_files"]:
            rows, excluded = [], 0
            for filename in part["path"]:
                with contained(bundle, filename).open(encoding="utf-8") as file:
                    for line in file:
                        row = json.loads(line)
                        if errors := validate_runner(row, exact=True):
                            raise ValueError(f"invalid runner row: {errors}")
                        inst = row["instance_id"]
                        matches = record_flags(row)
                        screened[inst] = sorted(matches)
                        reasons = sorted(matches.keys() & QUARANTINE)
                        if reasons:
                            withheld[inst] = reasons
                            excluded += 1
                        else:
                            retained.add(inst)
                            rows.append(row)
            split = part["split"]
            if not normalized_path(split) or "/" in split:
                raise ValueError("invalid split name")
            paths = write_rows(destination, split, rows)
            counts[name][split] = {"included": len(rows), "withheld": excluded}
            if paths:
                data_files.append(
                    {"split": split, "path": [p.relative_to(out).as_posix() for p in paths]}
                )
        if data_files:
            configs.append({"config_name": name, "data_files": data_files})

    # Read evidence locally; export only source links and hashes, never raw companions.
    sources = {}
    for path in sorted((bundle / "companions").glob("*/v*/records-*.jsonl")):
        with path.open(encoding="utf-8") as file:
            for line in file:
                row = json.loads(line)
                inst = row["instance_id"]
                if inst not in retained:
                    continue
                selected = row["metadata"]["integrity"]["reports"]["selected"] or {}
                source = {
                    "instance_id": inst,
                    "repo": row["repo"],
                    "report_url": selected.get("url") or row["metadata"].get("report_url"),
                    "report_source": row["problem_source"],
                    "processed_text_sha256": sha256(row["problem_statement"]),
                    "payload_sha256": (selected.get("payload") or {}).get("sha256"),
                }
                if record_flags(source).keys() & QUARANTINE:
                    raise ValueError(f"source link requires review: {inst}")
                sources[inst] = source
    if set(sources) != retained:
        raise ValueError("missing companion provenance for retained rows")
    provenance = out / "provenance"
    provenance.mkdir()
    write_rows(provenance, "sources", (sources[k] for k in sorted(sources)))
    for path in sorted((bundle / "companions").glob("*/baseline-v1/summary.json")):
        shutil.copyfile(path, provenance / f"{path.parent.parent.name}-baseline.json")

    metadata.update(
        configs=configs,
        license_name="upstream-rights-review-pending",
        license_link="README.md#rights-and-access",
    )
    card = "---\n" + json.dumps(metadata, indent=2) + "\n---\n\n# cpp-loc\n\n"
    card += (
        "**PRIVATE REVIEW SNAPSHOT. Keep this repository private. Public release is "
        "pending privacy and redistribution-rights review.**\n\n"
        "Six existing C/C++ repository populations for file-level code localization. "
        "Unfiltered configurations preserve historical eligibility, subject to the "
        "screen below; diagnostic splits remain provisional. Strict configurations, "
        "where nonempty, are rule-based candidates requiring source review.\n\n"
        "Each row has exactly instance_id, repo, base_commit, problem_statement, and "
        "file_changes. Gold is evaluator-only. Model input is report text and opaque "
        "workspace context; the exporter does not implement runtime isolation.\n\n"
        "Phone-context and credential-pattern rows are withheld without editing their "
        "text. The same screen covers every runner field. False positives include "
        "examples; names, email addresses, home paths, and other personal information "
        "may remain. This is not anonymization or legal clearance. Counts, withheld "
        "IDs/reasons, and parent hashes are in release.json. Raw mail, patches, fixing "
        "messages, caches, and full evidence remain local.\n\n"
        "Source links and report hashes are in provenance/. Baseline summaries describe "
        "the original populations before this storage filter. LLVM remains the "
        "adaptation candidate; other repositories are evaluation candidates.\n\n"
        "## Rights and access\n\n"
        "The implementation is MIT. This snapshot supplies no blanket license for "
        "upstream reports or embedded code; existing notices are preserved in retained "
        "text. Source-specific rights and notices still require review before public "
        "release. Private access does not itself resolve those obligations.\n\n"
        "[Implementation and review](https://github.com/jingunhong/cpp-loc).\n"
    )
    (out / "README.md").write_text(card, encoding="utf-8")
    release = {
        "implementation": code,
        "destination": "jingunhong/cpp-loc",
        "publication_status": "private_review_only",
        "parent_release_sha256": sha256((bundle / "release.json").read_bytes()),
        "screen_rule": RULE,
        "quarantine_categories": sorted(QUARANTINE),
        "screen_scope": "all decoded string values of every exported runner row and source link",
        "screened_unique_instances": len(screened),
        "retained_unique_instances": len(retained),
        "flagged_unique_instances": dict(Counter(k for hits in screened.values() for k in hits)),
        "withheld": dict(sorted(withheld.items())),
        "counts": counts,
        "output_hashes": file_hashes(out),
    }
    write_json(out / "release.json", release)
    return release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = package(args.bundle, args.out)
    print(json.dumps({k: result[k] for k in ("publication_status", "counts")}, indent=2))


if __name__ == "__main__":
    main()
