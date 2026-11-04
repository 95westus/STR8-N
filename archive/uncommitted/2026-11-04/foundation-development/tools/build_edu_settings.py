"""Build the read-only EDU metadata helper for ROM padding and a RAM trial."""
import argparse,binascii,json,re,shutil,subprocess
from pathlib import Path
from build_mona import ROOT,cells,equs,sha
from mona_branches import conservative_branches


def build(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh build directory required')
    freeze=json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(sha((ROOT/p).read_bytes())==v for p,v in freeze['sources'].items())
    boot=equs(ROOT/'src/core/boot-symbols.inc');eq=equs(ROOT/'src/include/str8n-v2-eq.inc')
    out.mkdir(parents=True);source=ROOT/'monitors/native/edu-settings.asm';logs=[];artifacts={};symbols={}
    text,branches=conservative_branches(source.read_text(),'EC_LONG_')
    for name,origin,base in (('ROM',0x8E90,0x9C),('RAM',0x7290,0x50)):
        stage=out/name;stage.mkdir();(stage/'edu-settings.asm').write_text(text)
        bindings=dict(EC_SOURCE_PAGE=base,EC_SOURCE_END_PAGE=base+4,EC_CRC_INIT=boot['J_CRC_INIT'],
                      EC_CRC_BYTE=boot['J_CRC_BYTE'],EC_CRC_LOW=eq['J_CRC'])
        (stage/'edu-settings-bindings.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in bindings.items()))
        for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W','edu-settings.asm'],
                        [shutil.which('wdcln'),'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o','edu-settings.s19','edu-settings.obj']):
            assert command[0];p=subprocess.run(command,cwd=stage,capture_output=True,text=True)
            logs.append(dict(variant=name,command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
            if p.returncode:raise RuntimeError('EDU helper failed; inspect build-log.json')
        sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(stage/'edu-settings.map').read_text(),re.M)}
        memory=cells(stage/'edu-settings.s19');body=bytes(memory[a] for a in range(origin,sy['EC_END']))
        assert len(body)<=240,f'EDU helper needs{len(body)} bytes;240 available before shared help'
        filename='EDU-SETTINGS-'+name+'.bin';(out/filename).write_bytes(body)
        artifacts[filename]=dict(bytes=len(body),sha256=sha(body),origin=f'{origin:04X}',source_page=f'{base:02X}')
        symbols[name]=sy
    helptext=(b'VERSION TIME B0..3 D M/!M G L Q S19\r\n'
              b'M1-3 W APPS APP CLOCK FLASH MAINT\r\n'
              b'S/T/R EDU SRAM WORK BATCH\r\nB3:C/D/F protected\r\n\0')
    assert len(helptext)<=126
    (out/'MON-SHARED-HELP.bin').write_bytes(helptext)
    r=dict(status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED',F_rebuilt=False,F_sha256=freeze['sha256'],build_passes=1,
        CPU_simulations=0,flash_writes=0,artifacts=artifacts,help_bytes=len(helptext),
        planned_ROM='B3:8E90-8F7F helper;8F80-8FFD help; reseal native-loader image, not F',
        source_sha256={source.relative_to(ROOT).as_posix():sha(source.read_bytes())},branches=branches,
        record='ED/1: seqLE32@4; mode0/1@8; FF9-27; CRC28-29 LE; FF30; commit0@31',
        RAM_fixture='5000-53FF metadata; helper7290; result6700-6707; system ZP E0-E3; no I/O or NVM write')
    (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');(out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    print(json.dumps({'artifacts':artifacts,'help_bytes':len(helptext)},indent=2));return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out)
