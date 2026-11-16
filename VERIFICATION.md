# Verification — updated 15 November 2026

## Current result

The integrated local prototype works with public source documents, optional two-pass AI, source-aware monitoring, persistent alerts and synthetic contacts. Chrome checks passed at desktop and phone widths. The submission bundle starts from a clean extraction with a ready-to-search public corpus. The owner confirmed hosted readiness, login, original PDF access, research citations and Network search at https://finn-rzzb.onrender.com/. The owner's GitHub CLI confirmed the repository is public; the actual build-history attachment and covering note are now prepared privately; final live checks, latest publication/deployment and sending remain.

Research is usable with disclosed coverage limits. A structural pass is not a factual-accuracy score. Announcement coverage is partial, and six current transcript candidates remain unverified. The free deployment commit 3c5b063 was pushed and its hosted workflows were confirmed by the owner. The assistant could not independently fetch the hosted endpoints. No submission email has been sent.

## Requirement audit and new implementation

All five pages of the challenge were checked. [CHALLENGE_AUDIT.md](docs/CHALLENGE_AUDIT.md) maps mandatory requirements, optional examples, evidence and remaining delivery work.

The automatic PDF validator was replayed against all twelve real bundled primary documents: all passed, with literal quarter-end labels retained where present.

Added generic new-ticker acquisition before API research: company directory resolution/fallbacks, original issuer/exchange PDFs only, identity/type/period inspection, indexing, progress, cached attempts and explicit retry. Tests acquire a company outside all seeds and obtain company-scoped evidence without following it. Added official NSE RSS announcement fallback across followed companies, bounded-history coverage labels and deduplication across API/RSS transports. Added shared-demo HTTP Basic access, a minimal readiness route, proxy-origin tests and a Render Blueprint with a generated secret; the later free-hosting revision removed its disk.

The user confirmed push 9d63c8b, then real automatic HDFCBANK acquisition (one annual report and two transcripts), MARUTI partial acquisition (annual report only), a completed refresh of all eighteen price feeds, and passed Chrome checks at both widths. The RSS endpoint returned a valid recent overnight snapshot without portfolio matches; the date-range API still returned 403. MARUTI transcript links used an HTML viewer and exposed a parser gap. Generic encoded-query/embedded-PDF resolution and issuer-hosted brand-name handling are now fixed and regression-tested; the owner subsequently confirmed MARUTI ready with its FY2026 annual report and Q1/Q2 FY2027 transcripts, without acquisition failures. Successful RSS now also supplements configured company-IR pages instead of skipping them. This executor still cannot resolve external DNS or bind a browser server. No new paid model batch or cloud service was silently started.

## Free hosting choice — 15 November

The user confirmed no Render resources exist and requested no payment. The default Blueprint now uses Free compute without a disk and temporary storage at /tmp/finn. The hosted app displays a reset/monitoring notice. Existing local data and credentials are unchanged. The default cloud deployment omits model credentials; AI remains optional and now supports the Gemini free tier with its own eligibility and quotas. A fresh-workspace smoke check verifies public-corpus restoration and hosted access; the owner has deployed it and confirmed the main hosted workflows. The Render-specific filesystem reset itself has not been independently tested remotely. See DEPLOYMENT.md for the revised free-runtime checks. Persistent local tests do not establish persistence on the free host.

## Evidence from real runs

