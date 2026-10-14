# WP-14 review r1 remediation

Date: 2026-09-21 (Asia/Shanghai)

Status: `IMPLEMENTED_NOT_ACCEPTED`. This is executor self-verification for ISSUE-001 and ISSUE-002 only. It is not a review, acceptance, deployment, or WP-15 start.

## Baseline and scope

The remediation used [wp-14-review-r1.md](wp-14-review-r1.md) and its four preserved counterexamples as the fixed review baseline. The historical report and evidence were not changed. Production changes are limited to:

- `frontend/src/formal/pages/DocumentsPage.tsx`
- `frontend/src/formal/pages/HistoryPage.tsx`
- `frontend/tests/pagination-context.test.tsx` (new product regression suite)

The evidence directory contains the isolated browser runner/fixture and this run's summaries. Backend pagination, eligibility, OpenAPI, accepted preview behavior, and user instances were not changed.

## ISSUE-001: pagination cursors

### Documents and chunks

`DocumentsPage` now uses `useInfiniteQuery` for `/documents?limit=50` and version-isolated chunk queries with `limit=100`. Non-null cursors are encoded with `encodeURIComponent`; numeric chunk cursor `0` remains valid. Pages are appended with stable deduplication by document id and by the server's version-local chunk ordinal. The query key contains document and version identity, so pages cannot cross versions.

Later-page errors leave prior pages rendered and expose a retry for that page. `加载更多资料` and `加载更多切块` report their fetch state and disappear only after the server cursor is exhausted. No total count or full-text server search is claimed.

### History

History remains inactive until the user submits a search. Each submit receives a new generation in its query key. When the current pages contain no match and `next_cursor` exists, the page continues fetching and displays `正在继续搜索后续病例`; `没有匹配病例` appears only after exhaustion. Items are deduplicated by case id. A repeated cursor terminates pagination instead of forming a request loop, and an older generation cannot populate the current search.

The original three pagination counterexamples and added encoded cursor, duplicate item, repeated cursor, page error, `cursor=0`, version isolation, and search-generation cases are now part of the product test suite.

## ISSUE-002: retrieval context binding

Each evidence search freezes document id, version id, query text, and a monotonically increasing generation. Starting a newer request aborts its predecessor. Changing document/version, changing the query text, successful upload context switch, or component cleanup invalidates and aborts the old request. Success, error, and settle callbacks independently recheck mounted lifecycle, the frozen context, query text, and generation, so an ineffective abort still cannot publish a stale result or stale error.

The current request's real error is retained and shown; the question input is not cleared. The button permits a newer same-context request to supersede an in-flight request. Results continue to display the server's response unchanged and are not described as formal evidence.

The production-page tests cover A-to-B late success, A-to-B late error, ABA late success, current-context success/error, and an older request attempting to overwrite a newer result. The lifecycle setup explicitly restores its mounted flag, including React StrictMode's development setup/cleanup cycle.

## Verification

Final evidence is summarized in [verification-summary.md](evidence/wp-14-remediation-r1/verification-summary.md) and [browser-summary.md](evidence/wp-14-remediation-r1/browser-summary.md).

- WP-14 frontend: 5 files / **24 passed**, exit 0.
- Preview compatibility: **24 passed**, exit 0.
- TypeScript: exit 0.
- OpenAPI generation check: exit 0.
- Independent production build: exit 0, 102 modules, output `.local-data/wp14-remediation-r1-build-final`.
- Browser: real isolated API showed 51 documents and 101 chunks through load-more controls and found a case on the second history page; console error/warning count 0.

The controlled tests are the evidence for delayed-success/error timing. The local real server answered the history second page too quickly to preserve the transient continuation label in a screenshot. This limitation is recorded rather than presented as a browser timing proof.

## Git index protection

All commands used `GIT_OPTIONAL_LOCKS=0`. Before and after the remediation, both staged-content representations were saved and hashed:

| Representation | Before SHA-256 | After SHA-256 |
|---|---|---|
| `git ls-files --stage` | `e146135dd7084735f6b331b6ed1a3ac32938bf971f8705cf9e75e1dccb49a4ea` | same |
| `git diff --cached --binary` | `fa5b7372e0841a7d934b5b7a134050ca8d2cc653e93d78b597a73028a3152a12` | same |

Therefore the staged business content is unchanged. The raw `.git/index` hash is deliberately not used. The review-r1 disclosure that stat-cache refresh changed that raw file hash remains applicable and is not rewritten.

Evidence: [git-index-content-comparison.json](evidence/wp-14-remediation-r1/git-index-content-comparison.json), plus the before/after text and binary patch captures in the same directory. No `git add`, `reset`, `commit`, or index-file copy was performed.

## Retained boundaries

- WP-14 remains `IMPLEMENTED_NOT_ACCEPTED` pending focused review of these two issues.
- No server full-text search, fake total, backend protocol change, material-eligibility change, WP-15 capability, deployment, or paid model call was added.
- `frontend/dist`, 5180, and 5196 were not modified or operated.
