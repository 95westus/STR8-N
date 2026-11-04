"""Read-only proof of the live post-upgrade metadata layout; no flash writer."""
import binascii
import argparse
import json
import install_2512_native_utilities as d

t=d.t
CASE=t.ROOT/'output/qualification/2609-live-metadata-admission-20261031-r1'


def run():
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    path=t.ROOT/'output/qualification/device-operations/2609.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    native=(t.REPO/'monitors/candidates/native-g00000001-r16/RTC-HISTORY-B3-9000.bin').read_bytes()
    r=dict(board='2609',passed=False,flash_writes=0,F_writes=0,RTC_writes=0,
        source='Live readback after approved native-profile installation and default-B change',
        owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=prefix=None;verified=False
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(path.read_text());m.update(kw);t.save(path,m)
    def rec():
        if s.context==t.MON:s.command('Q',(t.REC,))
        elif s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        assert s.context==t.REC
    save()
    with t.serial_lease('2609-live-metadata-readonly-admission',timeout=30):
        marker=json.loads(path.read_text());assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (CASE/'owner-prefix.bin').write_bytes(prefix);(CASE/'owner-zp.bin').write_bytes(zp)
                borrowed=True;mark(metadata_admission_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500)
                assert memory[:len(reader)]==reader and s.client.read(b'Z',0xE0)==zp
                ram=prefix+memory[len(reader):];(CASE/'owner-ram.bin').write_bytes(ram)
                b3=s.client.flash(3);(CASE/'B3-current.bin').write_bytes(b3)
                assert t.sha(b3)==marker['current_physical_bank_sha256']['B3']
                assert b3[0x1000:0x1C00]==native[:3072]
                assert binascii.crc_hqx(b3[0x1000:0x1C00],65535)==0
                assert b3[0x1C00:0x2000]==b'\xff'*1024
                assert b3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
                r.update(B3_sha256=t.sha(b3),native_history_code_verified=True,
                    metadata_window='B3:9C00-9FFF;1024 bytes blank FF',
                    proposed_record_addresses=['B3:9C00-9C1F','B3:9C20-9C3F'],
                    proposed_record_bytes=64,proposed_erase_count=0,
                    history_code_window='B3:9000-9BFF; sealed native candidate exact',
                    legacy_code_superseded_by_approved_install=True,golden_F_verified=True)
                verified=True
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                            ram=prefix+memory[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['COM8_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        mark(metadata_admission_worker_active=False,application_RAM_restore_pending=not restored,
                            application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                            last_live_metadata_admission=str(CASE/'report.json'))
                    r['passed']=verified and r['owner_RAM_restored'] and r['owner_ZP_restored'];save()
    print(json.dumps(r,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=str)
    args=parser.parse_args()
    if args.out:
        CASE=(t.ROOT/args.out).resolve()
        assert CASE.is_relative_to(t.ROOT/'output/qualification')
    run()
