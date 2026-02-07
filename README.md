# Template Intelligence Engine

## Chosen Problem

Financial advisory firms generate thousands of client documents monthly using Word templates containing a mix of static content (legal disclaimers, headers, formatting) and dynamic content (client names, figures, recommendations). Managing these templates manually is slow, error-prone, and does not scale — analysts waste hours identifying what needs updating, formatting breaks when copying between documents, and version control is handled manually.

## Solution Overview

The Template Intelligence Engine automates the full template-to-document lifecycle:

- **Intelligent Parsing** — Upload a `.docx` template and the system extracts its complete structure while preserving formatting.
- **Automatic Classification** — Each section is classified as static or dynamic using rule-based analysis and optional LLM-assisted classification.
- **Document Generation** — Generate new documents where dynamic sections are populated from prompts and static sections are preserved exactly.
- **Surgical Regeneration** — Update individual sections or regenerate entire documents when templates change, with full version tracking.
- **Async Job System** — All heavy operations (parsing, classification, generation, regeneration) run as background jobs for reliability.

## Tech Stack Used

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic, python-docx |
| **Frontend** | Next.js 16, TypeScript, React, Tailwind CSS, shadcn/ui |
| **Database** | PostgreSQL 15 |
| **Queue** | Redis 7 (job queue and pub/sub) |
| **Storage** | MinIO (S3-compatible object storage) |
| **Infra** | Docker, Docker Compose |
| **LLM** *(optional)* | OpenAI-compatible API (GPT-4o-mini via OpenRouter or OpenAI) |

## Setup Instructions

### Prerequisites

- **Docker** and **Docker Compose** (required for backend infrastructure)
- **Node.js 18+** and **npm** (required for the frontend)
- **Make** (optional, for convenience commands)

### Backend Setup

The backend (API server, worker, PostgreSQL, Redis, MinIO) runs entirely via Docker Compose. No local Python install is needed.

1. Copy the example environment file and fill in your values:
   ```bash
   cp .env.example .env
   ```
2. Build and start all backend services:
   ```bash
   make up
   ```

### Frontend Setup

1. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Create a local environment file:
   ```bash
   echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
   ```
3. Start the frontend dev server:
   ```bash
   npm run dev
   ```

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Application
APP_ENV=development

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/template_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# S3-compatible Storage (MinIO)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=template-intelligence

# Logging
LOG_DIR=./logs

# OpenAI / LLM (optional — leave OPENAI_API_KEY empty to disable)
OPENAI_API_KEY=
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
LLM_INFERENCE_ENABLED=false
```

For the frontend, create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Step-by-step Guide to Run the Project Locally

```bash
# 1. Clone the repository
git clone <repository-url>
cd hackathon

# 2. Create your environment file
cp .env.example .env

# 3. Start all backend services (PostgreSQL, Redis, MinIO, API, Worker)
make up

# 4. Wait for services to be healthy (~15 seconds), then verify
make health

# 5. In a new terminal, install and start the frontend
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev

# 6. Open the app
#    Frontend:  http://localhost:3000
#    API Docs:  http://localhost:8000/docs

# 7. (Optional) Seed demo data for immediate exploration
curl -X POST http://localhost:8000/api/v1/demo/seed

# 8. To stop everything
make down
```
