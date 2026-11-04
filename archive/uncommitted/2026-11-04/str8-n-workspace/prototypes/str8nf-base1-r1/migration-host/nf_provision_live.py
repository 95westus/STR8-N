"""Unqualified live C/D provisioning through programmer-installed frozen BASE1 F.

Default: capture, plan, independently verify unchanged flash, restore escrow.
--execute explicitly authorizes only a freshly admitted D-then-C transaction.
No port opens on import. Original pre-helper RAM escrow is mandatory.
"""
import argparse
import importlib.util
from pathlib import Path

import nf_migrate as planning
import nf_migrate_live as live

ROOT=Path(__file__).resolve().parents[1]
CHOICES=b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
IDENTITY=b'STR8N-F 0.3.0 g00000001\r\nBASE1 / PR05\r\n'
ESCROW_FILES={'owner-ram.bin':planning.OWNER_RAM_SIZE,
              'owner-ram-repeat.bin':planning.OWNER_RAM_SIZE,
              'owner-zp.bin':planning.OWNER_ZP_SIZE,
              'owner-zp-repeat.bin':planning.OWNER_ZP_SIZE}


def module_at(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def owner_escrow(root,*,cpu,usb_serial):
    """Admit externally captured ORIGINAL RAM, never helper working bytes."""
    root=Path(root).resolve()
    meta=planning.read_json(root/'escrow.json')
    planning.require(cpu in planning.CPU_MODELS and meta.get('schema')==1
        and meta.get('cpu')==cpu and meta.get('board_model')==planning.CPU_MODELS[cpu]
        and isinstance(usb_serial,str) and bool(usb_serial.strip())
        and meta.get('usb_serial')==usb_serial,'Escrow CPU/USB identity mismatch')
    planning.require(meta.get('original_before_helpers') is True
        and meta.get('method')=='independent-double-read'
        and meta.get('owner_RAM_range')=='0200-66FF'
        and meta.get('owner_ZP_range')=='0000-00DF',
        'Explicit original pre-helper RAM/ZP escrow is required')
    bodies={}
    for name,size in ESCROW_FILES.items():
        path=root/name;record=meta.get('files',{}).get(name,{})
        planning.require(path.resolve().is_relative_to(root) and not path.is_symlink(),
                         'Outside/symlink escrow member')
        body=path.read_bytes()
        planning.require(len(body)==size==record.get('bytes')
            and planning.sha(body)==record.get('sha256'),'Incomplete/changed escrow: '+name)
        bodies[name]=body
    for stem in ('owner-ram','owner-zp'):
        planning.require(not (root/(stem+'.bin')).samefile(root/(stem+'-repeat.bin'))
            and bodies[stem+'.bin']==bodies[stem+'-repeat.bin'],
            'Escrow requires separate identical repeated originals: '+stem)
    return meta,bodies


def inputs(readback_file,f_file,engine_file,manifest_file):
    readback,f_image,engine=map(lambda p:Path(p).read_bytes(),(readback_file,f_file,engine_file))
    manifest=planning.read_json(manifest_file)
    record=manifest['artifacts']['STR8N-F-READBACK-RAM.bin']
    planning.require(len(f_image)==4096 and planning.sha(f_image)==planning.F_SHA256,
                     'Only the frozen BASE1 F is supported')
    planning.require(len(readback)==3078 and planning.sha(readback)==live.READBACK_SHA256
        and manifest.get('F_sha256')==planning.F_SHA256 and manifest.get('profile')=='BASE1'
        and record.get('bytes')==len(readback) and record.get('sha256')==live.READBACK_SHA256,
        'Matching BASE1 READBACK and manifest required')
    planning.require(len(engine)==8192 and planning.sha(engine)==live.ENGINE_TEMPLATE_SHA256,
                     'Matching built NFM1 engine required; do not rebuild')
    return readback,f_image,engine


class RecoveryLink(live.WdcLink):
    """Only explicit USB port; never sends WDC sync or auto-reset."""
    def __init__(self,port,log,*,usb_serial):
        import serial
        from serial.tools.list_ports import comports
        matches=[p for p in comports() if p.device==port and p.serial_number==usb_serial]
        planning.require(len(matches)==1,'Selected port does not match escrow USB serial')
        self.serial=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=5,
            xonxoff=False,rtscts=False,dsrdtr=False)
        self.serial.dtr=False;self.serial.rts=False;self.serial.port=port
        self.serial.open()
        self.log,self.pending,self.loaded=log,bytearray(),None


