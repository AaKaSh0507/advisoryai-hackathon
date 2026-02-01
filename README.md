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
## Phase 4 - Template Parsing

### Overview

Phase 4 implements Word document parsing and structure inference:

1. **Document Validation** - Validates .docx file integrity and format
2. **Deterministic Parsing** - Extracts structural elements (headings, paragraphs, tables, lists)
3. **LLM-Assisted Inference** - Resolves ambiguous structure (optional, constrained)
4. **Persistence** - Stores parsed representation in object storage

### Parsed Representation

The parsed document is stored as JSON at:
```
templates/{template_id}/{version}/parsed.json
```

Contains:
- Document metadata (title, author, dates)
- Ordered structural blocks with stable IDs
- Block types: heading, paragraph, table, list, header, footer
- Formatting information (fonts, alignment, indentation)
- Content hash for determinism verification

### Block Types

| Type | Description |
|------|-------------|
| `heading` | Heading with level (1-9) |
| `paragraph` | Body text with formatting |
| `table` | Table with rows and cells |
| `list` | Bullet or numbered list |
| `header` | Document header content |
| `footer` | Document footer content |
| `page_break` | Explicit page break |

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for inference | None (disabled) |
| `OPENAI_API_BASE_URL` | API endpoint | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model to use | `gpt-4o-mini` |
| `LLM_INFERENCE_ENABLED` | Enable LLM inference | `true` |
| `LLM_CONFIDENCE_THRESHOLD` | Min confidence for suggestions | `0.85` |

LLM inference is:
- **Optional** - Works without API key
- **Constrained** - Only resolves ambiguity, never invents structure
- **Validated** - All suggestions verified before application
- **Conservative** - High confidence threshold prevents false positives

### API Endpoints

#### Templates
- `POST /api/v1/templates/{id}/versions` - Upload template (.docx only)
- `GET /api/v1/templates/{id}/versions/{num}` - Get version details
- `GET /api/v1/templates/{id}/versions/{num}/parsed` - Get parsed representation
- `GET /api/v1/templates/{id}/versions/{num}/status` - Get parsing status

### Determinism

The parser guarantees:
- Same input always produces identical output
- Stable block IDs based on content hash
- Content hash for verification
- No non-deterministic operations

### Error Handling

Parsing failures are:
- **Explicit** - Clear error messages with details
- **Logged** - Full error context in logs
- **Persisted** - Error stored in template version record
- **Non-blocking** - Failed parsing doesn't affect other versions
