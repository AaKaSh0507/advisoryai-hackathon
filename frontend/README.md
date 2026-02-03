# Template Intelligence Engine - Frontend

React/Next.js frontend for the Template Intelligence Engine.

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Open http://localhost:3000

## Configuration

Create `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Structure

```
├── app/           # Next.js pages
├── components/    # React components
│   ├── dashboard-header.tsx
│   ├── job-monitor.tsx
│   ├── sidebar.tsx
│   ├── template-card.tsx
│   ├── template-list.tsx
│   └── upload-zone.tsx
└── lib/           # Utilities
    ├── api.ts     # Backend API client
    └── utils.ts   # Helper functions
```
