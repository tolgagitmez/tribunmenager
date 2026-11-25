#!/usr/bin/env bash
# Build actual native simulation and record one upstream full-match smoke.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(realpath -m "${1:-league-soccer-trace.ndjson}")"
mkdir -p "$(dirname "$out")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
readarray -t upstream < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["repository"]); print(d["revision"])' "$here/upstream.json")
git init -q "$work/source"
git -C "$work/source" remote add origin "${upstream[0]}"
git -C "$work/source" fetch --depth 1 origin "${upstream[1]}"
git -C "$work/source" checkout --detach FETCH_HEAD
test "$(git -C "$work/source" rev-parse HEAD)" = "${upstream[1]}"
python3 "$here/instrument.py" "$work/source"
if [[ $# -ge 2 ]]; then
  node "$here/fixture-adapter.cjs" "$2" "$work/fixture.txt"
  cp "$work/fixture.txt.json" "$out.fixture.json"
  export TRIBUN_LEAGUE_SOCCER_FIXTURE="$work/fixture.txt"
fi
cd "$work/source"
if [[ "${TRIBUN_INSTALL_NATIVE_DEPS:-0}" == 1 ]]; then
  bash scripts/setup_linux_deps.sh
fi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build --parallel "${TRIBUN_BUILD_JOBS:-2}"
rm -f "$out"
export TRIBUN_LEAGUE_SOCCER_TRACE="$out"
cd build
bash ../tests/run_menu_smoke.sh ./gameplayfootball "$work/source/data/menu_smoke_full_match.config" 420 \
  "[menu-smoke] Full match complete:" \
  "[menu-smoke] Full-match verification succeeded, quitting test run"
python3 "$here/validate_trace.py" "$out"
if [[ $# -ge 2 ]]; then
  python3 "$here/validate_fixture_trace.py" "$out" "$out.fixture.json"
fi
