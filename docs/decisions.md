# Decisions

A living record of the meaningful, non-obvious decisions and *why* they were
made. Append a new entry when a decision is taken or changed; do not rewrite
history — supersede an old entry with a new one and mark the old as superseded.

Format per entry:
- **Date** — when decided
- **Decision** — what was decided
- **Why** — the reasoning and the tradeoffs accepted
- **Status** — accepted / superseded (link the superseding entry)

---

## 2026-09-21 — Backend pinned to Python 3.11 (not 3.12)

**Decision.** The backend runtime and container base image use Python 3.11.

**Why.** 3.11 is chosen for ecosystem stability across our dependencies
(FastAPI, Pydantic v2, boto3, LangGraph, bedrock-agentcore) and mature tooling
support, over the newer 3.12. The gain from 3.12 was not worth the risk for the
MVP. `tech.md` records the version.

**Status.** Accepted.

---

## 2026-09-21 — Local-first build (Approach B)

**Decision.** Build features against local/mocked AWS first (DynamoDB Local,
LocalStack for S3/SQS, mocked Bedrock/GraphRAG behind adapters), and stand up
real AWS infrastructure (Terraform) and the managed AI services once the
application contracts are proven.

**Why.** Fast feedback and no AWS cost while iterating; matches the steering
requirement that services be testable without a running AWS environment. The
`router → service → repository/integration` boundary makes the later swap from
mock to real clients localized. The riskiest/costliest pieces (GraphRAG,
AgentCore) are de-risked behind a stable contract before real provisioning.

**Status.** Accepted.

---

## 2026-09-21 — uv as the Python dependency manager

**Decision.** Use `uv` for dependency resolution, locking, and running backend
commands; commit `uv.lock`.

**Why.** Fast, reproducible, lockfile-based installs that work identically
locally and in the Docker build. Keeps the `pyproject.toml` + lockfile as the
single source of truth for dependencies.

**Status.** Accepted.

---

## 2026-09-21 — Frontend on Tailwind CSS v3 (not v4)

**Decision.** Use Tailwind CSS v3 with the classic `tailwind.config.js` + PostCSS
setup.

**Why.** v3 is the stable, well-documented path and avoids v4's newer PostCSS
plugin model. Stability over novelty for the MVP.

**Status.** Accepted.

---

## 2026-09-21 — Three isolated agents, one container image each

**Decision.** The three LangGraph agents (ingestion, adaptive-reading,
discussion) are each packaged as their **own container image** and deployed to
their **own AgentCore Runtime**, rather than a single agent image with three
entrypoints.

**Why.** Isolation is a primary goal for this system: agents must deploy, scale,
version, and fail independently so one cannot crash another. Per-image isolation
also keeps each agent's dependencies separate (e.g. ingestion's heavy
PDF/extraction libraries stay out of the discussion agent). The cost — more
images to build/scan/push, more ECR repos, and more AgentCore/Terraform wiring —
is accepted as a one-time setup in exchange for real deployment-level isolation.
This is a deliberate move beyond the earlier "one agent image" reading of the
spec; `tech.md`, `structure.md`, and `development.md` were updated to match.

**Status.** Accepted.

---

## 2026-09-21 — Tools live in a separate MCP server (not in-process)

**Decision.** Agent capabilities (GraphRAG retrieval, authorized-content access,
concept persistence, etc.) are exposed by a dedicated **MCP (Model Context
Protocol) server** running as its own image/process. Agents call tools over MCP;
they do not call AWS or business logic directly and do not run tools in-process.

**Why.** The user requires tool isolation: a misbehaving tool must be contained
to the tool tier and unable to crash an agent or the API. An MCP server gives
one enforced allowlist boundary with explicit tool schemas, satisfying the
security rule that agent tools be "explicit and allowlisted" and that agents
"cannot invoke arbitrary AWS APIs." Tradeoff accepted: an additional deployable
to build, secure, deploy, and monitor — more moving parts than a purely
in-process design, justified by the isolation requirement. `security.md`,
`tech.md`, and `structure.md` were updated to match.

