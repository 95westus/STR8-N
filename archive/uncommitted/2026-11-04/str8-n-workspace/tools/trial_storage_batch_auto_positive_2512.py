"""The three reviewed B0 erases and8256-byte PROGRAM trial; exact cleanup."""
import argparse,binascii,json,re
from pathlib import Path
from storage_release_trial_2512 import *
from storage_large_source import source_packet


def allocation(meta):
    assert len(meta)==0x240
    free=[];occupied=set(range(8));names=[]
    for slot in range(8):
        row=meta[64+slot*64:128+slot*64]
        if row[63]!=0xA5:free.append(slot);continue
        assert row[:4]==b'SP\x01\0' and binascii.crc_hqx(row[:62],65535)==0 and row[62]==0
        name=row[16:32].rstrip(b'\0');names.append(name)
        if row[15]==1:occupied.update(range(row[14],row[14]+(int.from_bytes(row[6:8],'little')+255)//256))
    assert free and max(free)==4 and b'LG4' not in names
    assert not occupied.intersection(range(0x98,0xB8)), 'Reviewed32-page PROGRAM target is occupied'
    return names


def run():
    p=approved();ir=json.loads((INST/'report.json').read_text())
    assert ir['passed'] and ir['NVM_verified'] and ir['owner_RAM_restored'] and ir['owner_ZP_restored'] and ir['port_released']
    expected,_=forecast_install(p);initial=expected.copy()
    fixture=(SCOPE/'STORAGE-LARGE-RESTORER.bin').read_bytes();assert t.sha(fixture)==p['SPI_temporary']['restorer_sha256']
    packets={name:source_packet(program) for name,program in (('flash',False),('PROGRAM',True))}
    blocks=[0x140]+list(range(0x9800,0xB800,64))
    with Trial(POS,'2512-approved-AUTO-large-return-positive',expected,360) as x:
        (POS/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
        for name,(packet,body) in packets.items():(POS/(name+'-source-packet.bin')).write_bytes(packet);(POS/(name+'-source.bin')).write_bytes(body)
        x.r.update(SPI_restore_pending=False,SPI_restored=False,B0_restore_pending=False,B0_restored=False,temporary_PROGRAM_bytes=8256)
        before={};meta=None;spi_dirty=False;b0_dirty=False
        def bench():
            x.mon();x.cmd('MAINT LOAD',(t.WB,));x.cmd('EDU ON');face=x.cmd('SRAM');assert b'SSRAM PROGRAM:' in face,face
            x.cmd('Q',MONS);x.rec();x.s.load(fixture,t.sha(fixture),PB)
        def raw(address,data=None):
            assert x.s.context==PB and address%64==0
            fields=address.to_bytes(3,'big')
            if data is not None:
                assert address in blocks and data==before[address] and len(data)==64
                crc=binascii.crc_hqx(fields+data,65535)
                x.s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode())
                face=x.s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face
            x.s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=x.s.until((PB,))
            matches=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(matches)==1,face
            packet=bytes.fromhex(matches[0].decode());assert packet[:3]==fields and binascii.crc_hqx(packet[:-2],65535)==int.from_bytes(packet[-2:],'big')
            if data is not None:assert packet[3:-2]==data
            return packet[3:-2]
        def restore_spi():
            nonlocal spi_dirty
            if not spi_dirty:return
            bench();changed=[]
            for address in blocks:
                if raw(address)!=before[address]:raw(address,before[address]);changed.append(f'{address:05X}')
            assert b''.join(raw(a) for a in range(0,0x240,64))==meta
            assert b''.join(raw(a) for a in blocks)==b''.join(before[a] for a in blocks)
            spi_dirty=False;x.r.update(SPI_restore_pending=False,SPI_restored=True,SPI_restored_blocks=changed);x.mark(storage_large_SPI_restore_pending=False);x.save()
        def restore_b0():
            nonlocal b0_dirty
            if not b0_dirty:return
            if x.r.get('uncertain_flash_mutation'):raise RuntimeError('Uncertain mutation: no automatic restoration erase')
            wire=x.wire()
            for page in (0x90,0xA0):
                off=(page-0x80)*256;original=initial[0][off:off+4096];current=wire.read_sector(0,page)
                if current!=original:
                    assert x.r['flash_erase_requests']<3,'Three reviewed fixture erases exhausted'
                    x.replace(0,page,current,original);wire=x.wire()
            assert x.expected[0]==initial[0]
            b0_dirty=False;x.r.update(B0_restore_pending=False,B0_restored=True);x.mark(storage_large_B0_restore_pending=False);x.save()
        def source(name):
            packet,body=packets[name];x.rec();x.s.load(packet,t.sha(packet),t.MON)
            start=0x4700 if name=='PROGRAM' else 0x4E00
            assert x.s.dump(start,0x66FF)==body
            return body
        def area():
            x.mon();x.cmd('AREA 0 9000 AFFF');assert x.s.dump(0x6A29,0x6A2E)==bytes.fromhex('01 00 00 90 00 B0')
        try:
            # Fresh exact target admission precedes any temporary write.
            for bank in (0,3):assert x.s.client.flash(bank)==initial[bank]
            bench();meta=b''.join(raw(a) for a in range(0,0x240,64));names=allocation(meta)
            for address in blocks:before[address]=raw(address)
            assert before[0x140]==meta[0x140:0x180]
            opaque.durable_file(POS/'SPI8256-before.bin',b''.join(before[a] for a in blocks))
            opaque.durable_file(POS/'PROGRAM-directory-before.bin',meta);x.r['retained_names']=[n.decode('ascii') for n in names]
            x.check('fresh-B0-history-and-slot4-pages98-B7-admission-new-restorer-reads')
            if drift_pending():raise InterruptedError('RTC priority before first fixture write')
            b0_dirty=True;x.r['B0_restore_pending']=True;x.mark(storage_large_B0_restore_pending=True);x.save()
            x.replace(0,0xA0,initial[0][0x2000:0x3000],b'\xff'*4096)
            x.check('one-reviewed-A-erase-blank-AUTO-area-no-9-setup-erase')
            area();body=source('flash')
            assert x.s.dump(0x6A29,0x6A2E)==bytes.fromhex('01 00 00 90 00 B0')
            x.cmd('STORE 0 AUTO 4E00 66FF LGFA',(FLASH_YES,));face=x.cmd('YES',MONS)
            assert b'Flash record OK' in face and b'REFUSED' not in face,face
            assert x.s.dump(0x4E00,0x66FF)==body
            wire=x.wire();head=b'SR\x01\x3F'+bytes.fromhex('00 4E 00 19')+b'LGFA'.ljust(16,b'\0')
            want=bytearray(initial[0]);want[0x1000:0x3000]=b'\xff'*8192;want[0x1000:0x1000+len(head)+len(body)]=head+body
            assert wire.read_sector(0,0x90)==want[0x1000:0x2000] and wire.read_sector(0,0xA0)==want[0x2000:0x3000]
            x.expected[0]=bytes(want);x.check('wide-AUTO-at9000-source-preserved-exact-SR01-commit-and-payload')
            # A separate small append must skip all6400 bytes, including FF.
            area();tail=b'TAIL4G4\0';x.cmd('M 1000 '+tail.hex(' ').upper())
            x.cmd('STORE 0 AUTO 1000 1007 TAIL4',(FLASH_YES,));assert b'Flash record OK' in x.cmd('YES',MONS)
            h=b'SR\x01\x3F'+bytes.fromhex('00 10 08 00')+b'TAIL4'.ljust(16,b'\0')
            want[0x2918:0x2918+32]=h+tail;x.expected[0]=bytes(want)
            wire=x.wire();assert wire.read_sector(0,0xA0)==want[0x2000:0x3000]
            x.mon();face=x.cmd('TABLE 0');assert b'LGFA' in face and b'TAIL4' in face,face
            assert b'Flash record OK' in x.cmd('RESTORE 0 LGFA L',MONS)
            x.mon()
            assert x.s.dump(0x4E00,0x66FF)==body
            x.check('AUTO-tail-atA918-not-FF-payload-TABLE-and-wide-load-only-RESTORE')
            restore_b0();x.check('B0-9-A-restored-exactly-within-three-erases')
            if drift_pending():raise InterruptedError('RTC priority; B0 is restored')
            program=source('PROGRAM')
            x.cmd('STORE P 9800 4700 66FF LG4',(PROGRAM_YES,))
            spi_dirty=True;x.r['SPI_restore_pending']=True;x.mark(storage_large_SPI_restore_pending=True);x.save()
            face=x.cmd('YES',MONS);assert b'STORE status $00' in face,face
            assert x.s.dump(0x4700,0x66FF)==program
            bench();row=raw(0x140);data=b''.join(raw(a) for a in range(0x9800,0xB800,64))
            assert row[:4]==b'SP\x01\0' and row[63]==0xA5 and binascii.crc_hqx(row[:62],65535)==0
            assert row[4:10]==bytes.fromhex('00 47 00 20 00 47') and row[14:16]==bytes((0x98,1)) and row[16:32]==b'LG4'.ljust(16,b'\0')
            assert data==program and int.from_bytes(row[12:14],'little')==binascii.crc_hqx(program,65535)
            current=b''.join(raw(a) for a in range(0,0x240,64));assert current[:0x140]==meta[:0x140] and current[0x180:]==meta[0x180:]
            (POS/'LG4-record.bin').write_bytes(row);x.check('large-PROGRAM-STORE-source-preserved-record-and-8KiB-CRC')
            x.mon();x.cmd('M 18FF 00');face=x.cmd('BATCH RESTORE P LG4;D 18FF',MONS)
            assert b'BATCH done' in face and b'18FF: 4C' in face and b'BATCH stopped' not in face,face[-1500:]
            assert x.s.dump(0x18FF,0x18FF)==b'L';(POS/'large-BATCH-return.txt').write_bytes(face)
            x.check('8KiB-registered-PROGRAM-overwrites-WB-public-HOLD-and-BATCH-tail-runs')
            restore_spi();x.check('all8256-PROGRAM-bytes-and-retained-directory-restored')
            assert x.expected[3]==(SCOPE/'B3-final-predicted.bin').read_bytes() and x.r['flash_erase_requests']==3
            x.verify_banks(range(4));j=t.classify_journal(x.expected[3]);assert j['sequence']==1164 and j['counts'][28:]==[57,37,37,24]
            x.mon();face=x.cmd('TIME');assert b' trim $0C ctrl $80' in face,face
            x.check('final-images-boot-metadata-history-counts-F-and-TIME-exact')
            x.r['passed']=True
        finally:
            errors=[]
            for restore in (restore_spi,restore_b0):
                try:restore()
                except BaseException as e:errors.append(repr(e))
            if errors:x.r['restoration_errors']=errors;x.save();raise RuntimeError('Preservation remains pending: '+repr(errors))
            if x.r['flash_erase_requests'] and not x.r.get('uncertain_flash_mutation') and not x.r.get('NVM_verified'):
                x.verify_banks((0,3))
    r=json.loads((POS/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
    print('PASS2512 installed BATCH, wide AUTO and large returning BATCH; all fixtures/owner restored; COM4 free',flush=True)


if __name__=='__main__':run()
