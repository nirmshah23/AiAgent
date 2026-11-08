# Dialog orchestration

## Scope and boundaries

`apps/backend/voice_api/dialog` implements a text-in / response-plan-out engine. The live `audio_pipeline.py` connects complete caller turns to `DialogVoiceBridge`, then sends its configured response texts through Piper and browser playback. No typed chat or policy editing API is exposed.

`DialogVoiceBridge` receives the aggregator's complete `UserTurnStoppedMessage.content`, rather than each Vosk fragment. A private response task handles each caller turn without blocking audio ingestion. New speech cancels and awaits obsolete dialog/speech work; disconnect cancels that task before clearing dialog history and stopping Pipecat. A `complete`, `ended`, `failed` or `history_limit` reply finishes the workflow after speech drains. Cancellation during a business API call terminates the workflow because its outcome is unknown; no automatic replay or retry occurs.

The API loads one shared CPU `LocalModels` instance off the event loop at startup. Each connection loads a fresh database policy snapshot in a worker thread and creates a private `DialogSession`. Configured welcome scripts, clarification questions, missing-field prompts, business templates and goodbye scripts all use the same Piper path. `MAX_VOICE_SESSIONS` defaults to two per API process; additional connections close with 1013. This bounds model/pipeline allocation, not a measured concurrency guarantee. Changing `entity_threshold` requires an API restart; other policy imports affect new sessions.

The application has one PostgreSQL database, `voice`, with no tenant databases. Alembic revision `0002` adds the singleton `dialog_policy` table to this shared application database and seeds General `WELCOME` and `END`. It preserves `voice_sessions`. Its downgrade deletes configured policy. On 2026-11-08, revisions `0001` through `0003` were applied successfully to a newly provisioned local Compose PostgreSQL 17 `voice` database. The stored policy validated with WELCOME, END and CLAIM_STATUS, including three sufficient-field rules. Configuration and rules are durable; caller history and extracted entities remain in session memory and are erased by `close()`. Business APIs necessarily receive configured extracted values.

## Configuration

The authoritative schema is [config.py](../apps/backend/voice_api/dialog/config.py). Both General and Business intents live in the database policy, distinguished by `type`. General begins with reserved `WELCOME` and `END`; their descriptions and scripts are editable, and more General intents can be added. Revision `0003` adds the supplied Claim Status business intent; see the seed and simulation instructions below. Names are globally unique. Active workflows use a private configuration snapshot; imports affect subsequently created workflows.

Each intent has a name, type and classification description. The following are optional:

| Setting | Meaning |
| --- | --- |
| `fields` | Entity names, GLiNER labels, Regex patterns and normalization |
| `rules` | Alternative sufficient-field rules; all conditions within a rule must pass |
| `api` | Endpoint alias, HTTP method, entity bindings and response bindings |
| `responses` | Multiple response templates, selected deterministically by completed-intent count |
| `missing_template` | Defaults to `Please provide {missing_fields}.`; supports `{intent}` too |
| `next_intent` | A configured intent to evaluate after successful completion |

An omitted rules list imposes no rule requirements. `present`, `equals`, `one_of` and `matches` are supported predicates; stored rules are data, never Python expressions. Invalid values are requested again. If no rule succeeds, the engine chooses the rule requiring the fewest distinct missing/invalid fields; configuration order breaks ties. Every configured `query`/`body` API binding is required and participates in that minimization. Regex conditions use full matches, with execution timeouts. Cyclic or unresolved transitions, duplicate names/labels, unknown field references and unsafe/unbound placeholders are rejected at import time. `WELCOME` is a dependency-free script read once; an explicit `END` intent delivers its response and terminates the workflow.

Response templates accept simple `{name}` placeholders only. API `response` maps those names to dot-separated JSON paths, including numeric array indexes. Values must be non-null scalars. Static scripts work without an API; a placeholder-bearing response requires its API binding. There is no executable formatting, attribute lookup, arbitrary script or secret interpolation.

