"""One RAM-only helper: archive SRAM, retire only four CLK commit bytes."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha

def run():
 out=ROOT/'BUILD/2609-CLK-retirement-r1';out.mkdir();stage=out/'source';stage.mkdir()
 old=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source'
 source=(old/'sram-bench.asm').read_text()
 needle='Q_WRITE:\n        JSR Q_SET_TRANSFER\n        LDA #2\n'
 assert source.count(needle)==1
 source=source.replace(needle,'''Q_WRITE:
        ; Only invalidate the named slot's commit; other63 bytes never written.
        LDA $303F
        BEQ CLK_COMMIT_ZERO
        JMP Q_BAD_FRAME
CLK_COMMIT_ZERO:
        JSR Q_SET_TRANSFER
        LDA Q_ADDR
        ORA #$3F
        STA SP_A0
        LDA #$3F
        STA SP_PTR
        LDA #1
        STA SP_COUNT
        LDA #2
''')
 (stage/'sram-bench.asm').write_text(source)
 for name in ('str8n-v2-public.inc','workbench-layout.inc','workbench-interface.inc','program-layout.inc'):
  shutil.copyfile(old/name,stage/name)
 provider=(ROOT/'BUILD/program-sp1-g3-store-r2/STR8N-PROGRAM-SP1-6B00.bin').read_bytes()
 assert sha(provider)=='8128b9c542ecdc335d400465ed9a3cb8f3a1fbfce6ed37a507ddfe1bafc4f667'
 assert binascii.crc_hqx(provider,65535)==0
 sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(ROOT/'BUILD/program-sp1-g3-store-r2/staging/program-provider.map').read_text(),re.M)}
 f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert sha(f)==json.loads((REPO/'F_FREEZE.json').read_text())['sha256'];crc=binascii.crc_hqx(f,65535)
 values=dict(BENCH_F_LO=crc&255,BENCH_F_HI=crc>>8,BENCH_PV_HI=provider[-2],BENCH_PV_LO=provider[-1],BENCH_TRANSFER=sy['SP_TRANSFER'],BENCH_LIMIT=0,BENCH_ALLOW_BYTES=8)
 (stage/'sram-bench-params.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n,v in values.items()))
 (stage/'sram-bench-allow.inc').write_text('        DB $40,$01,$80,$01,$C0,$01,$00,$02\n')
 logs=[]
 for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
  assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(out/'build-log.json').write_text(json.dumps(logs,indent=2));assert p.returncode==0,p.stdout+p.stderr
 sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
 memory=cells(stage/'sram-bench.s19');body=bytearray(memory[a] for a in range(0x200,sy['Q_END']));at=sy['Q_IMAGE_CRC']-0x200;body[at:at+2]=binascii.crc_hqx(body[:at],65535).to_bytes(2,'big');assert binascii.crc_hqx(body,65535)==0
 (out/'CLK-RETIRE-RAM.bin').write_bytes(body)
 record=dict(sha256=sha(body),bytes=len(body),firmware_builds=0,RAM_helper_builds=1,CPU_simulations=0,allowed_write_addresses=['0017F','001BF','001FF','0023F'],allowed_write_value=0,transfer=sy.get('BENCH_TRANSFER',0x75d4),provider_sha256=sha(provider),F_sha256=sha(f))
 (out/'manifest.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))

if __name__=='__main__':run()
