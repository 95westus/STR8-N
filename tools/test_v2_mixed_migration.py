"""Exact backup-bound beta23 A / beta25 B qualification, without board I/O."""
import json,hashlib
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_storage import cmd
from test_v2_spi_resident import k
from beta4_migration import metadata,config_sum

ROOT=OUT.parents[1];BASE=ROOT/'output/qualification/beta25-unified-2026-10-14/2205'
META=json.loads((OUT/'build.json').read_text());PLAN=json.loads((BASE/'upgrade/plan.json').read_text())
EXPECTED=[(BASE/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
FALLBACK=(BASE/'prior-verified/b3.bin').read_bytes()[0x2000:0x3000]

def start(key=None,fault=None):
    c,m=fresh(primary=layout());m.banks=[bytearray(b) for b in EXPECTED];m.spi.banks=m.banks;m.bus.ee[0xF2:0xF8]=m.banks[3][0x1C08:0x1C0E];m.bus.rtc_regs[7:9]=bytes((0x80,17))
    if fault:
        page,kind=fault;offset=(page-0x80)*256
        if kind=='commit':m.banks[3][offset+31]=0xFF
        elif kind=='cookie':m.banks[3][offset+20]^=1
        else:m.banks[3][offset+400]^=1
    k.model.run(c,lambda:c.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
    if key is not None:m.rx.extend(key)
    boot(c);return c,m

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    assert EXPECTED[3][0x2000:0x3000]==FALLBACK and hashlib.sha256(FALLBACK).hexdigest()==PLAN['fallback_sha256']
    assert EXPECTED[0]==(BASE/'prior-verified/b0.bin').read_bytes() and EXPECTED[1][0x3000:]==(BASE/'prior-verified/b1.bin').read_bytes()[0x3000:]
    for key,page,version in ((b'A',0xA0,b'2.0b23'),(b'a',0xA0,b'2.0b23'),(b'B',0xB0,b'2.0b25'),(b'b',0xB0,b'2.0b25'),(None,0xB0,b'2.0b25')):
        c,m=start(key);assert m.ram[0x7D30]==page and b'STR8-N '+version in m.tx,bytes(m.tx[-300:])
        before=snapshot(m);assert b'\xff' not in cmd(c,m,b'APPS\r')
        text=cmd(c,m,b'TIME\r');lines=[l for l in text.split(b'\r\n') if l and l not in (b'TIME',b'B3> ')]
        assert len(lines)==1 and b'(-05:00)' in lines[0] and b'UTC ' not in text,text
        assert b'CLOCK' in cmd(c,m,b'T 1\r') and b'SRAM' in cmd(c,m,b'T 2\r')
        old=bytes(m.ram[0x3E20:0x3E23]);cmd(c,m,b'M 3E20 01 03 00\r');assert m.ram[0x3E20:0x3E23]==b'\1\3\0';m.ram[0x3E20:0x3E23]=old
        clock=cmd(c,m,b'R CLOCK\r');assert b'CLOCK>' in clock and b'UTC ' in clock
        cmd(c,m,b'STATUS\r');cmd(c,m,b'Q\r')
        maint=cmd(c,m,b'R MAINT\r');assert b'BM>' in maint
        assert b'NAME' in cmd(c,m,b'NAME\r');cmd(c,m,b'Q\r')
        assert m.ram[0x7D30]==page and snapshot(m)==before and not m.events
        print('PASS exact mixed command case',key,version.decode(),flush=True)
    passed('exact mixed image: A/a beta23 and B/b/default beta25; APPS/TIME/T/CLOCK/MAINT, RAM edit and HOLD work with complete preservation')
    for kind in ('commit','cookie','crc'):
        c,m=start(b'\r',(0xB0,kind));assert m.ram[0x7D30]==0xA0 and b'STR8-N 2.0b23' in m.tx
        assert m.banks[3][0x2000:0x3000]==FALLBACK and not m.events
    c,m=start(b'\r',(0xA0,'crc'));assert m.ram[0x7D30]==0xB0 and b'STR8-N 2.0b25' in m.tx
    passed('uncommitted, incompatible and CRC-corrupt beta25 automatically fall back to untouched beta23; bad A retains beta25 B')
    c,m=start(b'A');cmd(c,m,b'P A\r')
    from beta4_migration import journal
    r=journal(m.banks[3]);assert r[15:21]==b'P\xA0'+(32).to_bytes(4,'little')
    cmd(c,m,b'P B\r');r=journal(m.banks[3]);assert r[15:21]==b'P\xB0'+(37).to_bytes(4,'little')
    assert m.banks[3][0x2000:0x3000]==FALLBACK
    passed('old beta23 P command validates/promotes either generation through the new fixed-F ABI without touching either slot')
    c,m=start(b'B');cmd(c,m,b'P A\r');r=journal(m.banks[3]);assert r[15:21]==b'P\xA0'+(32).to_bytes(4,'little')
    cmd(c,m,b'P B\r');r=journal(m.banks[3]);assert r[15:21]==b'P\xB0'+(37).to_bytes(4,'little')
    assert m.banks[3][0x2000:0x3000]==FALLBACK
    passed('new beta25 P command calls the beta23-family validator and promotes either slot')
    (OUT/'mixed-slot-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],
        expected_hashes=PLAN['expected_hashes'],fallback_sha256=PLAN['fallback_sha256'],board_access=False,boards_flashed=False),indent=2)+'\n')

if __name__=='__main__':main()
