"""Permanent owner-local rc1g34 archive; no device or firmware build."""
import hashlib,json,os,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'BUILD/rc1-r10p2-g0034'
OUT=ROOT/'local-archives/STR8-N-rc1-g0034-2604-20261102'
sha=lambda b:hashlib.sha256(b).hexdigest()

def run():
 meta=json.loads((BUILD/'r10-build.json').read_text());fw=(BUILD/'firmware.bin').read_bytes();f=(BUILD/'payload/str8n-v2-recovery-f000-ffff.bin').read_bytes()
 assert meta['generation']==52 and sha(fw)==meta['firmware_sha256']=='0df4a802d618c0df5e658dcf2cd05037f0a892a209abaeac6bca0d595c468945'
 assert len(f)==4096 and sha(f)=='78ee949e20545cbe0e10030185dd5629b65c584af526c16e2c75c9fa103ceaec'
 receipt=ROOT/'output/qualification/rc1-r10p2-install-2604/2604/flash-report.json';assert json.loads(receipt.read_text())['passed']
 OUT.mkdir(parents=True);(OUT/'.gitignore').write_text('*\n')
 def durable(name,body):
  p=OUT/name
  with p.open('xb') as s:s.write(body);s.flush();os.fsync(s.fileno())
  assert p.read_bytes()==body
 durable('firmware-B1-B3-g0034.bin',fw);durable('F-rc1-g0034-4096.bin',f)
 parent=(ROOT/'BUILD/rc1-r10p2-base/firmware.bin').read_bytes()[-4096:];assert sha(parent)=='274e5419b7781de4be2c71ff4ff320bd77b5b7068033c2a9901d4fe1ce02380a';durable('F-earlier-parent-4096.bin',parent)
 durable('qualified-2604-install-receipt.json',receipt.read_bytes())
 durable('baseline-g0034.json',(ROOT/'tests/baselines/rc1-r10p2-current.json').read_bytes())
 durable('selected-source.json',(ROOT/'src/current/target.json').read_bytes())
 refs=subprocess.run(['git','show-ref'],cwd=ROOT,capture_output=True,check=True).stdout;durable('git-refs-at-preservation.txt',refs)
 inputs={}
 with zipfile.ZipFile(OUT/'rc1-g0034-build-source-and-payload.zip','x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for directory,prefix in ((BUILD,'qualified-build'),(ROOT/'src/current','selected-source-snapshot'),(ROOT/'release/candidates/rc1-r10p2','rc1-r10p2-parent')):
   for p in sorted(directory.rglob('*')):
    if p.is_file():
     assert not p.is_symlink();body=p.read_bytes();name=prefix+'/'+p.relative_to(directory).as_posix();z.writestr(name,body);inputs[name]=dict(bytes=len(body),sha256=sha(body))
  for rel in ('tools/build_rc1_r10.py','tools/select_rc1_r10p2.py','docs/rc1/R10_G0034.md'):
   body=(ROOT/rel).read_bytes();z.writestr('project/'+rel,body);inputs['project/'+rel]=dict(bytes=len(body),sha256=sha(body))
  for p in sorted((ROOT/'tools/str8build').rglob('*.py')):
   body=p.read_bytes();name='project/'+p.relative_to(ROOT).as_posix();z.writestr(name,body);inputs[name]=dict(bytes=len(body),sha256=sha(body))
 with zipfile.ZipFile(OUT/'rc1-g0034-build-source-and-payload.zip') as z:
  assert z.testzip() is None
  for name,info in inputs.items():assert sha(z.read(name))==info['sha256']
 durable('source-archive-manifest.json',(json.dumps(inputs,indent=2)+'\n').encode())
 durable('KEEP-LOCAL.txt',b'PERMANENT OWNER ARCHIVE - do not treat as BUILD/tmp/qualification cleanup.\nUntracked and ignored by Git; never publish owner/device captures.\nrc1 g0034 = generation52, exact qualified build plus source/payload.\nfirmware-B1-B3 is98KiB and does not include B0 or fresh board settings.\nA separate live-board/ capture will preserve the actual full128KiB flash.\nDo not restore old wear counters blindly; restoration needs a reviewed plan.\n')
 files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in OUT.iterdir() if p.is_file()}
 durable('archive-manifest.json',(json.dumps(dict(permanent=True,local_only=True,firmware_generation='00000034',files=files,board_access=False,firmware_builds=0),indent=2)+'\n').encode())
 relative=OUT.relative_to(ROOT).as_posix()
 tracked=subprocess.run(['git','ls-files','--',relative],cwd=ROOT,capture_output=True,text=True,check=True);assert not tracked.stdout.strip()
 ignored=subprocess.run(['git','check-ignore','-v',relative+'/firmware-B1-B3-g0034.bin'],cwd=ROOT,capture_output=True,text=True,check=True)
 print(json.dumps(dict(passed=True,permanent_archive=str(OUT),build_SHA256=sha(fw),F_SHA256=sha(f),source_archive_members=len(inputs),Git_tracked=False,Git_ignored=True,ignore_rule=ignored.stdout.strip(),board_access=False),indent=2))

if __name__=='__main__':run()
