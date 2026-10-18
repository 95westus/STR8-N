"""Execute relocated beta27 and preserved beta26, including real SRAM CLK data."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-beta27')
import argparse,json,re
from pathlib import Path
from beta4_migration import crc,metadata,journal,config_sum
from test_v2_status import fresh,boot,snapshot,OUT
from test_v2_storage import cmd,service
from test_v2_spi_resident import k
from test_v2_sram_store import install,run_api,request
from test_v2_local_time import invoke
import deploy_v2_beta27 as deploy

def bound(root,meta,plan,final,array):
    """Bind the qualified code to fresh physical banks and retained CLK bytes.

    The extensive map/fault/EDU-OFF suite need not repeat: require its exact
    artifact receipt, then exercise the live layout and previously unknown CLK.
    """
    prior=deploy.read(OUT/'beta27-test-results.json')
    assert prior['passed'] and prior['artifacts']==meta['artifacts']
    banks=[(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    calculated,_,_,_,_=deploy.layout(banks)
    assert [bytes(b) for b in calculated]==final
    assert len(array)==131072
    status=(root/'retained/devices-before/status.txt').read_bytes()
    rtc=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
    assert len(rtc)==9
    checks=['Exact artifact-bound standalone map, AUTO, corruption/fallback and EDU OFF suite passed; final banks regenerated exactly from fresh physical preimage']
    def start(key=None):
        cpu,m=fresh();m.banks=[bytearray(b) for b in final];m.spi.banks=m.banks
        m.bus.rtc_regs[:9]=rtc
        m.spi.devices[0].data[:]=array;m.fast=True;m.bus.ee[0xF2:0xF8]=m.banks[3][0x1C08:0x1C0E]
        k.model.run(cpu,lambda:cpu.pc==meta['boot']['BOOT_STARTUP_DOTS'],30000000)
        if key:m.rx.extend(key)
        boot(cpu);return cpu,m
    for key,page,version in [(None,0xB0,b'2.0b27'),(b'A',0xA0,b'2.0b26')]:
        print('CHECK physical-backup fixture',version.decode(),flush=True)
        cpu,m=start(key);assert m.ram[0x7D30]==page and b'STR8-N '+version in m.tx
        before=snapshot(m)
        text=cmd(cpu,m,b'VERSION\r');assert b'STR8-N '+version in text and b'MONITOR B gen 00000027 VALID default' in text,text
        assert b'(-05:00)' in cmd(cpu,m,b'TIME\r')
        user=bytes(m.ram[0x200:0x6500]);text=cmd(cpu,m,b'R SRAM\r');assert b'SRAM 1.2' in text,text
        assert bytes(m.ram[0x200:0x6500])==user
        assert b'CLK 2000 2FD7' in cmd(cpu,m,b'T\r')
        text=cmd(cpu,m,b'G CLK\r');assert b'CLOCK 1.8' in text,text
        assert b'Running: yes' in cmd(cpu,m,b'STATUS\r')
        assert b'Battery' in cmd(cpu,m,b'BATTERY\r')
        cmd(cpu,m,b'Q\r')
        text=cmd(cpu,m,b'R MAINT\r');assert b'BANK MAINT 2.2' in text,text
        cmd(cpu,m,b'Q\r')
        after=snapshot(m)
        if after!=before or m.events:
            diagnostic=dict(events=m.events,flash_differences=[dict(bank=i,offsets=[j for j,(a,b) in enumerate(zip(before[0][i],after[0][i])) if a!=b][:80]) for i in range(4) if before[0][i]!=after[0][i]],devices_changed=[i for i in range(1,4) if before[i]!=after[i]])
            (root/'upgrade/model-diagnostic.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
        assert after==before and not m.events
        checks.append(version.decode()+': exact physical target banks, VERSION/TIME, preserving SRAM loader, actual archived CLK execution and MAINT; flash/RTC/EEPROM/SRAM unchanged')
        print('PASS',checks[-1],flush=True)
    # Simulate storage writes separately; the real retained array is untouched.
    # A fresh model-only directory avoids assuming live spare version slots.
    cpu,m=start();install(cpu,m)
    assert run_api(cpu,m,request(6,key=b'FORMAT!!'))==0
    cpu.pc=0x7E67;cmd(cpu,m,b'')
    original=[bytes(b) for b in m.banks]
    text=cmd(cpu,m,b'R MAINT\rX 2 WORK S WORKCOPY\rY\r');assert b'Copied and verified' in text,text[-800:]
    assert [bytes(b) for b in m.banks]==original
    text=cmd(cpu,m,b'X S WORKCOPY 1 WORKCP\rY\r');assert b'Destination B01:8000' in text and b'Copied and verified' in text,text[-800:]
    assert bytes(m.banks[1][24:24+0x148B])==bytes(m.banks[2][0x4018:0x4018+0x148B])
    assert all(e[0]=='program' and e[1] in (1,3) for e in m.events),m.events[:5]
    checks.append('Model-only MAINT copy: relocated WORK -> SPI -> freed B1:8000; exact payload, source retained, no erases')
    print('PASS',checks[-1],flush=True)
    report=dict(passed=True,checks=checks,artifacts=meta['artifacts'],expected_hashes=plan['expected_hashes'],physical_backup_bound=True,retained_sram_sha256=deploy.sha(array),standalone_receipt_sha256=deploy.sha((OUT/'beta27-test-results.json').read_bytes()),board_access=False,boards_flashed=False)
    (root/'upgrade/beta27-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

def main(root=None):
    meta=deploy.build_audit();checks=[]
    if root:
        plan=deploy.read(root/'upgrade/plan.json')
        final=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
        array=(root/'retained/sram-prior/array-0.bin').read_bytes()
        return bound(root,meta,plan,final,array)
    else:
        prior=deploy.ROOT/'output/qualification/beta26-2026-10-15-retry/2609/upgrade'
        banks=[(prior/f'post-reset-b{i}.bin').read_bytes() for i in range(4)]
        banks[1]=banks[1][:0x3000]+b'\xff'*(32768-12288)
        final,_,_,_,_=deploy.layout(banks)
        plan={'expected_hashes':[deploy.sha(b) for b in final]}
        cpu,m=fresh();m.banks=[bytearray(b) for b in final];m.spi.banks=m.banks
        boot(cpu);install(cpu,m);m.fast=True
        assert run_api(cpu,m,request(6,key=b'FORMAT!!'))==0
        clock=(OUT/'clock/clock.bin').read_bytes();m.ram[0x2000:0x2000+len(clock)]=clock
        assert run_api(cpu,m,request(1,'CLK',end=0x2000+len(clock)-1))==0
        array=bytes(m.spi.devices[0].data)
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    def start(key=None,fault=None,off=False):
        cpu,m=fresh(off=off);m.banks=[bytearray(b) for b in final];m.spi.banks=m.banks
        m.spi.devices[0].data[:]=array;m.fast=True
        m.bus.ee[0xF2:0xF8]=m.banks[3][0x1C08:0x1C0E]
        if off:
            j=journal(m.banks[3]);cfg=bytearray(j[8:24]);cfg[13]=0xA5;cfg[14:]=config_sum(cfg)
            counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
            m.banks[3][0x4000:0x5000]=metadata(cfg,counts,int.from_bytes(j[4:8],'little'))+b'\xff'*(4096-128)
        if fault:m.banks[3][0x3000+{'commit':31,'cookie':20,'crc':400}[fault]]^=1
        k.model.run(cpu,lambda:cpu.pc==meta['boot']['BOOT_STARTUP_DOTS'],30000000)
        if key:m.rx.extend(key)
        boot(cpu);return cpu,m
    for key,page,version in [(None,0xB0,b'2.0b27'),(b'A',0xA0,b'2.0b26')]:
        print('CHECK',version.decode(),'startup and relocated commands',flush=True)
        cpu,m=start(key);assert m.ram[0x7D30]==page and b'STR8-N '+version in m.tx
        before=snapshot(m)
        text=cmd(cpu,m,b'VERSION\r');assert b'STR8-N '+version in text and b'MONITOR B gen 00000027 VALID default' in text and b'MONITOR A gen 00000026 VALID' in text,text
        assert b'(-05:00)' in cmd(cpu,m,b'TIME\r')
        text=cmd(cpu,m,b'T\r');assert b'B1:' not in text and all(s in text for s in [b'B2:8000',b'B2:B000',b'B2:C000',b'B2:D580']),text
        text=cmd(cpu,m,b'APPS\r');assert b'\xff' not in text and b'Bad cmd' not in text,text
        for view in (1,2):
            print('CHECK',version.decode(),'map',view,flush=True)
            text=cmd(cpu,m,f'M{view}\r'.encode());assert text.endswith(b'B3> '),text
            if view==1:assert b'B1 .  .  .  .  .  .  .  .' in text and b'B2 S  +  +  S  S  +  F  F' in text,text
            else:assert b'Firmware status formatter D800-E1FF reserved' in text and b'Local/board F000-F6FF; VERSION F800-FFFF reserved' in text,text
            (OUT/f'beta27-{page:02x}-M{view}.txt').write_bytes(text)
        # Named manager path must still preserve the complete user RAM region.
        user=bytes(m.ram[0x200:0x6500]);text=cmd(cpu,m,b'R SRAM\r');assert b'SRAM 1.2' in text,text
        assert bytes(m.ram[0x200:0x6500])==user
        text=cmd(cpu,m,b'T\r');assert b'CLK 2000 2FD7' in text,text
        text=cmd(cpu,m,b'G CLK\r');assert b'CLOCK 1.8' in text,text
        assert b'RTC registers (raw):' in cmd(cpu,m,b'STATUS\r')
        assert b'Battery' in cmd(cpu,m,b'BATTERY\r')
        assert b'-05:00' in cmd(cpu,m,b'OFFSET\r')
        cmd(cpu,m,b'Q\r')
        for name,prompt,wanted in [('WORK',b'WORK>',b'WORK 1.2'),('EDU',b'EDU>',b'EDU'),('MAINT',b'BM>',b'BANK MAINT 2.2')]:
            text=cmd(cpu,m,('R '+name+'\r').encode());assert wanted in text and prompt in text,(name,text)
            cmd(cpu,m,b'Q\r')
        assert b'B2:F' in cmd(cpu,m,b'W\r')
        assert snapshot(m)==before and not m.events
        passed(version.decode()+': boot, VERSION/TIME/T/APPS, maps, preserving SRAM loader, retained CLK, WORK/EDU/MAINT, W; no storage changes')
    cpu,m=start();before=snapshot(m)
    m.ram[0x7D2C]=1;m.ram[0x7D2D:0x7D2F]=(56).to_bytes(2,'little');assert service(cpu,m,5)==(0,0x80,True)
    # Only reserved firmware padding remains erased; AUTO must refuse it.
    m.banks[2][:0x5800]=bytes(0x5800)
    m.ram[0x7D2C]=2
    result=service(cpu,m,5);assert not result[2],result
    passed('AUTO uses newly free B1:8000; refuses B2 firmware padding D800-FFFF')
    for fault in ('commit','cookie','crc'):
        cpu,m=start(fault=fault);assert m.ram[0x7D30]==0xA0 and b'STR8-N 2.0b26' in m.tx
        assert b'2.0b26' in cmd(cpu,m,b'VERSION\r')
        assert b'(-05:00)' in cmd(cpu,m,b'TIME\r')
        assert not m.events
    passed('uncommitted/incompatible/corrupt beta27 falls back to preserved beta26 A with relocated helpers')
    cpu,m=start(off=True);user=bytes(m.ram[0x200:0x6700]);before=snapshot(m);frames=len(m.spi.frames);accesses=len(m.bus.accesses)
    assert b'2.0b27' in cmd(cpu,m,b'VERSION\r')
    cmd(cpu,m,b'TIME\r');text=cmd(cpu,m,b'R SRAM\r');assert b'SRAM loader unavailable' in text,text
    assert snapshot(m)==before and bytes(m.ram[0x200:0x6700])==user and len(m.spi.frames)==frames and len(m.bus.accesses)==accesses
    passed('EDU OFF: relocated VERSION/TIME work; SRAM refuses without touching devices or reclaimed RAM')
    # Actual map validation covers wrapping VERSION CRC across the top of B2.
    cpu,m=start();image=(OUT/'maint/board-name.bin').read_bytes();m.ram[0x2000:0x2000+len(image)]=image
    s=json.loads((OUT/'maint/manifest.json').read_text())['symbols'];original=[bytearray(b) for b in m.banks]
    def identify(sector):
        m.ram[s['MAPBANK']]=2;m.ram[s['MAPSEC']]=sector;m.ram[s['MAP_APP_OWNER']]=0xFF
        m.ram[s['MAP_OWNER_END']:s['MAP_OWNER_END']+2]=b'\0\0';m.ram[s['MAP_STATUS']+(sector-0x80)//16]=ord('U')
        m[0x7FEC]=(m.ram[0x7FEC]&0x11)|0xEC;invoke(cpu,s['MAP_IDENTIFY']);return chr(m.ram[s['MAP_KIND']])
    for offset,length,sector in [(0x5800,2560,0xE0),(0x7000,1792,0xF0),(0x7800,2048,0xF0)]:
        for fault in ('crc','header','erased'):
            m.banks=[bytearray(b) for b in original];m.spi.banks=m.banks
            a=bytearray(m.banks[2][offset:offset+length])
            if fault=='erased':a[:]=b'\xff'*length
            elif fault=='header':a[0]^=1;a[-2:]=crc(a[:-2]).to_bytes(2,'big')
            else:a[100]^=1
            m.banks[2][offset:offset+length]=a
            assert identify(sector)=='U',(offset,fault)
    passed('relocated status/local/VERSION map checks refuse bad CRC/header and erased assets, including FFFF wrap')
    # Simulated writes only: copy a real relocated record to SPI and back into
    # the newly free B1. Live retained data is never modified by qualification.
    cpu,m=start();before=snapshot(m)
    text=cmd(cpu,m,b'R MAINT\rX 2 WORK S WORKCOPY\rY\r');assert b'Copied and verified' in text,text[-800:]
    assert [bytes(b) for b in m.banks]==before[0]
    text=cmd(cpu,m,b'X S WORKCOPY 1 WORKCP\rY\r');assert b'Destination B01:8000' in text and b'Copied and verified' in text,text[-800:]
    original=bytes(m.banks[2][0x4018:0x4018+0x148B])
    assert bytes(m.banks[1][24:24+0x148B])==original
    assert all(e[0]=='program' and e[1] in (1,3) for e in m.events),m.events[:5]
    passed('simulated MAINT transfer: relocated WORK -> SPI -> AUTO B1:8000; payload exact, source retained, no erases')
    report=dict(passed=True,checks=checks,artifacts=meta['artifacts'],expected_hashes=plan['expected_hashes'],physical_backup_bound=bool(root),board_access=False,boards_flashed=False)
    path=(root/'upgrade' if root else OUT)/'beta27-test-results.json';path.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path);a=p.parse_args();main(a.root)
