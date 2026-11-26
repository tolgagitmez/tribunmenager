# Stage 137 — verify actual OpenAL source ownership
Stage 136 concurrent PulseAudio synthetic-client test passed. This stage checks
real OpenAL source clients using two distinct test tones on independent private
monitors, with process ownership and spectral isolation checks. Synthetic
tones are CI-only and never used in actual matches. Actual native capture
requires sink input process IDs from the game's process tree, on the intended
private sink. Transient pactl errors are counted and retried; a missing or
unidentified owner cannot pass. Ownership is a sampled observation, not
continuous proof of source identity or perceptual sound quality. Full
concurrent match validation still required. No gameplay or main change.
