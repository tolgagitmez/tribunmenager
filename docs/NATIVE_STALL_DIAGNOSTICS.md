# Stage 173 — classify observed match inactivity
User reported a stationary ball carrier near 44:08 and again in second
half, while GPU rendering is now smooth. Existing trace already includes
native clock, phase, ball and player velocities and unique possession.
Sampled stationary controlled outfielder episodes >=1200 native ms,
exclude set pieces, keepers, ambiguous possession, motion, phase
transitions and gaps >250ms. Wall observer checks bounded trace tail every
500ms while capture runs, records >=3s progress gaps only after kickoff,
no post-final gap. No automatic clock manipulation or forced animation
reset. Keep video repetition as separate existing quality measure.
Partial traces can inform diagnosis but not produce verified results.
Unknown missing log not zero. Existing C++ patch hashes unchanged from
172; GPU setting retained. Stage172 build/preparation reached real
alpha run; full result pending. No main merge, no claimed cure.
