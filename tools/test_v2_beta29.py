"""Exercise beta29 reference images in the CPU model; no board access."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta29-candidate'
import json,re
from pathlib import Path
from test_v2_status import fresh,boot,snapshot,layout
from test_v2_sram_store import console,fast_transfer
from test_v2_spi_resident import k
from build_v2_spi_resident import sha
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-beta29-candidate';META=json.loads((OUT/'build.json').read_text());X=json.loads((OUT/'xip/build.json').read_text());S=X['symbols']
EVIDENCE=ROOT/'output/qualification/beta28-2026-10-15/2512'

def fixture(key=None,corrupt=None):
    cpu,m=fresh();m.banks=[bytearray((OUT/f'candidate/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks
    base=type(m)
    class StrictMemory(base):
        def __getitem__(self,a):
            if isinstance(a,int):assert not 0x7F00<=a<0x7F80,('I/O used as RAM',hex(a),hex(self.cpu.pc))
            return super().__getitem__(a)
        def __setitem__(self,a,v):
            if isinstance(a,int):assert not 0x7F00<=a<0x7F80,('I/O used as RAM',hex(a),hex(self.cpu.pc))
            return super().__setitem__(a,v)
    m.__class__=StrictMemory
    if corrupt=='crc':m.banks[2][0x100]^=1
    if corrupt=='old':m.banks[2][:]=(OUT.parent/'v2-beta28-b23/candidate/b2.bin').read_bytes()
    m.spi.devices[0].data[:]=(EVIDENCE/'retained/sram-final/array-0.bin').read_bytes();m.fast=True
    raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(EVIDENCE/'retained/devices-after/status.txt').read_bytes())[1].decode());m.bus.rtc_regs[:9]=raw
    k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
    if key:m.rx.extend(key)
    boot(cpu);return cpu,m

def cmd(cpu,m,line):return console(cpu,m,line,limit=100000000)

def main():
    checks=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    cpu,m=fixture();assert b'2.0b29' in m.tx and m.ram[0x7D30]==0xB0,bytes(m.tx[-400:])
    original=snapshot(m);passed('beta29 B boot, beta28 A retained, no startup storage writes')
    text=cmd(cpu,m,b'?\r');assert b'S bank flash start end [name]' in text and b'BATCH cmd;cmd' in text,text
    passed('full monitor help preserved in flash, including BATCH syntax')
    text=cmd(cpu,m,b'BATCH VERSION;TIME\r');print(text.decode(errors='replace'),flush=True)
    assert b'2.0b29' in text and b'BATCH done' in text and text.endswith(b'B3> '),text[-1000:]
    assert snapshot(m)==original and not m.events
    passed('monitor BATCH sequential VERSION/TIME completes and preserves storage')
    text=cmd(cpu,m,b'BATCH B9;VERSION\r');assert b'BATCH stopped: command failed' in text and b'Running:' not in text,text
    passed('monitor parser error discards remaining commands')
    for line in [b'BATCH ;VERSION\r',b'BATCH VERSION;;TIME\r',b'BATCH VERSION;\r']:
        text=cmd(cpu,m,line);assert b'BATCH: empty/long' in text and b'Running:' not in text,text
    passed('whole-list validation rejects empty commands before executing any prefix')
    text=cmd(cpu,m,b'BATCH R SRAM;T;Q;VERSION\r');assert b'SRAM: 40' in text and b'BATCH stopped' in text and text.endswith(b'SRAM> ') and b'Running:' not in text,text[-1000:]
    cmd(cpu,m,b'Q\r');passed('SRAM operation error 40 stops before Q and VERSION, leaving SRAM prompt')
    text=cmd(cpu,m,b'BATCH R EDU;?;Q;TIME\r');assert b'EDU 1.4' in text and b'BATCH done' in text and text.endswith(b'B3> '),text[-1000:]
    passed('native prompt handoff, Q return, then monitor TIME')
    # Put ESC into the console only after the first queued command has been
    # dispatched, rather than canceling entry of the BATCH line itself.
    m.rx.extend(b'BATCH TIME;VERSION\r');start=len(m.tx);injected=False
    for _ in range(100000000):
        if m.ram[0x7EE4] and m.ram[0x7EE5]>0 and not injected:
            m.rx.append(0x1B);injected=True
        if k.model.waiting(cpu):break
        if cpu.pc==0x66A6:fast_transfer(cpu,m);continue
        cpu.step()
    else:raise AssertionError('ESC test timeout')
    text=bytes(m.tx[start:]);assert injected and b'BATCH canceled' in text and b'Running:' not in text,text[-1000:]
    passed('ESC cancels undispatched commands without running VERSION')
    # Regression for the user-reported NAME exit from flash. No confirmation
    # is synthesized by BATCH; NAME must wait for real input.
    text=cmd(cpu,m,b'R MAINT\rNAME 2512\r');assert text.endswith(b'Type YES: ') and m.bank==2,text[-1000:]
    before=[bytes(b) for b in m.banks];assert not m.events
    text=cmd(cpu,m,b'NO\r');assert text.endswith(b'BM> ') and [bytes(b) for b in m.banks]==before,text[-500:]
    text=cmd(cpu,m,b'NAME 2512\rYES\r');assert b'Board: 2512' in text and text.endswith(b'BM> '),text[-1000:]
    assert m.events and all(e[0]=='program' and e[1]==3 and 0x9C00<=e[2]<0xA000 for e in m.events),m.events[:20]
    assert m.events[-1][2]%32==31 and m.events[-1][3]==0
    cmd(cpu,m,b'Q\r');assert b'Board: 2512' in cmd(cpu,m,b'VERSION\r')
    passed('NAME 2512 waits for YES, refuses NO without writes, appends/commits/reads back from XIP and survives return')
    # CLOCK 1.9 can run interactively from the new saved flash record.
    text=cmd(cpu,m,b'R CLOCK\rSTATUS\rBATTERY\rQ\r');assert b'CLOCK 1.9' in text and b'Running: yes' in text and text.endswith(b'B3> '),text[-1000:]
    passed('CLOCK 1.9 normal STATUS/BATTERY/Q with batch-aware line hook')
    for name,prompt in [('MAINT',b'BM> '),('WORK',b'WORK> '),('EDU',b'EDU> ')]:
        text=cmd(cpu,m,('BATCH R '+name+';BOGUS;Q;TIME\r').encode())
        assert b'BATCH stopped: command failed' in text and text.endswith(prompt),(name,text[-1000:])
        assert not m.ram[0x7EE4]
        cmd(cpu,m,b'Q\r')
    passed('MAINT, WORK and EDU parser errors each stop before queued Q/TIME')
    for fault in ['crc','old']:
        cpu,m=fixture(corrupt=fault);assert b'2.0b29' in m.tx and not m.ram[0x7EF4],(fault,bytes(m.tx[-500:]))
        text=cmd(cpu,m,b'B3\r');assert text.endswith(b'B3> '),(fault,text[-500:])
        text=cmd(cpu,m,b'BATCH TIME;VERSION\r');assert text.endswith(b'B3> ') and b'BATCH done' not in text,(fault,text[-500:])
    passed('damaged or older B2 provider disables batching; basic monitor still operates')
    report=dict(passed=True,checks=checks,build_sha256=sha((OUT/'build.json').read_bytes()),artifacts=META['artifacts'],utility_sha256=X['sha256'],board_access=False,boards_flashed=False)
    (OUT/'beta29-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
