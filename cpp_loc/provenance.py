"""Evidence from existing report payloads; heuristics never stand in for edit history."""

import base64
import email
import email.policy
import email.utils
import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlsplit

RULE_VERSION = "report-evidence-2"


def sha256(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value)
    except TypeError, ValueError:
        try:
            result = email.utils.parsedate_to_datetime(value)
        except TypeError, ValueError:
            return None
    return result.astimezone(UTC) if result.tzinfo is not None else None


def identity(source: str, ref: str, upstream: str, raw=None) -> str:
    """Repository-scoped source identity. Decode once; message-id case is significant."""
    prefix = f"{upstream.lower()}|{source}|"
    parsed = urlsplit(ref)
    if source == "github_issue":
        number = str(raw["number"]) if isinstance(raw, dict) and raw.get("number") else ref
        return prefix + number.rstrip("/").rsplit("/", 1)[-1].lstrip("#")
    if source == "gitlab_issue":
        return prefix + parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if source in {"lore_report", "pgsql_archive"}:
        if source == "pgsql_archive":
            match = re.search(r"/(?:m|message-id)/(?:flat/)?([^/]+)", parsed.path)
        else:
            match = re.search(r"/[^/]+/([^/]+)", parsed.path)
        return prefix + (unquote(match[1]).strip("<>") if match else ref)
    if source == "kernel_bugzilla":
        return prefix + parse_qs(parsed.query).get("id", [ref])[0]
    if source == "syzbot":
        bug = (raw or {}).get("bug", {})
        return prefix + (f"id={bug['id']}" if bug.get("id") else ref)
    return prefix + ref


def task_kind(title: str, body: str, labels: list[str], issue_type: str | None) -> dict:
    """Conservative positive evidence, with explicit unknown/conflicting outcomes."""
    names = [*labels, *([issue_type] if issue_type else [])]
    feature = [
        x
        for x in names
        if re.fullmatch(r"(?:type\s*[:/]\s*)?(?:feature(?: request)?|enhancement)", x.strip(), re.I)
    ]
    other = [x for x in names if re.fullmatch(r"question|documentation|discussion", x, re.I)]
    bug = [x for x in names if re.search(r"\b(bug|regression|crash|miscompile|fuzz)\b", x, re.I)]
    if re.search(r"\bfeature request\b|^\[feature\]", title, re.I):
        feature.append("feature request in title")
    if re.search(
        r"\b(bug|regression|crash(?:es)?|miscompil\w*|use.after.free|segfault)\b", title, re.I
    ):
        bug.append("defect term in title")
    if "The following bug has been logged" in body:
        bug.append("PostgreSQL bug form in body")
    if feature and bug:
        kind, evidence = "unknown", ["conflicting bug/feature signals", *bug, *feature]
    elif feature:
        kind, evidence = "feature", feature
    elif other and not bug:
        kind, evidence = "other", other
    elif bug:
        kind, evidence = "bug", bug
    else:
        kind, evidence = "unknown", ["no explicit task evidence"]
    return {"kind": kind, "evidence": evidence, "confidence": "heuristic", "rule": RULE_VERSION}


def mail_kind(subject: str, body: str, sender: str = "") -> dict:
    if re.search(r"\[.*?\bPATCH\b|^pgsql:", subject, re.I):
        kind = "reply" if re.match(r"re:", subject, re.I) else "patch_submission"
        evidence = ["patch/commit subject"]
    elif re.search(r"kernel test robot|lkp@intel.com|syzbot", sender + "\n" + subject, re.I):
        kind, evidence = "automated_diagnostic", ["explicit diagnostic sender/subject"]
    elif re.match(r"re:", subject, re.I):
        kind, evidence = "reply", ["reply subject"]
    elif task_kind(subject, body, [], None)["kind"] == "bug":
        kind, evidence = "explicit_bug_report", ["defect title or bug form"]
    else:
        kind, evidence = "ordinary_message", ["no positive report-kind evidence"]
    return {"kind": kind, "evidence": evidence, "confidence": "heuristic", "rule": RULE_VERSION}


