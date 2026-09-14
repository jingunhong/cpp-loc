"""Output writers: ``instances*.jsonl``, ``dataset.jsonl`` and ``STATS.md``."""

import json
from dataclasses import asdict
from pathlib import Path

from .schema import Instance

MAX_SHARD_BYTES = 45_000_000  # under the repository's 50 MB per-file limit


def write_jsonl(out_dir: Path, instances: list[Instance], max_bytes: int = MAX_SHARD_BYTES):
    """Write ``instances.jsonl``, or ``instances-000.jsonl``... when one file would exceed
    ``max_bytes``. Returns the paths written."""
    shards: list[list[bytes]] = [[]]
    size = 0
    for inst in instances:
        line = (inst.to_json() + "\n").encode("utf-8")
        if shards[-1] and size + len(line) > max_bytes:
            shards.append([])
            size = 0
        shards[-1].append(line)
        size += len(line)
    names = (
        ["instances.jsonl"]
        if len(shards) == 1
        else [f"instances-{i:03d}.jsonl" for i in range(len(shards))]
    )
    paths = []
    for name, lines in zip(names, shards, strict=True):
        path = out_dir / name
        path.write_bytes(b"".join(lines))
        paths.append(path)
    return paths


def write_dataset(out_dir: Path, instances: list[Instance]) -> Path:
    """``dataset.jsonl``: the rows a localizer can run on (``problem_statement`` not null),
    every field but ``patch`` (kept in ``instances*.jsonl``; join on ``instance_id``). The
    Multi-SWE-bench C/C++ fields are ``instance_id``, ``repo``, ``base_commit``,
    ``problem_statement`` and ``file_changes``; everything else is an extra."""
    path = out_dir / "dataset.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for inst in instances:
            if inst.problem_statement is not None:
                row = asdict(inst)
                del row["patch"]
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def write_stats(path: Path, title: str, funnel: list[tuple[str, int]], notes: dict) -> None:
    """``funnel`` is an ordered list of (stage, survivors); the first stage is the
    candidate pool every percentage is relative to."""
    total = funnel[0][1] if funnel else 0
    lines = [
        f"# {title}",
        "",
        "| Stage | Survived | % of candidates | Dropped here |",
        "|---|---:|---:|---:|",
    ]
    prev = total
    for stage, count in funnel:
        pct = 100 * count / total if total else 0
        lines.append(f"| {stage} | {count} | {pct:.1f}% | {prev - count} |")
        prev = count
    lines += ["", "## Run", ""] + [f"- **{k}**: {v}" for k, v in notes.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
