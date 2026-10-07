# Screenshots

Capture these from **local mock mode** (`docs/local-mock.md`) so the primary
journey can be shown without a live AWS deployment. The amber "local mock mode"
banner is expected in captures and signals that AI output is simulated.

Suggested set (save alongside this file and embed in the root README):

| File | Screen | What to show |
|------|--------|--------------|
| `01-discover.png` | Discover | Search results for a real title |
| `02-book-detail.png` | Book details | Metadata, cover, original reading time, links |
| `03-library-upload.png` | My Library | Upload form with the authorization checkbox |
| `04-reading-config.png` | Reading config | Quick/Balanced/Deep + focus selector |
| `05-reading-result.png` | Reading result | Condensed prose + source references + word counts |
| `06-discussion.png` | Discussion | A grounded answer with citations |
| `07-library-progress.png` | My Library | "Continue reading" with saved progress |

A short GIF of steps 01 → 06 (`journey.gif`) makes a strong README header.

## How to capture

1. Start backend + frontend in local mock mode (see `docs/local-mock.md`).
2. Walk the journey: sign in → search → upload → read → discuss → continue.
3. Capture each screen at ~1280px wide; keep the mock banner visible.
