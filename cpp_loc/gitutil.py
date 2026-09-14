"""Thin ``git`` subprocess wrappers.

Everything here works on a blob-less clone (``git clone --filter=blob:none``)
without triggering lazy blob fetches, except :func:`diff` and
:func:`prefetch_blobs`, which need file contents.
"""

import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

_RS, _FS = "\x1e", "\x1f"
_FORMAT = f"{_RS}%H{_FS}%P{_FS}%aI{_FS}%cI{_FS}%B{_FS}"


@dataclass
class Commit:
    sha: str
    parents: list[str]
    author_date: str
    committer_date: str
    message: str
    files: list[str]  # changed paths vs. first parent; empty unless requested


def run(repo: Path, *args: str, input: str | None = None, offline: bool = False) -> str:
    return subprocess.run(
        ["git", *(["--no-lazy-fetch"] if offline else []), "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        input=input,
        timeout=60 if offline else None,
        env={
            **os.environ,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ALLOW_PROTOCOL": "",
        }
        if offline
        else None,
    ).stdout


def log(repo: Path, *, since: str | None = None, rev: str = "HEAD", files: bool = False):
    """Yield commits reachable from ``rev`` in ``git log`` order.

    ``files=True`` adds the name-only diff against the first parent in the same
    pass (one git process for the whole history instead of one per commit).
    """
    args = ["log", f"--format={_FORMAT}", "--no-renames"]
    if since:
        args.append(f"--since={since}")
    if files:
        args.append("--name-only")
    args.append(rev)
    out = run(repo, *args)
    for record in out.split(_RS)[1:]:
        sha, parents, date, committer, message, names = record.split(_FS, 5)
        yield Commit(sha, parents.split(), date, committer, message, names.split())


def parents(repo: Path, sha: str) -> list[str]:
    return run(repo, "rev-list", "--parents", "-n1", sha).split()[1:]


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    return run(repo, "diff", "--name-only", "-z", "--no-renames", base, head).split("\0")[:-1]


RENAME_POLICY = "--no-renames (moves are represented as deletion plus addition)"


def parse_changes(raw: str) -> list[dict]:
    """Parse ``git diff --name-status -z`` without splitting whitespace in paths."""
    if raw and not raw.endswith("\0"):
        raise ValueError("unterminated NUL-delimited name-status diff")
    fields = iter(raw.split("\0")[:-1])
    records = []
    try:
        for status in fields:
            path = next(fields)
            if status.startswith(("R", "C")):
                old, new = path, next(fields)
            else:
                old = None if status == "A" else path
                new = None if status == "D" else path
            records.append({"status": status, "old_path": old, "new_path": new})
    except StopIteration as exc:
        raise ValueError("truncated NUL-delimited name-status diff") from exc
    return records


def changes(repo: Path, base: str, fix: str) -> list[dict]:
    return parse_changes(
        run(repo, "diff-tree", "-r", "--name-status", "-z", "--no-renames", base, fix, offline=True)
    )


def commit_info(repo: Path, sha: str) -> dict:
    """Read exactly this commit; do not traverse history or fetch missing objects."""
    raw = run(
        repo,
        "log",
        "--no-walk",
        "-1",
        "--format=%H%x00%P%x00%aI%x00%cI%x00%B%x00",
        sha,
        offline=True,
    )
    fix, parent_text, author, committer, message_text = raw.split("\0", 4)
    return {
        "sha": fix,
        "parents": parent_text.split(),
        "author_at": author,
        "committer_at": committer,
        "message": message_text.rsplit("\0", 1)[0],
    }


def tree_files(repo: Path, sha: str, paths: list[str] | None = None) -> list[str]:
    """Blob paths in a tree, optionally restricted by literal pathspecs; never fetch."""
    # Large jumps between historical branches can exceed the OS argv limit.
    if paths and len(paths) > 1 and sum(len(p.encode()) + 1 for p in paths) > 32_000:
        mid = len(paths) // 2
        return sorted(set(tree_files(repo, sha, paths[:mid]) + tree_files(repo, sha, paths[mid:])))
    args = ["--literal-pathspecs", "ls-tree", "-r", "-z", "--full-tree", sha]
    if paths is not None:
        if not paths:
            return []
        args += ["--", *paths]
    records = run(repo, *args, offline=True).split("\0")[:-1]
    # Symlinks and gitlinks are not existing implementation files.
    return [r.split("\t", 1)[1] for r in records if r.startswith(("100644 blob ", "100755 blob "))]


class TreeInventory:
    """Cache an inventory using exact tree diffs, without fetching file contents.

    Prediction receives only paths and the derived basename index, not this controller.
    """

    def __init__(self, repo: Path):
        self.repo = repo
        self.commit = None
        self.tree_sha = None
        self.paths = set()
        self.basenames = defaultdict(set)

    def at(self, sha: str) -> None:
        tree_sha = run(self.repo, "rev-parse", "--verify", f"{sha}^{{tree}}", offline=True).strip()
        if self.commit is None:
            removed, added = set(), set(tree_files(self.repo, sha))
        else:
            delta = [c for c in changes(self.repo, self.commit, sha) if c["status"] != "M"]
            removed = {c["old_path"] for c in delta if c["old_path"]} & self.paths
            candidates = [c["new_path"] for c in delta if c["new_path"]]
            added = set(tree_files(self.repo, sha, candidates))
        # Keep the old cache intact until every Git read succeeded.
        for path in removed:
            self.paths.remove(path)
            self.basenames[path.rsplit("/", 1)[-1]].discard(path)
        for path in added:
            self.paths.add(path)
            self.basenames[path.rsplit("/", 1)[-1]].add(path)
        self.commit, self.tree_sha = sha, tree_sha


def stable_patch_id(repo: Path, base: str, fix: str) -> str | None:
    # Blob-less clones often contain the old gold patch's blobs but not added tests.
    # Check the full diff's blob inputs before asking git diff to read them.
    raw = run(repo, "diff-tree", "-r", "--raw", "-z", "--no-renames", base, fix, offline=True)
    fields = raw.split("\0")[:-1]
    oids = set()
    for header in fields[::2]:
        old_mode, new_mode, old, new, _ = header.split()
        for mode, oid in ((old_mode.lstrip(":"), old), (new_mode, new)):
            if mode != "160000" and set(oid) != {"0"}:
                oids.add(oid)
    checked = (
        run(repo, "cat-file", "--batch-check", input="\n".join(sorted(oids)) + "\n", offline=True)
        if oids
        else ""
    )
    missing = [line.split()[0] for line in checked.splitlines() if line.endswith(" missing")]
    if missing:
        raise FileNotFoundError("full-diff blobs missing: " + " ".join(missing))
    patch = run(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--no-renames",
        "--diff-algorithm=myers",
        "--unified=3",
        base,
        fix,
        offline=True,
    )
    result = run(repo, "patch-id", "--stable", input=patch, offline=True).split()
    return result[0] if result else None


def author_date(repo: Path, sha: str) -> str:
    return run(repo, "log", "-1", "--format=%aI", sha).strip()


def message(repo: Path, sha: str) -> str:
    return run(repo, "log", "-1", "--format=%B", sha)


def diff(repo: Path, base: str, head: str, paths: list[str], *, offline: bool = False) -> str:
    """Unified diff restricted to ``paths``. Fetches missing blobs lazily."""
    return run(
        repo,
        "--literal-pathspecs",
        "diff",
        "--no-renames",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        base,
        head,
        "--",
        *paths,
        offline=offline,
    )


def blob_oids(repo: Path, base: str, head: str, paths: list[str]) -> list[str]:
    """Pre- and post-image blob ids touched by the diff, without fetching them."""
    raw = run(repo, "diff-tree", "-r", "--no-renames", base, head, "--", *paths)
    oids = []
    for line in raw.splitlines():
        _, _, old, new, _ = line.split(maxsplit=4)
        oids += [o for o in (old, new) if set(o) != {"0"}]
    return oids


def prefetch_blobs(repo: Path, oids: list[str], batch: int = 5000) -> None:
    """Fetch blobs in bulk from the promisor remote (same command git's lazy fetch uses).

    No-op on a full clone.
    """
    if run(repo, "config", "--default", "", "remote.origin.promisor").strip() != "true":
        return
    oids = sorted(set(oids))
    for i in range(0, len(oids), batch):
        run(
            repo,
            "-c",
            "fetch.negotiationAlgorithm=noop",
            "fetch",
            "origin",
            "--quiet",
            "--no-tags",
            "--no-write-fetch-head",
            "--recurse-submodules=no",
            "--filter=blob:none",
            "--stdin",
            input="\n".join(oids[i : i + batch]) + "\n",
        )


def head(repo: Path) -> str:
    return run(repo, "rev-parse", "HEAD").strip()
