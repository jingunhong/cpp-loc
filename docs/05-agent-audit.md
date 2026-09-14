# 05 — Seeded source review

Reviewer: **agent**, 2026-09-14. No human validation was performed. Seed:
`cpp-loc-v3-2026-09-14`. The sampler chooses one example per relevant stratum and
deduplicates selections; this is targeted coverage, not an unbiased prevalence sample.
“Normal report” is a random report-backed case, not a promise of strict eligibility.

Reviewed all 20 LLVM and 18 final ClickHouse samples, plus one superseded ClickHouse
selection. For every reviewed case, the locally cached selected payload SHA-256,
parser output against the frozen problem statement, and raw-text hash matched.
Checks are retained locally in `releases/{llvm,clickhouse}-sample-payload-checks.json`;
source identity, payload path/hash, full changes and chronology are in the versioned
audit samples. Judgments below are separate from dataset rows. No reproducer was run.

Except for the explicitly noted locally strict examples, consumed GitHub text-version
availability remains unknown. Post-fix resource updates do not establish body edits.
These reviews establish the stated evidence/limitations, not bug causality or legal clearance.

## LLVM

| Instance | Inspected evidence and agent judgment |
|---|---|
| `llvm__01a15dca09e5` | RVV spilling reproducer; new vector-mask mutation source plus build changes. Missing-base/status exclusion is correct. Performance issue remains task-unknown. |
| `llvm__1a9521565019` | DirectX Int64Ops implementation acceptance criteria. Looks like development work; unknown is appropriate and must not become a verified bug. Added test is allowed. |
| `llvm__1bb2328fd3ad` | Standard-library proposal link, added join-with header, multiple reports. Status and ambiguity exclusions are warranted. |
| `llvm__20675ee67d04` | SLP assertion reproducer, bug/crash metadata, one modified implementation, resource update before fix. Locally strict but shared group excludes strict one-to-one use. |
| `llvm__2ca085505996` | Expected/actual clang-format example and Bug type. Implementation changes plus unit tests; test paths stay outside gold. Version and extra references unresolved. |
| `llvm__4bab0387e9be` | HLSL layout-compatibility capability request, source changes plus a `.def` input. Unknown task and narrower-scope sensitivity are necessary. |
| `llvm__4fabe6ffae88` | ARM64EC coroutine linker-error reproducer. Bug-like content lacks approved task evidence; unknown is a heuristic false negative. Embedded Microsoft copyright/SPDX notices demonstrate third-party content inside reports. |
| `llvm__614b860af084` | Constraint-recursion reproducer and diagnostics. Bug-like, but conservatively unknown; release notes outside primary scope. |
| `llvm__61571e9046fa` | Formatting reproducer, multiple resolved issue references. Cannot assign one issue the entire change without ambiguity. |
| `llvm__7068b522545e` | Header-only math refactoring request adds implementation headers and changes build files. Unsupported target additions correctly exclude. |
| `llvm__778b6a21ec27` | DirectX vector-allocation omission, Bug type, explicit source URL. Suitable diagnostic; current body version is unverified. |
| `llvm__9604bdf11809` | CTAD compiler disagreement, question label and language-rule uncertainty. Label-based other exclusion is conservative; it is not proof that no compiler defect exists. |
| `llvm__a9a5a18a0e99` | HLSL sign implementation checklist names source locations. Shared report and `.td` changes remain visible; this is not verified bug-fix gold. |
| `llvm__ac0a880f4eef` | Nonportable clang-tidy suggestion, enhancement label. Feature classification follows source metadata but content is defect-like: a documented heuristic limitation needing broader task review. |
| `llvm__b577438a8793` | Doxygen descriptions inconsistent with behavior, documentation label. Other exclusion is appropriate despite a header-only patch. |
| `llvm__dd46a521607e` | AArch64 dead-stack-frame example and explicit fixing-message assistance marker. Marker supports observed assistance only; optimization task remains unknown. |
| `llvm__def50f701f6a` | Standard flat-map proposal, new headers and more than five projected files. All relevant exclusion reasons are retained. |
| `llvm__eac7a7346250` | MIPS relocation reproducer and Bug type; one modified parser plus added regression test. Diagnostic valid under the chosen structural rules; chronology/references unresolved. |
| `llvm__f2650c54c9a6` | Shader-flag implementation criteria and previous changeset link. Unknown task/provenance is appropriate for strict exclusion. |
| `llvm__f65341ccfd3f` | Proposed AMDGPU comparison optimization and Feature type. Excluded from bug-fix subset; not reclassified based on convenience. |

## ClickHouse

