# Verification — updated 13 November 2026

## Current result

The integrated local prototype works with public source documents, optional two-pass AI, source-aware monitoring, persistent alerts and synthetic contacts. Chrome checks passed at desktop and phone widths. The submission bundle starts from a clean extraction with a ready-to-search public corpus. **Public GitHub publication, hosting/access setup and actual build-history links are still required for submission.**

Research is usable with disclosed coverage limits. A structural pass is not a factual-accuracy score. Announcement coverage is partial, and six current transcript candidates remain unverified. The initial private GitHub push was confirmed at ac72021; public visibility, deployment and email sending have not occurred.

## Requirement audit and new implementation

All five pages of the challenge were checked. [CHALLENGE_AUDIT.md](docs/CHALLENGE_AUDIT.md) maps mandatory requirements, optional examples, evidence and remaining delivery work.

The automatic PDF validator was replayed against all twelve real bundled primary documents: all passed, with literal quarter-end labels retained where present.

Added generic new-ticker acquisition before API research: company directory resolution/fallbacks, original issuer/exchange PDFs only, identity/type/period inspection, indexing, progress, cached attempts and explicit retry. Tests acquire a company outside all seeds and obtain company-scoped evidence without following it. Added official NSE RSS announcement fallback across followed companies, bounded-history coverage labels and deduplication across API/RSS transports. Added shared-demo HTTP Basic access, a minimal readiness route, proxy-origin tests and a Render Blueprint with persistent storage and a generated secret.

The user confirmed push 9d63c8b, then real automatic HDFCBANK acquisition (one annual report and two transcripts), MARUTI partial acquisition (annual report only), a completed refresh of all eighteen price feeds, and passed Chrome checks at both widths. The RSS endpoint returned a valid recent overnight snapshot without portfolio matches; the date-range API still returned 403. MARUTI transcript links used an HTML viewer and exposed a parser gap. Generic encoded-query/embedded-PDF resolution and issuer-hosted brand-name handling are now fixed and regression-tested; a targeted MARUTI live retry remains. Successful RSS now also supplements configured company-IR pages instead of skipping them. This executor still cannot resolve external DNS or bind a browser server. No new paid model batch or cloud service was silently started.

## Free hosting choice — 15 November

The user confirmed no Render resources exist and requested no payment. The default Blueprint now uses Free compute without a disk and temporary storage at /tmp/finn. The hosted app displays a reset/monitoring notice. Existing local data and credentials are unchanged. The default cloud deployment omits model credentials; AI remains an optional separately billed integration. A fresh-workspace smoke check verifies public-corpus restoration and hosted access; actual Render deployment still needs user execution. See DEPLOYMENT.md for the revised free-runtime checks. Persistent local tests do not establish persistence on the free host.

## Evidence from real runs

| Check | Observed outcome |
| --- | --- |
| Primary corpus | Four FY2026 annual reports and eight current/historical transcripts indexed for TCS, INFY, RELIANCE and ASIANPAINT; one report and two transcripts per company. |
| Archived corpus | Twelve original public filings, five dated archive events and a reviewed Reliance numeric example. |
| Real AI | Latest full run: 12/12 structural passes; analyst `gpt-4o-mini`, reviewer `gpt-6.1-sol`, pipeline 6, low reviewer effort. Both passes completed; seven draft claims withheld. |
| Assistant source inspection | All 41 retained findings inspected against selected passages. All 67 support spans independently matched text extracted from the original PDF pages. Main retained claims are supported within the scope described in docs/EVALUATION.md; several answers are incomplete or repetitive. This is not an independent human audit. |
| Unreviewed caveat correction | An Infosys caveat wrongly said no explicit guidance was available despite guidance on a cited page. Analyst caveats now give way to a deterministic retrieval-scope notice. This applies to cached results without extra model calls; findings and reviewer decisions are unchanged. Offline SDK/cache regression checks cover both routes. |
| Prices | All eighteen followed symbols refreshed successfully from Yahoo. Persistent real price alerts were observed. |
| Announcements | NSE returned HTTP 403. The official Reliance IR fallback imported ten filings and created five alerts. Result is explicitly partial: one of eighteen followed companies. Publication dates with unknown times retain that precision. |
| Browser | User-terminal Playwright/Chrome run passed twelve interaction checks at each of 1440×1000 and 390×844; no page errors. Representative screenshots inspected. |
| Fresh package | 24 public PDFs, generated public-only SQLite/FTS index, manifest hashes verified. Clean extracted app started in about 1.3s, served every PDF, returned primary research evidence and preserved saved state across restart. |
| Automated suite | Latest suite: 102/102 passed in 26.962 seconds. JavaScript syntax and Python compilation passed. |
| Container/cloud/public repository | Container configuration prepared; Docker build and deployment not executed. No public GitHub repository created. |

