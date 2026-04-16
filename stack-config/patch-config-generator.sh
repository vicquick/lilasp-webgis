#!/bin/sh
# Patch qwc-config-generator :latest-2026-lts at container start.
#
# 1. print_service_config.py crashes on projects with no print templates
#    (NoneType subscript) — handle None safely.
# 2. capabilities_reader.py logs duplicate-layer-name as critical which
#    blocks the whole regen even with ignore_errors=true — demote to error
#    so ignore_errors takes effect.

set -eu

f1=/srv/qwc_service/config_generator/print_service_config.py
f2=/srv/qwc_service/config_generator/capabilities_reader.py

python3 - <<'PY'
import pathlib

# Patch 1: print_service_config null-safety
p = pathlib.Path('/srv/qwc_service/config_generator/print_service_config.py')
s = p.read_text()
old = (
    "            project_metadata = self.themes_reader.project_metadata(service_name)\n"
    "            # collect print templates\n"
    "            for template in project_metadata['print_templates']:"
)
new = (
    "            project_metadata = self.themes_reader.project_metadata(service_name) or {}\n"
    "            # collect print templates\n"
    "            for template in (project_metadata.get('print_templates') or []):"
)
if old in s:
    p.write_text(s.replace(old, new))
    print('patched print_service_config.py')

# Patch 2: capabilities_reader critical → error for duplicate/comma layer names
p = pathlib.Path('/srv/qwc_service/config_generator/capabilities_reader.py')
s = p.read_text()
patched = 0
for marker in ("logger.critical(\n                f\"The layer",
               "logger.critical(\n                f\"Duplicate layer name"):
    new_s = s.replace(marker, marker.replace("logger.critical", "logger.error"))
    if new_s != s:
        s = new_s
        patched += 1
p.write_text(s)
print(f'patched capabilities_reader.py ({patched} sites)')
PY
