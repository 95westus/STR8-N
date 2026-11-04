"""Build one bounded restorer for the approved320 PROGRAM bytes, not WORK."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches

def run():
    scope=ROOT/'output/qualification/NAMED-EDU-2512-scope-20261101-r1'
    a=json.loads((scope/'approval.json').read_text());assert a['approved'] and a['total_erases']==12
    assert a['plan_sha256']==sha((scope/'plan.json').read_bytes())
    out=ROOT/'BUILD/named-edu-restorer-r1';out.mkdir(exist_ok=False);stage=out/'source';stage.mkdir()
    original=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source/sram-bench.asm'
    source=original.read_text();start=source.index('        LDY #0\nQ_ALLOWED:');end=source.index('Q_WRITE:\n',start)
    guard='''        LDA Q_ADDR
        AND #$3F
        BNE Q_BAD_FRAME
        LDA Q_ADDR+1
        CMP #1
        BNE Q_PAYLOAD_WINDOW
        LDA Q_ADDR
        CMP #$40
        BEQ Q_WRITE
        JMP Q_BAD_FRAME
Q_PAYLOAD_WINDOW:
        CMP #8
        BNE Q_BAD_FRAME
'''
    source=source[:start]+guard+source[end:];source,_=conservative_branches(source,'NE_RESTORE_LONG_')
    (stage/'sram-bench.asm').write_text(source)
    for n,f in [('str8n-v2-public.inc','src/include'),('workbench-layout.inc','monitors/src'),('workbench-interface.inc','monitors/src'),('batch-interface.inc','monitors/src'),('program-layout.inc','monitors/src')]:shutil.copyfile(REPO/f/n,stage/n)
    prior=ROOT/'BUILD/transfer-restorer-r1/source'
    for n in ('sram-bench-params.inc','sram-bench-allow.inc'):shutil.copyfile(prior/n,stage/n)
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
        p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));(out/'build-log.json').write_text(json.dumps(logs,indent=2))
        assert p.returncode==0
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
    m=cells(stage/'sram-bench.s19');body=bytearray(m[i] for i in range(0x200,sy['Q_END']));at=sy['Q_IMAGE_CRC']-0x200
    body[at:at+2]=binascii.crc_hqx(body[:at],65535).to_bytes(2,'big');assert binascii.crc_hqx(body,65535)==0
    (out/'NAMED-EDU-SPI-RESTORER.bin').write_bytes(body)
    report=dict(filename='NAMED-EDU-SPI-RESTORER.bin',sha256=sha(body),bytes=len(body),allowed_write_blocks=['00140','00800','00840','00880','008C0'],temporary_bytes=320,WORKSPACE_writes=0,flash_writes=0,build_passes=1,CPU_simulations=0)
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':run()
