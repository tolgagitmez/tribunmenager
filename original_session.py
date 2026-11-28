"""Explicit local desktop launch bridge, never edits native game settings."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import original_engine


def allowed(client, server, host, origin=None):
    # Only the IPv4 loopback server and literal localhost/127.0.0.1 Host.
    # Refuse forwarded/public bindings, DNS rebinding and cross-site POSTs.
    try:
        if not (ipaddress.ip_address(client).is_loopback and
                ipaddress.ip_address(server[0]).is_loopback):
            return False
    except ValueError:
        return False
    hosts={f'127.0.0.1:{server[1]}',f'localhost:{server[1]}'}
    if server[1]==80:
        hosts.update(('127.0.0.1','localhost'))
    return host in hosts and (origin is None or origin=='http://'+host)


class OriginalSession:
    def __init__(self):
        self.lock=threading.Lock()
        self.process=None

    def _status(self):
        supported=sys.platform.startswith('linux')
        work=original_engine.cache_root()/original_engine.REVISION
        installed=(work/'pristine-manifest.json').is_file()
        code=self.process.poll() if self.process is not None else None
        running=self.process is not None and code is None
        save_status=None
        if supported:
            from original_saves import store_status
            save_status=store_status(original_engine.save_root_path())
            # A live session directory is not an interrupted session.
            if running:
                save_status['interruptedSessionCount']=None
        return dict(supported=supported,installed=installed,running=running,
                    lastExitCode=code,revision=original_engine.REVISION,
                    nativeDesktop=True,managerBridge=False,saveStore=save_status)

    def status(self):
        with self.lock:
            return self._status()

    def results(self):
        with self.lock:
            path=original_engine.cache_root()/'last-native-results.json'
            try:
                if path.is_symlink() or path.stat().st_size>4*1024*1024:
                    return None
                result=json.loads(path.read_text(encoding='utf-8'))
                if result.get('schema')!=1 or result.get('revision')!=original_engine.REVISION:
                    return None
                # Old reports remain readable but cannot be certified current.
                result['snapshotConsistency']='unknown'
                if sys.platform.startswith('linux') and result.get('snapshotId'):
                    from original_saves import current_snapshot
                    try:
                        current=current_snapshot(original_engine.save_root_path())
                        result['snapshotConsistency']='matches-saved-snapshot' if current is not None and current.name==result['snapshotId'] else 'different-saved-snapshot'
                    except (OSError,RuntimeError,ValueError):
                        result['snapshotConsistency']='unknown'
                # Internal identifier is not needed by the browser.
                result.pop('snapshotId',None)
                return result
            except (OSError,ValueError,AttributeError):
                return None

    def launch(self):
        with self.lock:
            state=self._status()
            if not state['supported'] or not state['installed']:
                return 409,state
            if state['running']:
                return 409,state
            # Fixed command, no user-supplied parameters or config overrides.
            self.process=subprocess.Popen([sys.executable,
                str(Path(__file__).resolve().parent/'start.py'),
                '--mode','original','--original-installed-only'],
                env=original_engine.clean_env(os.environ))
            return 202,self._status()
