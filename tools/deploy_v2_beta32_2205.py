"""Exact-backup beta32 prerelease on 2205; no 2.1 code or fleet changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

os.environ['STR8_RTC_BUILD'] = 'BUILD/v2-beta32-candidate'
import beta4_migration as m
from deploy_v2_beta32_2512 import audit_build
from qualify_v2_spi_install import load_image, write
from qualify_v2_spi_storage import memory_request
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/qualification/beta32-2205-2026-10-16'
BUILD = ROOT / 'BUILD/v2-beta32-candidate'
PEER = ROOT / 'output/qualification/fleet-as-is-backup-2026-10-16/2512'
read = lambda path: json.loads(path.read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()


def port(board):
    from serial.tools.list_ports import comports
    return next(p.device for p in comports() if p.serial_number == SERIALS[board])


def banks_at(folder, prefix='flash-1-b'):
    return [(folder / f'{prefix}{b}.bin').read_bytes() for b in range(4)]


def prepare():
    meta = audit_build()
    prior = OUT / 'prior'
    assert read(prior / 'report.json')['passed']
    before = banks_at(prior)
    peer = banks_at(PEER)
    peer_report=read(PEER/'report.json');assert peer_report['passed']
    for b,image in enumerate(peer):assert sha(image)==peer_report['files'][f'flash-1-b{b}.bin']['sha256']
    assert peer[2]==(BUILD/'candidate/b2.bin').read_bytes()
    assert peer[3][0x6000:0x7000]==(BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    assert peer[3][:4096]==(BUILD/'str8n-rtc-component-8000-8fff.bin').read_bytes()
    assert peer[3][0x1000:0x1C00]==(BUILD/'str8n-journal-9000-9fff.bin').read_bytes()[:3072]
    assert all(before[b] == (prior / f'flash-2-b{b}.bin').read_bytes() for b in range(4))
    assert before[3][0x7000:] == peer[3][0x7000:] == (BUILD / 'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    old = ROOT / 'BUILD/v2-beta25-b23'
    assert before[3][0x3000:0x4000] == (old / 'str8n-v2-recovery-slot-b0.bin').read_bytes()
    assert not any(before[3][i:i+4]==b'BN\x01\0' for i in range(0x1C00,0x2000,32)), 'Preserve and model any existing board name'
    assert before[1][0x3000:0x3008] == b'SR\x01\x3f\x00\x20\x92\x22'
    body = (BUILD / 'clock/clock.bin').read_bytes()
    clock_record = (BUILD / 'clock/storage.bin').read_bytes()
    assert clock_record[:24] == b'SR\x01\x3f\x00\x20' + len(body).to_bytes(2, 'little') + b'CLOCK'.ljust(16, b'\0')
    assert clock_record[24:24+len(body)] == body and len(clock_record) == 12288
    final = [bytearray(b) for b in before]
    final[2][:] = peer[2]
    final[3][:0x1C00] = peer[3][:0x1C00]
    final[3][0x2000:0x4000] = peer[3][0x2000:0x4000]
    final[3][0x6000:0x7000] = peer[3][0x6000:0x7000]
    final[1][0x3000:0x6000] = clock_record
    assert final[3][0x2000:0x3000] == (ROOT / 'BUILD/v2-beta28-b23/str8n-v2-recovery-slot-a0.bin').read_bytes()
    assert final[3][0x3000:0x4000] == (BUILD / 'str8n-v2-recovery-slot-b0.bin').read_bytes()
    # Publish valid shared assets and CLOCK before the monitor commits. The
    # unchanged fixed F validates source beta25, fallback beta28 and beta32.
    order = [(3,12)]
    order += [(2,s) for s in range(15,7,-1) if before[2][(s-8)*4096:(s-7)*4096] != final[2][(s-8)*4096:(s-7)*4096]]
    order += [(1,s) for s in (13,12,11)]
    order += [(3,s) for s in (9,14,10,11) if before[3][(s-8)*4096:(s-7)*4096] != final[3][(s-8)*4096:(s-7)*4096]]
    assert len(order) == 15 and order[-1] == (3,11)
    j = m.journal(before[3]); assert j is not None
    cfg = bytearray(j[8:24]); assert cfg[14:] == m.config_sum(cfg)
    cfg[7:13] = b'P\xB0' + (44).to_bytes(4, 'little'); cfg[14:] = m.config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i], 'little') for i in range(32)]
    oldcounts = counts[:]
    for bank, sector in order:
        i = bank*8 + sector-8; counts[i] += 1; assert counts[i] < 0xFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, int.from_bytes(j[4:8], 'little')+1) + b'\xff'*(4096-128)
    assert final[0] == before[0] and final[1][:0x3000] == before[1][:0x3000] and final[1][0x6000:] == before[1][0x6000:]
    assert final[3][0x1C00:0x2000] == before[3][0x1C00:0x2000]
    assert final[3][0x5000:0x6000] == before[3][0x5000:0x6000] and final[3][0x7000:] == before[3][0x7000:]
    mf = read(BUILD / 'migrator/manifest.json'); assert len(order) <= mf['max_sectors']
    cells, entry = m.read_s19(BUILD / 'migrator/rtc-migrator-2000.s19')
    cells[mf['count']] = len(order); cells[mf['commit_after']] = 0
    sy = mf['symbols']; call = sy['MIG_HALT']-3; printer = sy['MIG_PRINT']; tail = max(cells)+1
    assert bytes(cells[call+i] for i in range(3)) == b'\x20'+printer.to_bytes(2,'little')
    cells.update(dict(enumerate(b'\x20'+printer.to_bytes(2,'little')+b'\x4C\x04\xF0', tail)))
    cells.update(dict(enumerate(b'\x20'+tail.to_bytes(2,'little'), call)))
    token = 'MIGRATION VERIFIED; READY FOR J3'
    message = token.encode()+b'\r\n\0'; assert len(message) <= sy['MIG_BAD']-sy['MIG_DONE']
    cells.update(dict(enumerate(message, sy['MIG_DONE'])))
    pending = [bytearray(b) for b in before]; payloads = []
    for index, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096; data = bytearray(final[bank][offset:offset+4096])
        address = (sector<<12)+31 if bank == 3 and sector in (10,11) else 0xB003 if (bank,sector) == (1,11) else 0
        if address: data[address-(sector<<12)] = 255
        row = bytes((sector<<4,)) + m.fnv(pending[bank]).to_bytes(4,'little') + m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row, mf['table']+9*index))); cells[mf['banks']+index] = bank
        cells[mf['commits']+index] = bank+1 if address else 0
        cells.update(dict(enumerate(address.to_bytes(2,'little')+b'\0\0', mf['commit_addresses']+4*index)))
        pending[bank][offset:offset+4096] = data
        if address: pending[bank][address-0x8000] = 0 if bank == 3 else 0x3F
        payloads.append(data)
    assert pending == final
    out = OUT / 'upgrade'; out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry); (out / 'installer.s19').write_bytes(installer)
    peak = max(counts); index = counts.index(peak)
    plan = dict(board='2205', version='2.0b32', generation=44, target_build=str(BUILD.relative_to(ROOT)),
                prior_directory='prior-verified', source=dict(active_page=0xB0,version='2.0b25'),
                steps=[dict(bank=b,sector=s) for b,s in order], prior_hashes=[sha(b) for b in before],
                expected_hashes=[sha(b) for b in final], installer_sha256=sha(installer),
                build_sha256=sha((BUILD/'build.json').read_bytes()), template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
                storage_update=True, commit_records=[dict(bank=1,address=0xB000)],
                source_generation=37, config=cfg.hex(), counts_before=oldcounts, counts_after=counts,
                physical_reset_required=False, returns_to_monitor=True, success_checkpoint=tail+3, completion_token=token,
                fixed_recovery_preserved=True, old_maint_record_preserved=True, clock_version='1.9',
                expected_wear_peak=f'Sector B{index//8}:{8+index%8:X}, max {peak} tracked erases.')
    save(out/'plan.json', plan)
    verified = OUT/'prior-verified'; verified.mkdir(exist_ok=False)
    for i, data in enumerate(before): (verified/f'b{i}.bin').write_bytes(data)
    for i, data in enumerate(final): (out/f'expected-b{i}.bin').write_bytes(data)
    for i, data in enumerate(payloads): (out/f'transfer-{i:02d}.bin').write_bytes(data)
    print('PREPARED beta32 B, beta28 A, CLOCK 1.9; fifteen sectors; fixed F unchanged', order, flush=True)


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def rehearse():
    import test_v2_rtc_upgrade as test
    plan = read(OUT/'upgrade/plan.json'); expected = banks_at(OUT/'upgrade', 'expected-b')
    base = test.Memory; instances = []
    class Memory(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs); instances.append(self)
        def mutated(self, kind, address, value):
            assert not (self.bank == 3 and address >= 0xF000), 'Fixed F must stay unchanged'
            if self.bank == 3 and address in (0xA01F,0xB01F) and value == 0:
                start = (address & 0xF000)-0x8000
                assert self.banks[2] == expected[2], 'Shared utilities must precede monitor publication'
                assert bytes(self.banks[3][start:start+4096]) == expected[3][start:start+4096]
            super().mutated(kind,address,value)
    test.Memory = Memory
    prior_argv = sys.argv
    try:
        sys.argv = ['rehearse','--root',str(OUT)]; test.main()
    finally:
        sys.argv = prior_argv; test.Memory = base
    assert instances[0].events[-1] == ('program',3,0xB01F,0)
    print('PASS source guards, exact allowlist, full CLOCK commit, beta32 monitor commit last', flush=True)


def functional():
    from test_v2_status import fresh, boot
    from test_v2_sram_store import console
    plan = read(OUT/'upgrade/plan.json'); expected = banks_at(OUT/'upgrade','expected-b')
    prior = OUT/'prior'; array = (prior/'spi-sram-1.bin').read_bytes(); body = (BUILD/'clock/clock.bin').read_bytes()
    def fixture(fallback=False, return_path=False):
        cpu, mem = fresh(); mem.fast = True
        mem.banks = [bytearray(b) for b in expected]; mem.spi.banks = mem.banks
        mem.spi.devices[0].data[:] = array
        raw = (prior/'rtc-registers-1.bin').read_bytes(); assert raw[3]&0x10 == 0, 'Model startup-history reconciliation separately if power fail is pending'
        mem.bus.rtc_regs[:32] = raw
        mem.bus.ee[:128] = (prior/'eeprom-1.bin').read_bytes()
        mem.bus.ee[0xF0:0xF8] = (prior/'eeprom-protected-1.bin').read_bytes(); mem.bus.ee[255] = (prior/'eeprom-status-1.bin').read_bytes()[0]
        if return_path:
            mem.banks = [bytearray(b) for b in banks_at(prior)]; mem.spi.banks = mem.banks
            boot(cpu); assert mem.ram[0x7D30] == 0xB0
            mem.banks = [bytearray(b) for b in expected]; mem.spi.banks = mem.banks
            cells,_ = m.read_s19(OUT/'upgrade/installer.s19')
            for address,value in cells.items(): mem.ram[address] = value
            sy = read(BUILD/'migrator/manifest.json')['symbols']; n = sy['V2W_END']-0x7800
            mem.ram[0x7800:0x7800+n] = bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
            cpu.x = sy['MIG_DONE']&255; cpu.y = sy['MIG_DONE']>>8; cpu.pc = plan['success_checkpoint']-3; mem.tx.clear()
        if fallback:
            from test_v2_spi_resident import k
            at = read(BUILD/'build.json')['boot']['BOOT_STARTUP_DOTS']
            k.model.run(cpu,lambda: cpu.pc == at,30000000); mem.rx.extend(b'A')
        boot(cpu); return cpu,mem
    cpu, mem = fixture(return_path=True)
    assert b'2.0b32' in mem.tx and mem.ram[0x7D30] == 0xB0 and plan['expected_wear_peak'].encode() in mem.tx
    transcript = bytearray(mem.tx)
    def command(line):
        print('MODEL',line,flush=True)
        result = console(cpu,mem,line.encode()+b'\r',limit=100000000); transcript.extend(result)
        (OUT/'upgrade/model-functional-progress.txt').write_bytes(transcript)
        return result
    text = command('VERSION'); assert b'Board: unnamed' in text and b'2.0b32' in text
    text = command('APPS'); assert all(n+b' FLASH B2' in text for n in (b'MAINT',b'SRAM',b'WORK',b'EDU'))
    text = command('R CLOCK'); assert b'CLOCK 1.9' in text; command('Q')
    mem.ram[0x2000:0x2000+len(body)] = body
    text = command(f'SRAM\rS CLK 2000 {0x2000+len(body)-1:04X} 2000\rQ')
    assert b'SRAM: 00' in text and text.endswith(b'B3> ')
    changed_array = bytes(mem.spi.devices[0].data)
    program_limit = int.from_bytes(array[5:7],'little')*256
    assert program_limit in (16384,32768,49152,65536)
    assert changed_array[program_limit:] == array[program_limit:]
    for line in ('BATCH SRAM;G CLK;Q','BATCH SRAM;G CLK;STATUS;Q','BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q'):
        text = command(line); assert b'BATCH done' in text and text.endswith(b'B3> ')
        if 'MAINT' in line: assert all(title in text for title in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
    text = command('BATCH SRAM;BOGUS;Q'); assert b'BATCH stopped: command failed' in text and text.endswith(b'SRAM> '); command('Q')
    text = command('BATCH MAINT;NAME TEST;Q'); assert text.endswith(b'Type YES: ')
    text = console(cpu,mem,b'\x1b',limit=100000000); transcript.extend(text); assert b'BATCH canceled' in text; command('Q')
    text = command('J3'); assert b'2.0b32' in text and plan['expected_wear_peak'].encode() in text
    assert [bytes(b) for b in mem.banks] == expected and bytes(mem.spi.devices[0].data) == changed_array
    assert bytes(mem.bus.ee[:128]) == (prior/'eeprom-1.bin').read_bytes()
    assert bytes(mem.bus.rtc_regs[:9])[7:] == (prior/'rtc-registers-1.bin').read_bytes()[7:9]
    (OUT/'expected-sram.bin').write_bytes(changed_array); (OUT/'upgrade/model-functional.txt').write_bytes(transcript)
    cpu, mem = fixture(fallback=True); assert b'2.0b28' in mem.tx and mem.ram[0x7D30] == 0xA0
    result = console(cpu,mem,b'VERSION\rR MAINT\rQ\r',limit=100000000)
    assert b'Board: unnamed' in result and b'MAINT 2.4' in result
    save(OUT/'upgrade/functional.json',dict(passed=True, expected_hashes=plan['expected_hashes'],
         build_sha256=plan['build_sha256'], prior_sram_sha256=sha(array), expected_sram_sha256=sha(changed_array),
         clock_sha256=sha(body), fallback_version='2.0b28', source_return_verified=True,
         utilities_verified=True,batch_completion_error_escape_verified=True,workspace_preserved=True,
         program_limit=program_limit,rtc_eeprom_preserved=True))
    print('PASS installer return, both monitor boots, all providers, flash and SRAM CLOCK 1.9, BATCH/error/ESC, RTC/EEPROM/workspace',flush=True)


def audit():
    audit_build(); plan=read(OUT/'upgrade/plan.json'); proof=read(OUT/'upgrade/model-check.json'); functional=read(OUT/'upgrade/functional.json')
    assert proof['passed'] and proof['stale_preimage_refused'] and proof['corrupt_payload_refused'] and functional['passed']
    assert plan['installer_sha256']==proof['installer_sha256']==sha((OUT/'upgrade/installer.s19').read_bytes())
    assert proof['expected_hashes']==functional['expected_hashes']==plan['expected_hashes']
    assert functional['build_sha256']==plan['build_sha256']==sha((BUILD/'build.json').read_bytes())
    assert plan['template_manifest_sha256']==sha((BUILD/'migrator/manifest.json').read_bytes())
    assert proof['record_commits']==[[1,0xB000]] and read(OUT/'prior/report.json')['passed']
    for b,h in enumerate(plan['expected_hashes']): assert sha((OUT/f'upgrade/expected-b{b}.bin').read_bytes())==h


def dump_ram(link):
    return b''.join(link.dump(a,min(a+4095,0x64FF)) for a in range(0x0200,0x6500,4096))


def restore_ram(link, original, out):
    image=m.s19(dict(enumerate(original,0x0200)),0x0200); (out/'ram-restore-load-only.s19').write_bytes(image)
    link.command('L',b'S19')
    for row in image.splitlines(): link.send(row+b'\r\n');time.sleep(.04)
    link.until(b'\r\nB3> ')
    actual=dump_ram(link); assert actual==original,'Application RAM restoration mismatch'
    (out/'ram-restored.bin').write_bytes(actual)
    save(out/'ram-restore-needed.json',dict(needed=False,sha256=sha(actual)))


def array_read(link,label):
    load_image(link,ROOT/'BUILD/v2-spi-resident/hardware-client/client.s19');blocks=[]
    for block in range(16):
        write(link,0x3E20,b'\x01\x03\0');write(link,0x3E00,memory_request(1,block*8192))
        link.command('G 2003');r=link.dump(0x3E10,0x3E38)
        assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
        blocks.append(link.dump(0x4000,0x5FFF));print(label,block+1,'/16',flush=True)
    return b''.join(blocks)


def retained(link,out,stage):
    load_image(link,ROOT/'BUILD/board-state-reader/reader.s19');results={}
    for name,dev,offset,count in [('eeprom',0xAE,0,128),('eeprom-protected',0xAE,0xF0,8),('eeprom-status',0xAE,255,1),('rtc-registers',0xDE,0,32),('rtc-sram',0xDE,32,64)]:
        write(link,0x2F00,bytes((dev,offset,count)));link.command('G 2000');status=link.dump(0x2F10,0x2F15)
        assert status[0]==0 and status[5]==count and status[1]==status[2]
        data=link.dump(0x3000,0x3000+count-1);(out/f'{stage}-{name}.bin').write_bytes(data);results[name]=data
    return results


def install():
    audit();plan=read(OUT/'upgrade/plan.json');proof=read(OUT/'upgrade/functional.json')
    out=OUT/'hardware';out.mkdir(exist_ok=False);original=None;needed=False
    result=dict(board='2205',passed=False,version='2.0b32',application_ram_restored=False)
    with serial_lease('beta32-2205-install',priority=True),(out/'serial.jsonl').open('x') as log:
        link=m.Link(port('2205'),log)
        try:
            establish_b3(link);assert link.dump(0x7D30,0x7D30)==b'\xB0'
            original=dump_ram(link);(out/'ram-prior.bin').write_bytes(original);assert dump_ram(link)==original
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                image=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(image)==plan['prior_hashes'][bank],f'Stale B{bank}; no writes'
                (out/f'preflight-b{bank}.bin').write_bytes(image);print('PASS fresh preimage B'+str(bank),flush=True)
            link.command('B3');needed=True;save(out/'ram-restore-needed.json',dict(needed=True,sha256=sha(original)))
            before=retained(link,out,'before')
            for name in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):
                assert before[name]==(OUT/f'prior/{name}-1.bin').read_bytes(),name+' changed; requalify before flashing'
            assert before['rtc-registers'][7:]==(OUT/'prior/rtc-registers-1.bin').read_bytes()[7:] and before['rtc-registers'][3]&0x10==0
            load_image(link,OUT/'upgrade/installer.s19')
            link.command('G 2000',b'Y then Enter> ');link.send(b'Y\r')
            for index,step in enumerate(plan['steps']):
                link.until(f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode(),90)
                payload=(OUT/f'upgrade/transfer-{index:02d}.bin').read_bytes()
                for offset in range(0,4096,64):link.send(payload[offset:offset+64]);time.sleep(.01)
                print('FLASH 2205',f'B{step["bank"]}:{step["sector"]:X}',flush=True)
            text=link.until(plan['completion_token'].encode(),90)+link.until(b'\r\nB3> ',90)
            assert b'STR8-N 2.0b32' in text and link.dump(0x7D30,0x7D30)==b'\xB0'
            (out/'installer-return.txt').write_bytes(text)
            assert sha(array_read(link,'Fresh retained SRAM guard'))==proof['prior_sram_sha256']
            assert load_image(link,BUILD/'clock/clock.s19')==proof['clock_sha256']
            body=(BUILD/'clock/clock.bin').read_bytes();link.command('SRAM',b'SRAM> ')
            text=link.command(f'S CLK 2000 {0x2000+len(body)-1:04X} 2000',b'SRAM> ');assert b'SRAM: 00' in text;text+=link.command('Q')
            (out/'save-clk.txt').write_bytes(text)
            from run_v2_beta32_soak import batch
            for name,line in [('batch-clock','SRAM;G CLK;Q'),('batch-clock-status','SRAM;G CLK;STATUS;Q'),('batch-providers','MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')]:
                text=batch(link,line);(out/f'{name}.txt').write_bytes(text)
                if name.startswith('batch-clock'):assert b'CLOCK 1.9' in text
                if name=='batch-providers':assert all(title in text for title in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
            text=link.command('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed')+link.until(b'SRAM> ')+link.command('Q')
            (out/'batch-error.txt').write_bytes(text)
            text=link.command('BATCH MAINT;NAME TEST;Q',b'Type YES: ');link.send(b'\x1b')
            text+=link.until(b'BATCH canceled')+link.until(b'BM> ')+link.command('Q');(out/'batch-escape.txt').write_bytes(text)
            for command in ('VERSION','TIME','APPS','T 1','M1','W','C'):
                text=link.command(command);(out/f'query-{command.replace(" ","-")}.txt').write_bytes(text)
                if command=='VERSION':assert b'Board: unnamed' in text and b'2.0b32' in text and b'MONITOR A gen 00000028 VALID' in text
                if command=='TIME':assert b'(-05:00)' in text
                if command=='APPS':assert all(n+b' FLASH B2' in text for n in (b'MAINT',b'SRAM',b'WORK',b'EDU'))
            text=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.9' in text
            text+=link.command('STATUS',b'CLOCK> ')+link.command('HISTORY',b'CLOCK> ')+link.command('EUI',b'CLOCK> ')+link.command('Q')
            (out/'flash-clock.txt').write_bytes(text)
            link.send(b'J3\r');text=link.until(b'A/B/S,Enter default [3s]: ');link.send(b'A');text+=link.until(b'\r\nB3> ')
            assert b'STR8-N 2.0b28' in text and link.dump(0x7D30,0x7D30)==b'\xA0';(out/'fallback-boot.txt').write_bytes(text)
            text=link.command('J3');assert b'STR8-N 2.0b32' in text and plan['expected_wear_peak'].encode() in text
            assert text.count(b'FLASH: wear check ')==1;(out/'final-boot.txt').write_bytes(text)
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==plan['expected_hashes'][bank],bank;(out/f'final-b{bank}.bin').write_bytes(data)
                print('PASS final full flash B'+str(bank),flush=True)
            link.command('B3');actual=array_read(link,'Final SRAM verification')
            assert sha(actual)==proof['expected_sram_sha256'];(out/'final-sram.bin').write_bytes(actual)
            after=retained(link,out,'after')
            for name in ('eeprom','eeprom-protected','eeprom-status','rtc-sram'):assert after[name]==before[name],name+' changed'
            assert after['rtc-registers'][7:]==before['rtc-registers'][7:]
            assert after['rtc-registers'][3]&0x38==before['rtc-registers'][3]&0x38
            result.update(passed=True,monitor='B',fallback='2.0b28 A',clock='1.9',native_utilities=True,
                          batch_completion_error_escape=True,j3_verified=True,all_flash_verified=True,
                          sram_matches_model=True,workspace_preserved=True,rtc_eeprom_history_identity_preserved=True,
                          fixed_recovery_preserved=True,wdc_backup_preserved=True,erase_counts_accounted=True)
        except Exception as error:
            result['error']=repr(error);raise
        finally:
            try:
                if needed and original is not None:
                    restore_ram(link,original,out);result['application_ram_restored']=True
            finally:
                link.serial.close();save(out/'report.json',result)
    print('PASS 2205 complete beta32 prerelease; all preservation and functional checks',flush=True)


def peer():
    audit_build();out=OUT/'peer-2512';out.mkdir(exist_ok=False);original=None;needed=False
    with serial_lease('beta32-2512-confirm',priority=True),(out/'serial.jsonl').open('x') as log:
        link=m.Link(port('2512'),log)
        try:
            establish_b3(link);original=dump_ram(link);(out/'ram-prior.bin').write_bytes(original)
            needed=True;save(out/'ram-restore-needed.json',dict(needed=True,sha256=sha(original)))
            text=link.command('VERSION');assert b'Board: 2512' in text and b'2.0b32' in text;(out/'version.txt').write_bytes(text)
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert data==(PEER/f'flash-1-b{bank}.bin').read_bytes();(out/f'b{bank}.bin').write_bytes(data)
            link.command('B3')
            from run_v2_beta32_soak import batch
            text=batch(link,'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q');assert all(t in text for t in (b'MAINT 2.4',b'SRAM 1.4',b'WORK 1.4',b'EDU 1.4'))
            (out/'providers.txt').write_bytes(text)
            text=batch(link,'SRAM;G CLK;Q');assert b'CLOCK 1.9' in text;(out/'batch-clock.txt').write_bytes(text)
            save(out/'report.json',dict(passed=True,board='2512',version='2.0b32',clock='1.9',full_flash_unchanged=True,batch_verified=True,flash_written=False,soak_started=False))
        finally:
            try:
                if needed and original is not None:restore_ram(link,original,out)
            finally:link.serial.close()
    print('PASS 2512 unchanged complete beta32 prerelease, providers and CLOCK BATCH',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','rehearse','functional','install','peer'))
    globals()[parser.parse_args().stage]()
