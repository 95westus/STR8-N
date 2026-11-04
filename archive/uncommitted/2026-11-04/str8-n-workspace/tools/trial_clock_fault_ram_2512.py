"""2512 CLOCK SET/ACK/trim CPU-RAM qualification; no device-data writers."""
import binascii,json,re
from pathlib import Path
import install_named_edu_2512 as ins
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q
BUILD=t.ROOT/'BUILD/clock-fault-RAM-r3';OUT=Q/'2512-CLOCK-fault-RAM-20261101-r3'
PRIOR=Q/'2512-BOOT-CLOCK-positive-20261101-r1'
YES=b'Type YES to confirm: '
CASES=[('SET-latched',0,'SET'),('ACK-latched',0,'ACK'),('SET-EEPROM-NACK',1,'SET'),
 ('ACK-commit-NACK',2,'ACK'),('SET-readback-corrupt',3,'SET'),('ACK-write-protected',4,'ACK'),
 ('SET-RTC-NACK',5,'SET'),('ACK-RTC-NACK',6,'ACK'),('TRIM-order-restore',0,'TRIM2'),
 ('TRIM-active-output',0,'GUARD'),('TRIM-write-NACK',7,'TRIM'),('TRIM-readback-corrupt',8,'TRIM'),
 ('SET-foreign-layout',0,'FOREIGN'),('ACK-no-event',0,'NONE')]

def packet(mode,kind):
    mf=json.loads((BUILD/'manifest.json').read_text());body=(BUILD/'CLOCK-FAULT-RAM.bin').read_bytes()
    assert t.sha(body)==mf['packet_sha256'];a=bytearray(body)
    def put(addr,data):a[addr-0x200:addr-0x200+len(data)]=data
    assert len(a)<=0x6300
    put(0x1A00,b'\0'*0x2C0);ee=(PRIOR/'EEPROM-00-7F-after.bin').read_bytes();assert len(ee)==128
    put(0x1A00,ee);put(0x1A80,bytes.fromhex('D6 34 12 39 02 11 26 80 0C'))
    put(0x1A98,bytes.fromhex('00 12 01 11 30 12 01 11'));put(0x1AA0,bytes.fromhex('54 10 EC B6 74 3C'))
    put(0x1AC0,bytes((mode,)))
    if kind.startswith('TRIM') or kind=='GUARD':put(0x1A87,bytes((0xC4 if kind=='GUARD' else 0x84,)))
    if kind=='FOREIGN':put(0x1A00,b'X')
    if kind=='NONE':put(0x1A83,b'\x29')
    return bytes(a)

