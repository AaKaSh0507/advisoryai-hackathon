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
