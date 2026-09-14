# Linux extraction (v0, v1, v2)

Upstream: `torvalds/linux`, blob-less clone at `repos/linux`. Candidates are non-merge,
non-revert commits whose message carries a `Fixes: <sha> ("...")` trailer. The problem
statement is the commit subject and body with trailers stripped (`problem_source =
"commit_message"`); `base_commit` is the first parent; `created_at` is the author date;
`file_changes` are the changed non-test C/C++ sources; `gold_functions` is `null`.

## Range

- **v0**: `--since 2026-01-01`, a single file under the 50 MB limit.
- **v1**: `--since 2022-01-01`, five shards (`instances-000.jsonl` … `instances-004.jsonl`,
  four of 45 MB and one of 0.3 MB), plus `metadata.leakage` flags. Same upstream HEAD.

`--since` is a committer-date bound; 325 v1 instances carry an author date (`created_at`)
before 2022, the earliest 2019-05-02. Split on `created_at`.

v1 funnel (`data/linux/v1/STATS.md`):

| Stage | Survived | % of candidates |
|---|---:|---:|
| candidates | 412,585 | 100.0% |
| not merge | 379,555 | 92.0% |
| not revert | 377,187 | 91.4% |
| has `Fixes:` reference | 73,087 | 17.7% |
| has gold files | 63,671 | 15.4% |
| 1–5 gold files | 63,115 | 15.3% |
| has problem statement | 63,115 | 15.3% |

`scripts/validate.py`: 63,115 valid, 0 invalid, 0 duplicate ids. A dry run earlier the
same day over the same HEAD counted 412,587 candidates: git's `--since` pruning is a
heuristic at the date boundary and can differ by a few commits between runs; the
instance count was identical.

Full-set leakage (v1): 6.4% of problem statements name a gold path verbatim, 8.6% a gold
basename, 39.4% a function from the patch's hunk headers.

Shipped v0 funnel (`--since 2026-01-01`, `data/linux/v0/STATS.md`): 66,410 candidates →
60,927 non-merge → 60,625 non-revert → 16,577 with a `Fixes:` reference → 15,042 with gold
files → **14,918 instances** (1–5 gold files). `scripts/validate.py`: 14,918 valid, 0 invalid,
0 duplicate ids. `instances.jsonl` is 43.7 MB.

## Practical notes

- A name-only `git log` over the whole range is tree-only on a partial clone (verified:
  no promisor pack appeared over 412k commits). Patches need blobs: the extractor collects
  pre/post blob ids with `git diff-tree` and bulk-fetches them in batches of 5,000 before
  running `git diff`, which then works offline at ~30 ms per instance.
- Keep shells, editors and IDE git integrations out of `repos/linux`; anything that diffs
  HEAD against the (empty, `--no-checkout`) index fetches all ~96k blobs of HEAD (293 MB).
- `gc.auto` is set to 0 on the clone; a background repack of the 2 GB clone stalls diffs.

## Leakage note

`uv run python scripts/leakage.py data/linux/v0/instances.jsonl --n 20 --seed 0` samples 20
instances and checks whether the problem statement contains, verbatim, a gold file path,
a gold file basename, or a function name taken from the patch's hunk headers.

| Named verbatim in the problem statement | Instances (of 20) |
|---|---:|
| full gold file path | 2 |
| gold file basename | 3 |
| function name from the patch | 9 |

Function names leak in roughly half the sample: kernel commit subjects are conventionally
`subsystem: function_name: what was wrong`, and bodies routinely quote the function being
fixed. Paths are rarer. Nothing is scrubbed in v0; a later version should at least measure
this on the full set and consider masking identifiers or evaluating on the body only.

## v2: original reports as problem statements

`data/linux/v2/` (same clone, HEAD, range and funnel as v1: 63,115 instances, five shards
of 45 MB, 45 MB, 45 MB, 45 MB and 38 MB). `problem_statement` is the original report when
the commit links one, resolved in the order syzbot → lore `Closes:` → bugzilla.kernel.org;
the commit message moved to `commit_message`. `Link:` is recorded in
`metadata.report_refs.link` (42,561 instances) and never fetched.

### Reports

| Source | Instances with a ref | Resolved | Drops (refs) |
|---|---:|---:|---|
| `syzbot` (`Reported-by: syzbot+…`, `syzkaller.appspot.com/bug?…`): bug title + first crash report | 1,812 | 1,809 | 4 not found (login-only namespace) |
| `lore_report` (`Closes: https://lore.kernel.org/…`): subject + body, quotes and signature stripped | 3,853 | 3,087 | 230 `[PATCH …]` posts, 124 not found |
| `kernel_bugzilla` (`bugzilla.kernel.org/show_bug.cgi?id=N`): summary + first comment | 548 | 528 | (private bugs are cached as not found; none hit) |
| any | 5,752 (9.1%) | **5,424 (8.6%)** | |
| `problem_statement: null` | | **57,691 (91.4%)** | |

