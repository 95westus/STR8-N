"""Two-erase B0 launcher trial: saved default, one physical RESET, full restoration."""
import argparse
import json
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as files

t=p.t
SCOPE=t.ROOT/'output/qualification/2512-WDC-default-boot-scope-20261030-r1'
PLAN_SHA='281edb36ae09cbe76806a055630f4131990da20dd4563c3b6eeb5757a6f25a40'
SERVICE=b'RAM SERVICE BASE1> '
CONFIG=b'RAM CONFIG ? B C I W Q> '
WDC=b'PRIVATE-WDC-PROTOCOL'
BANNER=b'WDC B0 / BASE1 DEFAULT BOOT\r\n'


def run(folder):
    folder=folder.resolve()
    assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    assert t.sha((SCOPE/'plan.json').read_bytes())==PLAN_SHA
    plan=json.loads((SCOPE/'plan.json').read_text())
    assert plan['total_sector_erases']==2 and plan['journal_appends']==4
    assert plan['F_writes']==plan['C_D_erases']==0 and plan['all_24_original_records_retained']
    manifest=json.loads((t.REPO/'firmware/minimal-manifest.json').read_text())
    packets={key:(t.REPO/'firmware/payload'/name).read_bytes() for key,name in
             [('reader','STR8N-F-READBACK-RAM.bin'),('writer','STR8N-F-OPAQUE-RAM.bin'),('config','STR8N-F-CONFIG-RAM.bin')]}
    hashes={key:manifest['artifacts'][name]['sha256'] for key,name in
            [('reader','STR8N-F-READBACK-RAM.bin'),('writer','STR8N-F-OPAQUE-RAM.bin'),('config','STR8N-F-CONFIG-RAM.bin')]}
    for key in packets:assert t.sha(packets[key])==hashes[key]
    assert hashes['reader']==t.live.READBACK_SHA256
    original=(SCOPE/'original-B0-8000-4096.bin').read_bytes()
    launcher=(SCOPE/'WDC-B0-8000-4096.bin').read_bytes();ret=(SCOPE/'return-RESET-2000-8192.bin').read_bytes()
    assert t.sha(original)==plan['original_sector_sha256']
    assert t.sha(launcher)==plan['launcher']['image_sha256'] and len(launcher)==4096
    assert t.sha(ret)==plan['launcher']['return_packet_sha256'] and len(ret)==8192
    for step in plan['steps']:
        assert [t.sha((SCOPE/f"{step['name']}-expected-B{n}.bin").read_bytes()) for n in range(4)]==step['after_sha256']
    folder.mkdir(parents=True);(folder/'.gitignore').write_text('*\n')
    files.durable_file(folder/'reviewed-plan.json',(SCOPE/'plan.json').read_bytes())
    files.durable_file(folder/'trial-driver.py',Path(__file__).read_bytes())
    files.durable_file(folder/'original-B0-8000-4096.bin',original)
    r=dict(schema=1,board='2512',CPU='65C02',passed=False,started_utc=t.utc(),phase='FRESH_ADMISSION',checks=[],
        plan_sha256=PLAN_SHA,erase_requests=0,erases_completed=0,settings_requests=0,
        flash_restore_pending=False,boot_policy_restore_pending=False,owner_RAM_restore_pending=False,
        owner_RAM_restored=False,owner_ZP_restored=False,serial_port_opened=False,
        physical_resets_observed=0,software_foundation_restarts=0,F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,
        SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,
        assembler_invocations=1,F_rebuilt=False,CPU_simulations=0,physical_default_boot_verified=False,
        WDC_debugger_verified=False,vendor_F818_reset_executed=False,new_NFM2_engine_executed=False,
        full_factory_migration_qualified=False,source_bank_sha256=plan['source_bank_sha256'])
    s=None;marker=None;borrowed=False;ram=zp=None
    def save():t.save(folder/'report.json',r)
    def mark(**fields):
        m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
    def check(label):
        r['checks'].append(label);save();print('PASS '+label,flush=True)
    def rec():
        if s.context==SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==files.PROMPT:
            s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        elif s.context==CONFIG:
            s.link.send(b'Q\r');s.context=None;recovery_after_restart('cleanup-config')
        elif s.context!=t.REC:
            assert s.context==t.MON,'Unknown protocol context; keep power and escrow; RESET recovery requires an armed receiver'
            s.rec()
    def verify(stage,label,double=False):
        expected=plan['source_bank_sha256'] if stage=='source' else next(v['after_sha256'] for v in plan['steps'] if v['name']==stage)
        if s.context!=SERVICE:rec();s.service(packets['reader'])
        for repeat in range(1,3 if double else 2):
            for n in range(4):
                body=s.client.flash(n);files.durable_file(folder/f'{label}-pass{repeat}-B{n}.bin',body)
                assert t.sha(body)==expected[n],f'Unexpected B{n} state; no further mutation'
    def recovery_after_restart(label):
        face=s.link.until(t.transport.CHOICES,seconds=30)
        assert t.transport.IDENTITY in face
        s.link.send(b'S');s.until((t.REC,),seconds=30)
        files.durable_file(folder/f'{label}-Foundation-recovery.txt',face)
        r['software_foundation_restarts']+=1;save()
    def replace(stage,before,target):
        assert r['erase_requests']<2
        rec();t.transport.recovery_usb(s.link);s.load(packets['writer'],hashes['writer'],files.PROMPT)
        wire=files.Wire(s.link.serial,timeout=60,trace=log,progress=lambda text:print(text,flush=True))
        assert wire.read_sector(0,0x80)==before
        files.durable_file(folder/f'{stage}-preimage.bin',before)
        r.update(erase_requests=r['erase_requests']+1,flash_restore_pending=True,phase='WRITING_'+stage.upper());save()
        mark(WDC_default_flash_restore_pending=True);s.context=None
        assert not wire.replace_sector(0,0x80,before,target)
        s.context=files.PROMPT;assert wire.read_sector(0,0x80)==target
        rec();verify(stage,stage)
        r['erases_completed']+=1;check(stage+'-sector-and-all-bank-postimages')
    def config(target,stage):
        rec();t.transport.recovery_usb(s.link);s.load(packets['config'],hashes['config'],CONFIG)
        shown=s.command('B',(CONFIG,));assert b'B0 ON  ENTRY=8000' in shown
        assert r['settings_requests']<2
        r.update(settings_requests=r['settings_requests']+1,boot_policy_restore_pending=True,phase='SAVING_DEFAULT_'+target);save()
        mark(WDC_default_boot_policy_restore_pending=True)
        out=s.command('C '+target,(CONFIG,));assert b'OK\r\n' in out and b'REFUSED' not in out
        s.link.send(b'Q\r');s.context=None;recovery_after_restart(stage)
        verify(stage,stage)
        if target=='B':
            r['boot_policy_restore_pending']=False;save();mark(WDC_default_boot_policy_restore_pending=False)
        check('saved-default-'+target+'-verified')
    save()
    try:
        print('WAIT: shared serial lease; no port opened',flush=True)
        with t.serial_lease('2512-WDC-default-boot-two-erases',timeout=300):
            marker=json.loads(t.MARK.read_text())
            assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==plan['source_bank_sha256']
            t.save(folder/'marker-before.json',marker)
            with (folder/'serial.jsonl').open('x',encoding='utf-8') as log:
                try:
                    s=p.Session(folder,log,'2512');r['serial_port_opened']=True;save()
                    s.link.send(b'\r');s.until((t.MON,),seconds=15)
                    face=s.command('V');assert b'g00000008 / MON B' in face and b'CPU $02' in face
                    ram,zp=s.owner();assert s.owner()==(ram,zp)
                    files.durable_file(folder/'owner-ram.bin',ram);files.durable_file(folder/'owner-zp.bin',zp)
                    r.update(RAM_sha256=t.sha(ram),ZP_sha256=t.sha(zp),native_owner_double_escrow=True)
                    borrowed=True;r['owner_RAM_restore_pending']=True;save()
                    mark(WDC_default_boot_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    check('fresh-native-owner-double-escrow')
                    rec();t.transport.recovery_usb(s.link);verify('source','before',double=True)
                    b0=(folder/'before-pass1-B0.bin').read_bytes()
                    assert t.sha(b0[-4096:])==plan['launcher']['vendor_F_sha256']
                    for n in range(4):files.durable_file(folder/f'live-original-B{n}.bin',(folder/f'before-pass1-B{n}.bin').read_bytes())
                    check('all-bank-double-admission-and-pinned-vendor-ROM')
                    replace('installed',original,launcher)
                    config('0','default0')
                    s.client.restore_owner(ram,zp);s.context=t.REC
                    r.update(phase='PHYSICAL_RESET_REQUIRED',preboot_owner_RAM_restored=True,
                             startup_log_start=log.tell());save()
                    mark(physical_reset_pending=True)
                    files.durable_file(folder/'reset-request.json',t.live.planning.encoded(dict(
                        ready=True,board='2512',purpose='Saved-default WDC boot',
                        message='Press only 2512 physical RESET; keep USB connected; press no chooser key; let countdown finish')))
                    print('READY: PRESS ONLY 2512 RESET; NO CHOOSER KEY; SAVED DEFAULT 0',flush=True)
                    s.context=None
                    boot=s.link.until(BANNER,seconds=1200)
                    r['startup_log_end']=log.tell()
                    assert t.transport.IDENTITY in boot and t.transport.CHOICES in boot
                    assert b'Boot : 6 5 4 3 2 1 0' in boot
                    files.durable_file(folder/'physical-default-boot.txt',boot)
                    r.update(physical_resets_observed=1,physical_default_boot_verified=True,
                             phase='WDC_DEFAULT_BOOT_OBSERVED',host_chooser_keys_during_physical_boot=0);save()
                    mark(physical_reset_pending=False)
                    s.link.set_stock_handshake(True)
                    original_protocol=s.link.protocol
                    def guarded_protocol(command):
                        assert command in (2,3,6),'Unadmitted WDC operation'
                        return original_protocol(command)
                    s.link.protocol=guarded_protocol
                    identity=s.link.identity_after_reset(seconds=20)  # Protocol probe, no CPU reset.
                    t.live.verify_identity(identity,'65c02',bytes.fromhex('535842322c010000c8000000'))
                    s.context=WDC;r.update(WDC_debugger_verified=True,WDC_identity_hex=identity.hex());save()
                    expected=(SCOPE/'default0-expected-B0.bin').read_bytes()
                    for repeat in (1,2):
                        body=s.link.stock_read(0x8000,32768)
                        files.durable_file(folder/f'WDC-default-visible-B0-pass{repeat}.bin',body);assert body==expected
                    check('physical-saved-default-boot-and-WDC-debugger-visible-B0')
                    s.link.load_ram(ret,0x2000);assert s.link.loaded==(t.sha(ret),0x2000)
                    r['WDC_return_RAM_readback_verified']=True;save()
                    s.context=None;s.link.execute_ram(0x2000);s.link.set_stock_handshake(False)
                    recovery_after_restart('WDC-return')
                    r['public_RESET_return_verified']=True;check('WDC-public-RESET-return-to-recovery')
                    verify('default0','after-WDC')
                    config('B','defaultB')
                    assert not r['boot_policy_restore_pending']
                    replace('restored',launcher,original)
                    verify('restored','final',double=True)
                    final=t.classify_journal((folder/'final-pass1-B3.bin').read_bytes());assert final==plan['final_journal']
                    r.update(flash_restore_pending=False,original_B0_restored=True,all_24_original_journal_records_retained=True,
                             final_bank_sha256=plan['expected_final_bank_sha256'],final_journal=final);save()
                    mark(WDC_default_flash_restore_pending=False)
                    check('original-FLASH-and-boot-policy-restored-24-records-retained')
                finally:
                    try:
                        if borrowed:
                            rec();s.service(packets['reader'])
                            restored=s.client.restore_owner(ram,zp)
                            assert restored['owner_RAM_restored'] and restored['owner_ZP_restored']
                            s.context=t.REC;s.monitor();assert s.owner()==(ram,zp)
                            r.update(owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_restore_pending=False)
                    finally:
                        if s is not None:
                            s.link.close();r['COM4_released']=True
                            r['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            good=r['owner_RAM_restored'] and not r['flash_restore_pending'] and not r['boot_policy_restore_pending']
                            mark(WDC_default_boot_worker_active=False,application_ram_restored=r['owner_RAM_restored'] if borrowed else marker['application_ram_restored'],
                                application_RAM_restore_pending=borrowed and not r['owner_RAM_restored'],
                                block_snapshot=marker['block_snapshot'] if good or not borrowed else True,
                                last_WDC_default_boot_report=str(folder/'report.json'))
                        save()
        assert r['physical_default_boot_verified'] and r['WDC_debugger_verified'] and r['public_RESET_return_verified']
        assert r['owner_RAM_restored'] and r['erases_completed']==r['erase_requests']==2 and r['settings_requests']==2
        r.update(passed=True,phase='SAVED_DEFAULT_WDC_LAUNCHER_BOOT_PASSED_RESTORED',finished_utc=t.utc());save()
        t.save(folder/'final-receipt.json',r)
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),plan['expected_final_bank_sha256'])),
             current_full_flash_sha256=t.sha(b''.join((SCOPE/f'restored-expected-B{n}.bin').read_bytes() for n in range(4))),
             current_journal_sequence=1041,current_journal_valid_records=28,
             current_tracked_erase_counts=dict(marker['current_tracked_erase_counts'],**{'B0:8':10}),
             last_WDC_default_boot_preservation_receipt=str(folder/'final-receipt.json'))
        print('PASS saved-default WDC boot; original FLASH/B default/RAM restored; F golden; COM4 released',flush=True)
    except BaseException as error:
        r.update(error=repr(error),finished_utc=t.utc());save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--execute-reviewed-two-erases',action='store_true')
    args=parser.parse_args()
    if not args.execute_reviewed_two_erases:parser.error('Explicit two-erase execution switch required')
    run(args.folder)
