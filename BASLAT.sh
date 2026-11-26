#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10 veya daha yeni bir sürüm gerekli.'; exit 1; }
echo 'Tribun Manager: varsayilan yeni motor (yerel alfa). Eski motor icin --mode local.'
exec python3 start.py "$@"
