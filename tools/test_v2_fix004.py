"""Instruction-level APPS reproduction, malformed rows, and real app validation."""
import hashlib,json
from pathlib import Path
from beta4_migration import crc
from build_v2_beta4_launcher import descriptor
from test_v2_status import fresh,boot,layout,snapshot,OUT
from test_v2_storage import cmd

META=json.loads((OUT/'build.json').read_text())
PARENT=OUT.parent/'v2-time-local'
EMPTY=b'APPS\r\n\r\nB3> '

def seal(m):
    b=m.banks[3];b[0x67FE:0x6800]=crc(b[0x6000:0x67FE]).to_bytes(2,'big')
    b[0x6FFE:0x7000]=crc(b[0x6000:0x6FFE]).to_bytes(2,'big')

def table(m,rows=(),magic=b'AT\x01\x08'):
    m.banks[3][0x66F0:0x66F4]=magic
    m.banks[3][0x66F4:0x67F4]=b''.join(rows).ljust(256,b'\0');seal(m)

def image(start):
    payload=b'\x4c\x67\x7e' # actual native app tail-returns through RAM HOLD
    h=b'AP\x01\x01'+(16+len(payload)).to_bytes(2,'little')+(start+16).to_bytes(2,'little')+bytes(4)+b'\xff\xff'
    return h+crc(h).to_bytes(2,'little')+payload

def app(m,name='DEMO',bank=0,start=0x9000):
    body=image(start);m.banks[bank][start-0x8000:start-0x8000+len(body)]=body
    if bank!=3:m.banks[bank][-32:]=m.banks[3][-32:]
    return descriptor(name,bank=bank,start=start,image=body,entry=start+16)

