"""Existing-SNBT F upgrade: append a durable reservation, then replace F only.

Separate from factory provisioning. No port on import or prepare/inspect.
Live execution is unqualified and requires an explicit execute flag.
"""
import argparse
from pathlib import Path

import nf_migrate as planning
import nf_migrate_live as live
import nf_provision_live as recovery_transport

ROOT=Path(__file__).resolve().parents[1]
UPGRADE_SHA256='137a73923af1661a6af03d8dc9351e1b1f650f4c6e3381669ae3cf020f8c6b62'
B15_F_SHA256='1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8'
RESERVED=b'JOURNAL: F reservation committed and full B3 verified\r\n'


def derive(banks,target):
    planning.require(len(banks)==4 and all(len(b)==32768 for b in banks),'Four complete source banks required')
    planning.require(len(target)==4096 and planning.sha(target)==planning.F_SHA256,'Target F must remain frozen BASE1')
    status=planning.classify_journal(banks[3])
    planning.require(status['kind']=='valid-snbt','Only clean existing SNBT history is admitted; no conversion/repair')
    old=planning.sha(banks[3][-4096:])
    planning.require(old in (B15_F_SHA256,planning.F_SHA256),'Unsupported source F/raw-L contract')
    base=dict(journal_before=status,source_sha256=planning.bank_hashes(banks),old_F_sha256=old,
        target_F_sha256=planning.F_SHA256,completed_noop=old==planning.F_SHA256)
    if base['completed_noop']:
        return dict(base,expected_sha256=base['source_sha256'],reservation=None),list(map(bytes,banks)),None
    planning.require(status['sequence']<0xffffffff,'SNBT sequence exhausted; no wrap')
    planning.require(status['counts'][31]<planning.MAX_COUNT,'F erase counter exhausted')
    free=[offset for offset in range(0x4000,0x6000,256) if banks[3][offset:offset+256]==b'\xff'*256]
    planning.require(bool(free),'No erased append page; refuse without C/D garbage collection')
    latest=next(bytes(banks[3][offset:offset+256]) for offset in range(0x4000,0x6000,256)
        if planning.valid_snapshot(banks[3][offset:offset+256])
        and int.from_bytes(banks[3][offset+8:offset+12],'little')==status['sequence'])
    row=bytearray(latest)
    row[8:12]=(status['sequence']+1).to_bytes(4,'little')
    row[157:160]=(status['counts'][31]+1).to_bytes(3,'little')
    row[30:32]=planning.crc(row[:30]).to_bytes(2,'little')
    row[252:254]=planning.crc(row[:252]).to_bytes(2,'little')
    planning.require(planning.valid_snapshot(row),'Internal reservation serialization failure')
    offset=free[0];reserved=bytearray(banks[3]);reserved[offset:offset+256]=row
    expected=list(map(bytes,banks));expected[3]=bytes(reserved[:0x7000])+target
    uncommitted=bytes(row[:255])+b'\xff'
    return dict(base,reservation=dict(address=offset+0x8000,bytes=256,commit_address=offset+0x80ff,
        sequence=status['sequence']+1,F_count_before=status['counts'][31],F_count_reserved=status['counts'][31]+1,
        reserved_B3_fnv=f'{planning.fnv(reserved):08x}',record_sha256=planning.sha(row),
        C_D_erases=0,settings_and_other_counters_preserved=True),
        expected_sha256=planning.bank_hashes(expected)),expected,uncommitted


def render(template,tx,expected,frame,target):
    planning.require(len(template)==8192 and planning.sha(template)==UPGRADE_SHA256,'Pinned NFU1 RAM template required')
    planning.require(not tx['completed_noop'],'No RAM engine for a no-op')
    page=bytearray(256);page[:6]=b'NFU1\x01\x01'
    page[8:24]=b''.join(planning.fnv(b).to_bytes(4,'little') for b in tx['_source_banks'])
    page[32]=0xf0
    page[36:40]=int(tx['reservation']['reserved_B3_fnv'],16).to_bytes(4,'little')
    page[40:44]=planning.fnv(target).to_bytes(4,'little')
    page[44:48]=planning.fnv(expected[3]).to_bytes(4,'little')
    image=bytearray(template);image[0x1000:0x1100]=page;image[0x1100:0x1200]=frame
    info=bytearray(16);info[:4]=b'JFR1';info[4]=tx['reservation']['address']>>8
    info[8:12]=page[36:40];image[0x1300:0x1310]=info
    image[0x1ffc:]=planning.fnv(image[:0x1ffc]).to_bytes(4,'little')
    return bytes(image)


