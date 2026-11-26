# Stage 171 — local WSLg GPU alpha trial
In Ubuntu, existing stage169 checkout: commit or preserve your own
changes first. From ~/tribun-alpha:
    git fetch origin experiment/native-wsl-gpu-stage171
    git switch -c native-gpu-171 FETCH_HEAD
    bash BASLAT.sh --native-wsl-gpu
Use same runtime if manifest matches; no C++ source changes.
Requires glxinfo, WSLg /dev/dxg, DISPLAY=:0, D3D12 hardware GLX.
A real game GL context must match the preflight before window capture.
Shared local display is NOT dedicated: keep game window visible,
avoid overlapping applications; capture uses only owned SDL window ID.
Never publish captures or expose the private server. CPU x264/HLS,
automated browser and full match verification remain; smoothness not
guaranteed. No hardware test in GitHub Linux runner; software regression
and mocked contracts only. No main change. GPU opt-in only.
