"""Set board-name metadata and CLOCK display offset; never set RTC time."""
import binascii
import json
import re
import time
from datetime import datetime
import install_2512_native_utilities as d

t=d.t
CASE=t.ROOT/'output/qualification/2609-name-offset-20261031-r1'
CONFIRM=b'Type YES to confirm: '


def metadata(magic,payload):
    row=bytearray(b'\xff'*32)
    row[:4]=magic+bytes((1,0));row[4:8]=(1).to_bytes(4,'little')
    row[8:8+len(payload)]=payload
    row[28:30]=binascii.crc_hqx(row[:28],65535).to_bytes(2,'little')
    row[31]=0
    return bytes(row)


def status(out):
    raw=bytes.fromhex(re.search(rb'RTC registers \(raw\):((?: [0-9A-F]{2}){9})',out)[1].decode())
    trim=int(re.search(rb'Trim (-?\d+) steps',out)[1])
    calendar=datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',out)[1].decode(),'%Y-%m-%d %H:%M:%S')
    return raw,trim,calendar


def run():
    admission=json.loads((t.ROOT/'output/qualification/2609-live-metadata-admission-20261031-r2/report.json').read_text())
    assert admission['passed'] and admission['native_history_code_verified']
    assert admission['golden_F_verified'] and admission['proposed_record_bytes']==64
    assert admission['metadata_window']=='B3:9C00-9FFF;1024 bytes blank FF'
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    r=dict(board='2609',requested_name='2609',requested_offset='-05:00',passed=False,
        sector_erases=0,F_writes=0,boot_journal_writes=0,RTC_SET=0,trim_writes=0,
        PF_ACK=0,RTC_history_writes=0,SRAM_data_writes=0,power_cuts=0,
        name_commit_requests=0,offset_confirmation_requests=0,
        owner_RAM_restored=False,owner_ZP_restored=False)
    path=t.ROOT/'output/qualification/device-operations/2609.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    name=metadata(b'BN',bytes((4,))+b'2609'+bytes(4))
    zone=metadata(b'TZ',(-300).to_bytes(2,'little',signed=True))
    (CASE/'BN-record.bin').write_bytes(name);(CASE/'TZ-record.bin').write_bytes(zone)
    s=None;borrowed=False;ram=zp=prefix=None;verified=False;current3=None
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(path.read_text());m.update(kw);t.save(path,m)
    def rec():
        if s.context==CONFIRM:s.command('NO',(t.CLOCK,))
        if s.context==t.CLOCK:s.command('Q',(t.MON,))
        if s.context==t.MON:s.command('Q',(t.REC,))
        elif s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        assert s.context==t.REC,'Unknown state: no blind recovery command'
    def checked(cmd):
        out=s.command(cmd)
        assert b'REFUSED' not in out and b'Invalid command' not in out and b'failed' not in out.lower(),out
        return out
    save()
    with t.serial_lease('2609-owner-requested-name-and-display-offset',timeout=30):
        marker=json.loads(path.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                assert b'g0000000C / MON B' in s.command('VERSION')
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (CASE/'owner-prefix.bin').write_bytes(prefix);(CASE/'owner-zp.bin').write_bytes(zp)
                mark(metadata_settings_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500)
                assert memory[:len(reader)]==reader and s.client.read(b'Z',0xE0)==zp
                ram=prefix+memory[len(reader):];assert len(ram)==0x6500
                (CASE/'owner-ram.bin').write_bytes(ram)
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
                before=s.client.flash(3);(CASE/'B3-before.bin').write_bytes(before)
                assert t.sha(before)==marker['current_physical_bank_sha256']['B3']
                assert t.sha(before)==admission['B3_sha256']
                native=(t.REPO/'monitors/candidates/native-g00000001-r16/RTC-HISTORY-B3-9000.bin').read_bytes()
                assert before[0x1000:0x1C00]==native[:3072]
                assert binascii.crc_hqx(before[0x1000:0x1C00],65535)==0
                assert before[0x1C00:0x2000]==b'\xff'*1024
                prior=t.classify_journal(before)
                assert prior['default']=='B' and prior['sequence']==1052 and prior['valid_records']==22
                rec();s.command('B',(t.MON,));s.command('R CLOCK',(t.CLOCK,))
                first=s.command('STATUS');(CASE/'STATUS-before.txt').write_bytes(first)
                raw0,trim0,date0=status(first);mono0=time.monotonic()
                history0=s.command('HISTORY');assert b'History unavailable/error' not in history0
                (CASE/'HISTORY-before.txt').write_bytes(history0)
                s.command('Q',(t.MON,));cache0=s.dump(0x6B00,0x6B7F)
                (CASE/'RTC-EEPROM-history-before.bin').write_bytes(cache0)
                print('PASS fresh RAM escrow, empty metadata pocket, RTC status/history captured',flush=True)
                # The installed tool has a BN reader, not a NAME writer. Use
                # its existing guarded1->0 monitor operation for this one
                # explicitly requested BN record. Verify payload, commit last.
                assert s.dump(0x9C00,0x9C1F)==b'\xff'*32
                for off in range(0,31,8):
                    part=name[off:min(off+8,31)]
                    checked(f'!M {0x9C00+off:04X} '+part.hex(' ').upper())
                assert s.dump(0x9C00,0x9C1F)==name[:31]+b'\xff'
                r['name_commit_requests']=1;save()
                checked('!M 9C1F 00');assert s.dump(0x9C00,0x9C1F)==name
                print('PASS board name2609 committed at B3:9C00',flush=True)
                opening=s.command('R CLOCK',(t.CLOCK,))
                assert b'Board: 2609' in opening
                s.command('OFFSET -05:00',(CONFIRM,))
                r['offset_confirmation_requests']=1;save()
                out=s.command('YES',(t.CLOCK,))
                assert b'Local UTC offset: -05:00' in out and b'not saved' not in out
                local=s.command('TIME');assert b'(-05:00)' in local and b'UTC:' in local
                (CASE/'TIME-local-and-UTC.txt').write_bytes(local)
                last=s.command('STATUS');(CASE/'STATUS-after.txt').write_bytes(last)
                raw1,trim1,date1=status(last);mono1=time.monotonic()
                assert trim1==trim0 and raw1[7:9]==raw0[7:9]
                assert raw1[3:]==raw0[3:],'Calendar date/weekday/flags/control/trim must stay stable'
                assert raw1[0]&0x80==raw0[0]&0x80 and raw1[2]&0x40==raw0[2]&0x40
                assert abs((date1-date0).total_seconds()-(mono1-mono0))<2.5,'UTC must advance naturally; no time jump'
                history1=s.command('HISTORY');assert history1==history0
                (CASE/'HISTORY-after.txt').write_bytes(history1)
                s.command('Q',(t.MON,));cache1=s.dump(0x6B00,0x6B7F)
                assert cache1==cache0
                (CASE/'RTC-EEPROM-history-after.bin').write_bytes(cache1)
                version=s.command('VERSION');assert b'Board: 2609' in version and b'(-05:00)' in version
                (CASE/'VERSION-after.txt').write_bytes(version)
                rec();s.service(reader);current3=s.client.flash(3)
                expected=bytearray(before);expected[0x1C00:0x1C20]=name;expected[0x1C20:0x1C40]=zone
                assert current3==expected,'Only the two requested metadata records may change'
                assert t.classify_journal(current3)==prior
                (CASE/'B3-after.bin').write_bytes(current3)
                r.update(metadata_records=['B3:9C00 BN seq1','B3:9C20 TZ seq1'],
                    final_B3_sha256=t.sha(current3),journal=prior,RTC_trim=trim1,RTC_control=raw1[7],
                    RTC_PF_latched=bool(raw1[3]&0x10),RTC_history_sha256=t.sha(cache1),
                    UTC_advance_seconds=(date1-date0).total_seconds(),elapsed_seconds=mono1-mono0,
                    raw_RTC_settings_preserved=True,raw_RTC_history_preserved=True,
                    boot_journal_byte_identical=True,F_byte_identical=True)
                verified=True;print('PASS name/offset displayed; only two32-byte metadata records written; RTC and boot history preserved',flush=True)
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                            ram=prefix+memory[len(reader):]
                        if current3 is None:current3=s.client.flash(3)
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['COM8_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields=dict(metadata_settings_worker_active=False,
                            application_RAM_restore_pending=not restored,application_ram_restored=restored,
                            block_snapshot=marker['block_snapshot'] if restored else True,
                            last_name_offset_change=str(CASE/'report.json'),final_prompt='B3>' if restored else None)
                        if current3 is not None:
                            hashes=marker['current_physical_bank_sha256'].copy();hashes['B3']=t.sha(current3)
                            fields['current_physical_bank_sha256']=hashes
                        if verified:
                            fields.update(board_name='2609',display_offset_minutes=-300,
                                metadata_settings_update_complete=restored,current_owner_RAM_sha256=r['RAM_sha256'],
                                current_owner_ZP_sha256=r['ZP_sha256'])
                        mark(**fields)
                    save()
    r['passed']=verified and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print('PASS 2609 name2609 / -05:00; zero erases; owner RAM restored; COM8 free',flush=True)


if __name__=='__main__':run()
