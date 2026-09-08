---
inclusion: always
---

# Product Steering — Book Companion

## Vision

Build a book companion for people who do not naturally read books, struggle to start, or struggle to finish. The product should make books approachable by turning a large reading commitment into small, meaningful reading sessions while preserving the ideas, arguments, examples, and context that make a book valuable.

The product is not a book-hosting platform and should not encourage users to replace full books with shallow summaries. Its purpose is to reduce friction, build a reading habit, and make returning to a book easier.

## Core user journey

`I don't really read books → Discover → Why should I care? → Start → 3/5/10 minute reading → Ask/Discuss → Save progress → Come back → Continue`

## Primary MVP features

1. **Read / Adaptive Reading**
   - Let users choose approximately 3, 5, or 10 minutes.
   - 3 minutes: quick understanding of the central idea and most important argument.
   - 5 minutes: balanced reading with major arguments, explanations, examples, and context.
   - 10 minutes: deeper condensed reading with important arguments, evidence/examples, relationships, and nuance.
   - Output must read like coherent condensed prose, not a bullet dump or arbitrary text truncation.

2. **Chat / Discussion**
   - Let users ask questions about books they are authorized to access.
   - Use GraphRAG for retrieval so answers can connect concepts, entities, arguments, and evidence across the book.
   - Ground answers in source material and provide chapter/page/section/source references when available.
   - Preserve discussion context so users can continue later.

3. **Recommendations**
   - Recommend books using book metadata, user reading activity, saved concepts, preferences, and similarity signals.
   - Keep recommendation logic understandable and testable.

## Supporting MVP features

- Search books by title, author, or ISBN.
- Show metadata, cover, description, categories, identifiers, estimated original reading time, and legitimate buy/borrow links when available.
- Allow users to upload authorized PDF copies.
- Keep uploaded books private to the owning user.
- Show original reading time separately from adaptive reading time.
- Dynamic content focuses within adaptive reading (including summary-style focuses).
- Save reading progress and continue from the last position.
- Continue discussions for uploaded books.
- Async job status for ingestion and adaptive reading generation.
- Security, observability, validation, and audit-friendly logging.

## Reading modes

Adaptive reading has three modes — `quick_read`, `balanced_read`, `deep_read` —
mapped to the ~3/5/10-minute experience above. Alongside these, users can pick a
content focus (executive summary, key ideas, key arguments, practical
takeaways, examples, chapter summary, concept explanation, or narrative summary
where applicable). The exact focus enumeration and identifiers live in the MVP
spec.

The UI must clearly distinguish **original estimated reading time** from
**selected adaptive reading time**.

## Legal and content boundaries

- The application must only process content the user is authorized to access.
- External book URLs are discovery/buy/borrow links only; arbitrary external URLs must not be ingested.
- Do not scrape, bypass paywalls, defeat DRM, or provide unauthorized book downloads.
- User-uploaded content remains private and access-controlled.

## Product principles

- Reduce friction, do not remove the value of reading.
- Make every AI output useful, readable, and grounded.
- Prefer meaningful depth over generic summaries.
- Make the 3/5/10-minute experience the product differentiator.
- Keep the MVP focused on Read, Discuss, and Recommend.
- Build production-quality foundations without unnecessary infrastructure.
- Every feature must have a clear user outcome.

## Out of scope for MVP

- Hosting or distributing copyrighted books.
- Social network features.
- Public book uploads.
- Full audiobook/podcast production.
- Complex multi-agent orchestration.
- Custom vector database or custom graph database pipeline outside managed Bedrock GraphRAG.
- Microservice sprawl.
- Kubernetes.
