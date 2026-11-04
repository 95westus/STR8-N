"""Fresh2512 metadata/PROGRAM read-only capture for the next write review."""
import json,re,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=d.t;Q=t.ROOT/'output/qualification';OUT=Q/'2512-named-EDU-review-preflight-20261101-r1'


def run():
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    assert time.time()+240<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,
        owner_RAM_restored=False,owner_ZP_restored=False,resets=0,power_cuts=0)
    s=None;ram=zp=prefix=old3=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
    def mon():
        if s.context==t.WB:cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def raw(addr):
        face=cmd(f'SRAM READ 0 {addr:04X}');match=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',face);assert match,face
        return bytes.fromhex(match[1].decode())
    save()
    with t.serial_lease('2512-named-EDU-write-review-readonly',timeout=60):
      if drift_pending():raise InterruptedError('RTC priority')
      marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon();cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(named_edu_review_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            # Cached diagnostic fields survived the failed read-only lookup.
            for lo,hi,n in ((0x67C7,0x67F6,'SM-state'),(0x6900,0x69FF,'SM-directory-cache'),(0x6300,0x639B,'X-state')):
                (OUT/(n+'.bin')).write_bytes(s.dump(lo,hi))
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            opaque.durable_file(OUT/'B3-before.bin',old3)
            mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON')
            face=cmd('SRAM')
            if b'SSRAM error $01' in face:cmd('SRAM PREP');face=cmd('SRAM')
            assert b'SSRAM PROGRAM:' in face,face
            table=cmd('TABLE P');(OUT/'PROGRAM-table.txt').write_bytes(table)
            meta=b''.join(raw(a) for a in range(0,0x240,64));(OUT/'PROGRAM-directory.bin').write_bytes(meta)
            used=set(range(8));free=[];slots=[]
            for i in range(8):
                slot=meta[64+i*64:128+i*64]
                if slot[63]!=0xA5:free.append(i);continue
                assert slot[:3]==b'SP\x01' and slot[3]==0 and binascii_crc(slot[:62])==0
                name=slot[16:32].split(b'\0')[0].decode();size=int.from_bytes(slot[6:8],'little');page=slot[14]
                if slot[15]==1:used.update(range(page,page+(size+255)//256))
                slots.append(dict(slot=i,name=name,load=int.from_bytes(slot[4:6],'little'),length=size,
                    entry=int.from_bytes(slot[8:10],'little'),sequence=int.from_bytes(slot[10:12],'little'),page=page,type=slot[15]))
            page=next(p for p in range(8,256) if p not in used)
            payload=b''.join(raw(page*256+a) for a in range(0,256,64));(OUT/'PROGRAM-free-page.bin').write_bytes(payload)
            r.update(PROGRAM_slots=slots,free_slots=free,first_free_page=page,temporary_slot=free[-1],PROGRAM_directory_sha256=t.sha(meta))
            cmd('Q',(t.MON,));rec();s.service(reader);assert s.client.flash(3)==old3;r['B3_unchanged']=True
        except BaseException as error:r['error']=repr(error);save();raise
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
                mark(named_edu_review_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_named_EDU_preflight=str(OUT/'report.json'))
            save()
    r['passed']=r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    save();assert r['passed'];print(json.dumps(r,indent=2),flush=True)


def binascii_crc(b):
    import binascii
    return binascii.crc_hqx(b,65535)


if __name__=='__main__':run()
