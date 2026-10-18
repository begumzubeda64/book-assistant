# End-to-End Validation (spec group 15)

The critical-path happy flow and its pass criteria. Automated by
`scripts/e2e_smoke.py`; this doc is the human checklist and the
requirement-traceability map.

## Running

```bash
# Local mock (no AWS): start the backend in mock mode, then:
python scripts/e2e_smoke.py --base-url http://localhost:8000

# Real deployment (Cognito): obtain an access token, then:
python scripts/e2e_smoke.py --base-url https://<api-host> --token "$JWT"
```

Exit code 0 = every step passed. Only the standard library is required.

## Critical path → requirements

| # | Step | Requirement | Pass criteria |
|---|------|-------------|---------------|
| 1 | Sign in | 1.1/1.2 | Authenticated session (Cognito JWT, or local-dev bypass locally) |
| 2 | Search a book, open details | 2.1/2.2 | `/books/search` returns normalized metadata (≥1 item) |
| 3 | Upload an authorized PDF | 3.1/3.2/3.3 | Confirmation required; presigned URL issued; direct-to-S3; private per-user key |
| 4 | Ingestion job completes | 3.4/8.1 | `BOOK_INGESTION` job reaches `COMPLETED` |
| 5 | Generate a 5-minute balanced reading | 4.7/4.5/4.6 | Returns `job_id` immediately; result is coherent prose within budget, with source refs |
| 6 | Ask a cross-chapter question | 5.1/5.3/5.4 | GraphRAG-grounded answer with source references |
| 7 | Save progress, return & continue | 6.1/6.2 | Saved position is read back on continue |
| 8 | Recommendations | 7.1 | Recommendations endpoint responds (items appear once signals exist) |
| 9 | Unauthorized resource access rejected | 1.3 | Another user's / unknown resource returns 403/404 |

## Scope notes

- **Local mock mode** exercises the full flow with deterministic, clearly-marked
  AI output and in-memory stores — ideal for CI-style verification and demos.
- **Real AWS** additionally validates Cognito, S3 presign/PUT, DynamoDB, SQS →
  AgentCore agents, and Bedrock KB + Neptune Analytics GraphRAG. The e2e script
  is identical; only `--base-url`/`--token` change.
- Recommendations (step 8) returns an empty list until a reading-history/
  saved-concepts store populates user signals (see `docs/decisions.md`); the
  endpoint contract is still validated.
