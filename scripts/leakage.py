"""Leakage report: how many texts name a gold file or patched function verbatim.

uv run python scripts/leakage.py data/linux/v2/instances*.jsonl          # whole set
uv run python scripts/leakage.py data/linux/v2/instances.jsonl --n 20    # sampled table

Reports ``problem_statement`` over the instances that have one and ``commit_message`` over
all instances (v2); older files without ``commit_message`` report the statement only.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc import leakage  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path, nargs="+")
    ap.add_argument("--n", type=int, default=0, help="sample size; 0 = all instances")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rows = [json.loads(line) for p in args.jsonl for line in p.open(encoding="utf-8")]
    if args.n:
        rows = random.Random(args.seed).sample(rows, min(args.n, len(rows)))
    texts = {"problem_statement": "leakage", "commit_message": "commit_message_leakage"}
    for field, key in texts.items():
        hits: dict[str, dict[str, int]] = {}  # per problem_source (one key for commit_message)
        for r in rows:
            if field not in r or r[field] is None:
                continue
            paths = r.get("gold_files") or [f["file"] for f in r["file_changes"]]  # v0/v1 | v2
            f = r["metadata"].get(key) or leakage.flags(r[field], paths, r["patch"])
            source = r.get("problem_source", "") if field == "problem_statement" else ""
            h = hits.setdefault(source, dict.fromkeys(leakage.FLAGS, 0) | {"n": 0})
            h["n"] += 1
            for k in leakage.FLAGS:
                h[k] += bool(f[k])
            if args.n:
                cells = " | ".join("x" if f[k] else "" for k in leakage.FLAGS)
                print(f"| {r['instance_id']} | {cells} |")
        for source, h in sorted(hits.items()):
            print(f"\n{field}{f' ({source})' if source else ''}, {h['n']} instances:")
            for k in leakage.FLAGS:
                print(f"  {k}: {h[k]} ({100 * h[k] / h['n']:.1f}%)")


if __name__ == "__main__":
    main()
