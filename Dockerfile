# Multi-stage build for combined frontend and backend
FROM node:18-alpine AS frontend-build

WORKDIR /app

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build frontend assets with explicit error handling
RUN set -e && \
    npm run build && \
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

COPY Pipfile Pipfile.lock ./

# Generate pinned requirements from lock file, stripping torch and all GPU-only packages.
# We install torch separately from the CPU-only wheel index to avoid pulling CUDA libraries.
# nvidia-* packages are transitive deps of the CUDA torch wheel and not needed for CPU-only.
RUN pip install --no-cache-dir pipenv && \
    pipenv requirements | grep -v -E '^(torch|torchvision|torchaudio|triton|nvidia-)' > /tmp/requirements.txt

# Install CPU-only PyTorch — avoids ~2-4 GB of CUDA libraries shipped in the default PyPI wheel
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python packages (torch already present, openai-whisper will reuse it)
RUN pip install --no-cache-dir -r /tmp/requirements.txt

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

# Copy compiled Python packages from builder stage
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
RUN rm -rf ./src/instance
COPY scripts/ ./scripts/
RUN chmod +x scripts/start_services.sh

# Copy built frontend assets to Flask static folder
COPY --from=frontend-build /app/dist ./src/app/static

# Create non-root user for running the application
RUN groupadd -r appuser && \
    useradd --no-log-init -r -g appuser -d /home/appuser appuser && \
    mkdir -p /home/appuser && \
    chown -R appuser:appuser /home/appuser

# Create necessary directories and set permissions
RUN mkdir -p /app/processing /app/src/instance /app/src/instance/data /app/src/instance/data/in /app/src/instance/data/srv /app/src/instance/config /app/src/instance/db && \
    chown -R appuser:appuser /app

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod 755 /docker-entrypoint.sh

EXPOSE 5001

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["./scripts/start_services.sh"]