Private evidence is in `data/verification/`: `evaluate.json`, `source-review.json`, `refresh.json`, `browser/report.json`, browser screenshots and `package.json`. It is excluded from publication because reports can contain investor context. Public documentation summarises results without exporting that state.

## What the browser run established

Real browser interaction exercised the default live window, saved events, event details and original PDFs, research progress/evidence and source coverage, PDF upload, explicit second-degree contact paths and Escape, empty results, JSON contact import, portfolio, settings, persisted alert read state and a research failure state. Monitoring and AI calls were disabled in an isolated database snapshot. Financial tables intentionally scroll horizontally; no blocking page overflow was observed.

This was a Chrome viewport simulation, not physical-phone Safari testing, accessibility certification or a browser factual evaluation of live AI. Real AI was exercised separately through the CLI.

## Source and research limits

- Six newer BSE transcript candidates returned HTTP 403 and were not promoted into verified coverage. Historical fallback periods remain explicit. A discovery date is never treated as a reporting period.
- Live announcement fallback currently covers Reliance only. An empty window does not establish portfolio-wide completeness. No alternate source is silently represented as a successful NSE response.
- The stronger reviewer improved metric labels, source attribution and numerical bases. Conservative numeric validation can withhold supported guidance using abbreviated fiscal years. Infosys outlook consequently retained only one finding, despite guidance existing in the source. Asian Paints business coverage is partial and cash-flow findings repeat. Historical guidance should be read with the period shown by its citation.
- Research has no investment recommendation score. Support-line matching and a second model pass constrain errors but do not prove completeness, interpretation or future accuracy. See [the research evaluation](docs/EVALUATION.md).
- The financial-table parser is limited to the reviewed archived Reliance consolidated table. Other documents remain readable and searchable; general table extraction is not claimed.

## Public bundle and privacy

`python3 package_submission.py` builds `dist/finn-submission.zip` using an explicit allowlist. It includes twelve archive PDFs, twelve primary PDFs and a fresh generated index containing only selected public documents, extracted text, canonical provenance, company metadata and default settings. It does not copy the investor database. Contacts, events, prices, jobs, alerts, refresh history, model caches and monitoring state are empty in the index; startup creates the documented synthetic demo data.

The archive excludes `.env`, investor uploads, runtime data, verification reports and credentials. Each file has a SHA-256 entry, and configured-key scanning runs before inclusion. The index installs only into a new workspace, validates bundled PDF paths, and cannot overwrite an existing investor database. Path rejection and state preservation are covered by tests. Existing local user data and credentials were not replaced.

## Changes since the initial verification

Earlier verification ran inside a restricted executor that could neither resolve external hosts nor connect to localhost. Those failures remain real observations of that executor. Subsequent commands run by the user in their normal terminal established the live AI, corpus, prices, fallback announcements and browser outcomes above. No permission bypass was used.

Earlier mini-only AI evaluations fluctuated between 9/12 and 12/12 structural passes and failed source inspection. The source-reviewed full batch explicitly used the separate stronger reviewer. The app still defaults to the analyst model for both passes unless `FINN_REVIEW_MODEL` is set; the README gives the tested configuration. No silent paid-model configuration change was made to `.env`.

The initial Asian Paints annual-report download exceeded the 25 MB generic PDF cap. Annual reports now allow up to 100 MB, while transcripts/filings remain capped at 25 MB; the real report imported successfully. Schema migrations preserve original contacts, saved/read state and historical TATAMOTORS records while the current portfolio uses TMPV.

## Remaining submission work

1. Resolve or explicitly disclose the latest-transcript gaps and limited live announcement coverage.
2. Choose a Python-compatible host with persistent storage and an access gate for this single-investor app; deploy and verify the real public URL. Container execution has not yet been tested.
3. Push the new reviewed changes to the existing private unordinarysubstance/FINN repository. The brief asks for public visibility; keep the user-requested private setting until they approve changing it.
4. Add actual coding-agent conversation exports/share links; no build history has been fabricated.
5. Fill the concrete links/name in docs/SUBMISSION_EMAIL.md, review the final note and submit by 15 November 2026. Sending requires explicit user instruction.
