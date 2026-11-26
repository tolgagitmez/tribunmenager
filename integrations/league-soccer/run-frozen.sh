#!/usr/bin/env bash
# Run one frozen fixture from a prepared runtime; no git fetch or compilation here.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime="$(realpath "$1")"
fixture="$(realpath "$2")"
out="$(realpath -m "$3")"
render_interval="${4:-0}"
[[ $# -le 4 ]] || { echo "Unexpected runner arguments" >&2; exit 2; }
case "$render_interval" in 0|100) ;; *) echo "Invalid diagnostic render interval" >&2; exit 2;; esac
case "${TRIBUN_NATIVE_DEFENSE_SHAPE:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 && "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" == 0 && "${TRIBUN_NATIVE_DUEL:-0}" == 0 && "${TRIBUN_NATIVE_HOLD_UP:-0}" == 0 && "${TRIBUN_NATIVE_FINISH:-0}" == 0 && "${TRIBUN_NATIVE_KEEPER_AI:-0}" == 0 ]] || { echo "Defense shape require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid defense shape flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_KEEPER_AI:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 && "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" == 0 && "${TRIBUN_NATIVE_DUEL:-0}" == 0 && "${TRIBUN_NATIVE_HOLD_UP:-0}" == 0 && "${TRIBUN_NATIVE_FINISH:-0}" == 0 ]] || { echo "Keeper AI require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid keeper AI flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_FINISH:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 && "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" == 0 && "${TRIBUN_NATIVE_DUEL:-0}" == 0 && "${TRIBUN_NATIVE_HOLD_UP:-0}" == 0 ]] || { echo "Finish require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid finish flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_HOLD_UP:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 && "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" == 0 && "${TRIBUN_NATIVE_DUEL:-0}" == 0 ]] || { echo "Hold-up require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid hold-up flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_DUEL:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 && "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" == 0 ]] || { echo "Duel require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid duel flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_CREATIVE_CARRY:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 && "${TRIBUN_NATIVE_TRIANGLE:-0}" == 0 ]] || { echo "Creative carry require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid creative carry flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_TRIANGLE:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 && "${TRIBUN_NATIVE_RUN_LANES:-0}" == 0 ]] || { echo "Triangle require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid triangle flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_RUN_LANES:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 && "${TRIBUN_NATIVE_LINE_BREAK:-0}" == 0 ]] || { echo "Run lanes require isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid run lanes flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_LINE_BREAK:-0}" in
  0) ;;
  1) [[ "${TRIBUN_LEAGUE_SOCCER_ATTACK:-baseline}" == short-match && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 0 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 0 && "${TRIBUN_NATIVE_FINAL_THIRD_RETENTION:-0}" == 0 && "${TRIBUN_NATIVE_BOX_LANE_RUNS:-0}" == 0 && "${TRIBUN_NATIVE_TIMED_ATTACK:-0}" == 0 ]] || { echo "Line break requires isolated fixed-clock short-match" >&2; exit 2; } ;;
  *) echo "Invalid line break flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_LIMB_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_CHAIN_IMPACT:-0}" == 1 ]] || { echo "Limb impact requires chain mode" >&2; exit 2; } ;;
  *) echo "Invalid limb impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_CHAIN_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_SPLIT_IMPACT:-0}" == 1 ]] || { echo "Chain impact requires split mode" >&2; exit 2; } ;;
  *) echo "Invalid chain impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_SPLIT_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_SWEPT_IMPACT:-0}" == 1 ]] || { echo "Split impact requires swept mode" >&2; exit 2; } ;;
  *) echo "Invalid split impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_SWEPT_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_ANGULAR_IMPACT:-0}" == 1 ]] || { echo "Swept impact requires angular mode" >&2; exit 2; } ;;
  *) echo "Invalid swept impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_ANGULAR_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_SURFACE_IMPACT:-0}" == 1 ]] || { echo "Angular impact requires surface mode" >&2; exit 2; } ;;
  *) echo "Invalid angular impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_SURFACE_IMPACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 1 && "${TRIBUN_NATIVE_CONTACT_INTERVAL_MS:-100}" == 10 && "${TRIBUN_NATIVE_ADAPTIVE_CONTACT:-0}" == 0 ]] || { echo "Surface impact requires uniform collision-only 10 ms mode" >&2; exit 2; } ;;
  *) echo "Invalid surface impact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_ADAPTIVE_CONTACT:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 1 && "${TRIBUN_NATIVE_CONTACT_INTERVAL_MS:-100}" == 10 ]] || { echo "Adaptive contact requires collision-only 10 ms reference" >&2; exit 2; } ;;
  *) echo "Invalid adaptive contact flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_CONTACT_INTERVAL_MS:-100}" in
  100) ;;
  50|20|10) [[ "${TRIBUN_NATIVE_COLLISION_POSE:-0}" == 1 ]] || { echo "Contact cadence requires collision-only mode" >&2; exit 2; } ;;
  *) echo "Invalid contact interval" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_COLLISION_POSE:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_ORDERED_POSE:-0}" == 1 && "${TRIBUN_NATIVE_DETERMINISM:-0}" == 1 ]] || { echo "Collision pose requires ordered deterministic mode" >&2; exit 2; } ;;
  *) echo "Invalid collision pose flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_ORDERED_POSE:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_DETERMINISM:-0}" == 1 ]] || { echo "Ordered pose requires deterministic null diagnostic" >&2; exit 2; } ;;
  *) echo "Invalid ordered pose flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_DETERMINISM:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "$render_interval" == 100 ]] || { echo "Determinism probe requires isolated null mode" >&2; exit 2; } ;;
  *) echo "Invalid determinism probe flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_POSITION_SKINNING:-0}" in
  0) ;;
  1) [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "$render_interval" == 100 ]] || { echo "Position skinning requires isolated null mode" >&2; exit 2; } ;;
  *) echo "Invalid position skinning flag" >&2; exit 2;;
