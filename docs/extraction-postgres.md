# PostgreSQL extraction (v0, v2)

Upstream: `postgres/postgres` (GitHub mirror of git.postgresql.org), blob-less clone at
`repos/postgres`, walking `master` only, so back-patched copies of a fix on release branches
never appear. Candidates are non-revert commits carrying a `Reported-by:` or `Bug: #N`
trailer, the project's conventions for fixes of reported problems. The problem statement is
the commit message with trailers stripped (`problem_source = "commit_message"`);
PostgreSQL adds `Discussion:`, `Backpatch-through:`, `Author:` and `Security:` to the usual
keys. `metadata.references` holds the bug numbers (`#18123`) and the `Discussion:` mailing
list archive URLs, which point at the original report.

## Results (`--since 2022-01-01`, `data/postgres/v0/STATS.md`)

12,540 candidates (no merge commits) → 12,377 non-revert → 2,069 with a report trailer →
1,395 with gold files → **1,333 instances** (1–5 gold files). All validate; one 5.7 MB file.
Leakage over the full set: path 0.2%, basename 8.8%, patched function 36.2%.

## Caveats

- `Reported-by:` is also used for reported shortcomings that are not defects (a sampled
  instance adjusts query jumbling for a new command). The 143 commits with an explicit
  `Bug: #N` number are the strict subset; filter on `metadata.references` starting with `#`.
- PostgreSQL commit messages describe the fix as much as the problem, so leakage of the
  patched function name is high (36%), comparable to Linux.
- Bug report bodies from the `pgsql-bugs` archive are not fetched in v0; v2 does.

## v2: mailing-list reports as problem statements

`data/postgres/v2/` (same clone, HEAD, range and funnel as v0: 1,333 instances). The
`Discussion:` URL of each commit is resolved through the archive's flat thread view
(`https://www.postgresql.org/message-id/flat/<msgid>`; the raw-message endpoint and
`postgr.es/m/` redirect non-browser clients to HTML, so the page is parsed). One message
of the flat thread is the report, chosen by three rules in order (extractor 0.2.1):

1. the first message whose subject starts with `BUG #` (`report_pick = "bug_subject"`);
2. else, if the thread root's subject starts with `pgsql:` (a pgsql-committers commit
   notification, i.e. a previous fix's message), its first reply (`"committers_reply"`);
   a notification without a reply is a drop (`pgsql_archive: committers thread without
   reply`);
3. else the message the `Discussion:` URL points at (`"linked_message"`), not the thread
   root: the committer chose that link, and it is the report far more often than the
   root is.

`problem_statement` = subject + body with `>`-quoted lines and the `-- ` signature removed
(`problem_source = "pgsql_archive"`); `metadata.report_url` is the chosen message,
`metadata.report_pick` the rule that chose it, `metadata.report_thread_root_subject` the
root's subject and `metadata.report_thread_position` the chosen message's 0-based index in
the flat thread, so the choice is auditable offline. The commit message moved to
`commit_message`.

### Reports

| | Instances |
|---|---:|
| with a `Discussion:` archive URL | 1,329 (99.7%) |
| resolved to a message | 1,318 |
| `pgsql_archive: not found` (404 on the archive) | 11 refs |
| with `problem_statement: null` | 15 (1.1%) |
| `report_pick = "bug_subject"` (subject starts with `BUG #`) | 210 |
| `report_pick = "committers_reply"` | 70 |
| `report_pick = "linked_message"` | 1,038 |
| thread root is a `pgsql:` commit notification | 70 (all had a reply; 0 dropped) |
| chosen message is the thread root (`report_thread_position = 0`) | 785 |
| `Bug: #N` trailer (recorded in `report_refs.pgsql_bug`) | 135 |

The first v2 run took the thread root whenever no `BUG #` message existed; the rules
above changed the chosen message for 533 of the 1,318 instances (463 to the linked
message, 70 to the committers reply). Reports shorter than 300 characters: 48.

Leakage: `problem_statement` (1,318) path 13.7%, basename 32.8%, patched function 36.4%
(was 13.4% / 27.2% / 25.3% with the thread root); `commit_message` (1,333) path 0.2%,
basename 8.8%, function 36.2%. The linked message sits later in the thread and nearer the
diagnosis than the root, so it names the patched function about as often as the commit
message does; the flags are there to stratify on. Report length: median 1,324
characters (root rule: 1,828), longest 134k.

Caveats: the linked message in a `pgsql-hackers` thread can still be a design discussion
or a review comment rather than a bug report (`Reported-by:` marks both); the `BUG #`
subset is the strict one. The archive obfuscates addresses (`name(at)host(dot)org`) and
that text is kept as is. All 1,333 validate; one file.
