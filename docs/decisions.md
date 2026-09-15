# Decisions

Conservative choices made without feedback, newest last. Dates are absolute.
Pre-migration commits and artifacts are retained in a private research archive;
their identifiers record provenance and do not imply public access. Package-path
examples use the current `cpp_loc` name; frozen manifests retain their recorded paths.

## 2026-09-05 — scaffold

- **Package layout.** Use a top-level package directory (now `cpp_loc/`, with uv
  `module-root = ""`) rather than a `src/` layout.
- **Upstream clones live in `./repos/` (git-ignored)**, not `~/repos/` as the original README said.
  README updated. API caches for later repositories go under `repos/cache/`.
- **Runtime dependencies: none.** git is driven via `subprocess`; JSON, regex, argparse from stdlib.
- **Hooks.** `no-commit-to-branch` deliberately not enabled (we commit to main). Large-file limit
  is 50 MB (`--maxkb=51200`). pytest runs as a local `language: system` hook via `uv run`.
- **Timestamps.** `created_at` is git's `%aI` verbatim; git prints UTC as `...Z`, which is valid
  ISO-8601 and is accepted by `validate()`. Not normalised to `+00:00`.
- **`--since` semantics.** Passed straight to `git log --since`, which filters on *committer*
  date, while `created_at` records the *author* date. So a few instances may carry an author
  date earlier than `--since`. Accepted for v0; consumers doing temporal splits should split on
  `created_at`, not on the run's `--since`.
- **Revert detection** is textual: subject starting with `Revert` or a body line starting with
  `This reverts commit`. No SHA verification.
- **Trailer stripping** removes matching lines anywhere in the message, not only in the final
  trailer block, and treats any `<Word>-by:` key as a trailer. Continuation lines of trailers
  (rare, indented) are not stripped.
- **Test-path heuristic** is by directory name (`test`, `tests`, `testing`, `selftests`,
  `unittest(s)`) and by a `test` token in the file name delimited by `_`, `-`, `.` or the
  ends of the name. `kernel/latest.c` and `mm/contest.c` are not test paths.
- **Gold files** exclude test paths rather than dropping the commit: a fix touching
  `mm/x.c` plus a selftest yields `gold_files == ["mm/x.c"]`. The total number of changed
  files is kept in `metadata.changed_files_total` so this can be revisited.
- **Blob fetching.** Patches need contents, so after filtering we collect the pre/post blob ids
  from `git diff-tree` (tree-only, no fetch) and bulk-fetch them with the same
  `git fetch --stdin --filter=blob:none` command git's own lazy fetch uses, in batches of
  5000, before running `git diff`. This avoids one round trip per instance.
- **instance_id** uses the first 12 hex characters of the fix SHA.

## 2026-09-05 — Linux v0 run

- **Shell working directory must stay outside the clone.** The tooling around this session runs
  `git diff --cached --shortstat` in the shell's current directory; inside a `--no-checkout`
  partial clone that command needs every blob in HEAD and pulled 293 MB (95,380 blobs) twice
  before it was traced. The extractor itself was verified tree-only: a name-only log over
  412k commits fetched nothing.
- **Auto-gc disabled on clones** (`git config gc.auto 0` in `repos/linux` and `repos/llvm`).
  Lazy fetches create one pack each; the first run hit `gc.autoPackLimit` and a background
  repack of the 2 GB clone stalled every `git diff` for minutes.
- **Prefetch guard** checks `remote.origin.promisor == true`; `extensions.partialClone` is
  not set by current git for `--filter` clones.
- **`--since 2026-01-01`, not 2022-01-01.** The full range since 2022 yields 63,115 instances
  (~190 MB with patches); the 50 MB limit allows ~15k instances at the measured ~3 KB per
  instance, and 2026-01-01 is the earliest month boundary that fits. Funnel counts for the
  full 2022+ range are recorded in `docs/extraction-linux.md` for reference.
