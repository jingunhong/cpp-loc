"""A report-only explicit-path baseline and deterministic descriptive audits."""

import re
import statistics
from collections import Counter, defaultdict

from . import filters, leakage
from .provenance import sha256, utc
from .splits import evidence

BASELINE_RULE = "explicit-paths-1"
_EXTENSIONS = "|".join(
    re.escape(s[1:]) for s in sorted(filters.CPP_SUFFIXES, key=lambda x: (-len(x), x))
)
_TOKEN = re.compile(
    r"(?<![\w./\\+-])(?:[A-Za-z]:)?[\w./\\+~-]+\.(?:" + _EXTENSIONS + r")(?![\w.-])"
)


def predict(
    report: str, inventory, *, unique_basename: bool = True, basename_index=None
) -> list[str]:
    """Only report + pre-fix regular-file inventory enter prediction.

    Tokens end before ``:line[:column]``; slash/backslash paths accept leading ./ and
    arbitrary build prefixes by dropping leading components until a tree path matches.
    Bare basenames are optional and must be unique across the entire tree. Whitespace
    inside a filename is unsupported. Non-target files never become predictions.
    """
    tree = inventory if isinstance(inventory, set) else set(inventory)
    basenames = basename_index if basename_index is not None else defaultdict(list)
    if unique_basename and basename_index is None:
        for path in tree:
            basenames[path.rsplit("/", 1)[-1]].append(path)
    predicted = set()
    for match in _TOKEN.finditer(report):
        token = match[0].replace("\\", "/")
        token = re.sub(r"^[A-Za-z]:", "", token).lstrip("/")
        while token.startswith("./"):
            token = token[2:]
        if ".." in token.split("/"):
            continue
        parts = token.split("/")
        found = False
        for start in range(len(parts) - 1):
            candidate = "/".join(parts[start:])
            if candidate in tree and filters.is_target_path(candidate):
                predicted.add(candidate)
                found = True
                break
        if not found and unique_basename:
            matches = basenames.get(parts[-1], [])
            if len(matches) == 1:
                path = next(iter(matches))
                if filters.is_target_path(path):
                    predicted.add(path)
    return sorted(predicted)


def score(predicted: list[str], gold: list[str]) -> dict:
    p, g = set(predicted), set(gold)
    correct = len(p & g)
    precision = correct / len(p) if p else 0.0
    recall = correct / len(g) if g else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if correct else 0.0,
        "empty_prediction": not p,
    }


def baseline_result(
    row: dict, inventory, error: str | None = None, *, basename_index=None, tree_sha=None
) -> dict:
    ev = evidence(row)
    gold = ev["git"]["primary_files"]
    predicted = (
        predict(row["problem_statement"], inventory, basename_index=basename_index)
        if inventory is not None
        else []
    )
    hints = leakage.flags(row["problem_statement"], gold, "")
    stratum = "path" if hints["path"] else "basename" if hints["basename"] else "no_file_hint"
    return {
        "instance_id": row["instance_id"],
        "repo": row["repo"],
        "source": row["problem_source"],
        "kind": ev["eligibility"]["report_kind"],
        "hint_stratum": stratum,
        "predictions": predicted,
        **score(predicted, gold),
        "status": "ok" if inventory is not None else "inventory_unavailable",
        "error": error,
        "inventory_git_tree": tree_sha,
        "inventory_sha256": sha256("\0".join(sorted(inventory)))
        if inventory is not None and tree_sha is None
        else None,
        "gold_status": "available" if ev["git"].get("changes") is not None else "unavailable",
        "rule": BASELINE_RULE,
    }


def baseline_summary(results: list[dict]) -> dict:
    buckets = defaultdict(list)
    for row in results:
        buckets["all"].append(row)
        for key in ("repo", "source", "kind", "hint_stratum"):
            buckets[key + ":" + str(row[key])].append(row)
    return {
        "rule": BASELINE_RULE,
        "denominator": "all report-backed attempted instances; infrastructure failures score zero",
        "slices": {
            key: {
                "n": len(rows),
                **{
                    metric: statistics.mean(r[metric] for r in rows)
                    for metric in ("precision", "recall", "f1", "empty_prediction")
                },
                "status_counts": dict(Counter(r["status"] for r in rows)),
                "gold_status_counts": dict(Counter(r["gold_status"] for r in rows)),
            }
            for key, rows in sorted(buckets.items())
        },
    }


