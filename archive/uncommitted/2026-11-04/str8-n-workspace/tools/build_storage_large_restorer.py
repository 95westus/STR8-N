"""Build the exact slot4/9800-B7FF SPI restorer; no hardware access."""
import binascii,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from build_mona import cells,sha
from mona_branches import conservative_branches


def run():
    out=ROOT/'BUILD/storage-large-restorer-r1';out.mkdir(exist_ok=False);stage=out/'source';stage.mkdir()
    prior=ROOT/'BUILD/named-edu-restorer-r1/source'
    source=(prior/'sram-bench.asm').read_text()
    a=source.index('Q_PAYLOAD_WINDOW:');b=source.index('Q_WRITE:',a)
    source=source[:a]+'''Q_PAYLOAD_WINDOW:
        CMP #$98
        BCC Q_BAD_FRAME
        CMP #$B8
        BCS Q_BAD_FRAME
'''+source[b:]
    source,_=conservative_branches(source,'SLR_LONG_');(stage/'sram-bench.asm').write_text(source)
    for p in prior.glob('*.inc'):shutil.copyfile(p,stage/p.name)
    logs=[]
    for cmd in ([shutil.which('wdc02as'),'-G','-L','-S','-W','sram-bench.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','sram-bench.s19','sram-bench.obj']):
        p=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);logs.append(dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if p.returncode:raise RuntimeError('Inspect build-log.json')
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'sram-bench.map').read_text(),re.M)}
    m=cells(stage/'sram-bench.s19');body=bytearray(m[a] for a in range(0x200,sy['Q_END']));at=sy['Q_IMAGE_CRC']-0x200
    body[at:at+2]=binascii.crc_hqx(body[:at],65535).to_bytes(2,'big');assert binascii.crc_hqx(body,65535)==0
    (out/'STORAGE-LARGE-RESTORER.bin').write_bytes(body)
    r=dict(status='BUILT_NOT_EXECUTION_QUALIFIED',filename='STORAGE-LARGE-RESTORER.bin',sha256=sha(body),bytes=len(body),
        write_bank=0,write_blocks=['00140']+[f'{a:05X}' for a in range(0x9800,0xB800,64)],temporary_bytes=8256,
        flash_writes=0,WORKSPACE_writes=0,CPU_simulations=0,build_passes=1)
    (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='write_blocks'},indent=2))


if __name__=='__main__':run()
