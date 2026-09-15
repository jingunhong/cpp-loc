# cpp-loc

Tools for file-level code localization in C/C++: turn linked reports and pre-fix
source trees into auditable candidate datasets, grouped temporal splits, and
report-only path baselines.

This GitHub repository contains the implementation, tests, configuration, and
documentation. Corpora, intermediate results, upstream clones, API caches, and
release drafts belong in local storage. The dataset destination is
[`jingunhong/cpp-loc` on Hugging Face](https://huggingface.co/datasets/jingunhong/cpp-loc);
access is restricted to private review. Public release remains held for the
[privacy and redistribution review](docs/04-publication-review.md).

## Setup

Requires Python 3.14 and uv.

```sh
uv sync --locked
uv run pre-commit install
uv run pytest
```

The Python distribution is named `cpp-loc`; import its package as `cpp_loc`.
No trainer, repair harness, or runtime sandbox is included.

## Use the existing local corpus

Historical corpora, raw evidence, and pre-migration implementation revisions are
retained in a private research archive. They are not included in this GitHub
repository or publicly downloadable. Replaying the recorded runs requires authorized
access to those inputs; the private dataset export omits the full raw evidence.

With an authorized local copy containing `data/`, `repos/`, and `releases/`, set its
location and validate the frozen LLVM diagnostic export:

```sh
CPP_LOC_ARCHIVE=/path/to/local/research-archive
uv run python scripts/validate.py --runner --exact \
  "$CPP_LOC_ARCHIVE"/data/llvm/diagnostic-v2/{train,dev,test}-*.jsonl
```

Prepare a new local diagnostic split from the same archive:

```sh
uv run python scripts/prepare.py split \
  --input "$CPP_LOC_ARCHIVE/data/llvm/v3.1" \
  --out data/llvm/pilot-diagnostic-v1 \
  --view diagnostic --role adaptation-candidate \
  --test-end 2026-09-09T00:00:00Z
```

For enrichment or a baseline audit, `--repos-dir "$CPP_LOC_ARCHIVE/repos"` reuses
the existing clones and caches; `--input` selects the existing corpus. The default
`data/`, `repos/`, and `releases/` directories are ignored by Git, as are JSONL,
Parquet, Arrow, and Git bundle files. The pre-commit large-file check limits newly
added files to 1 MiB. Commit implementation changes before generating artifacts;
preparation records the producing revision and refuses to overwrite outputs.

## Measured candidate status

These are frozen **provisional diagnostic** instances, not distinct bugs or a
temporally verified benchmark. The complete historical report-backed corpus has
18,216 instances across six repositories.

| Repository | Historical reports | Diagnostic train | Dev | Test |
|---|---:|---:|---:|---:|
| LLVM | 8,357 | 5,330 | 300 | 1,059 |
| ClickHouse | 1,022 | — | — | 397 |
| Linux | 5,424 | — | — | 382 |
| systemd | 1,418 | — | — | 73 |
| PostgreSQL | 1,318 | — | — | 171 |
| QEMU | 677 | — | — | 20 |

Linux also yields **105 strict-rule future test candidates**; the other repositories
have empty strict future tests (LLVM refuses its strict adaptation configuration).
These remain rule-based candidates requiring source review, not a certified benchmark.
Baseline results, exclusions, and reproducibility checks for all six are in the
[six-source report](docs/06-six-source-validation.md). Unknown chronology is never
relaxed to obtain a split.

The private storage copy withholds five flagged historical rows, retaining 18,211
unique report-backed instances. None of those five appears in the diagnostic or
strict splits above.
The historical and diagnostic views overlap and must not be summed as distinct bugs.

Additional versioned adaptation splits are now prepared locally: Linux, PostgreSQL,
and systemd support the primary 300-row dev configuration; QEMU supports an explicit
50-row dev pilot. ClickHouse remains evaluation-only with just 127 eligible historical
pool records. Linux also supports strict adaptation candidates. Frozen LLVM and all
existing tests are unchanged. See [measured yields, artifact paths, and training
commands](docs/07-repository-adaptation.md). The additive HF package is local;
these new configurations have not been uploaded.

- [Integrity and evidence rules](docs/01-dataset-integrity.md)
- [Grouping, temporal splits, and runner handoff](docs/02-splits-and-provenance.md)
- [Measured validation and exclusion counts](docs/03-validation-report.md)
- [Full six-source follow-up and private review export](docs/06-six-source-validation.md)
- [Additional repository adaptations and training handoff](docs/07-repository-adaptation.md)
- [Publication review and remaining work](docs/04-publication-review.md)
- [Agent review of seeded source samples](docs/05-agent-audit.md)
- [Decision and migration history](docs/decisions.md)

The historical documents' `data/`, `repos/`, and `releases/` paths are relative to
that private archive, not files tracked here. Pre-migration commit IDs identify
archived provenance and may not resolve in this repository's Git history. Existing
manifests retain their original hashes and revisions.

## License

The implementation is [MIT-licensed](LICENSE). That license does not relicense
upstream report text, mail, patches, or code snippets. Dataset redistribution terms,
required notices, and privacy treatment require a separate review. Private hosting
does not itself resolve those obligations.