**Status.** Accepted.

---

## 2026-09-21 — No MCP for anything beyond the agent tool boundary

**Decision.** MCP is used only as the agent tool boundary described above. We do
not consume third-party MCP servers for product features, and book discovery
stays on direct HTTP calls to Google Books / Open Library.

**Why.** `security.md` forbids arbitrary external ingestion; discovery needs only
plain metadata calls. Adding external MCP dependencies would increase the trust
surface for no product benefit.

**Status.** Accepted.

---

## 2026-09-21 — Agent-tier dependencies isolated from the FastAPI image

**Decision.** LangGraph, `bedrock-agentcore`, `pypdf`, and `mcp` are an
`agents` optional-dependency group, installed into the agent images and the MCP
server image but not the FastAPI application image.

**Why.** Keeps the API image lean and reinforces tier isolation (the API never
imports agent/graph code). The deps are also included in the `dev` group so the
pipeline is runnable and testable locally.

**Status.** Accepted.

---

## 2026-09-21 — GraphRAG KB provisioned via the `awscc` provider

**Decision.** The Bedrock Knowledge Base with **Neptune Analytics** GraphRAG
storage (and its S3 data source) is provisioned with the `hashicorp/awscc`
provider; the Neptune Analytics graph, S3 buckets, and IAM stay on the classic
`hashicorp/aws` provider.

**Why.** The classic `aws` provider does not yet support the `NEPTUNE_ANALYTICS`
storage type for `aws_bedrockagent_knowledge_base` (provider issue #41745; even
at v5.100 the storage sub-blocks are only OpenSearch/Pinecone/RDS/Redis). The
Cloud Control (`awscc`) provider mirrors the CloudFormation schema and supports
`neptune_analytics_configuration`, so it can express the required
GraphRAG-with-Neptune capability today. When the classic provider adds support,
this can be migrated. Provider pins were bumped (`aws ~> 5.90`, added
`awscc ~> 1.0`).

**Status.** Accepted.

---

## 2026-09-21 — Ingestion agent built with mockable ports; live Bedrock deferred

**Decision.** The ingestion pipeline (LangGraph graph, deterministic nodes, MCP
tools) is built and fully unit-tested against `Protocol` ports with fake
implementations. Real PDF extraction uses `pypdf`; the KB-ingestion tool has the
real boto3/Bedrock shape but is exercised via a fake in tests. Live Bedrock KB /
Neptune Analytics ingestion is a deploy-time concern.

**Why.** Approach B (local-first): Bedrock KB and Neptune Analytics have no local
emulation, so gating implementation on live AWS would stall progress and incur
cost. Ports keep the pipeline testable and make the mock→real swap localized.

**Status.** Accepted.

---

## 2026-09-21 — Frontend (group 12) moved ahead of recommendations (group 11)

**Decision.** Build the frontend once the feature-backend API contracts are
stable (auth, books, uploads, reading, discussions, jobs, progress), rather than
waiting for every backend feature. Recommendations (group 11) — a single scored
endpoint with no agent — is decoupled from the frontend and runs in
parallel/after; the frontend stubs the recommendations screen until it lands.
The spec wave graph and `development.md` were updated to match.

**Why.** After groups 5–10 the API surface is stable and real, so there is no
benefit to deferring the frontend further. Building it now yields a tangible,
interactive product and surfaces contract gaps earlier. Recommendations does not
block any other frontend screen, so it need not gate the frontend. Hardening
(group 13) now waits on both 11 and 12. Tradeoff accepted: the recommendations
screen is a stub for a short window.

**Status.** Accepted.

---

## 2026-09-21 — Recommendations: transparent additive scoring, no learned model

