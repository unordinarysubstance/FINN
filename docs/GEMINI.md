# Gemini Flash setup

FINN now defaults to `gemini-3.8-flash` for both drafting and reviewing research. Google currently lists this model with free-tier input/output tokens. Actual access and quotas depend on your project; free access is limited. [Model](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash) · [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## Create a key privately

1. Sign in to [Google AI Studio API keys](https://aistudio.google.com/api-keys) with your Google account.
2. Create/select a project eligible for the free tier and create an API key. Leave billing disabled and do not attach a payment method for this no-payment setup. Imported projects may require verification before free-tier access works.
3. Copy the key only into your local `.env` or Render's secret Environment settings. Do not paste it into chat, a terminal command, a URL or Git. [Google's key instructions](https://ai.google.dev/gemini-api/docs/api-key).

## Local configuration

Edit your existing `.env`, preserving unrelated settings. Add/update these settings, putting the actual key after `GEMINI_API_KEY=` privately:

```dotenv
FINN_AI_PROVIDER=gemini
GEMINI_API_KEY=
FINN_GEMINI_MODEL=gemini-3.8-flash
```

Restart the server after saving. Exported environment variables take precedence over `.env`; remove any old exported `FINN_AI_PROVIDER=openai` selection. Older FINN_MODEL/FINN_REVIEW_MODEL settings apply only to OpenAI and do not override Gemini. The optional FINN_GEMINI_REVIEW_MODEL overrides only the Gemini reviewer, otherwise it uses the drafting model.

Run one small check first:

```sh
python3 manage.py smoke-ai
```

Look for `mode: ai`, `provider: gemini`, and both `analyst_completed` and `reviewer_completed` set to true. A smoke pass checks the integration; inspect the finding against its cited original PDF. Then, if your free quota permits:

```sh
python3 manage.py evaluate --symbols TCS --question-index 1
python3 manage.py evaluate
```

A full uncached evaluation can make up to 24 requests, so a small free quota may interrupt it. Structural pass counts do not establish factual correctness. Gemini needs its own original-page review; the older OpenAI evaluation does not validate this provider.

## Existing Render service

1. Push the reviewed project changes to GitHub.
2. Open the existing FINN service → Environment. Set FINN_AI_PROVIDER to gemini, FINN_GEMINI_MODEL to gemini-3.8-flash, and GEMINI_API_KEY to your key privately. Remove any hosted OPENAI_API_KEY; old OpenAI model/effort settings can also be removed. Keep the existing FINN access-password and free-hosting settings.
3. Save the environment and use Manual Deploy → Deploy latest commit. Changing render.yaml in Git alone does not change an existing service's environment.
4. Log in to the hosted app and ask one TCS research question. Confirm the result identifies Gemini Flash and has source quotations. If evidence mode appears, use the returned diagnostics to distinguish missing key, quota, model access, connectivity and validation failures.

The key remains on the backend. No additional Python dependency is needed: the transport uses the existing httpx dependency and Google's generateContent REST endpoint.

## Quotas and data use

Each uncached answer uses up to two model requests. Cached answers reuse the same evidence/provider/model configuration. There are no automatic retries, paid-provider failover, Google Search grounding or model tools. Quota exhaustion or provider/validation failure returns source evidence. FINN cannot determine your project's billing status from its API key; the free-tier project setting is what prevents API charges.

Google's free-tier terms allow inputs and outputs to be used to improve its products. FINN sends the question and selected source passages, never contact profiles. Use public documents and avoid confidential questions/uploads with this free API. This differs from the earlier OpenAI store=False configuration. [Terms](https://ai.google.dev/gemini-api/terms).

OpenAI support is retained for explicitly selected FINN_AI_PROVIDER=openai only. A leftover OpenAI key is ignored while Gemini is selected.
