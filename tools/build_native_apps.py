"""Build CLOCK and FLASH/MAINT overlays above frozen BASE1; no device access."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build import cells, db
from mona_branches import conservative_branches

ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()
crc = lambda b: binascii.crc_hqx(b, 65535)


def normalized(text):
    """Convert WDC's old column-zero labels to the explicit current spelling."""
    result = []
    for row in text.splitlines():
        if row and not row[0].isspace() and not row.startswith(';'):
            m = re.match(r'^(\w+)(?:\s+(.*))?$', row)
            if m and not re.match(r'^(EQU|SET)\b', m[2] or '', re.I):
                row = m[1]+':'+(' '+m[2] if m[2] else '')
        result.append(row)
    return '\n'.join(result)+'\n'


def sealed(body, size):
    if len(body) > size-2:
        raise ValueError(f'{len(body)} linked bytes exceed {size-2} byte budget')
    data = body.ljust(size-2, b'\xff')
    data += crc(data).to_bytes(2, 'big')
    assert crc(data) == 0
    return data


def build(out, reuse_from=None):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Fresh output directory required')
    freeze = json.loads((ROOT/'F_FREEZE.json').read_text())
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == freeze['sha256']
    for name, digest in freeze['sources'].items():
        assert sha((ROOT/name).read_bytes()) == digest, name
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise RuntimeError('WDC assembler/linker required')
    out.mkdir(parents=True)
    sources = {}
    for folder in ('src/core', 'src/include', 'monitors/native'):
        for p in (ROOT/folder).iterdir():
            if p.suffix not in ('.asm', '.inc'):
                continue
            # The public include copies agree; core has the worker symbol pin.
            target = out/p.name
            if target.exists() and folder == 'src/include' and '../include/' not in target.read_text():
                continue
            sources[p.relative_to(ROOT).as_posix()] = sha(p.read_bytes())
            target.write_text(p.read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    shutil.copyfile(ROOT/'monitors/src/batch-interface.inc', out/'batch-interface.inc')
    sources['monitors/src/batch-interface.inc'] = sha((ROOT/'monitors/src/batch-interface.inc').read_bytes())
    shutil.copyfile(ROOT/'monitors/src/monitor-ui.inc', out/'monitor-ui.inc')
    sources['monitors/src/monitor-ui.inc'] = sha((ROOT/'monitors/src/monitor-ui.inc').read_bytes())
    ui = (ROOT/'monitors/src/workbench-monitor-ui.inc').read_text()
    ui = ui[ui.index('W_UI_EXPECTED EQU'):ui.index('W_UI_ERROR:')]
    # The caller wrapper/error path are workbench-only; admission is shared.
    a, b = ui.index('W_UI_CALL:'), ui.index('W_UI_CHECK:')
    ui = ui[:a]+ui[b:]
    # Native CLOCK owns gateway code through6645; its UI scratch belongs in
    # the reserved5B context, while WB continues using its own6630 state.
    ui = re.sub(r'EQU \$663([0-8])', r'EQU $5B1\1', ui)
    (out/'native-ui-check.inc').write_text(ui)
    sources['monitors/src/workbench-monitor-ui.inc'] = sha((ROOT/'monitors/src/workbench-monitor-ui.inc').read_bytes())

    config = (ROOT/'src/core/ram-config.asm').read_text()
    config = config.split('        CODE\n', 1)[1].split('        INCLUDE "config-engine.inc"')[0]
    a, b = config.index('CONFIG_MENU:'), config.index('        LDA V2_LINE\n')
    config = config[:a]+'CONFIG_MENU:\n        JMP FT_MENU\nCONFIG_DISPATCH:\n'+config[b:]
    config = config.replace('JMP $F004', 'JMP $5E00')
    config = config.replace('Restart through F using the saved default', 'Return to the monitor')
    config = config.replace('CONFIG_BAD:\n','CONFIG_BAD:\n        LDA #2\n        STA $5DF5\n').replace('CONFIG_FAILED:\n','CONFIG_FAILED:\n        LDA #2\n        STA $5DF5\n')
    (out/'board-config.inc').write_text(config)
    opaque = (ROOT/'src/core/ram-installer.asm').read_text()
    opaque = opaque.split('        CODE\n', 1)[1].split('        INCLUDE "prototype-engine.inc"')[0]
    opaque = re.sub(r'^OI_(PTR|STAGE) EQU.*\n', '', opaque, flags=re.M)
    opaque = opaque.replace('JMP BOOT_RECOVERY', 'JMP FT_HOST_QUIT')
    # OIP1 remains its own wire prompt. Native operations share only the writer.
    opaque = opaque.replace('        JSR V2W_RX_RESET\n        JSR BOOT_PRINT\n        JMP INSTALLER_MENU',
        '        JSR V2W_RX_RESET\n        LDA #1\n        STA V2_LED\n        JSR BOOT_PRINT\n        JMP FT_OIP_FINISH')
    (out/'board-opaque.inc').write_text(opaque)
    engine = (out/'config-engine.inc').read_text()
    engine = engine.replace('CONFIG_NOT_BANK:\n',
        'CONFIG_NOT_BANK:\n        LDA JE_MODE\n        CMP #7\n        BNE FT_ENGINE_DEFAULT\n        JMP FT_BOOT_APPLY\nFT_ENGINE_DEFAULT:\n')
    (out/'config-engine.inc').write_text(engine)
    for name in ('ram-config.asm','ram-installer.asm','config-engine.inc'):
        sources['src/core/'+name] = sha((ROOT/'src/core'/name).read_bytes())

    for p in out.glob('*.inc'):
        text, _ = conservative_branches(normalized(p.read_text()), 'NI_'+re.sub(r'\W', '_', p.name)+'_')
        p.write_text(text, encoding='utf-8', newline='\n')
    logs, linked = [], {}
    def link(name, origin, end):
        p = out/(name+'.asm')
        text = re.sub(r'^\s*XDEF\s+.*$', '', p.read_text(), flags=re.M)
        body, branches = conservative_branches(normalized(text), name.upper().replace('-', '_')+'_LONG_')
        p.write_text(body, encoding='utf-8', newline='\n')
        reused = False
        prior = Path(reuse_from).resolve() if reuse_from else None
        if prior and (prior/(name+'.map')).exists() and (prior/(name+'.s19')).exists():
            def same_tree(filename, seen=None):
                seen = set() if seen is None else seen
                if filename in seen:
                    return True
                seen.add(filename)
                current, old = out/filename, prior/filename
                if not old.exists() or current.read_bytes() != old.read_bytes():
                    return False
                return all(same_tree(n, seen) for n in re.findall(r'INCLUDE\s+"([^"]+)"', current.read_text(), re.I))
            if same_tree(name+'.asm'):
                shutil.copyfile(prior/(name+'.map'), out/(name+'.map'))
                shutil.copyfile(prior/(name+'.s19'), out/(name+'.s19'))
                reused = True
        commands = [] if reused else ([assembler, '-G', '-L', '-S', '-W', name+'.asm'],
                    [linker, '-g', '-s', '-t', f'-c{origin:04X}', '-hm19', '-j', '-o', name+'.s19', name+'.obj'])
        for cmd in commands:
            done = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
            logs.append(dict(command=cmd, returncode=done.returncode, stdout=done.stdout, stderr=done.stderr))
            (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n')
            if done.returncode:
                raise RuntimeError('Build failed: '+str(out/'build-log.json'))
        sy = {n:int(v, 16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (out/(name+'.map')).read_text(), re.M)}
        memory = cells(out/(name+'.s19'))
        assert set(memory) == set(range(origin, sy[end])), name
        raw = bytes(memory[a] for a in range(origin, sy[end]))
        linked[name] = dict(origin=f'{origin:04X}', end=f'{sy[end]:04X}', bytes=len(raw), branches=branches,
                           reused_from=str(prior) if reused else None)
        print(name, len(raw), 'linked bytes', flush=True)
        return raw, sy

    provider, ps = link('rtc-provider', 0x8000, 'SERVICE_END')
    provider = sealed(provider, len(provider)+2)
    assert len(provider) <= 0xA00
    (out/'split-defs.inc').write_text(f'PROVIDER_SIZE EQU ${len(provider):04X}\nPROVIDER_BASE EQU $8000\nPROVIDER_BITS EQU $EE\nPRIVATE_BASE EQU $6669\nPRIVATE_SIZE EQU 57\n')
    reader, brs = link('batch-reader', 0x8900, 'BR_END_CODE')
    reader = sealed(reader,256)
    assert len(provider) <= 0x900
    gate, gs = link('rtc-gateway', 0x6500, 'GATE_END')
    assert gs['GATE_END'] <= 0x6660, 'Gateway code overlaps mutable private state'
    gate = sealed(gate, 512)
    (out/'journal-transport.inc').write_text(f'EE_TRANSFER EQU ${ps["EE_TRANSFER"]:04X}\nTRIM_CONTROL EQU ${ps["TRIM_CONTROL"]:04X}\nBIND_FLASH_BYTE EQU $7B64\n')
    journal, js = link('journal', 0x9000, 'JOURNAL_END')
    ret, rs = link('native-return', 0x5E00, 'NR_END')
    assert len(ret) <= 512
    assert len(ret) <= 510 and len(journal) <= 0xA00
    # Last two return-padding bytes are the history-code CRC, never executed.
    journal_sector = sealed(journal.ljust(0xA00,b'\xff')+ret.ljust(510,b'\xff'),3072)+b'\xff'*1024
    db(out/'native-return-image.inc', ret.ljust(512, b'\xff'))
    (out/'native-api.inc').write_text(f'NR_CALL EQU ${rs["NR_CALL"]:04X}\n')
    loader, ls = link('native-loader', 0x7000, 'NL_END')
    loader = sealed(loader, 1024)
    rtc_sector = provider.ljust(0x900, b'\xff')+reader+gate+loader
    assert len(rtc_sector) == 4096
    clock, cs = link('clock', 0x2000, 'APP_END')
    board, bs = link('board-tool', 0x2000, 'BOARD_END')
    assert cs['APP_END'] < 0x5B00 and bs['BOARD_END'] < 0x5B00

    artifacts = {}
    def emit(name, body, **metadata):
        (out/name).write_bytes(body)
        artifacts[name] = dict(bytes=len(body), sha256=sha(body), **metadata)
    def app(name, body, kind, sectors):
        h = bytearray(b'\xff'*32)
        h[:8] = b'RP'+bytes((1,kind))+b'PR05'
        h[8:10] = len(body).to_bytes(2,'little')
        h[10:12] = (0x2000).to_bytes(2,'little')
        h[12:14] = (0x2000).to_bytes(2,'little')
        h[14:18] = (1).to_bytes(4,'little')
        packed = sealed(bytes(h)+body, sectors*4096)
        emit(name+'-flash.bin', packed, sectors=sectors, RAM='2000-'+f'{0x2000+len(body)-1:04X}', linked_bytes=len(body), free_bytes=len(packed)-34-len(body))
        emit(name+'-RAM.bin', body, entry='2000', requires='admitted native-loader context; raw entry alone is not self-contained')
    app('CLOCK-g00000001', clock, 0, 3)
    app('FLASH-MAINT-g00000001', board, 1, 2)
    emit('RTC-BASE1-B3-8000.bin', rtc_sector, allocation='B3:8; provider + gateway + loader')
    emit('RTC-HISTORY-B3-9000.bin', journal_sector, allocation='B3:9; first 3072 bytes code/seal; final 1024 bytes target-owned metadata')
    report = dict(schema=1, status='BUILD_ONLY_NOT_EXECUTION_QUALIFIED', F_sha256=freeze['sha256'], F_rebuilt=False,
                  hardware_access=False, CPU_simulations=0, source_sha256=sources, linked=linked, artifacts=artifacts,
                  allocation=['B2:B/C/D CLOCK','B2:E/F FLASH/MAINT','B3:8 RTC/gateway/loader','B3:9 history/code + target metadata'],
                  overlay_RAM=['2000-5AFF code/state','5B00 CRC scratch','5C00 owner ZP escrow','5D00 monitor session escrow','5E00-5FFF return code',
                               '6500-66FF RTC gateway/state','6700 boot/wear snapshot','6800-77FF FLASH sector buffer OR RTC/history scratch'],
                  preservation='Runtime overlays deliberately borrow declared RAM; return restores 00-DF and MON session, invalidates WB cache',
                  RTC='b35 SET/status/EUI/trim/history/offset/battery behavior; no RTC changes during build',
                  protected_flash=['B3:C','B3:D','B3:F'], factory_restore='Separate reviewed host workflow; never bypass normal FLASH guards',
                  build_passes=1, assembler_linker_invocations=len(logs))
    (out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({n:{k:v for k,v in a.items() if k in ('bytes','linked_bytes','free_bytes')} for n,a in artifacts.items()}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reuse-from', type=Path)
    args = parser.parse_args()
    build(args.out, args.reuse_from)
