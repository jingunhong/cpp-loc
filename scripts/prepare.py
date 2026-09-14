"""Offline preparation: enrich existing rows, split, audit, then package for publication."""

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import batched
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc import (  # noqa: E402
    EXTRACTOR_VERSION,
    audit,
    filters,
    gitutil,
    integrity,
    splits,
)
from cpp_loc.provenance import RULE_VERSION, json_bytes, sha256, task_kind, utc  # noqa: E402
from cpp_loc.schema import RUNNER_FIELDS, Instance, validate_runner  # noqa: E402
from scripts.extract import REPOS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load_rows(directory: Path, pattern: str) -> list[dict]:
    paths = sorted(directory.glob(pattern))
    if not paths:
        raise ValueError(f"no {pattern} in {directory}")
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as file:
            rows.extend(json.loads(line) for line in file)
    return rows


def write_json(path: Path, value) -> None:
    path.write_bytes(json_bytes(value))


def write_rows(directory: Path, stem: str, rows, max_bytes: int = 45_000_000) -> list[Path]:
    paths, size, file = [], 0, None
    try:
        for row in rows:
            data = json_bytes(row)
            if len(data) > max_bytes:
                raise ValueError("one record exceeds the shard size limit")
            if file is None or size + len(data) > max_bytes:
                if file:
                    file.close()
                path = directory / f"{stem}-{len(paths):03d}.jsonl"
                paths.append(path)
                file, size = path.open("wb"), 0
            file.write(data)
            size += len(data)
    finally:
        if file:
            file.close()
    return paths


def fresh(directory: Path) -> None:
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(f"output must be new/empty; refusing to overwrite {directory}")
    directory.mkdir(parents=True, exist_ok=True)