def observe_reset(link,phases,*,reset_wait,message):
    message('Press physical RESET, then wait: observing frozen BASE1 identity and chooser. No automatic reset.',flush=True)
    face=link.until(CHOICES,seconds=reset_wait)
    planning.require(IDENTITY in face,'Frozen BASE1 startup identity not observed; no helper loaded')
    link.send(b'S')
    recovery=link.until(live.REC,seconds=reset_wait)
    planning.require(b'Recovery L ' in recovery,'Expected BASE1 recovery face missing')
    phases.add('physical-reset-BASE1-REC-observed',observation_only=True)
    return face+recovery


def recovery_usb(link):
    link.send(b'C1\r');link.until(live.REC,seconds=15)


def run(link,root,*,escrow,cpu,usb_serial,readback_file,f_file,engine_file,manifest_file,
        provision_cd=False,execute=False,history_file=None,allow_unqualified=False,
        reset_wait=60,message=print,pace=live.time.sleep):
    """Fresh capture/plan only, or explicit execution; never replay a saved plan."""
    planning.require(allow_unqualified,'Explicit --allow-unqualified required; no device action')
    meta,original=owner_escrow(escrow,cpu=cpu,usb_serial=usb_serial)
    readback,f_image,engine=inputs(readback_file,f_file,engine_file,manifest_file)
    root=Path(root)
    planning.require(root.exists() and not (root/'result.json').exists(),'Fresh private run directory required')
    phases=live.PhaseLog(root,message=message)
    state=dict(schema=1,hardware_access=bool(link.hardware_access),execution_qualified=False,
        source_kind='nf-recovery',cpu=cpu,usb_serial=usb_serial,execute_requested=bool(execute),
        flash_written=False,flash_may_have_changed=False,F_written=False,
        owner_RAM_restored=False,owner_ZP_restored=False,owner_RAM_restore_required=False,
        independent_flash_readback_verified=False,REC_verified=False,passed=False,
        owner_escrow_authority='Operator-declared original pre-helper escrow; not a fresh pre-upload RAM read')
    client=None;service_ready=False
    recovery=module_at('nf_provision_recovery',ROOT/'tools/nf_recovery.py')

    def checkpoint(phase):
        phases.add(phase,**state)
        planning.durable_write(root/f'result-{phases.counter:03d}.json',planning.encoded(state))

    def restore():
        nonlocal service_ready
        service_ready=False
        result=client.restore_owner(original['owner-ram.bin'],original['owner-zp.bin'])
        planning.require(result.get('owner_RAM_restored') and result.get('owner_ZP_restored')
            and result.get('stopped_at_REC'),'Escrow restoration did not complete at REC>')
        state.update(result,owner_RAM_restore_required=False,REC_verified=True)
        checkpoint('original-owner-escrow-restored-and-readback-verified')

    try:
        # Durable original escrow precedes the first helper and is never replaced.
        for name,body in original.items():planning.durable_write(root/name,body)
        planning.durable_write(root/'escrow.json',planning.encoded(meta))
        checkpoint('original-owner-escrow-durable-before-helper')
        boot=observe_reset(link,phases,reset_wait=reset_wait,message=message)
        planning.durable_write(root/'initial-physical-reset-REC.txt',boot)
        state['REC_verified']=True
        recovery_usb(link)
        client=recovery.RecoveryClient(live.LoggedRecoveryStream(link),sleep=pace,
            progress=lambda text:message(text,flush=True))
        state['owner_RAM_restore_required']=True
        checkpoint('before-first-READBACK-upload')
        client.load(readback,live.READBACK_SHA256,REC_observed=True);service_ready=True
        capture=root/'capture';capture.mkdir()
        banks={}
        # Check actual F first; startup text alone is not the exact-F proof.
        for pass_number in (1,2):
            for bank in (3,0,1,2):
                service_ready=False;body=client.flash(bank);service_ready=True
                planning.require(len(body)==32768,'Incomplete bank capture')
                if bank==3:planning.require(body[-4096:]==f_image,'Actual F differs from frozen BASE1')
                if pass_number==2:planning.require(body==banks[bank],'Repeated source bank differs')
                banks[bank]=body
                suffix='' if pass_number==1 else '-repeat'
                planning.durable_write(capture/f'b{bank}{suffix}.bin',body)
                message(f'CAPTURE: B{bank} pass {pass_number} CRC verified; SHA-256 {planning.sha(body)}',flush=True)
        for name,body in original.items():planning.durable_write(capture/name,body)
        identity=dict(schema=1,cpu=cpu,board_model=planning.CPU_MODELS[cpu],source_kind='nf-recovery',
            method='independent-double-read',hardware_capture=bool(link.hardware_access),
            usb_serial=usb_serial,owner_escrow_sha256=planning.sha(planning.encoded(meta)),
            owner_escrow_authority=state['owner_escrow_authority'],owner_RAM_restored=False)
        planning.durable_write(capture/'capture.json',planning.encoded(identity))
        # Snapshot exact inputs to make the fresh derived plan durable and inspectable.
        planning.durable_write(root/'frozen-F.bin',f_image)
        planning.durable_write(root/'engine-template.bin',engine)
        plan_root=root/'plan'
        plan=planning.prepare(capture,root/'frozen-F.bin',plan_root,cpu=cpu,
            source_kind='nf-recovery',provision_cd=provision_cd,history_file=history_file,
            template_file=root/'engine-template.bin')
        planning.inspect(plan_root)
        operations=plan['transaction']['operations']
        planning.require(not operations or [op['address'] for op in operations]==[0xd000,0xc000],
                         'This path permits D then C only; F/opaque destinations are forbidden')
        state.update(completed_noop=plan['transaction']['completed_noop'],
            plan_sha256=planning.sha((plan_root/'plan.json').read_bytes()),
            source_bank_sha256=plan['transaction']['source_sha256'])
        checkpoint('fresh-source-and-CD-only-plan-verified')
        if not execute or not operations:
            message('NO FLASH: '+('existing boot/wear history retained byte-for-byte' if not operations else
                'plan-only run; --execute was not supplied'),flush=True)
            # Fresh independent comparison before returning the promised owner escrow.
            service_ready=False;actual=client.verify_flash(plan['transaction']['source_sha256']);service_ready=True
            state.update(independent_flash_readback_verified=True,final_bank_sha256=actual)
            restore();state['passed']=True
        else:
            # End the RAM service only after the complete plan/intent is durable.
            wrapper,_=module_at('nf_provision_wrapper',ROOT/'migrator/build.py').recovery_loader(
                (plan_root/'migrator.bin').read_bytes())
            planning.require(len(wrapper)==8611 and wrapper[419:]==(plan_root/'migrator.bin').read_bytes(),
                             'Unexpected raw-L relocation wrapper')
            planning.durable_write(root/'rendered-recovery-loader.bin',wrapper)
            planning.durable_write(root/'erase-intent-before-execution.json',(plan_root/'erase-intent.json').read_bytes())
            service_ready=False;client.send(b'Q');client.until(live.REC);client.admitted=False
            recovery_usb(link)
            state['REC_verified']=False
            checkpoint('before-rendered-RAM-preflight-no-flash-authorized')
            client.send(b'L\r');client.until(b'SEND BIN\r\n');client.paced(wrapper)
            preflight=link.until(live.ENGINE_READY,seconds=60)
            planning.require(live.ENGINE_SELF_OK in preflight and live.ENGINE_SOURCE_OK in preflight,
                             'NFM1 self-image/source/chip preflight missing; no Y sent')
            planning.durable_write(root/'engine-preflight.txt',preflight)
            # Durability BEFORE Y is essential: a short write can still authorize erase.
            state['flash_may_have_changed']=True
            checkpoint('CD-flash-authorized-no-automatic-retry')
            link.send(b'Y\r')
            for op in operations:
                marker=f"SEND 4096 BYTES FOR B3:{op['address'] >> 12:X}\r\n".encode('ascii')
                ready=link.until(marker,seconds=60)
                # Reinspect pinned transfers just before delivery, without changing the plan.
                planning.inspect(plan_root)
                body=(plan_root/op['transfer_file']).read_bytes()
                for offset in range(0,4096,64):link.send(body[offset:offset+64]);pace(.01)
                done=link.until(live.ROW_DONE,seconds=60)
                planning.durable_write(root/f"sector-{op['index']:02d}-console.txt",ready+done)
                state['flash_written']=True;checkpoint(f"sector-{op['address']:04X}-device-verified")
            planning.durable_write(root/'engine-complete.txt',link.until(live.ENGINE_DONE,seconds=60))
            state['REC_verified']=False;checkpoint('device-verified-physical-reset-pending')
            boot=observe_reset(link,phases,reset_wait=reset_wait,message=message)
            planning.durable_write(root/'final-physical-reset-REC.txt',boot)
            state['REC_verified']=True;recovery_usb(link)
            client=recovery.RecoveryClient(live.LoggedRecoveryStream(link),sleep=pace,
                progress=lambda text:message(text,flush=True))
            client.load(readback,live.READBACK_SHA256,REC_observed=True)
            actual=[]
            for bank in range(4):
                body=client.flash(bank)
                planning.durable_write(root/f'fresh-post-b{bank}.bin',body)
                planning.require(planning.sha(body)==plan['transaction']['expected_sha256'][bank],
                                 'Independent final bank mismatch; inspect before restoration')
                actual.append(planning.sha(body))
            state.update(independent_flash_readback_verified=True,final_bank_sha256=actual)
            service_ready=True;restore();state['passed']=True
        checkpoint('provisioning-checkpoint')
    except BaseException as error:
        state['failure']=str(error)
        # An admission refusal while the known read-only service is idle can
        # restore escrow safely. Protocol failures/any possible flash mutation
        # stop for inspection instead of guessing the active program or retrying.
        if service_ready and not state['flash_may_have_changed']:
            try:restore()
            except BaseException as restore_error:state['restoration_failure']=str(restore_error)
        checkpoint('inspection-required-no-retry')
        raise
    finally:
        planning.durable_write(root/'result.json',planning.encoded(state))
    return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--usb-serial',required=True)
    parser.add_argument('--cpu',choices=tuple(planning.CPU_MODELS),required=True)
    parser.add_argument('--owner-escrow',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--readback',type=Path,default=ROOT/'firmware/payload/STR8N-F-READBACK-RAM.bin')
    parser.add_argument('--readback-manifest',type=Path,default=ROOT/'firmware/minimal-manifest.json')
    parser.add_argument('--f-image',type=Path,default=ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin')
    parser.add_argument('--engine-template',type=Path,default=ROOT/'migrator/payload/template.bin')
    parser.add_argument('--provision-cd',action='store_true',help='Explicit first-journal conversion; never reinitialize recognized history')
    parser.add_argument('--execute',action='store_true',help='Authorize freshly guarded D/C writes; default is plan/verify/restore only')
    parser.add_argument('--history',type=Path)
    parser.add_argument('--allow-unqualified',action='store_true')
    parser.add_argument('--reset-wait',type=float,default=60)
    args=parser.parse_args(argv)
    if not args.allow_unqualified:parser.exit(2,'REFUSED: --allow-unqualified is required; no port opened.\n')
    try:
        planning.require(args.reset_wait>0,'Positive reset timeout required')
        owner_escrow(args.owner_escrow,cpu=args.cpu,usb_serial=args.usb_serial)
        inputs(args.readback,args.f_image,args.engine_template,args.readback_manifest)
        root=live.private_root(args.out)
        with (root/'serial.jsonl').open('x',encoding='utf-8',newline='\n') as log:
            link=RecoveryLink(args.port,log,usb_serial=args.usb_serial)
            try:
                result=run(link,root,escrow=args.owner_escrow,cpu=args.cpu,usb_serial=args.usb_serial,
                    readback_file=args.readback,f_file=args.f_image,engine_file=args.engine_template,
                    manifest_file=args.readback_manifest,provision_cd=args.provision_cd,execute=args.execute,
                    history_file=args.history,allow_unqualified=True,reset_wait=args.reset_wait)
                print('COMPLETE: '+('C/D provisioning verified' if result['flash_written'] else 'no flash writes')+
                      '; supplied original owner RAM/ZP restored and verified; stopped at REC>.')
            finally:link.close()
    except (KeyError,OSError,ValueError,TimeoutError) as error:
        parser.exit(2,'STOPPED: '+str(error)+'\nRetain private escrow and phases; no automatic replay/reset.\n')


if __name__=='__main__':main()
