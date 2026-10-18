# Book Companion — Frontend

React + TypeScript + Vite, styled with Tailwind CSS. shadcn/ui components are
added incrementally as UI is built (task group 12).

## Layout

```
src/
  app/            App entry (main.tsx, App.tsx), global styles
  components/     Shared/reusable UI components
  features/       Feature slices: auth, books, reading, discussion, recommendations
  hooks/          Reusable React hooks
  services/       API client and per-domain API calls
  stores/         Client-side state
  types/          Shared TypeScript types
  utils/          Utilities
tests/            Component and integration tests
```

## Commands

```bash
npm install
npm run dev         # dev server on :5173 (proxies /api and /health to :8000)
npm run build       # type-check + production build
npm run typecheck   # tsc --noEmit
npm run lint        # eslint
```

During local development, API requests to `/api` and `/health` are proxied to
the FastAPI backend at `http://localhost:8000` (see `vite.config.ts`).
