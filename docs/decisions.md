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