def validate(data,kind,mode):
    assert len(data)==768
    ee=data[:128];regs=data[128:160];stats=data[0xC0:0xD2];log=[tuple(data[256+i*4:260+i*4]) for i in range(stats[1])]
    assert stats[9]==stats[15]==0,('forbidden/overflow',stats.hex())
    old=(PRIOR/'EEPROM-00-7F-after.bin').read_bytes();pre=bytearray.fromhex('D6 34 12 39 02 11 26 80 0C')
    stamps=bytes.fromhex('00 12 01 11 30 12 01 11');row=ee[96:128]
    result=dict(mode=mode,stats_hex=stats.hex(),log=log,RTC_shadow_hex=regs.hex(),EEPROM_shadow_hex=ee.hex())
    if kind in ('TRIM2','TRIM','GUARD'):
      assert ee==old and regs[:7]==pre[:7] and regs[24:32]==stamps
      assert stats[4]==0
      writes=[(r,v) for k,r,n,v in log if k==2]
      if kind=='TRIM2':
        assert writes==[(7,0x80),(8,0x8D),(8,0x0C)],writes
        assert regs[7:9]==bytes.fromhex('80 0C') and stats[10]==0
      elif kind=='GUARD':
        assert not writes and regs[7:9]==bytes.fromhex('C4 0C') and stats[10]==2
      elif mode==7:
        assert writes==[(7,0x80),(8,0x8D)] and stats[3]==1 and regs[7:9]==bytes.fromhex('80 0C') and stats[10]==2
      elif mode==8:
        assert writes==[(7,0x80),(8,0x8D)] and regs[7:9]==bytes.fromhex('80 8D') and stats[16]>0 and stats[10]==2
    elif kind=='NONE':
      assert ee==old and stats[2]==stats[4]==0 and regs[3]==0x29 and stats[10]==0
    else:
      if kind=='FOREIGN':
        assert ee[0]==ord('X') and ee[1:]==old[1:] and stats[2]==stats[4]==0 and stats[10]==2
      else:assert ee[:96]==old[:96]
      if kind in ('SET','ACK') and mode in (0,5,6):
        nextseq=max(int.from_bytes(old[i+8:i+12],'little') for i in range(0,128,32))+1
        assert row[:8]==bytes.fromhex('50 46 01 04 4A 52 20 A5') and int.from_bytes(row[8:12],'little')==nextseq,row.hex()
        assert row[12:20]==stamps and binascii.crc_hqx(row[:28],65535)==int.from_bytes(row[28:30],'little')
        assert row[31]==0xA5 and stats[7]>0,('commit verification before RTC',stats.hex())
        first=data[512+96:512+128]
        assert first[:30]==row[:30] and first[30:]==bytes.fromhex('FF A5'),first.hex()
        if mode==0:
          assert row[30]==0 and regs[3]&0x10==0 and regs[24:32]==b'\0'*8 and stats[10]==0
          if kind=='SET':assert regs[:3]==bytes.fromhex('80 35 12') and regs[4:9]==bytes.fromhex('29 02 28 80 0C'),regs.hex()
          else:assert regs[:3]==pre[:3] and regs[4:9]==pre[4:9]
        else:
          assert row[30]==0xFF and regs[:9]==pre and regs[24:32]==stamps and stats[3]==0 and stats[10]==2
      elif mode in (1,2,3,4) or kind=='FOREIGN':
        assert stats[2]==0 and regs[:9]==pre and regs[24:32]==stamps and stats[10]==2
        if mode==3:assert stats[16]>0
    return result

