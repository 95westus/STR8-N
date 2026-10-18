"""RAM-only CPU/ABI observer with serial output; no host memory readbacks."""
import hashlib,json,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tmp/rc1mode1';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    assert not OUT.exists();OUT.mkdir();s=OUT/'s';s.mkdir();source=(ROOT/'tools/qualification/bf1_cpu_mode_probe.asm').read_text()
    code='''        LDX #0
PRINT:  LDA $2440,X
        PHX
        JSR $7E7C
        LDA #$20
        JSR $7E6D
        PLX
        INX
        CPX #14
        BNE PRINT
        JSR $7E7F
        JMP $7E67'''
    assert source.count('        JMP $7E67')==1;source=source.replace('        JMP $7E67',code);(s/'mode.asm').write_text(source)
    for cmd in [[shutil.which('wdc02as'),'-G','-L','-S','-W','mode.asm'],[shutil.which('wdcln'),'-g','-s','-t','-c2000','-hm19','-j','-o','mode.s19','mode.obj']]:
        result=subprocess.run(cmd,cwd=s,capture_output=True,text=True);assert result.returncode==0,(result.stdout,result.stderr)
    cells={}
    for line in (s/'mode.s19').read_text().splitlines():
        raw=bytes.fromhex(line[2:]);assert len(raw)==raw[0]+1 and sum(raw)&255==255
        if line[1]=='1':cells.update(dict(enumerate(raw[3:-1],int.from_bytes(raw[1:3],'big'))))
    assert set(cells)==set(range(0x2000,max(cells)+1)) and max(cells)<0x2100
    sys_path=ROOT/'output/qualification/rc1-2604-2609-hardware-2026-10-18-r1/extracted/str8n-2.0rc1/migration'
    import sys;sys.path.insert(0,str(sys_path));import legacy_transport as wire
    data=wire.s19(cells,0x2000);(OUT/'mode.s19').write_bytes(data);(OUT/'mode.bin').write_bytes(bytes(cells[x] for x in sorted(cells)))
    (OUT/'report.json').write_text(json.dumps(dict(passed=True,s19_sha256=sha(data),entry=0x2000,bytes=len(cells),temporary_RAM_only=True,never_enters_native_mode=True,no_persistent_writes=True,result_via_console=True),indent=2)+'\n')
    print('PASS console-only E=1 observation helper:',len(cells),'bytes; no memory dumps')
if __name__=='__main__':main()
