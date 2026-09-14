# 02 — Groups, temporal splits, baseline, and runner handoff

The frozen artifacts referenced below are retained in a private research archive
and require authorized access. See the [local corpus examples](../README.md#use-the-existing-local-corpus)
for running this repository's tooling against an archive at any local path.

## Groups before eligibility

`groups-1` scans the complete available extraction population, including null reports
and ineligible instances. Identities are repository-scoped and based on source issue
numbers, selected mail/message IDs, or syzbot canonical IDs. Equivalent known URL forms
normalize without lowercasing email Message-IDs. Every available reference is resolved;
known PRs are distinguished from issues. Missing references remain explicit and group
conservatively. The exact historical selected report is preserved even if its payload
is absent or no longer matches. A different report/body is never silently substituted.

Edges record shared report identity, explicit cherry-pick/upstream references resolving
to actual commits, and exact stable **full** patch IDs when available. Explicit backport
trailers are repository evidence, not a claim of independently proved patch equivalence.
Group IDs hash sorted member IDs. Exact whitespace-normalized duplicate report text is
flagged for audit, not automatically merged; generic titles and different repositories
are never fuzzy-clustered.

Shared Linux `Fixes:` targets are resolved and reported, but do not create grouping
edges: these identify introducing commits, not necessarily the same bug. One-to-one
means within the input's documented mined range/revision only. Strict records must have
unambiguous local report references and singleton evidence groups. Broader diagnostic
views can retain related fixes, with group separation. Selection bias from requiring
Linux `Fixes:` and other historical mining filters remains; candidate expansion is deferred.

## Frozen temporal configuration: temporal-1

| Partition | Half-open interval/rule |
|---|---|
| Train/development pool | `[2024-01-01T00:00:00Z, 2026-03-01T00:00:00Z)` |
| Buffer | `[2026-03-01T00:00:00Z, 2026-06-01T00:00:00Z)` |
| Test | `[2026-06-01T00:00:00Z, --test-end)` |
| Development | Latest 300 eligible pool records, ordered by UTC committer time, then instance ID |

Every cutoff is configurable and recorded. `--test-end` is mandatory; no moving now.
Groups crossing any partition, including buffer and out-of-range partitions, are fully
quarantined before local eligibility. Unknown group times quarantine too. No future
records move into training. At the train/dev boundary, crossing diagnostic groups are
quarantined and the latest 300 are recomputed among survivors; all quarantines remain in
the manifest. Fewer than 301 pool survivors refuses an adaptation configuration (exit 2),
with exact reasons and **no** train/dev/test exports. Evaluation-only roles need no pool.

LLVM is the first public adaptation candidate. ClickHouse is a provisional transfer
candidate requiring audit; it is not selected using final test performance. A <=2025
ClickHouse diagnostic is not a valid future test after source adaptation through 2026.
No DuckDB/Godot expansion or GPU/model evaluation is part of this work.

Manifests retain every instance/group assignment, local and group exclusions, rule
versions, source/target role, input hashes/snapshot, output hashes, and refusal status.
Strict candidates are not represented as publication-ready or human-validated.
Diagnostics keep unknown evidence visible and must never be called temporally verified.

## Commands

Commit the implementation and use new output directories. Existing v2 artifacts remain
intact. These initial-pass examples assume local inputs in `data/` and clones/caches
in `repos/`; neither is included in a code checkout. For the completed six-source
results and replay example, see [06](06-six-source-validation.md).

```sh
uv run python scripts/prepare.py enrich --repo llvm --input data/llvm/v2 --out data/llvm/v3 --offline
uv run python scripts/prepare.py enrich --repo clickhouse --input data/clickhouse/v2 --out data/clickhouse/v3 --offline
uv run python scripts/prepare.py split --input data/llvm/v3 --out data/llvm/splits-v1 --test-end 2026-09-09T00:00:00Z
uv run python scripts/prepare.py split --input data/clickhouse/v3 --out data/clickhouse/splits-v1 --role provisional-transfer-evaluation --test-end 2026-09-09T00:00:00Z
uv run python scripts/prepare.py audit --repo llvm --input data/llvm/v3 --out data/llvm/baseline-v1 --offline
uv run python scripts/prepare.py audit --repo clickhouse --input data/clickhouse/v3 --out data/clickhouse/baseline-v1 --offline
```

The explicit example end is the day after the pinned extraction snapshot; it is not a
claim of complete upstream coverage through that day. The snapshot's original command
and upstream SHA define actual coverage. `--view diagnostic` prepares an explicitly
provisional grouped view with the same dates and dev-size requirement. Do not relax
strict checks to obtain a convenient yield.

```sh
uv run python scripts/prepare.py enrich --repo postgres --input data/postgres/v2 --out data/postgres/v3 --offline --reports-only
uv run python scripts/prepare.py enrich --repo linux --input data/linux/v2 --out data/linux/v3 --offline --reports-only
```

Reports-only outputs annotate cached text but do not certify Git gold or fix chronology.

## Explicit-hint baseline: explicit-paths-1

Prediction takes only report text and the pre-fix regular-file inventory. Extract path
tokens, normalize slash/backslash, `file:line[:column]`, leading `./`, and absolute build
prefixes by dropping leading components until a real tree path matches. Optionally
resolve a bare basename only when unique across the entire inventory. Ambiguous names,
parent traversal, and whitespace inside path tokens are unsupported. Predict only the
versioned target scope. Predictions never see gold, patches, commit messages, fixing
SHAs, or hint labels; retain wrong tree paths when scoring.

For the real-data audit, an incremental cache uses exact base-tree diffs and records
the native Git tree SHA. A fixture checks the cached inventory against full tree lists,
including file type changes and backward jumps. Prediction receives only the paths and
derived basename index, never the cache controller or commit metadata.

Macro precision, recall, F1, and empty-prediction rate use all report-backed attempted
instances, including failures scored zero. Separate status counts expose unavailable
inventories/gold. Breakdowns cover repository, report source/kind, and explicit path,
basename, or no-file-hint strata. Historical `leakage` fields measure explicit hints,
not proof of training contamination. The raw-population baseline is a descriptive audit,
not a final test result used to choose the target.

The audit also measures authored/committed dates, report age using actual available
report dates, task/status distributions, reuse, and explicit fixing-message assistance
markers. `observed`, `not-observed`, `unknown` never imply that missing markers prove
human-only authorship. Seeded targeted samples cover ordinary and flagged strata;
review status and reviewer type are explicit. They do not estimate population prevalence.

## Runner boundary

New train/dev/test JSONL has exactly `instance_id`, `repo`, `base_commit`,
`problem_statement`, `file_changes`. `file_changes` is evaluator-only gold. Validate
with `scripts/validate.py --runner --exact`; raw extraction validation still requires
its patch. Legacy v2 runner views can be checked using `--runner` without `--exact`.

The model-visible allowlist is report text plus necessary **opaque** workspace context.
Never serialize a dataset row into observations. Repository/base/fix identifiers,
labels, fixing messages and provenance stay controller-side except the minimal checkout
information the controller itself needs. Each rollout gets an isolated workspace.
No reachable fix history, sibling clone, label files, host paths, or inherited credentials;
use network isolation where required. Removing a gitlink or grepping commands for `git`
does not enforce this: arbitrary shell/file APIs can read host paths and metadata.
A detector log supplements the actual process/filesystem/network boundary. This exporter
implements no sandbox. HANA-first training and public GPU pilots belong in the separate
training repository.

## Frozen annotation correction

`report-evidence-2` recognizes explicit feature-task labels (`feature`, `feature request`,
`enhancement`, optionally prefixed by `type:` or `type/`). An area label such as
`experimental feature` is insufficient. The seeded ClickHouse review found this
false classification in the first local v3 candidate. `reclassify` reuses the frozen
selected report text/labels and all Git/payload evidence, recomputes annotations and
eligibility, and writes a new immutable `v3.1` directory. It never reads a clone or
fetches a payload. Its snapshot records the parent snapshot and every parent file hash.
No historical v0/v1/v2 row is changed, and no exception is attached to an individual row.

```sh
uv run python scripts/prepare.py reclassify --input data/llvm/v3 --out data/llvm/v3.1
uv run python scripts/prepare.py reclassify --input data/clickhouse/v3 --out data/clickhouse/v3.1
```

Final LLVM/ClickHouse partitions use `v3.1`, `splits-v2`, and `diagnostic-v2`;
`baseline-v1` is the first completed baseline. Superseded `v3` and ClickHouse
`*-v1` partition candidates remain local for audit. The local package command
selects these final directories when present; PostgreSQL/Linux retain `v3`
report-only annotations. It writes an explicitly held review draft, not an upload.
