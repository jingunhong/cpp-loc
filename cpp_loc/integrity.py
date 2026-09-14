"""Enrich an existing extraction population; validate separately from mining."""

import re
import subprocess
from pathlib import Path, PurePosixPath

from . import EXTRACTOR_VERSION, filters, gitutil
from .provenance import assistance, chronology, identity, sha256, utc

RULE_VERSION = "eligibility-1"


def normalized_path(path) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and "\0" not in path
        and "\\" not in path
        and not path.startswith("/")
        and not re.match(r"^[A-Za-z]:", path)
        and all(p not in {"", ".", ".."} for p in path.split("/"))
        and PurePosixPath(path).as_posix() == path
    )


def git_evidence(row: dict, clone: Path, upstream_revision: str) -> dict:
    """Offline commit/tree checks; missing blobs do not trigger a fetch."""
    result = {
        "errors": [],
        "upstream_revision": upstream_revision,
        "rename_policy": gitutil.RENAME_POLICY,
        "path_rule": filters.PATH_RULE_VERSION,
        "changes": None,
        "primary_files": [],
        "base_files_present": [],
        "stable_patch_id": None,
        "backports": [],
        "fixes_targets": [],
    }
    errors = result["errors"]
    if any(
        not isinstance(row.get(key), str) or not re.fullmatch(r"[0-9a-f]{40}", row[key])
        for key in ("fix_commit", "base_commit")
    ):
        errors.append("commit_not_full_sha")
        return result
    try:
        fix = gitutil.commit_info(clone, row["fix_commit"])
        base = gitutil.commit_info(clone, row["base_commit"])
        result.update(
            {
                "fix_sha": fix["sha"],
                "base_sha": base["sha"],
                "parents": fix["parents"],
                "author_at": fix["author_at"],
                "committer_at": fix["committer_at"],
                "commit_message": filters.message_evidence(fix["message"]),
            }
        )
        if not fix["parents"]:
            errors.append("root_commit")
        elif fix["parents"] != [base["sha"]]:
            errors.append("not_single_parent_base")
        if fix["sha"] != row["fix_commit"] or base["sha"] != row["base_commit"]:
            errors.append("commit_not_full_sha")
        if filters.is_revert(fix["message"]):
            errors.append("revert")
        changes = gitutil.changes(clone, base["sha"], fix["sha"])
        result["changes"] = changes
        paths = {c[k] for c in changes for k in ("old_path", "new_path") if c[k] is not None}
        result["primary_files"] = filters.gold_files(paths)
        result["base_files_present"] = gitutil.tree_files(
            clone, base["sha"], result["primary_files"]
        )
        # Exact full-diff IDs only; never substitute the historical gold-only patch.
        try:
            result["stable_patch_id"] = gitutil.stable_patch_id(clone, base["sha"], fix["sha"])
            result["patch_id_state"] = "available"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            result["patch_id_state"] = "unavailable_full_diff_offline"
            result["patch_id_unavailable_reason"] = (
                str(exc) if isinstance(exc, FileNotFoundError) else type(exc).__name__
            )
        for ref in dict.fromkeys(filters.fixes_shas(fix["message"])):
            try:
                resolved = gitutil.run(
                    clone, "rev-parse", "--verify", f"{ref}^{{commit}}", offline=True
                ).strip()
            except subprocess.CalledProcessError:
                resolved = None
            result["fixes_targets"].append({"reference": ref, "sha": resolved})
        backports = re.findall(
            r"\(cherry picked from commit ([0-9a-f]{7,40})\)|"
            r"^[ \t]*[Cc]ommit ([0-9a-f]{7,40}) upstream\.",
            fix["message"],
            re.M,
        )
        for a, b in backports:
            ref = a or b
            try:
                resolved = gitutil.run(
                    clone, "rev-parse", "--verify", f"{ref}^{{commit}}", offline=True
                ).strip()
                status = "verified_commit_reference"
            except subprocess.CalledProcessError:
                resolved, status = None, "unresolved"
            result["backports"].append(
                {
                    "reference": ref,
                    "sha": resolved,
                    "state": status,
                    "evidence": "explicit cherry-pick/upstream trailer",
                }
            )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
        errors.append("git_objects_unavailable_or_invalid")
        result["error_detail"] = type(exc).__name__
    return result


