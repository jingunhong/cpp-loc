# LLVM extraction (v0, v1, v2)

Upstream: `llvm/llvm-project`, blob-less clone at `repos/llvm`. Candidates are non-merge,
non-revert commits whose message references an issue of `llvm/llvm-project` with
`Fixes/Closes/Resolves #N`, the full issue URL, or `llvm/llvm-project#N` (references to other
repositories such as `clangd/clangd` are ignored). The problem statement is the issue title
plus body from the GitHub REST API (`problem_source = "github_issue"`); everything else
follows the Linux pipeline: `base_commit` is the first parent, `created_at` the author
date, `file_changes` the changed non-test C/C++ sources, `gold_functions` `null`.

## Range

- **v0**: `--since 2025-01-01`, chosen to keep the first API pass around an hour.
- **v1**: `--since 2024-01-01`, sharded output, plus `metadata.leakage` flags. Same upstream
  HEAD as v0. Earlier LLVM commits mostly reference Bugzilla, which the pipeline does not read.

Upstream HEAD and the exact command are in `data/llvm/<ver>/COMMAND.txt`.

## GitHub API

- Endpoint `GET /repos/llvm/llvm-project/issues/{n}`; the same endpoint also returns pull
  requests (with a `pull_request` key), which are skipped. The first referenced number that
  is a real issue wins; a commit whose references are all PRs or deleted is dropped and
  counted under `problem statement drops` in `STATS.md`.
- Responses are cached verbatim under `repos/cache/llvm__llvm-project/<n>.json` (`null` for
  404), so a re-run with the same clone and cache is offline and deterministic.
- The run used a token from `GITHUB_TOKEN` (5,000 requests/hour). Unauthenticated runs are
  supported but pause one second per request and sleep through quota exhaustion.

## Results

**v1** (`data/llvm/v1/STATS.md`): 110,841 candidates → 106,646 non-revert → 8,632 with an
`llvm/llvm-project` issue reference → 8,357 instances after the gold-file gates and issue
lookup (149 commits referenced only pull requests, 1 a deleted issue). All 8,357 validate;
two shards, 45.0 MB + 17.7 MB. Leakage over the full set: path 14.8%, basename 23.2%,
patched function 19.0%.

**v0** funnel (`data/llvm/v0/STATS.md`): 73,215 candidates → 70,835 non-revert (LLVM has no merge
commits) → 6,920 with an `llvm/llvm-project` issue reference → 6,253 with gold files →
5,831 with 1–5 gold files → **5,794 instances** with a problem statement (38 commits
referenced only pull requests; no referenced issue was missing). `scripts/validate.py`:
5,794 valid, 0 invalid, 0 duplicate ids. `instances.jsonl` is 44.0 MB; 5,693 API responses
are cached. Gold files by top-level project: llvm 3,253, clang 2,956, flang 592, mlir 560,
libc 374, clang-tools-extra 356, libcxx 274, lldb 160. Median problem statement length is
1,452 characters; the shortest is 21 (a title-only issue).

## Leakage note

`uv run python scripts/leakage.py data/llvm/v0/instances.jsonl --n 20 --seed 0`:

| Named verbatim in the problem statement | Instances (of 20) |
|---|---:|
| full gold file path | 1 |
| gold file basename | 6 |
| function name from the patch | 4 |

Issue reports leak less than kernel commit messages at the function level but more at the
file level: crash reports and reproducers often quote a basename from an assertion message
or a stack trace (`SemaExpr.cpp:1234`). Nothing is scrubbed in v0.

## v2: schema only

`data/llvm/v2/` re-runs the v1 range over the same clone, HEAD and API cache (offline)
with the v2 schema: `commit_message` (trailers stripped) is a separate field,
`metadata.commit_message_leakage` is computed against it, and commits whose references
are all pull requests or deleted issues are **kept** with `problem_statement: null`
instead of being dropped at a `has problem statement` stage.

### Reports

| | Instances |
|---|---:|
| with a GitHub issue ref | 8,504 (100%) |
| resolved to an issue (`github_issue`) | 8,357 |
| with `problem_statement: null` | 147 (1.7%; 149 refs were pull requests, 1 a deleted issue) |

Leakage: `problem_statement` (8,357 instances) path 14.8%, basename 23.2%, patched function 19.0%, unchanged from v1;
`commit_message` (8,504) path 1.2%, basename 3.6%, function 18.2%.

All 8,504 validate; two shards, 45.0 MB + 24.1 MB. Same cache as v1, moved to
`repos/cache/github_issue/<owner__repo>/`.
