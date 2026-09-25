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
