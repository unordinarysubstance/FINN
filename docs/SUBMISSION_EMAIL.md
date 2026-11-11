To: assessment@enam.com
Subject: IIT Kanpur – Founding AI Engineer - 2027

Draft — replace bracketed fields and finish the verification checklist before sending. No email has been sent.

Hello ENAM team,

FINN is a mobile-first investment desk built around a short journey: portfolio event → original-source evidence → someone in the investor’s network who can add context.

Prototype: [DEPLOYED URL]
Public repository: [GITHUB URL]
Actual AI build history: [CONVERSATION EXPORTS OR SHARE LINKS]

The prototype uses FastAPI, SQLite/FTS5 and a plain JavaScript interface. It has historical company filings, company-scoped PDF retrieval with page citations, an optional analyst/reviewer model workflow, configurable monitoring with persisted in-app alerts, and explainable contact matching inside event and research views. Synthetic contacts include employment histories and explicit second-degree relationships. Shared employment is not treated as proof that people know each other.

The source-reviewed configuration uses gpt-4o-mini for drafting and gpt-6.1-sol for review. Retrieval and threshold arithmetic are deterministic. Model work is bounded to an analyst and a reviewer; the reviewer selects supporting source lines separately for each claim. Successful answers are cached by evidence, models and pipeline version. Only source passages and questions leave the backend; network profiles stay local. Source failures and missing research coverage remain visible.

The implementation is local-first. [DESCRIBE ACTUAL HOST AND ACCESS MODEL AFTER DEPLOYMENT.] Runtime data and secrets are excluded from the repository. Real multi-user deployment would need investor-level access control, consented imports, deletion/retention controls and encrypted storage.

I prioritised the integrated workflow over a general financial-table parser, a multi-round debate engine or automated outreach. The Reliance results parser is source-specific. The packaged corpus contains four annual reports, eight transcripts and twelve historical filings. All eighteen price feeds refreshed, and the official-company fallback imported ten Reliance announcements with five alerts. NSE returned HTTP 403, so announcement coverage is partial (Reliance only). The twelve-question AI run passed structural checks; assistant source inspection matched 67 support spans to original PDFs and recorded incomplete answers. Chrome interaction checks passed at desktop and phone widths. Full validation details and remaining transcript, research and deployment limits are in VERIFICATION.md.

The design draws on CS787 AlphaAgents by Aamir Ahmad, Aaryan Maheshwari, Aviral Gupta, Pallav Rastogi and Suyash Kapoor. The original project is preserved; FINN is a separate application using the supplied archived public filing corpus and a smaller bounded research pipeline.

Regards,
[YOUR NAME]
