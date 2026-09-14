import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def commit(repo: Path, message: str, files: dict[str, str], date: str) -> str:
    for path, content in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    git(repo, "add", "-A")
    env_date = f"GIT_AUTHOR_DATE={date} GIT_COMMITTER_DATE={date}"
    subprocess.run(
        f"{env_date} git -C {repo} commit -q -F -",
        shell=True,
        input=message,
        text=True,
        check=True,
    )
    return git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A tiny repo: one bug-introducing commit, one Fixes: commit, one revert, one
    test-only Fixes: commit, one Fixes: commit that touches too many files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    shas = {}
    shas["initial"] = commit(
        repo,
        "init: add driver\n\nSigned-off-by: A <a@x>\n",
        {"drivers/foo.c": "int foo(void) { return 1; }\n", "README": "hi\n"},
        "2023-01-01T10:00:00+09:00",
    )
    shas["fix"] = commit(
        repo,
        "foo: fix off-by-one\n\nfoo() returned the wrong value.\n\n"
        f'Fixes: {shas["initial"][:12]} ("init: add driver")\n'
        "Signed-off-by: A <a@x>\nLink: https://example.com\n",
        {"drivers/foo.c": "int foo(void) { return 0; }\n", "drivers/foo.h": "int foo(void);\n"},
        "2023-02-01T10:00:00+09:00",
    )
    shas["revert"] = commit(
        repo,
        f'Revert "foo: fix off-by-one"\n\nThis reverts commit {shas["fix"]}.\n\n'
        f'Fixes: {shas["fix"][:12]} ("foo: fix off-by-one")\n',
        {"drivers/foo.c": "int foo(void) { return 1; }\n"},
        "2023-03-01T10:00:00+09:00",
    )
    shas["test_only"] = commit(
        repo,
        f'selftests: cover foo\n\nFixes: {shas["initial"][:12]} ("init: add driver")\n',
        {"tools/testing/selftests/foo_test.c": "int main(void){return 0;}\n"},
        "2023-04-01T10:00:00+09:00",
    )
    shas["too_many"] = commit(
        repo,
        f'foo: big fix\n\nFixes: {shas["initial"][:12]} ("init: add driver")\n',
        {f"drivers/f{i}.c": f"int f{i};\n" for i in range(6)},
        "2023-05-01T10:00:00+09:00",
    )
    return repo, shas