**Decision.** Recommendations use a simple, documented, additive scoring formula
(`services/recommendation_scoring.py`): weighted category overlap + author match
+ capped saved-concept overlap, each producing a human-readable reason. No agent,
no learned recommender model. Candidate books come from the discovery providers
seeded by the user's preferred categories/authors; already started/completed
books are excluded and zero-score items are dropped.

**Why.** `development.md` calls for transparent, testable scoring over available
signals rather than a complex model for the MVP. Additive weights (module
constants) keep it explainable and unit-testable, and every recommendation
carries a reason (requirement 7.2).

**MVP limitation (honest).** There is no dedicated reading-history / saved-
concepts store yet, so the signals provider currently returns empty signals
server-side, which means the endpoint returns an empty list until that data
exists. The scoring and service are fully implemented and tested; enriching the
signals provider (from progress + a saved-concepts store) is a localized future
change that does not touch the scoring formula. The frontend handles the empty
state gracefully.

**Status.** Accepted.

---

## 2026-09-21 — AI cost-abuse protection: per-user in-memory rate limiting

**Decision.** Expensive AI endpoints (`POST /reading/generate`,
`POST /discussions/{id}/messages`) are guarded by a per-user, per-operation
sliding-window rate limiter (`core/rate_limit.py`), enforced via a FastAPI
dependency that returns 429 when exceeded. The default implementation is
in-memory behind a `RateLimiter` protocol.

**Why.** `security.md` requires request limits on expensive AI operations. A
small protocol-backed limiter is enough for the MVP and keeps call sites stable.
Job idempotency already prevents duplicate expensive *work*; this caps request
*rate*.

**Limitation.** In-memory state is per-task, so with multiple ECS tasks the
effective limit is per-task, not global. The protocol lets it be swapped for a
shared store (DynamoDB/Redis) when horizontal scaling makes that necessary,
without changing endpoints.

**Status.** Accepted.

---

## 2026-10-07 — Local mock mode for the full journey without AWS

**Decision.** Added an opt-in local mock mode (`APP_ENV=local` + `LOCAL_MOCK=true`)
that makes the entire user journey clickable locally without AWS: in-memory
repositories, an inline job runner (SQS/AgentCore stand-in that runs the agents
synchronously on enqueue), a local keyword-based knowledge base
(ingest/retrieve), and a deterministic mock text generator. AI output is prefixed
`[local mock output — not real AI generation]`; the frontend shows an amber
banner when `VITE_LOCAL_MOCK=true`.

**Why.** Bedrock KB + Neptune Analytics have no local emulator, so the AI flows
couldn't be exercised locally. Mock mode enables demos and manual testing of the
whole flow at zero AWS cost, while the fakes implement the **same ports** as the
real integrations so the application services are reused unchanged and the AWS
path remains the default. The explicit mock markers keep it honest — mocked
output is never mistaken for real generation.

**Status.** Accepted. See `docs/local-mock.md` for run instructions.

---

## 2026-10-07 — E2E validation as a portable smoke script

**Decision.** End-to-end validation (group 15) is a stdlib-only Python script
(`scripts/e2e_smoke.py`) that drives the full happy path over HTTP and asserts
the spec's requirement checks, runnable unchanged against local-mock (now) and
real AWS (post-deploy) via `--base-url`/`--token`. A companion checklist
(`docs/e2e-validation.md`) maps each step to its requirement.

**Why.** The real-AWS run depends on a live deployment (cost + account), so
gating "done" on it would stall. A portable harness makes the critical path
verifiable immediately against local-mock and ready to point at the deployment
with zero changes.

**Status.** Accepted. Local-mock run: 16/16 checks pass. Real-AWS run pending
deployment.

---

## 2026-10-07 — SQS→AgentCore bridge as a dedicated dispatcher service

