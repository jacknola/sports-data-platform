# Frontend Agent — Actionable Tasks

> This agent handles all React/TypeScript frontend changes: components, pages, API integration, styling, and testing.

---

## Identity & Scope

- **Name:** Frontend Agent
- **Language:** TypeScript (React 18)
- **Build:** Vite
- **Styling:** Tailwind CSS
- **State:** React Query (`@tanstack/react-query`)
- **Responsibilities:** Fix bugs, implement UI features, improve UX, add tests

---

## Setup Commands

```bash
cd frontend
npm install
```

## Verification Commands

```bash
# Dev server
npm run dev

# Build (TypeScript check + Vite build)
npm run build

# Linting
npm run lint

# Tests
npx vitest run

# Type check only
npx tsc --noEmit
```

---

## Priority Tasks

### P0 — Bug Fixes

- [ ] **Add error boundary** to `App.tsx`
  - Create `components/ErrorBoundary.tsx` using React error boundary pattern
  - Wrap `<Routes>` in `<ErrorBoundary>`
  ```tsx
  import { ErrorBoundary } from './components/ErrorBoundary';
  // In App:
  <ErrorBoundary>
    <Routes>...</Routes>
  </ErrorBoundary>
  ```

- [ ] **Add 404 catch-all route** to `App.tsx`
  ```tsx
  <Route path="*" element={<NotFound />} />
  ```

- [ ] **Fix type safety in Dashboard.tsx**
  - Replace `[string, any]` with proper `AgentData` interface
  - Add error state handling from `useQuery`
  - Add loading skeleton for agent status

### P1 — API Layer Improvements

- [ ] **Add timeout to axios** in `utils/api.ts`
  ```typescript
  const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/',
    timeout: 30000,
  });
  ```

- [ ] **Add error interceptor** in `utils/api.ts`
  ```typescript
  api.interceptors.response.use(
    (response) => response.data,
    (error) => {
      console.error('API Error:', error.response?.status, error.message);
      return Promise.reject(error);
    }
  );
  ```

- [ ] **Improve TypeScript types** in `types/api.ts`
  - Create `MistakeRecord` interface for agent mistakes
  - Make `BetItem.edge` and `BetItem.probability` required fields
  - Add `ParlayStatus` union type

### P2 — UI/UX Improvements

- [ ] **Add loading states** to all pages
  - Create reusable `components/LoadingSkeleton.tsx`
  - Create `components/Spinner.tsx`
  - Use in Dashboard, Bets, Parlays pages

- [ ] **Add empty states** to all list pages
  - "No bets found" for Bets page
  - "No parlays available" for Parlays page
  - "No analysis results" for Analysis page

- [ ] **Add accessibility attributes**
  - `aria-label` on interactive elements
  - `role="alert"` on error messages
  - `aria-live="polite"` on loading states

- [ ] **Fix hardcoded agent count** in Dashboard.tsx
  ```tsx
  count={Object.keys(agentStatus?.agents || {}).length}
  ```

### P3 — Feature Implementation

- [ ] **RAG Pipeline Dashboard** (from problem statement)
  - Create `pages/RAGPipeline.tsx` page component
  - Display semantic search results
  - Show embedding status and vector store health
  - Add search interface for historical data retrieval

- [ ] **Create prop analysis results page**
  - Display ML model outputs (XGBoost, LightGBM, Bayesian)
  - Show confidence intervals and edge percentages
  - Kelly sizing recommendations
  - DvP matchup grades

- [ ] **Add dark mode toggle**
  - Use Tailwind `dark:` variants
  - Store preference in localStorage

### P4 — Testing

- [ ] **Add page render tests**
  - `Dashboard.test.tsx` — render, loading, error states
  - `Bets.test.tsx` — bet list rendering, empty state
  - `Parlays.test.tsx` — parlay display, status colors

- [ ] **Add API mock tests**
  - Install MSW: `npm install -D msw`
  - Create `test/mocks/handlers.ts` with API mocks
  - Test API integration in components

- [ ] **Add component tests**
  - `QuickStats.test.tsx` — stat card rendering
  - `ActionCard.test.tsx` — click handling
  - `AgentStatus.test.tsx` — status indicator states

---

## Code Style Rules

1. Functional components with hooks only — no class components
2. React Query for all server state — no Redux/Context for global state
3. Tailwind CSS only — no inline styles unless dynamic
4. Custom colors: `primary-*`, `accent-*`
5. Path alias: `@/*` maps to `./src/*`
6. All API requests prefixed with `/api`
7. Use `import.meta.env.VITE_*` for environment variables
8. Axios client in `utils/api.ts` unwraps `response.data` via interceptor

---

## File Structure Convention

```
src/
├── components/         # Reusable components
│   ├── ErrorBoundary.tsx
│   ├── LoadingSkeleton.tsx
│   └── [Component].tsx
├── pages/              # Route-level pages
│   └── [Page].tsx
├── utils/              # Utility functions
│   └── api.ts
├── types/              # TypeScript interfaces
│   └── api.ts
└── test/               # Test setup
    └── setup.ts
```

---

## Testing Checklist

After any change:
1. `npm run build` — no TypeScript errors
2. `npm run lint` — no ESLint warnings
3. `npx vitest run` — all tests pass
4. Visual verification in browser at `http://localhost:3000`
