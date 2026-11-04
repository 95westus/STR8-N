"""Approved named copies: two B0:9 cleanup erases,320 SPI bytes restored."""
import binascii,json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=ins.t;d=ins.d;Q=ins.Q;SCOPE=ins.SCOPE;BM=ins.BM;ST=ins.ST;XY=ins.XY
OUT=Q/'2512-named-transfer-positive-20261101-r1';PB=t.PB
MONS=tuple(f'B{n}> '.encode() for n in range(4))
BLOCKS=[0x140,0x800,0x840,0x880,0x8C0]


def run():
    p=ins.approved();ins.window();prior=json.loads((ins.OUT/'report.json').read_text());assert prior['passed']
    from journal_rotation_plan import reserve
    initial=ins.forecast(p);expected3=initial
    hm=json.loads((t.ROOT/'BUILD/named-edu-restorer-r1/manifest.json').read_text())
    fixture=(t.ROOT/'BUILD/named-edu-restorer-r1'/hm['filename']).read_bytes();assert t.sha(fixture)==hm['sha256']
    assert [int(x,16) for x in hm['allowed_write_blocks']]==BLOCKS
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    payload=(bytes.fromhex('A9 58 20 6D 7E 20 7F 7E 4C 67 7E')+bytes(range(21)))
    header=b'SR\x01\x3F'+(0x3000).to_bytes(2,'little')+(32).to_bytes(2,'little')+b'XSRC'.ljust(16,b'\0')
    source=header+payload;assert len(source)==56
    mp=Q/'device-operations/2512.json';s=None;ram=zp=prefix=None;borrowed=False;marker=None;dirty=False;flash_dirty=False;before={};meta=None
    r=dict(board='2512',passed=False,checks=[],fixture_erases_requested=0,F_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
        owner_RAM_restored=False,owner_ZP_restored=False,SPI_restore_pending=False,SPI_restored=False,B0_restored=False,automatic_retries=0)
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        if tokens is None and s.context in MONS:tokens=MONS
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:s.until(MONS+(t.REC,BM,ST,XY,opaque.PROMPT),seconds=10)
        if s.context==XY:cmd('NO',(BM,ST))
        if s.context==PB:s.link.send(b'Q');s.until(MONS)
        if s.context in (BM,ST,t.WB,t.CLOCK,d.FT,b'SRAM> ',b'WORK> '):cmd('Q',MONS)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',MONS)
        if s.context in MONS and s.context!=t.MON:cmd('B3',MONS)
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def readback():
        if s.context!=d.SERVICE:rec();s.service(reader)
    def bench():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON');face=cmd('SRAM')
        if b'SSRAM error $01' in face:cmd('SRAM PREP');face=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in face
        cmd('Q',MONS);rec();s.load(fixture,t.sha(fixture),PB)
    def raw(address,data=None):
        assert s.context==PB and address%64==0
        fields=address.to_bytes(3,'big')
        if data is not None:
            assert address in BLOCKS and len(data)==64 and data==before[address]
            crc=binascii.crc_hqx(fields+data,65535)
            s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode());face=s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face
        s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=s.until((PB,))
        found=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(found)==1,face
        frame=bytes.fromhex(found[0].decode());assert frame[:3]==fields and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
        if data is not None:assert frame[3:-2]==data
        return frame[3:-2]
    def check(n):r['checks'].append(n);save();print('PASS2512 named '+n,flush=True)
    def erase_fixture():
        nonlocal expected3,flash_dirty
        assert r['fixture_erases_requested']<2
        rec();s.load(writer,t.sha(writer),opaque.PROMPT);wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
        before9=wire.read_sector(0,0x90);assert before9!=b'\xff'*4096
        updated,op=reserve(expected3,1);assert not op['journal_sector_erases']
        r['fixture_erases_requested']+=1;save();s.context=None
        assert not wire.replace_sector(0,0x90,before9,b'\xff'*4096)
        s.context=opaque.PROMPT;assert wire.read_sector(0,0x90)==b'\xff'*4096;expected3=updated;flash_dirty=False
    def cleanup_spi():
        nonlocal dirty
        if not dirty:return
        bench()
        for addr in BLOCKS:
            if raw(addr)!=before[addr]:raw(addr,before[addr])
        assert b''.join(raw(a) for a in range(0,0x240,64))==meta
        assert b''.join(raw(a) for a in range(0x800,0x900,64))==(SCOPE/'PROGRAM-page0800-original.bin').read_bytes()
        dirty=False;r.update(SPI_restored=True,SPI_restore_pending=False);mark(named_edu_SPI_restore_pending=False)
        check('exact320-SPI-bytes-directory-and-retained-records-restored')
    save()
    with t.serial_lease('2512-approved-named-flash-PROGRAM-positive',timeout=60):
      ins.window();marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['monitor_generation']=='0000000E' and marker['current_physical_bank_sha256']['B3']==t.sha(initial)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until(MONS+(t.REC,),seconds=12);mon()
            assert b'g0000000E / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(named_edu_copy_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            readback();memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            assert s.client.flash(0)==(SCOPE/'B0-original.bin').read_bytes() and s.client.flash(3)==initial
            bench();meta=b''.join(raw(a) for a in range(0,0x240,64));assert meta==(SCOPE/'PROGRAM-directory-original.bin').read_bytes()
            for addr in BLOCKS:before[addr]=raw(addr)
            assert b''.join(before[a] for a in BLOCKS[1:])==(SCOPE/'PROGRAM-page0800-original.bin').read_bytes()
            (OUT/'SPI-original320.bin').write_bytes(b''.join(before[a] for a in BLOCKS))
            raw(0x140,before[0x140]);check('fresh-PROGRAM-preimages-and-bounded-no-change-restorer')
            if drift_pending():raise InterruptedError('RTC requested; no fixture created')
            mon();cmd('B0',(b'B0> ',));flash_dirty=True;save()
            for off in range(0,len(source),8):
                face=cmd(f'!M {0x9000+off:04X} '+source[off:off+8].hex(' ').upper());assert b'REFUSED' not in face
            cmd('B3',(t.MON,));readback();b0=s.client.flash(0)
            assert b0[:0x1000]==(SCOPE/'B0-original.bin').read_bytes()[:0x1000] and b0[0x1000:0x1038]==source and b0[0x1038:]==(SCOPE/'B0-original.bin').read_bytes()[0x1038:]
            mon();cmd('R MAINT',(BM,));cmd('X 0 XSRC P XCOPY',(XY,))
            dirty=True;r['SPI_restore_pending']=True;mark(named_edu_SPI_restore_pending=True);save()
            face=cmd('Y',(BM,));assert b'Copied and verified; source retained.' in face,face
            check('installed-BM-flash-to-PROGRAM-positive-and-return')
            bench();row=raw(0x140);data=b''.join(raw(a) for a in range(0x800,0x900,64))
            assert row[:4]==b'SP\x01\0' and row[63]==0xA5 and binascii.crc_hqx(row[:62],65535)==0
            assert row[4:10]==bytes.fromhex('00 30 20 00 00 30') and row[14:16]==bytes((8,1)) and row[16:32]==b'XCOPY'.ljust(16,b'\0')
            assert data[:32]==payload and binascii.crc_hqx(payload,65535)==int.from_bytes(row[12:14],'little')
            (OUT/'PROGRAM-copy-record.bin').write_bytes(row);(OUT/'PROGRAM-copy-page.bin').write_bytes(data)
            mon();assert b'XCOPY' in cmd('TABLE P');assert b'X\r\n' in cmd('RESTORE P XCOPY',MONS)
            check('PROGRAM-record-payload-CRC-TABLE-run-and-HOLD-return')
            erase_fixture();check('first-B0-fixture-cleanup-reservation-and-blank-readback')
            mon();cmd('R MAINT',(BM,));cmd('X P XCOPY 0 XBACK',(XY,));flash_dirty=True;save()
            face=cmd('Y',(BM,));assert b'Copied and verified; source retained.' in face,face
            readback();copy0=s.client.flash(0);want=bytearray((SCOPE/'B0-original.bin').read_bytes())
            want[0x1000:0x1018]=header[:8]+b'XBACK'.ljust(16,b'\0');want[0x1018:0x1038]=payload
            assert copy0==want
            mon();assert b'XBACK' in cmd('TABLE 0');assert b'X\r\n' in cmd('RESTORE 0 XBACK',MONS)
            check('PROGRAM-to-flash-AUTO-commit-last-exact-copy-and-run')
            erase_fixture();cleanup_spi();readback();assert s.client.flash(0)==(SCOPE/'B0-original.bin').read_bytes();r['B0_restored']=True
            assert s.client.flash(3)==expected3
            mon();cmd('R FLASH',(d.FT,));assert b'OK' in cmd('BOOT C B');cmd('Q',(t.MON,))
            # The single reviewed generation binding follows both cleanup reservations.
            final=bytearray((SCOPE/'B3-target.bin').read_bytes());final[0x1D80:0x1DC0]=b'\xff'*64;expected3=bytes(final)
            readback();actual=s.client.flash(3);assert actual==expected3
            opaque.durable_file(OUT/'B3-after.bin',actual);r['NVM_verified']=True
            check('default-B-gE-bound-all-images-settings-history-and-F-verified')
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if borrowed:
                if flash_dirty:erase_fixture()
                if dirty:cleanup_spi()
                readback()
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];kw=dict(named_edu_copy_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    named_edu_SPI_restore_pending=dirty,named_edu_B0_restore_pending=flash_dirty,block_snapshot=True,final_prompt='REC>',last_named_copy_trial=str(OUT/'report.json'))
                if r.get('NVM_verified'):
                    j=t.classify_journal(expected3);hs=marker['current_physical_bank_sha256'].copy();hs['B3']=t.sha(expected3);counts=marker['current_tracked_erase_counts'].copy()
                    for i,v in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=v
                    for n,i in zip('ABCDEF',range(26,32)):counts[n]=j['counts'][i]
                    kw.update(current_physical_bank_sha256=hs,current_wear_counts=j['counts'],current_tracked_erase_counts=counts,current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],default_monitor_generation='0000000E',current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                mark(**kw)
            save()
    r['passed']=bool(r.get('NVM_verified') and r['SPI_restored'] and r['B0_restored'] and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS2512 named transfer trial; exact cleanup; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
