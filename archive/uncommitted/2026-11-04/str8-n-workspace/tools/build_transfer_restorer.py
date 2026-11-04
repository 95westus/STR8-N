"""Build one private RAM SPI restorer for the exact approved8256-byte window."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches


def run():
    scope=ROOT/'output/qualification/TRANSFER-scope-20261101-r2'
    approval=json.loads((scope/'approval.json').read_text());assert approval['approved']
    assert approval['review_sha256']==sha((scope/'review.json').read_bytes())
    out=ROOT/'BUILD/transfer-restorer-r1';out.mkdir(exist_ok=False);stage=out/'source';stage.mkdir()
    sourcefile=ROOT/'output/qualification/2609-PROGRAM-positive-scope-20261030-r1/source/sram-bench.asm'
    source=sourcefile.read_text()
    start=source.index('        LDY #0\nQ_ALLOWED:');end=source.index('Q_WRITE:\n',start)
    # Block-aligned exact directory slot or payload window. Bank0 is checked
    # immediately before this guard in the preserved helper.
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
        CMP #$98
        BCC Q_BAD_FRAME
        CMP #$B8
        BCS Q_BAD_FRAME
'''
    source=source[:start]+guard+source[end:]
    source,_=conservative_branches(source,'TR_LONG_')
    (stage/'sram-bench.asm').write_text(source)
    for name,folder in [('str8n-v2-public.inc','src/include'),('workbench-layout.inc','monitors/src'),
                        ('workbench-interface.inc','monitors/src'),('batch-interface.inc','monitors/src'),('program-layout.inc','monitors/src')]:
        shutil.copyfile(REPO/folder/name,stage/name)
    build=ROOT/'BUILD/program-sp1-g3-store-r2';manifest=json.loads((build/'manifest.json').read_text())
    provider=(build/manifest['artifact']['filename']).read_bytes();assert sha(provider)==manifest['artifact']['sha256']
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(build/'staging/program-provider.map').read_text(),re.M)}
    f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert sha(f)==json.loads((REPO/'F_FREEZE.json').read_text())['sha256']
    crc=binascii.crc_hqx(f,65535)
    values=dict(BENCH_F_LO=crc&255,BENCH_F_HI=crc>>8,BENCH_PV_HI=provider[-2],BENCH_PV_LO=provider[-1],
        BENCH_TRANSFER=symbols['SP_TRANSFER'],BENCH_LIMIT=0,BENCH_ALLOW_BYTES=0)
    (stage/'sram-bench-params.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in values.items()))
    (stage/'sram-bench-allow.inc').write_text('        DB 0\n')
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],
                [shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
        assert cmd[0];p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:raise RuntimeError('Restorer build failed; inspect build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
    memory=cells(stage/'sram-bench.s19');body=bytearray(memory[a] for a in range(0x200,sy['Q_END']))
    pos=sy['Q_IMAGE_CRC']-0x200;body[pos:pos+2]=binascii.crc_hqx(body[:pos],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(body,65535)==0 and len(body)<0x1000
    name='TRANSFER-SPI-RESTORER-RAM.bin';(out/name).write_bytes(body)
    m=dict(filename=name,bytes=len(body),sha256=sha(body),provider_sha256=sha(provider),F_sha256=sha(f),
        allowed_write_blocks=['00140']+[f'{a:05X}' for a in range(0x9800,0xB800,64)],
        temporary_bytes=8256,WORKSPACE_writes=False,flash_writes=False,mode_register_writes=False,
        build_passes=1,CPU_simulations=0,review_sha256=approval['review_sha256'],source_original_sha256=sha(sourcefile.read_bytes()))
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('Built exact8256-byte SPI restoration guard;',len(body),'RAM code bytes')

if __name__=='__main__':run()
