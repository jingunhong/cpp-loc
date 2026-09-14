from cpp_loc import filters

MESSAGE = """\
net: fix a leak

The skb was leaked on the error path.

Fixes: 1234567890ab ("net: add path")
Reported-by: Someone <s@x>
Cc: stable@vger.kernel.org # 5.10
Link: https://lore.kernel.org/r/abc
Signed-off-by: Dev <d@x>
"""


def test_strip_trailers_keeps_subject_and_body():
    expected = "net: fix a leak\n\nThe skb was leaked on the error path."
    assert filters.strip_trailers(MESSAGE) == expected


def test_strip_trailers_handles_unknown_by_and_change_id():
    msg = "subj\n\nbody\nChange-Id: I123\nDebugged-by: X <x@y>\nAnalyzed-by: Y\n"
    assert filters.strip_trailers(msg) == "subj\n\nbody"


def test_strip_trailers_does_not_eat_prose_with_colon():
    assert filters.strip_trailers("subj\n\nNote: this matters\n") == "subj\n\nNote: this matters"


def test_fixes_shas():
    assert filters.fixes_shas(MESSAGE) == ["1234567890ab"]
    assert filters.fixes_shas("no trailer\n\nfixes: nothing here") == []


def test_report_refs():
    msg = (
        "Fix planner crash\n\nThe planner dereferenced NULL.\n\n"
        "Reported-by: A <a@x>\nBug: #18123\nDiscussion: https://postgr.es/m/abc@x\n"
        "Backpatch-through: 13\n"
    )
    assert filters.pgsql_refs(msg) == ["#18123", "https://postgr.es/m/abc@x"]
    assert filters.pgsql_refs("Add feature\n\nDiscussion: https://postgr.es/m/x\n") == []
    assert filters.strip_trailers(msg) == "Fix planner crash\n\nThe planner dereferenced NULL."


def test_issue_refs():
    msg = "Fix crash (fixes #12, closes: #7)\n\nResolves https://github.com/o/r/issues/99"
    assert filters.issue_refs(msg, "o/r") == [12, 7, 99]
    assert filters.issue_refs("Fixes o/r#5 and fixes #5", "o/r") == [5]
    assert filters.issue_refs("Fixes https://github.com/x/y/issues/3, fixes x/y#4", "o/r") == []
    assert filters.issue_refs("see #5 for context", "o/r") == []


def test_is_cpp_source():
    for p in ("a.c", "x/y.H", "z.cpp", "w.hxx", "q.cc"):
        assert filters.is_cpp_source(p), p
    for p in ("Makefile", "a.py", "a.rs", "dir.c/x.txt"):
        assert not filters.is_cpp_source(p), p


def test_is_test_path():
    for p in (
        "tests/foo.c",
        "src/test/bar.cc",
        "tools/testing/selftests/net/x.c",
        "lib/foo_test.c",
        "lib/test-foo.c",
        "lib/test_foo.c",
        "lib/foo.test.cc",
    ):
        assert filters.is_test_path(p), p
    for p in ("drivers/net/foo.c", "kernel/latest.c", "mm/contest.c", "fs/attest.h"):
        assert not filters.is_test_path(p), p


def test_gold_files_and_count_gate():
    paths = ["b.c", "a.c", "tests/t.c", "Makefile", "a.h"]
    assert filters.gold_files(paths) == ["a.c", "a.h", "b.c"]
    assert filters.file_count_ok(["a.c"])
    assert filters.file_count_ok([f"{i}.c" for i in range(5)])
    assert not filters.file_count_ok([])
    assert not filters.file_count_ok([f"{i}.c" for i in range(6)])


def test_merge_and_revert():
    assert filters.is_merge(["a", "b"])
    assert not filters.is_merge(["a"])
    assert filters.is_revert('Revert "x"\n\nThis reverts commit abc.')
    assert filters.is_revert("x: undo\n\nThis reverts commit abc.")
    assert not filters.is_revert("x: reverting the logic order is fine")
