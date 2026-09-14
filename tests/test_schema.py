import dataclasses

import pytest

from cpp_loc.schema import Instance

SHA = "a" * 40


def make(**overrides) -> Instance:
    base = dict(
        instance_id="r__aaaaaaaaaaaa",
        repo="o/r",
        base_commit=SHA,
        fix_commit="b" * 40,
        created_at="2023-02-01T10:00:00+00:00",
        problem_statement="broken",
        problem_source="github_issue",
        commit_message="fix: broken",
        file_changes=[{"file": "a.c"}],
        gold_functions=None,
        patch="diff",
        metadata={},
    )
    return Instance(**(base | overrides))


def test_roundtrip():
    inst = make(metadata={"k": [1, 2]})
    assert Instance.from_json(inst.to_json()) == inst
    assert make().validate() == []


def test_field_order_matches_readme():
    assert [f.name for f in dataclasses.fields(Instance)] == [
        "instance_id", "repo", "base_commit", "fix_commit", "created_at",
        "problem_statement", "problem_source", "commit_message", "file_changes", "gold_functions",
        "patch", "metadata",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "overrides,fragment",
    [
        ({"base_commit": SHA[:12]}, "base_commit"),
        ({"fix_commit": SHA.upper()}, "fix_commit"),
        ({"created_at": "yesterday"}, "created_at"),
        ({"file_changes": []}, "file_changes"),
        ({"file_changes": ["a.c"]}, "file_changes"),
        ({"file_changes": [{"file": ""}]}, "file_changes"),
        ({"problem_statement": ""}, "problem_statement"),
        ({"problem_statement": None}, "problem_source"),
        ({"problem_source": "commit_message"}, "problem_source"),
        ({"commit_message": ""}, "commit_message"),
        ({"gold_functions": "a::b"}, "gold_functions"),
    ],
)
def test_validate_rejects(overrides, fragment):
    assert any(fragment in e for e in make(**overrides).validate())


def test_null_report_is_valid():
    assert make(problem_statement=None, problem_source=None).validate() == []
