"""Atomic JSON publication with bounded Windows file-sharing retries."""
import json,os,tempfile,time
from pathlib import Path

def publish(path,value,timeout=10):
    path=Path(path)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    staged=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,indent=2);stream.write('\n')
            stream.flush();os.fsync(stream.fileno())
        deadline=time.monotonic()+timeout
        while True:
            try:os.replace(staged,path);return
            except OSError as error:
                if getattr(error,'winerror',None) not in (5,32,33) or time.monotonic()>=deadline:raise
                time.sleep(.05)
    finally:
        try:staged.unlink(missing_ok=True)
        except OSError:pass  # Preserve the original error and leave diagnostic staging data.
