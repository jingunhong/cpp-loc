# CLAUDE.md

* Python 3.14, managed with uv. Write modern Python: built-in generics (`list[str]`, `X | None`), no `typing` imports or compatibility shims for older versions.
* Lint, format, and run tests before every commit. The pre-commit hooks enforce this; do not bypass or weaken them.
* Commit directly to main; no branches, PRs, or CI. When a decision is needed and no one is available, take the conservative option, note it in `docs/decisions.md`, and continue.
* This repository holds dataset tooling: never fabricate or hand-edit data. A dropped instance is better than a wrong label; count every drop in the stats.
* Keep dataset artifacts, upstream clones/caches, and release drafts outside Git. Use the ignored `data/`, `repos/`, and `releases/` directories or explicit external paths.
