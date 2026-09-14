# 04 — Publication privacy and licensing review

Status: **hold the full-text public upload pending review** (2026-09-14).
This is an engineering risk assessment using published policies, not legal advice
or a determination that the dataset is unlawful. Hugging Face write access is verified;
`jingunhong/cpp-loc` is an empty private placeholder with no dataset files uploaded.
Evidence paths below refer to the original `Cpp-SWE-bench` checkout.

The user subsequently authorized **private review storage**, with the public-release
review deferred. `scripts/package_private.py` prepares a separate runner-only copy of
a verified local bundle: it withholds phone/credential-pattern rows, preserves retained
text, source links, groups, chronology and eligibility, and leaves raw companions local. Its manifest records the screen,
counts, exclusions, and parent hashes. The screen covers all runner fields, but names,
email addresses, home paths, and other personal information may remain. Private access
is a storage decision, not clearance for public redistribution. Verify actual Hub
visibility before upload; `hf upload --private` alone does not change an existing repo.

## Evidence found locally

A reproducible pattern screen of all 18,216 v2 report-backed rows flags email-like
strings, home directories, IPv4-like strings, two URL credentials, one AWS access-key
shape, and two phone-context rows. Counts are instance counts and overlap. They are
not counts of unique people, confirmed credentials, or confirmed legal violations.
The scanner never emits matched values; raw data remains local and unchanged.

| Repository | Reports | Email-like | Home path | Phone context | URL credentials | AWS key shape |
|---|---:|---:|---:|---:|---:|---:|
| LLVM | 8,357 | 93 | 662 | 0 | 0 | 0 |
| Linux | 5,424 | 1,836 | 34 | 1 | 0 | 0 |
| systemd | 1,418 | 79 | 34 | 0 | 0 | 0 |
| PostgreSQL | 1,318 | 33 | 35 | 1 | 0 | 0 |
| ClickHouse | 1,022 | 4 | 39 | 0 | 2 | 1 |
| QEMU | 677 | 54 | 73 | 0 | 0 | 0 |

Agent inspection identified personal contact signatures in
`linux__1ca61060de92` and `postgres__4fdb6558c270` (telephone/contact details), which
survived cleaning. Do not reproduce those values in public audit reports.
The credential-shaped ClickHouse cases require context: `clickhouse__0029829b819b`
is a localhost RabbitMQ configuration, `clickhouse__bdf12f0b24e8` a local MinIO test
configuration, and `clickhouse__dc112c3a7273` includes AWS example-looking credentials.
These observations do not validate live credentials or justify publishing all matches.
No credentials were tested against a service. Many Linux addresses are diagnostic
identifiers/service mailboxes, not necessarily personal contact details.

Run on candidate files and again on enriched companions before any release:

```sh
uv run python scripts/privacy_audit.py data/*/v2/dataset.jsonl --out /tmp/cpp-loc-privacy-v2.json
```

The enriched report-backed integrity companions were screened too: email-like
instance counts are LLVM 794, ClickHouse 558, PostgreSQL 1,262, and Linux 3,544;
phone-context flags are PostgreSQL 1 and Linux 12. These are overlapping pattern
flags, not additional confirmed people. Results and input hashes are retained in
`releases/privacy-enriched.json`. This scan does not cover every raw patch, historical
commit-message field, or null-report companion row, so it cannot clear the full bundle.

The patterns are a review aid, not comprehensive PII detection or anonymization.
They miss arbitrary names, obfuscated contacts, sensitive narratives, and some secrets;
IP-like version strings and sample values can be false positives. Raw commit evidence
and mail/provenance companions can contain more contact data than runner fields.
Do not assume a five-field export is privacy-clean just because metadata was removed.

## Policy and rights assessment