**Decision.** The async bridge (consume the job queue, invoke the matching
AgentCore agent runtime) is a dedicated **dispatcher** ECS service, not a thread
in the API and not a Lambda. It reuses the API container image with the
`src.workflows.dispatcher_main` entrypoint (command override in the task def),
routes by `job_type`, acks a message only on a successful invoke (failures
redeliver → DLQ), and has its own least-privilege task role (SQS receive/delete
+ `bedrock-agentcore:InvokeAgentRuntime`). The SQS receive/delete and the invoke
call are behind ports (`SqsConsumerPort`, `AgentInvokerPort`) so the loop is
unit-tested with fakes.

**Why.** AgentCore runtimes are invoked, not a native SQS event source, so
something must poll and invoke. A dedicated service keeps the API stateless,
matches the "tiers fail independently" principle, and respects the steering rule
against orchestration Lambda. The at-least-once + idempotent-agent design means
redelivery is safe. The real `invoke_agent_runtime` call was verified against the
boto3 `bedrock-agentcore` client (`agentRuntimeArn` + `payload`).

**Status.** Accepted. Enabled with `deploy_agents=true`.

---

## 2026-10-18 — Manual deploy with a single git-SHA image tag

**Decision.** Deploy to AWS manually (no CD pipeline for the live `dev`
environment): build all five images, tag them with the current short git SHA,
`terraform apply -var image_tag=<sha>`, then sync the frontend to S3 and
invalidate CloudFront. Unchanged images are retagged to the new SHA so every
image the Terraform run references exists under one consistent tag.

**Why.** The user wanted hands-on, demo-grade control over each release rather
than an always-on pipeline. A single SHA across all images makes a deployment a
single coherent, traceable unit (one tag = one commit = one apply) and keeps the
`image_tag` variable the only moving part of the apply. The GitHub Actions
pipeline (group 14) still runs the quality gates; it just isn't the deploy path
for this environment. Tradeoff accepted: a few manual steps per release and the
need to retag unchanged images.

**Operational note.** On Windows the Docker Desktop `desktop` credential helper
returned HTTP 400 on `docker login` to ECR; the workaround is a temporary
`--config` dir holding the base64 ECR auth, bypassing the helper. Images are
built `--platform linux/arm64 --provenance=false` (AgentCore and Graviton
Fargate require ARM64).

**Status.** Accepted.

---

## 2026-10-18 — GraphRAG retrieval filtering via metadata sidecar files

**Decision.** When ingesting, write each chunk's text as the document body and a
companion `<key>.txt.metadata.json` sidecar (`{"metadataAttributes": {...}}`)
carrying `user_id`/`book_id`, so Bedrock Knowledge Base treats them as
**filterable** attributes. Retrieval then filters on those attributes.

**Why.** Retrieval must be scoped to the authenticated user's own book
(security.md). Without the sidecar the metadata was not filterable and scoped
retrieval could not be enforced at the KB layer. Verified live
(`numberOfMetadataDocumentsScanned` > 0).

**Status.** Accepted. Books ingested before this change must be re-uploaded.

---

## 2026-10-18 — Generation model: Claude Sonnet 4.6; graph model: Haiku 4.5

**Decision.** Use `eu.anthropic.claude-sonnet-4-6` for answer/reading generation
and `eu.anthropic.claude-haiku-4-5` for GraphRAG graph construction, both via EU
inference profiles in `eu-central-1`.

**Why.** The earlier Sonnet 4 (`20250514`) reaches end-of-life 2026-06-15, so a
current model was required. GraphRAG graph construction only accepts
Haiku-family models, so that step is pinned to Haiku 4.5. `tech.md` notes that
model availability in `eu-central-1` must be confirmed per model.

**Status.** Accepted.

---

## 2026-10-18 — Cold-start mitigation: on-login warm-up, not always-on

**Decision.** On login the frontend calls `POST /api/v1/warmup`; the API fires a
background task that pings the three agent runtimes with `{"warmup": true}`, and
each agent returns `{"status": "warm"}` immediately (an early return before any
real work). SQS visibility timeout was reduced from 900s to 180s and the
dispatcher's AgentCore invoke is bounded (`read_timeout=120`).

