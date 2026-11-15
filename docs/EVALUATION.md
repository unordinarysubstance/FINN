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

Each uncached request has at most two model passes, with no contact profiles in input. Gemini can make up to three HTTP attempts per pass for explicit transient server errors; an explicit per-minute quota with a retry hint gets one cooldown retry; daily/unknown quota and authentication errors are not retried. OpenAI requests use `store=False`; Gemini uses generateContent under Google's free-tier data terms. Pipeline 7 adds provider identity to the cache alongside evidence, periods, both model names and review effort. Old OpenAI results cannot stand in for a Gemini evaluation.

For a targeted check of the current provider use `python3 manage.py evaluate --symbols INFY --question-index 2`. To reproduce the historical OpenAI configuration, explicitly select `FINN_AI_PROVIDER=openai FINN_REVIEW_MODEL=gpt-6.1-sol`. Evaluation reports are archived before replacement. A structural pass always requires source inspection; model randomness, changing evidence or a different reviewer can change the outcome.

## Gemini migration and live smoke check

Pipeline 8 defaults both passes to Gemini Flash (`gemini-3.6-flash`). Offline HTTP tests cover authentication, JSON review schema, exact source-line copying, quota fallback, malformed/truncated output rejection, no paid-provider failover, model-specific caching and availability diagnostics. Earlier 3.8 requests encountered overload/timeouts. Research now has a configurable 120-second timeout per Gemini pass.

The owner passed the 3.6 availability probe in 3,664 ms, then completed a live filing smoke check in 9,384 ms. Analyst and reviewer each succeeded on the first attempt; the result was uncached, with no rejected or revised claims. The two passes used 10,571 input tokens and 1,084 output/thinking tokens in total.

The smoke answer has two retained findings from the combined archived TCS filing. Original PDF page 1 supports the June 2025 consolidated quarter's revenue, reported/constant-currency growth and operating cash conversion. Original PDF page 14 supports the September 2025 quarter's corresponding metrics. Both support spans independently match text extracted from those original pages. The first finding repeats its revenue growth label, but the retained metric labels, dates, units and bases are supported. This is one archived filing example, not a full annual-report/transcript or four-company Gemini acceptance run.

The private gemini-smoke-source-review.json binds this inspection to the exact smoke-report and PDF hashes. The first broader Gemini evaluation returned 2/12 structural passes: five per-minute quota failures and five analyst output-validation failures. Their original failure diagnostics omitted the validation reason, so the causes of the invalid outputs remain unknown. Full acceptance and original-page inspection of a successful batch remain pending. The historical OpenAI evaluation above remains historical evidence; it does not establish Gemini quality.

Pipeline 8 addresses batch transport and formatting: 15-second process-local pacing per model, one retry only for a confirmed minute limit with a bounded retry hint, strict analyst JSON Schema with evidence-only source IDs, and safe finish/block/JSON failure reasons. It preserves financial and source-line validation. Evaluation now prints progress for each answer and uses a new cache protocol version. The targeted TCS outlook rerun passed. The subsequent batch completed five structural passes before daily quota exhaustion; the remaining questions require a later run.

## Pipeline 8 batch: five passes, then daily quota

The next owner run produced structural passes for all three TCS questions and Infosys business/outlook. One was cached; four were freshly completed. Infosys cash flow completed its analyst but the reviewer hit a daily cap, and all six remaining requests also returned the same daily-cap error. Every quota error identifies a 20-request/day free-tier allowance. No analyst output-validation failures occurred before the quota stopped progress. This supports improvement on the five completed questions; all twelve and their factual accuracy are not yet established.

The private gemini-evaluation-daily-quota.json binds the 5/12 tally to the exact report hash. Evaluation now stops at the first confirmed daily quota and records later selections as not_attempted. Daily exhaustion has its own diagnostic code. Pipeline 8 cache identity is unchanged by this transport/reporting fix, so the five successful answers can be reused after the daily reset. A new 12-answer batch requires up to 24 generation calls, exceeding the observed daily cap; completing it across resets with the same local cache is the zero-payment path.
