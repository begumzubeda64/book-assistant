# Requirements Document

MVP requirements for Book Companion.

## Introduction

Book Companion helps people who do not naturally read books to start, engage
with, and finish them by turning a large reading commitment into short,
meaningful sessions (approximately 3, 5, or 10 minutes) while preserving the
ideas, arguments, examples, and context that make a book valuable. The MVP
delivers three primary capabilities — adaptive reading, GraphRAG discussion, and
recommendations — supported by book discovery, authorized PDF upload,
asynchronous job processing, and reading-progress tracking.

This document defines the MVP requirements as user stories with acceptance
criteria in EARS notation (`WHEN [condition] THE SYSTEM SHALL [behavior]`, or
`THE SYSTEM SHALL [behavior]` for invariants). The design in `design.md`
implements these requirements, and the tasks in `tasks.md` reference them for
traceability.

## Requirements

### Requirement 1: Authentication and user identity

**User Story:** As a reader, I want to sign in securely and have my identity
recognized on every request, so that only I can access my books and data.

#### Acceptance Criteria

1. WHEN a user authenticates THE SYSTEM SHALL use Amazon Cognito to establish identity.
2. WHEN an authenticated API request is received THE SYSTEM SHALL derive the user identity from a validated Cognito JWT.
3. WHEN a user requests a resource owned by another user THE SYSTEM SHALL deny access to that user's uploaded books, conversations, progress, jobs, or generated private artifacts.

### Requirement 2: Book discovery

**User Story:** As a reader, I want to search for books and see their details,
so that I can decide what to read and how to access it legitimately.

#### Acceptance Criteria

1. WHEN a user searches by title, author, or ISBN THE SYSTEM SHALL query supported book metadata providers and return normalized book metadata.
2. WHEN book metadata is available THE SYSTEM SHALL display the title, author, cover, description, categories, identifiers, and original estimated reading time.
3. WHEN legitimate buy/borrow links are available THE SYSTEM SHALL display them as external discovery links.
4. THE SYSTEM SHALL NOT ingest arbitrary external book URLs.

### Requirement 3: Authorized PDF upload

**User Story:** As a reader, I want to upload a PDF I am authorized to use, so
that I can read and discuss my own book privately.

#### Acceptance Criteria

1. WHEN a signed-in user uploads a PDF THE SYSTEM SHALL require the user to confirm they are authorized to use the content before accepting it.
2. WHEN an upload is requested THE SYSTEM SHALL issue a short-lived presigned S3 upload URL rather than proxying the entire PDF through FastAPI.
3. WHEN a PDF is uploaded THE SYSTEM SHALL store it privately and associate it with the owning user.
4. WHEN an upload completes THE SYSTEM SHALL create an asynchronous `BOOK_INGESTION` job.

### Requirement 4: Reading time and adaptive reading

**User Story:** As a reader, I want to generate a coherent condensed reading of a
chosen length and focus, so that I can understand a book in a few minutes without
losing its meaning.

#### Acceptance Criteria

1. WHEN sufficient word-count information is available THE SYSTEM SHALL show the estimated original reading time.
2. WHEN a user configures adaptive reading THE SYSTEM SHALL allow choosing approximately 3, 5, or 10 minutes.
3. WHEN a user configures adaptive reading THE SYSTEM SHALL allow choosing Quick Read, Balanced Read, or Deep Read.
4. WHEN a user configures adaptive reading THE SYSTEM SHALL allow selecting a focus such as key arguments, key ideas, examples, practical takeaways, or chapter summary.
5. WHEN adaptive reading is generated THE SYSTEM SHALL produce coherent condensed reading rather than simple truncation or an unstructured bullet list.
6. WHEN source references are available THE SYSTEM SHALL retain them in the generated reading.
7. WHEN adaptive reading is requested THE SYSTEM SHALL execute generation asynchronously and return a job ID immediately.

### Requirement 5: GraphRAG discussion

**User Story:** As a reader, I want to ask questions about a book and get grounded
answers that connect ideas across it, so that I can understand and explore the
material.

#### Acceptance Criteria

1. WHEN a user asks a question about an authorized book THE SYSTEM SHALL answer it.
2. WHEN discussion retrieval runs THE SYSTEM SHALL use Bedrock Knowledge Bases GraphRAG backed by Neptune Analytics.
3. WHEN a question requires relationships across chapters, concepts, entities, or arguments THE SYSTEM SHALL support answering it.
4. WHEN source metadata is available THE SYSTEM SHALL include chapter/page/section/source references in answers.
5. WHEN a user returns to a discussion THE SYSTEM SHALL have stored prior messages and allow the user to continue.