**Why.** AgentCore runtimes cold-start, which made the first interaction slow and
could cascade with the old 15-minute visibility lock. Warming on login hides the
cold start behind the user's first navigation. An always-on scheduled ping or
provisioned concurrency was rejected as needless idle cost for a demo. The MCP
runtime is not warmed directly (it speaks the MCP protocol, not a plain JSON
warm-up payload).

**Status.** Accepted.

---

## 2026-10-18 — Discussion titles: LLM-generated, intent-based, refreshed while generic

**Decision.** Conversation titles are short (2–3 word) intent-based labels
generated by the discussion agent alongside the answer. The agent regenerates
the title during the opening turns, and also keeps regenerating it for as long
as the stored title is still a placeholder ("General chat"/none), so a topic that
emerges later replaces it. Once a real title is set it stabilizes. The frontend
also shows an instant client-derived title the moment a message is sent (from the
question text), which the agent's title then replaces on the response.

**Why.** The product wants a meaningful title, not a verbatim truncation of the
first question (the earlier approach, now removed). Passing the current title
into the agent lets it honor "replace the title if the earlier context wasn't
enough." The instant client title gives real-time feedback in the chat header
without waiting for the agent round-trip.

**Status.** Accepted. Supersedes the earlier "truncate the first question"
titling.

---

## 2026-10-18 — Discussion streaming is a frontend reveal, not end-to-end token streaming

**Decision.** The chat "streams" the assistant answer by progressively revealing
the already-returned text (a typewriter reveal with a caret), rather than
streaming tokens end-to-end from Bedrock through the MCP tool, the agent,
AgentCore, and FastAPI to the browser.

**Why.** The backend path is request/response: `generate_text` uses Bedrock
`invoke_model` (not the streaming variant) and returns a complete string; the
title and citations are derived *after* the answer. True token streaming would
require changing every tier (MCP tool, LangGraph node, AgentCore response,
FastAPI SSE) plus disabling CloudFront/ALB response buffering — a multi-tier,
high-risk change to a live, working system, for a mostly perceptual gain. The
reveal delivers the visible streaming effect with zero backend/infra risk and
preserves the citation and title flow. Honest tradeoff: time-to-first-token is
unchanged (the reveal starts only after the full answer arrives).

**Status.** Superseded by "Real end-to-end discussion streaming over SSE"
(2026-10-18). The CloudFront concern turned out not to block SSE when the
`CachingDisabled` policy is used (see the superseding entry).

---

## 2026-10-18 — Expired session is treated as logged out (client-side)

**Decision.** When the stored Cognito token is absent/expired, or any API call
returns 401, the frontend clears the local session and drops to logged-out so the
route guard sends the user to the in-app `/login` page. The deliberate "Sign out"
button still uses the Cognito Hosted UI logout; only *expiry* uses the local
clear (no Hosted UI round trip). The nav bar shows email + "Sign out" only when
authenticated, and a "Sign in" link otherwise.

**Why.** Previously an expired token left a stale "logged in" nav bar with a dead
session and no clear way back to login. Re-checking token validity on mount and
on tab focus, plus a 401 handler, keeps the UI honest without a jarring redirect
through the Hosted UI on every expiry.

**Status.** Accepted.

---

## 2026-10-18 — Library reflects started readings via a local activity flag

**Decision.** The backend reading list returns only *completed* readings, so the
Library couldn't show "Continue reading" until generation finished and the user
opened the result. The frontend now records, per user in localStorage, that a
reading was started for a book (the moment generation is kicked off) and uses that
to show "Continue reading" immediately; it reconciles with completed readings and
clears the flag when the book is removed.

**Why.** The user expects the Library to reflect that work is underway the instant
they start it, independent of backend job propagation. A small client-side flag
(same pattern as the existing `uploadedBooks` store) delivers that without a new
"list my jobs by book" backend endpoint.

