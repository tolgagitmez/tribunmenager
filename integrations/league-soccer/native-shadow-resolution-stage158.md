# Stage 158 shadow experiment
Native shadow depth texture 2048x2048 vs 1024x1024; same 720p
window and shadow update cadence. 75% fewer shadow texels, not
75% lower total render cost. First actual shadow viewport required.
Stage 157 workflow mistakenly invoked the attack comparison;
replacement tests both graphics experiments with a shared baseline.
No disabled shadows, altered physics, synthetic frames or promotion.
Stage 154 E2E succeeded, but repeated reduced images 65.06% and
longest identical run 3.48s. Real speed and visual results pending.
No main change.
