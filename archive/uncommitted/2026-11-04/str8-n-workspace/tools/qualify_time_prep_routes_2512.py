"""Read-only installed-tool continuation; no repeats of the three erases."""
import json,re
from pathlib import Path
import install_time_prep_2512 as ins
t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2512-TIME-PREP-installed-routes-20261101-r1'

def run():
    ins.approved();proof=json.loads((ins.OUT/'report.json').read_text());assert proof['NVM_verified'] and proof['erase_requests']==3 and proof['owner_RAM_restored'] and proof['owner_ZP_restored']
    ins.base.window(90);OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    ram=(ins.OUT/'owner-ram.bin').read_bytes();zp=(ins.OUT/'owner-zp.bin').read_bytes();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,RTC_setting_writes=0,SRAM_data_writes=0,owner_RAM_restored=False,owner_ZP_restored=False);s=None;borrowed=False
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:03d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(b);return b
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context in (b'SRAM> ',b'BM> ',d.FT,t.CLOCK):cmd('Q',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(n):r['checks'].append(n);save();print('PASS2512 installed '+n,flush=True)
    save()
    with t.serial_lease('2512-TIME-PREP-installed-readonly-routes',timeout=30):
      m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and m['monitor_generation']=='0000000F'
      assert m['current_owner_RAM_sha256']==t.sha(ram) and m['current_owner_ZP_sha256']==t.sha(zp)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon();assert b'g0000000F / MON B' in cmd('VERSION')
            assert s.dump(0x200,0x23F)==ram[:64] and s.dump(0,0xDF)==zp
            mark(time_prep_routes_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            cmd('R SRAM',(b'SRAM> ',));table=cmd('T');assert all(n in table for n in (b'CLK',b'CLOCK',b'NFCOPY'));cmd('Q',(t.MON,));check('SRAM-TABLE-Q')
            cmd('R MAINT',(b'BM> ',));assert b'Saved/default: EDU ON' in cmd('EDU');cmd('Q',(t.MON,));check('MAINT-EDU-query-Q')
            cmd('R CLOCK',(t.CLOCK,));assert b'REFUSED' not in cmd('TIME');assert b'REFUSED' not in cmd('TRIM');cmd('Q',(t.MON,));check('CLOCK-TIME-TRIM-Q')
            cmd('R FLASH',(d.FT,));assert b'FLASH g2' in cmd('VERSION');cmd('Q',(t.MON,));check('FLASH-RP-CRC-VERSION-Q')
        finally:
          try:
            if borrowed:rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:mark(time_prep_routes_worker_active=False,application_RAM_restore_pending=not r['owner_RAM_restored'],application_ram_restored=r['owner_RAM_restored'],final_prompt='REC>')
            save()
    r['passed']=len(r['checks'])==4 and r['owner_RAM_restored'] and r['owner_ZP_restored'];save();assert r['passed']
    t.save(ins.OUT/'installation-acceptance.json',dict(passed=True,original_write_receipt=str(ins.OUT/'report.json'),original_write_sha256=t.sha((ins.OUT/'report.json').read_bytes()),routes_receipt=str(OUT/'report.json'),routes_sha256=t.sha((OUT/'report.json').read_bytes()),erases=3,additional_flash_writes=0,owner_RAM_ZP_restored=True))
    print('PASS2512 installed tools; no additional writes; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
