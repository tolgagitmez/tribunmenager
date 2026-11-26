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
policy_only="${TRIBUN_POLICY_ONLY:-0}"
case "$policy_only" in 0|1) ;; *) echo "Invalid TRIBUN_POLICY_ONLY" >&2; exit 2;; esac
if [[ "${TRIBUN_PATCH_ONLY:-0}" == 1 || "$policy_only" == 1 ]]; then
  [[ -z "${TRIBUN_NATIVE_RUNTIME_OUT:-}" && "$#" == 1 ]] || exit 2
  git -C "$work/source" diff --check
  echo "Pinned upstream patch application passed (not C++ compilation)"
  if [[ "$policy_only" == 0 ]]; then exit 0; fi
fi
# Exercise the actual patched C++ decision predicates before building the full game.
c++ -std=c++17 -I"$work/source/src/onthepitch" "$here/attack-policy-test.cpp" -o "$work/attack-policy-test"
"$work/attack-policy-test"
echo "Full patched attack-policy assertions passed (not full engine build)"
if [[ "$policy_only" == 1 ]]; then exit 0; fi
if [[ $# -ge 2 ]]; then
  node "$here/fixture-adapter.cjs" "$2" "$work/fixture.txt"
  cp "$work/fixture.txt.json" "$out.fixture.json"
# Mid-match activation currently crashes upstream; isolate the experimental diagnostic.
python3 - "$out.fixture.json" <<'PY'
import json,os,sys
with open(sys.argv[1]) as f: manifest=json.load(f)
if any(t.get("substitutions") for t in manifest["teams"]) and os.environ.get("TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS")!="1":
    raise SystemExit("Native halftime substitutions quarantined: experimental diagnostic only")
PY
  export TRIBUN_LEAGUE_SOCCER_FIXTURE="$work/fixture.txt"
  export TRIBUN_LEAGUE_SOCCER_SEED="${TRIBUN_LEAGUE_SOCCER_SEED:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["seed"])' "$out.fixture.json")}"
fi
cd "$work/source"
if [[ "${TRIBUN_INSTALL_NATIVE_DEPS:-0}" == 1 ]]; then
  bash scripts/setup_linux_deps.sh
fi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build --parallel "${TRIBUN_BUILD_JOBS:-2}"
# Optional reusable runtime bundle; target must not exist.
if [[ -n "${TRIBUN_NATIVE_RUNTIME_OUT:-}" ]]; then
  runtime="$(realpath -m "$TRIBUN_NATIVE_RUNTIME_OUT")"
  [[ ! -e "$runtime" ]] || { echo "Runtime destination already exists" >&2; exit 2; }
  mkdir -p "$runtime"
  cp -a build/gameplayfootball build/data build/databases build/locale build/media "$runtime/"
  cp tests/run_menu_smoke.sh "$runtime/"
  cp data/menu_smoke_full_match.config "$runtime/native-match.config"
  python3 - "$here" "$runtime" <<'PY'
import hashlib, json, pathlib, sys
here, runtime = map(pathlib.Path, sys.argv[1:])
patches = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in
           ("instrument.py", "fixture_patch.py", "short_match_patch.py")}
(runtime / "tribun-runtime.json").write_text(json.dumps({
    "upstream": json.loads((here / "upstream.json").read_text()), "patches": patches
}))
PY
  if [[ "${TRIBUN_PREPARE_ONLY:-0}" == 1 ]]; then exit 0; fi
fi
# Build once; each match gets a fresh native process and identical frozen elevens.
config="$work/source/data/menu_smoke_full_match.config"
if [[ "${TRIBUN_BENCHMARK:-0}" == 1 ]]; then
  [[ $# -ge 2 ]] || { echo "Benchmark needs frozen fixture input" >&2; exit 2; }
  config="$work/native-five-minute.config"
  sed 's/"menu_smoke_match_time_scale" "6.0"/"menu_smoke_match_time_scale" "1.0"/' "$work/source/data/menu_smoke_full_match.config" > "$config"
  grep -F '"menu_smoke_match_time_scale" "1.0"' "$config" >/dev/null
fi
cd build
run_match() {
  local dest="$1" seed="$2" profile="$3" limit="$4"
  rm -f "$dest" "$dest.attack.json"
  export TRIBUN_LEAGUE_SOCCER_TRACE="$dest"
  export TRIBUN_LEAGUE_SOCCER_ATTACK="$profile"
  if [[ -n "$seed" ]]; then export TRIBUN_LEAGUE_SOCCER_SEED="$seed"; fi
  bash ../tests/run_menu_smoke.sh ./gameplayfootball "$config" "$limit" \
    "[menu-smoke] Full match complete:" \
    "[menu-smoke] Full-match verification succeeded, quitting test run"
  python3 "$here/validate_trace.py" "$dest"
  node "$here/attack-report.cjs" "$dest" "$dest.attack.json"
  if [[ $# -ge 2 && -f "$out.fixture.json" && -n "${TRIBUN_LEAGUE_SOCCER_FIXTURE:-}" ]]; then
    python3 "$here/validate_fixture_trace.py" "$dest" "$out.fixture.json"
    python3 "$here/../../native_season.py" "$dest" "$out.fixture.json" "$dest.season.json"
  fi
}
if [[ "${TRIBUN_BENCHMARK:-0}" == 1 ]]; then
  read -r -a seeds <<< "${TRIBUN_BENCHMARK_SEEDS:-2026 2027 2028}"
  [[ ${#seeds[@]} -ge 1 && ${#seeds[@]} -le 6 ]] || exit 2
  for seed in "${seeds[@]}"; do
    [[ "$seed" =~ ^[0-9]+$ ]] || exit 2
    for profile in baseline short-match; do
      run_match "$out.$seed.$profile.ndjson" "$seed" "$profile" 900
    done
  done
  node "$here/compare-attacks.cjs" "$out" "${seeds[@]}"
else
  run_match "$out" "${TRIBUN_LEAGUE_SOCCER_SEED:-}" "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" 420
fi
