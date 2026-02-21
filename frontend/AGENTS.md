# Frontend

## Overview
React 18 and TypeScript dashboard for sports data intelligence.

## Structure
```
frontend/
├── src/
│   ├── components/  # Layout, QuickStats, ActionCard, AgentStatus
│   ├── pages/       # Dashboard, Agents, Bets, Analysis, Settings
│   └── utils/       # api.ts (Axios client)
├── tailwind.config.cjs
└── vite.config.ts
```

## State Management
React Query handles server state.
Global client state like Context or Redux isn't used.
You'll find the QueryClient in main.tsx.
Keep state local to components whenever possible.

## API Integration
Axios uses the /api base URL.
Requests get proxied to the backend via Vite.
Follow the useQuery hook pattern with queryKey and queryFn.
Define interfaces for all API responses in the utils or components.

## Styling
Tailwind CSS provides the styling.
Custom primary and accent colors define the look.
Lucide React provides the icons.
Check index.css for custom component classes.
Avoid inline styles unless calculating dynamic values.

## Development
Run `npm run dev` to start the development server.
The frontend expects the backend to run on port 8000.
Vite handles hot module replacement for fast iterations.
Build the production bundle using `npm run build`.
