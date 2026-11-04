"""Qualify dispatcherg4 MAINT LOAD fix in RAM; no flash or storage writes."""
import argparse,json,re,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import mon_features_2609_ram as t
from installer.common import save

INSTALL=ROOT/'output/qualification/2609-mon-feature-install-20261030-r1'
BOOT=ROOT/'output/qualification/2609-mon-feature-boot-20261030-r1'
SOURCE=t.KIT/'monitors/candidates/services-g00000004'
utc=lambda:datetime.now(timezone.utc).isoformat()


def run(folder):
    installed=json.loads((INSTALL/'install-receipt.json').read_text())
    boot=json.loads((BOOT/'report.json').read_text());marker=json.loads(t.MARK.read_text())
    assert installed['passed'] and installed['erase_requests']==5
    assert boot['physical_MON_B_boot'] and boot['owner_RAM_restored'] and boot['all_banks_expected']
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    m=json.loads((SOURCE/'manifest.json').read_text())
    name,info=next((n,i) for n,i in m['artifacts'].items() if i['variant']=='RAM trial composite')
    image=(SOURCE/name).read_bytes();assert t.sha(image)==info['sha256']
    reader=(t.KIT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();assert t.sha(reader)==t.live.READBACK_SHA256
    ram,zp=(INSTALL/'owner-ram.bin').read_bytes(),(INSTALL/'owner-zp.bin').read_bytes()
    folder=folder.resolve();folder.mkdir(parents=True,exist_ok=False)
    report=dict(board='2609',passed=False,phase='prepared',source_manifest=str(SOURCE/'manifest.json'),
       RAM_packet_sha256=info['sha256'],F_writes=0,flash_writes=0,journal_writes=0,SRAM_data_writes=0,
       RTC_SET=0,trim_writes=0,PF_ACK=0,owner_RAM_restored=False,checks=[],started_utc=utc())
    link=None;context=None;client=None;borrowed=False;n=0
    def checkpoint():save(folder/'report.json',report)
    def mark(**fields):
        state=json.loads(t.MARK.read_text());state.update(fields);save(t.MARK,state)
    def wait(tokens,seconds=35):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            found=[(link.pending.find(x),x) for x in tokens if x in link.pending]
            if found:
                start,token=min(found,key=lambda z:z[0]);count=start+len(token)
                data=bytes(link.pending[:count]);del link.pending[:count];return data,token
            link.pending.extend(link.read(max(1,link.serial.in_waiting)))
        raise TimeoutError(repr(bytes(link.pending[-180:])))
    def cmd(text,tokens=None):
        nonlocal context,n
        link.send(text.encode()+b'\r');data,context=wait(tokens or (context,))
        n+=1;(folder/f'{n:03d}.txt').write_bytes(data);return data
    def readback():
        nonlocal context,client,borrowed
        assert context==t.REC;t.recovery.PROMPT=b'RAM SERVICE BASE1> '
        client=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link),timeout=60)
        borrowed=True;context=None;client.load(reader,t.live.READBACK_SHA256,REC_observed=True);context=t.recovery.PROMPT
    def dump(a,b):
        data=cmd(f'D {a:04X} {b:04X}');cells={}
        for line in data.decode().splitlines():
            match=re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
            if match:cells.update((int(match[1],16)+i,x) for i,x in enumerate(bytes.fromhex(match[2])))
        assert all(x in cells for x in range(a,b+1));return bytes(cells[x] for x in range(a,b+1))
    def shell(text):
        out=cmd(text,(t.WB,t.MON));assert context==t.WB and b'WORKBENCH WB2 g00000005' in out
        cmd('?',(t.WB,));cmd('Q',(t.MON,))
        # HOLD returned to installed ROM B; reenter the still-resident RAM core.
        out=cmd('G 0200',(t.MON,));assert b'g00000008 / RAM' in out
    checkpoint()
    try:
      with t.serial_lease('2609-MAINT-LOAD-RAM-fix',timeout=30):
       with (folder/'serial.jsonl').open('x') as log:
        try:
            link=t.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
            link.send(b'\r');_,context=wait((t.REC,));t.transport.recovery_usb(link)
            mark(feature_reload_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
            readback()
            a,b=client.read(b'M',0x6500),client.read(b'M',0x6500)
            z,zr=client.read(b'Z',0xe0),client.read(b'Z',0xe0)
            assert a==b and z==zr==zp and a[:len(reader)]==reader and a[len(reader):]==ram[len(reader):]
            for bank in range(4):assert client.flash(bank)==(INSTALL/f'after-B{bank}.bin').read_bytes()
            client.send(b'Q');client.until(t.REC);context=t.REC
            t.recovery.PROMPT=t.MON;loader=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link),timeout=60)
            context=None;loader.load(image,info['sha256'],REC_observed=True);context=t.MON
            assert dump(0x7e67,0x7e69)==bytes.fromhex('4C 93 7E')
            cmd('M 4800 00');assert dump(0x4800,0x4800)==b'\x00'
            shell('MAINT LOAD');report['checks'].append('cold-explicit-reload')
            shell('MAINT LOAD');report['checks'].append('warm-explicit-reload')
            shell('  MAINT LOAD  ');report['checks'].append('leading-trailing-spaces')
            bad=cmd('MAINT LOAD X');assert b'REFUSED' in bad and b'Load flash WB2' not in bad
            report['checks'].append('extra-argument-refused-before-load')
            shell('MAINT');report['checks'].append('bare-MAINT-retained')
            for text in ('M1','W','APPS'):assert b'Services absent/invalid' not in cmd(text)
            assert dump(0x7e67,0x7e69)==bytes.fromhex('4C 93 7E')
            cmd('Q',(t.REC,));readback()
            for bank in range(4):
                data=client.flash(bank);(folder/f'after-B{bank}.bin').write_bytes(data)
                assert data==(INSTALL/f'after-B{bank}.bin').read_bytes()
            report['all_postimages_unchanged']=True
        finally:
          try:
            if borrowed:
                if context==t.WB:cmd('Q',(t.MON,))
                if context==t.MON:cmd('Q',(t.REC,))
                if context==t.REC:readback()
                if context==b'RAM SERVICE BASE1> ':
                    report.update(client.restore_owner(ram,zp));report['owner_RAM_restored']=True;context=t.REC
                else:raise RuntimeError('No restoration prompt; retain power')
          finally:
            if link is not None:link.close();report['COM8_released']=True
            mark(feature_reload_worker_active=False,application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                 application_ram_restored=report['owner_RAM_restored'] if borrowed else True,block_snapshot=True,
                 last_MAINT_reload_RAM_fix=str(folder/'report.json'))
            report['final_context']=context.decode() if context else None;checkpoint()
      assert report['all_postimages_unchanged'] and report['owner_RAM_restored']
      report.update(passed=True,phase='RAM_FIX_VERIFIED_NOT_FLASHED',finished_utc=utc());checkpoint()
      print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
      report.update(error=repr(error),finished_utc=utc());checkpoint();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    run(p.parse_args().folder)
