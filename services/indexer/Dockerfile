FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# tippecanoe builds PMTiles, gdal's ogr2ogr handles reprojection.
# geostyler-cli (QML → MapLibre style) is deferred to a later phase — see
# bake.py's `style_path` fallback. Without it, vector tiles ship with
# martin's default style; WMS is still pixel-identical for any
# non-eligible layer.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tippecanoe \
      gdal-bin \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install -e .

CMD ["python", "-m", "indexer.main"]
