# Template Intelligence Engine

**Intelligent template management and document generation platform for AdvisoryAI**

## Problem Statement

Financial advisory firms generate thousands of client documents monthly using Word templates. These templates contain a mix of:
- **Static content** that never changes (legal disclaimers, headers, formatting)
- **Dynamic content** that must be customized per client (names, figures, recommendations)

Manual template management doesn't scale:
- Analysts spend hours identifying which sections need updates
- Formatting is lost when copying content between documents
- Version control is manual and error-prone
- Regenerating documents after template changes requires re-work

## Solution Overview

The Template Intelligence Engine automates the entire template lifecycle:

1. **Intelligent Parsing** - Upload a Word template and the system extracts its complete structure
2. **Automatic Classification** - Each section is classified as static or dynamic using rule-based and LLM-assisted analysis
3. **Document Generation** - Generate new documents with dynamic sections populated from prompts
4. **Surgical Regeneration** - Update individual sections or regenerate entire documents when templates change
5. **Version Control** - Full versioning for templates and generated documents

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                    │
│                      (Next.js / React / TypeScript)                     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ REST API
┌───────────────────────────────────┴─────────────────────────────────────┐
│                             Backend API                                  │
│                    (FastAPI / Python / SQLAlchemy)                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Templates │ Sections │ Documents │ Jobs │ Regeneration │ Rendering    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────┴───────┐         ┌─────────┴─────────┐       ┌─────────┴─────────┐
│   PostgreSQL  │         │       Redis       │       │       MinIO       │
│   (Database)  │         │  (Job Queue/Pub)  │       │  (File Storage)   │
└───────────────┘         └───────────────────┘       └───────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │   Background      │
                          │     Workers       │
                          │  (Job Processing) │
                          └───────────────────┘
```

### Processing Pipeline

```
Template Upload → PARSE Job → CLASSIFY Job → Ready for Generation
                                                    │
Document Request ──────────────────────────→ GENERATE Job → Document
                                                    │
Template Update ───────────────────────────→ REGENERATE Jobs
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend development)
- Make (optional, for convenience commands)

### Start the System

