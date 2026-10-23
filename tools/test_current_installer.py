"""Offline differential, simulated-link and linked-CPU installer regression suite."""
import argparse
import importlib.abc
from copy import deepcopy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from unittest.mock import patch
import zipfile

SERIAL_IMPORT_ATTEMPTS=[]
class NoSerial(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname=='serial' or fullname.startswith('serial.'):
            SERIAL_IMPORT_ATTEMPTS.append(fullname)
            raise AssertionError('Serial import prohibited during offline verification')
sys.meta_path.insert(0,NoSerial())

from installer import capture, cli, model, package, plan, workflow
from installer.common import REGISTRY, save
from installer.engine import runtime as r, legacy_transport as wire

ROOT=Path(__file__).resolve().parents[1]


def baseline_fixtures(out):
    """Load immutable generic images and Phase-4 historical transaction oracles.

    These files contain built project firmware and synthetic transaction metadata,
    never board captures. No historical builder, installer kit or BUILD tree is read.
    """
    fixtures=ROOT/'tests/fixtures';manifest=r.read(fixtures/'installer-fixtures.json')
    phase1_path=ROOT/'tests/baselines/phase1.json';phase4_path=ROOT/'tests/baselines/phase4.json'
    r.require(manifest['schema']==1 and manifest['board_access'] is False and
              manifest['private_board_captures'] is False,'Wrong fixture scope')
    r.require(r.sha(phase1_path.read_bytes())==manifest['phase1_manifest_sha256'],'Changed phase-1 fixture anchor')
    r.require(r.sha(phase4_path.read_bytes())==manifest['phase4_manifest_sha256'],'Changed phase-4 fixture anchor')
    phase1=r.read(phase1_path);phase4=r.read(phase4_path)
    entry=phase4['evidence']['differential'];evidence=ROOT/entry['file']
    r.require(r.sha(evidence.read_bytes())==entry['sha256'],'Changed phase-4 differential evidence')
    golden=r.read(evidence)
    archive=fixtures/manifest['archive']['file']
    r.require(r.sha(archive.read_bytes())==manifest['archive']['sha256'],'Changed profile fixture archive')
    r.require(set(manifest['profiles'])==set(REGISTRY['candidates'])-{'asm-dev'},'Wrong fixture profile inventory')
    images={};destination=out/'reference-images';destination.mkdir()
    with zipfile.ZipFile(archive) as source:
        r.require(set(source.namelist())=={row['file'] for row in manifest['profiles'].values()} and
                  len(source.infolist())==len(manifest['profiles']),'Wrong fixture archive inventory')
        for name,row in manifest['profiles'].items():
            r.require(row['file']==name+'.bin','Wrong fixture file identity')
            body=source.read(row['file']);expected=REGISTRY['candidates'][name]
            r.require(len(body)==row['bytes']==expected['bytes'] and
                      r.sha(body)==row['sha256']==expected['firmware_sha256']==
                      phase1['baselines'][row['phase1_baseline']]['existing_firmware_sha256'],
                      'Profile fixture differs from phase 1/registry: '+name)
            images[name]=destination/row['file'];images[name].write_bytes(body)
    transactions={}
    r.require(set(manifest['transactions'])=={'generic','cleanup'},'Wrong transaction fixture inventory')
    for name,row in manifest['transactions'].items():
        path=fixtures/row['file'];r.require(r.sha(path.read_bytes())==row['sha256'],'Changed transaction fixture: '+name)
        transaction=r.read(path);r.require('label' not in transaction and row['label_omitted'],'Unnormalized transaction fixture')
        r.require(transaction['source_sha256']==[golden[name]['device_artifacts'][f'source-b{n}.bin'] for n in range(4)] and
                  transaction['expected_sha256']==[golden[name]['device_artifacts'][f'expected-b{n}.bin'] for n in range(4)],
                  'Transaction fixture differs from phase-4 bank hashes: '+name)
        transactions[name]=transaction
    return images,golden,transactions


def compare_baseline(folder, golden, transaction, label):
    actual={p.name:r.sha(p.read_bytes()) for p in folder.iterdir()
            if p.is_file() and p.suffix in ('.bin','.s19')}
    r.require(actual==golden['device_artifacts'],'Flashing artifacts differ from phase 4: '+label)
    current=r.read(folder/'plan.json')['transaction']
    r.require({k:v for k,v in current.items() if k!='label'}==transaction,'Transaction differs from phase 4: '+label)


class Link:
    """In-memory monitor; no serial object, port discovery or external I/O."""
    def __init__(self, board, banks, ram, *, edu=False):
        self.profile=REGISTRY['boards'][board];self.banks=list(map(bytearray,banks));self.bank=3
        self.ram=bytearray(32768);self.ram[0x200:0x200+len(ram)]=ram
        self.ram[0x7D0A:0x7D0C]=(0x64FF if edu else 0x66FF).to_bytes(2,'little')
        self.ram[0x7D30]=r.latest(banks)[2][16]
        self.commands=[];self.sends=[];self.loading=False;self.loaded=[];self.ram_loads=0
        self.repeat_mismatch=False;self.cycles=0;self.corrupt_target=False;self.corrupt_restore=False
        self.bad_cpu=False;self.bad_slot=False;self.pending_reset=False
        self.changed_monitor=False
        self.repeat_ram_mismatch=False;self.ram_reads=0

    def command(self, text, prompt=b'\r\nB3> '):
        self.commands.append(text)
        if text.startswith('B') and len(text)==2:
            self.bank=int(text[1]);self.cycles+=int(self.bank==0)
        if text=='VERSION':
            cpu='WRONG' if self.bad_cpu else self.profile['cpu']
            a='00000031' if self.bad_slot else '00000032'
            return (f"STR8-N 2.0rc1 {cpu}\r\nBoard: {self.profile['board']}\r\n"
                    f'MONITOR A gen {a} VALID\r\nMONITOR B gen 00000032 VALID\r\nB3> ').encode()
        if text=='L':self.loading=True;self.loaded=[];return b'S19'
        return prompt

    def dump(self, first, last, prompt=b'\r\nB3> '):
        if first>=0x8000:
            data=bytes(self.banks[self.bank][first-0x8000:last-0x8000+1])
            if self.repeat_mismatch and self.cycles>=2 and self.bank==0 and first==0x8000:
                data=bytes([data[0]^1])+data[1:]
            return data
        data=bytes(self.ram[first:last+1])
        if first==0x200:
            self.ram_reads+=1
            if self.repeat_ram_mismatch and self.ram_reads>=2:data=bytes([data[0]^1])+data[1:]
        return data

    def send(self, data):
        self.sends.append(data)
        assert self.loading, 'Unexpected programming stream in host workflow test'
        self.loaded.append(data.decode().strip())

    def until(self, token, seconds=45):
        if self.loading:
            entry=None
            for line in self.loaded:
                raw=bytes.fromhex(line[2:]);address=int.from_bytes(raw[1:3],'big')
                if line.startswith('S1'):self.ram[address:address+len(raw)-4]=raw[3:-1]
                elif line.startswith('S9'):entry=address
            self.loading=False;self.ram_loads+=1
            if self.corrupt_restore:self.ram[0x201]^=1
            return f'Entry {entry:04X}\r\nB3> '.encode()
        assert self.pending_reset, 'Unexpected wait outside simulated reset'
        self.pending_reset=False
        if self.corrupt_target:self.banks[1][0x201]^=1
        if self.changed_monitor:self.ram[0x7D30]^=0x10
        return b'STR8-N 2.0rc1\r\nB3> '


def fixture(image, slot, edu):
    banks=[bytearray(b'\xA6'*32768)]+[bytearray(image[i:i+32768]) for i in range(0,len(image),32768)]
    banks[1][:4096]=b'\x82'*4096  # Nonowned application/owner bytes remain opaque.
    cfg=r.preference(r.latest(banks)[2][8:24],slot,50)
    banks[3][0x1C00:0x2000]=b'\x5D'*1024  # Append-only TZ policy history.
    banks[3][0x4000:0x6000]=b'\xff'*8192
    banks[3][0x4000:0x4080]=r.record(cfg,list(range(120,152)),1000)
    ram=bytes(i%251 for i in range(0x6300 if edu else 0x6500))
    return list(map(bytes,banks)),ram


def auth(root, folder, board, action):
    # Synthetic gate fixture, used only with Link above; never passed to live CLI.
    value=dict(owner_authorized=True,action=action,board=board,usb_serial=REGISTRY['boards'][board]['usb_serial'],
               other_boards_authorized=False,RTC_campaign_resume_authorized=False,synthetic_test_authorization=True,
               manifest_sha256=r.sha((root/'installer-manifest.json').read_bytes()))
    if folder:value['plan_sha256']=r.sha((folder/'plan.json').read_bytes())
    return value


def host_proof(root, folder):
    # Host-state-machine double. Actual CPU qualification is performed separately.
    return dict(passed=True,board_access=False,hardware_qualified=False,
        manifest_sha256=r.sha((root/'installer-manifest.json').read_bytes()),plan_sha256=r.sha((folder/'plan.json').read_bytes()),
        model_source_sha256=r.sha(Path(model.__file__).read_bytes()),
        models=[dict(passed=True,CPU=cpu) for cpu in ('65C02','65C816 E=1')])


def transfer(link, folder, **kwargs):
    assert kwargs['host_readback'] is True
    info=r.read(folder/'plan.json')
    link.ram[0x200:0x200+(0x6300 if len((folder/'capture/application-ram.bin').read_bytes())==0x6300 else 0x6500)]=b'\xD4'*len((folder/'capture/application-ram.bin').read_bytes())
    link.banks=[bytearray((folder/f'expected-b{n}.bin').read_bytes()) for n in range(4)]
    link.pending_reset=True
    for n,op in enumerate(info['transaction']['operations'][1:]):kwargs['progress'](n+1,op)
    return dict(transaction_device_verified=True,physical_reset_pending=True,transfers_completed=len(info['transaction']['operations'])-1,host_memory_readbacks=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--deps-02',type=Path,required=True);parser.add_argument('--deps-816',type=Path,required=True)
    parser.add_argument('--firmware',type=Path,help='Explicit historical asm-dev regression image; default also verifies a fresh src/current build')
    args=parser.parse_args();out=args.out.resolve();r.require(not out.exists(),'Fresh test directory required')
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');checks=[];cpu=[]
    def passed(label):checks.append(label);print('PASS',label,flush=True);save(out/'progress.json',dict(checks=checks,cpu=cpu))
    def refused(label,call):
        try:call()
        except (ValueError,AssertionError,KeyError,OSError):passed(label)
        else:raise AssertionError('Accepted '+label)
    def command(label,argv):
        with (out/(label+'.log')).open('w') as log:
            result=subprocess.run([sys.executable,'-B',*map(str,argv)],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
        r.require(result.returncode==0,'Reference/portable command failed: '+label)

    image_paths,golden,transactions=baseline_fixtures(out)
    if args.firmware is None:
        command('current-build',[ROOT/'tools/build_current.py','--out',out/'current-build'])
        current=out/'current-build/firmware.bin'
        matches=[name for name,row in REGISTRY['candidates'].items() if r.sha(current.read_bytes())==row['firmware_sha256']]
        if not matches:
            # A selected development target has its own sealed installation kit.
            # The historical differential suite keeps its original profile inventory.
            selected=r.read(ROOT/'src/current/target.json')
            target_fixture=ROOT/selected['fixture']
            approved={'monitor-size-branches':'efb5f2c031be32d268aefb9bc14a16d0b8f7f4bef12974293664de517ec83dad',
                      'fixed-f-size-recovery':'7fcec7cdbf8a9c9aed0766894d0d63a396c48d38e2da7cf90f894a565f2485f1',
                        'fixed-f-flow-size':'c85c4055eac41e5e522f1bc62f2bd354957018e3afc1ccdc25a91e52a55a980e'}
            r.require(selected['candidate'] in approved and
                      selected['firmware_sha256']==approved[selected['candidate']] and
                      r.sha(current.read_bytes())==selected['firmware_sha256'] and
                      r.sha(target_fixture.read_bytes())==selected['fixture_sha256'] and
                      r.read(out/'current-build/build-report.json')['passed'],
                      'Fresh current build must match its approved selected target')
        else:
            r.require(len(matches)==1,'Fresh current build must match one registered candidate')
            image_paths[matches[0]]=current
        if matches!=['asm-dev']:
            # Historical differential oracles intentionally still test asm-dev upgrades.
            # Their image is data, never an alternate build chain or install default.
            image_paths['asm-dev']=ROOT/'tests/fixtures/asm-dev-regression.bin'
            r.require(r.sha(image_paths['asm-dev'].read_bytes())==REGISTRY['candidates']['asm-dev']['firmware_sha256'],
                      'Historical asm-dev regression fixture differs')
        passed('Fresh current firmware matches its selected verified target')
    else:image_paths['asm-dev']=args.firmware.resolve()
    kit=out/'kit';package.create(kit,'asm-dev',image_paths)
    command('portable-profiles',[kit/'install.py','profiles'])
    passed('Self-contained kit imports and lists profiles without opening ports')

    def compare(folder,name,label):
        compare_baseline(folder,golden[name],transactions[name],label)
        passed(label+' exact installer S19, transfers, four-bank targets, operation order and wear reservations')

    source=image_paths['console-edit'].read_bytes();plans=[]
    for board in REGISTRY['boards']:
        for edu in (False,True):
            for slot in (0xA0,0xB0):
                label=board+('-edu-' if edu else '-bare-')+f'{slot:02x}';banks,ram=fixture(source,slot,edu)
                cap=out/(label+'-capture');capture.write(cap,REGISTRY['boards'][board],banks,ram,synthetic=True)
                folder=out/(label+'-plan');info=plan.prepare(kit,cap,folder);plans.append((label,board,edu,slot,banks,ram,folder))
                r.require(r.latest([(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)])[2][8:24]==r.latest(banks)[2][8:24],'Settings changed')
                link=Link(board,banks,ram,edu=edu);marker=dict(board=board,soak_owner_stopped=True,RTC_sampling_owner_stopped=True)
                preflight=workflow.preflight(kit,link,board,out/(label+'-preflight'),marker,auth(kit,None,board,'capture'),synthetic=True)
                r.require(preflight['passed'] and not link.sends and not preflight['RAM_loaded'] and not preflight['flash_written'],'Preflight performed writes')
                with patch.object(workflow.transport,'execute',side_effect=transfer),patch.object(workflow.time,'sleep',return_value=None):
                    state=workflow.execute(kit,folder,out/(label+'-run'),link,board,marker,auth(kit,folder,board,'execute'),host_proof(kit,folder))
                r.require(state['passed'] and state['RAM_restored'] and link.ram_loads==1 and bytes(link.ram[0x200:0x200+len(ram)])==ram,'RAM escrow differs')
                link.banks[0][123]^=1
                seq,_,row,_=r.latest(link.banks);newcfg=bytearray(row[8:24]);newcfg[6]^=1;newcfg[14:]=wire.config_sum(newcfg)
                counts=[int.from_bytes(row[24+3*i:27+3*i],'little') for i in range(32)]
                free=next(i for i in range(0x4000,0x6000,128) if link.banks[3][i:i+128]==b'\xff'*128)
                link.banks[3][free:free+128]=r.record(newcfg,counts,seq+1)
                current=out/(label+'-current');capture.write(current,REGISTRY['boards'][board],list(map(bytes,link.banks)),ram,synthetic=True)
                no_write=out/(label+'-no-write');plan.prepare(kit,current,no_write)
                with patch.object(workflow.transport,'execute',side_effect=AssertionError('No-write must not execute engine')):
                    state=workflow.execute(kit,no_write,out/(label+'-no-write-run'),link,board,marker,auth(kit,no_write,board,'execute'),host_proof(kit,no_write))
                r.require(state['no_write'] and not link.pending_reset and link.ram_loads==1,'No-write loaded RAM or requested reset')
                restored=out/(label+'-restore');plan.restore(kit,folder,current,restored)
                r.require(r.latest([(restored/f'expected-b{n}.bin').read_bytes() for n in range(4)])[2][8:24]==r.latest(link.banks)[2][8:24],'Restore replayed old settings')
                r.require((restored/'expected-b0.bin').read_bytes()==bytes(link.banks[0]),'Restore lost newer owner bytes')
                passed(label+' host workflow, full readback, double RAM reread, no-write and restore')
    first=plans[0];label,board,edu,slot,banks,ram,folder=first
    command('portable-plan',[kit/'install.py','plan','--kit',kit,'--capture',folder/'capture','--out',out/'portable-plan'])
    command('portable-verify',[kit/'install.py','verify','--kit',kit,'--plan',out/'portable-plan'])
    no_write=out/(label+'-no-write')
    command('portable-no-write-proof',[kit/'install.py','qualify','--kit',kit,'--plan',no_write,'--out',out/'no-write-proof.json',
            '--deps-02',args.deps_02,'--deps-816',args.deps_816])
    proof=r.read(out/'no-write-proof.json');workflow.proof(kit,no_write,proof)
    r.require(all(row['no_write'] and row['CPU_execution_performed'] is False for row in proof['models']),'No-write proof misstates CPU execution')
    passed('Portable kit plans/verifies independently and qualifies no-write without CPU execution')
    compare(folder,'generic','Generic differential')

    # Recovery and readback failures retain accurate pending flags and escrow.
    marker=dict(board=board,soak_owner_stopped=True,RTC_sampling_owner_stopped=True);link=Link(board,banks,ram)
    def interrupted(*a,**kw):transfer(*a,**kw);raise IOError('Simulated lost completion/reset')
    run=out/'interrupted-run'
    with patch.object(workflow.transport,'execute',side_effect=interrupted):
        refused('Interrupted transaction retained for recovery',lambda:workflow.execute(kit,folder,run,link,board,marker,auth(kit,folder,board,'execute'),host_proof(kit,folder)))
    r.require(marker['application_RAM_restore_pending'] and marker['physical_reset_pending'] and link.ram_loads==0,'Premature RAM restoration')
    wrong_marker=deepcopy(marker);wrong_marker['installer_plan_sha256']='0'*64
    refused('Recovery refuses another pending plan',lambda:workflow.recover_ram(kit,folder,run,link,board,wrong_marker,auth(kit,folder,board,'recover')))
    link.banks[0][321]^=1
    refused('Unknown interrupted state retains RAM escrow',lambda:workflow.recover_ram(kit,folder,run,link,board,marker,auth(kit,folder,board,'recover')))
    r.require(link.ram_loads==0 and marker['application_RAM_restore_pending'],'Unknown-state recovery wrote RAM')
    link.banks[0][321]^=1
    link.pending_reset=False  # Simulated operator RESET, never a real device action.
    with patch.object(workflow.time,'sleep',return_value=None):
        state=workflow.recover_ram(kit,folder,run,link,board,marker,auth(kit,folder,board,'recover'))
    r.require(state['full_target_verified'] and state['RAM_restored'] and not marker['application_RAM_restore_pending'],'Recovery failed')
    passed('Known-state RAM recovery clears pending flags only after two full rereads')
    for fault in ('corrupt_target','corrupt_restore','changed_monitor'):
        link=Link(board,banks,ram);setattr(link,fault,True);marker=dict(board=board,soak_owner_stopped=True,RTC_sampling_owner_stopped=True)
        with patch.object(workflow.transport,'execute',side_effect=transfer),patch.object(workflow.time,'sleep',return_value=None):
            refused(fault+' is not reported as success',lambda:workflow.execute(kit,folder,out/(fault+'-run'),link,board,marker,auth(kit,folder,board,'execute'),host_proof(kit,folder)))
        if fault=='corrupt_restore':r.require(marker['application_RAM_restore_pending'],'RAM failure lost pending flag')
    for fault in ('bad_cpu','bad_slot','repeat_mismatch','repeat_ram_mismatch'):
        link=Link(board,banks,ram);setattr(link,fault,True)
        refused(fault+' preflight refusal',lambda:workflow.preflight(kit,link,board,out/(fault+'-capture'),dict(board=board,soak_owner_stopped=True,RTC_sampling_owner_stopped=True),auth(kit,None,board,'capture'),synthetic=True))
        r.require(not link.sends and not (out/(fault+'-capture')).exists(),'Failed preflight wrote/accepted capture')
    link=Link(board,banks,ram)
    refused('Wrong operation marker before any link call',lambda:workflow.preflight(kit,link,board,out/'wrong-marker',dict(board='2609',soak_owner_stopped=True,RTC_sampling_owner_stopped=True),auth(kit,None,board,'capture'),synthetic=True))
    r.require(not link.commands and not link.sends,'Wrong marker reached link')
    marker_file=out/'synthetic-marker.json';auth_file=out/'synthetic-authorization.json'
    save(marker_file,dict(board=board,soak_owner_stopped=True,RTC_sampling_owner_stopped=True));save(auth_file,auth(kit,folder,board,'execute'))
    proof_file=out/'synthetic-proof.json';save(proof_file,host_proof(kit,folder))
    with patch.object(cli,'live_link',side_effect=AssertionError('Live adapter must remain unreachable')) as adapter:
        try:cli.main(['execute','--kit',str(kit),'--plan',str(folder),'--board',board,'--run',str(out/'forbidden-live-run'),
                      '--marker',str(marker_file),'--authorization',str(auth_file),'--proof',str(proof_file),'--coordination',str(out/'unused-coordination')])
        except SystemExit as error:r.require('Synthetic capture' in str(error),'Wrong CLI refusal')
        else:raise AssertionError('Synthetic capture reached live CLI')
        adapter.assert_not_called()
    passed('Live CLI refuses synthetic capture before entering serial adapter')
    refused('Wrong board/USB capture',lambda:capture.validate(folder/'capture','2609'))
    refused('Active campaign',lambda:workflow.idle(dict(soak_owner_stopped=False,RTC_sampling_owner_stopped=True)))
    refused('Pending RAM ownership',lambda:workflow.idle(dict(soak_owner_stopped=True,RTC_sampling_owner_stopped=True,application_RAM_restore_pending=True)))
    bad=host_proof(kit,folder);bad['plan_sha256']='0'*64
    refused('Stale model proof',lambda:workflow.proof(kit,folder,bad))
    bad=auth(kit,folder,board,'execute');bad['usb_serial']='WRONG'
    refused('Wrong USB authorization',lambda:workflow.authorization(bad,board,'execute',root=kit,folder=folder))
    badcap=out/'different-repeated-capture';shutil.copytree(folder/'capture',badcap)
    member=badcap/'b0-repeat.bin';data=bytearray(member.read_bytes());data[0]^=1;member.write_bytes(data)
    capinfo=r.read(badcap/'capture.json');capinfo['files']['b0-repeat.bin']['sha256']=r.sha(data);save(badcap/'capture.json',capinfo)
    refused('Rehashed mismatching repeated bank',lambda:capture.validate(badcap))
    badcap2=out/'unknown-firmware-capture';shutil.copytree(folder/'capture',badcap2)
    capinfo=r.read(badcap2/'capture.json')
    for suffix in ('','-repeat'):
        name='b1'+suffix+'.bin';data=bytearray((badcap2/name).read_bytes());data[0x6000]^=1;(badcap2/name).write_bytes(data)
        capinfo['files'][name]['sha256']=r.sha(data)
    save(badcap2/'capture.json',capinfo)
    refused('Rehashed unknown firmware refused without force',lambda:plan.prepare(kit,badcap2,out/'unknown-plan'))
    installer=folder/'installer-model-only.s19';original=installer.read_bytes();installer.write_bytes(original.replace(b'S0',b'S1',1))
    info=r.read(folder/'plan.json');saved=deepcopy(info);info['installer_sha256']=r.sha(installer.read_bytes());save(folder/'plan.json',info)
    refused('Rehashed edited installer',lambda:plan.verify(kit,folder))
    installer.write_bytes(original);save(folder/'plan.json',saved)

    for name,image in image_paths.items():
        candidate_banks,candidate_ram=fixture(image.read_bytes(),0xB0,False)
        candidate_cap=out/(name+'-registered-capture');capture.write(candidate_cap,REGISTRY['boards'][board],candidate_banks,candidate_ram,synthetic=True)
        candidate_plan=out/(name+'-registered-plan');info=plan.prepare(kit,candidate_cap,candidate_plan)
        r.require(info['source_profile']==name and (info['transaction'] is None)==(name=='asm-dev'),'Registered source misidentified')
        if name!='asm-dev':
            after=[(candidate_plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            r.require(after[0]==candidate_banks[0] and after[3][0x1000:0x2000]==candidate_banks[3][0x1000:0x2000],'Registered source preservation differs')
        passed('Registered '+name+' source admitted with exact identity and preservation/no-write policy')

    # The sole erase profile uses a separate, explicit source-capture policy.
    cleanup_banks=[bytearray(x) for x in banks];cleanup_banks[0][:]=b'\xff'*32768
    cleanup_banks[1][:4096]=source[:4096]
    text=['ORG $0200','BRK $01','BRK $02','END']
    packed=b''.join(struct.pack('<HBB',10*(i+1),len(t),0)+t.encode() for i,t in enumerate(text))
    body=b'AS\1\10'+struct.pack('<HH',len(packed),wire.crc(packed))+packed
    for i,name in enumerate(REGISTRY['cleanup']['source_names']):
        header=bytearray(32);header[:4]=b'SF\1\xff';header[4:6]=len(body).to_bytes(2,'little');header[6]=1;header[8:24]=name.encode().ljust(16,b'\0')
        header[24:26]=wire.crc(header[:24]).to_bytes(2,'little');header[3]=0x3F
        cleanup_banks[0][i*4096:(i+1)*4096]=header+body+b'\xff'*(4096-32-len(body))
    cleanup_cap=out/'cleanup-capture';capture.write(cleanup_cap,REGISTRY['boards']['2604'],list(map(bytes,cleanup_banks)),ram,synthetic=True)
    cleanup=out/'cleanup-kit';package.create(cleanup,'asm-dev-cleanup-2604',{'console-edit':image_paths['console-edit'],'asm-dev':image_paths['asm-dev']},board='2604',cleanup_capture=cleanup_cap)
    cleaned=out/'cleanup-plan';plan.prepare(cleanup,cleanup_cap,cleaned)
    compare(cleaned,'cleanup','Cleanup differential')
    refused('Cleanup cannot target another board',lambda:plan.prepare(cleanup,folder/'capture',out/'wrong-cleanup',board='2609'))
    refused('Cleanup has no automatic destructive restore',lambda:plan.restore(cleanup,cleaned,cleanup_cap,out/'cleanup-restore'))
    refused('Cleanup rejects alternate target even when already at that source',lambda:plan.prepare(cleanup,cleanup_cap,out/'cleanup-wrong-target',target='console-edit'))

    # Execute the real linked installer instructions, with no hardware/ports.
    proof=model.qualify(kit,folder,out/'cpu-proof.json',deps02=args.deps_02,deps816=args.deps_816)
    cpu.extend(proof['models']);passed('Generic installer executes and verifies all four banks on both CPU models')
    restored=out/(label+'-restore');proof=model.qualify(kit,restored,out/'restore-cpu-proof.json',deps02=args.deps_02,deps816=args.deps_816)
    cpu.extend(proof['models']);passed('Restore executes on both CPUs while preserving newer settings/owner bytes and increasing wear')
    for name in ('release-r9','source-store','maint-source'):
        proof=model.qualify(kit,out/(name+'-registered-plan'),out/(name+'-cpu-proof.json'),deps02=args.deps_02,deps816=args.deps_816)
        cpu.extend(proof['models']);passed('Registered '+name+' upgrade executes with exact all-bank result on both CPUs')
    for fault in ('stale','corrupt'):
        for is816 in (False,True):
            row=model.execute(kit,folder,banks,is816=is816,deps02=args.deps_02,deps816=args.deps_816,fault=fault)
            row['CPU']='65C816 E=1' if is816 else '65C02';cpu.append(row);passed('Linked installer '+fault+' refusal on '+row['CPU'])
    proof=model.qualify(cleanup,cleaned,out/'cleanup-cpu-proof.json',deps02=args.deps_02,deps816=args.deps_816)
    cpu.extend(proof['models']);passed('Explicit cleanup executes with exact erase accounting on both CPU models')
    r.require(not SERIAL_IMPORT_ATTEMPTS,'Offline suite attempted serial imports')
    result=dict(passed=True,board_access=False,serial_ports_opened=0,serial_import_attempts=SERIAL_IMPORT_ATTEMPTS,checks=checks,cpu_models=cpu,
                generic_manifest_sha256=r.sha((kit/'installer-manifest.json').read_bytes()),
                cleanup_manifest_sha256=r.sha((cleanup/'installer-manifest.json').read_bytes()),
                fixture_manifest_sha256=r.sha((ROOT/'tests/fixtures/installer-fixtures.json').read_bytes()),
                phase4_differential_checked=True,historical_build_or_installer_chain_required=False,
                test_source_sha256=r.sha(Path(__file__).read_bytes()),private_fixture_data_not_for_distribution=True)
    save(out/'report.json',result);print('PASS all installer regression checks:',out/'report.json',flush=True)


if __name__=='__main__':main()
