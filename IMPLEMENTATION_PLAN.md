# FINN — Implementation and Resumption Plan

Prepared: 11 November 2026
Challenge deadline: 15 November 2026
Intended file: finn/IMPLEMENTATION_PLAN.md

Document status: Canonical copy of the complete phase sequence from the original file with a leading space in its name. The original draft is preserved unchanged. This plan's initial-state observations are historical; consult VERIFICATION.md for current verified outcomes.

Implementation checkpoint (12 November 2026): four annual reports and eight transcripts indexed; real two-pass research completed (12/12 structural checks with separate stronger reviewer); 41 retained findings source-inspected with coverage limits; eighteen price feeds refreshed; ten Reliance filings imported through the partial official-company fallback; desktop and phone browser checks passed. A portable public corpus and search index are packaged without investor state. Current transcript gaps, broader announcement coverage, public repository, hosting and actual build-history links remain open. See VERIFICATION.md for exact evidence and limits.

13 November requirement audit: added automatic new-ticker primary acquisition, official NSE RSS fallback, shared hosted-demo access, readiness and Render configuration. See docs/CHALLENGE_AUDIT.md for mandatory versus optional scope and exact pending delivery checks. Initial private GitHub push confirmed; visibility remains private by user instruction.

## 1. Objective and current state

Complete a focused, reliable FINN prototype demonstrating:

Important portfolio announcement → company analysis grounded in primary documents → relevant network contact and a reason to speak with them.

The challenge requires at least one working workflow in each of Push, Pull, and Network. Its detailed feature examples are optional; implementation quality and product judgment matter more than breadth.

### Workspace

- Workspace: /Users/aaryan/Desktop/ENAM
- New application: finn/
- Original project: CS787-main/
- Challenge specification: 1. ENAM_Founding AI Engineer Build Challenge_Main.pdf
- Preserve the original CS787 project and acknowledge its team in the submission.

### Verified current state

- FastAPI application runs at http://127.0.0.1:8000.
- Mobile-responsive frontend has Briefing, Research, Network, and Portfolio views.
- SQLite persists documents, page chunks, events, contacts, settings, research jobs, prices, and cached model outputs.
- Portfolio contains 18 companies.
- Source library contains 12 archived company filings, zero annual reports, and zero earnings-call transcripts.
- Five curated historical announcement cards and ten synthetic contacts are seeded.
- Reliance’s archived results view calculates Revenue, EBITDA, PBT, and PAT comparisons from one specifically supported table.
- Research supports company-filtered keyword retrieval and links to original PDF pages.
- Strict fundamental research excludes ordinary filings; filing analysis is a separate scope.
- Optional AI workflow consists of an analyst followed by an evidence reviewer.
- .env loading is implemented. The user has supplied an API key, and the running application reports AI configured.
- A successful real model request has not been verified.
- Fourteen backend tests and JavaScript syntax checks previously passed.
- Browser/mobile verification and live-data integration remain incomplete.

### Important corrections to existing documentation

README.md and VERIFICATION.md contain historical statements that are now stale:

- The server can now run.
- Network access is enabled by the current environment.
- An API key is configured.

Update these documents after rechecking actual behavior. Do not assume that previously blocked integrations still fail.

### Existing code responsibilities

| Module | Responsibility |
|---|---|
| app.py | HTTP endpoints, background jobs, startup, settings and portfolio operations |
| store.py | SQLite schema, PDF import, page chunks, retrieval, calculations |
| connectors.py | NSE announcements, Yahoo market data, document discovery and downloads |
| research.py | Evidence retrieval, optional analyst/reviewer, Reliance-specific metrics |
| seed.py | Mock portfolio, archived events, synthetic contacts and matching |
| static/ | Browser interface |
| tests/ | Backend and mocked-model checks |

## 2. Implementation sequence

### Phase A — Re-establish the baseline

1. Read this plan and the challenge PDF.
2. Inspect the application for changes made after this plan.
3. Check whether port 8000 already serves FINN before starting another instance.
4. Confirm that the key is configured using a boolean check only. Never print .env contents or include credentials in logs.
5. Run the existing verification commands:

cd /Users/aaryan/Desktop/ENAM/finn
python3 -m unittest discover -s tests -v
node --check static/app.js

6. If necessary, start the server:

python3 -m uvicorn app:app --host 127.0.0.1 --port 8000

7. Inspect the running frontend in a real browser now that restrictions have changed.

Acceptance: The existing archive → filing evidence → contact workflow works, and baseline tests pass.

