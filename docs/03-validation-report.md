# 03 — Measured validation report

This report records preparation in the original `Cpp-SWE-bench` checkout. Its
producing commits and local artifacts remain there; the implementation subsequently
moved to `cpp-loc`. See the [migration record](decisions.md#2026-09-14--code-repository-migration).

This is the **initial focused pass**, retained as a historical record. The later
[six-source follow-up](06-six-source-validation.md) extends full Git enrichment,
splits, and baselines to Linux, systemd, PostgreSQL, and QEMU and documents the
separate private review export. Counts and no-upload statements below describe
the initial pass, not the current delivery status.

Measured offline on 2026-09-14. The reviewed checkout was
`362a920de99d95e16b4935877dd0f3e36998eb0d`, with no pre-existing working changes;
its original 38 tests passed. The implementation now has **73 passing tests**, plus
Ruff check/format and all required pre-commit hooks. No GPU, trainer, repair harness,
runner change, new upstream repository, or historical data rewrite was performed.

**Outcome:** frozen diagnostic candidates exist; there is no nonempty strict future
evaluation set. The full-text Hugging Face upload is held for the requested
[privacy/redistribution review](04-publication-review.md). Schema validity and
reproducible membership do not certify bug causality, temporal text validity, or rights.

## Inputs and implementation

| Population | Original full / report-backed rows | Pinned upstream revision |
|---|---:|---|
| LLVM | 8,504 / 8,357 | `3efd20d463e1b1210d2ff07cd79b68d6fa215f24` |
| ClickHouse | 1,049 / 1,022 | `d1adb9f9ffeeb41f2a7b4db2259d14e3db5a8edc` |
| PostgreSQL | 1,333 / 1,318 | `798bdcae89debabc59fa8afc6d690fec584db32f` |
| Linux | 63,115 / 5,424 | `654ae5d73c05bd2943d65636ce6cd0aa46e62f18` |

All populations are the complete original v2 extraction inputs, including null reports,
not a fresh history mine. Original `COMMAND.txt` and shard hashes are recorded in each
snapshot; LLVM used the historical since-2024 candidate extraction and the other three
since-2022. Git log filtering and ancestry limit coverage; no completeness claim is made
through the explicit test end, `2026-09-09T00:00:00Z`.

Implementation commits precede their output generation:

- `25e8eb22b717f90aff01d4016743bb36c4c2e568`: preparation pipeline; PostgreSQL report annotations.
- `b717dc2e35d2b5db81c62dd52c0f5f59ded449e8`: metadata reads avoid merge-parent blobs; final full LLVM/ClickHouse Git enrichment and Linux report annotations.
- `0e36b47`: bounded tree pathspecs, feature-area task correction, frozen-evidence reclassification; final v3.1 annotations, splits and baselines. Full revisions/file hashes are in snapshots/manifests.

The final package reader correction is named by the committed implementation in
`release.json`; earlier enrichment/split/baseline revisions remain unchanged.

The first smoke run exposed `git show -s` attempting merge-parent blob reads; it was
interrupted before output files and replaced with exact `git log --no-walk -1`.
ClickHouse baseline then exposed the OS argument limit on a large branch jump; bounded
literal pathspec batches fixed it before the first completed baseline was frozen.
The seeded sample found feature-area misclassification: v3.1 reclassifies frozen
text/labels under report-evidence-2 without another Git enrichment or manual row edits.
Preliminary v3 and ClickHouse partition-v1 artifacts remain local and superseded.
Final packaging also found one QEMU report with a Unicode line separator inside a
valid JSON string. The shared JSONL reader now iterates physical file lines; its
regression test preserves that text. No data row was repaired or dropped. The failed
partial package is retained separately; it did not produce a release manifest.

## Yield and exclusions

| Measure | LLVM | ClickHouse |
|---|---:|---:|
| Historical report-backed instances | 8,357 | 1,022 |
| Locally diagnostic eligible, before group/date exclusions | 7,679 | 911 |
| Locally strict, before grouping | 8 | 2 |
| Locally strict with singleton evidence group | 0 | 2 |
| Frozen strict train / dev / test | refused | — / — / 0 |
| Frozen diagnostic train | 5,330 | — |
| Frozen diagnostic dev | 300 | — |
| Frozen diagnostic test | 1,059 | 397 |
| Excluded from diagnostic export, full population | 1,815 | 652 |

LLVM refuses the strict adaptation configuration because it has zero eligible pool
records; it does not shrink the 300-row development set. ClickHouse's evaluation role
needs no train/dev split, but both locally strict singletons lie outside future test.
Its manifest says `strict-candidate` with **zero exports**, not a certified benchmark.
Roles were fixed before baseline/model performance: LLVM adaptation candidate;
ClickHouse provisional transfer evaluation. Diagnostics retain unknown task/provenance
checks and may contain development requests; they are not verified bug-fix sets.

The following local reasons overlap and cannot be summed as disjoint drops. Structural
exclusions concern the full extraction population; task/ambiguity counts here concern
report-backed cases. Missing reports are counted separately.

| Reason / evidence gap | LLVM | ClickHouse |
|---|---:|---:|
| No report | 147 | 27 |
| Unsupported target change status | 210 | 19 |
| Primary file missing in base | 201 | 18 |
| Projected file count outside 1–5 | 2 | 0 |
| Multiple resolved reports | 322 | 36 |
| Explicit feature task | 154 | 59 |
| Other task | 25 | 6 |
| Unknown task among reports | 4,308 | 335 |
| Unknown consumed text version among reports | 8,206 | 1,014 |
| Unresolved extra references among reports | 7,832 | 189 |

Every selected report's creation timestamp precedes its fix. Only 151 LLVM and 8
ClickHouse consumed versions have supported pre-fix evidence; the others remain
unknown, not proven edited after the fix. Expanded reference resolution distinguishes
17 known LLVM PR references and 5 ClickHouse PR references; remaining cache misses
(8,841 / 240 reference attempts) are not silently presumed to be PRs or fetched.
The legacy multiple-number counts were reproduced: LLVM 296, ClickHouse 30; expanded
resolved-report counts above use a different parser/evidence denominator.

The two LLVM issue #139380 instances (`llvm__58cc1675ec7b` and
`llvm__56385af687c3`) share a group and are quarantined across the pool/test boundary.
Temporal group crossings quarantine 152 LLVM and 35 ClickHouse rows before local
filtering; another 9 LLVM rows are quarantined at train/dev. The 1,008 LLVM and 351
ClickHouse buffer exclusions remain visible. Repeated reports are grouped even when
one member is later ineligible. Full patch IDs were available for 569/8,504 LLVM and
170/1,049 ClickHouse rows; missing full-diff blobs are explicit offline limitations.
This limits duplicate discovery and is not evidence that the remaining patches are unique.

