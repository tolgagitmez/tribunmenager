# Stage 172 — stationary controlled ball carrier recovery
Observed user match rendered smoothly with WSLg Intel UHD but carrier
appeared stationary around end of first half and again in second half.
Single screenshot cannot establish whether only AI or whole match clock
stalled. Upstream ElizaController pass filter requires tactical advantage
or support; if no candidate, dribble movement may remain idle. New
per-controller watchdog uses native actual clock, confirmed unique
possession, last touch, low movement, close ball, open play and AI
outfielder only. 1200ms stationary; retry every 400ms while stagnant.
Prioritize safe native short pass (odds >=.55, receiver clearance and
onside), else native low-speed move in clear space, else native panic
clearance only near own goal under pressure. No teleport, forced touch,
animation unlock, or global state reset. Reset watchdog on controller
Reset, phase change, ineligible observation, motion or gap. Log requests,
not outcomes. Explicit private alpha sets flag by default, GPU route
unchanged, standard diagnostic runs unchanged. C++ patch changes require
rebuild. Fix stage171 lease mock regression by not passing false optional
kwargs. Actual real user freeze reproduction not yet confirmed. No main.
