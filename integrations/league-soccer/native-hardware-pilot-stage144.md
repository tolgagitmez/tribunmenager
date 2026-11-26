# Stage 144 — actual native GL context and hardware match
The dedicated GLX preflight is no longer enough: the native game must report
its own current GL vendor and renderer at its first observed SDL swap. A
software renderer or mismatched vendor/renderer fails capture. The C hook
is locally compiled and used only for the GPU diagnostic. It does not
change rendering, physics, AI or animation. Mock interposition test is
not hardware verification. Single-host manual test after preparing runtime,
dedicated authenticated X server, FFmpeg hardware encoder, Chrome and dependencies:
```sh
TRIBUN_GPU_DEDICATED=1 python3 integrations/league-soccer/native_hardware_match.py \
  /private/runtime /private/fixture.json /private/hardware-run \
  --display :90 --encoder nvenc --gpu-index 0 --dedicated-display
```
VAAPI/QSV use --drm-device /dev/dri/renderD128 instead of --gpu-index.
The full diagnostic requires actual five-minute wall duration, HLS,
audio, native context, hardware encoder preflight, browser and both
manager acknowledgements. No physical GPU available on standard CI;
no hardware or capacity qualification until actual operator test. GPU
and encoder may be different physical devices; no utilization guarantee.
Private output outside static web root, no media redistribution.
Main untouched.
