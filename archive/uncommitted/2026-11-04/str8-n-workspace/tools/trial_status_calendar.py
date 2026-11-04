"""Execute STATUS local-date edge cases on2512 CPU using RAM samples, not RTC SET."""
import json,re
from datetime import datetime,timedelta
from pathlib import Path
import trial_status_prepared_sram as p
t=p.t;d=p.d
CASE=t.ROOT/'output/qualification/2512-STATUS-calendar-RAM-20261031-r2'
DATES=[(2000,1,1,0,15,0,-300,1),(2000,2,28,23,30,7,60,1),
       (2000,3,1,0,30,8,-60,1),(2001,3,1,0,30,9,-60,1),
       (2099,12,31,23,30,10,840,1),(2026,10,31,12,45,11,-720,1),
       (2026,10,31,23,45,12,840,1),(2026,10,31,0,5,13,0,0)]
def run():
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    authority=json.loads((p.AUTH/'report.json').read_text());assert authority['passed']
    ram=(p.AUTH/'owner-ram.bin').read_bytes();zp=(p.AUTH/'owner-zp.bin').read_bytes()
    sy={n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(p.CANDIDATE/'MON/mona.map').read_text(),re.M)}
    quiet=sy['M_QUIET_ENTRY']
    code=bytes.fromhex('78 D8 A9 03 8D F0 7B A9 34 8D F1 7B A9 02 A2 03 20 E8 7B 4C')+quiet.to_bytes(2,'little')
    image=(p.CANDIDATE/'STR8N-STATUS-RAM-TRIAL.bin').read_bytes()
    go_literal=sy['M_GO']+17
    assert image[go_literal-0x201:go_literal-0x1FE]==bytes.fromhex('A9 00 D0')
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,RTC_SET=0,RTC_data_writes=0,flash_writes=0,SRAM_writes=0,
           owner_RAM_restored=False,owner_ZP_restored=False,cases=[],escrow_authority=str(p.AUTH/'report.json'))
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False;save()
    with t.serial_lease('2512-STATUS-RAM-calendar-edges',timeout=30):
      marker=json.loads(t.MARK.read_text());assert not marker['application_RAM_restore_pending']
      with (CASE/'serial.jsonl').open('x') as log:
       try:
        s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
        assert s.dump(0x200,0x23F)==ram[:64] and s.dump(0,0xDF)==zp
        borrowed=True;mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
        s.rec();t.transport.recovery_usb(s.link);s.load(image,t.sha(image),t.MON)
        # Shipping RAM smoke MON deliberately refuses every G. Enable only its
        # ROM/RAM discriminator in this private RAM fixture; normal RAM address
        # bounds and every flash guard remain. No release artifact is changed.
        assert s.dump(go_literal,go_literal)==b'\0'
        s.command(f'!M {go_literal:04X} 01')
        r['private_RAM_fixture_G_literal']=f'{go_literal:04X}:00->01'
        s.modify(0x4000,code)
        for i,(year,month,date,hour,minute,second,offset,haszone) in enumerate(DATES):
            utc=datetime(year,month,date,hour,minute,second)
            fields=bytes((second,minute,hour,utc.isoweekday(),date,month,year-2000))
            s.command('!M 6AA8 '+fields.hex(' ').upper());s.command('!M 6A9B 01')
            off=bytes((haszone,))+(offset&65535).to_bytes(2,'little')
            s.command('!M 6A69 '+off.hex(' ').upper())
            out=s.command('G 4000',(t.MON,));(CASE/f'case-{i}.txt').write_bytes(out)
            local=utc+timedelta(minutes=offset)
            expected=local.strftime('%a %Y-%m-%d %H:%M:%S')
            expected+=f' ({"+" if offset>=0 else "-"}{abs(offset)//60:02}:{abs(offset)%60:02})' if haszone else ' UTC'
            row=dict(UTC=utc.isoformat(),offset_minutes=offset,has_saved_zone=bool(haszone),expected=expected,passed=expected.encode() in out)
            r['cases'].append(row);save();assert row['passed'],(expected,out)
            print('PASS calendar '+expected,flush=True)
       finally:
        try:
         if borrowed:
            if s.context!=t.REC:s.command('Q',(t.REC,))
            s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            s.command('B',(t.MON,));r.update(owner_RAM_restored=True,owner_ZP_restored=True)
        finally:
         if s is not None:s.link.close();r['port_released']=True
         if borrowed:mark(status_worker_active=False,application_RAM_restore_pending=not r['owner_RAM_restored'],
            application_ram_restored=r['owner_RAM_restored'],block_snapshot=marker['block_snapshot'] if r['owner_RAM_restored'] else True)
         save()
    r['passed']=len(r['cases'])==len(DATES) and all(c['passed'] for c in r['cases']) and r['owner_RAM_restored'];save()
if __name__=='__main__':run()
