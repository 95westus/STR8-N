"""2512 RAM guards for dense S19 and wide flash records; no NVM writes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import time
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending

t=d.t
FT=b'FLASH/MAINT> '
YES=b'type YES> '
STORE_YES=b'type YES: '
SEND=b'SEND S19; complete ascending sectors; Ctrl-C cancels\r\n'
BUILD=t.ROOT/'BUILD/flash-transfer-g1-r5'


def record_packet(worker,line,gate=None):
    text=line.encode()+b'\0';assert len(text)<=41 and len(worker)==2048
    stub=bytes.fromhex('A2 80 A0 67 20 08 6B 4C 67 7E') if gate is None else bytes.fromhex('A2 40 A0 68 20 0B 73 4C 67 7E')
    code=bytearray(bytes.fromhex('78 D8 A2 00'));loop=len(code)
    for n in range(8 if gate is None else 12):code.extend(bytes((0xBD,0,3+n,0x9D,0,0x6B+n)))
    code.extend(bytes.fromhex('E8 D0'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('A2 3F'));loop=len(code)
    code.extend(bytes.fromhex('BD 80 02 9D 80 67 CA 10') if gate is None else bytes.fromhex('BD 80 02 9D 40 68 CA 10'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('A2 0A'));loop=len(code)
    code.extend(bytes.fromhex('BD C0 02 9D 21 6A CA 10'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('4C 21 6A'));assert len(code)<=128
    return bytes(code).ljust(128,b'\xff')+text.ljust(64,b'\xff')+stub.ljust(64,b'\xff')+worker+(gate or b'')


def flash_packet(body,bank3):
    code=bytes.fromhex('78 D8 A2 00 BD 00 6A 9D 00 5D BD 00 00 9D 00 5C E8 D0 F1 4C 00 20')
    image=bytearray(code.ljust(0x5E00,b'\xff'))
    image[0x1E00:0x1E00+len(body)]=body
    image[0x5C00:0x5E00]=bank3[0x1A00:0x1C00]
    return bytes(image)


def srec(kind,address,data=b''):
    b=bytes((len(data)+3,))+address.to_bytes(2,'big')+data
    return b'S'+str(kind).encode()+b.hex().upper().encode()+f'{(~sum(b))&255:02X}\r\n'.encode()


def run(out,resume=None):
    next_due=json.loads((t.ROOT/'output/qualification/rtc-hourly-controller-last.json').read_text())['next_due']
    if time.time()+180>=datetime.fromisoformat(next_due.replace('Z','+00:00')).timestamp():
        raise TimeoutError('Leave three minutes for RTC; no port opened')
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    mf=json.loads((BUILD/'manifest.json').read_text())
    def artifact(name):
        data=(BUILD/name).read_bytes();assert t.sha(data)==mf['artifacts'][name]['sha256'];return data
    app=artifact('FLASH-S19-RAM.bin');worker=artifact('FLASH-RECORD-6B00.bin');gate=artifact('FLASH-TRANSFER-GATE-7300.bin')
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/'output/qualification/device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,F_writes=0,SRAM_writes=0,
           RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,owner_RAM_restored=False,owner_ZP_restored=False)
    if resume:
        resume=Path(resume).resolve();prior=json.loads((resume/'report.json').read_text())
        recovery=json.loads((resume/'owner-recovery/report.json').read_text())
        assert len(prior['checks'])==6 and recovery['passed'] and recovery['owner_RAM_restored'] and recovery['B3_unchanged']
        assert artifact('FLASH-S19-RAM.bin')==(t.ROOT/'BUILD/flash-transfer-g1-r4/FLASH-S19-RAM.bin').read_bytes()
        r['checks']=prior['checks'];r['dense_evidence_carried_from']=str(resume/'report.json')
    s=None;ram=zp=prefix=old0=old3=None;marker=None;borrowed=False;origin=None;edu=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def boundary():
        if drift_pending():raise InterruptedError('RTC priority')
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(folder/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt').write_bytes(face);return face
    def mon():
        if s.context==YES:s.link.send(b'NO\r');s.until((FT,))
        if s.context==FT:cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(label):r['checks'].append(label);save();print('PASS2512 '+label,flush=True)
    def rx_tail():
        return b''.join(bytes.fromhex(v['hex']) for line in (folder/'serial.jsonl').read_text().splitlines() if (v:=json.loads(line))['direction']=='RX')[-4096:]
    def invoke(line,expect,reply=None,*,through_gate=False,image=None):
        boundary();rec();packet=record_packet(worker if image is None else image,line,gate if through_gate else None)
        # Observe both valid exits. A refusal is already a safe MON context;
        # never discard it while waiting solely for a confirmation marker.
        s.link.send(b'L\r');s.until((b'SEND BIN\r\n',),seconds=10)
        for offset in range(0,len(packet),16):s.link.send(packet[offset:offset+16]);time.sleep(.002)
        face=s.until((STORE_YES,t.MON),seconds=30)
        if reply is not None:
            assert s.context==STORE_YES,(line,face)
            s.link.send(reply);face+=s.until((t.MON,),seconds=30)
        else:assert s.context==t.MON,(line,face)
        assert expect in face,(line,face)
        source=b''.join(s.dump(a,min(a+1023,0x66FF)) for a in range(0x4E00,0x6700,1024))
        assert source==ram[0x4C00:],'Large Store frontend changed owner source'
    save()
    with t.serial_lease('2512-dense-S19-wide-flash-RAM-guards',timeout=180):
      boundary()
      # Check the window again after acquiring the shared lease.
      due=json.loads((t.ROOT/'output/qualification/rtc-hourly-controller-last.json').read_text())['next_due']
      assert time.time()+180<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()
      marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context;mon()
            assert b'g0000000D / MON B' in cmd('VERSION');edu=s.dump(0x6A20,0x6A20)[0]
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(flash_transfer_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old0=s.client.flash(0);old3=s.client.flash(3)
            (folder/'B0-before.bin').write_bytes(old0);(folder/'B3-before.bin').write_bytes(old3)
            assert t.sha(old0)==marker['current_physical_bank_sha256']['B0']
            assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            if not resume:
                rec();packet=flash_packet(app,old3);s.load(packet,t.sha(packet),FT)
                assert b'I first last' in cmd('?')
                assert b'REFUSED' in cmd('I C000 CFFF')
                cmd('BANK 0')
                for line in ('I 9001 9FFF','I 9000 9FFE','I A000 9FFF','I 9000 EFFF'):
                    assert b'REFUSED' in cmd(line)
                check('dense-I-whole-sector-bank-and-range-guards')
                cmd('I 9000 AFFF',(YES,));assert b'Canceled' in cmd('NO',(FT,))
                check('dense-I-live-NO-before-stream')
                for label,payload,code in (
                    ('initial-Ctrl-C',b'\x03',b'03'),
                    ('bad-record-checksum',srec(1,0x9000,bytes(range(16)))[:-4]+b'00\r\n',b'02'),
                    ('nonascending-record',srec(1,0x9010,bytes(range(16))),b'01'),
                    ('early-S9-no-full-sector',srec(1,0x9000,bytes(range(16)))+srec(9,0x9000),b'01')):
                    boundary();cmd('I 9000 AFFF',(YES,));s.link.send(b'YES\r');s.until((SEND,),seconds=10)
                    s.link.send(payload);face=s.until((FT,),seconds=30);assert b'S19 stopped $'+code in face,face
                    check('dense-I-'+label)
                cmd('Q',(t.MON,));rec();s.service(reader)
            else:
                assert old0==(resume/'B0-before.bin').read_bytes() and old3==(resume/'B3-before.bin').read_bytes()
            s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            invoke('STORE 0 9000 5800 66FF WIDEFL',b'Canceled',b'NO\r',through_gate=True)
            check('large-flash-Store-NO-preserves-source-through66FF')
            for line in ('STORE 3 9000 4E00 66FF WIDEFL','STORE 0 9000 4E00 6700 WIDEFL',
                         'STORE 0 9000 6600 4E00 WIDEFL','STORE 0 DFF0 4E00 66FF WIDEFL'):
                invoke(line,b'Use STORE' if 'DFF0' not in line else b'REFUSED')
            check('large-flash-bank-range-and-end-overflow-refusals')
            invoke('STORE 0 8000 4E00 66FF WIDEFL',b'REFUSED')
            invoke('STORE 0 AUTO 4E00 66FF WIDEFL',b'REFUSED')
            invoke('RESTORE 0 ABSENT L',b'REFUSED')
            check('occupied-AUTO-opaque-and-missing-restore-refusals')
            bad=bytearray(worker);bad[100]^=1
            invoke('STORE 0 9000 4E00 66FF WIDEFL',b'transfer image invalid',through_gate=True,image=bytes(bad))
            check('gate-full-payload-CRC-refusal-before-execution')
            invoke('STORE 0 AUTO 0200 020F SMALL',b'B3> ',through_gate=True)
            assert s.dump(0x69F9,0x69F9)==b'\0'
            check('flash-AUTO-gate-defers-to-existing-AREA-WB-path')
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          try:
            if borrowed:
                if s.context is None:s.until((FT,t.MON,t.REC),seconds=8)
                rec();s.service(reader)
                if old0 is not None:
                    new0=s.client.flash(0);(folder/'B0-after.bin').write_bytes(new0);r['B0_unchanged']=new0==old0
                if old3 is not None:
                    new3=s.client.flash(3);(folder/'B3-after.bin').write_bytes(new3);r['B3_unchanged']=new3==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:cmd(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(flash_transfer_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=marker['block_snapshot'] if restored else True,last_flash_transfer_RAM_trial=str(folder/'report.json'))
            save()
    r['passed']=len(r['checks'])==11 and not r.get('error') and not r.get('yielded_to_collection') and r.get('B0_unchanged') and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+'2512 flash transfer RAM guards; owner RAM restored; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--resume');a=p.parse_args();run(a.out,a.resume)
