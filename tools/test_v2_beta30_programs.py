"""Batch program handoff, retained fallback and staging tests, offline only."""
import json
from test_v2_beta30 import fixture,cmd,OUT,META,X,sha
from test_v2_workspace import req
from test_v2_beta28_candidate import api

def main():
    checks=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    cpu,m=fixture()
    text=cmd(cpu,m,b'SRAM\rF\rFORMAT SRAM\r');assert b'SRAM: 00' in text,text[-500:]
    body=(OUT/'clock/clock.bin').read_bytes();m.ram[0x2000:0x2000+len(body)]=body
    text=cmd(cpu,m,f'S CLK 2000 {0x2000+len(body)-1:04X} 2000\rQ\r'.encode());assert b'SRAM: 00' in text and text.endswith(b'B3> '),text[-1000:]
    array=bytes(m.spi.devices[0].data)
    text=cmd(cpu,m,b'BATCH SRAM;G CLK;STATUS;Q\r');(OUT/'batch-clock-example.txt').write_bytes(text)
    assert b'CLOCK 1.9' in text and b'Running: yes' in text and b'BATCH done' in text and text.endswith(b'B3> '),text[-1500:]
    assert bytes(m.spi.devices[0].data)==array
    passed('R SRAM;G CLK;STATUS;Q crosses all three interpreters and returns to monitor without storage writes')
    text=cmd(cpu,m,b'BATCH SRAM;G CLK;BOGUS;Q\r');assert b'BATCH stopped: command failed' in text and text.endswith(b'CLOCK> '),text[-1000:]
    cmd(cpu,m,b'Q\r');passed('CLOCK parse error stops before queued Q and stays at CLOCK prompt')
    text=cmd(cpu,m,b'R SRAM\r');m.ram[0x2000:0x2003]=b'\x4c\x67\x7e'
    text=cmd(cpu,m,b'S RAW 2000 2002 2000\rQ\r');assert b'SRAM: 00' in text,text
    array=bytes(m.spi.devices[0].data)
    text=cmd(cpu,m,b'BATCH SRAM;G RAW;Q;VERSION\r')
    assert b'SRAM: 4A' in text and b'BATCH stopped' in text and text.endswith(b'SRAM> ') and b'Running:' not in text,text[-1000:]
    assert bytes(m.spi.devices[0].data)==array
    cmd(cpu,m,b'Q\r');passed('unregistered RAM program is refused before execution; pending commands discarded')
    # Full sector staging overlaps most utility scratch, but not batch RAM.
    pattern=bytes((i*13)&255 for i in range(4096));m.banks[0][:4096]=pattern
    text=cmd(cpu,m,b'BATCH MAINT;C 0 8 1 8;Q\r');assert text.endswith(b'WRITE? TYPE Y> '),text[-800:]
    assert bytes(m.banks[1][:4096])==b'\xff'*4096
    text=cmd(cpu,m,b'Y\r');assert b'VERIFIED' in text and b'BATCH done' in text and text.endswith(b'B3> '),text[-1000:]
    assert bytes(m.banks[1][:4096])==pattern
    passed('manual flash-write confirmation; complete 4KiB staging preserves queue and resumes Q')
    before=[bytes(b) for b in m.banks]
    text=cmd(cpu,m,b'BATCH MAINT;NAME TEST;YES;Q\r');assert text.endswith(b'Type YES: '),text[-700:]
    assert [bytes(b) for b in m.banks]==before
    text=cmd(cpu,m,b'\x1b');assert b'BATCH canceled' in text and text.endswith(b'BM> '),text[-700:]
    assert [bytes(b) for b in m.banks]==before
    cmd(cpu,m,b'Q\r');passed('queued YES is never used as confirmation; ESC cancels pending NAME and remaining commands')
    # WORK's bootstrap must reinstall its gateway without overwriting BATCH.
    text=cmd(cpu,m,b'BATCH WORK;?;Q;TIME\r');assert b'WORK 1.4' in text and b'BATCH done' in text,text[-1000:]
    passed('WORK launch and stub installation preserve pending batch commands')
    cpu,m=fixture(b'A');assert b'2.0b28' in m.tx and m.ram[0x7D30]==0xA0
    for name,title in [('MAINT',b'BANK MAINT 2.4'),('SRAM',b'SRAM 1.4'),('WORK',b'WORK 1.4'),('EDU',b'EDU 1.4')]:
        text=cmd(cpu,m,('R '+name+'\rQ\r').encode());assert title in text and text.endswith(b'B3> '),(name,text[-500:])
    text=cmd(cpu,m,b'R CLOCK\rSTATUS\rQ\r');assert b'CLOCK 1.9' in text and b'Running: yes' in text and text.endswith(b'B3> '),text[-800:]
    passed('retained beta28 A launches all new native utilities and CLOCK interactively with batching disabled')
    flags=m.ram[0x7D07];m.ram[0x7D07]=0
    text=cmd(cpu,m,b'R SRAM\r');assert text.endswith(b'B3> ') and b'SRAM 1.4' not in text,text[-700:]
    m.ram[0x7D07]=flags
    passed('retained fallback refuses unavailable SRAM safely without calling an uninitialized batch gateway')
    assert (OUT/'str8n-v2-recovery-f000-ffff.bin').read_bytes()==(OUT.parent/'v2-beta28-b23/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    report=dict(passed=True,checks=checks,build_sha256=sha((OUT/'build.json').read_bytes()),artifacts=META['artifacts'],utility_sha256=X['sha256'],board_access=False,boards_flashed=False)
    (OUT/'beta30-program-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
