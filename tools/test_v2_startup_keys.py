"""Execute early-input boot and slot rejection paths with linked instructions."""
import json
from test_v2_status import fresh,layout,OUT
from test_v2_spi_resident import k

META=json.loads((OUT/'build.json').read_text());B=META['boot'];checks=[]

def run(cpu,stop):
    k.model.run(cpu,stop,30000000)

def case(key=None,bad=None,usb=True):
    cpu,m=fresh(primary=layout());m.usb=usb
    if bad:
        page,kind=bad;offset=(page-0x80)*256
        if kind=='commit':m.banks[3][offset+31]=255
        elif kind=='cookie':m.banks[3][offset+20]^=1
        else:m.banks[3][offset+128]^=1
    before=[bytes(b) for b in m.banks]
    if key is not None:
        run(cpu,lambda:cpu.pc==B['BOOT_STARTUP_DOTS']);m.rx.extend(key)
    run(cpu,lambda:(cpu.pc==B['BOOT_RECOVERY_WINDOW'] and not m.rx) or k.model.waiting(cpu))
    assert [bytes(b) for b in m.banks]==before and not m.events
    return cpu,m

def main():
    for key,page in ((b'A',0xA0),(b'a',0xA0),(b'B',0xB0),(b'b',0xB0)):
        cpu,m=case(key);assert k.model.waiting(cpu) and m.ram[0x7D30]==page
        assert bytes(m.tx).split(b'\r\n')[0].count(b'.')==0 and b'Enter default' not in m.tx
        checks.append('early '+key.decode()+' validates and launches');print('PASS',checks[-1],flush=True)
    for key in (b'\x1b',b'x',b' ',b'\r',b'S',b'\x03'):
        cpu,m=case(key);assert cpu.pc==B['BOOT_RECOVERY_WINDOW'] and bytes(m.tx).split(b'\r\n')[0].count(b'.')==0
        assert b'A/B/S,Enter default [3s]: ' in m.tx
        m.rx.extend(b'S');run(cpu,lambda:k.model.waiting(cpu));assert b'FIXED F RECOVERY' in m.tx
    checks.append('ESC/other bytes skip only dots; menu S still reaches independent recovery');print('PASS',checks[-1],flush=True)
    for page,key in ((0xA0,b'A'),(0xB0,b'B')):
        for kind in ('commit','cookie','crc'):
            cpu,m=case(key,(page,kind));assert cpu.pc==B['BOOT_RECOVERY_WINDOW'] and b' INVALID' in m.tx
            m.rx.extend(b'\r');run(cpu,lambda:k.model.waiting(cpu));assert m.ram[0x7D30]!=(page)
    checks.append('uncommitted/incompatible/CRC-corrupt A and B never launch; valid fallback retained');print('PASS',checks[-1],flush=True)
    cpu,m=case();assert bytes(m.tx).split(b'\r\n')[0].count(b'.')==160 and cpu.pc==B['BOOT_RECOVERY_WINDOW']
    run(cpu,lambda:k.model.waiting(cpu));assert m.ram[0x7D30]==0xA0
    checks.append('no-key 160 dots and timed default boot unchanged');print('PASS',checks[-1],flush=True)
    cpu,m=case(usb=False);run(cpu,lambda:k.model.waiting(cpu));assert m.ram[0x7D30]==0xA0
    checks.append('disconnected USB boot remains bounded');print('PASS',checks[-1],flush=True)
    from test_v2_storage import cmd
    for key,page in ((b'A',0xA0),(b'B',0xB0)):
        cpu,m=case(key)
        offset=(page-0x80)*256
        assert int.from_bytes(m.banks[3][offset+70:offset+72],'little')==META['monitors'][f'{page:02x}']['V2_M_EDIT']
        cmd(cpu,m,b'M 3E20 01 03 00\r')
        assert bytes(m.ram[0x3E20:0x3E23])==b'\x01\x03\0'
    checks.append('A/B private RAM-edit service and actual M writes/readback retained');print('PASS',checks[-1],flush=True)
    (OUT/'startup-keys-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,
        artifacts=META['artifacts'],boot_compatibility=META['boot_compatibility']),indent=2)+'\n')

if __name__=='__main__':main()