def population_summary(rows: list[dict], grouped: dict) -> dict:
    reports = [r for r in rows if r.get("problem_statement")]
    exclusions = Counter(reason for r in rows for reason in evidence(r)["eligibility"]["excluded"])
    unknowns = Counter(reason for r in rows for reason in evidence(r)["eligibility"]["unknown"])
    reused = Counter()
    statuses, author_months, committer_months = Counter(), Counter(), Counter()
    ages = []
    added_gold = all_added = refs_multi = multi_issues = unresolved_refs = 0
    reference_states = Counter()
    for row in reports:
        ev = evidence(row)
        git, refs = ev["git"], ev["reports"]
        selected = refs["selected"] or {}
        if selected.get("identity"):
            reused[selected["identity"]] += 1
        created, fix = utc(selected.get("created_at")), utc(git.get("committer_at"))
        if created and fix:
            ages.append((fix - created).total_seconds() / 86400)
        author, committer = (
            utc(git.get("author_at") or row.get("created_at")),
            utc(git.get("committer_at")),
        )
        author_months[author.strftime("%Y-%m") if author else "unknown"] += 1
        committer_months[committer.strftime("%Y-%m") if committer else "unknown"] += 1
        changes = git.get("changes") or []
        statuses.update({c["status"] for c in changes})
        added = {c["new_path"] for c in changes if c["status"] == "A"}
        old_gold = {x["file"] for x in row["file_changes"]}
        added_gold += bool(old_gold & added)
        all_added += bool(old_gold) and old_gold <= added
        refs_multi += len(set(row["metadata"].get("references", []))) > 1
        multi_issues += (
            len({r["identity"] for r in refs["references"] if r["state"] == "report"}) > 1
        )
        unresolved_refs += any(
            r["state"] not in {"report", "pull_request", "target is a patch"}
            for r in refs["references"]
        )
        reference_states.update(r["state"] for r in refs["references"])
    strict = [r for r in rows if evidence(r)["eligibility"]["strict_local"]]
    sizes = {g["group_id"]: g["size"] for g in grouped["groups"]}
    singleton = [r for r in strict if sizes[grouped["membership"][r["instance_id"]]] == 1]
    return {
        "extraction_instances": len(rows),
        "report_backed_instances": len(reports),
        "strict_local_before_grouping": len(strict),
        "strict_one_to_one": len(singleton),
        "diagnostic_local": sum(evidence(r)["eligibility"]["diagnostic"] for r in rows),
        "exclusion_counts_overlapping": dict(sorted(exclusions.items())),
        "unknown_counts_overlapping": dict(sorted(unknowns.items())),
        "all_non_test_in_scope_among_strict": sum(
            evidence(r)["eligibility"]["all_non_test_changes_in_scope"] is True for r in singleton
        ),
        "author_year_counts": dict(
            sorted(
                Counter(
                    {
                        year: sum(v for k, v in author_months.items() if k.startswith(year))
                        for year in {k[:4] for k in author_months}
                    }
                ).items()
            )
        ),
        "author_month_counts": dict(sorted(author_months.items())),
        "committer_month_counts": dict(sorted(committer_months.items())),
        "report_age_days": {
            "known": len(ages),
            "unknown": len(reports) - len(ages),
            "negative": sum(a < 0 for a in ages),
            "min": min(ages) if ages else None,
            "median": statistics.median(ages) if ages else None,
            "max": max(ages) if ages else None,
        },
        "reused_selected_reports": dict(sorted((k, v) for k, v in reused.items() if v > 1)),
        "task_counts": dict(Counter(evidence(r)["eligibility"]["task"] for r in reports)),
        "kind_counts": dict(Counter(evidence(r)["eligibility"]["report_kind"] for r in reports)),
        "status_instance_counts": dict(sorted(statuses.items())),
        "legacy_gold_has_addition": added_gold,
        "legacy_gold_all_added": all_added,
        "multiple_legacy_references": refs_multi,
        "multiple_resolved_reports": multi_issues,
        "instances_with_unresolved_references": unresolved_refs,
        "reference_state_counts": dict(sorted(reference_states.items())),
        "assistance_counts": dict(Counter(evidence(r)["ai_assisted"]["status"] for r in reports)),
        "assistance_note": (
            "explicit fixing-message markers; not-observed does not establish human-only work"
        ),
        "group_size_histogram": grouped["size_histogram"],
    }


def sample(rows: list[dict], grouped: dict, seed: str = "cpp-loc-v3-2026-09-14") -> list[dict]:
    """One seeded example per relevant stratum; targeted, not a prevalence estimate."""
    categories = defaultdict(list)
    sizes = {g["group_id"]: g["size"] for g in grouped["groups"]}
    by_id = {r["instance_id"]: r for r in rows}
    for row in rows:
        if not row.get("problem_statement"):
            continue
        ev = evidence(row)
        elig = ev["eligibility"]
        keys = {"normal_report", "task:" + elig["task"], "kind:" + elig["report_kind"]}
        keys.update(elig["excluded"] + elig["unknown"])
        if sizes[grouped["membership"][row["instance_id"]]] > 1:
            keys.add("shared_group")
        if ev["ai_assisted"]["status"] == "observed":
            keys.add("explicit_assistance")
        if elig["strict_local"]:
            keys.add("strict_local")
        for key in keys:
            categories[key].append(row["instance_id"])
    chosen = defaultdict(list)
    for key, ids in sorted(categories.items()):
        inst = min(ids, key=lambda i: sha256(seed + "|" + key + "|" + i))
        chosen[inst].append(key)
    result = []
    for inst, strata in sorted(chosen.items()):
        row, ev = by_id[inst], evidence(by_id[inst])
        selected = ev["reports"]["selected"] or {}
        result.append(
            {
                "instance_id": inst,
                "seed": seed,
                "strata": strata,
                "report_url": selected.get("url") or row["metadata"].get("report_url"),
                "report_excerpt": row["problem_statement"][:1600],
                "payload": selected.get("payload"),
                "task_evidence": selected.get("task"),
                "kind_evidence": selected.get("annotation"),
                "chronology": ev["chronology"],
                "changes": ev["git"].get("changes"),
                "eligibility": ev["eligibility"],
                "review": {"performed": False, "reviewer": None, "judgment": None},
            }
        )
    return result