def all_reports(row: dict, sources: list, raw_message: str | None) -> dict:
    """Resolve every available reference, preserving known PRs and unresolved references.

    The selected report is matched by exact processed text, never replaced with another
    issue or today's body. Alternate successful reports contribute grouping identities.
    """
    resolved, selected = [], None
    refs = row["metadata"].get("report_refs", {})
    for src in sources:
        candidates = list(refs.get(src.name, []))
        if raw_message is not None:
            candidates.extend(src.refs(raw_message))
            if src.name == "github_issue":
                # Includes closing lists and PR numbers in subjects; cache tells which is which.
                candidates += re.findall(r"(?<![\w/])#(\d+)\b", raw_message)
                up = re.escape(src.upstream)
                candidates += re.findall(
                    rf"https://github\.com/{up}/(?:issues|pull)/(\d+)\b", raw_message, re.I
                )
        for ref in dict.fromkeys(map(str, candidates)):
            entry = {
                "source": src.name,
                "ref": ref,
                "identity": identity(src.name, ref, row["repo"]),
            }
            try:
                raw = src.get(ref)
                if raw is None:
                    entry["state"] = "not_found"
                elif src.name == "github_issue" and "pull_request" in raw:
                    entry["state"] = "pull_request"
                else:
                    parsed = src.report(ref)
                    if isinstance(parsed, str):
                        entry["state"] = parsed
                    else:
                        title, body, extra = parsed
                        evidence = extra["report_provenance"]
                        entry["state"] = "report"
                        entry["identity"] = identity(src.name, evidence["url"], row["repo"], raw)
                        evidence["identity"] = entry["identity"]
                        entry["selected_identity"] = entry["identity"]
                        # Preserve both referenced and exactly selected mail identities.
                        entry["reference_identity"] = identity(src.name, ref, row["repo"], raw)
                        text = f"{title.strip()}\n\n{body.strip()}".strip()
                        entry["processed_text_sha256"] = sha256(text)
                        if (
                            selected is None
                            and row["problem_source"] == src.name
                            and row["problem_statement"] == text
                        ):
                            selected = evidence
                entry["payload"] = src.consumed[
                    src.cache_path(ref).relative_to(src.cache_dir).as_posix()
                ]
            except FileNotFoundError:
                entry["state"] = "offline_cache_miss"
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                entry["state"] = "invalid_cached_payload"
                entry["error"] = type(exc).__name__
            resolved.append(entry)
    # Retain the historical selected identity even when its payload is missing/changed.
    historical = row["metadata"].get("report_url")
    historical_identity = (
        identity(row["problem_source"], historical, row["repo"])
        if historical and row["problem_source"]
        else None
    )
    return {
        "selected": selected,
        "references": resolved,
        "historical_selected_identity": historical_identity,
        "selection_state": "matched_exact_text"
        if selected
        else (
            "no_report" if row["problem_statement"] is None else "payload_missing_or_text_mismatch"
        ),
    }


