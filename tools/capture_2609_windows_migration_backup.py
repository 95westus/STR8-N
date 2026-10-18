"""2609 Windows-migration preserving read capture. No persistent writes, reset or RTC setters."""
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from qualify_v2_spi_install import load_image,read_application_s19
from qualify_v2_spi_storage import memory_request
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--snapshot',required=True,type=Path);a=ap.parse_args()
    snap=json.loads(a.snapshot.read_text());assert snap['passed'] and [b['board'] for b in snap['boards']]==['2609']
    active=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text());assert '2609' not in active['powered_off_boards'] and set(active['powered_off_boards'])=={'2205','2512'}
    authorization=ROOT/'output/qualification/bf1-2609-windows-migration-owner-authorization-2026-10-18-r1.json'
    auth=json.loads(authorization.read_text());assert auth['owner_authorized'] and auth['board']=='2609'
    soak=ROOT/'output/qualification/bf1-powered-soak-2609-2026-10-17-r1'
    stopped=json.loads((soak/'status.json').read_text());restored=json.loads((soak/'restore-needed.json').read_text())
    assert stopped['state']=='stopped-by-request' and stopped['application_ram_restored'] and not restored['needed'] and restored['verified']
    marker=ROOT/'output/qualification/device-operations/2609.json'
    operation=json.loads(marker.read_text());assert operation['state']=='windows-migration-backup-authorized' and operation['block_snapshot']
    from atomic_json import publish
    import os
    publish(marker,dict(board='2609',state='windows-migration-backup-running',pid=os.getpid(),block_snapshot=True,backup=str(a.out.resolve())))
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==snap['boards'][0]['port']
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(board='2609',port=port,usb_serial=SERIALS['2609'],started_utc=datetime.now(timezone.utc).isoformat(),snapshot=str(a.snapshot.resolve()),snapshot_sha256=sha(a.snapshot.read_bytes()),passed=False,clock_set=False,trim_changed=False,persistent_writes=False,reset=False,files={})
    def save(): (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def put(name,data): (a.out/name).write_bytes(data);report['files'][name]=dict(bytes=len(data),sha256=sha(data));save()
    original=None;link=None
    with (a.out/'serial.jsonl').open('x') as log:
      try:
        link=Link(port,log);establish_b3(link)
        for cmd in ('VERSION','TIME','APPS'):put(cmd.lower()+'.txt',link.command(cmd))
        put('runtime-status.bin',link.dump(0x7D00,0x7D3F));report['active_page']=link.dump(0x7D30,0x7D30)[0];assert report['active_page'] in (0xA0,0xB0)
        for repeat in range(2):
          for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
            data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
            put(f'b{bank}'+('-repeat' if repeat else '')+'.bin',data)
            if repeat:assert data==(a.out/f'b{bank}.bin').read_bytes(),f'Flash B{bank} unstable'
            print('FLASH',repeat,bank,sha(data),flush=True)
        link.command('B3');report['flash_repeat_verified']=True;save()
        def ram():return b''.join(link.dump(x,min(x+4095,0x64ff)) for x in range(0x200,0x6500,4096))
        original=ram();assert original==ram(),'Application RAM unstable';put('application-ram-original.bin',original)
        put('restore-application-ram.s19',s19(dict(enumerate(original,0x200)),0x200))
        (a.out/'restore-needed.json').write_text(json.dumps(dict(needed=True,first=512,last=0x64ff,sha256=sha(original)),indent=2)+'\n')
        eeprom=ROOT/'BUILD/v2-eeprom-inventory/probe.s19';client=ROOT/'BUILD/v2-spi-resident/hardware-client/client.s19'
        for path,digest in [(eeprom,'afded41e146341f4ab28fb82cf03934d91a3e7dc7fcc466bff03a70506a98621'),(client,'e892f3175bb315b2be8db4a94317e41569f50a22de3f067eb74170595593c4fc')]:
            cells,_=read_application_s19(path);assert sha(bytes(cells[i] for i in range(min(cells),max(cells)+1)))==digest
        load_image(link,eeprom)
        for repeat in range(2):
            link.command('G 2000');data=link.dump(0x2400,0x2494)
            assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            put('eeprom'+('-repeat' if repeat else '')+'.bin',data[:137]);put(f'eeprom-status-{repeat}.bin',data)
        assert (a.out/'eeprom.bin').read_bytes()==(a.out/'eeprom-repeat.bin').read_bytes();report['eeprom_repeat_verified']=True;save()
        assert load_image(link,client)=='e892f3175bb315b2be8db4a94317e41569f50a22de3f067eb74170595593c4fc'
        for repeat in range(2):
            blocks=[]
            for block in range(16):
                link.write_ram(0x3E20,b'\x01\x03\0');link.write_ram(0x3E00,memory_request(1,block*8192));link.command('G 2003')
                reply=link.dump(0x3E10,0x3E38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
                data=link.dump(0x4000,0x5fff);put(f'sram-{repeat}-{block:02d}.bin',data);blocks.append(data)
                if repeat:assert data==(a.out/f'sram-0-{block:02d}.bin').read_bytes(),f'SRAM block {block} unstable'
                print('SRAM',repeat,block,flush=True)
            put('sram'+('-repeat' if repeat else '')+'.bin',b''.join(blocks))
        report['sram_repeat_verified']=True
      except BaseException:
        report['failure']=traceback.format_exc();save();raise
      finally:
        try:
          if link and original is not None:
            from restore_2609_return_ram import saved_ram_image
            path=a.out/'restore-application-ram.s19';cells,entry=saved_ram_image(path)
            assert entry==0x200 and set(cells)==set(range(0x200,0x6500)) and bytes(cells[n] for n in range(0x200,0x6500))==original
            establish_b3(link);link.command('L',b'S19')
            for row in path.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
            reply=link.until(b'\r\nB3> ');assert not any(v in reply for v in (b'Bad',b'Protected',b'Wrap',b'Error')),reply
            actual=ram();put('application-ram-restored.bin',actual);assert actual==original,'Application RAM restoration failed'
            report['application_ram_restored']=True
            (a.out/'restore-needed.json').write_text(json.dumps(dict(needed=False,verified=True,sha256=sha(actual)),indent=2)+'\n')
        finally:
          if link:link.serial.close()
          save()
    report.update(passed=True,finished_utc=datetime.now(timezone.utc).isoformat(),ports_released=True);save();publish(marker,dict(board='2609',state='windows-migration-backup-complete',backup=str(a.out.resolve()),report_sha256=sha((a.out/'report.json').read_bytes()),block_snapshot=False));print('PASS',a.out/'report.json',flush=True)
if __name__=='__main__':main()
