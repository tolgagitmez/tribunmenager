"""Single-host worker fencing; expired attempts are quarantined, never replayed automatically."""
import hashlib
from pathlib import Path

TTL=30
SCHEMA="""CREATE TABLE IF NOT EXISTS native_av_leases(
 attempt TEXT PRIMARY KEY, boot TEXT NOT NULL, expires REAL NOT NULL,
 quarantined INTEGER NOT NULL DEFAULT 0 CHECK(quarantined IN (0,1)));
"""
def boot():
    return hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()

def expire(db,now):
    rows=db.execute("""SELECT j.attempt FROM native_av_jobs j JOIN native_av_leases l ON l.attempt=j.attempt
        WHERE j.state='running' AND (l.expires<=? OR l.boot<>?)""",(now,boot())).fetchall()
    for (attempt,) in rows:
        db.execute("UPDATE native_av_jobs SET state='failed',finished=?,error='Worker heartbeat expired' WHERE attempt=? AND state='running'",(now,attempt))
        db.execute("UPDATE native_av_leases SET quarantined=1 WHERE attempt=?",(attempt,))
    return len(rows)

def reserve(db,attempt,now):
    db.execute('INSERT INTO native_av_leases(attempt,boot,expires) VALUES(?,?,?)',(attempt,boot(),now+TTL))

def renew(db,attempt,now):
    return db.execute("""UPDATE native_av_leases SET expires=? WHERE attempt=? AND boot=? AND quarantined=0 AND expires>?
        AND EXISTS(SELECT 1 FROM native_av_jobs WHERE attempt=? AND state='running')""",(now+TTL,attempt,boot(),now,attempt)).rowcount==1

def live(db,attempt,now):
    row=db.execute('SELECT boot,expires,quarantined FROM native_av_leases WHERE attempt=?',(attempt,)).fetchone()
    return row is None or (row[0]==boot() and row[1]>now and row[2]==0)

def held(db):
    return db.execute('SELECT count(*) FROM native_av_leases WHERE quarantined=1').fetchone()[0]

def clear_after_reboot(db,attempt):
    return db.execute('DELETE FROM native_av_leases WHERE attempt=? AND quarantined=1 AND boot<>?',(attempt,boot())).rowcount==1