def report_evidence(src, ref: str, raw, parsed: tuple) -> dict:
    """Preserve exactly the selected title/body plus source-specific timestamp evidence.

    This is separate from Source.parse so legacy text selection stays unchanged.
    """
    from .reports import clean_body, html_to_text

    title, body, extra = parsed
    processed = f"{title.strip()}\n\n{body.strip()}".strip()
    upstream = getattr(src, "upstream", getattr(src, "project", ""))
    raw_title, raw_body = title, body
    created, updated, version_at, version_basis = None, None, None, None
    labels, issue_type, selected_id = [], None, None
    selection = "title plus issue body"
    annotation = {"kind": "unknown", "confidence": "heuristic", "evidence": []}
    details = {}
    if src.name in {"github_issue", "gitlab_issue"}:
        raw_title = raw.get("title") or ""
        raw_body = raw.get("body" if src.name == "github_issue" else "description") or ""
        created, updated = raw.get("created_at"), raw.get("updated_at")
        labels = [
            x.get("name", "") if isinstance(x, dict) else str(x) for x in raw.get("labels", [])
        ]
        itype = raw.get("type") or raw.get("issue_type")
        issue_type = itype.get("name") if isinstance(itype, dict) else itype
        selected_id = raw.get("id")
        details["issue_type_payload"] = itype
    elif src.name == "lore_report":
        msg = email.message_from_bytes(base64.b64decode(raw), policy=email.policy.default)
        part = msg.get_body(preferencelist=("plain",))
        try:
            raw_body = part.get_content(errors="strict") if part else ""
        except LookupError, UnicodeDecodeError, KeyError:
            raw_body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
        selected_id = str(msg.get("Message-ID", "")).strip("<>") or None
        created = str(msg.get("Date", "")) or None
        version_at, version_basis = created, "immutable mail Date header; sender timestamp"
        selection = "linked mail; plain part; remove quotes and signature"
        annotation = mail_kind(title, raw_body, str(msg.get("From", "")))
        details["legacy_lore_kind"] = extra.get("report_kind")
        details["in_reply_to"] = str(msg.get("In-Reply-To", "")) or None
    elif src.name == "pgsql_archive":
        messages = src.messages(raw)
        position = extra["report_thread_position"]
        raw_title, selected_id, raw_body = messages[position]
        headers = re.findall(
            r'<table\b[^>]*class="[^"]*message-header[^"]*"[^>]*>(.*?)</table>', raw, re.S
        )
        header = headers[position] if position < len(headers) else ""
        dates = re.search(r"Date:</th>\s*<td>(.*?)</td>", header, re.S)
        created = html_to_text(dates[1]).strip() if dates else None
        # Archive dates without a zone are preserved, but never silently interpreted as UTC.
        version_at, version_basis = created, "archived mail date; requires explicit timezone"
        selection = extra["report_pick"] + "; remove quotes and signature"
        annotation = mail_kind(raw_title, raw_body)
        details.update({k: v for k, v in extra.items() if k.startswith("report_thread_")})
    elif src.name == "syzbot":
        bug = raw["bug"]
        created = bug.get("first-crash")
        crash = (bug.get("crashes") or [None])[0]
        selected_id = crash.get("crash-report-link") if crash else None
        # Aggregate first-crash is NOT the selected crash's timestamp.
        version_at = (crash.get("timestamp") or crash.get("time")) if crash else None
        version_basis = "selected crash timestamp, when present; current title version unknown"
        details["selected_crash_at"] = version_at
        details["selected_crash"] = crash
        version_at = None  # The concatenated current title also needs version evidence.
        selection = "crashes[0] report link (not assumed earliest); current bug title"
        annotation = {
            "kind": "automated_diagnostic",
            "confidence": "source",
            "evidence": ["syzbot crash report"],
        }
    elif src.name == "kernel_bugzilla":
        bug, comment = raw["bug"], raw.get("comment") or {}
        created, updated = bug.get("creation_time"), bug.get("last_change_time")
        selected_id = comment.get("id")
        details["comment_created_at"] = comment.get("creation_time") or comment.get("time")
        details["severity"] = bug.get("severity")
        issue_type = "feature" if bug.get("severity") == "enhancement" else "bug"
        selection = "current bug summary plus first cached comment"
    task = task_kind(title, body, labels, issue_type)
    if src.name == "syzbot" and body:
        task = {
            "kind": "bug",
            "confidence": "source",
            "evidence": ["nonempty syzbot diagnostic"],
            "rule": RULE_VERSION,
        }
    if src.name in {"github_issue", "gitlab_issue", "kernel_bugzilla"}:
        annotation = {
            "kind": "explicit_bug_report" if task["kind"] == "bug" else "unknown",
            "confidence": "heuristic",
            "evidence": task["evidence"],
        }
    if annotation["kind"] == "automated_diagnostic" and clean_body(body):
        task = {
            "kind": "bug",
            "confidence": "heuristic",
            "evidence": annotation["evidence"],
            "rule": RULE_VERSION,
        }
    raw_text = raw_title + "\n\n" + raw_body
    payload = src.consumed.get(src.cache_path(ref).relative_to(src.cache_dir).as_posix())
    return {
        "rule": RULE_VERSION,
        "source": src.name,
        "ref": ref,
        "identity": identity(src.name, extra["report_url"], upstream, raw),
        "url": extra["report_url"],
        "selected_id": selected_id,
        "selection_rule": selection,
        "created_at": created,
        "resource_updated_at": updated,
        "text_version_at": version_at,
        "text_version_basis": version_basis,
        "raw_text": raw_text,
        "raw_text_sha256": sha256(raw_text),
        "processed_text_sha256": sha256(processed),
        "payload": payload,
        "labels": labels,
        "issue_type": issue_type,
        "task": task,
        "annotation": annotation,
        **details,
    }


