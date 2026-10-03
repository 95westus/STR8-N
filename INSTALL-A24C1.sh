#!/bin/sh
# Run with: sh ./INSTALL-A24C1.sh
set -eu
kit_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$kit_dir/install_a24c1_linux.py" "$@"
