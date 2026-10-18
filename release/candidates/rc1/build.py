#!/usr/bin/env python3
"""Build STR8-N 2.0rc1 generation 49 from this directory alone, using Python stdlib and WDC.

No historical BUILD tree, board receipt, binary input, emulator, Git, network,
or serial port is used. --out must be a new, short path for legacy WDC tools.
"""
import argparse
import binascii
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SR_CALLS = ('V2_HEX_WORD', 'V2_HEX_BYTE', 'V2_SKIP_SPACES', 'V2_PRINT_ADDR',
            'V2_PUTC', 'V2_HEX_OUT', 'V2_NEWLINE', 'V2_BAD_HEX',
            'V2_BAD_RANGE', 'V2_PROTECTED', 'V2_PROMPT', 'V2_MESSAGE',
            'V2_FLASH_FAILED', 'V2_FLASH_DONE', 'V2_CONFIRM', 'V2_PRINT',
            'V2_READ_LINE', 'V2_CHECK_CANCEL', 'V2_CANCELLED')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc(data):
    return binascii.crc_hqx(data, 0xffff)


def sealed(data, size):
    if len(data) > size-2:
        raise ValueError(f'{len(data)} bytes exceed {size}-byte sealed region')
    data = data+b'\xff'*(size-2-len(data))
    result = data+crc(data).to_bytes(2, 'big')
    assert crc(result) == 0
    return result


def db(path, data, label=''):
    path.write_text(label+''.join(' DB '+','.join(f'${b:02X}' for b in data[i:i+16])+'\n'
                                 for i in range(0, len(data), 16)), encoding='ascii')


def record(kind, address, data=b''):
    raw = bytes([len(data)+3])+address.to_bytes(2, 'big')+data
    return 'S'+kind+(raw+bytes([255-(sum(raw)&255)])).hex().upper()


def s19(data, address, entry):
    # Preserve the established serialization, including its historical S0 label.
    lines = [record('0', 0, b'STR8-N 2.0b4 exact source migration')]
    lines += [record('1', address+i, data[i:i+32]) for i in range(0, len(data), 32)]
    return ('\n'.join(lines+[record('9', entry)])+'\n').encode('ascii')