The narrower all-non-test-in-scope sensitivity retains 5,923/7,679 locally diagnostic
LLVM and 890/911 ClickHouse rows (loss 1,756 / 21); primary eligibility does not silently
require it. Full raw changes preserve `.td`, `.def`, build files, and gitlinks.

## ClickHouse shift audit

The added-gold regression is reproduced: **18/1,022** reports have added historical
gold, including **4** with only newly added gold. `clickhouse__234ed4f04615` / issue
#116905 is excluded for feature-task evidence, target addition and missing base file.
LLVM likewise has 198 added-gold rows, 42 entirely added. New projection counts can
differ from historical gold; raw fields were not rewritten.

ClickHouse authored-year counts are 2022: 34, 2023: 39, 2024: 19, 2025: 42,
2026: **888/1,022 (86.9%)**. Its 2026 committer-month counts are:

| Month | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Instances | 8 | 85 | 127 | 66 | 158 | 153 | 152 | 132 | 8 |

All earlier author/committer months remain in `summary.json`. Median report age is
9.229 days, range 0.000081–3,337.461 days; all 1,022 ages use actual selected-report
creation times and committer times, with no negative ages. There are 973 distinct
selected reports, 39 reused identities. Full-population group sizes are 930 singletons,
42 pairs, 7 triples, 2 groups of four and 1 of six.

Task counts are bug 622, feature 59, other 6, unknown 335. Among report-backed full
change lists, status M occurs in 1,019 rows, A in 730 and D in 10; these overlap and
include tests/non-target files. Only target-status violations drive the local exclusion.

Raw fixing-message attribution supports observed assistance in **518/1,022** rows;
504 have no observed marker. LLVM has 312 observed and 8,045 not-observed. Earlier
stripped messages had removed attribution evidence. These are scoped marker counts,
not estimates of all AI assistance or claims that an entire population was generated.
No marker-based blanket exclusion is applied. See [the agent sample review](05-agent-audit.md).

## Explicit-path baseline

All report-backed LLVM/ClickHouse rows are attempted, including structurally excluded
ones, using projected gold for scoring only. This is a descriptive population audit,
not a strict test result. Predictions receive report text plus the exact pre-fix regular
file inventory and a derived unique-basename index. Wrong predictions are retained.
Source is `github_issue` for both populations; per-source totals equal repository totals.

| Repository | Reports | Macro precision | Macro recall | Macro F1 | Empty predictions | Inventory failures |
|---|---:|---:|---:|---:|---:|---:|
| llvm | 8,357 | 0.1237 | 0.1959 | 0.1312 | 63.81% | 0 |
| clickhouse | 1,022 | 0.2053 | 0.3606 | 0.2221 | 47.36% | 0 |

| Repository / stratum | n | Macro F1 | Empty predictions |
|---|---:|---:|---:|
| llvm / hint_stratum:basename | 679 | 0.4566 | 3.68% |
| llvm / hint_stratum:no_file_hint | 6,439 | 0.0000 | 82.31% |
| llvm / hint_stratum:path | 1,239 | 0.6350 | 0.65% |
| llvm / kind:explicit_bug_report | 3,870 | 0.1403 | 44.44% |
| llvm / kind:unknown | 4,487 | 0.1234 | 80.52% |
| clickhouse / hint_stratum:basename | 30 | 0.5567 | 0.00% |
| clickhouse / hint_stratum:no_file_hint | 593 | 0.0000 | 80.78% |
| clickhouse / hint_stratum:path | 399 | 0.5271 | 1.25% |
| clickhouse / kind:explicit_bug_report | 622 | 0.1774 | 41.96% |
| clickhouse / kind:unknown | 400 | 0.2918 | 55.75% |