| Instance | Inspected evidence and agent judgment |
|---|---|
| `clickhouse__1498d6f45dd2` | Empty-table backup reproducer and bug label; one modified backup source plus added tests. Structural diagnostic passes; version unknown. |
| `clickhouse__246614229fb2` | ArrowStream slowdown, new wait-for-process source/header. Target-addition exclusion is correct. |
| `clickhouse__270afe7aed37` | Log-pointer logical error, bug/fuzz labels, modified sources and tests. Diagnostic retained; not a temporally verified report body. |
| `clickhouse__4366f7fb3b02` | Memory-preallocation failure described without approved task cues. Unknown is conservative and may miss real defects. |
| `clickhouse__555f912fd8a4` | Deprecation guard mismatch; report explicitly mentions automated ClickGap review. Extra reference remains unresolved. Report-generation evidence is distinct from fixing-message assistance. |
| `clickhouse__60c45d67d386` | MySQL dictionary-freeze regression and bug labels, source modification plus tests. Diagnostic retained. |
| `clickhouse__8c94832c2041` | Logical error in an experimental join feature. Initial rule mistook area label “experimental feature” for a task type. Shared rule corrected; v3.1 preserves the row as unknown, not a verified bug. This was the superseded task-feature sample. |
| `clickhouse__9cfb2abdb953` | Fuzzer report with pre-fix resource-update evidence and modified Aggregator source. Locally strict, but fix lies in the buffer and cannot enter future test. |
| `clickhouse__a4e6ca94ce30` | Logical error from repeated input function; shared report group. Group restrictions are necessary. |
| `clickhouse__b2f68b66f751` | MaterializedPostgreSQL schema behavior, experimental-feature area label. Same global rule correction prevents unsupported feature-task inference. |
| `clickhouse__b9d7cd6a5d7c` | Executable settings-argument request with explicit feature label. Feature exclusion is supported. |
| `clickhouse__bbe657ba243b` | Parallel multipart-storage request introduces helper files. Missing-base and target-status exclusions are correct. |
| `clickhouse__c7415f4f1c68` | Kafka drop-table hang, explicit fixing-message assistance, source changes and a contrib gitlink update. Gitlink stays in full evidence and makes narrower-scope sensitivity false. |
| `clickhouse__d59c0c87b192` | Wrong TTL-argument behavior with reproducer/source hint. Unknown task is a documented conservative false negative. |
| `clickhouse__d6bfbeb95f1e` | ThreadSanitizer thread leak, multiple resolved reports. Keep ambiguity exclusion. |
| `clickhouse__e0eccd215bad` | Text-index logical error; body explicitly describes AST fuzzing. Generic task heuristic misses that body evidence, so provenance remains unknown. |
| `clickhouse__f0630bbcb95b` | Automated CI fuzzer issue. Source boilerplate is not timestamp evidence; exact consumed version remains unknown. |
| `clickhouse__f0cf4718da4e` | Compound-interval syntax capability request with explicit feature label, parser modification and tests. Final seeded feature sample; exclusion supported. |
| `clickhouse__f8b0cc71bfa6` | Dotted-username error and question label. Other classification follows metadata; possible defect requires task review rather than a row override. |

The feature-area defect was corrected globally in `report-evidence-2`, using frozen
text/labels to create v3.1. LLVM counts did not change; ClickHouse feature/other/unknown
and diagnostic counts did. Original v3 evidence was retained. Remaining heuristic
limitations are reported rather than converted to manually curated ground truth.

## Six-source follow-up: systemd, PostgreSQL, and QEMU

The agent inspected selected excerpts, task/kind evidence, statuses, and chronology
for 18 systemd, 17 PostgreSQL, and 15 QEMU seeded cases. All 50 cached selected
payload/text/raw-text hashes matched, and full-tree baseline reads reproduced each
sample's predictions. These automated checks are recorded in the original checkout's
`releases/six-repo-20260914/<repo>-verification.json`. No reproducer was executed,
no human review occurred, and these judgments do not replace the frozen annotations.

| systemd instance | Agent judgment |
|---|---|
| `systemd__0688bea1631c` | JOURNAL_STREAM behavior request; unknown task can retain development work in diagnostics. |
| `systemd__0718a21c13ef` | Explicit DNS feature request; feature and added-target exclusions are supported. |
| `systemd__10f3f4ed016b` | Watchdog-information capability request; unknown does not establish a bug. |
| `systemd__1ed8887e3b53` | tmpfiles regression report was created after this linked fix; chronology exclusion is necessary. |
| `systemd__2367bdcfc901` | Boot-loader specification/documentation request; other-task exclusion is supported. |
| `systemd__3bcc999fa555` | Firmware timing complaint shares a report; grouping remains necessary despite supported text timing. |
| `systemd__4bf1a2c3834c` | WireGuard PublicKeyFile capability request; a diagnostic unknown, not a verified bug. |
| `systemd__70b7e03ebbd9` | NX compatibility report; added memory-attribute header prevents existing-file eligibility. |
| `systemd__8f2477715691` | API return-value complaint; documentation classification and added example source need care. |
| `systemd__925095a6db67` | Flexible-array placement/compiler warning with a source hint; exact text version remains unknown. |
| `systemd__acdba85e0e2b` | udevadm verifier RFC adds an implementation file; target-status exclusion is supported. |
| `systemd__b3ae4e8622c0` | Network reconfiguration report is linked alongside other reports; labels remain ambiguous. |
| `systemd__bf1b9ae487b6` | WakeSystem user-unit capability request illustrates development work among unknown tasks. |
| `systemd__bf478dcffbc3` | Boot-time resolver failure with bug evidence; version chronology is still unresolved. |
| `systemd__e09402326c3d` | Comparator-transitivity report contains precise source context; extra references remain unresolved. |
| `systemd__e3b84b105e63` | repart hardlink-leak report passes local strict rules; this does not establish future-test eligibility. |
| `systemd__ea583ed5a366` | Xen detection regression with an explicit source link; bug evidence does not certify consumed text timing. |
| `systemd__f7725647bb41` | Concurrent portable-service image conflict; exact consumed text version remains unknown. |

