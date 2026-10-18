"""Clean Windows cmd/Linux WSL extraction and admitted candidate workflow tests; no ports."""
import argparse,hashlib,json,os,re,subprocess,sys,tarfile,traceback,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--packages',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--linux-distro',default='Ubuntu-24.04');a=p.parse_args();assert not a.out.exists()
    info=json.loads((a.packages/'packages.json').read_text());checks=[];commands=[]
    work=a.out.with_suffix('');assert not work.exists();work.mkdir();work=work.resolve();roots={};images=[]
    def passed(name):checks.append(dict(name=name,passed=True))
    def linux(v):
        p=Path(v).resolve();assert p.drive.upper()=='C:';return '/mnt/c/'+p.as_posix()[3:]
    env=dict(os.environ,STR8N_PYTHON=sys.executable,PYTHONUTF8='1',PYTHONPATH='',PYTHONDONTWRITEBYTECODE='1')
    def run(platform,args):
        if platform=='windows':
            quote=' '.join('"'+str(v)+'"' for v in args);command='"'+os.environ['COMSPEC']+'" /d /s /c ""'+str(roots[platform]/'bf1.cmd')+'" '+quote+'"'
        else:command=['wsl.exe','-d',a.linux_distro,'--exec','/usr/bin/env','STR8N_PYTHON=/usr/bin/python3','PYTHONDONTWRITEBYTECODE=1',linux(roots[platform]/'bf1.sh'),*[linux(v) if isinstance(v,Path) else str(v) for v in args]]
        result=subprocess.run(command,cwd=work,env=env,capture_output=True,text=True,timeout=90);commands.append(dict(platform=platform,arguments=list(map(str,args)),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));return result
    try:
        for platform,receipt in info['packages'].items():
            path=a.packages/receipt['filename'];assert sha(path.read_bytes())==receipt['sha256'];dest=work/platform;dest.mkdir()
            if platform=='windows':
                with zipfile.ZipFile(path) as archive:
                    names=archive.namelist();assert len(set(names))==len(names) and all((dest/n).resolve().is_relative_to(dest) for n in names);archive.extractall(dest)
            else:
                with tarfile.open(path) as archive:
                    members=archive.getmembers();assert all(m.isfile() and (dest/m.name).resolve().is_relative_to(dest) for m in members);archive.extractall(dest,filter='data')
                zipped=a.packages/receipt['zip']['filename'];assert sha(zipped.read_bytes())==receipt['zip']['sha256']
                with zipfile.ZipFile(zipped) as archive:
                    assert {n:archive.read(n) for n in archive.namelist()}=={m.name:(dest/m.name).read_bytes() for m in members}
            root=next(dest.iterdir());roots[platform]=root;manifest=json.loads((root/'package-manifest.json').read_text());assert manifest['live_installation_enabled'] and not manifest['distribution_qualified']
            actual={v.relative_to(root).as_posix() for v in root.rglob('*') if v.is_file()};assert actual==set(manifest['files'])|{'package-manifest.json','SHA256SUMS'}
            for name,entry in manifest['files'].items():
                body=(root/name).read_bytes();assert len(body)==entry['bytes'] and sha(body)==entry['sha256']
                assert Path(name).name.lower() not in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl')
                if name.endswith(('.md','.py','.json')):assert not re.search(r'C:[\\/](?:SRC|Users)[\\/]|output[\\/]qualification',body.decode(),re.I)
                if name.endswith('.md'):
                    for target in re.findall(r'\]\(([^)]+)\)',body.decode()):
                        if re.match('[a-z]+:',target):continue
                        path=((root/name).parent/target.split('#')[0]).resolve();assert path.is_relative_to(root) and path.is_file(),(name,target)
            for row in (root/'SHA256SUMS').read_text().splitlines():
                digest,name=row.split('  ',1);assert sha((root/name).read_bytes())==digest
            assert len(list((root/'docs').glob('*.md')))==14
            assert (root/'uchess-source/LICENSE.txt').read_bytes()==(ROOT/'BUILD/microchess-asm04/LICENSE.txt').read_bytes()
            full=next((root/'firmware').glob('*apps-str8n-only.bin')).read_bytes();fixed=(root/'firmware/str8n-2.0bf1-b3-f000-ffff.bin').read_bytes()
            assert len(fixed)==4096 and fixed==full[0x17000:0x18000] and int.from_bytes(fixed[-4:-2],'little')==0xf004
            assert len(list((root/'docs/diagrams').glob('*.svg')))==3
            images.append(full);passed(platform+' safe extraction, exact allowlist/checksums, B3-only F component, 14 manuals/three rendered diagrams and full uChess license')
        assert images[0]==images[1] and len(images[0])==98304 and sha(images[0])=='f20b53793563acd5685cca1ed987f67118f7340fa8f1551955b135830f5e672a';passed('identical STR8-N-only all-apps firmware; no source/bridge/vendor image')
        for platform in roots:
            result=run(platform,['verify']);assert result.returncode==0 and 'enabled for admitted empty-bank' in result.stdout,result.stderr
            result=run(platform,['status']);assert result.returncode==0 and json.loads(result.stdout)['live_installation_enabled'];passed(platform+' actual launcher verify/status')
            for command in ('beta4','wdcmonv2'):
                out=work/(platform+' '+command+' private plan');source=Q/'bf1-public-empty-bank-models-2026-10-18-r1'/('2609-source' if command=='wdcmonv2' else '2604-source')
                args=[command,'--capture',source,'--out',out]+(['--accept-unknown-wear-history'] if command=='wdcmonv2' else [])
                result=run(platform,args);assert result.returncode==0,result.stderr
                reference=Q/'bf1-public-empty-bank-models-2026-10-18-r1'/('2609-WDC-to-full-bf1' if command=='wdcmonv2' else '2604-beta4-to-full-bf1')
                assert (out/'installer-model-only.s19').read_bytes()==(reference/'installer-model-only.s19').read_bytes()
                result=run(platform,['verify-plan','--plan',out]);assert result.returncode==0,result.stderr;passed(platform+' '+command+' exact fresh CPU-qualified full installer and plan verification')
            result=run(platform,['capture','--port','MUST-NOT-OPEN','--board','fixture','--out',work/(platform+' refused')]);assert result.returncode!=0 and 'USB serial required' in result.stderr,result.stderr
            result=run(platform,['beta4','--port','MUST-NOT-OPEN','--board','fixture','--out',work/(platform+' refused2'),'--empty-banks']);assert result.returncode!=0 and 'USB serial required' in result.stderr,result.stderr;passed(platform+' enabled capture/install refuse missing USB identity before serial import')
            test=ROOT/'tools/test_bf1_candidate_workflow.py';receipt=work/(platform+' workflow.json');fixtures=Q/'bf1-empty-bank-tests-2026-10-18-r1'
            if platform=='windows':cmd=[sys.executable,str(test),'--kit',str(roots[platform]/'migration'),'--fixtures',str(fixtures),'--out',str(receipt)]
            else:cmd=['wsl.exe','-d',a.linux_distro,'--exec','/usr/bin/python3',linux(test),'--kit',linux(roots[platform]/'migration'),'--fixtures',linux(fixtures),'--out',linux(receipt)]
            result=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True,timeout=90);commands.append(dict(platform=platform,test='full workflow simulated endpoints',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));assert result.returncode==0,result.stderr;assert json.loads(receipt.read_text())['passed'];passed(platform+' clean extracted actual full install and original-RAM recovery workflows with simulated serial endpoints')
    except BaseException:
        a.out.write_text(json.dumps(dict(passed=False,checks=checks,commands=commands,error=traceback.format_exc()),indent=2)+'\n');raise
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,commands=commands,packages=info['packages'],native_Windows_tested=True,native_Linux_WSL_tested=True,Linux_distribution=a.linux_distro,physical_serial_tested=False,publication_permitted=False),indent=2)+'\n');print('PASS',len(checks),'clean extracted Windows/Linux candidate checks')
if __name__=='__main__':main()
