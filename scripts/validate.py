"""Re-validate every line of an instances.jsonl against the schema.

uv run python scripts/validate.py data/linux/v1/instances*.jsonl
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpp_loc.schema import Instance, validate_runner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--runner", action="store_true")
    parser.add_argument("--exact", action="store_true", help="require only five runner fields")
    args = parser.parse_args()
    total, bad, ids = 0, 0, Counter()
    problems: Counter[str] = Counter()
    for path in args.paths:
        with path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                total += 1
                try:
                    if args.runner:
                        row = json.loads(line)
                        errors = validate_runner(row, exact=args.exact)
                        ids[row.get("instance_id")] += 1
                    else:
                        inst = Instance.from_json(line)
                        errors = inst.validate()
                        ids[inst.instance_id] += 1
                except (TypeError, ValueError) as e:
                    errors = [f"unparseable: {e}"]
                if errors:
                    bad += 1
                    problems.update(errors)
                    print(f"{path}:{lineno}: {'; '.join(errors)}", file=sys.stderr)
    dupes = sum(1 for n in ids.values() if n > 1)
    print(f"{total} instances, {total - bad} valid, {bad} invalid, {dupes} duplicate ids")
    for problem, n in problems.most_common():
        print(f"  {n}x {problem}")
    sys.exit(1 if bad or dupes else 0)


if __name__ == "__main__":
    main()
