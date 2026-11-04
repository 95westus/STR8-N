"""Remaining approved PROGRAM test only; the14 flash erases are exhausted."""
import binascii,json,re
from pathlib import Path
from storage_release_trial_2512 import *
from storage_large_source import source_packet
from trial_storage_batch_auto_positive_2512 import allocation
OUT=Q/'2512-storage-large-return-continuation-20261101-r1'


def carry_auto():
    r=json.loads((POS/'report.json').read_text())
    assert r['flash_erase_requests']==3 and r['B0_restored'] and not r['SPI_restore_pending']
    assert r['NVM_verified'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    assert r['error']=='AssertionError()' and 'wide-AUTO-at9000-source-preserved-exact-SR01-commit-and-payload' in r['checks']
    table=next(POS.glob('*-TABLE_0.txt')).read_bytes();restore=next(POS.glob('*-RESTORE_0_LGFA_L.txt')).read_bytes()
    assert b'B0:9000 + 4E00 1900 LGFA' in table and b'B0:A918 + 1000 0008 TAIL4' in table
    assert b'Flash record OK' in restore and b'B0> ' in restore
    events=[json.loads(line) for line in (POS/'serial.jsonl').read_text().splitlines()]
    rx=b''.join(bytes.fromhex(e['hex']) for e in events if e.get('direction')=='RX')
    target=b'SR\x01\x3F'+bytes.fromhex('00 10 08 00')+b'TAIL4'.ljust(16,b'\0')+b'TAIL4G4\0'
    pages=[part[:4096] for part in rx.split(opaque.READ_READY)[1:] if len(part)>=4098 and binascii.crc_hqx(part[:4096],65535)==int.from_bytes(part[4096:4098],'little') and part[0x918:0x938]==target]
    assert pages and all(page==pages[0] for page in pages)
    return dict(report=str(POS/'report.json'),report_sha256=t.sha((POS/'report.json').read_bytes()),
        tail_sector_sha256=t.sha(pages[0]),tail_at='B0:A918',table_passed=True,wide_RESTORE_acknowledged=True,
        limitation='New exact RAM readback after flash load-only Restore was not completed: host required B3 prompt while TABLE selected B0. Prior exact flash-Restore acceptance remains separate.',
        no_flash_test_repeated=True),pages[0]


def run():
    p=approved();ir=json.loads((INST/'report.json').read_text());assert ir['passed'] and ir['owner_RAM_restored'] and ir['owner_ZP_restored']
    carried,tail=carry_auto();expected,_=forecast_install(p);expected[3]=(SCOPE/'B3-final-predicted.bin').read_bytes()
    fixture=(SCOPE/'STORAGE-LARGE-RESTORER.bin').read_bytes();assert t.sha(fixture)==p['SPI_temporary']['restorer_sha256']
    packet,program=source_packet(True);blocks=[0x140]+list(range(0x9800,0xB800,64))
    with Trial(OUT,'2512-approved-PROGRAM-only-large-return',expected,360) as x:
        (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'carried-AUTO-tail-sector.bin').write_bytes(tail)
        (OUT/'PROGRAM-source-packet.bin').write_bytes(packet);(OUT/'PROGRAM-source.bin').write_bytes(program)
        x.r.update(carried_AUTO=carried,erase_allowance_remaining=0,SPI_restore_pending=False,SPI_restored=False,temporary_PROGRAM_bytes=8256)
        def no_flash(*args,**kw):raise RuntimeError('All14 reviewed flash erases are spent; PROGRAM-only continuation')
        x.replace=no_flash;x.wire=no_flash
        dirty=False;before={};meta=None
        def bench():
            x.mon();x.cmd('MAINT LOAD',(t.WB,));x.cmd('EDU ON');face=x.cmd('SRAM');assert b'SSRAM PROGRAM:' in face,face
            x.cmd('Q',MONS);x.rec();x.s.load(fixture,t.sha(fixture),PB)
        def raw(addr,data=None):
            assert x.s.context==PB and addr%64==0
            fields=addr.to_bytes(3,'big')
            if data is not None:
                assert addr in blocks and data==before[addr] and len(data)==64
                crc=binascii.crc_hqx(fields+data,65535);x.s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode())
                face=x.s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face
            x.s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=x.s.until((PB,))
            match=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(match)==1,face
            body=bytes.fromhex(match[0].decode());assert body[:3]==fields and binascii.crc_hqx(body[:-2],65535)==int.from_bytes(body[-2:],'big')
            if data is not None:assert body[3:-2]==data
            return body[3:-2]
        def cleanup():
            nonlocal dirty
            if not dirty:return
            bench();changed=[]
            for addr in blocks:
                if raw(addr)!=before[addr]:raw(addr,before[addr]);changed.append(f'{addr:05X}')
            assert b''.join(raw(a) for a in range(0,0x240,64))==meta
            assert b''.join(raw(a) for a in blocks)==b''.join(before[a] for a in blocks)
            dirty=False;x.r.update(SPI_restore_pending=False,SPI_restored=True,SPI_restored_blocks=changed)
            x.mark(storage_large_SPI_restore_pending=False);x.save()
        try:
            bench();meta=b''.join(raw(a) for a in range(0,0x240,64));names=allocation(meta)
            for addr in blocks:before[addr]=raw(addr)
            opaque.durable_file(OUT/'SPI8256-before.bin',b''.join(before[a] for a in blocks));opaque.durable_file(OUT/'PROGRAM-directory-before.bin',meta)
            x.r['retained_names']=[n.decode('ascii') for n in names];x.check('fresh-slot4-pages98-B7-and-exact-preimages-admitted')
            if drift_pending():raise InterruptedError('RTC priority before PROGRAM write')
            x.rec();x.s.load(packet,t.sha(packet),t.MON);x.mon();assert x.s.dump(0x4700,0x66FF)==program
            x.cmd('STORE P 9800 4700 66FF LG4',(PROGRAM_YES,))
            dirty=True;x.r['SPI_restore_pending']=True;x.mark(storage_large_SPI_restore_pending=True);x.save()
            face=x.cmd('YES',MONS);assert b'STORE status $00' in face,face
            x.mon();assert x.s.dump(0x4700,0x66FF)==program
            bench();row=raw(0x140);data=b''.join(raw(a) for a in range(0x9800,0xB800,64))
            assert row[:4]==b'SP\x01\0' and row[63]==0xA5 and binascii.crc_hqx(row[:62],65535)==0
            assert row[4:10]==bytes.fromhex('00 47 00 20 00 47') and row[14:16]==bytes((0x98,1)) and row[16:32]==b'LG4'.ljust(16,b'\0')
            assert data==program and int.from_bytes(row[12:14],'little')==binascii.crc_hqx(program,65535)
            after=b''.join(raw(a) for a in range(0,0x240,64));assert after[:0x140]==meta[:0x140] and after[0x180:]==meta[0x180:]
            (OUT/'LG4-record.bin').write_bytes(row);x.check('8KiB-STORE-source-preserved-committed-header-and-payload-CRC')
            if drift_pending():raise InterruptedError('RTC priority; restoring PROGRAM before yielding')
            x.mon();x.cmd('M 18FF 00');face=x.cmd('BATCH RESTORE P LG4;D 18FF',MONS)
            assert b'BATCH done' in face and b'18FF: 4C' in face and b'BATCH stopped' not in face,face[-1500:]
            x.mon();assert x.s.dump(0x18FF,0x18FF)==b'L';(OUT/'large-BATCH-return.txt').write_bytes(face)
            x.check('8KiB-BT-program-overwrites-WB-public-HOLD-and-following-BATCH-command')
            cleanup();x.check('all8256-SPI-bytes-and-retained-directory-restored')
            assert x.r['flash_erase_requests']==0
            x.verify_banks(range(4));x.mon();face=x.cmd('TIME');assert b' trim $0C ctrl $80' in face,face
            x.check('final-all-images-settings-history-F-and-RTC-trim-preserved')
            x.r.update(passed=True,scope_checks_complete=True)
        finally:
            cleanup()
    r=json.loads((OUT/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    print('PASS2512 large returning BATCH; SPI and owner restored; zero extra flash; COM4 free',flush=True)


if __name__=='__main__':run()
