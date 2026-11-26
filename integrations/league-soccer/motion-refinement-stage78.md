# Stage 78 — locomotion refinement (experimental)

Parent: 728dedfadfdce6c94ec1580535c5e697f751dd3a. This branch does not replace the original stage 78 experiment or enable native production.

- A shared elliptical traction envelope limits combined longitudinal and lateral velocity changes, preserving the requested change direction.
- Smoothstep blending across 0.25–0.75 m/s avoids a hard low-speed switch.
- Preserve the incoming vertical component; reject non-finite time steps by retaining the original delta.
- These are tuning hypotheses, not measured human biomechanics. No player mass model, new animation clip, IK, or foot-contact adjustment is introduced.
- Tests cover combined traction, reverse turns, boundary continuity, rotational invariance, invalid time steps and existing limits.
- The existing six-match diagnostic compares the candidate against the unmodified short-match profile. It does not establish superiority over the original stage 78 smoothing or compatibility with stage 77 close-touch; those need separate paired experiments.
- Keep the existing attack, speed, pass accuracy, duration and resource gates; never promote without completed evidence and visual review.