### Phase B — Make primary-source company research work

Demo companies: TCS, Infosys, and Reliance.
Generalisation check: Asian Paints, outside the original portfolio.

1. Validate document discovery against actual Screener pages and company investor-relations pages.
2. Prefer direct company/exchange primary documents. Repair selectors and redirects based on observed responses.
3. Import the latest available annual report and two recent earnings-call transcripts for each demo company.
4. Preserve source URL, company, document type, financial period, and page numbers.
5. Where a source cannot be obtained, expose the missing coverage clearly and support manual PDF import. Do not substitute news, broker research, or model knowledge.
6. Show each company’s research coverage in the UI: available annual reports, transcripts, periods, and missing documents.
7. Verify discovery, import, and retrieval for Asian Paints without adding company-specific research logic.

Initial research outputs:

- Business and segment overview.
- Main growth and margin drivers.
- Cash-flow/debt observations where supported.
- Management outlook, risks, and questions to investigate.

Acceptance: Each demo company answers at least three questions using annual reports/transcripts, with correct company and page citations. Missing evidence produces a clear limitation.

### Phase C — Verify and strengthen AI analysis

1. Run one small real request using the configured API key.
2. Confirm that the returned mode is AI and both analyst and reviewer execute successfully.
3. Distinguish configuration, authentication, quota, model-access, timeout, parsing, and citation-validation failures in server diagnostics. Keep secrets out of logs and browser responses.
4. Maintain the evidence fallback, but make its reason clear to the user.
5. Keep the initial two-call architecture; do not add a debate loop to every request.
6. Require the reviewer to evaluate each claim against the passages it cites, not merely against any retrieved passage.
7. Preserve disagreement and uncertainty. Do not force investment recommendations or confidence scores.
8. Improve retrieval to select complementary evidence across documents and periods while retaining strict ticker/source filters.
9. Record request latency, model, token usage when available, cache hits, and reviewer rejections.

Acceptance: Manually inspect at least nine answers across the three demo companies. Material claims must be traceable to the cited passages, with no unsupported period comparisons or cross-company contamination.

### Phase D — Make live portfolio monitoring operational

1. Validate all 18 portfolio symbols against the chosen market-data source; correct stale symbols or replace unavailable ones while keeping 15–20 companies.
2. Fetch completed-session prices and volumes.
3. Verify daily price change and volume relative to the previous 20 sessions.
4. Repair NSE announcement ingestion against actual responses.
5. Support requested date windows through source queries or explicit coverage tracking; do not claim completeness from a source that only returns a limited recent slice.
6. Preserve publication time, original filing link, and source provenance.
7. Deduplicate repeated announcements.
8. Show last successful refresh, covered period, and source failures.
9. Keep archived and live data separate. Make the normal briefing default to the live 24-hour window; retain a clearly labelled archive demo.
10. Link imported live announcement PDFs back to their event records so the investor can continue directly into analysis.

Acceptance: At least one successful market refresh and announcement refresh are demonstrated. A genuine no-announcement window is acceptable when coverage is clearly reported.

### Phase E — Add an actual Push workflow

For the local prototype:

- Poll announcements every 15 minutes while the backend runs.
- Refresh completed-session market data after 16:00 Asia/Kolkata.
- Use one scheduler with overlapping-run protection.
- Persist refresh attempts and alert records.
- Create alerts only for newly encountered matching announcements or new qualifying trading sessions.
- Add an in-app unread-alert indicator and alert list.
- Respect configured categories and thresholds.
- Explain that monitoring pauses when the local backend stops.

Use deterministic calculations for thresholds. Do not use an LLM for price or volume arithmetic.

Acceptance: A controlled test crossing a threshold creates one alert; repeating the refresh creates no duplicate. Live source health and the observed trading date remain visible.

### Phase F — Complete the integrated Network experience

Retain synthetic profiles; the challenge explicitly permits them.

1. Document the investor’s starting input as structured contacts containing employment history, expertise, education, and explicitly known relationships.
2. Add a simple JSON contact import with an example file, allowing the network to be replaced without editing application code.
3. Support multiple employment entries with dates.
4. Explain each recommendation using relevant employer, sector, role, or expertise.
5. Display second-degree paths explicitly, such as investor → Rohan → Kavya.
6. Label employment/education overlaps as possible connections unless a relationship is explicitly recorded.
7. Show relevant contacts in both event detail and company research.
8. Keep suggested questions grounded in the contact’s stated expertise; do not invent personal knowledge.