**Status.** Accepted.

---

## 2026-10-18 — Keeping `flow.md` and `decisions.md` current is an enforced rule

**Decision.** `development.md` now explicitly requires updating `docs/flow.md`
whenever a boundary, tier, endpoint, service, integration, agent behavior,
frontend flow, or runtime/deploy behavior changes, and appending a **dated**
`docs/decisions.md` entry (supersede, never rewrite) for any meaningful or
non-obvious decision — including live-deploy, bug-fix, and UX work, not just new
features. "Definition of done" names both files. A `Stop` hook
(`.kiro/hooks/docs-currency-check.json`) reminds the agent to check doc currency
at the end of each turn.

**Why.** Across a long live-deploy/bug-fix session both docs drifted because the
prior steering only said "update documentation" in the abstract and referenced
these files as *pointers*, not as a maintenance obligation. Naming the files and
the triggering conditions — plus a hook backstop — makes the existing "living
record" intent explicit so it no longer depends on memory. Tradeoff accepted: a
small per-change overhead to keep the docs honest; the hook can't force judgment,
only prompt the check.

**Status.** Accepted.

---

## 2026-10-18 — Discussion personas (human podcast voice by default)

**Decision.** Discussions answer in a natural, human "podcast discussion" voice
rather than a formal summary. A conversation carries an optional `persona`
(voice/style) chosen at creation, defaulting to **Podcast Host**. Options:
Podcast Host (default), Scholar, Coach, Skeptic, Storyteller
(`agents/discussion/personas.py`). The persona's voice is injected into the
grounded prompt; the grounding and citation rules are unchanged — persona changes
*delivery*, never the facts. `GET /api/v1/discussions/personas` lists them; the
persona is stored on the conversation and surfaced on the discussion list and the
chat header.

**Why.** The default answers read like a careful source summary, which felt
formal and un-human. A persona layer makes the discussion engaging and
conversational while keeping it grounded. A small, fixed set of distinct voices
(selectable, optional, with a sensible default) gives variety without
uncontrolled prompt sprawl. The grounded prompt itself was also rewritten to
instruct a direct, conversational, specifics-first answer rather than a report.

**Status.** Accepted.

---

## 2026-10-18 — Adaptive reading prompt preserves the book's specifics

**Decision.** The adaptive-reading generation prompt (`agents/adaptive_reading/
nodes.py::build_prompt`) now explicitly instructs the model to keep the book's
concrete specifics (named people, examples, data, distinctive terminology) and
the author's framing, to use plain direct language, and to avoid vague filler —
instead of the earlier terse "condense into coherent prose, preserve meaning".

**Why.** Output sometimes read generically because the prompt asked only for a
faithful condensed summary without protecting the specifics that make a given
book distinctive. Preserving concrete detail and the author's line of reasoning
is what stops the reading from sounding like a template. The deterministic
ranking/selection pipeline is unchanged; this is a prompt-quality improvement to
the single generation step.

**Status.** Accepted.

---

## 2026-10-18 — Added a playful "The Wit" discussion persona

**Decision.** Added a sixth discussion persona, **The Wit** (`wit`): a witty,
playfully sarcastic voice for a more fun discussion. Its voice instructions keep
the sass light and good-natured — tease the ideas, never the listener; never
mean/crude; and correctness wins over the joke. It rides on the same grounded,
citation-respecting answer as every other persona.

**Why.** Requested for a bit of fun. The persona layer is generic (enum +
profile + `/discussions/personas` endpoint drives the frontend picker), so this
is a localized addition with no pipeline or frontend changes. The guardrails in
the voice text keep the humor from undermining accuracy or turning rude.

**Status.** Accepted. Extends the 2026-10-18 personas decision.

---

## 2026-10-18 — Real end-to-end discussion streaming over SSE

**Decision.** The discussion answer now streams token-by-token end to end,
replacing the frontend typewriter reveal. The path:

