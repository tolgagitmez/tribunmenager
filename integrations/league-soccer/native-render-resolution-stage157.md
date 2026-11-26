# Stage 157 — native resolution and SDL swap comparison
Stage 143 real resource trial (run 45864135388): single 299.36s / CPU
p95 68.5% / reduced-image repeats 58.89%; dual baseline 766.58 and
798.47s / 99.88% / 74.40 and 75.19%; dual bounded 574.44 and
574.94s / 76.46% / 79.20 and 80.65%. Both dual trials failed.
Stage 156 attack comparison remains running. Stage 155 lease contracts
passed but separate native pilot failed; no production readiness claim.
Pinned upstream graphics_system.cpp reads context_x/context_y defaults
1280x720 and context_fullscreen. Test explicit 1280x720 and 960x540
windowed configs; actual X window geometry must match. Capture output
remains 1280x720 H264 25fps, with candidate upscaled, not native 720p
detail. Same frozen fixture/seed, baseline AI, two GL workers, same
software encoder/audio, SDL swap probe in both. No synthetic frames,
physics timing changes, or automatic selection. Provisional screening
requires reduced repetition by at least five percentage points, >=10%
higher swap rate, no longer identical runs or worse p95 gap, <=1% drops.
Only one pair; native window geometry not independently GPU framebuffer
verification, swaps not unique frames, and visual sharpness unverified.
No changes to normal league default or main.
