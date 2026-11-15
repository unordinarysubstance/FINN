# Free Render deployment

Hosted URL: https://finn-rzzb.onrender.com/. The owner confirmed readiness, login, archive PDF access, research citations and Network search on 15 November. This is owner verification; independent HTTP fetches from the assistant environment were unavailable.

The user selected zero-payment hosting. The default render.yaml now uses one Free Docker web service, no attached disk, and temporary runtime storage at /tmp/finn. The password gate remains enabled and Render generates its secret. Gemini Flash is the default AI provider. API keys are omitted from the Blueprint, so the demo shows evidence until a key is added privately. The existing local .env and local database are unchanged.

## What the free demo preserves

The image includes twelve archive filings, twelve primary PDFs and their public search index. A fresh workspace restores this corpus, the eighteen-company portfolio, five archive examples and synthetic contacts automatically. It does not restore private uploads, extra acquired documents, saved events, settings, alerts or model caches from a previous filesystem. The app displays this limitation whenever FINN_EPHEMERAL_DEMO=1.

Render Free sleeps after fifteen idle minutes and may take about a minute to resume. Its local filesystem is discarded on sleep, restart or redeploy. It cannot attach a persistent disk. Monitoring therefore runs only while the process is awake. [Official free-tier limits](https://render.com/docs/free).

Within an awake instance, research, acquisition, settings and alerts use the ordinary SQLite workflow. Persistent storage across those platform resets would require an external database/file-storage design; adding a database URL alone does not migrate this SQLite/FTS application. Do not interpret the free demo as always-on monitoring or durable investor storage.

## Deploy a new free service

No Render resources had been created when the user chose this configuration.

1. Ensure the reviewed free configuration is committed and pushed to the repository branch you will deploy. The current FINN demo uses main.
2. Sign in to your personal [Render dashboard](https://dashboard.render.com/) and authorize GitHub access to unordinarysubstance/FINN through the browser flow.
3. Choose New → Blueprint, connect FINN, choose main, and use render.yaml at the repository root. Leave any root-directory field blank. Review the proposed service: plan Free, no disk, Docker, Singapore, /healthz readiness, one instance. Create only that free service. [Blueprint instructions](https://render.com/docs/infrastructure-as-code).
4. For generated answers, follow [Gemini setup](GEMINI.md) and add GEMINI_API_KEY privately in Environment. Use a free-tier Google AI Studio project without billing. Set FINN_AI_PROVIDER=gemini and FINN_GEMINI_MODEL=gemini-3.8-flash; remove any hosted OPENAI_API_KEY. Without a Gemini key, evidence mode remains available. Render hosting and Google API quotas are separate.
5. After the service becomes Live, open Environment and retrieve FINN_ACCESS_PASSWORD privately. Visit the actual onrender.com URL and log in as finn. Never put the password or API key in Git, a URL or chat.
6. Check /healthz returns {"status":"ok"} without login; the main app and APIs should require login. Try Archive → Reliance, an original PDF, Network search, and TCS source research on desktop and phone.
7. For a free-runtime reset check, save an archive event and restart the service. A genuinely replaced filesystem should restore the bundled corpus and reset that saved state. This is the expected temporary-demo behavior. Do not use the earlier persistent-disk restart criterion.

Do not add a payment method for this requested no-payment setup. Render documents suspension/build restrictions when included limits are exhausted without one. Check usage in its dashboard; no unlimited-usage promise is made. [Free usage handling](https://render.com/docs/free).

If an existing paid service or disk is ever involved, handle it separately before following these fresh-service instructions. Removing resource definitions from a Blueprint does not automatically delete existing resources. [Blueprint resource lifecycle](https://render.com/docs/infrastructure-as-code).

## Local development

```sh
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Local runtime data remains in data/ or FINN_DATA_DIR until the workspace owner removes it. The ephemeral-demo flag is enabled only in the free-hosting configuration. Authentication is optional locally and required in the Blueprint. Shared-demo authentication does not isolate multiple investors.

Only selected source passages/questions go to the optional model. Gemini requests use generateContent without tools or search grounding; Google's free-tier data terms allow product improvement. The legacy OpenAI transport sets store=False. Contact profiles are not sent. Real multi-user deployment still needs per-investor ownership, consented imports, deletion/export, retention controls and access auditing.

## Update the existing FINN service

Push the reviewed changes, then open the existing service's Environment settings. Apply the Gemini variables in [GEMINI.md](GEMINI.md), save them privately, and choose Manual Deploy → Deploy latest commit. The Blueprint has automatic deployment disabled. Environment settings on an existing service do not update merely because render.yaml changed in Git. Keep the service on Free and preserve its access password.
