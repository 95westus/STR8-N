"""Set 2609 default MON B with one append; preserve images/RAM and counts."""
import json
import install_2512_native_utilities as d

t=d.t
CASE=t.ROOT/'output/qualification/2609-default-MON-B-20261031-r1'
CONFIG=b'RAM CONFIG ? B C I W Q> '


def run():
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    r=dict(board='2609',requested='default 2609 to boot a mon',selected='MON B',
        passed=False,append_requests=0,sector_erases=0,F_writes=0,RTC_writes=0,
        SRAM_writes=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    marker_path=t.ROOT/'output/qualification/device-operations/2609.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    config=(t.REPO/'firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes()
    s=None;borrowed=False;ram=zp=prefix=None;default_verified=False
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(marker_path.read_text());m.update(kw);t.save(marker_path,m)
    def rec():
        if s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with t.serial_lease('2609-owner-requested-default-MON-B',timeout=30):
        marker=json.loads(marker_path.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2609');s.link.send(b'\r');s.until((t.REC,t.MON),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                assert b'g0000000C / MON ' in s.command('VERSION')
                # The qualified readback loader changes only its3078-byte
                # prefix below6700; the service runs at6800. Capture that
                # prefix natively, then read the untouched remainder framed.
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (CASE/'owner-prefix.bin').write_bytes(prefix);(CASE/'owner-zp.bin').write_bytes(zp)
                mark(default_boot_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500)
                assert memory[:len(reader)]==reader and s.client.read(b'Z',0xE0)==zp
                ram=prefix+memory[len(reader):]
                assert len(ram)==0x6500
                (CASE/'owner-ram.bin').write_bytes(ram)
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
                old=s.client.flash(3);(CASE/'B3-before.bin').write_bytes(old)
                assert t.sha(old)==marker['current_physical_bank_sha256']['B3']
                prior=t.classify_journal(old)
                assert prior['sequence']==1051 and prior['valid_records']==21 and prior['default']=='S'
                assert old[0x4500:0x4600]==b'\xff'*256
                assert int.from_bytes(old[0x3008:0x300C],'little')==12
                print('PASS fresh owner escrow; C500 blank; zero-erase default append admitted',flush=True)
                rec();s.load(config,t.sha(config),CONFIG)
                assert b'DEFAULT=S' in s.command('B')
                r['append_requests']=1;save()
                assert b'OK' in s.command('C B')
                assert b'DEFAULT=B' in s.command('B')
                boot=s.command('Q',(t.MON,))
                (CASE/'saved-default-software-startup.txt').write_bytes(boot)
                assert b'g0000000C / MON B' in boot
                r['saved_default_software_boot_passed']=True
                rec();s.service(reader);after=s.client.flash(3)
                latest=t.classify_journal(after)
                assert latest['sequence']==1052 and latest['valid_records']==22 and latest['default']=='B'
                for key in ('counts','unknown_mask','enabled_mask','entries'):assert latest[key]==prior[key]
                assert after[:0x4500]==old[:0x4500] and after[0x4600:]==old[0x4600:]
                assert after[0x4512:0x4516]==(12).to_bytes(4,'little')
                (CASE/'B3-after.bin').write_bytes(after)
                r.update(journal=latest,final_B3_sha256=t.sha(after),saved_B_generation='0000000C',
                    old_records_retained_exact=21)
                default_verified=True
                print('PASS C500/seq1052 default B/gC; all counts and21 old records preserved',flush=True)
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500)
                            assert memory[:len(reader)]==reader
                            ram=prefix+memory[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['COM8_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields=dict(default_boot_worker_active=False,application_RAM_restore_pending=not restored,
                            application_ram_restored=restored,
                            block_snapshot=marker['block_snapshot'] if restored else True,
                            last_default_boot_change=str(CASE/'report.json'))
                        if default_verified:
                            hashes=marker['current_physical_bank_sha256'].copy();hashes['B3']=r['final_B3_sha256']
                            fields.update(current_physical_bank_sha256=hashes,saved_default='B',
                                saved_default_generation='0000000C',final_prompt='B3>',
                                rtc_prompt_adapter_worker_active=True,
                                current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256'])
                        mark(**fields)
                    save()
    r['passed']=default_verified and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print('PASS 2609 default B; owner RAM/ZP restored; COM8 released',flush=True)


if __name__=='__main__':run()
