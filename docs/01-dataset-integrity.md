# 01 — Dataset integrity (extractor 0.4.0)

`cpp-loc` prepares file-level localization data from original reports and pre-fix
source trees. Raw extraction, eligibility, and model observations are different
artifacts. No training, repair harness, function labels, or runtime sandbox is provided.

## Preserved evidence

v0/v1/v2 are historical, immutable inputs. `scripts/prepare.py enrich` reads the
complete v2 `instances*.jsonl` population, including null reports, without mining
additional history. New `data/<repo>/v3/records-*.jsonl` retains every original field
and adds `metadata.integrity`. Historical `file_changes` and `patch` remain the
original projection; **new primary labels are `metadata.integrity.git.primary_files`**.
Only the latter enters new eligible five-field exports. Enrichment cannot recover
commits already excluded by the narrower historical v2 path/mining filters.

Evidence includes complete NUL-delimited name-status changes, raw fixing messages,
ordered duplicate trailers and continuation lines, removed lines, both Git dates,
full base/fix SHAs, the input's pinned upstream revision, and exact full-diff stable
patch IDs when all required blobs are available. The explicit rename policy is
`--no-renames`: moves appear as an addition plus a deletion. This avoids heuristic
rename pairing and excludes moved targets from the strict subset. All changes,
including tests and build/generated inputs, remain visible.

`created_at` retains its historical author-date meaning. New splits use
`committer_at`, an availability proxy, not proof of the first integration on the
upstream target branch. The pinned upstream reachability and single-parent base
relationship are checked separately. Missing Git objects produce explicit errors.
Missing optional full-diff blobs are recorded without substituting the old gold-only
patch for a full stable patch ID. Git transport is disabled in offline operations.

## Primary path rule: cpp-paths-1

Case-insensitive extensions: `.c .h .cc .cpp .cxx .hh .hpp .hxx .inc .inl .ipp .tpp .tcc`.
The last five are inline/template fragments. This is an extension heuristic, not a
content classifier; ambiguous `.def` files are excluded. Exclude directory components
`test`, `tests`, `testing`, `selftests`, `unittest`, `unittests`, and filenames with a
`test`/`tests` token bounded by start/end, underscore, dot, or dash. Build/config files,
`.td`, `.dts`, and unrelated languages are outside primary scope.

Validate normalized, unique, repository-relative paths and base-tree regular-file
existence. Symlinks and gitlinks do not count as implementation files. Any target
addition, deletion, rename/copy, type change, or other non-`M` status excludes the
instance; do not remove just that target and treat the remaining labels as complete.
Apply the 1–5 rule after projection. An added regression test does not exclude a
source modification. `all_non_test_changes_in_scope` measures the narrower sensitivity
subset and its loss; it is not a universal eligibility gate. This gold is neither all
changed files nor complete causal gold.

## Tasks and report provenance: report-evidence-1 / report-evidence-2

Preserve source labels/type and positive evidence for `bug`, `feature`, `other`, or
`unknown`. Closing keywords are candidate signals. Explicit issue type/labels and
defect terms in titles or the PostgreSQL bug form support conservative heuristic
classification. Conflicting bug/feature signals remain unknown. Unknown tasks are
provisional diagnostics, never verified bugs. The final LLVM/ClickHouse v3.1
annotations use report-evidence-2 to distinguish feature-task labels from experimental
feature-area labels; original payload/chronology evidence retains its producing rule.

Keep existing lore `fresh/robot/reply` annotations. Additional annotations distinguish
explicit bug reports, ordinary messages, replies, patch submissions, automated
diagnostics, and unknowns. A PostgreSQL `BUG #` subject supports task classification,
not chronology or independent provenance verification. Patch/commit replies remain
unresolved. No rule certifies all `fresh`, syzbot, or Bugzilla cases automatically.

Exact selected message/crash identity, selection rule, raw versus cleaned text,
SHA-256 hashes, payload path/hash, and available timestamps are retained. Quote/signature
stripping never destroys the raw companion text. Existing syzbot `crashes[0]` selection
is preserved; aggregate `first-crash` is not the selected crash time. Its current title
also needs version evidence. PostgreSQL HTML dates without a timezone are preserved as
unknown chronology, not assumed UTC.

Creation and exact consumed text availability are independent checks. Explicit mail
Date headers substantiate an immutable message timestamp (subject to sender-clock
limitations). Cached resource last-update timestamps preceding the fix or exact
payloads actually fetched before the fix support pre-fix availability. A resource
updated after the fix is only a review signal: comments/state changes may have caused
it. No body edit history is invented. Post-fix creation excludes; unresolved version
availability remains unknown. Strict eligibility requires both checks supported and
compatible bug-report provenance. Historical GitHub body reconstruction is deferred.

## Cache and replay

`--offline` is mandatory for preparation. A miss is counted, never fetched. New online
extraction fetches save actual UTC fetch time and payload hash in `.fetch.json` sidecars;
legacy caches retain unknown fetch time. No filesystem mtime is used. No request
headers or credentials are exported.

`snapshot.json` pins implementation revision/file hashes, input shard/command hashes,
source revision, configuration and rules. `payloads-*.jsonl` lists every consumed
payload, including alternate issue references, known PRs and cached missing results.
Replay needs those exact cache bytes and any listed fetch sidecars, original input
shards/COMMAND, pinned commit/tree objects, and the same availability of full-diff blobs
(recorded missing blobs must remain unavailable to reproduce optional patch-ID checks).
Retain this minimal payload bundle locally; a hash cannot recreate missing content.
The whole cache is never copied into a publication bundle. Outputs are hashed in the
manifest; a new/empty output directory is required. The implementation must be committed
before generation. Worker count affects throughput, not output bytes.

See [split and runner rules](02-splits-and-provenance.md),
[validation report](03-validation-report.md), and [decision history](decisions.md).
