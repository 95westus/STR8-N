"""Approved2512 8KiB PROGRAM Store/Table/load-only Restore; exact SPI cleanup."""
import argparse,binascii,json,re,sys,time
from pathlib import Path
from datetime import datetime
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
SCOPE=t.ROOT/'output/qualification/TRANSFER-scope-20261101-r2'
PB=t.PB;CONFIRM=b'STORE PROGRAM from original RAM; type YES: '
ALLOWED=[0x140]+list(range(0x9800,0xB800,64))


def admit_directory(meta):
    h=meta[:64];assert h[:60]==b'SS\x01\x08\x08\x00\x01\x00'+bytes(52)
    assert h[62:]==b'\0\xA5' and binascii.crc_hqx(h[:62],65535)==0
    used=set(range(8));free=[];names=[]
    for slot in range(8):
        row=meta[(slot+1)*64:(slot+2)*64];assert len(row)==64
        if row[63]!=0xA5:free.append(slot);continue
        assert row[:4]==b'SP\x01\0' and row[62]==0 and not any(row[32:60]) and binascii.crc_hqx(row[:62],65535)==0
        names.append(row[16:32].split(b'\0')[0]);length=int.from_bytes(row[6:8],'little')
        if row[15]==1:
            load=int.from_bytes(row[4:6],'little');assert 0x200<=load and length>0 and load+length<=0x6700
            pages=set(range(row[14],row[14]+(length+255)//256));assert row[14]>=8 and max(pages)<256 and not used&pages;used|=pages
        else:assert row[15]==2 and length==0 and row[14]==0
    assert free and max(free)==4 and 4 in free and b'WIDETEST' not in names
    assert not used&set(range(0x98,0xB8))
    return dict(format='SS1',boundary='10000',selected_slot=4,payload='09800-0B7FF',existing_names=[n.decode() for n in names])


def run(out):
    approval=json.loads((SCOPE/'approval.json').read_text());assert approval['approved'] and approval['review_sha256']==t.sha((SCOPE/'review.json').read_bytes())
    plan=json.loads((SCOPE/'2512/plan.json').read_text());assert approval['plan_sha256']['2512']==t.sha((SCOPE/'2512/plan.json').read_bytes())
    helper=t.ROOT/'BUILD/transfer-restorer-r1';hm=json.loads((helper/'manifest.json').read_text())
    fixture=(helper/hm['filename']).read_bytes();assert t.sha(fixture)==hm['sha256']
    assert [int(v,16) for v in hm['allowed_write_blocks']]==ALLOWED and hm['temporary_bytes']==8256
    schedule=json.loads((t.ROOT/'output/qualification/rtc-hourly-controller-last.json').read_text())
    if time.time()+300>=datetime.fromisoformat(schedule['next_due'].replace('Z','+00:00')).timestamp():
        raise TimeoutError('Leave five-minute RTC window; no port opened')
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification');folder.mkdir(exist_ok=False)
    (folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    mp=t.ROOT/'output/qualification/device-operations/2512.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,F_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,owner_RAM_restored=False,owner_ZP_restored=False,
        SPI_restored=False,SPI_restore_pending=False,temporary_SPI_bytes=8256,restored_blocks=[])
    s=None;marker=None;ram=zp=prefix=old3=None;before={};meta=None;origin=None;edu=None;borrowed=False;dirty=False;cleanup=False
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def boundary():
        if not cleanup and drift_pending():raise InterruptedError('RTC priority')
    def check(name):r['checks'].append(name);save();print('PASS2512 '+name,flush=True)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(folder/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:36]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:s.until((t.MON,t.REC,t.WB,PB,CONFIRM),seconds=8)
        if s.context==CONFIRM:s.link.send(b'NO\r');s.until((t.MON,))
        if s.context==PB:s.link.send(b'Q');s.until((t.MON,))
        if s.context==t.WB:cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def bench():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON');face=cmd('SRAM')
        if b'SSRAM error $01' in face:cmd('SRAM PREP');face=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in face
        cmd('T P');cmd('Q',(t.MON,));rec();s.load(fixture,t.sha(fixture),PB)
    def raw(address,data=None):
        assert s.context==PB and address%64==0
        fields=address.to_bytes(3,'big')
        if data is not None:
            assert address in ALLOWED and len(data)==64 and address in before and data==before[address]
            crc=binascii.crc_hqx(fields+data,65535)
            s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode())
            face=s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face,face
        s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=s.until((PB,))
        matches=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(matches)==1,face
        frame=bytes.fromhex(matches[0].decode());assert frame[:3]==fields
        assert binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
        if data is not None:assert frame[3:-2]==data
        return frame[3:-2]
    def source():return b''.join(s.dump(a,min(a+1023,0x66FF)) for a in range(0x4700,0x6700,1024))
    def restore_spi():
        nonlocal dirty
        if not dirty:return
        if s.context!=PB:bench()
        # Retire the temporary directory entry before restoring its payload.
        for a in ALLOWED:
            if raw(a)!=before[a]:raw(a,before[a]);r['restored_blocks'].append(f'{a:05X}');save()
        for a in ALLOWED:assert raw(a)==before[a]
        assert b''.join(raw(a) for a in range(0,0x240,64))==meta
        assert raw(0x10000)==before[0x10000]
        dirty=False;r.update(SPI_restored=True,SPI_restore_pending=False);mark(transfer_PROGRAM_SPI_restore_pending=False)
        check('all8256-temporary-bytes-primary-directory-and-WORK-header-restored')
    save()
    with t.serial_lease('2512-approved-large-PROGRAM-Store',timeout=600):
      boundary();marker=json.loads(mp.read_text())
      assert marker.get('transfer_installed') and not marker.get('transfer_install_pending')
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert all(marker['current_physical_bank_sha256'][f'B{b}']==plan['target_bank_sha256'][f'B{b}'] for b in (1,2,3))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context;mon()
            assert b'g0000000D / MON B' in cmd('VERSION');edu=s.dump(0x6A20,0x6A20)[0]
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(transfer_PROGRAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);(folder/'B3-before.bin').write_bytes(old3);assert t.sha(old3)==plan['target_bank_sha256']['B3']
            bench();parts=[]
            for a in range(0,0x240,64):boundary();before[a]=raw(a);parts.append(before[a])
            meta=b''.join(parts);r['directory_admission']=admit_directory(meta)
            for a in (*ALLOWED,0x10000):
                boundary()
                if a not in before:before[a]=raw(a)
            (folder/'SPI-primary-directory-before.bin').write_bytes(meta)
            (folder/'SPI-test-window-before.bin').write_bytes(b''.join(before[a] for a in ALLOWED))
            (folder/'SPI-WORK-header-before.bin').write_bytes(before[0x10000])
            check('fresh-slot4-and9800-B7FF-unallocated-and-escrowed')
            # Establish restoration before publishing a new record: the same
            # captured bytes are written back to the approved free slot.
            boundary();raw(0x140,before[0x140]);assert raw(0x140)==before[0x140]
            check('bounded-restorer-original-byte-write-readback-before-STORE')
            boundary();rec();s.service(reader);s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            if edu!=1:cmd('!M 6A20 01')
            assert source()==ram[0x4500:];check('original-8KiB-source-intact-before-STORE')
            boundary();cmd('STORE P 9800 4700 66FF WIDETEST',(CONFIRM,))
            dirty=True;r['SPI_restore_pending']=True;mark(transfer_PROGRAM_SPI_restore_pending=True);save()
            s.link.send(b'YES\r');face=s.until((t.MON,),seconds=120)
            (folder/'STORE-result.txt').write_bytes(face);assert b'STORE status $00' in face,face
            assert source()==ram[0x4500:];check('installed-large-STORE-preserves-source-and-reports-success')
            boundary();assert b'WIDETEST' in cmd('TABLE P')
            bench();row=raw(0x140);payload=b''.join(raw(a) for a in range(0x9800,0xB800,64))
            (folder/'SPI-record-after.bin').write_bytes(row);(folder/'SPI-payload-after.bin').write_bytes(payload)
            assert row[:4]==b'SP\x01\0' and row[63]==0xA5 and binascii.crc_hqx(row[:62],65535)==0
            assert row[4:6]==bytes.fromhex('00 47') and row[6:8]==bytes.fromhex('00 20') and row[14:16]==bytes((0x98,1))
            assert row[16:32]==b'WIDETEST'.ljust(16,b'\0') and payload==ram[0x4500:]
            assert binascii.crc_hqx(payload,65535)==int.from_bytes(row[12:14],'little')
            check('TABLE-and-exact-committed8KiB-payload-CRC')
            boundary();mon();face=cmd('RESTORE P WIDETEST L',(t.MON,))
            assert b'PROGRAM OK' in face and source()==ram[0x4500:]
            check('wide-load-only-RESTORE-through66FF-and-quiet-MON-return')
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          cleanup=True
          try:
            if borrowed:
                try:restore_spi()
                except Exception as e:r['SPI_restoration_error']=repr(e);raise
                rec();s.service(reader)
                if old3 is not None:r['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:cmd(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'] and not dirty
                mark(transfer_PROGRAM_worker_active=False,transfer_PROGRAM_SPI_restore_pending=dirty,
                    application_RAM_restore_pending=not(r['owner_RAM_restored'] and r['owner_ZP_restored']),
                    application_ram_restored=r['owner_RAM_restored'] and r['owner_ZP_restored'],
                    block_snapshot=marker['block_snapshot'] if restored else True,last_transfer_PROGRAM_trial=str(folder/'report.json'))
            save()
    r['passed']=len(r['checks'])==7 and not r.get('error') and not r.get('yielded_to_collection') and r['SPI_restored'] and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+'2512 approved large PROGRAM trial; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
