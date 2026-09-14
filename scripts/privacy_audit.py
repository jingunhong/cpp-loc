"""Local screening of candidate text exports. Findings contain no matched personal values.

This is a review aid, not anonymization, secret verification, or legal clearance.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc.provenance import json_bytes, sha256  # noqa: E402

RULE = "publication-screen-2"
PATTERNS = {
    "email_like": re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "personal_home_path": re.compile(r"(?:/(?:home|Users)/[^\s/]+/|[A-Za-z]:\\Users\\[^\s\\]+\\)"),
    "ipv4_like": re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"),
    "phone_context": re.compile(r"\b(?:phone|tel|mobile)\s*[:=]\s*\+?[\d ()-]{7,}", re.I),
    "private_key_marker": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token_shape": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"
    ),
    "aws_access_key_shape": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "url_credentials": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I),
    "literal_credential_context": re.compile(
        r"\b(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"'][^\"'\n]{4,}[\"']", re.I
    ),
}


def flags(text: str) -> dict:
    return {
        name: len(pattern.findall(text))
        for name, pattern in PATTERNS.items()
        if pattern.search(text)
    }


def record_flags(value) -> dict:
    """Scan decoded strings so JSON escaping cannot hide quotes or line breaks."""
    if isinstance(value, str):
        return flags(value)
    result = Counter()
    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return {}
    for item in values:
        result.update(record_flags(item))
    return dict(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("choose a new output file")
    findings, counts, populations, hashes = [], defaultdict(Counter), Counter(), {}
    for path in args.paths:
        hashes[path.as_posix()] = sha256(path.read_bytes())
        with path.open(encoding="utf-8") as file:
            for line in file:
                row = json.loads(line)
                if not row.get("problem_statement"):
                    continue
                repo = row["repo"]
                populations[repo] += 1
                fields = {"problem_statement": row["problem_statement"]}
                ev = row.get("metadata", {}).get("integrity", {})
                if ev:
                    fields["companion_evidence"] = ev
                for field, text in fields.items():
                    matched = record_flags(text)
                    if matched:
                        findings.append(
                            {
                                "instance_id": row["instance_id"],
                                "repo": repo,
                                "field": field,
                                "matches": matched,
                            }
                        )
                        counts[repo + "|" + field].update(matched.keys())
    result = {
        "rule": RULE,
        "publication_status": "held_for_privacy_and_rights_review",
        "scope": "report-backed rows only; pattern screening, not absence-of-PII certification",
        "limitations": (
            "May match examples, service accounts, version numbers, and identifiers. "
            "Does not detect arbitrary names, sensitive narrative data, all credentials, "
            "or establish redistribution rights. No matched values are emitted."
        ),
        "input_hashes": hashes,
        "report_backed_instances": dict(populations),
        "flagged_instance_counts_by_field": {k: dict(v) for k, v in sorted(counts.items())},
        "findings": findings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(result))
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"findings", "input_hashes"}}, indent=2
        )
    )


if __name__ == "__main__":
    main()
