# Template Intelligence Engine

Backend foundation for the AdvisoryAI Template Intelligence Platform.

## Run the System

### API Server

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Background Worker

```bash
python -m backend.app.worker.main
```

### Database Migrations

```bash
cd backend && alembic upgrade head
```

## Architecture

### Job System

The system uses an asynchronous job-based architecture:

1. **API** receives requests and creates jobs
2. **Workers** poll for and process jobs
3. **Database** is the source of truth for job state
4. **Redis** provides coordination and notifications (not source of truth)

### Processing Pipeline

Template processing follows a deterministic pipeline:

```
Template Upload → PARSE job → CLASSIFY job → Ready for Generation
                                                    ↓
Document Create ─────────────────────────→ GENERATE job
```

- Each stage persists completion state
- Downstream jobs only created after upstream success
- Pipelines resume correctly after restart
- Failed jobs halt the pipeline and are queryable

### Job States

- `PENDING` - Job awaiting processing
- `RUNNING` - Job claimed by a worker
- `COMPLETED` - Job finished successfully
- `FAILED` - Job failed (terminal state)

## Configuration

The application is configured via environment variables.

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `S3_ENDPOINT_URL` | S3-compatible storage endpoint |
| `S3_ACCESS_KEY` | Storage access key |
| `S3_SECRET_KEY` | Storage secret key |
| `S3_BUCKET_NAME` | Storage bucket name |
| `LOG_DIR` | Directory for log output (default: `./logs/`) |
| `APP_ENV` | Environment name (e.g., `development`, `production`) |

## API Endpoints

### Jobs

- `GET /api/v1/jobs` - List jobs with filtering
- `GET /api/v1/jobs/counts` - Get job counts by status
- `GET /api/v1/jobs/{id}` - Get job details
- `GET /api/v1/jobs/{id}/status` - Get job status
- `POST /api/v1/jobs/{id}/cancel` - Cancel a job
- `GET /api/v1/jobs/pipeline/{template_version_id}` - Get pipeline status

### Health

- `GET /health` - Basic health check
- `GET /health/infrastructure` - Infrastructure status
- `GET /health/workers` - Active worker status
