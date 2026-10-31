"""Link the same STATUS source in owner RAM for a preserving hardware trial.

No simulator. The staged MON is the already-built RAM source, with only the
provider addresses relocated. It never dispatches a workbench/tool in this trial.
"""
import argparse,json,re,shutil,subprocess
from pathlib import Path
from build_status import build
from build_mona import cells,sha

def run(out,monitor):
    out=Path(out).resolve();monitor=Path(monitor).resolve()
    report=build(out,True)
    stage=out/'MON';shutil.copytree(monitor/'RAM',stage)
    shutil.copyfile(out/'status-core/status-interface.inc',stage/'status-interface.inc')
    path=stage/'status-mon.inc';body=path.read_text(encoding='utf-8')
    assert body.count('LDA #$AC')==1
    body=body.replace('LDA #$AC','LDA #$30')
    before='DB $40,$80,$C0,0,$40,$82,$C0,0,0,$AC,0,4,$50,$FA,$AA,5'
    after='DB 0,$20,$C0,0,$C0,$20,$C0,0,0,$30,0,4,0,$34,$AA,5'
    assert body.count(before)==1;body=body.replace(before,after)
    path.write_text(body,encoding='utf-8',newline='\n')
    logs=[]
    for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W','mona.asm'],
                    [shutil.which('wdcln'),'-g','-s','-t','-c0200','-hm19','-j','-o','mona.s19','mona.obj']):
        r=subprocess.run(command,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        (out/'MON-build-log.json').write_text(json.dumps(logs,indent=2)+'\n')
        if r.returncode:raise RuntimeError('RAM MON failed; see MON-build-log.json')
    memory=cells(stage/'mona.s19');image=bytearray(b'\xff'*(0x39AA-0x0200))
    assert max(memory)<0x2000 and min(memory)==0x0200
    for a,b in memory.items():image[a-0x0200]=b
    for name,artifact in report['artifacts'].items():
        a=int(artifact['address'],16);b=(out/name).read_bytes()
        assert set(image[a-0x0200:a-0x0200+len(b)])=={255}
        image[a-0x0200:a-0x0200+len(b)]=b
    name='STR8N-STATUS-RAM-TRIAL.bin';(out/name).write_bytes(image)
    report.update(payload=dict(file=name,bytes=len(image),sha256=sha(image),load='0200-39A9'),
                  monitor_build=str(monitor),monitor_manifest_sha256=sha((monitor/'manifest.json').read_bytes()),
                  hardware_test_commands=['VERSION','TIME','EDU OFF','VERSION','EDU ON','VERSION','Q'],
                  restore='Fresh 0200-66FF owner RAM and 0000-00DF ZP before releasing port')
    (out/'RAM-trial-manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(name,len(image),sha(image))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--monitor',required=True);a=p.parse_args();run(a.out,a.monitor)
