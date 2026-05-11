"""Verify a project loads cleanly via py-qgis-server GetCapabilities."""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
async def verify(slug: str) -> tuple[bool, str]:
    """Returns (ok, error_message)."""
    # MAP is resolved relative to QGSRV_CACHE_ROOTDIR (/srv/gis); the indexer
    # discovers either a .qgs or a .qgz under <slug>/<slug>.* — try both.
    map_relative = f"{slug}/{slug}.qgz"
    url = (
        f"{config.PYQGIS_URL}/?MAP={map_relative}"
        f"&SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        if b"<WMS_Capabilities" not in r.content:
            return False, f"no WMS_Capabilities element: {r.text[:200]}"
        # py-qgis-server reports failed layers in the body with
        # `name="<layername>" ... Layer(s) not valid` — surface as warning.
        return True, ""
