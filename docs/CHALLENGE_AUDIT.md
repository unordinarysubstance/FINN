# Challenge requirement audit — submission review

Latest submission checks: [FINAL_STATUS.md](FINAL_STATUS.md). Historical runs below retain their actual outcomes.

Checked against all five pages of `1. ENAM_Founding AI Engineer Build Challenge_Main.pdf`. The brief requires a focused working prototype with Push, Pull and Network; its long feature menus are explicitly optional.

## Required product and data

| Requirement | Implementation and evidence | Limit or outstanding verification |
| --- | --- | --- |
| Mobile-first prototype, pp. 1/4/5 | Four responsive views. Earlier Chrome checks passed at 1440px and 390px. | User rerun passed at both widths after acquisition/access changes; Hosted readiness, login, PDF links, research and Network were subsequently confirmed by the owner; independent physical-device coverage is not claimed. |
| 15–20 portfolio companies, p. 2 | Eighteen followed companies across sectors; add/remove controls. All eighteen price feeds passed a real refresh. | Observations keep their actual dates. |
| 3–5 research demo companies, p. 2 | TCS, Infosys, Reliance and Asian Paints; four annual reports, eight transcripts; real two-pass AI evaluated. | Six newer transcript candidates remain unverified. Historical periods stay explicit. |
| Generalise beyond demo tickers, p. 2 | Research now automatically discovers, verifies and imports available issuer/exchange PDFs for the entered ticker. Includes directory fallbacks, official-site crawl, progress and retries. An unseeded-ticker API test returns acquired primary evidence without changing the portfolio. | Real HDFCBANK acquisition passed (one annual report/two transcripts); MARUTI annual report imported. Generic viewer resolution fixes its transcript-format failure; the targeted live retry passed with both transcripts. All twelve bundled PDF validators also passed. Availability/layouts still vary. |
| EOD price/volume, p. 2 | Yahoo completed sessions, previous twenty-session volume baseline, split suppression, persisted health. | EOD, not intraday. |
| Corporate announcements, p. 2 | NSE date-range API, new official NSE RSS fallback across followed companies, then company-IR fallback. Links/times, classification and idempotent alerts. | API previously returned 403. Real IR fallback success covers Reliance only. Live RSS retrieval/parsing passed on a short overnight feed without portfolio matches; its finite history cannot prove complete window coverage. Configured issuer pages now supplement a successful RSS response. |
| Annual reports/transcripts, pp. 2/3 | PDF originals, page citations, provenance and automatic acquisition. Screener/Yahoo only locate links; secondary commentary never enters synthesis. | No model-memory substitution, broker/news analysis or automatic OCR. |
| Legitimate Network data, p. 2 | Ten labelled synthetic contacts, JSON import, employer dates, expertise, education and explicit relationships. | No LinkedIn scraping or invented real relationships. |
| At least one Push workflow, p. 4 | Backend monitoring, configurable thresholds/categories, persistent deduplicated alerts, read state; live alerts observed. Digest defaults to 24 hours and collapses routine items. | Monitoring pauses with the backend; no device/email or intraday push claim. |
| At least one Pull workflow, pp. 3/4 | Company/period-scoped business and cash-quality research, per-claim model review, supporting source lines and PDF links. | Some answers are incomplete/repetitive. Structural passes do not establish factual accuracy. |
| Integrated and directly queryable Network, pp. 1/3/4 | Relevant contact cards and reasons inside events/research; direct theme/company/person search and explicit second-degree paths. | Shared employment never invents a relationship. No automatic outreach. |

## Required writeup and delivery

| Requirement | Current state |
| --- | --- |
| Pipelines and source linking | README plus ARCHITECTURE.md describe the pipelines, diagram, provenance and event/contact integration. |
| Privacy, retention and real consent/access control | README/DEPLOYMENT explain storage, model inputs, persistence, consent/deletion and ownership gaps. New shared-demo password gate protects UI/documents/APIs; it is not multi-user isolation. |
| Models, agents, cost and efficiency | Two bounded model passes, configurable routing, evidence/model-aware cache, measured usage and quality limits in EVALUATION.md. |
| Cloud choices | User-selected Free Render Blueprint: no disk, temporary runtime, generated access secret and readiness route. Reset behavior is visible. Free deployment is live at https://finn-rzzb.onrender.com/ with owner-confirmed core workflows. |
| Phone-accessible delivered prototype | Local responsive app and portable corpus work. Hosted URL: https://finn-rzzb.onrender.com/; core workflows confirmed by the owner. |
| Public GitHub repository | The authenticated owner CLI confirmed `unordinarysubstance/FINN` is public. Publication uses the GitHub CLI with a full-history credential/public-corpus audit and remote-commit verification. Confirm the final reviewed version is on main before sending the email. No force push is required. |
| Actual AI build history | A genuine redacted export of the recorded FINN Codex conversation is prepared privately as FINN_AI_BUILD_HISTORY.zip. It contains visible user/assistant messages, with credentials and local home paths redacted; hidden instructions/reasoning and tool payloads are omitted. Attach the actual export; it is excluded from the public repository. |
| Covering email | The covering note uses the actual hosted/repository links, Aaryan Maheshwari as the configured author, and the prepared history attachment. The owner must add the shared demo password privately in the email and send it. No email has been sent. |

## Optional examples deliberately left out

The four-quarter promise tracker, general financial-table extraction, every guidance/bull/bear output, automatic executive biographies, voice and an elaborate network graph are optional examples, not mandatory missing features. The archived Reliance numeric parser is source-specific. The generic Pull journey uses primary PDF evidence. These limits are disclosed rather than presenting unimplemented examples as working features.

## Final live verification

```sh
# Run in the normal terminal after restarting the updated app:
python3 manage.py acquire --symbols HDFCBANK MARUTI
python3 manage.py refresh --days 30
python3 browser_qa.py
```

Inspect individual failures in `data/verification/acquire.json` and `refresh.json`; partial status remains a coverage gap. Try a non-demo company in Research and open its acquired source pages. After Render deployment, test authentication, phone navigation, source access and the documented free-runtime reset behavior. Fill actual delivery links before declaring the submission complete.
