# Stage 127 — dedicated GPU GLX diagnostic

Default remains Xvfb + software OpenGL. Do not share a desktop or disable X access
control. This pilot requires a separately provisioned local GPU-backed X server
(e.g. :90), authenticated with XAUTHORITY, no TCP listener, 1920x1080-compatible
window, no other League Soccer process, and glxinfo (mesa-utils). The runner
does not install drivers or create the GPU X server. Only a single GPU match is
supported; concurrent capacity is deliberately blocked until per-match displays
and resource isolation are proven.

With a pinned prepared engine and existing balanced fixture:

    python3 integrations/league-soccer/native_gpu_display.py --display :90
    TRIBUN_GPU_DISPLAY=:90 TRIBUN_GPU_DEDICATED=1 python3 integrations/league-soccer/native-live-video.py /path/to/runtime /path/to/balanced.json /path/to/new-output --audio --interactive --linger 60

Run the existing browser validation in another terminal with
TRIBUN_EXPECT_AUDIO=1 TRIBUN_EXPECT_CONTROL=1 TRIBUN_EXPECT_FULL_PLAYBACK=1
TRIBUN_PLAYBACK_MIN_SECONDS=300, passing the output's local-url.txt.
Run equivalent software baseline without GPU environment variables.

The preflight refuses software/indirect/unknown rendering. It validates GLX
on the same display, not the actual game's GL context. A hardware capacity claim
still requires engine-context evidence and repeatable paired full matches.
No public media upload, engine logic change or commercial deployment.
