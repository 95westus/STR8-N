"""Qualify an exact migration image and its retained monitor, without hardware."""
import argparse,json,os,hashlib,binascii
from pathlib import Path

def main(root):
    plan=json.loads((root/'upgrade/plan.json').read_text());os.environ['STR8_RTC_BUILD']=plan['target_build']
    from test_v2_status import fresh,boot,layout,snapshot,OUT
    from test_v2_storage import cmd
    from test_v2_spi_resident import k
    from beta4_migration import journal
    meta=json.loads((OUT/'build.json').read_text());expected=[(root/f'upgrade/expected-b{i}.bin').read_bytes() for i in range(4)]
    a=plan['source']['active_page'];b=plan['source']['inactive_page'];offset=(a-0x80)*256
    fallback=(root/'prior-verified/b3.bin').read_bytes()[offset:offset+4096]
    assert expected[3][offset:offset+4096]==fallback and hashlib.sha256(fallback).hexdigest()==plan['fallback_sha256']
    off=journal(expected[3])[21]==0xA5;checks=[]
    zones=[expected[3][i:i+32] for i in range(0x1C20,0x2000,32)]
    zones=[r for r in zones if r[:4]==b'TZ\1\0' and r[31]==0 and binascii.crc_hqx(r[:28],65535)==int.from_bytes(r[28:30],'little')]
    minutes=int.from_bytes(max(zones,key=lambda r:int.from_bytes(r[4:8],'little'))[8:10],'little',signed=True) if zones else 0
    wanted=('(' + ('-' if minutes<0 else '+')+f'{abs(minutes)//60:02d}:{abs(minutes)%60:02d}'+')').encode()
    device=root/'retained/devices-before/report.json';settings=json.loads(device.read_text()) if device.exists() else {}
    def start(key=None,fault=None):
        c,m=fresh(off=off,primary=layout());m.banks=[bytearray(x) for x in expected];m.spi.banks=m.banks
        binding=m.banks[3][0x1C00:0x1C20]
        if binding[:2]==b'EI':m.bus.ee[0xF2:0xF8]=binding[8:14]
        m.bus.rtc_regs[7:9]=bytes((settings.get('control_register',0x80),settings.get('trim_register',14)))
        if fault:
            page,kind=fault;i=(page-0x80)*256
            if kind=='commit':m.banks[3][i+31]=0xFF
            elif kind=='cookie':m.banks[3][i+20]^=1
            else:m.banks[3][i+400]^=1
        k.model.run(c,lambda:c.pc==meta['boot']['BOOT_STARTUP_DOTS'],30000000)
        if key is not None:m.rx.extend(key)
        boot(c);return c,m
    for page,version in ((a,plan['source']['version']),(b,meta['version'])):
        c,m=start(chr(page//16-10+65).encode());assert m.ram[0x7D30]==page and ('STR8-N '+version).encode() in m.tx
        before=snapshot(m);assert b'\xff' not in cmd(c,m,b'APPS\r')
        text=cmd(c,m,b'TIME\r');lines=[x for x in text.split(b'\r\n') if x and x not in (b'TIME',b'B3> ')]
        if version=='2.0b4':
            assert text==b'TIME\r\nBad hex\r\nB3> ',text # b4 predates the TIME command
        else:assert len(lines)==1 and (b'unavailable' in text if off else wanted in text and b'UTC ' not in text),text
        prior=bytes(m.ram[0x3E20:0x3E23]);cmd(c,m,b'M 3E20 01 03 00\r');assert m.ram[0x3E20:0x3E23]==b'\1\3\0';m.ram[0x3E20:0x3E23]=prior
        assert b'CLOCK' in cmd(c,m,b'T 1\r') and b'SRAM' in cmd(c,m,b'T 2\r')
        if not off:
            text=cmd(c,m,b'R CLOCK\r');assert b'CLOCK>' in text,text
            if version=='2.0b4':assert b'Services unavailable' in text,text
            else:
                assert b'UTC ' in text and b', changed' not in text,text
                assert (b', unbound' in text)==(expected[3][0x1C00:0x1C02]!=b'EI'),text
                for line in (b'STATUS\r',b'TRIM\r',b'OFFSET\r',b'EUI\r',b'HISTORY\r'):cmd(c,m,line)
            cmd(c,m,b'Q\r')
        assert b'BM>' in cmd(c,m,b'R MAINT\r');assert b'Board:' in cmd(c,m,b'NAME\r');cmd(c,m,b'Q\r')
        assert snapshot(m)==before and not m.events and m.ram[0x7D30]==page
        checks.append(version+' monitor command/HOLD/read-only preservation');print('PASS',plan['board'],checks[-1],flush=True)
        for target,gen in ((a,plan['source_generation']),(b,meta['generation'])):
            cmd(c,m,('P '+chr(target//16-10+65)+'\r').encode());r=journal(m.banks[3]);assert r[15:21]==b'P'+bytes((target,))+gen.to_bytes(4,'little')
        assert m.banks[3][offset:offset+4096]==fallback
    for key,page in ((b'a',0xA0),(b'b',0xB0),(None,b)):
        c,m=start(key);assert m.ram[0x7D30]==page
    for kind in ('commit','cookie','crc'):
        c,m=start(b'\r',(b,kind));assert m.ram[0x7D30]==a and not m.events
    c,m=start(b'\r',(a,'crc'));assert m.ram[0x7D30]==b and not m.events
    checks.extend(('both old/new P commands validate and promote either generation without changing fallback','lowercase A/B and default; invalid commit/cookie/CRC fall back; bad fallback retains new monitor'))
    report=dict(passed=True,board=plan['board'],checks=checks,artifacts=meta['artifacts'],expected_hashes=plan['expected_hashes'],fallback_sha256=plan['fallback_sha256'],board_access=False)
    (root/'upgrade/mixed-slot-test-results.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',plan['board'],'exact mixed firmware qualification',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();main(a.root)
