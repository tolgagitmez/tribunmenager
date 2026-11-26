# Stage 210 — exact native animation selector rejection diagnostics

Actual archived stage 204 baseline (run 45903395880, artifact
15156694798): player 20, team 1, phase 2, native elapsed 226300–275500
ms. Map via trace fixedClock.startMs=2370 to actual time interval
[228670,277870). Count raw [tribun-action] records within interval:
ball-control rejected 2188, accepted 62, contact 30; movement rejected
2033, accepted 155. These are repeated selection attempts, not
distinct animation defects. Normal requeue protection can reject
commands; accepted animation does not imply displacement.

Pinned Humanoid::SelectAnim inspected: 17 false exits, 1 true exit.
Patch audits exact exits for active AI-controlled slow unique carrier
during open play, without changing return values, selector conditions,
touch, movement or physics. Reasons identify early distance/prediction
filters, requeue restrictions, similar commands, momentum, empty crude
selection, incompatible movement and final no applicable animation.
Logs include requested/current/outgoing speed, interrupt, player,
phase, actual and match times. Accepted low outgoing velocity is
not proof of observed motion.

The new Python reader is wired into match quality reports. Five local
unit tests actually passed against copied reader and tests
(/tmp/stage210). These are synthetic parser tests, not real evidence
for the new reasons. The exact native exit order was inspected
against pinned source; stage 210 has not been compiled or run.
Stage 209 PR #77 run 45905280421 completed its full patched policy
preflight and was building the engine at last check. Preserve that
run and stage 204 second match. No production qualification, no
main merge. New code is diagnostic only.