That is the honest picture: over 90% of `Fixes:` commits link no report at all, only the
patch's own submission (`Link:`). The kernel's `Closes:` convention dates from 2023, so the
report rate rises over the range.

Leakage: `problem_statement` (5,424 instances) path 55.2%, basename 56.8%, patched function
45.1%; `commit_message` (63,115) path 6.4%, basename 8.6%, function 39.4%. Crash dumps and
build logs name files and functions almost by definition (`WARNING: mm/vma.h:277 at
vma_set_pgoff`), so report-backed Linux instances leak far more than commit messages at the
file level; nothing is masked, the flags are there to stratify on.

Report length: syzbot median 4,036 characters (longest 145k), lore 2,569 (longest 545k, a
kernel test robot mail with its config attached inline), bugzilla 1,541. Lore reports
include kernel test robot build/sparse warnings (`oe-kbuild-all`), reviewer replies to
patches (`Re: [PATCH …]`, including automated review bots) and human reports.

Practical: all fetching goes through `repos/cache/<source>/`; the syzkaller dashboard
throttles an IP at ~20 requests/minute, so `Syzbot.pace = 3 s` and the ~1,900 bugs (two
requests each) take about 3.5 hours; lore and bugzilla run at 0.5 s pace in parallel
threads. The blob-less clone rules above still apply; the v2 patch phase reused the blobs
fetched for v1.

### v2.1 (extractor 0.2.1): lore text fixes

The first v2 run decoded lore mail as UTF-8 before parsing it, which mangled non-UTF-8
charsets and transfer-encoded bodies: 285 of the 3,087 lore reports carried U+FFFD
mojibake (138) or literal `\uXXXX` escape sequences (147). The fetcher now caches the raw
message bytes (base64 in the JSON cache) and parses them with
`email.message_from_bytes`, so the email library resolves charset and transfer encoding;
a part whose declared charset is unknown or does not decode falls back to UTF-8 with
replacement and is counted under `report counters` as `lore_report: charset fallback`
(24 on this run, not drops). The same run fixed the signature cut in `clean_body`: only
a `-- ` line (dash dash space) ends the body; a bare `--` inside a log or diff used to
truncate it.

Effect on the data (lore refs re-fetched, syzbot and bugzilla caches untouched): 494
lore problem statements changed, 241 of them longer (signature rule), the yield is
unchanged (5,424 / 3,087). Acceptance: literal `\uXXXX` in any problem statement 0;
U+FFFD in lore reports 20 instances, of which one mail (a `charset="utf-8"` base64 body
that is not valid UTF-8) accounts for 3,733 characters and the other 19 carry 1–14 each.
The leakage rates above moved with the longer bodies (path 54.6% → 55.2%, basename
56.2% → 56.8%, function 44.3% → 45.1%).

### v2.1: lore report kinds, short reports, syzbot crash choice

`metadata.report_kind` classifies lore reports from the cached mail only (sender, list in
the URL, subject, cleaned body; no fetching), rules in order: `robot` when the sender is
`lkp@intel.com`, the list is `oe-kbuild-all` or `oe-lkp`, or "kernel test robot" appears
in From or body; else `reply` when the subject matches `^Re:\s*\[` (a reply to a posted
patch); else `fresh`. syzbot and bugzilla instances carry `report_kind: null`.

| `report_kind` (lore_report, 3,087) | Instances |
|---|---:|
| `robot` | 1,034 |
| `reply` | 909 |
| `fresh` | 1,144 |

Reports shorter than 300 characters after cleaning (title + body; informational, not a
filter): lore 117, syzbot 13, bugzilla 14.

Per-source leakage of `problem_statement` (`uv run python scripts/leakage.py
data/linux/v2/instances*.jsonl`): syzbot path 83.5%, basename 84.1%, function 57.2%
(1,809); lore 46.0% / 48.1% / 42.8% (3,087); bugzilla 12.1% / 14.0% / 17.4% (528).

Syzbot crash choice: the bug JSON's `crashes[]` entries carry no time field (checked over
all 48,857 crash entries of the 1,910 cached bugs: title, kernel config, kernel and
syzkaller commits, crash-report and reproducer links only), so the report stays
`crashes[0]`, the dashboard's newest crash, which may postdate the fix. Nothing was
re-fetched and no `report_crash_time` is recorded.