- **`Fixes:` reference is not resolved.** `metadata.references` stores the SHA prefixes as
  written in the trailer (7–40 hex chars); they are not verified to exist.
- **Multiple `Fixes:` trailers** keep the commit as one instance listing all references.

## 2026-09-05 — LLVM v0 run

- **Repository choice: llvm/llvm-project.** Compiler, C++-heavy, and since the 2021 move to
  GitHub issues commits carry `Fixes #N` / `Fixes <issue url>` / `Closes #N` lines
  (~10k such commits since 2024). ClickHouse references issues mostly in PR merge commits;
  Godot is smaller. Not benchmarked further.
- **`--since 2025-01-01`.** 5,924 git-side survivors versus 8,632 for 2024+, chosen to keep
  the first API pass around one hour at the authenticated 5,000 requests/hour limit.
- **Token.** `GITHUB_TOKEN` was not set. `gh` on this machine is logged in, so the run was
  started with `GITHUB_TOKEN="$(gh auth token)"` (the user's own account, read-only public
  issue reads). The extractor only ever reads the `GITHUB_TOKEN` environment variable.
- **Issue resolution.** The first referenced number that resolves to a real issue is used;
  numbers that are pull requests or 404 are skipped and counted under
  `problem statement drops` in STATS.md. A commit whose references are all PRs is dropped.
- **Responses cached** as raw JSON under `repos/cache/llvm__llvm-project/<n>.json` (404s cached
  as `null`), so re-runs are offline.
- **Problem statement = issue title + body verbatim** (Markdown, including any code blocks and
  stack traces). No scrubbing in v0; see the leakage note.
- **Transient API failures are retried** (up to 8 attempts, exponential backoff) for
  connection drops, timeouts and 5xx responses; 403/429 sleep until the quota resets; any
  other HTTP error aborts the run. The first LLVM run died on a `RemoteDisconnected` after
  562 issues; the cache made the restart free.

## 2026-09-05 — leakage and v1

- **Full-set leakage (v0).** Linux: 4.9% of problem statements name a gold path verbatim,
  6.9% a gold basename, 53.0% a function patched by the fix. LLVM: 14.4% path, 23.3%
  basename, 20.9% function.
- **No masking.** Real bug reports name functions and files; rewriting the text would make
  the instances less faithful and the masking itself is another labeling step that can be
  wrong. Instead every instance now carries `metadata.leakage = {path, basename, function}`
  so consumers can filter or stratify, and STATS.md reports the totals. Revisit if an
  evaluation needs a leakage-free subset larger than what filtering leaves.
- **Function-name leakage is measured from hunk headers**, i.e. git's default C/C++
  funcname heuristic on the patch; it is a proxy, not a gold function label.
- **v1 = full ranges + leakage flags, sharded.** `write_jsonl` splits above 45 MB into
  `instances-NNN.jsonl`; readers glob `instances*.jsonl`. Linux v1 covers commits since
  2022-01-01, LLVM v1 since 2024-01-01 (GitHub issues start in late 2021; earlier LLVM
  commits reference Bugzilla, which the pipeline does not read). Schema unchanged.
- **v0 is kept as is**; it is a strict subset range of v1 without the flags.
- **`git log --since` is not exactly reproducible at the boundary.** Two runs over the same
  HEAD counted 412,587 and 412,585 candidates (git prunes the walk heuristically when it
  meets commits older than the bound); the surviving instances were identical. A future
  version should pin the range by commit (`<sha>..HEAD`) instead of by date.
- **Patch phase parallelised** with 8 threads of read-only git calls; results are
  deterministic (ordered map), so output does not depend on scheduling.

## 2026-09-05 — more repositories

Survey (git-side funnel only, instances = 1–5 gold files; issue repos since 2024-01-01,
`Fixes:`-trailer repos since 2022-01-01):

