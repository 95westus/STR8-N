"""Shared serial lease; RTC collection has priority over resumable soak units."""
import contextlib,json,msvcrt,os,time,uuid,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'output/qualification/serial-coordination'

def drift_pending():
    if not ROOT.exists():return False
    for p in ROOT.glob('drift-*.json'):
        try:
            state=json.loads(p.read_text())
            if not state.get('released') and time.time()-state['created']<900:return True
        except (OSError,ValueError,KeyError):return True
    return False

def sharing_retry(action,seconds=3):
    deadline=time.monotonic()+seconds
    while True:
        try:return action()
        except OSError as error:
            if getattr(error,'winerror',None) not in (32,33) or time.monotonic()>=deadline:raise
            time.sleep(.05)

def release_marker(marker):
    # Publish release before deletion: Windows readers/scanners may briefly
    # deny deletion, but an inactive marker must never block the next worker.
    state=sharing_retry(lambda:json.loads(marker.read_text()));state.update(released=True,released_at=time.time())
    sharing_retry(lambda:marker.write_text(json.dumps(state)))
    try:sharing_retry(lambda:marker.unlink(missing_ok=True))
    except OSError as error:
        if getattr(error,'winerror',None) not in (32,33):raise
        warnings.warn(f'Released serial marker retained after sharing conflict: {marker}',RuntimeWarning)

@contextlib.contextmanager
def serial_lease(kind,timeout=180):
    # Analyzer subprocesses share their parent's already-held drift lease.
    inherited=os.environ.get('STR8_DRIFT_LEASE_PID')
    if kind=='drift' and inherited:
        try:owner=json.loads((ROOT/'owner.json').read_text())
        except (OSError,ValueError):owner={}
        if owner.get('kind')=='drift' and str(owner.get('pid'))==inherited:
            yield
            return
    ROOT.mkdir(parents=True,exist_ok=True);marker=None
    if kind=='drift':
        marker=ROOT/('drift-'+uuid.uuid4().hex+'.json')
        marker.write_text(json.dumps(dict(pid=os.getpid(),created=time.time())))
    handle=(ROOT/'lease.lock').open('a+b');locked=False;start=time.monotonic();previous=os.environ.get('STR8_DRIFT_LEASE_PID')
    try:
        if handle.seek(0,2)==0:handle.write(b'0');handle.flush()
        while time.monotonic()-start<timeout:
            if kind!='drift' and drift_pending():time.sleep(.2);continue
            try:
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;break
            except OSError:time.sleep(.2)
        if not locked:raise TimeoutError('Serial lease unavailable; no board port opened')
        if kind!='drift' and drift_pending():raise TimeoutError('Drift request has priority; retry soak later')
        (ROOT/'owner.json').write_text(json.dumps(dict(kind=kind,pid=os.getpid(),since=time.time())))
        if kind=='drift':os.environ['STR8_DRIFT_LEASE_PID']=str(os.getpid())
        yield
    finally:
        if locked:
            (ROOT/'owner.json').write_text(json.dumps(dict(kind='idle',released=time.time())))
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        handle.close()
        try:
            if marker:release_marker(marker)
        finally:
            if kind=='drift':
                if previous is None:os.environ.pop('STR8_DRIFT_LEASE_PID',None)
                else:os.environ['STR8_DRIFT_LEASE_PID']=previous