def prepare(capture,out,*,cpu,target_file,template_file=ROOT/'migrator/upgrade/payload/template.bin'):
    out=Path(out).resolve();planning.require(not out.exists(),'Fresh private plan directory required')
    identity,banks,members=planning.read_capture(capture,cpu,'nf-recovery')
    planning.require(identity.get('owner_original_before_helpers') is True
        and isinstance(identity.get('usb_serial'),str) and bool(identity['usb_serial'].strip()),
        'Source capture must declare original pre-helper RAM and exact USB serial')
    target=Path(target_file).read_bytes();tx,expected,frame=derive(banks,target)
    files={'source/'+name:body for name,body in members.items()}
    files['target-F.bin']=target
    files.update({f'expected-b{n}.bin':body for n,body in enumerate(expected)})
    if frame is not None:
        files['reservation-uncommitted.bin']=frame
        template=Path(template_file).read_bytes()
        image=render(template,dict(tx,_source_banks=banks),expected,frame,target)
        files['engine-template.bin']=template;files['upgrade.bin']=image
        wrapper,_=recovery_transport.module_at('nfu_wrapper',ROOT/'migrator/build.py').recovery_loader(image)
        files['upgrade-recovery.bin']=wrapper
    plan=dict(schema=1,kind='existing-SNBT-F-upgrade',cpu=cpu,source_identity=identity,transaction=tx,
        hardware_qualified=False,flash_written=False,files={name:dict(bytes=len(body),sha256=planning.sha(body))
            for name,body in files.items()})
    out.mkdir(parents=True);planning.durable_write(out/'.gitignore',b'*\n')
    for name,body in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);planning.durable_write(p,body)
    planning.durable_write(out/'plan.json',planning.encoded(plan))
    inspect(out);return plan


def inspect(root):
    root=Path(root).resolve();plan=planning.read_json(root/'plan.json')
    planning.require(plan.get('schema')==1 and plan.get('kind')=='existing-SNBT-F-upgrade'
        and plan.get('hardware_qualified') is False and plan.get('flash_written') is False,'Wrong upgrade plan')
    for name,record in plan['files'].items():
        p=root/name
        planning.require(p.resolve().is_relative_to(root) and not p.is_symlink(),'Outside/symlink plan member')
        body=p.read_bytes()
        planning.require(len(body)==record['bytes'] and planning.sha(body)==record['sha256'],'Changed plan member: '+name)
    identity,banks,_=planning.read_capture(root/'source',plan['cpu'],'nf-recovery')
    planning.require(identity==plan['source_identity'] and identity.get('owner_original_before_helpers') is True
        and bool(identity.get('usb_serial')),'Changed original escrow/USB declaration')
    target=(root/'target-F.bin').read_bytes();tx,expected,frame=derive(banks,target)
    planning.require(tx==plan['transaction'],'Changed reservation/transaction')
    for n,body in enumerate(expected):planning.require((root/f'expected-b{n}.bin').read_bytes()==body,'Changed final bank')
    if frame is not None:
        planning.require((root/'reservation-uncommitted.bin').read_bytes()==frame,'Changed reservation')
        image=render((root/'engine-template.bin').read_bytes(),dict(tx,_source_banks=banks),expected,frame,target)
        wrapper,_=recovery_transport.module_at('nfu_inspect_wrapper',ROOT/'migrator/build.py').recovery_loader(image)
        planning.require((root/'upgrade.bin').read_bytes()==image
            and (root/'upgrade-recovery.bin').read_bytes()==wrapper,'Changed rendered upgrade')
    return plan


