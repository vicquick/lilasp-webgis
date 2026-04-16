#!/bin/sh
# Generate pg_service.conf from environment variables
# Called by init-secrets container at startup
set -e

cat > /pg-config/pg_service.conf << EOF
[qwc_configdb]
host=config-db
port=5432
dbname=qwc_services
user=qwc_admin
password=${CONFIG_DB_PASSWORD}
sslmode=disable

[qwc_wiesbaden]
host=host.docker.internal
port=6432
dbname=lilasp_wiesbaden
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable

[qwc_cuxhaven]
host=host.docker.internal
port=6432
dbname=lilasp_cuxhaven
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable

[qwc_frankfurt]
host=host.docker.internal
port=6432
dbname=lilasp_frankfurt
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable

[qwc_frankfurt_nep]
host=host.docker.internal
port=6432
dbname=lilasp_frankfurt_naturerlebnisprofile
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable

[qwc_frankfurt_plaetze]
host=host.docker.internal
port=6432
dbname=lilasp_frankfurt_plaetze
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable

[qwc_frankfurt_strassen]
host=host.docker.internal
port=6432
dbname=lilasp_frankfurt_strassen
user=qwc_service
password=${QWC_SERVICE_DB_PASSWORD}
sslmode=disable
EOF

echo "pg_service.conf written ($(wc -l < /pg-config/pg_service.conf) lines)"
