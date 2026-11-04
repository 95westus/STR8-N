"""Backup-bound beta33/ASM installation and ORG $0200 S/T/R proof on 2512.

Requires explicit board authorization and the completed fresh capture. No soak
or v2.1 work. Shared read/restore helpers come from the prior qualified tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('STR8_BOARD_DATA_ROOT',str(ROOT)))
BUILD=ROOT/'BUILD/v2-beta33-candidate'
OUT=DATA/'output/qualification/beta33-2512-2026-10-16'
import deploy_v2_beta32_2205 as io
io.ROOT=DATA
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta33-candidate'
import beta4_migration as m
from qualify_v2_spi_install import load_image
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
import serial_test_coordination as coordination
coordination.ROOT=DATA/'output/qualification/serial-coordination'

read=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
save=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
images=lambda folder,prefix:[(folder/f'{prefix}{b}.bin').read_bytes() for b in range(4)]


def build_audit():
    meta=read(BUILD/'build.json');proof=read(BUILD/'beta33-qualification.json')
    assert proof['passed'] and proof['build_sha256']==sha((BUILD/'build.json').read_bytes())
    for name,h in meta['artifacts'].items():assert sha((BUILD/name).read_bytes())==h,name
    for name,h in proof['receipts'].items():assert sha((BUILD/name).read_bytes())==h and read(BUILD/name)['passed']
    for name,h in proof['source_sha256'].items():assert sha((ROOT/name).read_bytes())==h,name
    return meta


def prepare():
    build_audit();prior=OUT/'prior';report=read(prior/'report.json')
    assert report['passed'] and report['application_ram_restored']
    before=images(prior,'flash-1-b');assert before==images(prior,'flash-2-b')
    baseline=DATA/'output/qualification/fleet-as-is-backup-2026-10-16/2512'
    assert before==images(baseline,'flash-1-b'),'Unknown source; requalify'
    assert before[1]==b'\xff'*32768
    base=ROOT/'BUILD/v2-beta32-candidate'
    assert before[2]==(base/'candidate/b2.bin').read_bytes()
    assert before[3][0x3000:0x4000]==(base/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    final=[bytearray(b) for b in before]
    candidate=images(BUILD/'candidate','b')
    final[1][0x6000:]=candidate[1][0x6000:]
    final[2][:0x5800]=(BUILD/'xip/utilities.bin').read_bytes()
    final[3][0x6000:0x7000]=(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    final[3][0x3000:0x4000]=(BUILD/'str8n-v2-recovery-slot-b0.bin').read_bytes()
    changed=[(b,s) for b in range(4) for s in range(8,16) if before[b][(s-8)*4096:(s-7)*4096]!=final[b][(s-8)*4096:(s-7)*4096]]
    assert set(changed)=={(1,14),(1,15),(2,13),(3,14),(3,11)},changed
    order=[(3,12),(1,15),(1,14),(2,13),(3,14),(3,11)]
    j=m.journal(before[3]);assert j
    cfg=bytearray(j[8:24]);assert cfg[14:]==m.config_sum(cfg)
    cfg[7:13]=b'P\xB0'+(45).to_bytes(4,'little');cfg[14:]=m.config_sum(cfg)
    counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)];oldcounts=counts[:]
    for b,s in order:
        i=b*8+s-8;counts[i]+=1;assert counts[i]<0xFFFFFF
    final[3][0x4000:0x5000]=m.metadata(cfg,counts,int.from_bytes(j[4:8],'little')+1)+b'\xff'*(4096-128)
    assert final[0]==before[0] and final[1][:0x6000]==before[1][:0x6000]
    assert final[2][:0x5000]==before[2][:0x5000] and final[2][0x6000:]==before[2][0x6000:]
    assert final[3][:0x3000]==before[3][:0x3000] and final[3][0x5000:0x6000]==before[3][0x5000:0x6000]
    assert final[3][0x7000:]==before[3][0x7000:]
    mf=read(BUILD/'migrator/manifest.json');sy=mf['symbols']
    cells,entry=m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']]=len(order);cells[mf['commit_after']]=0
    call=sy['MIG_HALT']-3;printer=sy['MIG_PRINT'];tail=max(cells)+1
    assert bytes(cells[call+i] for i in range(3))==b'\x20'+printer.to_bytes(2,'little')
    cells.update(dict(enumerate(b'\x20'+printer.to_bytes(2,'little')+b'\x4C\x04\xF0',tail)))
    cells.update(dict(enumerate(b'\x20'+tail.to_bytes(2,'little'),call)))
    token='MIGRATION VERIFIED; READY FOR J3';message=token.encode()+b'\r\n\0'
    assert len(message)<=sy['MIG_BAD']-sy['MIG_DONE'];cells.update(dict(enumerate(message,sy['MIG_DONE'])))
    pending=[bytearray(b) for b in before];payloads=[]
    for i,(b,s) in enumerate(order):
        off=(s-8)*4096;payload=bytearray(final[b][off:off+4096])
        address=0xE712 if (b,s)==(3,14) else 0xB01F if (b,s)==(3,11) else 0
        if address:payload[address-(s<<12)]=255
        row=bytes((s<<4,))+m.fnv(pending[b]).to_bytes(4,'little')+m.fnv(payload).to_bytes(4,'little')
        cells.update(dict(enumerate(row,mf['table']+9*i)));cells[mf['banks']+i]=b
        cells[mf['commits']+i]=b+1 if address else 0
        cells.update(dict(enumerate(address.to_bytes(2,'little')+b'\0\0',mf['commit_addresses']+4*i)))
        pending[b][off:off+4096]=payload
        if address:pending[b][address-0x8000]=0 if address&255==31 else 0x3F
        payloads.append(payload)
    assert pending==final
    out=OUT/'upgrade';out.mkdir(exist_ok=False);verified=OUT/'prior-verified';verified.mkdir(exist_ok=False)
    installer=m.s19(cells,entry);(out/'installer.s19').write_bytes(installer)
    peak=max(counts);i=counts.index(peak)
    plan=dict(board='2512',version='2.0b33',generation=45,source=dict(version='2.0b32',active_page=0xB0),
        source_generation=44,target_build=str(BUILD),prior_directory='prior-verified',
        steps=[dict(bank=b,sector=s) for b,s in order],prior_hashes=[sha(b) for b in before],
        expected_hashes=[sha(b) for b in final],installer_sha256=sha(installer),
        build_sha256=sha((BUILD/'build.json').read_bytes()),template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
        storage_update=True,commit_records=[],success_checkpoint=tail+3,completion_token=token,
        returns_to_monitor=True,physical_reset_required=False,counts_before=oldcounts,counts_after=counts,
        expected_wear_peak=f'Sector B{i//8}:{8+i%8:X}, max {peak} tracked erases.',
        asm_descriptor_commit=0xE712,asm_bank=1,asm_address=0xE000,demo_name='HELLO0200',demo_origin=0x200)
    save(out/'plan.json',plan)
    for b,data in enumerate(before):(verified/f'b{b}.bin').write_bytes(data)
    for b,data in enumerate(final):(out/f'expected-b{b}.bin').write_bytes(data)
    for i,data in enumerate(payloads):(out/f'transfer-{i:02d}.bin').write_bytes(data)
    print('PREPARED six sectors; beta28 A, fixed recovery, B0 and all SRAM retained',flush=True)


def rehearse():
    import test_v2_rtc_upgrade as test
    expected=images(OUT/'upgrade','expected-b');parent=test.Memory;instances=[]
    class Memory(parent):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.require_maintenance_commit=False;self.app_published=False;instances.append(self)
        def mutated(self,kind,address,value):
            assert not(self.bank==3 and address>=0xF000)
            if self.bank==3 and address==0xE712 and value==0x3F:
                assert bytes(self.banks[1])==expected[1]
                assert bytes(self.banks[2])==expected[2]
                assert bytes(self.banks[3][0x6000:0x7000])==expected[3][0x6000:0x7000]
                self.app_published=True
            if self.bank==3 and address==0xB01F and value==0:
                assert self.app_published
            super().mutated(kind,address,value)
    test.Memory=Memory;argv=sys.argv
    try:sys.argv=['rehearse','--root',str(OUT)];test.main()
    finally:test.Memory=parent;sys.argv=argv
    assert instances[0].events[-1]==('program',3,0xB01F,0)
    p=OUT/'upgrade/model-check.json';proof=read(p);proof.update(app_publish_verified_after_code=True,monitor_commit_verified_last=True);save(p,proof)


def source_lines():
    raw=(ROOT/'examples/beta33/hello.asm').read_text().replace('ORG $2000','ORG $0200')
    return [f'{i*10} {line}' for i,line in enumerate([s for s in raw.splitlines() if s and not s.startswith(';')],1)]


def functional():
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    from test_v2_spi_resident import k
    prior=OUT/'prior';plan=read(OUT/'upgrade/plan.json');expected=images(OUT/'upgrade','expected-b')
    array=(prior/'spi-sram-1.bin').read_bytes();raw=(prior/'rtc-registers-1.bin').read_bytes()
    assert raw[3]&0x10==0
    def fixture(fallback=False):
        cpu,mem=fresh();mem.fast=True;mem.banks=[bytearray(b) for b in expected];mem.spi.banks=mem.banks
        mem.spi.devices[0].data[:]=array;mem.bus.rtc_regs[:32]=raw
        mem.bus.ee[:128]=(prior/'eeprom-1.bin').read_bytes();mem.bus.ee[0xF0:0xF8]=(prior/'eeprom-protected-1.bin').read_bytes()
        mem.bus.ee[255]=(prior/'eeprom-status-1.bin').read_bytes()[0]
        if fallback:
            at=read(BUILD/'build.json')['boot']['BOOT_STARTUP_DOTS']
            k.model.run(cpu,lambda:cpu.pc==at,30000000);mem.rx.extend(b'A')
        else:
            # Recreate the running beta32 console/worker state the RAM
            # installer actually inherits before testing its success return.
            mem.banks=[bytearray(b) for b in images(prior,'flash-1-b')];mem.spi.banks=mem.banks
            boot(cpu);assert b'2.0b32' in mem.tx and mem.ram[0x7D30]==0xB0
            mem.banks=[bytearray(b) for b in expected];mem.spi.banks=mem.banks
            cells,_=m.read_s19(OUT/'upgrade/installer.s19')
            for a,v in cells.items():mem.ram[a]=v
            sy=read(BUILD/'migrator/manifest.json')['symbols'];n=sy['V2W_END']-0x7800
            mem.ram[0x7800:0x7800+n]=bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
            cpu.x=sy['MIG_DONE']&255;cpu.y=sy['MIG_DONE']>>8;cpu.pc=plan['success_checkpoint']-3
            mem.tx.clear()
        boot(cpu);return cpu,mem
    cpu,mem=fixture();transcript=bytearray(mem.tx)
    assert b'2.0b33' in mem.tx and mem.ram[0x7D30]==0xB0 and plan['expected_wear_peak'].encode() in mem.tx
    def cmd(line):
        print('MODEL',line,flush=True);out=console(cpu,mem,line.encode()+b'\r',limit=100000000);transcript.extend(out)
        (OUT/'upgrade/functional-progress.txt').write_bytes(transcript);return out
    assert b'ASM installed B1:E000' in cmd('APPS')
    assert b'ASM 0.4' in cmd('ASM')
    cmd('10 FILL 12544,$AB')
    assert b'OK 12544 bytes, origin $0200, buffer $0200' in cmd('ASM')
    assert b'10 FILL 12544,$AB' in cmd('LIST')
    cmd('10 FILL 12545,$AB');assert b'Output full' in cmd('ASM');cmd('QUIT')
    assert bytes(mem.ram[0x0200:0x3300])==b'\xAB'*12544
    assert b'ASM 0.4' in cmd('ASM')
    for line in source_lines():assert b'Error' not in cmd(line)
    assert b'OK 23 bytes, origin $0200, buffer $0200' in cmd('ASM')
    assert b'0200:' in cmd('DUMP');body=bytes(mem.ram[0x200:0x217]);cmd('QUIT')
    assert bytes(mem.ram[0x200:0x217])==body
    assert b'OK\r\n' in cmd('G 0200')
    assert b'Done' in cmd('S 1 AUTO 0200 0216 HELLO0200')
    out=cmd('T 1');assert b'0200-0216' in out and b'HELLO0200' in out
    mem.ram[0x200:0x217]=bytes(23)
    assert b'Done' in cmd('R 1 HELLO0200 L') and bytes(mem.ram[0x200:0x217])==body
    assert b'OK\r\n' in cmd('R 1 HELLO0200')
    cmd('J3');assert mem.ram[0x7D30]==0xB0
    final=[bytes(b) for b in mem.banks]
    assert all(final[b]==expected[b] for b in (0,2,3)) and final[1][0x6000:]==expected[1][0x6000:]
    assert bytes(mem.spi.devices[0].data)==array and bytes(mem.bus.ee[:128])==(prior/'eeprom-1.bin').read_bytes()
    for b,data in enumerate(final):(OUT/f'upgrade/demo-b{b}.bin').write_bytes(data)
    (OUT/'upgrade/demo-body.bin').write_bytes(body);(OUT/'upgrade/functional.txt').write_bytes(transcript)
    cpu,mem=fixture(fallback=True);assert b'2.0b28' in mem.tx and mem.ram[0x7D30]==0xA0
    out=console(cpu,mem,b'R MAINT\rQ\r',limit=100000000);assert b'MAINT 2.4' in out
    save(OUT/'upgrade/functional.json',dict(passed=True,build_sha256=plan['build_sha256'],expected_hashes=plan['expected_hashes'],
        demo_hashes=[sha(b) for b in final],demo_body_sha256=sha(body),source_lines=source_lines(),
        sram_sha256=sha(array),installer_return_verified=True,fallback_verified=True,j3_verified=True,
        asm_0200_and_store_table_restore_verified=True,retained_data_preserved=True,
        contiguous_code_window_verified=True,output_capacity=12544,overflow_refused=True))
    print('PASS exact startup, ASM ORG 0200 direct output, S/T/R, J3, fallback and retained data',flush=True)


def audit():
    build_audit();plan=read(OUT/'upgrade/plan.json');model=read(OUT/'upgrade/model-check.json');proof=read(OUT/'upgrade/functional.json')
    assert read(OUT/'prior/report.json')['passed'] and proof['passed'] and model['passed']
    assert model['stale_preimage_refused'] and model['corrupt_payload_refused'] and model['app_publish_verified_after_code'] and model['monitor_commit_verified_last']
    assert plan['installer_sha256']==model['installer_sha256']==sha((OUT/'upgrade/installer.s19').read_bytes())
    assert proof['build_sha256']==plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert proof['source_lines']==source_lines()
    assert proof['expected_hashes']==model['expected_hashes']==plan['expected_hashes']
    for b,h in enumerate(proof['demo_hashes']):assert sha((OUT/f'upgrade/demo-b{b}.bin').read_bytes())==h


def install():
    audit();plan=read(OUT/'upgrade/plan.json');proof=read(OUT/'upgrade/functional.json')
    out=OUT/'hardware';out.mkdir(exist_ok=False);original=None;needed=False
    result=dict(board='2512',version='2.0b33',passed=False,application_ram_restored=False)
    with serial_lease('beta33-2512-install',priority=True),(out/'serial.jsonl').open('x') as log:
        link=m.Link(io.port('2512'),log)
        def cmd(line,prompt=b'\r\nB3> '):
            text=link.command(line,prompt);print('LIVE',line,flush=True);return text
        def flash_dump(stage,hashes):
            for b in range(4):
                prompt=f'\r\nB{b}> '.encode();cmd(f'B{b}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==hashes[b],f'{stage} B{b} mismatch';(out/f'{stage}-b{b}.bin').write_bytes(data)
                print('PASS',stage,'full B'+str(b),flush=True)
            cmd('B3')
        try:
            establish_b3(link);assert link.dump(0x7D30,0x7D30)==b'\xB0'
            original=io.dump_ram(link);(out/'ram-prior.bin').write_bytes(original);assert io.dump_ram(link)==original
            flash_dump('preflight',plan['prior_hashes']);needed=True;save(out/'ram-restore-needed.json',dict(needed=True,sha256=sha(original)))
            before=io.retained(link,out,'before')
            for name in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):assert before[name]==(OUT/f'prior/{name}-1.bin').read_bytes()
            assert before['rtc-registers'][7:]==(OUT/'prior/rtc-registers-1.bin').read_bytes()[7:] and before['rtc-registers'][3]&0x10==0
            load_image(link,OUT/'upgrade/installer.s19');cmd('G 2000',b'Y then Enter> ');link.send(b'Y\r')
            for i,step in enumerate(plan['steps']):
                link.until(f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode(),90)
                data=(OUT/f'upgrade/transfer-{i:02d}.bin').read_bytes()
                for j in range(0,4096,64):link.send(data[j:j+64]);time.sleep(.01)
                print('FLASH 2512',f'B{step["bank"]}:{step["sector"]:X}',flush=True)
            text=link.until(plan['completion_token'].encode(),90)+link.until(b'\r\nB3> ',90)
            assert b'2.0b33' in text and plan['expected_wear_peak'].encode() in text
            (out/'installer-return.txt').write_bytes(text);flash_dump('installed',plan['expected_hashes'])
            transcript=bytearray(cmd('APPS'));assert b'ASM installed B1:E000' in transcript
            transcript.extend(cmd('ASM',b'ASM> '))
            transcript.extend(cmd('10 FILL 12544,$AB',b'ASM> '))
            text=cmd('ASM',b'ASM> ');assert b'OK 12544 bytes, origin $0200, buffer $0200' in text;transcript.extend(text)
            text=cmd('LIST',b'ASM> ');assert b'10 FILL 12544,$AB' in text;transcript.extend(text)
            transcript.extend(cmd('10 FILL 12545,$AB',b'ASM> '))
            text=cmd('ASM',b'ASM> ');assert b'Output full' in text;transcript.extend(text)
            transcript.extend(cmd('QUIT'))
            window=b''.join(link.dump(a,min(a+4095,0x32FF)) for a in range(0x0200,0x3300,4096))
            assert window==b'\xAB'*12544;(out/'full-code-window.bin').write_bytes(window)
            transcript.extend(cmd('ASM',b'ASM> '))
            for line in source_lines():
                text=cmd(line,b'ASM> ');assert b'Error' not in text;transcript.extend(text)
            text=cmd('ASM',b'ASM> ');assert b'OK 23 bytes, origin $0200, buffer $0200' in text;transcript.extend(text)
            transcript.extend(cmd('DUMP',b'ASM> '));body=(OUT/'upgrade/demo-body.bin').read_bytes()
            transcript.extend(cmd('QUIT'));assert link.dump(0x0200,0x0216)==body
            text=cmd('G 0200');assert b'OK\r\n' in text;transcript.extend(text)
            text=cmd('S 1 AUTO 0200 0216 HELLO0200',b'\r\nB1> ');assert b'Done' in text;transcript.extend(text);cmd('B3')
            text=cmd('T 1');assert b'HELLO0200' in text and b'0200-0216' in text;transcript.extend(text)
            link.write_ram(0x0200,bytes(23));assert link.dump(0x0200,0x0216)==bytes(23)
            text=cmd('R 1 HELLO0200 L');assert b'Done' in text and link.dump(0x0200,0x0216)==body;transcript.extend(text)
            text=cmd('R 1 HELLO0200');assert b'OK\r\n' in text;transcript.extend(text)
            (out/'asm-0200-store-table-restore.txt').write_bytes(transcript)
            from run_v2_beta32_soak import batch
            for name,line in [('providers','MAINT;Q;SRAM;Q;WORK;Q;EDU;Q'),('clock','SRAM;G CLK;STATUS;Q'),('apps','APPS;VERSION')]:
                text=batch(link,line);(out/f'batch-{name}.txt').write_bytes(text)
                if name=='clock':assert b'CLOCK 1.9' in text and b'Running: yes' in text
                if name=='providers':assert all(t in text for t in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
            text=cmd('BATCH ASM;VERSION',b'BATCH stopped: unsupported')+link.until(b'\r\nB3> ');assert b'ASM>' not in text;(out/'batch-asm-refused.txt').write_bytes(text)
            text=cmd('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed')+link.until(b'SRAM> ');cmd('Q');(out/'batch-error.txt').write_bytes(text)
            text=cmd('BATCH MAINT;NAME TEST;Q',b'Type YES: ');link.send(b'\x1b');text+=link.until(b'BATCH canceled')+link.until(b'BM> ');cmd('Q');(out/'batch-esc.txt').write_bytes(text)
            link.send(b'J3\r');text=link.until(b'A/B/S,Enter default [3s]: ');link.send(b'A');text+=link.until(b'\r\nB3> ')
            assert b'2.0b28' in text and link.dump(0x7D30,0x7D30)==b'\xA0';(out/'fallback-boot.txt').write_bytes(text)
            text=cmd('J3');assert b'2.0b33' in text and plan['expected_wear_peak'].encode() in text and text.count(b'FLASH: wear check ')==1;(out/'final-boot.txt').write_bytes(text)
            for name in ('VERSION','TIME','APPS','T 1','M1','W','C'):
                text=cmd(name);(out/f'query-{name.replace(" ","-")}.txt').write_bytes(text)
                if name=='VERSION':assert b'Board: 2512' in text and b'MONITOR B gen 0000002D VALID default' in text
                if name=='TIME':assert b'(-05:00)' in text
            flash_dump('final',proof['demo_hashes'])
            array=io.array_read(link,'Final retained SRAM');assert sha(array)==proof['sram_sha256'];(out/'final-sram.bin').write_bytes(array)
            after=io.retained(link,out,'after')
            for name in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):assert after[name]==before[name]
            assert after['rtc-registers'][7:]==before['rtc-registers'][7:] and after['rtc-registers'][3]&0x38==before['rtc-registers'][3]&0x38
            result.update(passed=True,monitor='B',generation=45,fallback='2.0b28 A',asm='0.4',asm_source_entered_on_board=True,
                org_0200_verified=True,direct_assembly_to_origin_verified=True,store_table_restore_verified=True,demo_record='B1:8000 HELLO0200',
                contiguous_code_window_verified=True,output_capacity=12544,overflow_refused=True,
                native_utilities_verified=True,batch_completion_error_escape_verified=True,clock='1.9',j3_verified=True,
                complete_flash_verified=True,sram_preserved=True,rtc_eeprom_history_identity_preserved=True,
                fixed_recovery_preserved=True,b0_preserved=True,erase_counts_accounted=True,soak_started=False,
                final_flash_hashes=proof['demo_hashes'],build_sha256=plan['build_sha256'])
        except Exception as error:result['error']=repr(error);raise
        finally:
            try:
                if needed and original is not None:
                    establish_b3(link);io.restore_ram(link,original,out);result['application_ram_restored']=True
            finally:link.serial.close();save(out/'report.json',result)
    print('PASS 2512 beta33, real ASM ORG 0200 + S/T/R; all retained data and application RAM preserved',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','rehearse','functional','audit','install'))
    stage=parser.parse_args().stage;globals()[stage]()
