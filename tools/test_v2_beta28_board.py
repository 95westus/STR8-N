"""Execute 2512's exact proposed banks and retained SRAM, entirely offline."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta28-b23'
import argparse,json,re
from pathlib import Path
from test_v2_status import fresh,boot,snapshot
from test_v2_beta28_candidate import command,api
from test_v2_spi_resident import k
from test_v2_workspace import req
from beta4_migration import crc
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-beta28-b23'
META=json.loads((BUILD/'build.json').read_text())

def main(root):
    plan=json.loads((root/'upgrade/plan.json').read_text());array=(root/'retained/sram-prior/array-0.bin').read_bytes();checks=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    def fixture(key=None):
        cpu,m=fresh();m.banks=[bytearray((root/f'upgrade/expected-b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
        m.spi.devices[0].data[:]=array;m.fast=True
        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(root/'retained/devices-before/status.txt').read_bytes())[1].decode())
        m.bus.rtc_regs[:9]=raw;m.bus.ee[0xF2:0xF8]=m.banks[3][0x1C08:0x1C0E]
        k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
        if key:m.rx.extend(key)
        boot(cpu);return cpu,m
    cpu,m=fixture();assert b'2.0b28' in m.tx and m.ram[0x7D30]==0xA0
    original=snapshot(m);text=command(cpu,m,b'VERSION\r')
    assert b'STR8-N 2.0b28' in text and b'MONITOR A gen 00000028 VALID default' in text and b'MONITOR B gen 00000025 VALID' in text,text
    text=command(cpu,m,b'TIME\r');assert re.search(rb'2026-\d\d-\d\d \d\d:\d\d:\d\d',text),text
    passed('exact 2512 banks boot beta28 A with valid beta25 B, VERSION and TIME')
    text=command(cpu,m,b'APPS\r');assert all(n+b' FLASH B2' in text for n in [b'MAINT',b'SRAM',b'WORK',b'EDU']),text
    text=command(cpu,m,b'T 2\r');assert b'B2:' not in text and b'MAINT' not in text,text
    text=command(cpu,m,b'T 1\r');assert b'CLOCK' in text and b'MAINT' not in text,text
    for name,title,query in [('MAINT',b'BANK MAINT 2.3',b'?\r'),('SRAM',b'SRAM 1.3',b'T\r'),('WORK',b'WORK 1.3',b'?\r'),('EDU',b'EDU 1.3',b'?\r')]:
        text=command(cpu,m,('R '+name+'\r').encode());assert title in text and m.bank==2,(name,text[-500:])
        text+=command(cpu,m,query)
        if name=='SRAM':(root/'upgrade/model-sram-table.txt').write_bytes(text)
        text+=command(cpu,m,b'Q\r');assert text.endswith(b'B3> ') and m.bank==3
        assert snapshot(m)==original and not m.events,name
        passed(name+' flash launch/query/Q; no flash or retained device mutation')
    for bank in range(4):
        status,_=api(cpu,m,req(0),bank);assert status==0x40,(bank,status)
    passed('WORK 5003 compatibility entry returns all four caller banks and preserves invalid-layout error 40')
    # The API harness returns to a synthetic $0200 caller, not the command
    # interpreter. Reenter through the published RAM prompt ABI first.
    cpu.pc=0x7E67;boot(cpu)
    text=command(cpu,m,b'R CLOCK\r');assert b'CLOCK 1.6' in text,text
    text=command(cpu,m,b'STATUS\r');assert b'Running: yes' in text,text
    command(cpu,m,b'Q\r')
    assert snapshot(m)==original and not m.events
    passed('preserved B1 CLOCK loads and executes against unchanged resident service')
    # Both direct caller and utility reads must restore B2 after viewing B0/B1.
    pattern=bytes((i*7)&255 for i in range(4096));m.banks[0][:4096]=pattern
    text=command(cpu,m,b'R MAINT\rC 0 8 1 8\rY\r');assert b'VERIFIED' in text and bytes(m.banks[1][:4096])==pattern,text[-500:]
    text=command(cpu,m,b'V 0 8 1 8\r');assert b'MATCH' in text
    command(cpu,m,b'Q\r');passed('MAINT cross-bank copy/verify; RAM flash worker executes without ROM fetch while busy')
    cpu,m=fixture(b'B');assert b'2.0b25' in m.tx and m.ram[0x7D30]==0xB0
    assert b'EDU 1.3' in command(cpu,m,b'R EDU\r');command(cpu,m,b'Q\r')
    passed('retained beta25 B boots and launches native beta28 EDU through shared extension')
    assert crc((BUILD/'xip/utilities.bin').read_bytes())==0 and crc((BUILD/'version/asset.bin').read_bytes())==0
    assert (root/'upgrade/expected-b0.bin').read_bytes()==(root/'prior-verified/b0.bin').read_bytes()
    b3=(root/'upgrade/expected-b3.bin').read_bytes();prior=(root/'prior-verified/b3.bin').read_bytes()
    assert b3[:0x2000]==prior[:0x2000] and b3[0x3000:0x4000]==prior[0x3000:0x4000] and b3[0x7000:]==prior[0x7000:]
    passed('B0, RTC/journal identity tail, fallback monitor and fixed recovery exact preservation')
    report=dict(passed=True,checks=checks,build_sha256=sha((BUILD/'build.json').read_bytes()),expected_hashes=plan['expected_hashes'],retained_sram_sha256=sha(array),board_access=False)
    (root/'upgrade/beta28-board-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
