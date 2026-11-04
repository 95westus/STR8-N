"""Beta34 integration: copy the actual printed Store command and restore it."""
import hashlib
import json
import re
from pathlib import Path

import test_asm as a
from beta4_migration import crc
from test_v2_status import fresh, boot, layout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'BUILD/v2-beta34-candidate'
META = json.loads((OUT/'build.json').read_text())
checks = []


def command(cpu, text):
    print('COMMAND',text,flush=True)
    return a.command(cpu,text.encode()+b'\r')


def assemble_example(cpu, name):
    assert b'Paste source' in command(cpu,'PASTE')
    raw = (ROOT/f'examples/beta33/{name}.asm').read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r')+b'.\r'
    assert b'Error' not in a.command(cpu,raw)
    text = command(cpu,'ASM')
    assert b'OK ' in text,text
    save_line=re.search(rb'\r\n(S 1 AUTO [0-9A-F]{4} [0-9A-F]{4} PROGRAM)\r\n',text)
    assert save_line,text
    cpu.save_command=save_line[1].decode()
    n = int.from_bytes(cpu.memory.ram[a.S['RESULT_LEN']:a.S['RESULT_LEN']+2],'little')
    body = bytes(cpu.memory.ram[0x0200:0x0200+n])
    assert b'B3>' in command(cpu,'QUIT')
    return body


def passed(text):
    checks.append(text); print('PASS',text,flush=True)


def workflow():
    cpu, m = a.setup(shell=True)
    before = [bytes(b) for b in m.banks]
    body = assemble_example(cpu,'hello')
    assert len(body)==23 and b'OK\r\n' in command(cpu,'G 0200')
    assert [bytes(b) for b in m.banks]==before and not m.events
    assert cpu.save_command=='S 1 AUTO 0200 0216 PROGRAM'
    (OUT/'assembler/save-command-output.txt').write_text(cpu.save_command+'\n')
    text = command(cpu,cpu.save_command)
    assert b'Done' in text,text
    table = command(cpu,'T 1')
    assert b'PROGRAM' in table and b'0200-0216' in table,table
    m.ram[0x0200:0x0217] = b'\xCC'*23
    assert b'Done' in command(cpu,'R 1 PROGRAM L')
    assert bytes(m.ram[0x0200:0x0217])==body
    assert b'OK\r\n' in command(cpu,'G 0200')
    m.ram[0x0200:0x0217] = bytes(23)
    assert b'OK\r\n' in command(cpu,'R 1 PROGRAM')
    assert bytes(m.ram[0x0200:0x0217])==body
    assert bytes(m.banks[1][0x6000:])==before[1][0x6000:]
    assert all(bytes(m.banks[i])==before[i] for i in (0,2,3))
    assert not any(event[0]=='erase' for event in m.events)
    (OUT/'assembler/store-table-restore.txt').write_bytes(table)
    passed('typed source, assembly, public console/HOLD, flash S AUTO, T, restore-only, execution and restore/run; no erases or ASM overwrite')
    assert b'ASM 0.5' in command(cpu,'ASM')
    counter = assemble_example(cpu,'ram-counter')
    assert b'01\r\n' in command(cpu,'G 0200')
    assert b'02\r\n' in command(cpu,'G 0200')
    assert bytes(m.ram[0x0200:0x0200+len(counter)-1])==counter[:-1]
    passed('RAM program modifies its own counter and calls public HEX/PUTC/HOLD twice')


def refusal():
    for kind in ('payload','descriptor','header','vectors'):
        cpu,m = a.setup()
        m.bank=3
        if kind=='payload': m.banks[1][0x6200]^=1
        elif kind=='header': m.banks[1][0x6004]^=1
        elif kind=='descriptor':
            m.banks[3][0x6706]^=1
            m.banks[3][0x67FE:0x6800]=crc(m.banks[3][0x6000:0x67FE]).to_bytes(2,'big')
        else: m.banks[1][0x7FFA]^=1
        before = bytes(m.ram[0x200:0x6500])
        flash = [bytes(b) for b in m.banks]
        result = command(cpu,'ASM')
        assert b'App invalid/incompatible' in result and b'ASM>' not in result,result
        assert bytes(m.ram[0x200:0x6500])==before
        assert [bytes(b) for b in m.banks]==flash and not m.events
        assert m.bank==3
    cpu,m=a.setup();m.bank=3
    assert b'App takes no arguments' in command(cpu,'ASM EXTRA')
    assert b'BATCH stopped: unsupported' in command(cpu,'BATCH ASM;VERSION')
    passed('corrupt payload/header/descriptor/vectors refused before workspace writes; arguments and unsupported ASM BATCH refused')


def edu_on():
    cpu,m=a.fixture(primary=layout())
    m.fast=True
    retained=(bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
    boot(cpu)
    assert b'2.0b34' in m.tx and b'EDU ON' in m.tx
    assert b'ASM installed B1:E000' in command(cpu,'APPS')
    assert b'ASM 0.5' in command(cpu,'ASM')
    assemble_example(cpu,'hello')
    assert b'OK\r\n' in command(cpu,'G 0200')
    for name,title in [('MAINT',b'MAINT 2.4'),('SRAM',b'SRAM 1.4'),('WORK',b'WORK 1.4'),('EDU',b'EDU 1.4')]:
        text=command(cpu,name);assert title in text,(name,text)
        command(cpu,'Q')
    assert b'BATCH done' in command(cpu,'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
    assert retained==(bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
    assert not m.events
    passed('EDU ON boot, APPS descriptor, ASM/example, all four native providers and BATCH; EEPROM/RTC/SRAM unchanged')


def main():
    workflow();refusal();edu_on()
    assert (OUT/'candidate/b2.bin').read_bytes()[0x5800:]==(ROOT/'BUILD/v2-beta32-candidate/candidate/b2.bin').read_bytes()[0x5800:]
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(ROOT/'BUILD/v2-beta32-candidate/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    assert (OUT/'str8n-v2-recovery-e000-efff.bin').read_bytes()[2048:] == (ROOT/'BUILD/v2-beta32-candidate/str8n-v2-recovery-e000-efff.bin').read_bytes()[2048:]
    result=dict(passed=True,version='2.0b34',checks=checks,build_sha256=hashlib.sha256((OUT/'build.json').read_bytes()).hexdigest(),
        board_access=False,boards_flashed=False,hardware_tested=False,stable_release=False)
    (OUT/'beta34-integration.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
