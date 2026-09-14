# 06 — Six-source follow-up and private review export

Offline follow-up on 2026-09-14. The original focused pass is retained in
[03](03-validation-report.md). This pass extends full Git enrichment, grouping,
strict/diagnostic splitting, and the report-only path baseline to the four existing
Linux, systemd, PostgreSQL, and QEMU populations. LLVM and ClickHouse's frozen
outputs are preserved. No new repository, history mining, model training, GPU run,
or reproducer execution is included.

## Inputs and roles

All six populations use their complete original v2 extraction inputs, including
null reports for grouping: 78,246 candidates and 18,216 report-backed instances.
Original v0/v1/v2 files remain unchanged. Local paths below are relative to the
original `Cpp-SWE-bench` checkout; this code repository contains no corpus files.

LLVM remains the adaptation candidate. ClickHouse retains its provisional transfer
evaluation role. The four additional sources were assigned evaluation-only roles
before measuring their baselines, so they receive no train/dev exports. The unchanged
half-open UTC schedule is pool `[2024-01-01, 2026-03-01)`, buffer
`[2026-03-01, 2026-06-01)`, and test `[2026-06-01, 2026-09-09)`.
LLVM's development set remains the latest 300 eligible pool records with group
quarantine. Unsupported chronology is never relaxed to increase yield.

| Repository | Pinned upstream revision |
|---|---|
| LLVM | `3efd20d463e1b1210d2ff07cd79b68d6fa215f24` |
| ClickHouse | `d1adb9f9ffeeb41f2a7b4db2259d14e3db5a8edc` |
| Linux | `654ae5d73c05bd2943d65636ce6cd0aa46e62f18` |
| systemd | `726e17a933296e7107f862c6ebe175a3d176e6bb` |
| PostgreSQL | `798bdcae89debabc59fa8afc6d690fec584db32f` |
| QEMU | `ff1d2d19d7e24893e2012d879f8e73077e17b9bd` |

Pinned revisions, original extraction commands, consumed cache hashes, and input
shard hashes are recorded in each `data/<repo>/v3.1/snapshot.json` and manifest.
The full extraction range is inherited, not a completeness claim through test end.
Linux still reflects the original Fixes-based selection; expansion beyond it is deferred.

## Measured yield

| Repository | Full input | Reports | Local diagnostic | Local strict / singleton | Diagnostic train / dev / test | Strict test |
|---|---:|---:|---:|---:|---:|---:|
| LLVM | 8,504 | 8,357 | 7,679 | 8 / 0 | 5,330 / 300 / 1,059 | 0 |
| ClickHouse | 1,049 | 1,022 | 911 | 2 / 2 | 0 / 0 / 397 | 0 |
| Linux | 63,115 | 5,424 | 4,712 | 1,582 / 1,434 | 0 / 0 / 382 | 105 |
| systemd | 1,424 | 1,418 | 1,372 | 5 / 2 | 0 / 0 / 73 | 0 |
| PostgreSQL | 1,333 | 1,318 | 1,185 | 0 / 0 | 0 / 0 / 171 | 0 |
| QEMU | 2,821 | 677 | 646 | 0 / 0 | 0 / 0 / 20 | 0 |

“Local strict / singleton” is eligibility before temporal filtering, with the second
count additionally requiring one-to-one evidence within the mined population.
Diagnostics can retain unknown task/provenance evidence and development requests;
they are not verified bug-fix ground truth. A zero strict test is an actual empty
outcome. LLVM's strict adaptation command refuses an insufficient pool rather than
shrinking development. Historical reports, local eligibility, and frozen test counts
have different denominators.

| Local exclusion | Linux | systemd | PostgreSQL | QEMU |
|---|---:|---:|---:|---:|
| multiple report references | 682 | 16 | 105 | 20 |
| no report | 57,691 | 6 | 15 | 2,144 |
| patch submission | 18 | 0 | 24 | 0 |
| primary file count outside 1–5 | 0 | 0 | 0 | 2 |
| primary file missing in base | 91 | 17 | 4 | 10 |
| report creation post fix | 0 | 2 | 0 | 0 |
| report text version post fix | 0 | 2 | 0 | 0 |
| task feature | 1 | 1 | 0 | 0 |
| task other | 0 | 12 | 0 | 3 |
| unsupported target status | 133 | 18 | 4 | 14 |

