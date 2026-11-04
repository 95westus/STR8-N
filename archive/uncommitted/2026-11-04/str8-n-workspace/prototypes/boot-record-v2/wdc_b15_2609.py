"""Offline exact-source WDCMONV2 -> b15 F-only planner for board 2609.

There is deliberately no live execution command or serial import. The private
output binds the saved original firmware and one 4096-byte F transfer. Every
other flash byte is preserved. A future hardware step admits that source again.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(HERE)]
from installer.engine import legacy_transport as wire, runtime as r
from installer.common import save
from str8build.assemble import Assembly
from deployment_plan import snbt_records

BOARD='2609'
USB='A10MPQXCA'
WDC_SHA='1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94'
GENERATION=0x8000000f
TARGET=ROOT/'BUILD/pr04-b15-cancel-r3'
TEMPLATE=ROOT/'tools/installer/engine/template'
TEMPLATE_SHA='13e73e67b0305c238f23fca4d0cd1e07579a4f989acca9f61f3376549934ba7e'
NATIVE_ENTRY=bytes.fromhex('38fb78d8a2ff9af400002b4bab4c0720')
ORDER=((3,0xf000),)

def digest(path):return r.sha(Path(path).read_bytes())

def bind(path):
    path=Path(path).resolve()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest(path))

def inputs(session,backup,target=TARGET):
    session,backup,target=map(lambda p:Path(p).resolve(),(session,backup,target))
    state=r.read(session/'session.json');step=session/'step01-WDCMONV2-backup'
    first=r.read(step/'report.json');prior=r.read(backup/'report.json')
    execution=r.read(backup/'restore-execution/report.json')
    boot=r.read(backup/'original-WDC-boot-verification-final/report.json')
    history=r.read(backup/'post-restore-wear-history.json')
    r.require(state['board']==BOARD and state['step01']=='complete' and not state['b15_installed'], 'Completed 2609 step 1 required')
    r.require(first['passed'] and first['B0_copy_matches_B3'] and first['B3_backup_repeated'] and first['port_released'], 'Fresh original-WDC backup required')
    r.require(prior['passed'] and prior['flash_repeat_verified'] and execution['passed'] and execution['transaction_device_verified'] and boot['passed'], 'Verified full preimage provenance required')
    files=[step/'report.json',backup/'report.json',backup/'restore-execution/report.json',
           backup/'original-WDC-boot-verification-final/report.json',backup/'post-restore-wear-history.json']
    for name,info in first['files'].items():
        path=step/name;r.require(path.stat().st_size==info['bytes'] and digest(path)==info['sha256'], 'Changed step-1 backup member')
        files.append(path)
    source=[]
    for bank in range(4):
        if bank in (0,3):
            a,b=step/f'b{bank}-wdcmonv2.bin',step/f'b{bank}-wdcmonv2-repeat.bin'
        else:a,b=backup/f'b{bank}.bin',backup/f'b{bank}-repeat.bin'
        body=a.read_bytes();r.require(len(body)==32768 and body==b.read_bytes(),'Different repeated source bank')
        r.require(r.sha(body)==execution['expected_hashes'][bank], 'Source differs from device-verified original restoration')
        source.append(body);files += [a,b]
    r.require(source[0]==source[3] and r.sha(source[3])==WDC_SHA,'Exact 2609 original WDCMONV2 and B0 backup required')
    r.require((step/'stock-debugger-identity.bin').read_bytes()[:4]==b'SXB6','Original 65C816 debugger identity required')
    r.require(history['board']==BOARD and history['actual_erase_order_device_verified'] and not history['counts_are_reserved_upper_bounds_until_device_verified'], 'Verified owner-local wear history required')
    r.require(history['execution_report_sha256']==digest(backup/'restore-execution/report.json'),'Wear history execution binding changed')
    counts=history['counts'];config=bytes.fromhex(history['config']);sequence=history['sequence']
    r.record(config,counts,sequence)
    r.require(sequence<=0xfffffffd and config[1]==0 and config[8] in (0xa0,0xb0),'Unsupported source configuration/sequence')
    qualification=r.read(target/'b15-qualification.json')
    r.require(qualification['passed'] and qualification['checks']==512 and qualification['generation_hex']=='8000000F','Exact qualified b15 F target required')
    fpath=target/'payload/f-offline-component.bin'
    r.require(fpath.stat().st_size==4096 and digest(fpath)==qualification['reproducible_payload_sha256'][fpath.name],'Changed qualified b15 F image')
    files.append(fpath)
    for name,value in qualification['source_sha256'].items():r.require(digest(HERE/name)==value,'Changed qualified b15 source')
    files += [target/'b15-qualification.json',
              TEMPLATE/'integrated-template.s19',TEMPLATE/'manifest.json',TEMPLATE/'symbols.json',
              HERE/'wdc-b15-guard.asm',Path(__file__)]
    return source,config,counts,sequence,{str(p.resolve()):bind(p) for p in files}

def derive(source,config,counts,sequence,target=TARGET):
    r.valid_banks(source)
    r.require(source[0]==source[3] and r.sha(source[3])==WDC_SHA,'Only exact original 2609 WDC source is supported')
    r.require(not snbt_records(source),'Factory source must not be treated as an existing SNBT journal')
    reserved=list(counts)
    for bank,address in ORDER:
        i=bank*8+(address>>12)-8;r.require(reserved[i]<0xffffff,'Wear counter exhausted');reserved[i]+=1
    body=(Path(target)/'payload/f-offline-component.bin').read_bytes()
    r.require(len(body)==4096 and body[:4]==b'SN\x02\0' and body[-4:-2]==b'\x04\xf0','Exact 4096-byte b15 RESET root required')
    state=list(map(bytearray,source));operations=[];data=[]
    for bank,address in ORDER:
        before=r.hashes(state);off=address-0x8000;state[bank][off:off+4096]=body
        operations.append(dict(kind='b15-F-only',bank=bank,address=address,
            commit_address=None,source_sha256=before,after_sha256=r.hashes(state),data_sha256=r.sha(body)))
        data.append(body)
    expected=list(map(bytes,state));r.require(expected[:3]==source[:3],'B0/B1/B2 preservation failed')
    r.require(expected[3][:-4096]==source[3][:-4096],'A non-F B3 byte changed')
    r.require(not snbt_records(expected),'F-only stage must not initialize a journal')
    tx=dict(label='2609 WDCMONV2 to b15 F only; every other flash byte preserved',source_sha256=r.hashes(source),expected_sha256=r.hashes(expected),
        operations=operations,planned_erase_order=[[b,a>>12] for b,a in ORDER],counts_before=counts,reserved_counts=reserved,
        sequence_before=sequence,sequence_after=sequence,source_config=config.hex(),target_config=config.hex(),
        target_generation=GENERATION,initial_boot='F recovery; no compatible MON or SNBT installed',
        onboard_journal_initialized=False,wear_accounting='Host-only F erase reservation; C/D are untouched',
        no_lifetime_wear_claim=True,model_only=True,installation_permitted=False)
    return tx,data,expected

def build_guard(out):
    stage=out/'s/guard';stage.mkdir(parents=True)
    shutil.copyfile(HERE/'wdc-b15-guard.asm',stage/'guard.asm')
    a=object.__new__(Assembly);a.out=out;a.assembler=shutil.which('wdc02as');a.linker=shutil.which('wdcln');a.symbols={};a.compiled=[]
    r.require(a.assembler and a.linker,'WDC assembler and linker required')
    body,symbols=a.link('guard','guard',0x3000,'GUARD_END')
    r.require(len(body)<=0x300,'Guard overlaps template data')
    save(out/'guard-build.json',dict(bytes=len(body),sha256=r.sha(body),symbols=symbols,source_sha256=digest(HERE/'wdc-b15-guard.asm')))
    return body

def render(source,tx,data,guard):
    r.require(digest(TEMPLATE/'integrated-template.s19')==TEMPLATE_SHA,'Qualified RAM template changed')
    mf=r.read(TEMPLATE/'manifest.json');image,entry=wire.read_s19(TEMPLATE/'integrated-template.s19')
    r.require(entry==0x2000 and bytes(image[a] for a in range(0x2000,0x2007))==bytes.fromhex('38fb78d8a2ff9a'),'Template entry changed')
    image={a:image.get(a,0) for a in range(0x2000,0x4000)}
    for a in range(0x3000,0x3300):image[a]=0
    image.update(dict(enumerate(guard,0x3000)))
    image.update(dict(enumerate(NATIVE_ENTRY,0x3700)))
    image[mf['count']]=len(tx['operations']);image[mf['commit_after']]=0
    for key,size in (('banks',24),('commits',24),('commit_addresses',96),('commit_values',24),('table',216)):
        image.update({mf[key]+i:0 for i in range(size)})
    image.update(dict(enumerate(b''.join(wire.fnv(b).to_bytes(4,'little') for b in source),0x3500)))
    image.update({a:0 for a in range(0x3600,0x3700)})
    transfers=[];state=list(map(bytearray,source))
    for n,(op,body) in enumerate(zip(tx['operations'],data)):
        r.require(r.hashes(state)==op['source_sha256'],'Changed bootstrap preimage chain')
        bank,address,commit=op['bank'],op['address'],op['commit_address'];transfer=bytearray(body)
        if commit is not None:
            image[mf['commits']+n]=bank+1;image[mf['commit_values']+n]=body[commit-address]
            image.update(dict(enumerate(commit.to_bytes(2,'little'),mf['commit_addresses']+4*n)));transfer[commit-address]=255
        image[mf['banks']+n]=bank
        row=bytes([address>>8])+wire.fnv(state[bank]).to_bytes(4,'little')+wire.fnv(transfer).to_bytes(4,'little')
        image.update(dict(enumerate(row,mf['table']+9*n)));transfers.append(bytes(transfer))
        state[bank][address-0x8000:address-0x7000]=body
    checksum=wire.fnv(bytes(image[a] for a in range(0x2000,0x3f00)))
    image.update(dict(enumerate(checksum.to_bytes(4,'little'),0x3f00)))
    return wire.s19(image,0x3700),transfers

def prepare(session,backup,out,target=TARGET):
    out=Path(out).resolve();r.require(out.is_relative_to(ROOT) and not out.exists(),'Fresh private workspace output required')
    source,config,counts,sequence,bindings=inputs(session,backup,target)
    tx,data,expected=derive(source,config,counts,sequence,target)
    out.mkdir(parents=True);(out/'.gitignore').write_text('*\n');guard=build_guard(out)
    installer,transfers=render(source,tx,data,guard)
    (out/'installer-model-only.s19').write_bytes(installer)
    for n,body in enumerate(transfers):(out/f'transfer-{n:02d}.bin').write_bytes(body)
    for n in range(4):
        (out/f'source-b{n}.bin').write_bytes(source[n]);(out/f'expected-b{n}.bin').write_bytes(expected[n])
    (out/'b15-F-4096.bin').write_bytes(data[0])
    info=dict(schema=1,board=BOARD,usb_serial=USB,route='exact-WDCMONV2-65C816-to-b15-F-only',entry=0x3700,
        native_entry_bytes=NATIVE_ENTRY.hex(),source_cpu='65C816 native or emulation, bank zero',target_cpu='65C816 emulation',
        target_build=str(Path(target).resolve()),source_session=str(Path(session).resolve()),source_backup=str(Path(backup).resolve()),
        F_sha256=r.sha(data[0]),F_bytes=4096,installer_sha256=r.sha(installer),transaction=tx,
        source_sha256=r.hashes(source),expected_sha256=r.hashes(expected),bindings=bindings,
        guard_sha256=r.sha(guard),planner_sha256=digest(__file__),
        model_only=True,board_access=False,installation_permitted=False,hardware_qualified=False,
        source_provenance='B0/B3 freshly double-read in onboarding step 1; B1/B2 from repeated full backup, unchanged by device-verified original restoration; future device preflight rechecks all four complete banks',
        memory=dict(load_first=0x2000,load_last=0x3fff,staging_first=0x4000,staging_last=0x4fff,
                    system_scratch='6200-623F, E0-FF and emulation stack',RAM_worker='7800-7BFF',
                    native_WDC_stack_page_0700_not_uploaded=True),
        operator_policy=dict(stop_before_flashing=True,no_live_execute_command=True,
            MON_A_B_C_D_and_other_sectors_untouched=True,B1_selector_and_languages_deferred=True,
            RTC_time_trim_PF_EEPROM_writes=False),
        progress=[dict(step=1,total=1,destination='B3:F000',bytes=4096,kind='F only')])
    save(out/'plan.json',info);verify(out)
    print('PASS F-only plan: one 4096-byte transfer; every other flash byte preserved; no board access',out,flush=True)
    return info

def verify(out):
    out=Path(out).resolve();info=r.read(out/'plan.json')
    r.require(info['schema']==1 and info['board']==BOARD and info['usb_serial']==USB and info['route']=='exact-WDCMONV2-65C816-to-b15-F-only','Wrong plan identity/route')
    r.require(info['installation_permitted'] is False and info['model_only'] is True and info['board_access'] is False and info['hardware_qualified'] is False,'Offline plan cannot claim live authorization')
    r.require(info['planner_sha256']==digest(__file__),'Planner changed; regenerate')
    for item in info['bindings'].values():
        path=Path(item['path']);r.require(path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],'Changed input binding: '+str(path))
    source=[(out/f'source-b{n}.bin').read_bytes() for n in range(4)]
    r.require(r.hashes(source)==info['source_sha256'],'Changed complete source escrow')
    tx=info['transaction'];config=bytes.fromhex(tx['source_config'])
    derived,data,expected=derive(source,config,tx['counts_before'],tx['sequence_before'],Path(info['target_build']))
    r.require(tx==derived and r.hashes(expected)==info['expected_sha256'],'Changed transaction or target hash map')
    guard_info=r.read(out/'guard-build.json');stage=out/'s/guard/guard.s19'
    cells={}
    for line in stage.read_text().splitlines():
        raw=bytes.fromhex(line[2:]);r.require(sum(raw)&255==255,'Guard S19 checksum')
        if line.startswith('S1'):cells.update(dict(enumerate(raw[3:-1],int.from_bytes(raw[1:3],'big'))))
    guard=bytes(cells[a] for a in range(0x3000,0x3000+guard_info['bytes']))
    r.require(r.sha(guard)==info['guard_sha256']==guard_info['sha256'] and guard_info['source_sha256']==digest(HERE/'wdc-b15-guard.asm'),'Guard binding changed')
    installer,transfers=render(source,tx,data,guard)
    r.require((out/'installer-model-only.s19').read_bytes()==installer and r.sha(installer)==info['installer_sha256'],'Changed linked installer')
    for n,body in enumerate(transfers):r.require((out/f'transfer-{n:02d}.bin').read_bytes()==body,'Changed transfer')
    r.require({p.name for p in out.glob('transfer-*.bin')}=={'transfer-00.bin'},'F-only plan requires exactly one transfer')
    r.require((out/'b15-F-4096.bin').read_bytes()==data[0] and info['F_bytes']==4096 and info['F_sha256']==r.sha(data[0]),'Direct F BIN and RAM-migrator payload differ')
    for n,body in enumerate(expected):r.require((out/f'expected-b{n}.bin').read_bytes()==body,'Changed target escrow')
    return info

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    build=sub.add_parser('prepare');build.add_argument('--session',type=Path,required=True);build.add_argument('--backup',type=Path,required=True)
    build.add_argument('--out',type=Path,required=True);build.add_argument('--target',type=Path,default=TARGET)
    check=sub.add_parser('verify');check.add_argument('--plan',type=Path,required=True)
    args=p.parse_args()
    if args.action=='prepare':prepare(args.session,args.backup,args.out,args.target)
    else:verify(args.plan);print('PASS exact offline plan verification',flush=True)

if __name__=='__main__':main()
