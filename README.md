# FINN

FINN is an investment research app built for the ENAM Founding AI Engineer challenge. It brings together portfolio announcements, company documents and the people in an investor’s network who might help explain what is happening.

[Open the demo](https://finn-rzzb.onrender.com/) · [Requirement audit](docs/CHALLENGE_AUDIT.md)

The demo uses a shared login; access details are shared separately with evaluators. It runs on Render Free, so saved events, settings and extra downloads can reset when the service sleeps or restarts. The bundled company documents are restored on startup. A notice in the app explains this.

## A quick way to try it

Start in **Briefing**, switch to **Archive**, and open Reliance’s “Profit growth deserves a closer look.” The results table links back to the original filing. It also points out the investment-sale disclosure and suggests a relevant contact to speak with.

In **Research**, enter an NSE ticker and ask a question. FINN looks for an annual report and two earnings-call transcripts, checks the PDFs, indexes their pages and uses that evidence to answer. HDFC Bank and Maruti Suzuki both passed this acquisition flow outside the original four-company research demo. Some sites block downloads or publish formats the parser cannot read; those gaps are shown in the result. You can also import a PDF yourself.

**Network** searches the mock contacts by company, sector or expertise. Try `IT Services` to see the recorded introduction path from Rohan to Kavya. All ten seeded contacts are synthetic. Shared employment alone does not create a relationship.

**Portfolio** contains eighteen companies across several sectors. Price and volume thresholds, watched announcement categories and saved/read states are configurable. Alerts are kept in the app; no messages are sent to contacts.

## Run locally

Use Python 3.12 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000. The checkout includes 24 public PDFs and their search index, so the archive and document-search demo work without downloading them again. API documentation is at `/docs`.

An API key is optional. Without one, Research returns source passages and PDF links. Generated answers now use Gemini Flash for both drafting and review. Follow [the Gemini setup](docs/GEMINI.md) to create a free-tier Google AI Studio key, then add it to your local `.env` or Render's secret environment. Keep an existing `.env` intact and leave it out of Git.

The default model is `gemini-3.8-flash`. Each uncached answer has two model passes, with up to three HTTP attempts per pass for temporary server failures; a quota or validation failure returns source evidence. FINN never switches to OpenAI automatically. Free API access has usage limits and depends on your Google project's eligibility. Keep billing disabled if you want no API charges. Google may use free-tier inputs and outputs to improve its products; questions and selected document passages are sent, while contact profiles stay local.

OpenAI remains available only through an explicit `FINN_AI_PROVIDER=openai` setting. The earlier twelve-question evaluation used OpenAI; Gemini needs its own live evaluation once your key is configured.

## How it works

The backend is FastAPI, with SQLite/FTS5 for document search and a plain JavaScript frontend. There is no frontend build step. Background jobs handle downloads and research, while a single scheduler checks announcements and completed-session market data when the backend is running.

Screener and Yahoo help locate companies and documents. Pull research itself uses issuer or exchange PDFs: annual reports and call transcripts, with company, document type and reporting period kept separate. Broker commentary and news are not retrieved, and the model is instructed to stay within the supplied passages.

Generated answers use two model passes. Temporary Gemini server failures get at most two retries per pass, with short backoff; quota/authentication failures stop immediately. A reviewer checks each draft finding against its own citations and selects supporting source lines. Python validates those references and copies the quotations. Answers are cached against their evidence and model configuration. These checks reduce mistakes, but they do not establish that an answer is complete or financially correct.

The network stays in the workspace and is not included in model requests. You can import contacts using the format in [examples/contacts.json](examples/contacts.json). The hosted password gate protects one shared demo workspace; a real multi-investor product would need individual accounts, ownership checks and consent/deletion controls.

## What is still limited

Announcement coverage is partial. The NSE date-range endpoint returned 403 during live testing, so the app also reads the exchange’s recent RSS feed and configured company IR pages. A short RSS snapshot cannot prove that every filing in a requested window has been captured. Source health and failures stay visible.

The Reliance results table is a parser for one reviewed archived filing, not a general financial-table extractor. Research can return incomplete answers, and some current transcript links remain inaccessible. There is no automatic OCR, four-quarter promise tracker, executive biography scraper or device/email push notification.

Local state persists in `data/` or `FINN_DATA_DIR`. The free hosted demo has temporary runtime storage, and monitoring pauses while it sleeps. It defaults to evidence mode unless an API key is added. The [deployment notes](docs/DEPLOYMENT.md) cover those choices and the access gate.

## Checks and useful commands

```sh
FINN_DISABLE_MONITOR=1 python3 -m unittest discover -s tests -v
node --check static/app.js
python3 manage.py check-ai
python3 manage.py acquire --symbols HDFCBANK MARUTI
python3 manage.py refresh --days 30
```

For browser checks, install `requirements-dev.txt` and run `python3 browser_qa.py` with Chrome installed. It uses a temporary database copy and disables external acquisition, monitoring and model calls.

The latest suite passed 123 tests, including offline Gemini transport and citation checks. Desktop and phone-width browser runs passed, all eighteen price feeds refreshed, and both HDFC Bank and Maruti acquired an annual report plus two transcripts. The hosted readiness, source links, research and Network flow were confirmed by the owner. A twelve-question AI evaluation passed structural checks; its source review and remaining answer-quality issues are recorded in [EVALUATION.md](docs/EVALUATION.md). A pass count is not an accuracy score.

Reports under `data/verification/` are private. [VERIFICATION.md](VERIFICATION.md) summarises the evidence; [DEMO.md](docs/DEMO.md) has the walkthrough. `python3 package_submission.py` builds an allowlisted source archive with public documents and a file-hash manifest, excluding credentials and investor runtime data.

## Background

FINN draws on CS787 AlphaAgents by Aamir Ahmad, Aaryan Maheshwari, Aviral Gupta, Pallav Rastogi and Suyash Kapoor. It is a separate application with a smaller research pipeline, using scoped evidence, deterministic calculations and review before synthesis. The original project and its attribution are preserved. Company PDFs retain their original provenance.
