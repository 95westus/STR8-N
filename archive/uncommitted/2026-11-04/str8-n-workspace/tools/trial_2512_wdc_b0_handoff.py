"""RAM-only entry to the pinned B0 WDC debugger and public-HOLD return; no flash."""
import argparse
import json
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as files

t=p.t
SCOPE=t.ROOT/'output/qualification/2512-WDC-B0-handoff-scope-20261030-r1'
PLAN_SHA='767d09a0aa7381e4c9969a8f6090e8fc29e20b36448b2cd980259f63e94f1bad'
SERVICE=b'RAM SERVICE BASE1> '
WDC=b'PRIVATE-WDC-PROTOCOL'


def run(folder):
    folder=folder.resolve()
    assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    assert t.sha((SCOPE/'plan.json').read_bytes())==PLAN_SHA
    plan=json.loads((SCOPE/'plan.json').read_text())
    entry=(SCOPE/'entry-3000.bin').read_bytes();ret=(SCOPE/'return-2000-8192.bin').read_bytes()
    assert len(entry)==21 and t.sha(entry)==plan['entry_sha256']
    assert len(ret)==8192 and t.sha(ret)==plan['return_sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader)==t.live.READBACK_SHA256
    folder.mkdir(parents=True);(folder/'.gitignore').write_text('*\n')
    files.durable_file(folder/'reviewed-plan.json',(SCOPE/'plan.json').read_bytes())
    files.durable_file(folder/'trial-driver.py',Path(__file__).read_bytes())
    r=dict(schema=1,board='2512',CPU='65C02',passed=False,started_utc=t.utc(),checks=[],
        flash_writes=0,journal_writes=0,boot_setting_writes=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,assembler_invocations=0,CPU_simulations=0,
        serial_port_opened=False,owner_RAM_restored=False,owner_ZP_restored=False,owner_RAM_restore_pending=False,
        WDC_debugger_entered=False,public_HOLD_return=False,physical_WDC_boot_qualified=False,
        Foundation_default_WDC_boot_qualified=False,new_NFM2_engine_executed=False,full_factory_migration_qualified=False,
        plan_sha256=PLAN_SHA,source_bank_sha256=plan['source_bank_sha256'])
    s=None;marker=None;borrowed=False;ram=zp=None
    def save():t.save(folder/'report.json',r)
    def mark(**fields):
        m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
    def check(label):
        r['checks'].append(label);save();print('PASS '+label,flush=True)
    def rec():
        if s.context==SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:
            assert s.context==t.MON,'No native context: keep power and original escrow; physical RESET recovery required'
            s.rec()
    def verify(label):
        if s.context!=SERVICE:rec();s.service(reader)
        for repeat in (1,2):
            for n in range(4):
                body=s.client.flash(n)
                files.durable_file(folder/f'{label}-pass{repeat}-B{n}.bin',body)
                assert t.sha(body)==plan['source_bank_sha256'][n],f'Unexpected B{n} mutation'
    save()
    try:
        print('WAIT: shared serial lease; no port opened',flush=True)
        with t.serial_lease('2512-RAM-only-WDC-B0-handoff',timeout=300):
            marker=json.loads(t.MARK.read_text())
            assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
            assert not marker['block_snapshot'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
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
                    check('fresh-native-owner-double-escrow')
                    borrowed=True;r['owner_RAM_restore_pending']=True;save()
                    mark(WDC_B0_handoff_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    rec();t.transport.recovery_usb(s.link);verify('before')
                    b0=(folder/'before-pass1-B0.bin').read_bytes()
                    assert t.sha(b0[-4096:])==plan['vendor_F_sha256']
                    assert b0[0x78a6:0x78b1]==bytes.fromhex('78 d8 a2 ff 9a 20 f4 f9 c9 55 d0')
                    check('all-bank-double-admission-and-pinned-WDC-entry')
                    s.client.restore_owner(ram,zp);s.context=t.REC;s.monitor()
                    s.modify(0x3000,entry);assert s.dump(0x3000,0x3000+len(entry)-1)==entry
                    check('21-byte-RAM-entry-bridge-readback')
                    original_protocol=s.link.protocol
                    def guarded_protocol(command):
                        assert command in (2,3,6),'Unadmitted WDC command; no flash or auto-app command permitted'
                        return original_protocol(command)
                    s.link.protocol=guarded_protocol
                    s.link.set_stock_handshake(True)
                    s.link.send(b'G 3000\r');s.context=None
                    identity=s.link.identity_after_reset(seconds=20)  # Sync only; this method never resets the CPU.
                    t.live.verify_identity(identity,'65c02',bytes.fromhex(plan['vendor_identity_hex']))
                    s.context=WDC;r.update(WDC_debugger_entered=True,WDC_identity_hex=identity.hex());save()
                    for repeat in (1,2):
                        body=s.link.stock_read(0x8000,32768)
                        files.durable_file(folder/f'WDC-visible-B0-pass{repeat}.bin',body)
                        assert body==b0,'WDC visible bank is not the preserved B0'
                    check('WDC-SXB2-identity-and-visible-B0-double-read')
                    s.link.load_ram(ret,0x2000)
                    assert s.link.loaded==(t.sha(ret),0x2000)
                    check('WDC-RAM-upload-all-chunks-and-full-image-readback')
                    s.context=None;s.link.execute_ram(0x2000);s.link.set_stock_handshake(False)
                    face=s.until((t.MON,t.REC),seconds=30)
                    files.durable_file(folder/'public-HOLD-return.txt',face)
                    assert s.context==t.MON and b'g00000008 / MON B' in face and b'CPU $02' in face
                    r['public_HOLD_return']=True;check('B3-public-F007-HOLD-return-to-MON-B')
                    rec();t.transport.recovery_usb(s.link);verify('after')
                    r['all_flash_banks_and_journal_unchanged']=True
                    check('independent-all-bank-double-postimages-unchanged')
                finally:
                    try:
                        if borrowed:
                            rec();s.service(reader)
                            result=s.client.restore_owner(ram,zp)
                            assert result['owner_RAM_restored'] and result['owner_ZP_restored']
                            s.context=t.REC;s.monitor();assert s.owner()==(ram,zp)
                            r.update(owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_restore_pending=False)
                    finally:
                        if s is not None:
                            s.link.close();r['COM4_released']=True
                            r['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            restored=r['owner_RAM_restored'] if borrowed else marker['application_ram_restored']
                            mark(WDC_B0_handoff_worker_active=False,application_ram_restored=restored,
                                application_RAM_restore_pending=borrowed and not r['owner_RAM_restored'],
                                block_snapshot=marker['block_snapshot'] if restored else True,
                                last_WDC_B0_handoff_report=str(folder/'report.json'))
                        save()
        assert r['WDC_debugger_entered'] and r['public_HOLD_return'] and r['all_flash_banks_and_journal_unchanged']
        assert r['owner_RAM_restored'] and r['COM4_released']
        r.update(passed=True,phase='WDC_DEBUGGER_HANDOFF_PASSED_PHYSICAL_BOOT_STILL_OPEN',finished_utc=t.utc());save()
        t.save(folder/'final-receipt.json',r)
        mark(last_WDC_B0_handoff_preservation_receipt=str(folder/'final-receipt.json'))
        print('PASS WDC B0 debugger entry and public-HOLD return; all flash/journal and owner RAM preserved; COM4 released',flush=True)
    except BaseException as error:
        r.update(error=repr(error),finished_utc=t.utc());save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--execute-RAM-only-handoff',action='store_true')
    args=parser.parse_args()
    if not args.execute_RAM_only_handoff:parser.error('Explicit RAM-only execution switch required')
    run(args.folder)
