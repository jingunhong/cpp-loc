import json
from pathlib import Path

from cpp_loc import extract, filters, gitutil, reports, writers
from cpp_loc.schema import Instance


def test_end_to_end(synthetic_repo, tmp_path: Path):
    repo, shas = synthetic_repo
    funnel: dict[str, int] = {}
    instances = list(
        extract.mine(
            repo,
            "toy",
            "example/toy",
            since=None,
            references=filters.fixes_shas,
            refs={"link": reports.link_urls},
            funnel=funnel,
        )
    )
    assert funnel == {
        "candidates": 5,
        "not merge": 4,
        "not revert": 3,
        "has reference": 3,
        "has gold files": 2,
        "1-5 gold files": 1,
        "root commits skipped": 1,
    }
    [inst] = instances
    assert inst.instance_id == f"toy__{shas['fix'][:12]}"
    assert inst.base_commit == shas["initial"]
    assert inst.fix_commit == shas["fix"]
    assert inst.created_at == "2023-02-01T10:00:00+09:00"
    assert inst.commit_message == "foo: fix off-by-one\n\nfoo() returned the wrong value."
    assert inst.problem_statement is None and inst.problem_source is None
    assert inst.metadata["report_refs"] == {"link": ["https://example.com"]}
    assert inst.file_changes == [{"file": "drivers/foo.c"}, {"file": "drivers/foo.h"}]
    assert inst.paths == ["drivers/foo.c", "drivers/foo.h"]
    assert inst.gold_functions is None
    assert inst.metadata["references"] == [shas["initial"][:12]]

    extract.add_patches(repo, instances)
    assert "return 0" in inst.patch and "+int foo(void);" in inst.patch
    assert inst.validate() == []

    assert inst.metadata["leakage"] is None
    assert inst.metadata["commit_message_leakage"] == {
        "path": False,
        "basename": False,
        "function": False,
    }
    [out] = writers.write_jsonl(tmp_path, instances)
    assert Instance.from_json(out.read_text().splitlines()[0]) == inst
    assert writers.write_dataset(tmp_path, instances).read_text() == ""  # no report: not runnable
    inst.problem_statement, inst.problem_source = "foo() crashes", "github_issue"
    [row] = map(json.loads, writers.write_dataset(tmp_path, instances).read_text().splitlines())
    assert "patch" not in row and row["metadata"] == inst.metadata
    assert {k: row[k] for k in ("instance_id", "repo", "base_commit", "problem_statement")} == {
        "instance_id": inst.instance_id,
        "repo": "example/toy",
        "base_commit": shas["initial"],
        "problem_statement": "foo() crashes",
    }
    assert row["file_changes"] == [{"file": "drivers/foo.c"}, {"file": "drivers/foo.h"}]
    stats = tmp_path / "STATS.md"
    writers.write_stats(stats, "t", list(funnel.items()), {"n": 1})
    assert "| 1-5 gold files | 1 | 20.0% | 1 |" in stats.read_text()


def test_gitutil_helpers(synthetic_repo):
    repo, shas = synthetic_repo
    assert gitutil.parents(repo, shas["fix"]) == [shas["initial"]]
    assert gitutil.changed_files(repo, shas["initial"], shas["fix"]) == [
        "drivers/foo.c",
        "drivers/foo.h",
    ]
    assert gitutil.author_date(repo, shas["fix"]) == "2023-02-01T10:00:00+09:00"
    assert gitutil.message(repo, shas["fix"]).startswith("foo: fix off-by-one\n")
    assert len(gitutil.blob_oids(repo, shas["initial"], shas["fix"], ["drivers/foo.c"])) == 2
    assert gitutil.head(repo) == shas["too_many"]
