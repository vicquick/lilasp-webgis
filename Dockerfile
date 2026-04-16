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

# Stage 2: serve with qwc-map-viewer Flask service
FROM sourcepole/qwc-map-viewer:2026-lts

# Replace stock QWC2 assets with our custom build
COPY --from=builder /app/prod/ /srv/qwc_service/qwc2/

# Config files are mounted at runtime via volume
# JWT secret comes from environment