esac
case "${TRIBUN_NATIVE_TASK_WORKERS:-0}" in
  0) ;;
  3|4) [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "$render_interval" == 100 ]] || { echo "Worker limit requires isolated null mode" >&2; exit 2; } ;;
  *) echo "Invalid task worker limit" >&2; exit 2;;
esac
if [[ "${TRIBUN_NATIVE_VISUAL_RNG:-0}" == 1 || "${TRIBUN_NATIVE_SKIP_PITCH_TEXTURE:-0}" == 1 ]]; then
  [[ "${TRIBUN_NATIVE_VISUAL_RNG:-0}" == 1 && "${TRIBUN_NATIVE_LEAN_SCENE:-0}" == 1 && "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 ]] || { echo "Visual RNG requires isolated lean null mode" >&2; exit 2; }
fi
if [[ "${TRIBUN_NATIVE_LEAN_SCENE:-0}" == 1 ]]; then
  [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_SHARED_ASSETS:-0}" != 1 && "$render_interval" == 100 ]] || { echo "Lean scene requires isolated null mode" >&2; exit 2; }
fi
if [[ "$render_interval" != 0 && ( "${TRIBUN_NATIVE_FIXED_DURATION:-0}" != 1 || "${TRIBUN_NATIVE_REALTIME:-0}" != 1 ) ]]; then
  echo "Render cadence experiment requires fixed real-time fixture" >&2; exit 2
fi
[[ -x "$runtime/gameplayfootball" && -f "$runtime/tribun-runtime.json" ]]
python3 - "$here" "$runtime" <<'PY'
import hashlib, json, pathlib, sys
here, runtime = map(pathlib.Path, sys.argv[1:])
expected = json.loads((here / "upstream.json").read_text())
actual = json.loads((runtime / "tribun-runtime.json").read_text())
patches = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in
           ("instrument.py", "fixture_patch.py", "short_match_patch.py")}
if actual != {"upstream": expected, "patches": patches}:
    raise SystemExit("Native runtime revision or patches differ; rebuild")
PY
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# Copy, not shared writable assets or database. Native executable changes cwd.
if [[ "${TRIBUN_NATIVE_SHARED_ASSETS:-0}" == 1 ]]; then
  [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 && "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "$render_interval" == 100 ]] || exit 2
  python3 "$here/runtime-layout.py" "$runtime" "$work" "$out.layout.json"
else
  cp -a --reflink=auto "$runtime/." "$work/"
fi
node "$here/fixture-adapter.cjs" "$fixture" "$work/fixture.txt"
cp "$work/fixture.txt.json" "$out.fixture.json"
# Mid-match activation currently crashes upstream; isolate the experimental diagnostic.
python3 - "$out.fixture.json" <<'PY'
import json,os,sys
with open(sys.argv[1]) as f: manifest=json.load(f)
if any(t.get("substitutions") for t in manifest["teams"]) and os.environ.get("TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS")!="1":
    raise SystemExit("Native halftime substitutions quarantined: experimental diagnostic only")
PY
export TRIBUN_LEAGUE_SOCCER_FIXTURE="$work/fixture.txt"
export TRIBUN_LEAGUE_SOCCER_SEED="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["seed"])' "$out.fixture.json")"
export TRIBUN_LEAGUE_SOCCER_TRACE="$out"
cd "$work"
config="$work/native-match.config"
limit=420
if [[ "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "${TRIBUN_NATIVE_REALTIME:-0}" != 1 ]]; then
  echo "Fixed duration requires real-time diagnostic mode" >&2; exit 2
fi
if [[ "${TRIBUN_NATIVE_REALTIME:-0}" == 1 ]]; then
  scale="${TRIBUN_NATIVE_CLOCK_SCALE:-1.0}"
  if [[ "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 && "$scale" != 1.0 ]]; then
    echo "Fixed duration requires scale 1.0" >&2; exit 2
  fi
  case "$scale" in 1.0|1.10|1.25|1.5) ;; *) echo "Invalid diagnostic clock scale" >&2; exit 2;; esac
  sed "s/\"menu_smoke_match_time_scale\" \"6.0\"/\"menu_smoke_match_time_scale\" \"$scale\"/" "$config" > "$work/interactive.config"
  config="$work/interactive.config"
  grep -F "\"menu_smoke_match_time_scale\" \"$scale\"" "$config" >/dev/null
  limit=850
fi
if [[ "$render_interval" != 0 ]]; then
  python3 "$here/render-profile.py" "$config" "$work/render-profile.config" "$render_interval"
  config="$work/render-profile.config"
fi
if [[ "${TRIBUN_NATIVE_NULL_RENDERER:-0}" == 1 ]]; then
  [[ "${TRIBUN_NATIVE_NO_DRAW:-0}" == 1 && "${TRIBUN_NATIVE_NO_UPLOAD:-0}" == 1 && "$render_interval" == 100 && "${TRIBUN_NATIVE_FIXED_DURATION:-0}" == 1 ]] || exit 2
  # No Xvfb, no DISPLAY, no Wayland, no OpenGL window. SDL dummy is for CPU surfaces/events.
  log="$work/null-renderer.log"
  if ! env -u DISPLAY -u WAYLAND_DISPLAY SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
      timeout --foreground --kill-after=10s "${limit}s" ./gameplayfootball "$config" >"$log" 2>&1; then
    cat "$log"; exit 1
  fi
  cat "$log"
  grep -Fq '[tribun-render] null-context=dummy-no-gl' "$log"
  grep -Fq '[menu-smoke] Full match complete:' "$log"
  grep -Fq '[menu-smoke] Full-match verification succeeded, quitting test run' "$log"
else
  bash ./run_menu_smoke.sh ./gameplayfootball "$config" "$limit" \
  "[menu-smoke] Full match complete:" \
  "[menu-smoke] Full-match verification succeeded, quitting test run"
fi
python3 "$here/validate_trace.py" "$out"
python3 "$here/validate_fixture_trace.py" "$out" "$out.fixture.json"
node "$here/attack-report.cjs" "$out" "$out.attack.json"
python3 "$here/../../native_season.py" "$out" "$out.fixture.json" "$out.season.json"
