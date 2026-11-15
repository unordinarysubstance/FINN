# Research evaluation record

Checked 12 November 2026. Four companies, three questions each: business/segments, management outlook/margins, and cash flow/profit/working capital/debt.

## Latest real batch

The user ran `FINN_REVIEW_MODEL=gpt-6.1-sol python3 manage.py evaluate`. All twelve answers completed the analyst/reviewer workflow and passed structural checks using `gpt-4o-mini` for drafting, `gpt-6.1-sol` with low effort for review, and pipeline 6. Eleven answers were uncached; Asian Paints business analysis reused the earlier stronger-reviewer result. Seven drafts were withheld and 41 findings retained.

The assistant inspected each retained finding and its supporting lines, then independently extracted the corresponding original PDF pages. All 67 selected support spans matched the originals. This establishes quote provenance, not a 100% factual-accuracy score or independent human approval.

| Answer | Source inspection and practical limits |
| --- | --- |
| TCS businesses | Reportable segments and dated BFSI/consumer commentary supported. Demand drivers are partial. |
| TCS outlook | Supported dated Q1 FY2026 revenue decline/margins and FY2026 risk commentary; the source periods differ and are stated. |
| TCS cash flow | FY2026 consolidated profit ₹49,454 crore and net operating cash flow ₹52,094 crore match PDF page 172. ₹66,478 crore is correctly labelled cash generated from operations before the displayed tax deduction. Working-capital/debt coverage is thin. |
| Infosys businesses | Segment descriptions and dated spending priorities supported; not a full segment performance analysis. |
| Infosys outlook | Only the cautious-spending interpretation survived. Guidance is present in the source but was conservatively withheld because FY27 was not matched to FY2027 by numeric validation. This is an incomplete answer. |
| Infosys cash flow | Consolidated profit ₹29,474 crore and net operating cash flow ₹33,986 crore match PDF page 294. Standalone no-borrowings disclosure is explicitly distinguished from group working capital. |
| Reliance businesses | O2C definitions, FY2024-25 net-of-GST segment revenue and FY2025-26 digital drivers supported. Historical figures are not presented as current-year figures. Coverage omits some segments. |
| Reliance outlook | FY2025-26 O2C revenue/EBITDA commentary supported. Margin expectations come from a historical Q1 FY2026 call, whose period is visible in the citation; read them in that context rather than as current consolidated guidance. |
| Reliance cash flow | FY2025-26 standalone net operating cash flow ₹79,059 crore and profit before tax ₹54,076 crore correctly labelled. Ratios match the cited annual-report discussion; this is not a consolidated cash-conversion or comprehensive debt-risk assessment. |
| Asian Paints businesses | Kitchen/bath/industrial JV descriptions and historical product strategy supported. The unconfirmed analyst premise of an 85/15 repainting/new-home split was rejected. The main decorative-paints overview remains incomplete, with repetitive bath coverage. |
| Asian Paints outlook | Historical demand, margin and pricing commentary supported. Guidance and outlook are dated by transcript citation and must not be treated as current promises. |
| Asian Paints cash flow | FY2025-26 consolidated profit before tax ₹6,003.44 crore and net operating cash flow ₹7,088.18 crore match PDF page 236. Liquidity framework supported, but two findings repeat and specific working-capital risks are not resolved. |

One unreviewed analyst limitation incorrectly said no explicit Infosys guidance was available. That is contradicted by the cited Q2 FY2027 transcript, which prints 1–2% constant-currency revenue growth and 20–22% operating-margin guidance. The code now replaces unreviewed analyst caveats with an accurate deterministic retrieval-scope notice, for both fresh and cached answers. It does not add those withheld guidance claims or alter the evaluated model findings. Offline SDK/cache regression checks verify the correction without another paid batch.

The private `source-review.json` records the exact evaluated report hash, original-PDF support checks and per-answer notes. The original evaluation output is preserved. This inspection supports use as a prototype with disclosed limits, not a claim that every question has been answered completely.

## Protocol and failure history

Earlier mini-only runs passed structural checks while containing substantive errors: before/after working-capital cash flow conflation, debt claims attached to unrelated passages, aggregate liquidity renamed cash equivalents, omitted financial bases, analyst questions treated as disclosures and unsupported product-launch causality. Those batches are not accepted as source-grounded demonstrations.

Retrieval now restores page context and financial headings, promotes actual cash-flow statements, diversifies documents and preserves company/type/period filters. The reviewer receives only the evidence cited by each draft claim and may narrow it. Strict JSON Schema constrains source IDs; one-based source-line ranges replace brittle model-copied quotations. Python validates each range, copies real source lines, checks numerical literals and prunes unsupported references. Rejected drafts remain available for diagnosis, separate from final findings.

Matching lines cannot establish semantic completeness. Numeric checks can also reject valid abbreviations or references, which is why the evaluation records useful omissions as well as supported claims. Improving abbreviation handling, period labels, duplicate findings and business-segment completeness is further quality work.

## Usage and repeatability

The latest eleven uncached answers used 100,139 analyst tokens and 86,660 reviewer tokens, including output usage reported by the provider. Their measured latency ranged from about 9.5 to 23.2 seconds. The cached answer returned in 43 ms. These observations depend on request evidence and provider conditions; no invoice-derived cost or deterministic pass rate is claimed.

Each uncached request has at most two model passes, with no contact profiles in input. Gemini can make up to three HTTP attempts per pass for explicit transient server errors; quota/authentication failures are not retried. OpenAI requests use `store=False`; Gemini uses generateContent under Google's free-tier data terms. Pipeline 7 adds provider identity to the cache alongside evidence, periods, both model names and review effort. Old OpenAI results cannot stand in for a Gemini evaluation.

For a targeted check of the current provider use `python3 manage.py evaluate --symbols INFY --question-index 2`. To reproduce the historical OpenAI configuration, explicitly select `FINN_AI_PROVIDER=openai FINN_REVIEW_MODEL=gpt-6.1-sol`. Evaluation reports are archived before replacement. A structural pass always requires source inspection; model randomness, changing evidence or a different reviewer can change the outcome.

## Gemini migration

Pipeline 7 defaults both passes to Gemini Flash (`gemini-3.6-flash`). Offline HTTP tests verify request authentication, JSON review schema, exact source-line copying, quota fallback, malformed/truncated output rejection, no paid-provider failover, and model-specific caching. These tests establish integration behavior, not live Gemini answer quality. A Gemini key was not present during initial implementation. The owner subsequently ran a live smoke test: Google returned HTTP 503 UNAVAILABLE before synthesis, so successful smoke completion, full evaluation and original-page inspection remain pending. Historical OpenAI acceptance results above are preserved as historical evidence.

The following owner smoke attempt timed out after about 45 seconds. Gemini research now uses a configurable 120-second default for both passes, and check-ai provides a separate small provider probe. Neither the reported failures nor offline transport tests establish Gemini answer quality; successful full research and source inspection are still required.

The owner subsequently passed the tiny structured-JSON availability probe using gemini-3.6-flash in 3,664 ms on the first attempt. That model is now the default for both passes. This does not replace full research smoke/evaluation or source inspection.
