# Local and Render deployment

The user confirmed the initial private push to https://github.com/unordinarysubstance/FINN at `ac72021`. The challenge requests a public repository; it remains private under the user's explicit instruction pending approval to change visibility. Render is selected, but no service has been created or deployed in this session.

## Local

Use Python 3.12+, install requirements.txt, then run:

```sh
FINN_REVIEW_MODEL=gpt-6.1-sol python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Keep credentials in your existing local .env or environment. The password gate is optional locally. To enable it, set FINN_REQUIRE_ACCESS=1, FINN_ACCESS_USER=finn and a FINN_ACCESS_PASSWORD of at least sixteen characters in a private environment. Keep credentials out of command-line arguments, URLs, Git and chat.

## Render configuration

The root render.yaml defines one Docker web service in Singapore, compute plan `0.5c-512mb`, a 1 GB disk at /data, one instance and manual service deployments. Applying it creates **paid compute and storage**: review the current Render estimate first. Free Render web services cannot attach a persistent disk. This implementation preserves SQLite, settings, alerts and imported PDFs on that disk. [Render storage documentation](https://render.com/docs/disks).

The Docker process listens on 8000 and the Blueprint sets PORT to match. FORWARDED_ALLOW_IPS=* trusts Render's ingress so HTTPS origins work with the write guard; use it only behind a trusted reverse proxy. One worker/instance preserves SQLite and scheduler ownership. Large PDF imports may need more memory; the smallest plan has not been load-tested.

Render generates the shared access password as a secret. No actual password is committed. The minimal /healthz readiness route is public. UI, PDFs, /docs and workspace APIs require authentication. /api/health is protected because it contains source state. Required hosted access fails startup when the password is missing or too short. All authenticated users share one demo workspace; this is not per-investor ownership.

## Connect and launch

1. Push these reviewed changes to FINN.
2. Sign in to your personal [Render dashboard](https://dashboard.render.com/). Open Account Settings → Account Security → Git Deployment Credentials, add GitHub and authorize FINN. Complete browser authorization without sharing tokens. [Official connection instructions](https://render.com/docs/git-provider).
3. Choose New → Blueprint, select FINN/main and root render.yaml. Review the resource list and recurring cost before applying. Platform schema validation and service creation have not run from this restricted executor.
4. The first deploy can use evidence mode without model credentials. To enable AI, add OPENAI_API_KEY directly in the service's secret Environment settings and redeploy. The configured analyst/reviewer pair incurs model usage. No local .env is copied.
5. Retrieve FINN_ACCESS_PASSWORD privately in Render's Environment settings. Open the actual service URL and sign in as finn. Keep the password out of the URL/chat and share evaluator access only through the approved submission channel.
6. Check anonymous /healthz returns 200, anonymous UI/PDF/API requests return 401, and authenticated navigation, research, acquisition, uploads and settings work. Inspect live price/announcement source outcomes.
7. Save an event, restart/redeploy and confirm it persists on /data. Test from a phone, then record the real URL and checks in VERIFICATION.md and the covering note.

The public PDFs and portable index are in the image. Startup installs the index only into a new workspace and adds synthetic contacts and dated archive events. Existing investor state is never replaced. New downloads and mutable state live on /data; new-company acquisition and feeds require outbound HTTPS.

## Privacy and retention

Only selected source passages and questions go to the model with store=False. Contacts are not sent. Workspace data persists until removed by its owner. Back up SQLite consistently with its backup facility and retain original PDFs with it; copying an actively written database file alone is not reliable.

A real multi-user service still needs per-investor ownership checks, individual authentication, consented imports, deletion/export and retention rules, encrypted storage/backups and access auditing. The shared-demo password gate does not implement those controls.
