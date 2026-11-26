# Stage 187 — native give-and-go and triangle combinations

Private experimental descendant of stage 186. TRIBUN_AV_COMBINATION=1
enables native wall-pass and triangle states in the idle-recovery fixture
without enabling the entire short-match attack profile. Existing native
movement requests, pass choice, touch and possession confirmations are
retained. Before beginning a wall pass, check a point 4 m in front of the
passer; third-player options receive a comparable continuation check.
Require 1.5 m onside margin, 2 m endpoint clearance, 1.3 m projected
corridor clearance, 3–20 m continuation distance and 2–12 m progress.
Sample moving opponents at three points over a 0.6 s heuristic horizon.
Recheck current return/triangle pass geometry, with native odds >=0.76
and no more than 0.04 below the native candidate. No forced return,
forced one-touch action, or new animation. First pass contact starts the
trial, not the speculative candidate. Original run logic remains.

Report initial contact, first receiver possession, second native contact
and final possession separately by wall or triangle. Unlogged restarts,
shots and invalid-pass clears may leave unresolved records. The baseline
does not emit experimental trial logs. Counts alone do not establish a
causal improvement. The private experiment is default-off and mutually
exclusive with the prior private movement/pass flags. CI configured to
compare separate private matches; not guaranteed identical seed.

Two isolated C++ predicates were copied into a standalone file and
compiled using g++ -std=c++17 -Wall -Wextra -Werror; 15 assertions
executed successfully. These test threshold behavior only. Parser tests
are added but not run; full cumulative patch application, native build
and actual five-minute matches remain unverified. Main unchanged.
