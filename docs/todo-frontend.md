# Frontend — Code Issues & Suggested Fixes

> Generated from full codebase review of `frontend/src/`.

---

## App.tsx

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | LOW | No error boundary for route failures | Add `<ErrorBoundary>` wrapper or React Router `errorElement` |
| 2 | LOW | No 404 catch-all route | Add `<Route path="*" element={<NotFound />} />` |

---

## Dashboard.tsx

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `[string, any]` type assertion for agent data (line 70) — using `any` | Create `AgentData` interface and use proper typing |
| 2 | MEDIUM | `useQuery` doesn't check `error` state — no error display | Add `const { data, isLoading, error } = useQuery(...)` and show error UI |
| 3 | MEDIUM | Agent status has no `isLoading` check — flash of empty content | Add loading skeleton/spinner for agent status section |
| 4 | LOW | Hardcoded agent count `count={5}` (line 51) | Calculate from data: `count={Object.keys(agentStatus?.agents || {}).length}` |
| 5 | LOW | No empty state handling for zero bets | Show "No bets found" message when `bets?.length === 0` |

---

## utils/api.ts

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No timeout configured on axios instance — requests could hang indefinitely | Add `timeout: 30000` to `axios.create()` config |
| 2 | MEDIUM | Error interceptor doesn't log or transform errors | Add error interceptor: `instance.interceptors.response.use(null, errorHandler)` |
| 3 | LOW | BaseURL is `/` — assumes API on same origin | Use `import.meta.env.VITE_API_BASE_URL || '/'` for Vite |
| 4 | LOW | No request retry logic for transient failures | Add `axios-retry` or manual retry with backoff |

---

## types/api.ts

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `AgentData.recent_mistakes` typed as `Array<{ type: string; error?: string }>` — too loose | Create dedicated `MistakeRecord` interface |
| 2 | MEDIUM | `BetItem.edge` and `BetItem.probability` should be required, not optional | Change to required fields: `edge: number; probability: number` |
| 3 | LOW | No union type for parlay status | Add `type ParlayStatus = 'pending' \| 'won' \| 'lost' \| 'partial'` |
| 4 | LOW | No validation/assertion utilities for API responses | Add runtime validation with `zod` or manual type guards |

---

## Components (General)

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | No global error boundary component | Create `ErrorBoundary.tsx` in `components/` |
| 2 | MEDIUM | No loading state components (skeleton, spinner) | Create reusable `LoadingSkeleton.tsx` and `Spinner.tsx` |
| 3 | LOW | No accessibility attributes on interactive elements | Add `aria-label`, `role` attributes where needed |
| 4 | LOW | No dark mode toggle (Tailwind supports it) | Add `dark:` variants to existing styles |

---

## Build & Configuration

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | `tsconfig.json` enables `noUnusedLocals` and `noUnusedParameters` — strict but good | No fix needed — this is a best practice |
| 2 | LOW | No bundle analysis configured | Add `rollup-plugin-visualizer` to Vite config |
| 3 | LOW | No PWA/offline support | Consider `vite-plugin-pwa` for mobile users |

---

## Testing

| # | Severity | Issue | Suggested Fix |
|---|----------|-------|---------------|
| 1 | MEDIUM | Only 2 test files exist (`Layout.test.tsx`, `api.test.ts`) — low coverage | Add tests for each page component and utility |
| 2 | MEDIUM | No integration tests for API interactions | Add MSW (Mock Service Worker) for API mocking |
| 3 | LOW | No snapshot tests for components | Add `.toMatchSnapshot()` tests for key components |

---

## Summary

| Area | Issues | Highest Severity |
|------|--------|-----------------|
| App.tsx | 2 | LOW |
| Dashboard.tsx | 5 | MEDIUM |
| api.ts | 4 | MEDIUM |
| types/api.ts | 4 | MEDIUM |
| Components | 4 | MEDIUM |
| Build & Config | 3 | MEDIUM |
| Testing | 3 | MEDIUM |

**Total: 25 issues across frontend**