```bash
# Clone the repository
git clone <repository-url>
cd hackathon

# Start all backend services
make up

# In a separate terminal, start the frontend
make frontend
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Web application |
| Backend API | http://localhost:8000 | REST API |
| API Documentation | http://localhost:8000/docs | OpenAPI/Swagger UI |
| MinIO Console | http://localhost:9001 | Object storage UI |

### Available Commands

```bash
make help           # Show all available commands
make up             # Start all backend services
make down           # Stop all services
make restart        # Restart all services
make status         # Show service status
make health         # Check health of all services
make logs           # Tail logs from all services
make frontend       # Start frontend development server
make build          # Build/rebuild Docker images
make clean          # Stop services and remove volumes
make db-shell       # Open PostgreSQL shell
make redis-shell    # Open Redis CLI
```

## System Features

### Template Management

- Upload Word documents (.docx) as templates
- Automatic structure extraction preserving all formatting
- Version control for template updates
- Parsed representation stored as JSON for processing

### Section Classification

- **Rule-based classification** for common patterns (headers, footers, legal text)
- **LLM-assisted classification** for ambiguous content (optional)
- Sections marked as STATIC (preserved) or DYNAMIC (regenerated)
- Classification stored per template version

### Document Generation

- Generate documents from classified templates
- Dynamic sections populated based on prompts
- Static sections preserved exactly
- Original formatting maintained throughout

### Regeneration

- **Section regeneration** - Update individual sections without affecting others
- **Full regeneration** - Regenerate all dynamic sections
- **Template update propagation** - Regenerate documents when template changes
- Version tracking for all regenerated content

### Job System

Asynchronous job processing ensures reliability:

| State | Description |
|-------|-------------|
| PENDING | Job awaiting processing |
| RUNNING | Job claimed by worker |
| COMPLETED | Job finished successfully |
| FAILED | Job failed (queryable error) |

## API Reference

### Templates
- `GET /api/v1/templates` - List all templates
- `POST /api/v1/templates` - Create template
- `GET /api/v1/templates/{id}` - Get template details
- `POST /api/v1/templates/{id}/versions` - Upload template version
- `GET /api/v1/templates/{id}/versions` - List template versions

### Sections
- `GET /api/v1/sections/template-version/{id}` - Get sections for template version

### Documents
- `POST /api/v1/documents` - Create document from template
- `GET /api/v1/documents/{id}` - Get document details

### Jobs
- `GET /api/v1/jobs` - List all jobs
- `GET /api/v1/jobs/{id}` - Get job details
- `GET /api/v1/jobs/counts` - Get job counts by status

### Regeneration
- `POST /api/v1/regeneration/section` - Regenerate single section
- `POST /api/v1/regeneration/document` - Regenerate full document

### Health
- `GET /health` - Basic health check
- `GET /health/infrastructure` - Infrastructure component status
- `GET /health/workers` - Active worker status

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `S3_ENDPOINT_URL` | S3-compatible storage endpoint | Required |
| `S3_ACCESS_KEY` | Storage access key | Required |
| `S3_SECRET_KEY` | Storage secret key | Required |
| `S3_BUCKET_NAME` | Storage bucket name | Required |
| `LOG_DIR` | Directory for logs | `./logs` |
| `APP_ENV` | Environment name | `development` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | None |
| `LLM_INFERENCE_ENABLED` | Enable LLM classification | `false` |

## Demo Flow

The system includes seeded demo data for immediate exploration:

1. **View Templates** - See pre-loaded template with parsed structure
2. **Explore Sections** - View classified sections (static vs dynamic)
3. **Review Jobs** - See completed PARSE and CLASSIFY jobs
4. **Generate Document** - Create a new document from the template
5. **Regenerate** - Update sections and regenerate

To seed demo data programmatically:
```bash
curl -X POST http://localhost:8000/api/v1/demo/seed
```

## Technology Stack

### Backend
- **Python 3.11** - Core runtime
- **FastAPI** - High-performance API framework
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **python-docx** - Word document processing

### Frontend
- **Next.js 16** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components

### Infrastructure
- **PostgreSQL 15** - Primary database
- **Redis 7** - Job queue and pub/sub
- **MinIO** - S3-compatible object storage
- **Docker Compose** - Container orchestration

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API endpoints
│   │   ├── domains/         # Business logic modules
│   │   │   ├── assembly/    # Document assembly
│   │   │   ├── audit/       # Audit logging
│   │   │   ├── document/    # Document management
│   │   │   ├── generation/  # Content generation
│   │   │   ├── job/         # Job queue system
│   │   │   ├── parsing/     # Template parsing
│   │   │   ├── regeneration/# Section/document regeneration
│   │   │   ├── rendering/   # Document rendering
│   │   │   ├── section/     # Section classification
│   │   │   ├── template/    # Template management
│   │   │   └── versioning/  # Version control
│   │   ├── infrastructure/  # Database, Redis, Storage
│   │   └── worker/          # Background job processor
│   ├── migrations/          # Alembic migrations
│   └── tests/               # Test suite
├── frontend/
│   ├── app/                 # Next.js pages
│   ├── components/          # React components
│   └── lib/                 # Utilities and API client
├── docker-compose.yml       # Service orchestration
├── Dockerfile               # Container build
└── Makefile                 # Convenience commands
```

## Development

### Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

### Database Migrations

```bash
cd backend
alembic upgrade head      # Apply migrations
alembic revision -m "description"  # Create new migration
```

### Adding New Features

1. Create domain module in `backend/app/domains/`
2. Add repository, service, and schemas
3. Create API endpoints in `backend/app/api/v1/`
4. Add tests in `backend/tests/`

## License

Proprietary - AdvisoryAI Internal Platform
