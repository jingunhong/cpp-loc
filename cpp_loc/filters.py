"""Pure filter functions applied to mined commits."""

import re

PATH_RULE_VERSION = "cpp-paths-1"
CPP_SUFFIXES = frozenset(
    {
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".cxx",
        ".hh",
        ".hpp",
        ".hxx",
        ".inc",
        ".inl",
        ".ipp",
        ".tpp",
        ".tcc",
    }
)
_TEST_DIRS = frozenset({"test", "tests", "testing", "selftests", "unittest", "unittests"})
_TEST_FILE_RE = re.compile(r"(^|[_.-])tests?([_.-]|$)", re.IGNORECASE)
_REVERT_RE = re.compile(r"^\s*This reverts commit\b", re.MULTILINE)
_TRAILER_KEYS = {
    "signed-off-by",
    "reviewed-by",
    "acked-by",
    "tested-by",
    "reported-by",
    "suggested-by",
    "co-developed-by",
    "co-authored-by",
    "cc",
    "link",
    "fixes",
    "closes",
    "resolves",
    "change-id",
    "reviewed-on",
    "message-id",
    "bug",
    "references",
    "see-also",
    "discussion",
    "backpatch-through",
    "author",
    "security",
    "claude-session",
}
_TRAILER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):[ \t]")
_FIXES_SHA_RE = re.compile(r"^Fixes:\s*([0-9a-f]{7,40})\b", re.IGNORECASE | re.MULTILINE)
_REPORT_RE = re.compile(r"^(?:Bug: #(\d+)|Discussion: (\S+))", re.MULTILINE)
_REPORTED_RE = re.compile(r"^(?:Reported-by|Bug):", re.MULTILINE)
_ISSUE_KEYWORDS = r"\b(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s*:?\s*"
MIN_GOLD_FILES, MAX_GOLD_FILES = 1, 5


def is_cpp_source(path: str) -> bool:
    """True for C/C++ source or header files by extension."""
    dot = path.rfind(".")
    return dot > path.rfind("/") and path[dot:].lower() in CPP_SUFFIXES


def is_test_path(path: str) -> bool:
    """True if any directory component is a test directory (``tests/``, ``selftests/``,
    ``tools/testing/``...) or the file name carries a ``test`` token (``foo_test.c``,
    ``test-foo.c``, ``foo.test.cc``)."""
    parts = path.lower().split("/")
    return any(p in _TEST_DIRS for p in parts[:-1]) or bool(_TEST_FILE_RE.search(parts[-1]))


def is_merge(parents: list[str]) -> bool:
    """True for commits with more than one parent."""
    return len(parents) > 1


def is_revert(message: str) -> bool:
    """True if the subject starts with ``Revert`` or the body says ``This reverts commit``."""
    return bool(re.match(r"Revert\b", message) or _REVERT_RE.search(message))


def is_target_path(path: str) -> bool:
    """Versioned primary scope: implementation/header/inline fragments, excluding tests."""
    return is_cpp_source(path) and not is_test_path(path)


def gold_files(paths: list[str]) -> list[str]:
    """Changed paths that count as gold: non-test C/C++ sources, sorted."""
    return sorted(p for p in paths if is_target_path(p))


def file_count_ok(paths: list[str]) -> bool:
    """Gate on the number of gold files (inclusive bounds)."""
    return MIN_GOLD_FILES <= len(paths) <= MAX_GOLD_FILES


def is_trailer(line: str) -> bool:
    m = _TRAILER_RE.match(line)
    return bool(m) and (m[1].lower() in _TRAILER_KEYS or m[1].lower().endswith("-by"))


def strip_trailers(message: str) -> str:
    """Drop trailer lines (``Signed-off-by:``, ``Fixes:``, ``Link:``, any ``*-by:`` ...)
    anywhere in the message and collapse the leftover blank lines."""
    return message_evidence(message)["stripped"]


def message_evidence(message: str) -> dict:
    """Keep ordered, duplicate recognized trailers and their indented continuations.

    Recognition remains line-based, including outside the final trailer block. Raw lines
    and 1-based line numbers make the removal reversible; raw message is retained too.
    """
    kept, trailers, removed = [], [], []
    continuation = False
    for number, line in enumerate(message.splitlines(keepends=True), 1):
        value = line.rstrip("\r\n")
        if is_trailer(value):
            key, rest = value.split(":", 1)
            trailers.append({"key": key, "value": rest.lstrip(), "lines": [number]})
            continuation = True
        elif continuation and value.startswith((" ", "\t")):
            trailers[-1]["value"] += "\n" + value
            trailers[-1]["lines"].append(number)
        else:
            continuation = False
            kept.append(value.rstrip())
            continue
        removed.append({"line": number, "text": line})
    text = "\n".join(kept)
    return {
        "raw": message,
        "stripped": re.sub(r"\n{3,}", "\n\n", text).strip(),
        "trailers": trailers,
        "removed_lines": removed,
    }


def fixes_shas(message: str) -> list[str]:
    """SHA prefixes referenced by ``Fixes: <sha> (...)`` trailers, in order."""
    return _FIXES_SHA_RE.findall(message)


def pgsql_refs(message: str) -> list[str]:
    """PostgreSQL-style bug references: for commits carrying a ``Reported-by:`` or
    ``Bug: #N`` trailer, the bug numbers and ``Discussion:`` archive URLs; else empty."""
    if not _REPORTED_RE.search(message):
        return []
    return [f"#{bug}" if bug else url for bug, url in _REPORT_RE.findall(message)]


def issue_refs(message: str, upstream: str) -> list[int]:
    """Issue numbers of ``upstream`` (``owner/repo``) referenced as ``Fixes #N``,
    ``Closes: #N``, ``Resolves <issue url>``, ``Fix owner/repo#N``... in order of first
    mention, without duplicates. References to other repositories are ignored."""
    up = re.escape(upstream)
    pattern = _ISSUE_KEYWORDS + rf"(?:https://github\.com/{up}/issues/|{up}#|#)(\d+)\b"
    return list(dict.fromkeys(int(n) for n in re.findall(pattern, message, re.IGNORECASE)))
