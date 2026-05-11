FROM 3liz/qgis-map-server:3.44.8-1.9.6

USER root

# Project fonts — Futura PT for Cuxhaven, fallback DejaVu otherwise.
# Bind-mount /srv/gis-fonts at runtime to layer in custom fonts without rebuilding.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      fontconfig \
      fonts-dejavu \
      fonts-liberation2 \
      fonts-noto-core \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -fv

# Custom SRS overrides via runtime bind-mount onto qgis-home volume.
# (See config/README.md for how to seed srs.db from a QGIS Desktop profile.)
RUN install -d -o qgis -g qgis /home/qgis/QGIS/QGIS3/profiles/default/resources

# Workers self-restart at memory watermark — see ARCHITECTURE.md
ENV QGSRV_SERVER_MEMORY_HIGH_WATER_MARK=0.85

USER qgis

EXPOSE 8080
