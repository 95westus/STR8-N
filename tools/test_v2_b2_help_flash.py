"""Execute permanent H installation, registration, boot and RAM preservation."""
import hashlib
import json
import build_v2_b2_help_flash as module
import test_v2_b2 as host
from v2_b2_config import decode_locator

boot, MGR = host.boot, host.MGR
META = json.loads((module.OUT/'manifest.json').read_text())
S19 = module.OUT/(module.NAME+'.s19')
SECTOR = (module.OUT/(module.NAME+'.bin')).read_bytes()
STUB = bytes.fromhex(META['trampoline_hex'])


def fresh():
    cpu, mem = host.ready()
    mem.banks[3][0x4000:0x5000] = SECTOR
    return cpu, mem


def init(cpu):
    return host.send(cpu, b'G C000\r')


def register(cpu, key, address):
    ok, low, high, _ = host.lookup(cpu,'COMMAND.REGISTER')
    assert ok
    result = host.call(cpu,low+256*high,ord(key),address & 255,address >> 8)
    cpu.pc = boot.SYM['V2_PROMPT']
    boot.hold(cpu)
    return result


def reset(cpu, limit=12_000_000):
    cpu.pc = boot.SYM['START']
    # Execute the real configured hold window, not a synthetic jump to H.
    boot.run(cpu,lambda:boot.waiting(cpu),limit=limit)


def check_flash_install_and_memory_preservation():
    cpu, mem = host.ready()
    app = bytes(mem.ram[0x0200:0x5800])
    overlay = bytes(mem.ram[0x5800:0x6100])
    banks = [bytes(bank) for bank in mem.banks]
    output = host.send(cpu,b'I C000 CFFF\rY\r'+S19.read_bytes().replace(b'\n',b'\r\n'))
    assert b'Done' in output, output[-400:]
    assert bytes(mem.banks[3][0x4000:0x5000]) == SECTOR
    assert all(e[1]==3 and 0xC000<=e[2]<=0xCFFF for e in mem.events)
    assert all(bytes(mem.banks[b])==banks[b] for b in (0,1,2))
    assert mem.banks[3][:0x4000]==banks[3][:0x4000]
    assert mem.banks[3][0x5000:]==banks[3][0x5000:]
    assert bytes(mem.ram[0x0200:0x5800])==app
    assert bytes(mem.ram[0x5800:0x6100])==overlay
    assert b'conflict' not in init(cpu)
    assert mem.ram[0x7400:0x7403]==STUB
    assert mem.ram[MGR['MG_COUNT']]==15
    assert b'Registered: K S R T H ' in host.send(cpu,b'H\r')
    assert bytes(mem.ram[0x0200:0x5800])==app
    assert bytes(mem.ram[0x5800:0x6100])==overlay
    mem.events.clear()
    assert b'conflict' not in init(cpu)  # Idempotent registration.
    assert mem.ram[MGR['MG_COUNT']]==15 and not mem.events
    assert mem.ram[0x7403]==0x5A


def check_boot_persistence_hold_and_all_banks():
    cpu, mem = fresh()
    app = bytes(mem.ram[0x0200:0x5800])
    overlay = bytes(mem.ram[0x5800:0x6100])
    ef = bytes(mem.banks[3][0x6000:])
    out = host.send(cpu,b'C 1 3 C000 0A\rY\r')
    assert b'Done' in out
    assert decode_locator(mem.banks[3][0x7FD0:0x7FE0])==(3,13)
    assert mem.banks[3][0x6000:0x7FD0]==ef[:0x1FD0]
    assert mem.banks[3][0x7FE0:]==ef[0x1FE0:]
    before = [bytes(bank) for bank in mem.banks]
    mem.events.clear()
    for _ in range(2):
        reset(cpu)
        assert mem.ram[MGR['MG_COUNT']]==15
        assert mem.ram[0x7400:0x7403]==STUB
        assert b'Registered: K S R T H ' in host.send(cpu,b'H\r')
        assert bytes(mem.ram[0x0200:0x5800])==app
        assert bytes(mem.ram[0x5800:0x6100])==overlay
    for bank in range(4):
        host.send(cpu,f'B{bank}\r'.encode())
        assert b'Registered: K S R T H ' in host.send(cpu,b'H\r')
        assert mem.bank==3 and mem.ram[boot.SYM['V2_SELECTED']]==bank
    assert [bytes(bank) for bank in mem.banks]==before and not mem.events
    # S during the hold window deliberately bypasses all automatic application entry.
    host.send(cpu,b'B3\r')
    cpu.pc=boot.SYM['START']
    boot.run(cpu,lambda:cpu.pc==boot.SYM['V2_AUTO_TICK'],limit=5_000_000)
    mem.rx.extend(b'S')
    boot.hold(cpu)
    assert mem.ram[MGR['MG_COUNT']]==12
    assert b'conflict' not in init(cpu)
    assert b'Registered: K S R T H ' in host.send(cpu,b'H\r')
    # Cold boot with randomized RAM also reconstructs the stub and registration.
    mem.ram[0x0200:0x7F00]=bytes([0xA7])*0x7D00
    reset(cpu)
    assert mem.ram[MGR['MG_COUNT']]==15 and mem.ram[0x7400:0x7403]==STUB
    assert mem.ram[0x0200:0x6100]==bytes([0xA7])*0x5F00
    assert b'Registered: K S R T H ' in host.send(cpu,b'H\r')


