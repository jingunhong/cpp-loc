# systemd extraction (v0, v2)

Upstream: `systemd/systemd`, blob-less clone at `repos/systemd`. Same pipeline as LLVM:
candidates are non-merge, non-revert commits referencing a `systemd/systemd` issue
(`Fixes #N`, `Closes #N`, `Resolves <issue url>`...); the problem statement is the issue
title and body from the GitHub API (`problem_source = "github_issue"`), cached under
`repos/cache/systemd__systemd/`.

## Results (`--since 2022-01-01`, `data/systemd/v0/STATS.md`)

36,174 candidates → 31,169 non-merge → 30,936 non-revert → 2,055 with an issue reference →
1,498 with gold files → 1,424 with 1–5 gold files → **1,418 instances** (7 commits
referenced only pull requests). All validate; one 10.9 MB file. Leakage over the full set:
path 19.9%, basename 22.1%, patched function 15.9%.

## Caveats

- Most systemd fixes arrive through pull requests whose merge commit, not the individual
  commit, names the issue; only 6% of non-merge commits carry a reference. A "take the PR's
  commits when the merge commit references an issue" rule would enlarge this set several
  times over and is the main gap for this repository (and for Godot, DuckDB, ClickHouse).
- systemd issue bodies follow a template (version, distribution, expected/actual behaviour,
  log excerpts); file-path leakage is the highest of the repositories so far because logs
  and backtraces name source files.

## v2: schema only

`data/systemd/v2/` re-runs the v0 range over the same clone, HEAD and API cache (offline)
with the v2 schema: `commit_message` (trailers stripped) is a separate field,
`metadata.commit_message_leakage` is computed against it, and commits whose references
are all pull requests or deleted issues are **kept** with `problem_statement: null`
instead of being dropped at a `has problem statement` stage.

### Reports

| | Instances |
|---|---:|
| with a GitHub issue ref | 1,424 (100%) |
| resolved to an issue (`github_issue`) | 1,418 |
| with `problem_statement: null` | 6 (0.4%; 7 refs were pull requests) |

Leakage: `problem_statement` (1,418 instances) path 19.9%, basename 22.1%, patched function 15.9%, unchanged from v0;
`commit_message` (1,424) path 1.0%, basename 1.7%, function 12.6%.

All 1,424 validate; one 11.3 MB file. Same cache as v0, moved to
`repos/cache/github_issue/<owner__repo>/`.
