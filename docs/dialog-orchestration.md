# Dialog orchestration

## Scope and boundaries

`apps/backend/voice_api/dialog` implements a text-in / response-plan-out engine. It is separate from `audio_pipeline.py`, which owns Pipecat audio ingestion, VAD, turn detection, recognition, cancellation and cleanup. The voice transport is unchanged. As requested, this increment delivers the dialog engine and configuration first: no live TTS, playback, browser chat, configuration screen or new HTTP endpoint is added. The running capture application does not yet invoke the dialog engine.

`DialogVoiceBridge` accepts completed caller-turn transcripts and an injected asynchronous `speak(text)` function. The future voice integration must pass the aggregator's complete `UserTurnStoppedMessage.content`, not each Vosk transcription fragment; deliver speech through Pipecat; interrupt obsolete playback; cancel and await outstanding bridge work before closing it. The bridge does not manage audio tasks or close the WebSocket. A `complete`, `ended`, `failed` or `history_limit` reply ends the workflow. No API retries or crash recovery are implemented; an interrupted in-flight business call has an unknown outcome and must not be automatically replayed.

The application has one PostgreSQL database, `voice`, with no tenant databases. Alembic revision `0002` adds the singleton `dialog_policy` table to this shared application database and seeds General `WELCOME` and `END`. It preserves `voice_sessions`. Its downgrade deletes configured policy. No database migration was applied to a running database as part of this change. Configuration and rules are durable; caller history and extracted entities remain in session memory and are erased by `close()`. Business APIs necessarily receive configured extracted values.

## Configuration

The authoritative schema is [config.py](../apps/backend/voice_api/dialog/config.py). Both General and Business intents live in the database policy, distinguished by `type`. General begins with reserved `WELCOME` and `END`; their descriptions and scripts are editable, and more General intents can be added. Business starts empty because actual business intents and endpoints have not been supplied. Names are globally unique. Active workflows use a private configuration snapshot; imports affect subsequently created workflows.

Each intent has a name, type and classification description. The following are optional:

| Setting | Meaning |
| --- | --- |
| `fields` | Entity names, GLiNER labels, Regex patterns and normalization |
| `rules` | Alternative sufficient-field rules; all conditions within a rule must pass |
| `api` | Endpoint alias, HTTP method, entity bindings and response bindings |
| `responses` | Multiple response templates, selected deterministically by completed-intent count |
| `missing_template` | Defaults to `Please provide {missing_fields}.`; supports `{intent}` too |
| `next_intent` | A configured intent to evaluate after successful completion |

An omitted rules list imposes no rule requirements. `present`, `equals`, `one_of` and `matches` are supported predicates; stored rules are data, never Python expressions. Invalid values are requested again. If no rule succeeds, the engine chooses the rule requiring the fewest distinct missing/invalid fields; configuration order breaks ties. Every configured API binding is required and participates in that minimization. Regex conditions use full matches, with execution timeouts. Cyclic or unresolved transitions, duplicate names/labels, unknown field references and unsafe/unbound placeholders are rejected at import time. `WELCOME` is a dependency-free script read once; an explicit `END` intent delivers its response and terminates the workflow.

Response templates accept simple `{name}` placeholders only. API `response` maps those names to dot-separated JSON paths, including numeric array indexes. Values must be non-null scalars. Static scripts work without an API; a placeholder-bearing response requires its API binding. There is no executable formatting, attribute lookup, arbitrary script or secret interpolation.

Use [dialog-policy.example.json](../apps/backend/dialog-policy.example.json) as a structural example. `ORDER_STATUS` and the `orders` alias are illustrative, not an implemented business service or an authoritative API contract. Replace them with actual business intents and bind requests against that service's published API specification before use. Only flat query/JSON-body scalar bindings are currently supported; path parameters, nested request schemas, OAuth refresh, per-response-status templates and durable side-effect deduplication are not implemented.

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

Install the optional dependencies separately from the capture-only runtime, from the repository root:

