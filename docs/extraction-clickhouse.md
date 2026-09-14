# ClickHouse extraction (v0, v2)

Upstream: `ClickHouse/ClickHouse`, blob-less clone at `repos/clickhouse` (6.7 GB even
without blobs: 200k commits over a large tree). Same pipeline as LLVM: candidates are
non-merge, non-revert commits referencing a `ClickHouse/ClickHouse` issue; the problem
statement is the issue title and body from the GitHub API (`problem_source =
"github_issue"`), cached under `repos/cache/ClickHouse__ClickHouse/`.

## Results (`--since 2022-01-01`, `data/clickhouse/v0/STATS.md`)

198,025 candidates → 132,696 non-merge → 130,560 non-revert → 1,497 with an issue
reference → 1,120 with gold files → 1,049 with 1–5 gold files → **1,022 instances**
(29 commits referenced only pull requests). All validate; one 9.6 MB file. Leakage over
the full set: path 39.0%, basename 42.2%, patched function 27.6%.

## Caveats

- Only 1% of ClickHouse commits reference an issue directly; the link normally sits in the
  pull request body and its merge commit (22k merge subjects since 2024 carry a PR number).
  Walking PR merges is the missing rule, as for systemd, Godot and DuckDB.
- Issue bodies often paste a full stack trace or a fuzzer report naming the source file
  and function, hence the highest path leakage of all repositories (39%).

## v2: schema only

`data/clickhouse/v2/` re-runs the v0 range over the same clone, HEAD and API cache (offline)
with the v2 schema: `commit_message` (trailers stripped) is a separate field,
`metadata.commit_message_leakage` is computed against it, and commits whose references
are all pull requests or deleted issues are **kept** with `problem_statement: null`
instead of being dropped at a `has problem statement` stage.

### Reports

| | Instances |
|---|---:|
| with a GitHub issue ref | 1,049 (100%) |
| resolved to an issue (`github_issue`) | 1,022 |
| with `problem_statement: null` | 27 (2.6%; 29 refs were pull requests) |

Leakage: `problem_statement` (1,022 instances) path 39.0%, basename 42.2%, patched function 27.6%, unchanged from v0;
`commit_message` (1,049) path 2.2%, basename 6.0%, function 42.0%.

All 1,049 validate; one 11.8 MB file. Same cache as v0, moved to
`repos/cache/github_issue/<owner__repo>/`.