| Repository | Link type | Instances | Decision |
|---|---|---:|---|
| qemu/qemu | `Fixes: <sha>` trailer | 2,367 | added (`qemu`), same rules as Linux |
| postgres/postgres | `Reported-by:` / `Bug: #N` + `Discussion:` URL | 1,333 | added (`postgres`), commit-message source |
| systemd/systemd | GitHub issues | 754 (since 2024) | added (`systemd`), run since 2022 |
| duckdb/duckdb | GitHub issues | 376 | skipped: links live in PR merge commits |
| nodejs/node | `Fixes: <issue url>` | 304 | skipped: most fixes are JavaScript-only |
| godotengine/godot | GitHub issues | 222 | skipped: links live in PR merge commits |
| sqlite/sqlite | Fossil mirror, forum posts | n/a | skipped: no API, 149 C files in `src/` |
| ClickHouse/ClickHouse | GitHub issues | 954 | added (`clickhouse`), run since 2022; blob-less clone is 6.7 GB |

- **PostgreSQL candidates** are commits with a `Reported-by:` or `Bug: #N` trailer, which
  the project uses only for reported problems; `Discussion:` alone marks every commit and
  is not used as a signal. `metadata.references` holds the bug numbers and the
  `Discussion:` archive URLs. `Discussion`, `Backpatch-through`, `Author` and `Security`
  were added to the trailer keys so they are stripped from problem statements.
- Skipped repositories cost one table line to add later; the merge-commit-only link
  pattern (DuckDB, Godot) would need a "walk PR merges and take the PR's commits" rule
  that does not exist yet.

## 2026-09-07 — v2: original reports as problem statements

- **Schema.** `problem_statement` holds the original report only and is `null` when none
  is linked or none resolves; `problem_source` is `null` exactly then. The old commit-message
  text moves to a new top-level `commit_message` (always present). `problem_source` values:
  `github_issue`, `gitlab_issue`, `syzbot`, `lore_report`, `kernel_bugzilla`, `pgsql_archive`.
  `metadata.leakage` is computed against `problem_statement` (`null` without one);
  `metadata.commit_message_leakage` against `commit_message`. Never mixed. Instances without
  a report are kept; the `has problem statement` funnel stage is gone. `extractor_version`
  0.2.0, output under `data/<repo>/v2/`, v0/v1 untouched.
- **No fallback, no invented source.** `commit_message` is never copied into
  `problem_statement`; what consumers do at training time is their decision.
- **`commit_message` is required non-empty** by `validate()`. No instance in any run so far
  had an empty stripped message; if one appears, validation flags it rather than the
  pipeline silently keeping or dropping it.
- **`metadata.report_refs`** is a dict keyed by kind (source name, or `link`/`launchpad`/
  `pgsql_bug` for kinds without a fetcher) so per-source yield can be measured offline; the
  refs are stored as parsed tokens the fetcher takes (URLs as written, `extid=<hash>` for
  syzbot, issue numbers as strings for GitHub, `#N` for PostgreSQL bug numbers).
- **One `Source` abstraction** (now `cpp_loc/reports.py`) replaces `github.py`: `refs`,
  `fetch` (raw, JSON-serialisable), `parse`; raw responses cached as JSON under
  `repos/cache/<source>/` (`null` for 404), shared retry/backoff and rate-limit sleeps.
  The existing GitHub caches were moved on disk to `repos/cache/github_issue/<owner__repo>/`
  so the issue-backed re-runs stay offline. Report fetching is a stage in `extract.py`
  after the git filters and before patches; `--no-reports` skips it.
- **Step 0 yield** (`--no-patch --no-reports`, same clones and ranges as v1/v0; instances
  with at least one ref of the kind):

  | Repository | Instances | Fetchable refs | Record-only refs |
  |---|---:|---|---|
  | linux (2022+) | 63,115 | lore `Closes:` 3,853; syzbot 1,812; bugzilla.kernel.org 548; any of the three 5,752 (9.1%) | `Link:` 42,561 |
  | qemu (2022+) | 2,821 (was 2,367: GitLab issue URLs are now a candidate signal) | GitLab issue 683 | `Link:` 294; Launchpad 6 |
  | postgres (2022+) | 1,333 | `Discussion:` archive URL 1,329 | `Bug: #N` 135 |
  | llvm (2024+) | 8,504 | GitHub issue 8,504 | |
  | systemd (2022+) | 1,424 | GitHub issue 1,424 | |
  | clickhouse (2022+) | 1,049 | GitHub issue 1,049 | |

  The issue-backed counts are before the PR/404 drops that used to happen at the
  `has problem statement` stage (llvm v1 8,357, systemd v0 1,418, clickhouse v0 1,022);
  those commits are now kept with `problem_statement: null`.