Use [dialog-policy.example.json](../apps/backend/dialog-policy.example.json) as a structural example. `ORDER_STATUS` and the `orders` alias are illustrative, not an implemented business service or an authoritative API contract. Replace them with actual business intents and bind requests against that service's published API specification before use. `optional_query` bindings send only nonempty extracted values and do not impose extra sufficiency requirements. Only flat query/JSON-body scalar bindings are currently supported; path parameters, nested request schemas, OAuth refresh, per-response-status templates and durable side-effect deduplication are not implemented.

## Operator workflow

Use the existing [database setup](voice-capture.md#local-windows-development). Verify the effective `DATABASE_URL` points to the intended dedicated application database. From `apps/backend`, with that environment set:

```powershell
.venv/Scripts/alembic upgrade head
.venv/Scripts/python.exe -m voice_api.dialog.store export dialog-policy.local.json
# Edit the exported JSON, then import it atomically:
.venv/Scripts/python.exe -m voice_api.dialog.store import dialog-policy.local.json
```

On Linux use `.venv/bin/alembic` and `.venv/bin/python`. The local exported file is ignored by Git. Commands print the target URL with its password hidden. Imports validate before opening the database and replace the entire policy within one transaction; keep exported snapshots if rollback is needed. Alembic owns schema changes. No unauthenticated policy-write endpoint is exposed. Store service URLs and credentials in deployment-owned configuration, not in entity values or response templates.

## Processing semantics

1. Read the configured WELCOME script.
2. Accumulate each full caller response. Laya classifies the accumulated caller history using one independent yes/no (`noul`) question per intent, permitting multiple positive intents. Only scores strictly above `confidence_threshold` are accepted. WELCOME is excluded from classification.
3. Retain pending intents and merge newly accepted ones on follow-up turns. Never replay completed intents. If none is pending or accepted, request intent clarification without discarding history. Low confidence on a field-only follow-up does not erase an already identified intent.
4. Extract only fields configured for each pending intent. Run Regex then GLiNER for each previous caller response, merge their results, and normalize. Regex wins for the same field within a response; newer responses supersede older values. The first capture group is used when present, otherwise the full Regex match. Multiple matches use the latest occurrence. Supported normalization is trim, lower case, upper case or digits only.
5. Evaluate every pending intent before executing any of that batch's APIs. Collect minimum missing fields by intent and ask each intent's missing-information template. Repeat using all prior caller responses plus the new answer.
6. When all current pending intents are sufficient, process them in configuration order, with END last. Bind entities into API requests, map responses to templates and emit response text for speech delivery. Intents without APIs can emit static scripts or simply transition. Evaluate newly scheduled next intents through the same extraction/rule gate. Completed work is retained if a later transition needs more fields.
7. Finish when there is no pending work, or an explicit END succeeds. API/voice failures do not automatically retry a side effect. The owning voice session must call `close()` and release its speech resources on disconnect.

`max_history_chars` bounds session memory and fails explicitly rather than dropping earlier responses. Laya uses `predict_long` to scan beyond its context window; its per-window maximum yes/no scores are not calibrated conversation-wide probabilities. GLiNER processes each caller response separately and rejects responses exceeding its splitter-token limit instead of silently extracting from a truncated prefix. No automatic long-response splitting is implemented yet.

## Local inference adapters

Install the dialog runtime dependencies from the repository root:

```powershell
uv pip install --python apps/backend/.venv/Scripts/python.exe -r apps/backend/requirements-dialog.txt
```

The package interfaces are pinned to `laya==0.4.29` and `gliner==0.2.30`. Prepare English artifacts before startup (with Hugging Face offline flags unset):

```powershell
Push-Location apps/backend
.venv/Scripts/python.exe -m voice_api.dialog.provision --models-dir ../../models
Pop-Location
```

On Linux run the module with `.venv/bin/python` from `apps/backend`. The provisioning module pins source revisions for [Laya](https://huggingface.co/convaiinnovations/laya), [GLiNER-small v2.1](https://huggingface.co/urchade/gliner_small-v2.1), and [DeBERTa-v3-small](https://huggingface.co/microsoft/deberta-v3-small). It downloads the English Laya checkpoint only and makes GLiNER self-contained by saving its backbone tokenizer and embedding the backbone configuration. This avoids host-specific paths or downloads from a read-only container model mount. Downloads total approximately 1.5 GB plus small tokenizer/config assets. Large weight downloads use streamed HTTPS, verify pinned SHA-256 digests and resume `.download` files on retry. `sentencepiece==0.2.1` is pinned to remain compatible with Pipecat's protobuf runtime. Model directories remain ignored by Git.

Set `LAYA_MODEL_PATH` and `GLINER_MODEL_PATH` to the prepared absolute directories for native startup. Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` afterward. The runtime never provisions missing weights during a call; missing or incomplete artifacts fail startup.

Laya is explicitly loaded on CPU for intent identification only, with no response generation or extraction. The live runtime uses GLiNER FP32 on CPU by default (`GLINER_QUANTIZE=false`). Setting this flag to `true` enables dynamic INT8 quantization of linear layers; it does not quantize every operation or activation. In the native smoke comparison, FP32 extracted the synthetic claim number, member ID and birth date at the configured threshold, while stock INT8 extracted none. This is a diagnostic observation, not a representative quality or performance benchmark. Spoken date/identifier normalization still need domain validation. The Laya checkpoint also reports an out-of-range choice temperature; business confidence thresholds require calibration on representative calls. See the [Laya source](https://github.com/NandhaKishorM/laya) and [GLiNER usage documentation](https://github.com/urchade/GLiNER/blob/main/docs/usage.md).

`LocalModels` owns one serialized inference worker shared by sessions. Its semaphore prevents native inference jobs queuing unboundedly. Cancelling inference retains admission until the native operation completes; shutdown joins the worker off the event loop after voice sessions have closed.

`BusinessAPI` takes endpoint aliases mapped to fixed deployment-owned HTTP(S) URLs and separate per-alias headers. It does not derive destinations from extracted entities. Redirects, URL userinfo and environment proxy inheritance are disabled. Calls have a configured wall-clock timeout and a 1 MiB decoded response limit. Each call is attempted once. Runtime errors produce the configured safe failure script through the bridge. Templates, headers, response bodies and transcripts are not logged by these adapters.

The Docker image installs the dialog requirements and CPU-only PyTorch. Compose mounts the prepared models read-only, enables offline flags and starts the dialog runtime by default. `DIALOG_ENABLED=false` is an explicit capture/TTS diagnostic mode, not a fallback after model failures. The default `DIALOG_API_MODE=simulated` selects the synthetic Claim Status adapter; scripts label the result simulated. To use live configured services, set `DIALOG_API_MODE=live`, `BUSINESS_API_ENDPOINTS` to a JSON alias-to-URL map and `BUSINESS_API_HEADERS` to a JSON alias-to-header-map. Keep credentials out of tracked files. Unknown modes and missing policy API aliases fail startup. No Intel GPU passthrough or OpenVINO/NPU path is claimed.

Native Windows inspection found Intel Core Ultra 5 125H, 16,660,357,120 bytes physical RAM (about 15.5 GiB), Intel Arc Graphics and driver `32.0.101.5763`. Windows reported approximately 2 GiB through `AdapterRAM`; this is not reliable evidence of the integrated GPU's full usable graphics memory. Exact GPU variant, shared-memory budget, Linux/container visibility and NPU availability remain unverified. User-selected checkpoints have not been benchmarked on this host.

## Verification

Run `npm run test:backend:focused:dialog` from the root. See [test discovery](../tests/README.md) for Linux and broader capture checks. Tests use deterministic inference adapters, HTTPX mock transport, and isolated in-memory SQLite; they do not call real business APIs or write to the configured PostgreSQL database. They cover multi-intent gating, all-history follow-ups, alternative rules, invalid values, transitions, cancellation of side effects, templates, configuration validation, API binding/error limits, configuration snapshots, and migration upgrade/downgrade against SQLite.

The optional package set installed successfully on Windows/Python 3.12, and concrete package interfaces were inspected. Initial engine checks did not exercise real weights. Current inference and live integration verification is recorded below; representative extraction accuracy, conversational latency and concurrent-session performance remain unmeasured. Speech synthesis/playback are connected; see the live voice verification below.

## Live voice verification

On Windows/Python 3.12, all 34 existing dialog checks and 12 capture checks passed, as did Ruff, the UI production build, four Angular unit checks and four existing Playwright capture checks. Focused smoke checks verified generated missing-field prompts, follow-up responses, simulated claim result/goodbye delivery, PCM completion barriers, terminal browser playback drain, speech-failure cleanup and cancellation of an in-flight business call without replay. These deterministic checks isolate inference from orchestration.

A separate all-real offline native check synthesized a caller request, passed its PCM through Vosk, selected CLAIM_STATUS with Laya, produced a dialog missing-field question and streamed it through Piper. The prepared artifacts also loaded from the read-only Linux Compose mount. Compose built successfully, migrations found the database at `0003`, and the API became healthy. Chromium then passed a voice-to-generated-reply browser flow against the actual Compose stack using recorded microphone input; PostgreSQL recorded a completed session with nonzero audio bytes. No live insurer API was contacted. This verifies connectivity and reply delivery, not complete real-world claim extraction, recognition accuracy, acoustic quality or latency/concurrency targets. The stock INT8 comparison and outstanding calibration needs are described in the inference section above.

## Claim Status seed and simulation

[dialog-policy.claim-status.json](../apps/backend/dialog-policy.claim-status.json) is the complete importable seed. Revision `0003` adds absent intents to the shared `voice` database, preserves existing Claim Status configuration, and updates Welcome/End scripts only when they still match the original defaults. It changes policy data, not tables or session records. Downgrade deliberately retains operator-owned policy data. The local Compose database was subsequently provisioned and upgraded to `0003` on 2026-11-08. Verify the effective database target, export a policy backup, then use the existing `alembic upgrade head` operator workflow. Importing the JSON instead replaces the entire policy.

Revision `0004` replaces WELCOME and CLAIM_STATUS in the shared `voice` database with the new demo policy, preserving END, other intents and global settings. It changes policy data only, with no schema or tenant changes. Export the policy before migration if you need to recover customized claim/welcome content; downgrade retains the new policy. Fresh databases apply `0003` then `0004`. The local Compose `voice` database was backed up to ignored `apps/backend/dialog-policy.local.json` and upgraded to `0004` on 2026-11-08; the API became healthy, and both lookup combinations passed against the stored policy in the Linux container.

Claim Status accepts either of these sufficient-field combinations, with no caller type:

- `claimNumber` alone. Example: `DEMO-10001`.
- `memberId`, `dateOfBirth` and `dateOfService`. Example: `DEMO-M001`, `1980-05-20`, `2026-09-14`.

The simulator returns the same synthetic PAID claim for any nonempty claim number or complete member/date combination; these examples are not a database of matching records. Dates must have YYYY-MM-DD shape and be valid calendar dates. Missing-information speech explains both alternatives. The final response explicitly labels the lookup simulated and transitions to END.

The demo adapter contract is GET `/ivr/claims/search`, with optional query parameters `claimNumber`, `memberId`, `dateOfBirth`, `dateOfService`; at least one complete combination above is required. No caller type, provider identifiers or validation token is bound. HTTP 200 contains `callerAuthenticated`, `totalMatchesFound` and `claims`; the response bindings read `claims.0.claimNumber` and `claims.0.claimStatusSpeechText`. HTTP 400 indicates insufficient criteria or invalid supplied dates; unsupported method/path returns 404. This is a MockTransport contract, not an exposed FastAPI endpoint or a verified insurer contract.

To simulate a call without network access, construct the existing engine with `simulated_claim_api()` from `voice_api.dialog.claim_simulator` as its API adapter, and load the seeded policy. The factory returns `BusinessAPI` backed by HTTPX MockTransport: GET `/ivr/claims/search` follows normal request binding, HTTP status handling, JSON decoding and template mapping. Valid lookups return one fixed synthetic PAID claim with all 20 detail properties, `callerAuthenticated: true` and `totalMatchesFound: 1`; insufficient/invalid criteria return 400. Authentication is simulated, never proof of caller identity. The simulator is explicit and is not a fallback after real HTTP failures. It does not contact an insurer or use submitted identifiers as real claim records. The running Compose voice pipeline uses this simulator explicitly by default; native development must set `DIALOG_API_MODE=simulated` to select it.

For a future real integration, configure the `claim_status` alias against the actual service URL and add response authorization checks before exposing claim details; the supplied contract's `callerAuthenticated` must be enforced. The seeded response is only for the explicit simulator.