def query(cpu,m,command=b'APPS\r'):
    before=snapshot(m);user=bytes(m.ram[0x200:0x6500]);bank=m.bank;sp=cpu.sp;events=list(m.events)
    out=cmd(cpu,m,command)
    assert snapshot(m)==before and bytes(m.ram[0x200:0x6500])==user
    assert m.bank==bank and cpu.sp==sp and m.events==events
    assert out.endswith(b'B3> '),out
    assert all(x<128 for x in out),repr(out)
    return out

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    assert META['apps_listing_fixed'] and META['time_local_only']
    cpu,m=fresh(primary=layout());boot(cpu)
    # Run the exact parent extension in the same model to retain the failure.
    good=bytes(m.banks[3][0x6000:0x7000])
    m.banks[3][0x6000:0x7000]=(PARENT/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    before=snapshot(m);bad=cmd(cpu,m,b'APPS\r')
    assert bad.count(b'\xff'*12+b' not installed')==8 and snapshot(m)==before,bad
    (OUT/'apps-parent-reproduction.txt').write_bytes(bad)
    m.banks[3][0x6000:0x7000]=good
    assert query(cpu,m)==EMPTY
    passed('exact parent reproduces eight erased names; fixed empty table lists no native apps, with complete preservation')
    for fill in (bytes(32),b'\xff'*32):
        table(m,[fill]*8);assert query(cpu,m)==EMPTY
    row=app(m)
    malformed=[]
    for name in (b'\xff'*12,b'A\x1b'+bytes(10),b'ABCDEFGHIJKL',b'GOOD\0BAD'+bytes(4),b'a'+bytes(11),b'\0HIDDEN'+bytes(5)):
        r=bytearray(row);r[:12]=name;malformed.append(bytes(r))
    for r in malformed:
        table(m,[r]);assert query(cpu,m)==EMPTY
    for magic in (b'\xff'*4,b'AT\x02\x08',b'AT\x01\x09',b'XX\x01\x08'):
        table(m,[row],magic);assert query(cpu,m)==EMPTY
    passed('zero/erased rows, control bytes, non-ASCII, lowercase, overlong names, bad padding and table magic/version/count never print garbage')
    for bank,start in ((0,0x9000),(1,0xD000),(2,0x9000)):
        row=app(m,bank=bank,start=start);table(m,[row])
        expected=f'DEMO installed B{bank}:{start:04X} LEN 0013'.encode()
        text=query(cpu,m);assert expected in text,text
        (OUT/f'apps-bank-{bank}-preview.txt').write_bytes(text)
    # B3's former app sector is now reserved for the resident journal.
    row=descriptor('DEMO',bank=3,start=0x9800,image=image(0x9800),entry=0x9810)
    table(m,[row]);assert b'DEMO not installed' in query(cpu,m)
    passed('validated B0/B1/B2 apps print exact metadata; B3 journal reservation remains refused')
    row=app(m);table(m,[row]);assert b'DEMO installed' in query(cpu,m)
    for fault in ('descriptor-crc','commit','header','image','vectors','abi','range','workspace'):
        r=bytearray(row);m.banks[0][0x1000:0x1013]=image(0x9000);m.banks[0][-32:]=m.banks[3][-32:]
        if fault=='descriptor-crc':r[28]^=1
        elif fault=='commit':r[30]=0xFF
        elif fault=='header':m.banks[0][0x1000]^=1
        elif fault=='image':m.banks[0][0x1012]^=1
        elif fault=='vectors':m.banks[0][-2]^=1
        else:
            if fault=='abi':r[13]=2
            elif fault=='range':r[15]=0x70
            else:r[20:24]=bytes.fromhex('00 65 FF 65')
            r[28:30]=crc(r[:28]+r[30:]).to_bytes(2,'little')
        table(m,[bytes(r)]);text=query(cpu,m)
        assert b'DEMO not installed' in text and b' installed B' not in text,(fault,text)
    passed('commit, descriptor CRC, ABI, range, EDU workspace, app header/image and exception-vector faults never claim installed')
    rows=[app(m,name=name,start=0x9000+i*0x100) for i,name in enumerate(('A','BC','DEF','GHIJ','KLMNO','PQRSTU','VWXYZAB','ABCDEFGHIJK'))]
    table(m,rows);text=query(cpu,m);assert text.count(b' installed B0:')==8,text
    assert b'ABCDEFGHIJK installed B0:9700 LEN 0013' in text
    table(m,[rows[0],b'\xff'*32,rows[-1]])
    assert query(cpu,m).count(b' installed B0:')==2
    table(m,[descriptor('OPTION')]);assert b'OPTION not installed' in query(cpu,m)
    assert b'App takes no arguments' in query(cpu,m,b'APPS X\r')
    table(m,[row]);query(cpu,m,b'DEMO\r')
    passed('eight slots, first/last rows, 1/11-character names, sparse erased rows, arguments and actual native launch retain monitor and state')
    for off in (False,True):
        from test_v2_spi_resident import k
        cpu,m=fresh(off=off,primary=layout())
        k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000)
        m.rx.extend(b'B' if off else b'A');boot(cpu)
        assert m.ram[0x7D30]==(0xB0 if off else 0xA0)
        before=snapshot(m)
        assert query(cpu,m)==EMPTY
        assert b'MAINT' in query(cpu,m,b'T 1\r') and b'SRAM' in query(cpu,m,b'T 2\r')
        assert snapshot(m)==before
    passed('monitor A/EDU ON and monitor B/EDU OFF APPS stay read-only; separate T 1/T 2 saved-program inventory remains available')
    prior=json.loads((PARENT/'build.json').read_text())
    for name,digest in META['artifacts'].items():
        assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
        if not META.get('f_only_bootstrap') and name!='str8n-v2-recovery-e000-efff.bin':assert digest==prior['artifacts'][name],name
    (OUT/'apps-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=META['artifacts'],
        local_asset_sha256=META['local_asset_sha256'],status_asset_sha256=META['status_asset_sha256'],
        board_access=False,boards_flashed=False),indent=2)+'\n')

if __name__=='__main__':main()