| Check | Observed outcome |
| --- | --- |
| Primary corpus | Four FY2026 annual reports and eight current/historical transcripts indexed for TCS, INFY, RELIANCE and ASIANPAINT; one report and two transcripts per company. |
| Archived corpus | Twelve original public filings, five dated archive events and a reviewed Reliance numeric example. |
| Gemini live smoke | Owner run on gemini-3.6-flash: uncached analyst/reviewer completed on first attempts in 9.384 seconds, no rejected/revised claims. Two findings and two support spans checked against original TCS filing PDF pages 1 and 14. Broader company evaluation pending. |
| Real AI | Historical OpenAI full run: 12/12 structural passes; analyst `gpt-4o-mini`, reviewer `gpt-6.1-sol`, pipeline 6, low reviewer effort. Both passes completed; seven draft claims withheld. |
| Assistant source inspection | All 41 retained findings inspected against selected passages. All 67 support spans independently matched text extracted from the original PDF pages. Main retained claims are supported within the scope described in docs/EVALUATION.md; several answers are incomplete or repetitive. This is not an independent human audit. |
| Unreviewed caveat correction | An Infosys caveat wrongly said no explicit guidance was available despite guidance on a cited page. Analyst caveats now give way to a deterministic retrieval-scope notice. This applies to cached results without extra model calls; findings and reviewer decisions are unchanged. Offline SDK/cache regression checks cover both routes. |
| Prices | All eighteen followed symbols refreshed successfully from Yahoo. Persistent real price alerts were observed. |
| Announcements | NSE returned HTTP 403. The official Reliance IR fallback imported ten filings and created five alerts. Result is explicitly partial: one of eighteen followed companies. Publication dates with unknown times retain that precision. |
| Browser | User-terminal Playwright/Chrome run passed twelve interaction checks at each of 1440×1000 and 390×844; no page errors. Representative screenshots inspected. |
| Fresh package | 24 public PDFs, generated public-only SQLite/FTS index, manifest hashes verified. Clean extracted app started in about 1.3s, served every PDF, returned primary research evidence and preserved saved state across restart. |
| Automated suite | Latest suite: 135/135 passed in 42.103 seconds, including twenty-seven Gemini transport/diagnostic checks, quota classification and batch-stop checks. JavaScript syntax and Python compilation passed. |
| Container/cloud/public repository | Owner reports the Render deployment working. Shared-login and read/research workflows confirmed; assistant network verification unavailable. Repository is public, confirmed by the owner's authenticated GitHub CLI. |

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

Earlier mini-only AI evaluations fluctuated between 9/12 and 12/12 structural passes and failed source inspection. The source-reviewed full batch explicitly used the separate stronger reviewer. That configuration remains available with explicit OpenAI selection. The user has since requested Gemini Flash; pipeline 7 defaults both passes to Gemini. Local provider/model settings were updated without replacing existing credentials; the owner subsequently configured a key and received a Google 503 overload response on the initial smoke check.

The initial Asian Paints annual-report download exceeded the 25 MB generic PDF cap. Annual reports now allow up to 100 MB, while transcripts/filings remain capped at 25 MB; the real report imported successfully. Schema migrations preserve original contacts, saved/read state and historical TATAMOTORS records while the current portfolio uses TMPV.

## Remaining submission work

1. Resolve or explicitly disclose the latest-transcript gaps and limited live announcement coverage.
2. Hosted core workflows are confirmed by the owner. Keep the free-runtime limitations disclosed; independent remote reset testing is not claimed.
3. Push the final documentation changes and apply the now-authorized public visibility change to unordinarysubstance/FINN; verify its public status afterward.
4. Add actual coding-agent conversation exports/share links; no build history has been fabricated.
5. Fill the concrete links/name in docs/SUBMISSION_EMAIL.md, review the final note and submit by 15 November 2026. Sending requires explicit user instruction.

## Gemini provider migration

Pipeline 7 defaults to Gemini Flash for both model passes, using gemini-3.6-flash and server-side GEMINI_API_KEY. OpenAI requires explicit provider selection, and quota failures never trigger paid-provider failover. The source-line and numeric validators remain in place; cache keys now include provider identity. The current suite includes offline Gemini HTTP and end-to-end research checks. The owner's live Gemini smoke reached Google but received HTTP 503 UNAVAILABLE before the analyst completed. FINN now retries explicit transient server errors up to two times per pass and reports exhausted overload separately; daily/unknown quota and authentication errors do not retry; pipeline 8 permits one hinted minute-limit cooldown. The later 3.6 filing smoke check and its two source findings passed; the first broader batch passed 2/12 and pipeline 8 rerun remains pending. The 12/12 OpenAI result above is historical, not Gemini acceptance. See [setup and verification](docs/GEMINI.md).

## Gemini timeout diagnosis — 16 November 2026