def eligibility(row: dict, evidence: dict) -> dict:
    """Explicit external-input errors remain effective under python -O."""
    git, reports = evidence["git"], evidence["reports"]
    excluded, unknown = list(git["errors"]), []
    changes, gold = git.get("changes"), git["primary_files"]
    if changes is None:
        unknown.append("full_changes_unknown")
    else:
        change_paths = [c[k] for c in changes for k in ("old_path", "new_path") if c[k] is not None]
        if any(not normalized_path(p) for p in change_paths + gold):
            excluded.append("invalid_path")
        target_changes = [
            c
            for c in changes
            if any(c[k] and filters.is_target_path(c[k]) for k in ("old_path", "new_path"))
        ]
        if any(c["status"] != "M" for c in target_changes):
            excluded.append("unsupported_target_status")
        if not filters.file_count_ok(gold):
            excluded.append("primary_file_count_outside_1_5")
        target_names = [c["new_path"] or c["old_path"] for c in target_changes]
        if len(target_names) != len(set(target_names)) or len(gold) != len(set(gold)):
            excluded.append("duplicate_primary_paths")
        if not set(gold) <= set(git["base_files_present"]):
            excluded.append("primary_file_missing_in_base")
    if not row.get("problem_statement"):
        excluded.append("no_report")
    report = reports["selected"]
    if row.get("problem_statement") and report is None:
        unknown.append("selected_report_payload_unverified")
    task = (report or {}).get("task", {"kind": "unknown"})["kind"]
    if task in {"feature", "other"}:
        excluded.append("task_" + task)
    elif task == "unknown":
        unknown.append("task_unknown")
    kind = (report or {}).get("annotation", {}).get("kind", "unknown")
    if kind == "patch_submission":
        excluded.append("patch_submission")
    elif kind not in {"explicit_bug_report", "automated_diagnostic"}:
        unknown.append("report_provenance_unresolved")
    # Count resolved issues, not PRs. Alternate mail refs remain grouping evidence too.
    issues = {x["identity"] for x in reports["references"] if x["state"] == "report"}
    if len(issues) > 1:
        excluded.append("multiple_report_references")
    if any(
        x["state"] not in {"report", "pull_request", "target is a patch"}
        for x in reports["references"]
    ):
        unknown.append("unresolved_report_references")
    if utc(git.get("committer_at")) is None:
        unknown.append("fix_availability_unknown")
    checks = evidence["chronology"]
    for check in ("creation", "text_version"):
        state = checks[check]["state"]
        if state == "post-fix":
            excluded.append("report_" + check + "_post_fix")
        elif state == "unknown":
            unknown.append("report_" + check + "_unknown")
    non_target = [
        c
        for c in (changes or [])
        if any(c[k] and not filters.is_target_path(c[k]) for k in ("old_path", "new_path"))
    ]
    all_non_test_in_scope = (
        all(
            filters.is_test_path(c[k]) or filters.is_target_path(c[k])
            for c in (changes or [])
            for k in ("old_path", "new_path")
            if c[k]
        )
        if changes is not None
        else None
    )
    return {
        "rule": RULE_VERSION,
        "excluded": sorted(set(excluded)),
        "unknown": sorted(set(unknown)),
        "strict_local": not excluded and not unknown,
        "diagnostic": bool(row.get("problem_statement")) and not excluded,
        "task": task,
        "report_kind": kind,
        "non_target_changes": non_target,
        "all_non_test_changes_in_scope": all_non_test_in_scope,
    }


def enrich(
    row: dict, clone: Path, upstream_revision: str, sources: list, *, reports_only=False
) -> dict:
    if reports_only:
        git = {
            "errors": [],
            "changes": None,
            "primary_files": [],
            "base_files_present": [],
            "upstream_revision": upstream_revision,
            "mode": "report_annotations_only",
        }
    else:
        git = git_evidence(row, clone, upstream_revision)
    raw_message = git.get("commit_message", {}).get("raw")
    report = all_reports(row, sources, raw_message)
    evidence = {
        "extractor_version": EXTRACTOR_VERSION,
        "git": git,
        "reports": report,
        "chronology": chronology(report["selected"], git.get("committer_at")),
        "ai_assisted": assistance(raw_message),
    }
    row = {**row, "metadata": {**row["metadata"], "integrity": evidence}}
    evidence["eligibility"] = eligibility(row, evidence)
    return row
