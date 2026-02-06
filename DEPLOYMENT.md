# Render Deployment Guide

## Pre-Deployment Checklist

- [x] Dockerfile optimized for production (multi-stage build)
- [x] Entrypoint respects PORT environment variable
- [x] CORS origins configurable via environment variable
- [x] Database URL handles NeonDB format (`postgres://` → `postgresql+psycopg://`)
- [x] S3 storage configured for Cloudflare R2 compatibility
- [x] No hardcoded secrets (all from environment variables)
- [x] Health check endpoint at `/health`
- [x] `.dockerignore` optimized to reduce image size
- [x] `render.yaml` blueprint created

---

## Step 1: Set Up External Services

### NeonDB (PostgreSQL)
1. Go to [neon.tech](https://neon.tech) and create a project
2. Copy the connection string (looks like):
   ```
   postgresql://user:password@ep-xxx-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require
   ```

### Upstash (Redis)
1. Go to [upstash.com](https://upstash.com) and create a Redis database
2. Copy the Redis URL (looks like):
   ```
   rediss://default:xxx@xxx-xxx.upstash.io:6379
   ```
   > Note: Use `rediss://` (with double 's') for TLS

### Cloudflare R2 (S3 Storage)
1. Go to Cloudflare Dashboard → R2
2. Create a bucket named `template-intelligence`
3. Go to **Manage R2 API Tokens** → Create API Token
4. Note the following:
   - **Account ID**: Found in R2 overview
   - **Access Key ID**: From API token
   - **Secret Access Key**: From API token
   - **Endpoint**: `https://<account_id>.r2.cloudflarestorage.com`

---

## Step 2: Deploy to Render

### Option A: Using Blueprint (Recommended)
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Blueprint**
3. Connect your GitHub repository
4. Render will detect `render.yaml` and create services automatically
5. Fill in the secret environment variables when prompted

### Option B: Manual Setup
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Environment**: Docker
   - **Docker Build Context**: `.`
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Command**: `api`
   - **Health Check Path**: `/health`

---

## Step 3: Configure Environment Variables

In Render Dashboard → Your Service → **Environment**:

| Variable | Value | Description |
|----------|-------|-------------|
| `APP_ENV` | `production` | Application environment |
| `DATABASE_URL` | `postgresql://...` | NeonDB connection string |
| `REDIS_URL` | `rediss://...` | Upstash Redis URL |
| `S3_ENDPOINT_URL` | `https://<id>.r2.cloudflarestorage.com` | R2 endpoint |
| `S3_ACCESS_KEY` | `<r2_access_key>` | R2 API token access key |
| `S3_SECRET_KEY` | `<r2_secret_key>` | R2 API token secret key |
| `S3_BUCKET_NAME` | `template-intelligence` | R2 bucket name |
| `S3_REGION` | `auto` | Use 'auto' for R2 |
| `CORS_ORIGINS` | `https://your-app.vercel.app` | Vercel frontend URL |
| `LOG_DIR` | `/tmp/logs` | Log directory |
| `OPENAI_API_KEY` | `sk-...` | (Optional) OpenAI API key |

---

## Step 4: Deploy & Verify

1. Click **Create Web Service** or trigger a deploy
2. Wait for build and deployment to complete
3. Test endpoints:
   - `https://your-service.onrender.com/health` → Should return `{"status": "healthy"}`
   - `https://your-service.onrender.com/health/infrastructure` → Check all services
   - `https://your-service.onrender.com/docs` → FastAPI Swagger UI

---

## Step 5: Deploy Worker (Optional)

If you need the background worker for async jobs:
1. Create another **Background Worker** service
2. Use the same Docker settings but with command: `worker`
3. Add the same environment variables

---

## Troubleshooting

### Database Connection Errors
- Ensure NeonDB URL includes `?sslmode=require`
- Check if IP allowlist is configured (Neon allows all IPs by default)

### Redis Connection Errors  
- Use `rediss://` (with TLS) for Upstash
- Verify the password is included in the URL

### R2/S3 Errors
- Ensure bucket exists and matches `S3_BUCKET_NAME`
- Verify API token has read/write permissions
- Check endpoint format: `https://<account_id>.r2.cloudflarestorage.com`

### CORS Errors
- Add your Vercel URL to `CORS_ORIGINS`
- Include `https://` prefix
- Multiple origins: comma-separated, no spaces

### Missing Environment Variables
- Check Render logs for "Missing required environment variables"
- All required vars: `APP_ENV`, `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`

---

## Vercel Frontend Setup

After backend is deployed:

1. Deploy frontend to Vercel
2. Set environment variable in Vercel:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
   ```
3. Update `CORS_ORIGINS` in Render to include your Vercel URL
