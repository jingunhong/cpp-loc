# 07 — Additional repository adaptation splits

Generated locally on 2026-09-15 from the authorized `../Cpp-SWE-bench/` archive.
These are measured split outcomes, not training runs. All five repositories were
assessed; feasible views are separately named and versioned. LLVM and every existing
evaluation configuration retain their frozen data. The Hub remains at private
revision `528bffec7602b48d4ad4687d5735a61af8a7718c`; the additive package is local,
not uploaded.

## Yield and recommended use

Counts are **train / dev / test**. The pool column counts diagnostic-eligible rows
in the historical window after full-population temporal/group exclusions, **before**
the iterative train/dev quarantine. It is not total corpus size. Refused attempts
have manifests and no runner exports; their existing evaluation tests remain usable.
Arrows show the pool remaining after train/dev group quarantine.

| Repository | Eligible pre-cutoff pool | Primary diagnostic, dev=300 | Small diagnostic, dev=50 / train≥100 | Strict primary feasibility | Recommended use / main limitation |
|---|---:|---|---|---|---|
| ClickHouse | 127 | Refused: needs ≥301; frozen test 397 | Refused: needs ≥150; at most 77 train after 50 dev | Refused: pool 0, test candidates 0 | Evaluation-only transfer target; recent-history concentration leaves insufficient training data |
| Linux | 2,772 → 2,757 | 2,457 / 300 / 382 | Not attempted; primary feasible | 608 / 300 / 105; strict pool 908 | Priority direct adaptation, transfer source/target; diagnostic chronology gaps and original Fixes-based selection remain |
| PostgreSQL (`postgres`) | 631 → 629 | 329 / 300 / 171 | Not attempted; primary feasible | Refused: pool 0, test candidates 0 | Provisional direct and source→target adaptation; report archive dates lack timezone evidence |
| systemd | 596 | 296 / 300 / 73 | Not attempted; primary feasible | Refused: pool 1, test candidates 0 | Provisional direct and source→target adaptation; small train set and unresolved consumed-text chronology |
| QEMU | 300 | Refused: needs ≥301; frozen test 20 | 250 / 50 / 20 | Refused: pool 0, test candidates 0 | Explicit small-data diagnostic pilot; only 20 test instances and insufficient strict evidence |

Complete extraction populations / report-backed counts are ClickHouse 1,049 / 1,022;
Linux 63,115 / 5,424; PostgreSQL 1,333 / 1,318; systemd 1,424 / 1,418; QEMU
2,821 / 677. ClickHouse's 1,022 reports do not establish a substantial historical
training pool. Its 77-row hypothetical training remainder is not an exported
configuration. QEMU's primary refusal remains alongside its successful pilot.

The table describes the full authorized local splits. The separate HF-ready storage
copy applies the existing `publication-screen-2` policy and withholds one Linux and
one PostgreSQL diagnostic **training** row for phone-context matches. Storage train
counts are therefore **2,456** and **328**, respectively; all dev/test counts, Linux
strict counts, and other configurations are unchanged. These two IDs were already
withheld from the existing HF historical views. No text is masked or rewritten.
`release.json` records storage counts/withheld IDs; companion split manifests retain
the canonical local memberships. The exporter refuses any adaptation dev/test loss
or a training reduction below the recorded minimum.

Train/dev quarantine removes 15 eligible Linux records and two PostgreSQL records,
leaving pools of 2,757 and 629; systemd retains 596 and QEMU's pilot retains 300.
Manifests distinguish `eligible_before_train_dev.pool` from `eligible_before_dev.pool`
(the latter is the final surviving pool, retaining its existing field name).
Per-instance exclusions and group quarantines are recorded; overlapping exclusion
counts must not be added as disjoint losses.

## Boundaries and evidence