| PostgreSQL instance | Agent judgment |
|---|---|
| `postgres__2214a207ee81` | Inline documentation patch submission; excluded from original-report tasks. |
| `postgres__274bbced8538` | TLS ticket traffic observation; ordinary-message classification is conservative. |
| `postgres__28d3c2ddcf91` | GiST wrong-results bug form; report form does not supply missing timezone evidence. |
| `postgres__2cf212db5286` | Reply about Unicode safety/Coverity; added target and reply context remain visible. |
| `postgres__346fbdcc2a92` | pg_surgery infinite-loop bug form; original-message timestamp remains unresolved. |
| `postgres__3a8a1f3254b2` | SQL/JSON patch-thread reply about comments; not verified as an original bug report. |
| `postgres__3e83bdd35a5f` | aarch64 compilation failure looks defect-like but remains task-unknown under current rules. |
| `postgres__47c0accbe05b` | Serializable-transaction assertion shares a report; group restrictions are warranted. |
| `postgres__56d23855c864` | Postmaster cleanup reply reports an uninitialized name; thread timing is not consumed-message timing. |
| `postgres__7afa11feca6c` | Bug-plus-patch submission for property graphs; explicit patch context excludes it. |
| `postgres__843e50208a31` | Index-scan assertion bug form; chronology remains unknown. |
| `postgres__905e44152a1d` | Collation behavior discussion with multiple linked reports; whole-change attribution is ambiguous. |
| `postgres__b738f7b67967` | OAuth integer-overflow discussion is defect-like; unknown is a heuristic false negative. |
| `postgres__e92c0632c147` | GSSAPI/OpenSSL reply proposes a new shared header; added-target exclusion is supported. |
| `postgres__ebf6c5249b7d` | Query-ID regression-test noise; uncached extra references remain unresolved. |
| `postgres__f24523672de9` | Trigger memory-leak report is defect-like despite ordinary/unknown annotations. |
| `postgres__fa06a34d14ea` | Collation-upgrade reply points to a version-check error; reply provenance stays unresolved. |

| QEMU instance | Agent judgment |
|---|---|
| `qemu__0969e00b3933` | m68k segfault with backtrace; current task heuristic misses defect evidence. |
| `qemu__0c201cc17fef` | FSF license-notice address maintenance; other-task exclusion is appropriate. |
| `qemu__1e0c544673f4` | Windows monitor arrow-key malfunction; exact consumed text version is unknown. |
| `qemu__20ab88a9066b` | ast2600 boot failure with commands; unknown classification is conservative. |
| `qemu__32ba75adc009` | Missing plugin documentation; other-task exclusion is supported. |
| `qemu__333e7599a0d7` | VNC regression shares a report across fixes; grouping is necessary. |
| `qemu__40a205da415e` | Usermode CPU-feature warnings; task remains unknown rather than assumed bug. |
| `qemu__78255ce392dc` | aarch64/KVM missing-property failure; defect-like content remains unknown. |
| `qemu__a1367443bac7` | Missing VDSO behavior requires added targets; existing-file exclusion is supported. |
| `qemu__a8e63ff289d1` | macOS VM regression with multiple linked reports; labels remain ambiguous. |
| `qemu__bd64c210ce2b` | MIPS snapshot segfault has bug evidence; consumed text timing remains unknown. |
| `qemu__c9bc9f57ffba` | M-profile helper alignment issue has bug evidence; chronology is not independently certified. |
| `qemu__d44971e725c0` | nanoMIPS semihosting freeze exceeds the projected primary-file limit. |
| `qemu__e6c33efed3ca` | Generalizing ivshmem is a capability request with added targets; exclusion is supported. |
| `qemu__e73b8bb8a3e9` | Incorrect MPU region count has bug evidence; it is not a verified temporal test by itself. |

Systemd feature-request forms and several PostgreSQL/QEMU defect descriptions expose
known false negatives in the conservative task heuristics. Diagnostics intentionally
retain unknowns, so their counts must not be described as verified bugs. Public release
also needs review of names, obfuscated contact details, and embedded third-party notices;
the private storage screen is not a replacement for that review.
