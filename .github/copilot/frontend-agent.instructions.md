---
name: frontend-agent
description: >
  Fix bugs, implement features, and improve UI in the React/TypeScript frontend.
  Trigger for changes to frontend/src/**, frontend/package.json, or frontend/vite.config.ts.
  Uses React 18, TypeScript, Vite, Tailwind CSS, and React Query.
applyTo: 'frontend/**'
---

# Frontend Agent

You are the Frontend Agent for the sports-data-platform. When making changes
to React/TypeScript frontend code, follow these rules strictly.

## Before Any Change

1. Read `docs/todo-frontend.md` for known issues.
2. Run: `cd frontend && npm run build` (TypeScript check)
3. Run: `cd frontend && npm run lint` (ESLint)

## Conventions (Strict)

- **Components:** Functional with hooks only. No class components.
- **Server state:** React Query (`@tanstack/react-query`) for all API data. No Redux or Context for server state.
- **Styling:** Tailwind CSS only. Custom colors: `primary-*`, `accent-*`. No inline styles unless dynamically computed.
- **Types:** No `any` type. No `@ts-ignore`. No `@ts-expect-error`. Create proper interfaces in `src/types/api.ts`.
- **API calls:** Use `src/utils/api.ts` typed axios wrapper. All requests prefixed with `/api` for Vite proxy routing.
- **Path alias:** `@/*` maps to `./src/*`.
- **Env vars:** Use `import.meta.env.VITE_*` pattern. Never expose secrets to frontend.
- **Strict mode:** `noUnusedLocals` and `noUnusedParameters` are enabled in `tsconfig.json`.

## API Client Pattern

The axios wrapper in `src/utils/api.ts` unwraps `response.data` via interceptor. Callers receive `T` directly:

```typescript
import api from '@/utils/api';

// Returns T directly, not AxiosResponse<T>
const data = await api.get<PropsResponse>('/api/v1/props/nba');
```

## Component Pattern

```tsx
import { useQuery } from '@tanstack/react-query';
import api from '@/utils/api';

interface PropsData {
  player: string;
  line: number;
  edge: number;
}

export default function PropsTable() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['props', 'nba'],
    queryFn: () => api.get<PropsData[]>('/api/v1/props/nba'),
    staleTime: 60_000,
  });

  if (isLoading) return <div className="animate-pulse h-64 bg-gray-800 rounded-lg" />;
  if (error) return <div className="text-red-400">Failed to load props</div>;

  return (
    <div className="p-4">
      {data?.map(prop => (
        <div key={prop.player} className="bg-gray-900 rounded-lg p-3 mb-2">
          <span className="text-primary-400">{prop.player}</span>
          <span className="text-accent-300 ml-2">{(prop.edge * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}
```

## Page Structure

Pages live in `src/pages/` and map to routes:
- `Dashboard.tsx` — Main overview
- `Bets.tsx` — Bet tracking and history
- `Parlays.tsx` — Parlay suggestions
- `Analysis.tsx` — Sharp money analysis
- `CollegeBasketball.tsx` — NCAAB analysis
- `Agents.tsx` — Agent system status
- `Settings.tsx` — Configuration

## Key Rules

- All edge values from the API are decimal fractions (0.05 = 5%). Multiply by 100 for display.
- FanDuel is the primary book. Optimize display and UX around FanDuel data.
- Win probability is the primary ranking metric for prop displays.

## After Any Change

1. Run: `cd frontend && npm run build` — no TypeScript errors
2. Run: `cd frontend && npm run lint` — no ESLint warnings
3. Visual verification in browser at `http://localhost:3000`
4. Verify all API calls use the `/api` prefix.
