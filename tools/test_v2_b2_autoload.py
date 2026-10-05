"""Execute persistent selective autoload, recovery and provider contracts."""
import hashlib
import json
import test_v2_b2 as host
import build_v2_b2_command_example as providers
from v2_b2_config import checksum, encode_header, boot_pocket

AL = host.REPORT['autoload']
HX = (providers.OUT/(providers.NAME+'.bin')).read_bytes()


def fresh():
    cpu, mem = host.flash.boot_flash(3)
    mem.banks[3][0x4000:0x5000] = HX
    return cpu, mem


def reset(cpu):
    start = len(cpu.memory.tx)
    cpu.pc = host.boot.SYM['START']
    host.boot.hold(cpu)
    return bytes(cpu.memory.tx[start:])


def keys(mem):
    return bytes(mem.ram[host.MGR['MG_TABLE']+i]
                 for i in range(0,mem.ram[host.MGR['MG_COUNT']],3))


def edit(cpu, text, confirm=True):
    out = host.send(cpu, ('K AUTO '+text+'\r'+('Y\r' if confirm else '')).encode())
    assert b'Done; reset to apply' in out, out
    return out


def block(mem, bank=3, sector=13):
    off = (sector-8)*4096+16
    return bytes(mem.banks[bank][off:off+64])


def test_selection_reset_and_messages():
    cpu, mem = fresh()
    app = bytes(mem.ram[0x0200:0x6100])
    all_banks = [bytes(b) for b in mem.banks]
    assert b'AUTO legacy' in host.send(cpu,b'K AUTO ?\r')
    edit(cpu,'+X')
    edit(cpu,'+H')
    edit(cpu,'-S')
    assert keys(mem) == b'KSRT'  # Configuration changes do not unload live providers.
    out = reset(cpu)
    assert keys(mem) == b'KRTXH', (keys(mem),out)
    assert out.startswith(b'.' * 160), out
    assert out.startswith(b'.' * 160 + b'\r\nK registered'), out
    assert out.index(b'K registered') < out.index(b'STR8-N'), out
    for key in b'KRTXH':
        assert bytes((key,))+b' registered\r\n' in out, out
    assert b'S registered' not in out
    assert b'HELLO FROM X' in host.send(cpu,b'X HELLO\r')
    assert b'Registered: K R T X H ' in host.send(cpu,b'H\r')
    assert b'Bad cmd' in host.send(cpu,b'S 2000 2000 NO\r')
    assert bytes(mem.ram[0x0200:0x6100]) == app
    assert all(bytes(mem.banks[b])==all_banks[b] for b in (0,1,2))
    assert mem.banks[3][:0x5000] == all_banks[3][:0x5000]
    assert mem.banks[3][0x6000:] == all_banks[3][0x6000:]
    assert b'X ON B3 C70A' in host.send(cpu,b'K AUTO\r')
    edit(cpu,'-X')
    out = reset(cpu)
    assert keys(mem) == b'KRTH' and b'X registered' not in out
    assert b'Bad cmd' in host.send(cpu,b'X\r')
    edit(cpu,'QUIET 1')
    assert b' registered' not in reset(cpu)
    assert keys(mem) == b'KRTH'


def test_future_provider_and_invalid_inputs():
    cpu, mem = fresh()
    # Standalone Y EX/1 provider. Resident code pins a distinct reserved-RAM stub.
    register = host.MGR['MG_REGISTER']
    body = (b'\xa9\x4c\x8d\x06\x74\xa9\x50\x8d\x07\x74'
            b'\xa9\xca\x8d\x08\x74\xa9Y\xa2\x06\xa0\x74\x20'
            +register.to_bytes(2,'little')+b'\x60')
    mem.banks[3][0x4A00:0x4A07] = b'\x4c\x07\xcaEX\x01Y'
    mem.banks[3][0x4A07:0x4A07+len(body)] = body
    mem.banks[3][0x4A50:0x4A53] = b'\xa9\x01\x60'
    edit(cpu,'+Y CA00')
    assert b'Y registered' in reset(cpu)
    assert keys(mem) == b'KRSTY'
    assert b'Bad cmd' not in host.send(cpu,b'Y\r')
    edit(cpu,'-Y')
    assert b'Y registered' not in reset(cpu)
    assert b'Bad cmd' in host.send(cpu,b'Y\r')
    for text in ('+B','+K','+?','+XY','+Z 2000','+Z E000', '+Z CA00',
                 'QUIET 2','QUIET 1 EXTRA','-Y CA00','+X C70A EXTRA','AUTOMATIC'):
        before = [bytes(b) for b in mem.banks]
        out = host.send(cpu,('K AUTO '+text+'\r').encode())
        assert b'Bad AUTO' in out, (text,out)
        assert [bytes(b) for b in mem.banks] == before
    edit(cpu,'+Y')  # Remember the explicitly supplied initialization address.
    assert b'Y registered' in reset(cpu)
    # Damaged/incompatible provider never publishes its command.
    mem.banks[3][0x4A05] = 2
    out = reset(cpu)
    assert b'Y registration failed' in out and keys(mem) == b'KRST'
    assert b'Bad cmd' in host.send(cpu,b'Y\r')
    # A provider that registers then returns failure must not expose its entry.
    mem.banks[3][0x4A05] = 1
    mem.banks[3][0x4A07+len(body)-1:0x4A07+len(body)+1] = b'\x18\x60'
    out = reset(cpu)
    assert b'Y registration failed' in out and keys(mem) == b'KRST'


