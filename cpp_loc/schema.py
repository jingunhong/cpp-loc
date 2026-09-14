"""Instance schema: one record per line of ``instances.jsonl``."""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_STR = (
    "instance_id",
    "repo",
    "base_commit",
    "fix_commit",
    "created_at",
    "commit_message",
    "patch",
)
SOURCES = frozenset(
    {"github_issue", "gitlab_issue", "syzbot", "lore_report", "kernel_bugzilla", "pgsql_archive"}
)


@dataclass
class Instance:
    instance_id: str
    repo: str
    base_commit: str
    fix_commit: str
    created_at: str
    problem_statement: str | None
    problem_source: str | None
    commit_message: str
    file_changes: list[dict]  # [{"file": "<repo-relative path>"}, ...], Multi-SWE-bench shape
    gold_functions: list[str] | None
    patch: str
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Instance:
        return cls(**json.loads(line))

    @property
    def paths(self) -> list[str]:
        return [f["file"] for f in self.file_changes]

    def validate(self) -> list[str]:
        """Return a list of problems; empty means the instance is valid."""
        errors = []
        for name in _REQUIRED_STR:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                errors.append(f"{name}: required non-empty string")
        if self.problem_statement is None:
            if self.problem_source is not None:
                errors.append("problem_source: must be null when problem_statement is null")
        elif not isinstance(self.problem_statement, str) or not self.problem_statement:
            errors.append("problem_statement: must be null or a non-empty string")
        elif self.problem_source not in SOURCES:
            errors.append(f"problem_source: must be one of {sorted(SOURCES)}")
        for name in ("base_commit", "fix_commit"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
                errors.append(f"{name}: not a full 40-char lowercase SHA")
        try:
            datetime.fromisoformat(self.created_at)
        except TypeError, ValueError:
            errors.append("created_at: not ISO-8601")
        if not isinstance(self.file_changes, list) or not self.file_changes:
            errors.append("file_changes: must be a non-empty list")
        elif not all(
            isinstance(f, dict) and isinstance(f.get("file"), str) and f["file"]
            for f in self.file_changes
        ):
            errors.append('file_changes: entries must be {"file": <non-empty path>}')
        if self.gold_functions is not None and not isinstance(self.gold_functions, list):
            errors.append("gold_functions: must be a list or null")
        if not isinstance(self.metadata, dict):
            errors.append("metadata: must be an object")
        return errors


RUNNER_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement", "file_changes")


def validate_runner(row: dict, *, exact: bool = False) -> list[str]:
    """Runner rows intentionally lack patches; raw extraction validation is separate."""
    from .integrity import normalized_path

    if not isinstance(row, dict):
        return ["runner row must be an object"]
    errors = []
    if exact and set(row) != set(RUNNER_FIELDS):
        errors.append("runner row must have exactly five contract fields")
    for key in RUNNER_FIELDS[:-1]:
        if not isinstance(row.get(key), str) or not row[key].strip():
            errors.append(f"{key}: required nonempty string")
    sha = row.get("base_commit")
    if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
        errors.append("base_commit: required full SHA")
    changes = row.get("file_changes")
    if not isinstance(changes, list) or not changes:
        errors.append("file_changes: required nonempty list")
    elif any(
        not isinstance(c, dict) or set(c) != {"file"} or not normalized_path(c["file"])
        for c in changes
    ):
        errors.append("file_changes: invalid path objects")
    elif len(changes) != len({c["file"] for c in changes}):
        errors.append("file_changes: duplicate paths")
    return errors
