# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY backend backend
COPY backend/entrypoint.sh entrypoint.sh

# Create non-root user for security and set permissions
RUN useradd -m -u 1000 appuser && \
    chmod +x entrypoint.sh && \
    chown -R appuser:appuser /app && \
    mkdir -p /tmp/logs && chown appuser:appuser /tmp/logs

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    PORT=8000

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port (Render will override with PORT env var)
EXPOSE ${PORT}

ENTRYPOINT ["./entrypoint.sh"]
CMD ["api"]
