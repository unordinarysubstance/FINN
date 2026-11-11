# Local run and deployment preparation

FINN remains a local FastAPI/SQLite application. No host or public repository has been created. Sites hosting expects a static site or JavaScript Worker; this Python backend has not been migrated to that runtime.

## Local

Use Python 3.12+, install `requirements.txt`, then run:

```sh
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Put optional credentials in `.env`; never commit it. Monitoring starts with the backend and stops with it. Use one worker. SQLite and original PDFs live in `FINN_DATA_DIR` (default `data/`). Back up this directory together, not the SQLite file alone while the app is writing.

## Reviewable container configuration

The submission bundle contains twelve archived public PDFs under `demo_documents/`, twelve annual-report/transcript PDFs under `demo_primary/`, and a generated public-only SQLite/FTS index under `demo_data/`. First startup copies the index only when no investor database exists and resolves its relative PDF paths. It then adds the synthetic demonstration contacts and five historical events. The corpus works without a sibling CS787 checkout or network access. A clean extraction, all original-PDF endpoints, evidence retrieval and saved-state preservation across restart have passed in-process checks. The source workspace can also seed from `../CS787-main/company_assets`.

```sh
python3 package_submission.py
# Extract dist/finn-submission.zip into a clean directory, then from its finn/ folder:
docker build -t finn-demo .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -v finn-data:/data finn-demo
```

Set `FINN_REVIEW_MODEL=gpt-6.1-sol` alongside `OPENAI_API_KEY` to use the source-reviewed model pair. The default without this setting uses the analyst model for both passes. Public PDFs can live in the image; investor state and newly imported documents belong on the persistent `/data` volume.

The container configuration is prepared but has not been built in this restricted session. `.dockerignore` excludes local secrets and runtime data. Never bake credentials into an image. Store them in the host's secret manager/environment. A real host needs outbound HTTPS, a persistent volume, a long-running single process, and TLS. Ephemeral/serverless workers without a persistent volume or scheduler are unsuitable for this implementation.

Before making the prototype internet-accessible, configure an authenticated reverse proxy or equivalent access gate. This version has no application authentication or per-user ownership; keep real network data out of a publicly accessible demo. Use an isolated synthetic demo database. Monitor source health after deployment; do not interpret a running process as proof of working feeds.

## Data and retention

Only selected primary-source passages and the question go to the configured model, using `store=False`. Contact profiles stay in SQLite and are never included in model input. Local documents, profiles, saved events, jobs, alerts and caches persist until the workspace owner removes them; no automatic expiry is claimed. Full research reports in `data/verification` can contain questions, excerpts and contacts and are excluded from publication.

For a real multi-user service: separate each investor's ownership at every query; use consented profile imports with deletion/export; define retention periods; encrypt disks/backups; audit access; manage credentials server-side; and add access-controlled original-document downloads. These are deployment work, not existing capabilities.
