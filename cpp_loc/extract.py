"""The extraction pipeline: git history -> filtered Instance records + funnel counts."""

from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import EXTRACTOR_VERSION, filters, gitutil, leakage
from .reports import Source
from .schema import Instance

FILTER_ORDER = ("not merge", "not revert", "has reference", "has gold files", "1-5 gold files")


def mine(
    repo: Path,
    repo_name: str,
    upstream: str,
    *,
    since: str | None,
    references: Callable[[str], list],
    refs: dict[str, Callable[[str], list[str]]],
    funnel: dict[str, int],
) -> Iterator[Instance]:
    """Yield instances without ``patch`` (see :func:`add_patches`) and without a report
    (see :func:`add_reports`); ``problem_statement`` starts out None.

    ``references(message)`` returns the issue/commit references that make a commit a
    candidate; ``refs`` maps a report-ref kind to its parser, and every non-empty result
    lands in ``metadata.report_refs``. ``funnel`` is updated in place with survivor counts.
    """
    for stage in ("candidates", *FILTER_ORDER):
        funnel.setdefault(stage, 0)
    revision = gitutil.head(repo)
    for c in gitutil.log(repo, since=since, rev=revision):
        funnel["candidates"] += 1
        if not c.parents:
            funnel["root commits skipped"] = funnel.get("root commits skipped", 0) + 1
            continue
        if filters.is_merge(c.parents):
            continue
        funnel["not merge"] += 1
        if filters.is_revert(c.message):
            continue
        funnel["not revert"] += 1
        candidate_refs = references(c.message)
        if not candidate_refs:
            continue
        funnel["has reference"] += 1
        changes = gitutil.changes(repo, c.parents[0], c.sha)
        paths = {change[k] for change in changes for k in ("old_path", "new_path") if change[k]}
        gold = filters.gold_files(paths)
        if not gold:
            continue
        funnel["has gold files"] += 1
        if not filters.file_count_ok(gold):
            continue
        funnel["1-5 gold files"] += 1
        yield Instance(
            instance_id=f"{repo_name}__{c.sha[:12]}",
            repo=upstream,
            base_commit=c.parents[0],
            fix_commit=c.sha,
            created_at=c.author_date,
            problem_statement=None,
            problem_source=None,
            commit_message=filters.strip_trailers(c.message),
            file_changes=[{"file": p} for p in gold],
            gold_functions=None,
            patch="",
            metadata={
                "extractor_version": EXTRACTOR_VERSION,
                "references": candidate_refs,
                "report_refs": {k: v for k, f in refs.items() if (v := f(c.message))},
                "filters": list(FILTER_ORDER),
                "changed_files_total": len(changes),
                "changes": changes,
                "rename_policy": gitutil.RENAME_POLICY,
                "path_rule": filters.PATH_RULE_VERSION,
                "author_at": c.author_date,
                "committer_at": c.committer_date,
                "upstream_revision": revision,
                "commit_evidence": filters.message_evidence(c.message),
            },
        )


def _first_report(inst: Instance, sources: list[Source], drops: Counter):
    for src in sources:
        for ref in inst.metadata["report_refs"].get(src.name, ()):
            got = src.report(ref)
            if isinstance(got, str):
                drops[f"{src.name}: {got}"] += 1
            else:
                return src.name, got
    return None


def warm_caches(instances: list[Instance], sources: list[Source]) -> None:
    """Fetch every ref of every source into the cache, one thread per source (the sources
    are different hosts, each paced on its own), so :func:`add_reports` runs offline.
    Fetches a few refs a sequential resolution would have skipped; harmless."""

    def fill(src: Source) -> None:
        for inst in instances:
            for ref in inst.metadata["report_refs"].get(src.name, ()):
                try:
                    src.get(ref)
                except FileNotFoundError:
                    if not src.offline:
                        raise

    with ThreadPoolExecutor(len(sources) or 1) as pool:
        list(pool.map(fill, sources))


def add_reports(instances: list[Instance], sources: list[Source], drops: Counter) -> None:
    """Fill ``problem_statement``/``problem_source`` from the first ref (sources in order,
    refs in message order) that resolves to a report; every failed ref is counted in
    ``drops`` as ``"<source>: <reason>"``. Instances without a report keep None."""
    warm_caches(instances, sources)
    for inst in instances:
        found = _first_report(inst, sources, drops)
        if found:
            name, (title, body, extra) = found
            inst.problem_statement = f"{title.strip()}\n\n{body.strip()}".strip()
            inst.problem_source = name
            inst.metadata.update({"report_kind": None, **extra})  # kinds exist for lore only


def add_patches(repo: Path, instances: list[Instance], workers: int = 8, *, offline=False) -> None:
    """Fill ``patch``, ``metadata.leakage`` (flags of ``problem_statement``, None without one)
    and ``metadata.commit_message_leakage`` (flags of ``commit_message``) for every
    instance, bulk-fetching blobs first on partial clones. Read-only git calls run in
    parallel threads."""
    with ThreadPoolExecutor(workers) as pool:
        oids = pool.map(
            lambda i: gitutil.blob_oids(repo, i.base_commit, i.fix_commit, i.paths), instances
        )
        if not offline:
            gitutil.prefetch_blobs(repo, [o for batch in oids for o in batch])
        patches = pool.map(
            lambda i: gitutil.diff(repo, i.base_commit, i.fix_commit, i.paths, offline=offline),
            instances,
        )
        for inst, patch in zip(instances, patches, strict=True):
            inst.patch = patch
            inst.metadata["leakage"] = leakage.flags(inst.problem_statement, inst.paths, patch)
            inst.metadata["commit_message_leakage"] = leakage.flags(
                inst.commit_message, inst.paths, patch
            )
