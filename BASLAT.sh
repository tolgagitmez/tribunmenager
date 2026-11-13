#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10 veya daha yeni bir sürüm gerekli.'; exit 1; }
echo 'Oyunu http://localhost:8000 adresinde aç. Sunucuyu kapatmak için Ctrl+C.'
exec python3 start.py "$@"
