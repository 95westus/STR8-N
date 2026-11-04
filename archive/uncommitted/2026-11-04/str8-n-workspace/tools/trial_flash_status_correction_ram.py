"""2512 corrective layout/AUTO checks in RAM; no new flash/RTC/SPI writes."""
import json,struct,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import trial_flash_transfer_readonly as ro
from serial_test_coordination import drift_pending
t=d.t
Q=t.ROOT/'output/qualification';SCOPE=Q/'FLASH-transfer-scope-20261101-r1'
BUILD=t.ROOT/'BUILD/flash-status-correction-r4'
OUT=Q/'2512-flash-status-correction-RAM-20261101-r1'


def run():
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    if time.time()+180>=datetime.fromisoformat(due.replace('Z','+00:00')).timestamp():raise TimeoutError('RTC window; no port opened')
    mf=json.loads((BUILD/'manifest.json').read_text())
    def artifact(n):
        b=(BUILD/n).read_bytes();assert t.sha(b)==mf['artifacts'][n]['sha256'];return b
    app=bytearray(artifact('FLASH-RAM.bin'));library=artifact('DENSE-CONTROL-4000.bin')
    worker=artifact('FLASH-RECORD-6B00.bin');gate=artifact('FLASH-TRANSFER-GATE-7300.bin')
    off=int(mf['fragment_table_RAM'],16)-0x2000
    table=b''.join(struct.pack('<HH',0x4300+f['library_offset'],f['length']) for f in mf['fragments'])
    app[off:off+12]=table  # Data-only source addresses; code/lengths unchanged.
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,F_writes=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
           owner_RAM_restored=False,owner_ZP_restored=False,resets=0,power_cuts=0)
    s=None;ram=zp=prefix=None;borrowed=False;marker=None;banks={}
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        if tokens is None and s.context in MONS:tokens=MONS
        return s.command(line,tokens)
    MONS=tuple(f'B{n}> '.encode() for n in range(4))
    def mon():
        if s.context is None:s.until(MONS+(t.REC,ro.FT),seconds=8)
        if s.context==ro.YES:s.link.send(b'NO\r');s.until((ro.FT,))
        if s.context in (ro.FT,t.WB):cmd('Q',MONS)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',MONS)
        if s.context in MONS and s.context!=t.MON:cmd('B3',MONS)
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def readback():
        if s.context!=d.SERVICE:rec();s.service(reader)
    def raw(line,expected,reply=None):
        rec();packet=ro.record_packet(worker,line,gate)
        s.link.send(b'L\r');s.until((b'SEND BIN\r\n',))
        for i in range(0,len(packet),16):s.link.send(packet[i:i+16]);time.sleep(.002)
        face=s.until((ro.STORE_YES,b'STORE, no erase; type YES> ')+MONS,seconds=40)
        if reply is not None:
            assert s.context not in MONS,face
            s.link.send(reply);face+=s.until(MONS,seconds=30)
        assert expected in face,face
        return face
    def check(n):r['checks'].append(n);save();print('PASS2512 correction '+n,flush=True)
    save()
    with t.serial_lease('2512-corrective-layout-RAM-only',timeout=180):
      if drift_pending():raise InterruptedError('RTC priority')
      marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until(MONS+(t.REC,),seconds=12);mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(flash_status_correction_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
            plan=json.loads((SCOPE/'plan.json').read_text())
            for b in range(4):
                banks[b]=s.client.flash(b);(OUT/f'B{b}-before.bin').write_bytes(banks[b])
                assert t.sha(banks[b])==plan['final_bank_sha256'][f'B{b}']
            check('all-ten-approved-erases-and-final-images-journal-verified')
            rec();packet=bytearray(ro.flash_packet(bytes(app),banks[3]))
            packet[0x4100:0x4100+len(library)]=library
            s.load(bytes(packet),t.sha(packet),ro.FT)
            assert b'FLASH g2' in cmd('VERSION')
            cmd('BANK 0');cmd('I 9000 AFFF',(ro.YES,));face=cmd('NO',(ro.FT,));assert b'Canceled' in face
            cmd('Q',MONS);mon();assert s.dump(0x63F7,0x63F7)==b'\x01'
            check('fragment-library-load-CRC-ID-and-dense-dispatch-NO')
            readback();s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            raw('STORE 0 9000 5800 66FF FIXNO',b'Canceled',b'NO\r')
            readback();memory=s.client.read(b'M',0x6500);assert memory[0x4C00:]==ram[0x4C00:]
            check('shared-BOOT-hex-parser-wide-front-and-source-preservation')
            mon();cmd('MAINT LOAD',(t.WB,));cmd('Q',MONS);cmd('AREA 0 9000 9FFF')
            face=raw('STORE 0 AUTO 0200 020F AUTOFIX',b'Canceled',b'NO\r')
            assert b'Target B0:9000' in face,face
            check('AUTO-reloads-only-SP-retains-AREA-and-target-NO')
        finally:
          try:
            if borrowed:
                readback()
                r['B0_unchanged']=s.client.flash(0)==banks[0];r['B3_unchanged']=s.client.flash(3)==banks[3]
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                # Leave golden recovery while the reviewed corrections await approval.
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(flash_status_correction_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                     block_snapshot=True,last_flash_status_correction_RAM=str(OUT/'report.json'),final_prompt='REC>')
            save()
    r['passed']=len(r['checks'])==4 and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('B0_unchanged') and r.get('B3_unchanged')
    r['current_STATUS_unavailable']=True;r['candidate_STATUS_bytes_match_original']=mf['STATUS_details_exact']
    save();print(('PASS ' if r['passed'] else 'INCOMPLETE ')+'2512 correction RAM; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
