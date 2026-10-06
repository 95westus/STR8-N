#!/bin/sh
set -eu
kit_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
launcher="$kit_dir/beta4_migration.py"
if [ ! -f "$launcher" ]; then launcher="$kit_dir/tools/beta4_migration.py"; fi
exec python3 "$launcher" --kind str8n "$@"