Hugging Face supports datasets but prohibits privacy and third-party intellectual-property
violations, explicitly including unauthorized disclosure of private contact information.
This is not a blanket prohibition on every public author name or work address. The
publisher still needs a defensible basis for the actual content redistributed.
[Hugging Face Content Policy](https://huggingface.co/content-policy),
[Terms of Service](https://huggingface.co/terms-of-service).

GitHub's public-content permission includes viewing/forking through its service;
Section D.6 also says contributions to a licensed repository take that repository's
license unless a separate agreement applies. These are relevant evidence, not a reason
to assume all issue text, embedded logs, attachments, or third-party material is licensed
under the extractor's MIT license. Verify the applicable source/contribution terms and
preserve required notices and attribution. The cached API payloads contain no new
permission grant from this extraction pipeline.
[GitHub Terms, D.3–D.8](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#d-user-generated-content).

PostgreSQL's archive policy authorizes its public mailing-list archive; it does not by
itself settle unrestricted republishing as an ML training dataset on another platform.
[PostgreSQL Archives Policy](https://www.postgresql.org/about/policies/archives/).

The upstream code license families also differ. This is a starting inventory, not a
file-by-file clearance of patches or a blanket license for report text:

| Source | Code licensing evidence | Remaining release work |
|---|---|---|
| LLVM | [Apache-2.0 with LLVM exception; legacy contributions also documented](https://llvm.org/docs/DeveloperPolicy.html) | Check applicable file notices and contribution/report terms |
| ClickHouse | [Apache-2.0 repository license](https://github.com/ClickHouse/ClickHouse/blob/master/LICENSE) | Preserve applicable notices; check embedded third-party material |
| Linux | [GPL-2.0-only with documented syscall exception and file-level SPDX rules](https://www.kernel.org/doc/html/next/process/license-rules.html) | Check actual file licenses; do not infer that mail text has the kernel license |
| QEMU | [GPLv2 and separate component licenses](https://www.qemu.org/docs/master/about/license.html) | Check component/file notices and issue-content rights |
| PostgreSQL | [PostgreSQL License for software/documentation](https://www.postgresql.org/about/licence/) | Retain required notices; assess archived mail separately |
| systemd | [Repository includes LGPL 2.1 terms](https://github.com/systemd/systemd/blob/main/LICENSE.LGPL2.1) | Check per-file SPDX licenses and issue-content terms |

The draft bundle does not yet carry a verified per-file license/notice inventory.
Merely tagging it MIT or `license: other` on Hugging Face would not settle those
obligations. No claim is made that all patches or all reports share one license.

Privacy law is separate from copyright. Korea's PIPC describes lawful-basis assessment
and safeguards for personal data across generative-AI development; public availability
is not an automatic exemption. Which obligations apply to this project's collection,
redistribution, and cross-border hosting depends on the publisher, purpose, and
jurisdiction. Seek qualified advice if these rights/bases remain unresolved.
[PIPC's 2025 generative-AI guidance](https://pipc.go.kr/eng/user/ltn/new/noticeDetail.do?bbsId=BBSMSTR_000000000001&nttId=2875),
[PIPC's publicly available data guidance](https://pipc.go.kr/eng/user/ltn/new/noticeDetail.do?bbsId=BBSMSTR_000000000001&nttId=2591).

## Concrete release decision

The remaining work is:

1. **Fix the public payload.** The current draft includes raw evidence and companions.
   Keeping those local and publishing only reviewed runner fields and a minimal
   provenance manifest would reduce exposure; report text still needs review.
2. **Complete the privacy review for that payload.** Screen every field, including
   patches and null-report companions if included. Resolve the confirmed contact
   signatures and credential-shaped cases in context, then document what is retained,
   transformed, or excluded and the applicable privacy basis.
3. **Document redistribution rights.** For each source and included content type,
   identify the applicable license, permission, or other legal basis. Verify code and
   snippet notices and attribution, and assess issue/mail terms separately. The code
   repository's MIT license supplies no blanket dataset permission.
4. **Build and verify a new release version.** Apply the agreed policy reproducibly,
   keep raw evidence local, recompute hashes and eligibility/localization impact, and
   review the final files. Include the resulting license/notice inventory, dataset
   card, and a contact/removal process before uploading.

The current full-text corpus and raw companions are **not cleared for upload as-is**.
Keep the complete research evidence local. Before a full-text release, establish
source-specific redistribution rights/notice obligations, review flagged contact and
credential material, and decide a documented privacy transformation/exclusion policy.
A privacy transformation must be a new version with recomputed hashes and measured
localization impact; never silently edit frozen rows or strip attribution required by
a license. The earlier no-identifier-masking constraint is preserved during preparation.

A smaller initial publication of extraction code, aggregate results and a carefully
screened reference/manifest catalog would reduce copied-text exposure; it does not
establish that every URL or Message-ID is anonymous or remove all legal questions.
Prepare/review that concrete alternative before asking the user to choose a release.
Private/gated Hugging Face hosting changes access, not the underlying rights requirements.
A takedown/contact procedure should accompany any approved public dataset; it cannot
replace an initial rights review.
