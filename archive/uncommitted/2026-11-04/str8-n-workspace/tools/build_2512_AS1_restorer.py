"""Build a five-block RAM restorer for review; opens no board port."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
import devtools_2512_session as ds
ROOT=ds.t.ROOT;REPO=ds.t.REPO;SCOPE=ds.Q/'2512-AS1-PROGRAM-scope-20261102-r1';OUT=ROOT/'BUILD/2512-AS1-restorer-r1'
sys.path.insert(0,str(REPO/'tools'));from build_mona import cells,sha

def run():
 p=json.loads((SCOPE/'plan.json').read_text());assert p['temporary_PROGRAM_bytes']==320 and p['write_blocks']==['00140','00800','00840','00880','008C0']
 for a,h in p['preimages'].items():assert sha((SCOPE/f'SPI-{a}-original.bin').read_bytes())==h
 OUT.mkdir();stage=OUT/'source';stage.mkdir();old=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source'
 for n in ('sram-bench.asm','str8n-v2-public.inc','workbench-layout.inc','workbench-interface.inc','program-layout.inc'):shutil.copyfile(old/n,stage/n)
 provider=(ROOT/'BUILD/program-sp1-g3-store-r2/STR8N-PROGRAM-SP1-6B00.bin').read_bytes();assert sha(provider)=='8128b9c542ecdc335d400465ed9a3cb8f3a1fbfce6ed37a507ddfe1bafc4f667'
 f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert sha(f)==json.loads((REPO/'F_FREEZE.json').read_text())['sha256'];crc=binascii.crc_hqx(f,65535)
 values=dict(BENCH_F_LO=crc&255,BENCH_F_HI=crc>>8,BENCH_PV_HI=provider[-2],BENCH_PV_LO=provider[-1],BENCH_TRANSFER=0x75d4,BENCH_LIMIT=0,BENCH_ALLOW_BYTES=10)
 (stage/'sram-bench-params.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in values.items()))
 (stage/'sram-bench-allow.inc').write_text('        DB '+','.join(f'${b:02X}' for a in p['write_blocks'] for b in int(a,16).to_bytes(2,'little'))+'\n')
 logs=[]
 for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
  assert cmd[0];r=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));(OUT/'build-log.json').write_text(json.dumps(logs,indent=2));assert not r.returncode,r.stdout+r.stderr
 sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)};m=cells(stage/'sram-bench.s19');b=bytearray(m[a] for a in range(0x200,sy['Q_END']));off=sy['Q_IMAGE_CRC']-0x200;b[off:off+2]=binascii.crc_hqx(b[:off],65535).to_bytes(2,'big');assert binascii.crc_hqx(b,65535)==0
 (OUT/'AS1-SPI-RESTORER.bin').write_bytes(b);record=dict(bytes=len(b),sha256=sha(b),write_blocks=p['write_blocks'],plan_sha256=sha((SCOPE/'plan.json').read_bytes()),provider_sha256=sha(provider),F_sha256=sha(f),board_accessed=False,CPU_simulations=0,F_rebuilt=False)
 (OUT/'manifest.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))

if __name__=='__main__':run()
