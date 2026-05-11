FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# tippecanoe for PMTiles, ogr2ogr for reprojection.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tippecanoe \
      gdal-bin \
      ca-certificates \
      curl \
 && rm -rf /var/lib/apt/lists/*

# geostyler-cli (QML → MapLibre style)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g geostyler-cli@7 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

COPY src/ ./src/

CMD ["python", "-m", "indexer.main"]