- MCP tier: new `generate_text_stream` tool using Bedrock
  `invoke_model_with_response_stream`, forwarding each delta as an MCP progress
  notification (``message``). The agent's `McpToolClient.call_stream` consumes
  the progress callback and yields deltas.
- Agent runtime: the discussion `@app.entrypoint` returns a GENERATOR when
  ``stream`` is set; `BedrockAgentCoreApp` then emits `text/event-stream`
  automatically (SSE), yielding ``delta`` events then a ``final`` event with
  answer/citations/title/summary.
- Backend: `AgentCoreResponseInvoker.invoke_stream` sets
  ``accept=text/event-stream`` and iterates the streaming body; a new endpoint
  `POST /api/v1/discussions/{id}/messages/stream` returns a FastAPI
  `StreamingResponse(text/event-stream)` with anti-buffering headers
  (`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`) and an
  initial ``: open`` comment to flush immediately.
- Frontend: `streamMessage` reads `response.body` via a reader (fetch streaming,
  not EventSource, so it can POST a body + attach the bearer token), parses SSE
  frames, and reveals tokens through a paced render queue (~steady, readable
  rate — deliberately not instant bursts).

**No domain / CloudFront.** Earlier analysis assumed CloudFront would buffer SSE
and force a custom domain + ACM cert. That was wrong: CloudFront with the AWS
managed `CachingDisabled` policy (which the API distribution already uses) does
not buffer the response, so SSE passes through on the existing
`*.cloudfront.net` API URL. No domain was added.

**Navigate-away behavior.** Generation + persistence run in a DETACHED asyncio
task that is shielded and NOT tied to the response connection. If the user
navigates away mid-stream, the live view stops (the browser closes the SSE
connection) but the agent keeps generating server-side and persists the full
message to DynamoDB. On return, the chat loads the thread from the DB and shows
the completed answer. No hidden background SSE connection is kept in the browser.

**Why.** The user explicitly rejected the frontend reveal as a "cheap mockup"
and asked for real backend streaming, accepting the multi-tier change. The
detached-task design makes persistence robust to client disconnect (FastAPI may
cancel a `StreamingResponse` generator on disconnect, which would otherwise lose
the answer). The buffered `generate_text` tool and non-streaming `answer` path
are retained for the adaptive-reading agent and as a fallback.

**Status.** Accepted. Supersedes "Discussion streaming is a frontend reveal".

---

## 2026-10-18 — Streaming falls back to the tool return value (MCP progress not delivered over AgentCore)

**Decision.** `McpToolClient.call_stream` now treats the streaming tool's RETURN
VALUE (the complete text) as the source of truth, emitting any portion not
already delivered as live progress deltas. Progress notifications are still used
for live deltas when they arrive, but are no longer required for a correct
answer.

**Why (root cause).** With the first streaming build the discussion answer came
back EMPTY. Agent logs showed the runtime did stream and did call the MCP tool,
but the MCP server→client GET SSE channel repeatedly returned
`405 Method Not Allowed` ("GET stream disconnected, reconnecting") — i.e.
AgentCore's MCP transport does not deliver the tool's progress notifications
(our token deltas) back to the agent. `call_stream` had been yielding ONLY those
progress deltas, so zero deltas arrived and the answer was empty. Capturing the
tool's return value and reconciling against delivered deltas makes the answer
correct whether or not progress notifications get through.

**Resulting behavior (honest).** In the current AgentCore MCP environment,
progress deltas do not arrive, so the answer is emitted as effectively one chunk
and the UI's paced reveal animates it smoothly — still real server-side
generation (Bedrock `invoke_model_with_response_stream` runs in the MCP tier),
but not token-granular on the wire end-to-end. If/when AgentCore delivers MCP
progress notifications, finer live deltas light up automatically with no code
change. The buffered-to-UI reveal remains comfortable to read either way.

**Status.** Accepted. Fixes the empty-answer regression from the initial
streaming build.