All twelve final frozen manifests (six repositories × diagnostic/strict) were
checked against pool `[2024-01-01, 2026-03-01)`, buffer `[2026-03-01, 2026-06-01)`,
and test `[2026-06-01, 2026-09-09)`, in UTC, with primary dev size 300. Availability
uses the frozen **committer timestamp**, not historical `created_at` (author time).
No cutoff changed; no buffer/test row entered training. Latest dev selection uses
UTC committer time and instance ID, repeatedly quarantining crossing groups.
The pilot uses the same rules with dev=50 and a minimum of 100 train records,
enforced again after each quarantine.

The generator reads each complete `data/<repo>/v3.1/` population and its frozen
`groups.json`, verifies original v2 shard/command hashes and every retained original
field, and checks group evidence against the frozen records. Null reports and
ineligible records participate in grouping and temporal quarantine. Shared report
identities, backports, and available exact full-diff patch IDs retain their existing
edges; shared Linux `Fixes:` targets and duplicate-text flags remain audit-only.
Missing offline patch IDs and unknown chronology remain evidence limitations.
There is no new extraction, enrichment, report selection, or text cleaning.

Every runner row has exactly `instance_id`, `repo`, `base_commit`,
`problem_statement`, `file_changes`. All adaptation gold uses
`metadata.integrity.git.primary_files`, the same implementation-file projection as
LLVM; historical unfiltered configurations retain their original gold. Text is
unchanged. Diagnostics remain provisional; unknown consumed versions are never
promoted to verified pre-fix reports. Linux strict rows are rule-based candidates,
not human-certified bug/causality evidence.

Use one complete configuration for a run. Strict and diagnostic configurations
overlap and can select different development sets; do not combine their partitions.
Do not train on an HF `*_unfiltered/corpus` configuration: it overlaps evaluation
data and lacks the full grouping population. Frozen LLVM or Linux training can
serve as source adaptation; feasible target training supports subsequent target
adaptation. ClickHouse supports evaluation of transfer only under this schedule.
Preparing these choices does not commit the study to training on every repository.

## Local artifacts and training handoff

Paths below are relative to the `cpp-loc` checkout, except the explicitly named
archive. Dataset files remain ignored by Git.

- `data/adaptation-v1/<repo>/adaptation-diagnostic-v1/`: all five primary attempts.
- `data/adaptation-v1/{clickhouse,qemu}/adaptation-diagnostic-small-v1/`: the two pilots.
- `data/adaptation-v1/<repo>/adaptation-strict-v1/`: all five strict attempts.
- Each attempt contains `manifest.json`; successful attempts also contain
  `{train,dev,test}-000.jsonl`. Refused attempts contain only their manifest.
- `data/adaptation-v1/verification.json`: full input/output hashes, producing code
  and upstream revisions, original populations, exclusions, and replay checks.
- `releases/cpp-loc-adaptation-review-v1/`: full local review bundle, including
  frozen extraction evidence and all old/new configurations.
- `releases/cpp-loc-adaptation-private-v1/`: screened HF-ready local package;
  runner files are under `data/<config>/`, compact sources and adaptation assignment
  manifests under `provenance/`, with counts/hashes in `release.json`.
- `releases/adaptation-v1-package-verification.json`: storage exclusions, preserved
  existing-file hashes, loader counts, and private-package replay receipt.

New nonempty HF configuration names are `linux_adaptation_diagnostic_v1`,
`linux_adaptation_strict_v1`, `postgres_adaptation_diagnostic_v1`,
`systemd_adaptation_diagnostic_v1`, and `qemu_adaptation_diagnostic_small_v1`.
Each has `train`, `dev`, and `test`. The 13 existing configurations remain available.
These new names are prepared locally and are not yet available from the Hub.

For example, the training agent can validate and load Linux directly:

```sh
uv run python scripts/validate.py --runner --exact \
  data/adaptation-v1/linux/adaptation-diagnostic-v1/{train,dev,test}-*.jsonl
```

