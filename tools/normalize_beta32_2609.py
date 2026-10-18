"""Make 2609 firmware identical to qualified 2512 code, retaining board data."""
import argparse,json,os,re,sys
from pathlib import Path
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-candidate'
import upgrade_v2_fleet as f
import beta4_migration as m
import update_v2_beta24 as deploy
from deploy_v2_beta32_2512 import audit_build
from build_v2_spi_resident import sha
from serial_test_coordination import serial_lease
from rtc_prompt_sync import establish_b3
from qualify_v2_spi_install import load_image
from update_clk19_2609 import array_read
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-candidate'

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-beta32-candidate'
OUT=ROOT/'output/qualification/beta32-common-code-2609-2026-10-16'
OLD=ROOT/'output/qualification/clock19-2609-2026-10-16'
PEER=ROOT/'output/qualification/beta32-2026-10-16/2512/upgrade'
read=lambda p:json.loads(p.read_text())

def devices(stage):
    campaign=read(ROOT/'output/qualification/active-rtc-campaign.json')
    f.call(f.devices,['--root',str(OUT/'retained'),'--board','2609','--port',f.port('2609'),'--stage',stage,
        '--baseline-index',campaign['baseline_index'],'--clock-source','sram','--clock-name','CLK','--clock19-display-transition'])

def capture():
    audit_build();OUT.mkdir(parents=True,exist_ok=False);(OUT/'retained').mkdir()
    with serial_lease('2609-common-code-backup',priority=True):
        f.call(f.backup,['--board','2609','--port',f.port('2609'),'--out',str(OUT/'prior-verified')])
        f.call(f.array,['--root',str(OUT/'retained'),'--board','2609','--port',f.port('2609'),'--stage','prior'])
        devices('before')

