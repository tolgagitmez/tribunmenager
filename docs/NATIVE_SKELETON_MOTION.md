# Stage 180 — native ankle pose samples

Experimental descendant of stage 179. At simulation PreparePutBuffers, copy
the designated active ball carrier's animation ID, frame, touch frame,
snapshot time, match phase, match time and ball position. Sample movement
or frames within three of the authored contact frame. Pass this metadata
through the existing FetchPutBuffers handoff; in Put, read original left
and right ankle node derived positions after animation Apply and spatial
update, before historic temporal interpolation. Log one sample per player
snapshot. Do not query live ball position in the render-side sampler.
Do not change the skeleton, animation playback, IK or ball physics.

Report ankle-to-ball distances at sampled contact frames, adjacent horizontal
ankle speeds and candidate low-ankle motion intervals (experimental 0.16 m
height and 0.5 m/s speed thresholds). Exclude different animation IDs,
non-increasing frames, phase changes, duplicate snapshots and gaps over
100 ms. These proxies do not establish a planted sole, exact boot-to-ball
contact, actual foot slide or a successful physical touch. Sampling is
limited to the designated carrier and may miss frames. Coordinate origin,
ground height, foot geometry and simulation/render synchronization must
be verified in real matches before changing animation behavior.

Parser tests written for motion, contact distance, gaps, duplicate and
invalid samples. CI configured for pinned native build and private match;
not yet independently executed or verified here. Main and Windows launcher
remain unchanged. New native build required.