def file_hashes(directory: Path) -> dict:
    return {
        p.relative_to(directory).as_posix(): sha256(p.read_bytes())
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def verify_manifest(directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text())
    expected = manifest["output_hashes"]
    for name, digest in expected.items():
        path = directory / name
        if (
            not integrity.normalized_path(name)
            or not path.is_file()
            or sha256(path.read_bytes()) != digest
        ):
            raise ValueError(f"input manifest mismatch: {name}")


def implementation() -> dict:
    revision = gitutil.head(ROOT)
    changed = gitutil.run(
        ROOT,
        "diff",
        "HEAD",
        "--name-only",
        "--",
        "cpp_loc",
        "scripts",
        "pyproject.toml",
        "uv.lock",
    )
    untracked = gitutil.run(
        ROOT, "ls-files", "--others", "--exclude-standard", "--", "cpp_loc", "scripts"
    )
    if changed.strip() or untracked.strip():
        raise ValueError("commit the implementation before generating release artifacts")
    paths = sorted(
        [
            *ROOT.glob("cpp_loc/*.py"),
            *ROOT.glob("scripts/*.py"),
            ROOT / "pyproject.toml",
            ROOT / "uv.lock",
        ]
    )
    return {
        "revision": revision,
        "extractor_version": EXTRACTOR_VERSION,
        "files": {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in paths},
    }


def runner_row(row: dict, *, enriched: bool = True) -> dict:
    result = {k: row[k] for k in RUNNER_FIELDS}
    if enriched:
        result["file_changes"] = [{"file": p} for p in splits.evidence(row)["git"]["primary_files"]]
    errors = validate_runner(result, exact=True)
    if errors:
        raise ValueError(f"{row['instance_id']}: {errors}")
    return result


def enrich_batch(task):
    """Keep Git subprocess work in small workers instead of the full-corpus process."""
    name, rows, repos_dir, revision, reports_only = task
    sources = REPOS[name]["sources"](repos_dir / "cache", None)
    for source in sources:
        source.offline = True
    result = [
        integrity.enrich(row, repos_dir / name, revision, sources, reports_only=reports_only)
        for row in rows
    ]
    return result, {key: value for source in sources for key, value in source.consumed.items()}


def enrich_command(args) -> None:
    code = implementation()
    cfg = REPOS[args.repo]
    rows = load_rows(args.input, "instances*.jsonl")
    for row in rows:
        errors = Instance(**row).validate()
        if errors:
            raise ValueError(f"invalid extraction row {row.get('instance_id')}: {errors}")
    if any(r["repo"] != cfg["upstream"] for r in rows):
        raise ValueError("input population has the wrong repository")
    command = (args.input / "COMMAND.txt").read_text()
    revision = next(
        (
            line.removeprefix("upstream HEAD: ").strip()
            for line in command.splitlines()
            if line.startswith("upstream HEAD: ")
        ),
        None,
    )
    if not revision:
        raise ValueError("input COMMAND.txt must pin upstream HEAD")
    clone = args.repos_dir / args.repo
    sources = cfg["sources"](args.repos_dir / "cache", None)
    for src in sources:
        src.offline = True
    reachable = set()
    if not args.reports_only:
        reachable = set(gitutil.run(clone, "rev-list", revision, offline=True).splitlines())
    source_paths = [*sorted(args.input.glob("instances*.jsonl")), args.input / "COMMAND.txt"]
    inputs = {p.name: sha256(p.read_bytes()) for p in source_paths}
    fresh(args.out)

    def run(row):
        return integrity.enrich(row, clone, revision, sources, reports_only=args.reports_only)

    result, payloads = [], {}
    if args.processes:
        tasks = (
            (args.repo, chunk, args.repos_dir, revision, args.reports_only)
            for chunk in batched(rows, 250, strict=False)
        )
        with ProcessPoolExecutor(args.workers) as pool:
            for chunk, consumed in pool.map(enrich_batch, tasks, buffersize=args.workers * 2):
                result.extend(chunk)
                payloads.update(consumed)
                print(
                    f"{args.repo}: enriched {len(result)}/{len(rows)}", file=sys.stderr, flush=True
                )
    else:
        with ThreadPoolExecutor(args.workers) as pool:
            for n, row in enumerate(pool.map(run, rows, buffersize=args.workers * 2), 1):
                result.append(row)
                if n % 500 == 0:
                    print(f"{args.repo}: enriched {n}/{len(rows)}", file=sys.stderr, flush=True)
        payloads = {key: value for src in sources for key, value in src.consumed.items()}
    for row in result:
        if not args.reports_only and row["fix_commit"] not in reachable:
            ev = splits.evidence(row)
            ev["git"]["errors"].append("fix_outside_pinned_upstream")
            ev["eligibility"] = integrity.eligibility(row, ev)
    result.sort(key=lambda r: r["instance_id"])
    grouped = splits.groups(result)
    snapshot = {
        "implementation": code,
        "repository": cfg["upstream"],
        "source_revision": revision,
        "input_files": inputs,
        "original_extraction_command": command,
        "mode": "report_annotations_only" if args.reports_only else "full_integrity",
        "configuration": {
            "offline": True,
            "path_rule": filters.PATH_RULE_VERSION,
            "rename_policy": gitutil.RENAME_POLICY,
        },
        "replay": (
            "Requires original hashed input files, pinned git commit/tree objects, "
            "available full-diff blobs for patch IDs, and every payload/fetch sidecar "
            "listed in payloads.jsonl. Hashes cannot recreate missing payloads. Do not "
            "publish the whole cache automatically."
        ),
    }
    write_rows(args.out, "records", result)
    write_rows(args.out, "payloads", (payloads[k] for k in sorted(payloads)))
    write_json(args.out / "snapshot.json", snapshot)
    write_json(args.out / "groups.json", grouped)
    write_json(args.out / "summary.json", audit.population_summary(result, grouped))
    write_rows(args.out, "audit-sample", audit.sample(result, grouped))
    write_json(
        args.out / "manifest.json",
        {"kind": "enriched-extraction", "output_hashes": file_hashes(args.out)},
    )
    print(json.dumps(audit.population_summary(result, grouped), indent=2))


def reclassify_command(args) -> None:
    """Revise issue-task rules from frozen text/labels, without reading Git or the network."""
    code = implementation()
    verify_manifest(args.input)
    rows = load_rows(args.input, "records-*.jsonl")
    fresh(args.out)
    for row in rows:
        ev = splits.evidence(row)
        report = ev["reports"]["selected"]
        if report and report["source"] in {"github_issue", "gitlab_issue"}:
            title, _, body = row["problem_statement"].partition("\n\n")
            task = task_kind(title, body, report["labels"], report["issue_type"])
            report["task"] = task
            report["annotation"] = {
                "kind": "explicit_bug_report" if task["kind"] == "bug" else "unknown",
                "confidence": "heuristic",
                "evidence": task["evidence"],
                "rule": RULE_VERSION,
            }
        ev["eligibility"] = integrity.eligibility(row, ev)
    grouped = splits.groups(rows)
    snapshot = json.loads((args.input / "snapshot.json").read_text())
    snapshot = {
        **snapshot,
        "implementation": code,
        "derived_from": {"snapshot": snapshot, "input_hashes": file_hashes(args.input)},
        "annotation_revision": RULE_VERSION,
        "operation": "reclassify frozen issue text/labels; retain Git and payload evidence",
    }
    write_rows(args.out, "records", rows)
    for path in args.input.glob("payloads-*.jsonl"):
        shutil.copyfile(path, args.out / path.name)
    write_json(args.out / "snapshot.json", snapshot)
    write_json(args.out / "groups.json", grouped)
    write_json(args.out / "summary.json", audit.population_summary(rows, grouped))
    write_rows(args.out, "audit-sample", audit.sample(rows, grouped))
    write_json(
        args.out / "manifest.json",
        {"kind": "reclassified-extraction", "output_hashes": file_hashes(args.out)},
    )
    print(json.dumps(audit.population_summary(rows, grouped), indent=2))


def split_command(args) -> None:
    implementation()
    verify_manifest(args.input)
    rows = load_rows(args.input, "records-*.jsonl")
    grouped = json.loads((args.input / "groups.json").read_text())
    cfg = splits.config(
        test_end=args.test_end,
        role=args.role,
        view=args.view,
        **{k: getattr(args, k) for k in splits.DEFAULTS},
    )
    result = splits.split(rows, grouped, cfg)
    fresh(args.out)
    result["input_hashes"] = file_hashes(args.input)
    result["implementation"] = implementation()
    result["input_snapshot"] = json.loads((args.input / "snapshot.json").read_text())
    for part in ("train", "dev", "test"):
        selected = [
            runner_row(r)
            for r in rows
            if result["membership"][r["instance_id"]]["partition"] == part
        ]
        write_rows(args.out, part, selected)
    result["output_hashes"] = file_hashes(args.out)
    write_json(args.out / "manifest.json", result)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k in {"status", "counts", "refusal", "eligible_before_dev", "exclusion_counts"}
            },
            indent=2,
        )
    )
    if result["refusal"]:
        raise SystemExit(2)


