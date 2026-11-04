"""Extract/pin candidate4 for 2512-only acceptance; host preparation only."""
import importlib.util,json,subprocess,sys,time,zipfile
from pathlib import Path
import devtools_2512_session as ds
from serial_test_coordination import drift_pending
t=ds.t;Q=ds.Q;BASE=t.ROOT/'BUILD/unified-g10-candidate4-20261102-r1'
EXTRACT=t.ROOT/'BUILD/unified-g10-candidate4-2512-acceptance-20261102-r1'
LABEL='STR8N-UNIFIED-MON-g00000010-ASMDBG-g2-candidate4';KIT=EXTRACT/LABEL;FND=KIT/'foundation'
PIN='1e9d5a8e0f81036412ae7411edb80db37c9b4cd1d4eddcd2756fae26b27e77e9'
MONS=tuple(f'B{b}> '.encode() for b in range(4));BM=b'BM> ';FT=ds.d.FT
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def prepare():
 pr=json.loads((BASE/'packaging-receipt.json').read_text());archive=BASE/(LABEL+'.zip');assert pr['passed'] and t.sha(archive.read_bytes())==pr['ZIP_sha256']==PIN
 if not EXTRACT.exists():
  EXTRACT.mkdir()
  with zipfile.ZipFile(archive) as z:
   for member in z.infolist():
    dest=(EXTRACT/member.filename).resolve();assert dest.is_relative_to(EXTRACT.resolve()) and not member.is_dir();dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
 mf=json.loads((KIT/'CANDIDATE-MANIFEST.json').read_text())
 for name,info in mf['files'].items():
  body=(KIT/name).read_bytes();assert len(body)==info['bytes'] and t.sha(body)==info['sha256'],name
 p=subprocess.run([sys.executable,'verify_candidate.py'],cwd=KIT,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
 core=module('console_core',KIT/'terminal/console_core.py');console=module('candidate4_console',KIT/'terminal/nf_console.py');assert console.VERSION=='0.1.2'
 return mf,core,console
def await_window(seconds):
 announced=False
 while True:
  try:ds.ins.window(seconds);return
  except AssertionError:
   if not announced:print('WAIT RTC priority/window; no board port opened',flush=True);announced=True
   time.sleep(1)
def boundary():
 if drift_pending():raise InterruptedError('RTC priority at safe boundary; restore owner RAM and release')