def chronology(report: dict | None, fix_at: str | None) -> dict:
    """Creation and exact consumed version are two independent checks."""
    fix = utc(fix_at)
    report = report or {}
    creation = utc(report.get("created_at"))
    version = utc(report.get("text_version_at"))
    updated = utc(report.get("resource_updated_at"))
    fetched = utc((report.get("payload") or {}).get("fetched_at"))

    def state(date):
        return (
            "unknown"
            if date is None or fix is None
            else ("supported-pre-fix" if date < fix else "post-fix")
        )

    version_state, evidence = "unknown", ["no historical text-version evidence"]
    if version is not None:
        version_state, evidence = state(version), [report.get("text_version_basis")]
    elif fix is not None and fetched is not None and fetched < fix:
        version_state, evidence = "supported-pre-fix", ["exact cached payload fetched before fix"]
    elif fix is not None and updated is not None and updated < fix:
        version_state, evidence = "supported-pre-fix", ["resource last-update timestamp before fix"]
    if creation is not None and fix is not None and creation >= fix:
        version_state, evidence = "post-fix", ["report created at/after fix"]
    return {
        "creation": {"state": state(creation), "evidence": report.get("created_at")},
        "text_version": {"state": version_state, "evidence": evidence},
        "resource_updated_after_fix": bool(fix and updated and updated >= fix),
        "rule": RULE_VERSION,
    }


def assistance(raw_message: str | None) -> dict:
    if raw_message is None:
        return {"status": "unknown", "evidence": [], "scope": "fixing commit message"}
    evidence = [
        line
        for line in raw_message.splitlines()
        if re.match(r"(?:Assisted-by|Claude-Session):", line, re.I)
        or (
            re.search(
                r"co-authored-by:|\b(?:generated|assisted|written) (?:with|by|using)\b", line, re.I
            )
            and re.search(
                r"\b(claude|copilot|chatgpt|codex|gemini|openai|anthropic|AI)\b", line, re.I
            )
        )
    ]
    return {
        "status": "observed" if evidence else "not-observed",
        "evidence": evidence,
        "scope": "explicit fixing-commit markers only; not-observed does not mean human-only",
    }