- **Launchpad fetcher skipped** (6 QEMU instances). Bugzilla is worth it (548).
- **Fetchers were written together with the parsers** (same module) but not run on any
  dataset before the yield above was committed; each was smoke-tested on two real refs.
- **`Link:` is recorded, never fetched.** Even when it points at lore it is usually the
  patch's own submission link.
- **syzbot and bugzilla URLs are taken from any line of the message**, not only from
  `Reported-by:`/`Closes:`: `syzkaller.appspot.com/bug?` and `bugzilla.kernel.org/show_bug.cgi`
  can only be bug pages, so a `Link:` to them is a report. lore URLs are taken from
  `Closes:` only.
- **lore targets whose subject is a `[PATCH ...]` post** are counted as a drop
  (`lore_report: target is a patch`) instead of becoming the problem statement: a
  `Closes:` pointing at a patch submission is not a report. `Re: [PATCH ...]` replies are
  kept: in the first 1,164 cached lore targets 292 were such replies (a reviewer or bot
  reporting a problem against a posted patch) versus 89 bare patch posts. Mail bodies drop `>`-quoted
  lines and everything from a `-- ` signature marker; kernel test robot reports keep
  their build logs.
- **PostgreSQL archive: the flat thread page is the source.** `/message-id/raw/` and
  `postgr.es/m/` redirect non-browser clients to the HTML view, so one request fetches
  `/message-id/flat/<msgid>` and the messages are parsed from its HTML (subject,
  message-id, `message-content` div). The message whose subject starts with `BUG #` wins,
  else the thread's first message. The archive obfuscates addresses (`(at)`, `(dot)`);
  that text is kept as is. `Bug: #N` alone is not fetchable (no number-to-message mapping)
  and stays in `report_refs`.
- **GitLab issue URLs are the QEMU report ref wherever they appear** (`Resolves:`,
  `Fixes:`, `Closes:`, `Buglink:`, `Bug:`); GitLab's `web_url` (which now points at
  `-/work_items/N`) is stored as `report_url`.
- **Bugzilla private bugs** (HTTP 401) are cached as `null` like 404s.
- **Raw text responses are decoded as UTF-8 with replacement** before caching; mail in
  other charsets (rare on lore) may carry replacement characters.
- **syzbot bugs behind a login** (some namespaces redirect `bug?extid=` to a Google sign-in
  page instead of returning JSON) are cached as `null` and counted as
  `syzbot: not found`. The first Linux v2 run lost its syzbot thread to this after 104
  bugs; the cache made the restart free.
- **Report caches are warmed one thread per source** (`extract.warm_caches`) before the
  sequential resolution, so the three Linux hosts are fetched concurrently; this fetches a
  few refs the resolution order would have skipped, which only fills the cache.

## 2026-09-07 — v2 results

| Dataset | Instances | With a report | Sources | Drops (refs) |
|---|---:|---:|---|---|
| linux v2 | 63,115 | 5,424 (8.6%) | syzbot 1,809; lore 3,087; bugzilla 528 | lore: 230 patch posts, 124 not found; syzbot: 4 not found |
| qemu v2 | 2,821 | 677 (24.0%) | gitlab_issue | 8 not found |
| postgres v2 | 1,333 | 1,318 (98.9%) | pgsql_archive | 11 not found |
| llvm v2 | 8,504 | 8,357 (98.3%) | github_issue | 149 pull requests, 1 not found |
| systemd v2 | 1,424 | 1,418 (99.6%) | github_issue | 7 pull requests |
| clickhouse v2 | 1,049 | 1,022 (97.4%) | github_issue | 29 pull requests |

