# Stage 154 — native fixture lifecycle
Stage 152 and 153 actual single-match tests were still running at review;
stage 153 quality contracts passed. Fix false live indicators when a
fixture is queued or failed. Native status derives running from a
current managed lease, not the scheduled clock. Explicit queued,
preparing, interrupted, failed, inconsistent, blocked, completed states;
never send raw attempt IDs or error strings. Running means worker
reserved, not proof video is ready. Native status polls every three
seconds locally; legacy league retains previous polling and watch route.
Hold displayed match day at earliest incomplete round rather than skip
past unresolved matches. E2E asserts one complete and two queued.
No automatic restart, official write or production change.
