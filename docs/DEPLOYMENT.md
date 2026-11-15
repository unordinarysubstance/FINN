# Free Render deployment

The user selected zero-payment hosting. The default render.yaml now uses one Free Docker web service, no attached disk, and temporary runtime storage at /tmp/finn. The password gate remains enabled and Render generates its secret. OPENAI_API_KEY is omitted so the default hosted demo makes no paid model calls. The existing local .env and local database are unchanged.

## What the free demo preserves

The image includes twelve archive filings, twelve primary PDFs and their public search index. A fresh workspace restores this corpus, the eighteen-company portfolio, five archive examples and synthetic contacts automatically. It does not restore private uploads, extra acquired documents, saved events, settings, alerts or model caches from a previous filesystem. The app displays this limitation whenever FINN_EPHEMERAL_DEMO=1.

Render Free sleeps after fifteen idle minutes and may take about a minute to resume. Its local filesystem is discarded on sleep, restart or redeploy. It cannot attach a persistent disk. Monitoring therefore runs only while the process is awake. [Official free-tier limits](https://render.com/docs/free).

Within an awake instance, research, acquisition, settings and alerts use the ordinary SQLite workflow. Persistent storage across those platform resets would require an external database/file-storage design; adding a database URL alone does not migrate this SQLite/FTS application. Do not interpret the free demo as always-on monitoring or durable investor storage.

## Deploy a new free service

No Render resources had been created when the user chose this configuration.

1. From the normal terminal in finn/, run python3 data/verification/push_github.py to upload the reviewed free configuration.
2. Sign in to your personal [Render dashboard](https://dashboard.render.com/) and authorize GitHub access to unordinarysubstance/FINN through the browser flow.
3. Choose New → Blueprint, connect FINN, choose main, and use render.yaml at the repository root. Leave any root-directory field blank. Review the proposed service: plan Free, no disk, Docker, Singapore, /healthz readiness, one instance. Create only that free service. [Blueprint instructions](https://render.com/docs/infrastructure-as-code).
4. Keep OPENAI_API_KEY unset for the zero-model-charge demo. The app uses evidence mode: original source passages, PDFs, contact matching and the reviewed numeric example remain available. If you later add your API key, AI requests use that provider account's credits/billing; Render's free compute does not cover them.
5. After the service becomes Live, open Environment and retrieve FINN_ACCESS_PASSWORD privately. Visit the actual onrender.com URL and log in as finn. Never put the password or API key in Git, a URL or chat.
6. Check /healthz returns {"status":"ok"} without login; the main app and APIs should require login. Try Archive → Reliance, an original PDF, Network search, and TCS source research on desktop and phone.
7. For a free-runtime reset check, save an archive event and restart the service. A genuinely replaced filesystem should restore the bundled corpus and reset that saved state. This is the expected temporary-demo behavior. Do not use the earlier persistent-disk restart criterion.

Do not add a payment method for this requested no-payment setup. Render documents suspension/build restrictions when included limits are exhausted without one. Check usage in its dashboard; no unlimited-usage promise is made. [Free usage handling](https://render.com/docs/free).

If an existing paid service or disk is ever involved, handle it separately before following these fresh-service instructions. Removing resource definitions from a Blueprint does not automatically delete existing resources. [Blueprint resource lifecycle](https://render.com/docs/infrastructure-as-code).

## Local development

```sh
FINN_REVIEW_MODEL=gpt-6.1-sol python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Local runtime data remains in data/ or FINN_DATA_DIR until the workspace owner removes it. The ephemeral-demo flag is enabled only in the free-hosting configuration. Authentication is optional locally and required in the Blueprint. Shared-demo authentication does not isolate multiple investors.

Only selected source passages/questions go to the optional model with store=False. Contact profiles are not sent. Real multi-user deployment still needs per-investor ownership, consented imports, deletion/export, retention controls and access auditing.
