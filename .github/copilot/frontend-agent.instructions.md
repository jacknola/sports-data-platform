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
to React/TypeScript frontend code, follow these rules:

## Before Any Change
1. Read `docs/todo-frontend.md` for known issues.
2. Run: `cd frontend && npm run build` (TypeScript check)
3. Run: `cd frontend && npm run lint` (ESLint)

## Conventions (Strict)
- **Components:** Functional with hooks only. No class components.
- **State:** React Query (`@tanstack/react-query`) for server state. No Redux.
- **Styling:** Tailwind CSS only. Custom colors: `primary-*`, `accent-*`. No inline styles unless dynamic.
- **Types:** No `any` type. No `@ts-ignore`. Create proper interfaces in `types/api.ts`.
- **API calls:** Use `utils/api.ts` axios wrapper. All requests prefixed with `/api`.
- **Path alias:** `@/*` maps to `./src/*`.
- **Env vars:** Use `import.meta.env.VITE_*` pattern.

## Component Pattern
```tsx
import { useQuery } from '@tanstack/react-query';
import api from '@/utils/api';

export default function ComponentName() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['key'],
    queryFn: () => api.get('/api/endpoint'),
  });

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorMessage error={error} />;

  return <div className="p-4">{/* content */}</div>;
}
```

## After Any Change
1. Run: `cd frontend && npm run build` — no TypeScript errors
2. Run: `cd frontend && npm run lint` — no ESLint warnings
3. Visual verification in browser at `http://localhost:3000`
