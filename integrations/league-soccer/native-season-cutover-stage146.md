# Stage 146 — native season cutover rehearsal
Extract existing standings logic into shared projection with no intended
behavior change. Native cutover rehearses only in an in-memory copy of a
database, never changes actual official results. Reject legacy state,
partial rounds, mismatched frozen configuration and evidence digests.
Apply verified private native scores/cards/appearances through existing
season writer; compare all player state/appearance rows and standings
against private ledger. Check next-round participating player readiness
and bans against previously projected native results. Current conditioning
formula is unchanged (native minutes/sprint data, not direct fatigueFactor).
No authoritative writer or backend selection enabled. Real AV capacity
and authenticated match tests are still blockers; synthetic tests cannot
qualify them. Source must be a committed consistent database snapshot.
