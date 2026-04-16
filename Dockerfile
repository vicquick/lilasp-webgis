# Stage 1: build the React app
FROM node:22-alpine AS builder

WORKDIR /app

# Install deps first (cache layer)
COPY package.json yarn.lock* package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts

# Copy source
COPY . .

# Build production bundle
RUN npm run build

# Stage 2: serve with qwc-map-viewer-base Flask service
# qwc-map-viewer-base expects QWC2 assets at /qwc2/
FROM sourcepole/qwc-map-viewer-base:latest-2026-lts

# Copy our custom QWC2 build (dist/, assets/, translations/, data/, index.html)
COPY --from=builder /app/prod/ /qwc2/

# Config files mounted at runtime via Coolify volume (qwc-config)
# JWT secret and pg_service from environment vars / pg-config volume
