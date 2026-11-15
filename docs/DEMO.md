# Five-minute demonstration

This script separates the working local archive journey from checks still requiring a network-enabled runtime. Do not present empty primary coverage or mocked tests as a completed live demonstration.

The packaged corpus is ready offline. For AI research, configure Gemini using [GEMINI.md](GEMINI.md) and start the server normally. The historical OpenAI twelve-answer evaluation and desktop/mobile browser run have completed; Gemini live evaluation is pending. inspect their recorded limits in VERIFICATION.md. Before recording, refresh source health if needed and show its actual outcome. Six latest transcript candidates remain unverified; use the clearly dated indexed corpus. A fresh demo has no private cached answers, prices or alerts, so live feeds and AI requests require outbound network access.

1. **0:00–0:45 — Daily attention.** Open Briefing. Show the default live 24-hour window, source health, routine-event collapse and unread alerts. Explain observation dates and incomplete coverage. If sources failed, show that failure plainly.
2. **0:45–1:45 — Evidence behind an event.** Choose Archive → Reliance → “Profit growth deserves a closer look.” Open the original page and calculated QoQ/YoY table. Point out the investment-sale disclosure and recurring-earnings question. This is a reviewed historical table, not a general extractor.
3. **1:45–2:30 — A person who adds context.** Show Ananya’s exact-company experience and suggested question. From TCS research or Network, show Rohan → Kavya as an explicitly recorded second-degree path. All seeded people are synthetic.
4. **2:30–3:45 — Research.** Choose TCS or Infosys with Annual reports & transcripts. Show source coverage, select periods, ask about cash flow versus profit, and open a cited PDF page. Show analyst/reviewer diagnostics and literal support quotes. Only call it AI research if the result says AI and both passes completed. Repeat briefly with Asian Paints to demonstrate another ticker with its indexed annual report and transcripts. Explain that some answers are partial and guidance can be conservatively withheld.
5. **3:45–4:30 — Proactive attention.** Show persistent alerts, mark one read, and refresh to demonstrate no duplicate. Change thresholds and watched categories. Explain that monitoring runs in the backend every 15 minutes, and prices are checked after 16:00 IST. No email or device push is implemented.
6. **4:30–5:00 — Product boundaries.** Demonstrate an unknown company returning missing evidence and a network theme returning no match. Mention privacy, cost controls, and the remaining live validation/deployment gaps.

## Phone QA checklist

Chrome interaction checks passed at 390×844 and 1440×1000, with no page errors. Representative screenshots were inspected. Research in that browser run used evidence mode; real AI was tested separately through the CLI. Physical phone/Safari testing has not been performed.

At 390×844 and desktop width, exercise all four views; saved/read states; live/archive switches; every period filter; alert dialog and read action; empty/error states; settings; PDF upload; source discovery and confirmation; event PDF attachment; research progress and cache hits; JSON contact import; original-source links; keyboard focus and dialog Escape. Check page width equals viewport except intentionally scrollable tables; check bottom navigation does not cover actions. Confirm tap targets and long company names/source URLs.

Use synthetic data during phone demos. Keep the backend on a trusted machine and protect access before sharing beyond the local device.

## Automated browser checks

Use `python3 -m pip install -r requirements-dev.txt`, then `python3 browser_qa.py` from the normal terminal. Playwright uses installed Chrome; no browser download is required when Chrome is available. The runner uses a temporary database copy and disables model calls and monitoring. Reports/screenshots are in data/verification/browser and excluded from publication. This checks real browser interaction and responsive widths with evidence-mode research; live AI factual checks remain a separate evaluation. Review the screenshots as well as the report before claiming visual acceptance.
