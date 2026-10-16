"""Exact 2609 bank/SRAM fixture: beta32 A, retained B27 and native provider."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-2609-candidate'
import argparse
import json
from pathlib import Path
import re

from beta4_migration import read_s19
from build_v2_spi_resident import sha
from test_v2_status import fresh,boot,snapshot
from test_v2_spi_resident import k
from test_v2_sram_store import console

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-beta32-2609-candidate'
META=json.loads((BUILD/'build.json').read_text())
cmd=lambda cpu,m,line:console(cpu,m,line,limit=100000000)


def main(root):
    plan=json.loads((root/'upgrade/plan.json').read_text())
    array=(root/'retained/sram-prior/array-0.bin').read_bytes();checks=[]
    def passed(text):checks.append(text);print('PASS',text,flush=True)
    def fixture(fallback=False,installer_return=False):
        cpu,m=fresh();m.fast=True
        m.banks=[bytearray((root/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)]
        m.spi.banks=m.banks;m.spi.devices[0].data[:]=array
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(root/'retained/devices-before/status.txt').read_bytes())[1].decode())
        m.bus.rtc_regs[:9]=raw
        ee=(root/'retained/devices-before/eeprom-0.bin').read_bytes()
        m.bus.ee[:128]=ee[:128];m.bus.ee[0xFF]=ee[128];m.bus.ee[0xF0:0xF8]=ee[129:137]
        if fallback:
            # Run directly to the real retained startup window before injecting
            # B; use source-profile symbols, not the former 2512 F addresses.
            k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
            m.rx.extend(b'B')
        if installer_return:
            # Establish the source worker/vector RAM, then enter only the
            # modeled installer success-only print/return trampoline.
            saved=m.banks
            m.banks=[bytearray((root/f'prior-verified/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
            boot(cpu)
            assert b'2.0b27' in m.tx
            m.banks=saved;m.spi.banks=m.banks
            cells,_=read_s19(root/'upgrade/installer.s19')
            for a,v in cells.items():m.ram[a]=v
            sy=json.loads((BUILD/'migrator/manifest.json').read_text())['symbols']
            n=sy['V2W_END']-0x7800;m.ram[0x7800:0x7800+n]=bytes(cells[sy['MIG_WORKER']+i] for i in range(n))
            cpu.x=sy['MIG_DONE']&255;cpu.y=sy['MIG_DONE']>>8;cpu.pc=plan['success_checkpoint']-3;m.tx.clear()
        boot(cpu);return cpu,m

    cpu,m=fixture(installer_return=True)
    assert b'MIGRATION VERIFIED; READY FOR J3' in m.tx and b'2.0b32' in m.tx
    assert m.ram[0x7D30]==0xA0
    assert plan['expected_wear_peak'].encode() in m.tx
    passed('Source B27 worker -> successful installer return -> beta32 A with retained F31B')
    original=snapshot(m)
    text=cmd(cpu,m,b'VERSION\rTIME\rAPPS\rT\r')
    assert b'2.0b32' in text and b'MONITOR B gen 00000027 VALID' in text
    assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU'])
    assert b'(-05:00)' in text and b'Board: 2609' in text
    passed('VERSION/TIME/APPS/T resolve new ABI and retained slots/name/offset')
    for name,title,query in [('MAINT',b'MAINT 2.4',b'?'),('SRAM',b'SRAM 1.4',b'T'),('WORK',b'WORK 1.4',b'?'),('EDU',b'EDU 1.4',b'?')]:
        assert title in cmd(cpu,m,name.encode()+b'\r')
        cmd(cpu,m,query+b'\r');assert cmd(cpu,m,b'Q\r').endswith(b'B3> ')
        assert snapshot(m)==original and not m.events
        passed(name+' bare alias/query/Q preserves all persistent storage')
    text=cmd(cpu,m,b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r')
    assert b'BATCH done' in text and text.endswith(b'B3> '),text
    text=cmd(cpu,m,b'BATCH SRAM;BOGUS;Q\r')
    assert b'BATCH stopped: command failed' in text and text.endswith(b'SRAM> '),text
    cmd(cpu,m,b'Q\r')
    text=cmd(cpu,m,b'BATCH MAINT;NAME TEST;Q\r');assert text.endswith(b'Type YES: '),text
    text=cmd(cpu,m,b'\x1b');assert b'BATCH canceled' in text and text.endswith(b'BM> '),text
    cmd(cpu,m,b'Q\r')
    passed('A-bound BATCH four-provider handoff, error stop and confirmation ESC')
    text=cmd(cpu,m,b'BATCH SRAM;G CLK;Q\r')
    assert b'SRAM: 4A' in text and b'BATCH stopped' in text and text.endswith(b'SRAM> '),text
    cmd(cpu,m,b'Q\r')
    text=cmd(cpu,m,b'SRAM\rG CLK\rSTATUS\rQ\r')
    assert b'CLOCK 1.8' in text and b'Running: yes' in text and text.endswith(b'B3> '),text
    assert snapshot(m)==original and not m.events
    passed('Retained unmodified CLK 1.8 executes manually and is safely refused inside BATCH')
    text=cmd(cpu,m,b'J3\r')
    assert b'2.0b32' in text and text.count(b'FLASH: wear check ')==1 and plan['expected_wear_peak'].encode() in text
    assert snapshot(m)==original and not m.events
    passed('J3 defaults to beta32 A; correct decimal wear maximum once; all retained bytes unchanged')
    cpu,m=fixture(fallback=True)
    assert b'2.0b27' in m.tx and m.ram[0x7D30]==0xB0
    prior=snapshot(m);text=cmd(cpu,m,b'VERSION\rTIME\r')
    assert b'2.0b27' in text and b'Board: 2609' in text and snapshot(m)==prior and not m.events
    passed('Retained B27 boots and provides core VERSION/TIME with new shared assets')
    report=dict(passed=True,build_sha256=sha((BUILD/'build.json').read_bytes()),expected_hashes=plan['expected_hashes'],
                checks=checks,installer_return_verified=True,j3_reset_verified=True,fallback_boot_verified=True,
                retained_sram_sha256=sha(array),legacy_clk_preserved=True,board_access=False)
    (root/'upgrade/beta32-board-test-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