def read_s19(path):
    cells = {}
    for line in path.read_text(encoding='ascii').splitlines():
        if not line:
            continue
        if not re.fullmatch(r'S[019][0-9A-Fa-f]+', line):
            raise ValueError(f'Unsupported S-record: {path}')
        raw = bytes.fromhex(line[2:])
        if len(raw) != raw[0]+1 or sum(raw)&255 != 255:
            raise ValueError(f'Invalid S-record count/checksum: {path}')
        if line[1] == '1':
            for a, v in enumerate(raw[3:-1], int.from_bytes(raw[1:3], 'big')):
                if a in cells:
                    raise ValueError(f'Overlapping S-record: {path}')
                cells[a] = v
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--assembler', default=shutil.which('wdc02as'))
    parser.add_argument('--linker', default=shutil.which('wdcln'))
    args = parser.parse_args()
    if not args.assembler or not args.linker:
        parser.error('Install WDC02AS and WDCLN separately and put them on PATH')
    out = args.out.resolve()
    if out.exists():
        parser.error('--out must be a new directory (no reuse of stale outputs)')
    if len(str(out)) > 70:
        parser.error('Use a short --out path; legacy WDC tools fail on long paths')
    meta = json.loads((HERE/'release.json').read_text())
    provenance = json.loads((HERE/'source-provenance.json').read_text())
    if {p.relative_to(HERE).as_posix() for p in (HERE/'source').rglob('*') if p.is_file()} != set(provenance):
        raise ValueError('Source inventory differs from the frozen source manifest')
    for name, info in provenance.items():
        if sha((HERE/name).read_bytes()) != info['sha256']:
            raise ValueError(f'Frozen source changed: {name}')
    out.mkdir(parents=True)
    shutil.copytree(HERE/'source', out/'s')
    payload = out/'payload'
    payload.mkdir()
    symbols = {}
    compiled = []

    def assemble(module, name, address, end):
        stage = out/'s'/module
        log = []
        commands = [[args.assembler, '-G', '-L', '-S', '-W', '-I', str(stage), name+'.asm'],
                    [args.linker, '-g', '-s', '-t', f'-c{address:04X}', '-hm19', '-j',
                     '-o', name+'.s19', name+'.obj']]
        for command in commands:
            result = subprocess.run(command, cwd=stage, capture_output=True, text=True)
            log.append({'command': command, 'returncode': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr})
            (stage/(name+'.log.json')).write_text(json.dumps(log, indent=2)+'\n')
            if result.returncode:
                raise RuntimeError(f'WDC failed: {module}/{name}; see {stage/(name+".log.json")}')
        sy = {n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
                                               (stage/(name+'.map')).read_text(), re.M)}
        cells = read_s19(stage/(name+'.s19'))
        stop = sy[end]
        if set(cells) != set(range(address, stop)):
            raise ValueError(f'Non-contiguous or out-of-range link: {module}/{name}')
        body = bytes(cells[a] for a in range(address, stop))
        symbols[module+'/'+name] = sy
        compiled.append({'module':module, 'name':name, 'start':address, 'end':stop,
                         'bytes':len(body), 'sha256':sha(body)})
        print(f'{module}/{name}: {len(body)} bytes', flush=True)
        return body, sy

    def emit(name, data):
        path = payload/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    # Embedded executable images are derived exclusively from these fresh links.
    worker, ws = assemble('core', 'str8n-v2-worker', 0x7800, 'V2W_END')
    vectors, vs = assemble('core', 'str8n-v2-vectors', 0x7E20, 'V2V_END')
    db(out/'s/core/worker-image.inc', worker)
    db(out/'s/core/vectors-image.inc', vectors)
    messages = json.loads((out/'s/core/text.json').read_text())
    first = next(i for i,m in enumerate(messages) if m['name'] == 'V2_BAD_PREFIX')
    pool = bytearray()
    for i,m in enumerate(messages):
        raw = bytearray(m['text'].replace('{version}', meta['version']).encode('ascii'))
        if i < first:
            raw = raw[4:]
        raw[-1] |= 128
        pool.extend(raw)
    db(out/'s/core/text-image.inc', pool, 'V2_TEXT:\n')
    boot, bs = assemble('core', 'str8n-v2-boot', 0xF000, 'BOOT_END')
    f = bytearray(b'\xff'*4096)
    f[:len(boot)] = boot
    for a,n in {0xFFE4:'V2V_NATIVE_COP', 0xFFE6:'V2V_NATIVE_BRK',
                0xFFE8:'V2V_NATIVE_ABORT', 0xFFEA:'V2V_NATIVE_NMI',
                0xFFEE:'V2V_NATIVE_IRQ', 0xFFF4:'V2V_COP', 0xFFF8:'V2V_ABORT',
                0xFFFA:'V2V_NMI', 0xFFFE:'V2V_IRQ_BRK'}.items():
        f[a-0xF000:a-0xF000+2] = vs[n].to_bytes(2, 'little')
    f[0xFFC:0xFFE] = (0xF004).to_bytes(2,'little')
    compat_offset = bs['BOOT_COMPAT_DATA']-0xF000
    f[compat_offset:compat_offset+4] = meta['boot_compatibility'].to_bytes(4,'little')
    emit('str8n-v2-recovery-f000-ffff.bin', f)

    app, aps = assemble('assembler', 'asm-app', 0xE000, 'APP_END')
    app = bytearray(app)
    app[4:6] = len(app).to_bytes(2,'little')
    app[14:16] = crc(app[:14]).to_bytes(2,'little')
    emit('assembler/asm-e000.bin', app)
    appvectors = bytearray(b'\xff'*4096)
    appvectors[:len(app)-4096] = app[4096:]
    appvectors[-32:] = f[-32:]
    appvectors[-4:-2] = (0x7E67).to_bytes(2,'little')
    emit('assembler/vectors-f000.bin', appvectors)

    sr, ss = assemble('core', 'str8n-v2-sr', 0xE800, 'SR_END')
    launcher, ls = assemble('core', 'launcher', 0xE000, 'AP_END')
    mode, _ = assemble('mode', 'status-mode-init', 0xEE92, 'AUX_END')
    loader, _ = assemble('loader', 'version-loader', 0xEF00, 'AUX_END')
    e = bytearray(b'\xff'*4096)
    e[:len(launcher)] = launcher
    e[0x800:0x800+len(sr)] = sr
    e[0xE92:0xE92+len(mode)] = mode
    e[0xF00:0xF00+len(loader)] = loader
    # The launcher ABI descriptor follows code, before the app directory.
    e[0x6E0:0x6E8] = b'MP\x01\x08'+(0xE011).to_bytes(2,'little')+(0x7D90).to_bytes(2,'little')
    ap_list = ls['AP_LIST']-0xE000
    e[ap_list:ap_list+5] = bytes.fromhex('A9084C09EF')
    row = bytearray(32)
    row[:3] = b'ASM'
    row[12:14] = bytes([1,1])
    for offset,value in [(14,0xE000),(16,len(app)),(18,0xE010),(20,0x0200),(22,0x64FF)]:
        row[offset:offset+2] = value.to_bytes(2,'little')
    row[24:26] = bytes([0,0x3F])
    row[26:28] = crc(app).to_bytes(2,'little')
    row[30] = 0x3F
    row[28:30] = crc(row[:28]+row[30:]).to_bytes(2,'little')
    e[0x6F0:0x6F4] = b'AT\x01\x08'
    e[0x6F4:0x7F4] = row+bytes(224)
    e[0x7F4:0x7FD] = b'\r\nAPPS\r\n\0'
    e[0x7FE:0x800] = crc(e[:0x7FE]).to_bytes(2,'big')
    e[-2:] = crc(e[:-2]).to_bytes(2,'big')
    emit('str8n-v2-recovery-e000-efff.bin', e)

    batch,_ = assemble('batch','batch-gate',0x7C90,'B29_GATE_END')
    db(out/'s/core/batch-gate.inc',batch+b'\xEA'*(96-len(batch)))
    monitor, ms = assemble('core', 'monitor-b0', 0xB080, 'V2_END')
    slot = bytearray(b'\xff'*4096)
    slot[:8] = b'MI\x01\xB0\x03\x01\0\0'
    slot[8:12] = meta['generation'].to_bytes(4,'little')
    for offset,value in [(12,len(monitor)),(14,ms['START']),(16,ms['V2_PROMPT_ENTRY'])]:
        slot[offset:offset+2] = value.to_bytes(2,'little')
    slot[20:24] = meta['boot_compatibility'].to_bytes(4,'little')
    for i,name in enumerate(SR_CALLS):
        slot[32+2*i:34+2*i] = ms[name].to_bytes(2,'little')
    slot[70:72] = ms['V2_M_EDIT'].to_bytes(2,'little')
    slot[128:128+len(monitor)] = monitor
    slot[18:20] = crc(slot[:18]+slot[32:]).to_bytes(2,'little')
    slot[31] = 0
    emit('str8n-v2-recovery-slot-b0.bin', slot)
    a_source = (out/'s/core/monitor-b0.asm').read_text()
    require_count = a_source.count('V2_IMAGE_PAGE EQU $B0')
    assert require_count == 1
    (out/'s/core/monitor-a0.asm').write_text(a_source.replace('V2_IMAGE_PAGE EQU $B0','V2_IMAGE_PAGE EQU $A0',1))
    amonitor, ams = assemble('core','monitor-a0',0xA080,'V2_END')
    assert len(amonitor) <= 3968 and len(monitor) <= 3968
    aslot = bytearray(b'\xff'*4096)
    aslot[:8] = b'MI\x01\xA0\x03\x01\0\0'
    aslot[8:12] = meta['generation'].to_bytes(4,'little')
    for offset,value in [(12,len(amonitor)),(14,ams['START']),(16,ams['V2_PROMPT_ENTRY'])]:
        aslot[offset:offset+2] = value.to_bytes(2,'little')
    aslot[20:24] = meta['boot_compatibility'].to_bytes(4,'little')
    for i,name in enumerate(SR_CALLS):
        aslot[32+2*i:34+2*i] = ams[name].to_bytes(2,'little')
    aslot[70:72] = ams['V2_M_EDIT'].to_bytes(2,'little')
    aslot[128:128+len(amonitor)] = amonitor
    aslot[18:20] = crc(aslot[:18]+aslot[32:]).to_bytes(2,'little')
    aslot[31] = 0
    emit('str8n-v2-recovery-slot-a0.bin', aslot)


    provider, _ = assemble('provider', 'rtc-provider', 0x8000, 'SERVICE_END')
    gate, gs = assemble('gateway', 'rtc-gateway', 0x6500, 'GATE_END')
    banner, _ = assemble('banner', 'rtc-banner', 0x8900, 'BANNER_END')
    gateway = bytearray(512)
    gateway[:len(gate)] = gate
    gateway[0x146:0x14D] = bytes.fromhex('535001014CB866')
    gateway[0x1A2:0x1AE] = bytes.fromhex('534D01014CA966A2064C')+gs['ENTER'].to_bytes(2,'little')
    gateway[0x1AE:0x1B0] = b'\x01\0'
    gateway[0x1B0:0x1B8] = bytes.fromhex('AD0000608D000060')
    gateway[0x1B8:0x1BD] = b'\xA2\x05\x4C'+gs['ENTER'].to_bytes(2,'little')
    component = bytearray(b'\xff'*4096)
    component[:len(provider)+2] = provider+crc(provider).to_bytes(2,'big')
    component[0x900:0x900+len(banner)] = banner
    component[0xDF0:0xFF0] = gateway
    component[-2:] = crc(component[:-2]).to_bytes(2,'big')
    emit('str8n-rtc-component-8000-8fff.bin', component)
    journal, _ = assemble('journal', 'journal', 0x9000, 'JOURNAL_END')
    emit('str8n-journal-9000-9fff.bin', sealed(journal,3072)+b'\xff'*1024)

    for module,name,address,end,size,target in [
        ('status','storage-status',0x6E00,'APP_END',2560,'boot-status/asset.bin'),
        ('battery','battery',0x6E00,'APP_END',2560,'battery/asset.bin'),
        ('local','local-display',0x6700,'APP_END',1792,'local-display/asset.bin'),
        ('pf','pf',0x6700,'APP_END',768,'pf-worker/asset.bin')]:
        body,_ = assemble(module,name,address,end)
        emit(target, sealed(body,size))
    version,_ = assemble('version','version',0x6E00,'APP_END')
    version = bytearray(sealed(version,2048))
    version[0x300:0x600] = (payload/'pf-worker/asset.bin').read_bytes()
    version[-8:] = b'\xff\xff'+b''.join(vs[n].to_bytes(2,'little') for n in
                                        ('V2V_NMI','V2V_RAM_RESET_ENTRY','V2V_IRQ_BRK'))
    seed = crc(version[:-10])
    for word in range(65536):
        patch = word.to_bytes(2,'big')
        if binascii.crc_hqx(patch+version[-8:],seed) == 0:
            version[-10:-8] = patch
            break
    else:
        raise ValueError('VERSION seal patch unavailable')
    emit('version/asset.bin', version)

    gate,_ = assemble('xip','gate',0x7B90,'G_END')
    stub,_ = assemble('xip','work-stub',0x5000,'STUB_END')
    db(out/'s/xip/gate-image.inc',gate)
    db(out/'s/xip/work-stub.inc',stub+b'\xff'*(64-len(stub)))
    utilities,_ = assemble('xip','utilities',0x8000,'X28_END')
    emit('xip/utilities.bin',sealed(utilities,0x5800))
    clock,_ = assemble('clock','clock',0x2000,'APP_END')
    emit('clock/clock.bin',clock)
    emit('clock/clock.s19',s19(clock,0x2000,0x2000))
    storage = b'SR\x01\x3F\x00\x20'+len(clock).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+clock
    emit('clock/storage.bin',storage+b'\xff'*(12288-len(storage)))

    # Source-built migration/provisioning templates, never an installation plan.
    config = bytearray([1,0,3,7,0xF0,10,0]+[0]*9)
    a = b = 0
    for value in config[:14]:
        a = (a+value)&255
        b = (b+a)&255
    config[14:] = bytes([a,b])
    initial = bytearray(b'\xff'*128)
    initial[:8] = b'WC\x01\0\x01\0\0\0'
    initial[8:24] = config
    initial[24:120] = bytes(96)
    initial[120:122] = crc(initial[:120]).to_bytes(2,'little')
    initial[127] = 0
    db(out/'s/bootstrap/initial-record.inc',initial,'INITIAL_RECORD:\n')
    bootstrap,_ = assemble('bootstrap','bootstrap-journal',0x2000,'APP_END')
    emit('bootstrap/bootstrap-journal.bin',bootstrap)
    mw,_ = assemble('migration','migration-worker',0x7800,'V2W_END')
    db(out/'s/migration/migration-worker-image.inc',mw)
    db(out/'s/migration/migration-table.inc',b'\xff'*(16*9))
    migration,_ = assemble('migration','rtc-migrator',0x2000,'MIG_END')
    emit('migrator/rtc-migrator-2000.s19',s19(migration,0x2000,0x2000))

    actual = {p.relative_to(payload).as_posix(): {'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
              for p in sorted(payload.rglob('*')) if p.is_file()}
    comparison = {name:{'expected':info,'actual':actual.get(name),'match':actual.get(name)==info}
                  for name,info in meta['baseline_expected'].items()}
    passed = set(actual)==set(meta['baseline_expected'])|{'str8n-v2-recovery-slot-a0.bin'} and all(row['match'] or name in meta['expected_changed'] for name,row in comparison.items())
    report = {'version':meta['version'],'generation':meta['generation'],
              'source_only':True,'binary_inputs':[], 'compiled':compiled,
              'build_script_sha256':sha(Path(__file__).read_bytes()),
              'release_manifest_sha256':sha((HERE/'release.json').read_bytes()),
              'source_files':{n:i['sha256'] for n,i in provenance.items()},
              'toolchain':{str(Path(t).resolve()):sha(Path(t).read_bytes()) for t in (args.assembler,args.linker)},
              'comparison':comparison,'passed':passed,'artifacts':actual,
              'candidate_id':meta['candidate_id'],'expected_changed':meta['expected_changed'],
              'installation_permitted':False, 'deferred':meta['deferred']}
    (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'symbols.json').write_text(json.dumps(symbols,indent=2)+'\n')
    if not passed:
        raise ValueError('Payload comparison failed: '+', '.join(n for n,r in comparison.items() if not r['match']))
    print(f'PASS: {len(compiled)} fresh links, {len(actual)} candidate artifacts; pinned rc1 payload comparison passed, generation 49. No board access.',flush=True)


if __name__ == '__main__':
    main()
