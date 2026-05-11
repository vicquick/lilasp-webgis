FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# tippecanoe (PMTiles), gdal-bin (ogr2ogr), nodejs+npm (geostyler-cli@7).
# Use Debian Bookworm's bundled nodejs (18.19) — avoids the nodesource
# curl/apt-key dance that flakes on the Coolify builder.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tippecanoe \
      gdal-bin \
      nodejs \
      npm \
      ca-certificates \
 && npm install -g geostyler-cli@7 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /root/.npm

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

COPY src/ ./src/

CMD ["python", "-m", "indexer.main"]