- **Run order.** All six ran in parallel (different hosts and caches); Linux was restarted
  three times from its cache (syzbot login redirect, syzbot pacing, the `Re: [PATCH`
  rule), each restart free. Every output validates with 0 invalid and 0 duplicate ids.
- **Not done.** Launchpad fetcher (6 refs), PR-merge walking, `gold_functions`, masking,
  splits: out of scope as specified. `Bug: #N` without a `Discussion:` URL stays
  unresolved (4 PostgreSQL instances).

## 2026-09-08 — v2.1: report fixes

- **Lore cache holds raw bytes as base64 inside the JSON cache file**, not a sibling
  `.eml`: the base `Source.get` (one `.json` per ref, `null` for 404) stays the only cache
  format. The 0.2.0 cache of decoded strings cannot be reused; it was moved aside to
  `repos/cache/lore_report.v0.2.0-decoded-text` and the 3,853 lore refs were re-fetched at
  the existing 0.5 s pace. syzbot and bugzilla caches untouched.
- **Lore bodies are decoded strictly** (`get_content(errors="strict")`) before the
  UTF-8-with-replacement fallback. With the library default (`errors="replace"`) a
  `UnicodeDecodeError` can never reach the fallback, and an undeclared-charset mail with
  8-bit UTF-8 text would come out as U+FFFD instead of the right characters. The fallback
  is counted as `lore_report: charset fallback` (24 on the Linux v2 run), not as a drop.
- **Signature marker is `-- ` exactly** (dash dash space); a bare `--` no longer ends the
  body. The PostgreSQL archive keeps the trailing space (21,631 `-- <br` occurrences in the
  cached pages), so the rule holds there too.
- **Code is committed before the data it produced**, so `COMMAND.txt` names the extractor
  SHA that actually ran (the v2 runs recorded the previous commit). Each fix is therefore
  two commits: code + tests, then data + docs.
- **v2 is overwritten in place** (never released; no v3); v0 and v1 untouched.
- **PostgreSQL picks the linked message, not the thread root.** A review of the first v2
  run found the root differing from the committer's `Discussion:` link in 1,109 of 1,318
  instances, with 70 roots being `pgsql:` commit notifications (a previous fix's message,
  exactly what v2 exists to exclude). New rule: first `BUG #` message; else first reply to
  a `pgsql:` root; else the linked message itself. The linked message-id matched a page
  message in all 1,221 cached threads, so `linked message not in thread` is a drop reason
  that never fired. The choice is recorded per instance (`report_pick`,
  `report_thread_root_subject`, `report_thread_position`). Function leakage rose from
  25.3% to 36.4% as a consequence; reported, not filtered.
- **Fix 2 and Fix 3 code share one commit.** Fix 3's `report_kind: null` for non-lore
  sources touches every regenerated dataset, so committing it before the PostgreSQL run
  avoided a second PostgreSQL regeneration; the data commits stay separate.
- **`report_kind` is lore-only, rules ordered robot → reply → fresh.** A kernel test robot
  mail whose subject is `Re: [PATCH …]` is `robot`, not `reply`. "kernel test robot" is
  matched case-insensitively in From and the cleaned body, so a human reply naming the
  robot in its own (unquoted) text is `robot` too; the body match is what the task asked
  for, and quoted lines are already gone. syzbot and bugzilla get `null`; no kinds invented.
- **"Shorter than 300 characters" is measured on the final problem statement** (title +
  cleaned body), the text a consumer sees, not on the body alone.
- **Syzbot crash choice unchanged: the bug JSON has no per-crash time field** (all 48,857
  crash entries of the 1,910 cached bugs carry title, kernel config, kernel and syzkaller
  commits, crash-report and reproducer links only). `crashes[0]` stays, nothing was
  re-fetched, `report_crash_time` is not recorded.