def test_integrity_cancel_fault_and_relocation():
    cpu, mem = fresh()
    edit(cpu,'+X')
    before = [bytes(b) for b in mem.banks]
    out = host.send(cpu,b'K AUTO -X\rN\r')
    assert b'Canceled' in out and [bytes(b) for b in mem.banks] == before
    saved = block(mem)
    # Ordinary mask changes and explicitly relocating the sector retain AL/1.
    assert b'Done' in host.send(cpu,b'K B3 D 00 01 00 00\rY\r')
    assert block(mem) == saved
    assert b'Done' in host.send(cpu,b'K B2 A 00 00 3F 00\rY\r')
    assert block(mem,2,10) == saved
    assert b'X registered' in reset(cpu)
    assert keys(mem) == b'KRSTX'
    pocket = bytes(mem.banks[3][0x7FD0:0x7FE0])
    assert b'Done' in host.send(cpu,b'C 0 3 V A\rY\r')
    assert block(mem,2,10) == saved
    assert b'X registered' in reset(cpu)
    # AL corruption withdraws optional commands, keeps K and core recovery.
    mem.banks[2][0x2010+9] ^= 1
    out = reset(cpu)
    assert b'Autoload invalid' in out and keys(mem) == b'K'
    assert b'Bad cmd' in host.send(cpu,b'X\r')
    assert b'AUTO' in host.send(cpu,b'K AUTO ?\r') or b'Autoload' in mem.tx
    assert b'B0-3 D addr' in host.send(cpu,b'?\r')
    # The recovery editor can replace a damaged AL block explicitly.
    edit(cpu,'RESET')
    assert keys(mem) == b'K'
    reset(cpu)
    assert keys(mem) == b'KRST'
    edit(cpu,'CLEAR')
    out = reset(cpu)
    assert keys(mem) == b'K' and b'R registered' not in out
    edit(cpu,'+X')
    assert b'X registered' in reset(cpu) and keys(mem) == b'KX'
    # Repair by rewriting the CF sector through host fixture, not an implicit scan.
    mem.banks[2][0x2010:0x2050] = saved
    reset(cpu)
    before = [bytes(b) for b in mem.banks]
    mem.fault = 'timeout'
    out = host.send(cpu,b'K AUTO -X\rY\r')
    assert b'AUTO flash fail' in out and b'Done;' not in out, out
    assert mem.bank == 3 and not mem.busy
    mem.fault = None
    reset(cpu)
    # A sector erase/write fault may invalidate CF itself before AL is reached.
    assert b'Bad cmd' in host.send(cpu,b'X\r')
    assert all(bytes(mem.banks[b])==before[b] for b in (0,1,3))


def test_semantic_corruption_and_absent_config():
    cpu, mem = fresh()
    edit(cpu,'+X')
    saved = block(mem)
    assert mem.banks[3][0x500A] == 0xA1
    mem.banks[3][0x5010:0x5050] = b'\xff'*64
    out = reset(cpu)
    assert b'Autoload invalid' in out and keys(mem) == b'K'
    mem.banks[3][0x5010:0x5050] = saved
    for offset, value in ((9,2),(8,ord('K')),(20,ord('R')),(23,0x20),(5,1)):
        data = bytearray(saved)
        data[offset] = value
        data[62:] = checksum(data[:62])
        mem.banks[3][0x5010:0x5050] = data
        out = reset(cpu)
        assert b'Autoload invalid' in out and keys(mem) == b'K', (offset,out)
    mem.banks[3][0x5010:0x5050] = saved
    mem.banks[3][0x500E] ^= 1
    reset(cpu)
    assert b'Bad cmd' in host.send(cpu,b'X\r')
    assert b'K 02' in host.send(cpu,b'K\r')
    before = [bytes(b) for b in mem.banks]
    assert b'AUTO needs valid K config' in host.send(cpu,b'K AUTO +X\r')
    assert [bytes(b) for b in mem.banks] == before


def test_reset_before_application_and_missing_backing():
    cpu, mem = fresh()
    edit(cpu,'+X')
    # Application entry records that X already exists, then reenters the monitor.
    code = (b'\xad'+host.MGR['MG_COUNT'].to_bytes(2,'little')+b'\x8d\x00\x22\x4c'
            +host.boot.SYM['V2_REENTER'].to_bytes(2,'little'))
    mem.ram[0x2000:0x2000+len(code)] = code
    assert b'Done' in host.send(cpu,b'C 1 3 2000 A\rY\r')
    reset(cpu)
    assert mem.ram[0x2200] == 15 and keys(mem) == b'KRSTX'
    assert b'HELLO FROM X' in host.send(cpu,b'X HELLO\r')
    mem.banks[3][0x3240] ^= 1  # Authenticated autoload code, not only manager payload.
    reset(cpu)
    assert mem.ram[host.MGR['MG_READY']] == 0 and keys(mem) == b''
    assert b'B0-3 D addr' in host.send(cpu,b'?\r')


def main():
    checks = [test_selection_reset_and_messages, test_future_provider_and_invalid_inputs,
              test_integrity_cancel_fault_and_relocation,
              test_semantic_corruption_and_absent_config,
              test_reset_before_application_and_missing_backing]
    for check in checks:
        check()
        print('PASS:',check.__name__,flush=True)
    (host.firmware.OUT/'autoload-tests.json').write_text(json.dumps(dict(
        passed=[c.__name__ for c in checks], physical_hardware_tested=False,
        firmware_sha256=hashlib.sha256(host.boot.IMAGE).hexdigest(),
        provider_sha256=hashlib.sha256(HX).hexdigest()),indent=2)+'\n')


if __name__ == '__main__':
    main()