def run():
    mf=json.loads((BUILD/'manifest.json').read_text());f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert mf['F_sha256']==f['sha256'] and all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
    ins.window(420);OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'manifest.json').write_bytes((BUILD/'manifest.json').read_bytes())
    (OUT/'review-document.md').write_text('''# 2512 CLOCK CPU-RAM device-boundary trial

User CONTINUE follows BOOT/CLOCK closeout. Borrow CPU RAM0200-66FF and ZP00-DF,
restore fresh exact owner bytes, preserve discovery7D04-7D26 and BQ magic.
No resets, power cuts, flash/journal/metadata/RTC/trim/EEPROM/SPI data writes.
Only COM4/2512 is opened, under shared RTC-priority lease/window checks.
Real CLOCK HISTORY/STATUS/TIME queries before/after are read-only.
All SET/ACK/TRIM commands run against a CPU-RAM register/EEPROM mirror.
Actual provider decode/SET/ACK, private EE validation/trim and journal code
are linked in RAM; physical transport is absent. Four CLOCK flash call sites
and the journal binding writer point to a refusal stub.
Observe commit/readback before first RTC write; inject data/commit NACK,
readback mismatch, write protection, RTC NACK, trim NACK, active-output guard,
foreign layout and no-event cases. No mutation is retried automatically.
This verifies software decisions/order on the physical CPU, not physical
device writes, electrical failures, endurance, or 816 execution.
F and published binaries are untouched. DELAY wording is source-only.
''')
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,cases={},flash_erases=0,flash_writes=0,journal_appends=0,metadata_appends=0,
      RTC_SET=0,trim_writes=0,PF_ACK=0,EEPROM_writes=0,SPI_writes=0,WORKSPACE_writes=0,resets=0,power_cuts=0,
      CPU_simulations=0,owner_RAM_restored=False,owner_ZP_restored=False,port_released=False,
      boundary='Physical CPU executes CLOCK; device data operations use only CPU RAM',F_sha256=f['sha256'])
    ram=zp=prefix=None;s=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):return s.command(line,tokens)
    def mon():
      if s.context==t.CLOCK:cmd('Q',(t.MON,))
      if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
      if s.context==t.REC:cmd('B',(t.MON,))
      assert s.context==t.MON
    def rec():
      if s.context is None:
        s.link.send(b'\x03\r');s.until((t.CLOCK,t.REC,t.MON),seconds=10)
      if s.context==YES:cmd('NO',(t.CLOCK,))
      if s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def physical(label):
      mon();face=cmd('R CLOCK',(t.CLOCK,t.MON))
      if s.context==t.MON:
        assert b'Tools invalid' in face;cmd('MAINT LOAD',(t.WB,));cmd('Q',(t.MON,));cmd('R CLOCK',(t.CLOCK,))
      assert s.context==t.CLOCK
      status=cmd('STATUS');cmd('HISTORY');mon();ee=s.dump(0x6B00,0x6B7F);outage=s.dump(0x66D4,0x66DB);time=cmd('TIME')
      for name,data in [('status.txt',status),('EEPROM.bin',ee),('outage.bin',outage),('time.txt',time)]:(OUT/(label+'-'+name)).write_bytes(data)
      return ee,outage,re.search(rb'trim \$[0-9A-F]{2} ctrl \$[0-9A-F]{2}',time)[0]
    save()
    with t.serial_lease('2512-CLOCK-RAM-fault-ordering',timeout=30):
      ins.window(420);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['monitor_generation']=='00000010' and marker['current_F_sha256']==f['sha256']
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
          cmd('Q',(t.REC,));cmd('B',(t.MON,))
          assert b'STR8-N MON B  gen 00000010' in cmd('VERSION')
          prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
          (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
          mark(clock_fault_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
          rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
          ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
          before3=s.client.flash(3);assert t.sha(before3)==marker['current_physical_bank_sha256']['B3']
          physical_before=physical('before');assert physical_before[0]==(PRIOR/'EEPROM-00-7F-after.bin').read_bytes()
          discovery=s.dump(0x7D04,0x7D26);magic=s.dump(0x7DF9,0x7DF9)
          for name,mode,kind in CASES:
            if drift_pending():raise InterruptedError('RTC priority; restore owner before yielding')
            ins.window(75);rec();image=packet(mode,kind);(OUT/(name+'-RAM.bin')).write_bytes(image)
            s.load(image,t.sha(image),t.CLOCK)
            command='SET 2028-02-29 12:35:00' if kind in ('SET','FOREIGN') else 'ACK' if kind in ('ACK','NONE') else 'TRIM +13'
            face=cmd(command,(YES,t.CLOCK))
            if kind=='NONE':assert s.context==t.CLOCK
            else:assert s.context==YES,(name,face);face+=cmd('YES',(t.CLOCK,))
            if kind=='TRIM2':
              face+=cmd('TRIM -12',(YES,t.CLOCK));assert s.context==YES;face+=cmd('YES',(t.CLOCK,))
            (OUT/(name+'-console.txt')).write_bytes(face)
            cmd('Q',(t.REC,));mon();data=s.dump(0x1A00,0x1CFF);(OUT/(name+'-result.bin')).write_bytes(data)
            assert s.dump(0x7D04,0x7D26)==discovery and s.dump(0x7DF9,0x7DF9)==magic
            r['cases'][name]=validate(data,kind,mode);save();print('PASS2512 CLOCK RAM '+name,flush=True)
          physical_after=physical('after');assert physical_after==physical_before
          r['physical_EEPROM_outage_trim_preserved']=True
          rec();s.service(reader);after3=s.client.flash(3);assert after3==before3
          r['B3_F_settings_journal_exact']=True
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if borrowed:
              rec();s.service(reader)
              if ram is None:
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
              r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
              restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
              mark(clock_fault_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',
                last_CLOCK_fault_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['cases'])==len(CASES) and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['physical_EEPROM_outage_trim_preserved'] and r['B3_F_settings_journal_exact']
    save();assert r['passed'];print('PASS2512 CLOCK14 CPU-RAM cases; real device data preserved; REC>; COM4 released',flush=True)

if __name__=='__main__':
    import argparse,time
    p=argparse.ArgumentParser();p.add_argument('--wait-for-RTC',action='store_true');args=p.parse_args()
    if args.wait_for_RTC:
      started=last=time.monotonic()
      while True:
        try:ins.window(420);break
        except AssertionError:
          if time.monotonic()-started>900:raise TimeoutError('RTC window did not reopen; no port opened')
          if time.monotonic()-last>=40 or last==started:
            print('WAIT RTC priority: no serial port opened',flush=True);last=time.monotonic()
          time.sleep(1)
    run()