### Requirement 6: Reading progress

**User Story:** As a reader, I want my progress saved automatically, so that I can
stop and continue later from where I left off.

#### Acceptance Criteria

1. WHEN a user reads THE SYSTEM SHALL save the current book/chapter/position and the relevant reading mode.
2. WHEN a user returns THE SYSTEM SHALL provide a continue-reading entry point based on saved progress.
3. WHEN a user finishes a chapter or book THE SYSTEM SHALL support recording completion state.

### Requirement 7: Recommendations

**User Story:** As a reader, I want relevant book recommendations with a reason,
so that I can decide what to read next.

#### Acceptance Criteria

1. WHEN recommendations are requested THE SYSTEM SHALL recommend books using transparent metadata and behavioral signals available in the MVP.
2. WHEN a recommendation reason can be derived safely THE SYSTEM SHALL provide a concise reason in the UI.

### Requirement 8: Asynchronous jobs

**User Story:** As a reader, I want long-running work to run in the background with
visible status, so that the app stays responsive.

#### Acceptance Criteria

1. WHEN a job runs THE SYSTEM SHALL expose its status including queued, processing, completed, and failed states.
2. WHEN long-running work is triggered THE SYSTEM SHALL use SQS and/or Step Functions rather than blocking FastAPI requests.
3. WHEN a job is retried THE SYSTEM SHALL execute idempotently or in a safely retryable manner so duplicate expensive results are not produced.

### Requirement 9: Security and observability

**User Story:** As an operator, I want the system to run privately and be
observable, so that it is secure and supportable.

#### Acceptance Criteria

1. THE SYSTEM SHALL run FastAPI containers on ECS Fargate without public IP addresses.
2. WHEN public API traffic is served THE SYSTEM SHALL use HTTPS through the Application Load Balancer.
3. WHEN an API request is received THE SYSTEM SHALL validate inputs using Pydantic and perform server-side authorization checks.
4. THE SYSTEM SHALL NOT log secrets, tokens, or raw private book content.
5. THE SYSTEM SHALL provide CloudWatch logs and service/application metrics.

### Requirement 10: Non-functional requirements

**User Story:** As a developer, I want the backend to be reproducible, scalable,
stateless, and documented, so that it is easy to develop and operate.

#### Acceptance Criteria

1. WHEN developing locally THE SYSTEM SHALL run the FastAPI backend using the same application structure that runs in the ECS container.
2. THE SYSTEM SHALL be built from a Dockerfile and deployed through ECR.
3. THE SYSTEM SHALL support horizontal scaling through Fargate service auto scaling.
4. THE SYSTEM SHALL remain stateless, keeping persistent application state in managed services.
5. THE SYSTEM SHALL expose OpenAPI documentation suitable for local development and API review.

## Glossary

- **Adaptive reading** — A generated, coherent condensed version of a book or
  chapter targeted at an approximate reading duration (3, 5, or 10 minutes), not
  a truncation or bullet dump.
- **Reading mode** — The depth of an adaptive reading: Quick Read (`quick_read`),
  Balanced Read (`balanced_read`), or Deep Read (`deep_read`).
- **Focus** — The content emphasis of an adaptive reading (e.g. key arguments,
  key ideas, examples, practical takeaways, chapter summary).
- **Original reading time** — The estimated time to read the full source at a
  default reading speed, shown separately from the selected adaptive duration.
- **GraphRAG** — Retrieval-augmented generation using Bedrock Knowledge Bases
  backed by Neptune Analytics, combining vector search with graph traversal over
  entities, concepts, and relationships. A vector-only path is not GraphRAG.
- **Discussion / conversation** — A persisted question-and-answer thread about an
  authorized book, grounded in retrieved source material with source references.
- **Job** — An asynchronous unit of work (`BOOK_INGESTION`, `ADAPTIVE_READING`)
  created by the API, tracked by status, and executed off the request path via
  SQS/Step Functions.
- **Ingestion** — The pipeline that extracts and prepares an authorized uploaded
  PDF and loads it into the Bedrock Knowledge Base / Neptune Analytics graph.
- **Recommendation** — A suggested book produced by transparent, testable scoring
  over metadata and reading-behavior signals.
- **user_id** — The authenticated user identity derived from a validated Cognito
  JWT, used for all server-side ownership checks.
- **EARS** — Easy Approach to Requirements Syntax; acceptance criteria are written
  as `WHEN [condition] THE SYSTEM SHALL [behavior]` or `THE SYSTEM SHALL
  [behavior]` for invariants.