After the initial overload, the owner reported a ReadTimeout at 45.415 seconds before analyst completion. The transport now defaults Gemini research to 120 seconds per pass, configurable from 10 to 180 seconds, while preserving no retry on ambiguous read timeouts and no paid-provider fallback. Diagnostics include the failed stage, attempt count and timeout budget. The new check-ai CLI lists advertised Flash models and makes one small structured-JSON probe per configured model (30-second timeout, no retries, no company passages). This separates a small availability check from full research; it cannot determine remaining quota, free-tier eligibility or financial accuracy. The later 3.6 filing smoke completed successfully; that does not validate every research question.

## Gemini 3.6 availability confirmed by owner — 16 November

The owner's check-ai report for gemini-3.6-flash passed its advertised-model listing and single structured-JSON probe on the first attempt, with total latency 3,664 ms. The default model, local selections, example environment and Render Blueprint now use 3.6. Earlier overload/timeouts concerned 3.8. This availability check was followed by a successful live filing smoke and inspection of both retained findings; the first broader Gemini batch passed 2/12 and pipeline 8 rerun remains pending. Existing hosted service environment settings require a separate update and redeploy.

## Gemini full-batch failures and pipeline 8 — 16 November

The owner's first 12-answer Gemini evaluation returned 2 structural passes, 5 per-minute rate-limit failures and 5 analyst output-validation failures. Google's errors explicitly state a five-request/minute free-tier limit. Old validation diagnostics do not identify the invalid output's shape or finish/block reason. The private diagnosis binds this tally to the exact evaluation report hash.

Pipeline 8 adds 15-second request pacing across both passes/concurrent jobs in one process, one bounded cooldown retry only for a confirmed minute quota with a wait hint, strict analyst JSON with retrieved source IDs, and safe validation/finish/block metadata. Daily/unknown quotas and ambiguous read timeouts remain unretried; OpenAI is never an automatic fallback. The financial validators are unchanged. New cache identity separates the schema protocol. CLI progress makes the longer paced run visible. Offline checks do not establish that all five validation failures are fixed; a live targeted question and full rerun remain required.

## Pipeline 8 live progress and daily-quota stop

The targeted TCS outlook check passed. The next full selection returned five structural passes (all TCS questions and Infosys business/outlook) and seven quota failures, with no output-validation failures before quota exhaustion. Google's exact error identifies 20 generation requests per day. The first cap occurred during Infosys cash-flow review; the later calls could not complete either. Full Gemini acceptance remains incomplete.

Daily exhaustion is now classified as daily_quota. The evaluator stops immediately when it sees that code, reports the unattempted selections explicitly and preserves the full required count. No cache protocol/model/prompt change was made, so the five successful pipeline 8 answers remain reusable after the project's daily reset. Google documents midnight Pacific resets. The zero-payment continuation is the same local evaluate command after reset, using its cached successes; a fresh uncached batch would need up to 24 calls against this project's 20-call daily allowance.

## Submission handoff prepared

The final local review passed 135 Python tests and JavaScript syntax checks. A separate three-check offline handoff test verifies that inconsistent evaluation reports cannot publish, the no-payment workflow rejects OpenAI before commands run, and only manifest-allowlisted files are staged. All 35 supporting spans across the five completed Gemini answers independently match the correct primary PDF pages; financial interpretation/completeness still needs contextual inspection.

A genuine redacted export of the recorded FINN Codex conversation has been prepared as FINN_AI_BUILD_HISTORY.zip outside the public repository. It includes only visible user/assistant messages; hidden instructions/reasoning and tool payloads are omitted, credentials/local paths are redacted, and a credential scan passed. The covering note now names the configured author and links the actual prototype/repository; the owner adds the demo password privately in the email.

The executor cannot resolve Gemini/GitHub/Render or run the phone browser server here. The owner's normal-terminal finish_submission.py performs the resumed full evaluation, original-PDF audit, browser checks, history export, source packaging/audit and public repository push. It records actual acceptance counts and explicit limits; a partial AI evaluation is never labelled complete. The existing Render service then needs its manual deployment and private-password hosted check. No new email, paid cloud resource or unsupported live-acceptance claim has been made.