def execute(link,plan_root,run_root,*,allow_unqualified=False,reset_wait=60,message=print,pace=live.time.sleep):
    planning.require(allow_unqualified,'Explicit --allow-unqualified required')
    plan_root,run_root=Path(plan_root),Path(run_root);plan=inspect(plan_root)
    planning.require(not plan['source_identity'].get('reference_only'),
                     'Archived reference-only plan cannot execute; fresh double-read capture required')
    planning.require(not plan['transaction']['completed_noop'],'No upgrade planned; no device needed')
    readback=(ROOT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    planning.require(len(readback)==3078 and planning.sha(readback)==live.READBACK_SHA256,
                     'Matching BASE1 READBACK required before any device action')
    phases=live.PhaseLog(run_root,message=message)
    state=dict(schema=1,hardware_access=bool(link.hardware_access),hardware_qualified=False,
        journal_may_have_changed=False,journal_reservation_device_verified=False,F_may_have_changed=False,
        flash_written=False,passed=False,independent_flash_readback_verified=False,
        owner_RAM_restored=False,owner_ZP_restored=False,owner_RAM_restore_required=False)
    def checkpoint(phase):phases.add(phase,**state)
    try:
        checkpoint('original-escrow-and-upgrade-plan-durable')
        # Only admitted legacy b15/raw-L source F; actual preimages are freshly
        # checked by the independent RAM engine before Y and again before append.
        message('Press physical RESET. Waiting for the old F chooser; selecting recovery without changing saved default.',flush=True)
        link.until(recovery_transport.CHOICES,seconds=reset_wait);link.send(b'S')
        link.until(live.REC,seconds=reset_wait);recovery_transport.recovery_usb(link)
        state['owner_RAM_restore_required']=True;checkpoint('before-upgrade-RAM-upload')
        client=recovery_transport.module_at('nfu_recovery',ROOT/'tools/nf_recovery.py').RecoveryClient(
            live.LoggedRecoveryStream(link),sleep=pace,progress=lambda s:message(s,flush=True))
        client.send(b'L\r');client.until(b'SEND BIN\r\n')
        client.paced((plan_root/'upgrade-recovery.bin').read_bytes())
        preflight=link.until(live.ENGINE_READY,seconds=60)
        planning.require(live.ENGINE_SELF_OK in preflight and live.ENGINE_SOURCE_OK in preflight,
                         'Upgrade self/source/chip preflight missing; no Y sent')
        planning.durable_write(run_root/'preflight.txt',preflight)
        inspect(plan_root)
        state['journal_may_have_changed']=True;checkpoint('journal-append-authorized-before-Y-no-retry')
        link.send(b'Y\r')
        planning.durable_write(run_root/'reservation-device-verified.txt',link.until(RESERVED,seconds=60))
        state['journal_reservation_device_verified']=True;checkpoint('reservation-committed-before-F-payload')
        link.until(b'SEND 4096 BYTES FOR B3:F\r\n',seconds=60)
        inspect(plan_root)
        state['F_may_have_changed']=True;checkpoint('reserved-F-attempt-before-payload-no-retry')
        target=(plan_root/'target-F.bin').read_bytes()
        for offset in range(0,4096,64):link.send(target[offset:offset+64]);pace(.01)
        link.until(live.ROW_DONE,seconds=60);link.until(live.ENGINE_DONE,seconds=60)
        state['flash_written']=True;checkpoint('device-verified-physical-reset-required')
        face=recovery_transport.observe_reset(link,phases,reset_wait=reset_wait,message=message)
        planning.durable_write(run_root/'BASE1-physical-reset-REC.txt',face)
        recovery_transport.recovery_usb(link)
        client.load(readback,live.READBACK_SHA256,REC_observed=True)
        for bank in range(4):
            body=client.flash(bank);planning.durable_write(run_root/f'final-b{bank}.bin',body)
            planning.require(planning.sha(body)==plan['transaction']['expected_sha256'][bank],
                             'Independent final flash mismatch; inspect before restoring RAM')
        state['independent_flash_readback_verified']=True
        state.update(client.restore_owner((plan_root/'source/owner-ram.bin').read_bytes(),
            (plan_root/'source/owner-zp.bin').read_bytes()))
        planning.require(state.get('owner_RAM_restored') and state.get('owner_ZP_restored')
            and state.get('stopped_at_REC'),'Original escrow restoration incomplete')
        state.update(passed=True,owner_RAM_restore_required=False);checkpoint('upgrade-preservation-complete')
    except BaseException as error:
        state['failure']=str(error);checkpoint('inspection-required-no-automatic-retry');raise
    finally:planning.durable_write(run_root/'result.json',planning.encoded(state))
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    make=sub.add_parser('prepare');make.add_argument('--capture',type=Path,required=True)
    make.add_argument('--cpu',choices=tuple(planning.CPU_MODELS),required=True);make.add_argument('--out',type=Path,required=True)
    make.add_argument('--f-image',type=Path,default=ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin')
    check=sub.add_parser('inspect');check.add_argument('--plan',type=Path,required=True)
    live_cmd=sub.add_parser('execute');live_cmd.add_argument('--plan',type=Path,required=True)
    live_cmd.add_argument('--port',required=True);live_cmd.add_argument('--out',type=Path,required=True)
    live_cmd.add_argument('--allow-unqualified',action='store_true');live_cmd.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='prepare':result=prepare(args.capture,args.out,cpu=args.cpu,target_file=args.f_image)
        else:
            result=inspect(args.plan)
            if args.command=='execute':
                planning.require(args.allow_unqualified and args.execute,'--execute and --allow-unqualified required; no port opened')
                planning.require(not result['source_identity'].get('reference_only'),
                    'Archived reference-only plan cannot execute; fresh double-read capture required')
                if result['transaction']['completed_noop']:
                    print('NO-OP PLAN: target F already matches; no device opened.');return
                planning.require(planning.sha((ROOT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
                    ==live.READBACK_SHA256,'Matching BASE1 READBACK required before opening a port')
                root=live.private_root(args.out)
                with (root/'serial.jsonl').open('x',encoding='utf-8',newline='\n') as log:
                    link=recovery_transport.RecoveryLink(args.port,log,usb_serial=result['source_identity']['usb_serial'])
                    try:result=execute(link,args.plan,root,allow_unqualified=True)
                    finally:link.close()
        print(planning.encoded(result).decode('utf-8'))
    except (OSError,ValueError,KeyError,TimeoutError) as error:
        parser.exit(2,'STOPPED: '+str(error)+'\nKeep escrow and phase log; no automatic reset/replay.\n')


if __name__=='__main__':main()