```powershell
uv pip install --python apps/backend/.venv/Scripts/python.exe -r apps/backend/requirements-dialog.txt
```

The tested package interfaces are `laya==0.4.29` and `gliner==0.2.30`. Provision the English [Convai Innovations Laya checkpoint](https://huggingface.co/convaiinnovations/laya) and [GLiNER-small v2.1](https://huggingface.co/urchade/gliner_small-v2.1) into complete local directories under the ignored `models/` directory before constructing `LocalModels`. Include tokenizer and backbone configuration assets, not just weights. Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` after provisioning for offline operation; incomplete model directories must fail before accepting calls. No model download command or artifact manifest is provided in this increment.

Laya is explicitly loaded on CPU for intent identification only, with no response generation or extraction. GLiNER is loaded on CPU with `quantize="int8"`, which applies dynamic INT8 quantization to linear layers; this does not mean every operation or activation is INT8. The factory returns a concrete GLiNER model supporting extraction and token preflight. See the [Laya source](https://github.com/NandhaKishorM/laya) and [GLiNER usage documentation](https://github.com/urchade/GLiNER/blob/main/docs/usage.md). Stock GLiNER quantization can reduce extraction accuracy; benchmark against FP32 on representative domain examples before acceptance. Calibrate classification and entity thresholds on business examples, especially with several intents and long histories.

One `LocalModels` instance should be constructed off the event loop before serving sessions. Its single inference worker serializes model access; a semaphore prevents executor work from queuing unboundedly. A cancelled native inference retains admission until it completes. Load one configuration snapshot per session using `load_config(engine)` in a worker thread; instantiate `DialogSession(config, models, models, business_api)` with that snapshot and a `BusinessAPI` adapter. Pass `config.entity_threshold` when constructing the shared models, and reload that instance if the threshold changes. Call `models.close()` off the event loop after active sessions and their inference tasks have stopped. Caller concurrency still needs admission limits at the voice-service boundary before deployment.

`BusinessAPI` takes endpoint aliases mapped to fixed deployment-owned HTTP(S) URLs and separate per-alias headers. It does not derive destinations from extracted entities. Redirects, URL userinfo and environment proxy inheritance are disabled. Calls have a configured wall-clock timeout and a 1 MiB decoded response limit. Each call is attempted once. Runtime errors produce the configured safe failure script through the bridge. Templates, headers, response bodies and transcripts are not logged by these adapters.

The default Docker image continues to install the capture requirements only; it does not instantiate these optional models. A future live voice integration must install `requirements-dialog.txt` in its image and prepare/mount matching model artifacts. No Intel GPU passthrough or OpenVINO/NPU path is claimed.

Native Windows inspection found Intel Core Ultra 5 125H, 16,660,357,120 bytes physical RAM (about 15.5 GiB), Intel Arc Graphics and driver `32.0.101.5763`. Windows reported approximately 2 GiB through `AdapterRAM`; this is not reliable evidence of the integrated GPU's full usable graphics memory. Exact GPU variant, shared-memory budget, Linux/container visibility and NPU availability remain unverified. User-selected checkpoints have not been benchmarked on this host.

## Verification

Run `npm run test:backend:focused:dialog` from the root. See [test discovery](../tests/README.md) for Linux and broader capture checks. Tests use deterministic inference adapters, HTTPX mock transport, and isolated in-memory SQLite; they do not call real business APIs or write to the configured PostgreSQL database. They cover multi-intent gating, all-history follow-ups, alternative rules, invalid values, transitions, cancellation of side effects, templates, configuration validation, API binding/error limits, configuration snapshots, and migration upgrade/downgrade against SQLite.

The optional package set installed successfully on Windows/Python 3.12, and concrete package interfaces were inspected. Real Laya/GLiNER weights, extraction accuracy, INT8 quality, conversational latency, concurrent-session performance, PostgreSQL migration execution and Linux container inference remain unverified. Speech synthesis/playback and browser-to-dialog acceptance belong to the later voice integration.
