from pathlib import Path

from cpp_loc import leakage, writers
from tests.test_schema import make

PATCH = """\
diff --git a/a.c b/a.c
@@ -10,3 +10,3 @@ static int frob_widget(struct widget *w)
-\treturn 1;
+\treturn 0;
@@ -20,3 +20,3 @@ if (x)
"""


def test_patched_functions_and_flags():
    assert leakage.patched_functions(PATCH) == {"frob_widget"}
    assert leakage.flags("frob_widget() leaks", ["drivers/a.c"], PATCH) == {
        "path": False,
        "basename": False,
        "function": True,
    }
    assert leakage.flags("see drivers/a.c", ["drivers/a.c"], PATCH) == {
        "path": True,
        "basename": True,
        "function": False,
    }
    assert leakage.flags("frob_widgets are fine", ["a.c"], PATCH)["function"] is False
    assert leakage.flags(None, ["a.c"], PATCH) is None


def test_write_jsonl_shards(tmp_path: Path):
    insts = [make(instance_id=f"r__{i:012d}") for i in range(3)]
    assert [p.name for p in writers.write_jsonl(tmp_path, insts)] == ["instances.jsonl"]
    line = len(insts[0].to_json()) + 1
    paths = writers.write_jsonl(tmp_path, insts, max_bytes=2 * line)
    assert [p.name for p in paths] == ["instances-000.jsonl", "instances-001.jsonl"]
    assert sum(p.read_text().count("\n") for p in paths) == 3
    assert all(p.stat().st_size <= 2 * line for p in paths)
