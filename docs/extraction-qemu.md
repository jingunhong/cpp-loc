# QEMU extraction (v0, v2)

Upstream: `qemu/qemu` (GitHub mirror of gitlab.com/qemu-project/qemu), blob-less clone at
`repos/qemu`. QEMU follows the kernel's `Fixes: <sha> ("subject")` convention, so the
pipeline is the Linux one unchanged: candidates are non-merge, non-revert commits with a
`Fixes:` trailer; problem statement is the commit message with trailers stripped
(`problem_source = "commit_message"`); `metadata.references` holds the referenced SHA
prefixes. QEMU also uses `Resolves: <gitlab issue url>` lines; those are stripped as
trailers and not used as a candidate signal in v0.

## Results (`--since 2022-01-01`, `data/qemu/v0/STATS.md`)

40,309 candidates → 38,021 non-merge → 37,840 non-revert → 2,889 with a `Fixes:` trailer →
2,383 with gold files → **2,367 instances** (1–5 gold files). All validate; one 6.4 MB
file. Leakage over the full set: path 8.8%, basename 11.0%, patched function 31.6%.

## Caveats

- Only 7% of QEMU commits carry `Fixes:`; many fixes reference a GitLab issue instead
  (`Resolves: https://gitlab.com/qemu-project/qemu/-/issues/N`). Reading GitLab issues
  would roughly double the candidate pool and is the obvious next step for this repository.

## v2: GitLab issues as problem statements

`data/qemu/v2/` (same clone and HEAD as v0, `--since 2022-01-01`). Two changes:

- **`gitlab.com/qemu-project/qemu/-/issues/N` URLs are a candidate signal** alongside
  `Fixes: <sha>`, wherever they appear (`Resolves:`, `Fixes:`, `Closes:`, `Buglink:`, `Bug:`).
  Funnel: 40,309 candidates → 38,021 non-merge → 37,840 non-revert → **3,503** with a
  reference (v0: 2,889) → 2,856 with gold files → **2,821 instances** (v0: 2,367).
- **`problem_statement` is the GitLab issue** (title + description from the public API v4,
  `problem_source = "gitlab_issue"`, cached under `repos/cache/gitlab_issue/`); the commit
  message moved to `commit_message`.

### Reports

| | Instances |
|---|---:|
| with a GitLab issue ref | 683 (24.2%) |
| resolved to an issue | 677 |
| `gitlab_issue: not found` (404, deleted or confidential) | 8 refs |
| with `problem_statement: null` | 2,144 (76.0%) |
| Launchpad `Buglink:` (recorded only, no fetcher) | 6 |
| `Link:` (recorded only) | 294 |

Leakage: `problem_statement` (677 instances) path 40.0%, basename 43.9%, patched function
26.4%; `commit_message` (2,821) path 8.7%, basename 11.0%, function 30.7%. Issue reports
follow a template with a backtrace or reproduction command, hence the high path leakage;
the commit message still names the patched function more often.

All 2,821 validate; one 11.0 MB file.
