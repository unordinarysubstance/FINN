To: assessment@enam.com
Subject: IIT Kanpur – Founding AI Engineer - 2027
Attachment: FINN_AI_BUILD_HISTORY.zip

Submission draft: add the demo password privately in the email. The actual redacted history attachment is prepared under data/verification/submission/. No email has been sent.

Hello ENAM team,

I'm submitting FINN, a phone-friendly investment research prototype built around one journey: notice a portfolio event, open the company's evidence, and find someone in your network who can help explain it.

Demo: https://finn-rzzb.onrender.com/
Username: finn
Password: [ADD THE RENDER DEMO PASSWORD PRIVATELY IN THIS EMAIL]
Public repository: https://github.com/unordinarysubstance/FINN
AI build history: attached FINN_AI_BUILD_HISTORY.zip, exported from the actual coding conversation with credential redactions.

FINN follows eighteen companies. Briefing prioritises announcements and creates in-app alerts for configured event categories or unusual completed-session price/volume changes. Research accepts NSE tickers beyond the demo set, acquires available issuer annual reports and call transcripts, and links findings to original PDF pages. Network suggestions appear inside events and research, with reasons and explicit second-degree paths. The ten demo contacts are synthetic; I did not scrape LinkedIn.

The backend is FastAPI with SQLite/FTS5 and original PDF files; the frontend is plain JavaScript. Acquisition, financial arithmetic, alert rules and contact matching are deterministic code. Gemini 3.6 Flash drafts research and checks it in a second pass; Python validates its source-line references and numerical literals. Both passes use scoped primary evidence, and no contact profiles are sent to the model. Exact-evidence caching and request pacing keep the free-tier API usable. Google's free-tier data terms remain a limit for confidential questions/uploads.

The current Gemini filing smoke passed, with both findings checked against original pages. Five company research answers passed structural checks, and their 35 support spans match the original PDFs; the remaining full-batch checks were previously blocked by the daily free quota and still need the resumed run. The automated suite passes 135 tests. Desktop/phone-width browser checks, new-company acquisition, all eighteen price feeds and core hosted workflows have also been exercised. The verification notes distinguish these checks from factual completeness.

I chose Render Free to keep the prototype at zero hosting cost. It can sleep and reset runtime files; bundled documents restore automatically, and the app explains that limitation. The shared login protects this demo workspace, not separate investors. A production version needs durable storage, individual accounts, per-investor ownership, consent/deletion controls and ingestion workers that run independently of the web app. Announcement coverage remains partial when exchange endpoints deny access.

I deliberately left out a general financial-table extractor, a four-quarter promise tracker, executive biographies and outbound notifications. I'd improve source coverage and durable/private workspaces before expanding that menu. The repository's architecture note explains the pipelines and tradeoffs. FINN builds on the CS787 AlphaAgents project; its original team and attribution are preserved.

Regards,
Aaryan Maheshwari
