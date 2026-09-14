"""Leakage flags: does the problem statement name, verbatim, what the fix touched?"""

import re

_HUNK_FUNC_RE = re.compile(r"^@@ .* @@.*?\b([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_KEYWORDS = frozenset({"if", "for", "while", "switch", "return", "sizeof", "defined", "else"})
FLAGS = ("path", "basename", "function")


def mentions_file(text: str, name: str) -> bool:
    """A filename token: adjacent letters, digits, underscore, dot or dash cannot extend it.

    Slashes and colons are boundaries, so paths and ``io.c:123`` match, ``stdio.c`` does not.
    """
    return bool(re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", text))


def patched_functions(patch: str) -> set[str]:
    """Function names from the diff's hunk headers (git's default C/C++ funcname lines)."""
    return {f for f in _HUNK_FUNC_RE.findall(patch) if f not in _KEYWORDS}


def flags(statement: str | None, gold_files: list[str], patch: str) -> dict[str, bool] | None:
    """Whether ``statement`` contains a gold path, a gold basename, or a patched function;
    None when there is no statement."""
    if statement is None:
        return None
    funcs = patched_functions(patch)
    return {
        "path": any(mentions_file(statement, g) for g in gold_files),
        "basename": any(mentions_file(statement, g.rsplit("/", 1)[-1]) for g in gold_files),
        "function": any(re.search(rf"\b{re.escape(f)}\b", statement) for f in funcs),
    }
