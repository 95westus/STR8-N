"""Recurring host supervisor: no overlapping sweeps, RTC first, owner stop wins."""
import ctypes,json,msvcrt,os,time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import unified_readonly_soak as soak

def alive(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];k.CloseHandle.argtypes=[wintypes.HANDLE]
    h=k.OpenProcess(0x1000,False,int(pid))
    if not h:return ctypes.get_last_error()!=87
    try:
        code=wintypes.DWORD();return not k.GetExitCodeProcess(h,ctypes.byref(code)) or code.value==259
    finally:k.CloseHandle(h)

def run():
    state=soak.read(soak.CONTROL);root=Path(state['root']);worker=root/'worker.json'
    lock=(root/'supervisor.lock').open('a+b');held=False
    try:
        if lock.seek(0,2)==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);held=True
        except OSError:print('DEFER: soak sweep already supervised; no port opened');return
        if worker.exists():
            w=soak.read(worker)
            finished_initial=w.get('initial_sweep') and any(root.glob('sweep-*.json'))
            if w.get('running') and not finished_initial and alive(w['pid']):print('DEFER: existing soak sweep running; no port opened');return
        if not state.get('active') or (root/'STOP').exists():
            state['active']=False;soak.save(soak.CONTROL,state);print('STOPPED: no port opened');return
        assert soak.t.sha(Path(soak.__file__).read_bytes())==state['driver_sha256'],'Pinned read-only driver changed'
        soak.save(worker,dict(pid=os.getpid(),running=True,started_utc=soak.NOW()))
        summary=dict(started_utc=soak.NOW(),passed=[],deferred=[],failures=[],not_due=[])
        for board in state['boards']:
            latest=soak.read(soak.CONTROL)
            if not latest.get('active') or (root/'STOP').exists():break
            row=latest['results'][board]
            if row.get('failed'):continue
            if row.get('last_pass_utc') and time.time()-datetime.fromisoformat(row['last_pass_utc']).timestamp()<latest['interval_minutes']*60:
                summary['not_due'].append(board);continue
            try:
                path,r=soak.unit(board,latest)
                row.update(passed_units=row['passed_units']+1,last_pass_utc=soak.NOW(),last_report=path)
                summary['passed'].append(board);print('PASS soak '+board+' '+r['MON_slot'],flush=True)
            except soak.Defer as error:
                row['deferrals']+=1;row['last_defer']=str(error);summary['deferred'].append(dict(board=board,reason=str(error)))
            except Exception as error:
                row.update(failed=True,error=repr(error));summary['failures'].append(dict(board=board,error=repr(error)))
                print('FAIL soak '+board+' '+repr(error),flush=True)
            # Preserve a concurrent owner STOP rather than resurrecting old state.
            merged=soak.read(soak.CONTROL);merged['results'][board]=row;merged.update(updated_utc=soak.NOW(),last_sweep=summary)
            if (root/'STOP').exists():merged['active']=False
            soak.save(soak.CONTROL,merged);soak.save(root/'status.json',merged)
        summary['finished_utc']=soak.NOW();soak.save(root/f'supervised-sweep-{time.time_ns()}.json',summary)
        print(json.dumps(summary),flush=True)
    finally:
        if held:
            if worker.exists():
                w=soak.read(worker)
                if w.get('pid')==os.getpid():w.update(running=False,finished_utc=soak.NOW());soak.save(worker,w)
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()

if __name__=='__main__':run()