def audit_command(args) -> None:
    code = implementation()
    verify_manifest(args.input)
    rows = [r for r in load_rows(args.input, "records-*.jsonl") if r.get("problem_statement")]
    clone = args.repos_dir / args.repo
    fresh(args.out)

    inventory = gitutil.TreeInventory(clone)
    results = []
    # Ordering is only a cache optimization; each delta ends at the exact base tree.
    rows.sort(
        key=lambda r: (str(utc(splits.evidence(r)["git"].get("committer_at"))), r["instance_id"])
    )
    for n, row in enumerate(rows, 1):
        try:
            inventory.at(row["base_commit"])
            result = audit.baseline_result(
                row,
                inventory.paths,
                basename_index=inventory.basenames,
                tree_sha=inventory.tree_sha,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ValueError,
            OSError,
        ) as exc:
            result = audit.baseline_result(row, None, type(exc).__name__)
        results.append(result)
        if n % 500 == 0:
            print(f"{args.repo}: baseline {n}/{len(rows)}", file=sys.stderr, flush=True)
    results.sort(key=lambda r: r["instance_id"])
    write_rows(args.out, "predictions", results)
    summary = audit.baseline_summary(results)
    write_json(args.out / "summary.json", summary)
    write_json(
        args.out / "manifest.json",
        {
            "implementation": code,
            "input_hashes": file_hashes(args.input),
            "output_hashes": file_hashes(args.out),
        },
    )
    print(json.dumps(summary, indent=2))