## 2026-09-08 — runner format (extractor 0.3.0)

- **`gold_files` renamed to `file_changes`** with the Multi-SWE-bench C/C++ shape
  `[{"file": path}, …]`: same paths, same meaning, one name. v2 only (never released); v0
  and v1 keep `gold_files` and are not touched. The v2 schema already could not read
  v0/v1 files (`commit_message` is required), so no compatibility alias was added;
  `scripts/leakage.py` reads either key.
- **`dataset.jsonl` per v2 directory** is the runner view: only instances with a
  `problem_statement` (a localizer has nothing to run on otherwise; the `null` rows stay
  in `instances*.jsonl`, where yield is measured), every field except `patch`. `patch`
  is dropped because Linux (48.9 MB) and LLVM (68.5 MB) would exceed the 45 MB file
  limit with it and the runner does not read it; without it both are under 41 MB.
- **All six v2 datasets are regenerated** (offline, warm caches) rather than rewritten by
  a conversion script, so `COMMAND.txt` and `STATS.md` describe the files that exist.


## 2026-09-14 — controlled preparation (extractor 0.4.0)

- Dataset branding is `cpp-loc`, intended Hub namespace `jingunhong/cpp-loc`.
  The repository/package name stays stable.
- Enrich full existing extraction populations offline into new v3 companions; preserve
  all v0/v1/v2 bytes. Raw extraction labels/patches are historical. New primary labels
  live in `metadata.integrity.git.primary_files` and eligible five-field exports.
- Pin rename detection off; exact moves appear as A/D and fail strict target-status
  eligibility. Include documented inline/template suffixes in one shared path rule.
- Raw messages/trailers, all statuses, both dates, selected report text/hash and payload
  identity are evidence. Missing old fetch timestamps remain null. Never publish request
  headers/credentials. Missing full-diff blobs prevent exact patch-ID calculation;
  do not substitute a source-only patch or refetch tests automatically.
- Group before eligibility; shared introducing `Fixes:` SHAs alone are not bug groups.
  Use committer time as an explicit availability proxy. This supersedes the historical
  recommendation above to split on `created_at` (author time).
- Unknown bug classification/provenance/version timing belongs in diagnostics. HTML
  archive dates without a timezone remain unknown. Do not infer current GitHub body
  history from issue creation or a post-fix resource update.
- The user explicitly authorized a Hugging Face upload after preparation, then requested
  a privacy/legal review first. Publication is held while concrete contact-data and
  redistribution questions are unresolved. Preserve unmodified research inputs locally;
  do not silently introduce masking or claim legal clearance from a regex scan.

- Real-data follow-up: cache inventory pathspecs in bounded batches after ClickHouse
  branch jumps exceeded the OS argument limit; infrastructure errors remain in baseline
  denominators. Correct feature-area labels in shared `report-evidence-2` rules, then
  reclassify frozen evidence into v3.1 without re-reading Git or rewriting old artifacts.
- Keep new full-text evidence and local release drafts ignored until the requested
  privacy and redistribution review is resolved; this does not change tracked v0-v2.

- Publication draft validation found a Unicode line separator inside one valid QEMU
  JSONL string. Read physical file lines in the shared loader rather than splitting
  every Unicode line boundary; preserve original text and row counts.

## 2026-09-14 — code repository migration

- Copy implementation, tests, configuration, and documentation from the research archive
  at `f40360c9c49ebf128e75fe92fae73da2fc2291d8` onto the existing initial history of
  `jingunhong/cpp-loc`. Keep the archived repository and historical artifacts intact;
  importing its Git history would also import large intermediate datasets.
- Name the Python distribution `cpp-loc` and rename the import package to `cpp_loc`,
  updating scripts, tests, and implementation provenance paths together. Historical
  manifests retain the old package paths. Point future generated dataset cards
  at the new code repository.
