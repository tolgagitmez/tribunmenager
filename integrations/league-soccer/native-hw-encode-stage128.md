# Stage 128 — hardware H.264 encoding pilot

CPU x264 remains the default. Explicit hardware experiments use the existing
local HLS native runner, not a new renderer. Linux FFmpeg must be built with
the selected encoder and the host needs a working driver/device. Never use
public access or grant broad permissions to device nodes.

Example environment for one native audio + interactive match:
- NVIDIA: TRIBUN_AV_ENCODER=nvenc TRIBUN_AV_GPU_INDEX=0
- Intel: TRIBUN_AV_ENCODER=qsv TRIBUN_AV_DRM_DEVICE=/dev/dri/renderD128
- AMD (or supported Intel VAAPI): TRIBUN_AV_ENCODER=vaapi TRIBUN_AV_DRM_DEVICE=/dev/dri/renderD128

Use the existing native-live-video.py runtime fixture output --audio --interactive
--linger 60 and existing full browser playback test. GPU rendering is optional
and separately gated by stage 127. Real preflight encodes 100 synthetic 720p25
frames and decodes them before native game startup; failure stops the experiment
without fallback. The hardware profile requests baseline H.264, no B frames,
2-second GOP/forced keyframes, 2.5 Mb/s target (not visually equivalent to CRF25).
Full HLS timing, actual playback, command acknowledgements and A/V evidence
remain required. Measure objective visual quality, encoded rate and GPU/CPU load
before any performance claim. Concurrent hardware sessions intentionally blocked.
No game logic, public assets or main branch change.
