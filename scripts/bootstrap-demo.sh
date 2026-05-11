#!/usr/bin/env bash
# Drops the LL-WIE-2427 demo zip into projects/ so the indexer ingests it.
# Usage: ./scripts/bootstrap-demo.sh [/path/to/LL-WIE-2427.zip]
set -euo pipefail

SRC="${1:-/srv/inbox/LL-WIE-2427.zip}"
DEST_DIR="$(git rev-parse --show-toplevel)/projects"

if [[ ! -f "$SRC" ]]; then
    echo "demo zip not found at: $SRC" >&2
    echo "Pass the path as the first argument, or place it under /srv/inbox/." >&2
    exit 1
fi

cp -v "$SRC" "$DEST_DIR/"
echo "Drop applied. The indexer will ingest on next file-system event."
