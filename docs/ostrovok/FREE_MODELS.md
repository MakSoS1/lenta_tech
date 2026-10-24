# Free OpenCode models: integration and verified limits

Checked on **24 October 2026**. The application uses the unmodified official OpenCode CLI for optional intent extraction. Searches, prices, validation, quotes and demo orders remain application operations. If model access fails, the UI must display the limited parser mode; a failed model call is never represented as a successful LLM response.

## Exact configuration

| Variable | Default / accepted values |
|---|---|
| `LLM_MODE` | `opencode` (default), or `offline` |
| `OPENCODE_BIN` | `opencode`; may be an absolute path to the official executable |
| `OPENCODE_MODEL` | `opencode/deepseek-v4.1-flash-free` (default), or `opencode/glm-5.3-flash-free` |

The fixed fallback is `opencode/glm-5.3-flash-free`. It is attempted once after a transient primary service/process failure, within the same 55-second total execution budget. Authentication/403, rate limits, invalid model output, unexpected cost and timeouts stop the attempt. If GLM is selected as primary, it is attempted once.

**Only these two exact model IDs are accepted.** The corresponding IDs without `-free` are paid and are rejected before execution. There is no paid fallback, key rotation, automatic purchase or Go subscription path.

Install the tested official CLI version locally or in the deployment image:

```sh
npm install --global @opencode/cli@2.1.4
opencode --version
```

In this session the official npm registry returned version `2.1.4`, and the installed executable reported `opencode v2.1.4`. Use the deployment's normal reviewed dependency installation process. The adapter itself never installs or updates executables.

## Official API restrictions

