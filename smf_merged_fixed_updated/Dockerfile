# ==============================================================================
# Dockerfile — EduTrack Pro: Enterprise Smart Attendance & Face Recognition System
# Multi-stage optimized production container build (Vite + React SPA & FastAPI)
# ==============================================================================

# ── STAGE 1: Frontend Build (Node.js 20 Alpine) ──────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci --no-audit --prefer-offline || npm install

COPY frontend/ ./
RUN npm run build

# ── STAGE 2: Python Backend & Production Runtime (Python 3.11 Slim) ───────────
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=8000 \
    APP_ENV=production

# Install essential system dependencies (C++ compilers for dlib/cmake, OpenCV graphics libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application, core packages, and scripts
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY models/ ./models/
COPY *.py ./

# Copy compiled React 18 production bundle from Stage 1
COPY --from=frontend-builder /build/dist ./frontend/dist
COPY frontend/legacy/ ./frontend/legacy/

# Create persistent storage directories
RUN mkdir -p /app/data /app/faces /app/logs /app/attendance

EXPOSE 8000

# Container healthcheck ensuring API is healthy and serving requests
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || curl -f http://localhost:8000/api/health || exit 1

# Production ASGI server launch
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
