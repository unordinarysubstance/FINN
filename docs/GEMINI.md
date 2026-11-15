# Gemini Flash setup

FINN now defaults to `gemini-3.6-flash` for both drafting and reviewing research. Google currently lists this model with free-tier input/output tokens. Actual access and quotas depend on your project; free access is limited. [Model](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.6-flash) · [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## Create a key privately

1. Sign in to [Google AI Studio API keys](https://aistudio.google.com/api-keys) with your Google account.
2. Create/select a project eligible for the free tier and create an API key. Leave billing disabled and do not attach a payment method for this no-payment setup. Imported projects may require verification before free-tier access works.
3. Copy the key only into your local `.env` or Render's secret Environment settings. Do not paste it into chat, a terminal command, a URL or Git. [Google's key instructions](https://ai.google.dev/gemini-api/docs/api-key).

## Local configuration

Edit your existing `.env`, preserving unrelated settings. Add/update these settings, putting the actual key after `GEMINI_API_KEY=` privately:

```dotenv
FINN_AI_PROVIDER=gemini
GEMINI_API_KEY=
FINN_GEMINI_MODEL=gemini-3.6-flash
FINN_GEMINI_TIMEOUT_SECONDS=120
```

Restart the server after saving. Exported environment variables take precedence over `.env`; remove any old exported `FINN_AI_PROVIDER=openai` selection. Older FINN_MODEL/FINN_REVIEW_MODEL settings apply only to OpenAI and do not override Gemini. The optional FINN_GEMINI_REVIEW_MODEL overrides only the Gemini reviewer, otherwise it uses the drafting model.

First check provider availability without uploading any company passages:

```sh
python3 manage.py check-ai
```

This lists Flash models advertised by Google and sends one tiny JSON probe per configured model (one probe when analyst/reviewer use the same model). The probe has a 30-second timeout, a 1,024-token output budget and no retries. Listing a model does not prove free quota or current capacity. No model is replaced automatically. If the diagnostic passes, run the full research smoke check:

```sh
python3 manage.py smoke-ai
```

Look for `mode: ai`, `provider: gemini`, and both `analyst_completed` and `reviewer_completed` set to true. A smoke pass checks the integration; inspect the finding against its cited original PDF. Then, if your free quota permits:

```sh
python3 manage.py evaluate --symbols TCS --question-index 1
python3 manage.py evaluate
```

A full uncached evaluation uses up to 24 model passes; temporary server failures can increase that to 72 HTTP attempts. A small free quota may interrupt it. Structural pass counts do not establish factual correctness. Gemini needs its own original-page review; the older OpenAI evaluation does not validate this provider.

## Existing Render service

1. Push the reviewed project changes to GitHub.
2. Open the existing FINN service → Environment. Set FINN_AI_PROVIDER to gemini, FINN_GEMINI_MODEL to gemini-3.6-flash, and GEMINI_API_KEY to your key privately. Remove any hosted OPENAI_API_KEY; old OpenAI model/effort settings can also be removed. Keep the existing FINN access-password and free-hosting settings.
3. Save the environment and use Manual Deploy → Deploy latest commit. Changing render.yaml in Git alone does not change an existing service's environment.
4. Log in to the hosted app and ask one TCS research question. Confirm the result identifies Gemini Flash and has source quotations. If evidence mode appears, use the returned diagnostics to distinguish missing key, quota, model access, connectivity and validation failures.

The key remains on the backend. No additional Python dependency is needed: the transport uses the existing httpx dependency and Google's generateContent REST endpoint.

## Quotas and data use

Each uncached answer has two model passes, each limited to three HTTP attempts. Temporary HTTP 500/502/503/504 errors get short exponential backoff with jitter within the pass's remaining time budget; quota/authentication errors, invalid output and ambiguous transport failures are not retried. Cached answers reuse the same evidence/provider/model configuration. There is no paid-provider failover, Google Search grounding or model tool use. Quota exhaustion or provider/validation failure returns source evidence. FINN cannot determine your project's billing status from its API key; the free-tier project setting is what prevents API charges.

Google's free-tier terms allow inputs and outputs to be used to improve its products. FINN sends the question and selected source passages, never contact profiles. Use public documents and avoid confidential questions/uploads with this free API. This differs from the earlier OpenAI store=False configuration. [Terms](https://ai.google.dev/gemini-api/terms).

OpenAI support is retained for explicitly selected FINN_AI_PROVIDER=openai only. A leftover OpenAI key is ignored while Gemini is selected.

## Temporary high demand (HTTP 503)

The owner's first live Gemini smoke request on the previously selected gemini-3.8-flash reached Google and returned HTTP 503 UNAVAILABLE with a high-demand message, before the analyst completed. That is an unavailable-provider result, not a successful AI answer. FINN now retries explicit transient server failures up to two times, preserving the same model and payload. Diagnostics show analyst_attempts/reviewer_attempts on completed passes and error.attempts when server retries are exhausted. If Google remains unavailable, the app returns evidence with fallback_code temporarily_unavailable; no failed synthesis is cached.

Run `python3 manage.py smoke-ai` again after the update. If all attempts still return 503, wait and retry later. Keep billing disabled and avoid launching the full evaluation until the smoke check passes. If choosing a different model, confirm its current free-tier availability and structured-output support in AI Studio, then set FINN_GEMINI_MODEL explicitly; FINN does not silently switch models. Provider capacity cannot be fixed by local retry code. [Google's retry guidance](https://ai.google.dev/gemini-api/docs/troubleshooting#retry-strategy).

## Read timeout during research

The owner subsequently received a ReadTimeout after approximately 45 seconds, again before analyst completion. That error alone cannot distinguish provider load, response-generation latency or network delays. Research now allows 120 seconds per Gemini pass by default; FINN_GEMINI_TIMEOUT_SECONDS can set 10-180 seconds. The reviewer uses the same configured limit. Timeout failures record the stage, attempt count and timeout budget without exposing request content or keys. Read timeouts are not automatically retried because the provider might already have generated an answer.

Run check-ai before another full research request. If the tiny probe also times out or reports overload, longer research timeouts cannot establish service availability. If the probe passes but smoke-ai times out, the small request worked; investigate the larger payload, generation latency and intermittent service availability. A passing probe does not validate financial answers. Keep the existing source/reviewer checks and inspect any successful smoke answer against the PDF.

## Confirmed availability — 16 November 2026

The owner explicitly selected gemini-3.6-flash for both passes and ran check-ai. The model listing and tiny JSON probe passed on the first attempt; total diagnostic latency was 3,664 ms. FINN now defaults to that model, and the local .env selection has been saved without changing credentials. This confirms the small request worked at that time, not that full financial research has passed. Next run smoke-ai, inspect its citations, and only then run the research evaluation.

For the existing Render service, set FINN_GEMINI_MODEL=gemini-3.6-flash. Remove an old FINN_GEMINI_REVIEW_MODEL override so it follows that model, or explicitly set it to gemini-3.6-flash too. Push the reviewed changes and manually deploy the latest commit; editing the local .env does not update Render's environment.