def check_conflicts_and_missing_manager():
    for address in (0x7400,0x7401,0x7402):
        cpu, mem = fresh()
        assert register(cpu,'X',address)[:2]==(True,0)
        before=bytes(mem.ram[0x7400:0x7403])
        assert b'conflict' in init(cpu)
        assert bytes(mem.ram[0x7400:0x7403])==before
        assert mem.ram[MGR['MG_COUNT']]==15
    cpu,mem=fresh()
    assert register(cpu,'H',0x5800)[:2]==(True,0)
    before=bytes(mem.ram[0x7400:0x7403])
    assert b'conflict' in init(cpu)
    assert bytes(mem.ram[0x7400:0x7403])==before
    cpu,mem=fresh()
    for key in 'ABXY':
        assert register(cpu,key,0x7403)[:2]==(True,0)
    assert b'registry full' in init(cpu)
    assert mem.ram[MGR['MG_COUNT']]==24
    cpu,mem=fresh()
    mem.ram[MGR['MG_COUNT']]=0xFF
    assert b'conflict' in init(cpu)
    cpu,mem=fresh()
    mem.banks[3][0x6000:0x7000]=b'\xff'*4096
    before=bytes(mem.ram[0x7400:0x7403])
    assert b'H requires' in init(cpu)
    assert bytes(mem.ram[0x7400:0x7403])==before


def check_overlay_and_rts_coexistence():
    cpu,mem=fresh()
    assert b'conflict' not in init(cpu)
    mem.ram[0x5800:0x5803]=b'\xa9\x01\x60'
    assert register(cpu,'X',0x5800)[:2]==(True,0)
    assert b'Bad cmd' not in host.send(cpu,b'X\r')
    assert b'Registered: K S R T H X ' in host.send(cpu,b'H\r')
    assert b'conflict' not in init(cpu)
    payload=bytes(range(32))
    mem.ram[0x2000:0x2020]=payload
    assert b'Done' in host.send(cpu,b'S 2000 201F PERMH\r')
    assert b'PERMH' in host.send(cpu,b'T\r')
    mem.ram[0x2000:0x2020]=bytes(32)
    assert b'Done' in host.send(cpu,b'R PERMH\r')
    assert mem.ram[0x2000:0x2020]==payload
    assert mem.banks[3][0x4000:0x5000]==SECTOR
    # K refuses using the occupied provider sector as configuration.
    assert b'Config sector occupied' in host.send(cpu,b'K B3 C 00 3F 00 00\r'), 'opaque provider must be retained'
    # Even an accidentally enabled C mask cannot allocate the provider's gaps.
    host.install_policy(mem,(0,0,0,0x10))
    before=[bytes(bank) for bank in mem.banks]
    out=host.send(cpu,b'S 2000 2000 CSPACE B3\r')
    assert b'RTS error 07' in out, out
    assert [bytes(bank) for bank in mem.banks]==before
    assert b'Registered: K S R T H X ' in host.send(cpu,b'H\r')


def main():
    assert hashlib.sha256(SECTOR).hexdigest()==META['binary_sha256']
    assert hashlib.sha256(S19.read_bytes()).hexdigest()==META['s19_sha256']
    checks=[check_flash_install_and_memory_preservation,
            check_boot_persistence_hold_and_all_banks,
            check_conflicts_and_missing_manager,
            check_overlay_and_rts_coexistence]
    for check in checks:
        check()
        print('PASS:',check.__name__,flush=True)
    (module.OUT/'help-flash-tests.json').write_text(json.dumps(dict(
        passed=[check.__name__ for check in checks],
        module_sha256=hashlib.sha256(SECTOR).hexdigest(),
        s19_sha256=hashlib.sha256(S19.read_bytes()).hexdigest(),
        firmware_sha256=hashlib.sha256(boot.IMAGE).hexdigest(),
        physical_hardware_tested=False),indent=2)+'\n')


if __name__=='__main__':
    main()
