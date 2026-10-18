"""Clean extraction and real platform-launcher checks for offline bf1 review kits.

Uses private fixtures only outside extracted archives. Never opens serial ports.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import traceback
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification'
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packages',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--linux-distro');a=p.parse_args()
    if a.out.exists():raise ValueError('Retain earlier receipt')
    packages=json.loads((a.packages/'packages.json').read_text(encoding='utf-8'))
    checks=[];commands=[]
    def passed(name,**details):checks.append(dict(name=name,passed=True,**details))
    def require(value,message):
        if not value:raise ValueError(message)
    def capture(folder,banks):
        folder.mkdir();files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(folder/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=sha(body))
        (folder/'capture.json').write_text(json.dumps(dict(schema=1,board='local-fixture',repeat_verified=True,files=files)),encoding='utf-8')
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='bf1 extracted review ') as temporary:
            temp=Path(temporary).resolve();require(temp.is_relative_to((ROOT/'tmp').resolve()),'Unexpected temporary root')
            prior=Q/'bf1-2512-legacy-offline-2026-10-17-r6/v2-0b4-convert'
            source=[(prior/f'source-b{n}.bin').read_bytes() for n in range(4)]
            cap=temp/'source capture';capture(cap,source)
            escrow=temp/'metadata escrow.bin';escrow.write_bytes((Q/'bf1-2512-pre-migration-backup-2026-10-17-r2/b3.bin').read_bytes()[0x1c00:0x2000])
            original_plan=json.loads((prior/'plan.json').read_text(encoding='utf-8'))
            env=dict(os.environ,STR8N_PYTHON=sys.executable.replace('\\','/'),PYTHONPATH='',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
            roots={};firmware={}
            for platform,info in packages['packages'].items():
                path=a.packages/info['filename'];require(sha(path.read_bytes())==info['sha256'],'Changed archive')
                dest=temp/platform;dest.mkdir()
                if platform=='windows':
                    with zipfile.ZipFile(path) as archive:
                        names=archive.namelist();require(len(names)==len(set(names)),'Duplicate ZIP member')
                        for name in names:require((dest/name).resolve().is_relative_to(dest),'ZIP path escapes')
                        archive.extractall(dest)
                else:
                    with tarfile.open(path) as archive:
                        members=archive.getmembers();names=[v.name for v in members];require(len(names)==len(set(names)),'Duplicate tar member')
                        for member in members:
                            require(member.isfile() and (dest/member.name).resolve().is_relative_to(dest),'Unsafe tar member')
                            if member.name.endswith('.sh'):require(member.mode==0o755,'Linux wrapper lacks executable mode')
                        archive.extractall(dest,filter='data')
                roots[platform]=next(dest.iterdir());root=roots[platform]
                manifest=json.loads((root/'package-manifest.json').read_text(encoding='utf-8'))
                require(manifest['review_only'] and not manifest['distribution_qualified'] and not manifest['live_installation_enabled'],'Review gates missing')
                for name,expected in manifest['files'].items():
                    data=(root/name).read_bytes();require(len(data)==expected['bytes'] and sha(data)==expected['sha256'],'Changed extracted member: '+name)
                    require(expected['category'] in {'manual','uchess-source-or-license','firmware','required-tool-source','required-component','required-ram-installer-template','required-tool-manifest','platform-launcher','license-or-package-guide'},'Unknown file category')
                actual={v.relative_to(root).as_posix() for v in root.rglob('*') if v.is_file()}
                require(actual==set(manifest['files'])|{'package-manifest.json','SHA256SUMS'},'Unlisted archive file')
                for row in (root/'SHA256SUMS').read_text(encoding='ascii').splitlines():
                    digest,name=row.split('  ',1);require(sha((root/name).read_bytes())==digest,'Checksum mismatch')
                for name in actual:
                    if name.endswith('.md'):
                        text=(root/name).read_text(encoding='utf-8')
                        for link in re.findall(r'\]\(([^)]+)\)',text):
                            if re.match(r'[a-z]+:',link):continue
                            target=((root/name).parent/link.split('#')[0]).resolve();require(target.is_relative_to(root) and target.is_file(),'Broken extracted manual link: '+name+' '+link)
                    require('beta4-bridge' not in name.lower() and Path(name).name.lower() not in ('serial.jsonl','eeprom.bin','sram.bin','b0.bin','b1.bin','b2.bin','b3.bin'),'Forbidden capture/vendor name')
                s19={v for v in actual if v.endswith('.s19')}
                allowed={'migration/template/integrated-template.s19','migration/factory-template/bootstrap-template.s19'}
                require('migration/template/integrated-template.s19' in s19 and s19<=allowed,'Unneeded S19 payload')
                require(len(list((root/'docs').glob('*.md')))==14,'Expected 14 manuals/quickstarts')
                require((root/'uchess-source/LICENSE.txt').read_bytes()==(ROOT/'BUILD/microchess-asm04/LICENSE.txt').read_bytes(),'uChess license differs')
                firmware[platform]=next((root/'firmware').glob('*.bin')).read_bytes()
                passed(platform+' safe extraction, complete allowlist/checksums, 14 manual links, minimal S19 and exact license',files=len(actual))
            require(firmware['windows']==firmware['linux'] and len(firmware['windows'])==98304,'Platform firmware differs')
            passed('identical 96KiB application firmware for both host packages',sha256=sha(firmware['windows']))
            bash=Path('C:/Program Files/Git/bin/bash.exe')
            def linux_path(value):
                path=Path(value).resolve();require(path.drive.upper()=='C:','Only known workspace mount is admitted')
                return '/mnt/c/'+path.as_posix()[3:]
            def run(platform,launcher,args):
                root=roots[platform]
                if platform=='windows':
                    quoted=' '.join('"'+str(v).replace('"','')+'"' for v in args)
                    command='"'+os.environ.get('COMSPEC','C:/Windows/System32/cmd.exe')+'" /d /s /c ""'+str(root/(launcher+'.cmd'))+'" '+quoted+'"'
                elif a.linux_distro:
                    command=['wsl.exe','-d',a.linux_distro,'--exec','/usr/bin/env','STR8N_PYTHON=/usr/bin/python3',
                             'PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',linux_path(root/(launcher+'.sh')),
                             *[linux_path(v) if isinstance(v,Path) else str(v) for v in args]]
                else:
                    require(bash.is_file(),'POSIX compatibility shell unavailable')
                    command=[str(bash),(root/(launcher+'.sh')).as_posix(),*map(str,args)]
                result=subprocess.run(command,cwd=temp,env=env,capture_output=True,text=True,timeout=60)
                commands.append(dict(platform=platform,launcher=launcher,arguments=list(map(str,args)),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
                return result
            for platform in ('windows','linux'):
                result=run(platform,'bf1',['verify']);require(result.returncode==0 and 'no serial port opened' in result.stdout,'verify launcher failed: '+result.stderr)
                status=run(platform,'bf1',['status']);require(status.returncode==0 and json.loads(status.stdout)['live_installation_enabled'] is False,'status launcher failed')
                passed(platform+' extracted verify/status real launcher with spaces in path',host=('Windows cmd' if platform=='windows' else ('Linux WSL '+a.linux_distro if a.linux_distro else 'Git Bash POSIX compatibility on Windows')))
                out=temp/(platform+' forward plan');result=run(platform,'beta4-to-bf1',['--capture',cap,'--out',out,'--metadata-escrow',escrow]);require(result.returncode==0,'beta4 launcher failed: '+result.stderr)
                plan=json.loads((out/'plan.json').read_text(encoding='utf-8'));require(plan['expected_sha256']==original_plan['expected_sha256'],'Extracted plan changed expected target')
                require((out/'installer-model-only.s19').read_bytes()==(prior/'installer-model-only.s19').read_bytes(),'Extracted installer differs from qualified one')
                current=temp/(platform+' current capture');capture(current,[(out/f'expected-b{n}.bin').read_bytes() for n in range(4)])
                recovered=temp/(platform+' no-write recovery');result=run(platform,'bf1-recovery',['forward','--plan',out,'--capture',current,'--out',recovered]);require(result.returncode==0,'Recovery launcher failed: '+result.stderr)
                require(json.loads((recovered/'plan.json').read_text(encoding='utf-8'))['write_required'] is False,'Completed target recovery not write-free')
                passed(platform+' beta4/recovery launchers prepare exact qualified bytes and no-write receipt from clean extraction')
                result=run(platform,'bf1',['verify-plan','--plan',out]);require(result.returncode==0 and 'PASS bound offline plan' in result.stdout,'Extracted beta4 plan verification failed: '+result.stderr)
                passed(platform+' verify-plan re-derives beta4 input binding from actual wrapper')
                original_wdc=Q/'bf1-2609-windows-offline-2026-10-18-r1'
                wdc_out=temp/(platform+' direct WDC plan')
                result=run(platform,'wdcmonv2-to-bf1',['--capture',original_wdc/'model-only-WDC-capture',
                    '--out',wdc_out,'--history',original_wdc/'tracked-history.json',
                    '--metadata-escrow',original_wdc/'private-metadata-escrow.bin'])
                require(result.returncode==0,'Extracted direct WDC preparation failed: '+result.stderr)
                require((wdc_out/'installer-model-only.s19').read_bytes()==(original_wdc/'original-816-to-bf1/installer-model-only.s19').read_bytes(),'Extracted factory installer differs from exact CPU-qualified bytes')
                result=run(platform,'bf1',['verify-plan','--plan',wdc_out]);require(result.returncode==0 and 'PASS bound offline plan' in result.stdout,'Extracted WDC plan verification failed: '+result.stderr)
                passed(platform+' direct WDC wrapper prepares exact prior CPU-executed installer and validates all bindings',fresh_CPU_execution=False)
                altered=json.loads((wdc_out/'plan.json').read_text());altered['source_cpu']='65C02'
                (wdc_out/'plan.json').write_text(json.dumps(altered))
                result=run(platform,'bf1',['verify-plan','--plan',wdc_out]);require(result.returncode!=0 and 'CPU/profile mismatch' in result.stderr,'Extracted changed CPU entry accepted')
                passed(platform+' changed WDC CPU/profile is refused by actual wrapper before port access')
                for operation in ('capture','install'):
                    result=run(platform,'bf1',[operation,'--port','MUST-NOT-OPEN','--board','fixture']);require(result.returncode!=0 and 'No port was opened' in result.stderr,'Unqualified live operation was not refused')
                passed(platform+' unqualified capture/install refused before serial import/open')
                result=run(platform,'bf1',['beta4','--capture',temp/'nonexistent','--out',temp/'must-not-exist']);require(result.returncode!=0,'Missing capture accepted')
                passed(platform+' wrapper propagates preparation failure exit code')
    except Exception:
        a.out.write_text(json.dumps(dict(passed=False,checks=checks,commands=commands,error=traceback.format_exc(),board_access=False),indent=2)+'\n',encoding='utf-8')
        raise
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,commands=commands,packages=packages['packages'],
        native_Windows_launcher_tested=True,POSIX_shell_compatibility_tested_on_Windows=not bool(a.linux_distro),native_Linux_tested=bool(a.linux_distro),Linux_distribution=a.linux_distro,
        Linux_hardware_or_serial_qualified=False,board_access=False,publication_permitted=False,distribution_qualified=False,
        scope='Clean extraction and actual offline wrappers, allowlist/checksums/docs/licenses, qualified beta4 installer byte equivalence, no-write recovery and live-operation refusal; not live migration qualification.'),indent=2)+'\n',encoding='utf-8')
    print('PASS',len(checks),'extracted review-package checks; native Linux/live migration qualification remains pending')


if __name__=='__main__':main()