def prepare():
    meta=audit_build();manifest=read(OUT/'prior-verified/manifest.json');assert manifest['repeat_verified']
    source=read(ROOT/'BUILD/v2-beta32-2609-candidate/build.json')
    assert meta['worker']==source['worker'] and meta['vectors']==source['vectors']
    before=[(OUT/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    peer=[(PEER/f'post-reset-b{i}.bin').read_bytes() for i in range(4)]
    soak=read(ROOT/'output/qualification/beta32-enhanced-soak-2512-2026-10-16/status.json')
    assert [sha(b) for b in peer]==soak['flash_hashes']
    peer_sram=(PEER.parent/'retained/sram-final/array-0.bin').read_bytes()
    assert (BUILD/'clock/clock.bin').read_bytes() in peer_sram
    for i,b in enumerate(before):
        assert b==(OUT/f'prior-verified/b{i}-repeat.bin').read_bytes()==(OLD/f'flash-b{i}.bin').read_bytes()
    final=[bytearray(b) for b in before]
    final[2][:]=peer[2]
    for lo,hi in [(0,0x1C00),(0x2000,0x4000),(0x6000,0x8000)]:final[3][lo:hi]=peer[3][lo:hi]
    assert final[3][0x2000:0x3000]==(ROOT/'BUILD/v2-beta28-b23/str8n-v2-recovery-slot-a0.bin').read_bytes()
    assert final[3][0x3000:0x4000]==(BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    assert final[3][0x7000:]==(BUILD/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    # Preserve source monitor A until new B is committed and fixed F switched.
    order=[(3,12)]+[(2,s) for s in range(15,7,-1) if before[2][(s-8)*4096:(s-7)*4096]!=final[2][(s-8)*4096:(s-7)*4096]]
    order += [(3,s) for s in (8,9,14,11,15,10) if before[3][(s-8)*4096:(s-7)*4096]!=final[3][(s-8)*4096:(s-7)*4096]]
    j=m.journal(before[3]);cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xB0'+(44).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];oldcounts=counts[:]
    for b,s in order:counts[b*8+s-8]+=1;assert counts[b*8+s-8]<0xFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    assert final[:2]==before[:2] and final[3][0x1C00:0x2000]==before[3][0x1C00:0x2000]
    assert final[3][0x5000:0x6000]==before[3][0x5000:0x6000]
    mf=read(BUILD/'migrator/manifest.json');assert len(order)<=mf['max_sectors']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19');cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    sy=mf['symbols'];call=sy['MIG_HALT']-3;printer=sy['MIG_PRINT'];trampoline=max(cells)+1
    assert bytes(cells[call+i] for i in range(3))==b'\x20'+printer.to_bytes(2,'little') and trampoline+6<0x6200
    cells.update(dict(enumerate(b'\x20'+printer.to_bytes(2,'little')+b'\x4C\x04\xF0',trampoline)))
    cells.update(dict(enumerate(b'\x20'+trampoline.to_bytes(2,'little'),call)))
    message=b'MIGRATION VERIFIED; READY FOR J3\r\n\0';assert len(message)<=sy['MIG_BAD']-sy['MIG_DONE']
    cells.update(dict(enumerate(message,sy['MIG_DONE'])))
    pending=[bytearray(b) for b in before];payloads=[]
    for i,(b,s) in enumerate(order):
        off=(s-8)*4096;data=bytearray(final[b][off:off+4096]);address=(s<<12)+31 if b==3 and s in (10,11) else 0
        if address:data[31]=255
        row=bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=b;cells[mf['commits']+i]=4 if address else 0
        cells.update(dict(enumerate(address.to_bytes(2,'little')+b'\0\0',mf['commit_addresses']+4*i)))
        pending[b][off:off+4096]=data
        if address:pending[b][address-0x8000]=0
        payloads.append(data)
    assert pending==final
    out=OUT/'upgrade';out.mkdir();installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    peak=max(counts);index=counts.index(peak)
    plan=dict(board='2609',version='2.0b32',generation=44,target_build=str(BUILD.relative_to(ROOT)),prior_directory='prior-verified',
        source=dict(active_page=0xA0,inactive_page=0xB0,version='2.0b32'),target_page=0xB0,fallback_page=0xA0,
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in before],expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer),build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
        storage_update=True,commit_records=[],config=cfg.hex(),counts_before=oldcounts,counts_after=counts,no_sram_format=True,
        physical_reset_required=False,returns_to_monitor=True,success_checkpoint=trampoline+3,completion_token='MIGRATION VERIFIED; READY FOR J3',
        recovery_profile_normalized=True,expected_wear_peak=f'Sector B{index//8}:{8+index%8:X}, max {peak} tracked erases.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,b in enumerate(final):(out/f'expected-b{i}.bin').write_bytes(b)
    for i,b in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(b)
    print('PREPARED common code; preserve board data; sector order',order,flush=True)

def rehearse():
    import test_v2_rtc_upgrade as t
    t.MANIFEST=read(BUILD/'migrator/manifest.json');t.S=t.MANIFEST['symbols'];t.kernel.fw.OUT=BUILD
    base=t.Memory;instances=[];p=read(OUT/'upgrade/plan.json')
    expected=(OUT/'upgrade/expected-b3.bin').read_bytes();prior=(OUT/'prior-verified/b3.bin').read_bytes()
    class Memory(base):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);instances.append(self)
        def mutated(self,kind,address,value):
            if self.bank==3 and address>>12==15:
                assert bytes(self.banks[3][0x3000:0x4000])==expected[0x3000:0x4000],'New B must precede fixed F'
                assert bytes(self.banks[3][0x2000:0x3000])==prior[0x2000:0x3000],'Source A must survive until fixed F'
            if self.bank==3 and address>>12==10:
                assert bytes(self.banks[3][0x7000:])==expected[0x7000:],'Fixed F must precede fallback A replacement'
            if self.bank==3 and address in (0xA01F,0xB01F) and value==0:
                off=(address&0xF000)-0x8000
                assert bytes(self.banks[3][off:off+4096])==expected[off:off+4096]
            super().mutated(kind,address,value)
    t.Memory=Memory;sys.argv=['rehearse','--root',str(OUT)];t.main()
    assert instances[0].events[-1]==('program',3,0xA01F,0)
    print('PASS recovery transition order and both monitor commit checks',flush=True)

def functional():
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    p=read(OUT/'upgrade/plan.json');checks=[]
    def fixture(fallback=False,installer_return=False):
        print('MODEL fixture',dict(fallback=fallback,installer_return=installer_return),flush=True)
        cpu,mem=fresh();mem.fast=True
        banks=[bytearray((OUT/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)]
        mem.banks=banks;mem.spi.banks=banks
        array=(OUT/'retained/sram-prior/array-0.bin').read_bytes();mem.spi.devices[0].data[:]=array
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(OUT/'retained/devices-before/status.txt').read_bytes())[1].decode());mem.bus.rtc_regs[:9]=raw
        ee=(OUT/'retained/devices-before/eeprom-0.bin').read_bytes();mem.bus.ee[:128]=ee[:128];mem.bus.ee[255]=ee[128];mem.bus.ee[240:248]=ee[129:137]
        if installer_return:
            mem.banks=[bytearray((OUT/f'prior-verified/b{i}.bin').read_bytes()) for i in range(4)];mem.spi.banks=mem.banks
            boot(cpu);assert mem.ram[0x7D30]==0xA0;print('MODEL source boot passed',flush=True)
            mem.banks=banks;mem.spi.banks=banks
            cells,_=m.read_s19(OUT/'upgrade/installer.s19')
            for a,v in cells.items():mem.ram[a]=v
            sy=read(BUILD/'migrator/manifest.json')['symbols'];n=sy['V2W_END']-0x7800
            mem.ram[0x7800:0x7800+n]=bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
            cpu.x=sy['MIG_DONE']&255;cpu.y=sy['MIG_DONE']>>8;cpu.pc=p['success_checkpoint']-3;mem.tx.clear()
        if fallback:
            import test_v2_spi_resident as k
            startup_dots=read(BUILD/'build.json')['boot']['BOOT_STARTUP_DOTS']
            k.k.model.run(cpu,lambda:cpu.pc==startup_dots,30000000);mem.rx.extend(b'A')
        boot(cpu);print('MODEL fixture boot complete',hex(mem.ram[0x7D30]),flush=True);return cpu,mem
    cpu,mem=fixture(installer_return=True);assert mem.ram[0x7D30]==0xB0 and b'2.0b32' in mem.tx
    checks.append('Source worker installer return boots normalized fixed F and beta32 B')
    def cmd(s):
        print('MODEL command',repr(s),flush=True)
        result=console(cpu,mem,s,limit=30000000)
        print('MODEL command passed',repr(result[-80:]),flush=True);return result
    body=(BUILD/'clock/clock.bin').read_bytes();mem.ram[0x2000:0x2000+len(body)]=body
    text=cmd(f'SRAM\rS CLK 2000 {0x2000+len(body)-1:04X} 2000\rQ\r'.encode());assert b'SRAM: 00' in text,text[-500:]
    expected=bytes(mem.spi.devices[0].data);array=(OUT/'retained/sram-prior/array-0.bin').read_bytes();assert expected[65536:]==array[65536:]
    for line in [b'BATCH SRAM;G CLK;Q\r',b'BATCH SRAM;G CLK;STATUS;Q\r',b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r']:
        text=cmd(line);assert b'BATCH done' in text and text.endswith(b'B3> '),text[-1200:]
    text=cmd(b'BATCH SRAM;BOGUS;Q\r');assert b'BATCH stopped: command failed' in text and text.endswith(b'SRAM> ');cmd(b'Q\r')
    text=cmd(b'BATCH MAINT;NAME TEST;Q\r');assert text.endswith(b'Type YES: ');text=cmd(b'\x1b');assert b'BATCH canceled' in text;cmd(b'Q\r')
    text=cmd(b'J3\r');assert b'2.0b32' in text and p['expected_wear_peak'].encode() in text
    assert bytes(mem.spi.devices[0].data)==expected
    assert [bytes(b) for b in mem.banks]==[(OUT/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
    checks.append('CLOCK save, exact BATCH, four providers, errors, ESC and J3 preserve expected storage')
    cpu,mem=fixture(fallback=True);assert b'2.0b28' in mem.tx and mem.ram[0x7D30]==0xA0
    text=console(cpu,mem,b'VERSION\rTIME\rR MAINT\rQ\r',limit=100000000)
    assert b'Board: 2609' in text and b'MAINT 2.4' in text and b'(-05:00)' in text
    checks.append('Identical beta28 A fallback boots with retained board name and offset')
    (OUT/'expected-sram.bin').write_bytes(expected)
    report=dict(passed=True,checks=checks,expected_hashes=p['expected_hashes'],build_sha256=p['build_sha256'],
        expected_sram_sha256=sha(expected),prior_sram_sha256=sha(array),clock_sha256=sha(body))
    (OUT/'upgrade/functional.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

def audit():
    audit_build();p=read(OUT/'upgrade/plan.json');r=read(OUT/'upgrade/functional.json')
    rehearsal=read(OUT/'upgrade/model-check.json')
    assert rehearsal['passed'] and rehearsal['stale_preimage_refused'] and rehearsal['corrupt_payload_refused']
    assert rehearsal['installer_sha256']==p['installer_sha256'] and rehearsal['expected_hashes']==p['expected_hashes']
    assert r['passed'] and r['build_sha256']==p['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert r['expected_hashes']==p['expected_hashes']
    assert read(OUT/'retained/sram-prior/report.json')['passed'] and read(OUT/'retained/devices-before/report.json')['passed']
    for i,h in enumerate(p['expected_hashes']):assert sha((OUT/f'upgrade/expected-b{i}.bin').read_bytes())==h

def install():
    audit();deploy.BUILD=BUILD;deploy.audit=audit;deploy.serial_lease=lambda kind:serial_lease(kind,priority=True);deploy.install(OUT,'2609')

def verify():
    audit();p=read(OUT/'upgrade/plan.json');r=read(OUT/'upgrade/functional.json')
    with serial_lease('2609-common-code-verify',priority=True),(OUT/'upgrade/live-serial.jsonl').open('x') as log:
        link=m.Link(f.port('2609'),log)
        try:
            establish_b3(link);text=link.command('J3');assert b'MONITOR B gen 0000002C VALID default' in text and p['expected_wear_peak'].encode() in text
            (OUT/'upgrade/boot.txt').write_bytes(text)
            assert link.dump(0x7D30,0x7D30)==b'\xB0'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==p['expected_hashes'][bank];(OUT/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS common-code flash B'+str(bank),flush=True)
            link.command('B3');text=link.command('VERSION');assert b'Board: 2609' in text and b'65C816' in text and b'MONITOR A gen 00000028 VALID' in text
            (OUT/'upgrade/version.txt').write_bytes(text)
            for command in ['APPS','T','TIME','M1']:(OUT/f'upgrade/{command}.txt').write_bytes(link.command(command))
            assert sha(array_read(link,'Retained SRAM guard'))==r['prior_sram_sha256']
            assert load_image(link,BUILD/'clock/clock.s19')==r['clock_sha256']
            body=(BUILD/'clock/clock.bin').read_bytes();link.command('SRAM',b'SRAM> ')
            text=link.command(f'S CLK 2000 {0x2000+len(body)-1:04X} 2000',b'SRAM> ');assert b'SRAM: 00' in text;link.command('Q')
            from run_v2_beta32_soak import batch
            for name,line in [('clock-batch','SRAM;G CLK;Q'),('clock-status','SRAM;G CLK;STATUS;Q'),('providers','MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')]:
                text=batch(link,line)
                if name.startswith('clock'):assert b'CLOCK 1.9' in text
                (OUT/f'upgrade/{name}.txt').write_bytes(text)
            actual=array_read(link,'Final SRAM');assert sha(actual)==r['expected_sram_sha256'];(OUT/'actual-sram.bin').write_bytes(actual)
            link.send(b'J3\r');text=link.until(b'A/B/S,Enter default [3s]: ');link.send(b'A')
            text+=link.until(b'\r\nB3> ');assert b'STR8-N 2.0b28' in text and link.dump(0x7D30,0x7D30)==b'\xA0'
            text+=link.command('VERSION');assert b'Board: 2609' in text
            text+=link.command('TIME');assert b'(-05:00)' in text
            (OUT/'upgrade/fallback-boot.txt').write_bytes(text)
            text=link.command('J3');assert b'STR8-N 2.0b32' in text and link.dump(0x7D30,0x7D30)==b'\xB0'
            (OUT/'upgrade/final-boot.txt').write_bytes(text)
        finally:link.serial.close()
    with serial_lease('2609-common-code-devices',priority=True):devices('after')
    assert read(OUT/'retained/devices-after/report.json')['passed']
    report=dict(passed=True,board='2609',version='2.0b32',active_slot='B',fallback_version='2.0b28',fallback_slot='A',
        same_firmware_code_as_2512=True,clock_version='1.9',clock_sha256=r['clock_sha256'],batch_verified=True,
        all_flash_verified=True,rtc_history_settings_identity_eeprom_preserved=True,workspace_preserved=True,wear_peak=p['expected_wear_peak'])
    (OUT/'hardware-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','prepare','rehearse','functional','install','verify']);a=p.parse_args();globals()[a.stage]()