All 9,379 inventories and projected gold sets were available. Separate full-tree
reads reproduced incremental-cache predictions for every final seeded case (20 LLVM,
18 ClickHouse). No empty prediction or infrastructure failure was removed from the
denominator. Source/kind/hint slices and every predicted path remain in the artifacts.

## Cached mail/source annotations

PostgreSQL's 1,318 reports were annotated as 288 explicit bug reports, 475 ordinary
messages, 531 replies and 24 patch submissions. These are heuristics, **not 288 verified
original bugs**. Archived timestamps lacking a timezone stay unknown. Linux's 5,424
reports were annotated as 2,735 automated diagnostics, 1,060 explicit bug reports,
490 ordinary messages, 1,120 replies, 18 patch submissions and 1 unknown. Existing
lore kinds and the exact selected syzbot crash identity/evidence remain available.

These are reports-only runs: Git gold/fix timing was not enriched for PostgreSQL/Linux,
so their “strict 0”, empty change lists and zero added-gold counters do not certify
absence of problems. No strict splits/baselines were generated for them. systemd/QEMU
retain historical v2 only; the systemd 12-row multiple-reference count was reproduced,
but their full Git/provenance/split checks were not rerun in this focused pass. Linux
candidate expansion beyond the existing Fixes-based extraction remains deferred.

## Verification and artifacts

The focused fixtures cover target A/D/R/T exclusions, added-test acceptance, paths under
`python -O`, root/revert/token regressions, raw trailers, cache misses, task evidence,
creation versus body versions, groups/backports/shared-Fixes behavior, buffer/dev
quarantine, insufficient pool refusal, exact runner schema, deterministic hashes,
large tree inventories and prediction/scoring separation.

Real-data checks verified every consumed payload hash (LLVM 8,645; ClickHouse 1,038;
PostgreSQL 1,345; Linux 6,332), each evidence manifest, and unchanged original v2
input hashes. Both repositories' strict and diagnostic split commands replayed
byte-for-byte into separate temporary directories, with exact five-field validation
and no group overlap. CLI runner validation also passed all 7,086 exported instances
with zero invalid rows or duplicate IDs. Original tracked data has no diff. All 39 reviewed source
payload/text matches passed; the review is agent-only, targeted and non-executable.
Local machine-readable verification is in `releases/verification.json`.

Frozen local paths:

- `data/{llvm,clickhouse}/v3.1/{manifest,snapshot,summary,groups}.json` and record/payload/sample shards.
- `data/{llvm,clickhouse}/splits-v2/manifest.json`: strict refusal/empty outcome.
- `data/{llvm,clickhouse}/diagnostic-v2/manifest.json` and exact five-field runner shards.
- `data/{llvm,clickhouse}/baseline-v1/{manifest,summary}.json` and predictions.
- `data/{postgres,linux}/v3/`: cached source annotations only.

The full-text review package is prepared locally at
`releases/cpp-loc-review-v2/` for destination `jingunhong/cpp-loc`, with an explicit
publication hold. It preserves historical unfiltered five-field configs and final
companions; it has not been cleared or uploaded. The complete cache/clones are excluded.

Initial filesystem and network restrictions required committing in a temporary
checkout. After permissions were restored, the five implementation commits through
`f40360c9c49ebf128e75fe92fae73da2fc2291d8` were restored and pushed to the original
GitHub repository without rewriting history. Hugging Face write access was verified,
and `jingunhong/cpp-loc` was created as an empty private dataset repository. No dataset
files were uploaded. Delivery and recovery records remain under the original
checkout's `releases/` directory; the remaining publication hold concerns content.

## Next LLVM pilot handoff

The next local command validates the existing **provisional diagnostic** runner files:

```sh
uv run python scripts/validate.py --runner --exact data/llvm/diagnostic-v2/{train,dev,test}-*.jsonl
```

To reproduce preparation after applying the implementation commits, choose a fresh
output directory (the frozen one is never overwritten):

```sh
uv run python scripts/prepare.py split --input data/llvm/v3.1 --out data/llvm/pilot-diagnostic-v1 --view diagnostic --role adaptation-candidate --test-end 2026-09-09T00:00:00Z
```

This does not authorize public release or certify a strict experiment. Strict yield
needs evidence for consumed issue versions, resolution of uncached extra issue/PR
references, and task/provenance review; a historical-body crawler is outside this pass.
Missing full-diff blobs limit exact-patch grouping. No checks are silently relaxed.
Full-text publication additionally needs the rights/notices and privacy decisions in
[04](04-publication-review.md). The separate HANA-first runner must enforce the
[report-only observation and workspace boundary](02-splits-and-provenance.md#runner-boundary).