These are overlapping local reasons over full extraction populations and cannot be
summed into a total. Group and temporal exclusions are recorded separately in split
manifests. PostgreSQL's cached archive timestamps lack timezone information, leaving
all 1,333 creation/text-version checks unknown. Its 288 heuristic explicit bug reports
are not 288 verified original bugs. systemd has two selected reports created after
their linked fixes. QEMU has only four supported consumed text versions in the full
population, none yielding a locally strict record.

Linux has 3,087 lore reports, 1,809 syzbot reports, and 528 Bugzilla reports.
Consumed text timing is supported for all 3,087 selected mails and 208 Bugzilla
versions; it remains unknown for all 1,809 syzbot selections and 320 Bugzilla versions.
The strict future candidates are 98 lore and seven Bugzilla reports. Rule eligibility
is not exhaustive source review or verified bug causality. Groups spanning temporal
partitions quarantine 80 full-population Linux rows. The 11,198 shared Fixes targets
remain audit flags and are not used alone to merge distinct bugs; 239 duplicate-text
groups are also audit-only.

Full-diff stable patch IDs were available for 62,213/63,115 Linux, 993/1,424 systemd,
747/1,333 PostgreSQL, and 2,643/2,821 QEMU candidates. Missing offline diff blobs limit
duplicate discovery; singleton groups do not prove global one-to-one bug/fix relations.

## Report-only baseline and verification

| Repository | Reports | Macro precision | Macro recall | Macro F1 | Empty predictions |
|---|---:|---:|---:|---:|---:|
| llvm | 8,357 | 0.1237 | 0.1959 | 0.1312 | 63.81% |
| clickhouse | 1,022 | 0.2053 | 0.3606 | 0.2221 | 47.36% |
| linux | 5,424 | 0.2457 | 0.5208 | 0.2709 | 31.43% |
| systemd | 1,418 | 0.1406 | 0.1381 | 0.1314 | 79.90% |
| postgres | 1,318 | 0.2046 | 0.2508 | 0.1988 | 62.90% |
| qemu | 677 | 0.2258 | 0.2706 | 0.2305 | 59.82% |

All 18,216 pre-fix inventories and projected gold sets were available; no
infrastructure failures were removed or observed.

The denominator is every original report-backed instance, including rows excluded
from splits and later withheld from private storage. Prediction uses only report text
and the exact pre-fix regular-file inventory. Projected gold is scorer-only. Empty
predictions remain in the denominator. Source/kind/hint slices and predictions are
preserved in each baseline artifact; these population audits are not strict test scores.

For Linux, systemd, PostgreSQL, and QEMU, all four output manifests and original v2
input hashes passed verification. Every consumed payload hash matched: respectively
6,332, 1,389, 1,345, and 661 payload records. Their strict and diagnostic commands
replayed byte-identically at their producing revisions, with exact runner schemas,
no duplicate IDs within a view, and no group crossing between its partitions.

All 70 additional seeded cases (20 Linux, 18 systemd, 17 PostgreSQL, 15 QEMU) matched
the cached selected report, processed text, and raw-text hashes. Independent full-tree
inventory reads reproduced their incremental baseline predictions. Evidence is in
`releases/six-repo-20260914/<repo>-verification.json`; the earlier LLVM/ClickHouse
checks remain documented in [03](03-validation-report.md).

Agent judgments are recorded separately in [05](05-agent-audit.md). Sampling is
seeded, targeted, and not an unbiased prevalence estimate; no human validation or
bug-causality claim is made. The current implementation has 75 passing tests plus
Ruff check/format and required pre-commit hooks.

## Frozen artifacts and reproduction

For each of `llvm`, `clickhouse`, `linux`, `systemd`, `postgres`, and `qemu`:

- `data/<repo>/v3.1/`: full evidence, source snapshot, groups, summaries, seeded samples.
- `data/<repo>/splits-v2/`: strict manifest, including empty/refused outcomes.
- `data/<repo>/diagnostic-v2/`: diagnostic manifest and exact five-field runner shards.
- `data/<repo>/baseline-v1/`: baseline manifest, summaries, and every prediction.

The additional systemd/PostgreSQL/QEMU enrichment ran at `a69d969`, and their
split/baseline commands at `3d1538c`. Linux enrichment ran at `2cddad1` using the
optional bounded process backend; its split/baseline revision is `522a5b8`.
Existing LLVM/ClickHouse revisions remain recorded in their frozen manifests.
The process and thread backends produce identical fixture artifacts and use the same
eligibility rules. Every package records the committed implementation and file hashes.

