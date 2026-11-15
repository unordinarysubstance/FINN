To: assessment@enam.com
Subject: IIT Kanpur – Founding AI Engineer - 2027

Draft: add your name, actual AI-session links/exports and the demo password directly in the submission email. Confirm repository visibility before sending. No email has been sent.

Hello ENAM team,

I’m submitting FINN, a mobile-first investment research app that connects a portfolio event to the original company document and someone in the investor’s network who might help explain it.

Prototype: https://finn-rzzb.onrender.com/
Login: finn — [PROVIDE THE DEMO PASSWORD PRIVATELY IN THE EMAIL]
Repository: https://github.com/unordinarysubstance/FINN
AI build history: [ACTUAL SESSION SHARE LINKS OR ATTACHED EXPORTS]

The app follows eighteen companies, prioritises announcements and creates in-app alerts for configured categories and unusual end-of-day price/volume moves. Research accepts NSE company tickers beyond the demo set, acquires available annual reports and call transcripts, and links findings to original PDF pages. Synthetic contacts appear inside events and research, with reasons to reach out and explicitly recorded second-degree introductions. Contacts can also be searched directly or imported as JSON; I did not scrape LinkedIn.

The backend is FastAPI with SQLite/FTS5, original PDF files and a plain JavaScript frontend. Optional AI analysis uses a cheap drafting pass and a stronger evidence-review pass, bounded to two calls and cached against the exact evidence and model configuration. The tested pair is gpt-4o-mini and gpt-6.1-sol. Source-line checks and deterministic financial arithmetic constrain the model; network profiles are not sent to it.

The hosted demo uses Render Free with a shared password gate. It works without a model key in evidence mode, and user changes can reset when the service sleeps or restarts; bundled public documents restore automatically. Monitoring runs only while the backend is awake. A production version would need durable storage, per-investor ownership, individual authentication and consent/deletion controls.

Validation includes 102 passing tests, desktop/phone-width browser checks, live acquisition for HDFC Bank and Maruti, all eighteen price feeds and owner-confirmed hosted workflows. The twelve-answer AI evaluation passed structural checks, while source inspection recorded incomplete answers and reviewer mistakes. Announcement coverage is partial when NSE denies access. The Reliance numeric parser supports one reviewed filing; it is not a general table extractor. I left out the four-quarter promise tracker, executive biographies and outbound notifications to keep the main journey working.

The design builds on CS787 AlphaAgents by Aamir Ahmad, Aaryan Maheshwari, Aviral Gupta, Pallav Rastogi and Suyash Kapoor. FINN is separate code with a smaller research pipeline; the original project and attribution are preserved.

Regards,
[YOUR NAME]