def package_command(args) -> None:
    code = implementation()
    fresh(args.out)
    configs, counts = [], {}
    for name in sorted(REPOS):
        destination = args.out / "corpus" / name
        destination.mkdir(parents=True)
        rows = load_rows(args.data_dir / name / "v2", "instances*.jsonl")
        report_rows = [runner_row(r, enriched=False) for r in rows if r.get("problem_statement")]
        paths = write_rows(destination, "reports", report_rows)
        counts[name] = len(report_rows)
        configs.append(
            {
                "config_name": name + "_unfiltered",
                "data_files": [
                    {"split": "corpus", "path": [p.relative_to(args.out).as_posix() for p in paths]}
                ],
            }
        )
        evidence_dir = "v3.1" if (args.data_dir / name / "v3.1").is_dir() else "v3"
        split_dirs = [
            f"{kind}-v2" if (args.data_dir / name / f"{kind}-v2").is_dir() else f"{kind}-v1"
            for kind in ("splits", "diagnostic")
        ]
        # Retain the final evidence/partitions; superseded candidates stay local.
        for folder in (evidence_dir, *split_dirs, "baseline-v1"):
            source = args.data_dir / name / folder
            if source.is_dir():
                verify_manifest(source)
                shutil.copytree(source, args.out / "companions" / name / folder)
        for folder in split_dirs:
            split_dir = args.data_dir / name / folder
            if not split_dir.is_dir():
                continue
            manifest = json.loads((split_dir / "manifest.json").read_text())
            data_files = []
            for part in ("train", "dev", "test"):
                paths = sorted((args.out / "companions" / name / folder).glob(f"{part}-*.jsonl"))
                if paths:
                    data_files.append(
                        {"split": part, "path": [p.relative_to(args.out).as_posix() for p in paths]}
                    )
            if data_files:
                configs.append(
                    {
                        "config_name": name + "_" + manifest["config"]["view"],
                        "data_files": data_files,
                    }
                )
    docs = args.out / "docs"
    docs.mkdir()
    for path in sorted((ROOT / "docs").glob("*.md")):
        shutil.copyfile(path, docs / path.name)
    metadata = {
        "language": ["en", "code"],
        "license": "other",
        "license_name": "upstream-project-licenses",
        "license_link": "https://github.com/jingunhong/cpp-loc/blob/main/docs/04-publication-review.md",
        "pretty_name": "cpp-loc",
        "tags": ["code-localization", "cpp", "c", "bug-reports"],
        "configs": configs,
    }
    # JSON is valid YAML: keep Hub metadata dependency-free.
    card = "---\n" + json.dumps(metadata, indent=2) + "\n---\n\n# cpp-loc\n\n"
    card += "Repository-level code localization in C/C++. Dataset: `jingunhong/cpp-loc`.\n\n"
    card += (
        "**LOCAL REVIEW DRAFT — upload held for privacy and redistribution-rights review.** "
        "See [publication review](docs/04-publication-review.md).\n\n"
    )
    card += (
        "The `*_unfiltered` configurations preserve the historical v2 report-backed "
        "populations. They include feature requests, added-file targets, shared "
        "reports, and unresolved chronology; they are **not certified bug-fix "
        "evaluation sets**. Counts are instances, not distinct bugs.\n\n"
    )
    card += "| Repository | Report-backed instances |\n|---|---:|\n" + "".join(
        f"| {k} | {v} |\n" for k, v in counts.items()
    )
    card += (
        "\nCompanion v3 evidence, exclusions, groups, candidate split manifests, and "
        "baseline audits are under `companions/`. A refused split exports no "
        "train/dev/test rows. Diagnostic splits are provisional; strict candidates "
        "still require review. See [validation results](docs/03-validation-report.md) "
        "and [rules and handoff](docs/02-splits-and-provenance.md).\n\n"
    )
    card += (
        "Every data view has exactly `instance_id`, `repo`, `base_commit`, "
        "`problem_statement`, `file_changes`. The last field is evaluator-only gold. "
        "Model-visible input is report text plus opaque workspace context, never the "
        "serialized row. The exporter does not provide a sandbox.\n\n"
    )
    card += (
        "LLVM is the first adaptation candidate; ClickHouse remains a provisional "
        "transfer target. No training or GPU experiment is included. Selected "
        "raw/cleaned text and payload hashes are in companion evidence; replay requires"
        " the locally retained payload bundle described in each snapshot. The whole API"
        " cache is not published.\n\n"
    )
    card += (
        "## Licenses\n\nExtraction code is MIT. Source code and patches retain each "
        "upstream project's license; issue and mail text remains attributed to its "
        "authors and source URLs. This dataset does not relicense upstream material "
        "under MIT.\n\n"
    )
    card += "Source repository: https://github.com/jingunhong/cpp-loc\n"
    (args.out / "README.md").write_text(card, encoding="utf-8")
    write_json(
        args.out / "release.json",
        {
            "implementation": code,
            "destination": "jingunhong/cpp-loc",
            "publication_status": "held_for_privacy_and_rights_review",
            "counts": counts,
            "output_hashes": file_hashes(args.out),
        },
    )
    print(
        f"Prepared local review bundle {args.out}; "
        "publication is held pending privacy/rights review."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("enrich", "reclassify", "split", "audit", "package"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--out", required=True, type=Path)
        if name != "package":
            cmd.add_argument("--input", required=True, type=Path)
        if name in {"enrich", "audit"}:
            cmd.add_argument("--repo", required=True, choices=sorted(REPOS))
            cmd.add_argument("--repos-dir", type=Path, default=Path("repos"))
            if name == "enrich":
                cmd.add_argument("--workers", type=int, default=4)
                cmd.add_argument(
                    "--processes",
                    action="store_true",
                    help="use bounded process batches for large corpora",
                )
            cmd.add_argument("--offline", action="store_true", required=True)
        if name == "enrich":
            cmd.add_argument("--reports-only", action="store_true")
        elif name == "split":
            cmd.add_argument("--test-end", required=True)
            cmd.add_argument("--role", default="adaptation-candidate")
            cmd.add_argument("--view", choices=["strict", "diagnostic"], default="strict")
            for key, default in splits.DEFAULTS.items():
                cmd.add_argument(
                    "--" + key.replace("_", "-"),
                    default=default,
                    type=int if key == "dev_size" else str,
                )
        elif name == "package":
            cmd.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        {
            "enrich": enrich_command,
            "reclassify": reclassify_command,
            "split": split_command,
            "audit": audit_command,
            "package": package_command,
        }[args.command](args)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
