# Template Intelligence Engine

Backend foundation for the AdvisoryAI Template Intelligence Platform.

## Phase 0 - Foundation

This phase establishes the core infrastructure:
- FastAPI application with health endpoints
- PostgreSQL database connectivity
- Redis connectivity
- S3-compatible object storage connectivity
- Structured file logging

## Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- S3-compatible storage (e.g., MinIO for local development)

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Start the application:

```bash
uvicorn backend.app.main:app --reload
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/infrastructure` | GET | Infrastructure connectivity status |

## Project Structure

```
backend/
└── app/
    ├── main.py              # FastAPI application entry point
    ├── config.py            # Environment configuration
    ├── logging_config.py    # Structured logging setup
    └── infrastructure/
        ├── database.py      # PostgreSQL connectivity
        ├── redis.py         # Redis connectivity
        └── storage.py       # S3 connectivity
```

## Logging

Logs are written to the configured `LOG_DIR` (default: `./logs/`):
- `api.log` - API runtime logs
- `worker.log` - Worker runtime logs
- `errors.log` - Error-level logs

All logs are in structured JSON format.