- Ignore local corpora, clones/caches, release drafts, and dataset shard formats;
  reduce the existing large-file hook limit to 1 MiB. Inputs can be read from the
  local research archive using explicit paths. No dataset is regenerated by migration,
  and existing manifests retain their original implementation revisions and hashes.
- GitHub code delivery can proceed independently of the dataset's unresolved privacy
  and redistribution review. Hugging Face was an empty private placeholder at
  migration time; the later [delivery report](06-six-source-validation.md#private-review-delivery)
  records the uploaded private snapshot.

## 2026-09-14 — six-source preparation and private review storage

- Extend full offline enrichment, grouping, temporal validation, and the report-only
  baseline to the existing Linux, systemd, PostgreSQL, and QEMU populations. Preserve
  older report-only annotations and all v0/v1/v2 artifacts. Use new `v3.1`, `splits-v2`,
  `diagnostic-v2`, and `baseline-v1` directories for these four sources.
- Keep LLVM as the adaptation source. Freeze the other four sources as evaluation-only
  candidates before measuring their baselines, using the same UTC boundaries and
  explicit test end `2026-09-09T00:00:00Z`. Do not manufacture train/dev sets or relax
  chronology when a source has insufficient evidence.
- The user authorized private Hugging Face storage while deferring the remaining
  public-release privacy/IP review. Prepare a separate runner-only private review copy;
  retain raw messages, mail, patches, caches, and full evidence locally. Apply the
  existing phone/credential patterns to every serialized runner field, withholding
  matching rows with recorded IDs/reasons instead of editing frozen text. Retain source
  links and hashes. This screen can have false positives and does not certify anonymity
  or redistribution rights; private visibility must be checked before and after upload.
- Linux's 63,115-row enrichment exposed process-launch overhead from a large threaded
  Python process. Add optional `--processes` with bounded 250-row tasks and local
  worker caches; merge all evidence before grouping. The thread backend remains
  available with a bounded queue. A fixture verifies byte-identical evidence/manifests,
  cached payload accounting, cache misses, and pinned-upstream exclusions across both
  backends. No eligibility rules or historical rows change.
- Private-export verification exposed JSON escaping hiding double-quoted credential
  examples from a serialized-text scan. `publication-screen-2` recursively scans
  decoded string values, including nested file labels and companion evidence. The
  export regression now checks that double-quoted credentials are withheld too.
- Hub card validation requires an HTTPS `license_link`; relative README anchors
  were rejected before upload. Both package exporters now emit absolute HTTPS
  review links, with a regression assertion in the existing private-export check.
  Preserve the first private attempt locally and regenerate a new private v2 copy
  from the same research bundle. No runner rows or source evidence change.

## 2026-09-15 — private archive documentation

- The owner made the historical data repository private; verify that visibility
  while keeping the code-only `jingunhong/cpp-loc` repository public.
- Remove inaccessible repository links and hardcoded sibling-checkout paths from
  public documentation. Use `CPP_LOC_ARCHIVE` for local replay examples and state
  that the raw evidence and pre-migration revisions require authorized archive access.
  Preserve recorded hashes, measured results, and frozen artifacts.

## 2026-09-15 — additional adaptation configurations

- Assess the five existing non-LLVM populations using frozen v3.1 evidence and the
  existing temporal/group rules. Preserve primary refusals; attempt the requested
  dev=50/minimum-train=100 diagnostic alternative only where primary dev=300 fails.
  Results and training paths are in [07](07-repository-adaptation.md).
- Preserve all existing evaluation views and prepare additive local HF configurations.
  Keep canonical local splits intact; the existing storage screen withholds one Linux
  and one PostgreSQL training row. Record those storage subsets separately, enforce
  minimum training counts, and refuse any adaptation dev/test loss. The initial
  preparation performed no upload or visibility change.
- On the user's follow-up push authorization, push the implementation/documentation
  to GitHub main and upload the reviewed additive package to the existing private HF
  repository. Verify remote content identities, preserved configuration definitions,
  authenticated loading of all five new views, and unchanged private visibility.
