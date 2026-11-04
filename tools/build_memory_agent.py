"""Build the standalone MEMORY1 RAM agent; does not access a device."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def expand_branches(source):
    """Use absolute destinations for every conditional; independent of layout."""
    opposite = {'BCC': 'BCS', 'BCS': 'BCC', 'BEQ': 'BNE', 'BNE': 'BEQ',
                'BMI': 'BPL', 'BPL': 'BMI', 'BVC': 'BVS', 'BVS': 'BVC'}
    rows = []
    for n, line in enumerate(source.splitlines()):
        m = re.fullmatch(r'\s*(BCC|BCS|BEQ|BNE|BMI|BPL|BVC|BVS|BRA)\s+(\w+)\s*', line)
        if m:
            op, target = m.groups()
            if op == 'BRA':
                rows.append('        JMP '+target)
            else:
                rows += ['        '+opposite[op]+' MB_LONG_'+str(n),
                         '        JMP '+target, 'MB_LONG_'+str(n)+':']
        else:
            rows.append(line)
    return '\n'.join(rows)+'\n'


def build(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out/'source'
    stage.mkdir()
    # Reuse the project's open-drain I2C primitives, not its managed-device
    # policy layer. All mutable symbols below are private to this RAM agent.
    rtc = (ROOT/'src/current/provider/rtc-provider.asm').read_text()
    init = rtc[rtc.index('INIT    LDA VORA'):rtc.index('        INCLUDE "i2c-transport.inc"')]
    bus = rtc[rtc.index('START_BUS JSR SDA_RELEASE'):rtc.index('\nBUSY EQU')]
    primitives = init+bus
    names = {'INIT': 'I2C_INIT', 'RESTORE': 'I2C_RESTORE', 'START_BUS': 'I2C_START',
             'STOP_BUS': 'I2C_STOP', 'WRITE_BYTE': 'I2C_WRITE', 'READ_BYTE': 'I2C_READ',
             'RTC_BUS_BUSY': '1', 'RTC_TIMEOUT': '3', 'RTC_NACK': '2'}
    for name, replacement in names.items():
        primitives = re.sub(r'\b'+name+r'\b', replacement, primitives)
    # Convert label+instruction lines to explicit colon syntax before expansion.
    primitives = re.sub(r'^(\w+)\s+((?:LDA|STA|STZ|JSR|JMP|LDX|LDY|PHA|PHY|PLY|CLC|SEC|RTS)\b)',
                        r'\1:\n        \2', primitives, flags=re.M)
    source = (ROOT/'firmware/memory-agent/agent.asm').read_text().replace(
        '        INCLUDE "i2c.inc"', primitives)
    base = ROOT/'release/str8nf-v0.2.0'
    freeze = json.loads((base/'F_FREEZE.json').read_text())
    foundation = (base/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert hashlib.sha256(foundation).hexdigest() == freeze['sha256']
    symbols = (base/'src/core/boot-symbols.inc').read_text()
    recovery = int(re.search(r'BOOT_RECOVERY EQU \$([0-9A-F]+)', symbols)[1], 16)
    source = source.replace('        CODE', f'RECOVERY_ENTRY EQU ${recovery:04X}\n        CODE', 1)
    (stage/'agent.asm').write_text(expand_branches(source))
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC02AS and WDCLN must be on PATH')
    logs = []
    for command in ([assembler, '-G', '-L', '-S', '-W', 'agent.asm'],
                    [linker, '-g', '-s', '-t', '-c6800', '-hm19', '-j', '-o', 'agent.s19', 'agent.obj']):
        result = subprocess.run(command, cwd=stage, capture_output=True, text=True)
        logs.append({'command': command, 'code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        (out/'build-log.json').write_text(json.dumps(logs, indent=2))
        if result.returncode:
            raise RuntimeError('Assembly failed; see '+str(out/'build-log.json'))
    memory = {}
    for line in (stage/'agent.s19').read_text().splitlines():
        if line.startswith('S1'):
            raw = bytes.fromhex(line[2:])
            assert len(raw) == raw[0]+1 and sum(raw)&255 == 255
            address = int.from_bytes(raw[1:3], 'big')
            memory.update(enumerate(raw[3:-1], address))
    assert min(memory) == 0x6800 and max(memory) < 0x7800
    body = bytes(memory[a] for a in range(0x6800, max(memory)+1))
    # Raw recovery L loads at 0200; relocate the padded agent before entry.
    pages = (len(body)+255)//256
    loader = bytearray.fromhex('78 D8 A2 00')
    for page in range(pages):
        loader += bytes((0xBD, 0, 3+page, 0x9D, 0, 0x68+page))
    loader += bytes((0xE8, 0xD0, (4-(len(loader)+3))&255, 0x4C, 0, 0x68))
    assert len(loader) <= 256
    image = bytes(loader).ljust(256, b'\xff')+body.ljust(pages*256, b'\xff')
    (out/'memory-agent.bin').write_bytes(image)
    (out/'agent-6800.bin').write_bytes(body)
    manifest = {'protocol': 1, 'component': 'STR8-N UTIL MEMORY', 'file': 'memory-agent.bin',
                'sha256': hashlib.sha256(image).hexdigest(), 'bytes': len(image),
                'agent_bytes': len(body), 'entry': '0200', 'resident': '6800-77FF',
                'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                'hardware_qualification': 'NOT RUN', 'F_writes': False,
                'foundation_sha256': freeze['sha256'], 'recovery_entry': recovery}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(parser.parse_args().out)