The [current official model documentation](https://opencode.ai/v2/docs/console/models/) lists the API model IDs `deepseek-v4.1-flash-free` and `glm-5.3-flash-free`. Both are limited-time free offers. The documentation says their providers follow zero retention and do not use submitted data for training.

The [official Inference API documentation](https://opencode.ai/v2/docs/console/api/inference/) states that free-tier chat models are available only within OpenCode; other clients receive HTTP 403 even with an API key. Paid models use a personal or service-account bearer key. A public catalog can be fetched with:

```sh
curl --fail-with-body https://opencode.ai/inference/v1/models
```

This catalog listing confirms identifiers and availability metadata; it does **not** prove that inference is currently accessible. Do not call a free chat endpoint using a fabricated key or spoofed OpenCode headers. The adapter uses the [documented automation interface](https://opencode.ai/v2/docs/cli/commands/):

```sh
opencode run --standalone --agent travel \
  --model opencode/deepseek-v4.1-flash-free \
  --format json --title 'Travel intent' 'PROMPT'
```

`--format json` emits newline-delimited JSON. The adapter checks error events and exit status, extracts only text events, parses one JSON object and strictly validates its partial patch against the intent contract. A `step_start` event is not evidence of successful generation.

The OpenCode homepage advertises built-in free models without an account. No user account or API key was used in the checks below. Current official model and API documentation does **not** publish numeric RPM/TPM limits for the two models. No unlimited-usage guarantee is assumed. Both offers can change or end; see [OpenCode's service terms](https://opencode.ai/legal/terms-of-service).

## Isolation and spending controls

Every model attempt runs in a new temporary working directory with separate XDG data, configuration, cache and state directories. The child receives only executable, locale, temporary-directory and necessary network proxy/CA settings. It receives no provider API keys, OpenCode account credentials or unrelated application credentials. It does not reuse the app repository's agent instructions or tools.

The model prompt contains only the user request, a filtered current intent and the supplied reference time. State, session, quote and order fields are excluded. Known authority identifiers in the request are redacted. Output can contain only the partial intent fields in [IMPLEMENTATION_CONTRACT.md](IMPLEMENTATION_CONTRACT.md). Unknown fields, invalid types, out-of-range values and malformed JSON fail closed. The application validates any accepted patch again.

OpenCode permissions deny every tool, and the hard `tool.use` policy also denies every tool. Provider policy permits only OpenCode; MCP and skill integrations are denied. The custom travel agent has one model step. The hidden title, summary and compaction agents are pinned to the same approved free model, and an explicit session title avoids title generation. This matters because OpenCode may otherwise use a low-cost paid model for maintenance tasks. See [agent configuration](https://opencode.ai/v2/docs/agents/), [policy semantics](https://opencode.ai/v2/docs/policies/) and [model default/fallback rules](https://opencode.ai/v2/docs/models/).

The application never passes `OPENCODE_API_KEY`, other provider keys or a billing-backed account into this free-only child. It never relies on an unavailable default's automatic model selection. A reported nonzero/invalid cost rejects the result and stops further attempts. Process stdout and stderr are each capped at 256 KiB. Timeout, cancellation or excessive output terminates the private process group, including the CLI's descendants.

## Actual live evidence from this environment

These were real network attempts through an unmodified official CLI, separate from unit tests. No successful generated response has been observed here.

| Check | Result |
|---|---|
| Official npm version lookup and local installation | Successful, `@opencode/cli@2.1.4` |
| `opencode --version` | `opencode v2.1.4` |
| Public model catalog | Both requested free IDs present |
| `opencode models`, isolated environment without credentials | Both requested free models listed |
| DeepSeek free: Russian trip/date extraction prompt | Exit 1, `provider.auth`, HTTP 403 `FreeTierError` |
| GLM free: minimal JSON response prompt | Exit 1, `provider.auth`, HTTP 403 `FreeTierError` |
| Implemented adapter smoke using the official DeepSeek CLI | Exit 2, empty patch, `used: false`, `reason: free_model_unavailable` |

Both inference attempts returned the following service message:

> OpenCode's free tier can only be used from within OpenCode. Download it at https://opencode.ai and keep building.

This occurred **inside the official CLI** in this environment. The reason is not established; obtaining an API key has not been demonstrated to resolve it. The adapter reports `used: false`, `reason: "free_model_unavailable"`, and an empty patch. It does not attempt to circumvent the rejection. A prior network attempt without the required proxy environment failed DNS resolution; that attempt provides no model-quality evidence.

The implemented adapter was also exercised against the actual executable and produced:

```json
{"check":"official_cli_free_model","result":{"patch":{},"model":"opencode/deepseek-v4.1-flash-free","used":false,"reason":"free_model_unavailable"}}
```

To repeat a deliberate live check with the adapter:

```sh
OPENCODE_BIN=/absolute/path/to/opencode .venv/bin/python scripts/free_model_smoke.py
OPENCODE_BIN=/absolute/path/to/opencode .venv/bin/python scripts/free_model_smoke.py --model opencode/glm-5.3-flash-free
```

The smoke command prints a scrubbed JSON result and exits `2` if inference is unavailable. It does not inspect or request credentials and never changes headers to evade restrictions. Its sample prompt is frozen to `2026-10-24T12:00:00+03:00` for reproducibility.

## Automated verification

The first independent GitHub Actions live check on 24 October 2026 also called both models through the official CLI. Both jobs returned `status: blocked`, `used: false`, `reason: free_model_unavailable`, and exit code `2`. Reports were uploaded even on failure: [actual run](https://github.com/MakSoS1/lenta_tech/actions/runs/40123036282). This reproduces lack of usable inference in a second environment; the scrubbed CI result does not establish the precise provider-side cause. Later verification is recorded in [the implementation report](IMPLEMENTATION_REPORT_2026-10-24.md).

DeepSeek is the configured primary, not a measured model-quality winner. A comparative benchmark requires successful real inference and an independent held-out set; neither can be inferred from a successful parser run.

`apps/ostrovok/tests/test_model_gateway.py` runs real local fake executables at the subprocess boundary, without provider traffic. It covers offline behavior, paid-ID rejection, successful patch decoding, credential/identifier isolation, maintenance-model pinning, actual-style HTTP 403 handling, transient free fallback, malformed/unsafe schema output, nonzero reported cost, bounded output, and process-group timeout cleanup. Passing these tests verifies the adapter's behavior; it does not claim successful remote inference.
