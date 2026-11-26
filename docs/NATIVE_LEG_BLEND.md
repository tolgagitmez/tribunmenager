# Stage 181 — locomotion leg correction smoothing

An opt-in private CPU-only descendant of stage 180. Smooths the engine's
existing actual/animation velocity ratio before native hip, knee and ankle
offset blending. Time-dependent filter uses a 60 ms scale, constrains the
adjusted ratio to within 0.12 of native and preserves native speed clamps.
Reset on phase change, clock discontinuity, over-100 ms gap, ineligibility
or native ResetSituation. Scope: active AI outfield movement animations
without touch frame or special states, ball more than 1.2 m away, actual
and authored movement speeds >=1 m/s. No forced foot pin, IK, root motion,
playback speed, or direct changes to ball contact or physics.

Enable with TRIBUN_AV_LEG_BLEND=1 only on private alpha path; default off.
CI configured to run baseline and experimental private matches, archive
reports and native logs. These are separate fixtures, not a guaranteed
identical seeded A/B; do not infer causation from their raw differences.
Compare matched locomotion contexts and ankle motion proxy in stage 180.
Blend samples are sparse correction magnitude evidence, not proof of
foot-slide reduction. Stage 180 only samples designated carriers, so
additional representative off-ball sampling and sole/ground calibration
are needed for comprehensive gait evaluation.

Manually reproduced exact LegBlendWatch and 12 assertions compiled and
passed locally with C++17, warnings as errors. Repository-wide policy test,
Python parser tests, full native patch/build and real matches not verified.
Main and Windows launcher unchanged; new native build required.
