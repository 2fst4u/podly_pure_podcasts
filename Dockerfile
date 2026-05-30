# syntax=docker/dockerfile:1
# Multi-stage build for combined frontend and backend
FROM node:20-alpine AS frontend-build

WORKDIR /app

# Enable pnpm
RUN corepack enable pnpm

# Copy frontend package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy frontend source code
COPY frontend/ ./

# Build frontend assets with explicit error handling
RUN set -e && \
    pnpm build && \
    test -d dist && \
    echo "Frontend build successful - dist directory created"

# Python builder stage - compiles packages, kept separate to exclude build tools from final image
FROM python:3.11-slim AS python-builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install pipenv first to cache the tool independently of Pipfile changes
RUN pip install --no-cache-dir pipenv

COPY Pipfile Pipfile.lock ./

# Generate pinned requirements from lock file, stripping torch so we can install the CPU-only wheel.
RUN pipenv requirements | grep -v -E '^(torch|torchvision|torchaudio|triton|nvidia-)' > /tmp/requirements.txt

# Install CPU-only PyTorch wheel (~500 MB vs ~2-4 GB for the default GPU wheel).
# Cache mount keeps the downloaded wheel across rebuilds so re-installs skip the large download.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python packages (torch already present, openai-whisper will reuse it)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

# Backend runtime stage
FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime system dependencies only — no build tools needed here
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    sqlite3 \
    gosu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user for running the application
RUN groupadd -r appuser && \
    useradd --no-log-init -r -g appuser -d /home/appuser appuser && \
    mkdir -p /home/appuser && \
    chown -R appuser:appuser /home/appuser

# Create necessary directories and set permissions
RUN mkdir -p /app/processing /app/src/instance /app/src/instance/data /app/src/instance/data/in /app/src/instance/data/srv /app/src/instance/config /app/src/instance/db && \
    chown -R appuser:appuser /app

# Copy compiled Python packages from builder stage
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# Copy entrypoint and scripts (rarely change)
COPY --chown=appuser:appuser docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod 755 /docker-entrypoint.sh
COPY --chown=appuser:appuser scripts/ ./scripts/
RUN chmod +x scripts/start_services.sh

# Copy application code (frequent changes)
COPY --chown=appuser:appuser src/ ./src/
RUN rm -rf ./src/instance

# Copy built frontend assets to Flask static folder
COPY --from=frontend-build --chown=appuser:appuser /app/dist ./src/app/static

EXPOSE 5001

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["./scripts/start_services.sh"]