Acceptance: Demonstrate an exact-company contact, a sector expert, a second-degree introduction, and a no-match response.

### Phase G — Product verification and submission preparation

1. Test at approximately 390px mobile width and desktop width.
2. Verify navigation, scrolling, dialogs, source links, PDF upload, saved events, settings, research progress, empty states, and failure states.
3. Remove horizontal overflow except within deliberately scrollable tables.
4. Keep presentation concise: a short finding, supporting evidence, and a clear next action.
5. Produce a repeatable five-minute demonstration script.
6. Make seed fixtures reproducible from a clean checkout; document or package required public documents without including private runtime data.
7. Update architecture, limitations, privacy/retention, model rationale, costs, and deployment documentation.
8. Prepare a public repository with .env, credentials, local databases, and private uploads excluded.
9. Gather actual coding-agent conversation exports/share links. Do not fabricate build history.
10. Prepare the covering email and submission checklist.

Hosting: Continue local-first as the user requested. Before publication, choose an accessible Python-compatible deployment and its access model with the user. Do not use a JavaScript-only host for the existing Python backend without an explicit migration decision.

## 3. Interface and data changes

Preserve existing endpoints and extend them where practical.

| Area | Planned changes |
|---|---|
| Research results | Add source coverage, model/fallback status, review outcome, and operational diagnostics safe for display |
| Documents | Add a coverage endpoint by ticker; retain type, period, URL, and page provenance |
| Announcement import | Associate imported document IDs with originating events |
| Refresh jobs | Persist source, start/end time, coverage window, outcome, and failure category |
| Alerts | Persist unique event/session identity, trigger reason, created time, and read state; provide list/read APIs |
| Network | Accept validated JSON contacts and employment histories; return explicit relationship paths |
| Settings | Preserve thresholds and categories; add monitoring enablement |

Use versioned, additive SQLite migrations. Preserve existing saved events, uploaded documents, settings, and contacts. Do not reseed over user changes.

## 4. Verification and definition of done

### Required automated checks

- Ticker and source-type isolation.
- Citation IDs map to existing document pages.
- Duplicate import and refresh are idempotent.
- Missing primary sources cannot produce unsupported company analysis.
- Model failures produce an explicit fallback.
- Reviewer removes unsupported findings.
- Archive records do not enter live windows.
- Date-window filtering and Asia/Kolkata market-session handling.
- Threshold baselines exclude the current trading session.
- Alerts are deduplicated.
- Imported network data is validated and connection paths are explainable.
- Database migration preserves existing user state.

### Required manual checks

- Three companies produce useful primary-source research.
- One additional ticker works without special-case code.
- Live feeds are exercised successfully.
- One proactive alert workflow works.
- Contact recommendations are integrated into Push and Pull.
- The entire journey works on a phone-sized screen.
- The evaluator can launch or access the prototype without developer intervention.

### Submission checklist

- [ ] Accessible mobile-first prototype.
- [ ] Public GitHub repository.
- [ ] Clear CS787 attribution and explanation of new work.
- [ ] Actual AI build-history exports or share links.
- [ ] Covering note describing scope, decisions, architecture, privacy, models, cloud, omissions, and next steps.
- [ ] No credentials or private runtime data in published artifacts.
- [ ] Submission prepared for assessment@enam.com.
- [ ] Subject: IIT Kanpur – Founding AI Engineer - 2027.

Sending the email requires explicit user instruction.

## 5. Defaults, priorities, and deferred features

Defaults: Keep FastAPI, SQLite, the current frontend, the configured model, and the analyst/reviewer workflow. Use real primary documents and synthetic contacts. Prioritise local reliability before deployment.

Priority order: Primary documents → verified AI research → live sources → proactive alerts → integrated network → mobile verification → submission.

Defer unless the core journey is complete:

- Full CS787-style multi-round debate.
- Four-quarter management promise tracker.
- General extraction of arbitrary financial tables.
- Automated management biographies.
- Voice interaction and elaborate graph visualisations.
- Broker/news sentiment analysis, which is unsuitable for the restricted Pull corpus.

The Reliance parser remains a disclosed, source-specific example. Never describe it as a general financial extraction engine.

Resume instruction for the next session:

> Read this plan and inspect the current FINN application. Preserve existing work and never print the API key. Begin with Phase A, then complete primary-source ingestion and verify real analyst/reviewer calls. Continue in phase order, updating verification evidence as work completes. Do not treat configured connectors or passing mocks as proof that live integrations work.
