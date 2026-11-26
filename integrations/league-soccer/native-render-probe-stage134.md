# Stage 134 — renderer swap cadence
Optional preload counts completed SDL GL swap calls, timestamps against the
observed match window, and reports average cadence, p95 and maximum gaps.
It is not GPU presentation timing, unique image content or decoded FPS.
Missing/ambiguous instrumentation blocks a passing probe experiment.
The preload only runs in the native game process; source is compiled locally.
CI compares two concurrent matches with LP_NUM_THREADS=2 vs 1, same bounded
FFmpeg filter worker, same fixtures and unchanged graphics cadence, CRF, audio
and match duration. A single comparison cannot establish perceptual quality
or production capacity. Experimental reports are excluded from admission.
