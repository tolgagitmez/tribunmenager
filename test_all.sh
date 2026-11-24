#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

node --test --test-concurrency=3 tests/*.test.cjs
python3 -m unittest discover -s tests -v
python3 tests/fixture-roster-api.py