```python
from datasets import load_dataset

root = "data/adaptation-v1/linux/adaptation-diagnostic-v1"
data = load_dataset(
    "json", data_files={part: f"{root}/{part}-*.jsonl" for part in ("train", "dev", "test")}
)
```

The controller uses `repo`/`base_commit` for checkout and keeps `file_changes` and
companions private. Model observations contain report text and opaque workspace
context, following [the existing runner boundary](02-splits-and-provenance.md#runner-boundary).

## Reproduction and validation

Split/full-review implementation: `d3dbac67155a5b931536a36a7001497e73334a83`;
private-storage implementation: `457302290de66803549ffbf8f498f24db92d753e`.
Its file hashes, archive revision, frozen enrichment implementations/snapshots and
pinned upstream revisions are retained in the receipts/manifests. Byte-identical
manifest replay requires this code revision; later documentation-only commits
change the recorded revision even if runner bytes match.

Executed generation and packaging commands:

```sh
uv run python scripts/adapt.py --archive ../Cpp-SWE-bench --out data/adaptation-v1
uv run python scripts/prepare.py package \
  --data-dir ../Cpp-SWE-bench/data --adaptation-dir data/adaptation-v1 \
  --out releases/cpp-loc-adaptation-review-v1
uv run python scripts/package_private.py \
  --bundle releases/cpp-loc-adaptation-review-v1 \
  --out releases/cpp-loc-adaptation-private-v1
uv run --with datasets python releases/verify-adaptation-package-v1.py
```

Use fresh `--out` paths for another run. The generator automatically attempts the
pilot only after a primary diagnostic refusal, then assesses strict feasibility.
It replays every attempt in a fresh temporary directory and compares all bytes,
including refusal manifests. For an individual pilot the existing CLI is:

```sh
uv run python scripts/prepare.py split --input ../Cpp-SWE-bench/data/qemu/v3.1 \
  --out data/qemu/pilot-replay-v1 --view diagnostic --role adaptation-candidate \
  --dev-size 50 --min-train-size 100 --test-end 2026-09-09T00:00:00Z
```

Successful checks cover exact schema, unique IDs within configurations, enriched
gold and exact report text, full-group temporal separation, latest dev selection,
minimum train size, unchanged frozen test bytes, unchanged LLVM artifacts, original
archive hashes, and deterministic replay. The existing test suite has 77 passing
tests; Ruff and required pre-commit checks pass. No expensive baseline or model was
rerun. An incomplete initial run is retained at `data/adaptation-v1-incomplete/`;
it stopped on JSON histogram-key comparison in the validator, before Linux exports.
The comparison was corrected without changing any frozen grouping evidence.
The first private-package attempt stopped at the storage screen and is retained at
`releases/cpp-loc-adaptation-private-v1-incomplete/`. The final exporter explicitly
records allowed training-only storage reductions and enforces the split constraints.

All 18 named configurations loaded through the local dataset card with `datasets`
5.0.1. All 22 existing runner/provenance/baseline files match the prior private
release byte-for-byte, as do its 13 configuration definitions. The private exporter
also replayed byte-identically. The exact runner CLI validated all 5,941 new local
rows across five configurations, with zero invalid rows or duplicate IDs within a
configuration. These are overlapping views, not 5,941 distinct bugs.

SHA-256 anchors (individual shard hashes are in the manifests):

- Split verification: `ea111d7692950e6b6162fa610abcff2433f5d62341079d2eeb17f533bb66f900`.
- Full-review `release.json`: `95a6bffc8d328efe6418e9a1fa63d0c9aa2d693b9853fec673881745e6592f0d`.
- Private `release.json`: `30656feef7b85acbaab9ecba7a8098d737eae0250cf459a6046e38a4a590640a`.
- Package verification: `688576cfe82a289cb23283fc38e06ec19eb008910fe893fa349621afcda5f9f7`.

The full-review bundle contains the documentation snapshot from its generation;
this document additionally records the subsequent storage screen and validation.