Example replay from the code repository, using fresh output directories:

```sh
uv run python scripts/prepare.py enrich --repo systemd \
  --input ../Cpp-SWE-bench/data/systemd/v2 --out data/systemd/replay-v3 \
  --repos-dir ../Cpp-SWE-bench/repos --offline --workers 8
uv run python scripts/prepare.py split --input data/systemd/replay-v3 \
  --out data/systemd/replay-diagnostic --view diagnostic --role evaluation-only \
  --test-end 2026-09-09T00:00:00Z
uv run python scripts/prepare.py audit --repo systemd --input data/systemd/replay-v3 \
  --out data/systemd/replay-baseline --repos-dir ../Cpp-SWE-bench/repos --offline
```

Manifests include the producing revision: byte-identical manifest replay requires
the recorded code revision as well as the same data/configuration. Raw cache misses
and unavailable full-diff patch IDs remain evidence limitations, not uniqueness proof.

## Private review delivery

The full local bundle is `releases/cpp-loc-review-v3/`. The separate private storage
copy is `releases/cpp-loc-private-review-v2/`, destined for
[`jingunhong/cpp-loc`](https://huggingface.co/datasets/jingunhong/cpp-loc).
The local bundle is not the upload payload.

The first private package passed all local content/loader checks but Hub card
validation rejected its relative license-review link. The exporter now emits an
HTTPS link. That local-only v1 attempt is retained; v2 regenerates the card and
release hashes from the same parent bundle without changing any retained row.

The screen withholds five unique historical rows (two phone-context rows and three
credential-shaped examples), retaining **18,211** unique report-backed instances: LLVM 8,357,
ClickHouse 1,019, Linux 5,423, systemd 1,418, PostgreSQL 1,317, and QEMU 677.
None of the withheld IDs occur in the frozen strict or diagnostic exports, so those
split memberships and counts are unchanged. There are 13 nonempty configurations:
six historical views, six diagnostic views, and Linux's strict candidate test.
These overlapping views are not 13 disjoint datasets; the 105 strict Linux candidates
also occur in its 382-row diagnostic test.

`publication-screen-2` scans decoded string values in every runner field and exported
source record. It withholds phone-context and credential-pattern rows without masking
retained text. Original row bytes and eligibility evidence remain unchanged locally;
the storage subset and its hashes are a new release. Names, email addresses, home
paths, and unrecognized sensitive content may remain. False positives include examples.
Dedicated raw-mail, fixing-message, and full-patch companions and caches stay local;
retained reports can still contain quoted mail and embedded code/patch snippets.

The private copy includes exact five-field JSONL, source links and hashes, group and
eligibility/chronology metadata, baseline summaries, a dataset card, and `release.json`.
Metadata and gold are controller/reviewer-only. Unfiltered views preserve historical
gold; eligibility metadata refers to the enriched primary-file projection. Baseline
summaries describe the original populations before this storage filter. The exporter
does not implement the separate runner's runtime isolation.

Delivery verified on 2026-09-14: Hub commit
[`528bffec7602b48d4ad4687d5735a61af8a7718c`](https://huggingface.co/datasets/jingunhong/cpp-loc/commit/528bffec7602b48d4ad4687d5735a61af8a7718c)
is **private**. All 24 uploaded files (127,353,501 bytes) match the local content
hashes; the only additional remote file is the pre-existing `.gitattributes`.
The Hub accepted the card metadata, all 13 configurations loaded locally through
`datasets`, and authenticated loading of `linux_strict/test` from the pinned Hub
revision returned the expected 105 exact five-field rows. Every retained instance
has matching compact provenance, the storage screen has no remaining high-risk
pattern matches, and split group separation is preserved.

The private export was produced at `2c6db4d`; its `release.json` SHA-256 is
`d73ad6f5d63545c402ead475feb522e26a80d33f7a733f4c2fa86f9cb05bc2c5`.
Local verification receipts are
`releases/six-repo-20260914/{private-v2-verification,hf-delivery}.json`.
These checks establish delivery and the stated screening scope, not public-release
privacy or intellectual-property clearance.

Public privacy/IP review remains open: source-specific redistribution rights, embedded
code notices/attribution, personal-data treatment and basis, and a contact/removal
process. The code's MIT license supplies no blanket dataset license. Private access
does not settle these questions. See [04](04-publication-review.md).
