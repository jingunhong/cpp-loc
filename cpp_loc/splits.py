"""Repository-scoped evidence groups followed by deterministic temporal partitions."""

from collections import Counter, defaultdict

from .provenance import json_bytes, sha256, utc

GROUP_RULE = "groups-1"
SPLIT_RULE = "temporal-1"
DEFAULTS = {
    "pool_start": "2024-01-01T00:00:00Z",
    "buffer_start": "2026-03-01T00:00:00Z",
    "test_start": "2026-06-01T00:00:00Z",
    "dev_size": 300,
    "min_train_size": 1,
}


def evidence(row):
    return row["metadata"]["integrity"]


def groups(rows: list[dict]) -> dict:
    ids = [r["instance_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate instance IDs in scanned population")
    parent = dict.fromkeys(ids)
    parent.update((x, x) for x in ids)

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges, first = [], {}
    fixes, texts = defaultdict(list), defaultdict(list)
    commits = {(r["repo"].lower(), r["fix_commit"]): r["instance_id"] for r in rows}

    def link(a, b, reason, key):
        if a == b:
            return
        a, b = sorted((a, b))
        ra, rb = root(a), root(b)
        parent[max(ra, rb)] = min(ra, rb)
        edges.append({"a": a, "b": b, "reason": reason, "key": key})

    for row in sorted(rows, key=lambda r: r["instance_id"]):
        inst, repo, ev = row["instance_id"], row["repo"].lower(), evidence(row)
        keys = set()
        historical = ev["reports"].get("historical_selected_identity")
        if historical:
            keys.add(("shared_report", historical))
        for ref in ev["reports"]["references"]:
            if ref["state"] != "pull_request":
                # Unresolved references are still conservative grouping evidence.
                keys.add(("shared_report", ref["identity"]))
                if ref.get("reference_identity"):
                    keys.add(("shared_report", ref["reference_identity"]))
        git = ev["git"]
        if git.get("stable_patch_id"):
            keys.add(("exact_stable_patch", repo + "|" + git["stable_patch_id"]))
        for backport in git.get("backports", []):
            if backport["sha"]:
                keys.add(("verified_backport", repo + "|" + backport["sha"]))
                target = commits.get((repo, backport["sha"]))
                if target:
                    link(inst, target, "verified_backport", backport["sha"])
        for reason, key in sorted(keys):
            scoped = (repo, reason, key)
            if scoped in first:
                link(inst, first[scoped], reason, key)
            else:
                first[scoped] = inst
        for target in git.get("fixes_targets", []):
            if target["sha"]:
                fixes[repo + "|" + target["sha"]].append(inst)
        text = row.get("problem_statement")
        if text:
            texts[repo + "|" + sha256(" ".join(text.split()))].append(inst)
    members = defaultdict(list)
    for inst in sorted(ids):
        members[root(inst)].append(inst)
    entries, membership = [], {}
    for group in members.values():
        group_id = "group-" + sha256(json_bytes(group))[:24]
        entries.append({"group_id": group_id, "members": group, "size": len(group)})
        membership.update((inst, group_id) for inst in group)
    return {
        "rule": GROUP_RULE,
        "groups": sorted(entries, key=lambda x: x["group_id"]),
        "membership": membership,
        "edges": sorted(edges, key=lambda x: (x["a"], x["b"], x["reason"], x["key"])),
        "size_histogram": dict(sorted(Counter(g["size"] for g in entries).items())),
        "shared_fixes_targets_not_grouped": {
            k: sorted(set(v)) for k, v in sorted(fixes.items()) if len(set(v)) > 1
        },
        "duplicate_texts_audit_only": {
            k: sorted(v) for k, v in sorted(texts.items()) if len(v) > 1
        },
        "scope": "only the complete input extraction population, before eligibility filtering",
    }


def config(
    *, test_end: str, role: str = "adaptation-candidate", view: str = "strict", **kwargs
) -> dict:
    cfg = {**DEFAULTS, **kwargs, "test_end": test_end, "role": role, "view": view}
    dates = [utc(cfg[k]) for k in ("pool_start", "buffer_start", "test_start", "test_end")]
    if any(d is None for d in dates) or dates != sorted(set(dates)):
        raise ValueError("cutoffs must be strictly increasing explicit timezone-aware timestamps")
    if cfg["dev_size"] < 1:
        raise ValueError("dev_size must be positive")
    if cfg["min_train_size"] < 1:
        raise ValueError("min_train_size must be positive")
    if role not in {"adaptation-candidate", "provisional-transfer-evaluation", "evaluation-only"}:
        raise ValueError("unknown source/target role")
    if view not in {"strict", "diagnostic"}:
        raise ValueError("view must be strict or diagnostic")
    return cfg


def partition(timestamp: str | None, cfg: dict) -> str:
    time = utc(timestamp)
    if time is None:
        return "unknown_time"
    for name, lower, upper in (
        ("pool", "pool_start", "buffer_start"),
        ("buffer", "buffer_start", "test_start"),
        ("test", "test_start", "test_end"),
    ):
        if utc(cfg[lower]) <= time < utc(cfg[upper]):
            return name
    return "before_pool" if time < utc(cfg["pool_start"]) else "after_test"


def split(rows: list[dict], grouped: dict, cfg: dict) -> dict:
    """Quarantine on the full population, including ineligible rows in each group."""
    by_id = {r["instance_id"]: r for r in rows}
    if set(by_id) != set(grouped["membership"]):
        raise ValueError("group population differs from split input")
    assignments, group_reasons, candidates = {}, {}, {"pool": [], "test": []}
    for group in grouped["groups"]:
        gid, members = group["group_id"], group["members"]
        parts = {partition(evidence(by_id[i])["git"].get("committer_at"), cfg) for i in members}
        if "unknown_time" in parts:
            group_reasons[gid] = "group_time_unknown"
        elif len(parts) != 1:
            group_reasons[gid] = "group_crosses_temporal_partition"
        elif cfg["view"] == "strict" and len(members) > 1:
            group_reasons[gid] = "not_one_to_one_within_population"
        for inst in members:
            local = evidence(by_id[inst])["eligibility"]
            part = partition(evidence(by_id[inst])["git"].get("committer_at"), cfg)
            reasons = list(local["excluded"])
            if cfg["view"] == "strict":
                reasons += local["unknown"]
            if gid in group_reasons:
                reasons.append(group_reasons[gid])
            if part not in candidates:
                reasons.append(part)
            if cfg["role"] != "adaptation-candidate" and part == "pool":
                reasons.append("evaluation_only_role")
            assignments[inst] = {
                "group_id": gid,
                "temporal_partition": part,
                "partition": "excluded",
                "reasons": sorted(set(reasons)),
            }
            if not reasons:
                candidates[part].append(inst)
    refused = None
    pool = candidates["pool"]
    eligible_before_train_dev = len(pool)
    min_train_size = cfg.get("min_train_size", 1)
    dev = []
    if cfg["role"] == "adaptation-candidate":
        while True:
            pool.sort(key=lambda i: (utc(evidence(by_id[i])["git"]["committer_at"]), i))
            if len(pool) < cfg["dev_size"] + min_train_size:
                minimum = (
                    "nonempty training"
                    if min_train_size == 1
                    else f"at least {min_train_size} training records"
                )
                refused = (
                    f"need {cfg['dev_size']} dev records plus {minimum}; "
                    f"only {len(pool)} eligible pool records"
                )
                break
            dev = pool[-cfg["dev_size"] :]
            train_groups = {assignments[i]["group_id"] for i in pool[: -cfg["dev_size"]]}
            crossing = train_groups & {assignments[i]["group_id"] for i in dev}
            if not crossing:
                break
            for inst in pool:
                gid = assignments[inst]["group_id"]
                if gid in crossing:
                    assignments[inst]["reasons"].append("group_crosses_train_dev")
                    group_reasons[gid] = "group_crosses_train_dev"
            pool = [i for i in pool if assignments[i]["group_id"] not in crossing]
    if refused is None:
        for inst in pool:
            assignments[inst]["partition"] = "dev" if inst in set(dev) else "train"
        for inst in candidates["test"]:
            assignments[inst]["partition"] = "test"
    else:
        for inst in pool + candidates["test"]:
            assignments[inst]["reasons"].append("configuration_refused")
    counts = dict(Counter(a["partition"] for a in assignments.values()))
    return {
        "rule": SPLIT_RULE,
        "config": cfg,
        "status": "refused"
        if refused
        else ("strict-candidate" if cfg["view"] == "strict" else "provisional-diagnostic"),
        "refusal": refused,
        "counts": counts,
        "eligible_before_train_dev": {"pool": eligible_before_train_dev},
        "eligible_before_dev": {"pool": len(pool), "test": len(candidates["test"])},
        "exclusion_counts": dict(
            sorted(Counter(reason for a in assignments.values() for reason in a["reasons"]).items())
        ),
        "group_quarantines": dict(sorted(group_reasons.items())),
        "membership": dict(sorted(assignments.items())),
    }
