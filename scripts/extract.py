"""Extract localization instances from a local clone.

uv run python scripts/extract.py --repo linux --since 2022-01-01 --out data/linux/v2/
"""

import argparse
import os
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc import extract, filters, gitutil, leakage, reports, writers  # noqa: E402


def _qemu_references(message: str) -> list[str]:
    return filters.fixes_shas(message) + reports.gitlab_issue_refs(message, "qemu-project/qemu")


# references: what makes a commit a candidate; sources: report sources in resolution
# order (built with the cache dir and the GitHub token); refs: extra report-ref kinds
# recorded in metadata.report_refs without a fetcher.
REPOS = {
    "linux": {
        "upstream": "torvalds/linux",
        "references": filters.fixes_shas,
        "sources": lambda cache, token: [
            reports.Syzbot(cache),
            reports.Lore(cache),
            reports.Bugzilla(cache),
        ],
        "refs": {"link": reports.link_urls},
    },
    "qemu": {
        "upstream": "qemu/qemu",
        "references": _qemu_references,
        "sources": lambda cache, token: [reports.GitLab(cache, "qemu-project/qemu")],
        "refs": {"launchpad": reports.launchpad_refs, "link": reports.link_urls},
    },
    "postgres": {
        "upstream": "postgres/postgres",
        "references": filters.pgsql_refs,
        "sources": lambda cache, token: [reports.PgArchive(cache)],
        "refs": {"pgsql_bug": reports.pgsql_bug_refs},
    },
}
for _name, _upstream in (
    ("llvm", "llvm/llvm-project"),
    ("systemd", "systemd/systemd"),
    ("clickhouse", "ClickHouse/ClickHouse"),
):
    REPOS[_name] = {
        "upstream": _upstream,
        "references": lambda m, u=_upstream: filters.issue_refs(m, u),
        "sources": lambda cache, token, u=_upstream: [reports.GitHub(cache, u, token)],
        "refs": {},
    }


def _leak_summary(instances, key: str) -> str:
    rows = [i.metadata[key] for i in instances if i.metadata.get(key) is not None]
    n = len(rows)
    counts = {flag: sum(1 for r in rows if r[flag]) for flag in leakage.FLAGS}
    cells = ", ".join(
        f"{k}: {v} ({100 * v / n:.1f}%)" if n else f"{k}: 0" for k, v in counts.items()
    )
    return f"over {n} instances: {cells}"


def _count_key(instances, key: str) -> dict[str, int]:
    return dict(Counter(i.metadata[key] for i in instances if i.metadata.get(key)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, choices=sorted(REPOS))
    ap.add_argument("--since", help="git --since bound (committer date), e.g. 2022-01-01")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--repos-dir", type=Path, default=Path("repos"))
    ap.add_argument("--no-patch", action="store_true", help="skip patches (dry run for counts)")
    ap.add_argument("--no-reports", action="store_true", help="skip report fetching")
    ap.add_argument(
        "--offline", action="store_true", help="never fetch reports or missing git blobs"
    )
    args = ap.parse_args()
    if args.offline:
        os.environ.update(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0")
    if args.out.exists() and any(args.out.iterdir()):
        ap.error("choose a new output directory; historical extraction artifacts are immutable")
    extractor_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    clone = args.repos_dir / args.repo
    cfg = REPOS[args.repo]
    token = os.environ.get("GITHUB_TOKEN")
    sources = cfg["sources"](args.repos_dir / "cache", token)
    for source in sources:
        source.offline = args.offline
    funnel: dict[str, int] = {}
    instances = list(
        extract.mine(
            clone,
            args.repo,
            cfg["upstream"],
            since=args.since,
            references=cfg["references"],
            refs={s.name: s.refs for s in sources} | cfg["refs"],
            funnel=funnel,
        )
    )
    print(f"{len(instances)} instances after filters", file=sys.stderr)
    drops: Counter[str] = Counter()
    if not args.no_reports:
        extract.add_reports(instances, sources, drops)
    if not args.no_patch:
        extract.add_patches(clone, instances, offline=args.offline)

    args.out.mkdir(parents=True, exist_ok=True)
    paths = writers.write_jsonl(args.out, instances)
    dataset = writers.write_dataset(args.out, instances)
    n = len(instances)
    with_report = sum(1 for i in instances if i.problem_statement is not None)
    ref_counts = Counter(k for i in instances for k in i.metadata["report_refs"])
    by_source = dict(Counter(i.problem_source for i in instances if i.problem_source))
    upstream_head = gitutil.head(clone)
    writers.write_stats(
        args.out / "STATS.md",
        f"{args.repo} extraction stats",
        [(k, v) for k, v in funnel.items() if k != "root commits skipped"],
        {
            "instances written": n,
            "root commits skipped": funnel.get("root commits skipped", 0),
            "files": ", ".join(p.name for p in paths),
            "with a report / without": f"{with_report} / {n - with_report}",
            "dataset.jsonl rows (with a report, without patch)": with_report,
            "instances with at least one report ref, per kind": dict(ref_counts),
            "reports by source": by_source,
            "report drops": dict(drops) if not args.no_reports else "skipped (--no-reports)",
            "report counters (not drops)": {
                f"{s.name}: {k}": v for s in sources for k, v in s.stats.items()
            },
            "report kind (lore_report only)": _count_key(instances, "report_kind"),
            "report pick (pgsql_archive only)": _count_key(instances, "report_pick"),
            "reports shorter than 300 characters, per source": dict(
                Counter(
                    i.problem_source
                    for i in instances
                    if i.problem_source and len(i.problem_statement) < 300
                )
            ),
            "problem statement names a gold path / basename / patched function": _leak_summary(
                instances, "leakage"
            ),
            "commit message names a gold path / basename / patched function": _leak_summary(
                instances, "commit_message_leakage"
            ),
            "upstream": cfg["upstream"],
            "upstream HEAD": upstream_head,
            "since": args.since,
            "extractor commit": extractor_sha,
            "extractor version": extract.EXTRACTOR_VERSION,
            "report sources (resolution order)": ", ".join(s.name for s in sources),
            "github token": "GITHUB_TOKEN" if token else "none",
        },
    )
    (args.out / "COMMAND.txt").write_text(
        f"command: {shlex.join(sys.argv)}\n"
        f"extractor git SHA: {extractor_sha}\n"
        f"upstream HEAD: {upstream_head}\n"
    )
    print(f"wrote {n} instances to {', '.join(map(str, paths))}", file=sys.stderr)
    print(f"wrote {with_report} runnable rows to {dataset}", file=sys.stderr)


if __name__ == "__main__":
    main()
